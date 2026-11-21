"""Verify the smoke check's submission gate and completion checks."""

from argparse import Namespace
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from ppigfinder.hpc.scheduler_base import JobStatus
from scripts.developer.check_slurm_lifecycle import MARKER, check_job


class SlurmLifecycleTests(unittest.TestCase):
    def test_preflight_never_submits(self):
        scheduler = Mock()
        scheduler.resources.return_value = [object()]
        args = Namespace(partition="cpu", account=None, qos=None, submit=False)
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            root = Path(directory)
            check_job(root, scheduler, args)
            self.assertIn("#SBATCH --partition=cpu", (root / "probe.slurm").read_text())
        self.assertIn("SLURM_PREFLIGHT=PASS", output.getvalue())
        scheduler.submit.assert_not_called()

    def test_submitted_job_requires_successful_exit_and_log_marker(self):
        scheduler = Mock()
        scheduler.resources.return_value = [object()]
        scheduler.submit.return_value = "123"
        scheduler.log_paths.return_value = {"stdout": "stdout.log", "stderr": "stderr.log"}
        scheduler.status.return_value = JobStatus("123", "COMPLETED", "", "0:0")
        args = Namespace(partition=None, account=None, qos=None, submit=True, wait=10)
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            root = Path(directory)
            (root / "stdout.log").write_text(MARKER + "\n", encoding="utf-8")
            (root / "stderr.log").touch()
            check_job(root, scheduler, args)
        self.assertIn("SLURM_LIFECYCLE=PASS", output.getvalue())
        scheduler.status.assert_called_once_with("123")
        scheduler.cancel.assert_not_called()
