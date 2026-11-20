#!/usr/bin/env python3
"""Pure presentation widget for optional tool and integration capabilities."""
from __future__ import annotations

try:
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
    from PyQt6.QtGui import QColor
    QT6 = True
except ImportError:
    from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
    from PyQt5.QtGui import QColor
    QT6 = False


_STATUS = {
    "available": ("Available", "#2e7d32"),
    "detected": ("Detected (unverified)", "#1565c0"),
    "not_configured": ("Not configured", "#b26a00"),
    "not_implemented": ("Not implemented", "#757575"),
}


class BackendStatusWidget(QWidget):
    """Display capability metadata supplied by the backend-neutral registry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Integration", "Status", "Operations", "Details"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch if QT6 else QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers if QT6 else QTableWidget.NoEditTriggers
        )
        layout.addWidget(self.table)

    def set_backends(self, rows: list[dict]) -> None:
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            raw_status = row.get("status")
            if raw_status is None:  # Compatibility with old boolean rows.
                raw_status = "available" if row.get("available") else "not_configured"
            status_text, color = _STATUS.get(raw_status, (str(raw_status), "#757575"))
            cells = [
                QTableWidgetItem(str(row.get("backend", ""))),
                QTableWidgetItem(status_text),
                QTableWidgetItem(str(row.get("operations", row.get("version", "")) or "")),
                QTableWidgetItem(str(row.get("details", "") or "")),
            ]
            for column, item in enumerate(cells):
                self.table.setItem(index, column, item)
                item.setToolTip(item.text())
            cells[1].setForeground(QColor(color))
