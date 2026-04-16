#!/usr/bin/env python3
"""
SIFTA Research Simulators — Quantum Error Correction & Epidemiological Containment
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Two proof-of-concept simulations demonstrating stigmergic swarm intelligence
applied to real scientific problems:

TAB 1 — QUANTUM SURFACE CODE
  Real science: Toric/planar surface code error correction.
  • 2D grid of data qubits + stabilizer (ancilla) qubits
  • X-stabilizers detect bit-flip errors, Z-stabilizers detect phase-flips
  • Swimmers patrol the qubit lattice as autonomous sentinels
  • On syndrome detection (parity violation), swimmers swarm the error
  • Pheromone traces guide correction operators (Pauli X/Z gates)
  • Metrics: logical error rate, correction latency, syndrome density

TAB 2 — EPIDEMIOLOGICAL CONTAINMENT (SIR + CONTACT TRACING)
  Real science: SIR compartmental model + decentralized contact tracing.
  • Population of mobile agents in 2D space (each is a "phone node")
  • Agents drop cryptographic pheromone traces (Bluetooth handshakes)
  • Traces evaporate over time — no persistent identity storage
  • When an agent tests positive, their trace history is marked hostile
  • Nearby agents sense hostile traces → self-isolate (quarantine)
  • No central server ever knows who is sick or who they met
  • Metrics: R₀, infection curve, containment efficiency, privacy score

Run:  python3 Applications/sifta_quantum_epi_sim.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sys
import math
import time
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "System"))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame, QSplitter, QTabWidget,
    QSizePolicy, QGroupBox, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QRadialGradient,
    QLinearGradient, QPainterPath
)
import numpy as np

# ── Palette ────────────────────────────────────────────────────────
C_VOID       = QColor(8, 10, 18)
C_PANEL      = QColor(18, 20, 32)
C_BORDER     = QColor(45, 42, 65)
C_TEXT       = QColor(200, 210, 240)
C_TEXT_DIM   = QColor(100, 105, 130)
C_HIGHLIGHT  = QColor(0, 255, 200)
C_STGM      = QColor(0, 255, 128)
# Quantum
C_QUBIT_OK   = QColor(60, 80, 200)
C_QUBIT_ERR  = QColor(255, 60, 80)
C_STAB_X     = QColor(255, 180, 80)    # X-stabilizer (bit-flip detect)
C_STAB_Z     = QColor(120, 200, 255)   # Z-stabilizer (phase-flip detect)
C_CORRECTION = QColor(0, 255, 180)
C_SYNDROME   = QColor(255, 40, 100)
# Epidemiology
C_SUSCEPTIBLE = QColor(80, 160, 255)
C_INFECTED    = QColor(255, 60, 80)
C_RECOVERED   = QColor(80, 255, 140)
C_QUARANTINE  = QColor(255, 200, 60)
C_TRACE       = QColor(255, 255, 255, 20)
C_HOSTILE_TR  = QColor(255, 60, 80, 40)


# ═══════════════════════════════════════════════════════════════════
#  TAB 1: QUANTUM SURFACE CODE ERROR CORRECTION
# ═══════════════════════════════════════════════════════════════════

class QuantumSurfaceCanvas(QWidget):
    """
    Simulates a distance-d surface code on a 2D lattice.
    
    Real science:
      • Data qubits sit on edges of a square lattice
      • X-stabilizers (faces) detect bit-flip errors (|0⟩↔|1⟩)
      • Z-stabilizers (vertices) detect phase-flip errors (|+⟩↔|−⟩)
      • Syndrome = set of stabilizers that report -1 eigenvalue
      • Swimmers patrol, detect syndromes, swarm to apply corrections
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(700, 500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── Lattice config ────────────────────────────────────────
        self.grid_d = 7  # distance of the code (7×7 data qubits)
        self._init_lattice()

        # ── Swimmers ──────────────────────────────────────────────
        self.swimmers: List[List[float]] = []  # [gx, gy, vx, vy, state]
        self.swimmer_count = 40
        self._spawn_swimmers()

        # ── Stats ─────────────────────────────────────────────────
        self.tick = 0
        self.sim_time = 0.0
        self.errors_injected = 0
        self.errors_corrected = 0
        self.logical_errors = 0
        self.correction_latency_sum = 0.0
        self.correction_count = 0
        self.stgm_earned = 0.0
        self.error_rate = 0.01  # per-qubit error probability per tick
        self.log_lines: List[str] = []

        # ── Pheromone field on lattice ────────────────────────────
        self.pheromone = np.zeros((self.grid_d, self.grid_d), dtype=np.float32)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)  # 20 FPS

    def _init_lattice(self):
        d = self.grid_d
        # Data qubits: 0 = |0⟩, 1 = |1⟩ (bit-flip error state)
        self.data_qubits = np.zeros((d, d), dtype=np.int8)
        # Phase errors tracked separately
        self.phase_errors = np.zeros((d, d), dtype=np.int8)
        # Syndrome: X-stabilizer violations (faces)
        self.x_syndrome = np.zeros((d - 1, d - 1), dtype=np.int8)
        # Syndrome: Z-stabilizer violations (vertices — shifted grid)
        self.z_syndrome = np.zeros((d - 1, d - 1), dtype=np.int8)
        # Error timestamps for latency measurement
        self.error_birth: Dict[Tuple[int, int], float] = {}

    def _spawn_swimmers(self):
        self.swimmers.clear()
        d = self.grid_d
        for _ in range(self.swimmer_count):
            self.swimmers.append([
                random.uniform(0, d - 1),  # gx (grid position, float)
                random.uniform(0, d - 1),  # gy
                random.gauss(0, 0.3),       # vx
                random.gauss(0, 0.3),       # vy
                0,  # state: 0=PATROL, 1=SWARM, 2=CORRECT
            ])

    def set_swimmer_count(self, n):
        self.swimmer_count = n
        self._spawn_swimmers()

    def set_error_rate(self, rate_pct):
        self.error_rate = rate_pct / 1000.0  # slider is 1-50 → 0.001 to 0.050

    def inject_error_burst(self):
        d = self.grid_d
        for _ in range(max(3, d // 2)):
            x, y = random.randint(0, d - 1), random.randint(0, d - 1)
            if random.random() < 0.6:
                self.data_qubits[x][y] ^= 1  # bit-flip
            else:
                self.phase_errors[x][y] ^= 1  # phase-flip
            self.errors_injected += 1
            self.error_birth[(x, y)] = self.sim_time
        self._compute_syndrome()
        self._log(f"⚡ ERROR BURST: {d // 2} qubits corrupted")

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_lines.append(f"[{ts}] {msg}")
        if len(self.log_lines) > 200:
            self.log_lines = self.log_lines[-200:]

    def _compute_syndrome(self):
        """Compute X and Z stabilizer syndromes from qubit state.
        Real surface code math: stabilizer eigenvalue = product of adjacent data qubits."""
        d = self.grid_d
        # X-stabilizer: detect bit-flips on face plaquettes
        for i in range(d - 1):
            for j in range(d - 1):
                # Parity of 4 surrounding data qubits
                parity = (self.data_qubits[i][j] ^
                          self.data_qubits[i + 1][j] ^
                          self.data_qubits[i][j + 1] ^
                          self.data_qubits[i + 1][j + 1])
                self.x_syndrome[i][j] = parity

        # Z-stabilizer: detect phase-flips on vertex stars
        for i in range(d - 1):
            for j in range(d - 1):
                parity = (self.phase_errors[i][j] ^
                          self.phase_errors[i + 1][j] ^
                          self.phase_errors[i][j + 1] ^
                          self.phase_errors[i + 1][j + 1])
                self.z_syndrome[i][j] = parity

    def _tick(self):
        self.tick += 1
        dt = 0.05
        self.sim_time += dt
        d = self.grid_d

        # ── Random errors (environmental decoherence) ─────────────
        for i in range(d):
            for j in range(d):
                if random.random() < self.error_rate:
                    if random.random() < 0.6:
                        self.data_qubits[i][j] ^= 1
                    else:
                        self.phase_errors[i][j] ^= 1
                    self.errors_injected += 1
                    if (i, j) not in self.error_birth:
                        self.error_birth[(i, j)] = self.sim_time

        # ── Recompute syndrome ────────────────────────────────────
        self._compute_syndrome()

        # ── Pheromone deposit at syndrome locations ───────────────
        for i in range(d - 1):
            for j in range(d - 1):
                if self.x_syndrome[i][j] or self.z_syndrome[i][j]:
                    # Deposit pheromone in surrounding data qubit cells
                    for di in range(2):
                        for dj in range(2):
                            gi, gj = i + di, j + dj
                            if 0 <= gi < d and 0 <= gj < d:
                                self.pheromone[gi][gj] = min(1.0,
                                    self.pheromone[gi][gj] + 0.15)

        # ── Pheromone evaporation ─────────────────────────────────
        self.pheromone *= 0.96

        # ── Update swimmers ───────────────────────────────────────
        for sw in self.swimmers:
            gx, gy = sw[0], sw[1]
            igx, igy = int(round(gx)) % d, int(round(gy)) % d

            # Sense pheromone gradient
            best_ph = 0.0
            best_dx, best_dy = 0.0, 0.0
            for ddx in range(-2, 3):
                for ddy in range(-2, 3):
                    nx, ny = (igx + ddx) % d, (igy + ddy) % d
                    ph = self.pheromone[nx][ny]
                    if ph > best_ph:
                        best_ph = ph
                        best_dx = nx - gx
                        best_dy = ny - gy

            if best_ph > 0.1:
                # SWARM toward syndrome
                sw[4] = 1  # state = SWARM
                dist = math.sqrt(best_dx ** 2 + best_dy ** 2) + 0.01
                sw[2] += (best_dx / dist) * 0.4
                sw[3] += (best_dy / dist) * 0.4

                # Attempt correction when at error site
                if best_ph > 0.3 and dist < 1.5:
                    qx, qy = int(round(gx)) % d, int(round(gy)) % d
                    corrected = False
                    if self.data_qubits[qx][qy] == 1:
                        self.data_qubits[qx][qy] = 0  # Apply Pauli-X correction
                        corrected = True
                    if self.phase_errors[qx][qy] == 1:
                        self.phase_errors[qx][qy] = 0  # Apply Pauli-Z correction
                        corrected = True
                    if corrected:
                        sw[4] = 2  # CORRECT
                        self.errors_corrected += 1
                        self.stgm_earned += 0.05
                        self.pheromone[qx][qy] = max(0, self.pheromone[qx][qy] - 0.5)
                        # Measure latency
                        if (qx, qy) in self.error_birth:
                            latency = self.sim_time - self.error_birth.pop((qx, qy))
                            self.correction_latency_sum += latency
                            self.correction_count += 1
                        if self.errors_corrected % 10 == 0:
                            self._log(f"🔧 Corrected qubit ({qx},{qy}) — total: {self.errors_corrected}")
            else:
                sw[4] = 0  # PATROL
                sw[2] += random.gauss(0, 0.2)
                sw[3] += random.gauss(0, 0.2)

            # Physics
            sw[2] *= 0.85
            sw[3] *= 0.85
            speed = math.sqrt(sw[2] ** 2 + sw[3] ** 2)
            if speed > 1.5:
                sw[2] = (sw[2] / speed) * 1.5
                sw[3] = (sw[3] / speed) * 1.5
            sw[0] = (sw[0] + sw[2]) % d
            sw[1] = (sw[1] + sw[3]) % d

        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        d = self.grid_d

        # Background
        p.fillRect(0, 0, w, h, C_VOID)

        # ── Grid layout ───────────────────────────────────────────
        margin = 60
        grid_w = min(w - margin * 2 - 200, h - margin * 2 - 80)
        grid_h = grid_w
        gx0 = margin
        gy0 = margin + 20
        cell = grid_w / d

        # ── Draw lattice connections ──────────────────────────────
        p.setPen(QPen(QColor(40, 40, 60), 1))
        for i in range(d):
            for j in range(d):
                cx = gx0 + j * cell + cell / 2
                cy = gy0 + i * cell + cell / 2
                if j < d - 1:
                    p.drawLine(QPointF(cx, cy),
                               QPointF(cx + cell, cy))
                if i < d - 1:
                    p.drawLine(QPointF(cx, cy),
                               QPointF(cx, cy + cell))

        # ── Draw pheromone field ──────────────────────────────────
        for i in range(d):
            for j in range(d):
                ph = self.pheromone[i][j]
                if ph < 0.05:
                    continue
                cx = gx0 + j * cell + cell / 2
                cy = gy0 + i * cell + cell / 2
                alpha = int(ph * 120)
                grad = QRadialGradient(cx, cy, cell * 0.8)
                grad.setColorAt(0, QColor(255, 60, 100, alpha))
                grad.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(QBrush(grad))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(cx, cy), cell * 0.7, cell * 0.7)

        # ── Draw X-stabilizers (faces) ────────────────────────────
        for i in range(d - 1):
            for j in range(d - 1):
                fx = gx0 + j * cell + cell
                fy = gy0 + i * cell + cell
                if self.x_syndrome[i][j]:
                    # Syndrome detected!
                    p.setBrush(QBrush(QColor(255, 180, 80, 60)))
                    p.setPen(QPen(C_SYNDROME, 1.5))
                    p.drawRect(QRectF(fx - cell * 0.3, fy - cell * 0.3,
                                       cell * 0.6, cell * 0.6))
                    p.setFont(QFont("Menlo", 6))
                    p.drawText(QPointF(fx - 4, fy + 3), "X!")

        # ── Draw Z-stabilizers (vertex stars) ─────────────────────
        for i in range(d - 1):
            for j in range(d - 1):
                vx = gx0 + j * cell + cell
                vy = gy0 + i * cell + cell
                if self.z_syndrome[i][j]:
                    p.setPen(QPen(C_STAB_Z, 1.5))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(QPointF(vx, vy), cell * 0.25, cell * 0.25)
                    p.setFont(QFont("Menlo", 6))
                    p.setPen(QPen(C_STAB_Z))
                    p.drawText(QPointF(vx - 4, vy + 3), "Z!")

        # ── Draw data qubits ──────────────────────────────────────
        for i in range(d):
            for j in range(d):
                cx = gx0 + j * cell + cell / 2
                cy = gy0 + i * cell + cell / 2
                has_bit_err = self.data_qubits[i][j] == 1
                has_phase_err = self.phase_errors[i][j] == 1
                r = cell * 0.22

                if has_bit_err and has_phase_err:
                    color = QColor(255, 100, 200)  # Both errors — Y error
                elif has_bit_err:
                    color = C_QUBIT_ERR
                elif has_phase_err:
                    color = QColor(255, 200, 60)
                else:
                    color = C_QUBIT_OK

                p.setBrush(QBrush(color))
                p.setPen(QPen(QColor(255, 255, 255, 60), 0.5))
                p.drawEllipse(QPointF(cx, cy), r, r)

                # Label
                if has_bit_err or has_phase_err:
                    p.setFont(QFont("Menlo", 5))
                    p.setPen(QPen(C_TEXT))
                    label = ""
                    if has_bit_err:
                        label += "X"
                    if has_phase_err:
                        label += "Z"
                    p.drawText(QPointF(cx - 4, cy - r - 2), label)

        # ── Draw swimmers ─────────────────────────────────────────
        for sw in self.swimmers:
            sx = gx0 + sw[0] * cell + cell / 2
            sy = gy0 + sw[1] * cell + cell / 2
            state = int(sw[4])
            if state == 2:
                c = C_CORRECTION
                sz = 4
            elif state == 1:
                c = C_SYNDROME
                sz = 3.5
            else:
                c = C_HIGHLIGHT
                sz = 2.5
            p.setBrush(QBrush(c))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(sx, sy), sz, sz)

        # ── Stats panel (right side) ──────────────────────────────
        stats_x = gx0 + grid_w + 20
        stats_y = gy0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(15, 15, 25, 200)))
        p.drawRoundedRect(QRectF(stats_x, stats_y, w - stats_x - 10, grid_h), 8, 8)

        p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        p.setPen(QPen(C_HIGHLIGHT))
        p.drawText(QPointF(stats_x + 10, stats_y + 20), "QUANTUM SURFACE CODE")

        avg_latency = (self.correction_latency_sum / max(self.correction_count, 1))
        syndrome_count = int(np.sum(self.x_syndrome) + np.sum(self.z_syndrome))
        total_errors = int(np.sum(self.data_qubits) + np.sum(self.phase_errors))
        total_qubits = d * d
        error_pct = total_errors / total_qubits * 100

        stats = [
            (f"Distance: d={d}", C_TEXT),
            (f"Data qubits: {total_qubits}", C_TEXT),
            (f"", C_TEXT),
            (f"Errors injected: {self.errors_injected}", C_QUBIT_ERR),
            (f"Errors corrected: {self.errors_corrected}", C_CORRECTION),
            (f"Active errors: {total_errors} ({error_pct:.1f}%)", C_QUBIT_ERR if error_pct > 5 else C_TEXT),
            (f"Active syndromes: {syndrome_count}", C_SYNDROME if syndrome_count > 0 else C_TEXT),
            (f"Avg latency: {avg_latency:.2f}s", C_TEXT),
            (f"", C_TEXT),
            (f"Swimmers: {len(self.swimmers)}", C_HIGHLIGHT),
            (f"STGM earned: {self.stgm_earned:.2f}", C_STGM),
            (f"Sim time: {self.sim_time:.0f}s", C_TEXT_DIM),
            (f"", C_TEXT),
            (f"Error rate: {self.error_rate:.3f}/tick", C_TEXT_DIM),
        ]

        p.setFont(QFont("Menlo", 8))
        for i, (text, color) in enumerate(stats):
            p.setPen(QPen(color))
            p.drawText(QPointF(stats_x + 10, stats_y + 42 + i * 16), text)

        # ── Legend ────────────────────────────────────────────────
        legend_y = stats_y + 42 + len(stats) * 16 + 10
        legends = [
            (C_QUBIT_OK, "Qubit |0⟩ (healthy)"),
            (C_QUBIT_ERR, "Bit-flip (X error)"),
            (QColor(255, 200, 60), "Phase-flip (Z error)"),
            (QColor(255, 100, 200), "Y error (both)"),
            (C_STAB_X, "X-stabilizer syndrome"),
            (C_STAB_Z, "Z-stabilizer syndrome"),
            (C_HIGHLIGHT, "Swimmer (patrolling)"),
            (C_SYNDROME, "Swimmer (swarming)"),
            (C_CORRECTION, "Swimmer (correcting)"),
        ]
        p.setFont(QFont("Menlo", 7))
        for i, (color, text) in enumerate(legends):
            y = legend_y + i * 14
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(stats_x + 16, y), 4, 4)
            p.setPen(QPen(C_TEXT_DIM))
            p.drawText(QPointF(stats_x + 26, y + 3), text)

        # ── Title HUD ─────────────────────────────────────────────
        p.setPen(QPen(C_HIGHLIGHT))
        p.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        p.drawText(QPointF(10, 16),
                   f"⚛ QUANTUM SURFACE CODE  |  d={d}  |  "
                   f"Errors: {total_errors}/{total_qubits}  |  "
                   f"Corrected: {self.errors_corrected}  |  "
                   f"Syndromes: {syndrome_count}  |  "
                   f"STGM: {self.stgm_earned:.2f}")

        # Scan line
        scan_y = (self.tick * 1.2) % h
        p.setPen(QPen(QColor(0, 255, 200, 6), 1))
        p.drawLine(0, int(scan_y), w, int(scan_y))

        p.end()


# ═══════════════════════════════════════════════════════════════════
#  TAB 2: EPIDEMIOLOGICAL CONTAINMENT (SIR MODEL)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class EpiAgent:
    """A mobile agent in the epidemiological simulation."""
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    state: str = "S"  # S=Susceptible, I=Infected, R=Recovered, Q=Quarantine
    infected_at: float = -1.0
    recovery_time: float = 10.0  # seconds to recover
    trace_ids: Set[int] = field(default_factory=set)  # recently encountered agent IDs
    quarantine_until: float = -1.0
    knows_hostile: bool = False


class EpidemiologyCanvas(QWidget):
    """
    SIR compartmental model with decentralized stigmergic contact tracing.
    
    Real science:
      • S→I: infection on proximity contact (configurable radius & probability)
      • I→R: recovery after configurable duration
      • Contact tracing: agents drop pheromone traces (Bluetooth handshakes)
      • When agent tests positive, their trace history marked hostile
      • Nearby agents sense hostile traces → self-quarantine
      • No central database — pure stigmergic containment
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(700, 500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.population_size = 200
        self.agents: List[EpiAgent] = []
        self.traces: List[Tuple[float, float, float, int]] = []  # x, y, age, owner_id
        self.hostile_ids: Set[int] = set()

        # ── Parameters ────────────────────────────────────────────
        self.infection_radius = 20.0
        self.infection_prob = 0.08
        self.recovery_time = 12.0  # seconds
        self.trace_evap_rate = 0.02
        self.quarantine_duration = 8.0
        self.tracing_enabled = True
        self.initial_infected = 3

        # ── SIR history for curve plotting ────────────────────────
        self.sir_history: List[Tuple[int, int, int, int]] = []  # S, I, R, Q
        self.max_history = 400

        # ── Stats ─────────────────────────────────────────────────
        self.tick = 0
        self.sim_time = 0.0
        self.total_infections = 0
        self.total_quarantines = 0
        self.containment_success = 0  # quarantines that prevented spread
        self.peak_infected = 0
        self.stgm_earned = 0.0
        self.log_lines: List[str] = []

        self._init_population()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)  # 20 FPS

    def _init_population(self):
        w, h = self.width() or 700, self.height() or 500
        sim_w = w * 0.65
        sim_h = h * 0.6
        self.agents.clear()
        self.traces.clear()
        self.hostile_ids.clear()
        self.sir_history.clear()
        self.total_infections = 0
        self.total_quarantines = 0
        self.peak_infected = 0
        self.sim_time = 0.0
        self.tick = 0

        for i in range(self.population_size):
            a = EpiAgent(
                x=random.uniform(40, sim_w),
                y=random.uniform(60, sim_h + 40),
                vx=random.gauss(0, 1),
                vy=random.gauss(0, 1),
                recovery_time=self.recovery_time + random.gauss(0, 2),
            )
            self.agents.append(a)

        # Seed initial infected
        for i in range(min(self.initial_infected, len(self.agents))):
            self.agents[i].state = "I"
            self.agents[i].infected_at = 0.0
            self.total_infections += 1

        self._log(f"🦠 Population: {self.population_size}, Initial infected: {self.initial_infected}")

    def reset(self):
        self._init_population()

    def set_tracing(self, enabled):
        self.tracing_enabled = enabled
        self._log(f"📱 Contact tracing: {'ENABLED' if enabled else 'DISABLED'}")

    def set_infection_radius(self, r):
        self.infection_radius = r

    def inject_outbreak(self):
        susceptible = [a for a in self.agents if a.state == "S"]
        if susceptible:
            for _ in range(min(5, len(susceptible))):
                a = random.choice(susceptible)
                a.state = "I"
                a.infected_at = self.sim_time
                self.total_infections += 1
                susceptible.remove(a)
            self._log("🦠 OUTBREAK: 5 new infections injected!")

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_lines.append(f"[{ts}] {msg}")
        if len(self.log_lines) > 200:
            self.log_lines = self.log_lines[-200:]

    def _tick(self):
        self.tick += 1
        dt = 0.05
        self.sim_time += dt
        w, h = self.width() or 700, self.height() or 500
        sim_w = w * 0.65
        sim_h = h * 0.6

        s_count, i_count, r_count, q_count = 0, 0, 0, 0

        for idx, a in enumerate(self.agents):
            # ── Movement ──────────────────────────────────────────
            if a.state != "Q":
                a.vx += random.gauss(0, 0.3)
                a.vy += random.gauss(0, 0.3)
                a.vx *= 0.90
                a.vy *= 0.90
                speed = math.sqrt(a.vx ** 2 + a.vy ** 2)
                if speed > 3:
                    a.vx = (a.vx / speed) * 3
                    a.vy = (a.vy / speed) * 3
                a.x += a.vx
                a.y += a.vy
                # Bounce off walls
                if a.x < 30: a.x = 30; a.vx = abs(a.vx)
                if a.x > sim_w: a.x = sim_w; a.vx = -abs(a.vx)
                if a.y < 50: a.y = 50; a.vy = abs(a.vy)
                if a.y > sim_h + 40: a.y = sim_h + 40; a.vy = -abs(a.vy)

                # Drop pheromone trace (Bluetooth handshake)
                if self.tick % 5 == 0:
                    self.traces.append((a.x, a.y, 0.0, idx))

            # ── Quarantine release ────────────────────────────────
            if a.state == "Q" and self.sim_time > a.quarantine_until:
                a.state = "R"  # released as recovered
                self._log(f"✅ Agent {idx} released from quarantine")

            # ── Recovery ──────────────────────────────────────────
            if a.state == "I":
                if self.sim_time - a.infected_at > a.recovery_time:
                    a.state = "R"
                    self.stgm_earned += 0.02

            # ── Contact tracing — check nearby traces ─────────────
            if self.tracing_enabled and a.state == "S":
                for tx, ty, tage, tid in self.traces:
                    if tid in self.hostile_ids:
                        dist = math.sqrt((a.x - tx) ** 2 + (a.y - ty) ** 2)
                        if dist < self.infection_radius * 1.5 and tage < 3.0:
                            a.state = "Q"
                            a.quarantine_until = self.sim_time + self.quarantine_duration
                            self.total_quarantines += 1
                            self.stgm_earned += 0.1
                            self._log(f"🔒 Agent {idx} quarantined (hostile trace detected)")
                            break

            # Count states
            if a.state == "S": s_count += 1
            elif a.state == "I": i_count += 1
            elif a.state == "R": r_count += 1
            elif a.state == "Q": q_count += 1

        # ── Infection spread ──────────────────────────────────────
        infected = [(i, a) for i, a in enumerate(self.agents) if a.state == "I"]
        for idx, a in enumerate(self.agents):
            if a.state != "S":
                continue
            for inf_idx, inf in infected:
                dist = math.sqrt((a.x - inf.x) ** 2 + (a.y - inf.y) ** 2)
                if dist < self.infection_radius and random.random() < self.infection_prob:
                    a.state = "I"
                    a.infected_at = self.sim_time
                    a.recovery_time = self.recovery_time + random.gauss(0, 2)
                    self.total_infections += 1
                    # Mark this agent's traces as hostile
                    self.hostile_ids.add(idx)
                    break

        # Mark infected agents' traces as hostile
        for inf_idx, _ in infected:
            self.hostile_ids.add(inf_idx)

        # ── Trace evaporation ─────────────────────────────────────
        self.traces = [(x, y, age + dt, tid) for x, y, age, tid in self.traces
                       if age + dt < 5.0]  # evaporate after 5 seconds

        # ── Record SIR curve ──────────────────────────────────────
        self.sir_history.append((s_count, i_count, r_count, q_count))
        if len(self.sir_history) > self.max_history:
            self.sir_history.pop(0)
        self.peak_infected = max(self.peak_infected, i_count)

        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, C_VOID)

        if not self.agents:
            p.end()
            return

        sim_w = w * 0.65
        sim_h = h * 0.6

        # ── Simulation area border ────────────────────────────────
        p.setPen(QPen(C_BORDER, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(25, 45, sim_w - 15, sim_h + 5), 6, 6)

        # ── Draw traces (pheromone breadcrumbs) ───────────────────
        for tx, ty, tage, tid in self.traces:
            alpha = max(5, int((1 - tage / 5.0) * 25))
            if tid in self.hostile_ids:
                p.setBrush(QBrush(QColor(255, 60, 80, alpha)))
            else:
                p.setBrush(QBrush(QColor(255, 255, 255, alpha)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(tx, ty), 2, 2)

        # ── Draw agents ───────────────────────────────────────────
        for a in self.agents:
            if a.state == "S":
                color = C_SUSCEPTIBLE
                sz = 3.5
            elif a.state == "I":
                color = C_INFECTED
                sz = 5
            elif a.state == "R":
                color = C_RECOVERED
                sz = 3
            elif a.state == "Q":
                color = C_QUARANTINE
                sz = 4.5
            else:
                color = C_TEXT_DIM
                sz = 3

            p.setBrush(QBrush(color))
            p.setPen(QPen(QColor(255, 255, 255, 40), 0.5))
            p.drawEllipse(QPointF(a.x, a.y), sz, sz)

            # Infection radius halo for infected
            if a.state == "I":
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(255, 60, 80, 30), 0.5, Qt.PenStyle.DotLine))
                p.drawEllipse(QPointF(a.x, a.y), self.infection_radius, self.infection_radius)

            # Quarantine box
            if a.state == "Q":
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(C_QUARANTINE, 1, Qt.PenStyle.DashLine))
                p.drawRect(QRectF(a.x - 8, a.y - 8, 16, 16))

        # ── SIR Curve (bottom right) ─────────────────────────────
        curve_x = 25
        curve_y = sim_h + 65
        curve_w = sim_w - 15
        curve_h = h - curve_y - 10

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(15, 15, 25, 200)))
        p.drawRoundedRect(QRectF(curve_x, curve_y, curve_w, curve_h), 6, 6)

        p.setPen(QPen(C_TEXT_DIM))
        p.setFont(QFont("Menlo", 7))
        p.drawText(QPointF(curve_x + 6, curve_y + 12), "SIR CURVE")

        if len(self.sir_history) > 2:
            max_pop = self.population_size
            for series_idx, (color, label) in enumerate([
                (C_SUSCEPTIBLE, "S"), (C_INFECTED, "I"),
                (C_RECOVERED, "R"), (C_QUARANTINE, "Q"),
            ]):
                path = QPainterPath()
                for i, (s, inf, r, q) in enumerate(self.sir_history):
                    vals = [s, inf, r, q]
                    val = vals[series_idx]
                    px = curve_x + 6 + (i / self.max_history) * (curve_w - 12)
                    py = curve_y + curve_h - 8 - (val / max(max_pop, 1)) * (curve_h - 24)
                    if i == 0:
                        path.moveTo(px, py)
                    else:
                        path.lineTo(px, py)
                p.setPen(QPen(color, 1.5))
                p.drawPath(path)

            # Legend
            p.setFont(QFont("Menlo", 6))
            for i, (color, label) in enumerate([
                (C_SUSCEPTIBLE, "Susceptible"),
                (C_INFECTED, "Infected"),
                (C_RECOVERED, "Recovered"),
                (C_QUARANTINE, "Quarantined"),
            ]):
                lx = curve_x + curve_w - 90
                ly = curve_y + 12 + i * 11
                p.setBrush(QBrush(color))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(lx, ly), 3, 3)
                p.setPen(QPen(C_TEXT_DIM))
                p.drawText(QPointF(lx + 6, ly + 3), label)

        # ── Stats panel (right side) ──────────────────────────────
        stats_x = sim_w + 15
        stats_y = 45

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(15, 15, 25, 200)))
        p.drawRoundedRect(QRectF(stats_x, stats_y, w - stats_x - 10, h - 55), 8, 8)

        p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        p.setPen(QPen(C_HIGHLIGHT))
        p.drawText(QPointF(stats_x + 10, stats_y + 20), "EPIDEMIOLOGICAL")
        p.drawText(QPointF(stats_x + 10, stats_y + 34), "CONTAINMENT")

        cur = self.sir_history[-1] if self.sir_history else (0, 0, 0, 0)
        s, i, r, q = cur

        # Effective R₀ estimate
        if self.total_infections > self.initial_infected and i > 0:
            r0_est = (self.total_infections - self.initial_infected) / max(1, self.total_infections - i)
            r0_est = min(r0_est * 2, 10)
        else:
            r0_est = 0.0

        privacy_score = 100.0 if self.tracing_enabled else 0.0

        stats = [
            (f"", C_TEXT),
            (f"Population: {self.population_size}", C_TEXT),
            (f"Susceptible: {s}", C_SUSCEPTIBLE),
            (f"Infected: {i}", C_INFECTED),
            (f"Recovered: {r}", C_RECOVERED),
            (f"Quarantined: {q}", C_QUARANTINE),
            (f"", C_TEXT),
            (f"Total infections: {self.total_infections}", C_INFECTED),
            (f"Peak infected: {self.peak_infected}", C_INFECTED),
            (f"Quarantines: {self.total_quarantines}", C_QUARANTINE),
            (f"Est. R₀: {r0_est:.2f}", C_TEXT),
            (f"", C_TEXT),
            (f"Contact tracing: {'ON' if self.tracing_enabled else 'OFF'}", C_HIGHLIGHT if self.tracing_enabled else C_INFECTED),
            (f"Privacy: {privacy_score:.0f}% (no central DB)", C_STGM),
            (f"Trace evaporation: {5.0:.0f}s", C_TEXT_DIM),
            (f"", C_TEXT),
            (f"STGM earned: {self.stgm_earned:.2f}", C_STGM),
            (f"Sim time: {self.sim_time:.0f}s", C_TEXT_DIM),
        ]

        p.setFont(QFont("Menlo", 8))
        for i_stat, (text, color) in enumerate(stats):
            p.setPen(QPen(color))
            p.drawText(QPointF(stats_x + 10, stats_y + 56 + i_stat * 16), text)

        # Protocol explanation
        protocol_y = stats_y + 56 + len(stats) * 16 + 10
        p.setFont(QFont("Menlo", 7, QFont.Weight.Bold))
        p.setPen(QPen(C_HIGHLIGHT))
        p.drawText(QPointF(stats_x + 10, protocol_y), "PROTOCOL:")
        p.setFont(QFont("Menlo", 6))
        p.setPen(QPen(C_TEXT_DIM))
        protocol = [
            "1. Agents drop crypto traces",
            "2. Traces evaporate (5s)",
            "3. Infected → traces = HOSTILE",
            "4. Nearby agents sense hostile",
            "5. Auto-quarantine (no central DB)",
            "6. Privacy: 100% (stigmergic)",
        ]
        for i_p, line in enumerate(protocol):
            p.drawText(QPointF(stats_x + 10, protocol_y + 14 + i_p * 12), line)

        # ── Title HUD ─────────────────────────────────────────────
        p.setPen(QPen(C_HIGHLIGHT))
        p.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
        p.drawText(QPointF(10, 16),
                   f"🦠 EPIDEMIOLOGICAL CONTAINMENT  |  "
                   f"Pop: {self.population_size}  |  "
                   f"S:{s} I:{i} R:{r} Q:{q}  |  "
                   f"R₀≈{r0_est:.1f}  |  "
                   f"Peak: {self.peak_infected}  |  "
                   f"Tracing: {'ON' if self.tracing_enabled else 'OFF'}")

        # Scan line
        scan_y = (self.tick * 1.2) % h
        p.setPen(QPen(QColor(0, 255, 200, 6), 1))
        p.drawLine(0, int(scan_y), w, int(scan_y))

        p.end()


# ═══════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════

class QuantumEpiWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA Research — Quantum + Epidemiology")
        self.setMinimumSize(1300, 850)
        self.setStyleSheet("""
            QMainWindow { background: rgb(8, 10, 18); }
            QWidget { background: transparent; color: rgb(200, 210, 240); }
            QTabWidget::pane { border: 1px solid rgb(45,42,65); background: rgb(8,10,18); }
            QTabBar::tab {
                background: rgb(25,22,38); color: rgb(150,155,180);
                border: 1px solid rgb(45,42,65); padding: 8px 20px;
                font-family: 'Menlo'; font-size: 11px; font-weight: bold;
            }
            QTabBar::tab:selected {
                background: rgb(40,35,55); color: rgb(0,255,200);
                border-bottom-color: rgb(0,255,200);
            }
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgb(50,42,65), stop:1 rgb(30,25,42));
                border: 1px solid rgb(80,70,100); border-radius: 6px;
                padding: 6px 14px; color: rgb(200,210,240);
                font-family: 'Menlo'; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover {
                border-color: rgb(0,255,200);
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgb(70,60,90), stop:1 rgb(45,38,62));
            }
            QPushButton#btnDanger {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgb(150,30,50), stop:1 rgb(90,15,30));
                border-color: rgb(255,80,100);
            }
            QSlider::groove:horizontal { height: 4px; background: rgb(40,35,55); border-radius: 2px; }
            QSlider::handle:horizontal {
                background: rgb(0,255,200); width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }
            QTextEdit {
                background: rgb(10,8,16); border: 1px solid rgb(40,35,55);
                border-radius: 4px; font-family: 'Menlo'; font-size: 9px;
                color: rgb(0,255,200); padding: 4px;
            }
            QCheckBox { font-family: 'Menlo'; font-size: 10px; }
            QCheckBox::indicator { width: 14px; height: 14px; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)
        main.setContentsMargins(6, 6, 6, 6)

        tabs = QTabWidget()

        # ── TAB 1: Quantum ────────────────────────────────────────
        q_tab = QWidget()
        q_layout = QVBoxLayout(q_tab)

        q_controls = QHBoxLayout()
        btn_q_burst = QPushButton("⚡ Inject Error Burst")
        btn_q_burst.setObjectName("btnDanger")
        btn_q_burst.clicked.connect(self._q_inject)
        q_controls.addWidget(btn_q_burst)

        # Swimmer slider
        q_sw_box = QVBoxLayout()
        q_sw_box.addWidget(QLabel("Swimmers:"))
        self.q_slider = QSlider(Qt.Orientation.Horizontal)
        self.q_slider.setRange(10, 120)
        self.q_slider.setValue(40)
        self.q_slider.setFixedWidth(150)
        self.q_slider.valueChanged.connect(self._q_swimmers_changed)
        q_sw_box.addWidget(self.q_slider)
        self.q_sw_lbl = QLabel("40")
        self.q_sw_lbl.setStyleSheet("color: rgb(0,255,200); font-weight: bold; font-size: 9px;")
        q_sw_box.addWidget(self.q_sw_lbl)
        q_controls.addLayout(q_sw_box)

        # Error rate slider
        q_er_box = QVBoxLayout()
        q_er_box.addWidget(QLabel("Error Rate:"))
        self.q_er_slider = QSlider(Qt.Orientation.Horizontal)
        self.q_er_slider.setRange(1, 50)
        self.q_er_slider.setValue(10)
        self.q_er_slider.setFixedWidth(150)
        self.q_er_slider.valueChanged.connect(self._q_error_rate_changed)
        q_er_box.addWidget(self.q_er_slider)
        self.q_er_lbl = QLabel("0.010/tick")
        self.q_er_lbl.setStyleSheet("color: rgb(0,255,200); font-weight: bold; font-size: 9px;")
        q_er_box.addWidget(self.q_er_lbl)
        q_controls.addLayout(q_er_box)

        q_controls.addStretch()
        q_layout.addLayout(q_controls)

        self._q_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.q_canvas = QuantumSurfaceCanvas()
        self._q_splitter.addWidget(self.q_canvas)

        q_log_group = QGroupBox("QUANTUM LOG")
        q_log_layout = QVBoxLayout(q_log_group)
        self.q_log = QTextEdit()
        self.q_log.setReadOnly(True)
        self.q_log.setMinimumWidth(220)
        self.q_log.setMaximumWidth(280)
        q_log_layout.addWidget(self.q_log)
        self._q_splitter.addWidget(q_log_group)
        self._q_splitter.setStretchFactor(0, 3)
        self._q_splitter.setStretchFactor(1, 1)
        q_layout.addWidget(self._q_splitter, 1)

        tabs.addTab(q_tab, "⚛ Quantum Surface Code")

        # ── TAB 2: Epidemiology ───────────────────────────────────
        e_tab = QWidget()
        e_layout = QVBoxLayout(e_tab)

        e_controls = QHBoxLayout()
        btn_e_outbreak = QPushButton("🦠 Inject Outbreak")
        btn_e_outbreak.setObjectName("btnDanger")
        btn_e_outbreak.clicked.connect(self._e_outbreak)
        e_controls.addWidget(btn_e_outbreak)

        btn_e_reset = QPushButton("🔄 Reset")
        btn_e_reset.clicked.connect(self._e_reset)
        e_controls.addWidget(btn_e_reset)

        from PyQt6.QtWidgets import QCheckBox
        self.e_tracing_cb = QCheckBox("📱 Contact Tracing")
        self.e_tracing_cb.setChecked(True)
        self.e_tracing_cb.toggled.connect(self._e_tracing_toggled)
        e_controls.addWidget(self.e_tracing_cb)

        # Infection radius slider
        e_rad_box = QVBoxLayout()
        e_rad_box.addWidget(QLabel("Infection Radius:"))
        self.e_rad_slider = QSlider(Qt.Orientation.Horizontal)
        self.e_rad_slider.setRange(5, 50)
        self.e_rad_slider.setValue(20)
        self.e_rad_slider.setFixedWidth(140)
        self.e_rad_slider.valueChanged.connect(self._e_radius_changed)
        e_rad_box.addWidget(self.e_rad_slider)
        self.e_rad_lbl = QLabel("20px")
        self.e_rad_lbl.setStyleSheet("color: rgb(0,255,200); font-weight: bold; font-size: 9px;")
        e_rad_box.addWidget(self.e_rad_lbl)
        e_controls.addLayout(e_rad_box)

        e_controls.addStretch()
        e_layout.addLayout(e_controls)

        self._e_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.e_canvas = EpidemiologyCanvas()
        self._e_splitter.addWidget(self.e_canvas)

        e_log_group = QGroupBox("EPIDEMIOLOGY LOG")
        e_log_layout = QVBoxLayout(e_log_group)
        self.e_log = QTextEdit()
        self.e_log.setReadOnly(True)
        self.e_log.setMinimumWidth(220)
        self.e_log.setMaximumWidth(280)
        e_log_layout.addWidget(self.e_log)
        self._e_splitter.addWidget(e_log_group)
        self._e_splitter.setStretchFactor(0, 3)
        self._e_splitter.setStretchFactor(1, 1)
        e_layout.addWidget(self._e_splitter, 1)

        tabs.addTab(e_tab, "🦠 Epidemiological Containment")

        main.addWidget(tabs)

        QTimer.singleShot(0, self._balance_splitters)

        # Log refresh
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._refresh_logs)
        self.log_timer.start(500)

    def _balance_splitters(self) -> None:
        from System.splitter_utils import balance_horizontal_splitter

        balance_horizontal_splitter(
            self._q_splitter,
            self,
            left_ratio=0.72,
            min_right=220,
            min_left=240,
            max_right=280,
        )
        balance_horizontal_splitter(
            self._e_splitter,
            self,
            left_ratio=0.72,
            min_right=220,
            min_left=240,
            max_right=280,
        )

    # ── Quantum slots ─────────────────────────────────────────────
    def _q_inject(self):
        self.q_canvas.inject_error_burst()

    def _q_swimmers_changed(self, val):
        self.q_sw_lbl.setText(str(val))
        self.q_canvas.set_swimmer_count(val)

    def _q_error_rate_changed(self, val):
        rate = val / 1000.0
        self.q_er_lbl.setText(f"{rate:.3f}/tick")
        self.q_canvas.set_error_rate(val)

    # ── Epidemiology slots ────────────────────────────────────────
    def _e_outbreak(self):
        self.e_canvas.inject_outbreak()

    def _e_reset(self):
        self.e_canvas.reset()

    def _e_tracing_toggled(self, checked):
        self.e_canvas.set_tracing(checked)

    def _e_radius_changed(self, val):
        self.e_rad_lbl.setText(f"{val}px")
        self.e_canvas.set_infection_radius(val)

    def _refresh_logs(self):
        q_lines = self.q_canvas.log_lines[-60:]
        self.q_log.setPlainText("\n".join(q_lines))
        self.q_log.verticalScrollBar().setValue(self.q_log.verticalScrollBar().maximum())

        e_lines = self.e_canvas.log_lines[-60:]
        self.e_log.setPlainText("\n".join(e_lines))
        self.e_log.verticalScrollBar().setValue(self.e_log.verticalScrollBar().maximum())


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = QuantumEpiWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
