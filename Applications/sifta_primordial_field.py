#!/usr/bin/env python3
"""
Applications/sifta_primordial_field.py — AG31 + C55M - Primordial Field
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
Math/Physics Pass: C55M — Codex GPT-5.5
Pass to: Opus 4.7 / CG55M for final chrome + color.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "Kernel") not in sys.path:
    sys.path.insert(0, str(_REPO / "Kernel"))
if str(_REPO / "Applications") not in sys.path:
    sys.path.insert(0, str(_REPO / "Applications"))

import numpy as np
from collections import deque

try:
    from numba import njit as _njit
    _HAS_NUMBA = True
except Exception:
    _HAS_NUMBA = False
    _njit = None

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QFont, QImage, QPainter, QPen, QBrush, QPainterPath,
    QLinearGradient, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton,
    QSlider, QVBoxLayout, QWidget, QComboBox,
)
from System.swarm_app_hardening import record_app_hardening_event

# ── Doctor sigil bar (canonical Applications/_doctor_sigil_chrome) ────
try:
    from _doctor_sigil_chrome import paint_doctor_sigil_bar
    _HAS_SIGIL = True
except Exception:
    _HAS_SIGIL = False

# ── Try canonical PoUW economy ────────────────────────────────────────
try:
    from System.proof_of_useful_work import issue_work_receipt
    from Kernel.body_state import load_agent_state, save_agent_state
    _HAS_POUW = True
    _POUW_ERROR = ""
except Exception as exc:
    _HAS_POUW = False
    _POUW_ERROR = f"{type(exc).__name__}: {exc}"

# ══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════

GRID = 256 if _HAS_NUMBA else 128
N_AGENTS = 72 if _HAS_NUMBA else 40
STEPS_PER_TICK = 6 if _HAS_NUMBA else 8
DT = 1.0            # Gray-Scott time step
DIFFUSION_U = 0.2097
DIFFUSION_V = 0.1050
PATTERN_MINT_THRESHOLD = 3.20
PATTERN_MINT_INTERVAL_S = 10.0
NEON_CYAN   = QColor(0, 255, 200)
NEON_GOLD   = QColor(255, 200, 0)
NEON_PINK   = QColor(255, 60, 160)
NEON_PURPLE = QColor(180, 80, 255)
BG_DARK     = QColor(4, 6, 14)
BG_DEEP     = QColor(2, 3, 9)

# Comet / agent visuals
TRAIL_HISTORY = 10               # frames of position history per agent
RIPPLE_LIFESPAN_S = 1.4          # click-injection ripple visible for this long
INTRO_DURATION_S = 3.5           # welcome overlay


def _build_aurora_lut() -> np.ndarray:
    """256-stop cinematic field colormap — black → indigo → violet → pink
    → gold → near-white. Designed so Gray-Scott V fronts visually pop.
    """
    stops = [
        (0.00, (3, 4, 14)),       # space-black
        (0.10, (10, 12, 38)),     # deep ocean
        (0.25, (28, 18, 78)),     # indigo
        (0.45, (96, 32, 142)),    # violet
        (0.62, (200, 60, 130)),   # magenta
        (0.78, (255, 130, 90)),   # warm gold
        (0.90, (255, 220, 130)),  # solar
        (1.00, (255, 250, 230)),  # near-white core
    ]
    xs = np.linspace(0.0, 1.0, 256)
    out = np.zeros((256, 3), dtype=np.float32)
    for i, x in enumerate(xs):
        # find segment
        for j in range(len(stops) - 1):
            x0, c0 = stops[j]
            x1, c1 = stops[j + 1]
            if x0 <= x <= x1:
                t = (x - x0) / (x1 - x0) if x1 > x0 else 0.0
                # smoothstep
                t = t * t * (3 - 2 * t)
                out[i] = (
                    c0[0] + (c1[0] - c0[0]) * t,
                    c0[1] + (c1[1] - c0[1]) * t,
                    c0[2] + (c1[2] - c0[2]) * t,
                )
                break
    return np.clip(out, 0, 255).astype(np.uint8)


_AURORA_LUT = _build_aurora_lut()

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
APP_HARDENING_ID = "queue-003:sifta_primordial_field"


if _HAS_NUMBA:
    @_njit(cache=True, fastmath=True)
    def _grayscott_step_jit(U, V, F, K, steps, du, dv, dt):
        n = U.shape[0]
        for _ in range(steps):
            U0 = U.copy()
            V0 = V.copy()
            for y in range(n):
                ym = (y - 1) % n
                yp = (y + 1) % n
                for x in range(n):
                    xm = (x - 1) % n
                    xp = (x + 1) % n
                    u = U0[y, x]
                    v = V0[y, x]
                    lap_u = U0[ym, x] + U0[yp, x] + U0[y, xm] + U0[y, xp] - 4.0 * u
                    lap_v = V0[ym, x] + V0[yp, x] + V0[y, xm] + V0[y, xp] - 4.0 * v
                    uvv = u * v * v
                    new_u = u + dt * (du * lap_u - uvv + F * (1.0 - u))
                    new_v = v + dt * (dv * lap_v + uvv - (F + K) * v)
                    if new_u < 0.0:
                        new_u = 0.0
                    elif new_u > 1.0:
                        new_u = 1.0
                    if new_v < 0.0:
                        new_v = 0.0
                    elif new_v > 1.0:
                        new_v = 1.0
                    U[y, x] = new_u
                    V[y, x] = new_v


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
        if _HAS_NUMBA:
            _grayscott_step_jit(U, V, F, K, steps, DIFFUSION_U, DIFFUSION_V, DT)
            return

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
        """Shannon entropy of U grid in bits — proxy for pattern complexity."""
        return _array_entropy_bits(self.U, bins=32)

    def metrics(self, trail: Optional[np.ndarray] = None, agent_count: int = 0) -> Dict[str, float]:
        """Physics-backed pattern metrics used for honest receipt gating."""
        gy, gx = np.gradient(self.U)
        interface_pressure = float(np.mean(np.sqrt(gx * gx + gy * gy)))
        v_mass = float(np.mean(self.V))
        u_variance = float(np.var(self.U))
        trail_entropy = _array_entropy_bits(trail, bins=24) if trail is not None else 0.0
        entropy_bits = self.entropy()
        structure_score = (
            entropy_bits
            + min(2.0, interface_pressure * 160.0)
            + min(1.0, u_variance * 14.0)
            + min(1.0, trail_entropy * 0.20)
            + min(0.50, v_mass * 2.0)
        )
        return {
            "entropy_bits": round(entropy_bits, 6),
            "interface_pressure": round(interface_pressure, 8),
            "u_variance": round(u_variance, 8),
            "v_mass": round(v_mass, 8),
            "trail_entropy_bits": round(trail_entropy, 6),
            "agent_count": float(agent_count),
            "structure_score": round(float(structure_score), 6),
        }

    def state_digest(self, metrics: Dict[str, float]) -> str:
        """Canonical digest of the simulated chemistry, topology, and metrics."""
        stride = max(1, self.n // 32)
        payload = {
            "grid": self.n,
            "F": round(float(self.F), 6),
            "K": round(float(self.K), 6),
            "U_q": np.round(self.U[::stride, ::stride] * 255).astype(np.uint8).tolist(),
            "V_q": np.round(self.V[::stride, ::stride] * 255).astype(np.uint8).tolist(),
            "metrics": metrics,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def to_rgb_image(self) -> QImage:
        """Render the chemistry through a cinematic aurora colormap.

        The visual idea: U (substrate) fades to deep ocean; V (autocatalyst)
        flares as gold→pink→lavender highlights. We feed a single scalar
        per cell into a precomputed 256-stop LUT so even at 256×256 we
        render at full FPS. Bloom is layered separately by the canvas.
        """
        u = self.U
        v = self.V
        # Reaction "intensity" per cell: V dominates, U fills the dark.
        # We bias toward V so coral / mitosis patterns flare brightly.
        scalar = np.clip(0.05 + 1.55 * v + 0.18 * (1.0 - u), 0.0, 1.0)
        idx = (scalar * 255).astype(np.uint8)
        rgb = _AURORA_LUT[idx]            # (n, n, 3) uint8
        rgb = np.ascontiguousarray(rgb)
        h, w, ch = rgb.shape
        return QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()

    def to_bloom_image(self) -> QImage:
        """Soft additive bloom — bright cells leak light into neighbours.

        Cheap separable blur via three np.roll passes; alpha-encoded so the
        canvas can blit it on top with QPainter additive composition.
        """
        v = self.V
        # Threshold the brightest 30% so bloom hugs the active reaction.
        m = np.clip((v - 0.35) * 1.6, 0.0, 1.0)
        # 3x3 blur, three iterations
        for _ in range(3):
            m = (
                m
                + np.roll(m, 1, 0) + np.roll(m, -1, 0)
                + np.roll(m, 1, 1) + np.roll(m, -1, 1)
            ) / 5.0
        alpha = (m * 200).astype(np.uint8)
        # Warm aurora bloom — gold/pink, not the field colour itself.
        r = (m * 255).astype(np.uint8)
        g = (m * 130).astype(np.uint8)
        b = (m * 200).astype(np.uint8)
        rgba = np.stack([r, g, b, alpha], axis=-1)
        rgba = np.ascontiguousarray(rgba)
        h, w, _ = rgba.shape
        return QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()


def _array_entropy_bits(arr: Optional[np.ndarray], bins: int = 32) -> float:
    """Bounded Shannon entropy from histogram probabilities, not density."""
    if arr is None:
        return 0.0
    hist, _ = np.histogram(arr, bins=bins, range=(0.0, 1.0), density=False)
    total = float(hist.sum())
    if total <= 0:
        return 0.0
    probs = hist.astype(np.float64) / total
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log2(probs)))


# ══════════════════════════════════════════════════════════════════════
# PHYSARUM AGENT
# ══════════════════════════════════════════════════════════════════════

class PhysarumAgent:
    """One slime-mold explorer that chemotaxes over the Gray-Scott field."""

    SENSOR_ANGLE = math.radians(45)
    SENSOR_DIST  = 4.0
    ROTATE_SPEED = math.radians(30)

    def __init__(self, n: int, x: Optional[float] = None, y: Optional[float] = None) -> None:
        self.n = n
        self.x = float(x if x is not None else n // 2 + np.random.randint(-n // 6, n // 6))
        self.y = float(y if y is not None else n // 2 + np.random.randint(-n // 6, n // 6))
        self.angle = np.random.uniform(0, 2 * math.pi)
        self.alive = True
        self.age = 0
        # Last few positions for comet-tail rendering.
        self.history: deque = deque(maxlen=TRAIL_HISTORY)

    def _sense(self, U: np.ndarray, V: np.ndarray, trail: np.ndarray, angle_offset: float) -> float:
        sa = self.angle + angle_offset
        sx = int((self.x + math.cos(sa) * self.SENSOR_DIST) % self.n)
        sy = int((self.y + math.sin(sa) * self.SENSOR_DIST) % self.n)
        # U is nutrient, trail is social memory, V is predator/inhibitor.
        return float(U[sy, sx] + 0.42 * trail[sy, sx] - 0.68 * V[sy, sx])

    def step(self, U: np.ndarray, V: np.ndarray, trail: np.ndarray) -> None:
        # Sense ahead, left, right — prefer nutrient + pheromone, avoid V.
        fwd   = self._sense(U, V, trail, 0)
        left  = self._sense(U, V, trail, -self.SENSOR_ANGLE)
        right = self._sense(U, V, trail,  self.SENSOR_ANGLE)

        if fwd > left and fwd > right:
            pass  # stay straight
        elif left > right:
            self.angle -= self.ROTATE_SPEED
        elif right > left:
            self.angle += self.ROTATE_SPEED
        else:
            self.angle += np.random.uniform(-self.ROTATE_SPEED, self.ROTATE_SPEED)

        # Move
        self.history.append((self.x, self.y))
        self.x = (self.x + math.cos(self.angle)) % self.n
        self.y = (self.y + math.sin(self.angle)) % self.n

        # Deposit pheromone trail
        ix, iy = int(self.x) % self.n, int(self.y) % self.n
        trail[iy, ix] = min(1.0, trail[iy, ix] + 0.15)

        # Die if V overwhelms local cell (predator wins).
        if V[iy, ix] > 0.82 and self.age > 20:
            self.alive = False
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
        self._receipt_count = 0
        self._last_metrics = self.field.metrics(self.trail, len(self.agents))
        self._last_state_hash = self.field.state_digest(self._last_metrics)
        self._last_mint_note = "waiting for structured chemistry"
        self._fps_last = time.time()
        self._fps = 0.0
        self._tick_count = 0
        self._last_sigil_error = ""

        # Click ripples — list of (cx_px, cy_px, age_seconds) for visual feedback
        self._ripples: List[List[float]] = []

        # Intro overlay
        self._birth_ts = time.time()

        # Receipt-mint flash
        self._mint_flash_until = 0.0
        self._mint_flash_score = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)  # 25 fps target

    # ── Simulation tick ─────────────────────────────────────────────

    def _tick(self) -> None:
        self.field.step(steps=STEPS_PER_TICK)

        # Evaporate trail
        self.trail *= 0.96

        # Step agents
        for ag in self.agents:
            ag.step(self.field.U, self.field.V, self.trail)
        self.agents = [
            ag for ag in self.agents
            if ag.alive and ag.age < 2400
        ]

        # Replenish dead / old agents near high-nutrient cells so the organism
        # stays coupled to the chemistry instead of respawning randomly forever.
        while len(self.agents) < N_AGENTS:
            self.agents.append(self._spawn_agent())

        self._last_metrics = self.field.metrics(self.trail, len(self.agents))
        self._last_state_hash = self.field.state_digest(self._last_metrics)

        # Pattern metrics → canonical PoUW receipt.
        now = time.time()
        if now - self._last_mint > PATTERN_MINT_INTERVAL_S:
            ent = self._last_metrics["entropy_bits"]
            self._entropy_acc += ent
            score = self._last_metrics["structure_score"]
            if score >= PATTERN_MINT_THRESHOLD:
                self._issue_pattern_receipt(score=score)
            else:
                self._last_mint_note = f"score {score:.2f} below {PATTERN_MINT_THRESHOLD:.2f}"
            self._last_mint = now

        self._frame += 1
        self._tick_count += 1
        dt = now - self._fps_last
        if dt > 0.5:
            self._fps = self._frame / max(dt, 0.001)
            self._frame = 0
            self._fps_last = now

        # Age out old ripples
        if self._ripples:
            self._ripples = [r for r in self._ripples
                             if (time.time() - r[2]) < RIPPLE_LIFESPAN_S]

        self.update()

    def _spawn_agent(self) -> PhysarumAgent:
        nutrient = self.field.U - self.field.V
        ys, xs = np.where(nutrient > np.percentile(nutrient, 72))
        if len(xs):
            idx = int(np.random.randint(0, len(xs)))
            return PhysarumAgent(GRID, float(xs[idx]), float(ys[idx]))
        return PhysarumAgent(GRID)

    def _issue_pattern_receipt(self, score: float) -> None:
        if not _HAS_POUW:
            self._last_mint_note = f"PoUW unavailable: {_POUW_ERROR}"
            return
        agent_id = os.environ.get("SIFTA_NODE_AGENT", "LOCAL_PREDATOR")
        try:
            agent_state = load_agent_state(agent_id) or {"id": agent_id}
            payload = {
                "app": "AG31 + C55M - Primordial Field",
                "grid": GRID,
                "engine": "numba" if _HAS_NUMBA else "numpy",
                "metrics": self._last_metrics,
                "structure_score": round(float(score), 6),
                "state_hash": self._last_state_hash,
            }
            receipt = issue_work_receipt(
                agent_state=agent_state,
                work_type="PRIMORDIAL_FIELD_PATTERN",
                description=(
                    "Verified Gray-Scott + Physarum pattern: "
                    + json.dumps(payload, sort_keys=True)
                ),
                territory="primordial_field",
                output_hash=self._last_state_hash[:16],
            )
            save_agent_state(agent_state)
            self._receipt_count += 1
            self._stgm_total += receipt.work_value * 100.0
            self._last_mint_note = f"receipt {receipt.receipt_id} score={score:.2f}"
            # Visual flash + sub-second sparkle when STGM is minted
            self._mint_flash_until = time.time() + 1.6
            self._mint_flash_score = score
        except Exception as exc:
            self._last_mint_note = f"receipt failed: {type(exc).__name__}"

    # ── Painting ────────────────────────────────────────────────────

    def paintEvent(self, _) -> None:  # noqa: N802
        p = QPainter(self)
        try:
            self._paint(p)
        finally:
            p.end()

    def _paint(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # ── Deep depth gradient backdrop (subtle, never flat) ───────
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, BG_DEEP)
        bg.setColorAt(1.0, BG_DARK)
        p.fillRect(0, 0, w, h, QBrush(bg))

        # ── Gray-Scott field through aurora LUT ─────────────────────
        img = self.field.to_rgb_image()
        scaled = img.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        p.drawImage(0, 0, scaled)

        # ── Additive bloom on hot reaction fronts ───────────────────
        bloom = self.field.to_bloom_image()
        bloom_s = bloom.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.setOpacity(0.55)
        p.drawImage(0, 0, bloom_s)
        p.setOpacity(1.0)
        p.restore()

        # ── Physarum pheromone glow (additive aqua) ─────────────────
        trail_img = self._trail_to_image()
        scaled_trail = trail_img.scaled(w, h,
                                        Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation)
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.setOpacity(0.7)
        p.drawImage(0, 0, scaled_trail)
        p.setOpacity(1.0)
        p.restore()

        # ── Agent comet trails + radial halos + cores ───────────────
        sx = w / GRID
        sy = h / GRID
        self._draw_agents(p, sx, sy)

        # ── Click ripples (V-injection feedback) ────────────────────
        self._draw_ripples(p, sx, sy)

        # ── Receipt-mint sparkle flash ──────────────────────────────
        self._draw_mint_flash(p, w, h)

        # ── Edge vignette (focuses the eye on the chemistry) ────────
        self._draw_vignette(p, w, h)

        # ── Cinematic HUD: stat cards + structure thermometer ──────
        self._draw_hud(p, w, h)

        # ── Doctor Sigil bar (top chrome, painted last) ─────────────
        if _HAS_SIGIL:
            try:
                # Subtitle stays short so it never collides with the title.
                paint_doctor_sigil_bar(
                    p, doctors=["AG31", "C55M", "CG55M"],
                    x=0, y=0, w=w, h=42,
                    title="Primordial Field",
                    subtitle="Gray-Scott · Physarum · PoUW",
                )
            except Exception as exc:
                self._last_sigil_error = f"{type(exc).__name__}: {exc}"
                record_app_hardening_event(
                    APP_HARDENING_ID,
                    "doctor_sigil_paint_failed",
                    truth_label="OBSERVED",
                    details={"error": self._last_sigil_error},
                )

        # ── Welcome intro overlay (first ~3.5 s) ────────────────────
        self._draw_intro(p, w, h)

    # ── Visual layers ────────────────────────────────────────────────
    def _draw_agents(self, p: QPainter, sx: float, sy: float) -> None:
        # Comet trail strokes — older positions fade out.
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for ag in self.agents:
            hist = list(ag.history)
            if len(hist) >= 2:
                path = QPainterPath()
                x0, y0 = hist[0]
                path.moveTo(x0 * sx, y0 * sy)
                for hx, hy in hist[1:]:
                    path.lineTo(hx * sx, hy * sy)
                pen = QPen(QColor(120, 240, 240, 120), 1.4)
                p.setPen(pen)
                p.drawPath(path)
        p.restore()

        # Halos + cores
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for ag in self.agents:
            ax, ay = ag.position()
            cx = ax * sx
            cy = ay * sy
            # Soft halo
            grad = QRadialGradient(cx, cy, 9.0)
            grad.setColorAt(0.0, QColor(150, 255, 230, 200))
            grad.setColorAt(0.45, QColor(40, 200, 220, 90))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(grad))
            p.drawEllipse(QPointF(cx, cy), 9.0, 9.0)
            # Bright core
            p.setBrush(QBrush(QColor(220, 255, 245)))
            p.drawEllipse(QPointF(cx, cy), 1.6, 1.6)
        p.restore()

    def _draw_ripples(self, p: QPainter, sx: float, sy: float) -> None:
        if not self._ripples:
            return
        now = time.time()
        p.save()
        p.setBrush(Qt.BrushStyle.NoBrush)
        for cx_grid, cy_grid, t0 in self._ripples:
            age = now - t0
            t = age / RIPPLE_LIFESPAN_S
            if t >= 1.0:
                continue
            radius = (8 + 80 * t) * min(sx, sy)
            alpha = int(220 * (1 - t))
            pen = QPen(QColor(255, 220, 130, alpha), 2.0 - 1.5 * t)
            p.setPen(pen)
            p.drawEllipse(QPointF(cx_grid * sx, cy_grid * sy),
                          radius / sx, radius / sy)
        p.restore()

    def _draw_mint_flash(self, p: QPainter, w: int, h: int) -> None:
        now = time.time()
        if now >= self._mint_flash_until:
            return
        t = 1.0 - (self._mint_flash_until - now) / 1.6
        alpha = int(140 * (1 - t))
        # Warm rim flash
        p.save()
        for i, glow in enumerate([14, 8, 4]):
            rect = QRectF(glow, 42 + glow, w - 2 * glow, h - 60 - 2 * glow)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 220, 120, max(0, alpha - i * 35)),
                          1.0 + 0.5 * i))
            p.drawRoundedRect(rect, 6, 6)
        p.restore()

    def _draw_vignette(self, p: QPainter, w: int, h: int) -> None:
        # Soft radial darkening at the edges to focus on the field.
        p.save()
        grad = QRadialGradient(w / 2, h / 2, max(w, h) * 0.7)
        grad.setColorAt(0.55, QColor(0, 0, 0, 0))
        grad.setColorAt(1.00, QColor(0, 0, 0, 140))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(0, 0, w, h)
        p.restore()

    def _draw_intro(self, p: QPainter, w: int, h: int) -> None:
        age = time.time() - self._birth_ts
        if age >= INTRO_DURATION_S:
            return
        # Last 0.8s: fade out
        if age > INTRO_DURATION_S - 0.8:
            fade = (INTRO_DURATION_S - age) / 0.8
        else:
            fade = 1.0
        alpha = int(200 * fade)
        # Center pill
        msg = "click anywhere to inject V · drag the F/K sliders to morph the chemistry"
        p.save()
        p.setFont(QFont("Menlo", 11))
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(msg)
        bx = (w - tw - 32) // 2
        by = h - 130
        p.setBrush(QBrush(QColor(8, 10, 22, alpha)))
        p.setPen(QPen(QColor(120, 100, 200, alpha), 1.0))
        p.drawRoundedRect(QRectF(bx, by, tw + 32, 30), 15, 15)
        p.setPen(QPen(QColor(220, 230, 250, alpha)))
        p.drawText(QRectF(bx, by, tw + 32, 30),
                   Qt.AlignmentFlag.AlignCenter, msg)
        p.restore()

    def _trail_to_image(self) -> QImage:
        t = self.trail
        # RGBA: aqua/teal glow where trail is strong (additive composited above)
        alpha = (t * 220).astype(np.uint8)
        r = (t * 70).astype(np.uint8)
        g = (t * 255).astype(np.uint8)
        b = (t * 230).astype(np.uint8)
        rgba = np.stack([r, g, b, alpha], axis=-1)
        rgba = np.ascontiguousarray(rgba)
        h, w, _ = rgba.shape
        return QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()

    def _draw_hud(self, p: QPainter, w: int, h: int) -> None:
        """macOS-feel HUD: four frosted stat cards + structure thermometer."""
        m = self._last_metrics
        cards = [
            ("PATTERN",
             f"{self.field.F:.3f} / {self.field.K:.3f}",
             "feed / kill",
             NEON_CYAN),
            ("AGENTS",
             f"{len(self.agents)}",
             f"grid {GRID}²  ·  {'Numba' if _HAS_NUMBA else 'NumPy'}",
             NEON_GOLD),
            ("STRUCTURE",
             f"{m['structure_score']:.2f}",
             f"H={m['entropy_bits']:.2f}  I={m['interface_pressure']*100:.2f}",
             NEON_PINK),
            ("PoUW",
             f"{self._receipt_count}",
             f"{self._stgm_total:.1f} STGM",
             NEON_PURPLE),
        ]
        card_w = 198
        card_h = 60
        gap = 10
        n = len(cards)
        total_w = card_w * n + gap * (n - 1)
        x = (w - total_w) // 2
        y = h - card_h - 14
        for label, value, sub, accent in cards:
            self._draw_stat_card(p, x, y, card_w, card_h, label, value, sub, accent)
            x += card_w + gap

        # Structure thermometer (top-left, under sigil bar)
        self._draw_structure_thermometer(p, w, h)
        # Mint-note toast at bottom-left if anything pending
        self._draw_mint_note(p, w, h)

    def _draw_stat_card(self, p: QPainter, x: int, y: int, cw: int, ch: int,
                        label: str, value: str, sub: str,
                        accent: QColor) -> None:
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Frosted base
        p.setBrush(QBrush(QColor(10, 14, 28, 200)))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
        p.drawRoundedRect(QRectF(x, y, cw, ch), 10, 10)
        # Top accent strip
        strip = QColor(accent)
        strip.setAlpha(180)
        p.setBrush(QBrush(strip))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(x, y, cw, 3), 3, 3)
        # Label (top, small caps tiny)
        p.setFont(QFont("Menlo", 7, QFont.Weight.Bold))
        lbl_col = QColor(accent)
        lbl_col.setAlpha(220)
        p.setPen(QPen(lbl_col))
        p.drawText(QRectF(x + 12, y + 6, cw - 24, 14),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   label)
        # Value (large) — shrink-to-fit if needed
        value_rect = QRectF(x + 12, y + 22, cw - 24, 22)
        p.setFont(QFont("Menlo", 17, QFont.Weight.Bold))
        from PyQt6.QtGui import QFontMetrics
        for size in (17, 15, 13, 11):
            f = QFont("Menlo", size, QFont.Weight.Bold)
            if QFontMetrics(f).horizontalAdvance(value) <= value_rect.width():
                p.setFont(f)
                break
        p.setPen(QPen(QColor(235, 240, 255)))
        p.drawText(value_rect,
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   value)
        # Sub (dim)
        p.setFont(QFont("Menlo", 8))
        p.setPen(QPen(QColor(140, 150, 180)))
        p.drawText(QRectF(x + 12, y + 44, cw - 24, 14),
                   int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                   sub)
        p.restore()

    def _draw_structure_thermometer(self, p: QPainter, w: int, h: int) -> None:
        m = self._last_metrics
        score = float(m["structure_score"])
        # Normalize: 0..(threshold + 2)
        full = PATTERN_MINT_THRESHOLD + 2.0
        frac = max(0.0, min(1.0, score / full))
        x = 22
        y = 80
        bar_w = 240
        bar_h = 8
        p.save()
        # Backplate
        p.setBrush(QBrush(QColor(10, 14, 28, 200)))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
        p.drawRoundedRect(QRectF(x - 8, y - 18, bar_w + 16, 38), 8, 8)
        # Label
        p.setFont(QFont("Menlo", 7, QFont.Weight.Bold))
        p.setPen(QPen(QColor(180, 200, 240, 180)))
        p.drawText(QPointF(x, y - 4), "STRUCTURE  →  PoUW MINT")
        # Track
        p.setBrush(QBrush(QColor(30, 40, 60)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 4, 4)
        # Fill — gradient cyan→pink→gold by region
        fill_w = int(bar_w * frac)
        if fill_w > 0:
            grad = QLinearGradient(x, y, x + bar_w, y)
            grad.setColorAt(0.0, QColor(0, 255, 200))
            grad.setColorAt(0.6, QColor(180, 80, 255))
            grad.setColorAt(1.0, QColor(255, 220, 130))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(x, y, fill_w, bar_h), 4, 4)
        # Threshold tick
        tx = x + int(bar_w * (PATTERN_MINT_THRESHOLD / full))
        p.setPen(QPen(QColor(255, 255, 255, 180), 1.0))
        p.drawLine(int(tx), int(y - 2), int(tx), int(y + bar_h + 2))
        # Score number, right-aligned
        p.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        p.setPen(QPen(QColor(235, 240, 255)))
        p.drawText(QPointF(x + bar_w + 24, y + 8), f"{score:.2f}")
        p.restore()

    def _draw_mint_note(self, p: QPainter, w: int, h: int) -> None:
        if not self._last_mint_note:
            return
        text = self._last_mint_note[:64]
        p.save()
        p.setFont(QFont("Menlo", 8))
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(text)
        x = 14
        y = h - 96
        p.setBrush(QBrush(QColor(10, 14, 28, 180)))
        p.setPen(QPen(QColor(255, 255, 255, 14), 1.0))
        p.drawRoundedRect(QRectF(x, y, tw + 24, 22), 11, 11)
        p.setPen(QPen(QColor(160, 180, 220)))
        p.drawText(QPointF(x + 12, y + 15), text)
        p.restore()

    # ── Mouse interaction ────────────────────────────────────────────

    def mousePressEvent(self, ev) -> None:  # noqa: N802
        if ev.button() == Qt.MouseButton.LeftButton:
            row = int(ev.position().y() / self.height() * GRID)
            col = int(ev.position().x() / self.width() * GRID)
            self.field.inject(row, col, radius=5)
            # Visual feedback ripple
            self._ripples.append([float(col), float(row), time.time()])

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
        self._last_metrics = self.field.metrics(self.trail, len(self.agents))
        self._last_state_hash = self.field.state_digest(self._last_metrics)
        self._last_mint_note = "reset; waiting for structured chemistry"


# ══════════════════════════════════════════════════════════════════════
# MAIN WIDGET
# ══════════════════════════════════════════════════════════════════════

class PrimordialFieldWidget(QWidget):
    """Full application window."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AG31 + C55M - Primordial Field")
        # macOS-feel: vibrancy-tinted background, hairline borders,
        # SF-Pro-ish sizing, large rounded controls.
        self.setStyleSheet("""
            QWidget { background: rgb(4, 6, 14); color: rgb(220, 230, 250); }
            QLabel  {
                font-family: -apple-system, 'SF Pro Text', 'Helvetica Neue', 'Menlo';
                font-size: 11px; color: rgb(180, 195, 230);
                font-weight: 500;
            }
            QComboBox {
                background: rgba(255, 255, 255, 8);
                color: rgb(220, 235, 255);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 7px;
                font-family: -apple-system, 'SF Pro Text', 'Menlo';
                font-size: 11px; padding: 5px 12px 5px 10px;
                min-height: 22px;
            }
            QComboBox:hover  { background: rgba(0, 255, 200, 18); }
            QComboBox:focus  { border: 1px solid rgb(0, 200, 170); }
            QComboBox::drop-down { width: 18px; border: none; }
            QComboBox QAbstractItemView {
                background: rgb(14, 18, 36);
                color: rgb(220, 230, 250);
                selection-background-color: rgb(0, 120, 100);
                border: 1px solid rgba(255, 255, 255, 30);
                outline: 0;
            }
            QPushButton {
                background: rgba(255, 255, 255, 10);
                color: rgb(0, 255, 200);
                border: 1px solid rgba(0, 255, 200, 90);
                border-radius: 7px;
                font-family: -apple-system, 'SF Pro Text', 'Menlo';
                font-size: 11px; font-weight: 600;
                padding: 5px 14px; min-height: 22px;
            }
            QPushButton:hover    { background: rgba(0, 255, 200, 26); }
            QPushButton:pressed  { background: rgba(0, 255, 200, 60); }
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(255, 255, 255, 25);
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: rgb(0, 255, 200); border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 14px; height: 14px;
                margin: -5px 0; border-radius: 7px;
                border: 1px solid rgba(0, 0, 0, 100);
            }
            QSlider::handle:horizontal:hover {
                background: rgb(220, 250, 255);
            }
        """)
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 8)
        vbox.setSpacing(6)

        self.canvas = PrimordialCanvas(self)
        vbox.addWidget(self.canvas, 1)

        # ── Controls row ──────────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(14, 0, 14, 4)
        ctrl.setSpacing(14)

        # Preset
        preset_lbl = QLabel("Pattern")
        preset_lbl.setStyleSheet("color: rgb(140, 155, 190); font-size: 10px;")
        ctrl.addWidget(preset_lbl)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(PRESETS.keys()))
        self.preset_combo.setCurrentText(DEFAULT_PRESET)
        self.preset_combo.currentTextChanged.connect(self._on_preset)
        self.preset_combo.setFixedWidth(110)
        ctrl.addWidget(self.preset_combo)

        ctrl.addSpacing(14)

        # Feed slider
        f_init, k_init = PRESETS[DEFAULT_PRESET]
        f_lbl = QLabel("Feed")
        f_lbl.setStyleSheet("color: rgb(140, 155, 190); font-size: 10px;")
        ctrl.addWidget(f_lbl)
        self.sl_feed = QSlider(Qt.Orientation.Horizontal)
        self.sl_feed.setRange(100, 1000)
        self.sl_feed.setValue(int(f_init * 10000))
        self.sl_feed.setFixedWidth(140)
        self.sl_feed.valueChanged.connect(self._on_feed)
        ctrl.addWidget(self.sl_feed)
        self.lbl_feed = QLabel(f"{f_init:.4f}")
        self.lbl_feed.setStyleSheet("color: rgb(0, 255, 200); "
                                    "font-family: Menlo; font-size: 10px; "
                                    "font-weight: 600; min-width: 56px;")
        ctrl.addWidget(self.lbl_feed)

        ctrl.addSpacing(8)

        # Kill slider
        k_lbl = QLabel("Kill")
        k_lbl.setStyleSheet("color: rgb(140, 155, 190); font-size: 10px;")
        ctrl.addWidget(k_lbl)
        self.sl_kill = QSlider(Qt.Orientation.Horizontal)
        self.sl_kill.setRange(400, 800)
        self.sl_kill.setValue(int(k_init * 10000))
        self.sl_kill.setFixedWidth(140)
        self.sl_kill.valueChanged.connect(self._on_kill)
        ctrl.addWidget(self.sl_kill)
        self.lbl_kill = QLabel(f"{k_init:.4f}")
        self.lbl_kill.setStyleSheet("color: rgb(255, 100, 160); "
                                    "font-family: Menlo; font-size: 10px; "
                                    "font-weight: 600; min-width: 56px;")
        ctrl.addWidget(self.lbl_kill)

        ctrl.addStretch()

        # Reset
        reset_btn = QPushButton("⟳  Reset")
        reset_btn.clicked.connect(self._on_reset)
        ctrl.addWidget(reset_btn)

        vbox.addLayout(ctrl)

    def _on_preset(self, name: str) -> None:
        self.canvas.set_preset(name)
        if name in PRESETS:
            f, k = PRESETS[name]
            self.sl_feed.blockSignals(True)
            self.sl_kill.blockSignals(True)
            self.sl_feed.setValue(int(f * 10000))
            self.sl_kill.setValue(int(k * 10000))
            self.sl_feed.blockSignals(False)
            self.sl_kill.blockSignals(False)
            self.lbl_feed.setText(f"{f:.4f}")
            self.lbl_kill.setText(f"{k:.4f}")

    def _on_feed(self, v: int) -> None:
        self.canvas.set_feed(v)
        self.lbl_feed.setText(f"{v / 10000.0:.4f}")

    def _on_kill(self, v: int) -> None:
        self.canvas.set_kill(v)
        self.lbl_kill.setText(f"{v / 10000.0:.4f}")

    def _on_reset(self) -> None:
        name = self.preset_combo.currentText()
        self.canvas.reset()
        self.canvas.set_preset(name)


# ══════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("AG31 + C55M - Primordial Field")
    w = PrimordialFieldWidget()
    w.resize(680, 760)
    w.show()
    sys.exit(app.exec())
