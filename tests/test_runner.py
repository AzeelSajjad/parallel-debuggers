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


def test_python_executable_argument_is_threaded_through(tmp_path: Path) -> None:
    """Passing python_executable=sys.executable explicitly should be a no-op
    behaviorally — verifies the param is wired in, not just declared."""
    import sys

    (tmp_path / "test_ok.py").write_text("def test(): assert True\n")
    result = run_tests(tmp_path, python_executable=sys.executable)
    assert result.success


def test_python_executable_invalid_path_fails_gracefully(tmp_path: Path) -> None:
    (tmp_path / "test_ok.py").write_text("def test(): assert True\n")
    result = run_tests(tmp_path, python_executable="/nonexistent/python")
    assert not result.success
    # Either FileNotFoundError surfaces in stderr or the subprocess returns nonzero;
    # in either case run_tests must not raise.


def test_timeout(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_slow.py",
        "import time\ndef test_slow():\n    time.sleep(10)\n",
    )
    result = run_tests(tmp_path, timeout=1)
    assert not result.success
    assert result.timed_out
    assert "TIMED OUT" in result.failure_output
