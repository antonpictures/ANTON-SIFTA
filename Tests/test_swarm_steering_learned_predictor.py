"""Tests for the receipt-trained steering predictor.

This closes the honest gap:
route -> receipt -> self-model -> predicted route -> audit -> governor proposal
-> learned detector route table -> guarded self-model coupling.

The tests pin the safety posture: no learned route below 10 paired samples.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_steering_learned_predictor import (  # noqa: E402
    CALIBRATION_CYCLE_LEDGER,
    MIN_SAMPLES_TO_LEARN,
    PREDICTOR_LEDGER,
    PREDICTOR_MODEL,
    TRUTH_BOUNDARY,
    TRUTH_LABEL,
    latest_governor_weights,
    learned_predictor_prompt_block,
    load_learned_predictor_model,
    predict_route_with_learned_model,
    run_full_calibration_cycle,
    train_predictor_from_audit,
    write_learned_predictor_receipt,
)
from System.swarm_steering_self_model import model_self_state  # noqa: E402


def _pair(i: int, detector: str, actual_route: str) -> dict:
    return {
        "prediction_trace_id": f"self-{detector}-{i}",
        "actual_trace_id": f"actual-{detector}-{i}",
        "predicted_ts": float(i),
        "actual_ts": float(i) + 0.5,
        "predicted_next_route": "DEEP_CORTEX",
        "actual_route": actual_route,
        "correct": actual_route == "DEEP_CORTEX",
        "confidence": 0.75,
        "dominant_detector": detector,
        "fired_detectors": [detector],
        "time_to_next_turn_s": 0.5,
    }


def _audit(detector: str, actual_route: str, n: int) -> dict:
    return {
        "trace_id": "audit-test",
        "sample_count": n,
        "pairs": [_pair(i, detector, actual_route) for i in range(n)],
    }


def _novelty_rows(n: int = 10) -> list[dict]:
    return [
        {
            "route": "DEEP_CORTEX",
            "priority": 0.3,
            "interrupt": 0.1,
            "care": 0.1,
            "signals": {"novelty": 0.82},
        }
        for _ in range(n)
    ]


def test_truth_boundary_names_sample_gate():
    assert TRUTH_LABEL == "STEERING_LEARNED_PREDICTOR_V1"
    assert "sample_count" in TRUTH_BOUNDARY
    assert "not neural" in TRUTH_BOUNDARY.lower()


def test_train_predictor_refuses_below_min_samples():
    model = train_predictor_from_audit(_audit("novelty_pressure", "FAST_REFLEX", 2))
    assert model.status == "INSUFFICIENT_PAIRED_DATA"
    det = model.detector_models["novelty_pressure"]
    assert det.sample_count == 2
    assert det.ready is False
    assert model.open_gaps


def test_train_predictor_ready_after_min_samples():
    model = train_predictor_from_audit(
        _audit("novelty_pressure", "FAST_REFLEX", MIN_SAMPLES_TO_LEARN)
    )
    assert model.status == "READY"
    det = model.detector_models["novelty_pressure"]
    assert det.ready is True
    assert det.best_route == "FAST_REFLEX"
    assert det.route_counts["FAST_REFLEX"] == MIN_SAMPLES_TO_LEARN


def test_write_predictor_receipt_and_model_round_trip(tmp_path):
    model = train_predictor_from_audit(_audit("novelty_pressure", "FAST_REFLEX", 12))
    receipt = write_learned_predictor_receipt(model, state_dir=tmp_path, now=123.0)
    assert receipt["schema"] == "SIFTA_STEERING_LEARNED_PREDICTOR_RECEIPT_V1"
    assert receipt["truth_boundary"] == TRUTH_BOUNDARY
    assert (tmp_path / PREDICTOR_LEDGER).exists()
    assert (tmp_path / PREDICTOR_MODEL).exists()
    loaded = load_learned_predictor_model(state_dir=tmp_path)
    assert loaded is not None
    assert loaded.detector_models["novelty_pressure"].best_route == "FAST_REFLEX"


def test_predict_route_uses_fallback_without_model(tmp_path):
    pred = predict_route_with_learned_model(
        ["novelty_pressure"],
        fallback_route="DEEP_CORTEX",
        state_dir=tmp_path,
    )
    assert pred.learned_used is False
    assert pred.route == "DEEP_CORTEX"
    assert pred.status == "NO_MODEL"


def test_predict_route_uses_learned_model_when_ready(tmp_path):
    model = train_predictor_from_audit(
        _audit("novelty_pressure", "FAST_REFLEX", 12),
        state_dir=tmp_path,
        write=True,
    )
    pred = predict_route_with_learned_model(
        ["novelty_pressure"],
        fallback_route="DEEP_CORTEX",
        state_dir=tmp_path,
    )
    assert model.status == "READY"
    assert pred.learned_used is True
    assert pred.route == "FAST_REFLEX"
    assert pred.confidence > 0.0


def test_governor_weights_couple_into_learned_route_scores(tmp_path):
    pairs = [_pair(i, "novelty_pressure", "FAST_REFLEX") for i in range(12)]
    pairs += [_pair(100 + i, "truth_risk_burn", "VERIFY_BEFORE_ACTION") for i in range(12)]
    model = train_predictor_from_audit({"trace_id": "audit", "sample_count": 24, "pairs": pairs})
    # Two detectors fire. The governor weight makes truth_risk_burn dominate.
    pred = predict_route_with_learned_model(
        ["novelty_pressure", "truth_risk_burn"],
        fallback_route="DEEP_CORTEX",
        model=model,
        governor_weights={"novelty_pressure": 0.5, "truth_risk_burn": 1.5},
    )
    assert pred.learned_used is True
    assert pred.route == "VERIFY_BEFORE_ACTION"
    assert pred.governor_weights["truth_risk_burn"] == 1.5


def test_self_model_falls_back_when_learned_data_insufficient(tmp_path):
    train_predictor_from_audit(
        _audit("novelty_pressure", "FAST_REFLEX", 2),
        state_dir=tmp_path,
        write=True,
    )
    state = model_self_state(rows=_novelty_rows(), state_dir=tmp_path)
    assert state.predicted_next_route == "DEEP_CORTEX"


def test_self_model_uses_learned_predictor_when_ready(tmp_path):
    train_predictor_from_audit(
        _audit("novelty_pressure", "FAST_REFLEX", 12),
        state_dir=tmp_path,
        write=True,
    )
    state = model_self_state(rows=_novelty_rows(), state_dir=tmp_path)
    assert state.predicted_next_route == "FAST_REFLEX"


def test_latest_governor_weights_reads_adaptation_ledger(tmp_path):
    row = {
        "detector_weights": {"novelty_pressure": 1.25, "truth_risk_burn": "0.95"},
    }
    (tmp_path / "steering_adaptation_governor.jsonl").write_text(
        json.dumps(row) + "\n",
        encoding="utf-8",
    )
    weights = latest_governor_weights(state_dir=tmp_path)
    assert weights == {"novelty_pressure": 1.25, "truth_risk_burn": 0.95}


def test_prompt_block_exposes_open_gaps():
    model = train_predictor_from_audit(_audit("novelty_pressure", "FAST_REFLEX", 2))
    block = learned_predictor_prompt_block(model)
    assert "STEERING LEARNED PREDICTOR" in block
    assert "INSUFFICIENT_PAIRED_DATA" in block
    assert "open_gaps" in block


def test_full_calibration_cycle_writes_summary_receipt(tmp_path):
    self_lines = []
    steering_lines = []
    for i in range(12):
        t = float(i * 10)
        self_lines.append(json.dumps({
            "ts": t,
            "trace_id": f"self-{i}",
            "predicted_next_route": "DEEP_CORTEX",
            "dominant": "novelty_pressure",
            "signals": [
                {"name": "novelty_pressure", "value": 0.82, "threshold": 0.55, "fired": True},
            ],
            "route_counts": {"DEEP_CORTEX": 3},
        }))
        steering_lines.append(json.dumps({
            "ts": t + 1.0,
            "trace_id": f"actual-{i}",
            "route": "FAST_REFLEX",
        }))
    (tmp_path / "steering_self_model.jsonl").write_text("\n".join(self_lines) + "\n", encoding="utf-8")
    (tmp_path / "steering_subsystem.jsonl").write_text("\n".join(steering_lines) + "\n", encoding="utf-8")

    cycle = run_full_calibration_cycle(state_dir=tmp_path, write=True, now=500.0)

    assert cycle["audit"]["sample_count"] == 12
    assert cycle["learned_predictor"]["status"] == "READY"
    assert cycle["learned_predictor"]["ready_detectors"] == ["novelty_pressure"]
    assert (tmp_path / CALIBRATION_CYCLE_LEDGER).exists()
    receipt = json.loads((tmp_path / CALIBRATION_CYCLE_LEDGER).read_text(encoding="utf-8").strip())
    assert receipt["schema"] == "SIFTA_STEERING_CALIBRATION_CYCLE_RECEIPT_V1"
    assert receipt["payload"]["learned_predictor"]["status"] == "READY"
