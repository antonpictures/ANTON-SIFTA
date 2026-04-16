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

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer, QUrl, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen
from PyQt6.QtMultimedia import QSoundEffect

# Ensure System imports work
_APP_DIR = Path(__file__).resolve().parent
_REPO = _APP_DIR.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.sifta_base_widget import SiftaBaseWidget

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
        
        # Audio Initialization
        self.sounds: List[QSoundEffect] = []
        for i in range(14):
            snd = QSoundEffect(self)
            snd.setSource(QUrl.fromLocalFile(os.path.join(notes_dir, f"note_{i}.wav")))
            self.sounds.append(snd)
        
        # Update timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)  # 50ms tick
        
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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor(8, 10, 18))
        
        # Draw Pheromones
        for x in range(self.grid_w):
            for y in range(self.grid_h):
                val = self.pheromones[x][y]
                if val >= 5.0:
                    # Fossils are solid gold/yellow
                    painter.fillRect(x * self.cell_sz, y * self.cell_sz, self.cell_sz, self.cell_sz, QColor(255, 215, 0, 255))
                elif val > 0:
                    # Map to a fiery/cyber green based on intensity
                    r = int(val * 0)
                    g = int(val * 255)
                    b = int(val * 200)
                    painter.fillRect(x * self.cell_sz, y * self.cell_sz, self.cell_sz, self.cell_sz, QColor(r, g, b, int(val * 255)))
                    
        # Draw Agents
        painter.setPen(Qt.PenStyle.NoPen)
        for a in self.agents:
            painter.setBrush(QColor(100, 108, 140, 150))
            painter.drawEllipse(int(a.x * self.cell_sz), int(a.y * self.cell_sz), 3, 3)
            
        # Draw Playhead
        phead_x = self.playhead * self.cell_sz
        painter.setPen(QColor(255, 158, 100, 200)) # Orange
        painter.drawLine(phead_x, 0, phead_x, self.height())


# ── Main Application ─────────────────────────────────────────────────────────

class PheromoneSymphonyApp(SiftaBaseWidget):
    APP_NAME = "Pheromone Symphony"

    def build_ui(self, layout: QVBoxLayout) -> None:
        self.set_status("Synthesizing audio nodes (Diatonic)...")
        
        # Generate audio files on boot
        notes_dir = synthesize_audio()
        
        # Build UI
        top_bar = QHBoxLayout()
        self.heat_label = QLabel("Stigmergic Heat: 1.0x (Ambient)")
        self.heat_label.setStyleSheet("color: rgb(0, 255, 200); font-weight: bold;")
        top_bar.addWidget(self.heat_label)
        
        btn_mozart = QPushButton("Load Fossil Pheromones (Mozart K 545)")
        btn_mozart.clicked.connect(self.load_mozart)
        top_bar.addWidget(btn_mozart)
        
        top_bar.addStretch()
        layout.addLayout(top_bar)
        
        self.canvas = SymphonyCanvas(notes_dir)
        layout.addWidget(self.canvas)
        
        self.set_status(f"Biology loaded. 300 Swimmers active. Audio synth OK.")
        
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
            self.heat_label.setText(f"Stigmergic Heat: {h:.1f}x (CHAOS/INTENSE)")
            self.heat_label.setStyleSheet("color: rgb(247, 118, 142); font-weight: bold;")
        elif h > 1.5:
            self.heat_label.setText(f"Stigmergic Heat: {h:.1f}x (ACTIVE)")
            self.heat_label.setStyleSheet("color: rgb(255, 158, 100); font-weight: bold;")
        else:
            self.heat_label.setText(f"Stigmergic Heat: {h:.1f}x (AMBIENT)")
            self.heat_label.setStyleSheet("color: rgb(0, 255, 200); font-weight: bold;")


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = PheromoneSymphonyApp()
    window.resize(1000, 600)
    window.show()
    sys.exit(app.exec())
