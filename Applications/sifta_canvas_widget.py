#!/usr/bin/env python3
"""
sifta_canvas_widget.py — Stigmergic Swarm Canvas
══════════════════════════════════════════════════
You don't paint pixels. You deploy a biological ecosystem on blank territory.

The cursor is a pheromone emitter. PigmentForagers swarm from the edges,
carry wet pigment, and die on contact — staining the canvas with organic
textured strokes. Colors blend stigmergically on collision.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel,
    QPushButton, QSlider, QVBoxLayout,
)
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QImage, QPainter, QColor, QMouseEvent, QPen

from System.sifta_base_widget import SiftaBaseWidget
from System.stigmergic_canvas import CanvasEngine


COLORS = {
    "Cyan":       (0,   255, 220),
    "Magenta":    (255, 40,  200),
    "Yellow":     (255, 230, 0),
    "Neon Green": (40,  255, 80),
    "White":      (240, 240, 255),
    "Amber":      (255, 180, 30),
}

CANVAS_W = 720
CANVAS_H = 500


class SwarmCanvas(QLabel):
    """Custom QLabel that renders the pixel buffer and forager dots."""

    def __init__(self, engine: CanvasEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setFixedSize(CANVAS_W, CANVAS_H)
        self.setMouseTracking(True)
        self._painting = False
        self._current_color = COLORS["Cyan"]

    def set_color(self, rgb):
        self._current_color = rgb

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._painting = True
            self._emit(ev.position())

    def mouseMoveEvent(self, ev: QMouseEvent):
        if self._painting:
            self._emit(ev.position())

    def mouseReleaseEvent(self, ev: QMouseEvent):
        self._painting = False

    def _emit(self, pos: QPointF):
        x, y = pos.x(), pos.y()
        if 0 <= x < CANVAS_W and 0 <= y < CANVAS_H:
            r, g, b = self._current_color
            self.engine.add_trace(x, y, r, g, b)

    def render_frame(self):
        img = QImage(CANVAS_W, CANVAS_H, QImage.Format.Format_ARGB32)
        img.fill(QColor(8, 10, 18))

        pixels = self.engine.pixels
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Render deposited paint from pixel buffer (batch by non-empty rows)
        for y in range(self.engine.height):
            row = pixels[y]
            mask = row[:, 3] > 0.05
            if not mask.any():
                continue
            xs = np.where(mask)[0]
            for x in xs:
                r, g, b, a = row[x]
                painter.setPen(QPen(QColor(int(r), int(g), int(b), int(min(a, 1.0) * 255))))
                painter.drawPoint(x, y)

        # Render pheromone traces (faint glow)
        for t in self.engine.traces:
            alpha = int(max(20, min(120, t.strength * 120)))
            painter.setPen(QPen(QColor(t.r, t.g, t.b, alpha)))
            painter.drawRect(int(t.x) - 1, int(t.y) - 1, 3, 3)

        # Render live foragers as tiny bright dots
        for f in self.engine.foragers:
            if not f.alive or f.deposited:
                continue
            painter.setPen(QPen(QColor(f.r, f.g, f.b, 200)))
            painter.drawPoint(int(f.x), int(f.y))

        painter.end()
        self.setPixmap(img.toPixmap() if hasattr(img, 'toPixmap') else _qimage_to_pixmap(img))


def _qimage_to_pixmap(img: QImage):
    from PyQt6.QtGui import QPixmap
    return QPixmap.fromImage(img)


class CanvasWidget(SiftaBaseWidget):
    """Stigmergic Swarm Canvas — biological paintbrush for iSwarm OS."""

    APP_NAME = "Stigmergic Swarm Canvas"

    def build_ui(self, layout: QVBoxLayout) -> None:
        self.engine = CanvasEngine(CANVAS_W, CANVAS_H)
        self.canvas = SwarmCanvas(self.engine, self)

        # Controls row
        ctrl = QHBoxLayout()

        lbl_col = QLabel("Pigment:")
        lbl_col.setStyleSheet("font-size:11px;")
        ctrl.addWidget(lbl_col)

        self.cmb_color = QComboBox()
        self.cmb_color.addItems(COLORS.keys())
        self.cmb_color.currentTextChanged.connect(self._color_changed)
        ctrl.addWidget(self.cmb_color)

        ctrl.addWidget(self.separator())

        lbl_dens = QLabel("Swarm Density:")
        lbl_dens.setStyleSheet("font-size:11px;")
        ctrl.addWidget(lbl_dens)

        self.sld_density = QSlider(Qt.Orientation.Horizontal)
        self.sld_density.setRange(20, 400)
        self.sld_density.setValue(120)
        self.sld_density.valueChanged.connect(self._density_changed)
        self.sld_density.setFixedWidth(120)
        ctrl.addWidget(self.sld_density)

        ctrl.addWidget(self.separator())

        lbl_evap = QLabel("Evaporation:")
        lbl_evap.setStyleSheet("font-size:11px;")
        ctrl.addWidget(lbl_evap)

        self.sld_evap = QSlider(Qt.Orientation.Horizontal)
        self.sld_evap.setRange(1, 50)
        self.sld_evap.setValue(2)
        self.sld_evap.valueChanged.connect(self._evap_changed)
        self.sld_evap.setFixedWidth(100)
        ctrl.addWidget(self.sld_evap)

        ctrl.addWidget(self.separator())

        btn_clear = QPushButton("Clear Territory")
        btn_clear.clicked.connect(self._clear)
        ctrl.addWidget(btn_clear)

        ctrl.addStretch()

        # Telemetry
        self.lbl_telem = QLabel("Foragers: 0 | Deposited: 0 | Pheromone: 0.0")
        self.lbl_telem.setStyleSheet("font-size:10px; color:rgb(0,255,200);")
        ctrl.addWidget(self.lbl_telem)

        layout.addLayout(ctrl)
        layout.addWidget(self.canvas, 1)

        # Tick timer ~30fps
        self._timer = self.make_timer(33, self._tick)

    def _color_changed(self, name: str):
        self.canvas.set_color(COLORS.get(name, (0, 255, 220)))

    def _density_changed(self, val: int):
        self.engine.swarm_density = val

    def _evap_changed(self, val: int):
        self.engine.evaporation_rate = val / 100.0

    def _clear(self):
        self.engine.clear()

    def _tick(self):
        self.engine.step()
        self.canvas.render_frame()
        fc = self.engine.active_forager_count()
        dep = self.engine.total_deposited
        ph = self.engine.pheromone_density()
        self.lbl_telem.setText(f"Foragers: {fc} | Deposited: {dep} | Pheromone: {ph:.1f}")
        self.set_status(f"tick {self.engine.tick}")


# ── Standalone test ─────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = CanvasWidget()
    w.resize(780, 620)
    w.setWindowTitle("Stigmergic Swarm Canvas — SIFTA OS")
    w.show()
    sys.exit(app.exec())
