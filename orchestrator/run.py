"""Top-level orchestrator: parallel build → test → debugger swarm loop.

Phase 1 (build): N builders run in parallel, each in its own fork seeded
with the task's test files. Tests run against each fork. If any fork
passes, we're done.

Phase 2 (debug): If no builder fork passes, pick the closest-to-passing
fork as the canonical workspace and start a debugger-swarm loop. Each
round runs M debuggers in parallel; after they finish, the orchestrator
runs tests against each debugger fork and overwrites that debugger's
memory entry with the *real* outcome (debuggers can self-report wrong).
The best fork becomes the canonical for the next round. Loop until pass
or `max_debug_rounds`.
"""

from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from agents.builder import BuilderAgent, TaskSpec
from memory.store import SharedMemory
from orchestrator.swarm import fork_workspace, run_debugger_swarm
from runner.tests import TestResult, run_tests


@dataclass
class FullTaskSpec:
    task_id: str
    description: str
    test_files: dict[str, str]


@dataclass
class OrchestratorResult:
    success: bool
    canonical_workspace: Path
    rounds_used: int
    builder_summaries: list[str]
    debugger_rounds: list[list[str]] = field(default_factory=list)
    final_test_output: str = ""
    total_cost_usd: float = 0.0


def _count_failures(tr: TestResult) -> int:
    if tr.success:
        return 0
    m = re.search(r"(\d+) failed", tr.stdout)
    return int(m.group(1)) if m else 10**6


def _seed_workspace(seed: Path, test_files: dict[str, str]) -> None:
    seed.mkdir(parents=True, exist_ok=True)
    for fname, content in test_files.items():
        (seed / fname).write_text(content)


async def run_orchestrator(
    spec: FullTaskSpec,
    run_dir: Path,
    num_builders: int = 2,
    num_debuggers: int = 2,
    max_debug_rounds: int = 3,
    python_executable: str | None = None,
) -> OrchestratorResult:
    run_dir = Path(run_dir)
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    seed = run_dir / "_seed"
    _seed_workspace(seed, spec.test_files)

    # PHASE 1: builders ----------------------------------------------------
    builder_forks_root = run_dir / "_builder_forks"
    builder_forks_root.mkdir()
    builder_workspaces = [
        fork_workspace(seed, builder_forks_root / f"builder-{i + 1}")
        for i in range(num_builders)
    ]
    builders = [
        BuilderAgent(
            agent_id=f"builder-{i + 1}",
            spec=TaskSpec(
                task_id=spec.task_id,
                description=spec.description,
                workspace=builder_workspaces[i],
            ),
        )
        for i in range(num_builders)
    ]
    builder_results = await asyncio.gather(*[b.run() for b in builders])
    total_cost = sum((r.cost_usd or 0.0) for r in builder_results)
    builder_summaries = [r.summary for r in builder_results]

    builder_tests = [
        run_tests(ws, python_executable=python_executable) for ws in builder_workspaces
    ]
    for i, tr in enumerate(builder_tests):
        verdict = "PASS" if tr.success else f"FAIL ({_count_failures(tr)} failed)"
        print(f"[orch] builder-{i + 1}: {verdict}")

    # If any builder fork already passes, we're done.
    for i, tr in enumerate(builder_tests):
        if tr.success:
            return OrchestratorResult(
                success=True,
                canonical_workspace=builder_workspaces[i],
                rounds_used=0,
                builder_summaries=builder_summaries,
                total_cost_usd=total_cost,
            )

    # Pick closest-to-passing as the canonical for debugging.
    best_idx = min(range(num_builders), key=lambda i: _count_failures(builder_tests[i]))
    canonical = run_dir / "_canonical"
    fork_workspace(builder_workspaces[best_idx], canonical)
    print(f"[orch] no builder passed; promoting builder-{best_idx + 1} to canonical")

    # PHASE 2: debugger rounds --------------------------------------------
    memory = SharedMemory(run_dir / "memory.json", task_id=spec.task_id)
    debugger_rounds_summaries: list[list[str]] = []
    final_test_output = ""

    for round_num in range(1, max_debug_rounds + 1):
        canonical_test = run_tests(canonical, python_executable=python_executable)
        if canonical_test.success:
            break

        print(f"[orch] === debug round {round_num} ===")
        debug_forks_root = run_dir / f"_debug_round_{round_num}"
        swarm = await run_debugger_swarm(
            workspace=canonical,
            failure_output=canonical_test.failure_output,
            memory=memory,
            num_debuggers=num_debuggers,
            forks_root=debug_forks_root,
        )

        round_summaries: list[str] = []
        round_tests: list[TestResult] = []
        for sa in swarm.attempts:
            r = sa.debugger_result
            total_cost += r.cost_usd or 0.0
            round_summaries.append(f"{r.agent_id}: {r.summary[:150]}")

            tr = run_tests(sa.workspace, python_executable=python_executable)
            round_tests.append(tr)
            verdict = "PASS" if tr.success else f"FAIL ({_count_failures(tr)} failed)"
            print(f"[orch] {r.agent_id}: {verdict}")

            attempt = memory.find_latest_attempt_by_agent(r.agent_id)
            if attempt is not None:
                memory.record_result(
                    attempt.attempt_id,
                    success=tr.success,
                    detail=(
                        "tests pass"
                        if tr.success
                        else tr.failure_output[:500]
                    ),
                )

        debugger_rounds_summaries.append(round_summaries)

        winner_idx = next(
            (i for i, tr in enumerate(round_tests) if tr.success), None
        )
        if winner_idx is not None:
            winner_ws = swarm.attempts[winner_idx].workspace
            return OrchestratorResult(
                success=True,
                canonical_workspace=winner_ws,
                rounds_used=round_num,
                builder_summaries=builder_summaries,
                debugger_rounds=debugger_rounds_summaries,
                total_cost_usd=total_cost,
            )

        best_round_idx = min(
            range(len(round_tests)), key=lambda i: _count_failures(round_tests[i])
        )
        new_canonical_src = swarm.attempts[best_round_idx].workspace
        if canonical.exists():
            shutil.rmtree(canonical)
        shutil.copytree(new_canonical_src, canonical)
        final_test_output = round_tests[best_round_idx].failure_output

    return OrchestratorResult(
        success=False,
        canonical_workspace=canonical,
        rounds_used=max_debug_rounds,
        builder_summaries=builder_summaries,
        debugger_rounds=debugger_rounds_summaries,
        final_test_output=final_test_output,
        total_cost_usd=total_cost,
    )
