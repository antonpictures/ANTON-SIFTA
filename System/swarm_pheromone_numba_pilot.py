#!/usr/bin/env python3
"""
System/swarm_pheromone_numba_pilot.py
Round 61.1 — Numba @njit pilot for pheromone field diffusion.

One diffusion step on a 2D numpy grid:
  new[i,j] = decay * ((1 - 4*D)*old[i,j] + D*(neighbours))
where D is a diffusion coefficient and decay is evaporation.
Neumann boundary (zero-flux): clamp neighbour reads at edges.

Provides:
  diffuse_step_njit  — Numba-accelerated version
  diffuse_step_py    — pure-Python reference for correctness check
"""
from __future__ import annotations

import numpy as np

try:
    from numba import njit
    _HAS_NUMBA = True
except ImportError:
    _HAS_NUMBA = False

DECAY: float = 0.96
DIFF_COEFF: float = 0.1


def _njit_or_identity(fn):
    if _HAS_NUMBA:
        return njit(cache=True)(fn)
    return fn


@_njit_or_identity
def diffuse_step_njit(grid: np.ndarray, decay: float, D: float) -> np.ndarray:
    rows, cols = grid.shape
    out = np.empty_like(grid)
    for i in range(rows):
        for j in range(cols):
            top    = grid[i - 1, j] if i > 0        else grid[i, j]
            bottom = grid[i + 1, j] if i < rows - 1 else grid[i, j]
            left   = grid[i, j - 1] if j > 0        else grid[i, j]
            right  = grid[i, j + 1] if j < cols - 1 else grid[i, j]
            laplacian = top + bottom + left + right - 4.0 * grid[i, j]
            out[i, j] = decay * (grid[i, j] + D * laplacian)
    return out


def diffuse_step_py(grid: np.ndarray, decay: float, D: float) -> np.ndarray:
    rows, cols = grid.shape
    out = np.empty_like(grid)
    for i in range(rows):
        for j in range(cols):
            top    = grid[i - 1, j] if i > 0        else grid[i, j]
            bottom = grid[i + 1, j] if i < rows - 1 else grid[i, j]
            left   = grid[i, j - 1] if j > 0        else grid[i, j]
            right  = grid[i, j + 1] if j < cols - 1 else grid[i, j]
            laplacian = top + bottom + left + right - 4.0 * grid[i, j]
            out[i, j] = decay * (grid[i, j] + D * laplacian)
    return out


if __name__ == "__main__":
    N = 32
    rng = np.random.default_rng(42)
    grid = rng.random((N, N))

    result_py = diffuse_step_py(grid, DECAY, DIFF_COEFF)
    result_jit = diffuse_step_njit(grid, DECAY, DIFF_COEFF)

    assert result_py.shape == (N, N), f"shape mismatch: {result_py.shape}"
    assert result_jit.shape == (N, N), f"shape mismatch: {result_jit.shape}"

    max_diff = np.max(np.abs(result_py - result_jit))
    assert max_diff < 1e-6, f"max diff {max_diff} >= 1e-6"
    print(f"pilot ok  (max_diff={max_diff:.2e}, shape={result_jit.shape})")
