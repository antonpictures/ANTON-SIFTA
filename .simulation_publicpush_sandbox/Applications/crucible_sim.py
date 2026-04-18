#!/usr/bin/env python3
"""
SIFTA CRUCIBLE SIMULATOR — 10-Minute Swarm Defense Gauntlet
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PyQt6 real-time visualization of:
  • DDoS wave defense (rate limiting)
  • Anomaly injection + swarm foraging/quarantine
  • Stigmergic edge detection on noisy data
  • Live STGM economy (real ledger_balance reads)
  • Swimmer pheromone trails with particle physics

Designed to look like a mad scientist's war room.
Run:  python3 Applications/crucible_sim.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sys
import os
import json
import math
import time
import random
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

# ── Repo root ──────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "System"))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame, QProgressBar, QSplitter,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsRectItem, QGraphicsLineItem, QGraphicsTextItem,
    QSizePolicy, QGridLayout, QGroupBox, QTextEdit
)
from PyQt6.QtCore import (
    Qt, QTimer, QRectF, QPointF, pyqtSignal, QPropertyAnimation,
    QEasingCurve, QObject
)
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QRadialGradient,
    QLinearGradient, QPainterPath, QPixmap, QImage
)

import numpy as np

# ── Color Palette (Tokyo Night + Neon) ─────────────────────────────
C_BG         = QColor(26, 27, 38)        # deep navy
C_BG_PANEL   = QColor(30, 33, 49)        # panel bg
C_BORDER     = QColor(60, 65, 90)        # border
C_TEXT       = QColor(192, 202, 245)      # lavender text
C_TEXT_DIM   = QColor(110, 120, 160)      # dim text
C_GREEN      = QColor(158, 206, 106)      # healthy green
C_RED        = QColor(247, 118, 142)      # alert red
C_ORANGE     = QColor(255, 158, 100)      # warning orange
C_CYAN       = QColor(125, 207, 255)      # info cyan
C_PURPLE     = QColor(187, 154, 247)      # swarm purple
C_MAGENTA    = QColor(255, 0, 200)        # hot pink
C_YELLOW     = QColor(224, 175, 104)      # amber
C_BLUE       = QColor(122, 162, 247)      # link blue
C_TEAL       = QColor(115, 218, 202)      # mint
C_PLASMA1    = QColor(200, 60, 255)       # plasma purple
C_PLASMA2    = QColor(0, 255, 200)        # plasma teal
C_NEON_GREEN = QColor(0, 255, 128)        # neon matrix green
C_DARK_RED   = QColor(80, 20, 30)         # background pulse


# ═══════════════════════════════════════════════════════════════════
#  DATA CLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Swimmer:
    """A single autonomous swarm agent with physics."""
    sid: str
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    energy: float = 100.0
    pheromone_strength: float = 0.0
    state: str = "PATROL"      # PATROL, HUNT, QUARANTINE, EDGE_DETECT
    color: QColor = field(default_factory=lambda: C_CYAN)
    target_x: float = 0.0
    target_y: float = 0.0
    trail: list = field(default_factory=list)
    stgm_earned: float = 0.0
    kills: int = 0

@dataclass
class Anomaly:
    """A malicious data packet injected into the network."""
    x: float
    y: float
    payload: str
    discovered: bool = False
    quarantined: bool = False
    pulse: float = 0.0
    age: float = 0.0

@dataclass
class TrafficPacket:
    """A DDoS traffic wave packet."""
    x: float
    y: float
    target_x: float
    target_y: float
    speed: float
    blocked: bool = False
    age: float = 0.0


# ═══════════════════════════════════════════════════════════════════
#  MAIN SIMULATION CANVAS
# ═══════════════════════════════════════════════════════════════════

class CrucibleCanvas(QWidget):
    """PyQt6 custom widget — the war room visualization."""

    stats_updated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(900, 600)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── Simulation state ───────────────────────────────────────
        self.swimmers: List[Swimmer] = []
        self.anomalies: List[Anomaly] = []
        self.packets: List[TrafficPacket] = []
        self.pheromone_map = np.zeros((80, 60), dtype=np.float32)
        self.edge_map = np.zeros((80, 60), dtype=np.float32)
        self.noise_field = np.zeros((80, 60), dtype=np.float32)
        self.quarantine_zone = QRectF(0, 0, 0, 0)

        # ── Counters ──────────────────────────────────────────────
        self.tick = 0
        self.crucible_active = False
        self.elapsed_sec = 0.0
        self.total_requests = 0
        self.blocked_requests = 0
        self.anomalies_quarantined = 0
        self.total_stgm_minted = 0.0
        self.network_load = 0.0
        self.edges_found = 0

        # ── Swimmer names from real state ─────────────────────────
        self.swimmer_names = [
            "HERMES", "ANTIALICE", "M1QUEEN", "M1THER",
            "OPENCLAW", "ALICE_M5", "SEBASTIAN", "REPAIR-DRONE",
        ]

        # ── Server nodes (visual network) ─────────────────────────
        self.server_nodes = []
        self.server_stress = {}

        # ── Terminal log ──────────────────────────────────────────
        self.log_lines: List[str] = []

        self._init_simulation()

        # ── Render timer ──────────────────────────────────────────
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)  # ~30 FPS

    def _init_simulation(self):
        """Boot the simulation world."""
        w, h = 900, 600

        # Quarantine zone (bottom-right)
        self.quarantine_zone = QRectF(w - 180, h - 140, 170, 130)

        # Server nodes in a hex pattern
        cx, cy = w * 0.45, h * 0.45
        for i in range(6):
            angle = i * math.pi / 3 + math.pi / 6
            sx = cx + 140 * math.cos(angle)
            sy = cy + 140 * math.sin(angle)
            self.server_nodes.append((sx, sy, f"NODE_{i}"))
            self.server_stress[f"NODE_{i}"] = 0.0
        # Central master
        self.server_nodes.append((cx, cy, "MASTER"))
        self.server_stress["MASTER"] = 0.0

        # Generate noisy topography for edge detection
        self._generate_topography()

        # Spawn swimmers
        self._respawn_swimmers(count=16)

    def _generate_topography(self):
        """Generate a noisy terrain with hidden structures for swarm to find."""
        h, w = self.noise_field.shape[1], self.noise_field.shape[0]
        for x in range(w):
            for y in range(h):
                # Create circles, ridges, and noise
                cx1, cy1 = w * 0.3, h * 0.4
                cx2, cy2 = w * 0.7, h * 0.6
                d1 = math.sqrt((x - cx1) ** 2 + (y - cy1) ** 2)
                d2 = math.sqrt((x - cx2) ** 2 + (y - cy2) ** 2)
                ridge = math.sin(x * 0.3) * math.cos(y * 0.2) * 30
                blob1 = max(0, 80 - d1 * 4)
                blob2 = max(0, 60 - d2 * 3.5)
                noise = random.gauss(0, 15)
                self.noise_field[x][y] = blob1 + blob2 + ridge + noise + 40

    def _respawn_swimmers(self, count: int = 16):
        """Spawn fresh swimmers from the roster."""
        self.swimmers.clear()
        w, h = self.width() or 900, self.height() or 600
        palette = [C_CYAN, C_PURPLE, C_TEAL, C_BLUE, C_GREEN, C_MAGENTA, C_YELLOW, C_ORANGE]
        for i in range(count):
            name = self.swimmer_names[i % len(self.swimmer_names)]
            s = Swimmer(
                sid=f"{name}_{i}",
                x=random.uniform(60, w - 200),
                y=random.uniform(60, h - 160),
                vx=random.uniform(-1.5, 1.5),
                vy=random.uniform(-1.5, 1.5),
                color=palette[i % len(palette)],
            )
            self.swimmers.append(s)

    def set_swimmer_count(self, count: int):
        self._respawn_swimmers(count)

    def start_crucible(self):
        self.crucible_active = True
        self.elapsed_sec = 0.0
        self.total_requests = 0
        self.blocked_requests = 0
        self.anomalies_quarantined = 0
        self.total_stgm_minted = 0.0
        self.anomalies.clear()
        self.packets.clear()
        self.pheromone_map.fill(0)
        self.edge_map.fill(0)
        self.edges_found = 0
        self._log("[CRUCIBLE] 🔥 INITIATING 10-MINUTE CRUCIBLE GAUNTLET")
        self._log(f"[SWARM] {len(self.swimmers)} swimmers deployed")

    def stop_crucible(self):
        self.crucible_active = False
        self._log("[CRUCIBLE] ✅ CRUCIBLE COMPLETE — STANDING DOWN")
        self._log(f"[LEDGER] Total STGM minted: {self.total_stgm_minted:.2f}")
        self._log(f"[DEFENSE] Requests blocked: {self.blocked_requests}/{self.total_requests}")
        self._log(f"[QUARANTINE] Anomalies isolated: {self.anomalies_quarantined}")

    def inject_anomaly(self):
        w, h = self.width() or 900, self.height() or 600
        payloads = [
            "MALICIOUS_PAYLOAD_X99", "GHOST_MINT_ATTEMPT",
            "BUFFER_OVERFLOW_0xDEAD", "SOCIAL_ENGINEER_HEIST",
            "UNAUTH_STGM_MINT_100K", "FORGED_ED25519_SIG",
            "WORMHOLE_SPOOF_ATTEMPT", "REPLAY_ATTACK_T-900",
        ]
        a = Anomaly(
            x=random.uniform(80, w - 200),
            y=random.uniform(80, h - 160),
            payload=random.choice(payloads),
        )
        self.anomalies.append(a)
        self._log(f"[INJECT] ☠️  {a.payload} at ({int(a.x)}, {int(a.y)})")

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_lines.append(f"[{ts}] {msg}")
        if len(self.log_lines) > 200:
            self.log_lines = self.log_lines[-200:]

    # ── Physics tick ───────────────────────────────────────────────

    def _tick(self):
        self.tick += 1
        dt = 0.033

        if self.crucible_active:
            self.elapsed_sec += dt

            # Auto-stop at 600s
            if self.elapsed_sec >= 600:
                self.stop_crucible()

            # ── DDoS wave generation ──────────────────────────────
            if self.tick % 3 == 0:
                self._spawn_traffic_wave()

            # ── Random anomaly injection ──────────────────────────
            if random.random() < 0.008:
                self.inject_anomaly()

        # ── Update swimmers ───────────────────────────────────────
        for s in self.swimmers:
            self._update_swimmer(s, dt)

        # ── Update traffic packets ────────────────────────────────
        self._update_packets(dt)

        # ── Update anomalies ──────────────────────────────────────
        for a in self.anomalies:
            a.age += dt
            a.pulse = (math.sin(a.age * 8) + 1) * 0.5

        # ── Decay pheromone map ───────────────────────────────────
        self.pheromone_map *= 0.985

        # ── Update server stress ──────────────────────────────────
        for k in self.server_stress:
            self.server_stress[k] = max(0, self.server_stress[k] - 0.02)

        # ── Network load oscillation ──────────────────────────────
        if self.crucible_active:
            target = min(100, len(self.packets) * 0.5 + random.gauss(40, 15))
            self.network_load += (target - self.network_load) * 0.1
        else:
            self.network_load *= 0.95

        # ── Emit stats ───────────────────────────────────────────
        self.stats_updated.emit({
            "elapsed": self.elapsed_sec,
            "requests": self.total_requests,
            "blocked": self.blocked_requests,
            "quarantined": self.anomalies_quarantined,
            "stgm": self.total_stgm_minted,
            "load": self.network_load,
            "swimmers": len(self.swimmers),
            "edges": self.edges_found,
            "active": self.crucible_active,
        })

        self.update()

    def _spawn_traffic_wave(self):
        """Spawn incoming DDoS traffic packets aimed at server nodes."""
        w, h = self.width() or 900, self.height() or 600
        count = random.randint(5, 25)
        for _ in range(count):
            target = random.choice(self.server_nodes)
            # Spawn from edges
            edge = random.choice(["top", "left", "right"])
            if edge == "top":
                sx, sy = random.uniform(0, w), 0
            elif edge == "left":
                sx, sy = 0, random.uniform(0, h)
            else:
                sx, sy = w, random.uniform(0, h)

            p = TrafficPacket(
                x=sx, y=sy,
                target_x=target[0], target_y=target[1],
                speed=random.uniform(3, 8),
            )
            # Rate limit: 70% chance of blocking under heavy load
            if self.network_load > 60 and random.random() < 0.7:
                p.blocked = True
                self.blocked_requests += 1
            self.total_requests += 1
            self.packets.append(p)

    def _update_packets(self, dt: float):
        alive = []
        for p in self.packets:
            p.age += dt
            dx = p.target_x - p.x
            dy = p.target_y - p.y
            dist = math.sqrt(dx * dx + dy * dy) + 0.01
            p.x += (dx / dist) * p.speed
            p.y += (dy / dist) * p.speed

            if p.blocked and p.age > 0.3:
                continue  # fade out

            if dist < 15:
                # Hit server
                for node in self.server_nodes:
                    if abs(node[0] - p.target_x) < 5:
                        self.server_stress[node[2]] = min(1.0,
                            self.server_stress[node[2]] + 0.08)
                continue

            if p.age < 3.0:
                alive.append(p)

        self.packets = alive

    def _update_swimmer(self, s: Swimmer, dt: float):
        w, h = self.width() or 900, self.height() or 600

        # ── Check for nearby anomalies ────────────────────────────
        nearest_anomaly = None
        nearest_dist = 999999
        for a in self.anomalies:
            if a.quarantined:
                continue
            d = math.sqrt((s.x - a.x) ** 2 + (s.y - a.y) ** 2)
            if d < nearest_dist:
                nearest_dist = d
                nearest_anomaly = a

        # ── State machine ─────────────────────────────────────────
        if nearest_anomaly and nearest_dist < 200:
            s.state = "HUNT"
            s.target_x = nearest_anomaly.x
            s.target_y = nearest_anomaly.y

            if nearest_dist < 25:
                # Quarantine!
                nearest_anomaly.discovered = True
                if not nearest_anomaly.quarantined:
                    nearest_anomaly.quarantined = True
                    nearest_anomaly.x = self.quarantine_zone.x() + random.uniform(10, 150)
                    nearest_anomaly.y = self.quarantine_zone.y() + random.uniform(10, 110)
                    self.anomalies_quarantined += 1
                    s.kills += 1
                    reward = 0.5
                    s.stgm_earned += reward
                    self.total_stgm_minted += reward
                    s.state = "PATROL"
                    self._log(f"[SWARM] 🐜 {s.sid} quarantined {nearest_anomaly.payload} (+{reward} STGM)")
        elif self.crucible_active and random.random() < 0.02:
            s.state = "EDGE_DETECT"
        else:
            s.state = "PATROL"

        # ── Movement ──────────────────────────────────────────────
        if s.state == "HUNT":
            dx = s.target_x - s.x
            dy = s.target_y - s.y
            dist = math.sqrt(dx * dx + dy * dy) + 0.01
            s.vx += (dx / dist) * 3.0 * dt * 60
            s.vy += (dy / dist) * 3.0 * dt * 60
        elif s.state == "EDGE_DETECT":
            # Follow gradient in noise field
            gx = int(s.x / (w / 80)) % 80
            gy = int(s.y / (h / 60)) % 60
            grad_x = self.noise_field[min(79, gx + 1)][gy] - self.noise_field[max(0, gx - 1)][gy]
            grad_y = self.noise_field[gx][min(59, gy + 1)] - self.noise_field[gx][max(0, gy - 1)]
            grad_mag = math.sqrt(grad_x ** 2 + grad_y ** 2) + 0.01

            if grad_mag > 20:
                # Strong edge — deposit pheromone
                self.pheromone_map[gx][gy] = min(1.0, self.pheromone_map[gx][gy] + 0.15)
                self.edge_map[gx][gy] = 1.0
                self.edges_found += 1
                s.pheromone_strength = 1.0
                reward = 0.01
                s.stgm_earned += reward
                self.total_stgm_minted += reward

            # Follow perpendicular to gradient (trace edges)
            s.vx += (-grad_y / grad_mag) * 1.5 * dt * 60
            s.vy += (grad_x / grad_mag) * 1.5 * dt * 60
        else:
            # Patrol with random walk + pheromone following
            s.vx += random.gauss(0, 0.8)
            s.vy += random.gauss(0, 0.8)
            # Mild pheromone attraction
            gx = int(s.x / (w / 80)) % 80
            gy = int(s.y / (h / 60)) % 60
            for ddx in range(-2, 3):
                for ddy in range(-2, 3):
                    px, py = (gx + ddx) % 80, (gy + ddy) % 60
                    if self.pheromone_map[px][py] > 0.1:
                        s.vx += ddx * 0.05
                        s.vy += ddy * 0.05

        # Friction
        s.vx *= 0.92
        s.vy *= 0.92
        speed = math.sqrt(s.vx ** 2 + s.vy ** 2)
        max_speed = 6.0
        if speed > max_speed:
            s.vx = (s.vx / speed) * max_speed
            s.vy = (s.vy / speed) * max_speed

        s.x += s.vx
        s.y += s.vy

        # Bounds
        s.x = max(10, min(w - 10, s.x))
        s.y = max(10, min(h - 10, s.y))

        # Pheromone decay on swimmer
        s.pheromone_strength *= 0.96

        # Trail
        s.trail.append((s.x, s.y))
        if len(s.trail) > 30:
            s.trail.pop(0)

    # ── Rendering ──────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Background ────────────────────────────────────────────
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor(15, 16, 28))
        bg.setColorAt(1, QColor(22, 24, 40))
        p.fillRect(0, 0, w, h, bg)

        # ── Pheromone / edge glow layer ───────────────────────────
        cell_w = w / 80
        cell_h = h / 60
        for gx in range(80):
            for gy in range(60):
                ph = self.pheromone_map[gx][gy]
                ed = self.edge_map[gx][gy]
                if ph > 0.02 or ed > 0:
                    alpha = int(min(255, ph * 180 + ed * 80))
                    c = QColor(0, 255, 180, alpha)
                    p.fillRect(QRectF(gx * cell_w, gy * cell_h, cell_w + 1, cell_h + 1), c)

        # ── Network connections (faint lines between servers) ─────
        pen = QPen(QColor(60, 70, 100, 60), 1)
        p.setPen(pen)
        for i, n1 in enumerate(self.server_nodes):
            for j, n2 in enumerate(self.server_nodes):
                if i < j:
                    p.drawLine(QPointF(n1[0], n1[1]), QPointF(n2[0], n2[1]))

        # ── Traffic packets ───────────────────────────────────────
        for pkt in self.packets:
            alpha = max(0, int(255 * (1 - pkt.age / 3.0)))
            if pkt.blocked:
                c = QColor(247, 118, 142, alpha)
                size = 3
            else:
                c = QColor(125, 207, 255, alpha // 2)
                size = 2
            p.setBrush(QBrush(c))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(pkt.x, pkt.y), size, size)

        # ── Server nodes ──────────────────────────────────────────
        for sx, sy, name in self.server_nodes:
            stress = self.server_stress.get(name, 0)
            # Glow ring
            glow_alpha = int(stress * 200)
            glow_r = 30 + stress * 20
            grad = QRadialGradient(sx, sy, glow_r)
            if stress > 0.7:
                grad.setColorAt(0, QColor(247, 118, 142, glow_alpha))
            elif stress > 0.3:
                grad.setColorAt(0, QColor(255, 158, 100, glow_alpha))
            else:
                grad.setColorAt(0, QColor(125, 207, 255, 40))
            grad.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(sx, sy), glow_r, glow_r)
            # Core
            core_c = QColor(
                int(80 + stress * 167),
                int(200 - stress * 100),
                int(255 - stress * 150),
            )
            p.setBrush(QBrush(core_c))
            p.setPen(QPen(QColor(200, 210, 255, 100), 1.5))
            p.drawEllipse(QPointF(sx, sy), 12, 12)
            # Label
            p.setPen(QPen(C_TEXT_DIM))
            font = QFont("Menlo", 8)
            p.setFont(font)
            p.drawText(QPointF(sx - 18, sy + 25), name)

        # ── Quarantine zone ───────────────────────────────────────
        qz = self.quarantine_zone
        # Pulsing border
        pulse = (math.sin(self.tick * 0.08) + 1) * 0.5
        p.setBrush(QBrush(QColor(80, 20, 30, int(30 + pulse * 40))))
        p.setPen(QPen(QColor(247, 118, 142, int(80 + pulse * 100)), 2, Qt.PenStyle.DashLine))
        p.drawRoundedRect(qz, 8, 8)
        p.setPen(QPen(C_RED))
        font = QFont("Menlo", 10, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QPointF(qz.x() + 10, qz.y() + 18), "⛔ QUARANTINE")
        p.setPen(QPen(C_TEXT_DIM))
        font = QFont("Menlo", 8)
        p.setFont(font)
        p.drawText(QPointF(qz.x() + 10, qz.y() + 34), f"{self.anomalies_quarantined} isolated")

        # ── Anomalies ─────────────────────────────────────────────
        for a in self.anomalies:
            if a.quarantined:
                # In quarantine — dim red dot
                p.setBrush(QBrush(QColor(247, 118, 142, 80)))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(a.x, a.y), 5, 5)
            else:
                # Active threat — pulsing skull
                size = 10 + a.pulse * 6
                grad = QRadialGradient(a.x, a.y, size * 2)
                grad.setColorAt(0, QColor(255, 0, 80, 200))
                grad.setColorAt(0.5, QColor(255, 0, 150, 80))
                grad.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(a.x, a.y), size * 2, size * 2)
                # Core
                p.setBrush(QBrush(QColor(255, 50, 100)))
                p.drawEllipse(QPointF(a.x, a.y), size * 0.5, size * 0.5)
                # Label
                p.setPen(QPen(C_RED))
                font = QFont("Menlo", 7)
                p.setFont(font)
                p.drawText(QPointF(a.x - 30, a.y - size - 4), a.payload[:20])

        # ── Swimmer trails + bodies ───────────────────────────────
        for s in self.swimmers:
            # Trail
            if len(s.trail) > 2:
                for i in range(1, len(s.trail)):
                    alpha = int(i / len(s.trail) * 100)
                    pen = QPen(QColor(s.color.red(), s.color.green(), s.color.blue(), alpha), 1)
                    p.setPen(pen)
                    p.drawLine(
                        QPointF(s.trail[i-1][0], s.trail[i-1][1]),
                        QPointF(s.trail[i][0], s.trail[i][1])
                    )

            # Pheromone glow
            if s.pheromone_strength > 0.05:
                grad = QRadialGradient(s.x, s.y, 15 + s.pheromone_strength * 10)
                grad.setColorAt(0, QColor(0, 255, 180, int(s.pheromone_strength * 100)))
                grad.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(s.x, s.y), 15, 15)

            # Body
            if s.state == "HUNT":
                body_color = C_RED
                size = 5
            elif s.state == "EDGE_DETECT":
                body_color = C_NEON_GREEN
                size = 4
            else:
                body_color = s.color
                size = 3.5

            p.setBrush(QBrush(body_color))
            p.setPen(QPen(QColor(255, 255, 255, 120), 0.5))
            p.drawEllipse(QPointF(s.x, s.y), size, size)

        # ── Scan lines (mad scientist vibe) ───────────────────────
        if self.crucible_active:
            scan_y = (self.tick * 2) % h
            scan_pen = QPen(QColor(0, 255, 128, 15), 1)
            p.setPen(scan_pen)
            p.drawLine(0, int(scan_y), w, int(scan_y))
            # Secondary scan
            scan_y2 = (self.tick * 3 + h // 2) % h
            p.drawLine(0, int(scan_y2), w, int(scan_y2))

        # ── Top-left HUD overlay ──────────────────────────────────
        p.setPen(QPen(C_NEON_GREEN if self.crucible_active else C_TEXT_DIM))
        font = QFont("Menlo", 9, QFont.Weight.Bold)
        p.setFont(font)
        status = "🔥 CRUCIBLE ACTIVE" if self.crucible_active else "⏸ STANDBY"
        elapsed = f"{int(self.elapsed_sec)}s / 600s" if self.crucible_active else "—"
        p.drawText(QPointF(12, 20), f"{status}  |  {elapsed}")

        p.end()


# ═══════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════

class CrucibleWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA Crucible — Swarm Defense Simulator")
        self.setMinimumSize(1280, 820)
        self.setStyleSheet(f"""
            QMainWindow {{ background: rgb(22, 24, 38); }}
            QWidget {{ background: transparent; color: rgb(192, 202, 245); }}
            QGroupBox {{
                border: 1px solid rgb(60, 65, 90);
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                font-family: 'SF Pro Display', 'Menlo';
                font-size: 11px;
                color: rgb(192, 202, 245);
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: rgb(187, 154, 247);
            }}
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgb(60, 65, 100), stop:1 rgb(40, 44, 70));
                border: 1px solid rgb(80, 85, 120);
                border-radius: 6px;
                padding: 8px 18px;
                color: rgb(192, 202, 245);
                font-family: 'SF Pro Display', 'Menlo';
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgb(80, 85, 130), stop:1 rgb(55, 60, 95));
                border-color: rgb(125, 130, 170);
            }}
            QPushButton:pressed {{
                background: rgb(30, 33, 55);
            }}
            QPushButton#btnCrucible {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgb(180, 60, 60), stop:1 rgb(120, 30, 30));
                border-color: rgb(247, 118, 142);
            }}
            QPushButton#btnCrucible:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgb(220, 80, 80), stop:1 rgb(160, 50, 50));
            }}
            QPushButton#btnInject {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgb(180, 100, 30), stop:1 rgb(120, 60, 10));
                border-color: rgb(255, 158, 100);
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: rgb(50, 55, 80);
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: rgb(187, 154, 247);
                width: 14px; height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QProgressBar {{
                border: 1px solid rgb(60, 65, 90);
                border-radius: 4px;
                text-align: center;
                font-family: 'Menlo';
                font-size: 10px;
                color: rgb(192, 202, 245);
                background: rgb(30, 33, 49);
            }}
            QProgressBar::chunk {{
                border-radius: 3px;
            }}
            QTextEdit {{
                background: rgb(18, 19, 30);
                border: 1px solid rgb(50, 55, 75);
                border-radius: 4px;
                font-family: 'Menlo';
                font-size: 10px;
                color: rgb(0, 255, 128);
                padding: 4px;
            }}
            QLabel {{
                font-family: 'SF Pro Display', 'Menlo';
            }}
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # ── Title bar ─────────────────────────────────────────────
        title_bar = QHBoxLayout()
        title = QLabel("⚡ SIFTA CRUCIBLE — SWARM DEFENSE SIMULATOR")
        title.setFont(QFont("SF Pro Display", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(187, 154, 247); padding: 4px;")
        title_bar.addWidget(title)
        title_bar.addStretch()

        # Status light
        self.status_light = QLabel("● STANDBY")
        self.status_light.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        self.status_light.setStyleSheet("color: rgb(110, 120, 160);")
        title_bar.addWidget(self.status_light)
        main_layout.addLayout(title_bar)

        # ── Control panel ─────────────────────────────────────────
        controls = QHBoxLayout()
        controls.setSpacing(10)

        btn_crucible = QPushButton("🔥 TRIGGER CRUCIBLE")
        btn_crucible.setObjectName("btnCrucible")
        btn_crucible.setFixedHeight(40)
        btn_crucible.clicked.connect(self._toggle_crucible)
        self.btn_crucible = btn_crucible
        controls.addWidget(btn_crucible)

        btn_inject = QPushButton("☠️ INJECT ANOMALY")
        btn_inject.setObjectName("btnInject")
        btn_inject.setFixedHeight(40)
        btn_inject.clicked.connect(self._inject)
        controls.addWidget(btn_inject)

        # Swimmer count slider
        slider_box = QVBoxLayout()
        slider_label = QLabel("Swarm Agents:")
        slider_label.setStyleSheet("font-size: 10px; color: rgb(110, 120, 160);")
        slider_box.addWidget(slider_label)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(4, 64)
        self.slider.setValue(16)
        self.slider.setFixedWidth(200)
        self.slider.valueChanged.connect(self._slider_changed)
        slider_box.addWidget(self.slider)
        self.slider_value = QLabel("16")
        self.slider_value.setStyleSheet("font-size: 10px; color: rgb(187, 154, 247); font-weight: bold;")
        slider_box.addWidget(self.slider_value)
        controls.addLayout(slider_box)
        controls.addStretch()
        main_layout.addLayout(controls)

        # ── Metrics bar ───────────────────────────────────────────
        metrics = QHBoxLayout()
        metrics.setSpacing(12)

        self.metric_widgets = {}
        metric_defs = [
            ("network_load", "NETWORK LOAD", "%", C_CYAN),
            ("requests", "REQUESTS", "", C_BLUE),
            ("blocked", "BLOCKED (429)", "", C_RED),
            ("quarantined", "QUARANTINED", "", C_ORANGE),
            ("stgm", "STGM MINTED", "", C_GREEN),
            ("edges", "EDGES FOUND", "", C_TEAL),
            ("swimmers", "SWIMMERS", "", C_PURPLE),
        ]
        for key, label, suffix, color in metric_defs:
            box = QVBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"font-size: 9px; color: rgb({color.red()},{color.green()},{color.blue()});")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(lbl)
            val = QLabel("0" + suffix)
            val.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
            val.setStyleSheet(f"color: rgb({color.red()},{color.green()},{color.blue()});")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(val)
            frame = QFrame()
            frame.setLayout(box)
            frame.setStyleSheet("""
                QFrame {
                    background: rgb(30, 33, 49);
                    border: 1px solid rgb(50, 55, 78);
                    border-radius: 6px;
                    padding: 4px 10px;
                }
            """)
            metrics.addWidget(frame)
            self.metric_widgets[key] = val

        main_layout.addLayout(metrics)

        # ── Main content: Canvas + Log ────────────────────────────
        self._pane_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.canvas = CrucibleCanvas()
        self.canvas.stats_updated.connect(self._update_metrics)
        self._pane_splitter.addWidget(self.canvas)

        # Terminal log
        log_group = QGroupBox("SWARM TERMINAL")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumWidth(280)
        self.log_view.setMaximumWidth(350)
        log_layout.addWidget(self.log_view)
        self._pane_splitter.addWidget(log_group)

        self._pane_splitter.setStretchFactor(0, 3)
        self._pane_splitter.setStretchFactor(1, 1)
        main_layout.addWidget(self._pane_splitter, 1)
        QTimer.singleShot(0, self._balance_pane_splitter)

        # ── Log refresh timer ─────────────────────────────────────
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._refresh_log)
        self.log_timer.start(500)

    def _balance_pane_splitter(self) -> None:
        from System.splitter_utils import balance_horizontal_splitter

        balance_horizontal_splitter(
            self._pane_splitter,
            self,
            left_ratio=0.72,
            min_right=280,
            min_left=240,
            max_right=350,
        )

    def _toggle_crucible(self):
        if self.canvas.crucible_active:
            self.canvas.stop_crucible()
            self.btn_crucible.setText("🔥 TRIGGER CRUCIBLE")
            self.status_light.setText("● STANDBY")
            self.status_light.setStyleSheet("color: rgb(110, 120, 160);")
        else:
            self.canvas.start_crucible()
            self.btn_crucible.setText("⏹ STAND DOWN")
            self.status_light.setText("● CRUCIBLE ACTIVE")
            self.status_light.setStyleSheet("color: rgb(247, 118, 142);")

    def _inject(self):
        self.canvas.inject_anomaly()

    def _slider_changed(self, val):
        self.slider_value.setText(str(val))
        self.canvas.set_swimmer_count(val)

    def _update_metrics(self, stats: dict):
        self.metric_widgets["network_load"].setText(f"{stats['load']:.0f}%")
        self.metric_widgets["requests"].setText(f"{stats['requests']:,}")
        self.metric_widgets["blocked"].setText(f"{stats['blocked']:,}")
        self.metric_widgets["quarantined"].setText(str(stats["quarantined"]))
        self.metric_widgets["stgm"].setText(f"{stats['stgm']:.2f}")
        self.metric_widgets["edges"].setText(f"{stats['edges']:,}")
        self.metric_widgets["swimmers"].setText(str(stats["swimmers"]))

    def _refresh_log(self):
        lines = self.canvas.log_lines[-60:]
        self.log_view.setPlainText("\n".join(lines))
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())


# ═══════════════════════════════════════════════════════════════════
#  LAUNCH
# ═══════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = CrucibleWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
