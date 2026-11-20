"""Slurm operations on a host that already has the Slurm client configured."""

import re
import subprocess
from collections.abc import Callable

from .scheduler_base import JobStatus, SchedulerError


class SlurmAdapter:
    def __init__(self, *, run: Callable = subprocess.run, timeout: float = 30):
        self._run = run
        self._timeout = timeout

    def _command(self, *argv: str, absent_message: str = "", include_stderr: bool = False) -> str:
        try:
            result = self._run(argv, capture_output=True, text=True, timeout=self._timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            hint = " Check the queue before retrying a submission." if argv[0] == "sbatch" else ""
            raise SchedulerError(f"{argv[0]} timed out.{hint}") from exc
        except OSError as exc:
            raise SchedulerError(f"Could not start {argv[0]}: {exc}") from exc
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
            if absent_message and absent_message in detail.lower():
                return ""
            raise SchedulerError(f"{argv[0]}: {detail}")
        output = result.stdout.strip()
        if include_stderr and result.stderr.strip():
            output = "\n".join(filter(None, (output, result.stderr.strip())))
        return output

    @staticmethod
    def _job_id(job_id: str) -> str:
        if not re.fullmatch(r"[1-9][0-9]*", job_id):
            raise ValueError("Expected a positive numeric Slurm job ID")
        return job_id

    @staticmethod
    def _script(script: str) -> str:
        if not script.strip():
            raise ValueError("A batch script path is required")
        return script

    def validate(self, script: str) -> str:
        return self._command("sbatch", "--test-only", "--", self._script(script), include_stderr=True)

    def submit(self, script: str) -> str:
        output = self._command("sbatch", "--parsable", "--", self._script(script))
        match = re.fullmatch(r"([1-9][0-9]*)(?:;[^\s;]+)?", output)
        if not match:
            raise SchedulerError("Unexpected sbatch response. Check the queue before resubmitting.")
        return match.group(1)

    def status(self, job_id: str) -> JobStatus | None:
        job_id = self._job_id(job_id)
        queued = self._command(
            "squeue", "--noheader", f"--jobs={job_id}", "--format=%i|%T|%r",
            absent_message="invalid job id specified",
        )
        for line in queued.splitlines():
            fields = line.split("|", 2)
            if len(fields) == 3 and fields[0].strip() == job_id:
                return JobStatus(job_id, fields[1].strip(), fields[2].strip())

        accounted = self._command(
            "sacct", "--allocations", "--noheader", "--parsable2", f"--jobs={job_id}",
            "--format=JobIDRaw,State%40,Reason%80,ExitCode",
        )
        for line in accounted.splitlines():
            fields = line.split("|", 3)
            if len(fields) == 4 and fields[0].strip() == job_id:
                return JobStatus(job_id, fields[1].strip(), fields[2].strip(), fields[3].strip())
        return None

    def cancel(self, job_id: str) -> None:
        self._command("scancel", self._job_id(job_id))

    def log_paths(self, job_id: str) -> dict[str, str]:
        output = self._command("scontrol", "--oneliner", "show", "job", self._job_id(job_id))
        paths = {}
        for field, label in (("StdOut", "stdout"), ("StdErr", "stderr")):
            match = re.search(rf"(?:^|\s){field}=(.*?)(?=\s+[A-Za-z][A-Za-z0-9]*=|$)", output)
            if match and match.group(1) not in {"", "(null)", "None"}:
                paths[label] = match.group(1)
        return paths
