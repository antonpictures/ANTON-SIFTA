#!/usr/bin/env python3
"""
stigmergic_canvas.py — Biological Paintbrush Engine
═════════════════════════════════════════════════════
You don't paint pixels. You deploy a biological ecosystem on blank territory.

The cursor is a pheromone emitter. PigmentForagers swarm from the edges,
carry wet pigment to the trace, and die on contact — staining the canvas
with organic, textured strokes. When two colors collide, they blend
stigmergically: yellow meets blue → green emerges without selection.

Damaged images: drop a "Heal" pheromone over a scratch. Swimmers sample
healthy pixels around the damage and stigmergically rebuild the missing data.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np


@dataclass
class PheromoneTrace:
    """A point of intent left by the cursor."""
    x: float
    y: float
    r: int          # target color
    g: int
    b: int
    strength: float = 1.0
    age: float = 0.0


@dataclass
class PigmentForager:
    """A swimmer carrying wet pigment toward a pheromone trace."""
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    r: int = 0
    g: int = 0
    b: int = 0
    alive: bool = True
    target_idx: int = -1
    deposited: bool = False

    @property
    def color(self) -> Tuple[int, int, int]:
        return (self.r, self.g, self.b)


class CanvasEngine:
    """Core engine: pheromone field + forager swarm + pixel canvas."""

    def __init__(self, width: int = 800, height: int = 600):
        self.width = width
        self.height = height
        # RGBA canvas (persistent paint)
        self.pixels = np.zeros((height, width, 4), dtype=np.float32)
        # Pheromone traces (cursor intent)
        self.traces: List[PheromoneTrace] = []
        # Active foragers
        self.foragers: List[PigmentForager] = []
        # Telemetry
        self.total_deposited = 0
        self.tick = 0
        self.evaporation_rate = 0.02
        self.swarm_density = 120

    def add_trace(self, x: float, y: float, r: int, g: int, b: int, strength: float = 1.0):
        """Cursor drops intent pheromone."""
        self.traces.append(PheromoneTrace(x=x, y=y, r=r, g=g, b=b, strength=strength))
        self._spawn_foragers_for_trace(len(self.traces) - 1, r, g, b)

    def _spawn_foragers_for_trace(self, trace_idx: int, r: int, g: int, b: int):
        """Spawn foragers from canvas edges, targeting a trace."""
        n = max(4, self.swarm_density // 10)
        for _ in range(n):
            edge = random.randint(0, 3)
            if edge == 0:    # top
                sx, sy = random.uniform(0, self.width), 0
            elif edge == 1:  # bottom
                sx, sy = random.uniform(0, self.width), self.height
            elif edge == 2:  # left
                sx, sy = 0, random.uniform(0, self.height)
            else:            # right
                sx, sy = self.width, random.uniform(0, self.height)

            self.foragers.append(PigmentForager(
                x=sx, y=sy, r=r, g=g, b=b, target_idx=trace_idx,
                vx=random.gauss(0, 2), vy=random.gauss(0, 2),
            ))

    def step(self):
        """Advance one simulation tick."""
        self.tick += 1

        # Evaporate traces
        alive_traces = []
        for t in self.traces:
            t.age += 0.016
            t.strength -= self.evaporation_rate
            if t.strength > 0.01:
                alive_traces.append(t)
        self.traces = alive_traces

        # Move foragers toward their target trace
        for f in self.foragers:
            if not f.alive or f.deposited:
                continue

            if f.target_idx >= len(self.traces):
                # Target evaporated — wander or die
                f.alive = False
                continue

            t = self.traces[f.target_idx] if f.target_idx < len(self.traces) else None
            if t is None or t.strength < 0.01:
                f.alive = False
                continue

            # Chemotaxis toward trace
            dx = t.x - f.x
            dy = t.y - f.y
            dist = math.sqrt(dx * dx + dy * dy) + 0.1

            # Arrived? Deposit pigment.
            if dist < 4.0:
                self._deposit(f, t)
                continue

            # Accelerate toward trace with some noise
            f.vx += (dx / dist) * 1.8 + random.gauss(0, 0.6)
            f.vy += (dy / dist) * 1.8 + random.gauss(0, 0.6)
            f.vx *= 0.92
            f.vy *= 0.92

            speed = math.sqrt(f.vx ** 2 + f.vy ** 2)
            max_speed = 6.0
            if speed > max_speed:
                f.vx *= max_speed / speed
                f.vy *= max_speed / speed

            f.x += f.vx
            f.y += f.vy

            # Bounce at edges
            f.x = max(0, min(self.width - 1, f.x))
            f.y = max(0, min(self.height - 1, f.y))

        # Garbage collect dead foragers
        if len(self.foragers) > 5000:
            self.foragers = [f for f in self.foragers if f.alive and not f.deposited]

    def _deposit(self, f: PigmentForager, t: PheromoneTrace):
        """Forager arrives at trace — deposit pigment with organic blending."""
        ix = int(np.clip(f.x, 0, self.width - 1))
        iy = int(np.clip(f.y, 0, self.height - 1))

        # Splatter radius (organic, not pixel-perfect)
        radius = random.randint(1, 3)
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                px = ix + dx
                py = iy + dy
                if 0 <= px < self.width and 0 <= py < self.height:
                    existing = self.pixels[py, px]
                    alpha = existing[3]
                    # Stigmergic blending: mix with existing paint
                    blend = random.uniform(0.3, 0.7)
                    if alpha > 0.1:
                        nr = existing[0] * (1 - blend) + f.r * blend
                        ng = existing[1] * (1 - blend) + f.g * blend
                        nb = existing[2] * (1 - blend) + f.b * blend
                    else:
                        nr, ng, nb = float(f.r), float(f.g), float(f.b)
                    self.pixels[py, px] = [nr, ng, nb, min(1.0, alpha + 0.3)]

        f.deposited = True
        f.alive = False
        self.total_deposited += 1

    def clear(self):
        self.pixels[:] = 0
        self.traces.clear()
        self.foragers.clear()
        self.total_deposited = 0

    def active_forager_count(self) -> int:
        return sum(1 for f in self.foragers if f.alive and not f.deposited)

    def pheromone_density(self) -> float:
        return sum(t.strength for t in self.traces)
