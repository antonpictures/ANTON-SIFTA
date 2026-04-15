#!/usr/bin/env python3
"""
sifta_firmware_widget.py — Fluid Firmware: Swarm-Routed Hardware Membrane
═════════════════════════════════════════════════════════════════════════════
Firmware is dead code trying to run physical hardware.
This is living code that learns physical hardware.

Visualization: a microchip's routing grid rendered as a dark geometric lattice.
Signal swimmers carry payloads from Input pins (left) to Output pins (right),
leaving glowing neon traces.  Degrade silicon and watch the swarm reroute in
real-time.  Inject a Liquid Update and watch new swimmers organically overtake
old traces — zero-downtime firmware evolution.

Conceived by Gemini.  Built by Opus.  Owned by the Architect.
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
from System.fluid_firmware import (
    SiliconGrid, SignalSwimmer, ThermalForager,
    spawn_signal_batch, spawn_thermal_foragers,
    step_signal_swimmer, step_thermal_forager,
    degrade_cluster, tick_environment, compute_telemetry,
    save_routing_table,
)

# ── Colormaps ────────────────────────────────────────────────────

HEALTH_CMAP = LinearSegmentedColormap.from_list("health", [
    (0.0, "#ff0022"),  # dead
    (0.3, "#663300"),  # damaged
    (0.6, "#334455"),  # worn
    (0.85, "#1a2535"), # healthy-dim
    (1.0, "#0e1620"),  # pristine = dark (disappears into background)
])

SIGNAL_CMAP = LinearSegmentedColormap.from_list("signal", [
    (0.0, (0, 0, 0, 0)),
    (0.1, (0, 0.5, 1.0, 0.15)),
    (0.3, (0, 0.7, 1.0, 0.35)),
    (0.6, (0, 0.9, 1.0, 0.6)),
    (1.0, (0, 1.0, 0.9, 0.95)),
])

UPDATE_CMAP = LinearSegmentedColormap.from_list("update", [
    (0.0, (0, 0, 0, 0)),
    (0.2, (0, 1.0, 0.6, 0.2)),
    (0.5, (0.2, 1.0, 0.4, 0.5)),
    (1.0, (0.4, 1.0, 0.3, 0.9)),
])

THERMAL_CMAP = LinearSegmentedColormap.from_list("thermal", [
    (0.0, (0, 0, 0, 0)),
    (0.2, (1.0, 0.3, 0, 0.15)),
    (0.5, (1.0, 0.5, 0, 0.45)),
    (1.0, (1.0, 0.9, 0.3, 0.85)),
])

BG = "#060810"


# ── Canvas ───────────────────────────────────────────────────────

class FirmwareCanvas(FigureCanvas):
    """Renders the silicon grid with pheromone overlays and swimmers."""

    def __init__(self, parent: QWidget | None = None):
        self._fig = Figure(figsize=(16, 8), facecolor=BG, dpi=90)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setMinimumSize(900, 450)

        gs = self._fig.add_gridspec(1, 2, width_ratios=[3, 1], wspace=0.08)
        self._ax_chip = self._fig.add_subplot(gs[0, 0])
        self._ax_telem = self._fig.add_subplot(gs[0, 1])
        for ax in [self._ax_chip, self._ax_telem]:
            ax.set_facecolor(BG)

        self._grid: SiliconGrid | None = None
        self._swimmers: List[SignalSwimmer] = []
        self._foragers: List[ThermalForager] = []
        self._tick = 0
        self._throughput_history: List[float] = []
        self._health_history: List[float] = []

    def set_data(self, grid, swimmers, foragers):
        self._grid = grid
        self._swimmers = swimmers
        self._foragers = foragers

    def render_frame(self, telemetry: dict):
        if not self._grid:
            return
        self._tick += 1
        g = self._grid

        self._throughput_history.append(telemetry.get("total_delivered", 0))
        self._health_history.append(telemetry.get("avg_health", 1.0))
        if len(self._throughput_history) > 300:
            self._throughput_history = self._throughput_history[-200:]
            self._health_history = self._health_history[-200:]

        ax = self._ax_chip
        ax.clear()
        ax.set_facecolor(BG)
        ax.set_xlim(-0.5, g.cols - 0.5)
        ax.set_ylim(-0.5, g.rows - 0.5)
        ax.set_aspect("equal")
        ax.axis("off")

        # ── Health layer (damaged nodes glow red) ────────────
        health = g.health_matrix()
        ax.imshow(health, cmap=HEALTH_CMAP, origin="lower", aspect="equal",
                  vmin=0, vmax=1, interpolation="nearest", alpha=0.9)

        # ── Signal pheromone overlay (blue-cyan traces) ──────
        sig = g.signal_phero_matrix()
        if sig.max() > 0.005:
            ax.imshow(sig, cmap=SIGNAL_CMAP, origin="lower", aspect="equal",
                      vmin=0, vmax=max(0.3, sig.max()), interpolation="bilinear")

        # ── Update pheromone overlay (green traces) ──────────
        upd = g.update_phero_matrix()
        if upd.max() > 0.005:
            ax.imshow(upd, cmap=UPDATE_CMAP, origin="lower", aspect="equal",
                      vmin=0, vmax=max(0.3, upd.max()), interpolation="bilinear")

        # ── Thermal warning overlay ──────────────────────────
        therm = g.thermal_phero_matrix()
        if therm.max() > 0.01:
            ax.imshow(therm, cmap=THERMAL_CMAP, origin="lower", aspect="equal",
                      vmin=0, vmax=max(0.3, therm.max()), interpolation="bilinear")

        # ── Input/Output pin markers ─────────────────────────
        for r in range(g.rows):
            ax.plot(-0.3, r, ">", color="#00ccff", markersize=3, alpha=0.6)
            ax.plot(g.cols - 0.7, r, "<", color="#ffaa00", markersize=3, alpha=0.6)

        # ── Draw signal swimmers ─────────────────────────────
        alive_sw = [s for s in self._swimmers if s.alive]
        if alive_sw:
            pulse = 0.6 + 0.4 * math.sin(self._tick * 0.2)
            for sw in alive_sw:
                c = sw.color
                m = "o" if sw.generation == 1 else "D"
                ms = 3.5 if sw.generation == 1 else 4.5
                ax.plot(sw.col, sw.row, m, color=c, markersize=ms,
                        alpha=pulse, markeredgewidth=0.4, zorder=10)

                if len(sw.path) > 2:
                    trail = sw.path[-12:]
                    tx = [p[1] for p in trail]
                    ty = [p[0] for p in trail]
                    tc = c if sw.generation == 1 else "#00ffaa"
                    ax.plot(tx, ty, "-", color=tc, alpha=0.2, linewidth=0.6, zorder=8)

        # ── Draw thermal foragers ────────────────────────────
        for tf in self._foragers:
            if tf.alive:
                ax.plot(tf.col, tf.row, "^", color="#ff6622", markersize=4,
                        alpha=0.7, zorder=11)

        # ── Chip border ──────────────────────────────────────
        border_color = "#2a3040"
        ax.plot([-0.5, g.cols - 0.5, g.cols - 0.5, -0.5, -0.5],
                [-0.5, -0.5, g.rows - 0.5, g.rows - 0.5, -0.5],
                "-", color=border_color, linewidth=1.5, alpha=0.6)

        # ── HUD on chip ─────────────────────────────────────
        hud_lines = [
            "FLUID FIRMWARE — SWARM-ROUTED HARDWARE MEMBRANE",
            f"Health: {telemetry['avg_health']*100:.1f}%  |  Dead nodes: {telemetry['dead_nodes']}  |  Active paths: {telemetry['active_paths']}",
            f"Swimmers: {telemetry['active_swimmers']} active  |  Gen1: {telemetry['gen1_alive']}  Gen2: {telemetry['gen2_alive']}",
            f"Delivered: {telemetry['total_delivered']}  |  Dropped: {telemetry['total_dropped']}  |  Throughput: {telemetry['throughput_mb']:.1f} MB",
        ]
        for i, line in enumerate(hud_lines):
            c = "#00ffc8" if i == 0 else "#8090b0"
            fs = 7 if i == 0 else 6
            ax.text(0.5, g.rows + 0.8 - i * 0.9, line,
                    fontsize=fs, fontfamily="monospace", color=c, alpha=0.9,
                    va="bottom", ha="center")

        # Legend
        legend = [
            ("●", "#00ccff", "Signal (Gen1)"),
            ("◆", "#00ffaa", "Signal (Gen2 / Update)"),
            ("▲", "#ff6622", "Thermal Forager"),
        ]
        for i, (mk, cl, lb) in enumerate(legend):
            ax.text(g.cols + 0.5, g.rows - 1 - i * 1.2, f"{mk} {lb}",
                    fontsize=5, fontfamily="monospace", color=cl, alpha=0.8)

        # ── Telemetry panel ──────────────────────────────────
        ax2 = self._ax_telem
        ax2.clear()
        ax2.set_facecolor(BG)

        if len(self._throughput_history) > 2:
            x = range(len(self._throughput_history))
            # Delivered over time (cumulative)
            ax2.plot(x, self._throughput_history, "-", color="#00ccff",
                     linewidth=1.0, alpha=0.8, label="Delivered")

            # Health over time on twin axis
            ax2b = ax2.twinx()
            ax2b.plot(x, self._health_history, "-", color="#ff4466",
                      linewidth=1.0, alpha=0.7, label="Health")
            ax2b.set_ylim(0, 1.1)
            ax2b.tick_params(colors="#ff4466", labelsize=5)
            ax2b.set_ylabel("Health", fontsize=6, color="#ff4466")

        ax2.set_title("TELEMETRY", fontsize=7, color="#8090b0",
                       fontfamily="monospace", pad=4)
        ax2.tick_params(colors="#556688", labelsize=5)
        ax2.set_ylabel("Delivered", fontsize=6, color="#00ccff")
        ax2.set_xlabel("Tick", fontsize=5, color="#556688")

        self._fig.tight_layout(pad=0.8)
        self.draw_idle()


# ── Main Widget ─────────────────────────────────────────────────

class FirmwareWidget(SiftaBaseWidget):
    """Fluid Firmware — Swarm-Routed Hardware Membrane."""
    APP_NAME = "Fluid Firmware"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Controls ────────────────────────────────────────────
        ctrl = QHBoxLayout()

        self._btn_start = QPushButton("Power On")
        self._btn_start.clicked.connect(self._toggle_sim)
        ctrl.addWidget(self._btn_start)

        self._btn_degrade = QPushButton("Simulate Degradation")
        self._btn_degrade.setToolTip("Thermal damage to a random silicon cluster")
        self._btn_degrade.clicked.connect(self._degrade)
        ctrl.addWidget(self._btn_degrade)

        self._btn_update = QPushButton("Inject Liquid Update")
        self._btn_update.setToolTip("Deploy Gen2 swimmers — zero-downtime firmware update")
        self._btn_update.clicked.connect(self._liquid_update)
        ctrl.addWidget(self._btn_update)

        self._btn_reset = QPushButton("New Chip")
        self._btn_reset.clicked.connect(self._reset)
        ctrl.addWidget(self._btn_reset)

        ctrl.addStretch()

        self._chk_thermal = QCheckBox("Thermal foragers")
        self._chk_thermal.setChecked(True)
        ctrl.addWidget(self._chk_thermal)

        layout.addLayout(ctrl)

        # ── Splitter: canvas + log ──────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._canvas = FirmwareCanvas()
        splitter.addWidget(self._canvas)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumWidth(320)
        self._log.setPlaceholderText("Firmware log...")
        splitter.addWidget(self._log)

        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        # ── State ───────────────────────────────────────────────
        self._grid = SiliconGrid(rows=40, cols=60)
        self._swimmers: List[SignalSwimmer] = []
        self._foragers: List[ThermalForager] = spawn_thermal_foragers(self._grid, 6)
        self._running = False
        self._tick = 0
        self._timer: QTimer | None = None
        self._degradation_count = 0
        self._update_injected = False

        self._canvas.set_data(self._grid, self._swimmers, self._foragers)
        telem = compute_telemetry(self._grid, self._swimmers)
        self._canvas.render_frame(telem)

        self._log_msg("Silicon grid initialized: 40x60 (2400 nodes)")
        self._log_msg("Input pins: 40 (left edge)  |  Output pins: 40 (right edge)")
        self._log_msg("Cache region: center block  |  Power On to begin routing")
        self.set_status("Ready — Power On to begin")

    def _toggle_sim(self):
        if self._running:
            self._running = False
            if self._timer:
                self._timer.stop()
                self._timer = None
            self._btn_start.setText("Power On")
            self.set_status("Halted")
        else:
            self._running = True
            self._timer = self.make_timer(70, self._tick_step)
            self._btn_start.setText("Halt")
            self.set_status("Routing active")
            self._log_msg("CHIP POWERED ON — signal swimmers deploying")

    def _degrade(self):
        """Simulate thermal degradation on a random cluster."""
        r = random.randint(5, self._grid.rows - 5)
        c = random.randint(8, self._grid.cols - 8)
        radius = random.randint(3, 7)
        severity = random.uniform(0.5, 0.9)
        affected = degrade_cluster(self._grid, r, c, radius, severity)
        self._degradation_count += 1
        self._log_msg(
            f"DEGRADATION #{self._degradation_count}: cluster at ({r},{c}) "
            f"r={radius} sev={severity:.0%} — {affected} nodes damaged")
        self._log_msg("Swimmers will reroute around dead silicon...")

    def _liquid_update(self):
        """Inject Gen2 swimmers — the liquid firmware update."""
        new_swimmers = spawn_signal_batch(self._grid, count=15, generation=2)
        self._swimmers.extend(new_swimmers)
        self._update_injected = True
        self._log_msg(
            "LIQUID UPDATE INJECTED — 15 Gen2 swimmers deployed")
        self._log_msg(
            "Gen2 traces are GREEN — they will organically overtake Gen1 BLUE traces")

    def _reset(self):
        was_running = self._running
        if was_running:
            self._toggle_sim()
        self._grid = SiliconGrid(rows=40, cols=60)
        self._swimmers.clear()
        self._foragers = spawn_thermal_foragers(self._grid, 6)
        self._tick = 0
        self._degradation_count = 0
        self._update_injected = False
        self._canvas.set_data(self._grid, self._swimmers, self._foragers)
        self._canvas._throughput_history.clear()
        self._canvas._health_history.clear()
        telem = compute_telemetry(self._grid, self._swimmers)
        self._canvas.render_frame(telem)
        self._log_msg("NEW CHIP — silicon reset to pristine state")
        self.set_status("New chip — Power On")

    def _tick_step(self):
        self._tick += 1

        # Spawn new signal swimmers every few ticks
        if self._tick % 4 == 0:
            gen = 2 if self._update_injected and random.random() < 0.6 else 1
            batch = spawn_signal_batch(self._grid, count=4, generation=gen)
            self._swimmers.extend(batch)

        # Step all swimmers
        for sw in self._swimmers:
            step_signal_swimmer(sw, self._grid)

        # Step thermal foragers
        if self._chk_thermal.isChecked():
            for tf in self._foragers:
                step_thermal_forager(tf, self._grid)

        # Environment tick
        tick_environment(self._grid)

        # Garbage collect dead swimmers (keep recent for trail rendering)
        if len(self._swimmers) > 400:
            self._swimmers = [s for s in self._swimmers if s.alive] + \
                             [s for s in self._swimmers if not s.alive][-50:]

        # Telemetry
        telem = compute_telemetry(self._grid, self._swimmers)
        self.set_status(
            f"Tick {self._tick} | Health: {telem['avg_health']*100:.0f}% | "
            f"Active: {telem['active_swimmers']} | "
            f"Delivered: {telem['total_delivered']} | "
            f"Paths: {telem['active_paths']}")

        self._canvas.render_frame(telem)

        # Periodic save
        if self._tick % 100 == 0:
            save_routing_table(self._grid)

        # Log milestones
        if telem["total_delivered"] > 0 and telem["total_delivered"] % 100 == 0:
            self._log_msg(
                f"Milestone: {telem['total_delivered']} signals delivered | "
                f"Drop rate: {telem['total_dropped']}/{telem['total_delivered'] + telem['total_dropped']}")

    def _log_msg(self, msg: str):
        t = time.strftime("%H:%M:%S")
        self._log.appendPlainText(f"[{t}] {msg}")
        sb = self._log.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())


# ── Standalone ───────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = FirmwareWidget()
    w.setWindowTitle("Fluid Firmware — Swarm-Routed Hardware Membrane")
    w.resize(1440, 800)
    w.show()
    sys.exit(app.exec())
