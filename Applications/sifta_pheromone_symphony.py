#!/usr/bin/env python3
"""
sifta_pheromone_symphony.py - Stigmergic Music Generator
═══════════════════════════════════════════════════════════════════════════════
Simulation: 500 agents drop .scar “notes” while moving.
The canvas becomes a living musical score where pheromone concentration = pitch,
decay rate = tempo.

Global Cognitive Interface integration: As the user chats with the swarm,
the "Stigmergic Heat" multiplier spikes, making the music dynamic.
"""
from __future__ import annotations

import sys
import math
import wave
import struct
import tempfile
import random
import os
from pathlib import Path
from typing import List, Dict

import time
from collections import deque
from typing import Deque, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont,
    QLinearGradient, QRadialGradient,
    QHideEvent, QShowEvent,
)
from PyQt6.QtMultimedia import QSoundEffect

# Ensure System imports work
_APP_DIR = Path(__file__).resolve().parent
_REPO = _APP_DIR.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from System.sifta_base_widget import SiftaBaseWidget

# ── Doctor sigil chrome (canonical Applications/_doctor_sigil_chrome) ─
try:
    from _doctor_sigil_chrome import paint_doctor_sigil_bar
    _HAS_SIGIL = True
except Exception:
    _HAS_SIGIL = False

# ── Audio Synthesizer ───────────────────────────────────────────────────────

NOTES = [
    261.63,  # C4
    293.66,  # D4
    329.63,  # E4
    349.23,  # F4
    392.00,  # G4
    440.00,  # A4
    493.88,  # B4
    523.25,  # C5
    587.33,  # D5
    659.25,  # E5
    698.46,  # F5
    783.99,  # G5
    880.00,  # A5
    987.77   # B5
]

DIATONIC_SCALE = [
    (0, "C4"), (1, "D4"), (2, "E4"), (3, "F4"), (4, "G4"), (5, "A4"), (6, "B4"),
    (7, "C5"), (8, "D5"), (9, "E5"), (10, "F5"), (11, "G5"), (12, "A5"), (13, "B5")
]

def synthesize_audio() -> str:
    """Generates 14 pure sine wave notes in a temporary directory, returning the path."""
    tmpdir = Path(tempfile.gettempdir()) / "sifta_audio"
    tmpdir.mkdir(exist_ok=True)
    
    sample_rate = 44100
    duration = 1.0  # 1 second notes
    
    for idx, (note_idx, name) in enumerate(DIATONIC_SCALE):
        freq = NOTES[note_idx]
        wav_path = tmpdir / f"note_{idx}.wav"
        if not wav_path.exists():
            obj = wave.open(str(wav_path), 'w')
            obj.setnchannels(1)
            obj.setsampwidth(2)
            obj.setframerate(sample_rate)
            
            # Envelope: fast attack, exponential decay for a "chime/plucking" sound
            frames = []
            for i in range(int(sample_rate * duration)):
                t = i / sample_rate
                # Envelope calculation
                if t < 0.05:
                    envelope = t / 0.05 # Attack
                else:
                    envelope = math.exp(-(t - 0.05) * 4) # Decay (factor 4 makes it fade in ~1s)
                
                val = math.sin(2.0 * math.pi * freq * t) * envelope
                # Soft clipping/saturation for organic warmth
                val = math.tanh(val * 1.5)
                # 16-bit PCM format
                packed_value = struct.pack('<h', int(val * 32767.0 * 0.7)) # 0.7 master volume
                frames.append(packed_value)
                
            obj.writeframes(b''.join(frames))
            obj.close()
            
    return str(tmpdir)


# ── Symphony Canvas (Physics Engine) ────────────────────────────────────────

class SwimmerAgent:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-1, 1)
        self.vy = random.uniform(-1, 1)

_NOTE_NAMES = [
    "C4", "D4", "E4", "F4", "G4", "A4", "B4",
    "C5", "D5", "E5", "F5", "G5", "A5", "B5",
]
_TONIC_INDICES = {0, 7}  # C4, C5 — accent these on the staff

# Cinematic palette tuned to match the rest of the polished SIFTA OS apps.
_BG_DEEP   = QColor(2, 4, 14)
_BG_DARK   = QColor(10, 14, 28)
_STAFF     = QColor(110, 130, 200, 26)
_TONIC     = QColor(168, 107, 255, 60)
_BARLINE   = QColor(255, 255, 255, 14)
_NOTE_COOL = QColor(0, 220, 255)     # low-intensity living note
_NOTE_HOT  = QColor(160, 240, 255)   # hot living note
_FOSSIL    = QColor(255, 215, 100)   # immune fossil note (Mozart)
_FOSSIL_HALO = QColor(255, 200, 80)
_SWEEP_CORE = QColor(255, 220, 200)
_SWEEP_HALO = QColor(255, 158, 100)


class SymphonyCanvas(QWidget):
    def __init__(self, notes_dir: str):
        super().__init__()
        self.grid_w = 120
        self.grid_h = 80
        self.cell_sz = 6

        self.setMinimumSize(self.grid_w * self.cell_sz, self.grid_h * self.cell_sz)

        # Pheromone matrix [x][y]
        self.pheromones = [[0.0 for _ in range(self.grid_h)] for _ in range(self.grid_w)]
        self.agents = [SwimmerAgent(random.uniform(0, self.grid_w-1), random.uniform(0, self.grid_h-1)) for _ in range(300)]

        self.playhead = 0
        self.heat = 1.0 # 1.0 = normal, spikes to 3.0+ when chatting

        # Visual feedback ledger: ringed feedback for the last N triggered
        # notes (column, bucket_y, t_start, intensity). The ring expands
        # and fades over ~600ms — it gives the canvas the feel of a real
        # instrument that you can SEE strike each note.
        self._trigger_rings: Deque[Tuple[int, int, float, float]] = deque(maxlen=64)
        # Birth time for the gentle intro fade-in.
        self._birth_ts = time.time()
        # Subtle sweep afterglow: store the last few playhead X positions
        # so the active scan line trails a soft luminescence.
        self._sweep_trail: Deque[int] = deque(maxlen=10)

        # Audio Initialization
        self.sounds: List[QSoundEffect] = []
        for i in range(14):
            snd = QSoundEffect(self)
            snd.setSource(QUrl.fromLocalFile(os.path.join(notes_dir, f"note_{i}.wav")))
            self.sounds.append(snd)

        # Update timer (not registered on SiftaBaseWidget — must stop in stop_all())
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)  # 50ms tick

    def stop_all(self) -> None:
        """Stop physics tick and all QSoundEffect instances (close/tab must silence audio)."""
        self.timer.stop()
        for s in self.sounds:
            s.stop()

    def hideEvent(self, event: QHideEvent) -> None:
        # MDI subwindow close hides children without always sending closeEvent to the app widget.
        super().hideEvent(event)
        if self.isHidden():
            self.stop_all()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # Restore tick after minimize (close destroys the widget — no second show).
        if self.isVisible() and not self.timer.isActive():
            self.timer.start(50)

    def tick(self):
        # 1. Decay Heat
        self.heat = max(1.0, self.heat * 0.95)
        
        # 2. Physics & Pheromone Drop
        speed_mult = 0.5 * self.heat
        drop_chance = 0.02 * self.heat
        
        for a in self.agents:
            a.x += a.vx * speed_mult
            a.y += a.vy * speed_mult
            
            # Wall bounce
            if a.x <= 0 or a.x >= self.grid_w - 1:
                a.vx *= -1
                a.x = max(0, min(self.grid_w - 1, a.x))
            if a.y <= 0 or a.y >= self.grid_h - 1:
                a.vy *= -1
                a.y = max(0, min(self.grid_h - 1, a.y))
                
            # Random perturb
            a.vx += random.uniform(-0.1, 0.1) * self.heat
            a.vy += random.uniform(-0.1, 0.1) * self.heat
            
            # Normalize vector
            length = math.sqrt(a.vx**2 + a.vy**2)
            if length > 0:
                a.vx /= length
                a.vy /= length
                
            # Drop pheromone
            if random.random() < drop_chance:
                gx, gy = int(a.x), int(a.y)
                self.pheromones[gx][gy] = min(1.0, self.pheromones[gx][gy] + 0.3)
                
        # 3. Pheromone Decay (Fossils >= 5.0 are immune)
        for x in range(self.grid_w):
            for y in range(self.grid_h):
                val = self.pheromones[x][y]
                if val > 0 and val < 5.0:
                    self.pheromones[x][y] *= 0.96 # Exponential decay
                    if self.pheromones[x][y] < 0.01:
                        self.pheromones[x][y] = 0.0
                        
        # 4. Playhead Advance & Audio Trigger
        old_playhead = self.playhead
        self.playhead = (self.playhead + 1) % self.grid_w
        self._sweep_trail.append(self.playhead)

        # Scan vertical column at new playhead
        self.scan_and_play(self.playhead)

        self.update()
        
    def scan_and_play(self, x_idx: int):
        column = self.pheromones[x_idx]
        bucket_size = self.grid_h / 14.0
        
        buckets = [0.0] * 14
        for y, val in enumerate(column):
            if val > 0:
                b_idx = min(13, int(y / bucket_size))
                buckets[b_idx] += val
                
        for i, val in enumerate(buckets):
            if val > 0.4:  # Threshold to trigger note
                vol = float(min(1.0, val * 0.5))
                # Ensure it restarts if already playing to allow rapid hits
                if self.sounds[i].isPlaying():
                    self.sounds[i].stop()
                self.sounds[i].setVolume(vol)
                self.sounds[i].play()
                # Feed the visual feedback ledger so we can ring the
                # cell that just made noise.
                bucket_size = self.grid_h / 14.0
                bucket_y = int((i + 0.5) * bucket_size)
                self._trigger_rings.append(
                    (x_idx, bucket_y, time.time(), vol)
                )

    def load_fossil_score(self, score_data: List[tuple]):
        """Load permanent pheromone scars that do not decay."""
        bucket_size = self.grid_h / 14.0
        # Wipe the biological memory
        self.pheromones = [[0.0 for _ in range(self.grid_h)] for _ in range(self.grid_w)]
        
        for x_start, x_end, note_idx in score_data:
            # Drop Y coordinate right in the middle of the pitch bucket
            y_center = int((note_idx + 0.5) * bucket_size)
            for x in range(int(x_start), int(x_end)):
                if 0 <= x < self.grid_w and 0 <= y_center < self.grid_h:
                    self.pheromones[x][y_center] = 5.0 # FOSSIL MARKER

    # ── Cinematic paint pipeline (Opus 4.7 / CG55M graphics polish) ────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        self._paint_background(painter)
        self._paint_pheromones(painter)
        self._paint_trigger_rings(painter)
        self._paint_agents(painter)
        self._paint_playhead(painter)
        self._paint_pitch_ladder(painter)
        self._paint_doctor_sigil(painter)
        self._paint_intro_fade(painter)

    # Sub-passes ---------------------------------------------------------

    def _paint_background(self, p: QPainter) -> None:
        """Deep depth gradient + faint pitch staff lines + bar lines."""
        rect = self.rect()
        grad = QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0.0, _BG_DEEP)
        grad.setColorAt(0.55, _BG_DARK)
        grad.setColorAt(1.0, _BG_DEEP)
        p.fillRect(rect, QBrush(grad))

        # Pitch staff lines: one horizontal line per note bucket. Tonic
        # bands (C4, C5) get a slightly stronger purple tint so the staff
        # reads as a music-paper surface, not a generic grid.
        bucket_size = self.grid_h / 14.0
        for i in range(14):
            y = int((i + 0.5) * bucket_size) * self.cell_sz
            colour = _TONIC if i in _TONIC_INDICES else _STAFF
            p.setPen(QPen(colour, 1))
            p.drawLine(0, y, rect.width(), y)

        # Bar lines: one every 8 grid cells, very faint, give a
        # "measure" feel without being a hard grid.
        p.setPen(QPen(_BARLINE, 1))
        x = 0
        while x < rect.width():
            p.drawLine(x, 0, x, rect.height())
            x += 8 * self.cell_sz

    def _paint_pheromones(self, p: QPainter) -> None:
        """Soft glowing notes (living + fossil) instead of flat fillRects."""
        cell = self.cell_sz
        # Use additive composition so overlapping bright cells bloom.
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.setPen(Qt.PenStyle.NoPen)

        for x in range(self.grid_w):
            col = self.pheromones[x]
            for y in range(self.grid_h):
                val = col[y]
                if val <= 0:
                    continue
                cx = x * cell + cell / 2
                cy = y * cell + cell / 2
                if val >= 5.0:
                    # Fossil: bright golden bead with halo.
                    halo = QRadialGradient(QPointF(cx, cy), cell * 2.4)
                    halo.setColorAt(0.0, QColor(_FOSSIL_HALO.red(),
                                                _FOSSIL_HALO.green(),
                                                _FOSSIL_HALO.blue(), 180))
                    halo.setColorAt(1.0, QColor(0, 0, 0, 0))
                    p.setBrush(QBrush(halo))
                    p.drawEllipse(QPointF(cx, cy), cell * 2.4, cell * 2.4)
                    p.setBrush(QBrush(_FOSSIL))
                    p.drawEllipse(QPointF(cx, cy), cell * 0.55, cell * 0.55)
                else:
                    # Living note: cyan-white core scaled by intensity.
                    intensity = min(1.0, val)
                    halo_r = cell * (1.0 + 1.6 * intensity)
                    halo = QRadialGradient(QPointF(cx, cy), halo_r)
                    a_inner = int(180 * intensity)
                    halo.setColorAt(0.0, QColor(_NOTE_HOT.red(),
                                                _NOTE_HOT.green(),
                                                _NOTE_HOT.blue(), a_inner))
                    halo.setColorAt(0.45, QColor(_NOTE_COOL.red(),
                                                 _NOTE_COOL.green(),
                                                 _NOTE_COOL.blue(),
                                                 int(110 * intensity)))
                    halo.setColorAt(1.0, QColor(0, 0, 0, 0))
                    p.setBrush(QBrush(halo))
                    p.drawEllipse(QPointF(cx, cy), halo_r, halo_r)

        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    def _paint_trigger_rings(self, p: QPainter) -> None:
        """Expanding rings on cells that just played a note (last ~600ms)."""
        if not self._trigger_rings:
            return
        now = time.time()
        live = []
        cell = self.cell_sz
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for x_idx, y_idx, t_start, vol in self._trigger_rings:
            age = now - t_start
            if age > 0.6:
                continue
            live.append((x_idx, y_idx, t_start, vol))
            life = age / 0.6  # 0 → 1
            r = cell * (1.5 + 4.5 * life)
            alpha = int(180 * (1.0 - life) * (0.5 + 0.5 * vol))
            cx = x_idx * cell + cell / 2
            cy = y_idx * cell + cell / 2
            pen = QPen(QColor(255, 220, 200, alpha), 1.6)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        # GC the dead rings.
        self._trigger_rings = deque(live, maxlen=64)

    def _paint_agents(self, p: QPainter) -> None:
        """Agents as small luminous dots, color-modulated by heat."""
        # Heat shifts the swarm from cool blue (calm) to warm rose (chaos).
        heat_t = max(0.0, min(1.0, (self.heat - 1.0) / 4.0))
        r = int(100 + 150 * heat_t)
        g = int(108 + 30 * heat_t)
        b = int(220 - 100 * heat_t)
        col = QColor(r, g, b, 180)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(col))
        for a in self.agents:
            p.drawEllipse(QPointF(a.x * self.cell_sz, a.y * self.cell_sz),
                          1.6, 1.6)

    def _paint_playhead(self, p: QPainter) -> None:
        """Sweep playhead with afterglow trail and bright neon core."""
        h = self.height()
        # Afterglow: soft luminous trail from recent X positions.
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        n = len(self._sweep_trail)
        for i, x_idx in enumerate(list(self._sweep_trail)):
            x = x_idx * self.cell_sz
            alpha = int(60 * (i + 1) / max(n, 1))
            grad = QLinearGradient(x - 6, 0, x + 6, 0)
            grad.setColorAt(0.0, QColor(0, 0, 0, 0))
            grad.setColorAt(0.5, QColor(_SWEEP_HALO.red(),
                                         _SWEEP_HALO.green(),
                                         _SWEEP_HALO.blue(), alpha))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.fillRect(QRectF(x - 6, 0, 12, h), QBrush(grad))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # Core line: bright orange with a thin white inner stroke.
        x = self.playhead * self.cell_sz
        p.setPen(QPen(QColor(_SWEEP_HALO.red(),
                              _SWEEP_HALO.green(),
                              _SWEEP_HALO.blue(), 220), 2.2))
        p.drawLine(x, 0, x, h)
        p.setPen(QPen(QColor(_SWEEP_CORE.red(),
                              _SWEEP_CORE.green(),
                              _SWEEP_CORE.blue(), 230), 0.8))
        p.drawLine(x, 0, x, h)

    def _paint_pitch_ladder(self, p: QPainter) -> None:
        """Right-edge note ladder (C4..B5) like a piano-roll."""
        bucket_size = self.grid_h / 14.0
        right = self.width()
        # Frosted strip behind the labels.
        strip_w = 30
        p.fillRect(QRectF(right - strip_w, 0, strip_w, self.height()),
                   QColor(8, 10, 22, 140))
        font = QFont("SF Pro Text", 8)
        font.setBold(True)
        p.setFont(font)
        for i, name in enumerate(_NOTE_NAMES):
            y = int((i + 0.5) * bucket_size) * self.cell_sz
            colour = (QColor(255, 215, 100, 230)
                      if i in _TONIC_INDICES
                      else QColor(180, 200, 240, 160))
            p.setPen(QPen(colour))
            p.drawText(QRectF(right - strip_w + 2, y - 6, strip_w - 4, 12),
                       int(Qt.AlignmentFlag.AlignVCenter |
                           Qt.AlignmentFlag.AlignLeft),
                       name)

    def _paint_doctor_sigil(self, p: QPainter) -> None:
        """Doctor Sigil bar at the very top of the canvas."""
        if not _HAS_SIGIL:
            return
        try:
            paint_doctor_sigil_bar(
                p,
                rect=QRectF(0, 0, self.width(), 44),
                title="Pheromone Symphony",
                subtitle="Stigmergic music · Diatonic · GCI-modulated",
                doctor="CG55M",
                co_doctors=("AG31",),
                signature="CG55M-CURSOR-OPUS47",
            )
        except Exception:
            # Never let chrome break the live canvas.
            pass

    def _paint_intro_fade(self, p: QPainter) -> None:
        """Soft black overlay that fades out over the first ~1.2s of life."""
        age = time.time() - self._birth_ts
        if age >= 1.2:
            return
        alpha = int(210 * (1.0 - age / 1.2))
        p.fillRect(self.rect(), QColor(0, 0, 0, alpha))


# ── Main Application ─────────────────────────────────────────────────────────

_APP_QSS = """
QWidget#PheromoneRoot {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(6, 8, 18, 255),
        stop:1 rgba(2, 4, 14, 255));
}
QFrame#PheromoneToolbar {
    background: rgba(18, 22, 38, 220);
    border: 1px solid rgba(168, 107, 255, 60);
    border-radius: 14px;
}
QLabel#PheromoneHeat {
    color: rgb(0, 235, 220);
    font-family: "SF Pro Text", "Helvetica Neue", system-ui;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.5px;
    padding-left: 10px;
}
QLabel#PheromoneTagline {
    color: rgba(220, 230, 255, 170);
    font-family: "SF Pro Text", "Helvetica Neue", system-ui;
    font-size: 11px;
    letter-spacing: 0.6px;
    padding-right: 10px;
}
QPushButton#MozartBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 215, 100, 240),
        stop:1 rgba(220, 160, 60, 240));
    color: rgba(28, 18, 6, 255);
    border: 1px solid rgba(255, 230, 160, 200);
    border-radius: 9px;
    padding: 6px 14px;
    font-family: "SF Pro Text", "Helvetica Neue", system-ui;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#MozartBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 230, 140, 255),
        stop:1 rgba(235, 180, 80, 255));
}
QPushButton#MozartBtn:pressed {
    background: rgba(200, 150, 60, 240);
}
"""


class _HeatGauge(QWidget):
    """A slim animated horizontal gauge that mirrors stigmergic heat."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.heat = 1.0
        self.setFixedHeight(6)
        self.setMinimumWidth(120)

    def set_heat(self, h: float) -> None:
        self.heat = h
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        # Track.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(28, 32, 50, 200)))
        p.drawRoundedRect(rect, 3, 3)
        # Fill: how saturated the swarm is right now (1..6 range maps to 0..1).
        t = max(0.0, min(1.0, (self.heat - 1.0) / 5.0))
        if t <= 0:
            return
        fw = int(rect.width() * t)
        grad = QLinearGradient(0, 0, rect.width(), 0)
        grad.setColorAt(0.0, QColor(0, 220, 255, 230))
        grad.setColorAt(0.5, QColor(168, 107, 255, 230))
        grad.setColorAt(1.0, QColor(247, 118, 142, 240))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(QRectF(0, 0, fw, rect.height()), 3, 3)


class PheromoneSymphonyApp(SiftaBaseWidget):
    APP_NAME = "Pheromone Symphony"

    def build_ui(self, layout: QVBoxLayout) -> None:
        self.setObjectName("PheromoneRoot")
        self.setStyleSheet(_APP_QSS)
        self.set_status("Synthesizing audio nodes (Diatonic)...")

        # Generate audio files on boot.
        notes_dir = synthesize_audio()

        # Frosted toolbar containing a heat label, a slim heat gauge,
        # and the Mozart fossil button.
        toolbar = QFrame()
        toolbar.setObjectName("PheromoneToolbar")
        toolbar.setFrameShape(QFrame.Shape.NoFrame)
        bar_lay = QHBoxLayout(toolbar)
        bar_lay.setContentsMargins(12, 8, 12, 8)
        bar_lay.setSpacing(12)

        self.heat_label = QLabel("Stigmergic Heat · 1.0× · Ambient")
        self.heat_label.setObjectName("PheromoneHeat")
        bar_lay.addWidget(self.heat_label)

        self.heat_gauge = _HeatGauge()
        bar_lay.addWidget(self.heat_gauge, 1)

        tagline = QLabel("Pheromone density → pitch · 14-tone diatonic")
        tagline.setObjectName("PheromoneTagline")
        bar_lay.addWidget(tagline)

        btn_mozart = QPushButton("♪  Load Mozart K 545 Fossil")
        btn_mozart.setObjectName("MozartBtn")
        btn_mozart.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_mozart.clicked.connect(self.load_mozart)
        bar_lay.addWidget(btn_mozart)

        layout.addWidget(toolbar)

        self.canvas = SymphonyCanvas(notes_dir)
        layout.addWidget(self.canvas)

        self.set_status("Biology loaded. 300 Swimmers active. Audio synth OK.")

        # Hook into GCI (which SiftaBaseWidget injected as self._gci)
        if self._gci:
            self._gci.message_sent.connect(self.on_chat_activity)
            self._gci.response_received.connect(self.on_chat_activity)

        # UI update timer for heat label
        self.ui_timer = self.make_timer(100, self.update_heat_label)

    def load_mozart(self):
        # Mozart Sonata K 545 mapped to Diatonic X/Y coordinates
        # C5=7, E5=9, G5=11, B4=6, D5=8, A5=12, F5=10
        score = [
            (0, 8, 7),     # C5
            (10, 13, 9),   # E5
            (15, 18, 11),  # G5
            
            (20, 23, 6),   # B4
            (25, 27, 7),   # C5
            (28, 30, 8),   # D5
            (31, 38, 7),   # C5
            
            (40, 48, 12),  # A5
            (50, 53, 11),  # G5
            (55, 58, 7),   # C5
            
            (60, 63, 10),  # F5
            (65, 68, 9),   # E5
            (70, 78, 8),   # D5
            
            (80, 88, 7),   # C5
        ]
        self.canvas.load_fossil_score(score)
        self.set_status("Fossil Pheromones loaded: Mozart Sonata K 545.")
        
    def on_chat_activity(self, text: str):
        # Spike the heat when chat occurs
        # Longer message = more heat. At least 5x spike.
        added_heat = min(15.0, 5.0 + (len(text) / 20.0))
        self.canvas.heat = min(20.0, self.canvas.heat + added_heat)
        
    def update_heat_label(self):
        h = self.canvas.heat
        if h > 3.0:
            self.heat_label.setText(f"Stigmergic Heat · {h:.1f}× · Chaos")
            self.heat_label.setStyleSheet(
                "color: rgb(247, 118, 142); font-weight: 700; "
                "padding-left: 10px;"
            )
        elif h > 1.5:
            self.heat_label.setText(f"Stigmergic Heat · {h:.1f}× · Active")
            self.heat_label.setStyleSheet(
                "color: rgb(255, 184, 110); font-weight: 700; "
                "padding-left: 10px;"
            )
        else:
            self.heat_label.setText(f"Stigmergic Heat · {h:.1f}× · Ambient")
            self.heat_label.setStyleSheet(
                "color: rgb(0, 235, 220); font-weight: 600; "
                "padding-left: 10px;"
            )
        self.heat_gauge.set_heat(h)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        # GCI hooks keep firing heat if we stay connected after close; audio must stop first.
        if self._gci:
            try:
                self._gci.message_sent.disconnect(self.on_chat_activity)
            except TypeError:
                pass
            try:
                self._gci.response_received.disconnect(self.on_chat_activity)
            except TypeError:
                pass
        if getattr(self, "canvas", None):
            self.canvas.stop_all()
        super().closeEvent(event)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = PheromoneSymphonyApp()
    window.resize(1000, 600)
    window.show()
    sys.exit(app.exec())
