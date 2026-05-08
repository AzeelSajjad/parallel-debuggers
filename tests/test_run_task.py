"""Unit tests for the run_task CLI helpers.

Argument parsing and the canonical-copy helper. Does not invoke the
orchestrator (that's covered by the smoke scripts).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.run_task import copy_canonical_into, parse_args  # noqa: E402


def test_parse_args_minimal() -> None:
    ns = parse_args(["task.json"])
    assert ns.task_json == Path("task.json")
    assert ns.run_dir is None
    assert ns.into is None
    assert ns.python_executable is None


def test_parse_args_all_flags() -> None:
    ns = parse_args(
        [
            "t.json",
            "--run-dir", "/tmp/r",
            "--into", "/tmp/proj",
            "--python", "/foo/bin/python",
            "--num-builders", "3",
            "--num-debuggers", "4",
            "--max-debug-rounds", "5",
        ]
    )
    assert ns.run_dir == Path("/tmp/r")
    assert ns.into == Path("/tmp/proj")
    assert ns.python_executable == "/foo/bin/python"
    assert ns.num_builders == 3
    assert ns.num_debuggers == 4
    assert ns.max_debug_rounds == 5


def test_copy_canonical_into_creates_target(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "impl.py").write_text("x = 1\n")
    (canonical / "test_impl.py").write_text("def test(): pass\n")

    target = tmp_path / "out"
    copied = copy_canonical_into(canonical, target)

    assert (target / "impl.py").read_text() == "x = 1\n"
    assert (target / "test_impl.py").exists()
    assert sorted(copied) == ["impl.py", "test_impl.py"]


def test_copy_canonical_into_overwrites_existing_files(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "impl.py").write_text("new\n")

    target = tmp_path / "out"
    target.mkdir()
    (target / "impl.py").write_text("old\n")
    (target / "unrelated.py").write_text("keep me\n")

    copy_canonical_into(canonical, target)

    assert (target / "impl.py").read_text() == "new\n"
    assert (target / "unrelated.py").read_text() == "keep me\n"


def test_copy_canonical_into_skips_pycache(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    (canonical / "impl.py").write_text("x = 1\n")
    (canonical / "__pycache__").mkdir()
    (canonical / "__pycache__" / "impl.cpython-311.pyc").write_bytes(b"junk")
    (canonical / ".pytest_cache").mkdir()
    (canonical / ".pytest_cache" / "v.txt").write_text("1\n")

    target = tmp_path / "out"
    copied = copy_canonical_into(canonical, target)

    assert (target / "impl.py").exists()
    assert not (target / "__pycache__").exists()
    assert not (target / ".pytest_cache").exists()
    assert copied == ["impl.py"]


def test_copy_canonical_into_handles_subdirs(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    (canonical / "pkg").mkdir(parents=True)
    (canonical / "pkg" / "__init__.py").write_text("")
    (canonical / "pkg" / "thing.py").write_text("v = 2\n")

    target = tmp_path / "out"
    copy_canonical_into(canonical, target)

    assert (target / "pkg" / "thing.py").read_text() == "v = 2\n"
