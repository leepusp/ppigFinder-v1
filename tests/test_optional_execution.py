from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ppigfinder.services.structure_prediction_service import (
    StructuralPredictionRequest,
    prepare_structural_prediction_batch,
)
from ppigfinder.structure_prediction.models import SequenceTarget
from ppigfinder.structure_prediction.hpc_planner import plan_hpc_resources
from ppigfinder.structure_prediction.models import PredictionJobSpec
from ppigfinder.structure_prediction.slurm_renderer import render_sbatch_header


class OptionalExecutionTests(unittest.TestCase):
    def make_request(self, root, **kwargs):
        return StructuralPredictionRequest(
            base_job_id='optional_execution_test',
            root_dir=Path(root),
            targets=[SequenceTarget('A', 'M' * 40), SequenceTarget('B', 'M' * 50)],
            backend_ids=('af3',),
            **kwargs,
        )

    def test_export_does_not_require_scheduler(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = prepare_structural_prediction_batch(self.make_request(tmp))
            self.assertIsNone(result.slurm_scripts)
            self.assertTrue(result.artifacts.valid)
            self.assertEqual(result.artifacts.af3_input_count, 1)
            self.assertFalse((Path(tmp) / 'slurm').exists())

    def test_generic_scheduler_does_not_fake_gpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'GPU resources are unconfigured'):
                prepare_structural_prediction_batch(
                    self.make_request(tmp, execution_mode='slurm', cluster='generic_slurm')
                )
            self.assertFalse((Path(tmp) / "slurm").exists())

    def test_site_profile_is_optional(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = prepare_structural_prediction_batch(
                self.make_request(tmp, execution_mode='slurm', cluster='davinci')
            )
            self.assertIsNotNone(result.slurm_scripts)
            text = result.slurm_scripts.scripts[0].script_path.read_text()
            self.assertIn('--partition=max50', text)
            self.assertNotIn('module load alphafold3/1.0', text)

    def test_abstract_partition_is_not_rendered(self):
        job = PredictionJobSpec('A_B', 'af3', [SequenceTarget('A', 'M' * 40)])
        plan = plan_hpc_resources(job)
        text = render_sbatch_header(plan)
        self.assertNotIn('--partition=gpu_shared_or_standard', text)


if __name__ == '__main__':
    unittest.main()
