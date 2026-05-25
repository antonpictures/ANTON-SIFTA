#!/usr/bin/env python3
"""Stigmergic Maze Navigation for SIFTA.

One PyQt6 QWidget app. A generated maze becomes a small stigmergic field:
walkers explore from start to goal, successful paths deposit pheromone, stale
trails evaporate, and the best route becomes visible as the field converges.

No second Alice chat is created. The widget publishes focus context only.
"""
from __future__ import annotations

import json
import math
import random
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QPushButton,
    QWidget,
)

_REPO = Path(__file__).resolve().parents[2]
_STATE = _REPO / ".sifta_state"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    _publish_focus = None  # type: ignore


TRUTH_LABEL = "STIGMERGIC_MAZE_NAVIGATION_V1"
APP_ID = "stig_maze"

NORTH = 1
EAST = 2
SOUTH = 4
WEST = 8
ALL_WALLS = NORTH | EAST | SOUTH | WEST

DIRS = (
    (-1, 0, NORTH, SOUTH),
    (0, 1, EAST, WEST),
    (1, 0, SOUTH, NORTH),
    (0, -1, WEST, EAST),
)


@dataclass
class _Walker:
    r: int
    c: int
    path: list[tuple[int, int]]
    seed: int


def _append_jsonl(path: Path, row: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _publish_app_focus(detail: str, metadata: Optional[dict] = None) -> None:
    if not _publish_focus:
        return
    try:
        _publish_focus(
            title="Stigmergic Maze Navigation",
            detail=detail,
            app_id=APP_ID,
            metadata=metadata or {},
        )
    except Exception:
        pass


class StigmergicMazeNavigationWidget(QWidget):
    _live_instance: Optional["StigmergicMazeNavigationWidget"] = None

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                try:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                except Exception:
                    pass
                return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent=None):
        if getattr(self, "_stig_maze_initialized", False):
            return
        super().__init__(parent)
        type(self)._live_instance = self
        self._stig_maze_initialized = True

        self.setWindowTitle("Stigmergic Maze Navigation")
        self.setMinimumSize(780, 600)
        self.setMouseTracking(True)
        self.setAutoFillBackground(False)

        self._rng = random.Random()
        self._maze_size = 29
        self._walls: list[list[int]] = []
        self._pheromone: list[list[float]] = []
        self._walkers: list[_Walker] = []
        self._start = (0, 0)
        self._goal = (0, 0)
        self._best_path: list[tuple[int, int]] = []
        self._solved_count = 0
        self._steps = 0
        self._running = False
        self._last_receipt_best = 0

        self._title = QLabel("Stigmergic Maze Navigation", self)
        self._title.setFont(QFont("Avenir Next", 20, QFont.Weight.DemiBold))
        self._title.setStyleSheet("color: #e7edf5; background: transparent;")

        self._status = QLabel("", self)
        self._status.setFont(QFont("Avenir Next", 12))
        self._status.setStyleSheet("color: #aebbd0; background: transparent;")

        self._size_combo = QComboBox(self)
        for label, size in (("19 x 19", 19), ("29 x 29", 29), ("39 x 39", 39)):
            self._size_combo.addItem(label, size)
        self._size_combo.setCurrentIndex(1)
        self._size_combo.currentIndexChanged.connect(self._new_maze_from_control)

        self._new_btn = QPushButton("New", self)
        self._step_btn = QPushButton("Step", self)
        self._run_btn = QPushButton("Run", self)
        self._reset_btn = QPushButton("Reset", self)
        self._new_btn.clicked.connect(self._new_maze_from_control)
        self._step_btn.clicked.connect(lambda: self._evolve(32))
        self._run_btn.clicked.connect(self._toggle_run)
        self._reset_btn.clicked.connect(self._reset_navigation)

        for button in (self._new_btn, self._step_btn, self._run_btn, self._reset_btn):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton {"
                "background: #172033; color: #edf6ff; border: 1px solid #31506d;"
                "border-radius: 6px; padding: 7px 11px; font-weight: 650;"
                "}"
                "QPushButton:hover { background: #21304a; border-color: #58b7c9; }"
                "QPushButton:pressed { background: #102238; }"
            )
        self._size_combo.setStyleSheet(
            "QComboBox {"
            "background: #111827; color: #edf6ff; border: 1px solid #31506d;"
            "border-radius: 6px; padding: 6px 8px;"
            "}"
            "QComboBox::drop-down { border: 0; width: 20px; }"
        )

        self._timer = QTimer(self)
        self._timer.setInterval(42)
        self._timer.timeout.connect(lambda: self._evolve(9))

        self._new_maze(write_receipt=False)
        self._layout_controls()
        _publish_app_focus("opened", {"truth_label": TRUTH_LABEL})

    def closeEvent(self, event):
        self._timer.stop()
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        _publish_app_focus("closed", {"truth_label": TRUTH_LABEL})
        super().closeEvent(event)

    def resizeEvent(self, event):
        self._layout_controls()
        super().resizeEvent(event)

    def _layout_controls(self) -> None:
        pad = 14
        control_w = 474
        control_x = max(286, self.width() - control_w - pad)
        self._title.setGeometry(pad, 10, max(220, control_x - 2 * pad), 30)
        self._status.setGeometry(pad, 44, self.width() - 2 * pad, 24)

        y = 14
        x = control_x
        self._size_combo.setGeometry(x, y, 96, 32)
        x += 106
        for button in (self._new_btn, self._step_btn, self._run_btn, self._reset_btn):
            button.setGeometry(x, y, 82, 32)
            x += 92

    def _canvas_rect(self) -> QRectF:
        return QRectF(14, 84, max(100, self.width() - 28), max(100, self.height() - 98))

    def _new_maze_from_control(self) -> None:
        self._maze_size = int(self._size_combo.currentData() or 29)
        self._new_maze(write_receipt=True)

    def _new_maze(self, write_receipt: bool = True) -> None:
        n = self._maze_size
        self._walls = [[ALL_WALLS for _ in range(n)] for _ in range(n)]
        visited = [[False for _ in range(n)] for _ in range(n)]
        stack = [(0, 0)]
        visited[0][0] = True

        while stack:
            r, c = stack[-1]
            candidates = []
            for dr, dc, wall, opposite in DIRS:
                nr, nc = r + dr, c + dc
                if 0 <= nr < n and 0 <= nc < n and not visited[nr][nc]:
                    candidates.append((nr, nc, wall, opposite))
            if not candidates:
                stack.pop()
                continue
            nr, nc, wall, opposite = self._rng.choice(candidates)
            self._walls[r][c] &= ~wall
            self._walls[nr][nc] &= ~opposite
            visited[nr][nc] = True
            stack.append((nr, nc))

        # Braid a few dead ends so the field has alternatives to evaluate.
        for r in range(n):
            for c in range(n):
                if self._rng.random() > 0.075:
                    continue
                choices = []
                for dr, dc, wall, opposite in DIRS:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < n and 0 <= nc < n and (self._walls[r][c] & wall):
                        choices.append((nr, nc, wall, opposite))
                if choices:
                    nr, nc, wall, opposite = self._rng.choice(choices)
                    self._walls[r][c] &= ~wall
                    self._walls[nr][nc] &= ~opposite

        self._start = (0, 0)
        self._goal = (n - 1, n - 1)
        self._reset_navigation(write_receipt=False)
        if write_receipt:
            self._write_app_receipt("new_maze", {"size": n})
        _publish_app_focus("new maze", {"size": n, "truth_label": TRUTH_LABEL})

    def _reset_navigation(self, write_receipt: bool = True) -> None:
        n = self._maze_size
        self._pheromone = [[0.02 for _ in range(n)] for _ in range(n)]
        self._best_path = []
        self._solved_count = 0
        self._steps = 0
        self._last_receipt_best = 0
        self._walkers = [self._make_walker() for _ in range(36)]
        if write_receipt:
            self._write_app_receipt("reset_navigation", {"size": n})
        self._refresh_status()
        self.update()

    def _make_walker(self) -> _Walker:
        r, c = self._start
        return _Walker(r=r, c=c, path=[(r, c)], seed=self._rng.randrange(1_000_000))

    def _open_neighbors(self, r: int, c: int) -> list[tuple[int, int]]:
        walls = self._walls[r][c]
        out = []
        for dr, dc, wall, _opposite in DIRS:
            if walls & wall:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < self._maze_size and 0 <= nc < self._maze_size:
                out.append((nr, nc))
        return out

    def _toggle_run(self) -> None:
        self._running = not self._running
        if self._running:
            self._timer.start()
            self._run_btn.setText("Pause")
            _publish_app_focus("running", {"size": self._maze_size})
        else:
            self._timer.stop()
            self._run_btn.setText("Run")
            _publish_app_focus("paused", {"steps": self._steps, "solved": self._solved_count})

    def _evolve(self, rounds: int = 1) -> None:
        if not self._walls:
            return
        n = self._maze_size
        gr, gc = self._goal
        for _ in range(max(1, rounds)):
            self._steps += 1
            for r in range(n):
                row = self._pheromone[r]
                for c in range(n):
                    row[c] = max(0.01, row[c] * 0.992)

            if self._best_path:
                amount = min(0.10, 1.8 / max(1, len(self._best_path)))
                for r, c in self._best_path:
                    self._pheromone[r][c] = min(9.0, self._pheromone[r][c] + amount)

            for i, walker in enumerate(self._walkers):
                if (walker.r, walker.c) == self._goal:
                    self._commit_path(walker.path)
                    self._walkers[i] = self._make_walker()
                    continue

                neighbors = self._open_neighbors(walker.r, walker.c)
                if not neighbors:
                    self._walkers[i] = self._make_walker()
                    continue

                nr, nc = self._choose_next(walker, neighbors, gr, gc)
                walker.r, walker.c = nr, nc
                walker.path.append((nr, nc))
                self._pheromone[nr][nc] = min(9.0, self._pheromone[nr][nc] + 0.028)

                if len(walker.path) > n * n * 2:
                    self._walkers[i] = self._make_walker()

        self._refresh_status()
        self.update()

    def _choose_next(
        self,
        walker: _Walker,
        neighbors: list[tuple[int, int]],
        gr: int,
        gc: int,
    ) -> tuple[int, int]:
        local = random.Random(walker.seed + self._steps * 131 + len(walker.path) * 17)
        scores = []
        recent = set(walker.path[-10:])
        path_seen = set(walker.path)
        n = self._maze_size

        for nr, nc in neighbors:
            dist = abs(gr - nr) + abs(gc - nc)
            goal_pull = (2 * n - dist) / max(1, 2 * n)
            memory = self._pheromone[nr][nc]
            novelty = 0.45 if (nr, nc) not in path_seen else -0.55
            turn_penalty = -0.25 if (nr, nc) in recent else 0.0
            jitter = local.random() * 0.26
            raw = 0.95 + memory * 0.55 + goal_pull * 1.35 + novelty + turn_penalty + jitter
            scores.append(max(0.02, raw))

        total = sum(scores)
        pick = local.random() * total
        acc = 0.0
        for cell, score in zip(neighbors, scores):
            acc += score
            if acc >= pick:
                return cell
        return neighbors[-1]

    def _commit_path(self, path: list[tuple[int, int]]) -> None:
        if not path or path[-1] != self._goal:
            return
        self._solved_count += 1
        if not self._best_path or len(path) < len(self._best_path):
            self._best_path = list(path)
        deposit = min(1.25, max(0.16, 15.0 / max(1, len(path))))
        for r, c in path:
            self._pheromone[r][c] = min(9.0, self._pheromone[r][c] + deposit)

        best_len = len(self._best_path)
        if best_len and (self._last_receipt_best == 0 or best_len < self._last_receipt_best):
            self._last_receipt_best = best_len
            self._write_app_receipt(
                "path_found",
                {
                    "best_path_length": best_len,
                    "solved_count": self._solved_count,
                    "steps": self._steps,
                    "size": self._maze_size,
                    "used_solution_oracle": False,
                },
            )

    def _refresh_status(self) -> None:
        best = len(self._best_path) if self._best_path else 0
        max_pheromone = 0.0
        if self._pheromone:
            max_pheromone = max(max(row) for row in self._pheromone)
        self._status.setText(
            f"size {self._maze_size} | steps {self._steps} | solved {self._solved_count} | "
            f"best path {best or '-'} | max pheromone {max_pheromone:.2f}"
        )

    def _write_app_receipt(self, action: str, data: dict) -> None:
        row = {
            "ts": time.time(),
            "receipt_id": str(uuid.uuid4()),
            "app": "Stigmergic Maze Navigation",
            "app_id": APP_ID,
            "action": action,
            "ok": True,
            "truth_label": TRUTH_LABEL,
            "data": data,
        }
        _append_jsonl(_STATE / "stig_maze_receipts.jsonl", row)

    def mousePressEvent(self, event):
        cell = self._cell_from_point(event.position())
        if cell is not None:
            modifiers = event.modifiers()
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self._start = cell
            else:
                self._goal = cell
            self._reset_navigation(write_receipt=False)
            _publish_app_focus(
                "navigation endpoints changed",
                {"start": self._start, "goal": self._goal, "size": self._maze_size},
            )
            self.update()
        super().mousePressEvent(event)

    def _cell_from_point(self, point: QPointF) -> Optional[tuple[int, int]]:
        rect, origin_x, origin_y, cell = self._maze_geometry()
        if not rect.contains(point):
            return None
        c = int((point.x() - origin_x) / cell)
        r = int((point.y() - origin_y) / cell)
        if 0 <= r < self._maze_size and 0 <= c < self._maze_size:
            return r, c
        return None

    def _maze_geometry(self) -> tuple[QRectF, float, float, float]:
        canvas = self._canvas_rect()
        n = max(1, self._maze_size)
        side = min(canvas.width(), canvas.height()) - 32
        cell = max(4.0, side / n)
        maze_side = cell * n
        origin_x = canvas.x() + (canvas.width() - maze_side) / 2.0
        origin_y = canvas.y() + (canvas.height() - maze_side) / 2.0
        return QRectF(origin_x, origin_y, maze_side, maze_side), origin_x, origin_y, cell

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        bg = QLinearGradient(0, 0, self.width(), self.height())
        bg.setColorAt(0.0, QColor(5, 7, 13))
        bg.setColorAt(0.48, QColor(12, 18, 27))
        bg.setColorAt(1.0, QColor(15, 24, 28))
        painter.fillRect(self.rect(), bg)

        canvas = self._canvas_rect()
        painter.setPen(QPen(QColor(52, 80, 98, 170), 1.0))
        painter.setBrush(QColor(10, 15, 22, 210))
        painter.drawRoundedRect(canvas, 8, 8)

        if not self._walls:
            return

        maze_rect, ox, oy, cell = self._maze_geometry()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(9, 13, 20))
        painter.drawRect(maze_rect)

        self._paint_pheromone(painter, ox, oy, cell)
        self._paint_best_path(painter, ox, oy, cell)
        self._paint_walkers(painter, ox, oy, cell)
        self._paint_walls(painter, ox, oy, cell)
        self._paint_endpoints(painter, ox, oy, cell)

    def _paint_pheromone(self, painter: QPainter, ox: float, oy: float, cell: float) -> None:
        max_pheromone = max(0.1, max(max(row) for row in self._pheromone))
        painter.setPen(Qt.PenStyle.NoPen)
        for r, row in enumerate(self._pheromone):
            for c, value in enumerate(row):
                norm = min(1.0, value / max_pheromone)
                if norm < 0.045:
                    continue
                alpha = int(35 + norm * 150)
                hue_shift = int(norm * 80)
                painter.setBrush(QColor(0 + hue_shift, 200, 172, alpha))
                inset = max(1.0, cell * 0.16)
                painter.drawRoundedRect(
                    QRectF(ox + c * cell + inset, oy + r * cell + inset, cell - 2 * inset, cell - 2 * inset),
                    max(1.5, cell * 0.14),
                    max(1.5, cell * 0.14),
                )

    def _paint_best_path(self, painter: QPainter, ox: float, oy: float, cell: float) -> None:
        if len(self._best_path) < 2:
            return
        path = QPainterPath()
        first_r, first_c = self._best_path[0]
        path.moveTo(ox + (first_c + 0.5) * cell, oy + (first_r + 0.5) * cell)
        for r, c in self._best_path[1:]:
            path.lineTo(ox + (c + 0.5) * cell, oy + (r + 0.5) * cell)
        painter.setPen(QPen(QColor(255, 208, 88, 220), max(2.0, cell * 0.22)))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(255, 246, 175, 190), max(1.0, cell * 0.07)))
        painter.drawPath(path)

    def _paint_walkers(self, painter: QPainter, ox: float, oy: float, cell: float) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        radius = max(2.0, min(5.5, cell * 0.22))
        for index, walker in enumerate(self._walkers):
            alpha = 110 + (index % 4) * 30
            painter.setBrush(QColor(100, 218, 255, alpha))
            x = ox + (walker.c + 0.5) * cell
            y = oy + (walker.r + 0.5) * cell
            painter.drawEllipse(QPointF(x, y), radius, radius)

    def _paint_walls(self, painter: QPainter, ox: float, oy: float, cell: float) -> None:
        wall_pen = QPen(QColor(180, 206, 220), max(1.2, cell * 0.10))
        wall_pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        painter.setPen(wall_pen)
        n = self._maze_size
        for r in range(n):
            y = oy + r * cell
            for c in range(n):
                x = ox + c * cell
                walls = self._walls[r][c]
                if walls & NORTH:
                    painter.drawLine(QPointF(x, y), QPointF(x + cell, y))
                if walls & EAST:
                    painter.drawLine(QPointF(x + cell, y), QPointF(x + cell, y + cell))
                if walls & SOUTH:
                    painter.drawLine(QPointF(x, y + cell), QPointF(x + cell, y + cell))
                if walls & WEST:
                    painter.drawLine(QPointF(x, y), QPointF(x, y + cell))

    def _paint_endpoints(self, painter: QPainter, ox: float, oy: float, cell: float) -> None:
        for label, cell_pos, fill, rim in (
            ("S", self._start, QColor(82, 255, 170), QColor(185, 255, 222)),
            ("G", self._goal, QColor(255, 104, 92), QColor(255, 210, 188)),
        ):
            r, c = cell_pos
            x = ox + (c + 0.5) * cell
            y = oy + (r + 0.5) * cell
            radius = max(7.0, cell * 0.44)
            painter.setPen(QPen(rim, max(1.2, cell * 0.08)))
            painter.setBrush(fill)
            painter.drawEllipse(QPointF(x, y), radius, radius)
            painter.setPen(QPen(QColor(9, 13, 20), 1.0))
            font = QFont("Avenir Next", max(8, int(radius * 0.95)), QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(QRectF(x - radius, y - radius, radius * 2, radius * 2), Qt.AlignmentFlag.AlignCenter, label)


def main() -> None:
    app = QApplication(sys.argv)
    widget = StigmergicMazeNavigationWidget()
    widget.resize(980, 760)
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
