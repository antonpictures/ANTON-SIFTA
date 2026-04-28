#!/usr/bin/env python3
"""
Applications/sifta_sense_forge_widget.py — SIFTA Sense Forge.

Animal sense -> hardware organ -> stigmergic field -> truth receipt.

No in-app Alice chat. This app samples live ledgers/OS state, writes
.sifta_state/sense_bus.jsonl receipts, and displays exactly which senses
are REAL, DEMO, BROKEN, or UNKNOWN.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_app_focus import publish_focus
from System.swarm_franken_senses import sample_and_deposit
from System.swarm_sense_bus import DEFAULT_SENSE_BUS, StigmergicSenseBus

APP_NAME = "SIFTA Sense Forge"

COLORS = {
    "REAL": "#00ffc8",
    "DEMO": "#e0af68",
    "BROKEN": "#ff4466",
    "UNKNOWN": "#7a8199",
}


def _tail_text(path: Path, *, lines: int = 12) -> str:
    if not path.exists():
        return "(no sense_bus.jsonl receipts yet)"
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 65536))
            raw = handle.read().splitlines()[-lines:]
    except OSError:
        return "(receipt ledger unreadable)"
    out = []
    for row in raw:
        try:
            item = json.loads(row.decode("utf-8", "replace"))
        except Exception:
            continue
        if not isinstance(item, dict):
            continue
        out.append(
            f"{item.get('truth','?'):7s} "
            f"{item.get('animal','?'):<20.20s} "
            f"{item.get('name','?'):<28.28s} "
            f"value={float(item.get('value', 0.0) or 0.0):.3f} "
            f"conf={float(item.get('confidence', 0.0) or 0.0):.2f} "
            f"src={str(item.get('source',''))[:64]}"
        )
    return "\n".join(out) if out else "(no parseable sense receipts)"


class SenseForgeWidget(SiftaBaseWidget):
    APP_NAME = APP_NAME

    def build_ui(self, layout: QVBoxLayout) -> None:
        self._bus = StigmergicSenseBus(DEFAULT_SENSE_BUS)
        self._latest: dict[str, Any] = {}

        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: rgb(8,12,24); border: 1px solid rgb(45,60,92); "
            "border-radius: 8px; }"
        )
        header_lay = QGridLayout(header)
        header_lay.setContentsMargins(14, 12, 14, 12)
        title = QLabel("SIFTA Sense Forge")
        title.setFont(QFont("Menlo", 17, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(0,255,200);")
        header_lay.addWidget(title, 0, 0)

        subtitle = QLabel("animal sense -> hardware organ -> stigmergic field -> truth receipt")
        subtitle.setStyleSheet("color: rgb(160,170,205); font-size: 11px;")
        header_lay.addWidget(subtitle, 1, 0)

        self._field = QLabel("field: --")
        self._field.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._field.setFont(QFont("Menlo", 15, QFont.Weight.Bold))
        self._field.setStyleSheet("color: rgb(224,175,104);")
        header_lay.addWidget(self._field, 0, 1, 2, 1)
        layout.addWidget(header)

        controls = QHBoxLayout()
        self._sample_btn = QPushButton("Sample Live Senses")
        self._sample_btn.clicked.connect(lambda: self._sample(writer="sense_forge_button"))
        controls.addWidget(self._sample_btn)
        self._status = QLabel("Ready. REAL only follows a live receipt.")
        self._status.setStyleSheet("color: rgb(170,180,210);")
        controls.addWidget(self._status, 1)
        layout.addLayout(controls)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels([
            "Truth", "Animal", "Sense", "Hardware", "Value", "Conf", "Contribution", "Source"
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { background: rgb(6,8,16); color: rgb(220,225,245); "
            "gridline-color: rgb(40,45,70); font-family: Menlo; font-size: 11px; }"
            "QHeaderView::section { background: rgb(20,24,40); color: rgb(0,255,200); "
            "padding: 5px; border: 1px solid rgb(45,60,92); }"
        )
        layout.addWidget(self._table, 3)

        self._receipts = QPlainTextEdit()
        self._receipts.setReadOnly(True)
        self._receipts.setMaximumBlockCount(80)
        self._receipts.setStyleSheet(
            "QPlainTextEdit { background: rgb(5,7,12); color: rgb(180,200,230); "
            "border: 1px solid rgb(45,60,92); border-radius: 6px; "
            "font-family: Menlo; font-size: 10px; padding: 8px; }"
        )
        layout.addWidget(self._receipts, 2)

        self.make_timer(10_000, lambda: self._sample(writer="sense_forge_timer"))
        self._sample(writer="sense_forge_open")

    def _sample(self, *, writer: str) -> None:
        try:
            self._latest = sample_and_deposit(writer=writer)
            self._render()
            publish_focus(
                APP_NAME,
                "Sense Forge sampled live animal-hardware field",
                field_value=self._latest.get("field_value"),
                truth_counts=self._latest.get("truth_counts"),
            )
        except Exception as exc:
            self._status.setText(f"Sample failed: {type(exc).__name__}: {exc}")

    def _render(self) -> None:
        readings = list(self._latest.get("readings") or [])
        self._table.setRowCount(0)
        for row in readings:
            idx = self._table.rowCount()
            self._table.insertRow(idx)
            truth = str(row.get("truth", "UNKNOWN"))
            values = [
                truth,
                str(row.get("animal", "")),
                str(row.get("name", "")),
                str(row.get("hardware", "")),
                f"{float(row.get('value', 0.0) or 0.0):.3f}",
                f"{float(row.get('confidence', 0.0) or 0.0):.2f}",
                f"{float(row.get('contribution', 0.0) or 0.0):+.3f}",
                str(row.get("source", "")),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setForeground(QColor(COLORS.get(truth, COLORS["UNKNOWN"])))
                    item.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
                self._table.setItem(idx, col, item)

        counts = self._latest.get("truth_counts", {})
        self._field.setText(f"field: {float(self._latest.get('field_value', 0.0) or 0.0):+.4f}")
        self._status.setText(
            f"REAL={counts.get('REAL', 0)} DEMO={counts.get('DEMO', 0)} "
            f"BROKEN={counts.get('BROKEN', 0)} UNKNOWN={counts.get('UNKNOWN', 0)} "
            f"@ {time.strftime('%H:%M:%S')}"
        )
        self._receipts.setPlainText(_tail_text(DEFAULT_SENSE_BUS))


def create_widget(parent: QWidget | None = None) -> SenseForgeWidget:
    return SenseForgeWidget(parent)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SenseForgeWidget()
    w.resize(1180, 760)
    w.show()
    sys.exit(app.exec())
