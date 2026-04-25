from __future__ import annotations

import numpy as np
import pytest

from System.swarm_stigmergic_premonition import (
    PremonitionConfig,
    StigmergicPremonitionField,
    proof_of_property,
)
from Utilities.stigmergic_premonition_demo import run_demo


def test_future_traces_and_surprise_are_written():
    field = StigmergicPremonitionField(PremonitionConfig(grid_size=32, horizon=6, diffusion=0.0))
    first = np.array([[0.20, 0.50], [0.80, 0.50]], dtype=np.float32)
    second = np.array([[0.25, 0.50], [0.75, 0.50]], dtype=np.float32)

    assert np.all(field.step(first) == 0.0)
    rewards = field.step(second)

    assert field.future.max() > 0.0
    assert field.surprise.max() > 0.0
    assert rewards.shape == (2,)
    assert field.glyph("future")


def test_collision_corridor_is_penalized_more_than_open_space():
    field = StigmergicPremonitionField(PremonitionConfig(grid_size=64, horizon=8, diffusion=0.0))
    first = np.array([[0.30, 0.50], [0.70, 0.50]], dtype=np.float32)
    second = np.array([[0.40, 0.50], [0.60, 0.50]], dtype=np.float32)
    third = np.array([[0.50, 0.50], [0.50, 0.52]], dtype=np.float32)
    open_space = np.array([[0.10, 0.10], [0.90, 0.90]], dtype=np.float32)

    field.step(first)
    field.step(second)
    collision_obs = field.sense(third)
    open_obs = field.sense(open_space)

    assert collision_obs[:, 0].mean() > open_obs[:, 0].mean()


def test_predictable_motion_has_lower_surprise_than_turning_motion():
    predictable = StigmergicPremonitionField(PremonitionConfig(grid_size=48, horizon=5))
    turning = StigmergicPremonitionField(PremonitionConfig(grid_size=48, horizon=5))

    predictable.step(np.array([[0.20, 0.20]], dtype=np.float32))
    predictable.step(np.array([[0.25, 0.20]], dtype=np.float32))
    predictable.step(np.array([[0.30, 0.20]], dtype=np.float32))

    turning.step(np.array([[0.20, 0.20]], dtype=np.float32))
    turning.step(np.array([[0.25, 0.20]], dtype=np.float32))
    turning.step(np.array([[0.25, 0.30]], dtype=np.float32))

    assert turning.surprise.max() > predictable.surprise.max()


def test_reset_and_validation():
    field = StigmergicPremonitionField(PremonitionConfig(grid_size=16))
    field.step(np.array([[0.1, 0.1]], dtype=np.float32))
    field.step(np.array([[0.2, 0.1]], dtype=np.float32))

    field.reset()

    assert field.future.max() == 0.0
    assert field.surprise.max() == 0.0
    assert field.prev_positions is None
    with pytest.raises(ValueError, match="positions"):
        field.step(np.array([0.1, 0.2], dtype=np.float32))
    with pytest.raises(ValueError, match="mode"):
        field.glyph("magic")  # type: ignore[arg-type]


def test_demo_and_proof_pass():
    assert proof_of_property() is True
    result = run_demo(n_agents=8, steps=16, glyph_every=0, clear=False)

    assert result["future_max"] > 0.0
    assert result["surprise_max"] > 0.0
    assert result["glyph"]
