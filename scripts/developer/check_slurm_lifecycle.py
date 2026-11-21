"""Validate the ppigFinder Slurm adapter with an optional CPU-only test job."""

import argparse
from functools import partial
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ppigfinder.hpc.scheduler_base import SchedulerError
from ppigfinder.hpc.slurm import SlurmAdapter


MARKER = "PPIGFINDER_SLURM_CPU_JOB_OK"
FAILED_STATES = {
    "BOOT_FAIL", "CANCELLED", "DEADLINE", "FAILED", "NODE_FAIL",
    "OUT_OF_MEMORY", "PREEMPTED", "REVOKED", "TIMEOUT",
}


def site_value(value):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise argparse.ArgumentTypeError("Use a single Slurm name containing letters, numbers, dots, dashes or underscores")
    return value


def check_job(root, scheduler, args):
    script = root / "probe.slurm"
    directives = [
        "#!/bin/sh",
        "#SBATCH --job-name=ppigfinder-smoke",
        "#SBATCH --nodes=1",
        "#SBATCH --ntasks=1",
        "#SBATCH --cpus-per-task=1",
        "#SBATCH --mem=128M",
        "#SBATCH --time=00:02:00",
        "#SBATCH --output=stdout.log",
        "#SBATCH --error=stderr.log",
    ]
    for flag in ("partition", "account", "qos"):
        value = getattr(args, flag)
        if value:
            directives.append(f"#SBATCH --{flag}={value}")
    script.write_text("\n".join([*directives, f"printf '%s\\n' '{MARKER}'", ""]), encoding="ascii", newline="\n")

    resources = scheduler.resources()
    print(f"Slurm resource groups: {len(resources)}", flush=True)
    if not resources:
        raise SchedulerError("Slurm returned no visible partition resources")
    print(scheduler.validate(str(script)), flush=True)
    if not args.submit:
        print("SLURM_PREFLIGHT=PASS", flush=True)
        return

    job_id = scheduler.submit(str(script))
    print(f"SLURM_JOB_ID={job_id}", flush=True)
    finished = False
    try:
        paths = scheduler.log_paths(job_id)
        stdout = root / paths["stdout"]
        stderr = root / paths["stderr"]
        deadline = time.monotonic() + args.wait
        last_state = ""
        while time.monotonic() < deadline:
            status = scheduler.status(job_id)
            state = status.state.split()[0].rstrip("+") if status and status.state.strip() else ""
            if state != last_state:
                print(f"SLURM_STATE={state or 'WAITING_FOR_ACCOUNTING'}", flush=True)
                last_state = state
            if state == "COMPLETED" and status.exit_code == "0:0":
                finished = True
                if not stdout.is_file() or not stderr.is_file() or MARKER not in stdout.read_text(encoding="utf-8"):
                    raise SchedulerError(f"Missing expected smoke-test output in {root}")
                print("SLURM_LIFECYCLE=PASS", flush=True)
                return
            if state in FAILED_STATES or (state == "COMPLETED" and status.exit_code not in {None, "", "0:0"}):
                finished = True
                raise SchedulerError(f"Job {job_id} ended in {status.state} ({status.exit_code}): {status.reason}")
            time.sleep(2)
        raise SchedulerError(f"Timed out waiting for job {job_id}")
    finally:
        if not finished:
            try:
                scheduler.cancel(job_id)
            except SchedulerError as exc:
                print(f"Could not cancel smoke-test job {job_id}: {exc}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partition", type=site_value)
    parser.add_argument("--account", type=site_value)
    parser.add_argument("--qos", type=site_value)
    parser.add_argument("--wait", type=int, default=120, help="Seconds to wait for the submitted job")
    parser.add_argument("--submit", action="store_true", help="Actually submit the CPU-only smoke test")
    args = parser.parse_args()
    if args.wait <= 0:
        parser.error("--wait must be positive")
    root = Path(tempfile.mkdtemp(prefix="ppigfinder-slurm-", dir=Path.cwd()))
    print(f"SLURM_TEST_DIRECTORY={root}", flush=True)
    env = {key: value for key, value in os.environ.items() if not key.startswith("SBATCH_")}
    scheduler = SlurmAdapter(run=partial(subprocess.run, cwd=root, env=env))
    try:
        check_job(root, scheduler, args)
    except (KeyError, OSError, SchedulerError) as exc:
        parser.exit(1, f"Slurm check failed: {exc}\n")


if __name__ == "__main__":
    main()
