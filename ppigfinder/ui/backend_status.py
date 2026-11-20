#!/usr/bin/env python3
"""Capabilities and optional integrations dialog for the existing Qt GUI."""
from __future__ import annotations

try:
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout
except ImportError:
    from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout

from ppigfinder.infrastructure.capabilities import collect_capabilities
from ppigfinder.ui.widgets.backend_status_widget import BackendStatusWidget


def _backend_rows(detailed: bool = False) -> list[dict]:
    """Keep the previous UI helper contract; detection is always offline/fast."""
    return [
        {
            "backend": capability.label,
            "status": capability.status.value,
            "operations": ", ".join(capability.operations),
            "details": capability.detail,
        }
        for capability in collect_capabilities()
    ]


class BackendStatusDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Capabilities and Integrations")
        self.resize(920, 480)
        layout = QVBoxLayout(self)

        self.widget = BackendStatusWidget(self)
        self.widget.set_backends(_backend_rows())
        layout.addWidget(self.widget)

        buttons = QHBoxLayout()
        refresh_button = QPushButton("Refresh local detection")
        refresh_button.clicked.connect(self.refresh_detailed)
        buttons.addWidget(refresh_button)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def refresh_detailed(self) -> None:
        self.widget.set_backends(_backend_rows(detailed=True))


def show_backend_status_dialog(window) -> None:
    dialog = BackendStatusDialog(window)
    dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()


def install_backend_status_action(window) -> None:
    """Install in the existing GUI; no edits to legacy_v29_14.py."""
    from ppigfinder.ui.menu_installers import install_action_once

    window.show_backend_status = lambda: show_backend_status_dialog(window)
    install_action_once(
        window, "System", "Capabilities and Integrations",
        "_ppig_backend_status_action_installed", show_backend_status_dialog,
    )
