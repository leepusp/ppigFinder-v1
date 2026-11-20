from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ppigfinder.integrations.af3.schema import (
    read_protein_fasta, write_native_json, validate_native_payload, load_native_json,
)
from ppigfinder.integrations.af3.runner import AF3RunnerConfig, build_af3_command, run_af3
from ppigfinder.integrations.af3.cli import main


class AF3IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fasta = self.root / "pairs.faa"
        self.fasta.write_text(">bait\nMKTAYIAK\n>prey\nMKWVTFIS\n", encoding="utf-8")
        self.json_path = self.root / "native.json"
        self.native = write_native_json(self.json_path, read_protein_fasta(self.fasta), "bait_prey", [1, 2])
        self.out = self.root / "results"

    def test_native_one_object_not_list(self):
        payload = json.loads(self.json_path.read_text())
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["dialect"], "alphafold3")
        self.assertEqual(payload["modelSeeds"], [1, 2])
        self.assertEqual([x["protein"]["id"] for x in payload["sequences"]], ["A", "B"])

    def test_reject_server_dialect_and_duplicate_chain_ids(self):
        payload = load_native_json(self.json_path)
        with self.assertRaisesRegex(ValueError, "one object"):
            validate_native_payload([payload])
        payload["sequences"][1]["protein"]["id"] = "A"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_native_payload(payload)

    def test_official_cmd_flags_are_correct_and_dry_run(self):
        script = self.root / "run_alphafold.py"
        script.touch()
        models, db = self.root / "models", self.root / "database"
        models.mkdir()
        db.mkdir()
        cfg = AF3RunnerConfig(mode="official", script=str(script), python=sys.executable,
                              model_dir=str(models), db_dir=str(db))
        args = build_af3_command(cfg, self.native, self.out)
        self.assertIn(f"--json_path={self.native}", args)
        self.assertNotIn("--json-path", args)
        self.assertEqual(args, run_af3(cfg, self.native, self.out))
        self.assertFalse(self.out.exists())

    def test_docker_requires_external_resources_and_mounts(self):
        models, db = self.root / "models", self.root / "database"
        models.mkdir()
        db.mkdir()
        cfg = AF3RunnerConfig(mode="docker", model_dir=str(models), db_dir=str(db))
        with patch("ppigfinder.integrations.af3.runner._binary", return_value="/usr/bin/docker"):
            args = build_af3_command(cfg, self.native, self.out)
        self.assertIn("--gpus", args)
        self.assertIn("--json_path=/ppig_input/native.json", args)
        self.assertFalse(self.out.exists())

    def test_wrapper_uses_wrapper_flags_no_scheduler(self):
        cfg = AF3RunnerConfig(mode="wrapper", wrapper_command="af3")
        with patch("ppigfinder.integrations.af3.runner._binary", return_value="/usr/bin/af3"):
            args = build_af3_command(cfg, self.native, self.out)
        self.assertIn("--json-path", args)
        self.assertNotIn("--json_path", args)
        self.assertIn("--executor", args)
        self.assertEqual(args[args.index("--executor") + 1], "local")

    def test_empty_and_ambiguous_sequences_rejected(self):
        self.fasta.write_text(">bad\nMX\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            read_protein_fasta(self.fasta)

    def test_cli_validation_without_af3_installation(self):
        self.assertEqual(main(["validate", "--json", str(self.native)]), 0)


if __name__ == "__main__":
    unittest.main()
