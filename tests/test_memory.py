import threading
from pathlib import Path

import pytest

from memory.store import SharedMemory


def test_record_attempt_creates_in_progress_row(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    aid = mem.record_attempt("agent-1", "add null guard", "input is None")
    attempts = mem.get_all_attempts()
    assert len(attempts) == 1
    assert attempts[0].attempt_id == aid
    assert attempts[0].status == "in_progress"
    assert attempts[0].started_at != ""
    assert attempts[0].ended_at is None


def test_record_result_flips_status(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    aid = mem.record_attempt("agent-1", "approach A", "hyp A")
    mem.record_result(aid, success=False, detail="still NPE")
    a = mem.get_all_attempts()[0]
    assert a.status == "failed"
    assert a.result_detail == "still NPE"
    assert a.ended_at is not None


def test_record_result_unknown_id_raises(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    with pytest.raises(ValueError):
        mem.record_result("att-deadbeef", success=True, detail="nope")


def test_failed_approaches_excludes_succeeded(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    a1 = mem.record_attempt("a1", "approach A", "h1")
    a2 = mem.record_attempt("a2", "approach B", "h2")
    mem.record_result(a1, success=False, detail="nope")
    mem.record_result(a2, success=True, detail="works")

    blocked = mem.get_failed_approaches()
    assert [b.approach for b in blocked] == ["approach A"]


def test_in_progress_blocks_retry(tmp_path: Path) -> None:
    """in_progress attempts MUST appear in get_failed_approaches so that a
    concurrent debugger reading mid-flight does not pick the same approach."""
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    mem.record_attempt("a1", "approach A", "h1")
    blocked = mem.get_failed_approaches()
    assert len(blocked) == 1
    assert blocked[0].status == "in_progress"


def test_concurrent_writes_no_loss(tmp_path: Path) -> None:
    """Hammer the store from N threads; every write must land."""
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    N = 25

    def worker(i: int) -> None:
        mem.record_attempt(f"agent-{i}", f"approach {i}", f"hypothesis {i}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    approaches = sorted(a.approach for a in mem.get_all_attempts())
    assert approaches == sorted(f"approach {i}" for i in range(N))


def test_persistence_across_instances(tmp_path: Path) -> None:
    mem1 = SharedMemory(tmp_path / "mem.json", task_id="t1")
    aid = mem1.record_attempt("a1", "approach A", "h1")
    mem1.record_result(aid, success=False, detail="failed reason")

    mem2 = SharedMemory(tmp_path / "mem.json", task_id="t1")
    attempts = mem2.get_all_attempts()
    assert len(attempts) == 1
    assert attempts[0].status == "failed"
    assert attempts[0].result_detail == "failed reason"


def test_has_succeeded(tmp_path: Path) -> None:
    mem = SharedMemory(tmp_path / "mem.json", task_id="t1")
    assert not mem.has_succeeded()
    aid = mem.record_attempt("a1", "approach A", "h1")
    assert not mem.has_succeeded()
    mem.record_result(aid, success=True, detail="works")
    assert mem.has_succeeded()
