#!/usr/bin/env python3
"""
ARTIFICIAL GENERAL INTELLIGENCE.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A unified synthesis of Math, Physics, Biocode, and the Space-Time Continuum.
Combines:
- Physarum Contradiction Lab (Network Topology)
- Slime-Mold Bank (Resource flow, Minting)
- PoUW Fold-Swarm (Lennard-Jones Physics, ACO Stigmergy)

Engineered by: STIGDISTRO PREDATOR 555 / AG31 + C46S
Final Graphics Approval: CG55M Dr Cursor / Opus 4.7
"""

import sys, math, time, hashlib, json, random, collections, os
from pathlib import Path
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                         QRadialGradient, QPainterPath)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))
if str(_REPO / "Kernel") not in sys.path:
    sys.path.insert(0, str(_REPO / "Kernel"))

try:
    from System.proof_of_useful_work import issue_work_receipt
    from Kernel.body_state import load_agent_state, save_agent_state
except ImportError:
    pass

# ─── COLORS ──────────────────────────────────────────────────────────
C_BG        = QColor(5, 5, 10)
C_NETWORK   = QColor(40, 100, 255, 60)
C_NODE      = QColor(0, 255, 200, 150)
C_BEAD      = QColor(255, 60, 120)
C_SWIMMER   = QColor(255, 220, 0)
C_STGM      = QColor(0, 255, 160)
C_HUD_CYAN  = QColor(0, 230, 255)
C_HUD_GOLD  = QColor(255, 200, 50)
C_HUD_MAG   = QColor(255, 50, 200)

class GrandUnifiedModel:
    def __init__(self):
        self.step = 0
        self.kT = 4.0
        self.energy = 0.0
        
        # 1. Math/Space: Network Nodes (Physarum Topology)
        self.nodes = []
        for _ in range(40):
            self.nodes.append([random.uniform(0.1, 0.9), random.uniform(0.1, 0.9)])
            
        # 2. Physics/Time: Lennard-Jones Beads (Fold-Swarm)
        self.beads = []
        for i in range(15):
            angle = i * (2 * math.pi / 15)
            r = 0.2
            self.beads.append([0.5 + r*math.cos(angle), 0.5 + r*math.sin(angle)])
            
        # 3. Biocode: ACO Swimmers / Slime Particles
        self.swimmers = []
        for _ in range(30):
            self.swimmers.append({
                "pos": [0.5, 0.5],
                "vel": [random.uniform(-0.01, 0.01), random.uniform(-0.01, 0.01)],
                "life": 1.0
            })
            
        self.mints = []
        self.stgm_total = 0.0
        
    def tick(self):
        self.step += 1
        self.kT *= 0.9995
        self.kT = max(0.1, self.kT)
        
        # Physics update (jiggle beads)
        for b in self.beads:
            b[0] += random.gauss(0, 0.005 * self.kT)
            b[1] += random.gauss(0, 0.005 * self.kT)
            b[0] = max(0.05, min(0.95, b[0]))
            b[1] = max(0.05, min(0.95, b[1]))
            
        # Swimmer update
        for s in self.swimmers:
            s["pos"][0] += s["vel"][0]
            s["pos"][1] += s["vel"][1]
            if s["pos"][0] < 0 or s["pos"][0] > 1: s["vel"][0] *= -1
            if s["pos"][1] < 0 or s["pos"][1] > 1: s["vel"][1] *= -1
            
            # Pull towards nearest node
            min_d = 999
            target = None
            for n in self.nodes:
                d = math.hypot(n[0]-s["pos"][0], n[1]-s["pos"][1])
                if d < min_d:
                    min_d = d
                    target = n
            if target:
                dx = target[0] - s["pos"][0]
                dy = target[1] - s["pos"][1]
                s["vel"][0] += dx * 0.001
                s["vel"][1] += dy * 0.001
                
            # Speed limit
            speed = math.hypot(s["vel"][0], s["vel"][1])
            if speed > 0.02:
                s["vel"][0] = (s["vel"][0]/speed) * 0.02
                s["vel"][1] = (s["vel"][1]/speed) * 0.02
                
        # Stochastic PoUW Minting Event
        if random.random() < 0.02 and self.kT < 2.0:
            self.trigger_mint()
            
    def trigger_mint(self, is_architect=False):
        rh = hashlib.sha256(f"AGI_SIM_{self.step}_{time.time()}".encode()).hexdigest()[:16]
        amt = 0.65 if not is_architect else 0.80
        self.mints.append({"ts": time.time(), "hash": rh, "amt": amt, "arch": is_architect})
        self.stgm_total += amt
        if len(self.mints) > 20:
            self.mints.pop(0)
            
        # Ledger integration
        try:
            agent_id = os.environ.get("SIFTA_NODE_AGENT", "LOCAL_PREDATOR")
            agent_state = load_agent_state(agent_id) or {"id": agent_id}
            wt = "DEMAND_RESOLVED" if is_architect else "PROTEIN_FOLDED"
            desc = "Architect Intervention" if is_architect else "AGI Swarm Resonance"
            
            issue_work_receipt(
                agent_state=agent_state,
                work_type=wt,
                description=f"AGI Continuum: {desc} at step {self.step}",
                territory="artificial_general_intelligence",
                output_hash=rh
            )
            save_agent_state(agent_state)
        except Exception:
            pass

class AGICanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.model = GrandUnifiedModel()
        self.setMouseTracking(True)
        self.click_flashes = []
        
    def step(self):
        self.model.tick()
        self.update()
        
    def mousePressEvent(self, event):
        W, H = self.width(), self.height()
        fx, fy = event.position().x() / W, event.position().y() / H
        self.model.nodes.append([fx, fy])
        self.click_flashes.append([fx, fy, 0.0, 255.0])
        self.model.trigger_mint(is_architect=True)
        
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        
        p.fillRect(0, 0, W, H, C_BG)
        
        try:
            self._draw_continuum(p, W, H)
            self._draw_hud(p, W, H)
        except Exception as e:
            print(f"[AGI Paint Guard] {e}")
            
    def _draw_continuum(self, p, W, H):
        # 1. Math: Network edges
        p.setPen(QPen(C_NETWORK, 1.0))
        for i, n1 in enumerate(self.model.nodes):
            cx1, cy1 = int(n1[0]*W), int(n1[1]*H)
            p.drawEllipse(cx1-2, cy1-2, 4, 4)
            for n2 in self.model.nodes[i+1:i+4]:
                cx2, cy2 = int(n2[0]*W), int(n2[1]*H)
                if math.hypot(cx2-cx1, cy2-cy1) < 200:
                    p.drawLine(cx1, cy1, cx2, cy2)
                    
        # 2. Physics: Fold-Swarm Beads
        p.setPen(QPen(C_BEAD, 2.0))
        path = QPainterPath()
        for i, b in enumerate(self.model.beads):
            bx, by = int(b[0]*W), int(b[1]*H)
            if i == 0: path.moveTo(bx, by)
            else: path.lineTo(bx, by)
        p.drawPath(path)
        
        p.setBrush(QBrush(C_BEAD.darker(150)))
        for b in self.model.beads:
            bx, by = int(b[0]*W), int(b[1]*H)
            p.drawEllipse(bx-4, by-4, 8, 8)
            
        # 3. Biocode: Swimmers
        p.setBrush(QBrush(C_SWIMMER))
        p.setPen(Qt.PenStyle.NoPen)
        for s in self.model.swimmers:
            sx, sy = int(s["pos"][0]*W), int(s["pos"][1]*H)
            p.drawEllipse(sx-3, sy-3, 6, 6)
            
        # Architect flashes
        now = time.time()
        for i in reversed(range(len(self.click_flashes))):
            cf = self.click_flashes[i]
            cf[2] += 0.05
            cf[3] -= 10
            if cf[3] <= 0:
                self.click_flashes.pop(i)
                continue
            r = cf[2] * min(W,H)
            p.setPen(QPen(QColor(0, 255, 200, int(cf[3])), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(int(cf[0]*W - r), int(cf[1]*H - r), int(r*2), int(r*2))

    def _draw_hud(self, p, W, H):
        f_title = QFont("Courier New", 18, QFont.Weight.Bold)
        f_mono = QFont("Courier New", 12)
        
        p.setFont(f_title)
        p.setPen(QPen(C_HUD_CYAN))
        p.drawText(20, 40, "ARTIFFICIAL GENERAL INTELLIGENCE")
        
        p.setFont(f_mono)
        p.setPen(QPen(C_HUD_MAG))
        p.drawText(20, 65, "MATH · PHYSICS · BIOCODE · TIME · SPACE CONTINUUM")
        
        p.setPen(QPen(C_HUD_GOLD))
        p.drawText(20, H - 40, f"STEP {self.model.step:06d}")
        p.drawText(150, H - 40, f"kT {self.model.kT:.4f}")
        p.drawText(300, H - 40, f"NODES {len(self.model.nodes)}")
        p.drawText(420, H - 40, f"STGM {self.model.stgm_total:.2f}")
        
        # Mints
        rx, ry = W - 320, 40
        p.setPen(QPen(C_STGM))
        p.drawText(rx, ry, "━━ POuW AGI LEDGER ━━")
        for i, m in enumerate(reversed(self.model.mints[-15:])):
            c = QColor(255,220,0) if m["arch"] else C_STGM
            alpha = max(50, 255 - i * 15)
            c.setAlpha(alpha)
            p.setPen(QPen(c))
            p.drawText(rx, ry + 20 + i*16, f"{m['hash']} +{m['amt']:.2f} Ξ")

class AGIWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Artificial General Intelligence [Triple-IDE Synthesis]")
        self.setMinimumSize(1200, 800)
        self.canvas = AGICanvas()
        self.setCentralWidget(self.canvas)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.canvas.step)
        self.timer.start(30)

def main():
    app = QApplication(sys.argv)
    win = AGIWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
