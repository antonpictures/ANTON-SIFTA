from __future__ import annotations

import numpy as np
import pytest

from System.swarm_efference_copy import EfferenceConfig, EfferenceCopySystem, proof_of_property
from System.swarm_efference_copy import (
    compare_action_effect,
    efference_copy_path,
    get_latest_efference_row,
    predict_action_effect,
    summary_for_prompt,
)


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


def test_event143_predicts_minimal_action_effect():
    action = {"type": "explore", "target": "owner_context", "action_intensity": 0.8}

    predicted = predict_action_effect(action)

    assert predicted["action_type"] == "explore"
    assert predicted["status"] == "completed"
    assert predicted["target"] == "owner_context"
    assert 0.0 < predicted["energy_used"] <= 0.05


def test_event143_high_agency_when_result_matches(tmp_path):
    action = {"type": "explore", "target": "owner_context", "action_intensity": 1.0}
    result = {"status": "completed", "action": action, "latency": 0.1, "energy_used": 0.05}

    row = compare_action_effect(action, result, root=tmp_path, write_ledger=True, now=123.0)

    assert row["truth_label"] == "EFFERENCE_COPY"
    assert row["event_id"] == 143
    assert row["self_generated"] is True
    assert row["agency_confidence"] > 0.95
    assert efference_copy_path(tmp_path).exists()
    assert get_latest_efference_row(root=tmp_path)["trace_id"] == row["trace_id"]


def test_event143_low_agency_when_observed_action_mismatches(tmp_path):
    action = {"type": "explore", "target": "owner_context"}
    result = {
        "status": "failed",
        "action": {"type": "rest", "target": "unexpected"},
        "latency": 2.5,
        "energy_used": 1.0,
    }

    row = compare_action_effect(action, result, root=tmp_path, write_ledger=False)

    assert row["self_generated"] is False
    assert row["agency_confidence"] < 0.5
    assert row["sensorimotor_pe"] > 0.5


def test_event143_summary_for_prompt(tmp_path):
    action = {"type": "forage", "target": "pouw_work"}
    result = {"status": "completed", "action": action, "latency": 0.1, "energy_used": 0.05}
    compare_action_effect(action, result, root=tmp_path, write_ledger=True)

    summary = summary_for_prompt(root=tmp_path)

    assert "EFFERENCE COPY" in summary
    assert "action=forage" in summary
    assert "agency_confidence=" in summary


def test_event143_disable_env_does_not_write(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_EFFERENCE_DISABLE", "1")
    row = compare_action_effect({}, {}, root=tmp_path, write_ledger=True)

    assert row["disabled"] is True
    assert row["agency_confidence"] == 0.5
    assert not efference_copy_path(tmp_path).exists()
