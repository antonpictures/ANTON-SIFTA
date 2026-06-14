#!/usr/bin/env python3
"""
Applications/sifta_resa_substation_sim.py
=========================================

RESA Power — SS-SA Unit Substation Simulator

Animated mechanical elevation, single-line diagram, and three-line diagram
for the RESA POWER order (Unit Substation SS-SA). Lives under Simulations.

Truth label: SIMULATION — presentation graphics, not PE-stamped drawings.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QBrush
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from System.sifta_base_widget import SiftaBaseWidget
from Simulations.resa_ss_sa_substation import default_order, proof_of_property

_STYLE = """
QWidget { background: #0a0e14; color: #d8e2f0; font-family: Menlo, monospace; font-size: 12px; }
QTabWidget::pane { border: 1px solid #1e3a5f; border-radius: 6px; }
QTabBar::tab { background: #111a28; color: #7fa8d4; padding: 8px 16px; margin-right: 3px; border-top-left-radius: 5px; border-top-right-radius: 5px; }
QTabBar::tab:selected { background: #0a0e14; color: #5eead4; font-weight: bold; }
QPushButton { background: #111a28; color: #5eead4; border: 1px solid #2d6a9f; border-radius: 5px; padding: 6px 14px; }
QPushButton:hover { border-color: #5eead4; }
QTableWidget { background: #0a0e14; gridline-color: #1e3a5f; }
QHeaderView::section { background: #111a28; color: #5eead4; padding: 4px; }
"""


class _FlowMixin:
    """Shared energize + particle flow state for diagram canvases."""

    def __init_flow(self) -> None:
        self._energized = False
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(40)

    def set_energized(self, on: bool) -> None:
        self._energized = on
        self.update()

    def _advance(self) -> None:
        self._phase = (self._phase + 0.018) % 1.0
        if self._energized:
            self.update()


class _MechanicalCanvas(QWidget, _FlowMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(360)
        self.__init_flow__()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor("#0f1724"))
        grad.setColorAt(1, QColor("#060a10"))
        p.fillRect(0, 0, w, h, grad)

        order = default_order()
        sections = order.sections + tuple(
            {"id": d["id"], "name": d["name"], "mechanical": [f"{sum(b['count'] for b in d['breakers'])} breakers"]}
            for d in order.distribution_sections
        )
        n = len(sections)
        pad = 24
        slot_w = (w - pad * 2) / n
        y0, bh = 80, h - 140

        for i, sec in enumerate(sections):
            x = pad + i * slot_w + 8
            sw = slot_w - 16
            pulse = 0.55 + 0.45 * math.sin(self._phase * 2 * math.pi + i * 0.7) if self._energized else 0.35
            fill = QColor(30, 80, 120, int(180 * pulse))
            p.setPen(QPen(QColor("#5eead4"), 2))
            p.setBrush(QBrush(fill))
            p.drawRoundedRect(QRectF(x, y0, sw, bh), 8, 8)
            p.setPen(QColor("#e2f4ff"))
            p.setFont(QFont("Menlo", 9, QFont.Weight.Bold))
            p.drawText(QRectF(x, y0 + 8, sw, 24), Qt.AlignmentFlag.AlignCenter, sec["id"])
            p.setFont(QFont("Menlo", 8))
            lines = sec.get("mechanical", [])[:3]
            for li, line in enumerate(lines):
                p.drawText(QRectF(x + 6, y0 + 34 + li * 16, sw - 12, 16), Qt.AlignmentFlag.AlignLeft, line[:42])

        if self._energized:
            p.setPen(QPen(QColor("#fbbf24"), 3))
            for i in range(n - 1):
                x1 = pad + (i + 1) * slot_w
                y = y0 + bh / 2
                t = (self._phase + i * 0.15) % 1.0
                px = pad + i * slot_w + slot_w * 0.85 + (slot_w * 0.3) * t
                p.drawLine(int(x1 - slot_w * 0.15), int(y), int(x1), int(y))
                p.setBrush(QBrush(QColor("#fbbf24")))
                p.drawEllipse(QPointF(px, y), 5, 5)

        p.setPen(QColor("#7fa8d4"))
        p.setFont(QFont("Menlo", 10))
        p.drawText(12, h - 18, "Front elevation — SS-SA lineup (SIMULATION)")


class _SingleLineCanvas(QWidget, _FlowMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(400)
        self.__init_flow__()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#060a10"))

        cx, cy = w * 0.5, h * 0.42
        pen_on = QPen(QColor("#5eead4"), 3)
        pen_off = QPen(QColor("#334155"), 2, Qt.PenStyle.DashLine)
        p.setFont(QFont("Menlo", 9))

        nodes = [
            ("Utility 12.47 kV", cx - w * 0.38, cy - 60),
            ("LI Switch 600A", cx - w * 0.18, cy - 60),
            ("2500 kVA XFMR", cx, cy - 60),
            ("Main 4000A 65kAIC", cx + w * 0.2, cy - 60),
            ("Dist S4+S5", cx + w * 0.38, cy - 60),
        ]

        for i, (label, x, y) in enumerate(nodes):
            on = self._energized or i == 0
            p.setPen(pen_on if on else pen_off)
            p.setBrush(QBrush(QColor(20, 60, 90) if on else QColor(20, 28, 38)))
            p.drawEllipse(QPointF(x, y), 28, 28)
            p.setPen(QColor("#cbd5e1"))
            p.drawText(QRectF(x - 60, y + 34, 120, 20), Qt.AlignmentFlag.AlignCenter, label)

        for i in range(len(nodes) - 1):
            x1, y1 = nodes[i][1], nodes[i][2]
            x2, y2 = nodes[i + 1][1], nodes[i + 1][2]
            on = self._energized
            p.setPen(pen_on if on else pen_off)
            p.drawLine(int(x1 + 30), int(y1), int(x2 - 30), int(y2))
            if on:
                t = (self._phase + i * 0.2) % 1.0
                px = x1 + 30 + (x2 - x1 - 60) * t
                p.setBrush(QBrush(QColor("#fbbf24")))
                p.drawEllipse(QPointF(px, y1), 6, 6)

        p.setPen(QColor("#94a3b8"))
        p.drawText(12, h - 16, "Single-line diagram — 12.47 kV → 480Y/277 V (SIMULATION)")


class _ThreeLineCanvas(QWidget, _FlowMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(420)
        self.__init_flow__()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#060a10"))

        phases = [
            ("L1", QColor("#ef4444")),
            ("L2", QColor("#facc15")),
            ("L3", QColor("#3b82f6")),
        ]
        x0 = w * 0.12
        bus_y = h * 0.25
        bus_len = w * 0.76

        for pi, (name, col) in enumerate(phases):
            y = bus_y + pi * 90
            on = self._energized
            p.setPen(QPen(col if on else QColor("#475569"), 3))
            p.drawLine(int(x0), int(y), int(x0 + bus_len), int(y))
            p.setPen(col if on else QColor("#64748b"))
            p.drawText(int(x0 - 36), int(y + 5), name)

            order = default_order()
            breakers = order.breaker_inventory
            step = bus_len / (sum(b.count for b in breakers) + 1)
            idx = 0
            for spec in breakers:
                for _ in range(spec.count):
                    idx += 1
                    bx = x0 + step * idx
                    p.setPen(QPen(col if on else QColor("#334155"), 2))
                    p.drawLine(int(bx), int(y), int(bx), int(y + 50))
                    p.drawRect(QRectF(bx - 10, y + 50, 20, 14))
                    if on:
                        wave = math.sin(self._phase * 2 * math.pi + pi + idx * 0.4)
                        p.setBrush(QBrush(col))
                        p.drawEllipse(QPointF(bx, y + 57 + wave * 4), 3, 3)
                    if pi == 0 and idx <= 12:
                        p.setPen(QColor("#94a3b8"))
                        p.setFont(QFont("Menlo", 7))
                        p.drawText(QRectF(bx - 18, y + 68, 36, 12), Qt.AlignmentFlag.AlignCenter, f"{spec.amps}A")

        p.setPen(QColor("#94a3b8"))
        p.setFont(QFont("Menlo", 10))
        p.drawText(12, h - 16, f"Three-line — {order.total_breakers} bolt-on LI breakers @ 480V 65kAIC (SIMULATION)")


class ResaSubstationSimWidget(SiftaBaseWidget):
    APP_NAME = "RESA SS-SA Substation Simulator"

    def build_ui(self, layout: QVBoxLayout) -> None:
        self.setStyleSheet(_STYLE)
        order = default_order()

        header = QLabel(
            f"<span style='color:#5eead4;font-size:16px;font-weight:bold;'>⚡ {order.vendor} — Unit Substation {order.order_id}</span><br/>"
            f"<span style='color:#7fa8d4;'>2500 kVA · 12.47 kV → 480Y/277 V · {order.total_breakers} distribution breakers · Ship 2026-09-28</span>"
        )
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        ctrl = QHBoxLayout()
        self._energize_btn = QPushButton("▶ Energize Bus")
        self._energize_btn.clicked.connect(self._toggle_energize)
        ctrl.addWidget(self._energize_btn)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._tabs = QTabWidget()
        self._mech = _MechanicalCanvas()
        self._sld = _SingleLineCanvas()
        self._tld = _ThreeLineCanvas()
        self._tabs.addTab(self._wrap(self._mech), "Mechanical")
        self._tabs.addTab(self._wrap(self._sld), "Single-Line")
        self._tabs.addTab(self._wrap(self._tld), "Three-Line")
        self._tabs.addTab(self._build_bom_tab(order), "Order / BOM")
        layout.addWidget(self._tabs, 1)

        self._status.setText("SIMULATION — presentation graphics only")

    def _wrap(self, canvas: QWidget) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(8, 8, 8, 8)
        v.addWidget(canvas)
        return page

    def _toggle_energize(self) -> None:
        on = self._energize_btn.text().startswith("▶")
        self._energize_btn.setText("■ De-Energize" if on else "▶ Energize Bus")
        for c in (self._mech, self._sld, self._tld):
            c.set_energized(on)
        self._status.setText("ENERGIZED — animated flow (SIMULATION)" if on else "De-energized")

    def _build_bom_tab(self, order) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(("Section", "Item", "Qty", "Spec"))
        rows: list[tuple[str, str, str, str]] = []
        for sec in order.sections:
            rows.append((sec["id"], sec["name"], "1", sec["electrical"][0] if sec["electrical"] else ""))
        for dist in order.distribution_sections:
            for br in dist["breakers"]:
                rows.append((dist["id"], "LI Breaker", str(br["count"]), f"{br['trip_label']} 3P 65k@480V"))
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(val))
        table.resizeColumnsToContents()
        v.addWidget(table)
        note = QLabel(
            f"<span style='color:#64748b;'>Warranty: {order.misc['warranty']} · "
            f"Drawings: {order.lead_time['drawings']} · Shipping: {order.lead_time['shipping']}</span>"
        )
        note.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(note)
        return page


def main() -> None:
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    win = ResaSubstationSimWidget()
    win.resize(1280, 860)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()