"""Unit tests for the builder agent that don't invoke the SDK.

The end-to-end smoke test (real SDK call) lives in scripts/smoke_builder.py
and is run manually because it costs API credits.
"""

from pathlib import Path

from agents.builder import TaskSpec, _snapshot_files


def test_task_spec_from_dict(tmp_path: Path) -> None:
    spec = TaskSpec.from_dict(
        {
            "task_id": "t1",
            "description": "write a hello function",
            "workspace": str(tmp_path / "ws"),
        }
    )
    assert spec.task_id == "t1"
    assert spec.description == "write a hello function"
    assert spec.workspace == tmp_path / "ws"


def test_snapshot_files_finds_recursively(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("# a")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("# b")
    snap = _snapshot_files(tmp_path)
    assert snap == {"a.py", "sub/b.py"}


def test_snapshot_files_empty_dir(tmp_path: Path) -> None:
    assert _snapshot_files(tmp_path) == set()
