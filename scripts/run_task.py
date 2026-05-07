"""Run the orchestrator on a JSON task spec.

Usage:
    .venv/bin/python scripts/run_task.py <task.json> [run_dir]

The task JSON has shape:
    {
      "task_id": "...",
      "description": "...",
      "test_files": {"test_x.py": "<source>", ...}
    }
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.run import FullTaskSpec, run_orchestrator  # noqa: E402
from runner.tests import run_tests  # noqa: E402


async def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: run_task.py <task.json> [run_dir]", file=sys.stderr)
        return 2

    spec_path = Path(argv[1]).resolve()
    if not spec_path.exists():
        print(f"task file not found: {spec_path}", file=sys.stderr)
        return 2
    spec = FullTaskSpec(**json.loads(spec_path.read_text()))

    run_dir = Path(argv[2]) if len(argv) > 2 else ROOT / "workspace" / spec.task_id
    print(f"[run] task_id={spec.task_id}  run_dir={run_dir}")

    t0 = time.monotonic()
    result = await run_orchestrator(
        spec=spec,
        run_dir=run_dir,
        num_builders=2,
        num_debuggers=2,
        max_debug_rounds=2,
    )
    dt = time.monotonic() - t0

    print()
    print(f"[run] success={result.success}")
    print(f"[run] rounds_used={result.rounds_used}")
    print(f"[run] elapsed={dt:.1f}s  cost=${result.total_cost_usd:.4f}")
    print(f"[run] canonical={result.canonical_workspace}")

    print("[run] builder summaries:")
    for s in result.builder_summaries:
        print(f"  - {s[:160]}")
    for i, round_ in enumerate(result.debugger_rounds, 1):
        print(f"[run] debug round {i}:")
        for s in round_:
            print(f"  - {s[:160]}")

    if not result.success:
        print("[run] FAIL: did not converge")
        print(result.final_test_output[:2000])
        return 1

    final = run_tests(result.canonical_workspace)
    if not final.success:
        print("[run] FAIL: claimed success but final tests fail")
        print(final.failure_output[:2000])
        return 1

    print("[run] PASS — final tests verified")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv)))
