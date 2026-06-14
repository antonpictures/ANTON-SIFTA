#!/usr/bin/env python3
"""
Applications/sifta_jigsaw_widget.py
Stigmergic Jigsaw — salvaged from Hermes' failed attempt (receipt
b744f6d9-68d6-41a1-b6c8-269cb3d637b5, TIMEOUT after 420s).

Core idea preserved: each tile is an agent, edge-matching deposits
pheromone into a shared field. The pheromone guides swarm placement.

Mechanics:
  - NxN grid (3x3 / 4x4 / 5x5). Each tile has 4 colored edges (N/E/S/W).
  - Tiles sit in a pool; click a pool tile to select, click a grid cell
    to place. Matching adjacent edges deposit pheromone at that boundary.
  - Pheromone field visualized as glowing edge highlights.
  - "Swarm Solve" runs ACO: ant agents sample placements biased by
    pheromone, reinforce good placements, evaporate bad ones.
  - Score = total matched edges. Perfect score = all internal edges match.

Registration: salvaged by Cowork (Claude Opus 4.7) from Hermes receipt.
Truth label: STIGMERGIC_JIGSAW_V1

For the Swarm.
"""
from __future__ import annotations

"""SIFTA Jigsaw Widget — stigmergic organ for Alice body."""

import json
import math
import random
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QRectF, Qt, QTimer, QPointF
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter,
    QPainterPath, QPen, QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget, QSizePolicy,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
sys.path.insert(0, str(_REPO))

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    _publish_focus = None  # type: ignore

TRUTH_LABEL = "STIGMERGIC_JIGSAW_V1"
HERMES_RECEIPT = "b744f6d9-68d6-41a1-b6c8-269cb3d637b5"

# ── Palette ────────────────────────────────────────────────────────────
_BG = QColor(8, 10, 18)
_BG_BOARD = QColor(18, 20, 32)
_GRID_LINE = QColor(50, 55, 80)
_ACCENT = QColor(0, 255, 180)
_TEXT = QColor(200, 210, 240)
_TEXT_DIM = QColor(120, 130, 160)
_SELECTED_BORDER = QColor(255, 200, 80)
_PLACED_BG = QColor(28, 32, 50)
_EMPTY_BG = QColor(14, 16, 26)
_POOL_BG = QColor(22, 24, 38)
_PHERO_GLOW = QColor(0, 255, 180, 180)

EDGE_COLORS = [
    QColor(220, 60, 60),    # red
    QColor(60, 140, 255),   # blue
    QColor(80, 220, 120),   # green
    QColor(255, 200, 60),   # gold
    QColor(180, 80, 255),   # purple
    QColor(255, 140, 60),   # orange
]
EDGE_NAMES = ["red", "blue", "green", "gold", "purple", "orange"]

N_EDGE_TYPES = len(EDGE_COLORS)


def _publish_app_focus(title: str, detail: str = "") -> None:
    if _publish_focus:
        try:
            _publish_focus(title=title, detail=detail, app_id="sifta_stigmergic_jigsaw")
        except Exception:
            pass


# ── Tile: each tile is an "agent" with 4 colored edges ────────────────
class JigsawTile:
    __slots__ = ("edges", "tile_id")

    def __init__(self, n: int, e: int, s: int, w: int, tile_id: int = 0):
        self.edges = (n, e, s, w)  # indices into EDGE_COLORS
        self.tile_id = tile_id

    def north(self) -> int: return self.edges[0]
    def east(self) -> int: return self.edges[1]
    def south(self) -> int: return self.edges[2]
    def west(self) -> int: return self.edges[3]


# ── Puzzle generator: build tiles so a perfect solution exists ─────────
def _generate_puzzle(n: int) -> list[JigsawTile]:
    solution_edges_h = [[random.randint(0, N_EDGE_TYPES - 1) for _ in range(n)] for _ in range(n + 1)]
    solution_edges_v = [[random.randint(0, N_EDGE_TYPES - 1) for _ in range(n + 1)] for _ in range(n)]

    tiles: list[JigsawTile] = []
    tid = 0
    for r in range(n):
        for c in range(n):
            north = solution_edges_h[r][c]
            south = solution_edges_h[r + 1][c]
            west = solution_edges_v[r][c]
            east = solution_edges_v[r][c + 1]
            tiles.append(JigsawTile(north, east, south, west, tile_id=tid))
            tid += 1
    random.shuffle(tiles)
    return tiles


# ── Pheromone field on grid edges ──────────────────────────────────────
class PheromoneField:
    def __init__(self, n: int):
        self.n = n
        self.h_edges = [[0.0] * n for _ in range(n + 1)]
        self.v_edges = [[0.0] * (n + 1) for _ in range(n)]

    def deposit_h(self, r: int, c: int, amount: float = 1.0) -> None:
        if 0 <= r <= self.n and 0 <= c < self.n:
            self.h_edges[r][c] = min(self.h_edges[r][c] + amount, 5.0)

    def deposit_v(self, r: int, c: int, amount: float = 1.0) -> None:
        if 0 <= r < self.n and 0 <= c <= self.n:
            self.v_edges[r][c] = min(self.v_edges[r][c] + amount, 5.0)

    def evaporate(self, rate: float = 0.85) -> None:
        for r in range(self.n + 1):
            for c in range(self.n):
                self.h_edges[r][c] *= rate
        for r in range(self.n):
            for c in range(self.n + 1):
                self.v_edges[r][c] *= rate

    def get_h(self, r: int, c: int) -> float:
        if 0 <= r <= self.n and 0 <= c < self.n:
            return self.h_edges[r][c]
        return 0.0

    def get_v(self, r: int, c: int) -> float:
        if 0 <= r < self.n and 0 <= c <= self.n:
            return self.v_edges[r][c]
        return 0.0

    def reset(self) -> None:
        self.h_edges = [[0.0] * self.n for _ in range(self.n + 1)]
        self.v_edges = [[0.0] * (self.n + 1) for _ in range(self.n)]


# ── Main widget ────────────────────────────────────────────────────────
class StigmergicJigsawWidget(QWidget):
    _live_instance: Optional["StigmergicJigsawWidget"] = None
    _initialized_instance_ids: set = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                if id(existing) not in cls._initialized_instance_ids:
                    cls._live_instance = None
                else:
                    try:
                        existing.show(); existing.raise_(); existing.activateWindow()
                    except Exception:
                        pass
                    return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent=None):
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))

        self.setWindowTitle("Stigmergic Jigsaw")
        self.setMinimumSize(700, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background-color: {_BG.name()};")

        self._grid_n = 4
        self._tiles: list[JigsawTile] = []
        self._pool: list[JigsawTile] = []
        self._board: list[list[Optional[JigsawTile]]] = []
        self._field = PheromoneField(self._grid_n)
        self._selected_pool_idx: int = -1
        self._score = 0
        self._perfect = 0
        self._solving = False
        self._solve_ants: list[dict] = []
        self._solve_best: int = 0
        self._solve_iter = 0
        self._pool_scroll = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        hdr = QLabel("Stigmergic Jigsaw — tiles are agents, edges are pheromone")
        hdr.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {_ACCENT.name()};")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hdr)

        bar = QHBoxLayout()
        bar.setSpacing(8)

        self._size_combo = QComboBox()
        self._size_combo.addItems(["3×3", "4×4", "5×5"])
        self._size_combo.setCurrentIndex(1)
        self._size_combo.currentIndexChanged.connect(self._on_size_change)
        self._size_combo.setStyleSheet(
            f"QComboBox {{ color: {_TEXT.name()}; background: {_POOL_BG.name()}; "
            f"border: 1px solid {_GRID_LINE.name()}; padding: 4px 8px; border-radius: 4px; }}"
        )
        bar.addWidget(QLabel("Size:"))
        bar.itemAt(bar.count() - 1).widget().setStyleSheet(f"color: {_TEXT_DIM.name()};")

        bar.addWidget(self._size_combo)

        self._new_btn = QPushButton("New Puzzle")
        self._new_btn.clicked.connect(self._new_puzzle)
        self._solve_btn = QPushButton("Swarm Solve")
        self._solve_btn.clicked.connect(self._toggle_solve)
        self._clear_btn = QPushButton("Clear Board")
        self._clear_btn.clicked.connect(self._clear_board)

        for btn in (self._new_btn, self._solve_btn, self._clear_btn):
            btn.setStyleSheet(
                f"QPushButton {{ color: {_TEXT.name()}; background: {_POOL_BG.name()}; "
                f"border: 1px solid {_GRID_LINE.name()}; padding: 5px 14px; border-radius: 4px; }}"
                f"QPushButton:hover {{ background: {_PLACED_BG.name()}; }}"
            )
            bar.addWidget(btn)

        bar.addStretch()
        self._score_label = QLabel("Score: 0 / 0")
        self._score_label.setFont(QFont("Menlo", 11))
        self._score_label.setStyleSheet(f"color: {_TEXT.name()};")
        bar.addWidget(self._score_label)

        root.addLayout(bar)

        self._canvas = _JigsawCanvas(self)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._canvas, stretch=1)

        self._status = QLabel("")
        self._status.setFont(QFont("Menlo", 10))
        self._status.setStyleSheet(f"color: {_TEXT_DIM.name()};")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._new_puzzle()
        _publish_app_focus("Stigmergic Jigsaw", "opened")

    def closeEvent(self, event):
        self._solving = False
        self._timer.stop()
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        _publish_app_focus("Stigmergic Jigsaw", "closed")
        super().closeEvent(event)

    # ── puzzle lifecycle ───────────────────────────────────────────────
    def _on_size_change(self, idx: int) -> None:
        self._grid_n = [3, 4, 5][idx]
        self._new_puzzle()

    def _new_puzzle(self) -> None:
        self._solving = False
        self._timer.stop()
        n = self._grid_n
        self._tiles = _generate_puzzle(n)
        self._pool = list(self._tiles)
        self._board = [[None] * n for _ in range(n)]
        self._field = PheromoneField(n)
        self._selected_pool_idx = -1
        self._score = 0
        self._perfect = 2 * n * (n - 1)
        self._solve_iter = 0
        self._solve_best = 0
        self._pool_scroll = 0
        self._update_score()
        self._status.setText(f"New {n}×{n} puzzle — {n*n} tile-agents, {self._perfect} internal edges")
        self._canvas.update()

    def _clear_board(self) -> None:
        self._solving = False
        self._timer.stop()
        n = self._grid_n
        for r in range(n):
            for c in range(n):
                t = self._board[r][c]
                if t is not None:
                    self._pool.append(t)
                    self._board[r][c] = None
        self._field.reset()
        self._selected_pool_idx = -1
        self._score = 0
        self._solve_iter = 0
        self._pool_scroll = 0
        self._update_score()
        self._status.setText("Board cleared")
        self._canvas.update()

    # ── scoring + pheromone deposit ────────────────────────────────────
    def _recompute_score_and_pheromone(self) -> None:
        n = self._grid_n
        self._field.reset()
        score = 0
        for r in range(n):
            for c in range(n):
                t = self._board[r][c]
                if t is None:
                    continue
                if r > 0 and self._board[r - 1][c] is not None:
                    if t.north() == self._board[r - 1][c].south():
                        score += 1
                        self._field.deposit_h(r, c, 1.0)
                if c > 0 and self._board[r][c - 1] is not None:
                    if t.west() == self._board[r][c - 1].east():
                        score += 1
                        self._field.deposit_v(r, c, 1.0)
        self._score = score
        self._update_score()

    def _update_score(self) -> None:
        self._score_label.setText(f"Score: {self._score} / {self._perfect}")
        if self._score == self._perfect and self._perfect > 0 and not any(
            self._board[r][c] is None for r in range(self._grid_n) for c in range(self._grid_n)
        ):
            self._status.setText("PERFECT — all edges match! The swarm found the solution.")

    # ── user interaction ───────────────────────────────────────────────
    def _handle_pool_click(self, idx: int) -> None:
        if self._solving:
            return
        if 0 <= idx < len(self._pool):
            self._selected_pool_idx = idx
            self._canvas.update()

    def _handle_board_click(self, r: int, c: int) -> None:
        if self._solving:
            return
        if not (0 <= r < self._grid_n and 0 <= c < self._grid_n):
            return
        if self._board[r][c] is not None:
            tile = self._board[r][c]
            self._board[r][c] = None
            self._pool.append(tile)
            self._selected_pool_idx = len(self._pool) - 1
            self._recompute_score_and_pheromone()
            self._canvas.update()
            return
        if self._selected_pool_idx < 0 or self._selected_pool_idx >= len(self._pool):
            return
        tile = self._pool.pop(self._selected_pool_idx)
        self._board[r][c] = tile
        self._selected_pool_idx = -1
        self._recompute_score_and_pheromone()
        self._canvas.update()

    def _handle_pool_scroll(self, delta: int) -> None:
        self._pool_scroll = max(0, self._pool_scroll - delta)
        self._canvas.update()

    # ── Swarm Solve (ACO) ──────────────────────────────────────────────
    def _toggle_solve(self) -> None:
        if self._solving:
            self._solving = False
            self._timer.stop()
            self._solve_btn.setText("Swarm Solve")
            self._status.setText(f"Swarm stopped at iter {self._solve_iter}, best={self._solve_best}/{self._perfect}")
        else:
            self._clear_board()
            self._solving = True
            self._solve_btn.setText("Stop Swarm")
            self._solve_iter = 0
            self._solve_best = 0
            self._timer.start(60)
            self._status.setText("Swarm solving — ants placing tiles guided by pheromone…")

    def _tick(self) -> None:
        if not self._solving:
            self._timer.stop()
            return
        self._solve_iter += 1

        n = self._grid_n
        pool = list(self._tiles)
        random.shuffle(pool)
        trial_board: list[list[Optional[JigsawTile]]] = [[None] * n for _ in range(n)]

        positions = [(r, c) for r in range(n) for c in range(n)]
        random.shuffle(positions)

        for r, c in positions:
            best_tile = None
            best_score = -1.0
            best_idx = -1
            for i, tile in enumerate(pool):
                s = 0.0
                ph = 0.0
                if r > 0 and trial_board[r - 1][c] is not None:
                    if tile.north() == trial_board[r - 1][c].south():
                        s += 1
                        ph += self._field.get_h(r, c)
                if c > 0 and trial_board[r][c - 1] is not None:
                    if tile.west() == trial_board[r][c - 1].east():
                        s += 1
                        ph += self._field.get_v(r, c)
                if r < n - 1 and trial_board[r + 1][c] is not None:
                    if tile.south() == trial_board[r + 1][c].north():
                        s += 1
                        ph += self._field.get_h(r + 1, c)
                if c < n - 1 and trial_board[r][c + 1] is not None:
                    if tile.east() == trial_board[r][c + 1].west():
                        s += 1
                        ph += self._field.get_v(r, c + 1)
                quality = s + 0.3 * ph + random.random() * 0.15
                if quality > best_score:
                    best_score = quality
                    best_tile = tile
                    best_idx = i
            if best_tile is not None:
                trial_board[r][c] = best_tile
                pool.pop(best_idx)

        trial_score = 0
        for r in range(n):
            for c in range(n):
                t = trial_board[r][c]
                if t is None:
                    continue
                if r > 0 and trial_board[r - 1][c] is not None:
                    if t.north() == trial_board[r - 1][c].south():
                        trial_score += 1
                if c > 0 and trial_board[r][c - 1] is not None:
                    if t.west() == trial_board[r][c - 1].east():
                        trial_score += 1

        if trial_score >= self._solve_best:
            self._solve_best = trial_score
            self._board = trial_board
            self._pool = list(pool)
            self._recompute_score_and_pheromone()

            for r in range(n):
                for c in range(n):
                    t = trial_board[r][c]
                    if t is None:
                        continue
                    if r > 0 and trial_board[r - 1][c] is not None:
                        if t.north() == trial_board[r - 1][c].south():
                            self._field.deposit_h(r, c, 0.5)
                    if c > 0 and trial_board[r][c - 1] is not None:
                        if t.west() == trial_board[r][c - 1].east():
                            self._field.deposit_v(r, c, 0.5)

        self._field.evaporate(0.92)

        self._status.setText(
            f"Swarm iter {self._solve_iter} — best {self._solve_best}/{self._perfect}"
        )

        if self._solve_best == self._perfect:
            self._solving = False
            self._timer.stop()
            self._solve_btn.setText("Swarm Solve")
            self._status.setText(
                f"SOLVED in {self._solve_iter} iterations! All {self._perfect} edges match."
            )
            self._write_receipt(True)

        self._canvas.update()

    def _write_receipt(self, solved: bool) -> None:
        receipt = {
            "ts": time.time(),
            "kind": "JIGSAW_SOLVE",
            "truth_label": TRUTH_LABEL,
            "hermes_origin": HERMES_RECEIPT,
            "grid": f"{self._grid_n}x{self._grid_n}",
            "score": self._score,
            "perfect": self._perfect,
            "solved": solved,
            "iterations": self._solve_iter,
            "receipt_id": str(uuid.uuid4()),
        }
        try:
            path = _STATE / "jigsaw_receipts.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
        except Exception:
            pass


# ── Canvas: custom paint for grid + pool + pheromone ───────────────────
class _JigsawCanvas(QWidget):
    def __init__(self, parent: StigmergicJigsawWidget):
        super().__init__(parent)
        self._jw = parent
        self.setMouseTracking(True)
        self._hover_cell: tuple[int, int] | None = None

    def _layout_metrics(self):
        w, h = self.width(), self.height()
        pool_h = max(80, int(h * 0.18))
        board_area_h = h - pool_h - 12
        board_area_w = w - 16
        n = self._jw._grid_n
        cell = min(board_area_w // n, board_area_h // n, 120)
        bw = cell * n
        bh = cell * n
        bx = (w - bw) // 2
        by = 4
        return cell, bx, by, bw, bh, pool_h, w, h

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cell, bx, by, bw, bh, pool_h, w, h = self._layout_metrics()
        n = self._jw._grid_n

        p.fillRect(0, 0, w, h, _BG)

        # board background
        p.fillRect(bx - 2, by - 2, bw + 4, bh + 4, _BG_BOARD)

        # draw pheromone glow on edges
        field = self._jw._field
        for r in range(n + 1):
            for c in range(n):
                ph = field.get_h(r, c)
                if ph > 0.05:
                    alpha = min(int(ph * 60), 220)
                    glow = QColor(_PHERO_GLOW)
                    glow.setAlpha(alpha)
                    y_pos = by + r * cell
                    p.setPen(QPen(glow, max(2, int(ph * 2.5))))
                    p.drawLine(bx + c * cell + 2, y_pos, bx + (c + 1) * cell - 2, y_pos)

        for r in range(n):
            for c in range(n + 1):
                ph = field.get_v(r, c)
                if ph > 0.05:
                    alpha = min(int(ph * 60), 220)
                    glow = QColor(_PHERO_GLOW)
                    glow.setAlpha(alpha)
                    x_pos = bx + c * cell
                    p.setPen(QPen(glow, max(2, int(ph * 2.5))))
                    p.drawLine(x_pos, by + r * cell + 2, x_pos, by + (r + 1) * cell - 2)

        # grid cells
        for r in range(n):
            for c in range(n):
                rx = bx + c * cell
                ry = by + r * cell
                tile = self._jw._board[r][c]
                if tile:
                    p.fillRect(rx + 1, ry + 1, cell - 2, cell - 2, _PLACED_BG)
                    self._draw_tile(p, tile, rx, ry, cell)
                else:
                    p.fillRect(rx + 1, ry + 1, cell - 2, cell - 2, _EMPTY_BG)
                    if self._hover_cell == (r, c) and self._jw._selected_pool_idx >= 0:
                        hl = QColor(255, 255, 255, 25)
                        p.fillRect(rx + 1, ry + 1, cell - 2, cell - 2, hl)

        # grid lines
        p.setPen(QPen(_GRID_LINE, 1))
        for i in range(n + 1):
            p.drawLine(bx + i * cell, by, bx + i * cell, by + bh)
            p.drawLine(bx, by + i * cell, bx + bw, by + i * cell)

        # pool area
        pool_y = by + bh + 8
        p.fillRect(4, pool_y, w - 8, pool_h, _POOL_BG)
        p.setPen(QPen(_GRID_LINE, 1))
        p.drawRect(4, pool_y, w - 8, pool_h)

        pool_label_font = QFont("Menlo", 9)
        p.setFont(pool_label_font)
        p.setPen(_TEXT_DIM)
        p.drawText(10, pool_y + 14, f"Pool ({len(self._jw._pool)} tiles)")

        # draw pool tiles
        pool_cell = min(cell, int(pool_h * 0.8), 60)
        pool_start_x = 10
        pool_start_y = pool_y + 20
        max_visible = max(1, (w - 24) // (pool_cell + 4))
        scroll = min(self._jw._pool_scroll, max(0, len(self._jw._pool) - max_visible))
        self._jw._pool_scroll = scroll

        for i in range(min(max_visible, len(self._jw._pool) - scroll)):
            idx = scroll + i
            tile = self._jw._pool[idx]
            tx = pool_start_x + i * (pool_cell + 4)
            ty = pool_start_y
            bg = _PLACED_BG if idx != self._jw._selected_pool_idx else QColor(40, 45, 65)
            p.fillRect(tx, ty, pool_cell, pool_cell, bg)
            self._draw_tile(p, tile, tx, ty, pool_cell)
            if idx == self._jw._selected_pool_idx:
                p.setPen(QPen(_SELECTED_BORDER, 2))
                p.drawRect(tx, ty, pool_cell, pool_cell)

        if len(self._jw._pool) > max_visible:
            p.setPen(_TEXT_DIM)
            p.drawText(w - 80, pool_y + pool_h - 6, f"scroll ◀▶ {scroll+1}–{min(scroll+max_visible, len(self._jw._pool))}")

        self._pool_cell = pool_cell
        self._pool_start_x = pool_start_x
        self._pool_start_y = pool_start_y
        self._pool_max_vis = max_visible
        self._pool_y = pool_y

        p.end()

    def _draw_tile(self, p: QPainter, tile: JigsawTile, x: int, y: int, sz: int) -> None:
        cx, cy = x + sz // 2, y + sz // 2
        tri_inset = max(4, sz // 6)

        # north triangle
        path_n = QPainterPath()
        path_n.moveTo(x + 2, y + 2)
        path_n.lineTo(x + sz - 2, y + 2)
        path_n.lineTo(cx, cy - tri_inset)
        path_n.closeSubpath()
        p.fillPath(path_n, QBrush(EDGE_COLORS[tile.north()]))

        # east triangle
        path_e = QPainterPath()
        path_e.moveTo(x + sz - 2, y + 2)
        path_e.lineTo(x + sz - 2, y + sz - 2)
        path_e.lineTo(cx + tri_inset, cy)
        path_e.closeSubpath()
        p.fillPath(path_e, QBrush(EDGE_COLORS[tile.east()]))

        # south triangle
        path_s = QPainterPath()
        path_s.moveTo(x + sz - 2, y + sz - 2)
        path_s.lineTo(x + 2, y + sz - 2)
        path_s.lineTo(cx, cy + tri_inset)
        path_s.closeSubpath()
        p.fillPath(path_s, QBrush(EDGE_COLORS[tile.south()]))

        # west triangle
        path_w = QPainterPath()
        path_w.moveTo(x + 2, y + sz - 2)
        path_w.lineTo(x + 2, y + 2)
        path_w.lineTo(cx - tri_inset, cy)
        path_w.closeSubpath()
        p.fillPath(path_w, QBrush(EDGE_COLORS[tile.west()]))

        # center dot
        p.setBrush(QBrush(_BG_BOARD))
        p.setPen(Qt.PenStyle.NoPen)
        dot_r = max(2, sz // 12)
        p.drawEllipse(QPointF(cx, cy), dot_r, dot_r)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        mx, my = int(event.position().x()), int(event.position().y())
        cell, bx, by, bw, bh, pool_h, w, h = self._layout_metrics()
        n = self._jw._grid_n

        # check board click
        if bx <= mx < bx + bw and by <= my < by + bh:
            c = (mx - bx) // cell
            r = (my - by) // cell
            if 0 <= r < n and 0 <= c < n:
                self._jw._handle_board_click(r, c)
                return

        # check pool click
        pool_cell = getattr(self, "_pool_cell", 50)
        psx = getattr(self, "_pool_start_x", 10)
        psy = getattr(self, "_pool_start_y", 0)
        pmv = getattr(self, "_pool_max_vis", 10)
        scroll = self._jw._pool_scroll

        if psy <= my < psy + pool_cell:
            idx = (mx - psx) // (pool_cell + 4) + scroll
            if 0 <= idx < len(self._jw._pool):
                self._jw._handle_pool_click(idx)

    def mouseMoveEvent(self, event):
        mx, my = int(event.position().x()), int(event.position().y())
        cell, bx, by, bw, bh, pool_h, w, h = self._layout_metrics()
        n = self._jw._grid_n
        old = self._hover_cell
        if bx <= mx < bx + bw and by <= my < by + bh:
            c = (mx - bx) // cell
            r = (my - by) // cell
            self._hover_cell = (r, c) if 0 <= r < n and 0 <= c < n else None
        else:
            self._hover_cell = None
        if old != self._hover_cell:
            self.update()

    def wheelEvent(self, event):
        delta = 1 if event.angleDelta().y() > 0 else -1
        self._jw._handle_pool_scroll(delta)


# ── standalone launch ──────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    win = StigmergicJigsawWidget()
    win.resize(800, 700)
    win.show()
    sys.exit(app.exec())
