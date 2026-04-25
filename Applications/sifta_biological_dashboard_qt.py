#!/usr/bin/env python3
"""
Qt-only biological dashboard for SIFTA OS MDI.

``BiologicalDashboardWidget`` is the manifest entry — importing this module
must not load Tkinter / ``_tkinter``.
"""

from __future__ import annotations

import math
import random

from Applications.sifta_biological_core import hud_body, read_biology_tension

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class BiologicalDashboardWidget(QWidget):
    """Same physics/HUD as Tk visualizer, rendered inside MDI (Foundry or Sentry)."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(800, 520)
        self.setStyleSheet("background-color: #050508;")
        self._particles: list[dict] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._n = 60
        self._reset_particles_for_size(1200, 800)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() > 2 and self.height() > 2:
            self._reset_particles_for_size(float(self.width()), float(self.height()))

    def _reset_particles_for_size(self, w: float, h: float):
        w = max(w, 400.0)
        h = max(h, 300.0)
        self._particles = [
            {
                "x": random.uniform(0, w),
                "y": random.uniform(0, h),
                "vx": random.uniform(-2, 2),
                "vy": random.uniform(-2, 2),
            }
            for _ in range(self._n)
        ]

    def _step_physics(self, w: float, h: float, tension: float) -> None:
        for p in self._particles:
            p["vx"] += random.uniform(-tension, tension)
            p["vy"] += random.uniform(-tension, tension)
            p["vx"] *= 0.96
            p["vy"] *= 0.96
            speed = math.hypot(p["vx"], p["vy"])
            if speed > 0:
                p["vx"] = (p["vx"] / speed) * 3
                p["vy"] = (p["vy"] / speed) * 3
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if p["x"] < 0:
                p["x"] = w
            if p["x"] > w:
                p["x"] = 0
            if p["y"] < 0:
                p["y"] = h
            if p["y"] > h:
                p["y"] = 0

    def _tick(self):
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._timer.isActive():
            self._timer.start(60)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        w = max(float(self.width()), 400.0)
        h = max(float(self.height()), 300.0)
        if not self._particles:
            self._reset_particles_for_size(w, h)
        tension = read_biology_tension()
        self._step_physics(w, h, tension)

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#050508"))

        plist = self._particles
        for i, p1 in enumerate(plist):
            connections = 0
            for p2 in plist[i + 1 :]:
                dist = math.hypot(p1["x"] - p2["x"], p1["y"] - p2["y"])
                if dist < 60:
                    connections += 1
                    col = QColor("#ff0055" if connections > 2 else "#33ccff")
                    painter.setPen(QPen(col, 1))
                    painter.drawLine(QPointF(p1["x"], p1["y"]), QPointF(p2["x"], p2["y"]))

        painter.setPen(QPen(QColor("#00ffcc"), 1))
        for p in plist:
            painter.setBrush(QColor("#00ffcc"))
            painter.drawEllipse(QPointF(p["x"], p["y"]), 3, 3)

        painter.setPen(QColor("#ff0055"))
        painter.setFont(QFont("Courier", 14, QFont.Weight.Bold))
        painter.drawText(
            24,
            28,
            max(1, int(w - 48)),
            max(1, int(h - 28)),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            hud_body(len(plist), tension),
        )
