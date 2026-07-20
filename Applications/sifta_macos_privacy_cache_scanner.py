#!/usr/bin/env python3
"""SIFTA macOS privacy/cache scanner surface."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_macos_privacy_cache_scanner import (
    scan_macos_privacy_cache_surfaces,
    summarize_for_owner,
)


class MacOSPrivacyCacheScannerApp(SiftaBaseWidget):
    APP_NAME = "macOS Privacy Cache Scanner"

    def build_ui(self, layout: QVBoxLayout) -> None:
        header = QLabel(
            "Metadata-only scan of ~/Library/Caches. "
            "It classifies Apple service stubs, SIFTA cache, and delete candidates without reading cache payloads."
        )
        header.setWordWrap(True)
        header.setStyleSheet("color: rgb(215,225,250); font-size: 12px;")
        layout.addWidget(header)

        bar = QHBoxLayout()
        self.scan_btn = QPushButton("Scan Now")
        self.scan_btn.clicked.connect(self.run_scan)
        bar.addWidget(self.scan_btn)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Name",
            "Relation",
            "Service",
            "Helps SIFTA",
            "Recommendation",
            "Owner controls",
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 2)

        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setFont(QFont("Menlo", 10))
        layout.addWidget(self.details, 1)

        self.run_scan()

    def _cell(self, text: object) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def run_scan(self) -> None:
        scan = scan_macos_privacy_cache_surfaces(write_receipt=True)
        entries = scan.get("entries") or []
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            controls = "; ".join(entry.get("owner_control_surfaces") or [])
            values = [
                entry.get("name", ""),
                entry.get("relation_to_sifta", ""),
                entry.get("service", ""),
                "yes" if entry.get("helps_sifta_now") else "no",
                entry.get("recommendation", ""),
                controls,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, self._cell(value))
        self.table.resizeColumnsToContents()
        self.details.setPlainText(summarize_for_owner(scan))


def main() -> int:
    app = QApplication(sys.argv)
    widget = MacOSPrivacyCacheScannerApp()
    widget.resize(1100, 720)
    widget.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
