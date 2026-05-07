from pathlib import Path

from runner.tests import run_tests


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_passing_tests(tmp_path: Path) -> None:
    _write(tmp_path / "test_pass.py", "def test_ok():\n    assert 1 + 1 == 2\n")
    result = run_tests(tmp_path)
    assert result.success
    assert result.return_code == 0
    assert "1 passed" in result.stdout
    assert result.failure_output == ""


def test_failing_tests(tmp_path: Path) -> None:
    _write(tmp_path / "test_fail.py", "def test_bad():\n    assert 1 == 2\n")
    result = run_tests(tmp_path)
    assert not result.success
    assert result.return_code != 0
    assert "test_bad" in result.failure_output
    assert "stdout" in result.failure_output


def test_no_tests_collected(tmp_path: Path) -> None:
    _write(tmp_path / "code.py", "x = 1\n")
    result = run_tests(tmp_path)
    assert not result.success
    assert result.no_tests_collected
    assert "no tests collected" in result.failure_output


def test_mixed_pass_and_fail(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_mixed.py",
        "def test_a():\n    assert True\n\ndef test_b():\n    assert False\n",
    )
    result = run_tests(tmp_path)
    assert not result.success
    assert "test_a" in result.stdout
    assert "test_b" in result.stdout
    assert "1 failed" in result.stdout


def test_import_error_surfaces(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_broken.py",
        "from nonexistent_module import thing\n\ndef test_x():\n    assert thing\n",
    )
    result = run_tests(tmp_path)
    assert not result.success
    assert "nonexistent_module" in result.failure_output


def test_timeout(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_slow.py",
        "import time\ndef test_slow():\n    time.sleep(10)\n",
    )
    result = run_tests(tmp_path, timeout=1)
    assert not result.success
    assert result.timed_out
    assert "TIMED OUT" in result.failure_output
