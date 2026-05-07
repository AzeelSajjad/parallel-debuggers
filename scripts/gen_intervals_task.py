"""Generate examples/intervals_task.json — adversarial task with a touching-
intervals edge case that's commonly mis-implemented.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
EXAMPLES.mkdir(exist_ok=True)


TEST_FILE = '''from intervals import merge_intervals


def test_empty_input():
    assert merge_intervals([]) == []


def test_single_interval():
    assert merge_intervals([(1, 3)]) == [(1, 3)]


def test_disjoint_intervals():
    assert merge_intervals([(1, 3), (5, 7)]) == [(1, 3), (5, 7)]


def test_overlapping_intervals_merge():
    assert merge_intervals([(1, 4), (3, 6)]) == [(1, 6)]


def test_touching_intervals_merge():
    assert merge_intervals([(1, 3), (3, 5)]) == [(1, 5)]


def test_unsorted_input_is_handled():
    assert merge_intervals([(5, 7), (1, 3)]) == [(1, 3), (5, 7)]


def test_one_interval_contains_another():
    assert merge_intervals([(1, 10), (3, 5)]) == [(1, 10)]


def test_point_interval_preserved():
    assert merge_intervals([(3, 3)]) == [(3, 3)]


def test_complex_chain():
    assert merge_intervals(
        [(1, 4), (2, 5), (7, 9), (8, 10), (11, 11)]
    ) == [(1, 5), (7, 10), (11, 11)]
'''


SPEC = {
    "task_id": "merge-intervals",
    "description": (
        "Write a Python module `intervals.py` containing a function "
        "`merge_intervals(items)` that takes a list of (start, end) tuples and "
        "returns the list of merged non-overlapping intervals, sorted by "
        "start. The input is NOT guaranteed to be sorted. The test file "
        "`test_intervals.py` is the authoritative spec — read it first to see "
        "every required edge case (empty, point intervals, touching intervals, "
        "containment, unsorted input)."
    ),
    "test_files": {"test_intervals.py": TEST_FILE},
}


def main() -> None:
    out = EXAMPLES / "intervals_task.json"
    out.write_text(json.dumps(SPEC, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
