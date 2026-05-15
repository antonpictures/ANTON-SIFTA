#!/usr/bin/env python3
"""
Applications/sifta_lto_archive_demo_widget.py
══════════════════════════════════════════════════════════════════════════
StigAuth: SIFTA_LTO_ARCHIVE_DEMO_V1

Educational + planning demo for **Linear Tape-Open (LTO)** archival storage,
especially **LTO-10** public program claims (capacity tiers, LTFS, WORM,
marketing “quantum-safe” framing).  **This widget does not talk to tape
hardware** — macOS control of LTO drives requires vendor drivers / LTFS tools
outside this repo.

**Truth labels**
  * ``OBSERVED`` — this file exists; optional JSONL rows under ``.sifta_state/``.
  * ``SECONDARY_MEDIA`` — headline numbers from the LTO Program / vendor pages
    (Architect-paste + ``lto.org``); treat as **marketing / consortium spec
    copy**, not a lab measurement on your desk.
  * ``OPERATIONAL`` fit — SIFTA already lives on **append-only signed ledgers**
    and **offline-capable** exports; tape is a **cousin pattern** (air-gap,
    WORM-like immutability) for **human-operated** disaster recovery, not a
    second STGM quorum.

See ``https://www.lto.org/lto-10/`` and related press posts for primary web
anchors (do not trust this module’s constants if your procurement packet
differs — re-key numbers there).
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

TRUTH_LABEL = "SIFTA_LTO_ARCHIVE_DEMO_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)
_PLAN_LEDGER = _STATE / "lto_archive_demo_plans.jsonl"


def compressed_tb(native_tb: float, ratio: float = 2.5) -> float:
    """Vendor headline math: native * compression ratio (marketing lane)."""
    return round(float(native_tb) * float(ratio), 3)


def cartridges_needed(data_tb: float, cartridge_native_tb: float) -> int:
    if cartridge_native_tb <= 0:
        return 0
    return int(math.ceil(float(data_tb) / float(cartridge_native_tb)))


def _lto_reference_rows() -> list[tuple[str, str, str, str]]:
    """Static reference table (round marketing TB; not a drive probe)."""
    # LTO-7..9 numbers are widely cited program capacities; LTO-10 from LTO.org 2025 posts.
    return [
        ("LTO-7", "6 TB", "15 TB @ 2.5:1", "~300 MB/s native (class)"),
        ("LTO-8", "12 TB", "30 TB @ 2.5:1", "~360 MB/s native (class)"),
        ("LTO-9", "18 TB", "45 TB @ 2.5:1", "~400 MB/s native (class)"),
        (
            "LTO-10 (30 TB class)",
            "30 TB",
            "75 TB @ 2.5:1",
            "400 MB/s native (program claim)",
        ),
        (
            "LTO-10 (40 TB class)",
            "40 TB",
            "100 TB @ 2.5:1",
            "same drive — second cartridge tier (program claim)",
        ),
    ]


class LtoArchiveDemoWidget(QWidget):
    """LTO / cold-archive literacy for the Swarm (singleton per §7.6.2)."""

    _live_instance: Optional["LtoArchiveDemoWidget"] = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):  # noqa: ANN002
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                try:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                except Exception:
                    pass
                return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)

        self.setWindowTitle("SIFTA — LTO Cold Archive (demo)")
        self.resize(900, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("SIFTA — LTO / cold-archive field (demo)")
        title.setFont(QFont("Menlo", 15, QFont.Weight.Bold))
        root.addWidget(title)

        warn = QLabel(
            "<b>Scope</b>: education + rough sizing. "
            "<b>No tape drive I/O</b> from this widget — install OS-level LTFS / "
            "vendor tools separately if you mount hardware."
        )
        warn.setWordWrap(True)
        warn.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(warn)

        fit = QTextEdit()
        fit.setReadOnly(True)
        fit.setFont(QFont("Menlo", 10))
        fit.setMaximumHeight(160)
        fit.setPlainText(
            "Why this rhymes with SIFTA (measurement language):\n"
            "  • repair_log.jsonl + work receipts = append-only, signed, replayable "
            "state — same *shape* as WORM / compliance archives.\n"
            "  • Node sovereignty (covenant §3): tape is for **exported** bundles "
            "(hashes, seeds), never raw `.sifta_state/` cloning.\n"
            "  • Electricity → NAND/tape movement = thermodynamic bill; tape wins "
            "on **idle shelf watts** vs spinning rust for long retention (IDC-style "
            "claims — verify for your workload).\n"
            "  • STGM stays on **repair_log quorum** — tape does not mint tokens.\n"
            "\n"
            "LTO-10 highlights (program marketing / spec pages — SECONDARY_MEDIA):\n"
            "  • Two native tiers: 30 TB and 40 TB cartridges; compressed headline "
            "75 / 100 TB at 2.5:1.\n"
            "  • Native ~400 MB/s; compressed headline ~1200 MB/s (32 Gb FC).\n"
            "  • 15,104 data tracks; strontium-doped BaFe media (vendor materials).\n"
            "  • LTFS + WORM + hardware encryption story (AES-GCM-256 + "
            "PQ-ready key exchange framing per program copy).\n"
            "  • Generation-10 break: **no backward compatibility** to read older "
            "generation media in the new drive class (per program FAQ — confirm "
            "before you buy).\n"
            "\n"
            "Primary web anchor: https://www.lto.org/lto-10/"
        )
        root.addWidget(fit)

        tbl = QTableWidget(len(_lto_reference_rows()), 4)
        tbl.setHorizontalHeaderLabels(["Gen", "Native", "Compressed (2.5:1)", "Speed note"])
        for r, row in enumerate(_lto_reference_rows()):
            for c, val in enumerate(row):
                tbl.setItem(r, c, QTableWidgetItem(val))
        tbl.resizeColumnsToContents()
        root.addWidget(tbl, 1)

        plan = QLabel("Rough cartridge count (native tier, no compression)")
        plan.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        root.addWidget(plan)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Data to retain (TB):"))
        self.data_tb = QDoubleSpinBox()
        self.data_tb.setRange(0.01, 1_000_000.0)
        self.data_tb.setDecimals(3)
        self.data_tb.setValue(1145.0)
        row1.addWidget(self.data_tb)
        row1.addWidget(QLabel("Cartridge:"))
        self.tier = QComboBox()
        self.tier.addItems(["LTO-10 @ 30 TB native", "LTO-10 @ 40 TB native"])
        row1.addWidget(self.tier, 1)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_calc = QPushButton("Estimate cartridges")
        self.btn_calc.clicked.connect(self._on_calc)
        row2.addWidget(self.btn_calc)
        self.calc_out = QLabel("—")
        self.calc_out.setWordWrap(True)
        row2.addWidget(self.calc_out, 1)
        root.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Note (optional):"))
        self.note = QLineEdit()
        self.note.setPlaceholderText("e.g. nightly export of signed engram bundles …")
        row3.addWidget(self.note, 1)
        self.btn_log = QPushButton("Append plan row to lto_archive_demo_plans.jsonl")
        self.btn_log.clicked.connect(self._on_log_plan)
        row3.addWidget(self.btn_log)
        root.addLayout(row3)

        foot = QLabel(
            f"<code>{TRUTH_LABEL}</code> · ledger "
            f"<code>{_PLAN_LEDGER.relative_to(_REPO)}</code>"
        )
        foot.setTextFormat(Qt.TextFormat.RichText)
        foot.setStyleSheet("color:#8899aa;")
        root.addWidget(foot)

        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))
        self._on_calc()

    def closeEvent(self, event) -> None:  # noqa: N802
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        super().closeEvent(event)

    def _native_tb_choice(self) -> float:
        return 40.0 if self.tier.currentIndex() == 1 else 30.0

    def _on_calc(self) -> None:
        tb = self._native_tb_choice()
        n = cartridges_needed(self.data_tb.value(), tb)
        comp = compressed_tb(tb)
        self.calc_out.setText(
            f"Need ≥ {n} × {tb:.0f} TB native cartridges (~{comp:.0f} TB headline compressed each). "
            f"Data input: {self.data_tb.value():,.3f} TB."
        )

    def _on_log_plan(self) -> None:
        row = {
            "ts": time.time(),
            "truth_label": TRUTH_LABEL,
            "event": "LTO_ARCHIVE_PLAN_SNAPSHOT",
            "data_tb": float(self.data_tb.value()),
            "cartridge_tier_tb": self._native_tb_choice(),
            "cartridges_est": cartridges_needed(
                self.data_tb.value(), self._native_tb_choice()
            ),
            "note": (self.note.text() or "").strip()[:400],
        }
        try:
            with _PLAN_LEDGER.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError as e:
            QMessageBox.warning(self, "Ledger write failed", str(e))
            return
        QMessageBox.information(
            self,
            "Receipt",
            f"Appended one row to\n{_PLAN_LEDGER}",
        )


__all__ = [
    "LtoArchiveDemoWidget",
    "TRUTH_LABEL",
    "cartridges_needed",
    "compressed_tb",
]
