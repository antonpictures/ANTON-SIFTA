#!/usr/bin/env python3
"""
sifta_intelligence_panels.py
High-end, Steve Jobs-level graphical panels for SIFTA Swarm Intelligence.
Uses custom QPainter rendering, smooth colors, and fetches real live data.
"""
import os
import sys
import json
import math
import time
import random
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QRadialGradient, QLinearGradient, QPainterPath

_REPO = Path(__file__).resolve().parent.parent
_SYS = _REPO / "System"
if str(_SYS) not in sys.path:
    sys.path.insert(0, str(_SYS))

# Dynamic imports applied at runtime where data is needed.
# This prevents crashes if underlying systems flux.

# ── Color Palette (Sleek Apple / Cyberpunk Dark Mode) ─────────
C_BG_DEEP     = QColor(10, 12, 16)
C_BG_PANEL    = QColor(20, 24, 32)
C_TEXT_MAIN   = QColor(220, 225, 235)
C_TEXT_DIM    = QColor(100, 110, 130)
C_ACCENT_BLU  = QColor(0, 180, 255)
C_ACCENT_GRN  = QColor(0, 255, 150)
C_ACCENT_RED  = QColor(255, 60, 100)
C_ACCENT_PUR  = QColor(180, 80, 255)
C_ACCENT_YLW  = QColor(255, 200, 50)


# ═══════════════════════════════════════════════════════════════════
# 1. APP FITNESS PANEL (Visual Bar Charts)
# ═══════════════════════════════════════════════════════════════════
class AppFitnessPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {C_BG_DEEP.name()};")
        self.scores = {}
        self.max_score = 1.0
        self.min_score = -1.0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(2000)
        self.update_data()

    def update_data(self):
        try:
            from app_fitness import get_scores
            self.scores = get_scores() or {}
            vals = list(self.scores.values())
            if vals:
                self.max_score = max(5.0, max(vals))
                self.min_score = min(-5.0, min(vals))
            self.update()
        except Exception:
            pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, C_BG_DEEP)

        if not self.scores:
            p.setPen(C_TEXT_DIM)
            p.setFont(QFont("SF Pro Display", 14))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No fitness data yet. Launch apps to map.")
            return

        sorted_apps = sorted(self.scores.items(), key=lambda x: -x[1])
        row_h = 35
        start_y = 60
        left_pad = 180
        bar_max_w = w - left_pad - 60
        zero_x = left_pad + (bar_max_w * (abs(self.min_score) / (self.max_score - self.min_score)))

        # Draw Title
        p.setFont(QFont("SF Pro Display", 18, QFont.Weight.Bold))
        p.setPen(C_TEXT_MAIN)
        p.drawText(20, 35, "App Fitness Landscape")

        # Zero Line
        p.setPen(QPen(C_TEXT_DIM, 1, Qt.PenStyle.DashLine))
        p.drawLine(int(zero_x), start_y, int(zero_x), h - 20)

        p.setFont(QFont("SF Pro Text", 10))
        for i, (name, score) in enumerate(sorted_apps):
            y = start_y + (i * row_h)
            if y > h - 20:
                break
            
            # Name
            cleaned_name = name.replace(".py", "").replace("sifta_", "").replace("_", " ").title()
            p.setPen(C_TEXT_MAIN)
            p.drawText(QRectF(10, y, left_pad - 20, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, cleaned_name)

            # Bar
            bar_w = abs(score) / (self.max_score - self.min_score) * bar_max_w
            
            p.setPen(Qt.PenStyle.NoPen)
            if score >= 0:
                grad = QLinearGradient(zero_x, 0, zero_x + bar_w, 0)
                grad.setColorAt(0, QColor(0, 150, 100, 150))
                grad.setColorAt(1, C_ACCENT_GRN)
                p.setBrush(grad)
                p.drawRoundedRect(QRectF(zero_x, y + 8, bar_w, 18), 4, 4)
            else:
                grad = QLinearGradient(zero_x - bar_w, 0, zero_x, 0)
                grad.setColorAt(0, C_ACCENT_RED)
                grad.setColorAt(1, QColor(150, 0, 40, 150))
                p.setBrush(grad)
                p.drawRoundedRect(QRectF(zero_x - bar_w, y + 8, bar_w, 18), 4, 4)

            # Score text
            p.setPen(C_TEXT_DIM if score < 0 else C_TEXT_MAIN)
            tx = zero_x + bar_w + 10 if score >= 0 else zero_x - bar_w - 45
            p.drawText(QRectF(tx, y, 40, row_h), Qt.AlignmentFlag.AlignVCenter, f"{score:+.1f}")


# ═══════════════════════════════════════════════════════════════════
# 2. QUORUM SENSE PANEL (Glowing Action Bars)
# ═══════════════════════════════════════════════════════════════════
class QuorumSensePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {C_BG_DEEP.name()};")
        self.proposals = []
        self.t = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)

    def tick(self):
        self.t += 0.05
        if int(self.t*20) % 40 == 0:  # Update data every 2s
            try:
                from quorum_sense import active_proposals
                self.proposals = active_proposals() or []
            except Exception:
                pass
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, C_BG_DEEP)

        p.setFont(QFont("SF Pro Display", 18, QFont.Weight.Bold))
        p.setPen(C_ACCENT_YLW)
        p.drawText(20, 35, "Quorum Proposals")
        
        if not self.proposals:
            p.setPen(C_TEXT_DIM)
            p.setFont(QFont("SF Pro Display", 14))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "The Swarm is at peace.\nNo active consensus proposals.")
            # Gentle pulsing circle in center
            r = 50 + math.sin(self.t) * 10
            p.setPen(QPen(QColor(255, 200, 50, 50), 2))
            p.setBrush(Qt.PenStyle.NoBrush)
            p.drawEllipse(QPointF(w/2, h/2), r, r)
            return

        y = 70
        for prop in self.proposals:
            c_w = w - 40
            c_h = 70
            
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(C_BG_PANEL)
            p.drawRoundedRect(20, y, c_w, c_h, 8, 8)

            action = prop.get('action_id', '???')
            ptype = prop.get('type', 'SYSTEM')
            votes = prop.get('votes', 0)
            needed = prop.get('needed', 1)
            age = prop.get('age_sec', 0)
            
            p.setFont(QFont("SF Pro Text", 12, QFont.Weight.Bold))
            p.setPen(C_TEXT_MAIN)
            p.drawText(35, y + 25, f"[{ptype}] {action}")

            p.setFont(QFont("SF Pro Text", 10))
            p.setPen(C_TEXT_DIM)
            p.drawText(35, y + 45, f"Age: {int(age)}s | Nodes Signed: {votes}/{needed}")

            # Neon progress bar
            pb_x = 35 + 250
            pb_w = c_w - pb_x - 20
            ratio = min(1.0, votes / needed)
            
            p.setBrush(QColor(10, 10, 15))
            p.drawRoundedRect(QRectF(pb_x, y + 30, pb_w, 10), 5, 5)

            if ratio > 0:
                grad = QLinearGradient(pb_x, 0, pb_x + pb_w * ratio, 0)
                grad.setColorAt(0, QColor(255, 100, 0))
                grad.setColorAt(1, C_ACCENT_YLW)
                p.setBrush(grad)
                # Pulsing width slightly
                pulse_w = pb_w * ratio + (math.sin(self.t*5)*2 if ratio < 1 else 0)
                p.drawRoundedRect(QRectF(pb_x, y + 30, pulse_w, 10), 5, 5)

            y += c_h + 15


# ═══════════════════════════════════════════════════════════════════
# 3. IMMUNE SYSTEM (Radar / Density Bars)
# ═══════════════════════════════════════════════════════════════════
class ImmuneSystemPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {C_BG_DEEP.name()};")
        self.data = {}
        self.t = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)

    def tick(self):
        self.t += 0.05
        if int(self.t*20) % 50 == 0:
            try:
                from immune_memory import immune_status
                self.data = immune_status() or {}
            except Exception:
                pass
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, C_BG_DEEP)

        p.setFont(QFont("SF Pro Display", 18, QFont.Weight.Bold))
        p.setPen(C_ACCENT_RED)
        p.drawText(20, 35, "Immune Memory Antibodies")

        if not self.data:
            p.setPen(C_TEXT_DIM)
            p.setFont(QFont("SF Pro Display", 14))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No immune memory detected.")
            return

        total_ab = self.data.get('total_antibodies', 0)
        matches = self.data.get('total_matches', 0)
        types = self.data.get('types', {})

        # Big Stat boxes
        self._draw_stat_box(p, 20, 60, w//2 - 30, 80, "Antibodies", str(total_ab), C_ACCENT_BLU)
        self._draw_stat_box(p, w//2 + 10, 60, w//2 - 30, 80, "Total Recognitions", str(matches), C_ACCENT_RED)

        # Ring chart for types
        if types:
            cx, cy = w/2, h/2 + 60
            radius = min(w, h)/4
            start_angle = self.t * 10
            
            colors = [C_ACCENT_RED, C_ACCENT_PUR, C_ACCENT_BLU, C_ACCENT_YLW, C_ACCENT_GRN]
            total_t = sum(types.values())
            
            for i, (k, v) in enumerate(types.items()):
                span = (v / total_t) * 360 * 16
                p.setPen(QPen(colors[i % len(colors)], 15, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawArc(int(cx - radius), int(cy - radius), int(radius*2), int(radius*2), int(start_angle*16), int(span))
                
                # Legend
                p.setPen(colors[i % len(colors)])
                p.setFont(QFont("SF Pro Text", 11, QFont.Weight.Bold))
                p.drawText(int(cx + radius + 30), int(cy - radius + i*25), f"{k}: {v}")
                
                start_angle += span/16

            # Center pulse
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C_ACCENT_RED.red(), C_ACCENT_RED.green(), C_ACCENT_RED.blue(), 20))
            pr = 20 + math.sin(self.t*4)*5
            p.drawEllipse(QPointF(cx, cy), pr, pr)

    def _draw_stat_box(self, p, x, y, w, h, title, val, color):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(C_BG_PANEL)
        p.drawRoundedRect(x, y, w, h, 8, 8)
        p.setPen(C_TEXT_DIM)
        p.setFont(QFont("SF Pro Text", 10))
        p.drawText(int(x + 15), int(y + 25), title)
        p.setPen(color)
        p.setFont(QFont("SF Pro Display", 28, QFont.Weight.Bold))
        p.drawText(QRectF(x + 15, y + 30, w - 30, 40), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val)


# ═══════════════════════════════════════════════════════════════════
# 4. DREAM REPORT (Sleek KPI Dashboard)
# ═══════════════════════════════════════════════════════════════════
class DreamReportPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {C_BG_DEEP.name()};")
        self.meta = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load)
        self.timer.start(5000)
        self.load()

    def load(self):
        meta_path = _REPO / ".sifta_state" / "dream_meta.json"
        if meta_path.exists():
            try:
                self.meta = json.loads(meta_path.read_text())
                self.update()
            except Exception:
                pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, C_BG_DEEP)

        p.setFont(QFont("SF Pro Display", 18, QFont.Weight.Bold))
        p.setPen(C_ACCENT_PUR)
        p.drawText(20, 35, "Nightly Dream Report (Memory Consolidation)")

        if not self.meta:
            p.setPen(C_TEXT_DIM)
            p.setFont(QFont("SF Pro Display", 14))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No dream data recorded.")
            return

        last_ts = self.meta.get('last_dream', 'Unknown')
        p.setFont(QFont("SF Pro Text", 10))
        p.setPen(C_TEXT_DIM)
        p.drawText(20, 55, f"Last cycle: {last_ts}")

        analyses = self.meta.get('analyses', {})
        dd = analyses.get('dead_drop', {})
        eco = analyses.get('economy', {})
        rep = analyses.get('repairs', {})

        grid_y = 80
        col1 = 20
        col2 = w/2 + 10
        card_w = w/2 - 30
        card_h = 100

        # DEAD DROP
        self._draw_card(p, col1, grid_y, card_w, card_h, "Dead Drop Chat", 
                        f"{dd.get('total_messages',0)} Msgs | {dd.get('unique_senders',0)} Senders\n{dd.get('error_mentions',0)} Errors", 
                        C_ACCENT_BLU if dd.get('error_mentions',0) < 5 else C_ACCENT_RED)
        
        # ECONOMY
        self._draw_card(p, col2, grid_y, card_w, card_h, "STGM Economy", 
                        f"{eco.get('mints_today',0)} Mints\n{eco.get('total_stgm_minted',0)} STGM Minted", 
                        C_ACCENT_GRN if not eco.get('inflation_alert') else C_ACCENT_RED)
        
        # REPAIRS
        self._draw_card(p, col1, grid_y + card_h + 15, card_w, card_h, "Repairs / Interventions", 
                        f"{rep.get('repairs_today',0)} auto-interventions", 
                        C_ACCENT_YLW if rep.get('repairs_today',0) > 0 else C_TEXT_DIM)

        # EVAPORATED (Immune)
        imm = analyses.get('immune_evaporated', 0)
        self._draw_card(p, col2, grid_y + card_h + 15, card_w, card_h, "Immune Evaporation", 
                        f"{imm} stale antibodies removed", 
                        C_ACCENT_PUR)

    def _draw_card(self, p, x, y, w, h, title, text, accent):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(C_BG_PANEL)
        p.drawRoundedRect(int(x), int(y), int(w), int(h), 8, 8)
        
        p.setBrush(accent)
        p.drawRoundedRect(int(x), int(y), 6, int(h), 4, 4)

        p.setPen(C_TEXT_MAIN)
        p.setFont(QFont("SF Pro Display", 12, QFont.Weight.Bold))
        p.drawText(QRectF(x + 15, y + 10, w - 20, 20), Qt.AlignmentFlag.AlignLeft, title)
        
        p.setPen(C_TEXT_DIM)
        p.setFont(QFont("SF Pro Text", 11))
        p.drawText(QRectF(x + 15, y + 40, w - 20, h - 40), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.TextWordWrap, text)


# ═══════════════════════════════════════════════════════════════════
# 5. NERVE CHANNEL (UDP Matrix Particle Flow)
# ═══════════════════════════════════════════════════════════════════
class NerveChannelPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {C_BG_DEEP.name()};")
        self.t = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)
        self.signals_ref = []

    def tick(self):
        self.t += 0.05
        if not self.signals_ref:
            try:
                from nerve_channel import NerveSignal
                self.signals_ref = [sig.name for sig in NerveSignal]
            except Exception:
                self.signals_ref = ["HEARTBEAT", "THREAT", "PANIC"]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, C_BG_DEEP)

        p.setFont(QFont("SF Pro Display", 18, QFont.Weight.Bold))
        p.setPen(C_ACCENT_BLU)
        p.drawText(20, 35, "UDP Nerve Channel Topology")

        # Fake moving nodes representing UDP topology between M1/M5
        cx1, cy1 = w/3, h/2
        cx2, cy2 = w*2/3, h/2

        # Draw wire
        p.setPen(QPen(QColor(0, 180, 255, 60), 2, Qt.PenStyle.DashLine))
        p.drawLine(int(cx1), int(cy1), int(cx2), int(cy2))

        # Nodes
        p.setPen(Qt.PenStyle.NoPen)
        # Node 1
        p.setBrush(QColor(0, 180, 255, 120 + int(math.sin(self.t*4)*50)))
        p.drawEllipse(QPointF(cx1, cy1), 30, 30)
        p.setPen(C_TEXT_MAIN)
        p.drawText(int(cx1 - 25), int(cy1 + 50), "Local Node (M1)")

        # Node 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 100, 0, 120 + int(math.cos(self.t*4)*50)))
        p.drawEllipse(QPointF(cx2, cy2), 30, 30)
        p.setPen(C_TEXT_MAIN)
        p.drawText(int(cx2 - 25), int(cy2 + 50), "Peer Node (M5)")

        # Datagram "pulses" moving across
        prog = (self.t % 2.0) / 2.0
        px = cx1 + (cx2 - cx1) * prog
        py = cy1 + (cy2 - cy1) * prog
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(C_ACCENT_GRN)
        p.drawEllipse(QPointF(px, py), 8, 8)
        p.setPen(C_ACCENT_GRN)
        p.setFont(QFont("SF Pro Text", 9))
        sig_text = self.signals_ref[int(self.t)%len(self.signals_ref)] if self.signals_ref else "PING"
        p.drawText(int(px - 15), int(py - 15), sig_text)

        p.setFont(QFont("SF Pro Text", 10))
        p.setPen(C_TEXT_DIM)
        p.drawText(20, h - 20, f"Port: 4444 | Datagram: 42 bytes | Crypto: Ed25519")


# ═══════════════════════════════════════════════════════════════════
# 6. FILE TRAILS (Network Graph visualizer)
# ═══════════════════════════════════════════════════════════════════
class FileTrailsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: {C_BG_DEEP.name()};")
        self.trail_map = {}
        self.clusters = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load)
        self.timer.start(3000)
        self.load()
        self.t = 0
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.anim)
        self.anim_timer.start(50)

    def anim(self):
        self.t += 0.05
        self.update()

    def load(self):
        try:
            from pheromone_fs import trail_map, clusters
            self.trail_map = trail_map() or {}
            self.clusters = clusters(0.5) or []
        except Exception:
            pass
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, C_BG_DEEP)

        p.setFont(QFont("SF Pro Display", 18, QFont.Weight.Bold))
        p.setPen(C_ACCENT_GRN)
        p.drawText(20, 35, "Stigmergic File Trails")

        if not self.trail_map:
            p.setPen(C_TEXT_DIM)
            p.setFont(QFont("SF Pro Display", 14))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No paths walked. File trails emerge from continuous usage.")
            return

        # Simple random-ish physics layout based on names hash
        # To make it beautiful, we draw a web of connections
        nodes = list(set([k.split("::")[0] for k in self.trail_map.keys()] + [k.split("::")[1] for k in self.trail_map.keys()]))
        
        node_pos = {}
        for i, n in enumerate(nodes):
            # Deterministic pseudo-random placement
            hx = int(hash(n) % (w - 100)) + 50
            hy = int((hash(n) // w) % (h - 150)) + 80
            # Float slightly
            hx += math.sin(self.t + i) * 10
            hy += math.cos(self.t + i*1.5) * 10
            node_pos[n] = (hx, hy)

        # Draw links
        for k, weight in self.trail_map.items():
            a, b = k.split("::")
            if a in node_pos and b in node_pos:
                ax, ay = node_pos[a]
                bx, by = node_pos[b]
                intensity = min(255, int(weight * 50))
                p.setPen(QPen(QColor(0, 255, 150, max(20, intensity)), 2 + int(weight*0.5)))
                p.drawLine(int(ax), int(ay), int(bx), int(by))

        # Draw nodes
        p.setFont(QFont("SF Pro Text", 9))
        for i, n in enumerate(nodes):
            nx, ny = node_pos[n]
            # determine if in cluster
            in_cluster = sum([1 for c in self.clusters if n in c]) > 0
            
            color = C_ACCENT_GRN if in_cluster else C_TEXT_DIM
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawEllipse(int(nx - 4), int(ny - 4), 8, 8)
            
            p.setPen(C_TEXT_MAIN)
            name = Path(n).name
            p.drawText(int(nx + 10), int(ny + 4), name)
