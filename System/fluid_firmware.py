#!/usr/bin/env python3
"""
fluid_firmware.py — Swarm-Routed Hardware Membrane
═══════════════════════════════════════════════════════
"Firmware is dead code trying to run physical hardware."

Replace frozen monolithic firmware with a living fluid membrane.
Signal swimmers carry binary payloads across silicon pathways.
Degraded transistors create friction.  Swimmers abandon dying traces
and stigmergically carve new routes through surviving silicon.

Architecture:
  • SiliconGrid       — 2D lattice of SiliconNodes (pins, transistors, cache)
  • SignalSwimmer     — carries payload from Input pin to Output pin
  • UpdateSwimmer     — new-gen swimmer injected as "Liquid Update"
  • ThermalForager    — patrols for hotspots, drops thermal pheromone

Self-healing:
  Degradation ↑ → friction ↑ → pheromone sourness ↑ → swimmers reroute.
  No patches.  No reboots.  The silicon heals its own routing.

Liquid Update:
  New swimmers injected concurrently.  They lay stronger pheromone.
  Old swimmers starved out naturally.  Zero-downtime firmware update.

Persistence:
  .sifta_state/firmware_routing_table.json — the emergent routing map
"""
from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

REPO = Path(__file__).resolve().parent.parent
STATE_DIR = REPO / ".sifta_state"
ROUTING_FILE = STATE_DIR / "firmware_routing_table.json"


# ── Silicon Grid ─────────────────────────────────────────────────

@dataclass
class SiliconNode:
    """A single node on the chip: transistor, cache cell, or pin."""
    row: int
    col: int
    node_type: str = "transistor"  # "input_pin", "output_pin", "transistor", "cache"
    health: float = 1.0           # 1.0 = pristine, 0.0 = dead
    temperature: float = 25.0     # Celsius
    resistance: float = 0.0       # derived from health: lower health → higher resistance
    signal_pheromone: float = 0.0 # trace left by successful signal delivery
    thermal_pheromone: float = 0.0# warning: hotspot detected
    update_pheromone: float = 0.0 # trace from updated swimmers (v2)
    total_signals: int = 0        # lifetime signal count through this node


class SiliconGrid:
    """2D lattice representing a microchip's routing substrate."""

    def __init__(self, rows: int = 40, cols: int = 60):
        self.rows = rows
        self.cols = cols
        self.nodes: np.ndarray = np.empty((rows, cols), dtype=object)
        self.tick = 0
        self.total_delivered = 0
        self.total_dropped = 0

        for r in range(rows):
            for c in range(cols):
                if c == 0:
                    ntype = "input_pin"
                elif c == cols - 1:
                    ntype = "output_pin"
                elif (rows // 3 <= r <= 2 * rows // 3) and (cols // 3 <= c <= 2 * cols // 3):
                    ntype = "cache"
                else:
                    ntype = "transistor"
                self.nodes[r, c] = SiliconNode(row=r, col=c, node_type=ntype)

    def get(self, r: int, c: int) -> Optional[SiliconNode]:
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return self.nodes[r, c]
        return None

    def neighbors(self, r: int, c: int) -> List[SiliconNode]:
        """4-connected grid neighbors."""
        nbrs = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            n = self.get(r + dr, c + dc)
            if n is not None:
                nbrs.append(n)
        return nbrs

    def input_pins(self) -> List[SiliconNode]:
        return [self.nodes[r, 0] for r in range(self.rows)]

    def output_pins(self) -> List[SiliconNode]:
        return [self.nodes[r, self.cols - 1] for r in range(self.rows)]

    # ── Health arrays for fast visualization ─────────────────
    def health_matrix(self) -> np.ndarray:
        m = np.zeros((self.rows, self.cols))
        for r in range(self.rows):
            for c in range(self.cols):
                m[r, c] = self.nodes[r, c].health
        return m

    def signal_phero_matrix(self) -> np.ndarray:
        m = np.zeros((self.rows, self.cols))
        for r in range(self.rows):
            for c in range(self.cols):
                m[r, c] = self.nodes[r, c].signal_pheromone
        return m

    def thermal_phero_matrix(self) -> np.ndarray:
        m = np.zeros((self.rows, self.cols))
        for r in range(self.rows):
            for c in range(self.cols):
                m[r, c] = self.nodes[r, c].thermal_pheromone
        return m

    def update_phero_matrix(self) -> np.ndarray:
        m = np.zeros((self.rows, self.cols))
        for r in range(self.rows):
            for c in range(self.cols):
                m[r, c] = self.nodes[r, c].update_pheromone
        return m

    def temperature_matrix(self) -> np.ndarray:
        m = np.zeros((self.rows, self.cols))
        for r in range(self.rows):
            for c in range(self.cols):
                m[r, c] = self.nodes[r, c].temperature
        return m


# ── Signal Swimmers ──────────────────────────────────────────────

@dataclass
class SignalSwimmer:
    """Carries a payload from an input pin to an output pin."""
    swimmer_id: int
    generation: int = 1        # 1 = original firmware, 2 = liquid update
    row: int = 0
    col: int = 0
    target_row: int = -1
    target_col: int = -1
    payload: str = ""
    alive: bool = True
    delivered: bool = False
    hops: int = 0
    max_hops: int = 200
    path: List[Tuple[int, int]] = field(default_factory=list)
    stuck_counter: int = 0

    @property
    def color(self) -> str:
        if self.generation == 2:
            return "#00ffaa"   # liquid update = brighter green
        return "#00ccff"       # original = blue

    @property
    def is_update(self) -> bool:
        return self.generation >= 2


@dataclass
class ThermalForager:
    """Patrols the chip for thermal anomalies."""
    row: int = 0
    col: int = 0
    alive: bool = True
    hotspots_found: int = 0


# ── Core simulation logic ───────────────────────────────────────

def spawn_signal_batch(
    grid: SiliconGrid, count: int = 8, generation: int = 1, _id_counter: List[int] = [0]
) -> List[SignalSwimmer]:
    """Spawn a batch of signal swimmers at random input pins."""
    swimmers = []
    inputs = grid.input_pins()
    outputs = grid.output_pins()
    for _ in range(count):
        inp = random.choice(inputs)
        out = random.choice(outputs)
        _id_counter[0] += 1
        swimmers.append(SignalSwimmer(
            swimmer_id=_id_counter[0],
            generation=generation,
            row=inp.row, col=inp.col,
            target_row=out.row, target_col=grid.cols - 1,
            payload=f"PKT-{_id_counter[0]:06d}",
            path=[(inp.row, inp.col)],
        ))
    return swimmers


def spawn_thermal_foragers(grid: SiliconGrid, count: int = 6) -> List[ThermalForager]:
    return [ThermalForager(
        row=random.randint(0, grid.rows - 1),
        col=random.randint(0, grid.cols - 1),
    ) for _ in range(count)]


def step_signal_swimmer(sw: SignalSwimmer, grid: SiliconGrid) -> None:
    """Advance one signal swimmer by one hop. Core stigmergic routing."""
    if not sw.alive or sw.delivered:
        return

    sw.hops += 1
    if sw.hops > sw.max_hops:
        sw.alive = False
        grid.total_dropped += 1
        return

    node = grid.get(sw.row, sw.col)
    if node is None or node.health < 0.05:
        sw.alive = False
        grid.total_dropped += 1
        return

    # Arrived?
    if sw.col == sw.target_col:
        sw.delivered = True
        sw.alive = False
        grid.total_delivered += 1
        node.total_signals += 1
        phero_str = 0.15 if sw.generation == 1 else 0.25
        node.signal_pheromone = min(1.0, node.signal_pheromone + phero_str)
        if sw.is_update:
            node.update_pheromone = min(1.0, node.update_pheromone + 0.2)
        return

    nbrs = grid.neighbors(sw.row, sw.col)
    if not nbrs:
        sw.alive = False
        grid.total_dropped += 1
        return

    # Filter out very dead nodes and recent path (avoid loops)
    recent = set(sw.path[-8:])
    candidates = [n for n in nbrs if n.health > 0.1 and (n.row, n.col) not in recent]
    if not candidates:
        candidates = [n for n in nbrs if n.health > 0.05]
    if not candidates:
        sw.alive = False
        grid.total_dropped += 1
        return

    # Score each candidate: lower cost = better
    best_node = None
    best_score = float("inf")
    for n in candidates:
        dist_to_target = abs(n.row - sw.target_row) + abs(n.col - sw.target_col)
        resistance_cost = (1.0 - n.health) * 8.0
        thermal_cost = n.thermal_pheromone * 5.0
        # Pheromone attraction: existing traces reduce cost
        phero_bonus = n.signal_pheromone * 2.0
        if sw.is_update:
            phero_bonus += n.update_pheromone * 3.0
        # Prefer moving right (toward output)
        direction_bonus = (n.col - sw.col) * 0.5

        score = dist_to_target + resistance_cost + thermal_cost - phero_bonus - direction_bonus
        score += random.uniform(-0.3, 0.3)  # stochastic exploration

        if score < best_score:
            best_score = score
            best_node = n

    if best_node is None:
        sw.alive = False
        grid.total_dropped += 1
        return

    # Move
    sw.row = best_node.row
    sw.col = best_node.col
    sw.path.append((sw.row, sw.col))
    if len(sw.path) > 120:
        sw.path = sw.path[-80:]

    # Deposit trace pheromone
    deposit = 0.04 if sw.generation == 1 else 0.07
    best_node.signal_pheromone = min(1.0, best_node.signal_pheromone + deposit)
    if sw.is_update:
        best_node.update_pheromone = min(1.0, best_node.update_pheromone + 0.05)
    best_node.total_signals += 1

    # Thermal effect: carrying signals heats the node slightly
    best_node.temperature += 0.02

    # Stuck detection
    if sw.hops > 20 and sw.col < 3:
        sw.stuck_counter += 1
        if sw.stuck_counter > 15:
            sw.alive = False
            grid.total_dropped += 1


def step_thermal_forager(tf: ThermalForager, grid: SiliconGrid) -> None:
    """Thermal forager patrols for hotspots."""
    if not tf.alive:
        return

    node = grid.get(tf.row, tf.col)
    if node and node.temperature > 45.0:
        node.thermal_pheromone = min(1.0, node.thermal_pheromone + 0.1)
        tf.hotspots_found += 1

    nbrs = grid.neighbors(tf.row, tf.col)
    if nbrs:
        hottest = max(nbrs, key=lambda n: n.temperature + random.uniform(-5, 5))
        tf.row = hottest.row
        tf.col = hottest.col


# ── Degradation and environment ─────────────────────────────────

def degrade_cluster(grid: SiliconGrid, center_r: int, center_c: int, radius: int = 5,
                    severity: float = 0.7) -> int:
    """Simulate thermal/physical degradation of a cluster of nodes.
    Returns number of affected nodes."""
    affected = 0
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr * dr + dc * dc > radius * radius:
                continue
            n = grid.get(center_r + dr, center_c + dc)
            if n and n.node_type not in ("input_pin", "output_pin"):
                dist = math.sqrt(dr * dr + dc * dc) / max(radius, 1)
                damage = severity * (1.0 - dist * 0.6)
                n.health = max(0.0, n.health - damage)
                n.temperature += 30.0 * damage
                n.resistance = 1.0 - n.health
                affected += 1
    return affected


def tick_environment(grid: SiliconGrid, signal_decay: float = 0.992,
                     thermal_decay: float = 0.985, update_decay: float = 0.995,
                     cool_rate: float = 0.3) -> None:
    """Per-tick environmental decay: pheromone evaporation, cooling."""
    for r in range(grid.rows):
        for c in range(grid.cols):
            n = grid.nodes[r, c]
            n.signal_pheromone *= signal_decay
            n.thermal_pheromone *= thermal_decay
            n.update_pheromone *= update_decay
            # Cool toward ambient
            n.temperature += (25.0 - n.temperature) * cool_rate * 0.01
            # Resistance follows health
            n.resistance = 1.0 - n.health


# ── Telemetry ────────────────────────────────────────────────────

def compute_telemetry(grid: SiliconGrid, swimmers: List[SignalSwimmer]) -> Dict:
    active = sum(1 for s in swimmers if s.alive and not s.delivered)
    delivered = sum(1 for s in swimmers if s.delivered)
    dropped = sum(1 for s in swimmers if not s.alive and not s.delivered)
    gen1_alive = sum(1 for s in swimmers if s.alive and s.generation == 1)
    gen2_alive = sum(1 for s in swimmers if s.alive and s.generation == 2)

    healths = [grid.nodes[r, c].health
               for r in range(grid.rows) for c in range(grid.cols)]
    avg_health = sum(healths) / max(1, len(healths))
    dead_nodes = sum(1 for h in healths if h < 0.1)
    active_paths = sum(1 for r in range(grid.rows) for c in range(grid.cols)
                       if grid.nodes[r, c].signal_pheromone > 0.05)

    # Synthetic throughput: delivered signals per tick
    throughput = grid.total_delivered * 0.5  # ~0.5 MB per packet

    return {
        "active_swimmers": active,
        "delivered": delivered,
        "dropped": dropped,
        "gen1_alive": gen1_alive,
        "gen2_alive": gen2_alive,
        "avg_health": avg_health,
        "dead_nodes": dead_nodes,
        "active_paths": active_paths,
        "throughput_mb": throughput,
        "total_delivered": grid.total_delivered,
        "total_dropped": grid.total_dropped,
    }


# ── Persistence ──────────────────────────────────────────────────

def save_routing_table(grid: SiliconGrid) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    routes = {}
    for r in range(grid.rows):
        for c in range(grid.cols):
            n = grid.nodes[r, c]
            if n.signal_pheromone > 0.05 or n.total_signals > 0:
                routes[f"{r},{c}"] = {
                    "signal_phero": round(n.signal_pheromone, 4),
                    "signals": n.total_signals,
                    "health": round(n.health, 3),
                }
    ROUTING_FILE.write_text(json.dumps(routes, indent=2))
