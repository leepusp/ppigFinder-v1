"""Offline genome-to-result coverage across the public service boundaries."""

import csv
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from ppigfinder.integrations.af3.runner import AF3RunnerConfig, run_af3
from ppigfinder.integrations.af3.schema import load_native_json, write_native_json
from ppigfinder.io.af3_table_export import write_af3_results_table
from ppigfinder.services.alphafold_results_service import AlphaFoldResultsService
from ppigfinder.services.genome_service import GenomeService
from ppigfinder.services.orf_service import ORFPredictionService
from ppigfinder.services.project_service import ProjectService


class LocalWorkflowTests(unittest.TestCase):
    def test_genome_to_local_process_result_and_reopened_project(self):
        with tempfile.TemporaryDirectory(prefix="ppig local workflow ") as directory:
            root = Path(directory)
            dna = "ATG" + "GCT" * 10 + "TAA" + "CCC" * 4 + "ATG" + "GGT" * 10 + "TAA"
            fasta = root / "reference.fna"
            fasta.write_text(f">synthetic_reference\n{dna}\n", encoding="utf-8")
            genbank = root / "reference.gbk"
            genbank.write_text(
                f"LOCUS       synthetic_reference {len(dna)} bp DNA linear\n"
                "FEATURES             Location/Qualifiers\n"
                '     CDS             1..36\n                     /gene="example_a"\n'
                f"ORIGIN\n        1 {dna.lower()}\n//\n",
                encoding="utf-8",
            )
            reader = GenomeService()
            genome = reader.load_by_extension(fasta)
            annotated = reader.load_by_extension(genbank)
            self.assertEqual(genome.sequence, annotated.sequence)
            self.assertEqual(len(annotated.features), 1)
            found = ORFPredictionService().predict_six_frame(
                genome.sequence, min_aa=9, start_codons={"ATG"},
            )
            selected = [orf for orf in found if orf["strand"] == "+"]
            proteins = [orf["protein"].rstrip("*") for orf in selected]
            self.assertEqual(proteins, ["M" + "A" * 10, "M" + "G" * 10])
            input_path = write_native_json(
                root / "native.json", list(zip(("ORF1", "ORF2"), proteins)), "reference_pair", [1],
            )
            self.assertEqual(load_native_json(input_path)["name"], "reference_pair")

            # Run a deterministic stand-in via the real local runner and subprocess.
            script = root / "run_alphafold.py"
            script.write_text(
                "import argparse, json\n"
                "from pathlib import Path\n"
                "p = argparse.ArgumentParser()\n"
                "for flag in ('json_path', 'model_dir', 'db_dir', 'output_dir'):\n"
                "    p.add_argument('--' + flag, required=True, type=Path)\n"
                "args = p.parse_args()\n"
                "job = json.loads(args.json_path.read_text(encoding='utf-8'))\n"
                "assert args.model_dir.is_dir() and args.db_dir.is_dir()\n"
                "target = args.output_dir / job['name']\n"
                "target.mkdir()\n"
                "lengths = [len(chain['protein']['sequence']) for chain in job['sequences']]\n"
                "ids = ['A'] * lengths[0] + ['B'] * lengths[1]\n"
                "pae = [[1.0 if a == b else 4.0 for b in ids] for a in ids]\n"
                "(target / 'reference_pair_summary_confidences.json').write_text("
                "json.dumps({'iptm': 0.75, 'ptm': 0.8}), encoding='utf-8')\n"
                "(target / 'reference_pair_confidences.json').write_text("
                "json.dumps({'token_chain_ids': ids, 'pae': pae}), encoding='utf-8')\n",
                encoding="utf-8",
            )
            models, databases, results = (root / name for name in ("models", "databases", "results"))
            models.mkdir()
            databases.mkdir()
            config = AF3RunnerConfig(
                mode="official", script=str(script), python=sys.executable,
                model_dir=str(models), db_dir=str(databases),
            )
            run_af3(config, input_path, results)
            self.assertFalse(results.exists())
            run_af3(config, input_path, results, execute=True)
            parsed = AlphaFoldResultsService().parse_root_sequential(results)
            self.assertEqual(AlphaFoldResultsService().parse_root_parallel(results), parsed)
            self.assertEqual(len(parsed), 1)
            result = parsed[0]
            self.assertEqual(result["iptm"], 0.75)
            self.assertEqual(result["pae_inter"], 4.0)
            self.assertNotEqual(result["summary_file"], result["confidence_file"])
            report = root / "results.tsv"
            write_af3_results_table(report, parsed)
            with report.open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual((row["name"], row["iptm"], row["pae_inter"]), ("reference_pair", "0.75", "4.0"))

            service = ProjectService()
            snapshot = service.build_snapshot_from_legacy_window(SimpleNamespace(
                genome_name=genome.name, dna_sequence=genome.sequence,
                current_fasta_path=str(fasta), sg_features=annotated.features, orfs=selected,
                _af3_analysis_results=parsed, _af3_analysis_dir=str(results),
            ))
            project_file = root / "project.ppigfinder.json"
            service.save(project_file, snapshot)
            reopened = SimpleNamespace(_update_orfs_list=Mock(), _genome_map=Mock())
            service.apply_snapshot_to_legacy_window(reopened, service.load(project_file))
            self.assertEqual(reopened.current_fasta_path, str(fasta))
            self.assertEqual(reopened.filtered_orfs, selected)
            self.assertEqual(reopened.sg_features, annotated.features)
            self.assertEqual(reopened._af3_analysis_results, parsed)
            reopened._update_orfs_list.assert_called_once_with()
            reopened._genome_map.set_data.assert_called_once_with(len(dna), selected, [], dna)

    def test_result_parser_does_not_use_summary_as_confidences(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "job_summary_confidences.json").write_text('{"iptm": 0.7}', encoding="utf-8")
            result = AlphaFoldResultsService().parse_directory(root)
            self.assertEqual(result["iptm"], 0.7)
            self.assertIsNone(result["confidence_file"])
