#!/usr/bin/env python3
"""
sifta_calibrator_widget.py — Agentic Swarm Auto-Calibration Simulator
══════════════════════════════════════════════════════════════════════════
Inspired by NVIDIA Ising / Quantum Day 2025.

What NVIDIA does for quantum processor calibration (QPU gate-voltage
tuning via AI agents), this app does for Stigmergic Swarm physics.

The simulation renders:
  • A glowing geometric TARGET SHAPE (slowly rotating Lissajous star)
  • 200 swimmer agents that try to trace the target via pheromone trails
  • A 2D pheromone grid — target emits, agents deposit & follow
  • Periodic NOISE SPIKES that scatter agents and corrupt the grid
  • Two modes:
    - MANUAL: user adjusts Evaporation + Cohesion sliders by hand
    - AGENTIC: calibrator auto-moves sliders in real time (locked from user)
  • Telemetry HUD: Noise %, Coherence %, Calibrations/sec, Mode
  • S-Cal score: cumulative on-target time

The contrast between the two modes is the point: manual is chaos during
spikes, agentic is rock-solid — proving autonomous calibration works.

Embeds inside iSwarm OS MDI via NLEWidget pattern.
"""
from __future__ import annotations

import math
import random
import sys
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))

from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QHBoxLayout, QLabel, QSlider,
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

        # ── Target shape (Lissajous star vertices) ────────────────
        self.target_pts: List[Tuple[float, float]] = []
        self._target_angle = 0.0
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

        # ── Timer ─────────────────────────────────────────────────
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    def _rebuild_target(self):
        """Generate target shape: 5-petalled rose curve, centered on grid."""
        cx, cy = GRID_W / 2, GRID_H / 2
        r_base = min(GRID_W, GRID_H) * 0.32
        pts = []
        for i in range(360):
            theta = math.radians(i) + self._target_angle
            r = r_base * (0.6 + 0.4 * math.cos(5 * theta))
            pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
        self.target_pts = pts

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
        self._noise_timer += dt
        if not self._in_spike and self._noise_timer >= self._next_noise:
            self._in_spike = True
            self._spike_remaining = NOISE_DURATION
            self._noise_timer = 0.0
            self._next_noise = random.uniform(NOISE_INTERVAL_MIN, NOISE_INTERVAL_MAX)

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

            # Cohesion pull toward swarm centroid
            dx_c = cx_all - ag.x
            dy_c = cy_all - ag.y
            d_c = math.sqrt(dx_c ** 2 + dy_c ** 2) + 1e-6
            ag.vx += (dx_c / d_c) * self.cohesion * 0.3
            ag.vy += (dy_c / d_c) * self.cohesion * 0.3

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

        # ── HUD overlay ───────────────────────────────────────────
        p.setFont(QFont("Menlo", 9, QFont.Weight.Bold))

        # Top-left: mode badge
        mode_color = NEON_CYAN if self.agentic_mode else NEON_GOLD
        p.setPen(QPen(mode_color))
        badge = "AGENTIC AUTO-CAL" if self.agentic_mode else "MANUAL MODE"
        p.drawText(QPointF(12, 18), badge)

        # Top-right: telemetry
        p.setPen(QPen(TEXT_BRIGHT))
        p.setFont(QFont("Menlo", 8))
        telemetry_lines = [
            f"Noise: {self.noise_level * 100:.0f}%",
            f"Coherence: {self.coherence_pct:.1f}%",
            f"Cal/sec: {self.cal_per_sec:.1f}",
            f"Total Cal: {self.total_cal}",
            f"S-Cal: {self.scal_score:.1f}",
            f"Evap: {self.evaporation:.3f}",
            f"Cohesion: {self.cohesion:.3f}",
            f"Mode: {self.mode_label}",
        ]
        for i, line in enumerate(telemetry_lines):
            p.drawText(QPointF(w - 170, 18 + i * 14), line)

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

        p.end()


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
        title = QLabel("SIFTA AGENTIC CALIBRATOR — NVIDIA Ising Translation")
        title.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(0,255,200); padding: 2px;")
        title_row.addWidget(title)
        title_row.addStretch()
        self.status = QLabel("Ready")
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

    def closeEvent(self, event):
        self.canvas.timer.stop()
        self._sync_timer.stop()
        super().closeEvent(event)
