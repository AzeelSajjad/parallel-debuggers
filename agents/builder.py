"""BuilderAgent: takes a task spec, writes code to a workspace.

Single-agent / no-memory in this increment. Parallelism and shared memory
are layered on later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    query,
)


@dataclass
class TaskSpec:
    task_id: str
    description: str
    workspace: Path

    @classmethod
    def from_dict(cls, d: dict) -> "TaskSpec":
        return cls(
            task_id=d["task_id"],
            description=d["description"],
            workspace=Path(d["workspace"]),
        )


BUILDER_SYSTEM_PROMPT = """You are a builder agent. Your job is to write code that satisfies a task specification.

Rules:
- Write code into the current working directory using Write/Edit tools.
- If test files (`test_*.py` or `*_test.py`) already exist in the directory, treat them as the authoritative spec — read them with the Read tool to learn the expected behavior. DO NOT modify or delete them.
- Do not run tests — a separate test runner will validate your work.
- Do not ask clarifying questions; make sensible assumptions and proceed.
- Keep the code simple and direct. No speculative abstractions.
- When done, output a one-line summary of what you wrote.
"""


@dataclass
class BuilderResult:
    agent_id: str
    summary: str
    is_error: bool
    cost_usd: float | None
    files_written: list[str]


class BuilderAgent:
    def __init__(self, agent_id: str, spec: TaskSpec) -> None:
        self.agent_id = agent_id
        self.spec = spec

    async def run(self) -> BuilderResult:
        self.spec.workspace.mkdir(parents=True, exist_ok=True)

        before = _snapshot_files(self.spec.workspace)

        prompt = (
            f"Task: {self.spec.description}\n\n"
            "Write code into the current working directory to satisfy the task."
        )

        options = ClaudeAgentOptions(
            system_prompt=BUILDER_SYSTEM_PROMPT,
            cwd=str(self.spec.workspace),
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

        after = _snapshot_files(self.spec.workspace)
        files_written = sorted(after - before)

        return BuilderResult(
            agent_id=self.agent_id,
            summary=summary,
            is_error=is_error,
            cost_usd=cost_usd,
            files_written=files_written,
        )


def _snapshot_files(root: Path) -> set[str]:
    return {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file()
    }
