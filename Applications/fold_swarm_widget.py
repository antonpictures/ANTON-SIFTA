#!/usr/bin/env python3
"""
fold_swarm_widget.py — Stigmergic Fold Swarm (iSwarm OS embed)
==============================================================

Cα chain + Go-model funnel + WCA sterics + obstacles + pheromone field.
Swimmers = pivot Monte Carlo movers with SHA body hashes + Ed25519 checkpoints.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("QtAgg")
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QVBoxLayout, QWidget

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "Applications") not in sys.path:
    sys.path.insert(0, str(_REPO / "Applications"))

from fold_swarm_sim import FoldSwarmConfig, FoldSwarmSim  # noqa: E402

BG = "#0a0b12"
PANEL = "#12142a"
STEPS = 3


class FoldSwarmWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sim = FoldSwarmSim(FoldSwarmConfig())
        self._frame = 0

        self._figure = Figure(figsize=(15, 10), facecolor=BG)
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setMinimumSize(1020, 700)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)

        gs = self._figure.add_gridspec(
            2, 2, hspace=0.26, wspace=0.22, left=0.05, right=0.98, top=0.9, bottom=0.05
        )
        self.ax_main = self._figure.add_subplot(gs[0, 0])
        self.ax_pher = self._figure.add_subplot(gs[0, 1])
        self.ax_e = self._figure.add_subplot(gs[1, 0])
        self.ax_hud = self._figure.add_subplot(gs[1, 1])

        self._figure.suptitle(
            "STIGMERGIC FOLD SWARM — Cα Go-model + WCA + obstacles",
            color="#7aa2f7", fontsize=13, fontweight="bold", family="monospace",
        )
        self._figure.text(
            0.5, 0.93,
            "pivot-conserving Monte Carlo  |  pheromone-biased exploration  |  hardware-bound swimmer bodies",
            ha="center", color="#565f89", fontsize=9, family="monospace",
        )

        self._line_current = None
        self._line_native = None
        self._beads = None
        self._im = None
        self._line_e = None
        self._line_q = None
        self._obs_patches: list = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(28)

    def _world_bounds(self):
        lo = self.sim.world_lo
        hi = self.sim.world_hi
        return float(lo[0]), float(hi[0]), float(lo[1]), float(hi[1])

    def _tick(self) -> None:
        for _ in range(STEPS):
            self.sim.step()
        self._frame += 1
        if self._frame % 2 == 0 or self.sim.tick <= 4:
            self._render()

    def _render(self) -> None:
        m = {
            "tick": self.sim.tick,
            "E": self.sim.E,
            "Q": self.sim._fraction_native_contacts(self.sim.r),
            "Rg": self.sim._radius_gyration(self.sim.r),
            "Rg_native": self.sim._radius_gyration(self.sim.native_r),
            "accept_rate": getattr(self.sim, "accepts_tick", 0) / max(
                1, self.sim.cfg.n_swimmers
            ),
            "n_native_pairs": len(self.sim.native_pairs),
        }
        r = self.sim.r
        nat = self.sim.native_r
        x0, x1, y0, y1 = self._world_bounds()

        ax = self.ax_main
        ax.clear()
        ax.set_facecolor(PANEL)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_aspect("equal")
        ax.set_title("chain (solid) vs native ghost (dashed) + obstacles", color="#bb9af7", fontsize=10)
        ax.axis("off")

        for obs in self.sim.obstacles:
            c = Circle((obs.cx, obs.cy), obs.r, fill=True, facecolor="#3b1f2d", edgecolor="#f7768e", lw=1.2, alpha=0.75)
            ax.add_patch(c)

        ax.plot(nat[:, 0], nat[:, 1], "--", color="#565f89", lw=1.2, alpha=0.85, label="native")
        ax.plot(r[:, 0], r[:, 1], "-", color="#73daca", lw=2.0, alpha=0.95)
        ax.scatter(r[:, 0], r[:, 1], c=np.arange(len(r)), cmap="viridis", s=28, zorder=5, edgecolors="#1a1b26", linewidths=0.4)
        ax.scatter([r[0, 0]], [r[0, 1]], c=["#9ece6a"], s=120, marker="*", zorder=6, edgecolors="none", label="N-term")
        ax.scatter([r[-1, 0]], [r[-1, 1]], c=["#f7768e"], s=90, marker="D", zorder=6, edgecolors="none", label="C-term")

        ap = self.ax_pher
        ap.clear()
        ap.set_facecolor(PANEL)
        ap.set_title("truth pheromone field (good folds deposit here)", color="#9ece6a", fontsize=10)
        extent = [x0, x1, y0, y1]
        ph = self.sim.pher.T
        self._im = ap.imshow(
            ph,
            origin="lower",
            extent=extent,
            aspect="equal",
            cmap="magma",
            vmin=0,
            vmax=max(float(ph.max()), 0.01),
            interpolation="nearest",
        )
        ap.plot(r[:, 0], r[:, 1], "-", color="#7dcfff", lw=0.8, alpha=0.5)

        ae = self.ax_e
        ae.clear()
        ae.set_facecolor(PANEL)
        ae.set_title("energy Q Rg", color="#e0af68", fontsize=10)
        h = self.sim.E_history
        if len(h) > 2:
            x = np.arange(len(h))
            ae.plot(x, h, color="#f7768e", lw=1.0, label="E")
            ae2 = ae.twinx()
            if len(self.sim.Q_history) == len(h):
                ae2.plot(x, self.sim.Q_history, color="#9ece6a", lw=1.0, alpha=0.9, label="Q")
            if len(self.sim.Rg_history) == len(h):
                ae2.plot(x, self.sim.Rg_history, color="#bb9af7", lw=0.8, alpha=0.7, label="Rg")
            ae2.set_ylim(0, max(12, max(self.sim.Rg_history[-500:]) * 1.1))
        ae.set_xlabel("step", color="#565f89", fontsize=8)
        ae.tick_params(colors="#565f89", labelsize=7)

        ah = self.ax_hud
        ah.clear()
        ah.axis("off")
        ah.set_facecolor(PANEL)
        lines = [
            f"{'FOLD SWARM METRICS':^42}",
            f"{'─' * 42}",
            f"  tick            {m['tick']:>8d}",
            f"  total E         {m['E']:>12.4f}",
            f"  native Q        {m['Q']:>12.3f}",
            f"  Rg / Rg_nat     {m['Rg']:>6.3f} / {m['Rg_native']:<6.3f}",
            f"  native pairs    {m['n_native_pairs']:>8d}",
            f"  accept / step   {m['accept_rate']:>12.3f}",
            f"  swimmers        {self.sim.cfg.n_swimmers:>8d}",
            "",
            f"  bond E (fixed)  {self.sim._bond_energy(r):>12.6f}",
            f"  WCA + Go + obs  {'(see total)':>12}",
        ]
        if self.sim.checkpoints:
            lines.append("")
            lines.append(f"  {'LAST CHECKPOINT (Ed25519)':^38}")
            lines.append(f"  {'─' * 38}")
            cp = self.sim.checkpoints[-1]
            lines.append(f"  digest {cp.get('digest', '')}")
            sig = str(cp.get("ed25519", ""))[:48]
            lines.append(f"  sig    {sig}…")

        lines.append("")
        lines.append("  Swimmer sample (SHA body):")
        for sw in self.sim.swimmers[:4]:
            lines.append(f"    S{sw.sid:03d} hinge={sw.hinge}  {sw.body_hash}")

        ah.text(
            0.04, 0.96, "\n".join(lines), transform=ah.transAxes, va="top", ha="left",
            fontsize=9, family="monospace", color="#c0caf5",
            bbox={"facecolor": "#0b1020", "edgecolor": "#24283b", "pad": 8},
        )

        self._canvas.draw_idle()

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._timer.stop()
        super().closeEvent(event)
