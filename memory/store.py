"""Shared negative-memory store for debugger agents.

Each debugger logs the approach it intends to try BEFORE attempting it
(status=in_progress). Concurrent debuggers reading the store therefore
see in-flight approaches as already taken and pick something different.
On completion, the row flips to succeeded or failed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from filelock import FileLock
from pydantic import BaseModel, Field

AttemptStatus = Literal["in_progress", "failed", "succeeded"]


class Attempt(BaseModel):
    attempt_id: str
    agent_id: str
    approach: str
    hypothesis: str
    status: AttemptStatus
    result_detail: str | None = None
    started_at: str
    ended_at: str | None = None


class MemoryFile(BaseModel):
    task_id: str
    attempts: list[Attempt] = Field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SharedMemory:
    def __init__(self, path: str | Path, task_id: str) -> None:
        self.path = Path(path)
        self.lock = FileLock(str(self.path) + ".lock")
        self.task_id = task_id
        with self.lock:
            if not self.path.exists():
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self._write(MemoryFile(task_id=task_id))

    def _read(self) -> MemoryFile:
        return MemoryFile.model_validate_json(self.path.read_text())

    def _write(self, data: MemoryFile) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(data.model_dump_json(indent=2))
        tmp.replace(self.path)

    def record_attempt(self, agent_id: str, approach: str, hypothesis: str) -> str:
        attempt_id = f"att-{uuid.uuid4().hex[:8]}"
        with self.lock:
            data = self._read()
            data.attempts.append(
                Attempt(
                    attempt_id=attempt_id,
                    agent_id=agent_id,
                    approach=approach,
                    hypothesis=hypothesis,
                    status="in_progress",
                    started_at=_now(),
                )
            )
            self._write(data)
        return attempt_id

    def record_result(self, attempt_id: str, success: bool, detail: str) -> None:
        with self.lock:
            data = self._read()
            for att in data.attempts:
                if att.attempt_id == attempt_id:
                    att.status = "succeeded" if success else "failed"
                    att.result_detail = detail
                    att.ended_at = _now()
                    self._write(data)
                    return
            raise ValueError(f"attempt_id {attempt_id} not found")

    def get_failed_approaches(self) -> list[Attempt]:
        """Approaches that should NOT be retried — failed or currently in-flight."""
        with self.lock:
            data = self._read()
        return [a for a in data.attempts if a.status in ("failed", "in_progress")]

    def get_all_attempts(self) -> list[Attempt]:
        with self.lock:
            data = self._read()
        return data.attempts

    def has_succeeded(self) -> bool:
        with self.lock:
            data = self._read()
        return any(a.status == "succeeded" for a in data.attempts)
