"""tests/test_stigmergic_consensus.py
══════════════════════════════════════════════════════════════════════
Tests for StigmergicConsensus reward (AS46 / AG31 Event 55)
Runs WITHOUT ESPResSo — uses the graceful stub path.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pytest
from swarmrl.tasks import StigmergicConsensus


# ── Minimal Colloid stub ────────────────────────────────────────────
class FakeColloid:
    def __init__(self, pos, type_=0):
        self.pos = np.array(pos, dtype=float)
        self.type = type_


def make_task(**kw):
    return StigmergicConsensus(particle_type=0, **kw)


def run_one_step(task, positions_t0, positions_t1):
    """Seed with t0 then call with t1."""
    colloids0 = [FakeColloid(p) for p in positions_t0]
    colloids1 = [FakeColloid(p) for p in positions_t1]
    task.initialize(colloids0)
    return task(colloids1)


# ── Tests ────────────────────────────────────────────────────────────

def test_aligned_flock_positive_reward():
    """Three particles moving in the same direction → high alignment reward."""
    task = make_task(radius=5.0, alignment_weight=1.0, cohesion_weight=0.0,
                     separation_weight=0.0, activity_weight=0.0)
    # All particles at t=0, then shift uniformly right
    t0 = [[0,0,0], [2,0,0], [4,0,0]]
    t1 = [[1,0,0], [3,0,0], [5,0,0]]  # all move +1 in x
    rewards = run_one_step(task, t0, t1)
    assert all(r > 0.8 for r in rewards), f"Expected high rewards, got {rewards}"


def test_anti_aligned_negative_reward():
    """Two particles moving in opposite directions → negative alignment."""
    task = make_task(radius=5.0, alignment_weight=1.0, cohesion_weight=0.0,
                     separation_weight=0.0, activity_weight=0.0)
    t0 = [[0,0,0], [2,0,0]]
    t1 = [[1,0,0], [1,0,0]]   # first moves right, second moves left
    rewards = run_one_step(task, t0, t1)
    assert rewards[0] < 0.0, f"Expected negative reward for anti-alignment, got {rewards[0]}"


def test_isolation_penalty():
    """Particle with no neighbors within radius → -0.1 isolation penalty."""
    task = make_task(radius=1.0, min_neighbors=1)
    t0 = [[0,0,0], [100,0,0]]  # far apart
    t1 = [[1,0,0], [101,0,0]]
    rewards = run_one_step(task, t0, t1)
    assert all(r == pytest.approx(-0.1) for r in rewards), f"Expected isolation penalty, got {rewards}"


def test_separation_penalty_on_collapse():
    """Particles collapsing to same point → separation penalty fires."""
    task = make_task(
        radius=5.0,
        separation_weight=1.0, separation_radius=1.5,
        alignment_weight=0.0, cohesion_weight=0.0, activity_weight=0.0,
    )
    t0 = [[0,0,0], [1,0,0]]    # 1 unit apart at t0
    t1 = [[0.3,0,0], [0.7,0,0]]  # closing to 0.4 units — inside sep_radius
    rewards = run_one_step(task, t0, t1)
    assert all(r < 0.0 for r in rewards), f"Expected separation penalty, got {rewards}"


def test_activity_weight_normalized():
    """Activity term uses reference_speed — fast mover should get higher activity."""
    task_slow = make_task(reference_speed=10.0, activity_weight=1.0,
                          alignment_weight=0.0, cohesion_weight=0.0,
                          separation_weight=0.0, radius=5.0)
    task_fast = make_task(reference_speed=0.1, activity_weight=1.0,
                          alignment_weight=0.0, cohesion_weight=0.0,
                          separation_weight=0.0, radius=5.0)
    t0 = [[0,0,0], [2,0,0]]
    t1 = [[1,0,0], [3,0,0]]   # speed = 1 unit/step
    r_slow = run_one_step(task_slow, t0, t1)
    r_fast = run_one_step(task_fast, t0, t1)
    assert r_fast[0] > r_slow[0], (
        f"Faster reference_speed should reduce saturation: fast={r_fast[0]:.3f} slow={r_slow[0]:.3f}"
    )


def test_reward_shape():
    """Output shape matches number of species particles."""
    task = make_task(radius=3.0)
    t0 = [[i,0,0] for i in range(5)]
    t1 = [[i+0.5,0,0] for i in range(5)]
    rewards = run_one_step(task, t0, t1)
    assert rewards.shape == (5,), f"Expected shape (5,), got {rewards.shape}"


def test_previous_positions_updated():
    """After call, previous_positions matches the last positions array."""
    task = make_task(radius=5.0)
    t0 = [[0,0,0], [2,0,0]]
    t1 = [[1,0,0], [3,0,0]]
    colloids1 = [FakeColloid(p) for p in t1]
    task.initialize([FakeColloid(p) for p in t0])
    task(colloids1)
    np.testing.assert_array_equal(
        task.previous_positions,
        np.array(t1, dtype=float),
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
