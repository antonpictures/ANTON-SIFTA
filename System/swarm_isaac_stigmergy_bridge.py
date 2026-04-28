#!/usr/bin/env python3
"""
System/swarm_isaac_stigmergy_bridge.py
══════════════════════════════════════════════════════════════════════
Event 74 — 3-D Stigmergic Field + Isaac / Omniverse Bridge Scaffold

SIFTA vs GR00T design contrast (from Bishop drop 2026-04-28):

  GR00T / NVIDIA centralised:
    VLM planner @ ~10 Hz → diffusion transformer @ ~120 Hz → joint commands
    "one brain computes every angle"

  SIFTA decentralised embodied stigmergy (this file):
    Alice foveal gaze → goal pheromone drop in 3-D voxel space
    obstacles → hazard pheromones (repulsive potential)
    simulated arm segments → gradient climbers on unified field
    "environment carries the computation, limbs climb the gradient"

Truth labels (§8 Covenant):
  REAL    — pure-Python numpy proof running in-repo (no vendor dep)
  STUB    — Isaac / USD / Omniverse slot (not shipped without GO)
  NPPL    — no production robot / no weapons coupling

Authors: Architect (Ioan George Anton), AG31 (Antigravity/Gemini 2.5 Pro)
Date: 2026-04-28
Refs:
  Bishop drop: Archive/bishop_drops_pending_review/
               BISHOP_drop_nvidia_isaac_stigmergy_bridge_v1.dirt
  Tournament:  Documents/PREDATOR_TOURNAMENT_TRIPLE_IDE_ORDERS.md §7 + §7.1
  NVIDIA Isaac GR00T (vendor contrast, not a peer “beat”):
               https://developer.nvidia.com/isaac/gr00t
               https://developer.nvidia.com/blog/
               accelerate-generalist-humanoid-robot-development-
               with-nvidia-isaac-gr00t-n1/
  Potential fields: Khatib (1986) IJRR 5(1) DOI 10.1177/027836498600500106
  Stigmergy:   Grassé (1959) Insectes Sociaux DOI 10.1007/BF02223791
  Swarm → CS: Bonabeau, Dorigo, Theraulaz (1999) Swarm Intelligence, OUP
  ACO:         Dorigo & Stützle (2004) Ant Colony Optimization, MIT Press
  Octopus / embodied motor (metaphor): Hochner (2012) Current Biology
               DOI 10.1016/j.cub.2012.09.001
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import numpy as np
    _NP = True
except ImportError:
    _NP = False  # graceful fallback for environments without numpy

_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# ── Truth constants ──────────────────────────────────────────────────────────
TRUTH_NUMPY_PROOF = "REAL:numpy_proof"     # runs in-repo, no vendor dep
TRUTH_ISAAC_STUB  = "STUB:isaac_pending"   # Isaac/USD slot, not wired yet
TRUTH_NPPL        = "NPPL:sim_only"        # safety posture label


# ══════════════════════════════════════════════════════════════════════════════
# 1.  3-D VOXEL FIELD (pure-Python + numpy)
# ══════════════════════════════════════════════════════════════════════════════

class VoxelField:
    """
    Axis-aligned 3-D grid that stores stigmergic pheromone intensities.

    Two channels:
      GOAL    (+, attractive)   — Alice foveal / gaze marker
      HAZARD  (-, repulsive)    — obstacle / danger zone

    Gradient at any voxel = ∇GOAL - ∇HAZARD, evaluated with finite differences.
    A gradient-climbing arm segment moves along this vector each tick.

    Implementation: pure Python for portability; numpy path auto-activated
    when available (substantial speed-up for large grids).

    Truth: REAL — runs without any vendor runtime.
    """

    def __init__(self, shape: Tuple[int, int, int] = (16, 16, 16),
                 decay: float = 0.95) -> None:
        self.shape  = shape
        self.decay  = decay          # per-tick pheromone evaporation
        if _NP:
            self._goal   = np.zeros(shape, dtype=np.float32)
            self._hazard = np.zeros(shape, dtype=np.float32)
        else:
            n = shape[0] * shape[1] * shape[2]
            self._goal   = [0.0] * n
            self._hazard = [0.0] * n

    # ── Coordinate helpers ───────────────────────────────────────────────────
    def _idx(self, x: int, y: int, z: int) -> int:
        """Flat index for pure-Python fallback."""
        return (x * self.shape[1] + y) * self.shape[2] + z

    def _clip(self, x: int, y: int, z: int) -> Tuple[int, int, int]:
        return (
            max(0, min(self.shape[0] - 1, x)),
            max(0, min(self.shape[1] - 1, y)),
            max(0, min(self.shape[2] - 1, z)),
        )

    def _get(self, arr, x: int, y: int, z: int) -> float:
        if _NP:
            return float(arr[x, y, z])
        return arr[self._idx(x, y, z)]

    def _set(self, arr, x: int, y: int, z: int, v: float) -> None:
        if _NP:
            arr[x, y, z] = v
        else:
            arr[self._idx(x, y, z)] = v

    def _add(self, arr, x: int, y: int, z: int, v: float) -> None:
        if _NP:
            arr[x, y, z] += v
        else:
            arr[self._idx(x, y, z)] += v

    # ── Pheromone deposits ───────────────────────────────────────────────────
    def fill_goal_potential(self, gx: int, gy: int, gz: int, intensity: float = 1.0) -> None:
        """Set a global inverse-distance potential for the goal."""
        for x in range(self.shape[0]):
            for y in range(self.shape[1]):
                for z in range(self.shape[2]):
                    d = math.sqrt((x-gx)**2 + (y-gy)**2 + (z-gz)**2)
                    self._set(self._goal, x, y, z, intensity / (1.0 + d))

    def fill_hazard_potential(self, hx: int, hy: int, hz: int, intensity: float = 1.0) -> None:
        """Set a global inverse-distance potential for hazards."""
        for x in range(self.shape[0]):
            for y in range(self.shape[1]):
                for z in range(self.shape[2]):
                    d = math.sqrt((x-hx)**2 + (y-hy)**2 + (z-hz)**2)
                    self._set(self._hazard, x, y, z, intensity / (1.0 + d))

    def drop_goal(self, x: int, y: int, z: int, intensity: float = 1.0,
                  radius: int = 2) -> None:
        """Alice foveal gaze → goal pheromone at (x,y,z) with Gaussian spread."""
        cx, cy, cz = self._clip(x, y, z)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    nx, ny, nz = self._clip(cx + dx, cy + dy, cz + dz)
                    d2 = dx*dx + dy*dy + dz*dz
                    v  = intensity * math.exp(-d2 / (radius ** 2 + 1e-6))
                    self._add(self._goal, nx, ny, nz, v)

    def drop_hazard(self, x: int, y: int, z: int, intensity: float = 1.0,
                    radius: int = 2) -> None:
        """Obstacle → repulsive hazard pheromone."""
        cx, cy, cz = self._clip(x, y, z)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    nx, ny, nz = self._clip(cx + dx, cy + dy, cz + dz)
                    d2 = dx*dx + dy*dy + dz*dz
                    v  = intensity * math.exp(-d2 / (radius ** 2 + 1e-6))
                    self._add(self._hazard, nx, ny, nz, v)

    # ── Evaporation ──────────────────────────────────────────────────────────
    def tick(self) -> None:
        """Advance one time step: evaporate both channels."""
        if _NP:
            self._goal   *= self.decay
            self._hazard *= self.decay
        else:
            self._goal   = [v * self.decay for v in self._goal]
            self._hazard = [v * self.decay for v in self._hazard]

    # ── Gradient ─────────────────────────────────────────────────────────────
    def gradient(self, x: int, y: int, z: int) -> Tuple[float, float, float]:
        """
        Gradient of (GOAL - HAZARD) at voxel (x,y,z).
        Central difference where both neighbours exist;
        one-sided (forward/backward) at boundaries.
        Returns (gx, gy, gz) — the direction a gradient-climber should step.
        """
        def combined(cx, cy, cz) -> float:
            cx2, cy2, cz2 = self._clip(cx, cy, cz)
            return (self._get(self._goal,   cx2, cy2, cz2) -
                    self._get(self._hazard, cx2, cy2, cz2))

        def diff1d(pos: int, max_pos: int,
                   fn_minus, fn_plus) -> float:
            """Finite difference on one axis, one-sided at boundary."""
            if pos == 0:
                return fn_plus() - fn_minus()   # forward  (fn_minus is centre)
            if pos == max_pos - 1:
                return fn_minus() - fn_plus()   # backward (fn_plus  is centre)
            return (fn_plus() - fn_minus()) / 2.0

        gx = diff1d(x, self.shape[0],
                    lambda: combined(x,   y, z),
                    lambda: combined(x+1, y, z))
        gy = diff1d(y, self.shape[1],
                    lambda: combined(x, y,   z),
                    lambda: combined(x, y+1, z))
        gz = diff1d(z, self.shape[2],
                    lambda: combined(x, y, z  ),
                    lambda: combined(x, y, z+1))
        return (gx, gy, gz)

    def gradient_norm(self, x: int, y: int, z: int) -> float:
        gx, gy, gz = self.gradient(x, y, z)
        return math.sqrt(gx*gx + gy*gy + gz*gz)


# ══════════════════════════════════════════════════════════════════════════════
# 2.  GRADIENT-CLIMBING ARM SEGMENT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ArmSegment:
    """
    One segment of a simulated arm living in the VoxelField.

    Behaviour (sim-only, NPPL):
      Each tick, reads the field gradient at its current voxel and
      takes one step in the direction of steepest ascent (goal) /
      avoidance (hazard). No joint model — pure gradient climber.
    """
    x: int
    y: int
    z: int
    step_size: float = 1.0
    label: str = "arm_tip"
    history: List[Tuple[int, int, int]] = field(default_factory=list)

    def step(self, vf: VoxelField) -> Tuple[float, float, float]:
        """
        Move one step along the gradient. Returns (gx, gy, gz) before step.
        Fractional gradient → round to nearest voxel (integer grid).
        """
        gx, gy, gz = vf.gradient(self.x, self.y, self.z)
        mag = math.sqrt(gx*gx + gy*gy + gz*gz) or 1e-9
        # Normalise and scale by step_size, round to integer voxel delta
        dx = round(self.step_size * gx / mag)
        dy = round(self.step_size * gy / mag)
        dz = round(self.step_size * gz / mag)
        self.history.append((self.x, self.y, self.z))
        nx, ny, nz = vf._clip(self.x + dx, self.y + dy, self.z + dz)
        self.x, self.y, self.z = nx, ny, nz
        return (gx, gy, gz)

    def reached(self, tx: int, ty: int, tz: int, tol: int = 1) -> bool:
        """True if arm is within `tol` voxels of target."""
        return (abs(self.x - tx) <= tol and
                abs(self.y - ty) <= tol and
                abs(self.z - tz) <= tol)


# ══════════════════════════════════════════════════════════════════════════════
# 3.  SIMULATION RUNNER
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SimReceipt:
    """Ledger row written after each sim run (truth receipt per §8)."""
    ts:          float
    truth:       str
    ticks:       int
    reached:     bool
    start:       Tuple[int, int, int]
    goal:        Tuple[int, int, int]
    hazards:     List[Tuple[int, int, int]]
    final_pos:   Tuple[int, int, int]
    field_shape: Tuple[int, int, int]
    path_length: int
    notes:       str = ""


def run_sim(
    grid_shape: Tuple[int, int, int] = (16, 16, 16),
    start: Tuple[int, int, int] = (1, 1, 1),
    goal: Tuple[int, int, int] = (13, 13, 13),
    hazards: Optional[List[Tuple[int, int, int]]] = None,
    max_ticks: int = 60,
    goal_intensity: float = 5.0,
    hazard_intensity: float = 4.0,
    decay: float = 0.92,
    write_receipt: bool = True,
) -> SimReceipt:
    """
    Run a gradient-climbing arm simulation on a 3-D stigmergic field.

    Truth: REAL:numpy_proof — no vendor runtime required.
    NPPL: simulation / research posture only.
    """
    vf  = VoxelField(shape=grid_shape, decay=decay)
    arm = ArmSegment(x=start[0], y=start[1], z=start[2], label="arm_tip")
    hazards = hazards or [(7, 7, 4), (7, 7, 10), (4, 10, 7)]

    # Initial field state — global potential covers entire grid reliably
    vf.fill_goal_potential(*goal, intensity=goal_intensity)
    for hx, hy, hz in hazards:
        vf.fill_hazard_potential(hx, hy, hz, intensity=hazard_intensity)

    reached = False
    for tick in range(max_ticks):
        arm.step(vf)
        # Re-deposit goal each tick so gradient stays readable after evaporation
        vf.fill_goal_potential(*goal, intensity=goal_intensity * 0.3)
        vf.tick()
        if arm.reached(*goal):
            reached = True
            break

    receipt = SimReceipt(
        ts=time.time(),
        truth=TRUTH_NUMPY_PROOF,
        ticks=tick + 1,
        reached=reached,
        start=start,
        goal=goal,
        hazards=hazards,
        final_pos=(arm.x, arm.y, arm.z),
        field_shape=grid_shape,
        path_length=len(arm.history),
        notes=f"NPPL:sim_only numpy={'yes' if _NP else 'pure_python'}",
    )

    if write_receipt:
        _write_receipt(receipt)

    return receipt


def _write_receipt(receipt: SimReceipt) -> None:
    """Append sim receipt to visual_stigmergy.jsonl (the sim ledger)."""
    try:
        ledger = _STATE / "sim_receipts.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        row = asdict(receipt)
        # Tuples aren't JSON-native — convert
        for k in ("start", "goal", "final_pos", "field_shape"):
            row[k] = list(row[k])
        row["hazards"] = [list(h) for h in row["hazards"]]
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# 4.  ISAAC / OMNIVERSE STUB  (STUB:isaac_pending — not shipped)
# ══════════════════════════════════════════════════════════════════════════════

class IsaacStigmergicStub:
    """
    Placeholder interface for Isaac Sim / Omniverse coupling.

    When Architect gives GO and the Isaac Python environment is available,
    this stub is replaced with:
      • `omni.isaac.core` scene bootstrap
      • USD prim → voxel mapping (foveal marker → goal drop)
      • Joint velocity commands from gradient vector

    Truth: STUB:isaac_pending — interface defined; vendor runtime not wired.
    NPPL: simulation / research posture only. No autonomous hardware control
    without explicit Architect GO + safety review.
    """

    def __init__(self) -> None:
        self.truth  = TRUTH_ISAAC_STUB
        self.loaded = False

    def is_available(self) -> bool:
        """Return True only when the Isaac Python runtime is importable."""
        try:
            import omni.isaac.core  # type: ignore  # noqa
            self.loaded = True
            return True
        except ImportError:
            return False

    def step_scene(self, joint_deltas: List[float]) -> dict:
        """
        Apply joint velocity commands to Isaac scene.
        STUB: returns synthetic state until wired.
        """
        if not self.is_available():
            return {
                "status":  "STUB",
                "message": "Isaac runtime not present — pure-Python field used instead",
                "truth":   self.truth,
            }
        # TODO (when GO): call omni.isaac.core sim.step() and read back poses
        raise NotImplementedError("Isaac runtime wiring pending Architect GO")

    def export_voxel_slice(self, vf: VoxelField, z_slice: int) -> dict:
        """
        Export a 2-D z-slice of the VoxelField as a dict (JSON-serialisable).
        This is the data SIFTA would push to Isaac's Python extension point.
        """
        result: dict = {"z": z_slice, "goal": [], "hazard": [], "truth": TRUTH_NUMPY_PROOF}
        for x in range(vf.shape[0]):
            for y in range(vf.shape[1]):
                g = vf._get(vf._goal,   x, y, z_slice)
                h = vf._get(vf._hazard, x, y, z_slice)
                if g > 0.01:
                    result["goal"].append({"x": x, "y": y, "v": round(g, 4)})
                if h > 0.01:
                    result["hazard"].append({"x": x, "y": y, "v": round(h, 4)})
        return result


# ══════════════════════════════════════════════════════════════════════════════
# 5.  PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def quick_proof() -> SimReceipt:
    """Run the default sim and return a receipt. Used by pytest + CLI."""
    return run_sim()


def explain() -> str:
    """One-paragraph plain-English description of this module."""
    return (
        "Event 74 — 3-D Stigmergic Field (SIFTA vs GR00T).\n"
        "SIFTA approach: Alice's foveal gaze drops goal-pheromones onto a 3-D voxel grid; "
        "obstacles drop repulsive hazard-pheromones. "
        "A simulated arm segment climbs the combined gradient (goal - hazard) each tick — "
        "no central joint planner, no diffusion transformer. "
        "The environment carries the computation; the limb follows the field. "
        f"numpy present: {_NP}. Truth: {TRUTH_NUMPY_PROOF}. Posture: {TRUTH_NPPL}."
    )


# ══════════════════════════════════════════════════════════════════════════════
# CLI smoke
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(explain())
    print()
    receipt = quick_proof()
    print(f"Ticks:      {receipt.ticks}")
    print(f"Reached:    {receipt.reached}")
    print(f"Start:      {receipt.start}")
    print(f"Goal:       {receipt.goal}")
    print(f"Final pos:  {receipt.final_pos}")
    print(f"Path len:   {receipt.path_length}")
    print(f"Truth:      {receipt.truth}")
    print(f"Notes:      {receipt.notes}")

    # Gradient spot-check: fill_goal_potential guarantees non-zero at (1,1,1)
    vf = VoxelField()
    vf.fill_goal_potential(13, 13, 13, intensity=5.0)
    g = vf.gradient(1, 1, 1)
    print(f"\nGradient at (1,1,1) toward (13,13,13): ({g[0]:.4f}, {g[1]:.4f}, {g[2]:.4f})")
    assert all(v > 0 for v in g), "Gradient should point toward goal"
    print("✓ Gradient direction correct")


