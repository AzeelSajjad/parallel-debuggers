"""Pytest subprocess wrapper.

Runs the workspace's tests in a child process and returns a structured
result that downstream debugger agents can consume.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PYTEST_NO_TESTS_COLLECTED = 5


@dataclass
class TestResult:
    __test__ = False  # silence pytest collection warning on the class name

    success: bool
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    no_tests_collected: bool = False

    @property
    def failure_output(self) -> str:
        """Combined output suitable for handing to a debugger agent."""
        if self.success:
            return ""
        parts = []
        if self.timed_out:
            parts.append(f"[test runner: TIMED OUT]")
        if self.no_tests_collected:
            parts.append("[test runner: no tests collected]")
        if self.stdout:
            parts.append("--- stdout ---\n" + self.stdout)
        if self.stderr:
            parts.append("--- stderr ---\n" + self.stderr)
        return "\n\n".join(parts)


def run_tests(
    workspace: Path,
    test_path: str = ".",
    timeout: int = 120,
    python_executable: str | None = None,
) -> TestResult:
    """Run pytest in `workspace`. Uses `python_executable` if given (lets you
    point at a target project's venv); otherwise the current interpreter."""
    interpreter = python_executable or sys.executable
    cmd = [interpreter, "-m", "pytest", test_path, "-v", "--tb=short"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        return TestResult(
            success=False,
            return_code=-1,
            stdout=(e.stdout or "") if isinstance(e.stdout, str) else "",
            stderr=(e.stderr or "") if isinstance(e.stderr, str) else "",
            timed_out=True,
        )
    except (FileNotFoundError, OSError) as e:
        return TestResult(
            success=False,
            return_code=-1,
            stdout="",
            stderr=f"failed to launch interpreter {interpreter!r}: {e}",
        )

    no_tests = proc.returncode == PYTEST_NO_TESTS_COLLECTED
    success = proc.returncode == 0
    return TestResult(
        success=success,
        return_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        no_tests_collected=no_tests,
    )
