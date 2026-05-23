"""Tests for steering prediction audit.

The self-model predicts a next steering route. This audit pairs that
prediction with the next actual steering receipt and scores whether the
self-model is becoming a usable signal.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_steering_prediction_audit import (  # noqa: E402
    PREDICTION_AUDIT_LEDGER,
    SELF_MODEL_LEDGER,
    STEERING_LEDGER,
    TRUTH_BOUNDARY,
    TRUTH_LABEL,
    audit_predictions,
    demo_prediction_audit,
    pair_predictions,
    prediction_audit_prompt_block,
    read_prediction_inputs,
    write_prediction_audit_receipt,
)


def _self_row(ts, route, dominant="novelty_pressure", trace="self", fired=None):
    fired = fired or [dominant]
    return {
        "ts": float(ts),
        "trace_id": trace,
        "predicted_next_route": route,
        "dominant": dominant,
        "signals": [
            {
                "name": name,
                "value": 0.80,
                "threshold": 0.55 if name != "truth_risk_burn" else 0.50,
                "fired": True,
            }
            for name in fired
        ],
        "route_counts": {route: 2},
    }


def _actual_row(ts, route, trace="actual"):
    return {"ts": float(ts), "trace_id": trace, "route": route}


def test_truth_labels_are_stable():
    assert TRUTH_LABEL == "STEERING_PREDICTION_AUDIT_V1"
    assert STEERING_LEDGER == "steering_subsystem.jsonl"
    assert SELF_MODEL_LEDGER == "steering_self_model.jsonl"
    assert PREDICTION_AUDIT_LEDGER == "steering_prediction_audit.jsonl"
    assert "prediction accuracy" in TRUTH_BOUNDARY


def test_pair_predictions_uses_next_actual_route():
    pairs = pair_predictions(
        [_self_row(10, "DEEP_CORTEX", trace="s1")],
        [
            _actual_row(9, "FAST_REFLEX", trace="a0"),
            _actual_row(11, "DEEP_CORTEX", trace="a1"),
        ],
    )
    assert len(pairs) == 1
    assert pairs[0].prediction_trace_id == "s1"
    assert pairs[0].actual_trace_id == "a1"
    assert pairs[0].correct is True
    assert pairs[0].time_to_next_turn_s == 1.0


def test_pair_predictions_marks_wrong_route():
    pairs = pair_predictions(
        [_self_row(20, "VERIFY_BEFORE_ACTION", "truth_risk_burn", "s2")],
        [_actual_row(21, "NORMAL_CORTEX", "a2")],
    )
    assert len(pairs) == 1
    assert pairs[0].correct is False
    assert pairs[0].dominant_detector == "truth_risk_burn"


def test_audit_computes_accuracy_and_group_stats():
    self_rows = [
        _self_row(10, "DEEP_CORTEX", trace="s1"),
        _self_row(20, "VERIFY_BEFORE_ACTION", "truth_risk_burn", "s2"),
    ]
    actual_rows = [
        _actual_row(11, "DEEP_CORTEX", "a1"),
        _actual_row(21, "NORMAL_CORTEX", "a2"),
    ]
    audit = audit_predictions(self_rows=self_rows, steering_rows=actual_rows)
    assert audit.sample_count == 2
    assert audit.correct_count == 1
    assert audit.accuracy == 0.5
    assert audit.status == "PAIRED_BUT_UNDERPOWERED"
    assert audit.by_dominant_detector["novelty_pressure"]["accuracy"] == 1.0
    assert audit.by_dominant_detector["truth_risk_burn"]["accuracy"] == 0.0
    assert audit.by_detector["novelty_pressure"]["sample_count"] == 1


def test_audit_reports_no_pairs_cleanly():
    audit = audit_predictions(self_rows=[], steering_rows=[])
    assert audit.sample_count == 0
    assert audit.accuracy == 0.0
    assert audit.status == "UNTESTED_NO_PAIRED_PREDICTIONS"
    assert prediction_audit_prompt_block(audit) == ""


def test_status_reliable_when_accuracy_high():
    self_rows = [_self_row(i * 10, "DEEP_CORTEX", trace=f"s{i}") for i in range(4)]
    actual_rows = [_actual_row(i * 10 + 1, "DEEP_CORTEX", f"a{i}") for i in range(4)]
    audit = audit_predictions(self_rows=self_rows, steering_rows=actual_rows)
    assert audit.accuracy == 1.0
    assert audit.status == "RELIABLE_IN_WINDOW"


def test_status_low_accuracy_when_mismatch():
    self_rows = [_self_row(i * 10, "DEEP_CORTEX", trace=f"s{i}") for i in range(4)]
    actual_rows = [_actual_row(i * 10 + 1, "FAST_REFLEX", f"a{i}") for i in range(4)]
    audit = audit_predictions(self_rows=self_rows, steering_rows=actual_rows)
    assert audit.accuracy == 0.0
    assert audit.status == "LOW_ACCURACY_SELF_MODEL_MISMATCH"


def test_status_getting_better_when_recent_half_improves():
    self_rows = [_self_row(i * 10, "DEEP_CORTEX", trace=f"s{i}") for i in range(8)]
    actual_routes = ["FAST_REFLEX", "FAST_REFLEX", "FAST_REFLEX", "NORMAL_CORTEX",
                     "DEEP_CORTEX", "DEEP_CORTEX", "DEEP_CORTEX", "DEEP_CORTEX"]
    actual_rows = [_actual_row(i * 10 + 1, route, f"a{i}") for i, route in enumerate(actual_routes)]
    audit = audit_predictions(self_rows=self_rows, steering_rows=actual_rows)
    assert audit.status == "GETTING_BETTER"


def test_status_drifting_worse_when_recent_half_degrades():
    self_rows = [_self_row(i * 10, "DEEP_CORTEX", trace=f"s{i}") for i in range(8)]
    actual_routes = ["DEEP_CORTEX", "DEEP_CORTEX", "DEEP_CORTEX", "DEEP_CORTEX",
                     "FAST_REFLEX", "FAST_REFLEX", "NORMAL_CORTEX", "NORMAL_CORTEX"]
    actual_rows = [_actual_row(i * 10 + 1, route, f"a{i}") for i, route in enumerate(actual_routes)]
    audit = audit_predictions(self_rows=self_rows, steering_rows=actual_rows)
    assert audit.status == "DRIFTING_WORSE"


def test_receipt_is_sha256_signed_and_round_trips(tmp_path):
    audit = audit_predictions(
        self_rows=[_self_row(10, "DEEP_CORTEX")],
        steering_rows=[_actual_row(11, "DEEP_CORTEX")],
    )
    row = write_prediction_audit_receipt(audit, state_dir=tmp_path, now=123.0)
    body = {k: v for k, v in audit.to_dict().items() if k != "trace_id"}
    expected = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    assert row["sha256"] == expected
    assert row["schema"] == "SIFTA_STEERING_PREDICTION_AUDIT_RECEIPT_V1"
    assert row["truth_boundary"] == TRUTH_BOUNDARY
    parsed = json.loads((tmp_path / PREDICTION_AUDIT_LEDGER).read_text().strip())
    assert parsed["sha256"] == expected
    assert parsed["sample_count"] == 1


def test_read_prediction_inputs_skips_corrupt_lines(tmp_path):
    (tmp_path / SELF_MODEL_LEDGER).write_text(
        json.dumps(_self_row(10, "DEEP_CORTEX")) + "\nnot json\n",
        encoding="utf-8",
    )
    (tmp_path / STEERING_LEDGER).write_text(
        "bad\n" + json.dumps(_actual_row(11, "DEEP_CORTEX")) + "\n",
        encoding="utf-8",
    )
    self_rows, steering_rows = read_prediction_inputs(state_dir=tmp_path)
    assert len(self_rows) == 1
    assert len(steering_rows) == 1


def test_prediction_audit_prompt_block_summarizes_accuracy():
    audit = audit_predictions(
        self_rows=[_self_row(10, "DEEP_CORTEX")],
        steering_rows=[_actual_row(11, "DEEP_CORTEX")],
    )
    block = prediction_audit_prompt_block(audit)
    assert "STEERING PREDICTION AUDIT" in block
    assert "accuracy: 1.000 (1/1)" in block
    assert TRUTH_LABEL in block


def test_demo_prediction_audit_smoke():
    demo = demo_prediction_audit()
    assert demo["truth_label"] == TRUTH_LABEL
    assert demo["audit"]["sample_count"] == 2
    assert "prompt_block" in demo
