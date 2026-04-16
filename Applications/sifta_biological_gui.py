#!/usr/bin/env python3
"""
SIFTA BIOLOGICAL VISUALIZER : MUTANT STRAIN
Renders Active-matter particle swarms, pheromone links, and consensus tension.
Legacy Tk path: standalone `python3 Applications/sifta_biological_gui.py`
Embedded path: BiologicalDashboardWidget (PyQt6) inside sifta_os_desktop MDI.
"""

from __future__ import annotations

import json
import math
import random
import sys
import tkinter as tk
from pathlib import Path

STATE_FILE = Path(".sifta_state/state_bus.json")
_REPO_ROOT = Path(__file__).resolve().parent.parent


def read_biology_tension() -> float:
    """Poll the local state bus for ecosystem tension (same on every node)."""
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                vol = data.get("volatility_history", [])
                return 0.1 + (len(vol) * 0.05)
    except Exception:
        pass
    return 0.8


def node_hud_title_line() -> str:
    """
    Identify *this* machine — not a remote node.
    M5 Foundry (GTH4921YP3) vs M1 Sentry (C07FL0JAQ6NV); unknown serials still labeled honestly.
    """
    try:
        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))
        from body_state import SwarmBody

        sn = SwarmBody.get_local_serial()
        agent = SwarmBody.resolve_agent_from_serial(sn)
        if agent == "ALICE_M5":
            return f"[M5 FOUNDRY · {sn}] ACTIVE-MATTER SWARM"
        if agent == "M1THER":
            return f"[M1 SENTRY · {sn}] ACTIVE-MATTER SWARM"
        return f"[NODE · {sn}] ACTIVE-MATTER SWARM"
    except Exception:
        return "[LOCAL NODE] ACTIVE-MATTER SWARM"


def _hud_body(num_swimmers: int, tension: float) -> str:
    title = node_hud_title_line()
    return (
        f"{title}\n"
        f"Physical Swimmers: {num_swimmers}\n"
        f"Ecosystem Tension: {tension:.2f} (local state_bus)\n"
        f"Visualizing Stigmergic Consensus (this machine)…"
    )


class BioParticle:
    def __init__(self, x, y, canvas):
        self.x = x
        self.y = y
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-2, 2)
        self.canvas = canvas
        self.id = canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#00ffcc", outline="#ffffff", width=1)

    def update(self, width, height, tension):
        self.vx += random.uniform(-tension, tension)
        self.vy += random.uniform(-tension, tension)
        self.vx *= 0.96
        self.vy *= 0.96
        speed = math.hypot(self.vx, self.vy)
        if speed > 0:
            self.vx = (self.vx / speed) * 3
            self.vy = (self.vy / speed) * 3
        self.x += self.vx
        self.y += self.vy
        if self.x < 0:
            self.x = width
        if self.x > width:
            self.x = 0
        if self.y < 0:
            self.y = height
        if self.y > height:
            self.y = 0
        self.canvas.coords(self.id, self.x - 3, self.y - 3, self.x + 3, self.y + 3)


class SIFTAVisualizer:
    def __init__(self, root):
        self.root = root
        self.root.title(f"SIFTA Biological Heatmap // {node_hud_title_line()[:48]}…")
        self.root.geometry("1200x800")
        self.root.configure(bg="#050508")

        self.canvas = tk.Canvas(root, bg="#050508", highlightthickness=0, width=1200, height=800)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.particles = [
            BioParticle(random.randint(0, 1200), random.randint(0, 800), self.canvas) for _ in range(60)
        ]

        self.text_id = self.canvas.create_text(
            40, 40, text="INITIALIZING MUTANT KERNEL…",
            fill="#ff0055", font=("Courier", 16, "bold"), anchor=tk.NW
        )
        self.animate()

    def animate(self):
        self.canvas.delete("pheromone")
        tension = read_biology_tension()
        self.canvas.itemconfig(self.text_id, text=_hud_body(len(self.particles), tension))

        for i, p1 in enumerate(self.particles):
            p1.update(1200, 800, tension)
            connections = 0
            for p2 in self.particles[i + 1 :]:
                dist = math.hypot(p1.x - p2.x, p1.y - p2.y)
                if dist < 60:
                    connections += 1
                    color = "#ff0055" if connections > 2 else "#33ccff"
                    self.canvas.create_line(p1.x, p1.y, p2.x, p2.y, fill=color, width=1, tags="pheromone")

        self.root.after(60, self.animate)


# ── PyQt6: embedded in SIFTA OS (no separate Tk window) ─────────────────────

try:
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

            # Pheromone edges
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
            hud = _hud_body(len(plist), tension)
            painter.drawText(24, 28, w - 48, h - 28, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, hud)

except ImportError:
    BiologicalDashboardWidget = None  # type: ignore[misc, assignment]


if __name__ == "__main__":
    root = tk.Tk()
    app = SIFTAVisualizer(root)
    root.mainloop()
