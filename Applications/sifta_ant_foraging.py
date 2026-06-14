#!/usr/bin/env python3
"""Stigmergic Ant Foraging Trail - ant colony shortest-path demo.

The widget stays inside the PyQt6 SIFTA organism. Ants use local transition
weights from neighboring pheromone, obstacle geometry, and food odor. Returning
ants reinforce only the path they actually walked; evaporation prunes unused
trails. The path-length counters are observers, not planners.
"""

from __future__ import annotations

"""SIFTA Ant Foraging — stigmergic organ for Alice body."""

import json
import math
import random
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
sys.path.insert(0, str(_REPO))

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:  # pragma: no cover - desktop organ can be absent in tests
    _publish_focus = None  # type: ignore[assignment]

APP_TITLE = "Stigmergic Ant Foraging Trail"
APP_ID = "sifta_ant_foraging"
TRUTH_LABEL = "STIGMERGIC_ANT_FORAGING_TRAIL_V1"

GRID_W = 72
GRID_H = 46
NEST = (6, 35)
FOOD = (66, 10)
ANT_COUNT = 190

_BG_TOP = QColor(9, 11, 19)
_BG_BOTTOM = QColor(16, 18, 28)
_PANEL = QColor(18, 21, 34)
_PANEL_BORDER = QColor(62, 72, 105)
_TEXT = QColor(220, 226, 240)
_DIM = QColor(142, 153, 181)
_ACCENT = QColor(75, 235, 190)
_FOOD = QColor(90, 235, 110)
_NEST = QColor(255, 204, 92)
_PHERO_CORE = QColor(68, 238, 214)
_PHERO_HOT = QColor(255, 210, 90)
_RETURNING = QColor(85, 235, 245)
_SEARCHING = QColor(255, 172, 72)
_WALL = QColor(39, 44, 63)


def _publish_app_focus(detail: str, metadata: Optional[dict] = None) -> None:
    if _publish_focus is None:
        return
    try:
        _publish_focus(APP_TITLE, detail, metadata=metadata or {})
    except Exception:
        pass


def _write_app_receipt(event: str, payload: dict) -> None:
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "app": APP_TITLE,
            "event": event,
            "truth_label": TRUTH_LABEL,
            **payload,
        }
        with (_STATE / "ant_foraging_receipts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _distance(a: tuple[int, int], b: tuple[int, int]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _mix(a: QColor, b: QColor, t: float, alpha: int) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        alpha,
    )


@dataclass
class Ant:
    x: int
    y: int
    carrying: bool = False
    path: list[tuple[int, int]] = field(default_factory=list)
    return_index: int = 0
    trail_len: int = 0
    age: int = 0
    last_dx: int = 0
    last_dy: int = 0

    def reset(self) -> None:
        self.x, self.y = NEST
        self.carrying = False
        self.path = [NEST]
        self.return_index = 0
        self.trail_len = 0
        self.age = 0
        angle = random.random() * math.tau
        self.last_dx = int(round(math.cos(angle)))
        self.last_dy = int(round(math.sin(angle)))


class _TrailCanvas(QWidget):
    def __init__(self, owner: "StigmergicAntForagingWidget") -> None:
        super().__init__(owner)
        self.owner = owner
        self.setMinimumSize(760, 500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, _event) -> None:
        sim = self.owner
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0.0, _BG_TOP)
        bg.setColorAt(1.0, _BG_BOTTOM)
        p.fillRect(self.rect(), bg)

        margin = 18.0
        usable_w = max(1.0, self.width() - 2 * margin)
        usable_h = max(1.0, self.height() - 2 * margin)
        cell = min(usable_w / GRID_W, usable_h / GRID_H)
        ox = (self.width() - cell * GRID_W) / 2.0
        oy = (self.height() - cell * GRID_H) / 2.0

        field_rect = QRectF(ox - 7, oy - 7, cell * GRID_W + 14, cell * GRID_H + 14)
        p.setPen(QPen(_PANEL_BORDER, 1))
        p.setBrush(QBrush(QColor(11, 14, 24, 225)))
        p.drawRoundedRect(field_rect, 8, 8)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_WALL)
        for x, y in sim.obstacles:
            p.drawRoundedRect(
                QRectF(ox + x * cell, oy + y * cell, cell + 0.5, cell + 0.5),
                1.8,
                1.8,
            )

        max_ph = max(sim.max_pheromone, 0.1)
        for y, row in enumerate(sim.pheromone):
            for x, value in enumerate(row):
                if value <= 0.018:
                    continue
                t = min(1.0, value / max_ph)
                cx = ox + (x + 0.5) * cell
                cy = oy + (y + 0.5) * cell
                radius = cell * (0.25 + 1.05 * math.sqrt(t))
                alpha = int(40 + 190 * min(1.0, t * 1.25))
                grad = QRadialGradient(QPointF(cx, cy), radius)
                grad.setColorAt(0.0, _mix(_PHERO_CORE, _PHERO_HOT, t, alpha))
                grad.setColorAt(0.55, _mix(_PHERO_CORE, _PHERO_HOT, t, int(alpha * 0.45)))
                grad.setColorAt(1.0, QColor(_PHERO_CORE.red(), _PHERO_CORE.green(), _PHERO_CORE.blue(), 0))
                p.setBrush(QBrush(grad))
                p.drawEllipse(QPointF(cx, cy), radius, radius)

        self._draw_site(p, ox, oy, cell, NEST, _NEST, "NEST")
        self._draw_site(p, ox, oy, cell, FOOD, _FOOD, "FOOD")

        p.setPen(Qt.PenStyle.NoPen)
        for ant in sim.ants:
            cx = ox + (ant.x + 0.5) * cell
            cy = oy + (ant.y + 0.5) * cell
            color = _RETURNING if ant.carrying else _SEARCHING
            glow = QRadialGradient(QPointF(cx, cy), cell * 1.1)
            glow.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 210))
            glow.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF(cx, cy), cell * 0.8, cell * 0.8)
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(cx, cy), max(2.0, cell * 0.28), max(2.0, cell * 0.28))

        self._draw_route_legend(p, QRectF(ox, oy + cell * GRID_H + 13, cell * GRID_W, 26))
        p.end()

    def _draw_site(
        self,
        p: QPainter,
        ox: float,
        oy: float,
        cell: float,
        site: tuple[int, int],
        color: QColor,
        label: str,
    ) -> None:
        x, y = site
        cx = ox + (x + 0.5) * cell
        cy = oy + (y + 0.5) * cell
        grad = QRadialGradient(QPointF(cx, cy), cell * 3.8)
        grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 235))
        grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy), cell * 3.8, cell * 3.8)
        p.setBrush(QBrush(color))
        p.setPen(QPen(QColor(255, 255, 255, 180), 1.3))
        p.drawEllipse(QPointF(cx, cy), cell * 1.45, cell * 1.45)
        p.setPen(QPen(QColor(8, 10, 16), 1))
        p.setFont(QFont("Menlo", max(8, int(cell * 0.7)), QFont.Weight.Bold))
        p.drawText(QRectF(cx - cell * 3.0, cy - cell * 0.55, cell * 6.0, cell * 1.1), Qt.AlignmentFlag.AlignCenter, label)

    def _draw_route_legend(self, p: QPainter, rect: QRectF) -> None:
        p.setFont(QFont("Menlo", 9))
        p.setPen(_DIM)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "pheromone mass concentrates on the walked return paths; weak trails evaporate")


class StigmergicAntForagingWidget(QWidget):
    """PyQt6 ant colony widget with class-side singleton hardening."""

    _live_instance: Optional["StigmergicAntForagingWidget"] = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                if id(existing) not in cls._initialized_instance_ids:
                    cls._live_instance = None
                else:
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
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(960, 690)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget { background: #090b13; color: #dce2f0; } "
            "QPushButton { background: #202840; color: #dce2f0; border: 1px solid #4b577a; "
            "border-radius: 4px; padding: 6px 12px; } "
            "QPushButton:hover { background: #2c3657; } "
            "QSlider::groove:horizontal { height: 4px; background: #303a58; border-radius: 2px; } "
            "QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: #4bebbe; border-radius: 7px; }"
        )

        self.random = random.Random()
        self.running = True
        self.tick_count = 0
        self.interval_ms = 34
        self.steps_per_tick = 3
        self.evaporation = 0.991
        self.deposit_gain = 20.0
        self.pruned_last = 0
        self.pheromone_mass = 0.0
        self.max_pheromone = 0.0
        self.best_path_len: Optional[int] = None
        self.recent_path_lengths: list[int] = []
        self.success_count = 0
        self.obstacles: set[tuple[int, int]] = set()
        self.food_odor: list[list[float]] = []
        self.pheromone: list[list[float]] = []
        self.ants: list[Ant] = []

        self._make_world()
        self._reset_colony(clear_field=True)

        # The timer is intentionally created before _build_ui(). Slider handlers
        # can run during construction and must never see a missing _timer.
        self._timer = QTimer(self)
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self._tick)

        self._build_ui()
        self._timer.start()
        self._sync_stats()

        _publish_app_focus("opened", {"ants": len(self.ants), "truth_label": TRUTH_LABEL})
        _write_app_receipt("widget_boot", {"ants": len(self.ants), "timer_before_ui": True})

    def closeEvent(self, event) -> None:
        self.running = False
        try:
            self._timer.stop()
        except Exception:
            pass
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        _publish_app_focus("closed")
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(APP_TITLE)
        title.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_ACCENT.name()};")
        header.addWidget(title)
        header.addStretch()

        self.start_btn = QPushButton("Pause")
        self.reset_btn = QPushButton("Reset Field")
        self.seed_btn = QPushButton("Scatter Scouts")
        self.start_btn.clicked.connect(self._toggle_running)
        self.reset_btn.clicked.connect(lambda: self._reset_colony(clear_field=True))
        self.seed_btn.clicked.connect(lambda: self._reset_colony(clear_field=False))
        header.addWidget(self.start_btn)
        header.addWidget(self.reset_btn)
        header.addWidget(self.seed_btn)
        root.addLayout(header)

        controls = QHBoxLayout()
        controls.setSpacing(14)
        self.speed_slider = self._slider(1, 8, self.steps_per_tick)
        self.speed_slider.valueChanged.connect(self._set_speed)
        controls.addWidget(self._labeled_control("colony speed", self.speed_slider))

        evap_value = int(round((0.995 - self.evaporation) / (0.995 - 0.955) * 100))
        self.evap_slider = self._slider(0, 100, evap_value)
        self.evap_slider.valueChanged.connect(self._set_evaporation)
        controls.addWidget(self._labeled_control("evaporation", self.evap_slider))
        root.addLayout(controls)

        self.canvas = _TrailCanvas(self)
        root.addWidget(self.canvas, 1)

        stats = QGridLayout()
        stats.setHorizontalSpacing(8)
        stats.setVerticalSpacing(8)
        self.path_len_label = self._stat_card("path length", "searching")
        self.best_label = self._stat_card("best trail", "-")
        self.mass_label = self._stat_card("pheromone mass", "0.0")
        self.prune_label = self._stat_card("pruned cells", "0")
        self.success_label = self._stat_card("food returns", "0")
        self.max_label = self._stat_card("peak field", "0.0")
        for idx, widget in enumerate(
            (
                self.path_len_label,
                self.best_label,
                self.mass_label,
                self.prune_label,
                self.success_label,
                self.max_label,
            )
        ):
            stats.addWidget(widget, idx // 3, idx % 3)
        root.addLayout(stats)

    def _slider(self, minimum: int, maximum: int, value: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.setMinimumWidth(160)
        return slider

    def _labeled_control(self, label: str, control: QWidget) -> QWidget:
        box = QFrame()
        box.setStyleSheet("QFrame { background: #121622; border: 1px solid #28314d; border-radius: 5px; }")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 7, 10, 8)
        text = QLabel(label)
        text.setStyleSheet(f"color: {_DIM.name()}; font-family: Menlo; font-size: 10px;")
        layout.addWidget(text)
        layout.addWidget(control)
        return box

    def _stat_card(self, label: str, value: str) -> QLabel:
        widget = QLabel(f"{label}\n{value}")
        widget.setMinimumHeight(48)
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setStyleSheet(
            "QLabel { background: #121622; border: 1px solid #28314d; "
            "border-radius: 5px; padding: 5px; color: #dce2f0; font-family: Menlo; font-size: 11px; }"
        )
        return widget

    def _set_stat(self, widget: QLabel, label: str, value: str, accent: bool = False) -> None:
        color = _ACCENT.name() if accent else "#dce2f0"
        widget.setText(f"{label}\n{value}")
        widget.setStyleSheet(
            "QLabel { background: #121622; border: 1px solid #28314d; "
            f"border-radius: 5px; padding: 5px; color: {color}; font-family: Menlo; font-size: 11px; }}"
        )

    def _make_world(self) -> None:
        self.obstacles.clear()
        for x in range(30, 41):
            for y in range(5, 42):
                if 11 <= y <= 14 or 38 <= y <= 40:
                    continue
                self.obstacles.add((x, y))
        for x in range(18, 27):
            for y in range(17, 20):
                self.obstacles.add((x, y))
        for x in range(46, 58):
            for y in range(25, 28):
                self.obstacles.add((x, y))
        self._build_food_odor()

    def _build_food_odor(self) -> None:
        """Diffuse food scent through free cells so scouts can find the source."""
        odor = [[0.0 for _ in range(GRID_W)] for _ in range(GRID_H)]
        fx, fy = FOOD
        odor[fy][fx] = 1.0
        for _ in range(170):
            next_odor = [row[:] for row in odor]
            for y in range(GRID_H):
                for x in range(GRID_W):
                    if (x, y) in self.obstacles or (x, y) == FOOD:
                        continue
                    best = 0.0
                    for nx, ny, _dx, _dy in self._valid_neighbors(x, y):
                        if odor[ny][nx] > best:
                            best = odor[ny][nx]
                    next_odor[y][x] = max(next_odor[y][x] * 0.994, best * 0.968)
            odor = next_odor
            odor[fy][fx] = 1.0
        self.food_odor = odor

    def _reset_colony(self, clear_field: bool) -> None:
        if clear_field:
            self.pheromone = [[0.0 for _ in range(GRID_W)] for _ in range(GRID_H)]
            self.best_path_len = None
            self.recent_path_lengths.clear()
            self.success_count = 0
            self.tick_count = 0
        self.ants = [Ant(*NEST) for _ in range(ANT_COUNT)]
        for ant in self.ants:
            ant.reset()
        self.pruned_last = 0
        self._measure_field()
        if hasattr(self, "canvas"):
            self.canvas.update()
        if hasattr(self, "path_len_label"):
            self._sync_stats()
        _publish_app_focus("reset" if clear_field else "scouts scattered")

    def _toggle_running(self) -> None:
        self.running = not self.running
        self.start_btn.setText("Pause" if self.running else "Run")
        if self.running:
            self._timer.start(self.interval_ms)
        else:
            self._timer.stop()
        _publish_app_focus("running" if self.running else "paused")

    def _set_speed(self, value: int) -> None:
        self.steps_per_tick = max(1, value)
        self.interval_ms = max(16, 60 - value * 5)
        if hasattr(self, "_timer"):
            self._timer.setInterval(self.interval_ms)

    def _set_evaporation(self, value: int) -> None:
        self.evaporation = 0.995 - (max(0, min(100, value)) / 100.0) * (0.995 - 0.955)

    def _tick(self) -> None:
        for _ in range(self.steps_per_tick):
            self.tick_count += 1
            self._step_ants()
            self._evaporate()
        self._measure_field()
        self._sync_stats()
        self.canvas.update()

    def _valid_neighbors(self, x: int, y: int) -> list[tuple[int, int, int, int]]:
        options: list[tuple[int, int, int, int]] = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = x + dx
                ny = y + dy
                if not (0 <= nx < GRID_W and 0 <= ny < GRID_H):
                    continue
                if (nx, ny) in self.obstacles:
                    continue
                options.append((nx, ny, dx, dy))
        return options

    def _step_ants(self) -> None:
        for ant in self.ants:
            if ant.carrying:
                self._step_returning(ant)
            else:
                self._step_searching(ant)

    def _step_searching(self, ant: Ant) -> None:
        ant.age += 1
        if ant.age > 620 or len(ant.path) > 620:
            ant.reset()
            return

        if _distance((ant.x, ant.y), FOOD) <= 1.5:
            ant.carrying = True
            ant.trail_len = len(ant.path)
            ant.return_index = len(ant.path) - 1
            self._record_success(ant.trail_len)
            return

        options = self._valid_neighbors(ant.x, ant.y)
        if not options:
            ant.reset()
            return

        path_tail = set(ant.path[-32:])
        scored: list[tuple[float, tuple[int, int, int, int]]] = []
        current_food_dist = _distance((ant.x, ant.y), FOOD)
        current_odor = self.food_odor[ant.y][ant.x] if self.food_odor else 0.0
        for nx, ny, dx, dy in options:
            ph = self.pheromone[ny][nx]
            food_dist = _distance((nx, ny), FOOD)
            odor = self.food_odor[ny][nx] if self.food_odor else 1.0 / (food_dist + 1.0)
            odor_gain = max(0.0, odor - current_odor)
            improvement = max(-0.6, current_food_dist - food_dist)
            novelty = 0.18 if (nx, ny) in path_tail else 1.0
            continuity = 1.18 if (dx, dy) == (ant.last_dx, ant.last_dy) else 1.0
            exploratory = 0.05 + self.random.random() * 0.08
            weight = ((0.10 + ph) ** 1.55) * ((0.26 + odor) ** 2.8)
            weight *= (1.0 + max(0.0, improvement) * 0.55)
            weight *= (1.0 + odor_gain * 14.0)
            weight *= novelty * continuity
            scored.append((max(0.0001, weight + exploratory), (nx, ny, dx, dy)))

        nx, ny, dx, dy = self._weighted_choice(scored)
        ant.x, ant.y = nx, ny
        ant.last_dx, ant.last_dy = dx, dy
        cell = (nx, ny)
        if cell in ant.path:
            ant.path = ant.path[: ant.path.index(cell) + 1]
        else:
            ant.path.append(cell)

    def _step_returning(self, ant: Ant) -> None:
        if ant.return_index <= 0:
            self._deposit_at(NEST, ant.trail_len, 2.0)
            ant.reset()
            return
        self._deposit_at((ant.x, ant.y), ant.trail_len, 1.0)
        ant.return_index -= 1
        ant.x, ant.y = ant.path[ant.return_index]

    def _deposit_at(self, cell: tuple[int, int], trail_len: int, multiplier: float) -> None:
        x, y = cell
        if (x, y) in self.obstacles:
            return
        if 0 <= x < GRID_W and 0 <= y < GRID_H:
            strength = self.deposit_gain * multiplier / max(12.0, math.sqrt(max(1, trail_len)))
            self.pheromone[y][x] = min(22.0, self.pheromone[y][x] + strength)

    def _record_success(self, path_len: int) -> None:
        self.success_count += 1
        self.recent_path_lengths.append(path_len)
        if len(self.recent_path_lengths) > 36:
            self.recent_path_lengths = self.recent_path_lengths[-36:]
        if self.best_path_len is None or path_len < self.best_path_len:
            self.best_path_len = path_len
            _write_app_receipt("new_shorter_path", {"path_len": path_len, "success_count": self.success_count})

    def _weighted_choice(self, scored: list[tuple[float, tuple[int, int, int, int]]]) -> tuple[int, int, int, int]:
        total = sum(weight for weight, _ in scored)
        pick = self.random.random() * total
        accum = 0.0
        for weight, value in scored:
            accum += weight
            if accum >= pick:
                return value
        return scored[-1][1]

    def _evaporate(self) -> None:
        pruned = 0
        for y, row in enumerate(self.pheromone):
            for x, value in enumerate(row):
                if value <= 0.0:
                    continue
                value *= self.evaporation
                if value < 0.018:
                    if self.pheromone[y][x] > 0.0:
                        pruned += 1
                    value = 0.0
                row[x] = value
        self.pruned_last = pruned

    def _measure_field(self) -> None:
        mass = 0.0
        peak = 0.0
        for row in self.pheromone:
            for value in row:
                mass += value
                if value > peak:
                    peak = value
        self.pheromone_mass = mass
        self.max_pheromone = peak

    def _sync_stats(self) -> None:
        if self.recent_path_lengths:
            mean_len = sum(self.recent_path_lengths) / len(self.recent_path_lengths)
            path_text = f"{mean_len:.1f} steps"
        else:
            path_text = "searching"
        best_text = f"{self.best_path_len} steps" if self.best_path_len is not None else "-"
        self._set_stat(self.path_len_label, "path length", path_text, accent=bool(self.recent_path_lengths))
        self._set_stat(self.best_label, "best trail", best_text, accent=self.best_path_len is not None)
        self._set_stat(self.mass_label, "pheromone mass", f"{self.pheromone_mass:.1f}")
        self._set_stat(self.prune_label, "pruned cells", str(self.pruned_last))
        self._set_stat(self.success_label, "food returns", str(self.success_count))
        self._set_stat(self.max_label, "peak field", f"{self.max_pheromone:.2f}")


def main() -> None:
    app = QApplication(sys.argv)
    widget = StigmergicAntForagingWidget()
    widget.resize(1000, 720)
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
