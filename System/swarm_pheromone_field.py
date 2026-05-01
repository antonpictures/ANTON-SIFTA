#!/usr/bin/env python3
"""
System/swarm_pheromone_field.py
════════════════════════════════════════════════════════════════════════
Event 94 — Ant Pheromone Gradient (Spatial Path Memory / Navigation)

Biology:
  Ants don't store paths as discrete memories — they deposit chemical
  gradients in the environment. Stronger paths get reinforced by
  repeated success; weak paths decay. The world itself becomes memory.

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

Truth label (§7.11): OPERATIONAL toy dynamics — 32×32 is a proxy grid.
  Real spatial coordinates require a live cursor / vision / map feed.
  Do not claim this is production path-planning without that wiring.

NPPL: no weapons coupling.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent

# ── Constants ──────────────────────────────────────────────────────────────

GRID_SIZE:        int   = 32
DECAY:            float = 0.96   # per-tick evaporation (Wilson 1971 analogue)
DEPOSIT_STRENGTH: float = 0.25   # max deposit per positive td_value tick

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
    Uses a simple deterministic hash so the same action always hits the
    same cell — enabling genuine reinforcement.
    """
    h = abs(hash(str(action))) % (GRID_SIZE * GRID_SIZE)
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

def update_pheromone_field(
    row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    One tick of the pheromone field:
      1. Load grid.
      2. Decay all cells (evaporation — Wilson 1971).
      3. Deposit at action position weighted by td_value.
      4. Save grid.
      5. Return receipt.

    row: optional body_brain_memory dict; reads from JSONL if None.
    """
    grid = load_grid()

    # 1. Evaporation
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            grid[y][x] = max(0.0, grid[y][x] * DECAY)

    # 2. Deposit
    if row is None:
        row = read_last_action()

    action = str(row.get("action", "observe"))
    # td_value may live under "value" (older rows) or "td_value" (current)
    raw_val = row.get("td_value", row.get("value", 0.0))
    try:
        td_val = float(raw_val)
    except (TypeError, ValueError):
        td_val = 0.0

    x, y    = action_to_position(action)
    deposit = max(0.0, td_val) * DEPOSIT_STRENGTH
    grid[y][x] = min(1.0, grid[y][x] + deposit)

    save_grid(grid)

    return {
        "ts":      time.time(),
        "action":  action,
        "position": [x, y],
        "deposit": round(deposit, 4),
        "cell_value": round(grid[y][x], 4),
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
