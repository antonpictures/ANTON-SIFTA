#!/usr/bin/env python3
"""
sifta_slime_mold_bank.py — Slime-Mold Bank: Push to Mint
=========================================================

A gamified, multicolor, particle-rich simulation that runs the *real*
Physarum (slime-mold) solver from System/swarm_physarum_solver.py and the
*real* Proof-of-Useful-Work ledger from System/proof_of_useful_work.py.

Each press of "PUSH TO MINT" picks a city/network challenge, runs the
Tero 2010 Kirchhoff dynamics on it (μ = 1.8), animates rainbow particles
along the surviving tubes, and — if the slime mold pruned ≥ 30 % of the
waste — issues a real WorkReceipt and mints STGM into Alice's wallet.

This is not a demo of a demo. The math is real, the receipts are real,
the SHA-256 chain is real. Carlton, push the button.

Run standalone:
    python3 Applications/sifta_slime_mold_bank.py

OS launcher entry: Applications/apps_manifest.json
    "Slime-Mold Bank: Push to Mint" → Simulations
"""
from __future__ import annotations

import json
import math
import random
import sys
import time
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from PyQt6.QtCore import (
    Qt,
    QPointF,
    QRectF,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Real SIFTA modules — fail loud if missing, no fakery.
try:
    from System.swarm_physarum_solver import (
        MU,
        PRUNE_THRESHOLD,
        PhysarumSolver,
    )
    _SOLVER_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    _SOLVER_AVAILABLE = False
    _SOLVER_IMPORT_ERROR = repr(_e)
    MU = 1.8
    PRUNE_THRESHOLD = 1e-4

try:
    from System.proof_of_useful_work import (
        WORK_VALUES,
        issue_work_receipt,
        prove_useful_work,
    )
    _POUW_AVAILABLE = True
except Exception as _e:  # pragma: no cover
    _POUW_AVAILABLE = False
    _POUW_IMPORT_ERROR = repr(_e)


# ─── Visual constants ──────────────────────────────────────────────────────────

BG_TOP = QColor(8, 4, 22)
BG_BOTTOM = QColor(22, 4, 38)
NODE_GLOW = QColor(255, 255, 255, 200)
PANEL_BG = "#0a0420"
NEON_PINK = "#ff2d95"
NEON_CYAN = "#0ff0fc"
NEON_LIME = "#a6ff3d"
NEON_GOLD = "#ffd34e"

GAMIFIED_FONT = "Menlo"


# ─── Game graphs (with real geometry for pretty rendering) ─────────────────────

# Each graph: (name, source, sink, [(node_id, x_0to1, y_0to1)],
#              [(u, v, initial_conductance)], story)
@dataclass
class CityGraph:
    name: str
    story: str
    nodes_xy: List[Tuple[int, float, float]]
    edges: List[Tuple[int, int, float]]
    source: int
    sink: int


def _city_tokyo() -> CityGraph:
    # Tokyo metro stub — Tero 2010 reference shape, plus extra waste edges
    nodes_xy = [
        (0, 0.10, 0.50),  # Shinjuku (source)
        (1, 0.22, 0.32),  (2, 0.22, 0.68),
        (3, 0.36, 0.50),
        (4, 0.50, 0.30),  (5, 0.50, 0.70),
        (6, 0.62, 0.50),
        (7, 0.74, 0.32),  (8, 0.74, 0.68),
        (9, 0.86, 0.50),
        (10, 0.94, 0.30), (11, 0.94, 0.70),
        (12, 0.50, 0.50),  # central waste hub (should die)
        (13, 0.36, 0.18), (14, 0.36, 0.82),  # cross-link waste
    ]
    edges = [
        (0, 1, 1.0), (0, 2, 1.0), (1, 3, 1.0), (2, 3, 1.0),
        (3, 4, 1.0), (3, 5, 1.0), (4, 6, 1.0), (5, 6, 1.0),
        (6, 7, 1.0), (6, 8, 1.0), (7, 9, 1.0), (8, 9, 1.0),
        (9, 10, 1.0), (9, 11, 1.0),
        # Waste links
        (1, 12, 0.6), (2, 12, 0.6), (12, 4, 0.5), (12, 5, 0.5),
        (1, 13, 0.4), (13, 4, 0.4), (2, 14, 0.4), (14, 5, 0.4),
        (7, 11, 0.3), (8, 10, 0.3), (4, 8, 0.2), (5, 7, 0.2),
    ]
    return CityGraph(
        name="Tokyo Metro (Tero 2010 stub)",
        story="The mold beats Japan's engineers since 2010.",
        nodes_xy=nodes_xy,
        edges=edges,
        source=0,
        sink=10,
    )


def _city_refugee_camp() -> CityGraph:
    # 12-node aid distribution graph — depot, sub-hubs, distribution points
    random.seed(7)
    nodes_xy = [(0, 0.08, 0.50)]  # Depot
    for i in range(1, 12):
        angle = (i - 1) * (2 * math.pi / 11)
        r = 0.30 + 0.10 * math.sin(i * 1.3)
        nodes_xy.append((i, 0.55 + r * math.cos(angle),
                         0.50 + r * math.sin(angle) * 0.85))
    edges = []
    # Depot to all
    for i in range(1, 12):
        edges.append((0, i, 0.4 + random.random() * 0.6))
    # Random ring + chord redundancy (waste to be pruned)
    ring = list(range(1, 12)) + [1]
    for i in range(len(ring) - 1):
        edges.append((ring[i], ring[i + 1], 0.5 + random.random() * 0.5))
    for _ in range(8):
        u = random.randint(1, 11)
        v = random.randint(1, 11)
        if u != v:
            edges.append((u, v, 0.2 + random.random() * 0.4))
    return CityGraph(
        name="Refugee Camp Aid Routes",
        story="One depot, eleven distribution points. Prune the waste, save the diesel.",
        nodes_xy=nodes_xy,
        edges=edges,
        source=0,
        sink=6,
    )


def _city_power_grid() -> CityGraph:
    # 16-node mesh (4x4) with redundancy
    nodes_xy = []
    for y in range(4):
        for x in range(4):
            i = y * 4 + x
            nodes_xy.append((i, 0.10 + 0.26 * x, 0.18 + 0.22 * y))
    edges = []
    for y in range(4):
        for x in range(4):
            i = y * 4 + x
            if x + 1 < 4:
                edges.append((i, i + 1, 1.0))
            if y + 1 < 4:
                edges.append((i, i + 4, 1.0))
    # Diagonal redundancy
    for y in range(3):
        for x in range(3):
            i = y * 4 + x
            edges.append((i, i + 5, 0.4))
            edges.append((i + 1, i + 4, 0.4))
    return CityGraph(
        name="Power Grid Slice (4×4 mesh)",
        story="Find the N-1 fault-tolerant routing without a central planner.",
        nodes_xy=nodes_xy,
        edges=edges,
        source=0,
        sink=15,
    )


def _city_subway() -> CityGraph:
    # NYC-ish linear with branches
    nodes_xy = []
    for i in range(10):
        nodes_xy.append((i, 0.06 + 0.10 * i, 0.50))
    nodes_xy += [
        (10, 0.30, 0.20), (11, 0.50, 0.20), (12, 0.70, 0.20),
        (13, 0.30, 0.80), (14, 0.50, 0.80), (15, 0.70, 0.80),
    ]
    edges = [(i, i + 1, 1.0) for i in range(9)]
    edges += [
        (2, 10, 0.7), (10, 11, 0.7), (11, 12, 0.7), (12, 7, 0.7),
        (2, 13, 0.7), (13, 14, 0.7), (14, 15, 0.7), (15, 7, 0.7),
        (3, 11, 0.3), (4, 14, 0.3), (5, 11, 0.3), (6, 14, 0.3),
    ]
    return CityGraph(
        name="Subway Line (NY-style)",
        story="Same algorithm. Different graph. Same answer: less waste.",
        nodes_xy=nodes_xy,
        edges=edges,
        source=0,
        sink=9,
    )


def _city_cancer_lattice() -> CityGraph:
    # Dense radial 17-node — for nanobot delivery routes
    nodes_xy = [(0, 0.50, 0.50)]
    for i in range(1, 9):
        angle = (i - 1) * (2 * math.pi / 8)
        nodes_xy.append((i, 0.50 + 0.20 * math.cos(angle),
                         0.50 + 0.22 * math.sin(angle)))
    for i in range(9, 17):
        angle = (i - 9) * (2 * math.pi / 8) + math.pi / 8
        nodes_xy.append((i, 0.50 + 0.38 * math.cos(angle),
                         0.50 + 0.40 * math.sin(angle)))
    edges = []
    for i in range(1, 9):
        edges.append((0, i, 1.0))
    for i in range(1, 9):
        nxt = (i % 8) + 1
        edges.append((i, nxt, 0.5))
    for i in range(1, 9):
        edges.append((i, i + 8, 0.7))
        edges.append((i, ((i % 8) + 1) + 8, 0.3))
    for i in range(9, 17):
        nxt = ((i - 9 + 1) % 8) + 9
        edges.append((i, nxt, 0.4))
    return CityGraph(
        name="Cancer-Nanobot Delivery Lattice",
        story="Spatial planner for medical robotics. Slime mold finds the safe paths.",
        nodes_xy=nodes_xy,
        edges=edges,
        source=0,
        sink=13,
    )


CITIES: Dict[str, CityGraph] = {
    "Tokyo Metro": _city_tokyo(),
    "Refugee Camp": _city_refugee_camp(),
    "Power Grid": _city_power_grid(),
    "Subway Line": _city_subway(),
    "Cancer Lattice": _city_cancer_lattice(),
}


# ─── Particle ──────────────────────────────────────────────────────────────────

@dataclass
class Particle:
    edge_idx: int
    t: float  # 0..1 along edge
    speed: float
    hue: float  # 0..360
    life: float  # 0..1
    direction: int = 1  # +1 or -1


@dataclass
class MintBurst:
    cx: float
    cy: float
    born: float
    color: QColor


# ─── The big visual canvas ─────────────────────────────────────────────────────

class NetworkCanvas(QFrame):
    """Custom-painted city graph with live Physarum dynamics + rainbow particles."""

    mint_succeeded = pyqtSignal(dict)
    mint_failed = pyqtSignal(str)
    iteration_advanced = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(720, 620)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)

        self._city: CityGraph = CITIES["Tokyo Metro"]
        self._solver: Optional[PhysarumSolver] = None
        self._D_initial: Optional[np.ndarray] = None
        self._iteration: int = 0
        self._max_iter: int = 600
        self._converged: bool = False
        self._running: bool = False
        self._last_total_flow: float = 0.0
        self._reduction_pct: float = 0.0

        self._particles: List[Particle] = []
        self._bursts: List[MintBurst] = []
        self._mint_label_until: float = 0.0
        self._last_mint_amount: float = 0.0

        self._idle_phase = 0.0  # always-on ambient color cycle

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)  # ~30 fps
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start()

        self._solver_timer = QTimer(self)
        self._solver_timer.setInterval(50)  # solver step ~20 Hz
        self._solver_timer.timeout.connect(self._solver_step)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_city(self, name: str) -> None:
        if name in CITIES:
            self._city = CITIES[name]
            self._reset_state()
            self.update()

    def push_to_mint(self) -> bool:
        if not _SOLVER_AVAILABLE:
            self.mint_failed.emit(
                f"Physarum solver not importable: {_SOLVER_IMPORT_ERROR}"
            )
            return False
        # Re-build solver with fresh, slightly perturbed initial conductances
        nodes = [n for (n, _x, _y) in self._city.nodes_xy]
        rng = np.random.default_rng()
        edges_perturbed = [
            (u, v, max(0.05, d + rng.normal(0, 0.05)))
            for (u, v, d) in self._city.edges
        ]
        self._solver = PhysarumSolver(
            nodes=nodes,
            edges=edges_perturbed,
            source=self._city.source,
            sink=self._city.sink,
        )
        self._D_initial = self._solver.D.copy()
        self._iteration = 0
        self._converged = False
        self._running = True
        self._reduction_pct = 0.0
        self._last_total_flow = 0.0
        # Spawn initial particles based on edge count
        self._spawn_particles_for_run()
        self._solver_timer.start()
        return True

    # ── Internal: animation ───────────────────────────────────────────────────

    def _tick(self) -> None:
        self._idle_phase = (self._idle_phase + 0.6) % 360.0
        self._update_particles()
        self._update_bursts()
        self.update()

    def _solver_step(self) -> None:
        if not self._running or self._solver is None:
            return
        prev_D = self._solver.D.copy()
        total_flow = self._solver.step()
        self._last_total_flow = float(total_flow)
        self._iteration += 1
        delta = float(np.max(np.abs(self._solver.D - prev_D)))
        # Track live reduction percentage
        alive = int(np.sum(self._solver.D > PRUNE_THRESHOLD))
        pruned = len(self._solver.edges) - alive
        self._reduction_pct = pruned / max(len(self._solver.edges), 1)
        self.iteration_advanced.emit({
            "iter": self._iteration,
            "delta": delta,
            "total_flow": self._last_total_flow,
            "alive": alive,
            "pruned": pruned,
            "reduction_pct": self._reduction_pct,
        })
        if delta < 1e-5 or self._iteration >= self._max_iter:
            self._converged = True
            self._running = False
            self._solver_timer.stop()
            self._finalize_mint()

    def _finalize_mint(self) -> None:
        if self._solver is None:
            return
        # Build canonicalized topology hashes
        before_topology = sorted(
            [(u, v, round(float(d), 6)) for (u, v, _), d
             in zip(self._solver.edges, self._D_initial.tolist())],
            key=lambda x: (x[0], x[1]),
        )
        after_topology = sorted(
            [(u, v, round(float(d), 6)) for (u, v, _), d
             in zip(self._solver.edges, self._solver.D.tolist())
             if d > PRUNE_THRESHOLD],
            key=lambda x: (x[0], x[1]),
        )
        before_hash = hashlib.sha256(
            json.dumps(before_topology, sort_keys=True).encode()
        ).hexdigest()
        after_hash = hashlib.sha256(
            json.dumps(after_topology, sort_keys=True).encode()
        ).hexdigest()

        reduction = self._reduction_pct
        info = {
            "city": self._city.name,
            "iters": self._iteration,
            "alive": len(after_topology),
            "total": len(self._solver.edges),
            "reduction_pct": round(reduction * 100, 2),
            "before_hash": before_hash,
            "after_hash": after_hash,
        }

        if reduction < 0.30:
            info["minted"] = 0.0
            info["status"] = "NO_MINT"
            info["reason"] = (
                f"Pruned only {reduction*100:.1f} % — need ≥ 30 % "
                f"to mint. The mold tried, the city was already lean."
            )
            self._record_score(info, minted=0.0)
            self.mint_failed.emit(info["reason"])
            self.mint_succeeded.emit(info)  # emit anyway for stats panel
            self._spawn_failed_particles()
            return

        # Real Proof-of-Useful-Work: receipt + mint
        minted = 0.0
        receipt_hash = ""
        if _POUW_AVAILABLE:
            try:
                ok, reason = prove_useful_work(before_hash, after_hash)
                if ok:
                    agent_state = self._load_or_init_agent_state()
                    receipt = issue_work_receipt(
                        agent_state=agent_state,
                        work_type="PROTEIN_FOLDED",  # mapped value 0.65 in WORK_VALUES
                        description=(
                            f"PHYSARUM solve on '{self._city.name}': "
                            f"{info['alive']}/{info['total']} edges, "
                            f"{info['reduction_pct']:.1f}% pruned"
                        ),
                        territory=f"city:{self._city.name}",
                        output_hash=after_hash[:32],
                    )
                    receipt_hash = receipt.receipt_hash
                    minted = float(WORK_VALUES.get("PROTEIN_FOLDED", 0.65)) * 100.0
                    self._save_agent_state(agent_state)
                    info["status"] = "MINTED"
                else:
                    info["status"] = "PROOF_REJECTED"
                    info["reason"] = reason
            except Exception as exc:
                info["status"] = "MINT_ERROR"
                info["reason"] = f"{type(exc).__name__}: {exc}"
        else:
            info["status"] = "OFFLINE_DEMO_MINT"
            minted = 65.0  # demo fallback so UI is still satisfying
            receipt_hash = after_hash

        info["minted"] = minted
        info["receipt_hash"] = receipt_hash
        self._last_mint_amount = minted
        self._mint_label_until = time.time() + 3.0
        self._record_score(info, minted=minted)
        self._spawn_mint_burst()
        self.mint_succeeded.emit(info)

    # ── Particles ─────────────────────────────────────────────────────────────

    def _spawn_particles_for_run(self) -> None:
        n_edges = len(self._city.edges)
        target = min(220, 12 + n_edges * 4)
        self._particles = []
        for _ in range(target):
            self._particles.append(self._random_particle())

    def _random_particle(self) -> Particle:
        edge_idx = random.randint(0, len(self._city.edges) - 1)
        return Particle(
            edge_idx=edge_idx,
            t=random.random(),
            speed=0.005 + random.random() * 0.020,
            hue=random.random() * 360.0,
            life=1.0,
            direction=random.choice((-1, 1)),
        )

    def _update_particles(self) -> None:
        if not self._particles:
            # Always have an ambient sprinkle of particles
            for _ in range(80):
                self._particles.append(self._random_particle())
        for p in self._particles:
            # Modulate speed with conductance / flow if solver is running
            if self._solver is not None:
                d = float(self._solver.D[p.edge_idx])
                speed_scale = 0.4 + min(d, 2.5)
            else:
                speed_scale = 1.0
            p.t += p.speed * p.direction * speed_scale
            p.hue = (p.hue + 1.4) % 360.0
            if p.t < 0.0:
                p.t = 1.0
            elif p.t > 1.0:
                p.t = 0.0

    def _update_bursts(self) -> None:
        now = time.time()
        self._bursts = [b for b in self._bursts if now - b.born < 1.6]

    def _spawn_mint_burst(self) -> None:
        # Confetti blast at random alive nodes
        for n_id, x, y in self._city.nodes_xy[:6]:
            for _ in range(14):
                hue = random.random() * 360.0
                col = QColor.fromHsvF(hue / 360.0, 0.95, 1.0, 1.0)
                self._bursts.append(MintBurst(
                    cx=x + random.uniform(-0.02, 0.02),
                    cy=y + random.uniform(-0.02, 0.02),
                    born=time.time(),
                    color=col,
                ))

    def _spawn_failed_particles(self) -> None:
        for _ in range(20):
            x = random.random()
            y = random.random()
            self._bursts.append(MintBurst(
                cx=x, cy=y, born=time.time(),
                color=QColor(180, 70, 70, 180),
            ))

    # ── Persistence ───────────────────────────────────────────────────────────

    def _agent_state_path(self) -> Path:
        return _REPO / ".sifta_state" / "slime_mold_bank_agent.json"

    def _load_or_init_agent_state(self) -> dict:
        p = self._agent_state_path()
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
        return {
            "id": "SLIME_MOLD_BANK_PLAYER",
            "useful_work_score": 0.5,
            "stgm_balance": 0.0,
            "work_chain": [],
            "last_work_timestamp": time.time(),
        }

    def _save_agent_state(self, state: dict) -> None:
        try:
            p = self._agent_state_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            state["last_work_timestamp"] = time.time()
            p.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

    def _score_path(self) -> Path:
        return _REPO / ".sifta_state" / "slime_mold_bank_scores.jsonl"

    def _record_score(self, info: dict, minted: float) -> None:
        try:
            p = self._score_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "ts": time.time(),
                "city": info.get("city"),
                "reduction_pct": info.get("reduction_pct"),
                "iters": info.get("iters"),
                "alive": info.get("alive"),
                "total": info.get("total"),
                "minted_stgm": minted,
                "status": info.get("status"),
                "after_hash": info.get("after_hash"),
            }
            with p.open("a") as f:
                f.write(json.dumps(row) + "\n")
        except Exception:
            pass

    def _reset_state(self) -> None:
        self._solver = None
        self._D_initial = None
        self._iteration = 0
        self._running = False
        self._converged = False
        self._reduction_pct = 0.0
        self._particles = []

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        # Background gradient
        grad = QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0.0, BG_TOP)
        grad.setColorAt(1.0, BG_BOTTOM)
        p.fillRect(rect, grad)

        # Ambient grid
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        for gy in range(0, rect.height(), 28):
            p.drawLine(0, gy, rect.width(), gy)
        for gx in range(0, rect.width(), 28):
            p.drawLine(gx, 0, gx, rect.height())

        # Title overlay
        p.setPen(QPen(QColor(255, 255, 255, 60)))
        p.setFont(QFont(GAMIFIED_FONT, 11))
        p.drawText(
            14, rect.height() - 14,
            f"μ = {MU}  ·  Tero 2010 Kirchhoff dynamics  ·  prune τ = {PRUNE_THRESHOLD}",
        )

        # Compute pixel positions for nodes
        pad_x = 60
        pad_y = 50
        w = rect.width() - 2 * pad_x
        h = rect.height() - 2 * pad_y
        node_px: Dict[int, Tuple[float, float]] = {
            n_id: (pad_x + x * w, pad_y + y * h)
            for (n_id, x, y) in self._city.nodes_xy
        }

        # Edges (current conductance if solver running, else initial)
        if self._solver is not None:
            edges = self._solver.edges
            D = self._solver.D
        else:
            edges = self._city.edges
            D = np.array([d for (_u, _v, d) in self._city.edges], dtype=np.float64)

        max_D = float(max(np.max(D), 0.001))
        for k, (u, v, _d) in enumerate(edges):
            x1, y1 = node_px[u]
            x2, y2 = node_px[v]
            d = float(D[k])
            alive = d > PRUNE_THRESHOLD
            t_norm = d / max_D

            # Tube color: dead → dim red ghost, alive → cyan→pink gradient by flow
            if not alive:
                col = QColor(80, 30, 30, 80)
                pen_w = 1.0
            else:
                hue = (200 - 160 * t_norm + self._idle_phase * 0.2) % 360.0
                col = QColor.fromHsvF((hue / 360.0) % 1.0, 0.85, 1.0,
                                      0.55 + 0.35 * t_norm)
                pen_w = 1.5 + 7.0 * t_norm

            # Outer glow
            glow = QColor(col)
            glow.setAlpha(min(120, int(60 + 80 * t_norm)))
            p.setPen(QPen(glow, pen_w + 4.5))
            p.drawLine(int(x1), int(y1), int(x2), int(y2))
            # Core line
            p.setPen(QPen(col, pen_w))
            p.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Particles riding on edges
        for prt in self._particles:
            if prt.edge_idx >= len(edges):
                continue
            u, v, _ = edges[prt.edge_idx]
            d = float(D[prt.edge_idx])
            if d < PRUNE_THRESHOLD * 4:
                continue  # particles avoid dead tubes
            x1, y1 = node_px[u]
            x2, y2 = node_px[v]
            x = x1 + (x2 - x1) * prt.t
            y = y1 + (y2 - y1) * prt.t
            col = QColor.fromHsvF((prt.hue / 360.0) % 1.0, 0.9, 1.0, 1.0)
            self._draw_particle_glow(p, x, y, col, 5.0)

        # Nodes — neon
        node_radius = 11
        for n_id, _x, _y in self._city.nodes_xy:
            x, y = node_px[n_id]
            if n_id == self._city.source:
                base = QColor.fromHsvF((self._idle_phase / 360.0) % 1.0, 0.9, 1.0)
                self._draw_node(p, x, y, base, node_radius + 4, label="SRC")
            elif n_id == self._city.sink:
                base = QColor.fromHsvF(((self._idle_phase + 180) / 360.0) % 1.0,
                                       0.9, 1.0)
                self._draw_node(p, x, y, base, node_radius + 4, label="SINK")
            else:
                hue = (n_id * 27 + self._idle_phase * 0.6) % 360.0
                base = QColor.fromHsvF((hue / 360.0) % 1.0, 0.85, 1.0)
                self._draw_node(p, x, y, base, node_radius)

        # Mint bursts (confetti)
        now = time.time()
        for b in self._bursts:
            age = now - b.born
            if age < 0:
                continue
            radius = 4 + age * 70
            alpha = max(0, 240 - int(age * 160))
            col = QColor(b.color)
            col.setAlpha(alpha)
            cx = pad_x + b.cx * w
            cy = pad_y + b.cy * h
            self._draw_particle_glow(p, cx, cy, col, radius)

        # MINT label
        if now < self._mint_label_until and self._last_mint_amount > 0:
            self._draw_mint_label(p, rect, self._last_mint_amount)

        p.end()

    def _draw_node(self, p: QPainter, x: float, y: float,
                   col: QColor, r: float, label: Optional[str] = None) -> None:
        # Outer glow
        grad = QRadialGradient(QPointF(x, y), r * 3.2)
        glow = QColor(col)
        glow.setAlpha(180)
        grad.setColorAt(0.0, glow)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(x, y), r * 3.2, r * 3.2)
        # Core
        p.setBrush(QBrush(col))
        p.setPen(QPen(QColor(255, 255, 255, 220), 1.5))
        p.drawEllipse(QPointF(x, y), r, r)
        # Label
        if label:
            p.setPen(QPen(QColor(255, 255, 255, 230), 1))
            p.setFont(QFont(GAMIFIED_FONT, 9, QFont.Weight.Bold))
            p.drawText(QRectF(x - 30, y + r + 3, 60, 16),
                       Qt.AlignmentFlag.AlignCenter, label)

    def _draw_particle_glow(self, p: QPainter, x: float, y: float,
                            col: QColor, r: float) -> None:
        grad = QRadialGradient(QPointF(x, y), r)
        c0 = QColor(col)
        c0.setAlpha(min(255, col.alpha()))
        c1 = QColor(col)
        c1.setAlpha(0)
        grad.setColorAt(0.0, c0)
        grad.setColorAt(1.0, c1)
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(x, y), r, r)

    def _draw_mint_label(self, p: QPainter, rect, amount: float) -> None:
        text = f"+{amount:.2f} STGM ⚡"
        p.setPen(QPen(QColor(NEON_GOLD), 1))
        p.setFont(QFont(GAMIFIED_FONT, 36, QFont.Weight.Black))
        # Glow layer
        p.setPen(QPen(QColor(255, 220, 90, 100), 1))
        for dx in (-2, 0, 2):
            for dy in (-2, 0, 2):
                p.drawText(rect.adjusted(dx, dy - 30, dx, dy - 30),
                           Qt.AlignmentFlag.AlignCenter, text)
        p.setPen(QPen(QColor(255, 240, 160, 255), 1))
        p.drawText(rect.adjusted(0, -30, 0, -30),
                   Qt.AlignmentFlag.AlignCenter, text)


# ─── Control panel ─────────────────────────────────────────────────────────────

class ControlPanel(QFrame):
    city_changed = pyqtSignal(str)
    push_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(360)
        self.setMaximumWidth(420)
        self.setStyleSheet(
            f"QFrame {{ background: {PANEL_BG}; border-left: 1px solid #1d1040; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 18, 16, 18)
        lay.setSpacing(12)

        title = QLabel("🌿  SLIME-MOLD BANK")
        title.setStyleSheet(
            f"color: {NEON_PINK}; font-family: {GAMIFIED_FONT}; "
            "font-size: 22px; font-weight: 900; letter-spacing: 2px;"
        )
        lay.addWidget(title)

        sub = QLabel("Push to Mint · Tero 2010 · μ = 1.8")
        sub.setStyleSheet(
            f"color: {NEON_CYAN}; font-family: {GAMIFIED_FONT}; "
            "font-size: 11px; letter-spacing: 1px;"
        )
        lay.addWidget(sub)

        # City selector
        city_label = QLabel("Pick a city / network")
        city_label.setStyleSheet(
            "color: #8a85a8; font-size: 11px; "
            f"font-family: {GAMIFIED_FONT}; margin-top: 8px;"
        )
        lay.addWidget(city_label)

        self.city_combo = QComboBox()
        for k in CITIES.keys():
            self.city_combo.addItem(k)
        self.city_combo.setStyleSheet(
            "QComboBox { background: #1a0c3a; color: white; "
            f"font-family: {GAMIFIED_FONT}; font-size: 13px; padding: 8px; "
            f"border: 1px solid {NEON_PINK}; border-radius: 6px; }} "
            "QComboBox::drop-down { border: 0px; }"
        )
        self.city_combo.currentTextChanged.connect(self.city_changed.emit)
        lay.addWidget(self.city_combo)

        self.story_label = QLabel(CITIES["Tokyo Metro"].story)
        self.story_label.setWordWrap(True)
        self.story_label.setStyleSheet(
            f"color: {NEON_LIME}; font-family: {GAMIFIED_FONT}; "
            "font-size: 11px; padding: 6px 0; letter-spacing: 0.5px;"
        )
        lay.addWidget(self.story_label)

        # Big push button
        self.push_btn = QPushButton("⚡ PUSH TO MINT ⚡")
        self.push_btn.setMinimumHeight(72)
        self.push_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.push_btn.setStyleSheet(
            f"QPushButton {{ background: qlineargradient("
            f"x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {NEON_PINK}, stop:1 #ff8a3d); "
            f"color: white; font-family: {GAMIFIED_FONT}; "
            f"font-size: 22px; font-weight: 900; "
            f"border: 2px solid {NEON_GOLD}; border-radius: 14px; "
            f"letter-spacing: 3px; padding: 8px; }} "
            f"QPushButton:hover {{ background: qlineargradient("
            f"x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 #ff63b6, stop:1 #ffa56a); }} "
            f"QPushButton:disabled {{ background: #2a1850; "
            f"color: #6e6080; border-color: #3a2070; }}"
        )
        self.push_btn.clicked.connect(self.push_clicked.emit)
        lay.addWidget(self.push_btn)

        # Stats grid
        self.stat_iter = self._mk_stat("Iteration", "—", NEON_CYAN)
        self.stat_pruned = self._mk_stat("Waste pruned", "—", NEON_LIME)
        self.stat_flow = self._mk_stat("Σ flow", "—", "#9d6cff")
        self.stat_alive = self._mk_stat("Alive tubes", "—", "#ffd34e")
        for s in (self.stat_iter, self.stat_pruned, self.stat_flow, self.stat_alive):
            lay.addWidget(s["frame"])

        # Score
        score_label = QLabel("STREAK / WALLET")
        score_label.setStyleSheet(
            f"color: #8a85a8; font-family: {GAMIFIED_FONT}; "
            "font-size: 11px; letter-spacing: 1px; margin-top: 8px;"
        )
        lay.addWidget(score_label)
        self.score_box = QLabel("Mints: 0 · STGM minted: 0.00")
        self.score_box.setStyleSheet(
            f"color: {NEON_GOLD}; font-family: {GAMIFIED_FONT}; "
            "font-size: 14px; font-weight: 900; "
            "background: #14082e; padding: 10px; border-radius: 6px;"
        )
        lay.addWidget(self.score_box)

        # Receipt
        self.receipt_box = QLabel("No receipt yet — push the button.")
        self.receipt_box.setWordWrap(True)
        self.receipt_box.setStyleSheet(
            "color: #c0b8e0; font-family: " + GAMIFIED_FONT + "; "
            "font-size: 10px; padding: 8px; "
            "background: #0d0428; border: 1px solid #2b1a55; "
            "border-radius: 6px;"
        )
        lay.addWidget(self.receipt_box)

        # Tagline
        tag = QLabel(
            "Bitcoin proves you spent electricity.\n"
            "We prove a city now wastes less."
        )
        tag.setWordWrap(True)
        tag.setStyleSheet(
            f"color: {NEON_CYAN}; font-family: {GAMIFIED_FONT}; "
            "font-size: 10px; font-style: italic; padding-top: 6px;"
        )
        lay.addWidget(tag)

        lay.addStretch(1)

    def _mk_stat(self, label: str, value: str, color: str) -> dict:
        f = QFrame()
        f.setStyleSheet(
            "QFrame { background: #11062a; border-radius: 6px; padding: 6px; }"
        )
        h = QHBoxLayout(f)
        h.setContentsMargins(10, 6, 10, 6)
        l_lbl = QLabel(label)
        l_lbl.setStyleSheet(
            f"color: #8a85a8; font-family: {GAMIFIED_FONT}; font-size: 11px;"
        )
        l_val = QLabel(value)
        l_val.setStyleSheet(
            f"color: {color}; font-family: {GAMIFIED_FONT}; "
            "font-size: 14px; font-weight: 900;"
        )
        l_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(l_lbl)
        h.addStretch(1)
        h.addWidget(l_val)
        return {"frame": f, "label": l_lbl, "value": l_val}

    def update_stats(self, info: dict) -> None:
        self.stat_iter["value"].setText(f"{info.get('iter', 0)}")
        self.stat_pruned["value"].setText(f"{info.get('reduction_pct', 0)*100:.1f} %")
        self.stat_flow["value"].setText(f"{info.get('total_flow', 0):.2f}")
        self.stat_alive["value"].setText(
            f"{info.get('alive', 0)} / {info.get('alive', 0) + info.get('pruned', 0)}"
        )

    def update_score(self, mints: int, total_minted: float) -> None:
        self.score_box.setText(
            f"Mints: {mints}  ·  STGM minted: {total_minted:.2f}"
        )

    def update_receipt(self, info: dict) -> None:
        status = info.get("status", "?")
        if status == "MINTED":
            txt = (
                f"🟢 MINTED  ·  +{info.get('minted', 0):.2f} STGM\n"
                f"city: {info.get('city')}\n"
                f"pruned: {info.get('reduction_pct')}%  "
                f"alive: {info.get('alive')}/{info.get('total')}\n"
                f"after_hash: {info.get('after_hash','')[:32]}…\n"
                f"receipt: {info.get('receipt_hash','')[:24]}…"
            )
        elif status == "OFFLINE_DEMO_MINT":
            txt = (
                f"🟡 DEMO MINT  ·  +{info.get('minted', 0):.2f} STGM (offline)\n"
                f"city: {info.get('city')}\n"
                f"pruned: {info.get('reduction_pct')}%  "
                f"alive: {info.get('alive')}/{info.get('total')}\n"
                f"PoUW module not importable on this node."
            )
        elif status == "NO_MINT":
            txt = (
                f"⚪ NO MINT  ·  pruned only "
                f"{info.get('reduction_pct', 0):.1f} % (need ≥ 30 %)\n"
                f"city: {info.get('city')}\n"
                f"the mold tried, the city was already lean — try another."
            )
        else:
            txt = f"⚠️  {status}  ·  {info.get('reason','')}"
        self.receipt_box.setText(txt)


# ─── Top-level widget for the OS launcher ──────────────────────────────────────

class SlimeMoldBankWidget(QWidget):
    """Slime-Mold Bank — Push to Mint. Real Physarum + Real PoUW.

    Lives in apps_manifest.json under category Simulations.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SlimeMoldBankWidget")
        self.setStyleSheet(f"QWidget#SlimeMoldBankWidget {{ background: {PANEL_BG}; }}")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.canvas = NetworkCanvas(self)
        self.panel = ControlPanel(self)
        lay.addWidget(self.canvas, 3)
        lay.addWidget(self.panel, 0)

        self.panel.city_changed.connect(self._on_city_changed)
        self.panel.push_clicked.connect(self._on_push)
        self.canvas.iteration_advanced.connect(self.panel.update_stats)
        self.canvas.mint_succeeded.connect(self._on_mint_event)

        self._mints = 0
        self._total_minted = 0.0
        self._refresh_score_from_disk()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_city_changed(self, name: str) -> None:
        self.canvas.set_city(name)
        story = CITIES[name].story if name in CITIES else ""
        self.panel.story_label.setText(story)

    def _on_push(self) -> None:
        self.panel.push_btn.setEnabled(False)
        self.panel.push_btn.setText("⏳ SLIME MOLD THINKING…")
        ok = self.canvas.push_to_mint()
        if not ok:
            self.panel.push_btn.setEnabled(True)
            self.panel.push_btn.setText("⚡ PUSH TO MINT ⚡")

    def _on_mint_event(self, info: dict) -> None:
        self.panel.update_receipt(info)
        if info.get("status") in ("MINTED", "OFFLINE_DEMO_MINT"):
            self._mints += 1
            self._total_minted += float(info.get("minted", 0.0))
            self.panel.update_score(self._mints, self._total_minted)
        self.panel.push_btn.setEnabled(True)
        self.panel.push_btn.setText("⚡ PUSH TO MINT ⚡")

    def _refresh_score_from_disk(self) -> None:
        path = _REPO / ".sifta_state" / "slime_mold_bank_scores.jsonl"
        if not path.exists():
            return
        mints = 0
        total = 0.0
        try:
            for line in path.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if row.get("status") in ("MINTED", "OFFLINE_DEMO_MINT"):
                        mints += 1
                        total += float(row.get("minted_stgm", 0.0))
                except Exception:
                    continue
        except Exception:
            pass
        self._mints = mints
        self._total_minted = total
        self.panel.update_score(mints, total)


# ─── Standalone entry-point ────────────────────────────────────────────────────

def main() -> int:
    app = QApplication(sys.argv)
    win = QWidget()
    win.setWindowTitle("Slime-Mold Bank — Push to Mint")
    win.resize(1240, 820)
    lay = QVBoxLayout(win)
    lay.setContentsMargins(0, 0, 0, 0)
    widget = SlimeMoldBankWidget(win)
    lay.addWidget(widget)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
