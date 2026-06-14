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

Doctor: AG31 (Antigravity)
Signed: AG31-PHYSICIST
For the Swarm. 🐜⚡
"""
from __future__ import annotations

"""SIFTA Physics Observatory — stigmergic organ for Alice body."""

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
from System.swarm_higgs_vicsek_observatory import (
    TRUTH_BOUNDARY as ENGINE_C_TRUTH_BOUNDARY,
    build_engine_c_payload,
    render_engine_c_summary,
    write_engine_c_receipt,
)
from System.swarm_persistence_inertia_field import (
    TRUTH_BOUNDARY as PERSISTENCE_INERTIA_TRUTH_BOUNDARY,
    render_summary as render_persistence_inertia_summary,
    run_persistence_inertia_protocol,
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
# ENGINE C — SWARM FIELD / HIGGS-VICSEK CANVAS
# ══════════════════════════════════════════════════════════════════════════════

class SwarmFieldCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self._fig = Figure(figsize=(14, 8), facecolor=BG, dpi=90)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setMinimumSize(700, 360)
        gs = self._fig.add_gridspec(1, 2, hspace=0.25, wspace=0.28,
                                    left=0.07, right=0.97, top=0.88, bottom=0.15)
        self._ax_vicsek = self._fig.add_subplot(gs[0, 0])
        self._ax_higgs = self._fig.add_subplot(gs[0, 1])
        for ax in self._fig.axes:
            ax.set_facecolor(BG)
            ax.tick_params(colors=DIM, labelsize=7)
            for sp in ax.spines.values():
                sp.set_color(DIM)
        self.render_empty()

    def render_empty(self) -> None:
        for ax in (self._ax_vicsek, self._ax_higgs):
            ax.clear(); ax.set_facecolor(BG)
            ax.text(0.5, 0.5, "Run Engine C proof",
                    transform=ax.transAxes, ha="center", va="center",
                    color=DIM, fontsize=10, fontfamily="monospace")
            ax.set_xticks([]); ax.set_yticks([])
        self._fig.canvas.draw_idle()

    def render(self, payload: dict) -> None:
        # ── Vicsek order transition ──────────────────────────────────────
        scan = payload["vicsek"]["scan"]
        noises = scan["noises"]
        phis = scan["polar_orders"]
        stds = scan.get("polar_order_std", [0.0] * len(phis))
        ax = self._ax_vicsek
        ax.clear(); ax.set_facecolor(BG)
        ax.errorbar(noises, phis, yerr=stds, color=TEAL, ecolor=DIM,
                    marker="o", markersize=4, linewidth=1.2, capsize=2)
        crit = payload["vicsek"]["critical_noise_estimate"]
        if crit is not None:
            ax.axvline(float(crit), color=GOLD, linewidth=0.8, linestyle="--")
            ax.text(float(crit), 0.05, f"ηc≈{crit:.2f}", color=GOLD,
                    fontsize=7, rotation=90, va="bottom")
        ax.set_ylim(-0.03, 1.03)
        ax.set_xlabel("η noise", color=DIM, fontsize=8)
        ax.set_ylabel("φ polar order", color=TEAL, fontsize=8)
        ax.set_title("Vicsek flocking transition", color=TEAL,
                     fontsize=9, fontfamily="monospace")
        ax.grid(color="#182030", linewidth=0.4, alpha=0.7)

        # ── Higgs analogue swimmer inertia ───────────────────────────────
        swimmers = payload["higgs"]["result"]["swimmers"]
        names = [s["name"].replace("_swimmer", "").replace("_", "\n")
                 for s in swimmers]
        masses = [float(s["effective_mass"]) for s in swimmers]
        latencies = [float(s["latency_ms"]) for s in swimmers]
        ax2 = self._ax_higgs
        ax2.clear(); ax2.set_facecolor(BG)
        bars = ax2.bar(range(len(masses)), masses, color=[DIM, TEAL, GOLD],
                       alpha=0.88)
        for i, (bar, latency) in enumerate(zip(bars, latencies)):
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.06,
                     f"{masses[i]:.2f}×\n{latency:.0f}ms",
                     ha="center", va="bottom", color="#ffffff", fontsize=7)
        ax2.set_xticks(range(len(names)), names, color=DIM, fontsize=7)
        ax2.set_ylabel("effective mass", color=GOLD, fontsize=8)
        ax2.set_title("Scalar substrate → swimmer inertia", color=GOLD,
                      fontsize=9, fontfamily="monospace")
        ax2.grid(axis="y", color="#182030", linewidth=0.4, alpha=0.7)

        self._fig.suptitle("ENGINE C — SWARM FIELD / HIGGS-VICSEK ANALOGUE",
                           color="#ffffff", fontsize=10,
                           fontfamily="monospace")
        self._fig.canvas.draw_idle()


# ══════════════════════════════════════════════════════════════════════════════
# ENGINE D — HIGGS FIELD (LIVE) CANVAS
# ══════════════════════════════════════════════════════════════════════════════
#
# Cowork 2026-05-13. Same Higgs/stigmergy module Codex shipped as the
# engine, but this canvas runs the new HiggsParticleSwimmer organ in real
# time and renders the substrate as a divergent colormap with the
# swimmers as coloured dots whose radius tracks effective mass.
#
# Truth boundary is enforced by the yellow banner in the tab AND by the
# scalar-field module's TRUTH_LABEL/_BOUNDARY constants on every receipt
# this panel writes.

class HiggsLiveCanvas(FigureCanvas):
    """Live render of phi(x,y) + swimmer particles + mobility/mass tail."""

    # Tunable display defaults.
    FIELD_SHAPE = (24, 36)   # (height, width) — wider than tall for the tab
    BANDS = (
        ("free",   0.0, "#ffd54a"),  # gold
        ("weak",   1.0, "#4ee0a8"),  # teal-green
        ("strong", 4.0, "#ff5c5c"),  # red
    )
    PER_BAND = 25

    def __init__(self, parent=None):
        self._fig = Figure(figsize=(14, 7), facecolor=BG, dpi=90)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setMinimumSize(700, 380)
        gs = self._fig.add_gridspec(
            2, 3,
            hspace=0.42, wspace=0.32,
            left=0.05, right=0.97, top=0.92, bottom=0.10,
            height_ratios=[3, 1],
        )
        self._ax_field = self._fig.add_subplot(gs[0, :])      # big field map
        self._ax_order = self._fig.add_subplot(gs[1, 0])      # order param history
        self._ax_mass  = self._fig.add_subplot(gs[1, 1])      # mean mass per band
        self._ax_mob   = self._fig.add_subplot(gs[1, 2])      # mobility per band
        for ax in self._fig.axes:
            ax.set_facecolor(BG)
            ax.tick_params(colors=DIM, labelsize=7)
            for sp in ax.spines.values():
                sp.set_color(DIM)

        self._field = None
        self._swimmers: dict = {}
        self._order_history: list[float] = []
        self._pot_history: list[float] = []
        self._mass_history: dict[str, list[float]] = {}
        self._mob_history: dict[str, list[float]] = {}
        self._frame = 0

    def reset(self) -> None:
        """Build a fresh field + fresh swimmers + clear all histories."""
        from System.swarm_higgs_stigmergy_field import (
            HiggsFieldConfig, HiggsStigmergyField, HiggsParticleSwimmer,
        )
        h, w = self.FIELD_SHAPE
        cfg = HiggsFieldConfig(
            width=w, height=h, seed=int(time.time()) % 9973,
            initial_noise=0.05,
        )
        self._field = HiggsStigmergyField(cfg)
        self._swimmers = {}
        for name, coupling, color in self.BANDS:
            self._swimmers[name] = (
                HiggsParticleSwimmer(
                    n=self.PER_BAND, coupling=coupling,
                    field_shape=(h, w), seed=hash(name) & 0xFFFF,
                    name=name, thermal_kick=0.5,
                ),
                color,
            )
        self._order_history = []
        self._pot_history = []
        self._mass_history = {name: [] for name, *_ in self.BANDS}
        self._mob_history = {name: [] for name, *_ in self.BANDS}
        self._frame = 0
        self.render()

    def step(self, n: int = 1) -> None:
        """Advance the field n times AND every swimmer n times."""
        if self._field is None:
            self.reset()
        from System.swarm_higgs_stigmergy_field import phi_as_array
        for _ in range(n):
            self._field.step()
            phi = phi_as_array(self._field)
            for swimmer, _color in self._swimmers.values():
                swimmer.step(phi)
            self._order_history.append(self._field.order_parameter)
            self._pot_history.append(self._field.mean_potential)
            for name, (sw, _) in self._swimmers.items():
                self._mass_history[name].append(sw.mean_mass())
                self._mob_history[name].append(sw.mobility())
            self._frame += 1
            # Trim history so tail plots don't grow forever.
            max_hist = 600
            if len(self._order_history) > max_hist:
                self._order_history = self._order_history[-max_hist:]
                self._pot_history = self._pot_history[-max_hist:]
                for name in self._mass_history:
                    self._mass_history[name] = self._mass_history[name][-max_hist:]
                    self._mob_history[name] = self._mob_history[name][-max_hist:]

    def latest_stats(self) -> dict:
        if not self._order_history:
            return {}
        return {
            "frame": self._frame,
            "order": self._order_history[-1],
            "mean_potential": self._pot_history[-1],
            "bands": {
                name: {
                    "mass": self._mass_history[name][-1],
                    "mobility": self._mob_history[name][-1],
                    "coupling": next(c for n, c, _ in self.BANDS if n == name),
                }
                for name in self._mass_history
            },
        }

    def render(self) -> None:
        if self._field is None:
            for ax in (self._ax_field, self._ax_order, self._ax_mass, self._ax_mob):
                ax.clear(); ax.set_facecolor(BG)
                ax.text(
                    0.5, 0.5, "Press Run or Step to start",
                    transform=ax.transAxes, ha="center", va="center",
                    color=DIM, fontsize=10, fontfamily="monospace",
                )
                ax.set_xticks([]); ax.set_yticks([])
            self._fig.canvas.draw_idle()
            return

        from System.swarm_higgs_stigmergy_field import phi_as_array
        phi = phi_as_array(self._field)
        h, w = phi.shape

        # ── Field colormap with swimmers ─────────────────────────────────
        ax = self._ax_field
        ax.clear(); ax.set_facecolor(BG)
        # Symmetric vmin/vmax around 0 so the diverging colormap is honest.
        vmax = max(abs(phi).max(), 0.05)
        ax.imshow(
            phi, cmap="RdBu_r", origin="lower", aspect="auto",
            vmin=-vmax, vmax=vmax, interpolation="bilinear",
            extent=(0, w, 0, h),
        )
        # Swimmer dots — radius proportional to mean mass per band.
        for name, (swimmer, color) in self._swimmers.items():
            sizes = 8.0 + 28.0 * (swimmer.mass - 1.0) / max(swimmer.mass.max(), 1.0)
            ax.scatter(
                swimmer.pos[:, 0], swimmer.pos[:, 1],
                s=sizes, c=color, edgecolor="#0a0e16", linewidth=0.5,
                label=f"{name} (g={swimmer.coupling:.1f})",
                alpha=0.92,
            )
        ax.set_xlim(0, w); ax.set_ylim(0, h)
        ax.set_xticks([]); ax.set_yticks([])
        order = self._order_history[-1] if self._order_history else 0.0
        pot = self._pot_history[-1] if self._pot_history else 1.0
        ax.set_title(
            f"φ(x,y) substrate   order={order:.4f}   V_mean={pot:.4f}   "
            f"frame={self._frame}",
            color=TEAL, fontsize=10, fontfamily="monospace", pad=4,
        )
        ax.legend(
            loc="upper right", facecolor="#0a0e16", edgecolor=DIM,
            labelcolor="white", fontsize=7, framealpha=0.85,
        )

        # ── Order parameter history ──────────────────────────────────────
        ax2 = self._ax_order
        ax2.clear(); ax2.set_facecolor(BG)
        if len(self._order_history) >= 2:
            ax2.plot(self._order_history, color=TEAL, linewidth=1.0,
                     label="order")
            ax2.plot(self._pot_history, color=RED, linewidth=0.8,
                     linestyle="--", label="V_mean")
            ax2.legend(loc="center right", facecolor=BG, edgecolor=DIM,
                       labelcolor="white", fontsize=6, framealpha=0.6)
        ax2.set_ylim(-0.05, 1.10)
        ax2.set_xlabel("frame", color=DIM, fontsize=7)
        ax2.set_title("Symmetry breaking", color=TEAL, fontsize=8,
                      fontfamily="monospace")

        # ── Mean mass per band ───────────────────────────────────────────
        ax3 = self._ax_mass
        ax3.clear(); ax3.set_facecolor(BG)
        for name, (_sw, color) in self._swimmers.items():
            if len(self._mass_history[name]) >= 2:
                ax3.plot(self._mass_history[name], color=color, linewidth=1.0,
                         label=name)
        ax3.set_xlabel("frame", color=DIM, fontsize=7)
        ax3.set_ylabel("mean mass", color=GOLD, fontsize=7)
        ax3.set_title("Effective mass spectrum", color=GOLD, fontsize=8,
                      fontfamily="monospace")
        ax3.grid(color="#182030", linewidth=0.4, alpha=0.6)

        # ── Mobility per band ────────────────────────────────────────────
        ax4 = self._ax_mob
        ax4.clear(); ax4.set_facecolor(BG)
        for name, (_sw, color) in self._swimmers.items():
            if len(self._mob_history[name]) >= 2:
                ax4.plot(self._mob_history[name], color=color, linewidth=1.0,
                         label=name)
        ax4.set_xlabel("frame", color=DIM, fontsize=7)
        ax4.set_ylabel("|v| mean", color=GOLD, fontsize=7)
        ax4.set_title("Mobility (heavy → slow)", color=GOLD, fontsize=8,
                      fontfamily="monospace")
        ax4.grid(color="#182030", linewidth=0.4, alpha=0.6)

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
        self._tab_a = tab_a

        # ── Engine B tab ──────────────────────────────────────────────────
        tab_b = QWidget()
        lay_b = QVBoxLayout(tab_b)
        lay_b.setContentsMargins(0, 4, 0, 0)
        self._build_lbm_controls(lay_b)
        self._lbm_canvas = LBMCanvas()
        lay_b.addWidget(self._lbm_canvas, 1)
        self._tabs.addTab(tab_b, "🌊  Engine B — Fluid (LBM / Navier-Stokes)")
        self._tab_b = tab_b

        # ── Engine C tab ──────────────────────────────────────────────────
        tab_c = QWidget()
        lay_c = QVBoxLayout(tab_c)
        lay_c.setContentsMargins(0, 4, 0, 0)
        self._build_engine_c_controls(lay_c)
        self._engine_c_canvas = SwarmFieldCanvas()
        lay_c.addWidget(self._engine_c_canvas, 2)
        self._engine_c_text = QPlainTextEdit()
        self._engine_c_text.setReadOnly(True)
        self._engine_c_text.setMaximumHeight(250)
        self._engine_c_text.setPlainText(
            "Engine C ready.\n"
            "Click Run Proof + Receipt to execute the Vicsek scan and "
            "Higgs/stigmergic analogue.\n\n"
            f"Truth boundary: {ENGINE_C_TRUTH_BOUNDARY}"
        )
        self._engine_c_text.setStyleSheet(
            f"background: #050608; color: {TEAL}; font-family: Menlo; "
            "font-size: 10px; border: 1px solid #1d2a38;"
        )
        lay_c.addWidget(self._engine_c_text, 1)
        self._tabs.addTab(tab_c, "🐝  Engine C — Swarm Field / Higgs-Vicsek")

        # ── Engine D — Higgs Field (Live) ─────────────────────────────────
        # Architect 2026-05-13 doctrine: "Treat swimmers as literal
        # particles. Give them (x,y), velocity, coupling strength.
        # Mass = 1 + coupling × |φ|. Gradient force from the field pulls
        # them. Free swimmers diffuse fast; coupled ones get heavy and
        # slow." This tab runs the HiggsStigmergyField + HiggsParticleSwimmer
        # in real time so the mass spectrum is visible, not implied.
        # Engine C is the static Vicsek-scan + bar-chart proof (Cursor/
        # Codex's earlier surgery — left intact per §8.5 consensus). This
        # is the complementary live view.
        tab_d = QWidget()
        lay_d = QVBoxLayout(tab_d)
        lay_d.setContentsMargins(0, 4, 0, 0)
        self._build_engine_d_controls(lay_d)
        self._higgs_live_canvas = HiggsLiveCanvas()
        lay_d.addWidget(self._higgs_live_canvas, 1)
        # Yellow doctrine banner — investors see this first, doctrine
        # is held BEFORE anyone interprets the colormap.
        d_banner = QLabel(
            "ARCHITECT_DOCTRINE — Classical scalar-field analogue only. "
            "No OBSERVED Higgs bosons, no Yang-Mills proof, no particle-"
            "physics discovery on this Mac. Coupled swimmers acquire "
            "local effective mass from the substrate."
        )
        d_banner.setWordWrap(True)
        d_banner.setStyleSheet(
            f"background: #2a2410; color: {GOLD}; font-family: Menlo; "
            f"font-size: 10px; font-weight: 700; padding: 6px 8px; "
            f"border: 1px solid #5a4820; border-radius: 4px;"
        )
        lay_d.addWidget(d_banner)
        self._tabs.addTab(tab_d, "🌌  Engine D — Higgs Field (Live)")
        self._tab_d = tab_d

        # ── Engine E — Persistence / Organizational Inertia ───────────────
        tab_e = QWidget()
        lay_e = QVBoxLayout(tab_e)
        lay_e.setContentsMargins(0, 4, 0, 0)
        self._build_engine_e_controls(lay_e)
        self._engine_e_text = QPlainTextEdit()
        self._engine_e_text.setReadOnly(True)
        self._engine_e_text.setPlainText(
            "Engine E ready.\n"
            "Runs the §20.F perturbation protocol: baseline → nudge → "
            "recovery across free, recent, organ-member, and sentinel "
            "cohorts.\n\n"
            f"Truth boundary: {PERSISTENCE_INERTIA_TRUTH_BOUNDARY}"
        )
        self._engine_e_text.setStyleSheet(
            f"background: #050608; color: {TEAL}; font-family: Menlo; "
            "font-size: 10px; border: 1px solid #1d2a38;"
        )
        lay_e.addWidget(self._engine_e_text, 1)
        self._tabs.addTab(tab_e, "🧲  Engine E — Persistence Inertia")

        # Architect 2026-05-13 UX feedback: "I ran experiments in one tab
        # and switched to another — NPU got throttled because the first
        # one kept running. Steve Jobs would auto-pause." Wire the
        # currentChanged signal so any running engine whose tab is now
        # hidden gets cleanly paused.
        try:
            self._tabs.currentChanged.connect(self._on_tab_changed)
        except Exception as _conn_exc:
            print(f"[PhysicsObservatory] tab-change wire failed: {_conn_exc}")

        # ── Experiment governor ─────────────────────────────────────────
        # One owner-facing rule: one heavy experiment at a time. If George
        # switches tabs, live engines auto-pause; if a one-shot experiment
        # is running, the UI says so before more work can be queued.
        gov_row = QHBoxLayout()
        self._governor_label = QLabel(
            "Ready — one experiment at a time. Switch tabs safely; live engines auto-pause."
        )
        self._governor_label.setStyleSheet(
            f"color: {GOLD}; font-size: 10px; font-family: Menlo; "
            "font-weight: 700;"
        )
        gov_row.addWidget(self._governor_label, 1)
        self._btn_stop_experiment = QPushButton("⏹ Stop / Pause current")
        self._btn_stop_experiment.setToolTip(
            "Pause live engines immediately. For long one-shot Python calls, "
            "this marks stop requested and blocks new experiments until Ready."
        )
        self._btn_stop_experiment.setEnabled(False)
        self._btn_stop_experiment.clicked.connect(self._stop_current_experiment)
        gov_row.addWidget(self._btn_stop_experiment)
        layout.addLayout(gov_row)

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
        self._engine_c_payload: Optional[dict] = None
        self._active_experiment_name: Optional[str] = None
        self._stop_requested = False
        self._pouw_timer = self.make_timer(30_000, self._try_pouw_mint)
        self._last_mint_ops = 0

        # Architect 2026-05-13 11:00 — auto-seed first frame on open so
        # the canvases show real physics fields instead of blank axes.
        # Was: empty plots until owner clicked Run/Reset. The 3 LJ axes
        # and 4 LBM axes now have meaningful initial content from frame 0.
        # Owner still clicks Run to start the time-stepping loop; this
        # just paints the t=0 snapshot.
        try:
            QTimer.singleShot(0, self._seed_first_frames)
        except Exception:
            pass

    def _on_tab_changed(self, new_index: int) -> None:
        """Auto-pause any running timer-driven engine whose tab is no
        longer current. Steve-Jobs UX — just do the right thing, name
        what got paused in the status bar, don't ask permission.

        Engines A (LJ), B (LBM), D (Higgs Live) all use periodic
        QTimers that would otherwise keep eating CPU/NPU even while
        their tab is hidden. Engine C (Vicsek+Higgs static proof) and
        Engine E (Persistence Inertia) are one-shot button experiments
        with no timer to stop."""
        try:
            new_widget = self._tabs.widget(new_index)
        except Exception:
            return
        paused: list[str] = []

        # Engine A — LJ Colloid
        if getattr(self, "_lj_running", False):
            a_tab = getattr(self, "_tab_a", None)
            if a_tab is not None and a_tab is not new_widget:
                try:
                    if self._lj_timer:
                        self._lj_timer.stop()
                    self._lj_running = False
                    if hasattr(self, "_btn_lj_run"):
                        self._btn_lj_run.setText("▶ Run")
                    paused.append("Engine A (Colloid)")
                except Exception as e:
                    print(f"[PhysicsObservatory] Engine A auto-pause failed: {e}")

        # Engine B — LBM Fluid
        if getattr(self, "_lbm_running", False):
            b_tab = getattr(self, "_tab_b", None)
            if b_tab is not None and b_tab is not new_widget:
                try:
                    if self._lbm_timer:
                        self._lbm_timer.stop()
                    self._lbm_running = False
                    if hasattr(self, "_btn_lbm_run"):
                        self._btn_lbm_run.setText("▶ Run")
                    paused.append("Engine B (Fluid)")
                except Exception as e:
                    print(f"[PhysicsObservatory] Engine B auto-pause failed: {e}")

        # Engine D — Higgs Live
        if getattr(self, "_higgs_live_running", False):
            d_tab = getattr(self, "_tab_d", None)
            if d_tab is not None and d_tab is not new_widget:
                try:
                    timer = getattr(self, "_higgs_live_timer", None)
                    if timer:
                        timer.stop()
                    self._higgs_live_running = False
                    if hasattr(self, "_btn_d_run"):
                        self._btn_d_run.setText("▶ Run")
                    paused.append("Engine D (Higgs Live)")
                except Exception as e:
                    print(f"[PhysicsObservatory] Engine D auto-pause failed: {e}")

        if paused:
            self.set_status(
                "⏸ Auto-paused " + " + ".join(paused)
                + " to free CPU — click ▶ Run to resume."
            )
            if hasattr(self, "_governor_label"):
                self._governor_label.setText(
                    "Ready — paused hidden engine to avoid throttling."
                )

    def _pause_live_engines(self, reason: str) -> list[str]:
        """Pause every timer-driven engine and return the names paused."""
        paused: list[str] = []
        if getattr(self, "_lj_running", False):
            if getattr(self, "_lj_timer", None):
                self._lj_timer.stop()
            self._lj_running = False
            if hasattr(self, "_btn_lj_run"):
                self._btn_lj_run.setText("▶ Run")
            paused.append("Engine A")
        if getattr(self, "_lbm_running", False):
            if getattr(self, "_lbm_timer", None):
                self._lbm_timer.stop()
            self._lbm_running = False
            if hasattr(self, "_btn_lbm_run"):
                self._btn_lbm_run.setText("▶ Run")
            paused.append("Engine B")
        if getattr(self, "_higgs_live_running", False):
            timer = getattr(self, "_higgs_live_timer", None)
            if timer:
                timer.stop()
            self._higgs_live_running = False
            if hasattr(self, "_btn_d_run"):
                self._btn_d_run.setText("▶ Run")
            paused.append("Engine D")
        if paused:
            self.set_status(
                f"⏸ Paused {' + '.join(paused)} before {reason}."
            )
        return paused

    def _experiment_buttons(self) -> list[QPushButton]:
        """Every button that can start or mutate a heavy physics run."""
        names = (
            "_btn_lj_run", "_btn_lj_reset",
            "_btn_lbm_run", "_btn_lbm_reset",
            "_btn_engine_c_run", "_btn_engine_c_preview",
            "_btn_engine_e_run", "_btn_engine_e_preview",
            "_btn_d_run", "_btn_d_step", "_btn_d_relax", "_btn_d_reset",
            "_btn_d_receipt", "_btn_d_sweep", "_btn_d_killer",
            "_btn_d_symmetry", "_btn_d_adaptive", "_btn_d_memory",
            "_btn_d_collider", "_btn_d_temporal", "_btn_d_civ_shocks",
        )
        return [
            button for name in names
            if isinstance((button := getattr(self, name, None)), QPushButton)
        ]

    def _set_experiment_controls_enabled(self, enabled: bool) -> None:
        for button in self._experiment_buttons():
            button.setEnabled(enabled)
        if hasattr(self, "_btn_stop_experiment"):
            self._btn_stop_experiment.setEnabled(
                (not enabled) or any((
                    getattr(self, "_lj_running", False),
                    getattr(self, "_lbm_running", False),
                    getattr(self, "_higgs_live_running", False),
                ))
            )

    def _begin_experiment(self, name: str) -> bool:
        """Gate one-shot experiments so the owner cannot stack work."""
        active = getattr(self, "_active_experiment_name", None)
        if active:
            self.set_status(
                f"{active} is still running. Wait for Ready or press Stop/Pause."
            )
            return False
        self._pause_live_engines(name)
        self._active_experiment_name = name
        self._stop_requested = False
        self._set_experiment_controls_enabled(False)
        if hasattr(self, "_governor_label"):
            self._governor_label.setText(
                f"Running {name} — wait for Ready before switching experiments."
            )
        self.set_status(
            f"Running {name}. Stop/Pause will prevent more work from queuing."
        )
        QApplication.processEvents()
        return True

    def _end_experiment(self, final_status: str | None = None) -> None:
        self._active_experiment_name = None
        self._stop_requested = False
        self._set_experiment_controls_enabled(True)
        if hasattr(self, "_btn_stop_experiment"):
            self._btn_stop_experiment.setEnabled(False)
        if hasattr(self, "_governor_label"):
            self._governor_label.setText(
                "Ready — one experiment at a time. Switch tabs safely; live engines auto-pause."
            )
        if final_status:
            self.set_status(final_status)

    def _stop_current_experiment(self) -> None:
        active = getattr(self, "_active_experiment_name", None)
        paused = self._pause_live_engines("owner stop/pause")
        if active:
            self._stop_requested = True
            self.set_status(
                f"Stop requested for {active}; finishing current Python call, then Ready."
            )
            if hasattr(self, "_governor_label"):
                self._governor_label.setText(
                    f"Stop requested for {active} — no new experiment will start."
                )
            return
        self._set_experiment_controls_enabled(True)
        if hasattr(self, "_btn_stop_experiment"):
            self._btn_stop_experiment.setEnabled(False)
        if hasattr(self, "_governor_label"):
            if paused:
                self._governor_label.setText("Ready — live engine paused.")
            else:
                self._governor_label.setText("Ready — no active experiment.")
        self.set_status("Ready — no active physics experiment.")

    def _seed_first_frames(self) -> None:
        """Render frame-zero for both engines so opening the app shows
        live data instead of empty axes. Idempotent: re-seeding wipes
        any running state, which is the same contract as Reset."""
        try:
            self._reset_lj()
        except Exception as e:
            print(f"[PhysicsObservatory] LJ seed failed: {e}")
        try:
            self._reset_lbm()
        except Exception as e:
            print(f"[PhysicsObservatory] LBM seed failed: {e}")

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
            if hasattr(self, "_btn_stop_experiment") and not getattr(self, "_active_experiment_name", None):
                self._btn_stop_experiment.setEnabled(False)
            if hasattr(self, "_governor_label"):
                self._governor_label.setText("Ready — Engine A paused.")
            self.set_status("Engine A paused")
        else:
            if self._lj_state is None:
                self._reset_lj()
            self._lj_running = True
            self._lj_timer = self.make_timer(50, self._tick_lj)
            self._btn_lj_run.setText("⏸ Pause")
            if hasattr(self, "_btn_stop_experiment"):
                self._btn_stop_experiment.setEnabled(True)
            if hasattr(self, "_governor_label"):
                self._governor_label.setText(
                    "Engine A running — switch tabs or Stop/Pause will pause it."
                )
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
            if hasattr(self, "_btn_stop_experiment") and not getattr(self, "_active_experiment_name", None):
                self._btn_stop_experiment.setEnabled(False)
            if hasattr(self, "_governor_label"):
                self._governor_label.setText("Ready — Engine B paused.")
            self.set_status("Engine B paused")
        else:
            if self._lbm_state is None:
                self._reset_lbm()
            self._lbm_running = True
            self._lbm_timer = self.make_timer(80, self._tick_lbm)
            self._btn_lbm_run.setText("⏸ Pause")
            if hasattr(self, "_btn_stop_experiment"):
                self._btn_stop_experiment.setEnabled(True)
            if hasattr(self, "_governor_label"):
                self._governor_label.setText(
                    "Engine B running — switch tabs or Stop/Pause will pause it."
                )
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

    # ── Engine C controls ─────────────────────────────────────────────────────

    def _build_engine_c_controls(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()

        self._btn_engine_c_run = QPushButton("▶ Run Proof + Receipt")
        self._btn_engine_c_run.clicked.connect(self._run_engine_c_with_receipt)
        row.addWidget(self._btn_engine_c_run)

        self._btn_engine_c_preview = QPushButton("Preview (no receipt)")
        self._btn_engine_c_preview.clicked.connect(self._run_engine_c_preview)
        row.addWidget(self._btn_engine_c_preview)

        row.addWidget(self._sep())
        truth = QLabel("Classical analogues only — no collider claim")
        truth.setStyleSheet(f"color: {GOLD}; font-size: 9px; font-family: Menlo;")
        row.addWidget(truth)
        row.addStretch()

        layout.addLayout(row)

    def _run_engine_c_preview(self) -> None:
        self._run_engine_c(write_receipt=False)

    def _run_engine_c_with_receipt(self) -> None:
        self._run_engine_c(write_receipt=True)

    def _run_engine_c(self, *, write_receipt: bool) -> None:
        name = "Engine C proof" if write_receipt else "Engine C preview"
        if not self._begin_experiment(name):
            return
        self._btn_engine_c_run.setEnabled(False)
        self._btn_engine_c_preview.setEnabled(False)
        final_status = None
        try:
            self.set_status("Engine C running — Vicsek + Higgs/Stigmergy")
            payload = build_engine_c_payload()
            if write_receipt:
                payload["receipt"] = write_engine_c_receipt(payload)
            self._engine_c_payload = payload
            self._engine_c_canvas.render(payload)
            text = render_engine_c_summary(payload)
            if write_receipt:
                rec = payload.get("receipt", {})
                text += (
                    "\n\nReceipt written: "
                    f"{rec.get('trace_id', '?')}  sha={str(rec.get('sha256', ''))[:16]}"
                )
            self._engine_c_text.setPlainText(text)
            final_status = (
                "Engine C complete — "
                f"φ drop={payload['summary']['vicsek_order_drop']:.3f}, "
                f"mass span={payload['summary']['higgs_mass_span']:.3f}"
            )
            self.set_status(final_status)
        except Exception as e:
            self._engine_c_text.setPlainText(f"Engine C failed: {type(e).__name__}: {e}")
            final_status = f"Engine C failed: {e}"
            self.set_status(final_status)
        finally:
            self._btn_engine_c_run.setEnabled(True)
            self._btn_engine_c_preview.setEnabled(True)
            self._end_experiment(final_status)

    # ── Engine E controls ─────────────────────────────────────────────────────

    def _build_engine_e_controls(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()

        self._btn_engine_e_run = QPushButton("▶ Run Perturbation + Receipt")
        self._btn_engine_e_run.clicked.connect(self._run_engine_e_with_receipt)
        row.addWidget(self._btn_engine_e_run)

        self._btn_engine_e_preview = QPushButton("Preview (no receipt)")
        self._btn_engine_e_preview.clicked.connect(self._run_engine_e_preview)
        row.addWidget(self._btn_engine_e_preview)

        row.addWidget(self._sep())
        truth = QLabel("Organizational inertia analogue — no particle-physics claim")
        truth.setStyleSheet(f"color: {GOLD}; font-size: 9px; font-family: Menlo;")
        row.addWidget(truth)
        row.addStretch()

        layout.addLayout(row)

    def _run_engine_e_preview(self) -> None:
        self._run_engine_e(write_receipt=False)

    def _run_engine_e_with_receipt(self) -> None:
        self._run_engine_e(write_receipt=True)

    def _run_engine_e(self, *, write_receipt: bool) -> None:
        name = "Engine E perturbation" if write_receipt else "Engine E preview"
        if not self._begin_experiment(name):
            return
        self._btn_engine_e_run.setEnabled(False)
        self._btn_engine_e_preview.setEnabled(False)
        final_status = None
        try:
            self.set_status("Engine E running — persistence inertia protocol")
            result = run_persistence_inertia_protocol(write=write_receipt)
            text = render_persistence_inertia_summary(result)
            if write_receipt:
                rec = result.get("receipt", {})
                text += (
                    "\n\nReceipt written: "
                    f"{rec.get('trace_id', '?')}  sha={str(rec.get('sha256', ''))[:16]}"
                )
            self._engine_e_text.setPlainText(text)
            final_status = (
                "Engine E complete — "
                f"embedded/free resistance="
                f"{result['summary']['most_embedded_resistance_vs_free']:.2f}x"
            )
            self.set_status(final_status)
        except Exception as e:
            self._engine_e_text.setPlainText(f"Engine E failed: {type(e).__name__}: {e}")
            final_status = f"Engine E failed: {e}"
            self.set_status(final_status)
        finally:
            self._btn_engine_e_run.setEnabled(True)
            self._btn_engine_e_preview.setEnabled(True)
            self._end_experiment(final_status)

    # ── Engine D — Higgs Field (Live) controls ───────────────────────────────

    def _build_engine_d_controls(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()

        self._btn_d_run = QPushButton("▶ Run")
        self._btn_d_run.clicked.connect(self._toggle_higgs_live)
        row.addWidget(self._btn_d_run)

        self._btn_d_step = QPushButton("Step")
        self._btn_d_step.clicked.connect(self._higgs_live_step_one)
        row.addWidget(self._btn_d_step)

        self._btn_d_relax = QPushButton("Relax 100")
        self._btn_d_relax.clicked.connect(self._higgs_live_relax_100)
        row.addWidget(self._btn_d_relax)

        self._btn_d_reset = QPushButton("↺ Reset")
        self._btn_d_reset.clicked.connect(self._higgs_live_reset)
        row.addWidget(self._btn_d_reset)

        self._btn_d_receipt = QPushButton("📜 Write receipt")
        self._btn_d_receipt.clicked.connect(self._higgs_live_write_receipt)
        row.addWidget(self._btn_d_receipt)

        # Architect 2026-05-13 — Grok regime knob. Drive amplitude scales
        # the whole force vector on every swimmer. Slider from 0.1× (weak
        # regime) to 10.0× (saturation regime). Drag it during the demo
        # and watch the mass-spectrum response.
        row.addWidget(self._sep())
        row.addWidget(QLabel("Drive ×:"))
        self._sld_d_drive = QSlider(Qt.Orientation.Horizontal)
        self._sld_d_drive.setRange(1, 100)   # ÷10 → 0.1 to 10.0
        self._sld_d_drive.setValue(10)        # default = 1.0×
        self._sld_d_drive.setFixedWidth(140)
        self._sld_d_drive.valueChanged.connect(self._on_d_drive_change)
        row.addWidget(self._sld_d_drive)
        self._lbl_d_drive = QLabel("1.0×")
        self._lbl_d_drive.setFixedWidth(48)
        self._lbl_d_drive.setStyleSheet(f"color: {GOLD}; font-family: Menlo;")
        row.addWidget(self._lbl_d_drive)

        self._btn_d_sweep = QPushButton("⚡ Force sweep")
        self._btn_d_sweep.setToolTip(
            "Run the §20.F HYPOTHESIS sweep: drive_amplitude across "
            "[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]. Writes a "
            "HIGGS_FORCE_REGIME_SWEEP receipt."
        )
        self._btn_d_sweep.clicked.connect(self._higgs_force_sweep_receipt)
        row.addWidget(self._btn_d_sweep)

        self._btn_d_killer = QPushButton("🎯 Killer demo")
        self._btn_d_killer.setToolTip(
            "Q9 four-type demo: ghost / worker / organ / sentinel. "
            "Same drive applied to all; mobility stratifies via the "
            "unified mass law m_eff = 1 + g·|phi| + α·log(1+writes) + "
            "β·n_organs. Writes a HIGGS_KILLER_DEMO receipt."
        )
        self._btn_d_killer.clicked.connect(self._higgs_killer_demo_receipt)
        row.addWidget(self._btn_d_killer)

        self._btn_d_symmetry = QPushButton("🌀 Symmetry break")
        self._btn_d_symmetry.setToolTip(
            "Q6 spontaneous symmetry breaking. 80 IDENTICAL swimmers, "
            "linear inertia, crowding competition on. Population bifurcates "
            "into ~2x mass spread without any pre-labeling. Writes a "
            "HIGGS_SYMMETRY_BREAK receipt."
        )
        self._btn_d_symmetry.clicked.connect(self._higgs_symmetry_break_receipt)
        row.addWidget(self._btn_d_symmetry)

        self._btn_d_adaptive = QPushButton("🧠 Adaptive agents")
        self._btn_d_adaptive.setToolTip(
            "Persistence Inertia Field — adaptive layer. Each agent holds "
            "a softmax policy over {wander, chase, deposit, flee}. "
            "Identical starting policies + contextual reward → emergent "
            "role distribution. Writes a PERSISTENCE_INERTIA_FIELD_ADAPTIVE "
            "receipt."
        )
        self._btn_d_adaptive.clicked.connect(self._higgs_adaptive_receipt)
        row.addWidget(self._btn_d_adaptive)

        self._btn_d_memory = QPushButton("💾 Memory field (Q4)")
        self._btn_d_memory.setToolTip(
            "Q4 — Memory-driven field. phi(x,y) = tanh(decaying swimmer "
            "deposits). No Mexican-hat dynamics. The field IS the memory. "
            "Writes a PERSISTENCE_INERTIA_FIELD_MEMORY receipt."
        )
        self._btn_d_memory.clicked.connect(self._higgs_memory_field_receipt)
        row.addWidget(self._btn_d_memory)

        self._btn_d_collider = QPushButton("💥 Collider (Q7)")
        self._btn_d_collider.setToolTip(
            "Q7 — Two adaptive civilizations crash. Settled cultures with "
            "distinct role distributions, opposite mean velocities. "
            "Measures mass exchange + post-collision cluster count. "
            "Writes a PERSISTENCE_INERTIA_FIELD_COLLIDER receipt."
        )
        self._btn_d_collider.clicked.connect(self._higgs_collider_receipt)
        row.addWidget(self._btn_d_collider)

        self._btn_d_temporal = QPushButton("🌡️ Temporal phase (V2)")
        self._btn_d_temporal.setToolTip(
            "§21 Vector #2 — Temporal phase transitions. Scan memory "
            "field decay across regimes; measure Scheffer-2009 early-"
            "warning signals (variance, lag-1 autocorrelation, skewness) "
            "on the field order parameter time-series. Writes a "
            "PERSISTENCE_INERTIA_FIELD_TEMPORAL_PHASE receipt."
        )
        self._btn_d_temporal.clicked.connect(self._higgs_temporal_phase_receipt)
        row.addWidget(self._btn_d_temporal)

        self._btn_d_civ_shocks = QPushButton("🔥 Civilization shocks")
        self._btn_d_civ_shocks.setToolTip(
            "Codex's civilization shock lab. 10 shocks: memory erase, "
            "sentinel loss, write tax, reward inversion, parasites, "
            "organ sever, field freeze, misinformation, resource collapse, "
            "competing civ. Writes a CIVILIZATION_SHOCK_LAB_V1 receipt."
        )
        self._btn_d_civ_shocks.clicked.connect(self._civ_shocks_receipt)
        row.addWidget(self._btn_d_civ_shocks)

        self._btn_d_ghost = QPushButton("👻 Ghost civs (V3)")
        self._btn_d_ghost.setToolTip(
            "§21 Vector #3 — Ghost civilizations. Settle an adaptive "
            "civilization. Delete the agents but keep the field. Spawn "
            "naive newborns into the inherited field. Measure whether "
            "the dead civilization's roles re-emerge in the unborn. "
            "Writes a PERSISTENCE_INERTIA_FIELD_GHOST_CIVILIZATIONS receipt."
        )
        self._btn_d_ghost.clicked.connect(self._higgs_ghost_civ_receipt)
        row.addWidget(self._btn_d_ghost)

        self._btn_d_dream = QPushButton("💤 Dream cycle (V5)")
        self._btn_d_dream.setToolTip(
            "§21 Vector #5 — Dream organ. Detects idle window in "
            "Alice's journal (low voice + face activity), runs offline "
            "replay through memory-gravity scorer, mints relief STGM "
            "and writes a DREAM_CYCLE receipt with the digest line "
            "she'll see in her diary tomorrow."
        )
        self._btn_d_dream.clicked.connect(self._alice_dream_cycle_receipt)
        row.addWidget(self._btn_d_dream)

        row.addWidget(self._sep())
        self._lbl_d_stats = QLabel("φ→— | strong/free mob ratio →—")
        self._lbl_d_stats.setStyleSheet(
            f"color: {TEAL}; font-size: 9px; font-family: Menlo;"
        )
        row.addWidget(self._lbl_d_stats)
        row.addStretch()
        layout.addLayout(row)

    def _on_d_drive_change(self, raw: int) -> None:
        """Slider → drive_amplitude. Live-pushed to every swimmer band."""
        drive = max(raw, 1) / 10.0
        self._lbl_d_drive.setText(f"{drive:.1f}×")
        canvas = getattr(self, "_higgs_live_canvas", None)
        if canvas is None or canvas._field is None:
            return
        # Update every band's drive_amplitude live so the next frame
        # uses the new force scale.
        for swimmer, _color in canvas._swimmers.values():
            swimmer.set_drive_amplitude(drive)

    def _higgs_memory_field_receipt(self) -> None:
        """Q4 — MemoryDrivenField + swimmers experiment."""
        from System.swarm_higgs_stigmergy_field import run_memory_field_experiment
        if not self._begin_experiment("Engine D memory field"):
            return
        final_status = None
        try:
            self._btn_d_memory.setEnabled(False)
            self.set_status("Engine D running Q4 memory-driven-field experiment…")
            result = run_memory_field_experiment(
                n_swimmers=60, swimmer_steps=1000, write=True,
            )
            final_status = (
                f"Memory-field: order_param 0→{result['final_field_order_parameter']:.4f}, "
                f"mean mass {result['final_swimmer_state']['mean_mass']:.2f}. Receipt on disk."
            )
            self.set_status(final_status)
        except Exception as e:
            final_status = f"Memory-field experiment failed: {e}"
            self.set_status(final_status)
        finally:
            self._btn_d_memory.setEnabled(True)
            self._end_experiment(final_status)

    def _higgs_ghost_civ_receipt(self) -> None:
        """§21 Vector #3 — Ghost Civilizations experiment."""
        try:
            from System.swarm_higgs_stigmergy_field import (
                run_ghost_civilizations_experiment,
            )
            self._btn_d_ghost.setEnabled(False)
            self.set_status("Engine D running §21 Vector #3 ghost-civilizations…")
            result = run_ghost_civilizations_experiment(
                n_agents=40, civ_steps=600, ghost_steps=600, write=True,
            )
            im = result["inheritance_measurement"]
            self.set_status(
                f"Ghost civ done — L1={im['role_distribution_L1']:.3f}, "
                f"inheritance_observed={im['inheritance_observed']}. Receipt on disk."
            )
        except Exception as e:
            self.set_status(f"Ghost civ experiment failed: {e}")
        finally:
            self._btn_d_ghost.setEnabled(True)

    def _alice_dream_cycle_receipt(self) -> None:
        """§21 Vector #5 — Dream Organ offline replay."""
        try:
            from System.swarm_alice_dream_organ import run_dream_cycle
            self._btn_d_dream.setEnabled(False)
            self.set_status("Engine D running §21 Vector #5 dream cycle…")
            # force=True so the button always runs; production cron job
            # would call this without force and it would skip if awake.
            result = run_dream_cycle(force=True, write=True)
            kind = result.get("kind", "?")
            digest = result.get("digest_line", "")[:120]
            self.set_status(
                f"Dream cycle {kind} — {digest} Receipt on disk."
            )
        except Exception as e:
            self.set_status(f"Dream cycle failed: {e}")
        finally:
            self._btn_d_dream.setEnabled(True)

    def _civ_shocks_receipt(self) -> None:
        """Codex's civilization shock lab — 10 shocks, recovery telemetry."""
        if not self._begin_experiment("Engine D civilization shocks"):
            return
        final_status = None
        try:
            from System.swarm_civilization_shock_lab import (
                run_civilization_shock_suite,
            )
            self._btn_d_civ_shocks.setEnabled(False)
            self.set_status("Engine D running Codex's 10-shock civilization lab…")
            result = run_civilization_shock_suite(write=True)
            sm = result.get("summary", {})
            final_status = (
                f"Civ shocks done — {sm.get('recovered_count','?')}/"
                f"{sm.get('shock_count','?')} recovered, "
                f"most damaging: {sm.get('most_damaging_shock','?')}, "
                f"total STGM cost: {sm.get('total_stgm_cost','?'):.2f}. "
                f"Receipt on disk."
            )
            self.set_status(final_status)
        except Exception as e:
            final_status = f"Civilization shock lab failed: {e}"
            self.set_status(final_status)
        finally:
            self._btn_d_civ_shocks.setEnabled(True)
            self._end_experiment(final_status)

    def _higgs_temporal_phase_receipt(self) -> None:
        """§21 Vector #2 — Temporal phase transitions sweep."""
        from System.swarm_higgs_stigmergy_field import (
            run_temporal_phase_transition_sweep,
        )
        if not self._begin_experiment("Engine D temporal phase sweep"):
            return
        final_status = None
        try:
            self._btn_d_temporal.setEnabled(False)
            self.set_status("Engine D running §21 Vector #2 temporal phase sweep…")
            result = run_temporal_phase_transition_sweep(write=True)
            tau = result.get("candidate_critical_decay_tau_c")
            interior = result.get("is_interior_variance_peak")
            final_status = (
                f"Temporal phase sweep done — tau_c≈{tau}, interior peak={interior}. "
                f"Receipt on disk."
            )
            self.set_status(final_status)
        except Exception as e:
            final_status = f"Temporal phase sweep failed: {e}"
            self.set_status(final_status)
        finally:
            self._btn_d_temporal.setEnabled(True)
            self._end_experiment(final_status)

    def _higgs_collider_receipt(self) -> None:
        """Q7 — Two adaptive civilizations crash."""
        from System.swarm_higgs_stigmergy_field import run_collider_experiment
        if not self._begin_experiment("Engine D collider"):
            return
        final_status = None
        try:
            self._btn_d_collider.setEnabled(False)
            self.set_status("Engine D running Q7 collider experiment…")
            result = run_collider_experiment(
                n_per_side=40, settle_steps=600, collision_steps=1000, write=True,
            )
            me = result["mass_exchange"]
            final_status = (
                f"Collider: A→B {me['a_agents_crossed_into_b_side_final']}/40, "
                f"B→A {me['b_agents_crossed_into_a_side_final']}/40, "
                f"{result['cluster_count_after_collision']} clusters. Receipt on disk."
            )
            self.set_status(final_status)
        except Exception as e:
            final_status = f"Collider experiment failed: {e}"
            self.set_status(final_status)
        finally:
            self._btn_d_collider.setEnabled(True)
            self._end_experiment(final_status)

    def _higgs_adaptive_receipt(self) -> None:
        """Persistence Inertia Field — adaptive agent layer. Each
        agent chooses a behavior, learns from reward, roles emerge."""
        from System.swarm_higgs_stigmergy_field import (
            run_adaptive_experiment,
        )
        if not self._begin_experiment("Engine D adaptive agents"):
            return
        final_status = None
        try:
            self._btn_d_adaptive.setEnabled(False)
            self.set_status("Engine D running adaptive-policy experiment…")
            result = run_adaptive_experiment(
                n_agents=80,
                relax_steps=180,
                swarm_steps=1500,
                learning_rate=0.06,
                coupling=1.0,
                write_inertia_coefficient=0.1,
                write_inertia_kind="linear",
                write=True,
            )
            rc = result["final_role_counts"]
            ent = result["final_policy_entropy_nats"]
            roles_str = " ".join(f"{k}={v}" for k, v in rc.items())
            final_status = (
                f"Adaptive done — roles_emerged={result['roles_emerged']}, "
                f"entropy {result['initial_policy_entropy_nats']:.2f}→{ent:.3f}, "
                f"{roles_str}. Receipt on disk."
            )
            self.set_status(final_status)
        except Exception as e:
            final_status = f"Adaptive experiment failed: {e}"
            self.set_status(final_status)
        finally:
            self._btn_d_adaptive.setEnabled(True)
            self._end_experiment(final_status)

    def _higgs_symmetry_break_receipt(self) -> None:
        """Q6 — spontaneous symmetry breaking from identical swimmers.
        Runs the canonical config (crowding_competition=True,
        kind=linear, α=0.1, γ=1.5, coupling=1.0). Writes a
        HIGGS_SYMMETRY_BREAK receipt."""
        from System.swarm_higgs_stigmergy_field import (
            run_symmetry_breaking_experiment,
        )
        if not self._begin_experiment("Engine D symmetry break"):
            return
        final_status = None
        try:
            self._btn_d_symmetry.setEnabled(False)
            self.set_status("Engine D running Q6 spontaneous-symmetry-break experiment…")
            result = run_symmetry_breaking_experiment(
                n_swimmers=80,
                relax_steps=180,
                swimmer_steps=1500,
                base_write_rate=0.0,
                velocity_write_modulation=1.5,
                write_inertia_coefficient=0.1,
                write_inertia_kind="linear",
                coupling=1.0,
                crowding_competition=True,
                drive_amplitude=1.0,
                write=True,
                seed=41,
            )
            v = result["verdict"]
            fd = result["final_distribution"]
            final_status = (
                f"Symmetry break: {v['symmetry_broke']} — p95/p05={v['p95_over_p05']:.3f}, "
                f"CV={v['coefficient_of_variation']:.3f}, "
                f"mass {fd['mass_min']:.1f}→{fd['mass_max']:.1f}. Receipt on disk."
            )
            self.set_status(final_status)
        except Exception as e:
            final_status = f"Symmetry-break experiment failed: {e}"
            self.set_status(final_status)
        finally:
            self._btn_d_symmetry.setEnabled(True)
            self._end_experiment(final_status)

    def _higgs_killer_demo_receipt(self) -> None:
        """Run the §20.F Q9 killer-demo (ghost/worker/organ/sentinel)
        and write a HIGGS_KILLER_DEMO receipt. Same unified mass law
        the engine uses internally; the receipt is the proof that
        computational mass stratifies four types under the same drive."""
        from System.swarm_higgs_stigmergy_field import (
            run_killer_demo_experiment,
        )
        if not self._begin_experiment("Engine D killer demo"):
            return
        final_status = None
        try:
            self._btn_d_killer.setEnabled(False)
            self.set_status("Engine D running Q9 killer-demo experiment…")
            result = run_killer_demo_experiment(
                n_per_type=25,
                relax_steps=180,
                swimmer_steps=600,
                drive_amplitude=1.0,
                write_inertia_coefficient=0.5,
                organ_inertia_coefficient=0.25,
                write=True,
            )
            mob_spread = result.get("mobility_spread", 0.0)
            mass_spread = result.get("mass_spread", 0.0)
            visible = result.get("visible_computational_mass", False)
            final_status = (
                f"Killer demo done — mass_spread={mass_spread:.3f}, "
                f"mobility_spread={mob_spread:.4f}, visible={visible}. "
                f"Receipt on disk."
            )
            self.set_status(final_status)
        except Exception as e:
            final_status = f"Killer demo failed: {e}"
            self.set_status(final_status)
        finally:
            self._btn_d_killer.setEnabled(True)
            self._end_experiment(final_status)

    def _higgs_force_sweep_receipt(self) -> None:
        """Run the §20.F HYPOTHESIS force-regime sweep and write a receipt.
        Same code path as `run_force_regime_sweep` from the module — runs
        in ~1.5 s on a Mac and walks the drive across six regimes."""
        from System.swarm_higgs_stigmergy_field import (
            run_force_regime_sweep,
        )
        if not self._begin_experiment("Engine D force sweep"):
            return
        final_status = None
        try:
            self._btn_d_sweep.setEnabled(False)
            self.set_status("Engine D running force-regime sweep…")
            result = run_force_regime_sweep(
                drive_levels=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
                couplings=(0.0, 1.0, 4.0),
                n_per_band=25,
                relax_steps=180,
                swimmer_steps=400,
                write=True,
            )
            low = result["summary"]["lowest_drive_ratio"]
            high = result["summary"]["highest_drive_ratio"]
            collapsed = result["summary"]["ratio_collapsed_toward_one"]
            final_status = (
                f"Force sweep done — ratio {low:.3f}→{high:.3f}, "
                f"collapsed_toward_one={collapsed}. Receipt on disk."
            )
            self.set_status(final_status)
        except Exception as e:
            final_status = f"Force sweep failed: {e}"
            self.set_status(final_status)
        finally:
            self._btn_d_sweep.setEnabled(True)
            self._end_experiment(final_status)

    def _toggle_higgs_live(self) -> None:
        if getattr(self, "_higgs_live_running", False):
            self._higgs_live_running = False
            if getattr(self, "_higgs_live_timer", None):
                self._higgs_live_timer.stop()
            self._btn_d_run.setText("▶ Run")
            if hasattr(self, "_btn_stop_experiment") and not getattr(self, "_active_experiment_name", None):
                self._btn_stop_experiment.setEnabled(False)
            if hasattr(self, "_governor_label"):
                self._governor_label.setText("Ready — Engine D paused.")
            self.set_status("Engine D paused")
            return
        # Lazy-build the field on first Run.
        if self._higgs_live_canvas._field is None:
            self._higgs_live_canvas.reset()
        self._higgs_live_running = True
        if not getattr(self, "_higgs_live_timer", None):
            self._higgs_live_timer = self.make_timer(50, self._higgs_live_tick)  # 20 Hz
        self._higgs_live_timer.start()
        self._btn_d_run.setText("⏸ Pause")
        if hasattr(self, "_btn_stop_experiment"):
            self._btn_stop_experiment.setEnabled(True)
        if hasattr(self, "_governor_label"):
            self._governor_label.setText(
                "Engine D live running — switch tabs or Stop/Pause will pause it."
            )
        self.set_status("Engine D running — live Higgs/stigmergy field")

    def _higgs_live_tick(self) -> None:
        try:
            self._higgs_live_canvas.step(1)
            self._higgs_live_canvas.render()
            self._refresh_engine_d_stats()
        except Exception as e:
            print(f"[PhysicsObservatory] Engine D tick failed: {e}")
            if getattr(self, "_higgs_live_timer", None):
                self._higgs_live_timer.stop()

    def _higgs_live_step_one(self) -> None:
        if self._higgs_live_canvas._field is None:
            self._higgs_live_canvas.reset()
        self._higgs_live_canvas.step(1)
        self._higgs_live_canvas.render()
        self._refresh_engine_d_stats()

    def _higgs_live_relax_100(self) -> None:
        if not self._begin_experiment("Engine D relax 100"):
            return
        final_status = None
        try:
            if self._higgs_live_canvas._field is None:
                self._higgs_live_canvas.reset()
            self._higgs_live_canvas.step(100)
            self._higgs_live_canvas.render()
            self._refresh_engine_d_stats()
            final_status = "Engine D relaxed 100 frames. Ready."
        except Exception as e:
            final_status = f"Engine D relax failed: {e}"
            self.set_status(final_status)
        finally:
            self._end_experiment(final_status)

    def _higgs_live_reset(self) -> None:
        if getattr(self, "_higgs_live_timer", None):
            self._higgs_live_timer.stop()
        self._higgs_live_running = False
        self._btn_d_run.setText("▶ Run")
        self._higgs_live_canvas.reset()
        self._refresh_engine_d_stats()
        self.set_status("Engine D reset — new field, new swimmers")

    def _refresh_engine_d_stats(self) -> None:
        stats = self._higgs_live_canvas.latest_stats()
        if not stats:
            self._lbl_d_stats.setText("φ→— | strong/free mob ratio →—")
            return
        free_mob = stats["bands"].get("free", {}).get("mobility", 0.0)
        strong_mob = stats["bands"].get("strong", {}).get("mobility", 0.0)
        ratio = strong_mob / free_mob if free_mob > 1e-9 else 0.0
        free_m = stats["bands"].get("free", {}).get("mass", 1.0)
        weak_m = stats["bands"].get("weak", {}).get("mass", 1.0)
        strong_m = stats["bands"].get("strong", {}).get("mass", 1.0)
        self._lbl_d_stats.setText(
            f"frame {stats['frame']} | φ_order={stats['order']:.3f} "
            f"V={stats['mean_potential']:.3f} | masses "
            f"{free_m:.2f}/{weak_m:.2f}/{strong_m:.2f} | "
            f"strong/free mob = {ratio:.3f}"
        )

    def _higgs_live_write_receipt(self) -> None:
        """Run the canonical 1000-step experiment and write the receipt.
        This is the same code path as `python3 -m
        System.swarm_higgs_stigmergy_field.run_particle_higgs_experiment`,
        but invoked from the UI so the architect / an investor can see
        the receipt id appear in the status bar."""
        from System.swarm_higgs_stigmergy_field import (
            run_particle_higgs_experiment, HiggsFieldConfig,
        )
        if not self._begin_experiment("Engine D 1000-step receipt"):
            return
        final_status = None
        try:
            self._btn_d_receipt.setEnabled(False)
            self.set_status("Engine D running 1000-step experiment for receipt…")
            result = run_particle_higgs_experiment(
                couplings=(0.0, 1.0, 4.0),
                n_per_band=30,
                field_config=HiggsFieldConfig(
                    seed=13, width=24, height=16,
                ),
                relax_steps=180,
                swimmer_steps=1000,
                sample_every=200,
                write=True,
                seed=17,
            )
            ratio = result.get("final_mobility_ratio_strong_over_free")
            final_status = (
                f"Engine D receipt written — strong/free mobility = {ratio} "
                f"(see .sifta_state/higgs_stigmergy_receipts.jsonl)"
            )
            self.set_status(final_status)
        except Exception as e:
            final_status = f"Engine D receipt failed: {e}"
            self.set_status(final_status)
        finally:
            self._btn_d_receipt.setEnabled(True)
            self._end_experiment(final_status)

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
