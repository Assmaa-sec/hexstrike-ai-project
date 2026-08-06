"""
Job: the unit of work the (future) web layer creates, polls, and streams.

Kept dependency-free and in-memory for now. The orchestrator drives a Job through
its statuses and appends events; a web backend later persists these and pushes the
event log to the client. The state machine mirrors the pipeline stages exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from ..contracts import Target, new_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    QUEUED = "queued"
    INGESTING = "ingesting"
    DEPLOYING = "deploying"
    RECON = "recon"
    ANALYZING = "analyzing"
    SYNTHESIZING = "synthesizing"
    EXPLOITING = "exploiting"
    REPORTING = "reporting"
    DONE = "done"
    FAILED = "failed"


@dataclass
class JobEvent:
    at: datetime
    status: JobStatus
    message: str = ""


@dataclass
class Job:
    id: str
    target: Target
    status: JobStatus = JobStatus.QUEUED
    events: list[JobEvent] = field(default_factory=list)
    error: str = ""
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @classmethod
    def create(cls, target: Target) -> "Job":
        job = cls(id=new_id(), target=target)
        job._log(JobStatus.QUEUED, "job created")
        return job

    def _log(self, status: JobStatus, message: str = "") -> None:
        self.status = status
        self.updated_at = _now()
        self.events.append(JobEvent(at=self.updated_at, status=status, message=message))

    # Orchestrator-facing API ------------------------------------------------

    def enter(self, status: JobStatus, message: str = "") -> None:
        """Advance to a new stage."""
        self._log(status, message)

    def note(self, message: str) -> None:
        """Attach a message without changing the current status."""
        self.events.append(JobEvent(at=_now(), status=self.status, message=message))

    def complete(self) -> None:
        self._log(JobStatus.DONE, "pipeline complete")

    def fail(self, error: str) -> None:
        self.error = error
        self._log(JobStatus.FAILED, error)


class JobStore:
    """In-memory job registry. Swap for a persistent backend behind the web layer."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def put(self, job: Job) -> None:
        self._jobs[job.id] = job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        return list(self._jobs.values())
