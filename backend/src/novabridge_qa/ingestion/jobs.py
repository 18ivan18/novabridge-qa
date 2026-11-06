"""In-memory job registry. Jobs are lost on restart, which is a deliberate prototype trade-off."""

import threading
import uuid
from dataclasses import dataclass, replace
from typing import Literal

JobStatus = Literal["queued", "parsing", "embedding", "indexed", "failed"]


@dataclass(frozen=True)
class Job:
    job_id: str
    doc_id: str
    status: JobStatus = "queued"
    progress: int = 0
    error: str | None = None
    chunks: int | None = None


class JobRegistry:
    """Hands out immutable snapshots, so a reader never sees a half-applied update."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, doc_id: str) -> Job:
        job = Job(job_id=uuid.uuid4().hex, doc_id=doc_id)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(
        self,
        job_id: str,
        status: JobStatus,
        progress: int,
        *,
        error: str | None = None,
        chunks: int | None = None,
    ) -> Job:
        with self._lock:
            job = replace(
                self._jobs[job_id], status=status, progress=progress, error=error, chunks=chunks
            )
            self._jobs[job_id] = job
        return job
