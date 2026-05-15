#!/usr/bin/env python3
"""
sifta_mondaloy_research_widget.py

Embedded SIFTA OS simulation app for the Mondaloy process field.
All physics math and ledger writes live in System.swarm_mondaloy_research_field;
this module renders the field and dispatches user-triggered deposits.
"""
from __future__ import annotations

import math
import random
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "Applications") not in sys.path:
    sys.path.insert(0, str(_REPO / "Applications"))

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from System.swarm_mondaloy_research_field import (
    PROCESS_VECTORS,
    field_snapshot,
    run_hypothesis,
    score_grid,
    score_process_hypothesis,
    seed_public_source_deposits,
)

try:
    from _doctor_sigil_chrome import doctor_sigil_html
except Exception:
    doctor_sigil_html = None


BG0 = QColor(4, 7, 15)
BG1 = QColor(9, 15, 31)
PANEL = "#0e1628"
PANEL_2 = "#111d33"
TEXT = "#e6eefb"
MUTED = "#8ea0bd"
CYAN = QColor(54, 225, 214)
GOLD = QColor(255, 195, 91)
RED = QColor(255, 79, 107)
GREEN = QColor(91, 255, 147)
BLUE = QColor(83, 151, 255)


def _font(size: int, *, bold: bool = False) -> QFont:
    out = QFont("Menlo", size)
    if bold:
        out.setWeight(QFont.Weight.DemiBold)
    out.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return out


def _score_color(value: float) -> QColor:
    value = max(0.0, min(1.0, float(value)))
    stops = (
        (0.00, QColor(25, 33, 58)),
        (0.28, QColor(72, 59, 118)),
        (0.52, QColor(32, 128, 158)),
        (0.76, QColor(64, 214, 169)),
        (1.00, QColor(255, 206, 102)),
    )
    for idx in range(len(stops) - 1):
        x0, c0 = stops[idx]
        x1, c1 = stops[idx + 1]
        if x0 <= value <= x1:
            t = (value - x0) / max(1e-9, x1 - x0)
            t = t * t * (3.0 - 2.0 * t)
            return QColor(
                int(c0.red() + (c1.red() - c0.red()) * t),
                int(c0.green() + (c1.green() - c0.green()) * t),
                int(c0.blue() + (c1.blue() - c0.blue()) * t),
                228,
            )
    return QColor(stops[-1][1])


class ProcessFieldCanvas(QWidget):
    """Animated process-window heatmap plus stigmergic hypothesis deposits."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(420)
        self.setMouseTracking(True)
        self.alloy = "MONDALOY_200"
        self.vector = "heat_treat"
        self.grid: list[list[float]] = []
        self.snapshot: dict[str, Any] = {}
        self.score: dict[str, Any] | None = None
        self.phase = 0.0
        self._rng = random.Random(77)
        self._particles = [
            [self._rng.random(), self._rng.random(), self._rng.uniform(-0.003, 0.003), self._rng.uniform(-0.002, 0.002)]
            for _ in range(120)
        ]
        self.rebuild_grid()

    def rebuild_grid(self) -> None:
        try:
            self.grid = score_grid(alloy=self.alloy, vector=self.vector, nx=36, ny=26)
        except Exception:
            self.grid = []
        self.update()

    def set_context(self, alloy: str, vector: str) -> None:
        changed = alloy != self.alloy or vector != self.vector
        self.alloy = alloy
        self.vector = vector
        if changed:
            self.rebuild_grid()

    def set_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot
        self.update()

    def set_score(self, score: dict[str, Any] | None) -> None:
        self.score = score
        self.update()

    def tick(self) -> None:
        self.phase += 0.018
        for particle in self._particles:
            x, y, vx, vy = particle
            ridge = 0.52 + 0.12 * math.sin(self.phase + x * 5.0)
            particle[2] = vx * 0.985 + (ridge - y) * 0.0007
            particle[3] = vy * 0.985 + 0.0008 * math.sin(self.phase * 2.0 + x * 9.0)
            particle[0] = (x + particle[2]) % 1.0
            particle[1] = max(0.0, min(1.0, y + particle[3]))
        self.update()

    def _field_rect(self) -> QRectF:
        return QRectF(34, 54, max(100, self.width() - 68), max(120, self.height() - 112))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        root = QLinearGradient(0, 0, self.width(), self.height())
        root.setColorAt(0.0, BG0)
        root.setColorAt(0.6, BG1)
        root.setColorAt(1.0, QColor(17, 9, 29))
        painter.fillRect(self.rect(), root)

        self._paint_title(painter)
        field = self._field_rect()
        self._paint_heatmap(painter, field)
        self._paint_cliffs_and_ridge(painter, field)
        self._paint_particles(painter, field)
        self._paint_deposits(painter, field)
        self._paint_axes(painter, field)
        self._paint_score_overlay(painter, field)
        self._paint_unknowns(painter, field)

    def _paint_title(self, painter: QPainter) -> None:
        painter.setFont(_font(13, bold=True))
        painter.setPen(QPen(QColor(238, 246, 255)))
        painter.drawText(QRectF(22, 14, self.width() - 44, 24), int(Qt.AlignmentFlag.AlignLeft), "Mondaloy process field")
        painter.setFont(_font(9))
        painter.setPen(QPen(QColor(139, 158, 190)))
        painter.drawText(
            QRectF(22, 33, self.width() - 44, 18),
            int(Qt.AlignmentFlag.AlignLeft),
            f"{self.alloy} / {self.vector} / local surrogate + append-only receipts",
        )

    def _paint_heatmap(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.setClipPath(path)
        painter.fillRect(rect, QColor(10, 18, 32))
        if self.grid:
            ny = len(self.grid)
            nx = len(self.grid[0]) if ny else 0
            cell_w = rect.width() / max(1, nx)
            cell_h = rect.height() / max(1, ny)
            for j, row in enumerate(self.grid):
                for i, value in enumerate(row):
                    color = _score_color(value)
                    painter.fillRect(
                        QRectF(rect.left() + i * cell_w, rect.bottom() - (j + 1) * cell_h, cell_w + 1.0, cell_h + 1.0),
                        QBrush(color),
                    )
        vignette = QRadialGradient(rect.center(), rect.width() * 0.68)
        vignette.setColorAt(0.0, QColor(255, 255, 255, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 115))
        painter.fillRect(rect, QBrush(vignette))
        painter.restore()

        painter.setPen(QPen(QColor(92, 125, 170, 160), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 10, 10)

    def _paint_cliffs_and_ridge(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()
        painter.setClipRect(rect)
        painter.setPen(QPen(QColor(255, 78, 102, 110), 2.0, Qt.PenStyle.DashLine))
        for offset in (0.0, 0.12, 0.24):
            path = QPainterPath()
            for step in range(72):
                t = step / 71.0
                x = rect.left() + t * rect.width()
                y = rect.top() + rect.height() * (0.16 + 0.13 * math.sin(6.0 * t + self.phase + offset))
                if step == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)

        painter.setPen(QPen(QColor(255, 226, 130, 180), 2.4))
        path = QPainterPath()
        for step in range(96):
            t = step / 95.0
            x = rect.left() + t * rect.width()
            y = rect.top() + rect.height() * (0.56 + 0.08 * math.sin(t * 2.5 * math.pi + self.phase * 0.4))
            if step == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        painter.drawPath(path)
        painter.restore()

    def _paint_particles(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()
        painter.setClipRect(rect)
        for x_n, y_n, vx, vy in self._particles:
            x = rect.left() + x_n * rect.width()
            y = rect.top() + y_n * rect.height()
            speed = min(1.0, 160.0 * math.hypot(vx, vy))
            color = QColor(CYAN)
            color.setAlpha(40 + int(90 * speed))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(x, y), 1.4 + speed * 2.0, 1.4 + speed * 2.0)
        painter.restore()

    def _deposit_position(self, dep: dict[str, Any], rect: QRectF) -> QPointF:
        score = dep.get("physics_score") if isinstance(dep.get("physics_score"), dict) else {}
        temps = score.get("parsed_temperatures_c") or []
        try:
            solution = max(float(t) for t in temps) if temps else None
            aging = min(float(t) for t in temps if float(t) < float(solution) - 40.0) if solution else None
        except Exception:
            solution = aging = None
        if solution is not None and aging is not None:
            x = rect.left() + max(0.0, min(1.0, (solution - 1000.0) / 240.0)) * rect.width()
            y = rect.bottom() - max(0.0, min(1.0, (aging - 580.0) / 280.0)) * rect.height()
            return QPointF(x, y)
        vector = str(dep.get("vector", ""))
        idx = PROCESS_VECTORS.index(vector) if vector in PROCESS_VECTORS else 0
        x = rect.left() + (idx + 0.5) / len(PROCESS_VECTORS) * rect.width()
        y = rect.bottom() - 18.0 - 14.0 * math.sin(self.phase + idx)
        return QPointF(x, y)

    def _paint_deposits(self, painter: QPainter, rect: QRectF) -> None:
        strongest = self.snapshot.get("strongest") or []
        for dep in strongest[:14]:
            try:
                strength = float(dep.get("strength", 0.0))
            except Exception:
                strength = 0.0
            pos = self._deposit_position(dep, rect)
            color = GOLD if dep.get("alloy") == "MONDALOY_200" else GREEN
            if dep.get("kind") == "DOCUMENT_READ":
                color = BLUE
            radius = 5.0 + min(20.0, strength * 24.0)
            glow = QColor(color)
            glow.setAlpha(45)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(pos, radius * 2.0, radius * 2.0)
            color.setAlpha(210)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(pos, radius, radius)
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(pos, radius, radius)

    def _paint_axes(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(_font(8))
        painter.setPen(QPen(QColor(180, 196, 222)))
        painter.drawText(QRectF(rect.left(), rect.bottom() + 8, rect.width(), 18), int(Qt.AlignmentFlag.AlignCenter), "solution / HIP temperature C")
        painter.save()
        painter.translate(10, rect.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-rect.height() / 2, 0, rect.height(), 18), int(Qt.AlignmentFlag.AlignCenter), "aging temperature C")
        painter.restore()

        painter.setPen(QPen(QColor(158, 176, 205, 150), 1.0))
        for value in (1000, 1080, 1160, 1240):
            x = rect.left() + (value - 1000) / 240.0 * rect.width()
            painter.drawLine(int(x), int(rect.bottom()), int(x), int(rect.bottom() + 4))
            painter.drawText(QRectF(x - 24, rect.bottom() + 22, 48, 14), int(Qt.AlignmentFlag.AlignCenter), str(value))
        for value in (580, 700, 820, 860):
            y = rect.bottom() - (value - 580) / 280.0 * rect.height()
            painter.drawLine(int(rect.left() - 4), int(y), int(rect.left()), int(y))
            painter.drawText(QRectF(rect.left() - 34, y - 7, 30, 14), int(Qt.AlignmentFlag.AlignRight), str(value))

    def _paint_score_overlay(self, painter: QPainter, rect: QRectF) -> None:
        if not self.score:
            return
        box = QRectF(rect.right() - 284, rect.top() + 16, 260, 112)
        grad = QLinearGradient(box.topLeft(), box.bottomRight())
        grad.setColorAt(0.0, QColor(11, 18, 32, 225))
        grad.setColorAt(1.0, QColor(31, 24, 48, 225))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor(122, 154, 204, 150), 1.0))
        painter.drawRoundedRect(box, 8, 8)
        painter.setFont(_font(9, bold=True))
        painter.setPen(QPen(QColor(240, 247, 255)))
        painter.drawText(QRectF(box.left() + 12, box.top() + 9, box.width() - 24, 18), int(Qt.AlignmentFlag.AlignLeft), "last simulation receipt")
        painter.setFont(_font(8))
        lines = [
            f"physics={self.score.get('physics_score', 0):.3f} confidence={self.score.get('confidence', 0):.3f}",
            f"gamma-prime={self.score.get('gamma_prime_index', 0):.3f} burn={self.score.get('burn_resistance_proxy', 0):.3f}",
            f"strength={self.score.get('tensile_strength_ksi_proxy', 0):.1f} ksi  margin={self.score.get('promoted_combustion_margin_psi_proxy', 0):.0f} psi",
            f"diffusion={self.score.get('diffusion_length_um', 0):.2f} um",
        ]
        painter.setPen(QPen(QColor(189, 205, 230)))
        for idx, line in enumerate(lines):
            painter.drawText(QRectF(box.left() + 12, box.top() + 32 + idx * 18, box.width() - 24, 16), int(Qt.AlignmentFlag.AlignLeft), line)

    def _paint_unknowns(self, painter: QPainter, rect: QRectF) -> None:
        unknowns = self.snapshot.get("unknown_vectors") or []
        if not unknowns:
            return
        painter.setFont(_font(8))
        painter.setPen(QPen(QColor(255, 153, 153, 190)))
        text = "unknown vectors: " + ", ".join(str(v) for v in unknowns[:4])
        if len(unknowns) > 4:
            text += f" +{len(unknowns) - 4}"
        painter.drawText(QRectF(rect.left() + 10, rect.top() + 8, rect.width() - 20, 16), int(Qt.AlignmentFlag.AlignLeft), text)


class StatTile(QFrame):
    def __init__(self, label: str, value: str = "0.000", accent: str = "#36e1d6") -> None:
        super().__init__()
        self.setObjectName("StatTile")
        self.setStyleSheet(
            f"""
            QFrame#StatTile {{
                background: {PANEL_2};
                border: 1px solid rgba(130,160,210,70);
                border-radius: 8px;
            }}
            QLabel#TileLabel {{ color: {MUTED}; font-size: 10px; }}
            QLabel#TileValue {{ color: {accent}; font-size: 18px; font-weight: 700; }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.label = QLabel(label)
        self.label.setObjectName("TileLabel")
        self.value = QLabel(value)
        self.value.setObjectName("TileValue")
        layout.addWidget(self.label)
        layout.addWidget(self.value)

    def set_value(self, value: Any) -> None:
        self.value.setText(str(value))


class MondaloyResearchFieldApp(QWidget):
    """Programs > Simulations entry for local Mondaloy process research."""

    DEFAULT_HYPOTHESIS = (
        "solution_treat 1150C/2h + age 760C/8h + 650C/24h under argon; "
        "powder oxygen 250 ppm nitrogen 80 ppm; oxygen clean surface"
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mondaloy Stigmergic Research Field")
        self.resize(1240, 820)
        self._last_score: dict[str, Any] | None = None
        self.setStyleSheet(
            f"""
            QWidget {{ background: #050913; color: {TEXT}; font-family: Menlo; }}
            QLabel#Title {{ color: #f4f8ff; font-size: 22px; font-weight: 800; }}
            QLabel#Sub {{ color: {MUTED}; font-size: 11px; }}
            QFrame#Panel {{
                background: {PANEL};
                border: 1px solid rgba(112,143,191,70);
                border-radius: 8px;
            }}
            QComboBox, QPlainTextEdit {{
                background: #081224;
                color: {TEXT};
                border: 1px solid #273958;
                border-radius: 6px;
                padding: 7px;
                selection-background-color: #245a77;
            }}
            QPushButton {{
                background: #163554;
                color: #eff8ff;
                border: 1px solid #2d6f93;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: #1e5678; border-color: #36e1d6; }}
            QPushButton#Gold {{ background: #5a4219; border-color: #d5a54d; }}
            QTableWidget {{
                background: #081224;
                color: {TEXT};
                gridline-color: #1e304f;
                border: 1px solid #273958;
                border-radius: 6px;
            }}
            QHeaderView::section {{
                background: #12213a;
                color: #bdd2ee;
                border: 0;
                padding: 6px;
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)

        if doctor_sigil_html:
            sigil = QLabel()
            sigil.setText(doctor_sigil_html(["C55M", "CG55M"], "Mondaloy Stigmergic Research Field"))
            sigil.setFixedHeight(42)
            root.addWidget(sigil)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("Mondaloy process field")
        title.setObjectName("Title")
        sub = QLabel("MONDALOY 100/200 / heat, powder, HIP, oxygen service, burn-resistance proxies / local JSONL receipts")
        sub.setObjectName("Sub")
        titles.addWidget(title)
        titles.addWidget(sub)
        header.addLayout(titles, 1)
        self.status = QLabel("No simulation run yet")
        self.status.setObjectName("Sub")
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.status, 1)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        left = QVBoxLayout()
        left.setSpacing(10)
        body.addLayout(left, 2)
        self.canvas = ProcessFieldCanvas()
        left.addWidget(self.canvas, 1)

        stats = QGridLayout()
        stats.setSpacing(8)
        self.tile_physics = StatTile("physics", "0.000", "#36e1d6")
        self.tile_conf = StatTile("confidence", "0.000", "#5bff93")
        self.tile_burn = StatTile("burn proxy", "0.000", "#ffc35b")
        self.tile_gamma = StatTile("gamma-prime", "0.000", "#ff6f91")
        stats.addWidget(self.tile_physics, 0, 0)
        stats.addWidget(self.tile_conf, 0, 1)
        stats.addWidget(self.tile_burn, 0, 2)
        stats.addWidget(self.tile_gamma, 0, 3)
        left.addLayout(stats)

        right = QVBoxLayout()
        right.setSpacing(10)
        body.addLayout(right, 1)

        controls = QFrame()
        controls.setObjectName("Panel")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(8)
        self.alloy_box = QComboBox()
        self.alloy_box.addItems(["MONDALOY_200", "MONDALOY_100"])
        self.vector_box = QComboBox()
        self.vector_box.addItems(list(PROCESS_VECTORS))
        self.hypothesis_edit = QPlainTextEdit()
        self.hypothesis_edit.setPlainText(self.DEFAULT_HYPOTHESIS)
        self.hypothesis_edit.setFixedHeight(104)
        controls_layout.addWidget(QLabel("Alloy"))
        controls_layout.addWidget(self.alloy_box)
        controls_layout.addWidget(QLabel("Process vector"))
        controls_layout.addWidget(self.vector_box)
        controls_layout.addWidget(QLabel("Hypothesis"))
        controls_layout.addWidget(self.hypothesis_edit)
        buttons = QHBoxLayout()
        self.seed_button = QPushButton("Seed public sources")
        self.seed_button.setObjectName("Gold")
        self.run_button = QPushButton("Run simulation")
        buttons.addWidget(self.seed_button)
        buttons.addWidget(self.run_button)
        controls_layout.addLayout(buttons)
        right.addWidget(controls)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["kind", "alloy", "vector", "strength", "source"])
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(210)
        right.addWidget(self.table, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(150)
        right.addWidget(self.log)

        self.seed_button.clicked.connect(self.seed_sources)
        self.run_button.clicked.connect(self.run_simulation)
        self.alloy_box.currentTextChanged.connect(self._context_changed)
        self.vector_box.currentTextChanged.connect(self._context_changed)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)
        self.refresh_snapshot()

    def _context_changed(self) -> None:
        alloy = self.alloy_box.currentText()
        vector = self.vector_box.currentText()
        self.canvas.set_context(alloy, vector)
        preview = score_process_hypothesis(alloy, vector, self.hypothesis_edit.toPlainText())
        self._last_score = dict(preview.__dict__)
        self.canvas.set_score(self._last_score)
        self.update_tiles(self._last_score)

    def _tick(self) -> None:
        self.canvas.tick()

    def seed_sources(self) -> None:
        rows = seed_public_source_deposits()
        self.status.setText(f"Seeded {len(rows)} public-source deposits")
        self.refresh_snapshot()

    def run_simulation(self) -> None:
        alloy = self.alloy_box.currentText()
        vector = self.vector_box.currentText()
        hypothesis = self.hypothesis_edit.toPlainText().strip()
        if not hypothesis:
            self.status.setText("Hypothesis is empty")
            return
        result = run_hypothesis(alloy, vector, hypothesis, write=True)
        self._last_score = result["score"]
        self.canvas.set_score(self._last_score)
        self.update_tiles(self._last_score)
        receipt = result["hypothesis"]["receipt"][:16]
        self.status.setText(f"Wrote hypothesis receipt {receipt}")
        self.refresh_snapshot()

    def update_tiles(self, score: dict[str, Any] | None) -> None:
        if not score:
            return
        self.tile_physics.set_value(f"{float(score.get('physics_score', 0.0)):.3f}")
        self.tile_conf.set_value(f"{float(score.get('confidence', 0.0)):.3f}")
        self.tile_burn.set_value(f"{float(score.get('burn_resistance_proxy', 0.0)):.3f}")
        self.tile_gamma.set_value(f"{float(score.get('gamma_prime_index', 0.0)):.3f}")

    def refresh_snapshot(self) -> None:
        snapshot = field_snapshot()
        self.canvas.set_snapshot(snapshot)
        strongest = snapshot.get("strongest") or []
        self.table.setRowCount(len(strongest[:10]))
        for row_idx, dep in enumerate(strongest[:10]):
            values = [
                dep.get("kind", ""),
                dep.get("alloy", ""),
                dep.get("vector", ""),
                f"{float(dep.get('strength', 0.0)):.4f}",
                dep.get("source_doc", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col, item)
        self.table.resizeColumnsToContents()

        by_vector = snapshot.get("by_vector") or {}
        top_vectors = sorted(by_vector.items(), key=lambda item: abs(float(item[1])), reverse=True)[:6]
        lines = [
            f"ledger: {snapshot.get('ledger')}",
            f"deposits: {snapshot.get('deposit_count', 0)}",
            "field: " + ", ".join(f"{name}={value:.3f}" for name, value in top_vectors),
        ]
        if snapshot.get("unknown_vectors"):
            lines.append("unknown: " + ", ".join(snapshot["unknown_vectors"]))
        if self._last_score:
            falsifiers = self._last_score.get("falsifiers") or []
            if falsifiers:
                lines.append("falsifiers: " + "; ".join(str(f) for f in falsifiers))
        self.log.setPlainText("\n".join(lines))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MondaloyResearchFieldApp()
    w.show()
    sys.exit(app.exec())
