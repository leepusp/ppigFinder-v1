"""Non-blocking native AF3 launcher dialog; integrates with legacy GUI via menu.

AF3 runs as a separate QProcess, not in the Qt event loop. No scheduler or
remote transport is needed. Docker/official engine must be installed separately.
"""
from __future__ import annotations

import os
import shlex
from pathlib import Path

try:
    from PyQt6.QtCore import QProcess
    from PyQt6.QtWidgets import (
        QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
        QLineEdit, QComboBox, QPushButton, QPlainTextEdit, QMessageBox, QVBoxLayout,
    )
except ImportError:
    from PyQt5.QtCore import QProcess
    from PyQt5.QtWidgets import (
        QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
        QLineEdit, QComboBox, QPushButton, QPlainTextEdit, QMessageBox, QVBoxLayout,
    )

from ppigfinder.integrations.af3.runner import AF3RunnerConfig, build_af3_command


class AF3RunnerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AlphaFold 3 — Optional Local/Container Runner")
        self.resize(900, 650)
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self._stdout)
        self.process.readyReadStandardError.connect(self._stderr)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)
        self._active = False

        layout = QVBoxLayout(self)
        warning = QLabel(
            "Native AF3 input only. AF3 itself, model parameters, databases and GPU "
            "are optional external requirements. AlphaFold Server export is a separate workflow."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItems(["wrapper", "official", "docker"])
        self.mode.setCurrentText(os.getenv("PPIGFINDER_AF3_MODE", "wrapper"))
        form.addRow("Execution mode", self.mode)

        def field(label, env_name, default=""):
            edit = QLineEdit(os.getenv(env_name, default))
            form.addRow(label, edit)
            return edit

        self.input_json = field("Native JSON", "PPIGFINDER_AF3_JSON")
        browse_in = QPushButton("Browse native JSON...")
        browse_in.clicked.connect(self._browse_input)
        form.addRow("", browse_in)
        self.output_dir = field("Output directory", "PPIGFINDER_AF3_OUTPUT")
        browse_out = QPushButton("Choose output directory...")
        browse_out.clicked.connect(self._browse_output)
        form.addRow("", browse_out)
        self.model_dir = field("Model weights directory", "PPIGFINDER_AF3_MODELS")
        self.db_dir = field("Database directory", "PPIGFINDER_AF3_DATABASES")
        self.script = field("Official run_alphafold.py", "PPIGFINDER_AF3_SCRIPT")
        self.python = field("AF3 Python (official mode)", "PPIGFINDER_AF3_PYTHON")
        self.image = field("Docker image", "PPIGFINDER_AF3_IMAGE", "alphafold3")
        self.wrapper = field("AF3 wrapper executable", "PPIGFINDER_AF3_WRAPPER", "af3")
        layout.addLayout(form)

        row = QHBoxLayout()
        self.preview_button = QPushButton("Check configuration / Preview")
        self.preview_button.clicked.connect(self.preview)
        row.addWidget(self.preview_button)
        self.run_button = QPushButton("Execute locally")
        self.run_button.clicked.connect(self.execute)
        row.addWidget(self.run_button)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        row.addWidget(self.close_button)
        layout.addLayout(row)

        self.log = QPlainTextEdit(self)
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        self.log.setPlaceholderText("Preflight and process output appear here.")
        layout.addWidget(self.log)

    def _browse_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "Native AF3 JSON", "", "JSON (*.json)")
        if path:
            self.input_json.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Output directory")
        if path:
            self.output_dir.setText(path)

    def _config(self) -> AF3RunnerConfig:
        return AF3RunnerConfig(
            mode=self.mode.currentText(), model_dir=self.model_dir.text().strip(),
            db_dir=self.db_dir.text().strip(), script=self.script.text().strip(),
            python=self.python.text().strip(), docker_image=self.image.text().strip(),
            wrapper_command=self.wrapper.text().strip(),
        )

    def _command(self):
        if not self.input_json.text().strip() or not self.output_dir.text().strip():
            raise ValueError("Select native AF3 JSON and an output directory")
        return build_af3_command(self._config(), self.input_json.text(), self.output_dir.text())

    def preview(self):
        try:
            argv = self._command()
        except (OSError, ValueError) as exc:
            self.log.appendPlainText("Preflight failed: " + str(exc))
            return False
        self.log.appendPlainText("Preflight: basic paths and native JSON OK. Engine/GPU not exercised.")
        self.log.appendPlainText("$ " + shlex.join(argv) + "\n")
        return True

    def execute(self):
        if self._active:
            return
        try:
            argv = self._command()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "AF3 preflight", str(exc))
            return
        answer = QMessageBox.question(
            self, "Run AlphaFold 3?",
            "This starts a potentially long GPU/CPU computation using your configured "
            "local runtime. No HPC queue is submitted automatically. Continue?",
        )
        yes = QMessageBox.StandardButton.Yes if hasattr(QMessageBox, 'StandardButton') else QMessageBox.Yes
        if answer != yes:
            return
        Path(self.output_dir.text()).expanduser().mkdir(parents=True, exist_ok=True)
        self.run_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self._active = True
        self.log.appendPlainText("Starting: " + shlex.join(argv))
        self.process.start(argv[0], argv[1:])

    def _stdout(self):
        self.log.appendPlainText(bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace"))

    def _stderr(self):
        self.log.appendPlainText(bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace"))

    def _process_error(self, error):
        self.log.appendPlainText(f"AF3 process error: {self.process.errorString()}")
        stopped = QProcess.ProcessState.NotRunning if hasattr(QProcess, "ProcessState") else QProcess.NotRunning
        if self.process.state() == stopped:
            self._active = False
            self.preview_button.setEnabled(True)
            self.run_button.setEnabled(True)

    def _finished(self, exit_code, exit_status):
        self._active = False
        self.preview_button.setEnabled(True)
        self.run_button.setEnabled(True)
        self.log.appendPlainText(f"AF3 process exited: code={exit_code}, status={exit_status}. Verify output files and QC.")

    def closeEvent(self, event):
        if self._active:
            QMessageBox.warning(self, "AF3 still running", "The local AF3 process is running. Keep this window open until it exits.")
            event.ignore()
            return
        super().closeEvent(event)


def show_af3_runner_dialog(window, input_path=None):
    dialog = AF3RunnerDialog(window)
    if input_path is not None:
        dialog.input_json.setText(str(input_path))
    dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
