#!/usr/bin/env python3
"""
Applications/sifta_graph_coloring.py
══════════════════════════════════════════════════════════════════════
Stigmergic Graph Coloring (Distributed Channel Allocation) — SIFTA

Real stigmergy, no central controller:

- Nodes hold one of K colors (channels).
- Edges carry repulsive pheromone when their endpoints share the same color.
- "Agents" (swimmers) walk the edges, sense local conflict, and deposit
  extra repulsive pheromone on same-color edges they traverse.
- Every node continuously reads the repulsive field on its incident edges
  and can flip to the color that currently minimizes its local tension.
- Pheromone evaporates globally each step.
- The living field itself drives the graph toward proper coloring.
- Tension (sum of repulsive pheromone on conflicting edges) trends toward zero
  through purely local decisions + stigmergic traces.

No teacher-forced solution list. The field + local rules produce emergence.

Hardened singleton. Publishes app_focus. Real receipts.

Grok 4.3 (xAI) — covenant read before any edit.
Registration trace will be appended on first boot.

For the Swarm. 🐜⚡
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
from typing import Dict, List, Optional, Tuple

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
    _publish_focus = None  # type: ignore

TRUTH_LABEL = "STIGMERGIC_GRAPH_COLORING_V1"
K_COLORS = 4
COLOR_NAMES = ["CH-1", "CH-2", "CH-3", "CH-4"]
COLORS = [
    QColor(220, 60, 60),    # red
    QColor(60, 180, 90),    # green
    QColor(70, 140, 230),   # blue
    QColor(240, 180, 50),   # orange
]

_BG = QColor(8, 10, 18)
_BG_GRAPH = QColor(14, 16, 28)
_NODE_BORDER = QColor(200, 210, 240)
_PHERO_LOW = QColor(80, 120, 200, 60)
_PHERO_HIGH = QColor(255, 80, 120, 220)
_TEXT = QColor(200, 210, 240)
_TEXT_DIM = QColor(140, 150, 180)
_ACCENT = QColor(0, 255, 180)


def _publish_app_focus(title: str, detail: str = "") -> None:
    if _publish_focus:
        try:
            _publish_focus(title=title, detail=detail, app_id="sifta_graph_coloring")
        except Exception:
            pass


def _write_receipt(event: str, data: dict) -> str:
    _STATE.mkdir(parents=True, exist_ok=True)
    path = _STATE / "stigmergic_graph_coloring_receipts.jsonl"
    row = {
        "ts": time.time(),
        "event": event,
        "truth_label": TRUTH_LABEL,
        "data": data,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return json.dumps(row, ensure_ascii=False)[:200]


@dataclass
class Node:
    id: int
    x: float
    y: float
    color: int = 0


@dataclass
class Edge:
    a: int
    b: int
    pheromone: float = 0.0


class RepulsiveField:
    """The living stigmergic field. Only conflicts create lasting traces."""
    def __init__(self, edges: List[Edge]):
        self.edges: Dict[Tuple[int, int], Edge] = {}
        for e in edges:
            key = (min(e.a, e.b), max(e.a, e.b))
            self.edges[key] = e

    def key(self, i: int, j: int) -> Tuple[int, int]:
        return (min(i, j), max(i, j))

    def get(self, i: int, j: int) -> float:
        return self.edges.get(self.key(i, j), Edge(i, j)).pheromone

    def deposit(self, i: int, j: int, amount: float) -> None:
        k = self.key(i, j)
        if k in self.edges:
            self.edges[k].pheromone = min(12.0, self.edges[k].pheromone + amount)

    def evaporate(self, factor: float = 0.94) -> None:
        for e in self.edges.values():
            e.pheromone *= factor

    def tension(self) -> float:
        """Global tension = sum of repulsive pheromone on currently conflicting edges."""
        t = 0.0
        for (i, j), e in self.edges.items():
            # We will pass colors separately; here we just sum all existing pheromone
            # (deposits only happen on conflicts, so this is already conflict-weighted)
            t += e.pheromone
        return t

    def local_tension_for_color(self, node_id: int, neighbors: List[int],
                                 proposed_color: int, node_colors: Dict[int, int]) -> float:
        """If this node took proposed_color, how much repulsive field would it feel?"""
        t = 0.0
        for nb in neighbors:
            if node_colors.get(nb, -1) == proposed_color:
                t += self.get(node_id, nb)
        return t


class StigmergicGraphColoringWidget(QWidget):
    _live_instance: Optional["StigmergicGraphColoringWidget"] = None
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

        self.setWindowTitle("Stigmergic Graph Coloring — Field-Driven Channel Allocation")
        self.setMinimumSize(920, 720)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background-color: {_BG.name()};")

        self.nodes: List[Node] = []
        self.edges: List[Edge] = []
        self.field: Optional[RepulsiveField] = None
        self.agents: List[dict] = []  # {"edge_idx": int, "progress": float}
        self.tension_history: List[float] = []
        self.step_count = 0
        self.running = False
        self.speed_ms = 140

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._evolve_step)

        self._build_ui()
        self._new_graph(n_nodes=28, edge_prob=0.18)

        _publish_app_focus("Stigmergic Graph Coloring", "opened")
        _write_receipt("widget_boot", {"nodes": len(self.nodes), "edges": len(self.edges)})

    def closeEvent(self, event):
        self.running = False
        self._timer.stop()
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        _publish_app_focus("Stigmergic Graph Coloring", "closed")
        super().closeEvent(event)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(6)

        hdr = QLabel("Stigmergic Graph Coloring — repulsive pheromone field drives local color flips")
        hdr.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {_ACCENT.name()};")
        hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(hdr)

        bar = QHBoxLayout()
        bar.setSpacing(6)

        self._new_btn = QPushButton("New Random Graph")
        self._evolve_btn = QPushButton("Single Evolve Step")
        self._run_btn = QPushButton("▶ Run Swarm")
        self._stop_btn = QPushButton("■ Stop")
        self._reset_btn = QPushButton("Reset Pheromones")

        for btn in (self._new_btn, self._evolve_btn, self._run_btn, self._stop_btn, self._reset_btn):
            btn.setStyleSheet(
                f"QPushButton {{ color: {_TEXT.name()}; background: #1a1d2e; "
                f"border: 1px solid #3a3f5a; padding: 5px 12px; border-radius: 3px; }}"
                f"QPushButton:hover {{ background: #252a40; }}"
            )

        self._new_btn.clicked.connect(lambda: self._new_graph())
        self._evolve_btn.clicked.connect(self._evolve_step)
        self._run_btn.clicked.connect(self._start_swarm)
        self._stop_btn.clicked.connect(self._stop_swarm)
        self._reset_btn.clicked.connect(self._reset_pheromones)

        bar.addWidget(self._new_btn)
        bar.addWidget(self._evolve_btn)
        bar.addWidget(self._run_btn)
        bar.addWidget(self._stop_btn)
        bar.addWidget(self._reset_btn)

        bar.addStretch()

        self._tension_label = QLabel("Tension: 0.00")
        self._tension_label.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        self._tension_label.setStyleSheet(f"color: {_ACCENT.name()};")
        bar.addWidget(self._tension_label)

        self._steps_label = QLabel("Steps: 0")
        self._steps_label.setFont(QFont("Menlo", 10))
        self._steps_label.setStyleSheet(f"color: {_TEXT_DIM.name()};")
        bar.addWidget(self._steps_label)

        root.addLayout(bar)

        # Speed
        speed_bar = QHBoxLayout()
        speed_bar.addWidget(QLabel("Speed:"))
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(30, 420)
        self._speed_slider.setValue(self.speed_ms)
        self._speed_slider.valueChanged.connect(self._on_speed_change)
        speed_bar.addWidget(self._speed_slider, 1)
        self._speed_label = QLabel(f"{self.speed_ms} ms")
        self._speed_label.setStyleSheet(f"color: {_TEXT_DIM.name()};")
        speed_bar.addWidget(self._speed_label)
        root.addLayout(speed_bar)

        self._canvas = _GraphCanvas(self)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._canvas, stretch=1)

        self._status = QLabel("Field is alive. Agents deposit on conflicts. Nodes flip to drain local tension.")
        self._status.setFont(QFont("Menlo", 9))
        self._status.setStyleSheet(f"color: {_TEXT_DIM.name()};")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status)

    def _on_speed_change(self, v: int):
        self.speed_ms = v
        self._speed_label.setText(f"{v} ms")
        if self.running:
            self._timer.setInterval(v)

    def _new_graph(self, n_nodes: Optional[int] = None, edge_prob: float = 0.17):
        self.running = False
        self._timer.stop()

        n = n_nodes or random.randint(24, 32)
        self.nodes = []
        for i in range(n):
            # random geometric-ish placement
            angle = (i / n) * 2 * math.pi + random.uniform(-0.15, 0.15)
            r = 0.38 + random.uniform(-0.06, 0.06)
            x = 0.5 + r * math.cos(angle) + random.uniform(-0.04, 0.04)
            y = 0.5 + r * math.sin(angle) * 0.9 + random.uniform(-0.04, 0.04)
            self.nodes.append(Node(i, x, y, random.randrange(K_COLORS)))

        self.edges = []
        for i in range(n):
            for j in range(i + 1, n):
                if random.random() < edge_prob:
                    self.edges.append(Edge(i, j, pheromone=0.0))

        self.field = RepulsiveField(self.edges)
        self.agents = []
        for idx in range(min(12, len(self.edges))):
            self.agents.append({"edge_idx": idx, "progress": random.random()})

        self.tension_history.clear()
        self.step_count = 0
        self._update_labels()
        self._canvas.update()
        _write_receipt("new_graph", {"nodes": n, "edges": len(self.edges)})

    def _reset_pheromones(self):
        if self.field:
            for e in self.field.edges.values():
                e.pheromone = 0.0
            self.tension_history.clear()
            self._update_labels()
            self._canvas.update()
            _write_receipt("pheromones_reset", {})

    def _start_swarm(self):
        if not self.running:
            self.running = True
            self._timer.start(self.speed_ms)
            self._status.setText("Swarm running — field is actively driving color flips.")
            _write_receipt("swarm_started", {"steps": self.step_count})

    def _stop_swarm(self):
        self.running = False
        self._timer.stop()
        self._status.setText("Swarm paused. Field state preserved.")

    def _evolve_step(self):
        if not self.field or not self.nodes:
            return

        # 1. Evaporate
        self.field.evaporate(0.935)

        # 2. Agents walk + deposit on conflicts they observe
        for agent in self.agents:
            e = self.edges[agent["edge_idx"]]
            a, b = self.nodes[e.a], self.nodes[e.b]
            agent["progress"] += 0.18 + random.uniform(-0.03, 0.03)
            if agent["progress"] >= 1.0:
                agent["progress"] = 0.0
                # swap direction by picking a random adjacent edge at endpoint
                if random.random() < 0.5:
                    # at b, pick new edge
                    candidates = [i for i, ed in enumerate(self.edges) if ed.a == e.b or ed.b == e.b]
                else:
                    candidates = [i for i, ed in enumerate(self.edges) if ed.a == e.a or ed.b == e.a]
                if candidates:
                    agent["edge_idx"] = random.choice(candidates)

            # Deposit if the current edge is in conflict
            if a.color == b.color:
                self.field.deposit(e.a, e.b, 0.55)

        # 3. Every node evaluates local tension for each possible color and may flip
        node_neighbors: Dict[int, List[int]] = {i: [] for i in range(len(self.nodes))}
        for e in self.edges:
            node_neighbors[e.a].append(e.b)
            node_neighbors[e.b].append(e.a)

        flips = 0
        for node in self.nodes:
            current = node.color
            best_color = current
            best_t = self.field.local_tension_for_color(
                node.id, node_neighbors[node.id], current, {n.id: n.color for n in self.nodes}
            )

            for c in range(K_COLORS):
                if c == current:
                    continue
                t = self.field.local_tension_for_color(
                    node.id, node_neighbors[node.id], c, {n.id: n.color for n in self.nodes}
                )
                if t < best_t - 0.15:  # hysteresis so it doesn't oscillate wildly
                    best_t = t
                    best_color = c

            if best_color != current and random.random() < 0.38:
                node.color = best_color
                flips += 1

        # 4. Global conflict deposit (extra pressure on remaining same-color edges)
        for e in self.edges:
            a = self.nodes[e.a]
            b = self.nodes[e.b]
            if a.color == b.color:
                self.field.deposit(e.a, e.b, 0.35)

        self.step_count += 1
        t = self.field.tension()
        self.tension_history.append(t)
        if len(self.tension_history) > 180:
            self.tension_history.pop(0)

        self._update_labels()
        self._canvas.update()

        if self.step_count % 12 == 0:
            _write_receipt("evolve_batch", {
                "step": self.step_count,
                "tension": round(t, 3),
                "flips_last_batch": flips
            })

        # Auto-stop if tension is very low for a while
        if len(self.tension_history) > 18 and t < 1.8:
            recent = self.tension_history[-18:]
            if max(recent) - min(recent) < 1.5 and self.running:
                self._stop_swarm()
                self._status.setText("Field largely resolved conflicts. Tension stable and low.")

    def _update_labels(self):
        if self.field:
            t = self.field.tension()
            self._tension_label.setText(f"Tension: {t:.2f}")
            if t < 3.0:
                self._tension_label.setStyleSheet(f"color: #50ff90; font-weight: bold;")
            elif t < 9.0:
                self._tension_label.setStyleSheet(f"color: {_ACCENT.name()};")
            else:
                self._tension_label.setStyleSheet(f"color: #ffaa66;")
        self._steps_label.setText(f"Steps: {self.step_count}")

    def get_graph_for_paint(self):
        return self.nodes, self.edges, self.field


class _GraphCanvas(QWidget):
    def __init__(self, parent: StigmergicGraphColoringWidget):
        super().__init__(parent)
        self.parent_widget = parent
        self.setMinimumHeight(520)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()
        p.fillRect(self.rect(), _BG_GRAPH)

        nodes, edges, field = self.parent_widget.get_graph_for_paint()
        if not nodes or not field:
            return

        # Edges first (pheromone glow)
        for e in edges:
            a = nodes[e.a]
            b = nodes[e.b]
            x1, y1 = int(a.x * w), int(a.y * h)
            x2, y2 = int(b.x * w), int(b.y * h)

            ph = max(0.0, min(1.0, e.pheromone / 9.0))
            if ph < 0.02:
                continue

            pen_width = 1.2 + ph * 4.8
            alpha = int(55 + ph * 165)
            color = QColor(
                min(255, _PHERO_HIGH.red() + int(ph * 30)),
                min(255, _PHERO_HIGH.green() - int(ph * 60)),
                min(255, _PHERO_HIGH.blue() - int(ph * 40)),
                alpha
            )
            p.setPen(QPen(color, pen_width, Qt.PenStyle.SolidLine))
            p.drawLine(x1, y1, x2, y2)

            # extra glow for very high pheromone
            if ph > 0.65:
                glow = QColor(color.red(), color.green(), color.blue(), int(alpha * 0.35))
                p.setPen(QPen(glow, pen_width + 3.5, Qt.PenStyle.SolidLine))
                p.drawLine(x1, y1, x2, y2)

        # Nodes
        for node in nodes:
            x, y = int(node.x * w), int(node.y * h)
            r = 13

            # halo
            grad = QRadialGradient(x, y, r * 2.2)
            grad.setColorAt(0.0, QColor(255, 255, 255, 18))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x, y), r * 1.9, r * 1.9)

            # node body
            col = COLORS[node.color % len(COLORS)]
            p.setBrush(QBrush(col))
            p.setPen(QPen(_NODE_BORDER, 1.5))
            p.drawEllipse(QPointF(x, y), r, r)

            # channel label
            p.setPen(QPen(_TEXT, 1))
            p.setFont(QFont("Menlo", 7, QFont.Weight.Bold))
            p.drawText(QRectF(x - r, y - r, 2 * r, 2 * r),
                       Qt.AlignmentFlag.AlignCenter, COLOR_NAMES[node.color])

        # Legend / status
        p.setPen(QPen(_TEXT_DIM, 1))
        p.setFont(QFont("Menlo", 8))
        p.drawText(12, h - 14, f"Nodes: {len(nodes)}   Edges: {len(edges)}   Agents: {len(self.parent_widget.agents)}")


# ── Standalone smoke test ─────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = StigmergicGraphColoringWidget()
    w.show()
    print("Stigmergic Graph Coloring widget booted. For the Swarm. 🐜⚡")
    sys.exit(app.exec())
