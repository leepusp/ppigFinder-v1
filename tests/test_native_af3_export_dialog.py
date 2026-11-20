"""Regression coverage for exporting selected ORFs after filtering or sorting."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ppigfinder.integrations.af3.schema import load_native_json

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PyQt6 is optional")
class NativeAF3ExportDialogTests(unittest.TestCase):
    def test_selection_uses_orf_identity_and_passes_saved_json_to_destination(self):
        from ppigfinder.ui import af3_export

        app = QApplication.instance() or QApplication([])
        window = QMainWindow()
        window.orfs = [{"protein": "AAAA"}, {"protein": "CCCC"}, {"protein": "GGGG*"}]
        window._parse_orf_idx_from_text = lambda label: int(label.removeprefix("ORF")) - 1
        table = window._orf_table = QTableWidget(2, 1, window)
        for row, label in enumerate(("ORF3", "ORF2")):
            item = QTableWidgetItem(label)
            table.setItem(row, 0, item)
            item.setSelected(True)

        with tempfile.TemporaryDirectory() as directory:
            for destination, callback in (
                ("Local / container runner", "af3_runner_dialog.show_af3_runner_dialog"),
                ("Remote SSH/SFTP upload", "remote_connections_dialog.show_remote_connections_dialog"),
            ):
                with self.subTest(destination=destination):
                    path = Path(directory) / "job.json"
                    with patch.object(af3_export.QInputDialog, "getItem", return_value=(destination, True)), \
                         patch.object(af3_export.QFileDialog, "getSaveFileName", return_value=(str(path), "")), \
                         patch(f"ppigfinder.ui.{callback}") as show:
                        self.assertTrue(af3_export.prepare_selected_orfs_for_native_af3(window))
                    show.assert_called_once_with(window, path)
                    payload = load_native_json(path)
                    self.assertEqual(payload["name"], "ORF2_ORF3")
                    self.assertEqual([chain["protein"]["sequence"] for chain in payload["sequences"]],
                                     ["CCCC", "GGGG"])
