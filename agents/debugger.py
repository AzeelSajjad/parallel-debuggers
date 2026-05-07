"""DebuggerAgent: given a workspace with failing tests, attempts a fix.

Optionally takes a SharedMemory; when provided, the agent gets custom MCP
tools (read_failed_approaches / propose_approach / record_outcome) so that
its attempt is logged before it runs and so that prior attempts steer it
away from already-tried approaches.
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

from memory.store import SharedMemory
from tools.custom_tools import build_memory_tools


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


DEBUGGER_SYSTEM_PROMPT_WITH_MEMORY = """You are a debugger agent working alongside other debugger agents on the same bug. You share a NEGATIVE MEMORY store: every approach that any debugger has tried (failed or currently in flight) is logged so no two agents waste effort on the same dead end.

REQUIRED workflow — follow it exactly:

1. Call `read_failed_approaches` FIRST. Read every entry carefully.
2. Devise a fix that is materially different from every entry. If you cannot find a novel angle, call `record_outcome(success=false, detail="no novel approach available")` and stop.
3. Call `propose_approach(approach="...", hypothesis="...")` BEFORE editing any code. The approach string should name the file/line and the specific change. This RESERVES the approach so concurrent agents won't pick it. You will get back an attempt_id.
4. Apply the fix using Edit/Write. DO NOT modify test files (`test_*.py` or `*_test.py`).
5. Output a one-line summary, then call `record_outcome(attempt_id, success=true|false, detail="...")` and stop. If you believe the fix works, pass success=true; if you bailed, success=false.

Other rules:
- Make the smallest change that fixes the bug.
- DO NOT run tests — a separate runner will validate.
- ALWAYS call `record_outcome` before stopping, even on a bail.
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
        memory: SharedMemory | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.workspace = Path(workspace)
        self.failure_output = failure_output
        self.memory = memory

    async def run(self) -> DebuggerResult:
        before = _file_hashes(self.workspace)

        prompt = (
            "Tests are failing in the current directory. Here is the failure output:\n\n"
            "```\n"
            f"{self.failure_output}\n"
            "```\n\n"
            "Diagnose the bug and apply a minimal fix. Do not modify test files."
        )

        allowed_tools = ["Read", "Write", "Edit", "Glob", "Grep"]
        mcp_servers: dict = {}
        system_prompt = DEBUGGER_SYSTEM_PROMPT

        if self.memory is not None:
            server, memory_tool_names, _ = build_memory_tools(
                self.memory, self.agent_id
            )
            mcp_servers["negative_memory"] = server
            allowed_tools.extend(memory_tool_names)
            system_prompt = DEBUGGER_SYSTEM_PROMPT_WITH_MEMORY

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            cwd=str(self.workspace),
            allowed_tools=allowed_tools,
            disallowed_tools=["Bash"],
            permission_mode="bypassPermissions",
            max_turns=20,
            mcp_servers=mcp_servers,
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
