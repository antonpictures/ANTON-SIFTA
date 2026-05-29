"""Round 61.1 — focused test for swarm_pheromone_numba_pilot."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
from System.swarm_pheromone_numba_pilot import (
    diffuse_step_njit,
    diffuse_step_py,
    DECAY,
    DIFF_COEFF,
)


def test_pilot_no_crash_and_shape():
    grid = np.random.default_rng(7).random((32, 32))
    out_py = diffuse_step_py(grid, DECAY, DIFF_COEFF)
    out_jit = diffuse_step_njit(grid, DECAY, DIFF_COEFF)
    assert out_py.shape == grid.shape
    assert out_jit.shape == grid.shape


def test_pilot_correctness():
    grid = np.random.default_rng(7).random((32, 32))
    out_py = diffuse_step_py(grid, DECAY, DIFF_COEFF)
    out_jit = diffuse_step_njit(grid, DECAY, DIFF_COEFF)
    assert np.max(np.abs(out_py - out_jit)) < 1e-6


def test_uniform_grid_stays_uniform():
    grid = np.full((16, 16), 0.5)
    out = diffuse_step_py(grid, DECAY, DIFF_COEFF)
    assert np.allclose(out, 0.5 * DECAY), "uniform grid should just decay"


if __name__ == "__main__":
    test_pilot_no_crash_and_shape()
    test_pilot_correctness()
    test_uniform_grid_stays_uniform()
    print("all tests passed")
