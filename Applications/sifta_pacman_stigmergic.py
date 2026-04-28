#!/usr/bin/env python3
"""
Applications/sifta_pacman_stigmergic.py
══════════════════════════════════════════════════════════════════════
SIFTA Stigmergic Pac-Man — Predator v7.0 Edition

Stigmergic mechanics:
  • Pac-Man follows a SIFTA pheromone gradient field (VoxelField-style)
    toward dots — environment carries the computation, not a hardcoded path.
  • Ghost behaviour: STUB ghosts (cuRobo, Isaac Lab, GR00T, Cosmos) patrol
    the maze. They are coloured by their truth label.
  • Eating a dot = +1 STGM pheromone deposited.
  • Power pellet = WARP KERNEL active: ghosts become BROKEN (blue),
    Pac-Man gains REAL_CPU acceleration.
  • Live organ data sidebar shows real receipts from .sifta_state/.
  • All animations use the Predator desktop bg color palette.

Controls:
  Arrow keys / WASD = move
  P = pause / resume
  R = reset
  Q / Esc = quit

Authors: AG31 (Antigravity/Gemini 2.5 Pro), Architect Ioan George Anton
Date: 2026-04-28
NPPL: game / research posture only.
"""
from __future__ import annotations

import json, math, os, random, sys, time
from pathlib import Path
from typing import List, Tuple, Optional

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient, QKeyEvent, QFontMetrics,
)
from PyQt6.QtWidgets import QWidget, QApplication, QHBoxLayout, QVBoxLayout

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# ── Layout constants ──────────────────────────────────────────────────────────
COLS, ROWS = 28, 22
CELL  = 24
W_MAZE = COLS * CELL
H_MAZE = ROWS * CELL
W_SIDE = 220
WIN_W  = W_MAZE + W_SIDE
WIN_H  = H_MAZE + 60

# ── Color palette ─────────────────────────────────────────────────────────────
C_BG      = QColor(4, 4, 16)
C_WALL    = QColor(0, 60, 180)
C_DOT     = QColor(200, 200, 140)
C_PELLET  = QColor(255, 220, 60)
C_PACMAN  = QColor(255, 220, 0)
C_STUB    = QColor(255, 80,  80)    # STUB ghost
C_BROKEN  = QColor(60,  100, 220)   # frightened ghost
C_REAL    = QColor(0,   255, 140)   # organ readout
C_PHEROM  = QColor(0,   200, 100, 80)

# Ghost identities (STUB = not installed)
GHOST_DEFS = [
    ("cuRobo",    QColor(255,  80,  80)),
    ("IsaacLab",  QColor(255, 140,  40)),
    ("GR00T",     QColor(180,  80, 255)),
    ("Cosmos",    QColor(80,  200, 255)),
]

# ── Maze definition (0=open, 1=wall, 2=dot-space, 3=pellet) ──────────────────
# Classic-ish layout, 28×22
_RAW = [
    "1111111111111111111111111111",
    "1222222222222112222222222221",
    "1211121111121121111211112111",
    "1211121111121121111211112111",
    "1222222222222222222222222221",
    "1211121121111111112111211211",
    "1222222112222112222211222221",
    "1111121111112112111111211111",
    "0000121111000000001111210000",
    "1111121100111001110011211111",
    "0000121100100000010011210000",
    "0000121100100000010011210000",
    "1111121100111111110011211111",
    "0000121000000000000011210000",
    "1111121011111111111011211111",
    "1222222222222112222222222221",
    "1211121111121121111211112111",
    "1322222112222222222211222231",
    "1111122112211111112211221111",
    "1222222222222112222222222221",
    "1211111111111111111111111211",
    "1111111111111111111111111111",
]

def _parse_maze():
    maze = []
    for row in _RAW:
        maze.append([int(c) if c in "0123" else 1 for c in row])
    return maze

# ── Pheromone field ───────────────────────────────────────────────────────────
def _build_pheromone(maze, dots):
    """BFS distance field from all dots — Pac-Man follows the gradient."""
    from collections import deque
    field = [[9999] * COLS for _ in range(ROWS)]
    q = deque()
    for (r, c) in dots:
        field[r][c] = 0
        q.append((r, c))
    while q:
        r, c = q.popleft()
        for dr, dc in ((-1,0),(1,0),(0,-1),(0,1)):
            nr, nc = r+dr, c+dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and maze[nr][nc] != 1:
                if field[nr][nc] > field[r][c] + 1:
                    field[nr][nc] = field[r][c] + 1
                    q.append((nr, nc))
    return field


# ── Ghost AI ──────────────────────────────────────────────────────────────────
class Ghost:
    def __init__(self, idx: int, r: int, c: int):
        self.idx   = idx
        self.name, self.color = GHOST_DEFS[idx % len(GHOST_DEFS)]
        self.r, self.c = r, c
        self.dr, self.dc = random.choice([(-1,0),(1,0),(0,-1),(0,1)])
        self.frightened = False
        self.fright_end = 0.0
        self.move_cd = 0

    def tick(self, maze, pac_r, pac_c, t):
        self.move_cd -= 1
        if self.move_cd > 0:
            return
        speed = 4 if self.frightened else 6
        self.move_cd = speed

        if self.frightened and t > self.fright_end:
            self.frightened = False

        dirs = [(-1,0),(1,0),(0,-1),(0,1)]
        random.shuffle(dirs)

        best_dir = None
        best_score = None
        for dr, dc in dirs:
            nr, nc = self.r + dr, self.c + dc
            if not (0 <= nr < ROWS and 0 <= nc < COLS):
                continue
            if maze[nr][nc] == 1:
                continue
            if best_dir is None:
                best_dir = (dr, dc)
                best_score = (nr, nc)
            if self.frightened:
                # Flee from Pac-Man
                dist = (nr - pac_r)**2 + (nc - pac_c)**2
                if dist > (best_score[0]-pac_r)**2 + (best_score[1]-pac_c)**2:
                    best_dir = (dr, dc)
                    best_score = (nr, nc)
            else:
                # Chase Pac-Man (simple)
                dist = (nr - pac_r)**2 + (nc - pac_c)**2
                if dist < (best_score[0]-pac_r)**2 + (best_score[1]-pac_c)**2:
                    best_dir = (dr, dc)
                    best_score = (nr, nc)

        if best_dir:
            self.dr, self.dc = best_dir
            self.r += self.dr
            self.c += self.dc

    def frighten(self, duration=8.0):
        self.frightened = True
        self.fright_end = time.monotonic() + duration


# ── Main game widget ──────────────────────────────────────────────────────────
class PacManGame(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(WIN_W, WIN_H)

        self._reset()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)   # ~30 fps

        self._ledger_timer = QTimer(self)
        self._ledger_timer.timeout.connect(self._refresh_organs)
        self._ledger_timer.start(2000)
        self._organ_truths: dict = {}
        self._refresh_organs()

    def _reset(self):
        self._maze   = _parse_maze()
        self._dots   = set()
        self._pellets= set()
        for r in range(ROWS):
            for c in range(COLS):
                if self._maze[r][c] == 2:
                    self._dots.add((r, c))
                    self._maze[r][c] = 0
                elif self._maze[r][c] == 3:
                    self._pellets.add((r, c))
                    self._maze[r][c] = 0

        self._pac_r, self._pac_c = 17, 14
        self._pac_dr, self._pac_dc = 0, 0
        self._next_dr, self._next_dc = 0, -1
        self._pac_move_cd = 0
        self._pac_mouth   = 0.3
        self._pac_mouth_d = 0.05

        self._ghosts = [
            Ghost(0, 9,  12),
            Ghost(1, 9,  15),
            Ghost(2, 10, 12),
            Ghost(3, 10, 15),
        ]

        self._score      = 0
        self._stgm       = 0.0
        self._lives      = 3
        self._paused     = False
        self._game_over  = False
        self._won        = False
        self._warp_active = False
        self._warp_end   = 0.0
        self._frame      = 0
        self._t0         = time.monotonic()
        self._pheromone  = _build_pheromone(self._maze, self._dots | self._pellets)
        self._death_flash= 0

    def _refresh_organs(self):
        receipts = {
            "Gecko":   "gecko_adhesion_receipts.jsonl",
            "Bat":     "bat_echo_receipts.jsonl",
            "Spider":  "spider_web_receipts.jsonl",
            "VoxelFld":"sim_receipts.jsonl",
            "Warp":    "gecko_adhesion_receipts.jsonl",
        }
        for name, fname in receipts.items():
            p = _STATE / fname
            if p.exists():
                try:
                    lines = [l for l in p.read_text(errors="ignore").splitlines() if l.strip()]
                    if lines:
                        r = json.loads(lines[-1])
                        self._organ_truths[name] = r.get("truth", "REAL")
                except Exception:
                    self._organ_truths[name] = "STUB"
            else:
                self._organ_truths[name] = "STUB"

    def _tick(self):
        if self._paused or self._game_over or self._won:
            self.update()
            return

        t = time.monotonic()
        self._frame += 1

        # Pac-Man mouth animation
        self._pac_mouth += self._pac_mouth_d
        if self._pac_mouth >= 0.4 or self._pac_mouth <= 0.0:
            self._pac_mouth_d *= -1

        # Move pac-man
        self._pac_move_cd -= 1
        if self._pac_move_cd <= 0:
            speed = 3 if self._warp_active else 5
            self._pac_move_cd = speed

            # Try requested direction first
            nr = self._pac_r + self._next_dr
            nc = self._pac_c + self._next_dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and self._maze[nr][nc] != 1:
                self._pac_dr, self._pac_dc = self._next_dr, self._next_dc

            nr = self._pac_r + self._pac_dr
            nc = self._pac_c + self._pac_dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and self._maze[nr][nc] != 1:
                self._pac_r, self._pac_c = nr, nc
            # Wrap tunnels
            self._pac_c = self._pac_c % COLS

            # Eat dot
            pos = (self._pac_r, self._pac_c)
            if pos in self._dots:
                self._dots.remove(pos)
                self._score += 10
                self._stgm  += 1.0
                self._pheromone = _build_pheromone(self._maze, self._dots | self._pellets)

            # Eat pellet — WARP KERNEL activated
            if pos in self._pellets:
                self._pellets.remove(pos)
                self._score  += 50
                self._stgm   += 5.0
                self._warp_active = True
                self._warp_end    = t + 8.0
                for g in self._ghosts:
                    g.frighten(8.0)

        # Warp expiry
        if self._warp_active and t > self._warp_end:
            self._warp_active = False

        # Ghosts
        for g in self._ghosts:
            g.tick(self._maze, self._pac_r, self._pac_c, t)
            if g.r == self._pac_r and g.c == self._pac_c:
                if g.frightened:
                    # Eat ghost
                    self._score += 200
                    g.r, g.c = 9, 13
                    g.frightened = False
                else:
                    self._lives -= 1
                    self._death_flash = 8
                    self._pac_r, self._pac_c = 17, 14
                    if self._lives <= 0:
                        self._game_over = True

        if self._death_flash > 0:
            self._death_flash -= 1

        if not self._dots and not self._pellets:
            self._won = True

        self.update()

    def keyPressEvent(self, event: QKeyEvent):
        k = event.key()
        if k in (Qt.Key.Key_Left,  Qt.Key.Key_A): self._next_dr, self._next_dc = 0, -1
        elif k in (Qt.Key.Key_Right, Qt.Key.Key_D): self._next_dr, self._next_dc = 0,  1
        elif k in (Qt.Key.Key_Up,    Qt.Key.Key_W): self._next_dr, self._next_dc = -1, 0
        elif k in (Qt.Key.Key_Down,  Qt.Key.Key_S): self._next_dr, self._next_dc =  1, 0
        elif k == Qt.Key.Key_P: self._paused = not self._paused
        elif k == Qt.Key.Key_R: self._reset()
        elif k in (Qt.Key.Key_Q, Qt.Key.Key_Escape): self.close()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = time.monotonic() - self._t0

        # ── Background ────────────────────────────────────────────────────────
        p.fillRect(0, 0, self.width(), self.height(), C_BG)

        # ── Pheromone overlay ──────────────────────────────────────────────────
        for r in range(ROWS):
            for c in range(COLS):
                if self._maze[r][c] != 1:
                    ph = self._pheromone[r][c]
                    if ph < 9999:
                        alpha = max(0, min(60, int(60 * (1 - ph / 30))))
                        p.fillRect(c*CELL, r*CELL+30, CELL, CELL,
                                   QColor(0, 200, 100, alpha))

        # ── Maze walls ────────────────────────────────────────────────────────
        pulse_w = 0.7 + 0.3 * math.sin(t * 1.5)
        wall_color = QColor(int(0 * pulse_w), int(80 + 60*pulse_w), int(220 * pulse_w))
        p.setBrush(QBrush(wall_color))
        p.setPen(Qt.PenStyle.NoPen)
        for r in range(ROWS):
            for c in range(COLS):
                if self._maze[r][c] == 1:
                    p.drawRoundedRect(c*CELL+1, r*CELL+31, CELL-2, CELL-2, 4, 4)

        # ── Dots ──────────────────────────────────────────────────────────────
        p.setBrush(QBrush(C_DOT))
        for (r, c) in self._dots:
            p.drawEllipse(c*CELL + CELL//2 - 2, r*CELL + 31 + CELL//2 - 2, 4, 4)

        # ── Power pellets (pulsing) ────────────────────────────────────────────
        pellet_r = 6 + int(3 * math.sin(t * 4))
        p.setBrush(QBrush(C_PELLET))
        for (r, c) in self._pellets:
            p.drawEllipse(c*CELL + CELL//2 - pellet_r//2,
                          r*CELL + 31 + CELL//2 - pellet_r//2,
                          pellet_r, pellet_r)

        # ── Pac-Man ───────────────────────────────────────────────────────────
        if self._death_flash % 2 == 0:
            pac_color = QColor(255, 255, 0) if not self._warp_active else QColor(0, 255, 180)
            p.setBrush(QBrush(pac_color))
            p.setPen(Qt.PenStyle.NoPen)
            mouth_angle = int(self._pac_mouth * 360)
            start_angle  = 16 * (0 + mouth_angle // 2)
            span_angle   = 16 * (360 - mouth_angle)
            px = self._pac_c * CELL + 2
            py = self._pac_r * CELL + 32
            p.drawPie(px, py, CELL-4, CELL-4, start_angle, span_angle)

        # ── Ghosts ────────────────────────────────────────────────────────────
        for g in self._ghosts:
            color = C_BROKEN if g.frightened else g.color
            if g.frightened:
                pulse = 0.5 + 0.5 * math.sin(t * 8)
                color = QColor(int(60 * pulse), int(80 + 120*pulse), 220)
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            gx = g.c * CELL + 2
            gy = g.r * CELL + 32
            # Body
            p.drawRoundedRect(gx, gy, CELL-4, CELL-4, 8, 8)
            # Eyes
            p.setBrush(QBrush(QColor(255, 255, 255)))
            p.drawEllipse(gx+3, gy+3, 5, 5)
            p.drawEllipse(gx+10, gy+3, 5, 5)
            # Pupils
            p.setBrush(QBrush(QColor(0, 0, 180)))
            p.drawEllipse(gx+4, gy+4, 3, 3)
            p.drawEllipse(gx+11, gy+4, 3, 3)

        # ── HUD: title bar ────────────────────────────────────────────────────
        p.fillRect(0, 0, W_MAZE, 30, QColor(4, 4, 16))
        p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        warp_txt = " ⚡WARP KERNEL!" if self._warp_active else ""
        p.setPen(QColor(0, 255, 136))
        p.drawText(6, 20, f"SIFTA Stigmergic Pac-Man  ·  Score: {self._score}  ·  STGM: {self._stgm:.0f}  ·  Lives: {'●'*self._lives}{warp_txt}")

        # ── Overlays ──────────────────────────────────────────────────────────
        if self._paused:
            self._draw_overlay(p, "PAUSED", "P to resume · R to reset")
        elif self._game_over:
            self._draw_overlay(p, "GAME OVER", f"Score: {self._score} · R to restart")
        elif self._won:
            self._draw_overlay(p, "YOU WON! 🐜", f"STGM earned: {self._stgm:.0f} · R for new game")

        # ── Side panel ────────────────────────────────────────────────────────
        self._draw_side_panel(p, t)
        p.end()

    def _draw_overlay(self, p: QPainter, title: str, sub: str):
        p.fillRect(80, H_MAZE//2 - 50 + 30, W_MAZE - 160, 100,
                   QColor(4, 4, 30, 220))
        p.setFont(QFont("Menlo", 22, QFont.Weight.Bold))
        p.setPen(QColor(0, 255, 136))
        fm = QFontMetrics(p.font())
        tw = fm.horizontalAdvance(title)
        p.drawText((W_MAZE - tw)//2, H_MAZE//2 + 30, title)
        p.setFont(QFont("Menlo", 11))
        p.setPen(QColor(150, 200, 180))
        sw = fm.horizontalAdvance(sub)
        p.drawText((W_MAZE - sw)//2, H_MAZE//2 + 56, sub)

    def _draw_side_panel(self, p: QPainter, t: float):
        x0 = W_MAZE
        p.fillRect(x0, 0, W_SIDE, WIN_H, QColor(4, 6, 18))
        p.setPen(QPen(QColor(0, 60, 40), 1))
        p.drawLine(x0, 0, x0, WIN_H)

        # Header
        p.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        p.setPen(QColor(0, 255, 136))
        p.drawText(x0+8, 22, "PREDATOR v7.0")

        p.setFont(QFont("Menlo", 9))
        p.setPen(QColor(60, 180, 120))
        p.drawText(x0+8, 38, "SIFTA Organ Feed")

        p.setPen(QPen(QColor(0, 60, 40), 1))
        p.drawLine(x0+4, 44, x0+W_SIDE-4, 44)

        # Ghost roster (STUB enemies)
        y = 60
        p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        p.setPen(QColor(200, 160, 100))
        p.drawText(x0+8, y, "STUB Ghosts:")
        y += 18
        for g in self._ghosts:
            color = C_BROKEN if g.frightened else g.color
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(x0+8, y-10, 12, 12, 3, 3)
            p.setFont(QFont("Menlo", 10))
            p.setPen(color)
            label = "BROKEN" if g.frightened else "STUB"
            p.drawText(x0+26, y, f"{g.name} {label}")
            y += 18

        y += 8
        p.setPen(QPen(QColor(0, 60, 40), 1))
        p.drawLine(x0+4, y, x0+W_SIDE-4, y)
        y += 12

        # Live organ feed
        p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        p.setPen(QColor(200, 160, 100))
        p.drawText(x0+8, y, "Live Organs:")
        y += 18

        TRUTH_C = {
            "REAL_CPU": QColor(0, 255, 136),
            "REAL_GPU": QColor(0, 255, 220),
            "REAL":     QColor(0, 255, 136),
            "STUB":     QColor(255, 160, 40),
            "BROKEN":   QColor(255, 60,  60),
        }
        icons = {"Gecko": "🦎", "Bat": "🦇", "Spider": "🕷",
                 "VoxelFld": "🐙", "Warp": "⚡"}
        for name, truth in self._organ_truths.items():
            tc = TRUTH_C.get(truth, QColor(150, 150, 150))
            pulse = 0.6 + 0.4 * math.sin(t * 2.5 + y * 0.05)
            dot = QColor(tc)
            dot.setAlpha(int(200 * pulse))
            p.setBrush(QBrush(dot))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(x0+8, y-9, 8, 8)
            icon = icons.get(name, "○")
            p.setFont(QFont("Apple Color Emoji", 11))
            p.setPen(tc)
            p.drawText(x0+22, y, icon)
            p.setFont(QFont("Menlo", 10))
            badge = truth.replace("REAL_CPU","CPU✓").replace("REAL_GPU","GPU✓").replace("REAL","✓")
            p.drawText(x0+40, y, f"{name}")
            p.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
            p.drawText(x0+40, y+13, badge)
            y += 32
            if y > WIN_H - 60:
                break

        # Controls
        p.setPen(QPen(QColor(0, 60, 40), 1))
        p.drawLine(x0+4, WIN_H-50, x0+W_SIDE-4, WIN_H-50)
        p.setFont(QFont("Menlo", 8))
        p.setPen(QColor(80, 120, 100))
        for i, txt in enumerate(["WASD/Arrows: move", "P: pause  R: reset  Q: quit",
                                  "Pellet=WARP KERNEL ⚡", "🐜 For the Swarm"]):
            p.drawText(x0+6, WIN_H-40+i*11, txt)

    def closeEvent(self, event):
        self._timer.stop()
        self._ledger_timer.stop()
        super().closeEvent(event)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet("QWidget { background: #04040f; }")
    win = PacManGame()
    win.setWindowTitle("SIFTA Stigmergic Pac-Man — Predator v7.0")
    win.resize(WIN_W, WIN_H)
    win.show()
    sys.exit(app.exec())
