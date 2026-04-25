from __future__ import annotations

import numpy as np
import pytest

from System.swarm_adaptive_memory_weights import (
    AdaptiveMemoryWeights,
    AdaptiveWeightsConfig,
    features_from_unified_field,
)
from System.swarm_unified_field import UnifiedFieldConfig, UnifiedStigmergicField


def test_adaptive_memory_weights_learn_predictive_channel():
    adapter = AdaptiveMemoryWeights(
        AdaptiveWeightsConfig(lr=0.2, momentum=0.0, entropy_bonus=0.0)
    )
    features = np.array(
        [
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 2.0, 0.0, 0.0],
            [0.0, 3.0, 0.0, 0.0],
        ],
        dtype=np.float32,
    )
    rewards = np.array([0.0, 1.0, 2.0, 3.0], dtype=np.float32)

    for _ in range(3):
        weights = adapter.update(features, rewards)

    assert weights[1] > weights[0]
    assert weights[1] > 1.0
    assert adapter.score(features).shape == (4,)
    assert adapter.prev_reward == pytest.approx(1.5)
    assert adapter.normalized().sum() == pytest.approx(1.0)


def test_adaptive_memory_weights_validate_shapes_and_bounds():
    with pytest.raises(ValueError, match="n_fields"):
        AdaptiveWeightsConfig(n_fields=0)
    with pytest.raises(ValueError, match="momentum"):
        AdaptiveWeightsConfig(momentum=1.0)

    adapter = AdaptiveMemoryWeights(n_fields=4, lr=10.0, momentum=0.0, entropy_bonus=0.0)
    features = np.array([[0.0, 10.0, 0.0, 0.0], [0.0, -10.0, 0.0, 0.0]], dtype=np.float32)
    rewards = np.array([1.0, -1.0], dtype=np.float32)

    weights = adapter.update(features, rewards)

    assert float(weights.max()) <= adapter.cfg.max_weight
    with pytest.raises(ValueError, match="wrong number of fields"):
        adapter.score(np.ones((2, 3), dtype=np.float32))
    with pytest.raises(ValueError, match="rewards must match"):
        adapter.update(np.ones((2, 4), dtype=np.float32), np.ones(3, dtype=np.float32))


def test_adaptive_memory_weights_apply_to_unified_field():
    field = UnifiedStigmergicField(
        UnifiedFieldConfig(
            grid_size=16,
            diffusion=0.0,
            w_memory=1.0,
            w_prediction=0.8,
            w_attention=0.6,
            w_danger=1.2,
        )
    )
    pos = np.array([0.5, 0.5], dtype=np.float32)
    field.deposit(pos, "memory", 1.0)
    field.deposit(pos, "prediction", 2.0)
    field.deposit(pos, "attention", 3.0)
    field.deposit(pos, "danger", 0.5)

    adapter = AdaptiveMemoryWeights(n_fields=4)
    applied = adapter.apply_to_unified_field(field, [1.2, 1.4, 0.7, 0.2])
    total, channels = field.sense(pos)

    assert applied["alpha_memory"] == pytest.approx(1.2)
    assert applied["beta_prediction"] == pytest.approx(1.4)
    assert applied["salience_weight"] == pytest.approx(0.7)
    assert applied["delta_danger"] == pytest.approx(0.2)
    assert channels == pytest.approx((1.0, 2.0, 3.0, 0.5))
    assert total == pytest.approx(1.2 + 2.8 + 2.1 - 0.1)


def test_features_from_unified_field_samples_four_channels():
    field = UnifiedStigmergicField(UnifiedFieldConfig(grid_size=16, diffusion=0.0))
    positions = np.array([[0.25, 0.25], [0.75, 0.75]], dtype=np.float32)
    field.deposit(positions[0], "memory", 2.0)
    field.deposit(positions[1], "danger", 3.0)

    features = features_from_unified_field(field, positions)

    assert features.shape == (2, 4)
    assert features[0, 0] == pytest.approx(2.0)
    assert features[1, 3] == pytest.approx(3.0)
