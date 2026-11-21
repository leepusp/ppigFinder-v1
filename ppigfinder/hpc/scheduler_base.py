"""Scheduler operations independent of Qt, SSH and prediction engines."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class JobStatus:
    job_id: str
    state: str
    reason: str
    exit_code: str | None = None


@dataclass(frozen=True)
class PartitionResources:
    partition: str
    is_default: bool
    availability: str
    time_limit: str
    node_state: str
    node_count: int
    cpus_per_node: int | None
    memory_mib_per_node: int | None
    gres: str | None


class SchedulerError(RuntimeError):
    """The scheduler failed or returned an unusable response."""


class SchedulerAdapter(Protocol):
    def resources(self) -> list[PartitionResources]: ...
    def validate(self, script: str) -> str: ...
    def submit(self, script: str) -> str: ...
    def status(self, job_id: str) -> JobStatus | None: ...
    def cancel(self, job_id: str) -> None: ...
    def log_paths(self, job_id: str) -> dict[str, str]: ...
