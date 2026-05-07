"""DebuggerAgent: given a workspace with failing tests, attempts a fix.

This increment has no shared memory — the agent fixes from failure output
alone. Memory and dedup against prior approaches are wired in increment 5.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    query,
)


DEBUGGER_SYSTEM_PROMPT = """You are a debugger agent. The code in the current working directory has failing tests. Your job is to make them pass.

Rules:
- Read the failure output to understand what's broken.
- Use Read/Glob/Grep to inspect the existing code.
- Use Edit/Write to fix the bug.
- DO NOT modify test files (any file matching `test_*.py` or `*_test.py`).
- DO NOT run tests — a separate runner will validate your fix.
- Make the smallest change that fixes the bug.
- When done, output a one-line summary of the fix.
"""


@dataclass
class DebuggerResult:
    agent_id: str
    summary: str
    is_error: bool
    cost_usd: float | None
    files_modified: list[str]


class DebuggerAgent:
    def __init__(
        self,
        agent_id: str,
        workspace: Path,
        failure_output: str,
    ) -> None:
        self.agent_id = agent_id
        self.workspace = Path(workspace)
        self.failure_output = failure_output

    async def run(self) -> DebuggerResult:
        before = _file_hashes(self.workspace)

        prompt = (
            "Tests are failing in the current directory. Here is the failure output:\n\n"
            "```\n"
            f"{self.failure_output}\n"
            "```\n\n"
            "Diagnose the bug and apply a minimal fix. Do not modify test files."
        )

        options = ClaudeAgentOptions(
            system_prompt=DEBUGGER_SYSTEM_PROMPT,
            cwd=str(self.workspace),
            allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
            disallowed_tools=["Bash"],
            permission_mode="bypassPermissions",
            max_turns=20,
        )

        summary = ""
        is_error = False
        cost_usd: float | None = None

        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage):
                summary = msg.result or ""
                is_error = msg.is_error
                cost_usd = msg.total_cost_usd

        after = _file_hashes(self.workspace)
        files_modified = sorted(
            f
            for f in (before.keys() | after.keys())
            if before.get(f) != after.get(f)
        )

        return DebuggerResult(
            agent_id=self.agent_id,
            summary=summary,
            is_error=is_error,
            cost_usd=cost_usd,
            files_modified=files_modified,
        )


def _file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for p in root.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(root))
            hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes
