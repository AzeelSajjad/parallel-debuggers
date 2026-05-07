"""End-to-end orchestrator smoke test.

Task: build `is_prime(n: int) -> bool`. Tests cover edge cases. Builders
should mostly succeed; if they don't, the debug loop kicks in.

Run from project root:
    .venv/bin/python scripts/smoke_orchestrator.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.run import FullTaskSpec, run_orchestrator  # noqa: E402
from runner.tests import run_tests  # noqa: E402


TEST_FILE = """from is_prime import is_prime

def test_two_is_prime():
    assert is_prime(2)

def test_three_is_prime():
    assert is_prime(3)

def test_four_is_not_prime():
    assert not is_prime(4)

def test_seven_is_prime():
    assert is_prime(7)

def test_one_is_not_prime():
    assert not is_prime(1)

def test_zero_is_not_prime():
    assert not is_prime(0)

def test_negatives_are_not_prime():
    assert not is_prime(-5)
    assert not is_prime(-2)
"""


async def main() -> int:
    spec = FullTaskSpec(
        task_id="is-prime",
        description=(
            "Write a Python module `is_prime.py` containing a function "
            "`is_prime(n: int) -> bool` that returns True iff n is a positive "
            "prime number. Read the existing test file to learn the exact "
            "expected behavior. Do not import any external library."
        ),
        test_files={"test_is_prime.py": TEST_FILE},
    )

    run_dir = ROOT / "workspace" / "smoke_orchestrator"
    print(f"[smoke] starting orchestrator (run_dir={run_dir})")
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
    print(f"[smoke] success={result.success}")
    print(f"[smoke] rounds_used={result.rounds_used}")
    print(f"[smoke] elapsed={dt:.1f}s")
    print(f"[smoke] total_cost_usd=${result.total_cost_usd:.4f}")
    print(f"[smoke] canonical={result.canonical_workspace}")
    print(f"[smoke] builder summaries:")
    for s in result.builder_summaries:
        print(f"  - {s[:120]}")
    if result.debugger_rounds:
        for i, round_ in enumerate(result.debugger_rounds, 1):
            print(f"[smoke] debug round {i} summaries:")
            for s in round_:
                print(f"  - {s[:140]}")

    if not result.success:
        print("[smoke] FAIL: orchestrator did not converge to passing tests")
        print(result.final_test_output[:1500])
        return 1

    final = run_tests(result.canonical_workspace)
    if not final.success:
        print("[smoke] FAIL: claimed success but final tests fail")
        print(final.failure_output[:1500])
        return 1

    impl = (result.canonical_workspace / "is_prime.py").read_text()
    print()
    print("[smoke] is_prime.py:")
    print("---")
    print(impl)
    print("---")
    print("[smoke] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
