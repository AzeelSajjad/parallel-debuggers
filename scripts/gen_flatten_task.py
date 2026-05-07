"""Generate examples/flatten_task.json from a readable Python source.

Embedding multi-line code inside JSON is hard to read by hand; we keep
the test source as a regular Python triple-string and dump to JSON here.
Run once whenever the task definition changes:
    .venv/bin/python scripts/gen_flatten_task.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
EXAMPLES.mkdir(exist_ok=True)


TEST_FILE = '''from flatten import flatten


def test_flat_list_unchanged():
    assert flatten([1, 2, 3]) == [1, 2, 3]


def test_one_level_nesting():
    assert flatten([1, [2, 3], 4]) == [1, 2, 3, 4]


def test_deeply_nested():
    assert flatten([1, [2, [3, [4, [5]]]]]) == [1, 2, 3, 4, 5]


def test_strings_are_atomic():
    """Strings are iterable but must NOT be flattened into characters."""
    assert flatten([1, "ab", [3, "cd"]]) == [1, "ab", 3, "cd"]


def test_empty_list():
    assert flatten([]) == []


def test_nested_empties():
    assert flatten([[], [1], [], [[2]]]) == [1, 2]


def test_tuples_are_flattened():
    """Tuples are treated as nested containers (like lists)."""
    assert flatten([1, (2, 3), [4]]) == [1, 2, 3, 4]


def test_mixed_lists_and_tuples():
    assert flatten([(1, [2]), [3, (4, 5)]]) == [1, 2, 3, 4, 5]
'''


SPEC = {
    "task_id": "flatten-fn",
    "description": (
        "Write a Python module `flatten.py` containing a function "
        "`flatten(items)` that recursively flattens nested lists and tuples "
        "into a single flat list. Strings must be treated as atomic values "
        "(NOT flattened into characters), even though they are iterable. "
        "The test file `test_flatten.py` already exists and is the "
        "authoritative spec — read it first."
    ),
    "test_files": {"test_flatten.py": TEST_FILE},
}


def main() -> None:
    out = EXAMPLES / "flatten_task.json"
    out.write_text(json.dumps(SPEC, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
