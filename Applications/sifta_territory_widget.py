#!/usr/bin/env python3
"""
sifta_territory_widget.py — Territory Is The Law
═══════════════════════════════════════════════════
Geospatial Swarm Guardian — the most personal app in the OS.

Track anything with coordinates.  Swimmers map the city.
Routine paths glow green.  Deviations trigger sentinel alerts.
Pathfinders route around danger.  The territory protects what matters.

Four swimmer species visible on the tactical map:
  ◆ RoutineMapper (teal)   — follows entity, deposits safe pheromone
  ◆ DeviationSentinel (amber) — orbits entity, watches for drift
  ◆ Pathfinder (magenta)   — explores graph for optimal safe routes
  ◆ PerimeterGuard (white) — patrols the boundary of the safe zone
"""
from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QPlainTextEdit, QComboBox,
    QCheckBox, QFrame, QSplitter,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from System.sifta_base_widget import SiftaBaseWidget
from System.territory_guardian import (
    CityGraph, MapNode, TrackedEntity, TerritoryAlert,
    generate_brawley_grid, check_deviation, deposit_routine_pheromone,
    flag_danger, evaporate, save_routine, load_routine, log_alert,
)

# ── Palette ──────────────────────────────────────────────────────
BG         = "#060a12"
ROAD_DIM   = "#1a1e2a"
ROAD_SAFE  = "#00ffc8"
ROAD_DANGER= "#ff3366"
POI_HOME   = "#ffdd44"
POI_SCHOOL = "#44aaff"
POI_PARK   = "#44ff88"
POI_STORE  = "#ff8844"
POI_HOSP   = "#ff4488"
ENTITY_CLR = "#ffffff"
ALERT_CLR  = "#ff0033"

MAPPER_CLR   = "#00ffc8"
SENTINEL_CLR = "#ffaa00"
PATHFIND_CLR = "#cc44ff"
GUARD_CLR    = "#aabbdd"


# ── Swimmer agents on the graph ──────────────────────────────────

@dataclass
class GraphSwimmer:
    species: str          # "mapper", "sentinel", "pathfinder", "guard"
    current_node: int = 0
    target_node: int = -1
    progress: float = 0.0  # 0-1 lerp between nodes
    speed: float = 0.02
    trail: List[int] = field(default_factory=list)

    @property
    def color(self) -> str:
        return {"mapper": MAPPER_CLR, "sentinel": SENTINEL_CLR,
                "pathfinder": PATHFIND_CLR, "guard": GUARD_CLR}.get(self.species, "#ffffff")

    @property
    def marker(self) -> str:
        return {"mapper": "D", "sentinel": "^", "pathfinder": "o", "guard": "s"}.get(self.species, "o")


# ── Tactical Map Canvas ─────────────────────────────────────────

class TacticalMapCanvas(FigureCanvas):
    """Matplotlib canvas showing the city graph, pheromone trails, swimmers, and entity."""

    def __init__(self, parent: QWidget | None = None):
        self._fig = Figure(figsize=(14, 10), facecolor=BG, dpi=90)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setMinimumSize(800, 560)
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor(BG)

        self._graph: CityGraph | None = None
        self._entity: TrackedEntity | None = None
        self._swimmers: List[GraphSwimmer] = []
        self._alerts: List[Tuple[float, float, float, float]] = []  # (x, y, severity, age)
        self._tick = 0

    def set_data(self, graph: CityGraph, entity: TrackedEntity, swimmers: List[GraphSwimmer]):
        self._graph = graph
        self._entity = entity
        self._swimmers = swimmers

    def add_alert_flash(self, x: float, y: float, severity: float):
        self._alerts.append((x, y, severity, 0.0))

    def render_frame(self):
        if not self._graph:
            return
        self._tick += 1
        ax = self._ax
        ax.clear()
        ax.set_facecolor(BG)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.set_aspect("equal")
        ax.axis("off")
        g = self._graph

        # ── Draw edges (roads) ──────────────────────────────────
        for e in g.edges:
            na, nb = g.nodes[e.node_a], g.nodes[e.node_b]
            safe = max(e.safe_pheromone, na.safe_pheromone * 0.5, nb.safe_pheromone * 0.5)
            danger = max(e.danger_pheromone, na.danger_pheromone * 0.5, nb.danger_pheromone * 0.5)

            if danger > 0.1:
                color = ROAD_DANGER
                alpha = 0.3 + 0.6 * min(1.0, danger)
                lw = 1.5 + 2.0 * danger
            elif safe > 0.05:
                color = ROAD_SAFE
                alpha = 0.12 + 0.55 * min(1.0, safe)
                lw = 0.8 + 2.5 * safe
            else:
                color = ROAD_DIM
                alpha = 0.25
                lw = 0.5

            ax.plot([na.x, nb.x], [na.y, nb.y], color=color, alpha=alpha, linewidth=lw, zorder=1)

        # ── Draw nodes (intersections) ──────────────────────────
        for n in g.nodes:
            if n.poi_type:
                clr = {
                    "home": POI_HOME, "school": POI_SCHOOL, "park": POI_PARK,
                    "store": POI_STORE, "hospital": POI_HOSP, "library": "#6688ff",
                }.get(n.poi_type, "#ffffff")
                icon = {
                    "home": "H", "school": "S", "park": "P",
                    "store": "$", "hospital": "+", "library": "L",
                }.get(n.poi_type, "?")
                ax.plot(n.x, n.y, "o", color=clr, markersize=12, zorder=5, alpha=0.9)
                ax.text(n.x, n.y, icon, ha="center", va="center",
                        fontsize=7, fontweight="bold", color=BG, zorder=6)
                ax.text(n.x, n.y - 0.035, n.name, ha="center", va="top",
                        fontsize=6, color=clr, alpha=0.8, zorder=6)
            else:
                s = 0.5 + 3.0 * n.safe_pheromone
                c = ROAD_SAFE if n.safe_pheromone > 0.1 else ROAD_DIM
                a = 0.2 + 0.6 * min(1.0, n.safe_pheromone)
                if n.danger_pheromone > 0.1:
                    c = ROAD_DANGER
                    a = 0.4 + 0.5 * min(1.0, n.danger_pheromone)
                ax.plot(n.x, n.y, ".", color=c, markersize=s, alpha=a, zorder=2)

        # ── Draw swimmers ───────────────────────────────────────
        for sw in self._swimmers:
            if sw.current_node >= len(g.nodes):
                continue
            na = g.nodes[sw.current_node]
            sx, sy = na.x, na.y

            if sw.target_node >= 0 and sw.target_node < len(g.nodes):
                nb = g.nodes[sw.target_node]
                sx = na.x + (nb.x - na.x) * sw.progress
                sy = na.y + (nb.y - na.y) * sw.progress

            pulse = 0.6 + 0.4 * math.sin(self._tick * 0.15 + hash(id(sw)) * 0.1)
            ax.plot(sx, sy, sw.marker, color=sw.color, markersize=8, alpha=pulse,
                    markeredgecolor=sw.color, markeredgewidth=1.5, zorder=10)

            if sw.species == "sentinel" and self._entity and self._entity.is_deviating:
                ring_r = 0.015 + 0.005 * math.sin(self._tick * 0.3)
                circ = plt.Circle((sx, sy), ring_r, fill=False, color=ALERT_CLR,
                                  linewidth=1.5, alpha=pulse, zorder=9)
                ax.add_patch(circ)

        # ── Draw tracked entity ─────────────────────────────────
        if self._entity and self._entity.current_node < len(g.nodes):
            en = g.nodes[self._entity.current_node]
            ex, ey = en.x, en.y
            if self._entity.target_node >= 0 and self._entity.target_node < len(g.nodes):
                et = g.nodes[self._entity.target_node]
                ex = en.x + (et.x - en.x) * self._entity.progress
                ey = en.y + (et.y - en.y) * self._entity.progress

            glow = 0.7 + 0.3 * math.sin(self._tick * 0.1)
            if self._entity.is_deviating:
                ecol = ALERT_CLR
                esize = 14 + 3 * math.sin(self._tick * 0.4)
                ring = plt.Circle((ex, ey), 0.025, fill=False, color=ALERT_CLR,
                                  linewidth=2.0, alpha=glow, linestyle="--", zorder=14)
                ax.add_patch(ring)
            else:
                ecol = ENTITY_CLR
                esize = 12

            ax.plot(ex, ey, "*", color=ecol, markersize=esize, alpha=glow,
                    markeredgecolor=ecol, markeredgewidth=0.8, zorder=15)

            ax.text(ex, ey + 0.025, self._entity.name, ha="center", va="bottom",
                    fontsize=8, fontweight="bold", color=ecol, alpha=0.9, zorder=16)

        # ── Alert flashes ───────────────────────────────────────
        new_alerts = []
        for (ax_, ay_, sev, age) in self._alerts:
            age += 0.05
            if age < 1.0:
                new_alerts.append((ax_, ay_, sev, age))
                ring_r = 0.02 + 0.04 * age
                alpha = (1.0 - age) * sev
                circ = plt.Circle((ax_, ay_), ring_r, fill=False, color=ALERT_CLR,
                                  linewidth=2.0, alpha=alpha, zorder=20)
                ax.add_patch(circ)
        self._alerts = new_alerts

        # ── HUD overlay ─────────────────────────────────────────
        safe_coverage = sum(1 for n in g.nodes if n.safe_pheromone > 0.1) / max(1, len(g.nodes))
        danger_nodes = sum(1 for n in g.nodes if n.danger_pheromone > 0.3)
        dev_txt = "DEVIATING" if self._entity and self._entity.is_deviating else "ON TRAIL"
        dev_col = ALERT_CLR if self._entity and self._entity.is_deviating else ROAD_SAFE

        hud_lines = [
            f"TERRITORY IS THE LAW",
            f"Safe coverage: {safe_coverage*100:.0f}%  |  Danger zones: {danger_nodes}",
            f"Entity: {dev_txt}  |  Swimmers: {len(self._swimmers)}  |  Tick: {self._tick}",
        ]
        for i, line in enumerate(hud_lines):
            c = "#00ffc8" if i == 0 else "#8090b0"
            fs = 9 if i == 0 else 7
            ax.text(0.01, 0.99 - i * 0.035, line, transform=ax.transAxes,
                    fontsize=fs, fontfamily="monospace", color=c, alpha=0.9,
                    va="top", ha="left", zorder=30)

        # Legend
        legend_items = [
            ("D", MAPPER_CLR, "RoutineMapper"),
            ("^", SENTINEL_CLR, "DeviationSentinel"),
            ("o", PATHFIND_CLR, "Pathfinder"),
            ("s", GUARD_CLR, "PerimeterGuard"),
            ("*", ENTITY_CLR, "Tracked Entity"),
        ]
        for i, (mk, cl, lb) in enumerate(legend_items):
            ax.text(0.99, 0.99 - i * 0.03, f"{mk} {lb}", transform=ax.transAxes,
                    fontsize=6, fontfamily="monospace", color=cl, alpha=0.8,
                    va="top", ha="right", zorder=30)

        self._fig.tight_layout(pad=0.5)
        self.draw_idle()


# ── Main Widget ─────────────────────────────────────────────────

class TerritoryWidget(SiftaBaseWidget):
    """Territory Is The Law — Geospatial Swarm Guardian."""
    APP_NAME = "Territory Is The Law"

    def build_ui(self, layout: QVBoxLayout) -> None:
        # ── Controls row ────────────────────────────────────────
        ctrl = QHBoxLayout()

        self._btn_start = QPushButton("Start Patrol")
        self._btn_start.clicked.connect(self._toggle_patrol)
        ctrl.addWidget(self._btn_start)

        self._btn_deviate = QPushButton("Inject Deviation")
        self._btn_deviate.clicked.connect(self._inject_deviation)
        self._btn_deviate.setToolTip("Force entity off safe trail")
        ctrl.addWidget(self._btn_deviate)

        self._btn_hazard = QPushButton("Flag Hazard")
        self._btn_hazard.clicked.connect(self._flag_random_hazard)
        self._btn_hazard.setToolTip("Place danger pheromone on a random node")
        ctrl.addWidget(self._btn_hazard)

        self._btn_route = QPushButton("Safest Route")
        self._btn_route.clicked.connect(self._show_safest_route)
        self._btn_route.setToolTip("Calculate safest route avoiding danger zones")
        ctrl.addWidget(self._btn_route)

        ctrl.addStretch()

        self._chk_auto = QCheckBox("Auto-patrol (loop routine)")
        self._chk_auto.setChecked(True)
        ctrl.addWidget(self._chk_auto)

        self._combo_entity = QComboBox()
        self._combo_entity.addItems(["Lana", "Dog (Max)", "AirTag-1", "Phone-backup"])
        self._combo_entity.currentTextChanged.connect(self._change_entity)
        ctrl.addWidget(QLabel("Tracking:"))
        ctrl.addWidget(self._combo_entity)

        layout.addLayout(ctrl)

        # ── Splitter: map + alert log ───────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._canvas = TacticalMapCanvas()
        splitter.addWidget(self._canvas)

        self._alert_log = QPlainTextEdit()
        self._alert_log.setReadOnly(True)
        self._alert_log.setMaximumWidth(360)
        self._alert_log.setPlaceholderText("Alert log...")
        splitter.addWidget(self._alert_log)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        # ── Initialize graph + entity + swimmers ────────────────
        self._graph, self._pois = generate_brawley_grid()
        load_routine(self._graph)

        home_id = self._pois.get("Home", 0)
        self._entity = TrackedEntity(name="Lana", icon="*", current_node=home_id)

        self._swimmers: List[GraphSwimmer] = []
        self._spawn_swimmers()

        self._canvas.set_data(self._graph, self._entity, self._swimmers)

        self._route_highlight: List[int] = []
        self._routine_path: List[int] = []
        self._build_routine()

        self._entity_route_idx = 0
        self._patrol_running = False
        self._deviation_active = False
        self._deviation_ticks = 0
        self._tick = 0

        self._timer: QTimer | None = None
        self._canvas.render_frame()
        self.set_status("Ready — click Start Patrol")

    def _spawn_swimmers(self):
        g = self._graph
        n = len(g.nodes)
        home_id = self._pois.get("Home", 0)

        for _ in range(4):
            self._swimmers.append(GraphSwimmer(
                species="mapper", current_node=home_id, speed=0.04 + random.random() * 0.02))
        for _ in range(3):
            self._swimmers.append(GraphSwimmer(
                species="sentinel", current_node=home_id, speed=0.03 + random.random() * 0.02))
        for _ in range(3):
            self._swimmers.append(GraphSwimmer(
                species="pathfinder", current_node=random.randint(0, n - 1), speed=0.05))

        boundary = [i for i, nd in enumerate(g.nodes)
                     if nd.x < 0.1 or nd.x > 0.9 or nd.y < 0.1 or nd.y > 0.9]
        for _ in range(3):
            start = random.choice(boundary) if boundary else 0
            self._swimmers.append(GraphSwimmer(
                species="guard", current_node=start, speed=0.03))

    def _build_routine(self):
        """Build the demo routine: Home → School → Park → Store → Home."""
        path_segments = [
            ("Home", "School"),
            ("School", "Abe Gonzalez Park"),
            ("Abe Gonzalez Park", "Store"),
            ("Store", "Home"),
        ]
        full_path = []
        for start_name, end_name in path_segments:
            sid = self._pois.get(start_name, 0)
            eid = self._pois.get(end_name, 0)
            segment = self._graph.shortest_path(sid, eid, avoid_danger=False)
            if full_path and segment and full_path[-1] == segment[0]:
                segment = segment[1:]
            full_path.extend(segment)
        self._routine_path = full_path

        for nid in self._routine_path:
            deposit_routine_pheromone(self._graph, nid, 0.25)

    # ── Controls ────────────────────────────────────────────────

    def _toggle_patrol(self):
        if self._patrol_running:
            self._patrol_running = False
            if self._timer:
                self._timer.stop()
                self._timer = None
            self._btn_start.setText("Start Patrol")
            self.set_status("Patrol paused")
        else:
            self._patrol_running = True
            self._timer = self.make_timer(80, self._tick_step)
            self._btn_start.setText("Stop Patrol")
            self.set_status("Patrol active")

    def _inject_deviation(self):
        """Force entity off the safe trail into uncharted territory."""
        if not self._patrol_running:
            self._log_alert_text("Start patrol first.")
            return
        g = self._graph
        n = len(g.nodes)
        unsafe = [i for i in range(n) if g.nodes[i].safe_pheromone < 0.05]
        if not unsafe:
            unsafe = list(range(n))
        target = random.choice(unsafe)
        self._entity.current_node = target
        self._entity.target_node = -1
        self._entity.progress = 0.0
        self._deviation_active = True
        self._deviation_ticks = 0
        self._log_alert_text(f"DEVIATION INJECTED — entity moved to node {target}")

    def _flag_random_hazard(self):
        """Place danger pheromone on a random cluster of nodes."""
        g = self._graph
        center = random.randint(0, len(g.nodes) - 1)
        flag_danger(g, center, 0.8)
        for nb in g.neighbors(center):
            flag_danger(g, nb, 0.4)
        node = g.nodes[center]
        self._log_alert_text(f"HAZARD flagged at node {center} ({node.x:.2f}, {node.y:.2f})")

    def _show_safest_route(self):
        """Calculate and highlight safest route from entity to Home."""
        home_id = self._pois.get("Home", 0)
        path = self._graph.shortest_path(self._entity.current_node, home_id, avoid_danger=True)
        self._route_highlight = path
        names = []
        for nid in path:
            n = self._graph.nodes[nid]
            if n.name:
                names.append(n.name)
        self._log_alert_text(f"SAFEST ROUTE ({len(path)} hops): {' → '.join(names) if names else 'direct'}")

    def _change_entity(self, name: str):
        self._entity.name = name

    # ── Simulation tick ─────────────────────────────────────────

    def _tick_step(self):
        self._tick += 1
        g = self._graph

        evaporate(g, safe_decay=0.9995, danger_decay=0.998)

        self._move_entity()
        self._move_swimmers()

        alert = check_deviation(g, self._entity, threshold=0.10)
        if alert:
            self._canvas.add_alert_flash(alert.x, alert.y, alert.severity)
            self._log_alert_text(
                f"[{alert.alert_type}] sev={alert.severity:.2f} — {alert.message}")
            log_alert(alert)

        if self._tick % 50 == 0:
            save_routine(g)

        safe_ct = sum(1 for n in g.nodes if n.safe_pheromone > 0.1)
        danger_ct = sum(1 for n in g.nodes if n.danger_pheromone > 0.3)
        dev = "DEVIATING" if self._entity.is_deviating else "SAFE"
        self.set_status(f"Tick {self._tick} | {dev} | Safe: {safe_ct} | Danger: {danger_ct}")

        self._canvas.render_frame()

    def _move_entity(self):
        """Move entity along the routine path (or wander if deviating)."""
        g = self._graph
        ent = self._entity

        if self._deviation_active:
            self._deviation_ticks += 1
            if self._deviation_ticks > 40:
                self._deviation_active = False
                home_id = self._pois.get("Home", 0)
                path = g.shortest_path(ent.current_node, home_id, avoid_danger=True)
                self._entity_route_idx = 0
                self._routine_path = path
                self._log_alert_text("Entity returning to safe territory via safest route")
            else:
                nbrs = g.neighbors(ent.current_node)
                if nbrs:
                    unsafe_nbrs = [n for n in nbrs if g.nodes[n].safe_pheromone < 0.05]
                    pick = random.choice(unsafe_nbrs if unsafe_nbrs else nbrs)
                    ent.current_node = pick
                    ent.target_node = -1
                    ent.progress = 0.0
                return

        if not self._routine_path:
            return

        if ent.target_node < 0:
            if self._entity_route_idx < len(self._routine_path):
                ent.target_node = self._routine_path[self._entity_route_idx]
            else:
                if self._chk_auto.isChecked():
                    self._entity_route_idx = 0
                    self._build_routine()
                    ent.target_node = self._routine_path[0] if self._routine_path else -1
                return

        ent.progress += 0.04
        if ent.progress >= 1.0:
            ent.current_node = ent.target_node
            ent.progress = 0.0
            deposit_routine_pheromone(g, ent.current_node, 0.03)
            self._entity_route_idx += 1
            if self._entity_route_idx < len(self._routine_path):
                ent.target_node = self._routine_path[self._entity_route_idx]
            else:
                ent.target_node = -1

    def _move_swimmers(self):
        g = self._graph
        for sw in self._swimmers:
            if sw.target_node < 0:
                self._pick_swimmer_target(sw)

            sw.progress += sw.speed
            if sw.progress >= 1.0:
                sw.current_node = sw.target_node
                sw.progress = 0.0
                sw.target_node = -1
                sw.trail.append(sw.current_node)
                if len(sw.trail) > 60:
                    sw.trail = sw.trail[-40:]

                if sw.species == "mapper":
                    deposit_routine_pheromone(g, sw.current_node, 0.01)

    def _pick_swimmer_target(self, sw: GraphSwimmer):
        g = self._graph
        nbrs = g.neighbors(sw.current_node)
        if not nbrs:
            return

        if sw.species == "mapper":
            if self._entity:
                path = g.shortest_path(sw.current_node, self._entity.current_node, avoid_danger=True)
                if len(path) >= 2:
                    sw.target_node = path[1]
                    return
            sw.target_node = random.choice(nbrs)

        elif sw.species == "sentinel":
            if self._entity and self._entity.is_deviating:
                path = g.shortest_path(sw.current_node, self._entity.current_node, avoid_danger=False)
                if len(path) >= 2:
                    sw.target_node = path[1]
                    return
            if self._entity:
                en = self._entity.current_node
                en_nbrs = g.neighbors(en)
                orbit_targets = en_nbrs + [en]
                best = min(orbit_targets, key=lambda n: abs(
                    math.sqrt((g.nodes[n].x - g.nodes[sw.current_node].x)**2 +
                              (g.nodes[n].y - g.nodes[sw.current_node].y)**2) - 0.08))
                path = g.shortest_path(sw.current_node, best, avoid_danger=False)
                if len(path) >= 2:
                    sw.target_node = path[1]
                    return
            sw.target_node = random.choice(nbrs)

        elif sw.species == "pathfinder":
            unvisited = [n for n in nbrs if g.nodes[n].safe_pheromone < 0.1
                         and n not in sw.trail[-10:]]
            if unvisited:
                sw.target_node = random.choice(unvisited)
            else:
                sw.target_node = random.choice(nbrs)

        elif sw.species == "guard":
            boundary = [n for n in nbrs
                        if g.nodes[n].x < 0.12 or g.nodes[n].x > 0.88
                        or g.nodes[n].y < 0.12 or g.nodes[n].y > 0.88]
            if boundary:
                sw.target_node = random.choice(boundary)
            else:
                sw.target_node = random.choice(nbrs)

    # ── Alert log ───────────────────────────────────────────────

    def _log_alert_text(self, msg: str):
        t = time.strftime("%H:%M:%S")
        self._alert_log.appendPlainText(f"[{t}] {msg}")
        sb = self._alert_log.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())


# ── Standalone launch ────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = TerritoryWidget()
    w.setWindowTitle("Territory Is The Law — Geospatial Swarm Guardian")
    w.resize(1400, 900)
    w.show()
    sys.exit(app.exec())
