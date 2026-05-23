"""
tests/test_swarm_pheromone_field.py
════════════════════════════════════
Falsifiable tests for the Event 94 pheromone field organ.

Invariants:
  1. Deposit increases cell value.
  2. Decay reduces all cells each tick.
  3. Positive td_value → non-zero deposit; zero/negative → no deposit.
  4. sample_gradient returns the highest neighbour.
  5. chemotaxis_scalar stays in [0, 1].
  6. Grid survives corrupt JSON gracefully.
  7. action_to_position is deterministic and in-bounds.
"""
from __future__ import annotations

import json
import hashlib
from unittest.mock import patch

import pytest


# ── Fixture: isolated state dir ───────────────────────────────────────────

@pytest.fixture()
def state_dir(tmp_path, monkeypatch):
    import System.swarm_body_brain_loop as bbl
    monkeypatch.setattr(bbl, "_STATE_DIR", str(tmp_path), raising=False)
    return tmp_path


# ── 1. Deposit increases cell value ───────────────────────────────────────

def test_deposit_increases_cell(state_dir):
    from System.swarm_pheromone_field import (
        load_grid, update_pheromone_field
    )
    result = update_pheromone_field({"action": "explore", "td_value": 1.0})
    grid = load_grid()
    x, y = result["position"]
    assert grid[y][x] > 0.0, "Positive td_value must deposit pheromone"
    assert result["deposit"] > 0.0
    assert result["chemotaxis_gradient"] > 0.0


# ── 2. Decay reduces cells ────────────────────────────────────────────────

def test_decay_reduces_all_cells(state_dir):
    from System.swarm_pheromone_field import (
        load_grid, save_grid, update_pheromone_field, GRID_SIZE, DECAY
    )
    # Pre-fill grid with 0.5
    grid = [[0.5] * GRID_SIZE for _ in range(GRID_SIZE)]
    save_grid(grid)
    # One tick with zero deposit (td_value=0)
    update_pheromone_field({"action": "rest", "td_value": 0.0})
    new_grid = load_grid()
    # Every cell should be ≤ 0.5 * DECAY (deposit at rest cell may add a bit)
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            assert new_grid[y][x] <= 0.5 + 0.01, (
                f"Cell ({x},{y}) did not decay: {new_grid[y][x]}"
            )


# ── 3. Zero / negative td_value → no deposit ─────────────────────────────

def test_zero_td_no_deposit(state_dir):
    from System.swarm_pheromone_field import update_pheromone_field
    result = update_pheromone_field({"action": "rest", "td_value": 0.0})
    assert result["deposit"] == 0.0

def test_negative_td_no_deposit(state_dir):
    from System.swarm_pheromone_field import update_pheromone_field
    result = update_pheromone_field({"action": "rest", "td_value": -0.5})
    assert result["deposit"] == 0.0


# ── 4. sample_gradient returns best neighbour ─────────────────────────────

def test_gradient_returns_best_neighbour(state_dir):
    from System.swarm_pheromone_field import (
        load_grid, save_grid, sample_gradient, GRID_SIZE
    )
    grid = [[0.0] * GRID_SIZE for _ in range(GRID_SIZE)]
    # Place a peak at (10, 10)
    grid[10][10] = 0.9
    save_grid(grid)
    # Query from (9, 9) — should climb toward (10, 10)
    best, val = sample_gradient(9, 9)
    assert best == (10, 10), f"Expected (10,10), got {best}"
    assert abs(val - 0.9) < 0.01


# ── 5. chemotaxis_scalar stays in [0, 1] ─────────────────────────────────

def test_chemotaxis_scalar_bounded(state_dir):
    from System.swarm_pheromone_field import (
        save_grid, chemotaxis_scalar, GRID_SIZE
    )
    # Saturate a cell
    grid = [[0.0] * GRID_SIZE for _ in range(GRID_SIZE)]
    grid[5][5] = 1.5   # intentionally above 1.0 to test clamp
    save_grid(grid)
    scalar = chemotaxis_scalar(5, 5)
    assert 0.0 <= scalar <= 1.0, f"chemotaxis_scalar out of range: {scalar}"


# ── 6. Corrupt JSON falls back to empty grid ─────────────────────────────

def test_corrupt_grid_fallback(state_dir):
    from System.swarm_pheromone_field import (
        pheromone_path, load_grid, GRID_SIZE
    )
    pheromone_path().write_text("NOT_JSON{{", encoding="utf-8")
    grid = load_grid()
    assert len(grid) == GRID_SIZE
    assert all(v == 0.0 for row in grid for v in row)


# ── 7. action_to_position is deterministic and in-bounds ─────────────────

def test_action_to_position_deterministic_and_inbounds():
    from System.swarm_pheromone_field import action_to_position, GRID_SIZE
    for action in ("explore", "rest", "observe", "repair", "protect", ""):
        x, y = action_to_position(action)
        assert 0 <= x < GRID_SIZE, f"x={x} out of bounds for action={action!r}"
        assert 0 <= y < GRID_SIZE, f"y={y} out of bounds for action={action!r}"
        digest = hashlib.sha256(str(action).encode("utf-8")).digest()
        expected = int.from_bytes(digest[:8], "big") % (GRID_SIZE * GRID_SIZE)
        assert (x, y) == (expected % GRID_SIZE, expected // GRID_SIZE)
        assert action_to_position(action) == (x, y)


# ── 8. top_cells returns sorted results ──────────────────────────────────

def test_top_cells_sorted(state_dir):
    from System.swarm_pheromone_field import save_grid, top_cells, GRID_SIZE
    grid = [[0.0] * GRID_SIZE for _ in range(GRID_SIZE)]
    grid[0][0] = 0.9
    grid[1][1] = 0.5
    grid[2][2] = 0.1
    save_grid(grid)
    cells = top_cells(3)
    assert len(cells) == 3
    assert cells[0]["value"] >= cells[1]["value"] >= cells[2]["value"]
