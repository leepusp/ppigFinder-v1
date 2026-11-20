"""Scheduler operations independent of Qt, SSH and prediction engines."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class JobStatus:
    job_id: str
    state: str
    reason: str
    exit_code: str | None = None


class SchedulerError(RuntimeError):
    """The scheduler failed or returned an unusable response."""


class SchedulerAdapter(Protocol):
    def validate(self, script: str) -> str: ...
    def submit(self, script: str) -> str: ...
    def status(self, job_id: str) -> JobStatus | None: ...
    def cancel(self, job_id: str) -> None: ...
    def log_paths(self, job_id: str) -> dict[str, str]: ...
