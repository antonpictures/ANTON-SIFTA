"""tests/test_stigmal_555.py
══════════════════════════════════════════════════════════════════════
Tests for Stigmal555 reward (C47H drop + AG31 patches)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest
from swarmrl.tasks import Stigmal555


class FakeColloid:
    def __init__(self, pos, type_=0):
        self.pos = np.array(pos, dtype=float)
        self.type = type_


def make_task(**kw):
    return Stigmal555(particle_type=0, **kw)


def run_one_step(task, positions_t0, positions_t1):
    colloids0 = [FakeColloid(p) for p in positions_t0]
    colloids1 = [FakeColloid(p) for p in positions_t1]
    task.initialize(colloids0)
    return task(colloids1)


def test_field_decay_and_deposit():
    """Test that the 2D grid correctly accumulates and decays deposits."""
    task = make_task(grid_size=10, box_size=10.0, field_decay=0.5, deposit_strength=1.0)
    
    # Particle at (5.5, 5.5, 0)
    t0 = [[5.5, 5.5, 0]]
    t1 = [[5.5, 5.5, 0]]
    
    # Grid cell should be 5
    run_one_step(task, t0, t1)
    
    assert task.field[5, 5] == 1.0
    
    # Second step: field decays to 0.5, then +1.0 deposit = 1.5
    run_one_step(task, t1, t1)
    assert task.field[5, 5] == 1.5


def test_periodic_boundary_grid():
    """Test that coordinates wrap correctly to the grid."""
    task = make_task(grid_size=10, box_size=10.0, deposit_strength=1.0)
    
    # Out of bounds coordinate 11.5 % 10.0 = 1.5 -> grid cell 1
    t0 = [[11.5, -8.5, 0]]
    t1 = [[11.5, -8.5, 0]]
    
    run_one_step(task, t0, t1)
    assert task.field[1, 1] == 1.0


def test_memory_reward():
    """Agents receive higher reward when on a high-pheromone cell."""
    task = make_task(
        radius=10.0, alignment_weight=0.0, structure_weight=0.0, memory_weight=1.0,
        grid_size=10, box_size=10.0, deposit_strength=0.0, field_decay=1.0
    )
    
    # Manually spike the field at [2,2]
    task.field[2, 2] = 10.0
    
    t0 = [[2.5, 2.5, 0], [8.5, 8.5, 0]]
    t1 = [[2.5, 2.5, 0], [8.5, 8.5, 0]]
    
    rewards = run_one_step(task, t0, t1)
    
    # Particle 0 is on the spike, Particle 1 is on empty space
    assert rewards[0] > rewards[1]
    assert rewards[0] == 10.0


def test_structure_sweet_spot():
    """Structure term prefers distances near radius/2."""
    # Radius 4, target distance is 2.
    task = make_task(
        radius=4.0, alignment_weight=0.0, structure_weight=1.0, memory_weight=0.0
    )
    
    # Distance = 2.0 (perfect)
    t0_perf = [[0,0,0], [2,0,0]]
    t1_perf = [[0,0,0], [2,0,0]]
    r_perf = run_one_step(task, t0_perf, t1_perf)
    
    # Distance = 0.5 (too close)
    task.previous_positions = None
    t0_close = [[0,0,0], [0.5,0,0]]
    t1_close = [[0,0,0], [0.5,0,0]]
    r_close = run_one_step(task, t0_close, t1_close)
    
    assert r_perf[0] == 0.0  # -abs(2 - 2) = 0
    assert r_close[0] < 0.0  # -abs(0.5 - 2) = -1.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
