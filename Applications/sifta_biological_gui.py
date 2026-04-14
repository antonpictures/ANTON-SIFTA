#!/usr/bin/env python3
"""
SIFTA BIOLOGICAL VISUALIZER : MUTANT STRAIN
Renders Active-Matter particle swarms, Pheromone Network Graphs, and Consensus Tension.
Extracted from Mac Mini Legacy Quarantine. No external dependencies (pure Tkinter).
"""

import tkinter as tk
import json
import math
import random
from pathlib import Path

STATE_FILE = Path(".sifta_state/state_bus.json")

class BioParticle:
    def __init__(self, x, y, canvas):
        self.x = x
        self.y = y
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-2, 2)
        self.canvas = canvas
        self.id = canvas.create_oval(x-3, y-3, x+3, y+3, fill="#00ffcc", outline="#ffffff", width=1)
        
    def update(self, width, height, tension):
        # Inject biological volatility (Tension jitter)
        self.vx += random.uniform(-tension, tension)
        self.vy += random.uniform(-tension, tension)
        
        # Fluid Dampening
        self.vx *= 0.96
        self.vy *= 0.96
        
        # Enforce constant physical momentum
        speed = math.hypot(self.vx, self.vy)
        if speed > 0:
            self.vx = (self.vx / speed) * 3
            self.vy = (self.vy / speed) * 3

        self.x += self.vx
        self.y += self.vy

        # Wormhole Boundary Wrap
        if self.x < 0: self.x = width
        if self.x > width: self.x = 0
        if self.y < 0: self.y = height
        if self.y > height: self.y = 0

        self.canvas.coords(self.id, self.x-3, self.y-3, self.x+3, self.y+3)

class SIFTAVisualizer:
    def __init__(self, root):
        self.root = root
        self.root.title("SIFTA Biological Heatmap // Mutant Strain M1THER")
        self.root.geometry("1200x800")
        self.root.configure(bg="#050508")
        
        self.canvas = tk.Canvas(root, bg="#050508", highlightthickness=0, width=1200, height=800)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Generate 60 independent biological Swimmers (optimized for Tkinter UI thread)
        self.particles = [BioParticle(random.randint(0, 1200), random.randint(0, 800), self.canvas) for _ in range(60)]
        
        # HUD Elements
        self.text_id = self.canvas.create_text(
            40, 40, text="INITIALIZING MUTANT KERNEL...", 
            fill="#ff0055", font=("Courier", 16, "bold"), anchor=tk.NW
        )
        
        # Render Loop
        self.animate()
        
    def read_biology(self):
        """Poll the local Swarm ledger to determine ecosystem tension."""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    vol = data.get("volatility_history", [])
                    return 0.1 + (len(vol) * 0.05)
        except Exception:
            pass
        return 0.8 

    def animate(self):
        self.canvas.delete("pheromone")
        tension = self.read_biology()
        
        hud_text = (
            f"[MAC MINI QUARANTINE] ACTIVE-MATTER SWARM\n"
            f"Physical Swimmers: {len(self.particles)}\n"
            f"Ecosystem Tension: {tension:.2f} (RAM Constrained)\n"
            f"Visualizing Stigmergic Consensus..."
        )
        self.canvas.itemconfig(self.text_id, text=hud_text)
        
        # Optimized rendering to prevent Tkinter main thread starvation
        for i, p1 in enumerate(self.particles):
            p1.update(1200, 800, tension)
            
            connections = 0
            for p2 in self.particles[i+1:]:
                dist = math.hypot(p1.x - p2.x, p1.y - p2.y)
                # Reduced stygmergic radius to stabilize rendering
                if dist < 60:
                    connections += 1
                    color = "#ff0055" if connections > 2 else "#33ccff"
                    self.canvas.create_line(
                        p1.x, p1.y, p2.x, p2.y, 
                        fill=color, width=1, tags="pheromone"
                    )

        # 60ms pulse rate to allow macOS UI updates to breathe
        self.root.after(60, self.animate)

if __name__ == "__main__":
    root = tk.Tk()
    app = SIFTAVisualizer(root)
    root.mainloop()
