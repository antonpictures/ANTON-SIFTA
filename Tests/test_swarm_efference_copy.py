from __future__ import annotations

import numpy as np
import pytest

from System.swarm_efference_copy import EfferenceConfig, EfferenceCopySystem, proof_of_property


def test_self_motion_cancels_to_zero_residual():
    efference = EfferenceCopySystem(EfferenceConfig(initial_gain=1.0))
    motor = np.array([4.0, -2.0], dtype=np.float32)
    observed = np.array([4.0, -2.0], dtype=np.float32)

    residual = efference.filter(motor, observed)

    assert residual == pytest.approx([0.0, 0.0], abs=1e-6)


def test_external_motion_survives_camera_motion_filter():
    efference = EfferenceCopySystem(EfferenceConfig(initial_gain=1.0))
    motor = np.array([3.0, 0.0], dtype=np.float32)
    external = np.array([0.0, 1.25], dtype=np.float32)
    observed = motor + external

    residual = efference.filter(motor, observed)

    assert residual == pytest.approx(external, abs=1e-6)


def test_adaptation_learns_cross_axis_hardware_mapping():
    cfg = EfferenceConfig(initial_gain=1.0, adapt_rate=0.1)
    efference = EfferenceCopySystem(cfg)
    true_physics = np.array([[1.45, 0.15], [-0.1, 1.25]], dtype=np.float32)
    rng = np.random.default_rng(72)

    for _ in range(200):
        motor = rng.uniform(-3.0, 3.0, size=2).astype(np.float32)
        observed = motor @ true_physics
        efference.filter(motor, observed)
        efference.adapt(observed)

    assert np.linalg.norm(efference.gain_matrix - true_physics) < 0.04


def test_batch_adaptation_ignores_deadzone_and_learns_valid_samples():
    efference = EfferenceCopySystem(EfferenceConfig(initial_gain=1.0, adapt_rate=0.2, deadzone=0.1))
    true_physics = np.array([[1.2, 0.0], [0.0, 0.8]], dtype=np.float32)
    motors = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, -1.0], [2.0, 1.0]], dtype=np.float32)

    for _ in range(80):
        observed = motors @ true_physics
        efference.filter(motors, observed)
        efference.adapt(observed)

    assert np.linalg.norm(efference.gain_matrix - true_physics) < 0.03


def test_efference_copy_validates_shapes_and_config():
    with pytest.raises(ValueError, match="adapt_rate"):
        EfferenceConfig(adapt_rate=0.0)
    efference = EfferenceCopySystem()

    with pytest.raises(ValueError, match="2-vector"):
        efference.predict(np.array([1.0, 2.0, 3.0], dtype=np.float32))
    with pytest.raises(ValueError, match="matching shapes"):
        efference.correct(
            np.zeros(2, dtype=np.float32),
            np.zeros((2, 2), dtype=np.float32),
        )
    with pytest.raises(ValueError, match="finite"):
        efference.filter(
            np.array([np.nan, 0.0], dtype=np.float32),
            np.zeros(2, dtype=np.float32),
        )


def test_efference_copy_proof_of_property_passes():
    assert proof_of_property() is True
