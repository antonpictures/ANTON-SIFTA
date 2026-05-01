#!/usr/bin/env python3
"""
sifta_physics_observatory.py — SIFTA Physics Observatory
══════════════════════════════════════════════════════════
Two real physics engines. One instrument panel.

Engine A: Lennard-Jones Colloid Thermodynamics
  V_LJ(r) = 4ε[(σ/r)¹² − (σ/r)⁶]  + Langevin + DLVO
  Observables: T [K], P [Pa], S [J/mol·K], phase (GAS/LIQUID/CRYSTAL), g(r)

Engine B: Lattice-Boltzmann Fluid Dynamics
  f_i(x+e_i, t+1) = f_i(x,t) − (1/τ)(f_i − f_i^eq)   D2Q9 BGK
  Observables: Re, Ma, ν [m²/s], ω_z (vorticity), C_D (drag)

Replaces: Colloid Simulator + Fluid Firmware (2 apps → 1)

Doctor: AG31 (Antigravity / Claude Sonnet 4.6 Thinking)
Signed: AG31-PHYSICIST
For the Swarm. 🐜⚡
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
for _p in [str(_REPO), str(_REPO / "System"), str(_REPO / "Applications")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.gridspec as gridspec

from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QSlider, QTabWidget, QSplitter,
    QPlainTextEdit, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from System.sifta_base_widget import SiftaBaseWidget

# ── Physics engines ────────────────────────────────────────────────────────────
from System.physics_engines.lj_colloid import (
    init_state as lj_init, step as lj_step,
    collect_observables as lj_observe,
    radial_distribution,
    N_DEFAULT, BOX_REDUCED, DT_REDUCED, SIGMA_M, EPSILON_J, KB,
)
from System.physics_engines.lbm_fluid import (
    init_lbm, lbm_step, compute_vorticity,
    collect_lbm_observables, set_reynolds,
)

# ── Colormaps ──────────────────────────────────────────────────────────────────
VORTEX_CMAP = LinearSegmentedColormap.from_list("vortex", [
    "#1a0a2e", "#4b0082", "#0d0d0d", "#006400", "#00ff88",
])
SPEED_CMAP = LinearSegmentedColormap.from_list("speed", [
    "#050508", "#0a2040", "#0055aa", "#00aaff", "#00ffcc", "#ffffff",
])
BG = "#060810"
TEAL = "#00ffc8"
RED  = "#ff4466"
GOLD = "#ffcc44"
DIM  = "#4a5570"

# ── SI formatting helpers ──────────────────────────────────────────────────────

def _si(val: float, unit: str, dp: int = 3) -> str:
    """Format a value with SI prefix if large/small."""
    if abs(val) == 0:
        return f"0 {unit}"
    exp = math.floor(math.log10(abs(val)))
    prefixes = {-24:"y",-21:"z",-18:"a",-15:"f",-12:"p",-9:"n",-6:"µ",-3:"m",
                0:"",3:"k",6:"M",9:"G",12:"T"}
    best = max((e for e in prefixes if e <= exp), default=0)
    scaled = val / (10 ** best)
    return f"{scaled:.{dp}f} {prefixes[best]}{unit}"


# ══════════════════════════════════════════════════════════════════════════════
# ENGINE A — COLLOID CANVAS
# ══════════════════════════════════════════════════════════════════════════════

class ColloidCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self._fig = Figure(figsize=(14, 8), facecolor=BG, dpi=90)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setMinimumSize(700, 400)
        gs = self._fig.add_gridspec(2, 3, hspace=0.38, wspace=0.35,
                                    left=0.06, right=0.97, top=0.92, bottom=0.08)
        self._ax_main  = self._fig.add_subplot(gs[:, 0:2])   # particle field
        self._ax_gr    = self._fig.add_subplot(gs[0, 2])      # g(r)
        self._ax_T     = self._fig.add_subplot(gs[1, 2])      # T history
        for ax in self._fig.axes:
            ax.set_facecolor(BG)
            ax.tick_params(colors=DIM, labelsize=7)
            for sp in ax.spines.values():
                sp.set_color(DIM)
        self._state = None

    def set_state(self, s):
        self._state = s

    def render(self, obs: dict):
        if self._state is None:
            return
        s = self._state

        # ── Main particle field ───────────────────────────────────────────
        ax = self._ax_main
        ax.clear(); ax.set_facecolor(BG); ax.set_aspect("equal")
        ax.set_xlim(0, s.box); ax.set_ylim(0, s.box)
        ax.axis("off")

        # Colour by speed
        speed = np.sqrt((s.vel ** 2).sum(axis=1))
        v_max = max(speed.max(), 1e-10)
        colors = plt.cm.plasma(speed / v_max)

        ax.scatter(s.pos[:, 0], s.pos[:, 1],
                   c=colors, s=22, alpha=0.85, linewidths=0)

        # Phase annotation
        phase_col = {"GAS": DIM, "LIQUID": "#44aaff", "CRYSTAL": GOLD}
        ax.set_title(
            f"COLLOID FIELD   N={s.N}   Phase: {obs['phase']}   "
            f"Step {obs['step']:,}",
            color=phase_col.get(obs["phase"], TEAL),
            fontsize=9, fontfamily="monospace", pad=4,
        )

        # Instrument panel (text overlay)
        lines = [
            f"T  = {_si(obs['T_K'],'K',1)}",
            f"P  = {_si(obs['P_Pa'],'Pa',2)}",
            f"S  ≈ {obs['S_JmolK']:.2f} J/mol·K",
            f"MSD= {_si(obs['msd_m2'],'m²',2)}",
        ]
        for i, ln in enumerate(lines):
            ax.text(0.01, 0.98 - i * 0.055, ln,
                    transform=ax.transAxes,
                    fontsize=8, fontfamily="monospace",
                    color=TEAL, va="top", alpha=0.9)

        # ── g(r) ──────────────────────────────────────────────────────────
        ax2 = self._ax_gr
        ax2.clear(); ax2.set_facecolor(BG)
        try:
            r_arr, g_arr = radial_distribution(s, n_bins=60)
            r_nm = r_arr * 1e9  # → nanometres for display
            ax2.plot(r_nm, g_arr, color="#44aaff", linewidth=1.0)
            ax2.axhline(1.0, color=DIM, linewidth=0.6, linestyle="--")
            ax2.set_xlabel("r [nm]", fontsize=7, color=DIM)
            ax2.set_ylabel("g(r)", fontsize=7, color=DIM)
            ax2.set_title("Pair Correlation g(r)", fontsize=7,
                          color=TEAL, fontfamily="monospace")
            ax2.set_ylim(bottom=0)
        except Exception:
            pass

        # ── T history ─────────────────────────────────────────────────────
        ax3 = self._ax_T
        ax3.clear(); ax3.set_facecolor(BG)
        if len(s.T_history) > 2:
            ax3.plot(s.T_history, color=RED, linewidth=0.9, alpha=0.85)
        ax3.set_xlabel("Frame", fontsize=7, color=DIM)
        ax3.set_ylabel("T [K]", fontsize=7, color=RED)
        ax3.set_title("Temperature", fontsize=7, color=TEAL, fontfamily="monospace")

        self._fig.canvas.draw_idle()


# ══════════════════════════════════════════════════════════════════════════════
# ENGINE B — LBM CANVAS
# ══════════════════════════════════════════════════════════════════════════════

class LBMCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self._fig = Figure(figsize=(14, 8), facecolor=BG, dpi=90)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setMinimumSize(700, 400)
        gs = self._fig.add_gridspec(2, 3, hspace=0.38, wspace=0.35,
                                    left=0.06, right=0.97, top=0.92, bottom=0.08)
        self._ax_vel   = self._fig.add_subplot(gs[0, 0:2])   # speed field
        self._ax_vort  = self._fig.add_subplot(gs[1, 0:2])   # vorticity
        self._ax_Re    = self._fig.add_subplot(gs[0, 2])      # Re history
        self._ax_drag  = self._fig.add_subplot(gs[1, 2])      # drag history
        for ax in self._fig.axes:
            ax.set_facecolor(BG)
            ax.tick_params(colors=DIM, labelsize=7)
            for sp in ax.spines.values():
                sp.set_color(DIM)
        self._state = None

    def set_state(self, s):
        self._state = s

    def render(self, obs: dict):
        if self._state is None:
            return
        s = self._state

        speed = np.sqrt(s.ux ** 2 + s.uy ** 2)
        vort  = compute_vorticity(s)
        obs_mask = s.obstacle.astype(float)
        obs_mask[~s.obstacle] = np.nan

        # ── Speed field ───────────────────────────────────────────────────
        ax = self._ax_vel
        ax.clear(); ax.set_facecolor(BG); ax.axis("off")
        ax.imshow(speed, cmap=SPEED_CMAP, origin="lower", aspect="auto",
                  interpolation="bilinear")
        ax.imshow(obs_mask, cmap="gray_r", origin="lower", aspect="auto",
                  alpha=0.9, interpolation="nearest")
        Re = obs["Re"]
        regime = ("LAMINAR" if Re < 50 else
                  "VORTEX STREET" if Re < 200 else
                  "TURBULENT ONSET")
        ax.set_title(
            f"VELOCITY FIELD   Re = {Re:.1f}   Ma = {obs['Ma']:.3f}   {regime}",
            color=TEAL, fontsize=9, fontfamily="monospace", pad=4,
        )

        # ── Vorticity field ───────────────────────────────────────────────
        ax2 = self._ax_vort
        ax2.clear(); ax2.set_facecolor(BG); ax2.axis("off")
        v_lim = max(abs(vort).max() * 0.8, 1e-10)
        ax2.imshow(vort, cmap="RdBu_r", origin="lower", aspect="auto",
                   vmin=-v_lim, vmax=v_lim, interpolation="bilinear")
        ax2.imshow(obs_mask, cmap="gray_r", origin="lower", aspect="auto",
                   alpha=0.9, interpolation="nearest")
        nu_SI = obs.get("nu_SI_m2s", 0)
        ax2.set_title(
            f"VORTICITY ω_z   ν = {_si(nu_SI,'m²/s',2)}   "
            f"τ = {obs['tau']:.3f}   C_D = {obs['drag_coeff']:.3f}",
            color=GOLD, fontsize=8, fontfamily="monospace", pad=4,
        )

        # ── Re history ────────────────────────────────────────────────────
        ax3 = self._ax_Re
        ax3.clear(); ax3.set_facecolor(BG)
        if len(s.Re_history) > 2:
            ax3.plot(s.Re_history, color=TEAL, linewidth=0.9)
            ax3.axhline(50, color=DIM, linewidth=0.5, linestyle="--")
            ax3.axhline(200, color=RED, linewidth=0.5, linestyle="--")
        ax3.set_xlabel("Frame", fontsize=7, color=DIM)
        ax3.set_ylabel("Re", fontsize=7, color=TEAL)
        ax3.set_title("Reynolds Number", fontsize=7, color=TEAL, fontfamily="monospace")

        # ── Drag history ──────────────────────────────────────────────────
        ax4 = self._ax_drag
        ax4.clear(); ax4.set_facecolor(BG)
        if len(s.drag_history) > 2:
            ax4.plot(s.drag_history, color=GOLD, linewidth=0.9)
        ax4.set_xlabel("Frame", fontsize=7, color=DIM)
        ax4.set_ylabel("C_D", fontsize=7, color=GOLD)
        ax4.set_title("Drag Coefficient", fontsize=7, color=TEAL, fontfamily="monospace")

        self._fig.canvas.draw_idle()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN WIDGET
# ══════════════════════════════════════════════════════════════════════════════

class PhysicsObservatoryWidget(SiftaBaseWidget):
    APP_NAME = "SIFTA Physics Observatory"

    def showEvent(self, event):
        super().showEvent(event)
        try:
            from System.swarm_app_focus import publish_focus
            publish_focus(self.APP_NAME, "User is interacting with Physics Observatory")
        except Exception:
            pass

    def build_ui(self, layout: QVBoxLayout) -> None:
        self._rng = np.random.default_rng()

        # ── Tab switcher ──────────────────────────────────────────────────
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, 1)

        # ── Engine A tab ──────────────────────────────────────────────────
        tab_a = QWidget()
        lay_a = QVBoxLayout(tab_a)
        lay_a.setContentsMargins(0, 4, 0, 0)
        self._build_colloid_controls(lay_a)
        self._colloid_canvas = ColloidCanvas()
        lay_a.addWidget(self._colloid_canvas, 1)
        self._tabs.addTab(tab_a, "⚗️  Engine A — Colloid (LJ + Langevin)")

        # ── Engine B tab ──────────────────────────────────────────────────
        tab_b = QWidget()
        lay_b = QVBoxLayout(tab_b)
        lay_b.setContentsMargins(0, 4, 0, 0)
        self._build_lbm_controls(lay_b)
        self._lbm_canvas = LBMCanvas()
        lay_b.addWidget(self._lbm_canvas, 1)
        self._tabs.addTab(tab_b, "🌊  Engine B — Fluid (LBM / Navier-Stokes)")

        # ── PoUW receipt strip ────────────────────────────────────────────
        pouw_row = QHBoxLayout()
        self._pouw_label = QLabel("PoUW: idle")
        self._pouw_label.setStyleSheet(f"color: {DIM}; font-size: 9px; font-family: Menlo;")
        pouw_row.addWidget(self._pouw_label)
        pouw_row.addStretch()
        layout.addLayout(pouw_row)

        # ── Simulation state ──────────────────────────────────────────────
        self._lj_state  = None
        self._lbm_state = None
        self._lj_running  = False
        self._lbm_running = False
        self._lj_timer:  Optional[QTimer] = None
        self._lbm_timer: Optional[QTimer] = None
        self._pouw_timer = self.make_timer(30_000, self._try_pouw_mint)
        self._last_mint_ops = 0

    # ── Engine A controls ─────────────────────────────────────────────────────

    def _build_colloid_controls(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()

        self._btn_lj_run = QPushButton("▶ Run")
        self._btn_lj_run.clicked.connect(self._toggle_lj)
        row.addWidget(self._btn_lj_run)

        self._btn_lj_reset = QPushButton("↺ Reset")
        self._btn_lj_reset.clicked.connect(self._reset_lj)
        row.addWidget(self._btn_lj_reset)

        row.addWidget(self._sep())
        row.addWidget(QLabel("Temperature T*:"))

        self._sld_T = QSlider(Qt.Orientation.Horizontal)
        self._sld_T.setRange(10, 300)   # × 0.01 → T* in [0.1, 3.0]
        self._sld_T.setValue(100)        # T* = 1.0  (≈ ε/kB — near triple point)
        self._sld_T.setFixedWidth(150)
        self._sld_T.valueChanged.connect(self._on_T_change)
        row.addWidget(self._sld_T)

        self._lbl_T = QLabel("T* = 1.00")
        self._lbl_T.setFixedWidth(80)
        row.addWidget(self._lbl_T)
        row.addStretch()

        # Phase hint
        self._lbl_phase_hint = QLabel("GAS ← low T → CRYSTAL")
        self._lbl_phase_hint.setStyleSheet(f"color: {DIM}; font-size: 9px; font-family: Menlo;")
        row.addWidget(self._lbl_phase_hint)

        layout.addLayout(row)

    def _on_T_change(self, val: int) -> None:
        T_star = val / 100.0
        self._lbl_T.setText(f"T* = {T_star:.2f}")
        if self._lj_state is not None:
            self._lj_state.T_set = T_star
        # Update hint
        if T_star < 0.5:
            hint = "T* < 0.5 → expect CRYSTAL"
        elif T_star < 1.5:
            hint = "T* 0.5–1.5 → LIQUID regime"
        else:
            hint = "T* > 1.5 → GAS regime"
        self._lbl_phase_hint.setText(hint)

    def _toggle_lj(self) -> None:
        if self._lj_running:
            self._lj_running = False
            if self._lj_timer:
                self._lj_timer.stop()
            self._btn_lj_run.setText("▶ Run")
            self.set_status("Engine A paused")
        else:
            if self._lj_state is None:
                self._reset_lj()
            self._lj_running = True
            self._lj_timer = self.make_timer(50, self._tick_lj)
            self._btn_lj_run.setText("⏸ Pause")
            self.set_status("Engine A running — Lennard-Jones / Langevin")

    def _reset_lj(self) -> None:
        was = self._lj_running
        if was:
            self._lj_running = False
            if self._lj_timer:
                self._lj_timer.stop()
        T_star = self._sld_T.value() / 100.0
        self._lj_state = lj_init(N=N_DEFAULT, T=T_star, box=BOX_REDUCED)
        self._colloid_canvas.set_state(self._lj_state)
        obs = lj_observe(self._lj_state)
        self._colloid_canvas.render(obs)
        self.set_status("Engine A: colloid field initialized")

    def _tick_lj(self) -> None:
        if self._lj_state is None or not self._lj_running:
            return
        T_star = self._sld_T.value() / 100.0
        # 4 sub-steps per render frame (≈ 80 Hz physics at 50 ms timer)
        for _ in range(4):
            lj_step(self._lj_state, dt=DT_REDUCED, T=T_star, rng=self._rng)
        obs = lj_observe(self._lj_state)
        self._colloid_canvas.render(obs)
        self.set_status(
            f"A | Step {obs['step']:,}  T={obs['T_K']:.1f} K  "
            f"P={_si(obs['P_Pa'],'Pa',2)}  Phase={obs['phase']}"
        )

    # ── Engine B controls ─────────────────────────────────────────────────────

    def _build_lbm_controls(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()

        self._btn_lbm_run = QPushButton("▶ Run")
        self._btn_lbm_run.clicked.connect(self._toggle_lbm)
        row.addWidget(self._btn_lbm_run)

        self._btn_lbm_reset = QPushButton("↺ Reset")
        self._btn_lbm_reset.clicked.connect(self._reset_lbm)
        row.addWidget(self._btn_lbm_reset)

        row.addWidget(self._sep())
        row.addWidget(QLabel("Reynolds Re:"))

        self._sld_Re = QSlider(Qt.Orientation.Horizontal)
        self._sld_Re.setRange(5, 400)
        self._sld_Re.setValue(100)
        self._sld_Re.setFixedWidth(180)
        self._sld_Re.valueChanged.connect(self._on_Re_change)
        row.addWidget(self._sld_Re)

        self._lbl_Re = QLabel("Re = 100")
        self._lbl_Re.setFixedWidth(70)
        row.addWidget(self._lbl_Re)
        row.addStretch()

        self._lbl_regime = QLabel("von Kármán vortex street")
        self._lbl_regime.setStyleSheet(f"color: {DIM}; font-size: 9px; font-family: Menlo;")
        row.addWidget(self._lbl_regime)

        layout.addLayout(row)

    def _on_Re_change(self, val: int) -> None:
        self._lbl_Re.setText(f"Re = {val}")
        if self._lbm_state is not None:
            set_reynolds(self._lbm_state, float(val))
        regime = ("LAMINAR (symmetric wake)" if val < 50 else
                  "VON KÁRMÁN VORTEX STREET" if val < 200 else
                  "TURBULENT ONSET")
        self._lbl_regime.setText(regime)

    def _toggle_lbm(self) -> None:
        if self._lbm_running:
            self._lbm_running = False
            if self._lbm_timer:
                self._lbm_timer.stop()
            self._btn_lbm_run.setText("▶ Run")
            self.set_status("Engine B paused")
        else:
            if self._lbm_state is None:
                self._reset_lbm()
            self._lbm_running = True
            self._lbm_timer = self.make_timer(80, self._tick_lbm)
            self._btn_lbm_run.setText("⏸ Pause")
            self.set_status("Engine B running — Lattice-Boltzmann / Navier-Stokes")

    def _reset_lbm(self) -> None:
        was = self._lbm_running
        if was:
            self._lbm_running = False
            if self._lbm_timer:
                self._lbm_timer.stop()
        Re = self._sld_Re.value()
        self._lbm_state = init_lbm(ny=80, nx=200, Re_target=float(Re))
        self._lbm_canvas.set_state(self._lbm_state)
        obs = collect_lbm_observables(self._lbm_state)
        self._lbm_canvas.render(obs)
        self.set_status(f"Engine B: LBM channel initialized  Re_target={Re}")

    def _tick_lbm(self) -> None:
        if self._lbm_state is None or not self._lbm_running:
            return
        lbm_step(self._lbm_state, n_substeps=3)
        obs = collect_lbm_observables(self._lbm_state)
        self._lbm_canvas.render(obs)
        regime = ("LAMINAR" if obs["Re"] < 50 else
                  "VORTEX STREET" if obs["Re"] < 200 else "TURBULENT")
        self.set_status(
            f"B | Step {obs['step']:,}  Re={obs['Re']:.1f}  "
            f"Ma={obs['Ma']:.3f}  C_D={obs['drag_coeff']:.3f}  {regime}"
        )

    # ── PoUW mint ────────────────────────────────────────────────────────────

    def _try_pouw_mint(self) -> None:
        """Every 30 s: if ops have grown, trigger ATP mint."""
        ops_a = self._lj_state.total_ops  if self._lj_state  else 0
        ops_b = self._lbm_state.total_ops if self._lbm_state else 0
        total = ops_a + ops_b
        new_ops = total - self._last_mint_ops
        if new_ops < 1_000_000:
            return
        self._last_mint_ops = total
        try:
            from System.swarm_atp_synthase import mint_for_epoch
            result = mint_for_epoch()
            minted = result.get("minted_stgm", 0)
            eid    = result.get("ledger_event_id", "?")
            self._pouw_label.setText(
                f"PoUW: {new_ops:,} ops → {minted:.2e} STGM  [{eid}]"
            )
            self._pouw_label.setStyleSheet(f"color: {TEAL}; font-size: 9px; font-family: Menlo;")
        except Exception as e:
            self._pouw_label.setText(f"PoUW: mint skipped ({e})")

    # ── Utility ──────────────────────────────────────────────────────────────

    @staticmethod
    def _sep() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setStyleSheet(f"color: {DIM};")
        return f


# ── Standalone ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PhysicsObservatoryWidget()
    w.setWindowTitle("SIFTA Physics Observatory")
    w.resize(1440, 920)
    w.show()
    sys.exit(app.exec())
