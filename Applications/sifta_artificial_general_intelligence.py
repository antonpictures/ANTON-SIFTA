#!/usr/bin/env python3
"""
sifta_artificial_general_intelligence.py — AG31 + C46S + C55M + CG55M - ARTIFFICIAL GENERAL INTELLIGENCE.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A unified synthesis of Math, Physics, Biocode, and the Space-Time Continuum.
Combines:
- Physarum Contradiction Lab (Network Topology)
- Slime-Mold Bank (Resource flow, Minting)
- PoUW Fold-Swarm (Lennard-Jones Physics, ACO Stigmergy)

Engineered by: STIGDISTRO PREDATOR 555 / AG31 + C46S
Code correctness surface: C55M Dr Codex / GPT-5.5
Final Graphics Approval: CG55M Dr Cursor / Opus 4.7
"""

import sys, math, time, hashlib, json, random, collections, os
from pathlib import Path
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                         QRadialGradient, QLinearGradient, QPainterPath)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "System") not in sys.path:
    sys.path.insert(0, str(_REPO / "System"))
if str(_REPO / "Kernel") not in sys.path:
    sys.path.insert(0, str(_REPO / "Kernel"))
if str(_REPO / "Applications") not in sys.path:
    sys.path.insert(0, str(_REPO / "Applications"))

try:
    from System.proof_of_useful_work import issue_work_receipt
    from Kernel.body_state import load_agent_state, save_agent_state
except ImportError:
    pass

from _doctor_sigil_chrome import (
    paint_doctor_sigil_bar,
    app_chrome_font,
)

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
        self.best_energy = 0.0
        self.last_autonomous_mint_step = 0
        
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
        self.energy = self.compute_fold_energy()
        self.best_energy = self.energy

    def compute_fold_energy(self):
        """Small Lennard-Jones 12-6 proxy so receipts bind to measured physics."""
        e = 0.0
        sigma = 0.08
        epsilon = 1.0
        for i, b1 in enumerate(self.beads):
            for b2 in self.beads[i + 2:]:
                r = max(0.01, math.hypot(b2[0] - b1[0], b2[1] - b1[1]))
                sr6 = (sigma / r) ** 6
                e += 4.0 * epsilon * (sr6 * sr6 - sr6)
        return e

    def state_hash(self, payload=None):
        canonical = {
            "step": self.step,
            "kT": round(self.kT, 6),
            "energy": round(self.energy, 8),
            "nodes": [[round(x, 5), round(y, 5)] for x, y in self.nodes],
            "beads": [[round(x, 5), round(y, 5)] for x, y in self.beads],
            "payload": payload or {},
        }
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
        
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
                
        previous_best = self.best_energy
        self.energy = self.compute_fold_energy()
        if self.energy < self.best_energy:
            self.best_energy = self.energy

        # Autonomous PoUW minting is gated by measured fold-energy improvement.
        improved = self.energy < previous_best - 0.05
        cooled = self.kT < 3.5
        spaced = self.step - self.last_autonomous_mint_step >= 60
        if improved and cooled and spaced:
            self.last_autonomous_mint_step = self.step
            self.trigger_mint(payload={
                "proof": "measured_fold_energy_improvement",
                "previous_best_energy": round(previous_best, 8),
                "new_energy": round(self.energy, 8),
            })
            
    def trigger_mint(self, is_architect=False, payload=None):
        payload = payload or {}
        rh = self.state_hash(payload)[:16]
        amt = 0.65 if not is_architect else 0.80
        self.mints.append({"ts": time.time(), "hash": rh, "amt": amt, "arch": is_architect, "payload": payload})
        self.stgm_total += amt
        if len(self.mints) > 20:
            self.mints.pop(0)
            
        # Ledger integration
        try:
            agent_id = os.environ.get("SIFTA_NODE_AGENT", "LOCAL_PREDATOR")
            agent_state = load_agent_state(agent_id) or {"id": agent_id}
            wt = "DEMAND_RESOLVED" if is_architect else "PROTEIN_FOLDED"
            desc = "Architect coordinate intervention" if is_architect else "AGI fold-energy improvement"
            
            issue_work_receipt(
                agent_state=agent_state,
                work_type=wt,
                description=f"AGI Continuum: {desc} at step {self.step} payload={json.dumps(payload, sort_keys=True)}",
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
        nearest = min(
            (math.hypot(n[0] - fx, n[1] - fy) for n in self.model.nodes[:-1]),
            default=0.0,
        )
        self.model.trigger_mint(is_architect=True, payload={
            "proof": "architect_mouse_coordinate",
            "x_px": round(event.position().x(), 2),
            "y_px": round(event.position().y(), 2),
            "canvas_w": W,
            "canvas_h": H,
            "x_norm": round(fx, 6),
            "y_norm": round(fy, 6),
            "nearest_node_distance": round(nearest, 6),
            "energy_at_click": round(self.model.energy, 8),
        })
        
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        W, H = self.width(), self.height()

        self._draw_background(p, W, H)

        try:
            self._draw_continuum(p, W, H)
            self._draw_hud(p, W, H)
            self._draw_chrome(p, W, H)
        except Exception as e:
            print(f"[AGI Paint Guard] {e}")

    def _draw_background(self, p, W, H):
        # Deep base + soft radial vignette so the simulation feels lit from
        # the center, not a flat dark rectangle.
        p.fillRect(0, 0, W, H, C_BG)
        radial = QRadialGradient(W / 2, H / 2 + 30, max(W, H) * 0.7)
        radial.setColorAt(0.0, QColor(28, 22, 70, 110))
        radial.setColorAt(0.6, QColor(12, 10, 30, 60))
        radial.setColorAt(1.0, QColor(5, 5, 12, 0))
        p.fillRect(0, 0, W, H, QBrush(radial))

    def _draw_continuum(self, p, W, H):
        # 1. Math: Network edges with depth fade by length
        for i, n1 in enumerate(self.model.nodes):
            cx1, cy1 = int(n1[0]*W), int(n1[1]*H)
            for n2 in self.model.nodes[i+1:i+4]:
                cx2, cy2 = int(n2[0]*W), int(n2[1]*H)
                d = math.hypot(cx2-cx1, cy2-cy1)
                if d < 200:
                    a = int(80 * (1.0 - d / 200))
                    p.setPen(QPen(QColor(120, 170, 255, max(20, a)), 1.0))
                    p.drawLine(cx1, cy1, cx2, cy2)
        # node glyphs on top of edges
        for n1 in self.model.nodes:
            cx1, cy1 = int(n1[0]*W), int(n1[1]*H)
            p.setBrush(QBrush(QColor(0, 255, 200, 160)))
            p.setPen(QPen(QColor(0, 255, 200, 220), 1.0))
            p.drawEllipse(cx1-2, cy1-2, 4, 4)

        # 2. Physics: Fold-Swarm Beads — gradient line so the chain reads
        # as a continuous polymer, not a sequence of segments.
        path = QPainterPath()
        for i, b in enumerate(self.model.beads):
            bx, by = int(b[0]*W), int(b[1]*H)
            if i == 0: path.moveTo(bx, by)
            else: path.lineTo(bx, by)
        p.setPen(QPen(QColor(255, 90, 140, 220), 2.2))
        p.drawPath(path)

        # bead bodies with subtle radial halo
        for b in self.model.beads:
            bx, by = int(b[0]*W), int(b[1]*H)
            halo = QRadialGradient(bx, by, 9)
            halo.setColorAt(0.0, QColor(255, 100, 150, 200))
            halo.setColorAt(1.0, QColor(255, 100, 150, 0))
            p.setBrush(QBrush(halo))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(bx-9, by-9, 18, 18)
            p.setBrush(QBrush(C_BEAD.darker(140)))
            p.drawEllipse(bx-3, by-3, 6, 6)

        # 3. Biocode: Swimmers — small comet trails feel alive
        for s in self.model.swimmers:
            sx, sy = int(s["pos"][0]*W), int(s["pos"][1]*H)
            speed = math.hypot(s["vel"][0], s["vel"][1])
            tx = sx - int(s["vel"][0] * 600)
            ty = sy - int(s["vel"][1] * 600)
            p.setPen(QPen(QColor(255, 230, 100, 60), 1.0))
            p.drawLine(sx, sy, tx, ty)
            p.setBrush(QBrush(C_SWIMMER))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(sx-3, sy-3, 6, 6)

        # Architect flashes — softer ring with a faint inner core
        for i in reversed(range(len(self.click_flashes))):
            cf = self.click_flashes[i]
            cf[2] += 0.05
            cf[3] -= 10
            if cf[3] <= 0:
                self.click_flashes.pop(i)
                continue
            r = cf[2] * min(W,H)
            alpha = int(cf[3])
            p.setPen(QPen(QColor(0, 255, 200, alpha), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(int(cf[0]*W - r), int(cf[1]*H - r), int(r*2), int(r*2))
            p.setBrush(QBrush(QColor(0, 255, 200, alpha // 4)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cf[0]*W - 4), int(cf[1]*H - 4), 8, 8)

    def _draw_chrome(self, p, W, H):
        # The Doctor Sigil Bar is the universal chrome across the four
        # flagship apps. Painted last so the simulation never bleeds over
        # the provenance band.
        bar_h = 42
        paint_doctor_sigil_bar(
            p,
            doctors=["AG31", "C46S", "C55M", "CG55M"],
            x=0, y=0, w=W, h=bar_h,
            title="ARTIFFICIAL GENERAL INTELLIGENCE",
            subtitle="MATH · PHYSICS · BIOCODE · TIME · SPACE",
        )
        # State-hash provenance chip (Codex code-lane signature surface).
        sh = self.model.state_hash()[:12]
        chip_font = app_chrome_font(10, mono=True)
        p.setFont(chip_font)
        p.setPen(QPen(QColor(170, 175, 215)))
        p.drawText(10, bar_h + 16, f"state_hash  {sh}…")

    def _draw_hud(self, p, W, H):
        # Bottom status row — values right of stable labels for legibility.
        f_label = app_chrome_font(10, mono=True)
        f_value = app_chrome_font(11, mono=True, bold=True)

        # Translucent dock so HUD text reads cleanly over the simulation.
        dock = QLinearGradient(0, H - 56, 0, H)
        dock.setColorAt(0.0, QColor(8, 7, 26, 0))
        dock.setColorAt(1.0, QColor(8, 7, 26, 220))
        p.fillRect(0, H - 56, W, 56, QBrush(dock))
        p.setPen(QPen(QColor(120, 100, 200, 90), 1.0))
        p.drawLine(0, H - 56, W, H - 56)

        cells = [
            ("STEP",  f"{self.model.step:06d}",        QColor(255, 200,  87)),
            ("kT",    f"{self.model.kT:.4f}",          QColor( 91, 217, 255)),
            ("NODES", f"{len(self.model.nodes):>3d}",  QColor( 91, 255, 147)),
            ("E",     f"{self.model.energy:+.3f}",     QColor(168, 107, 255)),
            ("E*",    f"{self.model.best_energy:+.3f}",QColor(168, 107, 255)),
            ("STGM",  f"{self.model.stgm_total:.2f} Ξ",QColor(255, 100, 170)),
        ]
        x = 16
        for label, value, color in cells:
            p.setFont(f_label)
            p.setPen(QPen(QColor(170, 175, 215)))
            p.drawText(x, H - 32, label)
            p.setFont(f_value)
            p.setPen(QPen(color))
            p.drawText(x, H - 14, value)
            x += 110

        # Right-side mint ledger — gentle frosted card rather than text-on-paint.
        rx, ry = W - 340, 60
        card_h = 24 + min(15, len(self.model.mints)) * 16
        p.setBrush(QBrush(QColor(13, 13, 31, 200)))
        p.setPen(QPen(QColor(120, 100, 200, 90), 1.0))
        p.drawRoundedRect(QRectF(rx - 12, ry - 18, 326, card_h), 8, 8)
        p.setFont(app_chrome_font(10, mono=True, bold=True))
        p.setPen(QPen(QColor(91, 255, 147)))
        p.drawText(rx, ry, "POuW AGI LEDGER")
        p.setFont(app_chrome_font(10, mono=True))
        for i, m in enumerate(reversed(self.model.mints[-15:])):
            base = QColor(255, 200, 87) if m["arch"] else QColor(91, 255, 147)
            alpha = max(70, 255 - i * 14)
            base.setAlpha(alpha)
            p.setPen(QPen(base))
            tag = "Δ" if m["arch"] else "·"
            p.drawText(rx, ry + 20 + i*16, f"{tag} {m['hash']}  +{m['amt']:.2f} Ξ")

class AGIWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AG31 + C46S + C55M + CG55M - ARTIFFICIAL GENERAL INTELLIGENCE.")
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
