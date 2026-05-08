"""Run the orchestrator on a JSON task spec.

Usage:
    .venv/bin/python scripts/run_task.py <task.json>
        [--run-dir DIR]
        [--into TARGET_DIR]
        [--python /path/to/venv/python]

The task JSON has shape:
    {
      "task_id": "...",
      "description": "...",
      "test_files": {"test_x.py": "<source>", ...}
    }

Flags:
    --run-dir DIR     Where the orchestrator stages forks/canonical/memory.
                      Defaults to <brain>/workspace/<task_id>.
    --into TARGET     On success, copy every file in the canonical workspace
                      into TARGET (existing files are overwritten; nothing
                      else is deleted). Useful when running brain on a
                      separate project: point this at your project root or
                      a sub-package.
    --python PATH     Python interpreter used to run pytest. Defaults to the
                      current one (brain's venv). Point at your project's
                      venv when the tests need imports beyond stdlib.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.run import FullTaskSpec, run_orchestrator  # noqa: E402
from runner.tests import run_tests  # noqa: E402


COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
_IGNORED_DIRS = {"__pycache__", ".pytest_cache"}


def _was_copied(rel: Path) -> bool:
    if rel.suffix == ".pyc":
        return False
    return not any(part in _IGNORED_DIRS for part in rel.parts)


def copy_canonical_into(canonical: Path, target: Path) -> list[str]:
    """Copy every file under `canonical` into `target`, overwriting in place.
    Returns the list of relative paths actually copied (matches what
    `shutil.copytree(..., ignore=COPY_IGNORE)` writes)."""
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(canonical, target, ignore=COPY_IGNORE, dirs_exist_ok=True)
    copied = sorted(
        str(p.relative_to(canonical))
        for p in canonical.rglob("*")
        if p.is_file() and _was_copied(p.relative_to(canonical))
    )
    return copied


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="run_task.py")
    p.add_argument("task_json", type=Path, help="path to the task JSON spec")
    p.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="staging directory (default: <brain>/workspace/<task_id>)",
    )
    p.add_argument(
        "--into",
        type=Path,
        default=None,
        help="copy canonical contents here on success",
    )
    p.add_argument(
        "--python",
        dest="python_executable",
        default=None,
        help="python interpreter for pytest (default: current)",
    )
    p.add_argument("--num-builders", type=int, default=2)
    p.add_argument("--num-debuggers", type=int, default=2)
    p.add_argument("--max-debug-rounds", type=int, default=2)
    return p.parse_args(argv)


async def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if not args.task_json.exists():
        print(f"task file not found: {args.task_json}", file=sys.stderr)
        return 2

    spec = FullTaskSpec(**json.loads(args.task_json.read_text()))
    run_dir = args.run_dir or ROOT / "workspace" / spec.task_id
    print(f"[run] task_id={spec.task_id}  run_dir={run_dir}")
    if args.python_executable:
        print(f"[run] python={args.python_executable}")
    if args.into:
        print(f"[run] will copy canonical → {args.into} on success")

    t0 = time.monotonic()
    result = await run_orchestrator(
        spec=spec,
        run_dir=run_dir,
        num_builders=args.num_builders,
        num_debuggers=args.num_debuggers,
        max_debug_rounds=args.max_debug_rounds,
        python_executable=args.python_executable,
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

    final = run_tests(
        result.canonical_workspace, python_executable=args.python_executable
    )
    if not final.success:
        print("[run] FAIL: claimed success but final tests fail")
        print(final.failure_output[:2000])
        return 1

    if args.into is not None:
        copied = copy_canonical_into(result.canonical_workspace, args.into)
        print(f"[run] copied {len(copied)} files into {args.into}:")
        for f in copied:
            print(f"  + {f}")

    print("[run] PASS — final tests verified")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
