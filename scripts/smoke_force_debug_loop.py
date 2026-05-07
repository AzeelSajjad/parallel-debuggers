"""Force the orchestrator's debug loop to engage by skipping the build
phase and starting with deliberately broken code in the canonical.

Demonstrates: multi-round debugger swarms with shared memory accumulating
across rounds, and the orchestrator's pattern of overriding debugger
self-assessments with real test outcomes.

Run from project root:
    .venv/bin/python scripts/smoke_force_debug_loop.py
"""

from __future__ import annotations

import asyncio
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memory.store import SharedMemory  # noqa: E402
from orchestrator.swarm import fork_workspace, run_debugger_swarm  # noqa: E402
from runner.tests import TestResult, run_tests  # noqa: E402


BROKEN_IMPL = """def merge_intervals(items):
    return list(items)
"""

TESTS = """from intervals import merge_intervals


def test_empty():
    assert merge_intervals([]) == []


def test_overlapping_merge():
    assert merge_intervals([(1, 4), (3, 6)]) == [(1, 6)]


def test_touching_merge():
    assert merge_intervals([(1, 3), (3, 5)]) == [(1, 5)]


def test_unsorted():
    assert merge_intervals([(5, 7), (1, 3)]) == [(1, 3), (5, 7)]


def test_complex_chain():
    assert merge_intervals(
        [(1, 4), (2, 5), (7, 9), (8, 10), (11, 11)]
    ) == [(1, 5), (7, 10), (11, 11)]
"""

NUM_DEBUGGERS = 2
MAX_ROUNDS = 3


def _count_failures(tr: TestResult) -> int:
    if tr.success:
        return 0
    m = re.search(r"(\d+) failed", tr.stdout)
    return int(m.group(1)) if m else 10**6


async def main() -> int:
    base = ROOT / "workspace" / "smoke_force_debug_loop"
    if base.exists():
        shutil.rmtree(base)

    canonical = base / "canonical"
    canonical.mkdir(parents=True)
    (canonical / "intervals.py").write_text(BROKEN_IMPL)
    (canonical / "test_intervals.py").write_text(TESTS)

    pre = run_tests(canonical)
    print(f"[smoke] pre-fix tests: failed ({_count_failures(pre)} failing)")

    memory = SharedMemory(base / "memory.json", task_id="force-debug-fix-intervals")

    total_cost = 0.0
    success = False
    final_test_output = ""
    winner_workspace: Path | None = None

    t0 = time.monotonic()
    for round_num in range(1, MAX_ROUNDS + 1):
        print(f"\n[smoke] ===== round {round_num} =====")
        canonical_test = run_tests(canonical)
        if canonical_test.success:
            success = True
            winner_workspace = canonical
            break

        forks_root = base / f"_round_{round_num}"
        swarm = await run_debugger_swarm(
            workspace=canonical,
            failure_output=canonical_test.failure_output,
            memory=memory,
            num_debuggers=NUM_DEBUGGERS,
            forks_root=forks_root,
        )

        round_tests: list[TestResult] = []
        for sa in swarm.attempts:
            r = sa.debugger_result
            total_cost += r.cost_usd or 0.0
            tr = run_tests(sa.workspace)
            round_tests.append(tr)
            verdict = "PASS" if tr.success else f"FAIL ({_count_failures(tr)} failed)"
            print(f"[smoke] {r.agent_id}: {verdict}  approach: {r.summary[:120]!r}")

            attempt = memory.find_latest_attempt_by_agent(r.agent_id)
            if attempt is not None:
                memory.record_result(
                    attempt.attempt_id,
                    success=tr.success,
                    detail="tests pass" if tr.success else tr.failure_output[:400],
                )

        winner_idx = next(
            (i for i, tr in enumerate(round_tests) if tr.success), None
        )
        if winner_idx is not None:
            success = True
            winner_workspace = swarm.attempts[winner_idx].workspace
            break

        best = min(range(len(round_tests)), key=lambda i: _count_failures(round_tests[i]))
        if canonical.exists():
            shutil.rmtree(canonical)
        shutil.copytree(swarm.attempts[best].workspace, canonical)
        final_test_output = round_tests[best].failure_output
        print(f"[smoke] no fork passed; pivoting canonical to {swarm.attempts[best].workspace.name}")

    dt = time.monotonic() - t0

    print()
    print(f"[smoke] success={success}  rounds_used={round_num}  elapsed={dt:.1f}s  cost=${total_cost:.4f}")
    attempts = memory.get_all_attempts()
    print(f"[smoke] memory recorded {len(attempts)} total attempts:")
    for a in attempts:
        print(f"  - {a.attempt_id} [{a.status}] by {a.agent_id}: {a.approach[:100]!r}")

    if not success:
        print("[smoke] FAIL: did not converge")
        print(final_test_output[:1500])
        return 1

    final = run_tests(winner_workspace)
    if not final.success:
        print("[smoke] FAIL: claimed success but final tests fail")
        return 1

    print("[smoke] PASS — debug loop converged with shared memory")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
