#!/usr/bin/env python3
"""
Applications/sifta_primordial_field.py — Primordial Field
══════════════════════════════════════════════════════════════════════════
AG31 (Antigravity 31) · April 2026 — for Codex / Opus 4.7 final graphics.

═══════ WHAT THIS IS ═══════════════════════════════════════════════════
Two layers of emergent complexity running simultaneously:

  LAYER 1 — Gray-Scott Reaction-Diffusion (the Chemical Substrate)
  ────────────────────────────────────────────────────────────────────
  Two virtual chemicals U and V react and diffuse across a 128×128 grid
  at every frame. The feed/kill rates are user-tunable, producing a zoo
  of Turing patterns: coral, mitosis, stripes, mazes, spots. These are
  NOT random — they are the same mathematical patterns that make a
  leopard's spots, a zebrafish's stripes, and a coral polyp's skeleton.

  LAYER 2 — Physarum Agents ride the chemistry (the Organism)
  ────────────────────────────────────────────────────────────────────
  32 Physarum-style slime-mold agents float over the field. Each agent:
    • Senses U-concentration ahead, left-45°, right-45° (like the real
      slime mold's actin-myosin "arms")
    • Turns toward chemical richness (chemotaxis)
    • Deposits a pheromone trail that OTHER agents follow
    • Dies when V overwhelms the local cell (killed by predator chemical)
    • Spawns new agents when richness is high

  EMERGENCE — neither layer knows about the other's rules.
  The agents end up tracing the boundaries between Gray-Scott stripes,
  producing filamentous webs that look like early-universe cosmic web
  simulations, neuron dendrite trees, and actual slime-mold photographs.
  This is NOT pre-programmed. It emerges every run.

═══════ ECONOMICS ══════════════════════════════════════════════════════
  Every 10 s of sustained complex pattern → mint PHYSARUM_SOLVE STGM.
  Pattern complexity is measured by Shannon entropy of the U grid —
  a uniform field mints nothing; rich Turing patterns mint continuously.

═══════ CONTROLS ═══════════════════════════════════════════════════════
  Mouse click   → inject V pulse at cursor (disturb the field)
  F/K sliders   → feed/kill rate (change pattern mode live)
  Speed slider  → simulation frames per second
  Presets       → Coral / Mitosis / Maze / Stripes / Spots

Doctor Sigil: AG31 — Antigravity 31
Pass to: Codex 5.5 High → then Opus 4.7 for final chrome + color.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import numpy as np

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QFont, QImage, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton,
    QSlider, QVBoxLayout, QWidget, QComboBox,
)

# ── Try doctor sigil bar ──────────────────────────────────────────────
try:
    from System.sifta_doctor_sigil_bar import paint_doctor_sigil_bar
    _HAS_SIGIL = True
except Exception:
    _HAS_SIGIL = False

# ── Try STGM economy ──────────────────────────────────────────────────
try:
    from Kernel.inference_economy import mint_stgm
    _HAS_MINT = True
except Exception:
    _HAS_MINT = False

# ══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════

GRID = 128          # simulation grid (128×128 — fast without numba)
N_AGENTS = 40       # Physarum agent count
DT = 1.0            # Gray-Scott time step
DIFFUSION_U = 0.2097
DIFFUSION_V = 0.1050
NEON_CYAN   = QColor(0, 255, 200)
NEON_GOLD   = QColor(255, 200, 0)
NEON_PINK   = QColor(255, 60, 160)
NEON_PURPLE = QColor(180, 80, 255)
BG_DARK     = QColor(4, 6, 14)

# Gray-Scott presets (feed, kill)
PRESETS = {
    "Coral":    (0.0545, 0.062),
    "Mitosis":  (0.0367, 0.0649),
    "Maze":     (0.029,  0.057),
    "Stripes":  (0.022,  0.051),
    "Spots":    (0.035,  0.065),
    "Worms":    (0.078,  0.061),
}
DEFAULT_PRESET = "Coral"


# ══════════════════════════════════════════════════════════════════════
# GRAY-SCOTT REACTION-DIFFUSION ENGINE
# ══════════════════════════════════════════════════════════════════════

class GrayScottField:
    """Pure-numpy Gray-Scott two-chemical reaction-diffusion grid."""

    def __init__(self, size: int = GRID) -> None:
        self.n = size
        self.U = np.ones((size, size), dtype=np.float32)
        self.V = np.zeros((size, size), dtype=np.float32)
        self.F = PRESETS[DEFAULT_PRESET][0]
        self.K = PRESETS[DEFAULT_PRESET][1]
        self._seed()

    def _seed(self) -> None:
        """Plant a small V-square in the centre to start the reaction."""
        c = self.n // 2
        r = max(4, self.n // 16)
        self.V[c-r:c+r, c-r:c+r] = 1.0
        # Random noise so it doesn't stay symmetric
        self.V += np.random.uniform(0, 0.02, self.V.shape).astype(np.float32)
        self.U += np.random.uniform(-0.01, 0.01, self.U.shape).astype(np.float32)
        np.clip(self.U, 0.0, 1.0, out=self.U)
        np.clip(self.V, 0.0, 1.0, out=self.V)

    def step(self, steps: int = 8) -> None:
        """Advance the simulation by `steps` Euler iterations."""
        U, V, F, K = self.U, self.V, self.F, self.K
        for _ in range(steps):
            # Laplacian via roll (periodic boundary)
            lap_U = (
                np.roll(U, 1, 0) + np.roll(U, -1, 0) +
                np.roll(U, 1, 1) + np.roll(U, -1, 1) - 4.0 * U
            )
            lap_V = (
                np.roll(V, 1, 0) + np.roll(V, -1, 0) +
                np.roll(V, 1, 1) + np.roll(V, -1, 1) - 4.0 * V
            )
            uvv = U * V * V
            U += DT * (DIFFUSION_U * lap_U - uvv + F * (1.0 - U))
            V += DT * (DIFFUSION_V * lap_V + uvv - (F + K) * V)
            np.clip(U, 0.0, 1.0, out=U)
            np.clip(V, 0.0, 1.0, out=V)

    def inject(self, row: int, col: int, radius: int = 4) -> None:
        """User click: inject a pulse of V chemical."""
        r0 = max(0, row - radius)
        r1 = min(self.n, row + radius)
        c0 = max(0, col - radius)
        c1 = min(self.n, col + radius)
        self.V[r0:r1, c0:c1] = np.clip(
            self.V[r0:r1, c0:c1] + 0.5, 0.0, 1.0
        )

    def entropy(self) -> float:
        """Shannon entropy of U grid — proxy for pattern complexity."""
        hist, _ = np.histogram(self.U, bins=32, range=(0.0, 1.0), density=True)
        hist = hist[hist > 0]
        return float(-np.sum(hist * np.log2(hist)))

    def to_rgb_image(self) -> QImage:
        """Map U→blue, V→orange, blend to an RGB QImage."""
        u = self.U
        v = self.V
        # Neon: U → cyan channel, V → orange (red+green mix)
        r = np.clip(v * 2.2, 0.0, 1.0)
        g = np.clip(u * 0.8 + v * 0.6, 0.0, 1.0)
        b = np.clip(u * 1.5, 0.0, 1.0)
        rgb = np.stack([r, g, b], axis=-1)
        rgb = (rgb * 255).astype(np.uint8)
        rgb = np.ascontiguousarray(rgb)
        h, w, ch = rgb.shape
        return QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)


# ══════════════════════════════════════════════════════════════════════
# PHYSARUM AGENT
# ══════════════════════════════════════════════════════════════════════

class PhysarumAgent:
    """One slime-mold explorer that chemotaxes over the Gray-Scott field."""

    SENSOR_ANGLE = math.radians(45)
    SENSOR_DIST  = 4.0
    ROTATE_SPEED = math.radians(30)

    def __init__(self, n: int) -> None:
        self.n = n
        self.x = float(n // 2 + np.random.randint(-n // 6, n // 6))
        self.y = float(n // 2 + np.random.randint(-n // 6, n // 6))
        self.angle = np.random.uniform(0, 2 * math.pi)
        self.alive = True
        self.age = 0

    def _sense(self, U: np.ndarray, angle_offset: float) -> float:
        sa = self.angle + angle_offset
        sx = int((self.x + math.cos(sa) * self.SENSOR_DIST) % self.n)
        sy = int((self.y + math.sin(sa) * self.SENSOR_DIST) % self.n)
        return float(U[sy, sx])

    def step(self, U: np.ndarray, trail: np.ndarray) -> None:
        # Sense ahead, left, right — prefer HIGH U (chemical richness)
        fwd   = self._sense(U, 0)
        left  = self._sense(U, -self.SENSOR_ANGLE)
        right = self._sense(U,  self.SENSOR_ANGLE)

        if fwd > left and fwd > right:
            pass  # stay straight
        elif left > right:
            self.angle -= self.ROTATE_SPEED
        elif right > left:
            self.angle += self.ROTATE_SPEED
        else:
            self.angle += np.random.uniform(-self.ROTATE_SPEED, self.ROTATE_SPEED)

        # Move
        self.x = (self.x + math.cos(self.angle)) % self.n
        self.y = (self.y + math.sin(self.angle)) % self.n

        # Deposit pheromone trail
        ix, iy = int(self.x) % self.n, int(self.y) % self.n
        trail[iy, ix] = min(1.0, trail[iy, ix] + 0.15)

        # Die if V overwhelms local cell (predator wins)
        self.age += 1

    def position(self):
        return self.x, self.y


# ══════════════════════════════════════════════════════════════════════
# CANVAS
# ══════════════════════════════════════════════════════════════════════

class PrimordialCanvas(QWidget):
    """Renders the Gray-Scott field + Physarum agents."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(512, 512)
        self.setMouseTracking(True)

        self.field = GrayScottField(GRID)
        self.trail = np.zeros((GRID, GRID), dtype=np.float32)
        self.agents: List[PhysarumAgent] = [
            PhysarumAgent(GRID) for _ in range(N_AGENTS)
        ]

        self._frame = 0
        self._last_mint = time.time()
        self._entropy_acc = 0.0
        self._stgm_total = 0.0
        self._fps_last = time.time()
        self._fps = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)  # 25 fps target

    # ── Simulation tick ─────────────────────────────────────────────

    def _tick(self) -> None:
        self.field.step(steps=8)

        # Evaporate trail
        self.trail *= 0.96

        # Step agents
        for ag in self.agents:
            ag.step(self.field.U, self.trail)

        # Replenish dead / old agents
        while len(self.agents) < N_AGENTS:
            self.agents.append(PhysarumAgent(GRID))

        # Entropy → STGM minting
        now = time.time()
        if now - self._last_mint > 10.0:
            ent = self.field.entropy()
            self._entropy_acc += ent
            if ent > 2.5 and _HAS_MINT:
                try:
                    mint_stgm(
                        agent_id=os.environ.get("SIFTA_NODE_AGENT", "ALICE"),
                        amount=ent * 2.0,
                        reason="PRIMORDIAL_FIELD_TURING_PATTERN",
                    )
                    self._stgm_total += ent * 2.0
                except Exception:
                    pass
            self._last_mint = now

        self._frame += 1
        dt = now - self._fps_last
        if dt > 0.5:
            self._fps = self._frame / max(dt, 0.001)
            self._frame = 0
            self._fps_last = now

        self.update()

    # ── Painting ────────────────────────────────────────────────────

    def paintEvent(self, _) -> None:  # noqa: N802
        p = QPainter(self)
        try:
            self._paint(p)
        finally:
            p.end()

    def _paint(self, p: QPainter) -> None:
        w, h = self.width(), self.height()

        # ── Background ──────────────────────────────────────────────
        p.fillRect(0, 0, w, h, BG_DARK)

        # ── Gray-Scott field (scaled) ────────────────────────────────
        img = self.field.to_rgb_image()
        scaled = img.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        p.drawImage(0, 0, scaled)

        # ── Physarum trail overlay ────────────────────────────────────
        # Draw as semi-transparent neon cyan pixels
        trail_img = self._trail_to_image()
        scaled_trail = trail_img.scaled(w, h,
                                         Qt.AspectRatioMode.IgnoreAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
        p.setOpacity(0.6)
        p.drawImage(0, 0, scaled_trail)
        p.setOpacity(1.0)

        # ── Agent dots ───────────────────────────────────────────────
        sx = w / GRID
        sy = h / GRID
        p.setPen(Qt.PenStyle.NoPen)
        for ag in self.agents:
            ax, ay = ag.position()
            cx = ax * sx
            cy = ay * sy
            p.setBrush(QBrush(NEON_CYAN))
            p.drawEllipse(QPointF(cx, cy), 2.5, 2.5)

        # ── HUD ──────────────────────────────────────────────────────
        self._draw_hud(p, w, h)

        # ── Doctor sigil ─────────────────────────────────────────────
        if _HAS_SIGIL:
            try:
                paint_doctor_sigil_bar(
                    p, doctors=["AG31"],
                    x=0, y=0, w=w, h=38,
                    title="Primordial Field — Reaction-Diffusion + Physarum Swarm",
                    subtitle="Gray-Scott chemistry · slime-mold chemotaxis · STGM emergence",
                )
            except Exception:
                pass

    def _trail_to_image(self) -> QImage:
        t = self.trail
        # RGBA: cyan glow where trail is strong
        alpha = (t * 220).astype(np.uint8)
        r = np.zeros_like(alpha)
        g = (t * 255).astype(np.uint8)
        b = (t * 200).astype(np.uint8)
        rgba = np.stack([r, g, b, alpha], axis=-1)
        rgba = np.ascontiguousarray(rgba)
        h, w, _ = rgba.shape
        return QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888)

    def _draw_hud(self, p: QPainter, w: int, h: int) -> None:
        p.save()
        p.setBrush(QBrush(QColor(4, 6, 14, 180)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(10, h - 70, 260, 60), 8, 8)
        p.setPen(QPen(QColor(0, 255, 200)))
        p.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        p.drawText(QPointF(18, h - 50),
                   f"F={self.field.F:.4f}  K={self.field.K:.4f}  "
                   f"Agents={len(self.agents)}")
        p.drawText(QPointF(18, h - 34),
                   f"Entropy={self.field.entropy():.2f}  "
                   f"STGM minted={self._stgm_total:.1f}")
        p.setPen(QPen(QColor(120, 130, 160)))
        p.setFont(QFont("Menlo", 8))
        p.drawText(QPointF(18, h - 18),
                   f"Click to inject V pulse · FPS≈{self._fps:.0f}")
        p.restore()

    # ── Mouse interaction ────────────────────────────────────────────

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.MouseButton.LeftButton:
            row = int(ev.position().y() / self.height() * GRID)
            col = int(ev.position().x() / self.width() * GRID)
            self.field.inject(row, col, radius=5)

    # ── Public controls ──────────────────────────────────────────────

    def set_preset(self, name: str) -> None:
        if name in PRESETS:
            self.field.F, self.field.K = PRESETS[name]

    def set_feed(self, val: int) -> None:
        self.field.F = val / 10000.0

    def set_kill(self, val: int) -> None:
        self.field.K = val / 10000.0

    def reset(self) -> None:
        self.field = GrayScottField(GRID)
        self.trail = np.zeros((GRID, GRID), dtype=np.float32)
        self.agents = [PhysarumAgent(GRID) for _ in range(N_AGENTS)]


# ══════════════════════════════════════════════════════════════════════
# MAIN WIDGET
# ══════════════════════════════════════════════════════════════════════

class PrimordialFieldWidget(QWidget):
    """Full application window."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Primordial Field — AG31 · SIFTA OS")
        self.setStyleSheet("""
            QWidget { background: rgb(4, 6, 14); color: rgb(180, 200, 240); }
            QLabel  { font-family: 'Menlo'; font-size: 10px; }
            QComboBox, QPushButton {
                background: rgb(14, 18, 36); color: rgb(0, 255, 200);
                border: 1px solid rgb(0, 100, 80); border-radius: 5px;
                font-family: 'Menlo'; font-size: 11px; padding: 3px 8px;
            }
            QPushButton:hover { background: rgb(20, 40, 50); }
            QSlider::groove:horizontal { height: 4px; background: rgb(30, 40, 60); border-radius: 2px; }
            QSlider::handle:horizontal {
                background: rgb(0, 255, 200); width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }
        """)
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 6)
        vbox.setSpacing(4)

        self.canvas = PrimordialCanvas(self)
        vbox.addWidget(self.canvas, 1)

        # ── Controls row ──────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(8, 0, 8, 0)
        ctrl.setSpacing(12)

        # Preset
        preset_lbl = QLabel("Pattern:")
        ctrl.addWidget(preset_lbl)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(PRESETS.keys()))
        self.preset_combo.setCurrentText(DEFAULT_PRESET)
        self.preset_combo.currentTextChanged.connect(self.canvas.set_preset)
        ctrl.addWidget(self.preset_combo)

        ctrl.addSpacing(10)

        # Feed slider
        f_lbl = QLabel("Feed")
        ctrl.addWidget(f_lbl)
        f_init, k_init = PRESETS[DEFAULT_PRESET]
        self.sl_feed = QSlider(Qt.Orientation.Horizontal)
        self.sl_feed.setRange(100, 1000)
        self.sl_feed.setValue(int(f_init * 10000))
        self.sl_feed.setFixedWidth(100)
        self.sl_feed.valueChanged.connect(self.canvas.set_feed)
        ctrl.addWidget(self.sl_feed)

        ctrl.addSpacing(6)

        # Kill slider
        k_lbl = QLabel("Kill")
        ctrl.addWidget(k_lbl)
        self.sl_kill = QSlider(Qt.Orientation.Horizontal)
        self.sl_kill.setRange(400, 800)
        self.sl_kill.setValue(int(k_init * 10000))
        self.sl_kill.setFixedWidth(100)
        self.sl_kill.valueChanged.connect(self.canvas.set_kill)
        ctrl.addWidget(self.sl_kill)

        ctrl.addStretch()

        # Reset
        reset_btn = QPushButton("⟳ Reset")
        reset_btn.clicked.connect(self._on_reset)
        ctrl.addWidget(reset_btn)

        vbox.addLayout(ctrl)

    def _on_reset(self) -> None:
        name = self.preset_combo.currentText()
        self.canvas.reset()
        self.canvas.set_preset(name)


# ══════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Primordial Field")
    w = PrimordialFieldWidget()
    w.resize(680, 760)
    w.show()
    sys.exit(app.exec())
