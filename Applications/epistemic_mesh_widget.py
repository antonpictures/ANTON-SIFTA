#!/usr/bin/env python3
"""
epistemic_mesh_widget.py — The Anti-Gaslight Engine (iSwarm OS embed)
======================================================================

Four-panel real-time visualization:
  Top-left:     Network topology — nodes, edges, swimmers, colored by trust
  Top-right:    Truth pheromone heat (green highways vs red doubt corridors)
  Bottom-left:  Time-series: epistemic coverage, entropy, verification rate
  Bottom-right: Live HUD — proof-of-useful-work stats + verification ledger
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
from matplotlib.figure import Figure
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QVBoxLayout, QWidget

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "Applications") not in sys.path:
    sys.path.insert(0, str(_REPO / "Applications"))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))

from epistemic_mesh_sim import (  # noqa: E402
    EpistemicMeshSim,
    MeshConfig,
    NodeType,
    SwimmerState,
)

BG = "#0d0e17"
PANEL = "#11121e"
NODE_COLORS = {
    NodeType.ORIGIN: "#9ece6a",
    NodeType.RELAY: "#3b4261",
    NodeType.SLUDGE: "#f7768e",
}
NODE_SIZES = {NodeType.ORIGIN: 70, NodeType.RELAY: 16, NodeType.SLUDGE: 50}
NODE_MARKERS = {NodeType.ORIGIN: "D", NodeType.RELAY: "o", NodeType.SLUDGE: "X"}
SWIM_COLORS = {
    SwimmerState.IDLE: "#24283b",
    SwimmerState.TRACING: "#e0af68",
    SwimmerState.VERIFYING: "#ffffff",
    SwimmerState.DEPOSITING: "#73daca",
}

STEPS_PER_FRAME = 4
RENDER_EVERY = 10


class EpistemicMeshWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sim = EpistemicMeshSim(MeshConfig(seed=2026))
        self._frame = 0

        self._figure = Figure(figsize=(16, 11), facecolor=BG)
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setMinimumSize(1100, 750)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)

        gs = self._figure.add_gridspec(
            2, 2, hspace=0.28, wspace=0.22,
            left=0.04, right=0.97, top=0.92, bottom=0.04,
        )
        self.ax_mesh = self._figure.add_subplot(gs[0, 0])
        self.ax_pher = self._figure.add_subplot(gs[0, 1])
        self.ax_time = self._figure.add_subplot(gs[1, 0])
        self.ax_hud = self._figure.add_subplot(gs[1, 1])

        self._figure.suptitle(
            "THE EPISTEMIC MESH — Anti-Gaslight Engine",
            color="#bb9af7", fontsize=15, fontweight="bold", family="monospace",
        )
        self._figure.text(
            0.5, 0.955,
            "proof-of-useful-work  |  stigmergic truth verification  |  Ed25519 provenance",
            ha="center", color="#565f89", fontsize=9, family="monospace",
        )

        self._precompute_segments()
        self._init_panels()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(25)

    def _precompute_segments(self) -> None:
        self._segments = np.array([
            [[self.sim.node_x[i], self.sim.node_y[i]],
             [self.sim.node_x[j], self.sim.node_y[j]]]
            for (i, j) in self.sim.edges
        ]) if self.sim.edges else np.empty((0, 2, 2))

    def _init_panels(self) -> None:
        for ax in [self.ax_mesh, self.ax_pher, self.ax_time, self.ax_hud]:
            ax.set_facecolor(PANEL)
            for spine in ax.spines.values():
                spine.set_color("#24283b")
            ax.tick_params(colors="#565f89", labelsize=8)

    def _tick(self) -> None:
        for _ in range(STEPS_PER_FRAME):
            self.sim.step()
        self._frame += 1
        if self._frame % (RENDER_EVERY // STEPS_PER_FRAME) == 0 or self.sim.tick <= STEPS_PER_FRAME:
            self._render()

    def _render(self) -> None:
        m = self.sim._collect_metrics()
        conf = self.sim.confidence()

        self._draw_mesh(conf)
        self._draw_pheromone(conf)
        self._draw_timeseries()
        self._draw_hud(m)
        self._canvas.draw_idle()

    def _draw_mesh(self, conf: np.ndarray) -> None:
        ax = self.ax_mesh
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.set_aspect("equal")
        ax.set_title("network topology + swimmers", color="#7aa2f7", fontsize=10, family="monospace")
        ax.axis("off")

        if len(self._segments) > 0:
            colors = np.zeros((len(conf), 4))
            for i, c in enumerate(conf):
                if c > 0.5:
                    colors[i] = [0.45, 0.87, 0.75, min(0.3 + c * 0.6, 0.9)]
                elif c > 0.1:
                    colors[i] = [0.45, 0.55, 0.65, 0.15]
                else:
                    colors[i] = [0.23, 0.28, 0.38, 0.1]
            widths = np.clip(
                self.sim.truth_pher + self.sim.doubt_pher, 0.4, 4.0
            )
            lc = LineCollection(self._segments, colors=colors, linewidths=widths)
            ax.add_collection(lc)

        for ntype in [NodeType.RELAY, NodeType.SLUDGE, NodeType.ORIGIN]:
            mask = self.sim.node_type == ntype
            ax.scatter(
                self.sim.node_x[mask], self.sim.node_y[mask],
                s=NODE_SIZES[ntype], c=NODE_COLORS[ntype],
                marker=NODE_MARKERS[ntype], zorder=5,
                edgecolors="none", alpha=0.9,
            )

        for state in [SwimmerState.TRACING, SwimmerState.VERIFYING, SwimmerState.DEPOSITING]:
            sx = [self.sim.node_x[sw.node] for sw in self.sim.swimmers if sw.state == state]
            sy = [self.sim.node_y[sw.node] for sw in self.sim.swimmers if sw.state == state]
            if sx:
                ax.scatter(sx, sy, s=4, c=SWIM_COLORS[state], alpha=0.7, zorder=6, linewidths=0)

        burst = (
            self.sim.cfg.sludge_burst_interval > 0
            and (self.sim.tick % self.sim.cfg.sludge_burst_interval) < self.sim.cfg.sludge_burst_duration
        )
        if burst:
            for spine in ax.spines.values():
                spine.set_color("#f7768e")
                spine.set_linewidth(2)
            ax.text(
                0.5, 0.97, "⚠ SLUDGE BURST ⚠", transform=ax.transAxes,
                ha="center", va="top", color="#f7768e", fontsize=10,
                fontweight="bold", family="monospace",
            )

    def _draw_pheromone(self, conf: np.ndarray) -> None:
        ax = self.ax_pher
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.set_aspect("equal")
        ax.set_title("epistemic confidence heat", color="#73daca", fontsize=10, family="monospace")
        ax.axis("off")

        if len(self._segments) > 0:
            lc = LineCollection(
                self._segments, cmap="RdYlGn", norm=Normalize(0, 1),
                linewidths=np.clip(conf * 3 + 0.3, 0.3, 4.0),
            )
            lc.set_array(conf)
            ax.add_collection(lc)

        for ntype in [NodeType.ORIGIN, NodeType.SLUDGE]:
            mask = self.sim.node_type == ntype
            ax.scatter(
                self.sim.node_x[mask], self.sim.node_y[mask],
                s=NODE_SIZES[ntype] * 0.6, c=NODE_COLORS[ntype],
                marker=NODE_MARKERS[ntype], zorder=5,
                edgecolors="none", alpha=0.6,
            )

    def _draw_timeseries(self) -> None:
        ax = self.ax_time
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.set_title("convergence metrics", color="#e0af68", fontsize=10, family="monospace")

        hist = self.sim.history
        n = len(hist["epistemic_coverage"])
        if n < 2:
            return
        window = min(n, 600)
        x = np.arange(n - window, n)

        ax.plot(x, hist["epistemic_coverage"][-window:], color="#9ece6a", linewidth=1.2, label="coverage")
        ax.plot(x, hist["mesh_entropy"][-window:], color="#bb9af7", linewidth=1.0, label="entropy")

        vr = np.array(hist["verification_rate"][-window:])
        if vr.max() > 0:
            vr_norm = vr / max(vr.max(), 1.0)
            ax.fill_between(x, 0, vr_norm, color="#73daca", alpha=0.15, label="verif. rate")

        ax.set_ylim(-0.05, 1.15)
        ax.set_xlim(x[0], x[-1])
        ax.legend(loc="upper left", fontsize=7, framealpha=0.3, labelcolor="#a9b1d6")
        ax.tick_params(colors="#565f89", labelsize=7)
        ax.set_xlabel("tick", color="#565f89", fontsize=8)

    def _draw_hud(self, m: dict) -> None:
        ax = self.ax_hud
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.axis("off")

        lines = [
            f"{'PROOF OF USEFUL WORK':^44}",
            f"{'─' * 44}",
            f"  tick          {m['tick']:>8d}",
            f"  packets live  {m['packets_alive']:>8d}",
            f"  verified      {m['total_verified']:>8d}",
            f"  sludge reject {m['total_sludge_rejected']:>8d}",
            f"  STGM minted   {m['total_stgm_minted']:>8.2f}",
            "",
            f"  coverage      {m['epistemic_coverage']:>8.1%}",
            f"  entropy       {m['mesh_entropy']:>8.4f}",
            f"  τ_truth peak  {m['truth_pher_peak']:>8.2f}",
            f"  τ_doubt peak  {m['doubt_pher_peak']:>8.2f}",
        ]

        if m["in_sludge_burst"]:
            lines.append("")
            lines.append("  ⚠ DISINFORMATION ATTACK ACTIVE ⚠")

        vlog = self.sim.verification_log[-6:]
        if vlog:
            lines.append("")
            lines.append(f"  {'RECENT VERIFICATIONS':^40}")
            lines.append(f"  {'─' * 40}")
            for v in reversed(vlog):
                lines.append(
                    f"  t{v['tick']:<5d} S#{v['swimmer']:<3d}→O{v['origin']:<2d}  "
                    f"sig={v['sig']}  +{v['stgm']:.2f}"
                )

        text = "\n".join(lines)
        color = "#f7768e" if m["in_sludge_burst"] else "#7dcfff"
        ax.text(
            0.05, 0.95, text, transform=ax.transAxes,
            va="top", ha="left", color=color,
            fontsize=9, family="monospace",
            bbox={"facecolor": "#0b1020", "edgecolor": "#24283b", "alpha": 0.9, "pad": 10},
        )

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._timer.stop()
        super().closeEvent(event)
