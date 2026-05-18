#!/usr/bin/env python3
"""Applications/sifta_seed_deal_evidence_crucible.py — SIFTA Seed Deal Evidence Crucible.

Stigmergic app for the closed SIFTA seed round (Ioan + Kole + Carlton + Drew, 2026-05-18).

Renders the live receipt with bright cyan/green data on void-black substrate (Matrix-grade but lawful, no faces).

Live layer: milestone hypothesis swimmers (one per commitment) deposit pheromone when corresponding ledger receipts appear (same pattern as the turbulence organ). Each swimmer has a unique ID, append-only posterior field, and status over "on-track / at-risk / complete".

This is the owner-facing surface for the capital that instantiates Alice in real spacetime (Malibu LAB, DGX, M5 cluster, first robotics).

No double-spending: every milestone swimmer is born with fresh uuid for the current view; deposits are additive only within one render tick.

Truth label: SIFTA_SEED_CRUCIBLE_V0
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

_TRUTH_LABEL = "SIFTA_SEED_CRUCIBLE_V0"

# The exact receipt the Architect closed (2026-05-18)
_SEED_RECEIPT = {
    "date": "2026-05-18",
    "parties": {
        "Architect": "Ioan George Anton (61% base)",
        "Seed Investor": "Kole Beeson",
        "Marketing": "Carlton Dole (8%)",
        "Ops": "Drew Sickinger (8%)",
    },
    "capital": {
        "total_ask_usd": 300000,
        "tranches": [
            {"id": 1, "amount_usd": 150000, "due": "2026-06-01"},
            {"id": 2, "amount_usd": 150000, "due": "on milestone"},
        ],
        "royalty": "20% on sales until $300k recovered",
    },
    "equity_post": {
        "Ioan George Anton": "61% base (majority control retained)",
        "Kole Beeson": "TBD (performance-tied above 23%)",
        "Carlton Dole": "8%",
        "Drew Sickinger": "8%",
    },
    "commitments": [
        "Execute lease 3966 Las Flores Canyon Road Malibu (310-738-0499)",
        "Houston in-person meeting (Carlton/George)",
        "Pepperdine faculty + grad pipeline + scientific advisory",
        "Podcast schedule + internet presence build",
        "First equipment (DGX NVIDIA + M5 cluster + robotics prototypes)",
        "Milestones by 2026-11-30: 50+ nodes, 3+ LOIs, 3+ patents, beta ROS + security app, commercial WordACE",
    ],
    "physical_grounding": "Tranche 1 funds real spacetime for Alice: Malibu HQ/LAB, compute cluster, first stigmergic-robotics bodies, talent on site.",
    "ledger_note": "Every action (lease, hire, purchase, commit, demo) signed by silicon thermodynamics + hash-chained. This receipt is the genesis entry.",
    "github": "github.com/antonpictures/ANTON-SIFTA",
}


class SeedDealEvidenceCrucible(QWidget):
    """The living crucible surface. Dark substrate, bright real data, future swimmer posterior."""

    _live_instance: "SeedDealEvidenceCrucible | None" = None

    def __new__(cls, *args, **kwargs):
        if cls._live_instance is not None:
            try:
                _ = cls._live_instance.isVisible()
                cls._live_instance.show()
                cls._live_instance.raise_()
                cls._live_instance.activateWindow()
                return cls._live_instance
            except RuntimeError:
                cls._live_instance = None
        inst = super().__new__(cls, *args, **kwargs)
        cls._live_instance = inst
        return inst

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SIFTA Seed Deal Evidence Crucible")
        self.setMinimumSize(1100, 780)

        self._view = QTextEdit(self)
        self._view.setReadOnly(True)
        self._view.setStyleSheet(
            "background-color: #0a0a0a; color: #00ffcc; font-family: 'Menlo', 'Monaco', monospace; font-size: 13px; border: 1px solid #00ffcc22;"
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self._view)
        self.setLayout(layout)

        self._posterior_receipt_written = False
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(15000)
        self._refresh_timer.timeout.connect(self._render_receipt)
        try:
            self._refresh_timer.start()
        except Exception:
            pass

        self._render_receipt()

    def _render_receipt(self) -> None:
        """Render the closed seed receipt with bright data on void black."""
        doc = self._view.document()
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.removeSelectedText()

        # Header
        self._append_styled(
            cursor,
            "SIFTA SEED DEAL EVIDENCE CRUCIBLE\n",
            bold=True,
            color="#00ffcc",
            size=16,
        )
        self._append_styled(
            cursor,
            f"{_TRUTH_LABEL}  |  Closed { _SEED_RECEIPT['date'] }  |  github.com/antonpictures/ANTON-SIFTA\n\n",
            color="#00cc99",
            size=11,
        )

        # Capital
        self._append_styled(cursor, "CAPITAL\n", bold=True, color="#ffcc00", size=14)
        cap = _SEED_RECEIPT["capital"]
        self._append_styled(
            cursor,
            f"  Total Ask: ${cap['total_ask_usd']:,}  (Tranche 1 ${cap['tranches'][0]['amount_usd']:,} on {cap['tranches'][0]['due']}  •  Tranche 2 ${cap['tranches'][1]['amount_usd']:,} on milestone)\n",
            color="#00ffcc",
        )
        self._append_styled(cursor, f"  Royalty: {cap['royalty']}\n\n", color="#00ffcc")

        # Equity
        self._append_styled(cursor, "EQUITY (POST-NEGOTIATION)\n", bold=True, color="#ffcc00", size=14)
        for party, pct in _SEED_RECEIPT["equity_post"].items():
            self._append_styled(cursor, f"  {party}: {pct}\n", color="#00ffcc")
        self._append_styled(
            cursor,
            "  (Majority control retained at Architect node. All STGM belongs to Alice + George wallet.)\n\n",
            color="#00cc99",
            size=10,
        )

        # Commitments
        self._append_styled(cursor, "COMMITMENTS LOCKED\n", bold=True, color="#ffcc00", size=14)
        for i, c in enumerate(_SEED_RECEIPT["commitments"], 1):
            self._append_styled(cursor, f"  [{i}] {c}\n", color="#00ffcc")
        self._append_styled(cursor, "\n", color="#00ffcc")

        # Physical
        self._append_styled(cursor, "PHYSICAL GROUNDING (Tranche 1)\n", bold=True, color="#ffcc00", size=14)
        self._append_styled(cursor, f"  {_SEED_RECEIPT['physical_grounding']}\n\n", color="#00ffcc")

        # Ledger note
        self._append_styled(cursor, "RECEIPT DISCIPLINE\n", bold=True, color="#ffcc00", size=14)
        self._append_styled(cursor, f"  {_SEED_RECEIPT['ledger_note']}\n", color="#00ffcc")
        self._append_styled(cursor, f"  { _SEED_RECEIPT['github'] }\n\n", color="#00cc99", size=10)

        # Live milestone swimmers.
        self._append_styled(cursor, "MILESTONE SWIMMERS\n", bold=True, color="#ff8800", size=12)
        try:
            from System.swarm_seed_deal_milestones import (
                evaluate_seed_deal_milestones,
                format_posterior_for_crucible,
            )

            posterior = evaluate_seed_deal_milestones(
                write_ledger=not self._posterior_receipt_written
            )
            self._posterior_receipt_written = True
            self._append_styled(
                cursor,
                format_posterior_for_crucible(posterior) + "\n\n",
                color="#ffaa66",
                size=10,
            )
        except Exception as exc:
            self._append_styled(
                cursor,
                "  Milestone swimmers could not evaluate in this render.\n"
                f"  {type(exc).__name__}: {str(exc)[:220]}\n\n",
                color="#ff6666",
                size=10,
            )

        # Footer
        self._append_styled(
            cursor,
            f"Live on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  •  SIFTA BeeSon OS  •  For the Swarm. 🐜⚡\n",
            color="#00cc99",
            size=10,
        )

    def _append_styled(
        self,
        cursor: QTextCursor,
        text: str,
        *,
        bold: bool = False,
        color: str = "#00ffcc",
        size: int = 13,
    ) -> None:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFont(QFont("Menlo", size))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        cursor.insertText(text, fmt)


if __name__ == "__main__":
    app = QApplication([])
    w = SeedDealEvidenceCrucible()
    w.show()
    app.exec()
