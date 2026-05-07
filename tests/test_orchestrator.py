from pathlib import Path

from memory.store import SharedMemory
from orchestrator.run import _count_failures, _seed_workspace
from runner.tests import TestResult


def _result(stdout: str = "", success: bool = False) -> TestResult:
    return TestResult(success=success, return_code=0 if success else 1, stdout=stdout, stderr="")


def test_count_failures_zero_when_passing() -> None:
    assert _count_failures(_result(success=True)) == 0


def test_count_failures_parses_pytest_summary() -> None:
    out = "============= 3 failed, 2 passed in 0.5s ============="
    assert _count_failures(_result(out)) == 3


def test_count_failures_unparseable_returns_sentinel() -> None:
    """When stdout doesn't contain `N failed`, return a large number so the
    fork is treated as worst-case rather than mistakenly best."""
    n = _count_failures(_result("E: import error, no tests collected"))
    assert n >= 1000


def test_count_failures_picks_failed_not_passed() -> None:
    out = "============= 1 failed, 5 passed in 0.5s ============="
    assert _count_failures(_result(out)) == 1


def test_seed_workspace_writes_files(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    _seed_workspace(seed, {"test_x.py": "def test_x(): pass\n", "data.txt": "hi"})
    assert (seed / "test_x.py").read_text() == "def test_x(): pass\n"
    assert (seed / "data.txt").read_text() == "hi"


def test_find_latest_attempt_by_agent_returns_none_when_missing(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "m.json", task_id="t1")
    assert mem.find_latest_attempt_by_agent("dbg-1") is None


def test_find_latest_attempt_by_agent_returns_most_recent(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "m.json", task_id="t1")
    a1 = mem.record_attempt("dbg-1", "first", "h")
    a2 = mem.record_attempt("dbg-1", "second", "h")
    mem.record_attempt("dbg-2", "other", "h")
    found = mem.find_latest_attempt_by_agent("dbg-1")
    assert found is not None
    assert found.attempt_id == a2
    assert found.approach == "second"
    assert a1 != a2  # sanity


def test_find_latest_attempt_filters_by_agent(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "m.json", task_id="t1")
    mem.record_attempt("dbg-1", "approach A", "h")
    mem.record_attempt("dbg-2", "approach B", "h")
    a = mem.find_latest_attempt_by_agent("dbg-2")
    assert a is not None
    assert a.approach == "approach B"
