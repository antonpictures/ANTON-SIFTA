#!/usr/bin/env python3
"""
Applications/sifta_nvidia_join_widget.py — NVIDIA Joins SIFTA.

Embedded Qt app for the Predator v7 tournament lane. It shows which NVIDIA
public assets are useful to SIFTA and which ones are actually present on this
node. It never marks an asset REAL from a blog post alone.
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
from System.sifta_nvidia_join import (
    DEFAULT_RECEIPT_PATH,
    probe_and_write_receipt,
    recommended_next_step,
)

APP_NAME = "NVIDIA Joins SIFTA"

TRUTH_COLORS = {
    "REAL": "#00ffc8",
    "STUB": "#e0af68",
    "ONLINE": "#7aa2f7",
    "BLOCKED": "#ff4466",
}


def _tail_receipts(path: Path, *, limit: int = 4) -> str:
    if not path.exists():
        return "(no nvidia_join_receipts.jsonl rows yet)"
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 131072))
            rows = handle.read().splitlines()[-limit:]
    except OSError:
        return "(receipt ledger unreadable)"
    pretty = []
    for raw in rows:
        try:
            item = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            continue
        summary = item.get("summary", {})
        pretty.append(
            f"{time.strftime('%H:%M:%S', time.localtime(float(item.get('ts', 0) or 0)))} "
            f"REAL={summary.get('REAL', 0)} STUB={summary.get('STUB', 0)} "
            f"ONLINE={summary.get('ONLINE', 0)} BLOCKED={summary.get('BLOCKED', 0)}"
        )
        for asset in item.get("assets", [])[:8]:
            pretty.append(
                f"  {asset.get('local_truth','?'):7s} "
                f"{asset.get('name','?'):<28.28s} "
                f"{str(asset.get('local_detail',''))[:90]}"
            )
    return "\n".join(pretty) if pretty else "(no parseable NVIDIA receipts)"


class NvidiaJoinWidget(SiftaBaseWidget):
    APP_NAME = APP_NAME

    def build_ui(self, layout: QVBoxLayout) -> None:
        self._latest: dict[str, Any] = {}

        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: rgb(7,12,18); border: 1px solid rgb(55,80,90); "
            "border-radius: 8px; }"
        )
        grid = QGridLayout(header)
        grid.setContentsMargins(14, 12, 14, 12)

        title = QLabel("NVIDIA Joins SIFTA")
        title.setFont(QFont("Menlo", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(0,255,200);")
        grid.addWidget(title, 0, 0)

        subtitle = QLabel("optional vendor organs: GR00T / Isaac Lab / cuRobo / Warp / Cosmos")
        subtitle.setStyleSheet("color: rgb(160,180,205);")
        grid.addWidget(subtitle, 1, 0)

        self._summary = QLabel("probing...")
        self._summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._summary.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        self._summary.setStyleSheet("color: rgb(224,175,104);")
        grid.addWidget(self._summary, 0, 1, 2, 1)
        layout.addWidget(header)

        controls = QHBoxLayout()
        refresh = QPushButton("Probe Local NVIDIA Stack")
        refresh.clicked.connect(lambda: self._probe(writer="nvidia_join_button"))
        controls.addWidget(refresh)
        self._next = QLabel("REAL requires local import/cache. Blog posts are ONLINE, not runtime.")
        self._next.setStyleSheet("color: rgb(170,180,210);")
        controls.addWidget(self._next, 1)
        layout.addLayout(controls)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "Truth", "Asset", "Type", "Local Probe", "SIFTA Hook", "Next Step", "Risk"
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget { background: rgb(6,8,14); color: rgb(220,225,245); "
            "gridline-color: rgb(36,45,58); font-family: Menlo; font-size: 10px; }"
            "QHeaderView::section { background: rgb(15,24,32); color: rgb(0,255,200); "
            "padding: 5px; border: 1px solid rgb(45,60,70); }"
        )
        layout.addWidget(self._table, 3)

        self._receipts = QPlainTextEdit()
        self._receipts.setReadOnly(True)
        self._receipts.setMaximumBlockCount(120)
        self._receipts.setStyleSheet(
            "QPlainTextEdit { background: rgb(5,7,10); color: rgb(185,205,230); "
            "border: 1px solid rgb(45,60,70); border-radius: 6px; "
            "font-family: Menlo; font-size: 10px; padding: 8px; }"
        )
        layout.addWidget(self._receipts, 2)

        self.make_timer(30_000, lambda: self._probe(writer="nvidia_join_timer"))
        self._probe(writer="nvidia_join_open")

    def _probe(self, *, writer: str) -> None:
        try:
            self._latest = probe_and_write_receipt(writer=writer)
            self._render()
            publish_focus(
                APP_NAME,
                "NVIDIA optional organ readiness probe",
                summary=self._latest.get("summary"),
                truth_note=self._latest.get("truth_note"),
            )
        except Exception as exc:
            self._summary.setText("probe failed")
            self._next.setText(f"{type(exc).__name__}: {exc}")

    def _render(self) -> None:
        assets = list(self._latest.get("assets") or [])
        summary = self._latest.get("summary", {})
        self._summary.setText(
            f"REAL={summary.get('REAL', 0)} STUB={summary.get('STUB', 0)} "
            f"ONLINE={summary.get('ONLINE', 0)} BLOCKED={summary.get('BLOCKED', 0)}"
        )
        probes = []
        for row in assets:
            class Probe:
                key = row.get("key")
                local_truth = row.get("local_truth")

            probes.append(Probe())
        self._next.setText(recommended_next_step(probes))

        self._table.setRowCount(0)
        for row in assets:
            idx = self._table.rowCount()
            self._table.insertRow(idx)
            truth = str(row.get("local_truth", "ONLINE"))
            values = [
                truth,
                str(row.get("name", "")),
                str(row.get("asset_type", "")),
                str(row.get("local_detail", "")),
                str(row.get("sifta_hook", "")),
                str(row.get("next_step", "")),
                str(row.get("risk_note", "")),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 0:
                    item.setForeground(QColor(TRUTH_COLORS.get(truth, "#7a8199")))
                    item.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
                self._table.setItem(idx, col, item)

        self._receipts.setPlainText(_tail_receipts(DEFAULT_RECEIPT_PATH))


def create_widget(parent: QWidget | None = None) -> NvidiaJoinWidget:
    return NvidiaJoinWidget(parent)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = NvidiaJoinWidget()
    w.resize(1240, 780)
    w.show()
    sys.exit(app.exec())
