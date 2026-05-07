"""End-to-end smoke test for DebuggerAgent + SharedMemory.

Pre-seeds the memory with a fake "already-failed" approach, dispatches a
debugger, and verifies that:
  - the debugger called read_failed_approaches (we can't observe directly,
    but we infer from the workflow ordering)
  - the debugger called propose_approach BEFORE editing (we check that an
    in_progress / completed row was added during the run)
  - the debugger called record_outcome (final status is succeeded or
    failed, never in_progress)
  - the chosen approach differs from the seeded one
  - the bug actually got fixed

Run from project root:
    .venv/bin/python scripts/smoke_debugger_memory.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.debugger import DebuggerAgent  # noqa: E402
from memory.store import SharedMemory  # noqa: E402
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

SEEDED_APPROACH = "Replace the body of add() with `return a * b` in add.py."
SEEDED_HYPOTHESIS = "Maybe the function is supposed to multiply."
SEEDED_FAILURE_DETAIL = "Tests still fail — multiplication is wrong too."


async def main() -> int:
    workspace = ROOT / "workspace" / "smoke_debugger_memory"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    (workspace / "add.py").write_text(BROKEN_CODE)
    (workspace / "test_add.py").write_text(TEST_CODE)

    memory_path = workspace / "_memory.json"
    memory = SharedMemory(memory_path, task_id="smoke-fix-add")
    seeded_id = memory.record_attempt(
        agent_id="dbg-fake-prior",
        approach=SEEDED_APPROACH,
        hypothesis=SEEDED_HYPOTHESIS,
    )
    memory.record_result(seeded_id, success=False, detail=SEEDED_FAILURE_DETAIL)
    print(f"[smoke] seeded memory with failed approach: {seeded_id}")

    print("[smoke] running pytest on broken code (expect failure)")
    pre = run_tests(workspace)
    if pre.success:
        print("[smoke] FAIL: pre-fix tests unexpectedly passed")
        return 1

    print("[smoke] dispatching debugger agent (memory-aware)")
    debugger = DebuggerAgent(
        agent_id="dbg-smoke-mem-1",
        workspace=workspace,
        failure_output=pre.failure_output,
        memory=memory,
    )
    result = await debugger.run()
    print(f"[smoke] is_error={result.is_error}")
    print(f"[smoke] cost_usd={result.cost_usd}")
    print(f"[smoke] files_modified={result.files_modified}")
    print(f"[smoke] summary={result.summary[:200]!r}")

    attempts = memory.get_all_attempts()
    print(f"[smoke] memory has {len(attempts)} attempts:")
    for a in attempts:
        print(f"  - {a.attempt_id} [{a.status}] by {a.agent_id}: {a.approach[:80]!r}")

    new_attempts = [a for a in attempts if a.agent_id == "dbg-smoke-mem-1"]
    if not new_attempts:
        print("[smoke] FAIL: debugger did NOT call propose_approach (no new entry)")
        return 1
    if len(new_attempts) > 1:
        print(f"[smoke] WARN: debugger logged {len(new_attempts)} attempts (expected 1)")

    new = new_attempts[-1]
    if new.status == "in_progress":
        print("[smoke] FAIL: debugger did NOT call record_outcome (still in_progress)")
        return 1

    if new.approach.strip() == SEEDED_APPROACH.strip():
        print("[smoke] FAIL: debugger reused the seeded failed approach verbatim")
        return 1

    print("[smoke] re-running pytest (expect pass)")
    post = run_tests(workspace)
    if not post.success:
        print("[smoke] FAIL: tests still failing after debugger run")
        print(post.failure_output)
        return 1

    print("[smoke] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
