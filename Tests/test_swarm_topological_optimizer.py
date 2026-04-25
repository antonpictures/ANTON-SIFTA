from __future__ import annotations

import numpy as np
import pytest

from System.swarm_topological_optimizer import (
    TopologicalSwarmOptimizer,
    TopologyConfig,
    proof_of_property,
)


def test_k_nearest_uses_fixed_neighbor_count_not_radius():
    optimizer = TopologicalSwarmOptimizer(TopologyConfig(k_neighbors=2))
    positions = np.array(
        [[0.0, 0.0], [10.0, 0.0], [11.0, 0.0], [100.0, 0.0]],
        dtype=np.float32,
    )

    neighbors = optimizer._k_nearest(positions, 0)

    assert neighbors.tolist() == [1, 2]


def test_alignment_reduces_velocity_variance_and_clamps_speed():
    cfg = TopologyConfig(
        k_neighbors=2,
        alignment_weight=0.8,
        cohesion_weight=0.0,
        separation_weight=0.0,
        max_speed=0.05,
    )
    optimizer = TopologicalSwarmOptimizer(cfg)
    positions = np.array(
        [[0.0, 0.0], [0.2, 0.0], [0.4, 0.0], [0.6, 0.0], [0.8, 0.0]],
        dtype=np.float32,
    )
    velocities = np.array(
        [[0.05, 0.0], [-0.05, 0.0], [0.05, 0.0], [-0.05, 0.0], [0.05, 0.0]],
        dtype=np.float32,
    )

    before_variance = float(np.var(velocities[:, 0]))
    after = velocities
    for _ in range(8):
        after = optimizer.step(positions, after)

    assert float(np.var(after[:, 0])) < before_variance
    assert float(np.linalg.norm(after, axis=1).max()) <= cfg.max_speed + cfg.eps


def test_separation_pushes_close_agents_apart():
    optimizer = TopologicalSwarmOptimizer(
        TopologyConfig(
            k_neighbors=1,
            alignment_weight=0.0,
            cohesion_weight=0.0,
            separation_weight=0.1,
            separation_scale=0.1,
            max_speed=0.2,
        )
    )
    positions = np.array([[0.5, 0.5], [0.51, 0.5]], dtype=np.float32)
    velocities = np.zeros_like(positions)

    after = optimizer.step(positions, velocities)

    assert after[0, 0] < 0.0
    assert after[1, 0] > 0.0


def test_far_topological_neighbors_do_not_repel_forever():
    optimizer = TopologicalSwarmOptimizer(
        TopologyConfig(
            k_neighbors=1,
            alignment_weight=0.0,
            cohesion_weight=0.0,
            separation_weight=0.1,
            separation_scale=0.1,
            max_speed=0.2,
        )
    )
    positions = np.array([[0.0, 0.0], [10.0, 0.0]], dtype=np.float32)
    velocities = np.zeros_like(positions)

    after = optimizer.step(positions, velocities)

    assert after == pytest.approx(np.zeros_like(positions), abs=1e-6)


def test_blend_with_field_combines_topology_and_gradient():
    optimizer = TopologicalSwarmOptimizer(
        TopologyConfig(
            k_neighbors=1,
            alignment_weight=0.0,
            cohesion_weight=0.0,
            separation_weight=0.0,
            inertia_weight=1.0,
            max_speed=1.0,
        )
    )
    positions = np.array([[0.0, 0.0], [1.0, 0.0]], dtype=np.float32)
    velocities = np.array([[0.2, 0.0], [0.2, 0.0]], dtype=np.float32)
    gradients = np.array([[0.0, 0.4], [0.0, 0.4]], dtype=np.float32)

    blended = optimizer.blend_with_field(positions, velocities, gradients, topology_weight=0.5)

    assert blended[0] == pytest.approx([0.1, 0.2])
    assert blended[1] == pytest.approx([0.1, 0.2])


def test_topological_optimizer_validation_and_proof():
    with pytest.raises(ValueError, match="k_neighbors"):
        TopologyConfig(k_neighbors=0)
    with pytest.raises(ValueError, match="separation_scale"):
        TopologyConfig(separation_scale=0.0)
    with pytest.raises(ValueError, match="velocities"):
        TopologicalSwarmOptimizer().step(
            np.zeros((2, 2), dtype=np.float32),
            np.zeros((2, 3), dtype=np.float32),
        )
    with pytest.raises(ValueError, match="topology_weight"):
        TopologicalSwarmOptimizer().blend_with_field(
            np.zeros((2, 2), dtype=np.float32),
            np.zeros((2, 2), dtype=np.float32),
            np.zeros((2, 2), dtype=np.float32),
            topology_weight=1.5,
        )

    assert proof_of_property() is True
