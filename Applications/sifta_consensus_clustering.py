#!/usr/bin/env python3
"""Stigmergic Consensus Clustering — Lumer-Faieta ant-based data partitioning.

2D data points are scattered on a toroidal grid.  Ant agents walk randomly and
pick up / drop points based on local similarity density:

  f(i) = max(0, (1/s²) Σ_j∈neighborhood [1 - d(i,j)/α])

  P_pickup = (k_p / (k_p + f(i)))²   — HIGH when point is dissimilar to locals
  P_drop   = (f(i) / (k_d + f(i)))²   — HIGH when point is similar to locals

Clusters emerge without K-means, without a central coordinator.  Only local
pheromone-like density drives the partition.

Reference: Lumer & Faieta (1994) "Diversity and Adaptation in Populations of
Clustering Ants", Proc. 3rd Int. Conf. on Simulation of Adaptive Behavior.
"""

from __future__ import annotations

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
except Exception:
    _publish_focus = None  # type: ignore[assignment]

APP_TITLE = "Stigmergic Consensus Clustering"
APP_ID = "sifta_consensus_clustering"
TRUTH_LABEL = "STIGMERGIC_CONSENSUS_CLUSTERING_V1"

GRID_W = 80
GRID_H = 60
DEFAULT_N_POINTS = 120
DEFAULT_N_ANTS = 40
NEIGHBORHOOD_S = 5
ALPHA = 6.0
K_PICK = 0.15
K_DROP = 0.30

_BG_TOP = QColor(9, 11, 19)
_BG_BOTTOM = QColor(16, 18, 28)
_PANEL = QColor(18, 21, 34)
_PANEL_BORDER = QColor(62, 72, 105)
_TEXT = QColor(220, 226, 240)
_DIM = QColor(142, 153, 181)
_ACCENT = QColor(120, 200, 255)

_CLUSTER_COLORS = [
    QColor(255, 110, 90),
    QColor(90, 220, 255),
    QColor(120, 255, 140),
    QColor(255, 200, 80),
    QColor(200, 130, 255),
]
_ANT_LADEN = QColor(255, 220, 80)
_ANT_FREE = QColor(180, 185, 200)


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
        with (_STATE / "consensus_clustering_receipts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DataPoint:
    feature_x: float
    feature_y: float
    blob_id: int
    grid_x: int = -1
    grid_y: int = -1
    placed: bool = False


@dataclass
class ClusterAnt:
    x: int = 0
    y: int = 0
    carrying: Optional[int] = None  # index into points list
    steps: int = 0


# ---------------------------------------------------------------------------
# Lumer-Faieta engine (no Qt dependency)
# ---------------------------------------------------------------------------


class ConsensusField:
    """Grid-based Lumer-Faieta clustering field."""

    def __init__(
        self,
        rng: random.Random | None = None,
        grid_w: int = GRID_W,
        grid_h: int = GRID_H,
        neighborhood: int = NEIGHBORHOOD_S,
        alpha: float = ALPHA,
        k_pick: float = K_PICK,
        k_drop: float = K_DROP,
    ) -> None:
        self.rng = rng or random.Random()
        self.grid_w = grid_w
        self.grid_h = grid_h
        self.neighborhood = neighborhood
        self.alpha = alpha
        self.k_pick = k_pick
        self.k_drop = k_drop

        self.points: list[DataPoint] = []
        self.ants: list[ClusterAnt] = []
        self.grid: list[list[int]] = [[-1] * grid_w for _ in range(grid_h)]
        self.step_count = 0
        self.avg_similarity_history: list[float] = []

    def generate_blobs(self, n_points: int = DEFAULT_N_POINTS, n_blobs: int = 3, spread: float = 1.8) -> None:
        self.points.clear()
        for row in self.grid:
            for x in range(len(row)):
                row[x] = -1

        centers = []
        for b in range(n_blobs):
            cx = self.rng.uniform(3.0, 12.0)
            cy = self.rng.uniform(3.0, 12.0)
            centers.append((cx, cy))

        per_blob = n_points // n_blobs
        for b, (cx, cy) in enumerate(centers):
            count = per_blob if b < n_blobs - 1 else n_points - per_blob * (n_blobs - 1)
            for _ in range(count):
                fx = cx + self.rng.gauss(0, spread)
                fy = cy + self.rng.gauss(0, spread)
                self.points.append(DataPoint(feature_x=fx, feature_y=fy, blob_id=b))

        self._scatter_points_on_grid()

    def _scatter_points_on_grid(self) -> None:
        for idx, pt in enumerate(self.points):
            for _attempt in range(200):
                gx = self.rng.randint(0, self.grid_w - 1)
                gy = self.rng.randint(0, self.grid_h - 1)
                if self.grid[gy][gx] == -1:
                    pt.grid_x = gx
                    pt.grid_y = gy
                    pt.placed = True
                    self.grid[gy][gx] = idx
                    break

    def spawn_ants(self, n_ants: int = DEFAULT_N_ANTS) -> None:
        self.ants.clear()
        for _ in range(n_ants):
            a = ClusterAnt(
                x=self.rng.randint(0, self.grid_w - 1),
                y=self.rng.randint(0, self.grid_h - 1),
            )
            self.ants.append(a)

    def add_point_at_grid(self, gx: int, gy: int) -> bool:
        """Owner-dropped data point (click-to-seed). George 2026-05-25 — "something
        should happen if I click it." Purely ADDITIVE: it never disturbs existing
        points, so the converging field stays valid. The new point inherits the
        feature + blob of its nearest placed neighbour (so the colony actually
        sorts it into a real cluster); if the field is empty it gets a fresh blob.
        Returns True if a point was placed (the clicked cell must be empty)."""
        if not (0 <= gx < self.grid_w and 0 <= gy < self.grid_h):
            return False
        if self.grid[gy][gx] != -1:
            return False  # cell already occupied
        nearest = None
        best = 1e9
        for idx, pt in enumerate(self.points):
            if not pt.placed:
                continue
            d = abs(pt.grid_x - gx) + abs(pt.grid_y - gy)
            if d < best:
                best, nearest = d, idx
        if nearest is not None:
            src = self.points[nearest]
            fx = src.feature_x + self.rng.gauss(0, 0.4)
            fy = src.feature_y + self.rng.gauss(0, 0.4)
            bid = src.blob_id
        else:
            fx = self.rng.uniform(3.0, 12.0)
            fy = self.rng.uniform(3.0, 12.0)
            bid = max((p.blob_id for p in self.points), default=-1) + 1
        self.points.append(
            DataPoint(feature_x=fx, feature_y=fy, blob_id=bid, grid_x=gx, grid_y=gy, placed=True)
        )
        self.grid[gy][gx] = len(self.points) - 1
        return True

    def _feature_distance(self, i: int, j: int) -> float:
        a = self.points[i]
        b = self.points[j]
        return math.hypot(a.feature_x - b.feature_x, a.feature_y - b.feature_y)

    def _local_similarity(self, point_idx: int, gx: int, gy: int) -> float:
        s = self.neighborhood
        count = 0
        total = 0.0
        half = s // 2
        for dy in range(-half, half + 1):
            for dx in range(-half, half + 1):
                if dx == 0 and dy == 0:
                    continue
                nx = (gx + dx) % self.grid_w
                ny = (gy + dy) % self.grid_h
                other = self.grid[ny][nx]
                if other < 0:
                    continue
                d = self._feature_distance(point_idx, other)
                total += max(0.0, 1.0 - d / self.alpha)
                count += 1
        if count == 0:
            return 0.0
        area = s * s
        return max(0.0, total / area)

    def _pickup_prob(self, f: float) -> float:
        return (self.k_pick / (self.k_pick + f)) ** 2

    def _drop_prob(self, f: float) -> float:
        if f < 1e-9:
            return 0.0
        return (f / (self.k_drop + f)) ** 2

    def step(self) -> None:
        self.step_count += 1
        for ant in self.ants:
            ant.steps += 1
            dx = self.rng.choice([-1, 0, 1])
            dy = self.rng.choice([-1, 0, 1])
            ant.x = (ant.x + dx) % self.grid_w
            ant.y = (ant.y + dy) % self.grid_h

            cell = self.grid[ant.y][ant.x]

            if ant.carrying is None:
                if cell >= 0:
                    f = self._local_similarity(cell, ant.x, ant.y)
                    if self.rng.random() < self._pickup_prob(f):
                        ant.carrying = cell
                        self.points[cell].placed = False
                        self.grid[ant.y][ant.x] = -1
            else:
                if cell == -1:
                    f = self._local_similarity(ant.carrying, ant.x, ant.y)
                    if self.rng.random() < self._drop_prob(f):
                        self.grid[ant.y][ant.x] = ant.carrying
                        pt = self.points[ant.carrying]
                        pt.grid_x = ant.x
                        pt.grid_y = ant.y
                        pt.placed = True
                        ant.carrying = None

    def run_steps(self, n: int) -> None:
        for _ in range(n):
            self.step()

    def measure_avg_similarity(self) -> float:
        total = 0.0
        count = 0
        for idx, pt in enumerate(self.points):
            if not pt.placed:
                continue
            f = self._local_similarity(idx, pt.grid_x, pt.grid_y)
            total += f
            count += 1
        avg = total / max(1, count)
        self.avg_similarity_history.append(avg)
        return avg

    def measure_purity(self) -> float:
        """Cluster purity: for each grid neighborhood, majority blob label purity."""
        if not self.points:
            return 0.0
        blob_ids = set(pt.blob_id for pt in self.points)
        if len(blob_ids) <= 1:
            return 1.0

        correct = 0
        total_placed = 0
        half = self.neighborhood // 2
        for idx, pt in enumerate(self.points):
            if not pt.placed:
                continue
            total_placed += 1
            blob_counts: dict[int, int] = {}
            blob_counts[pt.blob_id] = blob_counts.get(pt.blob_id, 0) + 1
            for dy in range(-half, half + 1):
                for dx in range(-half, half + 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx = (pt.grid_x + dx) % self.grid_w
                    ny = (pt.grid_y + dy) % self.grid_h
                    other = self.grid[ny][nx]
                    if other < 0:
                        continue
                    bid = self.points[other].blob_id
                    blob_counts[bid] = blob_counts.get(bid, 0) + 1
            majority = max(blob_counts.values()) if blob_counts else 0
            total_in_neighborhood = sum(blob_counts.values())
            if total_in_neighborhood > 0:
                correct += majority / total_in_neighborhood

        return correct / max(1, total_placed)


# ---------------------------------------------------------------------------
# QPainter canvas
# ---------------------------------------------------------------------------


class _ClusterCanvas(QWidget):
    def __init__(self, owner: "StigmergicConsensusClusteringWidget") -> None:
        super().__init__(owner)
        self.owner = owner
        self.setMinimumSize(640, 440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip("Click to drop a data point — the colony will sort it into a cluster.")

    def mousePressEvent(self, event) -> None:
        # George 2026-05-25 — "something should happen if I click it." Drop a data
        # point at the clicked cell; the ant colony then clusters it live. Wrapped
        # so a click can NEVER crash the running simulation.
        try:
            field = self.owner.field
            margin = 16.0
            usable_w = max(1.0, self.width() - 2 * margin)
            usable_h = max(1.0, self.height() - 2 * margin)
            cell = min(usable_w / field.grid_w, usable_h / field.grid_h)
            ox = (self.width() - cell * field.grid_w) / 2.0
            oy = (self.height() - cell * field.grid_h) / 2.0
            pos = event.position()
            gx = int((pos.x() - ox) / cell)
            gy = int((pos.y() - oy) / cell)
            if field.add_point_at_grid(gx, gy):
                self.update()
        except Exception:
            pass
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:
        field = self.owner.field
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0.0, _BG_TOP)
        bg.setColorAt(1.0, _BG_BOTTOM)
        p.fillRect(self.rect(), bg)

        margin = 16.0
        usable_w = max(1.0, self.width() - 2 * margin)
        usable_h = max(1.0, self.height() - 2 * margin)
        cell = min(usable_w / field.grid_w, usable_h / field.grid_h)
        ox = (self.width() - cell * field.grid_w) / 2.0
        oy = (self.height() - cell * field.grid_h) / 2.0

        field_rect = QRectF(ox - 5, oy - 5, cell * field.grid_w + 10, cell * field.grid_h + 10)
        p.setPen(QPen(_PANEL_BORDER, 1))
        p.setBrush(QBrush(QColor(11, 14, 24, 225)))
        p.drawRoundedRect(field_rect, 6, 6)

        p.setPen(Qt.PenStyle.NoPen)
        for idx, pt in enumerate(field.points):
            if not pt.placed:
                continue
            cx = ox + (pt.grid_x + 0.5) * cell
            cy = oy + (pt.grid_y + 0.5) * cell
            color = _CLUSTER_COLORS[pt.blob_id % len(_CLUSTER_COLORS)]
            r = max(2.2, cell * 0.38)
            grad = QRadialGradient(QPointF(cx, cy), r * 2.0)
            grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 200))
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            p.setBrush(QBrush(grad))
            p.drawEllipse(QPointF(cx, cy), r * 2.0, r * 2.0)
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(cx, cy), r, r)

        for ant in field.ants:
            cx = ox + (ant.x + 0.5) * cell
            cy = oy + (ant.y + 0.5) * cell
            color = _ANT_LADEN if ant.carrying is not None else _ANT_FREE
            r = max(1.6, cell * 0.22)
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(cx, cy), r, r)

        self._draw_convergence_graph(p, ox, oy, cell, field)
        p.end()

    def _draw_convergence_graph(self, p: QPainter, ox: float, oy: float, cell: float, field: ConsensusField) -> None:
        history = field.avg_similarity_history
        if len(history) < 2:
            return
        graph_w = min(180.0, cell * field.grid_w * 0.25)
        graph_h = 60.0
        gx = ox + cell * field.grid_w - graph_w - 8
        gy = oy + 8

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(11, 14, 24, 200)))
        p.drawRoundedRect(QRectF(gx - 4, gy - 4, graph_w + 8, graph_h + 22), 4, 4)

        p.setFont(QFont("Menlo", 8))
        p.setPen(_DIM)
        p.drawText(QRectF(gx, gy + graph_h + 2, graph_w, 14), Qt.AlignmentFlag.AlignCenter, "avg similarity")

        window = history[-200:]
        max_val = max(max(window), 0.01)
        p.setPen(QPen(_ACCENT, 1.4))
        step_w = graph_w / max(1, len(window) - 1)
        for i in range(1, len(window)):
            x1 = gx + (i - 1) * step_w
            y1 = gy + graph_h - (window[i - 1] / max_val) * graph_h
            x2 = gx + i * step_w
            y2 = gy + graph_h - (window[i] / max_val) * graph_h
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------


class StigmergicConsensusClusteringWidget(QWidget):
    _live_instance: Optional["StigmergicConsensusClusteringWidget"] = None
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
        self.setMinimumSize(900, 660)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget { background: #090b13; color: #dce2f0; } "
            "QPushButton { background: #202840; color: #dce2f0; border: 1px solid #4b577a; "
            "border-radius: 4px; padding: 6px 12px; } "
            "QPushButton:hover { background: #2c3657; } "
            "QSlider::groove:horizontal { height: 4px; background: #303a58; border-radius: 2px; } "
            "QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: #78c8ff; border-radius: 7px; }"
        )

        self.running = True
        self.interval_ms = 40
        self.steps_per_tick = 6
        self.measure_every = 4

        self.field = ConsensusField()
        self.field.generate_blobs(n_points=DEFAULT_N_POINTS, n_blobs=3)
        self.field.spawn_ants(n_ants=DEFAULT_N_ANTS)

        self._timer = QTimer(self)
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self._tick)

        self._build_ui()
        self._timer.start()
        self.field.measure_avg_similarity()
        self._sync_stats()

        _publish_app_focus("opened", {"points": len(self.field.points), "truth_label": TRUTH_LABEL})
        _write_app_receipt("widget_boot", {"points": len(self.field.points), "ants": len(self.field.ants)})

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
        title.setFont(QFont("Menlo", 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_ACCENT.name()};")
        header.addWidget(title)
        header.addStretch()

        self.start_btn = QPushButton("Pause")
        self.reset_btn = QPushButton("New Dataset")
        self.start_btn.clicked.connect(self._toggle_running)
        self.reset_btn.clicked.connect(self._new_dataset)
        header.addWidget(self.start_btn)
        header.addWidget(self.reset_btn)
        root.addLayout(header)

        controls = QHBoxLayout()
        controls.setSpacing(14)
        self.speed_slider = self._slider(1, 12, self.steps_per_tick)
        self.speed_slider.valueChanged.connect(self._set_speed)
        controls.addWidget(self._labeled_control("colony speed", self.speed_slider))

        alpha_val = int(self.field.alpha * 10)
        self.alpha_slider = self._slider(10, 120, alpha_val)
        self.alpha_slider.valueChanged.connect(self._set_alpha)
        controls.addWidget(self._labeled_control("similarity radius (α)", self.alpha_slider))
        root.addLayout(controls)

        self.canvas = _ClusterCanvas(self)
        root.addWidget(self.canvas, 1)

        stats = QGridLayout()
        stats.setHorizontalSpacing(8)
        stats.setVerticalSpacing(8)
        self.step_label = self._stat_card("steps", "0")
        self.sim_label = self._stat_card("avg similarity", "0.000")
        self.purity_label = self._stat_card("cluster purity", "0.000")
        self.placed_label = self._stat_card("placed points", "0")
        self.carried_label = self._stat_card("carried", "0")
        self.peak_label = self._stat_card("peak similarity", "0.000")
        for idx, widget in enumerate(
            (self.step_label, self.sim_label, self.purity_label, self.placed_label, self.carried_label, self.peak_label)
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

    def _set_speed(self, value: int) -> None:
        self.steps_per_tick = max(1, value)
        self.interval_ms = max(16, 60 - value * 3)
        if hasattr(self, "_timer"):
            self._timer.setInterval(self.interval_ms)

    def _set_alpha(self, value: int) -> None:
        self.field.alpha = value / 10.0

    def _toggle_running(self) -> None:
        self.running = not self.running
        self.start_btn.setText("Pause" if self.running else "Run")
        if self.running:
            self._timer.start(self.interval_ms)
        else:
            self._timer.stop()

    def _new_dataset(self) -> None:
        self.field = ConsensusField()
        self.field.generate_blobs(n_points=DEFAULT_N_POINTS, n_blobs=3)
        self.field.spawn_ants(n_ants=DEFAULT_N_ANTS)
        self.field.measure_avg_similarity()
        self._sync_stats()
        self.canvas.update()

    def _tick(self) -> None:
        self.field.run_steps(self.steps_per_tick)
        if self.field.step_count % self.measure_every == 0:
            self.field.measure_avg_similarity()
        self._sync_stats()
        self.canvas.update()

    def _sync_stats(self) -> None:
        placed = sum(1 for pt in self.field.points if pt.placed)
        carried = sum(1 for ant in self.field.ants if ant.carrying is not None)
        history = self.field.avg_similarity_history
        avg_sim = history[-1] if history else 0.0
        peak_sim = max(history) if history else 0.0
        purity = self.field.measure_purity()

        self._set_stat(self.step_label, "steps", str(self.field.step_count))
        self._set_stat(self.sim_label, "avg similarity", f"{avg_sim:.4f}", accent=avg_sim > 0.01)
        self._set_stat(self.purity_label, "cluster purity", f"{purity:.4f}", accent=purity > 0.6)
        self._set_stat(self.placed_label, "placed points", str(placed))
        self._set_stat(self.carried_label, "carried", str(carried))
        self._set_stat(self.peak_label, "peak similarity", f"{peak_sim:.4f}")


def main() -> None:
    app = QApplication(sys.argv)
    widget = StigmergicConsensusClusteringWidget()
    widget.resize(960, 700)
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
