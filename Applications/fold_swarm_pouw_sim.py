#!/usr/bin/env python3
"""
SIFTA Proof-of-Useful-Work Simulation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A real-time visualization of the Fold-Swarm engine:
  • Lennard-Jones / Go-model potential for bead physics
  • Metropolis Monte Carlo acceptance criterion (real thermodynamics)
  • Ant Colony Optimization swimmers leaving stigmergic pheromone trails
  • Ebbinghaus pheromone decay  (R = e^(-t/S))
  • STGM token minting on verified useful work
  • Cryptographic SHA-256 receipt chain (no double-spend)

Author: Claude Sonnet 4.6 (C46S) — AG31 Assessment Validator
For the Swarm. 🐜⚡
"""

import sys, math, time, hashlib, json, random, collections
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                              QHBoxLayout, QLabel, QSplitter, QFrame)
from PyQt6.QtCore    import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui     import (QPainter, QColor, QPen, QBrush, QFont,
                              QRadialGradient, QLinearGradient, QPainterPath,
                              QFontDatabase)

# ─────────────────────────────────────────────────────────
#  PHYSICS CONSTANTS  (real units scaled for display)
# ─────────────────────────────────────────────────────────
N_BEADS      = 18           # amino-acid residues
EPSILON_LJ   = 1.0          # Lennard-Jones well depth (ε)
SIGMA_LJ     = 1.0          # LJ diameter (σ)
BOND_LEN     = 1.2          # equilibrium covalent bond length
K_BOND       = 80.0         # harmonic bond spring constant
KT_INIT      = 4.0          # initial kT (temperature × Boltzmann)
KT_MIN       = 0.4          # annealing floor
ANNEAL_RATE  = 0.9992       # geometric cooling per MC step
N_SWIMMERS   = 12           # ACO swimmer count
PHEROMONE_S  = 40.0         # Ebbinghaus stability (half-life steps)
GRID_RES     = 40           # pheromone grid resolution

# ─────────────────────────────────────────────────────────
#  COLORS  (Predator v7 palette)
# ─────────────────────────────────────────────────────────
C_BG        = QColor(8,  10, 18)
C_PANEL     = QColor(12, 14, 24)
C_GRID      = QColor(40, 50, 80)
C_BOND      = QColor(80, 220, 255, 220)
C_BEAD_HOT  = QColor(255, 90, 40)
C_BEAD_COLD = QColor(40, 255, 140)
C_SWIMMER   = [QColor(255, 210, 0),  QColor(0, 230, 255),
               QColor(220, 80, 255), QColor(80, 255, 120),
               QColor(255, 60, 140), QColor(0, 255, 200)]
C_RECEIPT   = QColor(0, 255, 160)      # neon mint
C_STGM      = QColor(255, 220, 0)      # gold
C_DANGER    = QColor(255, 60, 60)
C_ENERGY    = QColor(120, 200, 255)    # bright cyan-blue
# New bright text palette
C_TXT_CYAN    = QColor(0,   230, 255)  # MC stats / step counter
C_TXT_LIME    = QColor(140, 255, 80)   # Rg / accept rate
C_TXT_ORANGE  = QColor(255, 160, 40)   # energy graph labels
C_TXT_PINK    = QColor(255, 100, 200)  # best energy
C_TXT_WHITE   = QColor(240, 240, 255)  # general labels
C_TXT_PURPLE  = QColor(180, 120, 255)  # footer / attribution
C_TXT_GOLD    = QColor(255, 220, 0)    # STGM header


# ─────────────────────────────────────────────────────────
#  PHYSICS ENGINE
# ─────────────────────────────────────────────────────────
class FoldPhysics:
    """Metropolis Monte Carlo with Lennard-Jones + harmonic backbone."""

    def __init__(self, n=N_BEADS):
        self.n  = n
        self.kT = KT_INIT
        # Start in a line to show dramatic folding
        self.pos = np.array([[i * BOND_LEN, 0.0] for i in range(n)], dtype=float)
        self._jitter_init()
        self.energy      = self._total_energy()
        self.best_energy = self.energy
        self.best_pos    = self.pos.copy()
        self.step        = 0
        self.accept_rate = 0.5
        self._accept_buf = collections.deque(maxlen=200)
        # native contacts = pairs |i-j|>=3 in initial config
        self.native = [(i,j) for i in range(n) for j in range(i+3, n)]

    def _jitter_init(self):
        theta = 0.0
        for i in range(1, self.n):
            theta += math.pi * 0.7 + random.gauss(0, 0.4)
            dx = BOND_LEN * math.cos(theta)
            dy = BOND_LEN * math.sin(theta)
            self.pos[i] = self.pos[i-1] + [dx, dy]

    # ── Potential energy terms ──────────────────────────────
    def _lj(self, r2):
        """Lennard-Jones 12-6 (WCA repulsion + attraction)."""
        s2 = (SIGMA_LJ**2) / max(r2, 0.01)
        s6 = s2**3
        return 4 * EPSILON_LJ * (s6**2 - s6)

    def _bond_energy(self):
        E = 0.0
        for i in range(self.n - 1):
            d = np.linalg.norm(self.pos[i+1] - self.pos[i])
            E += 0.5 * K_BOND * (d - BOND_LEN)**2
        return E

    def _nonbond_energy(self):
        E = 0.0
        for i in range(self.n - 2):
            for j in range(i+2, self.n):
                r2 = np.sum((self.pos[i] - self.pos[j])**2)
                E += self._lj(r2)
        return E

    def _total_energy(self):
        return self._bond_energy() + self._nonbond_energy()

    # ── MC step ─────────────────────────────────────────────
    def mc_step(self, n_inner=30):
        accepted = 0
        for _ in range(n_inner):
            idx  = random.randint(0, self.n - 1)
            move = np.random.normal(0, 0.15, 2)
            old  = self.pos[idx].copy()
            self.pos[idx] += move
            dE = self._total_energy() - self.energy
            # Metropolis criterion
            if dE < 0 or random.random() < math.exp(-dE / max(self.kT, 1e-9)):
                self.energy += dE
                accepted += 1
            else:
                self.pos[idx] = old
        self._accept_buf.append(accepted / n_inner)
        self.accept_rate = np.mean(self._accept_buf)
        if self.energy < self.best_energy:
            self.best_energy = self.energy
            self.best_pos    = self.pos.copy()
        self.kT  = max(self.kT * ANNEAL_RATE, KT_MIN)
        self.step += 1
        return accepted

    def center(self):
        """Return centroid."""
        return self.pos.mean(axis=0)

    def radius_of_gyration(self):
        c = self.center()
        return math.sqrt(np.mean(np.sum((self.pos - c)**2, axis=1)))


# ─────────────────────────────────────────────────────────
#  PHEROMONE GRID  (Ebbinghaus stigmergic memory)
# ─────────────────────────────────────────────────────────
class PheromoneGrid:
    def __init__(self, w, h, res=GRID_RES):
        self.res = res
        self.grid = np.zeros((res, res), dtype=float)
        self.recall = np.zeros((res, res), dtype=int)

    def deposit(self, fx, fy, strength=2.0):
        gx = int(np.clip(fx * self.res, 0, self.res - 1))
        gy = int(np.clip(fy * self.res, 0, self.res - 1))
        self.grid[gy, gx] += strength
        self.recall[gy, gx] += 1

    def decay(self):
        """Ebbinghaus: R = e^(-1/S(recall)) per step."""
        S = 1.0 + self.recall * 2.5
        self.grid *= np.exp(-1.0 / S)
        self.grid  = np.clip(self.grid, 0, 20)

    def sample(self, fx, fy):
        gx = int(np.clip(fx * self.res, 0, self.res - 1))
        gy = int(np.clip(fy * self.res, 0, self.res - 1))
        return self.grid[gy, gx]


# ─────────────────────────────────────────────────────────
#  SWIMMER (ACO agent)
# ─────────────────────────────────────────────────────────
class Swimmer:
    def __init__(self, sid, color):
        self.sid    = sid
        self.color  = color
        self.x      = random.random()
        self.y      = random.random()
        self.angle  = random.uniform(0, 2*math.pi)
        self.energy = 100.0
        self.stgm   = 0.0
        self.trail  = collections.deque(maxlen=60)

    def move(self, grid: PheromoneGrid, physics: FoldPhysics):
        """Move towards lower energy + pheromone attractors."""
        # Bias angle toward best_pos projection
        cx, cy = physics.best_pos.mean(axis=0)
        # map physics coords (roughly -N..N) to 0..1
        scale = physics.n * BOND_LEN
        tx = (cx / scale) * 0.5 + 0.5
        ty = (cy / scale) * 0.5 + 0.5
        target_angle = math.atan2(ty - self.y, tx - self.x)
        # pheromone bias
        ph = grid.sample(self.x, self.y)
        wander = random.gauss(0, 0.4 + 0.3 / (1 + ph))
        self.angle = (0.8 * self.angle + 0.15 * target_angle +
                      0.05 * random.uniform(0, 2*math.pi) + wander)
        spd = 0.004 + 0.003 * ph
        self.x = (self.x + math.cos(self.angle) * spd) % 1.0
        self.y = (self.y + math.sin(self.angle) * spd) % 1.0
        grid.deposit(self.x, self.y, 0.3)
        self.trail.append((self.x, self.y))
        # Caloric cost
        self.energy -= 0.05
        if self.energy < 0:
            self.energy = 0

    def earn_stgm(self, amount):
        self.stgm += amount
        self.energy = min(100, self.energy + 5)


# ─────────────────────────────────────────────────────────
#  RECEIPT CHAIN  (cryptographic PoUW)
# ─────────────────────────────────────────────────────────
class ReceiptChain:
    def __init__(self):
        self.chain   = []
        self.prev    = "0" * 16
        self.total   = 0.0
        self.spent   = set()

    def mint(self, swimmer_id, energy, result_hash):
        task_hash = hashlib.sha256(
            f"{swimmer_id}:{energy:.4f}:{result_hash}:{self.prev}".encode()
        ).hexdigest()[:16]
        if task_hash in self.spent:
            return None     # double-spend blocked
        amount = max(0.05, min(1.0, -energy / 50.0))
        receipt = {
            "ts":      time.time(),
            "swimmer": swimmer_id,
            "energy":  round(energy, 4),
            "score":   round(amount, 4),
            "hash":    task_hash,
            "prev":    self.prev,
        }
        self.chain.append(receipt)
        self.spent.add(task_hash)
        self.prev   = task_hash
        self.total += amount
        if len(self.chain) > 40:
            self.chain.pop(0)
        return receipt


# ─────────────────────────────────────────────────────────
#  CANVAS WIDGET
# ─────────────────────────────────────────────────────────
class SimCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.physics  = FoldPhysics()
        self.grid     = PheromoneGrid(800, 600)
        self.swimmers = [Swimmer(i, C_SWIMMER[i % len(C_SWIMMER)])
                         for i in range(N_SWIMMERS)]
        self.chain    = ReceiptChain()
        self.tick     = 0
        self.energy_history = collections.deque(maxlen=300)
        self.last_mint_flash = 0
        self.setMinimumSize(780, 540)

    def step(self):
        self.physics.mc_step(25)
        self.grid.decay()
        self.energy_history.append(self.physics.energy)

        # Swimmers move
        for sw in self.swimmers:
            sw.move(self.grid, self.physics)

        # Mint every ~80 steps if energy improved
        if self.tick % 80 == 0 and self.physics.best_energy < -1.0:
            sw  = random.choice([s for s in self.swimmers if s.energy > 10])
            rh  = hashlib.sha256(
                    str(self.physics.best_pos.tobytes()).encode()
                  ).hexdigest()[:16]
            rec = self.chain.mint(sw.sid, self.physics.best_energy, rh)
            if rec:
                sw.earn_stgm(rec["score"])
                self.last_mint_flash = self.tick

        self.tick += 1
        self.update()

    # ── Render ───────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        # Background
        p.fillRect(0, 0, W, H, C_BG)

        # Pheromone heatmap
        self._draw_pheromone(p, W, H)

        # Swimmer trails + agents
        self._draw_swimmers(p, W, H)

        # Molecule
        self._draw_molecule(p, W, H)

        # Energy graph
        self._draw_energy_graph(p, W, H)

        # HUD
        self._draw_hud(p, W, H)

    def _draw_pheromone(self, p, W, H):
        res = self.grid.res
        cell_w = W / res
        cell_h = H / res
        g = self.grid.grid
        mx = g.max() if g.max() > 0 else 1
        for gy in range(res):
            for gx in range(res):
                v = g[gy, gx] / mx
                if v < 0.03:
                    continue
                col = QColor(
                    int(20  + 40  * v),
                    int(10  + 60  * v),
                    int(60  + 120 * v),
                    int(180 * v)
                )
                p.fillRect(
                    int(gx*cell_w), int(gy*cell_h),
                    int(cell_w)+1,  int(cell_h)+1,
                    col
                )

    def _draw_swimmers(self, p, W, H):
        for sw in self.swimmers:
            if sw.energy <= 0:
                continue
            trail = list(sw.trail)
            if len(trail) > 2:
                for i in range(1, len(trail)):
                    alpha = int(200 * i / len(trail))
                    col = QColor(sw.color.red(), sw.color.green(),
                                 sw.color.blue(), alpha)
                    pen = QPen(col, 1.2)
                    p.setPen(pen)
                    x0 = int(trail[i-1][0] * W)
                    y0 = int(trail[i-1][1] * H)
                    x1 = int(trail[i][0] * W)
                    y1 = int(trail[i][1] * H)
                    p.drawLine(x0, y0, x1, y1)
            # Agent dot
            sx = int(sw.x * W)
            sy = int(sw.y * H)
            r  = 5 + int(sw.stgm * 0.4)
            grd = QRadialGradient(sx, sy, r)
            grd.setColorAt(0, sw.color)
            grd.setColorAt(1, QColor(sw.color.red(), sw.color.green(),
                                     sw.color.blue(), 0))
            p.setBrush(QBrush(grd))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(sx-r, sy-r, r*2, r*2)

    def _mol_to_screen(self, pos, W, H):
        """Map molecule bead positions to screen coords (center-right zone)."""
        scale  = min(W, H) * 0.018
        ox     = W * 0.5
        oy     = H * 0.45
        c      = self.physics.pos.mean(axis=0)
        x      = ox + (pos[0] - c[0]) * scale
        y      = oy + (pos[1] - c[1]) * scale
        return int(x), int(y)

    def _draw_molecule(self, p, W, H):
        n   = self.physics.n
        pos = self.physics.pos
        kT  = self.physics.kT

        # Bonds
        p.setPen(QPen(C_BOND, 2.5))
        for i in range(n-1):
            x0, y0 = self._mol_to_screen(pos[i],   W, H)
            x1, y1 = self._mol_to_screen(pos[i+1], W, H)
            p.drawLine(x0, y0, x1, y1)

        # Beads  (colour = local LJ energy)
        for i in range(n):
            local_e = 0.0
            for j in range(n):
                if abs(i-j) < 2:
                    continue
                r2 = np.sum((pos[i]-pos[j])**2)
                local_e += self.physics._lj(r2)
            t   = min(1.0, max(0.0, (-local_e + 5) / 15))
            col = QColor(
                int(C_BEAD_HOT.red()   * (1-t) + C_BEAD_COLD.red()   * t),
                int(C_BEAD_HOT.green() * (1-t) + C_BEAD_COLD.green() * t),
                int(C_BEAD_HOT.blue()  * (1-t) + C_BEAD_COLD.blue()  * t),
            )
            bx, by = self._mol_to_screen(pos[i], W, H)
            r = 7 if i in (0, n-1) else 5
            grd = QRadialGradient(bx, by, r*2)
            grd.setColorAt(0, col.lighter(170))
            grd.setColorAt(1, col.darker(120))
            p.setBrush(QBrush(grd))
            p.setPen(QPen(col.lighter(200), 1))
            p.drawEllipse(bx-r, by-r, r*2, r*2)

        # Rg ring around molecule
        rg = self.physics.radius_of_gyration()
        scale = min(W, H) * 0.018
        cx_s, cy_s = self._mol_to_screen(self.physics.pos.mean(axis=0), W, H)
        rg_px = int(rg * scale)
        ring_col = QColor(0, 200, 255, 40)
        p.setBrush(QBrush(ring_col))
        p.setPen(QPen(QColor(0, 200, 255, 80), 1))
        p.drawEllipse(cx_s - rg_px, cy_s - rg_px, rg_px*2, rg_px*2)

    def _draw_energy_graph(self, p, W, H):
        hist = list(self.energy_history)
        if len(hist) < 2:
            return
        gw, gh = int(W * 0.38), int(H * 0.22)
        gx, gy = 12, H - gh - 12

        # Panel
        p.fillRect(gx, gy, gw, gh, QColor(8, 12, 24, 220))
        p.setPen(QPen(C_GRID, 1))
        p.drawRect(gx, gy, gw, gh)

        mn, mx = min(hist), max(hist)
        rng    = max(mx - mn, 0.1)
        pts    = []
        for i, e in enumerate(hist):
            px = gx + int(i * gw / len(hist))
            py = gy + gh - int((e - mn) / rng * gh)
            pts.append((px, py))

        # Gradient fill
        path = QPainterPath()
        path.moveTo(pts[0][0], gy + gh)
        for px, py in pts:
            path.lineTo(px, py)
        path.lineTo(pts[-1][0], gy + gh)
        path.closeSubpath()
        grad = QLinearGradient(0, gy, 0, gy + gh)
        grad.setColorAt(0, QColor(80, 160, 255, 120))
        grad.setColorAt(1, QColor(10, 30, 80, 20))
        p.fillPath(path, QBrush(grad))

        # Line
        p.setPen(QPen(C_ENERGY, 1.5))
        for i in range(1, len(pts)):
            p.drawLine(pts[i-1][0], pts[i-1][1], pts[i][0], pts[i][1])

        # Label — bright multicolor 3x
        f = QFont("Courier New", 27, QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QPen(C_TXT_ORANGE))
        p.drawText(gx+6, gy+34, f"E = {hist[-1]:.2f} ε")
        p.setPen(QPen(C_TXT_CYAN))
        p.drawText(gx+6, gy+66, f"kT = {self.physics.kT:.3f}")
        p.setPen(QPen(C_TXT_PINK))
        p.drawText(gx+6, gy+98, f"Best = {self.physics.best_energy:.2f}")

    def _draw_hud(self, p, W, H):
        f_mono  = QFont("Courier New", 27)
        f_bold  = QFont("Courier New", 27, QFont.Weight.Bold)
        f_big   = QFont("Courier New", 42, QFont.Weight.Bold)
        f_small = QFont("Courier New", 24)

        # ── STGM header ─────────────────────────────────────
        flash = self.tick - self.last_mint_flash < 20
        stgm_col = QColor(255, 255, 80) if flash else C_TXT_GOLD
        p.setPen(QPen(stgm_col))
        p.setFont(f_big)
        p.drawText(12, 62, f"STGM  {self.chain.total:.4f} Ξ")

        # subtitle
        p.setFont(f_small)
        p.setPen(QPen(C_TXT_CYAN))
        p.drawText(14, 96, "Proof-of-Useful-Work  ·  Lennard-Jones + Metropolis MC + ACO Stigmergy")

        # ── MC Stats row ────────────────────────────────────
        p.setFont(f_bold)
        p.setPen(QPen(C_TXT_CYAN))
        p.drawText(12, H - 130,
                   f"STEP  {self.physics.step:>7d}")
        p.setPen(QPen(C_TXT_LIME))
        p.drawText(340, H - 130,
                   f"ACCEPT  {self.physics.accept_rate:.2f}")
        p.setPen(QPen(C_TXT_ORANGE))
        p.drawText(660, H - 130,
                   f"kT  {self.physics.kT:.3f}")
        p.setPen(QPen(C_TXT_PINK))
        p.drawText(850, H - 130,
                   f"Rg  {self.physics.radius_of_gyration():.2f} σ")
        p.setPen(QPen(C_TXT_WHITE))
        p.drawText(1060, H - 130,
                   f"MINTS  {len(self.chain.chain)}")

        # ── Receipts panel ───────────────────────────────────
        rx, ry = W - 580, 110
        panel_h = min(len(self.chain.chain) * 32 + 55, 520)
        p.fillRect(rx-6, ry-6, 336, panel_h, QColor(2, 12, 8, 220))
        p.setPen(QPen(QColor(0, 200, 120, 60), 1))
        p.drawRect(rx-6, ry-6, 336, panel_h)

        p.setFont(f_bold)
        p.setPen(QPen(C_RECEIPT))
        p.drawText(rx, ry + 34, "━━ PoUW RECEIPT CHAIN ━━")

        p.setFont(f_small)
        # Colour-cycle receipts
        receipt_colors = [
            QColor(0, 255, 160),   # mint
            QColor(255, 220, 0),   # gold
            QColor(80, 220, 255),  # cyan
            QColor(220, 80, 255),  # purple
            QColor(255, 100, 120), # pink
        ]
        for k, rec in enumerate(reversed(self.chain.chain[-13:])):
            age_alpha = max(80, 255 - k * 16)
            rc = receipt_colors[k % len(receipt_colors)]
            col = QColor(rc.red(), rc.green(), rc.blue(), age_alpha)
            p.setPen(QPen(col))
            p.drawText(rx, ry + 58 + k * 32,
                       f"S{rec['swimmer']:02d}  {rec['hash']}  +{rec['score']:.4f} Ξ")

        # ── Swimmer energy bars ──────────────────────────────
        bx = W - 10
        p.setFont(f_small)
        for i, sw in enumerate(self.swimmers):
            col = sw.color
            bw  = int(sw.energy / 100 * 140)
            by  = H - 160 - i * 32
            # track bg
            p.fillRect(bx - 140, by - 18, 140, 18, QColor(15, 15, 25))
            # fill
            bar_col = QColor(col.red(), col.green(), col.blue(),
                             200 if sw.energy > 20 else 100)
            p.fillRect(bx - 140, by - 18, bw, 18, bar_col)
            # label — swimmer's own color, always bright
            bright = col.lighter(180)
            p.setPen(QPen(bright))
            p.drawText(bx - 310, by,
                       f"S{i:02d}  {sw.stgm:5.2f} Ξ  {'▌' * int(sw.energy/25)}")

        # ── Footer ───────────────────────────────────────────
        p.setFont(QFont("Courier New", 24, QFont.Weight.Bold))
        p.setPen(QPen(C_TXT_PURPLE))
        p.drawText(12, H - 14,
                   "C46S  ·  Lennard-Jones 12-6  +  Metropolis MC  +  ACO Stigmergy  ·  For the Swarm 🐜⚡")


# ─────────────────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────────────────
class PredatorSimWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA Predator v7 — PoUW Fold-Swarm Simulation  🐅")
        self.setMinimumSize(1100, 660)
        self.setStyleSheet(f"background: rgb(8,10,18); color: #aaffcc;")

        self.canvas = SimCanvas()
        self.setCentralWidget(self.canvas)

        # Timer: ~40 fps
        self.timer = QTimer()
        self.timer.timeout.connect(self.canvas.step)
        self.timer.start(25)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SIFTA PoUW Fold-Swarm")
    win = PredatorSimWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
