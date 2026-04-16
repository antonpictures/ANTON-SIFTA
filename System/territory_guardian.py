#!/usr/bin/env python3
"""
territory_guardian.py — Geospatial Pheromone Perimeter Engine
═══════════════════════════════════════════════════════════════════
"Territory is the Law."

Track a child, a pet, an AirTag, a phone — anything with coordinates.
Swimmers map the city as a graph.  Routine paths glow green.
Deviations trigger sentinel alerts.  Safest routes emerge from pheromone.

Architecture:
  • CityGraph      — nodes (intersections) + edges (roads), loaded from
                     OpenStreetMap Overpass API or synthetic demo grid
  • RoutineMapper  — follows tracked entity, deposits safe pheromone
  • DeviationSentinel — orbits entity, checks if path is on green trail
  • Pathfinder     — explores graph, finds safest routes avoiding red zones
  • PerimeterGuard — patrols the outer boundary of the safe zone

Alert pipeline:
  Deviation detected → severity scored (distance from safe trail) →
  nerve channel UDP pulse → Telegram push → desktop notification

Persistence:
  .sifta_state/territory_routine.json   — learned routine pheromone map
  .sifta_state/territory_alerts.jsonl   — alert history
"""
from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO = Path(__file__).resolve().parent.parent
STATE_DIR = REPO / ".sifta_state"
ROUTINE_FILE = STATE_DIR / "territory_routine.json"
ALERT_FILE = STATE_DIR / "territory_alerts.jsonl"


@dataclass
class MapNode:
    """An intersection or point of interest on the map."""
    id: int
    x: float          # normalized 0-1 canvas coordinate
    y: float
    name: str = ""
    poi_type: str = ""  # "home", "school", "park", "store", "hospital", ""
    neighbors: List[int] = field(default_factory=list)
    # Pheromone layers
    safe_pheromone: float = 0.0     # green — routine path
    danger_pheromone: float = 0.0   # red — flagged hazard
    visit_count: int = 0


@dataclass
class MapEdge:
    """A road segment between two intersections."""
    node_a: int
    node_b: int
    distance: float = 1.0
    road_name: str = ""
    safe_pheromone: float = 0.0
    danger_pheromone: float = 0.0


@dataclass
class TrackedEntity:
    """Something being tracked — child, pet, AirTag, phone."""
    name: str
    icon: str = "●"
    current_node: int = 0
    target_node: int = -1
    progress: float = 0.0   # 0-1 lerp between nodes
    path: List[int] = field(default_factory=list)
    speed: float = 1.0      # movement speed multiplier
    is_deviating: bool = False
    deviation_severity: float = 0.0


@dataclass
class TerritoryAlert:
    timestamp: float
    entity_name: str
    alert_type: str   # "DEVIATION", "SPEED", "BOUNDARY", "HAZARD"
    severity: float   # 0-1
    message: str
    node_id: int = -1
    x: float = 0.0
    y: float = 0.0


class CityGraph:
    """Graph representation of a city area."""

    def __init__(self):
        self.nodes: List[MapNode] = []
        self.edges: List[MapEdge] = []
        self._adj: Dict[int, List[int]] = {}

    def add_node(self, node: MapNode) -> None:
        self.nodes.append(node)
        self._adj.setdefault(node.id, [])

    def add_edge(self, a: int, b: int, road_name: str = "") -> None:
        if a >= len(self.nodes) or b >= len(self.nodes):
            return
        na, nb = self.nodes[a], self.nodes[b]
        dist = math.sqrt((na.x - nb.x)**2 + (na.y - nb.y)**2)
        self.edges.append(MapEdge(node_a=a, node_b=b, distance=dist, road_name=road_name))
        self._adj.setdefault(a, []).append(b)
        self._adj.setdefault(b, []).append(a)
        na.neighbors.append(b)
        nb.neighbors.append(a)

    def neighbors(self, node_id: int) -> List[int]:
        return self._adj.get(node_id, [])

    def edge_between(self, a: int, b: int) -> Optional[MapEdge]:
        for e in self.edges:
            if (e.node_a == a and e.node_b == b) or (e.node_a == b and e.node_b == a):
                return e
        return None

    def shortest_path(self, start: int, end: int, avoid_danger: bool = True) -> List[int]:
        """Dijkstra with pheromone-weighted cost. Safe = cheap, dangerous = expensive."""
        import heapq
        dist_map: Dict[int, float] = {start: 0.0}
        prev: Dict[int, int] = {}
        heap = [(0.0, start)]
        visited: Set[int] = set()

        while heap:
            d, u = heapq.heappop(heap)
            if u in visited:
                continue
            visited.add(u)
            if u == end:
                break
            for v in self.neighbors(u):
                if v in visited:
                    continue
                edge = self.edge_between(u, v)
                cost = edge.distance if edge else 1.0
                if avoid_danger:
                    nv = self.nodes[v]
                    cost += nv.danger_pheromone * 10.0
                    cost -= nv.safe_pheromone * 0.3
                    cost = max(0.01, cost)
                new_d = d + cost
                if new_d < dist_map.get(v, float('inf')):
                    dist_map[v] = new_d
                    prev[v] = u
                    heapq.heappush(heap, (new_d, v))

        path = []
        cur = end
        while cur in prev:
            path.append(cur)
            cur = prev[cur]
        if cur == start:
            path.append(start)
        return list(reversed(path))


# ── Demo city generator ──────────────────────────────────────────

def generate_brawley_grid() -> Tuple[CityGraph, Dict[str, int]]:
    """Generate a grid city inspired by Brawley, CA layout.
    Returns (graph, poi_map) where poi_map maps names to node IDs."""
    graph = CityGraph()
    ROWS, COLS = 10, 12
    node_id = 0

    pois = {
        (2, 2): ("Home", "home"),
        (7, 9): ("School", "school"),
        (5, 5): ("Park", "park"),
        (1, 8): ("Store", "store"),
        (9, 3): ("Hospital", "hospital"),
        (4, 10): ("Library", "library"),
        (8, 7): ("Donut Avenue", "store"),
        (3, 1): ("Too Cute Kitten Rescue", "park"),
        (6, 4): ("Abe Gonzalez Park", "park"),
    }

    street_names_h = [
        "E St", "D St", "C St", "B St", "Main St",
        "W K St", "Willard Ave", "Webster Rd", "Panno St", "Ronald St",
    ]
    street_names_v = [
        "1st St", "2nd St", "Brandt Rd", "Imperial Ave", "4th St",
        "5th St", "Western Ave", "7th St", "Brawley Ave", "9th St",
        "10th St", "Dogwood Rd",
    ]

    poi_map: Dict[str, int] = {}

    for r in range(ROWS):
        for c in range(COLS):
            x = 0.06 + c * (0.88 / (COLS - 1))
            y = 0.06 + r * (0.88 / (ROWS - 1))
            name = ""
            poi_type = ""
            if (r, c) in pois:
                name, poi_type = pois[(r, c)]
                poi_map[name] = node_id

            node = MapNode(id=node_id, x=x, y=y, name=name, poi_type=poi_type)
            graph.add_node(node)
            node_id += 1

    for r in range(ROWS):
        for c in range(COLS):
            nid = r * COLS + c
            if c < COLS - 1:
                graph.add_edge(nid, nid + 1, street_names_h[r] if r < len(street_names_h) else "")
            if r < ROWS - 1:
                graph.add_edge(nid, nid + COLS, street_names_v[c] if c < len(street_names_v) else "")

    return graph, poi_map


# ── Deviation detection ──────────────────────────────────────────

def check_deviation(graph: CityGraph, entity: TrackedEntity, threshold: float = 0.15) -> TerritoryAlert | None:
    """Check if entity is on a safe pheromone trail. Returns alert if deviating."""
    if entity.current_node >= len(graph.nodes):
        return None
    node = graph.nodes[entity.current_node]

    if node.safe_pheromone < threshold:
        severity = 1.0 - (node.safe_pheromone / max(threshold, 0.01))
        severity = min(1.0, max(0.0, severity))

        if node.danger_pheromone > 0.3:
            severity = min(1.0, severity + 0.3)

        entity.is_deviating = True
        entity.deviation_severity = severity

        return TerritoryAlert(
            timestamp=time.time(),
            entity_name=entity.name,
            alert_type="DEVIATION",
            severity=severity,
            message=f"{entity.name} OFF SAFE TRAIL at node {node.id}"
                    + (f" near {node.name}" if node.name else ""),
            node_id=node.id,
            x=node.x, y=node.y,
        )
    else:
        entity.is_deviating = False
        entity.deviation_severity = 0.0
        return None


def deposit_routine_pheromone(graph: CityGraph, node_id: int, amount: float = 0.05) -> None:
    """Deposit safe pheromone on a node (building the routine trail)."""
    if node_id < len(graph.nodes):
        graph.nodes[node_id].safe_pheromone = min(1.0, graph.nodes[node_id].safe_pheromone + amount)
        graph.nodes[node_id].visit_count += 1
        for e in graph.edges:
            if e.node_a == node_id or e.node_b == node_id:
                e.safe_pheromone = min(1.0, e.safe_pheromone + amount * 0.5)


def flag_danger(graph: CityGraph, node_id: int, amount: float = 0.5) -> None:
    """Flag a node as dangerous."""
    if node_id < len(graph.nodes):
        graph.nodes[node_id].danger_pheromone = min(1.0, graph.nodes[node_id].danger_pheromone + amount)
        for e in graph.edges:
            if e.node_a == node_id or e.node_b == node_id:
                e.danger_pheromone = min(1.0, e.danger_pheromone + amount * 0.5)


def evaporate(graph: CityGraph, safe_decay: float = 0.999, danger_decay: float = 0.995) -> None:
    """Decay pheromones each tick."""
    for n in graph.nodes:
        n.safe_pheromone *= safe_decay
        n.danger_pheromone *= danger_decay
    for e in graph.edges:
        e.safe_pheromone *= safe_decay
        e.danger_pheromone *= danger_decay


# ── Persistence ──────────────────────────────────────────────────

def save_routine(graph: CityGraph) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    data = {str(n.id): n.safe_pheromone for n in graph.nodes if n.safe_pheromone > 0.01}
    ROUTINE_FILE.write_text(json.dumps(data, indent=2))


def load_routine(graph: CityGraph) -> None:
    if not ROUTINE_FILE.exists():
        return
    try:
        data = json.loads(ROUTINE_FILE.read_text())
        for nid_str, val in data.items():
            nid = int(nid_str)
            if nid < len(graph.nodes):
                graph.nodes[nid].safe_pheromone = float(val)
    except Exception:
        pass


def log_alert(alert: TerritoryAlert) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(ALERT_FILE, "a") as f:
        f.write(json.dumps({
            "timestamp": alert.timestamp,
            "entity": alert.entity_name,
            "type": alert.alert_type,
            "severity": alert.severity,
            "message": alert.message,
            "node_id": alert.node_id,
        }) + "\n")
