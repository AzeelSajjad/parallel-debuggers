"""End-to-end smoke test for DebuggerAgent.

Sets up a workspace with intentionally-broken code + tests, runs pytest
to capture the failure, hands the failure output to a single debugger
agent, then re-runs pytest and verifies it passes.

Run from project root:
    .venv/bin/python scripts/smoke_debugger.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.debugger import DebuggerAgent  # noqa: E402
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


async def main() -> int:
    workspace = ROOT / "workspace" / "smoke_debugger"
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    (workspace / "add.py").write_text(BROKEN_CODE)
    (workspace / "test_add.py").write_text(TEST_CODE)
    test_file_before = (workspace / "test_add.py").read_text()

    print("[smoke] running pytest on broken code (expect failure)")
    pre = run_tests(workspace)
    if pre.success:
        print("[smoke] FAIL: pre-fix tests unexpectedly passed")
        return 1
    print(f"[smoke] pre-fix tests failed as expected (return_code={pre.return_code})")

    print("[smoke] dispatching debugger agent")
    debugger = DebuggerAgent(
        agent_id="dbg-smoke-1",
        workspace=workspace,
        failure_output=pre.failure_output,
    )
    result = await debugger.run()
    print(f"[smoke] is_error={result.is_error}")
    print(f"[smoke] cost_usd={result.cost_usd}")
    print(f"[smoke] files_modified={result.files_modified}")
    print(f"[smoke] summary={result.summary[:200]!r}")

    test_file_after = (workspace / "test_add.py").read_text()
    if test_file_after != test_file_before:
        print("[smoke] FAIL: debugger modified the test file (forbidden)")
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
