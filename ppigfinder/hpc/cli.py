"""Run Slurm operations on the configured cluster host."""

import argparse
from dataclasses import asdict
import json
import sys

from .scheduler_base import SchedulerError
from .slurm import SlurmAdapter


def main(argv=None):
    parser = argparse.ArgumentParser(description="Manage ppigfinder batch scripts on a Slurm host")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("resources", help="List partition and node configurations")
    commands.add_parser("validate", help="Check a script with Slurm without scheduling it").add_argument("script")
    submit = commands.add_parser("submit", help="Submit a prepared batch script")
    submit.add_argument("script")
    submit.add_argument("--confirm", action="store_true", required=True)
    commands.add_parser("status", help="Read queue or accounting status").add_argument("job_id")
    commands.add_parser("logs", help="Show the job's stdout and stderr paths").add_argument("job_id")
    cancel = commands.add_parser("cancel", help="Cancel one job")
    cancel.add_argument("job_id")
    cancel.add_argument("--confirm", action="store_true", required=True)
    args = parser.parse_args(argv)
    scheduler = SlurmAdapter()
    try:
        if args.action == "resources":
            result = {"resources": [asdict(resource) for resource in scheduler.resources()]}
        elif args.action == "validate":
            result = {"validation": scheduler.validate(args.script)}
        elif args.action == "submit":
            result = {"job_id": scheduler.submit(args.script)}
        elif args.action == "status":
            status = scheduler.status(args.job_id)
            result = asdict(status) if status else {"job_id": args.job_id, "state": "NOT_FOUND"}
        elif args.action == "logs":
            result = {"job_id": args.job_id, "paths": scheduler.log_paths(args.job_id)}
        else:
            scheduler.cancel(args.job_id)
            result = {"job_id": args.job_id, "cancellation_requested": True}
    except (SchedulerError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
