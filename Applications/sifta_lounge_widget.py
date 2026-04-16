#!/usr/bin/env python3
"""
sifta_lounge_widget.py — The Swarm Lounge Visualization
═══════════════════════════════════════════════════════════
Watch swimmers from 6 domains sit on "the couch," pair up across
domain boundaries, and swap pheromone knowledge via gossip.

Visual:
  • Central lounge (dark oval) with domain clusters around it
  • Swimmers drift toward the center when idle
  • Gossip links glow between paired swimmers (cross-domain)
  • Insight flashes appear when novel cross-domain intuition fires
  • Telemetry: gossip count, insights discovered, STGM earned

Built on SiftaBaseWidget for consistent chrome.
"""
from __future__ import annotations

import math
import random
import time
from typing import Dict, List, Tuple

from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))

from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSplitter,
    QTextEdit, QVBoxLayout, QWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QFont, QRadialGradient, QPainterPath,
)

from sifta_base_widget import SiftaBaseWidget
from sifta_swarm_lounge import (
    DOMAINS, DomainAgent, GossipEvent, gather_agents,
    gossip_round, cosine_similarity, _get_insight,
)

# ── Domain colors ─────────────────────────────────────────────────
DOMAIN_COLORS = {
    "NETWORK":    QColor(255, 80, 120),
    "VIDEO":      QColor(255, 200, 60),
    "BROWSER":    QColor(100, 200, 255),
    "CYBORG":     QColor(180, 80, 255),
    "FINANCE":    QColor(0, 255, 128),
    "CALIBRATOR": QColor(0, 255, 200),
}


class _LoungeAgent:
    """Visual state for an agent in the lounge."""
    __slots__ = ("agent", "x", "y", "vx", "vy", "home_x", "home_y",
                 "in_lounge", "partner_id", "gossip_flash")

    def __init__(self, agent: DomainAgent, hx: float, hy: float):
        self.agent = agent
        self.home_x = hx
        self.home_y = hy
        self.x = hx + random.gauss(0, 15)
        self.y = hy + random.gauss(0, 15)
        self.vx = 0.0
        self.vy = 0.0
        self.in_lounge = False
        self.partner_id: str = ""
        self.gossip_flash: float = 0.0


class LoungeCanvas(QWidget):
    """The visual lounge — swimmers drift, pair, and gossip."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.visual_agents: List[_LoungeAgent] = []
        self.gossip_events: List[GossipEvent] = []
        self.gossip_lines: List[Tuple[str, str, float, str]] = []  # (id_a, id_b, flash, insight)
        self.insights_discovered: List[str] = []
        self.total_stgm = 0.0
        self.total_gossip = 0
        self.tick_count = 0
        self.lounge_active = False
        self.round_counter = 0

        self._agents_by_id: Dict[str, _LoungeAgent] = {}

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start_lounge(self):
        """Gather agents and begin the lounge session."""
        raw_agents = gather_agents()
        w, h = self.width() or 800, self.height() or 600
        cx, cy = w / 2, h / 2
        radius = min(w, h) * 0.38

        self.visual_agents.clear()
        self._agents_by_id.clear()
        self.gossip_lines.clear()
        self.insights_discovered.clear()
        self.total_stgm = 0.0
        self.total_gossip = 0
        self.round_counter = 0

        domain_list = list(DOMAINS.keys())
        for i, agent in enumerate(raw_agents):
            di = domain_list.index(agent.domain) if agent.domain in domain_list else 0
            angle = (di / len(domain_list)) * 2 * math.pi
            hx = cx + radius * math.cos(angle)
            hy = cy + radius * math.sin(angle)
            va = _LoungeAgent(agent, hx, hy)
            self.visual_agents.append(va)
            self._agents_by_id[agent.agent_id] = va

        self.lounge_active = True
        self._timer.start(40)

    def _tick(self):
        self.tick_count += 1
        w, h = self.width() or 800, self.height() or 600
        cx, cy = w / 2, h / 2

        # Phase 1: agents drift toward center (the couch)
        for va in self.visual_agents:
            if self.lounge_active:
                target_x = cx + random.gauss(0, 40)
                target_y = cy + random.gauss(0, 30)
                va.vx += (target_x - va.x) * 0.008
                va.vy += (target_y - va.y) * 0.008
                va.in_lounge = math.sqrt((va.x - cx)**2 + (va.y - cy)**2) < min(w, h) * 0.25
            else:
                va.vx += (va.home_x - va.x) * 0.02
                va.vy += (va.home_y - va.y) * 0.02

            va.vx += random.gauss(0, 0.15)
            va.vy += random.gauss(0, 0.15)
            va.vx *= 0.88
            va.vy *= 0.88
            va.x += va.vx
            va.y += va.vy
            va.x = max(10, min(w - 10, va.x))
            va.y = max(10, min(h - 10, va.y))

            if va.gossip_flash > 0:
                va.gossip_flash -= 0.02

        # Gossip line decay
        self.gossip_lines = [(a, b, f - 0.005, ins) for a, b, f, ins in self.gossip_lines if f > 0.01]

        # Periodic gossip round
        if self.lounge_active and self.tick_count % 60 == 0:
            self.round_counter += 1
            raw = [va.agent for va in self.visual_agents]
            events = gossip_round(raw, blend_alpha=0.2)
            self.gossip_events.extend(events)

            for ev in events:
                self.total_gossip += 1
                self.total_stgm += 0.01 * ev.similarity * 2

                va_a = self._agents_by_id.get(ev.agent_a)
                va_b = self._agents_by_id.get(ev.agent_b)
                if va_a:
                    va_a.gossip_flash = 1.0
                    va_a.partner_id = ev.agent_b
                if va_b:
                    va_b.gossip_flash = 1.0
                    va_b.partner_id = ev.agent_a

                self.gossip_lines.append((ev.agent_a, ev.agent_b, 1.0, ev.insight))

                if ev.insight and ev.insight not in self.insights_discovered:
                    self.insights_discovered.append(ev.insight)

        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        p.fillRect(0, 0, w, h, QColor(6, 8, 16))

        # The Couch (central glow)
        couch_r = min(w, h) * 0.22
        grad = QRadialGradient(cx, cy, couch_r)
        grad.setColorAt(0, QColor(30, 25, 45, 80))
        grad.setColorAt(0.7, QColor(15, 12, 25, 40))
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(50, 45, 70, 60), 1))
        p.drawEllipse(QPointF(cx, cy), couch_r, couch_r * 0.7)

        p.setPen(QPen(QColor(80, 75, 100, 40)))
        p.setFont(QFont("Menlo", 10))
        p.drawText(QRectF(cx - 60, cy - 8, 120, 20), Qt.AlignmentFlag.AlignCenter, "THE LOUNGE")

        # Domain labels around the perimeter
        domain_list = list(DOMAINS.keys())
        radius = min(w, h) * 0.42
        p.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
        for i, dom in enumerate(domain_list):
            angle = (i / len(domain_list)) * 2 * math.pi
            lx = cx + radius * math.cos(angle)
            ly = cy + radius * math.sin(angle)
            color = DOMAIN_COLORS.get(dom, QColor(150, 150, 150))
            p.setPen(QPen(color))
            p.drawText(QRectF(lx - 50, ly - 8, 100, 16), Qt.AlignmentFlag.AlignCenter, dom)

        # Gossip links
        for (aid_a, aid_b, flash, insight) in self.gossip_lines:
            va_a = self._agents_by_id.get(aid_a)
            va_b = self._agents_by_id.get(aid_b)
            if not va_a or not va_b:
                continue
            alpha = int(flash * 180)
            if insight:
                p.setPen(QPen(QColor(255, 200, 60, alpha), 2.0))
            else:
                p.setPen(QPen(QColor(0, 255, 200, alpha), 1.0))
            p.drawLine(QPointF(va_a.x, va_a.y), QPointF(va_b.x, va_b.y))

            if insight and flash > 0.7:
                mid_x = (va_a.x + va_b.x) / 2
                mid_y = (va_a.y + va_b.y) / 2
                p.setFont(QFont("Menlo", 6))
                p.setPen(QPen(QColor(255, 200, 60, alpha)))
                p.drawText(QPointF(mid_x - 30, mid_y - 4), "INSIGHT")

        # Agents
        for va in self.visual_agents:
            color = DOMAIN_COLORS.get(va.agent.domain, QColor(150, 150, 150))
            r = 4.0
            if va.gossip_flash > 0:
                r = 4.0 + va.gossip_flash * 4
                glow = QRadialGradient(va.x, va.y, r * 3)
                glow.setColorAt(0, QColor(color.red(), color.green(), color.blue(), int(va.gossip_flash * 120)))
                glow.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(QBrush(glow))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(va.x, va.y), r * 3, r * 3)

            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(va.x, va.y), r, r)

        # HUD
        p.setPen(QPen(QColor(0, 255, 200)))
        p.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
        hud = (f"Agents: {len(self.visual_agents)}  |  "
               f"Rounds: {self.round_counter}  |  "
               f"Gossip: {self.total_gossip}  |  "
               f"Insights: {len(self.insights_discovered)}  |  "
               f"STGM: {self.total_stgm:.3f}")
        p.drawText(QPointF(10, h - 8), hud)

        # Latest insight banner
        if self.insights_discovered:
            latest = self.insights_discovered[-1]
            p.setFont(QFont("Menlo", 7))
            p.setPen(QPen(QColor(255, 200, 60, 180)))
            p.drawText(QRectF(10, 12, w - 20, 14), Qt.AlignmentFlag.AlignCenter,
                       f"Latest: {latest}")

        p.end()


class LoungeWidget(SiftaBaseWidget):
    """The Swarm Lounge — visual cross-domain gossip."""

    APP_NAME = "Swarm Lounge (Cross-Domain Gossip)"

    def build_ui(self, layout: QVBoxLayout) -> None:
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        btn_start = QPushButton("Enter The Lounge")
        btn_start.clicked.connect(self._start)
        toolbar.addWidget(btn_start)

        btn_stop = QPushButton("Awaken (Return to Domains)")
        btn_stop.clicked.connect(self._awaken)
        toolbar.addWidget(btn_stop)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._pane_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.canvas = LoungeCanvas()
        self._pane_splitter.addWidget(self.canvas)

        self.insight_log = QTextEdit()
        self.insight_log.setReadOnly(True)
        self.insight_log.setMaximumWidth(320)
        self.insight_log.setMinimumWidth(240)
        self.insight_log.setStyleSheet(
            "QTextEdit { background: rgb(10,8,16); color: rgb(255,200,60); "
            "font-family: 'Menlo'; font-size: 9px; padding: 6px; }")
        self._pane_splitter.addWidget(self.insight_log)
        self._pane_splitter.setStretchFactor(0, 3)
        self._pane_splitter.setStretchFactor(1, 1)
        layout.addWidget(self._pane_splitter, 1)
        QTimer.singleShot(0, self._balance_pane_splitter)

        self._refresh = self.make_timer(1000, self._refresh_log)

    def _balance_pane_splitter(self) -> None:
        from System.splitter_utils import balance_horizontal_splitter

        balance_horizontal_splitter(
            self._pane_splitter,
            self,
            left_ratio=0.72,
            min_right=240,
            min_left=200,
            max_right=320,
        )

    def _start(self):
        self.canvas.start_lounge()
        self.set_status("Lounge active — swimmers gathering on the couch...")

    def _awaken(self):
        self.canvas.lounge_active = False
        self.set_status("Awakening — agents returning to home domains with blended params")

    def _refresh_log(self):
        if not self.canvas.insights_discovered and not self.canvas.gossip_events:
            return
        lines = [f"GOSSIP ROUNDS: {self.canvas.round_counter}",
                 f"TOTAL TRANSFERS: {self.canvas.total_gossip}",
                 f"STGM EARNED: {self.canvas.total_stgm:.4f}",
                 f"INSIGHTS: {len(self.canvas.insights_discovered)}",
                 ""]
        for ins in self.canvas.insights_discovered:
            lines.append(f"  {ins}")
            lines.append("")

        if self.canvas.gossip_events:
            lines.append("--- RECENT GOSSIP ---")
            for ev in self.canvas.gossip_events[-15:]:
                lines.append(f"{ev.domain_a}/{ev.agent_a} <-> {ev.domain_b}/{ev.agent_b}")
                lines.append(f"  sim={ev.similarity:.3f} type={ev.transfer_type}")
                if ev.insight:
                    lines.append(f"  >> {ev.insight}")
                lines.append("")

        self.insight_log.setPlainText("\n".join(lines))
        sb = self.insight_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def closeEvent(self, event):
        self.canvas._timer.stop()
        super().closeEvent(event)
