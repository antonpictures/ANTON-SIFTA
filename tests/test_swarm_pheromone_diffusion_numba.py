"""Round 63 §ROUND 61.1 — diffusion integration into swarm_pheromone_field."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pytest


@pytest.fixture()
def state_dir(tmp_path, monkeypatch):
    import System.swarm_body_brain_loop as bbl
    monkeypatch.setattr(bbl, "_STATE_DIR", str(tmp_path), raising=False)
    return tmp_path


def test_diffuse_njit_vs_py_closeness():
    from System.swarm_pheromone_numba_pilot import (
        diffuse_step_njit, diffuse_step_py, DECAY, DIFF_COEFF,
    )
    grid = np.random.default_rng(99).random((32, 32))
    out_jit = diffuse_step_njit(grid, DECAY, DIFF_COEFF)
    out_py = diffuse_step_py(grid, DECAY, DIFF_COEFF)
    assert np.max(np.abs(out_jit - out_py)) < 1e-6


def test_tick_with_diffusion_shape_and_nonneg(state_dir):
    from System.swarm_pheromone_field import (
        update_pheromone_field, load_grid, GRID_SIZE,
    )
    result = update_pheromone_field({"action": "explore", "td_value": 0.8})
    grid = load_grid()
    assert len(grid) == GRID_SIZE
    assert all(len(row) == GRID_SIZE for row in grid)
    for row in grid:
        for v in row:
            assert v >= 0.0, f"negative pheromone value: {v}"


def test_diffusion_spreads_point_source(state_dir):
    from System.swarm_pheromone_field import (
        save_grid, update_pheromone_field, load_grid, GRID_SIZE,
        PHEROMONE_DIFFUSION_ENABLED,
    )
    if not PHEROMONE_DIFFUSION_ENABLED:
        pytest.skip("diffusion disabled")
    grid = [[0.0] * GRID_SIZE for _ in range(GRID_SIZE)]
    grid[16][16] = 1.0
    save_grid(grid)
    update_pheromone_field({"action": "rest", "td_value": 0.0})
    new_grid = load_grid()
    assert new_grid[15][16] > 0.0 or new_grid[17][16] > 0.0, \
        "diffusion should spread to neighbors"


if __name__ == "__main__":
    test_diffuse_njit_vs_py_closeness()
    print("all standalone tests passed (run pytest for fixture tests)")
