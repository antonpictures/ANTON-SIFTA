#!/usr/bin/env python3
"""
sifta_interstellar_evidence_crucible.py

Embedded SIFTA OS app for the 3I/ATLAS stigmergic evidence field.
The app stays inside Python/Qt and delegates all receipts, public-source seeds,
decay math, and JPL Horizons fetches to System.swarm_3i_evidence_field.
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
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from System.swarm_3i_evidence_field import (
    CLAIM_LANES,
    OBJECT_ID,
    TRUTH_LABEL,
    add_claim,
    fetch_jpl_horizons,
    field_snapshot,
    orbit_points_2d,
    seed_public_evidence_deposits,
)

try:
    from _doctor_sigil_chrome import doctor_sigil_html
except Exception:
    doctor_sigil_html = None


BG = QColor(4, 7, 13)
BG2 = QColor(9, 14, 27)
PANEL = "#0d1524"
PANEL2 = "#121d31"
TEXT = "#edf4ff"
MUTED = "#8c9bb6"
CYAN = QColor(70, 232, 221)
BLUE = QColor(91, 145, 255)
GOLD = QColor(255, 204, 101)
RED = QColor(255, 76, 104)
GREEN = QColor(95, 255, 158)
PURPLE = QColor(181, 117, 255)


def _font(size: int, *, bold: bool = False) -> QFont:
    out = QFont("Menlo", size)
    if bold:
        out.setWeight(QFont.Weight.DemiBold)
    out.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return out


def _lane_color(lane: str, value: float = 1.0) -> QColor:
    palette = {
        "orbit_dynamics": CYAN,
        "non_grav_acceleration": RED,
        "coma_morphology": GOLD,
        "chemistry": GREEN,
        "instrument_coverage": BLUE,
        "origin_model": PURPLE,
        "sentinel_claims": QColor(255, 137, 78),
    }
    base = QColor(palette.get(lane, QColor(160, 170, 195)))
    base.setAlpha(60 + int(170 * max(0.0, min(1.0, value))))
    return base


class InterstellarFieldCanvas(QWidget):
    """Orbit proxy + living evidence deposits."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(440)
        self.snapshot: dict[str, Any] = {}
        self.phase = 0.0
        self.points = orbit_points_2d()
        self._rng = random.Random(313)
        self._swimmers = [
            [self._rng.random(), self._rng.random(), 0.0, 0.0, self._rng.uniform(0.35, 1.3), self._rng.choice(tuple(CLAIM_LANES))]
            for _ in range(120)
        ]

    def set_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot
        self.update()

    def tick(self) -> None:
        self.phase += 0.018
        strongest = list(self.snapshot.get("strongest") or [])[:10]
        
        # Calculate node positions in normalized coordinates
        nodes = []
        for idx, row in enumerate(strongest):
            strength = max(0.0, float(row.get("strength", 0.0) or 0.0))
            angle = idx * 2.399 + self.phase * 0.15
            rr = 0.13 + 0.34 * ((idx * 29) % 100) / 100.0
            x_n = 0.5 + math.cos(angle) * rr
            y_n = 0.5 + math.sin(angle) * rr * 0.72
            nodes.append((x_n, y_n, strength))

        for sw in self._swimmers:
            # Gravity from nodes
            ax, ay = 0.0, 0.0
            for nx, ny, strength in nodes:
                dx = nx - sw[0]
                dy = ny - sw[1]
                dist_sq = max(0.001, dx*dx + dy*dy)
                f = (0.0003 * strength) / dist_sq
                ax += f * dx
                ay += f * dy
            
            # Add some swirling force (stigmergic turbulence)
            ax += 0.001 * math.sin(self.phase + sw[1]*10)
            ay += 0.001 * math.cos(self.phase + sw[0]*10)

            # Update velocity
            sw[2] += ax
            sw[3] += ay
            
            # Friction / speed limit
            speed = math.hypot(sw[2], sw[3])
            max_s = 0.015 * sw[4]
            if speed > max_s:
                sw[2] = (sw[2] / speed) * max_s
                sw[3] = (sw[3] / speed) * max_s
            
            sw[2] *= 0.98  # drag
            sw[3] *= 0.98
            
            # Update position
            sw[0] += sw[2]
            sw[1] += sw[3]
            
            # Wrap around
            sw[0] = sw[0] % 1.0
            sw[1] = sw[1] % 1.0
            
        self.update()

    def _plot_rect(self) -> QRectF:
        return QRectF(34, 58, max(100, self.width() - 68), max(120, self.height() - 118))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, BG)
        grad.setColorAt(0.62, BG2)
        grad.setColorAt(1.0, QColor(18, 11, 30))
        painter.fillRect(self.rect(), grad)

        rect = self._plot_rect()
        self._paint_title(painter)
        self._paint_space(painter, rect)
        self._paint_orbit(painter, rect)
        self._paint_observation_rings(painter, rect)
        self._paint_deposit_nodes(painter, rect)
        self._paint_swimmers(painter, rect)
        self._paint_stats(painter, rect)

    def _paint_title(self, painter: QPainter) -> None:
        painter.setFont(_font(13, bold=True))
        painter.setPen(QPen(QColor(245, 249, 255)))
        painter.drawText(QRectF(22, 14, self.width() - 44, 25), int(Qt.AlignmentFlag.AlignLeft), "Interstellar Evidence Crucible")
        painter.setFont(_font(9))
        painter.setPen(QPen(QColor(139, 154, 184)))
        painter.drawText(
            QRectF(22, 34, self.width() - 44, 20),
            int(Qt.AlignmentFlag.AlignLeft),
            f"{OBJECT_ID} / JPL + MPC + MPEC + telescope papers + claim decay / {TRUTH_LABEL}",
        )

    def _paint_space(self, painter: QPainter, rect: QRectF) -> None:
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        painter.save()
        painter.setClipPath(path)
        painter.fillRect(rect, QColor(7, 13, 25))
        for idx in range(90):
            x = rect.left() + ((idx * 37) % 101) / 101.0 * rect.width()
            y = rect.top() + ((idx * 61) % 97) / 97.0 * rect.height()
            alpha = 32 + (idx * 17) % 80
            painter.setPen(QPen(QColor(170, 204, 255, alpha), 1.0))
            painter.drawPoint(QPointF(x, y))
        glow = QRadialGradient(rect.center(), rect.width() * 0.55)
        glow.setColorAt(0.0, QColor(30, 82, 112, 92))
        glow.setColorAt(0.56, QColor(16, 36, 62, 42))
        glow.setColorAt(1.0, QColor(0, 0, 0, 150))
        painter.fillRect(rect, QBrush(glow))
        painter.restore()
        painter.setPen(QPen(QColor(83, 109, 151, 150), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 14, 14)

    def _scale_points(self, rect: QRectF) -> list[QPointF]:
        if not self.points:
            return []
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span = max(max_x - min_x, max_y - min_y, 1e-9)
        out: list[QPointF] = []
        for x, y, _r in self.points:
            xn = 0.5 + (x - (min_x + max_x) * 0.5) / span
            yn = 0.5 + (y - (min_y + max_y) * 0.5) / span
            out.append(QPointF(rect.left() + xn * rect.width() * 0.86, rect.top() + yn * rect.height() * 0.86))
        return out

    def _paint_orbit(self, painter: QPainter, rect: QRectF) -> None:
        pts = self._scale_points(rect)
        if len(pts) < 2:
            return
        painter.save()
        painter.setClipRect(rect)
        center = rect.center()
        
        # Center black hole / star pulse
        pulse = (math.sin(self.phase * 2.0) + 1.0) * 0.5
        painter.setPen(QPen(QColor(255, 194, 90, 45 + int(30 * pulse)), 1.1, Qt.PenStyle.DashLine))
        for radius in (38, 70, 108, 154):
            painter.drawEllipse(center, radius + pulse * 4.0, radius + pulse * 4.0)
            
        painter.setPen(QPen(QColor(255, 217, 129, 230), 3.0))
        orbit = QPainterPath(pts[0])
        for p in pts[1:]:
            orbit.lineTo(p)
        painter.drawPath(orbit)
        
        painter.setPen(QPen(QColor(95, 219, 255, 210), 1.2))
        painter.drawPath(orbit)
        
        # Sun core
        painter.setPen(Qt.PenStyle.NoPen)
        sun_glow = QRadialGradient(center, 40)
        sun_glow.setColorAt(0.0, QColor(255, 228, 132, 255))
        sun_glow.setColorAt(0.4, QColor(255, 158, 74, 180))
        sun_glow.setColorAt(1.0, QColor(255, 120, 20, 0))
        painter.setBrush(QBrush(sun_glow))
        painter.drawEllipse(center, 40, 40)
        
        # The object
        t = (math.sin(self.phase * 0.7) + 1.0) * 0.5
        idx = min(len(pts) - 1, max(0, int(t * (len(pts) - 1))))
        obj = pts[idx]
        
        obj_glow = QRadialGradient(obj, 15)
        obj_glow.setColorAt(0.0, QColor(226, 248, 255, 255))
        obj_glow.setColorAt(1.0, QColor(95, 219, 255, 0))
        painter.setBrush(QBrush(obj_glow))
        painter.drawEllipse(obj, 15.0, 15.0)
        
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawEllipse(obj, 3.0, 3.0)
        
        painter.setPen(QPen(QColor(226, 248, 255, 155), 1.0, Qt.PenStyle.DotLine))
        painter.drawLine(center, obj)
        painter.restore()

    def _paint_observation_rings(self, painter: QPainter, rect: QRectF) -> None:
        lanes = dict(self.snapshot.get("by_lane") or {})
        for idx, lane in enumerate(CLAIM_LANES):
            value = max(0.0, float(lanes.get(lane, 0.0)))
            angle = self.phase * 0.32 + idx * (2.0 * math.pi / max(1, len(CLAIM_LANES)))
            radius = 0.18 + 0.34 * ((idx % 4) / 3.0)
            x = rect.center().x() + math.cos(angle) * rect.width() * radius
            y = rect.center().y() + math.sin(angle) * rect.height() * radius * 0.64
            color = _lane_color(lane, min(1.0, value))
            painter.setPen(QPen(color, 1.4))
            painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 24 + int(28 * min(1.0, value)))))
            painter.drawEllipse(QPointF(x, y), 10 + 8 * min(1.0, value), 10 + 8 * min(1.0, value))

    def _paint_deposit_nodes(self, painter: QPainter, rect: QRectF) -> None:
        strongest = list(self.snapshot.get("strongest") or [])[:10]
        if not strongest:
            return
        painter.save()
        painter.setClipRect(rect)
        for idx, row in enumerate(strongest):
            lane = str(row.get("lane", ""))
            strength = max(0.0, float(row.get("strength", 0.0) or 0.0))
            angle = idx * 2.399 + self.phase * 0.15
            rr = 0.13 + 0.34 * ((idx * 29) % 100) / 100.0
            x = rect.center().x() + math.cos(angle) * rect.width() * rr
            y = rect.center().y() + math.sin(angle) * rect.height() * rr * 0.72
            color = _lane_color(lane, min(1.0, strength))
            
            # Glow
            glow = QRadialGradient(QPointF(x, y), 20.0 + 15.0 * min(1.0, strength))
            glow.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 100))
            glow.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(QPointF(x, y), 20.0 + 15.0 * min(1.0, strength), 20.0 + 15.0 * min(1.0, strength))

            painter.setPen(QPen(color, 1.5))
            painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 90 + int(120 * min(1.0, strength)))))
            radius = 5.0 + 12.0 * min(1.0, strength)
            painter.drawEllipse(QPointF(x, y), radius, radius)
            
            # Pulsing inner core
            core_pulse = (math.sin(self.phase * 3.0 + idx) + 1.0) * 0.5
            painter.setBrush(QBrush(QColor(255, 255, 255, int(150 * core_pulse))))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(x, y), radius * 0.4, radius * 0.4)
            
        painter.restore()

    def _paint_swimmers(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()
        painter.setClipRect(rect)
        
        strongest = list(self.snapshot.get("strongest") or [])[:10]
        nodes = []
        for idx, row in enumerate(strongest):
            angle = idx * 2.399 + self.phase * 0.15
            rr = 0.13 + 0.34 * ((idx * 29) % 100) / 100.0
            nx = rect.center().x() + math.cos(angle) * rect.width() * rr
            ny = rect.center().y() + math.sin(angle) * rect.height() * rr * 0.72
            nodes.append((nx, ny))

        for sw in self._swimmers:
            x = rect.left() + sw[0] * rect.width()
            y = rect.top() + sw[1] * rect.height()
            color = _lane_color(str(sw[5]), 0.8)
            
            # Draw connection to nearest node if close enough
            for nx, ny in nodes:
                dist = math.hypot(nx - x, ny - y)
                if dist < 60.0:
                    painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), int(80 * (1.0 - dist/60.0))), 0.8))
                    painter.drawLine(QPointF(x, y), QPointF(nx, ny))
            
            # Draw swimmer body
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            size = 1.5 + sw[4]
            painter.drawEllipse(QPointF(x, y), size, size)
            
            # Draw tail
            tx = x - sw[2] * rect.width() * 2.0
            ty = y - sw[3] * rect.height() * 2.0
            painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 100), size))
            painter.drawLine(QPointF(x, y), QPointF(tx, ty))
            
        painter.restore()

    def _paint_stats(self, painter: QPainter, rect: QRectF) -> None:
        deposits = int(self.snapshot.get("deposit_count", 0) or 0)
        reward = float(self.snapshot.get("total_stgm_reward_hint", 0.0) or 0.0)
        unknown = list(self.snapshot.get("unknown_lanes") or [])
        text = f"deposits={deposits}   reward_hint={reward:.2f} STGM   cold_lanes={len(unknown)}"
        box = QRectF(rect.left() + 18, rect.bottom() - 38, rect.width() - 36, 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(3, 7, 14, 170)))
        painter.drawRoundedRect(box, 8, 8)
        painter.setFont(_font(9, bold=True))
        painter.setPen(QPen(QColor(218, 232, 255)))
        painter.drawText(box.adjusted(12, 0, -12, 0), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), text)


class InterstellarEvidenceCrucibleApp(QWidget):
    """Programs > Simulations entry for public-data 3I/ATLAS evidence foraging."""

    DEFAULT_CLAIM = (
        "Non-gravitational acceleration anomaly requires orbit-residual refit against "
        "JPL Horizons/MPC observations and published comet outgassing parameters."
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SIFTA Interstellar Evidence Crucible")
        self.resize(1280, 840)
        self.setStyleSheet(
            f"""
            QWidget {{ background: #050914; color: {TEXT}; font-family: Menlo; }}
            QLabel#Title {{ color: #f8fbff; font-size: 23px; font-weight: 800; }}
            QLabel#Sub {{ color: {MUTED}; font-size: 11px; }}
            QFrame#Panel {{
                background: {PANEL};
                border: 1px solid rgba(118,145,185,80);
                border-radius: 10px;
            }}
            QLineEdit, QComboBox, QPlainTextEdit {{
                background: #081224;
                color: {TEXT};
                border: 1px solid #283954;
                border-radius: 7px;
                padding: 8px;
                selection-background-color: #245a77;
            }}
            QPushButton {{
                background: #16395b;
                color: #f4f9ff;
                border: 1px solid #2f7497;
                border-radius: 7px;
                padding: 8px 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: #1f5a7f; border-color: #46e8dd; }}
            QPushButton#Gold {{ background: #5b4118; border-color: #d7a753; }}
            QPushButton#Red {{ background: #5b1d2d; border-color: #dd536a; }}
            QTableWidget {{
                background: #081224;
                color: {TEXT};
                gridline-color: #20334f;
                border: 1px solid #283954;
                border-radius: 7px;
            }}
            QHeaderView::section {{
                background: #13233b;
                color: #c2d8f5;
                border: 0;
                padding: 6px;
            }}
            """
        )
        self._build_ui()
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)

        if doctor_sigil_html:
            sigil = QLabel()
            sigil.setText(doctor_sigil_html(["CG55M"], "Interstellar Evidence Crucible"))
            sigil.setFixedHeight(42)
            root.addWidget(sigil)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("SIFTA Interstellar Evidence Crucible")
        title.setObjectName("Title")
        sub = QLabel("3I/ATLAS / public ephemerides, observations, chemistry papers, claim falsifiers, STGM reward hints")
        sub.setObjectName("Sub")
        title_col.addWidget(title)
        title_col.addWidget(sub)
        header.addLayout(title_col, 1)
        self.status = QLabel("Ready")
        self.status.setObjectName("Sub")
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.status, 1)
        root.addLayout(header)

        main = QHBoxLayout()
        main.setSpacing(12)
        root.addLayout(main, 1)

        left = QVBoxLayout()
        main.addLayout(left, 3)
        self.canvas = InterstellarFieldCanvas()
        left.addWidget(self.canvas, 3)
        left.addWidget(self._controls_panel(), 1)

        right = QVBoxLayout()
        main.addLayout(right, 2)
        right.addWidget(self._metrics_panel())
        right.addWidget(self._table_panel(), 2)
        right.addWidget(self._actions_panel(), 1)

    def _controls_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        box = QVBoxLayout(panel)
        box.setContentsMargins(12, 10, 12, 12)
        top = QHBoxLayout()
        self.seed_btn = QPushButton("Seed Public Evidence")
        self.seed_btn.setObjectName("Gold")
        self.seed_btn.clicked.connect(self.seed_sources)
        top.addWidget(self.seed_btn)
        self.fetch_btn = QPushButton("Pull JPL Horizons")
        self.fetch_btn.clicked.connect(self.fetch_horizons)
        top.addWidget(self.fetch_btn)
        self.refresh_btn = QPushButton("Refresh Field")
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn)
        box.addLayout(top)

        claim_row = QHBoxLayout()
        self.lane_combo = QComboBox()
        self.lane_combo.addItems(list(CLAIM_LANES))
        self.lane_combo.setCurrentText("non_grav_acceleration")
        claim_row.addWidget(self.lane_combo, 1)
        self.claim_input = QLineEdit()
        self.claim_input.setText(self.DEFAULT_CLAIM)
        claim_row.addWidget(self.claim_input, 4)
        self.claim_btn = QPushButton("Deposit Claim")
        self.claim_btn.clicked.connect(self.deposit_claim)
        claim_row.addWidget(self.claim_btn)
        box.addLayout(claim_row)
        return panel

    def _metrics_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        box = QVBoxLayout(panel)
        box.setContentsMargins(12, 10, 12, 10)
        self.metrics = QLabel()
        self.metrics.setObjectName("Sub")
        self.metrics.setTextFormat(Qt.TextFormat.RichText)
        self.metrics.setWordWrap(True)
        box.addWidget(self.metrics)
        return panel

    def _table_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        box = QVBoxLayout(panel)
        box.setContentsMargins(12, 10, 12, 12)
        label = QLabel("Strongest evidence deposits")
        label.setObjectName("Sub")
        box.addWidget(label)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["lane", "kind", "strength", "source", "title"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        box.addWidget(self.table)
        return panel

    def _actions_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        box = QVBoxLayout(panel)
        box.setContentsMargins(12, 10, 12, 12)
        label = QLabel("Swimmer actions")
        label.setObjectName("Sub")
        box.addWidget(label)
        self.actions = QPlainTextEdit()
        self.actions.setReadOnly(True)
        self.actions.setMaximumHeight(150)
        box.addWidget(self.actions)
        return panel

    def _tick(self) -> None:
        self.canvas.tick()

    def seed_sources(self) -> None:
        rows = seed_public_evidence_deposits()
        self.status.setText(f"Seeded {len(rows)} public deposits")
        self.refresh()

    def fetch_horizons(self) -> None:
        self.status.setText("Pulling JPL Horizons...")
        QApplication.processEvents()
        row = fetch_jpl_horizons(timeout_s=10.0)
        ok = bool((row.get("payload") or {}).get("ok"))
        self.status.setText("JPL Horizons receipt OK" if ok else "JPL Horizons receipt logged with error")
        self.refresh()

    def deposit_claim(self) -> None:
        text = self.claim_input.text().strip()
        if not text:
            self.status.setText("No claim text to deposit")
            return
        row = add_claim(
            self.lane_combo.currentText(),
            text,
            title="Architect / local claim deposit",
            source_type="LOCAL_ANALYSIS",
            confidence=0.52,
            falsifier="Attach a primary source, Horizons pull, MPC observation set, or deterministic refit.",
        )
        self.status.setText(f"Claim deposited {str(row.get('receipt', ''))[:12]}")
        self.refresh()

    def refresh(self) -> None:
        snap = field_snapshot()
        self.canvas.set_snapshot(snap)
        self._render_metrics(snap)
        self._render_table(snap)
        self._render_actions(snap)

    def _render_metrics(self, snap: dict[str, Any]) -> None:
        by_lane = dict(snap.get("by_lane") or {})
        lane_bits = []
        for lane in CLAIM_LANES:
            value = float(by_lane.get(lane, 0.0) or 0.0)
            color = _lane_color(lane, min(1.0, value))
            lane_bits.append(
                f"<span style='color: rgb({color.red()},{color.green()},{color.blue()});'>"
                f"{lane}: {value:.2f}</span>"
            )
        latest = snap.get("latest_fetch") or {}
        latest_text = "none"
        if latest:
            payload = latest.get("payload") or {}
            latest_text = f"{payload.get('status')} / {str(latest.get('receipt', ''))[:12]}"
        self.metrics.setText(
            f"<b style='color:#f8fbff;'>Truth:</b> {snap.get('truth_label')}<br>"
            f"<b style='color:#f8fbff;'>Ledger:</b> {snap.get('deposit_count')} rows | "
            f"{float(snap.get('total_stgm_reward_hint', 0.0)):.2f} STGM reward hints<br>"
            f"<b style='color:#f8fbff;'>Latest JPL fetch:</b> {latest_text}<br>"
            f"<b style='color:#f8fbff;'>Field lanes:</b><br>" + "<br>".join(lane_bits)
        )

    def _render_table(self, snap: dict[str, Any]) -> None:
        rows = list(snap.get("strongest") or [])
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                str(row.get("lane", "")),
                str(row.get("kind", "")),
                f"{float(row.get('strength', 0.0) or 0.0):.3f}",
                str(row.get("source_type", "")),
                str(row.get("title", "")),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                if c == 0:
                    color = _lane_color(value, 0.9)
                    item.setForeground(QBrush(color))
                self.table.setItem(r, c, item)

    def _render_actions(self, snap: dict[str, Any]) -> None:
        lines = []
        for action in snap.get("swimmer_actions") or []:
            lines.append(
                f"{action.get('swimmer')}: {action.get('action')} "
                f"[{float(action.get('stgm_reward_hint', 0.0)):.2f} STGM]"
            )
        self.actions.setPlainText("\n".join(lines) or "No swimmer actions yet. Seed the field first.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = InterstellarEvidenceCrucibleApp()
    w.show()
    sys.exit(app.exec())
