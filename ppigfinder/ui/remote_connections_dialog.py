"""Optional SSH/SFTP connection dialog, without scheduler or Qt blocking calls."""
from __future__ import annotations

import json
from pathlib import Path

try:
    from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
    from PyQt6.QtWidgets import (QDialog, QFormLayout, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QComboBox, QPushButton, QCheckBox, QFileDialog,
        QInputDialog, QMessageBox, QPlainTextEdit)
except ImportError:
    from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
    from PyQt5.QtWidgets import (QDialog, QFormLayout, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QComboBox, QPushButton, QCheckBox, QFileDialog,
        QInputDialog, QMessageBox, QPlainTextEdit)

from ppigfinder.integrations.remote import (
    OpenSSHTransport, ProfileStore, RemoteProfile, SSHTransport as ParamikoTransport,
    preview_af3_wrapper,
)
from ppigfinder.integrations.af3.schema import load_native_json


USE_OPENSSH = OpenSSHTransport.is_available()
SSHTransport = OpenSSHTransport if USE_OPENSSH else ParamikoTransport


class _ConnectionWorker(QObject):
    completed = pyqtSignal(object, object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    @pyqtSlot()
    def run(self):
        try:
            self.completed.emit(self._fn(), None)
        except Exception as exc:
            self.completed.emit(None, f"{type(exc).__name__}: {exc}")


class RemoteConnectionsDialog(QDialog):
    def __init__(self, parent=None, *, input_path=None):
        super().__init__(parent)
        self.setWindowTitle("Remote Connections — OpenSSH / SFTP" if USE_OPENSSH else "Remote Connections — SSH / SFTP")
        self.resize(880, 640)
        self._store = ProfileStore()
        self._busy = False
        self._thread = None
        self._worker = None
        self._session = None  # Authenticated SSH/SFTP, only while this dialog is open
        self._last_af3_json = ""
        self._prepared_af3_json = str(input_path) if input_path is not None else ""
        self._controls = []
        layout = QVBoxLayout(self)
        note = QLabel(
            "SSH uses your ~/.ssh/config and trusted host keys. Connections stay open "
            "until the dialog is closed. Test, upload and download via SFTP. "
            "No remote commands, GPU inference or scheduler jobs are started by this dialog. "
            "Host keys MUST already be trusted in ~/.ssh/known_hosts."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()
        self.saved = QComboBox()
        self.saved.currentTextChanged.connect(self._select_profile)
        form.addRow("Saved profile", self.saved)
        self.name = QLineEdit()
        self.host = QLineEdit()
        self.user = QLineEdit()
        self.port = QLineEdit("0")
        self.subdir = QLineEdit("ppigfinder-runs")
        self.wrapper = QLineEdit("af3")
        for label, field in (
            ("Profile name", self.name), ("SSH host / ~/.ssh/config alias", self.host),
            ("SSH username (optional)", self.user), ("Port (0: SSH config)", self.port),
            ("Directory inside remote home", self.subdir), ("AF3 wrapper for preview", self.wrapper),
        ):
            form.addRow(label, field)
        layout.addLayout(form)

        row = QHBoxLayout()
        self.save_button = QPushButton("Save profile")
        self.save_button.clicked.connect(self._save)
        row.addWidget(self.save_button)
        self.remove_button = QPushButton("Remove selected")
        self.remove_button.clicked.connect(self._remove)
        row.addWidget(self.remove_button)
        self.use_agent = QCheckBox(
            "Use existing SSH session, agent or keys" if USE_OPENSSH else "Use SSH agent or keys"
        )
        self.use_agent.setChecked(False)  # Password first; key/agent is explicit opt-in
        row.addWidget(self.use_agent)
        layout.addLayout(row)

        row = QHBoxLayout()
        self.test_button = QPushButton("Test SSH/SFTP")
        self.test_button.clicked.connect(self._test)
        row.addWidget(self.test_button)
        self.upload_button = QPushButton(
            "Upload prepared JSON + preview" if self._prepared_af3_json else "Upload AF3 JSON + preview"
        )
        self.upload_button.clicked.connect(self._upload)
        row.addWidget(self.upload_button)
        self.download_button = QPushButton("Download one result file")
        self.download_button.clicked.connect(self._download)
        row.addWidget(self.download_button)
        layout.addLayout(row)

        self.log = QPlainTextEdit(self)
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1200)
        layout.addWidget(self.log)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        self._controls = [self.saved, self.save_button, self.remove_button,
                          self.test_button, self.upload_button, self.download_button]
        self._refresh()

    def _refresh(self, selected=""):
        self.saved.blockSignals(True)
        self.saved.clear()
        self.saved.addItem("— Choose a profile —", "")
        for profile in self._store.list():
            self.saved.addItem(profile.name, profile.name)
        self.saved.blockSignals(False)
        match = self.saved.findData(selected)
        self.saved.setCurrentIndex(match if match >= 0 else 0)
        if selected:
            self._select_profile(selected)

    def _select_profile(self, _):
        name = self.saved.currentData()
        if not name:
            return
        try:
            p = self._store.get(name)
        except KeyError:
            return
        for widget, value in ((self.name, p.name), (self.host, p.host),
                              (self.user, p.username), (self.port, str(p.port)),
                              (self.subdir, p.remote_subdir), (self.wrapper, p.af3_wrapper)):
            widget.setText(value)

    def _current(self) -> RemoteProfile:
        return RemoteProfile(
            name=self.name.text().strip(), host=self.host.text().strip(),
            username=self.user.text().strip(), port=int(self.port.text().strip()),
            remote_subdir=self.subdir.text().strip(), af3_wrapper=self.wrapper.text().strip(),
        )

    def _save(self):
        try:
            p = self._current()
            self._store.save(p)
            self._refresh(p.name)
            self.log.appendPlainText(f"PROFILE_SAVED={p.name} (passwords and keys are never stored)")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Invalid profile", str(exc))

    def _remove(self):
        name = self.saved.currentData()
        if not name:
            return
        yes = QMessageBox.StandardButton.Yes if hasattr(QMessageBox, "StandardButton") else QMessageBox.Yes
        if QMessageBox.question(self, "Remove profile", f"Delete local connection profile '{name}'?") != yes:
            return
        try:
            self._store.delete(name)
            self._refresh()
            self.log.appendPlainText(f"PROFILE_REMOVED={name}")
        except (OSError, KeyError) as exc:
            QMessageBox.warning(self, "Remove profile", str(exc))

    def _credentials(self):
        if self.use_agent.isChecked():
            return None, True
        echo = QLineEdit.EchoMode.Password if hasattr(QLineEdit, "EchoMode") else QLineEdit.Password
        password, ok = QInputDialog.getText(self, "SSH password", "Password (not stored):", echo)
        return password if ok else None, ok

    def _disconnect_session(self):
        """Forget a previously authenticated session; never cache credentials."""
        old = self._session
        self._session = None
        if old is not None:
            try:
                old.close()
            except Exception as exc:
                self.log.appendPlainText("Session cleanup: " + type(exc).__name__)

    def _perform_with_session(self, profile, operation):
        """Run one SFTP operation, reusing a validated session for the same profile.

        The QThread worker is the only user of the SSH transport while busy.
        A failed operation invalidates it; the next attempt asks credentials.
        No password is persisted in configuration or the dialog itself.
        """
        if self._busy:
            return
        if self._session is not None and self._session.profile != profile:
            self._disconnect_session()
        if self._session is None:
            password, ok = self._credentials()
            if not ok:
                return
            self.log.appendPlainText("Opening SSH/SFTP channel (strict host-key verification)...")
        else:
            password = None
            self.log.appendPlainText(
                "Reusing authenticated SSH/SFTP session for " + profile.name
            )

        def action():
            # This closure is executed serially in a worker thread.
            if self._session is not None:
                return operation(self._session), None
            session = SSHTransport(profile, password=password)
            try:
                session.connect()
                value = operation(session)
                return value, session
            except Exception:
                session.close()
                raise
        self._start(action)

    def _start(self, fn):
        if self._busy:
            return
        self._busy = True
        for control in self._controls:
            control.setEnabled(False)
        self._thread = QThread(self)
        self._worker = _ConnectionWorker(fn)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.completed.connect(self._complete)
        self._worker.completed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._thread_done)
        self._thread.start()

    def _complete(self, result, error):
        if error:
            self._disconnect_session()
            self.log.appendPlainText("REMOTE_ERROR=" + str(error))
        else:
            value, new_session = result
            if new_session is not None:
                self._session = new_session
            self.log.appendPlainText(json.dumps(value, indent=2, ensure_ascii=False))
        self.log.appendPlainText("—")

    def _thread_done(self):
        self._busy = False
        for control in self._controls:
            control.setEnabled(True)
        self._worker = None
        self._thread = None

    def _test(self):
        try:
            profile = self._current()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid connection", str(exc))
            return
        self._perform_with_session(profile, lambda conn: conn.test())

    def _upload(self):
        try:
            profile = self._current()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid connection", str(exc))
            return
        filename = self._prepared_af3_json
        if not filename:
            initial = self._last_af3_json or str(Path.home())
            filename, _ = QFileDialog.getOpenFileName(
                self, "Upload native AF3 JSON", initial, "JSON (*.json)"
            )
        if not filename:
            return
        self._last_af3_json = filename  # Retry starts at the chosen file
        try:
            job = load_native_json(filename)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Not native AF3 JSON", str(exc))
            return

        def operation(conn):
            receipt = conn.upload_file(filename)
            return {"status": "REMOTE_AF3_UPLOAD=PASS", "receipt": receipt.as_dict(),
                    "warning": "Preview only. Never execute on an HPC login node.",
                    "af3_preview": preview_af3_wrapper(profile, receipt, job["name"])}

        self._perform_with_session(profile, operation)

    def _download(self):
        try:
            profile = self._current()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid connection", str(exc))
            return
        remote_relative, ok = QInputDialog.getText(
            self, "Download one file", "Remote path INSIDE profile root (e.g. results/example/model.cif):"
        )
        if not ok or not remote_relative.strip():
            return
        destination, _ = QFileDialog.getSaveFileName(self, "Save remote result")
        if not destination:
            return
        self._perform_with_session(
            profile,
            lambda conn: conn.download_file(remote_relative.strip(), destination),
        )

    def done(self, result):
        if self._busy:
            QMessageBox.warning(self, "Connection running", "Wait until the SSH/SFTP operation finishes.")
            return
        self._disconnect_session()
        super().done(result)


def show_remote_connections_dialog(window, input_path=None):
    dialog = RemoteConnectionsDialog(window, input_path=input_path)
    dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
