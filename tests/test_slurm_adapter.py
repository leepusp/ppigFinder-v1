"""Exercise the Slurm command contract without a configured cluster."""

import subprocess
import unittest
from unittest.mock import Mock, patch

from ppigfinder.hpc.cli import main
from ppigfinder.hpc.scheduler_base import JobStatus, SchedulerError
from ppigfinder.hpc.slurm import SlurmAdapter


def response(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class SlurmAdapterTests(unittest.TestCase):
    def setUp(self):
        self.run_command = Mock()
        self.scheduler = SlurmAdapter(run=self.run_command)

    def test_validation_and_submission_of_a_generic_script(self):
        self.run_command.side_effect = [
            response(stderr="Estimated start time: 16:00"), response("714;generic-cluster\n"),
        ]
        self.assertIn("16:00", self.scheduler.validate("generic run.sh"))
        self.assertEqual(self.scheduler.submit("generic run.sh"), "714")
        self.assertEqual(
            [call.args[0] for call in self.run_command.call_args_list],
            [
                ("sbatch", "--test-only", "--", "generic run.sh"),
                ("sbatch", "--parsable", "--", "generic run.sh"),
            ],
        )

    def test_queue_status_does_not_require_accounting(self):
        self.run_command.return_value = response("714|PENDING|Resources\n")
        self.assertEqual(self.scheduler.status("714"), JobStatus("714", "PENDING", "Resources"))
        self.run_command.assert_called_once()

    def test_accounting_fallback_reports_terminal_state_and_exit_code(self):
        self.run_command.side_effect = [
            response(stderr="slurm_load_jobs error: Invalid job id specified", code=1),
            response("713|COMPLETED||0:0\n714|OUT_OF_MEMORY|None|0:9\n"),
        ]
        self.assertEqual(self.scheduler.status("714"), JobStatus("714", "OUT_OF_MEMORY", "None", "0:9"))
        self.assertEqual(self.run_command.call_args.args[0][0], "sacct")

    def test_log_paths_and_cancel(self):
        self.run_command.side_effect = [
            response("JobId=714 StdErr=/scratch/run 2/err.log StdOut=/scratch/run 2/out.log WorkDir=/scratch"),
            response(),
        ]
        self.assertEqual(self.scheduler.log_paths("714"), {
            "stdout": "/scratch/run 2/out.log", "stderr": "/scratch/run 2/err.log",
        })
        self.scheduler.cancel("714")
        self.assertEqual(self.run_command.call_args.args[0], ("scancel", "714"))

    def test_unsafe_job_identifier_and_scheduler_error(self):
        with self.assertRaises(ValueError):
            self.scheduler.cancel("--user=other")
        self.run_command.assert_not_called()
        self.run_command.return_value = response(stderr="Unable to contact slurm controller", code=1)
        with self.assertRaisesRegex(SchedulerError, "Unable to contact"):
            self.scheduler.status("714")
        self.run_command.assert_called_once()

    def test_submission_timeout_is_not_retried(self):
        self.run_command.side_effect = subprocess.TimeoutExpired("sbatch", 30)
        with self.assertRaisesRegex(SchedulerError, "Check the queue"):
            self.scheduler.submit("job.sh")
        self.run_command.assert_called_once()

    def test_cli_requires_confirmation_for_queue_changes(self):
        with patch("ppigfinder.hpc.cli.SlurmAdapter") as scheduler, patch("sys.stderr"):
            for args in (["submit", "job.sh"], ["cancel", "714"]):
                with self.assertRaises(SystemExit) as exc:
                    main(args)
                self.assertEqual(exc.exception.code, 2)
        scheduler.assert_not_called()
