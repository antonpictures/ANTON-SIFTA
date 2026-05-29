#!/usr/bin/env python3
"""
System/swarm_pheromone_field.py
════════════════════════════════════════════════════════════════════════
Event 94 — Ant Pheromone Gradient (Spatial Path Memory / Navigation)

Biology:
  Ants don't store paths as discrete memories — they deposit chemical
  gradients in the environment. Stronger paths get reinforced by
  repeated success; weak paths decay. The world itself becomes memory.

  
Biology research (deeper grounding for diffusion + cortex routing bias):

Real pheromone systems in social insects are not simple exponential decay.
They combine:
- Deposition (positive feedback on successful actions/paths)
- Evaporation (exponential decay, species-dependent time constant)
- Diffusion (lateral spread of the chemical in the substrate, creating smooth gradients instead of razor-sharp lines)

Key references:
- Grassé 1959 (origin of "stigmergy"): indirect coordination via persistent traces.
- Wilson 1971 "The Insect Societies": detailed measurements of trail evaporation rates and geometry.
- Dorigo & Stützle 2004 (Ant Colony Optimization): formalizes the evaporation + reinforcement loop; diffusion emerges naturally in continuous models.
- Recent Physarum polycephalum work (slime mold): uses similar chemical + mechanical fields for distributed optimization without any central controller. The organism "computes" shortest paths via reaction-diffusion dynamics.

In SIFTA translation:
  The new Laplacian diffusion step (D=0.1) implements the lateral spread that real pheromones exhibit.
  This creates "attraction basins" around high-value actions instead of delta spikes.
  When the cortex later samples route bias, it can perform a soft chemotaxis: prefer directions or foci where the local pheromone gradient points uphill.

This is exactly the high-dimensional, deeply interconnected field the Swarm requires: local deposits + global diffusion + decay = emergent, receipted, self-improving coordination without a central planner.

Biological spine (DOI-locked):
    Grassé, P.-P. (1959). La reconstruction du nid et les coordinations
      inter-individuelles chez Bellicositermes natalensis.
      Insectes Sociaux 6, 41–58. DOI 10.1007/BF02223791
    Wilson, E.O. (1971). The Insect Societies. Harvard University Press.
      — pheromone trail geometry + decay constants.
    Dorigo, M. & Stützle, T. (2004). Ant Colony Optimization.
      MIT Press. DOI 10.7551/mitpress/1290.001.0001

SIFTA translation:
  body_brain_memory.jsonl → action/td_value → spatial deposit
  pheromone_field.json    → 32×32 float grid (decay + reinforce)
  sample_gradient()       → "where should Alice go next?"

Truth label (§7.11): OPERATIONAL geometry via swarm_stigmergic_coordinate_feed.
  Proxy HASH_PROXY mode is only used when the coordinate feed is unavailable.
  Real spatial tracks are now local behavioral traces governed by NPPL.

NPPL: no weapons coupling.
"""
from __future__ import annotations

import json
import hashlib
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent

# ── Constants ──────────────────────────────────────────────────────────────

GRID_SIZE:        int   = 32
DECAY:            float = 0.96   # per-tick evaporation (Wilson 1971 analogue)
DEPOSIT_STRENGTH: float = 0.25   # max deposit per positive td_value tick

# Round 63 §ROUND 61.1 integration — diffusion now native via numba pilot when present.
PHEROMONE_DIFFUSION_ENABLED: bool = True
DIFF_COEFF: float = 0.1

try:
    from System.swarm_pheromone_numba_pilot import diffuse_step_njit, diffuse_step_py
    _HAS_DIFFUSION_PILOT = True
except ImportError:
    _HAS_DIFFUSION_PILOT = False

# ── State paths ────────────────────────────────────────────────────────────

def _state_dir() -> Path:
    """Follow body_brain_loop._STATE_DIR if monkey-patched in tests."""
    try:
        import System.swarm_body_brain_loop as _bbl
        d = getattr(_bbl, "_STATE_DIR", None)
        if d is not None:
            return Path(d).resolve()
    except Exception:
        pass
    return (_REPO / ".sifta_state").resolve()


def pheromone_path() -> Path:
    return _state_dir() / "pheromone_field.json"


def body_memory_path() -> Path:
    return _state_dir() / "body_brain_memory.jsonl"


# ── Grid I/O ───────────────────────────────────────────────────────────────

Grid = List[List[float]]


def init_grid() -> Grid:
    return [[0.0] * GRID_SIZE for _ in range(GRID_SIZE)]


def load_grid() -> Grid:
    p = pheromone_path()
    if not p.exists():
        return init_grid()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if (
            isinstance(data, list)
            and len(data) == GRID_SIZE
            and all(isinstance(r, list) and len(r) == GRID_SIZE for r in data)
        ):
            return [[float(v) for v in row] for row in data]
    except Exception:
        pass
    return init_grid()


def save_grid(grid: Grid) -> None:
    p = pheromone_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(grid), encoding="utf-8")


# ── Action → position proxy ────────────────────────────────────────────────

def action_to_position(action: str) -> Tuple[int, int]:
    """
    Map abstract action label → spatial grid cell.
    This is a PROXY. Later replace with real cursor / vision coordinates.
    Uses a stable digest so the same action always hits the same cell across
    Python process restarts — enabling genuine reinforcement.
    """
    digest = hashlib.sha256(str(action).encode("utf-8")).digest()
    h = int.from_bytes(digest[:8], "big") % (GRID_SIZE * GRID_SIZE)
    return h % GRID_SIZE, h // GRID_SIZE


# ── Read latest body-brain row ─────────────────────────────────────────────

def read_last_action(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or body_memory_path()
    if not p.exists():
        return {}
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            stripped = line.strip()
            if stripped:
                return json.loads(stripped)
    except Exception:
        pass
    return {}


# ── Core update ───────────────────────────────────────────────────────────

# ── Real coordinate integration ───────────────────────────────────────────

def _real_position() -> Tuple[int, int, str]:
    """
    Get best available grid position from real coordinates.
    Priority: retina/visual_stigmergy > Quartz cursor > Brownian sim > hash.
    Returns (gx, gy, truth_label).
    """
    try:
        from System.swarm_stigmergic_coordinate_feed import best_grid_position
        gx, gy, label = best_grid_position(GRID_SIZE, _state_dir())
        return gx, gy, label
    except Exception:
        return 0, 0, "COORD_FEED_UNAVAILABLE"


# ── Core update ───────────────────────────────────────────────────────────────

def update_pheromone_field(
    row: Optional[Dict[str, Any]] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
) -> Dict[str, Any]:
    """
    One tick of the pheromone field:
      1. Load grid.
      2. Decay all cells (evaporation — Wilson 1971).
      3. Resolve grid position (real coords > cursor > hash proxy).
      4. Deposit weighted by td_value.
      5. Save grid.
      6. Return receipt including coord_truth_label.

    row: optional body_brain_memory dict; reads from JSONL if None.
    x, y: optional explicit grid cell (e.g. from caller with real coords).
    """
    grid = load_grid()

    # 1. Evaporation (+ spatial diffusion when pilot is present)
    if PHEROMONE_DIFFUSION_ENABLED and _HAS_DIFFUSION_PILOT:
        grid_np = np.array(grid, dtype=np.float64)
        grid_np = diffuse_step_njit(grid_np, DECAY, DIFF_COEFF)
        np.clip(grid_np, 0.0, None, out=grid_np)
        grid = grid_np.tolist()
    else:
        for _y in range(GRID_SIZE):
            for _x in range(GRID_SIZE):
                grid[_y][_x] = max(0.0, grid[_y][_x] * DECAY)

    # 2. Read row
    if row is None:
        row = read_last_action()

    action = str(row.get("action", "observe"))
    raw_val = row.get("td_value", row.get("value", 0.0))
    try:
        td_val = float(raw_val)
    except (TypeError, ValueError):
        td_val = 0.0

    # 3. Resolve position (real coords > hash proxy)
    coord_truth_label: str
    if x is not None and y is not None:
        gx, gy = int(x) % GRID_SIZE, int(y) % GRID_SIZE
        coord_truth_label = "CALLER_SUPPLIED"
    else:
        gx, gy, coord_truth_label = _real_position()
        if coord_truth_label == "COORD_FEED_UNAVAILABLE":
            # Hash fallback — stable across restarts (SHA-256 based)
            gx, gy = action_to_position(action)
            coord_truth_label = "HASH_PROXY"

    # 4. Deposit
    deposit = max(0.0, td_val) * DEPOSIT_STRENGTH
    grid[gy][gx] = min(1.0, grid[gy][gx] + deposit)

    save_grid(grid)
    chemotaxis = chemotaxis_scalar(gx, gy)

    return {
        "ts":                time.time(),
        "action":            action,
        "position":          [gx, gy],
        "deposit":           round(deposit, 4),
        "cell_value":        round(grid[gy][gx], 4),
        "chemotaxis_gradient": round(chemotaxis, 4),
        "coord_truth_label": coord_truth_label,
    }


# ── Gradient sampling ─────────────────────────────────────────────────────

def sample_gradient(x: int, y: int) -> Tuple[Tuple[int, int], float]:
    """
    From cell (x, y), return the neighbour (or self) with the highest
    pheromone concentration — gradient ascent (chemotaxis / ACO step).
    """
    grid  = load_grid()
    best  = (x, y)
    best_val = grid[y][x]

    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < GRID_SIZE and 0 <= ny < GRID_SIZE:
                if grid[ny][nx] > best_val:
                    best     = (nx, ny)
                    best_val = grid[ny][nx]

    return best, round(best_val, 4)


def chemotaxis_scalar(x: int, y: int) -> float:
    """
    Return the pheromone strength at the best local gradient step,
    normalised to [0, 1] — ready to feed as u_chemotaxis_gradient
    into the visual phenotype bridge.
    """
    _, val = sample_gradient(x, y)
    return min(1.0, val)


def top_cells(n: int = 5) -> List[Dict[str, Any]]:
    """Return the n highest-value cells — useful for navigation summaries."""
    grid = load_grid()
    cells = [
        {"x": x, "y": y, "value": round(grid[y][x], 4)}
        for y in range(GRID_SIZE)
        for x in range(GRID_SIZE)
        if grid[y][x] > 0.0
    ]
    return sorted(cells, key=lambda c: c["value"], reverse=True)[:n]


# ── Module smoke test ──────────────────────────────────────────────────────


def get_cortex_route_bias(focus_key: str) -> float:
    """
    Return a bias scalar [0.0, 1.0] that the cortex / planning system can add
    when scoring possible next foci, arm dispatches, or attention targets.

    Biology grounding (real insect systems):
    - Ants and termites do not have a central map. They perform chemotaxis:
      they turn toward higher local pheromone concentration.
    - The gradient is created by the combination of point deposition + evaporation + diffusion.
    - Stronger gradients (higher traffic + recent success) produce stronger behavioral bias.
    - Diffusion prevents brittle "all-or-nothing" trail following and allows exploration of nearby good options.

    In SIFTA terms this is the high-dimensional field doing distributed, receipted optimization.
    The cortex does not need to "understand" the whole grid; it only needs to sample the local field
    at candidate decision points and let the bias emerge.

    Usage example (in cortex routing or planning mode):
        base_score = some_heuristic(action)
        pheromone_boost = 0.25 * get_cortex_route_bias(action)
        final_score = base_score + pheromone_boost
    """
    gx, gy = action_to_position(focus_key)
    grid = load_grid()
    conc = grid[gy][gx]
    # Soft normalization. Real ants have saturation too.
    # Typical useful range in current SIFTA deposits is ~0–5 before clipping.
    bias = min(1.0, max(0.0, conc / 5.0))
    return bias

if __name__ == "__main__":
    print("=== Pheromone Field Smoke Test ===")
    result = update_pheromone_field(
        {"action": "explore", "td_value": 0.8}
    )
    print("Update:", result)
    pos = result["position"]
    best, val = sample_gradient(pos[0], pos[1])
    print(f"Gradient from {pos}: best={best} value={val}")
    print("Top cells:", top_cells(3))
