"""GUI regression: reuse one validated SSH session for test -> upload."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
    from ppigfinder.ui import remote_connections_dialog as dialog_module
except ImportError:
    QApplication = None
    dialog_module = None


@unittest.skipIf(QApplication is None, "PyQt6 is optional")
class SSHSessionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_connected_session_reused_for_upload_and_closed_on_exit(self):
        calls = []
        prompts = []

        class FakeTransport:
            def __init__(self, profile, *, password=None):
                self.profile = profile
                self.password = password
                self.closed = False
                calls.append(self)

            def connect(self):
                return self

            def test(self):
                return {"status": "SSH_SFTP_CONNECTED"}

            def upload_file(self, path):
                return types.SimpleNamespace(as_dict=lambda: {"local_path": str(path)})

            def close(self):
                self.closed = True
                self.password = None

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "test_complex.json"
            fixture.write_text(json.dumps({
                "name": "test_complex", "modelSeeds": [1],
                "sequences": [{"protein": {"id": "A", "sequence": "MKTAYIAK"}}],
                "dialect": "alphafold3", "version": 1,
            }), encoding="utf-8")
            store = dialog_module.ProfileStore(root / "connections.json")
            with patch.object(dialog_module, "ProfileStore", return_value=store), \
                 patch.object(dialog_module, "SSHTransport", FakeTransport), \
                 patch.object(dialog_module, "preview_af3_wrapper", return_value="PREVIEW_ONLY"), \
                 patch.object(dialog_module, "QInputDialog", types.SimpleNamespace(getText=lambda *a, **k: (prompts.append(1) or "secret", True))), \
                 patch.object(dialog_module, "QFileDialog", types.SimpleNamespace(getOpenFileName=lambda *a, **k: (str(fixture), "JSON"))):
                window = dialog_module.RemoteConnectionsDialog()
                window.name.setText("davinci")
                window.host.setText("davinci")
                window.user.setText("testuser")
                window.port.setText("0")
                window.use_agent.setChecked(False)
                # Synchronous test harness: real implementation runs this in a QThread.
                window._start = lambda fn: window._complete(fn(), None)
                window._test()
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(prompts), 1)
                self.assertIn("SSH_SFTP_CONNECTED", window.log.toPlainText())
                window._upload()
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(prompts), 1)  # No second password prompt!
                self.assertIn("REMOTE_AF3_UPLOAD=PASS", window.log.toPlainText())
                self.assertEqual(window.log.toPlainText().count("Opening SSH/SFTP channel"), 1)
                self.assertIn("Reusing authenticated SSH/SFTP session", window.log.toPlainText())
                self.assertEqual(window._last_af3_json, str(fixture))
                window.done(0)
                self.assertTrue(calls[0].closed)


if __name__ == "__main__":
    unittest.main()
