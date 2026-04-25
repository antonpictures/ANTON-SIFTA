from __future__ import annotations

import numpy as np
import pytest

from System.swarm_immune_quorum import ImmuneQuorumConfig, SwarmImmuneQuorum


def test_inject_damage_marks_local_danger_without_global_spread():
    quorum = SwarmImmuneQuorum(ImmuneQuorumConfig(grid_size=32, danger_deposit=1.5))

    quorum.inject_damage(np.array([[0.50, 0.50]], dtype=np.float32), radius=0.05)

    assert float(quorum.danger.max()) == pytest.approx(1.5)
    assert np.count_nonzero(quorum.danger) < quorum.danger.size * 0.05
    assert quorum.glyph("danger")


def test_step_writes_signal_then_repairs_danger_after_quorum():
    cfg = ImmuneQuorumConfig(
        grid_size=32,
        decay=1.0,
        diffusion=0.0,
        signal_deposit=1.0,
        danger_deposit=2.0,
        repair_deposit=0.8,
        quorum_threshold=0.2,
    )
    quorum = SwarmImmuneQuorum(cfg)
    positions0 = np.array([[0.45, 0.50], [0.55, 0.50]], dtype=np.float32)
    positions1 = np.array([[0.50, 0.50], [0.50, 0.52]], dtype=np.float32)

    quorum.inject_damage(np.array([[0.50, 0.50]], dtype=np.float32), radius=0.06)
    center_idx = quorum._idx(positions1[0])
    danger_before = float(quorum.danger[center_idx])
    first = quorum.step(positions0)
    second = quorum.step(positions1)
    third = quorum.step(positions1)

    assert np.all(first == 0.0)
    assert float(quorum.signal.max()) > 0.0
    assert float(quorum.repair.max()) > 0.0
    assert float(quorum.danger[center_idx]) < danger_before
    assert float(second.max()) > -1.0
    assert float(third.max()) > float(second.min())


def test_sense_returns_signal_danger_repair_channels():
    quorum = SwarmImmuneQuorum(ImmuneQuorumConfig(grid_size=16))
    positions = np.array([[0.25, 0.25], [0.75, 0.75]], dtype=np.float32)

    quorum.inject_damage(positions[:1], radius=0.04)
    obs = quorum.sense(positions)

    assert obs.shape == (2, 3)
    assert obs[0, 1] > obs[1, 1]


def test_shape_validation_rejects_bad_inputs():
    quorum = SwarmImmuneQuorum(ImmuneQuorumConfig(grid_size=16))

    with pytest.raises(ValueError, match="positions"):
        quorum.step(np.array([0.5, 0.5], dtype=np.float32))
    with pytest.raises(ValueError, match="centers"):
        quorum.inject_damage(np.array([0.5, 0.5], dtype=np.float32))
    with pytest.raises(ValueError, match="radius"):
        quorum.inject_damage(np.array([[0.5, 0.5]], dtype=np.float32), radius=-0.1)
