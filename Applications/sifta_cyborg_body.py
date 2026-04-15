#!/usr/bin/env python3
"""
SIFTA CYBORG BODY SIMULATOR — Swimmers Power the Machine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PyQt6 real-time visualization of a cyborg body where:
  • Swimmers patrol organ territories (heart, brain, cochlea, spine, NFC)
  • Each organ has real-science waveform rendering
  • Immune system intercepts unsigned/foreign swimmers
  • Territory defense: swimmers swarm hostile injections
  • STGM minted per organ regulation tick (proof of useful work)
  • Ed25519 signed actions — only registered silicon can tune organs

TERRITORY IS THE LAW. 🐜

Run:  python3 Applications/sifta_cyborg_body.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sys
import math
import time
import random
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "System"))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame, QSplitter,
    QSizePolicy, QGroupBox, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QRadialGradient,
    QLinearGradient, QPainterPath, QPolygonF
)
import numpy as np

# ── Antibody Ledger (persistent immune memory) ─────────────────────
try:
    from antibody_ledger import record_kill as _ab_record_kill
    from antibody_ledger import is_vaccinated as _ab_is_vaccinated
    from antibody_ledger import get_antibody_count as _ab_count
    _HAS_ANTIBODY = True
except ImportError:
    _HAS_ANTIBODY = False
    def _ab_record_kill(*a, **kw): return {}
    def _ab_is_vaccinated(*a, **kw): return False
    def _ab_count(): return 0

# ── Biopunk Palette ────────────────────────────────────────────────
C_VOID       = QColor(8, 10, 18)
C_FLESH      = QColor(35, 28, 38)
C_BONE       = QColor(55, 48, 60)
C_BLOOD      = QColor(220, 40, 60)
C_BLOOD_DIM  = QColor(120, 25, 35)
C_NERVE      = QColor(0, 255, 200)
C_NERVE_DIM  = QColor(0, 120, 90)
C_BRAIN      = QColor(200, 160, 255)
C_BRAIN_DIM  = QColor(90, 70, 130)
C_COCHLEA    = QColor(255, 200, 80)
C_NFC        = QColor(80, 200, 255)
C_SPINE      = QColor(180, 255, 180)
C_HOSTILE    = QColor(255, 0, 80)
C_IMMUNE     = QColor(255, 220, 0)
C_TEXT       = QColor(200, 210, 240)
C_TEXT_DIM   = QColor(100, 105, 130)
C_STGM_GLOW = QColor(0, 255, 128)
C_TERRITORY  = QColor(255, 255, 255, 25)
C_REJECT_RED = QColor(255, 50, 50)
C_ACCEPT_GRN = QColor(50, 255, 120)
C_BCI_INTENT = QColor(255, 180, 255)     # BCI decoded intent pink-lavender
C_BCI_CLUSTER = QColor(255, 100, 220)    # BCI cluster hotspot

# ── BCI Intent Labels (emerge from pattern clustering) ─────────────
BCI_INTENT_LABELS = [
    "FOCUS", "CALM", "MOTOR_L", "MOTOR_R", "RECALL",
    "ALERT", "CREATIVE", "SLEEP", "PAIN", "JOY",
    "ANGER", "CURIOSITY",
]


# ═══════════════════════════════════════════════════════════════════
#  ORGAN TERRITORIES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OrganTerritory:
    """An organ region in the cyborg body. TERRITORY IS THE LAW."""
    name: str
    cx: float        # center x (fraction 0-1)
    cy: float        # center y (fraction 0-1)
    radius: float    # territory radius (fraction)
    color: QColor
    bpm: float = 72.0        # heart
    gain_db: float = 12.0    # cochlea
    neural_rate: float = 40.0  # brain (Hz)
    spine_signal: float = 0.8  # spine integrity
    nfc_level: str = "LOW"   # NFC access
    health: float = 1.0
    under_attack: bool = False
    stgm_earned: float = 0.0


@dataclass
class CyborgSwimmer:
    """A swimmer agent patrolling inside the cyborg body."""
    sid: str
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    home_organ: str = ""
    state: str = "PATROL"    # PATROL, TUNE, DEFEND, RETURN
    color: QColor = field(default_factory=lambda: C_NERVE)
    trail: list = field(default_factory=list)
    energy: float = 100.0
    stgm_earned: float = 0.0
    tune_cooldown: float = 0.0
    signed: bool = True      # Ed25519 verified


@dataclass
class HostileAgent:
    """An unsigned/foreign swimmer attempting organ access."""
    x: float
    y: float
    target_organ: str
    payload: str
    alive: bool = True
    pulse: float = 0.0
    age: float = 0.0


# ═══════════════════════════════════════════════════════════════════
#  WAVEFORM GENERATORS (real science)
# ═══════════════════════════════════════════════════════════════════

def ecg_waveform(t: float, bpm: float) -> float:
    """Realistic ECG PQRST waveform using superposed Gaussians."""
    period = 60.0 / max(bpm, 30)
    phase = (t % period) / period  # 0 to 1

    # P wave (atrial depolarization)
    p = 0.15 * math.exp(-((phase - 0.10) ** 2) / (2 * 0.008))
    # Q dip
    q = -0.08 * math.exp(-((phase - 0.18) ** 2) / (2 * 0.002))
    # R spike (ventricular depolarization — the big one)
    r = 1.0 * math.exp(-((phase - 0.22) ** 2) / (2 * 0.001))
    # S dip
    s = -0.15 * math.exp(-((phase - 0.26) ** 2) / (2 * 0.002))
    # T wave (ventricular repolarization)
    tw = 0.25 * math.exp(-((phase - 0.40) ** 2) / (2 * 0.012))

    return p + q + r + s + tw


def neural_spike_train(t: float, rate_hz: float) -> float:
    """Stochastic neural spike train — Poisson-like bursts."""
    base = math.sin(t * rate_hz * 0.3) * 0.15
    spike = 0.0
    for harmonic in range(1, 5):
        freq = rate_hz * harmonic * 0.7
        spike += (0.8 / harmonic) * max(0, math.sin(t * freq * 2 * math.pi))
    # Random burst noise
    noise = random.gauss(0, 0.05) if random.random() < 0.3 else 0
    return base + spike * 0.4 + noise


def cochlear_spectrum(t: float, gain_db: float) -> List[float]:
    """Frequency band powers — simulates cochlear hair cell response."""
    bands = []
    for i in range(16):
        freq = 250 * (2 ** (i / 3))  # 250 Hz to ~16 kHz
        amplitude = gain_db / 20.0 * math.exp(-abs(i - 8 + math.sin(t * 0.5) * 3) * 0.15)
        amplitude += random.gauss(0, 0.03)
        bands.append(max(0, min(1, amplitude)))
    return bands


def spinal_signal(t: float, integrity: float) -> float:
    """Spinal cord nerve conduction — clean sine if healthy, noisy if degraded."""
    base = math.sin(t * 12) * integrity
    noise = random.gauss(0, 0.1 * (1.0 - integrity))
    return base + noise


# ═══════════════════════════════════════════════════════════════════
#  CYBORG CANVAS
# ═══════════════════════════════════════════════════════════════════

class CyborgCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(950, 650)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── Organs ────────────────────────────────────────────────
        self.organs: Dict[str, OrganTerritory] = {
            "brain":     OrganTerritory("brain",     0.50, 0.12, 0.10, C_BRAIN),
            "cochlea_l": OrganTerritory("cochlea_l", 0.36, 0.14, 0.05, C_COCHLEA),
            "cochlea_r": OrganTerritory("cochlea_r", 0.64, 0.14, 0.05, C_COCHLEA),
            "heart":     OrganTerritory("heart",     0.45, 0.35, 0.08, C_BLOOD),
            "spine":     OrganTerritory("spine",     0.50, 0.55, 0.06, C_SPINE),
            "nfc":       OrganTerritory("nfc",       0.62, 0.28, 0.05, C_NFC),
        }

        # ── Swimmers ──────────────────────────────────────────────
        self.swimmers: List[CyborgSwimmer] = []
        self.hostiles: List[HostileAgent] = []

        self.swimmer_names = [
            "HERMES", "ANTIALICE", "M1QUEEN", "M1THER",
            "OPENCLAW", "ALICE_M5", "REPAIR-DRONE", "SEBASTIAN",
        ]

        # ── Waveform histories ────────────────────────────────────
        self.ecg_history: List[float] = [0.0] * 300
        self.neural_history: List[float] = [0.0] * 300
        self.spinal_history: List[float] = [0.0] * 300
        self.cochlear_bands: List[float] = [0.0] * 16
        self.bci_decoded_history: List[float] = [0.0] * 300

        # ── BCI Intent Map (stigmergic pattern detection) ─────────
        # 12x12 grid over the brain territory — pheromone heatmap
        self.bci_intent_map = np.zeros((12, 12), dtype=np.float32)
        # Discovered intent clusters: list of (gx, gy, label, strength)
        self.bci_clusters: List[tuple] = []
        self.bci_patterns_detected = 0
        self.bci_active_intent = "---"
        self.bci_confidence = 0.0

        # ── Sim state ─────────────────────────────────────────────
        self.tick = 0
        self.sim_time = 0.0
        self.running = True
        self.total_stgm = 0.0
        self.tunes_accepted = 0
        self.attacks_blocked = 0
        self.vaccinations_applied = 0
        self.log_lines: List[str] = []

        self._spawn_swimmers(20)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(30)  # ~33 FPS

    def _spawn_swimmers(self, count: int):
        self.swimmers.clear()
        organ_keys = list(self.organs.keys())
        colors = [C_NERVE, C_BRAIN, C_COCHLEA, C_NFC, C_SPINE, C_BLOOD,
                  C_STGM_GLOW, C_IMMUNE]
        for i in range(count):
            home = organ_keys[i % len(organ_keys)]
            org = self.organs[home]
            w, h = self.width() or 950, self.height() or 650
            s = CyborgSwimmer(
                sid=f"{self.swimmer_names[i % len(self.swimmer_names)]}_{i:02d}",
                x=org.cx * w + random.gauss(0, 20),
                y=org.cy * h + random.gauss(0, 20),
                home_organ=home,
                color=colors[i % len(colors)],
            )
            self.swimmers.append(s)

    def inject_hostile(self):
        w, h = self.width() or 950, self.height() or 650
        targets = list(self.organs.keys())
        payloads = [
            "UNSIGNED_PACEMAKER_SET", "FORGED_NEURAL_INJECT",
            "COCHLEA_OVERFLOW_0xBEEF", "SPINE_REPLAY_ATTACK",
            "NFC_ESCALATION_ROOT", "BRAIN_PROMPT_INJECTION",
            "UNAUTH_BPM_999", "FOREIGN_KEY_IMPLANT",
        ]
        target = random.choice(targets)
        org = self.organs[target]
        h_agent = HostileAgent(
            x=random.choice([0, w]) + random.gauss(0, 20),
            y=random.uniform(50, h - 50),
            target_organ=target,
            payload=random.choice(payloads),
        )
        self.hostiles.append(h_agent)

        # ── Vaccination check (instant immune rejection) ──────────
        if _ab_is_vaccinated(h_agent.payload):
            h_agent.alive = False
            self.attacks_blocked += 1
            self.vaccinations_applied += 1
            self._log(f"💉 VACCINATED: {h_agent.payload} → instant reject (antibody match)")
        else:
            self._log(f"☠️ HOSTILE: {h_agent.payload} → {target}")

    def set_swimmer_count(self, count: int):
        self._spawn_swimmers(count)

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_lines.append(f"[{ts}] {msg}")
        if len(self.log_lines) > 200:
            self.log_lines = self.log_lines[-200:]

    # ── Physics tick ───────────────────────────────────────────────

    def _tick(self):
        self.tick += 1
        dt = 0.03
        self.sim_time += dt
        w, h = self.width() or 950, self.height() or 650

        # ── Update waveforms (real science) ───────────────────────
        heart = self.organs["heart"]
        brain = self.organs["brain"]
        spine = self.organs["spine"]

        self.ecg_history.append(ecg_waveform(self.sim_time, heart.bpm))
        self.ecg_history.pop(0)

        neural_val = neural_spike_train(self.sim_time, brain.neural_rate)
        self.neural_history.append(neural_val)
        self.neural_history.pop(0)

        self.spinal_history.append(spinal_signal(self.sim_time, spine.spine_signal))
        self.spinal_history.pop(0)

        cochlea = self.organs.get("cochlea_l") or self.organs["cochlea_r"]
        self.cochlear_bands = cochlear_spectrum(self.sim_time, cochlea.gain_db)

        # ── BCI: feed neural signal into intent map ───────────────
        self._bci_process_signal(neural_val, brain)

        # ── BCI: decay intent map (pheromone evaporation) ─────────
        self.bci_intent_map *= 0.997

        # ── Auto-inject hostiles ──────────────────────────────────
        if self.running and random.random() < 0.006:
            self.inject_hostile()

        # ── Auto-tune organs (swimmers earn STGM) ─────────────────
        for s in self.swimmers:
            s.tune_cooldown = max(0, s.tune_cooldown - dt)

        # ── Update hostiles ───────────────────────────────────────
        for hostile in self.hostiles:
            if not hostile.alive:
                continue
            hostile.age += dt
            hostile.pulse = (math.sin(hostile.age * 10) + 1) * 0.5
            org = self.organs.get(hostile.target_organ)
            if org:
                tx, ty = org.cx * w, org.cy * h
                dx, dy = tx - hostile.x, ty - hostile.y
                dist = math.sqrt(dx * dx + dy * dy) + 0.01
                hostile.x += (dx / dist) * 2.5
                hostile.y += (dy / dist) * 2.5
                if dist < org.radius * w * 0.8:
                    org.under_attack = True
                    org.health = max(0.3, org.health - 0.001)

        # ── Update swimmers ───────────────────────────────────────
        for s in self.swimmers:
            self._update_swimmer(s, dt, w, h)

        # ── Decay organ attack flags ──────────────────────────────
        # ── BCI: update cluster detection every 60 ticks ──────────
        if self.tick % 60 == 0:
            self._bci_detect_clusters()

        for org in self.organs.values():
            if not any(ha.alive and ha.target_organ == org.name for ha in self.hostiles):
                org.under_attack = False
                org.health = min(1.0, org.health + 0.002)

        self.update()

    def _update_swimmer(self, s: CyborgSwimmer, dt: float, w: float, h: float):
        org = self.organs.get(s.home_organ)
        if not org:
            return

        # ── Check for nearby hostiles ─────────────────────────────
        nearest_hostile = None
        nearest_dist = 999999
        for hostile in self.hostiles:
            if not hostile.alive:
                continue
            d = math.sqrt((s.x - hostile.x) ** 2 + (s.y - hostile.y) ** 2)
            if d < nearest_dist:
                nearest_dist = d
                nearest_hostile = hostile

        if nearest_hostile and nearest_dist < 150:
            s.state = "DEFEND"
            dx = nearest_hostile.x - s.x
            dy = nearest_hostile.y - s.y
            dist = max(1, nearest_dist)
            s.vx += (dx / dist) * 4.0 * dt * 60
            s.vy += (dy / dist) * 4.0 * dt * 60

            if nearest_dist < 15:
                nearest_hostile.alive = False
                self.attacks_blocked += 1
                reward = 0.5
                s.stgm_earned += reward
                self.total_stgm += reward
                org.health = min(1.0, org.health + 0.05)

                # ── Create antibody (persistent memory B-cell) ────
                ab = _ab_record_kill(
                    payload=nearest_hostile.payload,
                    target_organ=s.home_organ,
                    killer_swimmer=s.sid,
                )
                cached = ab.get("_cached", False)
                if cached:
                    self._log(f"🐜 {s.sid} DESTROYED {nearest_hostile.payload} in {s.home_organ} (+{reward} STGM) [known sig]")
                else:
                    self._log(f"🧬 {s.sid} DESTROYED {nearest_hostile.payload} → NEW ANTIBODY CREATED (+{reward} STGM)")

        elif s.tune_cooldown <= 0 and random.random() < 0.005:
            s.state = "TUNE"
            # Regulate organ parameters
            if s.home_organ == "heart":
                # Sinus node regulation — keep BPM in healthy range
                target_bpm = 72 + math.sin(self.sim_time * 0.1) * 8
                org.bpm += (target_bpm - org.bpm) * 0.1
            elif "cochlea" in s.home_organ:
                org.gain_db = max(6, min(18, org.gain_db + random.gauss(0, 0.5)))
            elif s.home_organ == "brain":
                org.neural_rate = max(20, min(80, org.neural_rate + random.gauss(0, 1)))
                # BCI: brain swimmers deposit pheromones on the intent map
                self._bci_swimmer_deposit(s)
            elif s.home_organ == "spine":
                org.spine_signal = min(1.0, org.spine_signal + 0.01)

            reward = 0.02
            s.stgm_earned += reward
            self.total_stgm += reward
            org.stgm_earned += reward
            self.tunes_accepted += 1
            s.tune_cooldown = 2.0
            s.state = "PATROL"
        else:
            s.state = "PATROL"
            # Patrol within home organ territory
            home_x, home_y = org.cx * w, org.cy * h
            home_r = org.radius * w
            dx = home_x - s.x
            dy = home_y - s.y
            dist = math.sqrt(dx * dx + dy * dy) + 0.01

            if dist > home_r * 1.5:
                # Return to territory
                s.vx += (dx / dist) * 2.0 * dt * 60
                s.vy += (dy / dist) * 2.0 * dt * 60
            else:
                # Orbital dance within territory
                angle = math.atan2(dy, dx) + math.pi / 2
                s.vx += math.cos(angle) * 0.5 + random.gauss(0, 0.4)
                s.vy += math.sin(angle) * 0.5 + random.gauss(0, 0.4)

        # Friction + speed cap
        s.vx *= 0.90
        s.vy *= 0.90
        speed = math.sqrt(s.vx ** 2 + s.vy ** 2)
        if speed > 7:
            s.vx = (s.vx / speed) * 7
            s.vy = (s.vy / speed) * 7

        s.x += s.vx
        s.y += s.vy
        s.x = max(5, min(w - 5, s.x))
        s.y = max(5, min(h - 5, s.y))

        s.trail.append((s.x, s.y))
        if len(s.trail) > 25:
            s.trail.pop(0)

    # ── BCI Intent Map Methods ─────────────────────────────────────

    def _bci_process_signal(self, neural_val: float, brain: OrganTerritory):
        """Map the raw neural signal onto the intent heatmap.
        Swimmers wander through this noisy data and cluster
        around repeating patterns — the Swarm learns intent."""
        # Convert neural signal to a position on the 12x12 grid
        # using phase-space embedding (Takens' theorem — real science)
        if len(self.neural_history) < 10:
            return
        # Current value vs delayed value → 2D phase space
        x_phase = self.neural_history[-1]
        y_phase = self.neural_history[-5]  # tau=5 delay embedding
        # Normalize to grid coordinates
        max_v = max(abs(v) for v in self.neural_history[-30:]) or 1
        gx = int((x_phase / max_v + 1) * 5.5) % 12
        gy = int((y_phase / max_v + 1) * 5.5) % 12
        # Deposit trace at this phase-space location
        self.bci_intent_map[gx][gy] += 0.04 + abs(neural_val) * 0.02
        self.bci_intent_map[gx][gy] = min(1.0, self.bci_intent_map[gx][gy])

        # Update decoded BCI output (strongest cluster signal)
        if self.bci_clusters:
            best = max(self.bci_clusters, key=lambda c: c[3])
            self.bci_active_intent = best[2]
            self.bci_confidence = min(1.0, best[3])
        self.bci_decoded_history.append(self.bci_confidence * (1 if self.bci_active_intent != "---" else 0))
        self.bci_decoded_history.pop(0)

    def _bci_swimmer_deposit(self, s: CyborgSwimmer):
        """Brain swimmers deposit pheromones where they sense gradient.
        This is pure stigmergy — no central controller."""
        w, h = self.width() or 950, self.height() or 650
        brain = self.organs["brain"]
        bx = brain.cx * w
        by = brain.cy * h
        br = brain.radius * w
        # Map swimmer position to BCI grid
        local_x = (s.x - (bx - br)) / (2 * br)
        local_y = (s.y - (by - br)) / (2 * br)
        gx = int(local_x * 11) % 12
        gy = int(local_y * 11) % 12
        # Deposit where neural history shows repeating patterns
        recent = self.neural_history[-20:]
        if len(recent) >= 20:
            # Simple autocorrelation — check if pattern repeats
            early = sum(recent[:10])
            late = sum(recent[10:])
            similarity = 1.0 / (1.0 + abs(early - late))
            if similarity > 0.6:  # Pattern detected!
                deposit = similarity * 0.08
                self.bci_intent_map[gx][gy] = min(1.0,
                    self.bci_intent_map[gx][gy] + deposit)
                self.bci_patterns_detected += 1

    def _bci_detect_clusters(self):
        """Find hot regions in the intent map → assign intent labels.
        Like biological synaptic pruning: weak traces die, strong survive."""
        self.bci_clusters.clear()
        threshold = 0.25
        label_idx = 0
        for gx in range(12):
            for gy in range(12):
                val = self.bci_intent_map[gx][gy]
                if val >= threshold:
                    # Check if this is a local maximum
                    is_peak = True
                    for ddx in range(-1, 2):
                        for ddy in range(-1, 2):
                            if ddx == 0 and ddy == 0:
                                continue
                            nx, ny = (gx + ddx) % 12, (gy + ddy) % 12
                            if self.bci_intent_map[nx][ny] > val:
                                is_peak = False
                    if is_peak:
                        label = BCI_INTENT_LABELS[label_idx % len(BCI_INTENT_LABELS)]
                        self.bci_clusters.append((gx, gy, label, val))
                        label_idx += 1
                        if label_idx >= 6:  # max 6 clusters
                            return

    # ── Rendering ──────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Background: deep void with subtle flesh gradient ──────
        bg = QRadialGradient(w * 0.5, h * 0.45, w * 0.6)
        bg.setColorAt(0, C_FLESH)
        bg.setColorAt(0.7, QColor(15, 12, 22))
        bg.setColorAt(1, C_VOID)
        p.fillRect(0, 0, w, h, bg)

        # ── Body silhouette (stylized torso + head) ───────────────
        body_path = QPainterPath()
        # Head
        body_path.addEllipse(QPointF(w * 0.5, h * 0.10), w * 0.08, h * 0.08)
        # Neck
        body_path.addRect(QRectF(w * 0.47, h * 0.16, w * 0.06, h * 0.06))
        # Torso
        body_path.addRoundedRect(QRectF(w * 0.32, h * 0.22, w * 0.36, h * 0.45), 30, 30)
        # Spine line
        body_path.moveTo(w * 0.5, h * 0.18)
        body_path.lineTo(w * 0.5, h * 0.67)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(40, 32, 45, 80)))
        p.drawPath(body_path)
        # Outline
        p.setPen(QPen(QColor(80, 70, 100, 60), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(body_path)

        # ── Organ territories ─────────────────────────────────────
        for name, org in self.organs.items():
            ox, oy = org.cx * w, org.cy * h
            r = org.radius * w

            # Territory glow
            grad = QRadialGradient(ox, oy, r * 1.8)
            alpha = int(40 + org.health * 60)
            if org.under_attack:
                attack_pulse = (math.sin(self.tick * 0.15) + 1) * 0.5
                grad.setColorAt(0, QColor(255, 40, 60, int(alpha * attack_pulse)))
                grad.setColorAt(0.5, QColor(255, 0, 0, int(alpha * 0.3)))
            else:
                grad.setColorAt(0, QColor(org.color.red(), org.color.green(), org.color.blue(), alpha))
                grad.setColorAt(0.5, QColor(org.color.red(), org.color.green(), org.color.blue(), alpha // 4))
            grad.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(ox, oy), r * 1.5, r * 1.5)

            # ── BCI Intent Heatmap (brain only) ───────────────────
            if name == "brain":
                self._draw_bci_heatmap(p, ox, oy, r)

            # Territory border
            border_alpha = int(60 + org.health * 80)
            p.setPen(QPen(QColor(org.color.red(), org.color.green(), org.color.blue(), border_alpha),
                          1.0, Qt.PenStyle.DotLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(ox, oy), r, r)

            # Organ label
            p.setPen(QPen(QColor(org.color.red(), org.color.green(), org.color.blue(), 180)))
            font = QFont("Menlo", 8, QFont.Weight.Bold)
            p.setFont(font)
            label = name.upper().replace("_L", " L").replace("_R", " R")
            if name == "brain" and self.bci_active_intent != "---":
                label += f" ⟨BCI: {self.bci_active_intent} {self.bci_confidence:.0%}⟩"
            p.drawText(QPointF(ox - 25, oy - r - 6), label)

            # Health bar
            bar_w = r * 1.4
            bar_h = 3
            bar_x = ox - bar_w / 2
            bar_y = oy + r + 4
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(40, 40, 60)))
            p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 1, 1)
            health_color = C_ACCEPT_GRN if org.health > 0.7 else (C_COCHLEA if org.health > 0.4 else C_REJECT_RED)
            p.setBrush(QBrush(health_color))
            p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w * org.health, bar_h), 1, 1)

        # ── Neural connections (nerve fibers between organs) ──────
        connections = [
            ("brain", "cochlea_l"), ("brain", "cochlea_r"),
            ("brain", "spine"), ("brain", "heart"),
            ("spine", "heart"), ("spine", "nfc"),
        ]
        for a, b in connections:
            oa, ob = self.organs[a], self.organs[b]
            ax, ay = oa.cx * w, oa.cy * h
            bx, by = ob.cx * w, ob.cy * h
            # Animated pulse along fiber
            pulse_pos = (self.sim_time * 2) % 1.0
            mx = ax + (bx - ax) * pulse_pos
            my = ay + (by - ay) * pulse_pos
            p.setPen(QPen(QColor(0, 180, 150, 30), 1))
            p.drawLine(QPointF(ax, ay), QPointF(bx, by))
            # Pulse dot
            p.setBrush(QBrush(QColor(0, 255, 200, 120)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(mx, my), 2.5, 2.5)

        # ── Hostile agents ────────────────────────────────────────
        for hostile in self.hostiles:
            if not hostile.alive:
                continue
            size = 8 + hostile.pulse * 5
            grad = QRadialGradient(hostile.x, hostile.y, size * 2.5)
            grad.setColorAt(0, QColor(255, 0, 60, 220))
            grad.setColorAt(0.4, QColor(255, 50, 100, 80))
            grad.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(hostile.x, hostile.y), size * 2, size * 2)
            # Skull core
            p.setBrush(QBrush(QColor(255, 80, 100)))
            p.drawEllipse(QPointF(hostile.x, hostile.y), size * 0.4, size * 0.4)
            # Payload label
            p.setPen(QPen(C_HOSTILE))
            font = QFont("Menlo", 7)
            p.setFont(font)
            p.drawText(QPointF(hostile.x - 40, hostile.y - size - 5), hostile.payload[:22])

        # ── Swimmer trails + bodies ───────────────────────────────
        for s in self.swimmers:
            # Trail
            for i in range(1, len(s.trail)):
                alpha = int(i / len(s.trail) * 80)
                p.setPen(QPen(QColor(s.color.red(), s.color.green(), s.color.blue(), alpha), 1))
                p.drawLine(QPointF(s.trail[i-1][0], s.trail[i-1][1]),
                           QPointF(s.trail[i][0], s.trail[i][1]))

            # Body
            if s.state == "DEFEND":
                body_c = C_HOSTILE
                sz = 5
            elif s.state == "TUNE":
                body_c = C_STGM_GLOW
                sz = 4.5
            else:
                body_c = s.color
                sz = 3.5

            p.setBrush(QBrush(body_c))
            p.setPen(QPen(QColor(255, 255, 255, 80), 0.5))
            p.drawEllipse(QPointF(s.x, s.y), sz, sz)

        # ── Waveform panels (bottom strip) — 5 panels now ──────────
        panel_y = h * 0.72
        panel_h = h * 0.26
        panel_w = w * 0.185  # slightly narrower for 5 panels
        gap = 6

        # ECG
        self._draw_waveform(p, 10, panel_y, panel_w, panel_h,
                            self.ecg_history, "❤ ECG", C_BLOOD,
                            f"{self.organs['heart'].bpm:.0f} BPM")
        # Neural
        self._draw_waveform(p, 10 + (panel_w + gap), panel_y, panel_w, panel_h,
                            self.neural_history, "🧠 NEURAL", C_BRAIN,
                            f"{self.organs['brain'].neural_rate:.0f} Hz")
        # Spinal
        self._draw_waveform(p, 10 + (panel_w + gap) * 2, panel_y, panel_w, panel_h,
                            self.spinal_history, "⚡ SPINE", C_SPINE,
                            f"{self.organs['spine'].spine_signal:.0%}")
        # Cochlear spectrum
        self._draw_spectrum(p, 10 + (panel_w + gap) * 3, panel_y, panel_w, panel_h,
                            self.cochlear_bands, "👂 COCHLEA", C_COCHLEA,
                            f"{self.organs.get('cochlea_l', self.organs.get('cochlea_r')).gain_db:.0f} dB")
        # BCI Decoded Intent
        self._draw_waveform(p, 10 + (panel_w + gap) * 4, panel_y, panel_w, panel_h,
                            self.bci_decoded_history, "🔮 BCI", C_BCI_INTENT,
                            self.bci_active_intent)

        # ── Scan lines ────────────────────────────────────────────
        scan_y = (self.tick * 1.5) % h
        p.setPen(QPen(QColor(0, 255, 200, 8), 1))
        p.drawLine(0, int(scan_y), w, int(scan_y))

        # ── Title HUD ─────────────────────────────────────────────
        p.setPen(QPen(C_STGM_GLOW))
        font = QFont("Menlo", 9, QFont.Weight.Bold)
        p.setFont(font)
        s_elapsed = f"{self.sim_time:.0f}s"
        ab_count = _ab_count()
        p.drawText(QPointF(10, 16),
                   f"CYBORG BODY SIM  |  {s_elapsed}  |  "
                   f"STGM: {self.total_stgm:.2f}  |  "
                   f"Tunes: {self.tunes_accepted}  |  "
                   f"Killed: {self.attacks_blocked}  |  "
                   f"🧬 Ab: {ab_count}  |  "
                   f"💉 Vax: {self.vaccinations_applied}  |  "
                   f"🔮 BCI: {self.bci_active_intent} ({self.bci_confidence:.0%})  Patterns: {self.bci_patterns_detected}")

        p.end()

    def _draw_waveform(self, p: QPainter, x: float, y: float, w: float, h: float,
                       data: List[float], title: str, color: QColor, subtitle: str):
        # Panel background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(15, 15, 25, 200)))
        p.drawRoundedRect(QRectF(x, y, w, h), 6, 6)
        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 60), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(x, y, w, h), 6, 6)

        # Title
        p.setPen(QPen(color))
        font = QFont("Menlo", 9, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QPointF(x + 8, y + 16), title)
        p.setPen(QPen(C_TEXT_DIM))
        font = QFont("Menlo", 8)
        p.setFont(font)
        p.drawText(QPointF(x + w - 60, y + 16), subtitle)

        # Grid lines
        p.setPen(QPen(QColor(40, 45, 60, 80), 0.5))
        mid_y = y + h * 0.55
        p.drawLine(QPointF(x + 5, mid_y), QPointF(x + w - 5, mid_y))

        # Waveform
        if len(data) < 2:
            return
        max_val = max(abs(v) for v in data) or 1
        path = QPainterPath()
        margin = 8
        usable_w = w - margin * 2
        usable_h = h * 0.35

        for i, val in enumerate(data):
            px = x + margin + (i / len(data)) * usable_w
            py = mid_y - (val / max_val) * usable_h
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

        # Glow line
        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 60), 3))
        p.drawPath(path)
        # Sharp line
        p.setPen(QPen(color, 1.5))
        p.drawPath(path)

    def _draw_spectrum(self, p: QPainter, x: float, y: float, w: float, h: float,
                       bands: List[float], title: str, color: QColor, subtitle: str):
        # Panel background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(15, 15, 25, 200)))
        p.drawRoundedRect(QRectF(x, y, w, h), 6, 6)
        p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 60), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(x, y, w, h), 6, 6)

        # Title
        p.setPen(QPen(color))
        font = QFont("Menlo", 9, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QPointF(x + 8, y + 16), title)
        p.setPen(QPen(C_TEXT_DIM))
        font = QFont("Menlo", 8)
        p.setFont(font)
        p.drawText(QPointF(x + w - 50, y + 16), subtitle)

        # Spectrum bars
        bar_area_y = y + 24
        bar_area_h = h - 32
        margin = 8
        usable_w = w - margin * 2
        bar_w = usable_w / len(bands) - 2
        bottom = bar_area_y + bar_area_h

        for i, val in enumerate(bands):
            bx = x + margin + i * (bar_w + 2)
            bar_h = val * bar_area_h * 0.9
            by = bottom - bar_h

            # Gradient bar
            grad = QLinearGradient(bx, bottom, bx, by)
            intensity = int(val * 255)
            grad.setColorAt(0, QColor(color.red(), color.green(), color.blue(), 60))
            grad.setColorAt(1, QColor(color.red(), color.green(), color.blue(), intensity))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(bx, by, bar_w, bar_h), 2, 2)

            # Top glow
            p.setBrush(QBrush(QColor(255, 255, 255, int(val * 120))))
            p.drawRoundedRect(QRectF(bx, by, bar_w, 2), 1, 1)

    def _draw_bci_heatmap(self, p: QPainter, brain_cx: float, brain_cy: float, brain_r: float):
        """Render the BCI pheromone intent map as a glowing heatmap over the brain."""
        grid_size = 12
        cell_w = (brain_r * 2) / grid_size
        cell_h = (brain_r * 2) / grid_size
        base_x = brain_cx - brain_r
        base_y = brain_cy - brain_r

        for gx in range(grid_size):
            for gy in range(grid_size):
                val = self.bci_intent_map[gx][gy]
                if val < 0.05:
                    continue
                cx = base_x + gx * cell_w + cell_w / 2
                cy = base_y + gy * cell_h + cell_h / 2

                # Check if inside brain circle
                dx = cx - brain_cx
                dy = cy - brain_cy
                if (dx * dx + dy * dy) > brain_r * brain_r:
                    continue

                # Pheromone glow
                alpha = int(val * 180)
                grad = QRadialGradient(cx, cy, cell_w * 0.8)
                grad.setColorAt(0, QColor(255, 100, 220, alpha))
                grad.setColorAt(0.6, QColor(200, 80, 255, alpha // 3))
                grad.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx, cy), cell_w * 0.7, cell_h * 0.7)

        # Draw cluster labels
        for gx, gy, label, strength in self.bci_clusters:
            cx = base_x + gx * cell_w + cell_w / 2
            cy = base_y + gy * cell_h + cell_h / 2
            dx = cx - brain_cx
            dy = cy - brain_cy
            if (dx * dx + dy * dy) > brain_r * brain_r:
                continue
            # Bright cluster marker
            p.setBrush(QBrush(QColor(255, 220, 255, int(strength * 200))))
            p.setPen(QPen(C_BCI_INTENT, 1.5))
            p.drawEllipse(QPointF(cx, cy), 4, 4)
            # Label
            p.setPen(QPen(QColor(255, 200, 255, int(strength * 255))))
            font = QFont("Menlo", 6, QFont.Weight.Bold)
            p.setFont(font)
            p.drawText(QPointF(cx - 15, cy - 7), label)


# ═══════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════

class CyborgWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA Cyborg Body — Territory Is The Law")
        self.setMinimumSize(1300, 850)
        self.setStyleSheet(f"""
            QMainWindow {{ background: rgb(8, 10, 18); }}
            QWidget {{ background: transparent; color: rgb(200, 210, 240); }}
            QGroupBox {{
                border: 1px solid rgb(50, 45, 65);
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                font-family: 'Menlo';
                font-size: 11px;
                color: rgb(200, 210, 240);
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: rgb(0, 255, 200);
            }}
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgb(50, 42, 65), stop:1 rgb(30, 25, 42));
                border: 1px solid rgb(80, 70, 100);
                border-radius: 6px;
                padding: 8px 18px;
                color: rgb(200, 210, 240);
                font-family: 'Menlo';
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgb(70, 60, 90), stop:1 rgb(45, 38, 62));
                border-color: rgb(0, 255, 200);
            }}
            QPushButton#btnHostile {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgb(150, 30, 50), stop:1 rgb(90, 15, 30));
                border-color: rgb(255, 80, 100);
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: rgb(40, 35, 55);
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: rgb(0, 255, 200);
                width: 14px; height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QTextEdit {{
                background: rgb(10, 8, 16);
                border: 1px solid rgb(40, 35, 55);
                border-radius: 4px;
                font-family: 'Menlo';
                font-size: 10px;
                color: rgb(0, 255, 200);
                padding: 4px;
            }}
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Title
        title_bar = QHBoxLayout()
        title = QLabel("🦾 SIFTA CYBORG BODY — TERRITORY IS THE LAW")
        title.setFont(QFont("Menlo", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(0, 255, 200); padding: 4px;")
        title_bar.addWidget(title)
        title_bar.addStretch()
        main_layout.addLayout(title_bar)

        # Controls
        controls = QHBoxLayout()
        controls.setSpacing(10)

        btn_hostile = QPushButton("☠️ INJECT HOSTILE")
        btn_hostile.setObjectName("btnHostile")
        btn_hostile.setFixedHeight(38)
        btn_hostile.clicked.connect(self._inject)
        controls.addWidget(btn_hostile)

        btn_burst = QPushButton("💉 INJECT 5x BURST")
        btn_burst.setFixedHeight(38)
        btn_burst.clicked.connect(self._inject_burst)
        controls.addWidget(btn_burst)

        # Slider
        slider_box = QVBoxLayout()
        sl = QLabel("Swimmer Count:")
        sl.setStyleSheet("font-size: 10px; color: rgb(100, 105, 130);")
        slider_box.addWidget(sl)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(6, 80)
        self.slider.setValue(20)
        self.slider.setFixedWidth(200)
        self.slider.valueChanged.connect(self._slider_changed)
        slider_box.addWidget(self.slider)
        self.slider_val = QLabel("20")
        self.slider_val.setStyleSheet("font-size: 10px; color: rgb(0, 255, 200); font-weight: bold;")
        slider_box.addWidget(self.slider_val)
        controls.addLayout(slider_box)
        controls.addStretch()
        main_layout.addLayout(controls)

        # Splitter: Canvas + Log
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.canvas = CyborgCanvas()
        splitter.addWidget(self.canvas)

        log_group = QGroupBox("IMMUNE SYSTEM LOG")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumWidth(260)
        self.log_view.setMaximumWidth(320)
        log_layout.addWidget(self.log_view)
        splitter.addWidget(log_group)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, 1)

        # Log refresh
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._refresh_log)
        self.log_timer.start(400)

    def _inject(self):
        self.canvas.inject_hostile()

    def _inject_burst(self):
        for _ in range(5):
            self.canvas.inject_hostile()

    def _slider_changed(self, val):
        self.slider_val.setText(str(val))
        self.canvas.set_swimmer_count(val)

    def _refresh_log(self):
        lines = self.canvas.log_lines[-80:]
        self.log_view.setPlainText("\n".join(lines))
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CyborgWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
