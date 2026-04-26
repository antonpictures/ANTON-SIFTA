#!/usr/bin/env python3
"""
sifta_calibrator_widget.py — CG55M Dr Cursor: Alice-Sees Calibrator (Game Mode)
═════════════════════════════════════════════════════════════════════════════
Originally an NVIDIA-Ising-Day inspired auto-calibration simulator. Gamified
2026-04-26 by CG55M Dr Cursor / Claude Opus 4.7 EXTRA-HIGH so that gestures
seen by Alice's eye actually drive the simulation.

Core simulation (unchanged):
  • Pheromone grid + 180 swimmer agents tracing a target shape.
  • Periodic NOISE SPIKES; AGENTIC mode auto-tunes evaporation + cohesion.

Game layer (added):
  • Lives, Score, Streak, Level, High Score (persisted).
  • Six unlockable target shapes: Rose → Spiral → Infinity → Heart → Star
    → Mandala. Waving at Alice advances the level.
  • Alice's eye (`.sifta_state/visual_stigmergy.jsonl`) is decoded by
    `System.swarm_gesture_decoder.GestureDecoder` into six gestures —
    each one binds to a real, visible game effect:
      WAVE_HORIZONTAL  → "ALICE WAVES BACK": shape advances + sparkles
      WAVE_VERTICAL    → "EXCITEMENT": cohesion +0.2 for 5 s, agents glow
      APPROACH         → "FOCUS": target shrinks, noise interval halved
      RECEDE           → "OVERVIEW": target expands, noise interval doubled
      STILL            → "ZEN": noise spikes paused for 8 s
      FLAIL            → "CHAOS BLOOM": forced spike + 2× score for 4 s
  • The HUD shows ALICE SEES: <gesture> with a live confidence bar.

Embeds inside SIFTA OS MDI via the standard widget pattern.
"""
from __future__ import annotations

import json
import math
import random
import sys
import time
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))
if str(_REPO / "Applications") not in sys.path:
    sys.path.insert(0, str(_REPO / "Applications"))

from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QHBoxLayout, QLabel, QPushButton, QSlider,
    QVBoxLayout, QWidget, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QRadialGradient,
    QLinearGradient, QPainterPath,
)

from agentic_calibrator import (
    CalibratorState, SwarmPhysics, SwarmTelemetry,
    calibrate_once, DEFAULT_EVAPORATION, DEFAULT_COHESION,
)
from System.swarm_gesture_decoder import GestureDecoder, GestureEvent
from _doctor_sigil_chrome import paint_doctor_sigil_bar, app_chrome_font

# ── Palette ──────────────────────────────────────────────────────
BG        = QColor(6, 8, 16)
GRID_LINE = QColor(20, 22, 35)
NEON_CYAN = QColor(0, 255, 200)
NEON_PINK = QColor(255, 60, 130)
NEON_GOLD = QColor(255, 200, 60)
NEON_PURPLE = QColor(180, 80, 255)
AGENT_CLR = QColor(0, 220, 180, 180)
TRAIL_CLR = QColor(0, 255, 200, 40)
NOISE_CLR = QColor(255, 40, 80, 100)
TARGET_CLR = QColor(80, 255, 200, 200)
TEXT_DIM  = QColor(100, 108, 140)
TEXT_BRIGHT = QColor(200, 210, 240)

# ── Grid + Sim constants ─────────────────────────────────────────
GRID_W, GRID_H = 160, 120
N_AGENTS = 180
NOISE_INTERVAL_MIN = 4.0
NOISE_INTERVAL_MAX = 9.0
NOISE_DURATION = 1.5

# ── Game / shape constants ───────────────────────────────────────
HI_SCORE_PATH = _REPO / ".sifta_state" / "calibrator_high_scores.jsonl"
GAME_OVER_COHERENCE = 12.0     # below this during a spike → lose a life
LIFE_RECOVERY_COHERENCE = 90.0 # above this for a while → recover a life
LIFE_RECOVERY_SECONDS = 25.0
STREAK_THRESHOLD = 70.0        # coherence above this builds streak

SHAPES: List[Tuple[str, str]] = [
    ("ROSE",     "🌹"),
    ("SPIRAL",   "🌀"),
    ("INFINITY", "∞"),
    ("HEART",    "❤"),
    ("STAR",     "★"),
    ("MANDALA",  "✺"),
]


def _shape_points(name: str, angle: float) -> List[Tuple[float, float]]:
    """Return ~360 (gx, gy) target vertices for the given shape, on the
    pheromone grid. Origin is grid centre; rotation is `angle` radians."""
    cx, cy = GRID_W / 2.0, GRID_H / 2.0
    r_base = min(GRID_W, GRID_H) * 0.32
    pts: List[Tuple[float, float]] = []
    if name == "ROSE":
        for i in range(360):
            theta = math.radians(i) + angle
            r = r_base * (0.6 + 0.4 * math.cos(5 * theta))
            pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    elif name == "SPIRAL":
        # archimedean spiral, 4 turns
        for i in range(360):
            t = i / 359.0
            theta = t * 4 * 2 * math.pi + angle
            r = r_base * (0.15 + 0.85 * t)
            pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    elif name == "INFINITY":
        # Bernoulli lemniscate, parametrically:
        for i in range(360):
            t = math.radians(i) + angle
            denom = 1 + math.sin(t) ** 2
            x = r_base * 1.4 * math.cos(t) / denom
            y = r_base * 1.4 * math.sin(t) * math.cos(t) / denom
            pts.append((cx + x, cy + y))
    elif name == "HEART":
        # classic 16 sin^3 / cos polynomial heart
        for i in range(360):
            t = math.radians(i) + angle
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((cx + x * (r_base / 17.0),
                        cy - y * (r_base / 17.0)))
    elif name == "STAR":
        # 5-pointed star with inner/outer radius
        n = 10
        r_outer = r_base
        r_inner = r_base * 0.42
        verts = []
        for i in range(n):
            a = angle + i * (math.pi / (n / 2))
            r = r_outer if i % 2 == 0 else r_inner
            verts.append((cx + r * math.cos(a - math.pi / 2),
                          cy + r * math.sin(a - math.pi / 2)))
        # densify by interpolating along the polygon perimeter
        for i in range(len(verts)):
            x1, y1 = verts[i]
            x2, y2 = verts[(i + 1) % len(verts)]
            for s in range(36):
                t = s / 36.0
                pts.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    elif name == "MANDALA":
        # 8-petal mandala = sum of two rose curves
        for i in range(360):
            theta = math.radians(i) + angle
            r = r_base * (0.5 + 0.25 * math.cos(8 * theta) +
                          0.25 * math.sin(3 * theta))
            pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    else:
        # graceful fallback
        for i in range(360):
            theta = math.radians(i) + angle
            pts.append((cx + r_base * math.cos(theta),
                        cy + r_base * math.sin(theta)))
    return pts


def _gesture_color(kind: str) -> QColor:
    return {
        "WAVE_HORIZONTAL": QColor(0,   255, 200),
        "WAVE_VERTICAL":   QColor(180, 230, 255),
        "APPROACH":        QColor(255, 200, 60),
        "RECEDE":          QColor(180, 80,  255),
        "STILL":           QColor(120, 255, 180),
        "FLAIL":           QColor(255, 60,  120),
    }.get(kind, QColor(200, 200, 220))


def _gesture_label(kind: str) -> str:
    return {
        "WAVE_HORIZONTAL": "WAVE — Alice waves back",
        "WAVE_VERTICAL":   "NOD — excitement",
        "APPROACH":        "APPROACH — focus",
        "RECEDE":          "RECEDE — overview",
        "STILL":           "STILL — zen",
        "FLAIL":           "FLAIL — chaos bloom",
    }.get(kind, kind)


def _load_high_score() -> float:
    if not HI_SCORE_PATH.exists():
        return 0.0
    try:
        last = 0.0
        with HI_SCORE_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                last = max(last, float(row.get("score", 0.0)))
        return last
    except OSError:
        return 0.0


def _persist_high_score(score: float, level: int, streak: float) -> None:
    try:
        HI_SCORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with HI_SCORE_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "score": round(score, 2),
                "level": level,
                "best_streak_s": round(streak, 2),
                "doctor": "CG55M",
            }) + "\n")
    except OSError:
        pass


class _Agent:
    __slots__ = ("x", "y", "vx", "vy", "on_target")

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vx = random.gauss(0, 0.5)
        self.vy = random.gauss(0, 0.5)
        self.on_target = False


class CalibrationCanvas(QWidget):
    """Central simulation canvas — the Pheromone Matrix + agents + target."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(700, 500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── Pheromone grid (float32) ──────────────────────────────
        self.grid = np.zeros((GRID_H, GRID_W), dtype=np.float32)

        # ── Agents ────────────────────────────────────────────────
        self.agents: List[_Agent] = []
        for _ in range(N_AGENTS):
            self.agents.append(_Agent(
                random.uniform(10, GRID_W - 10),
                random.uniform(10, GRID_H - 10),
            ))

        # ── Target shape ──────────────────────────────────────────
        self.target_pts: List[Tuple[float, float]] = []
        self._target_angle = 0.0
        self.shape_idx = 0          # game level → shape index
        self._target_scale = 1.0    # APPROACH/RECEDE adjust this
        self._rebuild_target()

        # ── Physics (controlled by sliders / calibrator) ──────────
        self.evaporation = DEFAULT_EVAPORATION
        self.cohesion = DEFAULT_COHESION

        # ── Noise state ───────────────────────────────────────────
        self.noise_level = 0.0
        self._noise_timer = 0.0
        self._next_noise = random.uniform(NOISE_INTERVAL_MIN, NOISE_INTERVAL_MAX)
        self._in_spike = False
        self._spike_remaining = 0.0
        self._noise_interval_scale = 1.0  # APPROACH halves it, RECEDE doubles
        self._noise_pause_until = 0.0     # STILL "zen" suppression deadline
        self._spike_id = 0                # increments at spike start
        self._life_lost_in_spike = -1     # last spike id where we lost a life

        # ── Agentic calibrator ────────────────────────────────────
        self.agentic_mode = False
        self._cal_state = CalibratorState()
        self._cal_phys = SwarmPhysics(
            evaporation_rate=self.evaporation,
            cohesion_strength=self.cohesion,
        )

        # ── Metrics ───────────────────────────────────────────────
        self.coherence_pct = 100.0
        self.cal_per_sec = 0.0
        self.total_cal = 0
        self.scal_score = 0.0
        self.tick_count = 0
        self.mode_label = "IDLE"

        # ── Game state (gamification) ─────────────────────────────
        self.lives = 3
        self.score = 0.0
        self.streak_seconds = 0.0
        self.best_streak = 0.0
        self.life_recovery_progress = 0.0
        self.bonus_multiplier = 1.0
        self._bonus_until = 0.0
        self.cohesion_boost = 0.0
        self._cohesion_boost_until = 0.0
        self.high_score = _load_high_score()
        self.game_over = False
        self._high_score_persisted = False

        # ── Alice's eye → gestures ────────────────────────────────
        self.gesture_decoder = GestureDecoder()
        self.last_gesture: Optional[GestureEvent] = None
        self.gesture_log: Deque[GestureEvent] = deque(maxlen=8)
        self.gesture_count = 0
        self.alice_state: dict = self.gesture_decoder.state()
        self._sparkles: List[List[float]] = []   # [x_grid, y_grid, age, color_hsv]

        # ── Timers ────────────────────────────────────────────────
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)
        self._gesture_timer = QTimer(self)
        self._gesture_timer.timeout.connect(self._poll_gestures)
        self._gesture_timer.start(180)  # ~5.5 Hz, matches Alice's eye

    def _rebuild_target(self):
        """Generate target vertices for the current level's shape."""
        name, _icon = SHAPES[self.shape_idx % len(SHAPES)]
        pts = _shape_points(name, self._target_angle)
        # Apply gesture-driven zoom
        cx, cy = GRID_W / 2.0, GRID_H / 2.0
        s = max(0.55, min(1.45, self._target_scale))
        self.target_pts = [(cx + (px - cx) * s, cy + (py - cy) * s) for px, py in pts]

    def _deposit_target(self):
        """Deposit pheromone along the target shape."""
        for (tx, ty) in self.target_pts[::3]:
            gx, gy = int(tx), int(ty)
            if 0 <= gx < GRID_W and 0 <= gy < GRID_H:
                self.grid[gy, gx] = min(1.0, self.grid[gy, gx] + 0.08)

    def _tick(self):
        dt = 0.033
        self.tick_count += 1
        w_px, h_px = self.width(), self.height()

        # ── Rotate target slowly ──────────────────────────────────
        self._target_angle += 0.003
        if self.tick_count % 5 == 0:
            self._rebuild_target()

        # ── Deposit target pheromone ──────────────────────────────
        self._deposit_target()

        # ── Noise spike scheduling ────────────────────────────────
        # ZEN mode (STILL gesture) suppresses spikes for a few seconds.
        # APPROACH halves the interval; RECEDE doubles it.
        now_ts = time.time()
        zen_active = now_ts < self._noise_pause_until
        self._noise_timer += dt
        if not zen_active and not self._in_spike \
                and self._noise_timer >= self._next_noise:
            self._in_spike = True
            self._spike_remaining = NOISE_DURATION
            self._noise_timer = 0.0
            ni_min = NOISE_INTERVAL_MIN * self._noise_interval_scale
            ni_max = NOISE_INTERVAL_MAX * self._noise_interval_scale
            self._next_noise = random.uniform(ni_min, ni_max)
            self._spike_id += 1

        if self._in_spike:
            self._spike_remaining -= dt
            spike_intensity = self._spike_remaining / NOISE_DURATION
            self.noise_level = min(1.0, 0.5 + spike_intensity * 0.5)
            noise_grid = np.random.uniform(0, self.noise_level * 0.3,
                                           (GRID_H, GRID_W)).astype(np.float32)
            self.grid = np.clip(self.grid + noise_grid, 0, 1)
            for ag in self.agents:
                ag.vx += random.gauss(0, self.noise_level * 3.0)
                ag.vy += random.gauss(0, self.noise_level * 3.0)
            if self._spike_remaining <= 0:
                self._in_spike = False
        else:
            self.noise_level = max(0.0, self.noise_level - dt * 0.3)

        # ── Evaporate grid ────────────────────────────────────────
        self.grid *= self.evaporation

        # ── Agent physics ─────────────────────────────────────────
        on_count = 0
        cx_all, cy_all = 0.0, 0.0
        for ag in self.agents:
            cx_all += ag.x
            cy_all += ag.y
        if self.agents:
            cx_all /= len(self.agents)
            cy_all /= len(self.agents)

        for ag in self.agents:
            gx, gy = int(ag.x), int(ag.y)

            # Pheromone gradient sensing
            best_dx, best_dy, best_val = 0.0, 0.0, 0.0
            for ddx in (-2, -1, 0, 1, 2):
                for ddy in (-2, -1, 0, 1, 2):
                    nx, ny = gx + ddx, gy + ddy
                    if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                        v = self.grid[ny, nx]
                        if v > best_val:
                            best_val = v
                            best_dx = float(ddx)
                            best_dy = float(ddy)

            if best_val > 0.05:
                norm = math.sqrt(best_dx ** 2 + best_dy ** 2) + 1e-6
                ag.vx += (best_dx / norm) * 0.8
                ag.vy += (best_dy / norm) * 0.8

            # Cohesion pull toward swarm centroid (boosted by NOD gesture)
            dx_c = cx_all - ag.x
            dy_c = cy_all - ag.y
            d_c = math.sqrt(dx_c ** 2 + dy_c ** 2) + 1e-6
            coh_eff = self.cohesion + self.cohesion_boost
            ag.vx += (dx_c / d_c) * coh_eff * 0.3
            ag.vy += (dy_c / d_c) * coh_eff * 0.3

            # Random walk
            ag.vx += random.gauss(0, 0.15)
            ag.vy += random.gauss(0, 0.15)

            # Damping
            ag.vx *= 0.85
            ag.vy *= 0.85

            # Move
            ag.x += ag.vx
            ag.y += ag.vy
            ag.x = max(1, min(GRID_W - 2, ag.x))
            ag.y = max(1, min(GRID_H - 2, ag.y))

            # Deposit trail
            gx2, gy2 = int(ag.x), int(ag.y)
            if 0 <= gx2 < GRID_W and 0 <= gy2 < GRID_H:
                self.grid[gy2, gx2] = min(1.0, self.grid[gy2, gx2] + 0.03)

            # Check on-target
            ag.on_target = False
            min_d = 999.0
            for (tx, ty) in self.target_pts[::6]:
                d = math.sqrt((ag.x - tx) ** 2 + (ag.y - ty) ** 2)
                if d < min_d:
                    min_d = d
            if min_d < 4.0:
                ag.on_target = True
                on_count += 1

        self.coherence_pct = (on_count / max(len(self.agents), 1)) * 100.0
        self.scal_score += self.coherence_pct * dt * 0.01

        # ── Game scoring ──────────────────────────────────────────
        if not self.game_over:
            now_ts = time.time()
            # Bonus multiplier expiry
            if now_ts >= self._bonus_until:
                self.bonus_multiplier = 1.0
            # Cohesion-boost expiry
            if now_ts >= self._cohesion_boost_until:
                self.cohesion_boost = 0.0

            mode_bonus = 1.5 if self.agentic_mode else 1.0
            gain = self.coherence_pct * dt * mode_bonus * self.bonus_multiplier
            self.score += gain

            if self.coherence_pct >= STREAK_THRESHOLD:
                self.streak_seconds += dt
                self.best_streak = max(self.best_streak, self.streak_seconds)
            else:
                self.streak_seconds = 0.0

            if self._in_spike and self.coherence_pct < GAME_OVER_COHERENCE \
                    and self._life_lost_in_spike != self._spike_id:
                # One life per spike, max — even if we re-cross the threshold.
                self.lives = max(0, self.lives - 1)
                self._life_lost_in_spike = self._spike_id
                if self.lives <= 0:
                    self.game_over = True
                    if not self._high_score_persisted:
                        _persist_high_score(self.score, self.shape_idx + 1,
                                            self.best_streak)
                        self.high_score = max(self.high_score, self.score)
                        self._high_score_persisted = True

            if self.coherence_pct >= LIFE_RECOVERY_COHERENCE and self.lives < 3:
                self.life_recovery_progress += dt
                if self.life_recovery_progress >= LIFE_RECOVERY_SECONDS:
                    self.lives += 1
                    self.life_recovery_progress = 0.0
            else:
                self.life_recovery_progress = max(
                    0.0, self.life_recovery_progress - dt * 0.4
                )

        # Apply cohesion boost so it's visible to agent physics next tick.
        # (We mutate the live cohesion only when boosted; calibrator code
        # still reads/writes the base value through `evaporation/cohesion`.)
        # Keeping this read-only here: rendering uses cohesion + boost.

        # Sparkle decay
        for sp in self._sparkles:
            sp[2] += dt
        self._sparkles = [s for s in self._sparkles if s[2] < 1.4]

        # ── Agentic calibration ───────────────────────────────────
        if self.agentic_mode:
            tel = SwarmTelemetry(
                noise_level=self.noise_level,
                coherence_pct=self.coherence_pct,
                pheromone_entropy=float(np.std(self.grid)),
                agent_scatter=0.0,
                timestamp=time.time(),
            )
            self._cal_phys.evaporation_rate = self.evaporation
            self._cal_phys.cohesion_strength = self.cohesion
            self._cal_phys = calibrate_once(tel, self._cal_phys, self._cal_state)
            self.evaporation = self._cal_phys.evaporation_rate
            self.cohesion = self._cal_phys.cohesion_strength
            self.mode_label = self._cal_phys.mode
            self.cal_per_sec = self._cal_state.adjustments_per_sec
            self.total_cal = self._cal_state.adjustments_total
        else:
            self.mode_label = "MANUAL"
            self.cal_per_sec = 0.0

        self.update()

    # ── Alice's eye → game effects ───────────────────────────────
    def _poll_gestures(self):
        """Drain new gesture events from Alice's eye and apply their
        gameplay effects. Also refresh the live `alice_state` snapshot
        so the HUD shows what Alice currently thinks the user is doing."""
        try:
            events = self.gesture_decoder.poll()
            self.alice_state = self.gesture_decoder.state()
        except Exception:
            return
        for evt in events:
            self._apply_gesture(evt)

    def _apply_gesture(self, evt: GestureEvent):
        self.last_gesture = evt
        self.gesture_log.append(evt)
        self.gesture_count += 1
        if self.game_over:
            return
        kind = evt.kind
        now_ts = time.time()
        if kind == "WAVE_HORIZONTAL":
            # Alice waves back: advance shape level + sparkle burst.
            self.shape_idx = (self.shape_idx + 1) % len(SHAPES)
            self._rebuild_target()
            for _ in range(40):
                self._sparkles.append([
                    random.uniform(GRID_W * 0.2, GRID_W * 0.8),
                    random.uniform(GRID_H * 0.2, GRID_H * 0.8),
                    0.0, random.uniform(0.0, 1.0),
                ])
            self.score += 250.0
        elif kind == "WAVE_VERTICAL":
            # Excitement: cohesion boost
            self.cohesion_boost = 0.25
            self._cohesion_boost_until = now_ts + 5.0
            self.score += 80.0
        elif kind == "APPROACH":
            self._target_scale = max(0.55, self._target_scale - 0.18)
            self._noise_interval_scale = 0.5
            self.score += 60.0
        elif kind == "RECEDE":
            self._target_scale = min(1.45, self._target_scale + 0.18)
            self._noise_interval_scale = 1.6
            self.score += 60.0
        elif kind == "STILL":
            # Zen: pause noise spikes for 8 s
            self._noise_pause_until = now_ts + 8.0
            self._in_spike = False
            self._spike_remaining = 0.0
            self.score += 120.0
        elif kind == "FLAIL":
            # Chaos bloom: forced spike + 2× score multiplier for 4 s
            self._in_spike = True
            self._spike_remaining = NOISE_DURATION * 1.4
            self.bonus_multiplier = 2.0
            self._bonus_until = now_ts + 4.0

    def reset_game(self):
        self.lives = 3
        self.score = 0.0
        self.streak_seconds = 0.0
        self.best_streak = 0.0
        self.life_recovery_progress = 0.0
        self.game_over = False
        self._high_score_persisted = False
        self.shape_idx = 0
        self._target_scale = 1.0
        self._noise_interval_scale = 1.0
        self._noise_pause_until = 0.0
        self._life_lost_in_spike = -1
        self.bonus_multiplier = 1.0
        self.cohesion_boost = 0.0
        self.gesture_log.clear()
        self._sparkles.clear()
        self._rebuild_target()

    # ── Rendering ─────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, BG)

        sx = w / GRID_W
        sy = h / GRID_H

        # ── Pheromone field ───────────────────────────────────────
        step = max(1, int(2 / min(sx, sy)))
        for gy in range(0, GRID_H, step):
            for gx in range(0, GRID_W, step):
                v = self.grid[gy, gx]
                if v < 0.02:
                    continue
                alpha = int(min(255, v * 300))
                if self._in_spike:
                    r_c = int(40 + v * 180)
                    g_c = int(v * 100)
                    b_c = int(80 + v * 60)
                else:
                    r_c = int(v * 40)
                    g_c = int(v * 255)
                    b_c = int(v * 200)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(r_c, g_c, b_c, alpha)))
                px = gx * sx
                py_ = gy * sy
                p.drawRect(QRectF(px, py_, sx * step + 1, sy * step + 1))

        # ── Target shape ──────────────────────────────────────────
        if len(self.target_pts) > 2:
            path = QPainterPath()
            x0, y0 = self.target_pts[0]
            path.moveTo(x0 * sx, y0 * sy)
            for (tx, ty) in self.target_pts[1:]:
                path.lineTo(tx * sx, ty * sy)
            path.closeSubpath()

            glow_alpha = 80 + int(30 * math.sin(self.tick_count * 0.05))
            p.setPen(QPen(QColor(80, 255, 200, glow_alpha), 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

            p.setPen(QPen(QColor(80, 255, 200, glow_alpha // 3), 5.0))
            p.drawPath(path)

        # ── Agents ────────────────────────────────────────────────
        for ag in self.agents:
            px, py_ = ag.x * sx, ag.y * sy
            if ag.on_target:
                p.setBrush(QBrush(QColor(0, 255, 200, 200)))
                radius = 3.0
            else:
                p.setBrush(QBrush(QColor(255, 100, 60, 140)))
                radius = 2.0
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(px, py_), radius, radius)

        # ── Noise spike flash ─────────────────────────────────────
        if self._in_spike:
            flash_alpha = int(self.noise_level * 40)
            p.fillRect(0, 0, w, h, QColor(255, 30, 60, flash_alpha))
            p.setPen(QPen(NEON_PINK, 2))
            p.setFont(QFont("Menlo", 18, QFont.Weight.Bold))
            p.drawText(QRectF(0, h * 0.02, w, 30), Qt.AlignmentFlag.AlignCenter,
                       "⚡ NOISE SPIKE ⚡")

        # ── Sparkles (WAVE response) ─────────────────────────────
        for sx_g, sy_g, age, hue_t in self._sparkles:
            t = age / 1.4
            alpha = int(255 * (1 - t))
            if alpha <= 0:
                continue
            r = 2 + 18 * t
            col = QColor.fromHsvF((0.3 + 0.6 * hue_t) % 1.0, 0.9, 1.0,
                                  max(0.0, 1.0 - t))
            p.setPen(QPen(col, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(sx_g * sx, sy_g * sy), r, r)

        # ── HUD overlay ───────────────────────────────────────────
        # Top-right: telemetry (kept, polished spacing)
        hud_top = 50  # leave 42 px for the doctor sigil bar
        p.setPen(QPen(TEXT_BRIGHT))
        p.setFont(QFont("Menlo", 8))
        telemetry_lines = [
            f"Noise: {self.noise_level * 100:.0f}%",
            f"Coherence: {self.coherence_pct:.1f}%",
            f"Cal/sec: {self.cal_per_sec:.1f}",
            f"Total Cal: {self.total_cal}",
            f"S-Cal: {self.scal_score:.1f}",
            f"Evap: {self.evaporation:.3f}",
            f"Cohesion: {self.cohesion + self.cohesion_boost:.3f}",
            f"Mode: {self.mode_label}",
        ]
        for i, line in enumerate(telemetry_lines):
            p.drawText(QPointF(w - 170, hud_top + i * 14), line)

        # ── Game HUD (top-left dock) ─────────────────────────────
        p.save()
        p.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        x0 = 16
        y0 = hud_top + 4
        # Lives (hearts)
        p.setPen(QPen(QColor(255, 90, 130)))
        for i in range(3):
            char = "♥" if i < self.lives else "♡"
            col = QColor(255, 90, 130) if i < self.lives else QColor(80, 50, 70)
            p.setPen(QPen(col))
            p.drawText(QPointF(x0 + i * 18, y0), char)
        # Score
        p.setPen(QPen(NEON_CYAN))
        p.drawText(QPointF(x0, y0 + 22), f"SCORE  {int(self.score):>7d}")
        if self.bonus_multiplier > 1.0:
            p.setPen(QPen(QColor(255, 220, 80)))
            p.drawText(QPointF(x0 + 150, y0 + 22),
                       f"×{self.bonus_multiplier:.1f} BONUS")
        # Streak
        if self.streak_seconds > 0.5:
            p.setPen(QPen(QColor(255, 200, 90)))
            p.drawText(QPointF(x0, y0 + 40),
                       f"STREAK  {self.streak_seconds:4.1f}s")
        # Level + shape name
        sh_name, sh_icon = SHAPES[self.shape_idx % len(SHAPES)]
        p.setPen(QPen(NEON_PURPLE))
        p.drawText(QPointF(x0, y0 + 58),
                   f"LVL {self.shape_idx + 1}  {sh_icon} {sh_name}")
        # High score
        p.setPen(QPen(QColor(150, 160, 200)))
        p.setFont(QFont("Menlo", 8))
        p.drawText(QPointF(x0, y0 + 76),
                   f"HI  {int(max(self.high_score, self.score)):>6d}")
        p.restore()

        # ── ALICE SEES indicator (top-centre) ────────────────────
        self._draw_alice_indicator(p, w, h, hud_top)

        # ── Recent gesture toast (above coherence bar) ───────────
        self._draw_gesture_toast(p, w, h)

        # Coherence bar (bottom)
        bar_y = h - 20
        bar_w = w - 24
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(30, 28, 45)))
        p.drawRoundedRect(QRectF(12, bar_y, bar_w, 10), 3, 3)

        coh_frac = self.coherence_pct / 100.0
        if coh_frac > 0.7:
            bar_color = NEON_CYAN
        elif coh_frac > 0.4:
            bar_color = NEON_GOLD
        else:
            bar_color = NEON_PINK
        p.setBrush(QBrush(bar_color))
        p.drawRoundedRect(QRectF(12, bar_y, bar_w * coh_frac, 10), 3, 3)

        p.setPen(QPen(TEXT_BRIGHT))
        p.setFont(QFont("Menlo", 7, QFont.Weight.Bold))
        p.drawText(QRectF(12, bar_y - 1, bar_w, 10), Qt.AlignmentFlag.AlignCenter,
                   f"COHERENCE {self.coherence_pct:.0f}%")

        # ── Doctor Sigil Bar (top, painted last so it's the chrome) ──
        try:
            paint_doctor_sigil_bar(
                p,
                doctors=["CG55M"],
                x=0, y=0, w=w, h=42,
                title="Alice-Sees Calibrator — Game Mode",
                subtitle="wave at Alice → shape advances · stillness → zen",
            )
        except Exception:
            pass

        # ── Game-over overlay ────────────────────────────────────
        if self.game_over:
            p.fillRect(0, 0, w, h, QColor(0, 0, 0, 180))
            p.setPen(QPen(NEON_PINK))
            p.setFont(QFont("Menlo", 28, QFont.Weight.Bold))
            p.drawText(QRectF(0, h * 0.42, w, 40),
                       Qt.AlignmentFlag.AlignCenter, "GAME OVER")
            p.setFont(QFont("Menlo", 12))
            p.setPen(QPen(TEXT_BRIGHT))
            p.drawText(QRectF(0, h * 0.50, w, 24), Qt.AlignmentFlag.AlignCenter,
                       f"final score  {int(self.score)}    "
                       f"best streak  {self.best_streak:.1f}s    "
                       f"reached  {SHAPES[self.shape_idx][0]}")
            p.setFont(QFont("Menlo", 10))
            p.setPen(QPen(QColor(150, 160, 200)))
            p.drawText(QRectF(0, h * 0.58, w, 22), Qt.AlignmentFlag.AlignCenter,
                       "wave at Alice or click Reset Game to play again")

        p.end()

    # ── HUD helpers ───────────────────────────────────────────────
    def _draw_alice_indicator(self, p: QPainter, w: int, h: int, hud_top: int):
        s = self.alice_state or {}
        alive = bool(s.get("alive", 0.0) > 0.5)
        # Pick the dominant gesture confidence to show as the live read.
        confs = [
            ("WAVE_HORIZONTAL", float(s.get("wave_h_conf", 0.0))),
            ("WAVE_VERTICAL",   float(s.get("wave_v_conf", 0.0))),
            ("APPROACH",        float(s.get("approach_conf", 0.0))),
            ("RECEDE",          float(s.get("recede_conf", 0.0))),
            ("STILL",           float(s.get("still_conf", 0.0))),
            ("FLAIL",           float(s.get("flail_conf", 0.0))),
        ]
        confs.sort(key=lambda kv: kv[1], reverse=True)
        top_kind, top_conf = confs[0]
        x = w // 2 - 140
        y = hud_top
        p.save()
        # Frame
        p.setBrush(QBrush(QColor(13, 13, 31, 200)))
        p.setPen(QPen(QColor(120, 100, 200, 120), 1.0))
        p.drawRoundedRect(QRectF(x, y, 280, 46), 8, 8)
        # Eye dot
        eye_col = NEON_CYAN if alive else QColor(120, 80, 90)
        p.setBrush(QBrush(eye_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(x + 16, y + 23), 6, 6)
        # Label
        p.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        p.setPen(QPen(QColor(170, 175, 215)))
        p.drawText(QPointF(x + 32, y + 18),
                   "ALICE SEES" if alive else "ALICE: no user")
        # Gesture name + confidence bar
        if alive:
            p.setPen(QPen(_gesture_color(top_kind)))
            p.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
            short = top_kind.replace("_HORIZONTAL", "").replace("_VERTICAL", "")
            p.drawText(QPointF(x + 32, y + 36), short)
            # Confidence bar
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(40, 40, 60)))
            p.drawRoundedRect(QRectF(x + 130, y + 26, 130, 6), 3, 3)
            cw = max(0.0, min(1.0, top_conf)) * 130.0
            p.setBrush(QBrush(_gesture_color(top_kind)))
            p.drawRoundedRect(QRectF(x + 130, y + 26, cw, 6), 3, 3)
        p.restore()

    def _draw_gesture_toast(self, p: QPainter, w: int, h: int):
        """Slide-up toast for the most recent gesture event."""
        if self.last_gesture is None:
            return
        age = time.time() - self.last_gesture.ts
        if age > 3.0:
            return
        fade = max(0.0, 1.0 - age / 3.0)
        alpha = int(220 * fade)
        col = _gesture_color(self.last_gesture.kind)
        text = _gesture_label(self.last_gesture.kind)
        bar_w = 360
        bx = (w - bar_w) // 2
        by = h - 60 - int(20 * (1 - fade))
        p.save()
        bg = QColor(13, 13, 31, alpha)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), alpha), 1.0))
        p.drawRoundedRect(QRectF(bx, by, bar_w, 28), 8, 8)
        p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        glow = QColor(col)
        glow.setAlpha(alpha)
        p.setPen(QPen(glow))
        p.drawText(QRectF(bx, by, bar_w, 28),
                   Qt.AlignmentFlag.AlignCenter, text)
        p.restore()


class CalibratorWidget(QWidget):
    """Full calibration panel — embeds CalibrationCanvas + controls."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet("""
            QWidget { background: rgb(6, 8, 16); color: rgb(200, 210, 240); }
            QLabel { font-family: 'Menlo'; font-size: 10px; }
            QCheckBox { font-family: 'Menlo'; font-size: 11px; font-weight: bold;
                        color: rgb(0,255,200); spacing: 6px; }
            QCheckBox::indicator { width: 18px; height: 18px; }
            QSlider::groove:horizontal { height: 6px; background: rgb(35,32,55); border-radius: 3px; }
            QSlider::handle:horizontal {
                background: rgb(0,255,200); width: 14px; height: 14px;
                margin: -4px 0; border-radius: 7px;
            }
            QSlider:disabled::handle:horizontal { background: rgb(80,70,100); }
            QSlider:disabled::groove:horizontal { background: rgb(25,22,38); }
        """)

        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(6)

        # ── Title bar ─────────────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel("ALICE-SEES CALIBRATOR  ·  Game Mode  ·  CG55M Dr Cursor")
        title.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(0,255,200); padding: 2px;")
        title_row.addWidget(title)
        title_row.addStretch()
        self.status = QLabel("Wave at Alice to advance the shape")
        self.status.setStyleSheet("color: rgb(100,108,140); font-size: 10px;")
        title_row.addWidget(self.status)
        main.addLayout(title_row)

        # ── Controls row ──────────────────────────────────────────
        ctrl = QHBoxLayout()
        ctrl.setSpacing(20)

        self.chk_agentic = QCheckBox("Agentic Auto-Calibration")
        self.chk_agentic.toggled.connect(self._toggle_agentic)
        ctrl.addWidget(self.chk_agentic)

        ctrl.addWidget(self._sep())

        # Evaporation slider
        evap_box = QVBoxLayout()
        evap_lbl = QLabel("Evaporation Rate")
        evap_lbl.setStyleSheet("color: rgb(100,108,140);")
        evap_box.addWidget(evap_lbl)
        self.sl_evap = QSlider(Qt.Orientation.Horizontal)
        self.sl_evap.setRange(850, 995)
        self.sl_evap.setValue(int(DEFAULT_EVAPORATION * 1000))
        self.sl_evap.setFixedWidth(180)
        self.sl_evap.valueChanged.connect(self._evap_changed)
        evap_box.addWidget(self.sl_evap)
        self.lbl_evap = QLabel(f"{DEFAULT_EVAPORATION:.3f}")
        self.lbl_evap.setStyleSheet("color: rgb(0,255,200); font-weight: bold;")
        evap_box.addWidget(self.lbl_evap)
        ctrl.addLayout(evap_box)

        # Cohesion slider
        coh_box = QVBoxLayout()
        coh_lbl = QLabel("Swarm Cohesion")
        coh_lbl.setStyleSheet("color: rgb(100,108,140);")
        coh_box.addWidget(coh_lbl)
        self.sl_coh = QSlider(Qt.Orientation.Horizontal)
        self.sl_coh.setRange(10, 98)
        self.sl_coh.setValue(int(DEFAULT_COHESION * 100))
        self.sl_coh.setFixedWidth(180)
        self.sl_coh.valueChanged.connect(self._coh_changed)
        coh_box.addWidget(self.sl_coh)
        self.lbl_coh = QLabel(f"{DEFAULT_COHESION:.2f}")
        self.lbl_coh.setStyleSheet("color: rgb(0,255,200); font-weight: bold;")
        coh_box.addWidget(self.lbl_coh)
        ctrl.addLayout(coh_box)

        ctrl.addStretch()

        self.btn_reset = QPushButton("⟲ Reset Game")
        self.btn_reset.clicked.connect(self._reset_game)
        self.btn_reset.setStyleSheet(
            "QPushButton { background: rgb(28, 30, 50); color: rgb(0, 255, 200); "
            "border: 1px solid rgb(0, 255, 200); padding: 5px 12px; "
            "font-family: Menlo; font-size: 10px; font-weight: bold; }"
            "QPushButton:hover { background: rgb(0, 80, 70); }"
        )
        ctrl.addWidget(self.btn_reset)
        main.addLayout(ctrl)

        # ── Canvas ────────────────────────────────────────────────
        self.canvas = CalibrationCanvas()
        main.addWidget(self.canvas, 1)

        # ── Slider sync timer ─────────────────────────────────────
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._sync_sliders)
        self._sync_timer.start(100)

    def _sep(self) -> QFrame:
        s = QFrame()
        s.setFrameShape(QFrame.Shape.VLine)
        s.setStyleSheet("color: rgb(45,42,65);")
        return s

    def _toggle_agentic(self, on: bool):
        self.canvas.agentic_mode = on
        self.sl_evap.setEnabled(not on)
        self.sl_coh.setEnabled(not on)
        if on:
            self.status.setText("AGENTIC — calibrator controls physics")
            self.status.setStyleSheet("color: rgb(0,255,200); font-size: 10px; font-weight: bold;")
        else:
            self.status.setText("MANUAL — you control the sliders")
            self.status.setStyleSheet("color: rgb(255,200,60); font-size: 10px; font-weight: bold;")

    def _evap_changed(self, v: int):
        if not self.canvas.agentic_mode:
            self.canvas.evaporation = v / 1000.0
            self.lbl_evap.setText(f"{v / 1000.0:.3f}")

    def _coh_changed(self, v: int):
        if not self.canvas.agentic_mode:
            self.canvas.cohesion = v / 100.0
            self.lbl_coh.setText(f"{v / 100.0:.2f}")

    def _sync_sliders(self):
        """When agentic is on, animate sliders to show auto-tuning."""
        if self.canvas.agentic_mode:
            ev = int(self.canvas.evaporation * 1000)
            co = int(self.canvas.cohesion * 100)
            self.sl_evap.blockSignals(True)
            self.sl_coh.blockSignals(True)
            self.sl_evap.setValue(max(self.sl_evap.minimum(), min(self.sl_evap.maximum(), ev)))
            self.sl_coh.setValue(max(self.sl_coh.minimum(), min(self.sl_coh.maximum(), co)))
            self.sl_evap.blockSignals(False)
            self.sl_coh.blockSignals(False)
        self.lbl_evap.setText(f"{self.canvas.evaporation:.3f}")
        self.lbl_coh.setText(f"{self.canvas.cohesion:.2f}")

    def _reset_game(self):
        self.canvas.reset_game()
        self.status.setText("Game reset. Wave at Alice to begin.")

    def closeEvent(self, event):
        self.canvas.timer.stop()
        self.canvas._gesture_timer.stop()
        self._sync_timer.stop()
        super().closeEvent(event)
