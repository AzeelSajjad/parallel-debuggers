"""End-to-end swarm smoke test: N=3 debuggers fix the add() bug in parallel.

Verifies that:
  - All 3 debuggers run to completion concurrently.
  - Shared memory ends with one entry per debugger (no lost writes).
  - All 3 approach strings are distinct (negative-memory dedup worked).
  - At least one fork has passing tests (someone fixed the bug).

Run from project root:
    .venv/bin/python scripts/smoke_swarm.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memory.store import SharedMemory  # noqa: E402
from orchestrator.swarm import run_debugger_swarm  # noqa: E402
from runner.tests import run_tests  # noqa: E402

BROKEN_CODE = """def add(a, b):
    return a - b
"""

TEST_CODE = """from add import add

def test_add_positive():
    assert add(2, 3) == 5

def test_add_zero():
    assert add(0, 0) == 0

def test_add_negative():
    assert add(-1, -1) == -2
"""

NUM_DEBUGGERS = 3


async def main() -> int:
    base = ROOT / "workspace" / "smoke_swarm"
    if base.exists():
        shutil.rmtree(base)
    main_ws = base / "main"
    main_ws.mkdir(parents=True)
    (main_ws / "add.py").write_text(BROKEN_CODE)
    (main_ws / "test_add.py").write_text(TEST_CODE)

    print("[smoke] running pytest on broken code (expect failure)")
    pre = run_tests(main_ws)
    if pre.success:
        print("[smoke] FAIL: pre-fix unexpectedly passed")
        return 1

    memory = SharedMemory(base / "memory.json", task_id="swarm-fix-add")

    print(f"[smoke] dispatching swarm of {NUM_DEBUGGERS} debuggers")
    t0 = time.monotonic()
    swarm = await run_debugger_swarm(
        workspace=main_ws,
        failure_output=pre.failure_output,
        memory=memory,
        num_debuggers=NUM_DEBUGGERS,
    )
    dt = time.monotonic() - t0
    print(f"[smoke] swarm complete in {dt:.1f}s; {len(swarm.attempts)} attempts")

    for sa in swarm.attempts:
        r = sa.debugger_result
        print(
            f"  {r.agent_id}: is_error={r.is_error} "
            f"cost=${r.cost_usd or 0:.4f} files={r.files_modified}"
        )

    attempts = memory.get_all_attempts()
    print(f"[smoke] shared memory has {len(attempts)} entries:")
    for a in attempts:
        print(f"  - {a.attempt_id} [{a.status}] by {a.agent_id}: {a.approach[:100]!r}")

    if len(attempts) < NUM_DEBUGGERS:
        print(
            f"[smoke] FAIL: expected >={NUM_DEBUGGERS} attempts, got {len(attempts)}"
        )
        return 1

    approaches = [a.approach.strip().lower() for a in attempts]
    distinct = len(set(approaches))
    print(f"[smoke] distinct approaches: {distinct}/{len(approaches)}")
    if distinct < NUM_DEBUGGERS:
        print(
            "[smoke] FAIL: at least two debuggers proposed identical approach strings"
        )
        return 1

    pass_count = 0
    for sa in swarm.attempts:
        post = run_tests(sa.workspace)
        verdict = "PASS" if post.success else "FAIL"
        print(f"[smoke] {sa.workspace.name}: tests {verdict}")
        if post.success:
            pass_count += 1

    if pass_count == 0:
        print("[smoke] FAIL: no fork has passing tests")
        return 1

    print(
        f"[smoke] PASS — {pass_count}/{len(swarm.attempts)} forks fix the bug; "
        f"all {NUM_DEBUGGERS} approaches distinct"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
