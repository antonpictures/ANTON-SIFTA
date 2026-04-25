#!/usr/bin/env python3
"""Legacy Tk standalone biological visualizer (not used by Qt desktop manifest)."""

from __future__ import annotations

import math
import random

import tkinter as tk

from Applications.sifta_biological_core import hud_body, read_biology_tension


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
        self.root.title("SIFTA Biological Heatmap")
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
        self.canvas.itemconfig(self.text_id, text=hud_body(len(self.particles), tension))

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


def run_standalone() -> None:
    root = tk.Tk()
    SIFTAVisualizer(root)
    root.mainloop()


if __name__ == "__main__":
    run_standalone()
