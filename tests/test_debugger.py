from pathlib import Path

from agents.debugger import _file_hashes


def test_file_hashes_detects_modification(tmp_path: Path) -> None:
    f = tmp_path / "a.py"
    f.write_text("x = 1\n")
    h1 = _file_hashes(tmp_path)
    f.write_text("x = 2\n")
    h2 = _file_hashes(tmp_path)
    assert h1 != h2
    assert h1["a.py"] != h2["a.py"]


def test_file_hashes_stable_for_unchanged(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n")
    h1 = _file_hashes(tmp_path)
    h2 = _file_hashes(tmp_path)
    assert h1 == h2


def test_file_hashes_recursive(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("# a")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("# b")
    h = _file_hashes(tmp_path)
    assert set(h.keys()) == {"a.py", "sub/b.py"}
