"""End-to-end smoke test for BuilderAgent. Invokes the real Claude SDK.

Run from project root:
    .venv/bin/python scripts/smoke_builder.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.builder import BuilderAgent, TaskSpec  # noqa: E402


async def main() -> int:
    workspace = ROOT / "workspace" / "smoke_builder"
    if workspace.exists():
        shutil.rmtree(workspace)

    spec = TaskSpec(
        task_id="smoke-1",
        description=(
            "Write a single Python file `greet.py` containing a function "
            "`greet(name: str) -> str` that returns the string "
            "'Hello, <name>!'. No tests, no docstrings, no extra files."
        ),
        workspace=workspace,
    )
    agent = BuilderAgent(agent_id="builder-1", spec=spec)

    print(f"[smoke] running builder in {workspace}")
    result = await agent.run()

    print(f"[smoke] is_error={result.is_error}")
    print(f"[smoke] cost_usd={result.cost_usd}")
    print(f"[smoke] files_written={result.files_written}")
    print(f"[smoke] summary={result.summary[:200]!r}")

    target = workspace / "greet.py"
    if not target.exists():
        print(f"[smoke] FAIL: {target} not created")
        return 1

    contents = target.read_text()
    print(f"[smoke] greet.py contents:\n---\n{contents}\n---")

    if "def greet" not in contents:
        print("[smoke] FAIL: greet.py missing `def greet`")
        return 1

    print("[smoke] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
