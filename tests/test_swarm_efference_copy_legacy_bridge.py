from System.swarm_efference_copy import (
    compare_action_effect,
    efference_copy_path,
    get_latest_efference_row,
    predict_action_effect,
)


def test_predict_action_effect_legacy_schema():
    predicted = predict_action_effect({
        "type": "explore",
        "target": "owner_context",
        "action_intensity": 0.8,
    })

    assert predicted["action_type"] == "explore"
    assert predicted["target"] == "owner_context"
    assert predicted["status"] == "completed"
    assert 0.0 < predicted["energy_used"] <= 0.08


def test_compare_action_effect_high_agency_when_result_matches(tmp_path):
    action = {"type": "explore", "target": "owner_context", "action_intensity": 1.0}
    result = {"status": "completed", "action": action, "latency": 0.1, "energy_used": 0.05}

    row = compare_action_effect(action, result, root=tmp_path, write_ledger=True, now=123.0)

    assert row["truth_label"] == "EFFERENCE_COPY"
    assert row["event_id"] == 143
    assert row["action"] == "explore"
    assert row["sensorimotor_pe"] == row["prediction_error"]
    assert row["self_generated"] is True
    assert row["agency_confidence"] > 0.55
    assert efference_copy_path(tmp_path).exists()
    latest = get_latest_efference_row(root=tmp_path)
    assert latest["trace_id"] == row["trace_id"]
    assert latest["sensorimotor_pe"] == row["sensorimotor_pe"]
    assert latest["predicted_effect"]["action_type"] == "explore"


def test_compare_action_effect_low_agency_when_observed_action_mismatches(tmp_path):
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
    assert row["observed_effect"]["action_match"] is False
