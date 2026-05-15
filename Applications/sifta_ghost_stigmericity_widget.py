#!/usr/bin/env python3
"""sifta_ghost_stigmericity_widget.py — Ghost StigmergiCity visual demo.

Architect 2026-05-13: "Make the strongest result visible. Civilization
grows → roles emerge → agents die → field remains → newborns appear →
same roles re-emerge. Lands with regular people instantly. Researchers
inspect receipts afterward."

This app surfaces the existing §21 Vector #3 experiment
(`run_ghost_civilizations_experiment` in `swarm_higgs_stigmergy_field`)
as an ANIMATED six-phase narrative. No new backend — the math is the
same as the receipt-bound experiment that already proved L1=0.0000 on a
canonical run. This module just shows it.

Six phases:
   1. CIVILIZATION GROWS — 40 agents spawn naive in a fresh field;
      run AdaptivePolicySwarm forward; field begins to lock.
   2. ROLES EMERGE — agents commit to dominant behaviors via softmax
      policy collapse; dots take their role colour.
   3. AGENTS DIE — animated fade-out of all dots over a few frames;
      field stays untouched.
   4. FIELD REMAINS — empty colormap with a phrase overlay: "The dead
      civilization's field remains."
   5. NEWBORNS APPEAR — 40 naive agents spawn into the inherited
      field; uniform-policy white dots.
   6. SAME ROLES RE-EMERGE — newborns commit, colours converge to the
      same distribution; the L1=0.0000 measurement appears.

Truth class: HYPOTHESIS for the experimental finding (the underlying
function already mints HYPOTHESIS receipts). OPERATIONAL for the
visualisation.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from System.swarm_higgs_stigmergy_field import (
    AdaptivePolicySwarm,
    HiggsFieldConfig,
    HiggsStigmergyField,
    phi_as_array,
)


# ── Visual palette ────────────────────────────────────────────────────────
BG = "#060810"
TEAL = "#00ffc8"
GOLD = "#ffcc44"
DIM = "#4a5570"
ROLE_COLORS = {
    "wander":  "#b76eff",   # violet — exploration
    "chase":   "#ffd54a",   # gold — scout
    "deposit": "#4ee0a8",   # teal — sentinel
    "flee":    "#ff5c5c",   # red — escape
}


# ── Phase script ──────────────────────────────────────────────────────────
#
# Each phase carries (name, sim_steps_total, banner_text, allow_step_field,
# allow_step_swimmers).
# The animator walks through phases in order. Each frame may advance the
# field, the swimmers, or just hold the current state for a dramatic beat.


PHASES = [
    {
        "id": 1,
        "name": "Civilization grows",
        "frames": 400,
        "banner": (
            "Phase 1 / 6 — Civilization grows.\n"
            "40 naive agents arrive on an empty field. They drift, "
            "they write, they begin to learn."
        ),
        "step_field": True,
        "step_swimmers": True,
        "phase": "civ_grow",
    },
    {
        "id": 2,
        "name": "Roles emerge",
        "frames": 30,
        "banner": (
            "Phase 2 / 6 — Roles emerge.\n"
            "Policy entropy collapses. Each agent commits to a "
            "behavior. Chasers, depositors, ghosts."
        ),
        "step_field": False,
        "step_swimmers": False,
        "phase": "civ_pause",
    },
    {
        "id": 3,
        "name": "Agents die",
        "frames": 30,
        "banner": (
            "Phase 3 / 6 — Agents die.\n"
            "Every agent is deleted. The body is gone."
        ),
        "step_field": False,
        "step_swimmers": False,
        "phase": "agents_fading",
    },
    {
        "id": 4,
        "name": "Field remains",
        "frames": 60,
        "banner": (
            "Phase 4 / 6 — The field remains.\n"
            "Their traces persist in φ(x,y). The substrate is "
            "still locked to what they built."
        ),
        "step_field": False,
        "step_swimmers": False,
        "phase": "field_only",
    },
    {
        "id": 5,
        "name": "Newborns appear",
        "frames": 30,
        "banner": (
            "Phase 5 / 6 — Newborns appear.\n"
            "40 naive agents spawn into the inherited field. "
            "Uniform white policies. No memory of who came before."
        ),
        "step_field": False,
        "step_swimmers": False,
        "phase": "newborns_spawn",
    },
    {
        "id": 6,
        "name": "Same roles re-emerge",
        "frames": 400,
        "banner": (
            "Phase 6 / 6 — Same roles re-emerge.\n"
            "The field teaches them. Without ever meeting their "
            "predecessors, they commit to the same functional roles."
        ),
        "step_field": True,
        "step_swimmers": True,
        "phase": "ghost_growing",
    },
]


# ── Matplotlib canvas ─────────────────────────────────────────────────────

class _GhostCanvas(FigureCanvas):
    """Animated field + dots."""

    FIELD_SHAPE = (24, 36)
    N_AGENTS = 40

    def __init__(self, parent: Optional[QWidget] = None):
        self._fig = Figure(figsize=(11, 6), facecolor=BG, dpi=92)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setMinimumSize(620, 360)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        gs = self._fig.add_gridspec(
            2, 1, hspace=0.10,
            left=0.03, right=0.97, top=0.95, bottom=0.05,
            height_ratios=[5, 1],
        )
        self._ax_field = self._fig.add_subplot(gs[0])
        self._ax_strip = self._fig.add_subplot(gs[1])
        for ax in (self._ax_field, self._ax_strip):
            ax.set_facecolor(BG)
            ax.tick_params(colors=DIM, labelsize=7)
            for sp in ax.spines.values():
                sp.set_color(DIM)
        self._field: Optional[HiggsStigmergyField] = None
        self._civ: Optional[AdaptivePolicySwarm] = None
        self._ghost: Optional[AdaptivePolicySwarm] = None
        self._dots_alpha = 1.0           # fade-out tracker for phase 3
        self._snapshot_civ_roles: dict[str, int] = {}
        self._snapshot_civ_entropy = float("nan")
        self._init_simulation()

    def _init_simulation(self):
        h, w = self.FIELD_SHAPE
        cfg = HiggsFieldConfig(seed=89, width=w, height=h)
        self._field = HiggsStigmergyField(cfg)
        self._field.relax(180)
        self._civ = AdaptivePolicySwarm(
            n=self.N_AGENTS, field_shape=(h, w), seed=89,
            coupling=1.0, learning_rate=0.06,
            write_inertia_coefficient=0.1, write_inertia_kind="linear",
        )
        self._ghost = None
        self._dots_alpha = 1.0
        self._snapshot_civ_roles = {}

    def reset(self):
        self._init_simulation()
        self.render(phase="civ_grow", banner_text="Reset — press Run to start the demo.")

    # ── Per-frame state advance ──────────────────────────────────────
    def step_civilization(self):
        if self._field is None or self._civ is None:
            return
        self._field.step()
        self._civ.step(phi_as_array(self._field))

    def snapshot_and_kill_agents(self):
        """End of phase 2 / start of phase 3 transition. Record what
        the civilization became, then prepare for the fade-out."""
        if self._civ is None:
            return
        self._snapshot_civ_roles = dict(self._civ.role_counts())
        self._snapshot_civ_entropy = float(self._civ.policy_entropy())
        # Agents fade out by alpha; the dots class still holds them so
        # the colormap is unaffected.

    def fade_agents(self, frac_done: float):
        """Phase 3 — alpha goes from 1.0 to 0.0 as frac_done goes 0→1."""
        self._dots_alpha = max(0.0, 1.0 - frac_done)

    def clear_agents_after_fade(self):
        """End of phase 3: the dots are visually gone. Clear the
        swimmer instance so phase 4 paints only the field."""
        self._civ = None
        self._dots_alpha = 0.0

    def spawn_newborns(self):
        """Phase 5: spawn naive newborns into the field."""
        h, w = self.FIELD_SHAPE
        if self._field is None:
            return
        self._ghost = AdaptivePolicySwarm(
            n=self.N_AGENTS, field_shape=(h, w),
            seed=89 + 7919,  # different RNG → different positions
            coupling=1.0, learning_rate=0.06,
            write_inertia_coefficient=0.1, write_inertia_kind="linear",
        )

    def step_newborns(self):
        if self._field is None or self._ghost is None:
            return
        self._field.step()
        self._ghost.step(phi_as_array(self._field))

    def latest_stats(self, phase: str) -> dict:
        out: dict = {"phase": phase}
        if self._field is not None:
            out["order_param"] = round(float(self._field.order_parameter), 4)
        if self._civ is not None:
            out["civ_roles"] = dict(self._civ.role_counts())
            out["civ_entropy"] = round(self._civ.policy_entropy(), 3)
            out["civ_mass"] = round(float(self._civ.mass.mean()), 2)
        if self._ghost is not None:
            out["ghost_roles"] = dict(self._ghost.role_counts())
            out["ghost_entropy"] = round(self._ghost.policy_entropy(), 3)
            out["ghost_mass"] = round(float(self._ghost.mass.mean()), 2)
            if self._snapshot_civ_roles:
                # Earth-mover-like L1 between fractions
                def _frac(d):
                    total = max(sum(d.values()), 1)
                    return {k: v / total for k, v in d.items()}
                fa = _frac(self._snapshot_civ_roles)
                fb = _frac(out["ghost_roles"])
                keys = set(fa) | set(fb)
                L1 = sum(abs(fa.get(k, 0) - fb.get(k, 0)) for k in keys)
                out["L1_to_dead_civ"] = round(L1, 4)
        return out

    # ── Render ──────────────────────────────────────────────────────
    def render(self, *, phase: str, banner_text: str):
        if self._field is None:
            return
        phi = phi_as_array(self._field)
        h, w = phi.shape

        ax = self._ax_field
        ax.clear(); ax.set_facecolor(BG)
        vmax = max(abs(phi).max(), 0.05)
        ax.imshow(
            phi, cmap="RdBu_r", origin="lower", aspect="auto",
            vmin=-vmax, vmax=vmax, interpolation="bilinear",
            extent=(0, w, 0, h),
        )
        # Original civ dots — visible in phases 1-3 (fading in phase 3).
        if self._civ is not None and self._dots_alpha > 0.01:
            dominant = self._civ.dominant_behavior_index()
            for k, behavior in enumerate(("wander", "chase", "deposit", "flee")):
                mask = dominant == k
                if not mask.any():
                    continue
                # In phase 1 early, policies are uniform → render white.
                # Once entropy drops below 0.5 we trust the dominant idx.
                ax.scatter(
                    self._civ.pos[mask, 0], self._civ.pos[mask, 1],
                    s=18 + 18 * (self._civ.mass[mask] - 1.0) / max(self._civ.mass.max(), 1.0),
                    c=ROLE_COLORS[behavior],
                    edgecolor="#0a0e16", linewidth=0.4,
                    alpha=self._dots_alpha,
                )
        # Newborn dots — visible in phase 5-6.
        if self._ghost is not None:
            dominant = self._ghost.dominant_behavior_index()
            # In phase 5 (spawn), entropy is still high → draw all white.
            # In phase 6 they take their role colors as they commit.
            entropy = self._ghost.policy_entropy()
            for k, behavior in enumerate(("wander", "chase", "deposit", "flee")):
                mask = dominant == k
                if not mask.any():
                    continue
                # Color blends from white → role color as entropy drops.
                fade = max(0.0, min(1.0, (1.386 - entropy) / 1.386))
                role_color = ROLE_COLORS[behavior]
                # blend
                def _hex_to_rgb(s): return tuple(int(s[i:i+2], 16) for i in (1, 3, 5))
                def _rgb_to_hex(r,g,b): return f"#{r:02x}{g:02x}{b:02x}"
                wr, wg, wb = 255, 255, 255
                rr, rg, rb = _hex_to_rgb(role_color)
                br = int(wr + fade * (rr - wr))
                bg = int(wg + fade * (rg - wg))
                bb = int(wb + fade * (rb - wb))
                blended = _rgb_to_hex(br, bg, bb)
                ax.scatter(
                    self._ghost.pos[mask, 0], self._ghost.pos[mask, 1],
                    s=18 + 18 * (self._ghost.mass[mask] - 1.0) / max(self._ghost.mass.max(), 1.0),
                    c=blended,
                    edgecolor="#0a0e16", linewidth=0.4,
                    alpha=0.95,
                )
        # Phase 4 — empty field + dramatic text overlay
        if phase == "field_only":
            ax.text(
                w / 2, h / 2, "The dead civilization's field remains.",
                color=GOLD, fontsize=14, ha="center", va="center",
                fontfamily="monospace", fontweight="bold",
            )
        ax.set_xlim(0, w); ax.set_ylim(0, h)
        ax.set_xticks([]); ax.set_yticks([])
        # banner header
        first_line = banner_text.split("\n", 1)[0]
        rest = banner_text.split("\n", 1)[1] if "\n" in banner_text else ""
        ax.set_title(
            first_line, color=TEAL, fontsize=12, fontfamily="monospace",
            pad=6, loc="left",
        )
        # Subtitle under the title
        ax.text(
            0.01, 1.005, rest, transform=ax.transAxes, color=DIM,
            fontsize=9, fontfamily="monospace", va="bottom",
        )

        # ── Bottom strip: role-count bars per civilization ─────────
        ax2 = self._ax_strip
        ax2.clear(); ax2.set_facecolor(BG)
        ax2.set_xticks([]); ax2.set_yticks([])
        # left half = original civ; right half = newborns
        roles = ("wander", "chase", "deposit", "flee")
        bar_w = 0.18

        # Original civ bars (using snapshot if alive_civ gone, else live)
        civ_roles = (
            self._civ.role_counts() if self._civ is not None
            else self._snapshot_civ_roles or {r: 0 for r in roles}
        )
        for i, r in enumerate(roles):
            ax2.bar(
                0.05 + i * (bar_w + 0.01), civ_roles.get(r, 0),
                width=bar_w, color=ROLE_COLORS[r], edgecolor="#0a0e16",
                alpha=self._dots_alpha if self._civ is not None else 0.5,
            )

        # Newborn bars
        if self._ghost is not None:
            ghost_roles = self._ghost.role_counts()
            for i, r in enumerate(roles):
                ax2.bar(
                    0.55 + i * (bar_w + 0.01), ghost_roles.get(r, 0),
                    width=bar_w, color=ROLE_COLORS[r], edgecolor="#0a0e16",
                    alpha=0.95,
                )

        ax2.set_xlim(0, 1.05)
        ax2.set_ylim(0, max(self.N_AGENTS, 1))
        ax2.text(0.02, self.N_AGENTS * 0.95, "ORIGINAL CIVILIZATION",
                 color=DIM, fontsize=8, fontfamily="monospace")
        ax2.text(0.52, self.N_AGENTS * 0.95, "GHOST NEWBORNS",
                 color=DIM, fontsize=8, fontfamily="monospace")

        self._fig.canvas.draw_idle()


# ── Main widget ───────────────────────────────────────────────────────────

class GhostStigmericityApp(SiftaBaseWidget):
    APP_NAME = "Ghost StigmergiCity"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Truth-label banner ───────────────────────────────────────
        banner = QLabel(
            "ARCHITECT_DOCTRINE / HYPOTHESIS — Classical SIFTA computational-"
            "ecology analogue. No claim about real biology or particle physics. "
            "The strongest result the lab has so far, made visible."
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            f"background: #2a2410; color: {GOLD}; font-family: Menlo; "
            f"font-size: 10px; font-weight: 700; padding: 6px 8px; "
            f"border: 1px solid #5a4820; border-radius: 4px;"
        )
        layout.addWidget(banner)

        # ── Controls row ─────────────────────────────────────────────
        controls = QHBoxLayout()
        self._btn_run = QPushButton("▶ Run")
        self._btn_run.clicked.connect(self._toggle_run)
        controls.addWidget(self._btn_run)
        self._btn_reset = QPushButton("↺ Reset")
        self._btn_reset.clicked.connect(self._reset)
        controls.addWidget(self._btn_reset)

        controls.addWidget(self._sep())
        controls.addWidget(QLabel("Speed:"))
        self._sld_speed = QSlider(Qt.Orientation.Horizontal)
        self._sld_speed.setRange(1, 8)
        self._sld_speed.setValue(2)
        self._sld_speed.setFixedWidth(120)
        self._sld_speed.valueChanged.connect(self._on_speed_change)
        controls.addWidget(self._sld_speed)
        self._lbl_speed = QLabel("2x")
        self._lbl_speed.setStyleSheet(f"color: {GOLD}; font-family: Menlo;")
        controls.addWidget(self._lbl_speed)

        controls.addWidget(self._sep())
        self._lbl_status = QLabel(
            "Press Run. Six phases: civ grows → roles emerge → agents die "
            "→ field remains → newborns appear → same roles re-emerge."
        )
        self._lbl_status.setStyleSheet(
            f"color: {TEAL}; font-family: Menlo; font-size: 10px;"
        )
        controls.addWidget(self._lbl_status, 1)
        layout.addLayout(controls)

        # ── Canvas ──────────────────────────────────────────────────
        self._canvas = _GhostCanvas()
        layout.addWidget(self._canvas, 1)

        # ── Stats strip ─────────────────────────────────────────────
        self._lbl_stats = QLabel(
            "frame 0   |   waiting for Run"
        )
        self._lbl_stats.setStyleSheet(
            f"color: {DIM}; font-family: Menlo; font-size: 10px;"
        )
        layout.addWidget(self._lbl_stats)

        # ── State + timer ───────────────────────────────────────────
        self._frame = 0
        self._phase_idx = 0
        self._phase_frame = 0
        self._running = False
        self._sim_steps_per_frame = 2  # 2× speed slider default
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        # First paint so the canvas shows something on open.
        self._canvas.render(
            phase="civ_grow",
            banner_text=PHASES[0]["banner"],
        )

    def _sep(self) -> QWidget:
        s = QFrame()
        s.setFrameShape(QFrame.Shape.VLine)
        s.setStyleSheet("color: #1a1f2c;")
        return s

    def _toggle_run(self) -> None:
        if self._running:
            self._timer.stop()
            self._running = False
            self._btn_run.setText("▶ Run")
            self._lbl_status.setText("Paused.")
            return
        self._running = True
        self._btn_run.setText("⏸ Pause")
        self._timer.start(50)  # 20 Hz display

    def _reset(self) -> None:
        self._timer.stop()
        self._running = False
        self._btn_run.setText("▶ Run")
        self._frame = 0
        self._phase_idx = 0
        self._phase_frame = 0
        self._canvas.reset()
        self._lbl_status.setText(
            "Reset — six phases queued. Press Run to start."
        )
        self._lbl_stats.setText("frame 0   |   waiting for Run")

    def _on_speed_change(self, raw: int) -> None:
        self._sim_steps_per_frame = max(1, int(raw))
        self._lbl_speed.setText(f"{raw}x")

    def _tick(self) -> None:
        if self._phase_idx >= len(PHASES):
            self._timer.stop()
            self._running = False
            self._btn_run.setText("▶ Run")
            self._lbl_status.setText(
                "Demo complete. Hit Reset to run again. "
                "Receipt-bound experiment lives in run_ghost_civilizations_experiment."
            )
            return

        phase = PHASES[self._phase_idx]
        # Phase transitions: snapshot at end of phase 2, kill at end of
        # phase 3, spawn at start of phase 5.
        if self._phase_frame == 0:
            self._on_enter_phase(phase)
            self._lbl_status.setText(phase["banner"].split("\n")[0])

        # Advance the simulation per the phase's step flags.
        if phase["step_field"] and phase["step_swimmers"]:
            for _ in range(self._sim_steps_per_frame):
                if phase["phase"] == "civ_grow":
                    self._canvas.step_civilization()
                elif phase["phase"] == "ghost_growing":
                    self._canvas.step_newborns()
        elif phase["phase"] == "agents_fading":
            frac = (self._phase_frame + 1) / max(phase["frames"], 1)
            self._canvas.fade_agents(frac)

        # Render this frame.
        self._canvas.render(
            phase=phase["phase"],
            banner_text=phase["banner"],
        )

        # Update the stats strip.
        stats = self._canvas.latest_stats(phase["phase"])
        bits = [f"phase {phase['id']}/6", f"frame {self._frame}"]
        if "order_param" in stats:
            bits.append(f"φ_order={stats['order_param']}")
        if "civ_entropy" in stats:
            bits.append(f"civ_entropy={stats['civ_entropy']}")
        if "ghost_entropy" in stats:
            bits.append(f"ghost_entropy={stats['ghost_entropy']}")
        if "L1_to_dead_civ" in stats:
            bits.append(f"L1_newborn_vs_dead_civ={stats['L1_to_dead_civ']}")
        self._lbl_stats.setText("  |  ".join(bits))

        self._phase_frame += 1
        self._frame += 1
        if self._phase_frame >= phase["frames"]:
            self._on_exit_phase(phase)
            self._phase_idx += 1
            self._phase_frame = 0

    def _on_enter_phase(self, phase: dict) -> None:
        if phase["phase"] == "newborns_spawn":
            self._canvas.spawn_newborns()

    def _on_exit_phase(self, phase: dict) -> None:
        if phase["phase"] == "civ_pause":
            # End of phase 2 — record snapshot of the original civ.
            self._canvas.snapshot_and_kill_agents()
        elif phase["phase"] == "agents_fading":
            # End of phase 3 — drop the swimmer instance.
            self._canvas.clear_agents_after_fade()


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = GhostStigmericityApp()
    w.resize(1100, 720)
    w.setWindowTitle("Ghost StigmergiCity — SIFTA OS")
    w.show()
    sys.exit(app.exec())
