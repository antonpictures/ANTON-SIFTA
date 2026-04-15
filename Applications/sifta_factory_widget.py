#!/usr/bin/env python3
"""
sifta_factory_widget.py — Regenerative Factory: Stigmergic Manufacturing
═════════════════════════════════════════════════════════════════════════════
"Crypto for real... coordination software for regenerative production,
 not just moving labor and capital, but actual things." — Michel Bauwens

The Swarm coordinates physical reality.

Visualization: a decentralized 3D-printing farm producing ODRI robot
components.  Resource Foragers carry filament.  Assembly Swimmers deliver
parts.  Quality Sentinels catch defects.  STGM is minted ONLY when raw
material becomes a functional kinetic part.

Validated by the godfather of peer-to-peer theory on April 15, 2026.
"""
from __future__ import annotations

import math
import random
import sys
import time
from pathlib import Path
from typing import List

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QPlainTextEdit, QSplitter,
    QCheckBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from System.sifta_base_widget import SiftaBaseWidget
from System.regenerative_factory import (
    FactoryFloor, FactorySwimmer, CellType,
    spawn_factory_swimmers, step_factory, factory_telemetry,
    persist_ledger, COMPONENTS,
)

# ── Palette ──────────────────────────────────────────────────────
BG = "#060a12"

CELL_COLORS = {
    CellType.FLOOR:    "#0e1620",
    CellType.SOURCE:   "#1a3340",
    CellType.PRINTER:  "#1a2a1a",
    CellType.QC:       "#2a1a2a",
    CellType.ASSEMBLY: "#2a2a1a",
}

CELL_BORDER = {
    CellType.FLOOR:    "#1a2030",
    CellType.SOURCE:   "#2288aa",
    CellType.PRINTER:  "#22aa44",
    CellType.QC:       "#aa44cc",
    CellType.ASSEMBLY: "#ccaa22",
}

CELL_ICONS = {
    CellType.SOURCE:   ("S", "#44ccee"),
    CellType.PRINTER:  ("P", "#44ee66"),
    CellType.QC:       ("Q", "#cc66ff"),
    CellType.ASSEMBLY: ("A", "#eecc44"),
}


# ── Canvas ───────────────────────────────────────────────────────

class FactoryCanvas(FigureCanvas):
    def __init__(self, parent: QWidget | None = None):
        self._fig = Figure(figsize=(16, 9), facecolor=BG, dpi=85)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setMinimumSize(800, 500)

        gs = self._fig.add_gridspec(2, 2, width_ratios=[3, 1], height_ratios=[3, 1],
                                     wspace=0.1, hspace=0.12)
        self._ax_floor = self._fig.add_subplot(gs[0, 0])
        self._ax_inv = self._fig.add_subplot(gs[0, 1])
        self._ax_stgm = self._fig.add_subplot(gs[1, 0])
        self._ax_info = self._fig.add_subplot(gs[1, 1])
        for ax in [self._ax_floor, self._ax_inv, self._ax_stgm, self._ax_info]:
            ax.set_facecolor(BG)

        self._floor: FactoryFloor | None = None
        self._swimmers: List[FactorySwimmer] = []
        self._tick = 0
        self._stgm_history: List[float] = []
        self._printed_history: List[int] = []

    def set_data(self, floor, swimmers):
        self._floor = floor
        self._swimmers = swimmers

    def render_frame(self, telem: dict):
        if not self._floor:
            return
        self._tick += 1
        fl = self._floor

        self._stgm_history.append(telem.get("total_stgm", 0))
        self._printed_history.append(telem.get("total_printed", 0))
        if len(self._stgm_history) > 400:
            self._stgm_history = self._stgm_history[-300:]
            self._printed_history = self._printed_history[-300:]

        # ── Factory floor ────────────────────────────────────
        ax = self._ax_floor
        ax.clear()
        ax.set_facecolor(BG)
        ax.set_xlim(-0.5, fl.cols - 0.5)
        ax.set_ylim(-0.5, fl.rows - 0.5)
        ax.set_aspect("equal")
        ax.axis("off")

        # Draw grid cells
        for r in range(fl.rows):
            for c in range(fl.cols):
                cell = fl.cells[r][c]
                ct = cell.cell_type
                if ct == CellType.FLOOR:
                    # Show resource pheromone as faint blue glow
                    phero = max(cell.resource_pheromone, cell.assembly_pheromone,
                                cell.power_pheromone, cell.quality_pheromone)
                    if phero > 0.02:
                        ax.add_patch(plt.Rectangle(
                            (c - 0.45, r - 0.45), 0.9, 0.9,
                            facecolor="#00ccff", alpha=phero * 0.3, linewidth=0))
                    continue

                border_c = CELL_BORDER.get(ct, "#333")
                fill_c = CELL_COLORS.get(ct, BG)

                # Pheromone glow intensity
                phero_sum = (cell.resource_pheromone + cell.assembly_pheromone +
                             cell.power_pheromone + cell.quality_pheromone)
                alpha = min(0.9, 0.3 + phero_sum * 0.4)

                ax.add_patch(plt.Rectangle(
                    (c - 0.45, r - 0.45), 0.9, 0.9,
                    facecolor=fill_c, edgecolor=border_c,
                    linewidth=1.0, alpha=alpha))

                icon_data = CELL_ICONS.get(ct)
                if icon_data:
                    icon, icon_c = icon_data
                    ax.text(c, r, icon, ha="center", va="center",
                            fontsize=7, fontweight="bold", color=icon_c, alpha=0.9)

                # Print progress bar
                if ct == CellType.PRINTER and cell.printing:
                    bar_w = 0.8 * cell.print_progress
                    ax.add_patch(plt.Rectangle(
                        (c - 0.4, r - 0.48), bar_w, 0.12,
                        facecolor="#00ff88", alpha=0.7, linewidth=0))

                # Assembly inventory indicator
                if ct == CellType.ASSEMBLY:
                    total_inv = sum(cell.inventory.values())
                    if total_inv > 0:
                        ax.text(c, r - 0.35, f"{total_inv}",
                                ha="center", va="center", fontsize=5,
                                color="#eecc44", alpha=0.8)

        # Draw swimmers
        alive = [s for s in self._swimmers if s.alive]
        pulse = 0.6 + 0.4 * math.sin(self._tick * 0.2)
        for sw in alive:
            ms = 5 if sw.carrying else 3.5
            alpha = pulse if sw.carrying else 0.6
            ax.plot(sw.col, sw.row, sw.marker, color=sw.color,
                    markersize=ms, alpha=alpha, markeredgewidth=0.5, zorder=10)

        # HUD
        hud = [
            "REGENERATIVE FACTORY — STIGMERGIC MANUFACTURING",
            f"Printers: {telem['active_printers']}/{telem['printer_count']} active  |  "
            f"Swimmers: {telem['active_swimmers']}  |  Deliveries: {telem['total_deliveries']}",
            f"Printed: {telem['total_printed']}  |  Assembled: {telem['total_assembled']}  |  "
            f"STGM: {telem['total_stgm']:.2f}  |  Tick: {telem['tick']}",
        ]
        for i, line in enumerate(hud):
            c = "#00ffc8" if i == 0 else "#8090b0"
            fs = 7 if i == 0 else 6
            ax.text(0.5, fl.rows + 0.3 - i * 0.8, line,
                    fontsize=fs, fontfamily="monospace", color=c, alpha=0.9,
                    va="bottom", ha="center")

        # Legend
        legend = [
            ("●", "#00ccff", "ResourceForager"),
            ("◆", "#ff8800", "AssemblySwimmer"),
            ("▲", "#cc44ff", "QualitySentinel"),
            ("■", "#ffdd00", "PowerCourier"),
        ]
        for i, (mk, cl, lb) in enumerate(legend):
            ax.text(fl.cols + 0.3, fl.rows - 1 - i * 0.8, f"{mk} {lb}",
                    fontsize=5, fontfamily="monospace", color=cl, alpha=0.8)

        # ── Inventory bar chart ──────────────────────────────
        ax2 = self._ax_inv
        ax2.clear()
        ax2.set_facecolor(BG)
        inv = telem.get("inventory", {})
        if inv:
            names = [c.replace("_", "\n") for c in COMPONENTS]
            vals = [inv.get(c, 0) for c in COMPONENTS]
            colors = ["#44ee66", "#00ccff", "#ff8800", "#cc44ff", "#eecc44"]
            bars = ax2.barh(range(len(names)), vals, color=colors[:len(names)], alpha=0.8)
            ax2.set_yticks(range(len(names)))
            ax2.set_yticklabels(names, fontsize=5, color="#8090b0")
            ax2.tick_params(colors="#556688", labelsize=5)
            ax2.set_xlabel("In Stock", fontsize=6, color="#8090b0")
        ax2.set_title("ASSEMBLY INVENTORY", fontsize=7, color="#eecc44",
                       fontfamily="monospace", pad=4)

        # ── STGM economy curve ───────────────────────────────
        ax3 = self._ax_stgm
        ax3.clear()
        ax3.set_facecolor(BG)
        if len(self._stgm_history) > 2:
            x = range(len(self._stgm_history))
            ax3.plot(x, self._stgm_history, "-", color="#00ffc8", linewidth=1.0, alpha=0.9)
            ax3b = ax3.twinx()
            ax3b.plot(x, self._printed_history, "-", color="#44ee66", linewidth=0.8, alpha=0.7)
            ax3b.tick_params(colors="#44ee66", labelsize=4)
            ax3b.set_ylabel("Parts", fontsize=5, color="#44ee66")
        ax3.tick_params(colors="#556688", labelsize=4)
        ax3.set_ylabel("STGM", fontsize=5, color="#00ffc8")
        ax3.set_title("PROOF OF USEFUL PHYSICAL WORK", fontsize=7,
                       color="#00ffc8", fontfamily="monospace", pad=4)

        # ── Info panel ───────────────────────────────────────
        ax4 = self._ax_info
        ax4.clear()
        ax4.set_facecolor(BG)
        ax4.axis("off")

        info_lines = [
            ("Product:", "ODRI Joint Module"),
            ("Recipe:", "housing + bracket + 2x sleeve"),
            ("", "  + encoder_cap + linkage_arm"),
            ("Filament:", f"{telem['avg_filament']:.0f}% avg"),
            ("Power:", f"{telem['avg_power']:.0f}% avg"),
            ("Assembled:", f"{telem['total_assembled']} units"),
            ("STGM:", f"{telem['total_stgm']:.2f}"),
        ]
        for i, (label, val) in enumerate(info_lines):
            y = 0.95 - i * 0.13
            if label:
                ax4.text(0.05, y, label, fontsize=6, color="#8090b0",
                         fontfamily="monospace", transform=ax4.transAxes, va="top")
            ax4.text(0.45, y, val, fontsize=6, color="#00ffc8",
                     fontfamily="monospace", transform=ax4.transAxes, va="top")

        self._fig.tight_layout(pad=0.6)
        self.draw_idle()


# ── Main Widget ─────────────────────────────────────────────────

class FactoryWidget(SiftaBaseWidget):
    """Regenerative Factory — Stigmergic Decentralized Manufacturing."""
    APP_NAME = "Regenerative Factory"

    def build_ui(self, layout: QVBoxLayout) -> None:
        ctrl = QHBoxLayout()

        self._btn_start = QPushButton("Start Production")
        self._btn_start.clicked.connect(self._toggle)
        ctrl.addWidget(self._btn_start)

        self._btn_reset = QPushButton("New Factory")
        self._btn_reset.clicked.connect(self._reset)
        ctrl.addWidget(self._btn_reset)

        ctrl.addStretch()

        lbl = QLabel("Bauwens validated: STGM minted only for physical production")
        lbl.setStyleSheet("color: #8090b0; font-size: 9px; font-style: italic;")
        ctrl.addWidget(lbl)

        layout.addLayout(ctrl)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._canvas = FactoryCanvas()
        splitter.addWidget(self._canvas)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumWidth(340)
        self._log.setPlaceholderText("Production log...")
        splitter.addWidget(self._log)

        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self._floor = FactoryFloor(rows=20, cols=30)
        self._swimmers = spawn_factory_swimmers(self._floor)
        self._running = False
        self._timer: QTimer | None = None

        self._canvas.set_data(self._floor, self._swimmers)
        telem = factory_telemetry(self._floor, self._swimmers)
        self._canvas.render_frame(telem)

        self._log_msg("Factory floor: 20x30 grid, 8 printers, 3 QC, 2 assembly")
        self._log_msg("Product: ODRI Joint Module (6 components)")
        self._log_msg("STGM minted ONLY for physical production. Start Production to begin.")
        self.set_status("Ready — Start Production")

    def _toggle(self):
        if self._running:
            self._running = False
            if self._timer:
                self._timer.stop()
                self._timer = None
            self._btn_start.setText("Start Production")
            self.set_status("Halted")
        else:
            self._running = True
            self._timer = self.make_timer(100, self._tick_step)
            self._btn_start.setText("Halt")
            self._log_msg("PRODUCTION STARTED — swimmers deploying to stations")

    def _reset(self):
        was_running = self._running
        if was_running:
            self._toggle()
        self._floor = FactoryFloor(rows=20, cols=30)
        self._swimmers = spawn_factory_swimmers(self._floor)
        self._canvas.set_data(self._floor, self._swimmers)
        self._canvas._stgm_history.clear()
        self._canvas._printed_history.clear()
        telem = factory_telemetry(self._floor, self._swimmers)
        self._canvas.render_frame(telem)
        self._log_msg("NEW FACTORY — reset to initial state")

    def _tick_step(self):
        messages = step_factory(self._floor, self._swimmers)
        for msg in messages:
            self._log_msg(msg)

        telem = factory_telemetry(self._floor, self._swimmers)
        self.set_status(
            f"Tick {telem['tick']} | STGM: {telem['total_stgm']:.2f} | "
            f"Printed: {telem['total_printed']} | "
            f"Assembled: {telem['total_assembled']} | "
            f"Active: {telem['active_printers']}/{telem['printer_count']}")

        self._canvas.render_frame(telem)

        if self._floor.tick % 200 == 0:
            persist_ledger(self._floor)

    def _log_msg(self, msg: str):
        t = time.strftime("%H:%M:%S")
        self._log.appendPlainText(f"[{t}] {msg}")
        sb = self._log.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = FactoryWidget()
    w.setWindowTitle("Regenerative Factory — Stigmergic Manufacturing")
    w.resize(1440, 900)
    w.show()
    sys.exit(app.exec())
