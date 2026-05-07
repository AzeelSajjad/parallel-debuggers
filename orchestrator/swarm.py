"""Run multiple debugger agents concurrently against forks of a workspace.

Each debugger gets its own copy of the workspace so concurrent edits don't
clobber each other. The shared SharedMemory is passed to every debugger so
their negative memory is genuinely shared.

Increment 6 deliberately leaves test-validation and winner-selection to a
later increment — this module just runs the swarm and returns where each
agent ended up.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path

from agents.debugger import DebuggerAgent, DebuggerResult
from memory.store import SharedMemory


@dataclass
class SwarmAttempt:
    debugger_result: DebuggerResult
    workspace: Path


@dataclass
class SwarmRun:
    attempts: list[SwarmAttempt]


def fork_workspace(source: Path, dest: Path) -> Path:
    """Copy `source` into `dest`, replacing dest if it exists."""
    source = Path(source)
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)
    return dest


async def run_debugger_swarm(
    workspace: Path,
    failure_output: str,
    memory: SharedMemory,
    num_debuggers: int = 3,
    stagger_seconds: float = 1.5,
    forks_root: Path | None = None,
) -> SwarmRun:
    """Run `num_debuggers` debugger agents concurrently, one per fork.

    `stagger_seconds` is a small delay between successive launches so the
    first debugger has time to call `propose_approach` (reserving its slot
    in shared memory) before the next debugger reads. Tunable; set to 0 to
    launch all simultaneously.
    """
    workspace = Path(workspace)
    forks_root = forks_root or workspace.parent / "_forks"
    forks_root.mkdir(parents=True, exist_ok=True)

    forks = [
        fork_workspace(workspace, forks_root / f"dbg-{i + 1}")
        for i in range(num_debuggers)
    ]

    async def _run_one(idx: int) -> SwarmAttempt:
        if stagger_seconds > 0 and idx > 0:
            await asyncio.sleep(stagger_seconds * idx)
        agent = DebuggerAgent(
            agent_id=f"dbg-{idx + 1}",
            workspace=forks[idx],
            failure_output=failure_output,
            memory=memory,
        )
        result = await agent.run()
        return SwarmAttempt(debugger_result=result, workspace=forks[idx])

    attempts = await asyncio.gather(*[_run_one(i) for i in range(num_debuggers)])
    return SwarmRun(attempts=list(attempts))
