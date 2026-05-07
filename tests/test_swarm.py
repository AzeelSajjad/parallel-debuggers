from pathlib import Path

from orchestrator.swarm import fork_workspace


def test_fork_workspace_copies_files_recursively(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("x = 1")
    (src / "sub").mkdir()
    (src / "sub" / "b.py").write_text("y = 2")

    dest = tmp_path / "dest"
    fork_workspace(src, dest)

    assert (dest / "a.py").read_text() == "x = 1"
    assert (dest / "sub" / "b.py").read_text() == "y = 2"


def test_fork_workspace_replaces_existing_dest(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "new.py").write_text("new")

    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "old.py").write_text("old")

    fork_workspace(src, dest)
    assert (dest / "new.py").exists()
    assert not (dest / "old.py").exists()


def test_fork_returns_dest_path(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.py").write_text("")
    out = fork_workspace(src, tmp_path / "dest")
    assert out == tmp_path / "dest"
