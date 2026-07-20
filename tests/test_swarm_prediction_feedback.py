"""Tests for the prediction feedback loop."""
from __future__ import annotations

import json
from pathlib import Path

from System.swarm_prediction_feedback import (
    FeedbackReport,
    PredictionPair,
    adapt_weights,
    compute_feedback,
    feedback_prompt_block,
    pair_predictions,
    record_outcome,
    record_owner_correction,
)
from System.stigmergic_prediction_engine import build_prediction, write_prediction


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _local_ts(year: int, month: int, day: int, hour: int, minute: int) -> float:
    from datetime import datetime

    return datetime(year, month, day, hour, minute).timestamp()


def test_record_outcome_appends_to_ledger(tmp_path):
    state = tmp_path / ".sifta_state"
    row = record_outcome(label="meal", ts=_local_ts(2026, 7, 11, 9, 30), state_dir=state)
    assert row["label"] == "meal"
    assert row["kind"] == "outcome"
    assert row["truth_label"] == "PREDICTION_FEEDBACK_V1"
    ledger = state / "prediction_feedback.jsonl"
    assert ledger.exists()
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    assert len(rows) == 1
    assert rows[0]["label"] == "meal"


def test_record_owner_correction(tmp_path):
    state = tmp_path / ".sifta_state"
    row = record_owner_correction(
        predicted_label="meal", actual_label="desk_work", state_dir=state
    )
    assert row["kind"] == "correction"
    assert row["predicted_label"] == "meal"
    assert row["actual_label"] == "desk_work"


def test_pair_predictions_matches_label_and_time(tmp_path):
    predictions = [
        {
            "ts": _local_ts(2026, 7, 11, 9, 0),
            "trace_id": "pred-1",
            "next_likely_segment": "meal",
            "confidence": 0.75,
            "expected_start_min": 30,
            "now_minute_of_day": 9 * 60,
        }
    ]
    outcomes = [
        {
            "ts": _local_ts(2026, 7, 11, 9, 32),
            "label": "meal",
            "minute_of_day": 9 * 60 + 32,
            "kind": "outcome",
        }
    ]
    pairs = pair_predictions(predictions, outcomes)
    assert len(pairs) == 1
    assert pairs[0].correct is True
    assert pairs[0].predicted_label == "meal"
    assert pairs[0].brier < 0.1


def test_pair_predictions_no_match_on_wrong_label():
    predictions = [
        {
            "ts": _local_ts(2026, 7, 11, 9, 0),
            "trace_id": "pred-1",
            "next_likely_segment": "meal",
            "confidence": 0.75,
            "expected_start_min": 30,
            "now_minute_of_day": 9 * 60,
        }
    ]
    outcomes = [
        {
            "ts": _local_ts(2026, 7, 11, 9, 32),
            "label": "desk_work",
            "minute_of_day": 9 * 60 + 32,
            "kind": "outcome",
        }
    ]
    pairs = pair_predictions(predictions, outcomes)
    assert len(pairs) == 0


def test_pair_predictions_no_match_outside_window():
    predictions = [
        {
            "ts": _local_ts(2026, 7, 11, 9, 0),
            "trace_id": "pred-1",
            "next_likely_segment": "meal",
            "confidence": 0.75,
            "expected_start_min": 30,
            "now_minute_of_day": 9 * 60,
        }
    ]
    outcomes = [
        {
            "ts": _local_ts(2026, 7, 11, 12, 0),
            "label": "meal",
            "minute_of_day": 12 * 60,
            "kind": "outcome",
        }
    ]
    pairs = pair_predictions(predictions, outcomes, match_window_min=60)
    assert len(pairs) == 0


def test_compute_feedback_empty_when_no_data(tmp_path):
    state = tmp_path / ".sifta_state"
    report = compute_feedback(state_dir=state, write=False)
    assert report.total_predictions == 0
    assert report.matched_outcomes == 0
    assert report.accuracy == 0.0
    assert report.status == "UNTESTED_NO_PAIRED_PREDICTIONS"


def test_compute_feedback_with_paired_data(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    now = _local_ts(2026, 7, 11, 9, 0)
    _write_jsonl(
        state / "architect_day_segments.jsonl",
        [
            {
                "ts": now - 60,
                "label": "meal",
                "start_minute_of_day": 9 * 60 + 30,
                "segment_id": "meal-1",
            }
        ],
    )
    write_prediction(state_dir=state, now=now)
    record_outcome(label="meal", ts=now + 1800, state_dir=state)
    report = compute_feedback(state_dir=state, write=False)
    assert report.total_predictions >= 1
    assert report.matched_outcomes >= 1
    assert 0.0 <= report.accuracy <= 1.0
    assert report.status != "UNTESTED_NO_PAIRED_PREDICTIONS"


def test_feedback_prompt_block_empty_when_no_data(tmp_path):
    state = tmp_path / ".sifta_state"
    block = feedback_prompt_block(state_dir=state)
    assert block == ""


def test_feedback_prompt_block_contains_accuracy(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    now = _local_ts(2026, 7, 11, 9, 0)
    write_prediction(state_dir=state, now=now)
    record_outcome(label="meal", ts=now + 1800, state_dir=state)
    block = feedback_prompt_block(state_dir=state)
    assert "PREDICTION FEEDBACK" in block
    assert "accuracy" in block


def test_adapt_weights_insufficient_pairs(tmp_path):
    state = tmp_path / ".sifta_state"
    result = adapt_weights(state_dir=state, min_pairs=5, write=False)
    assert result["ok"] is False
    assert result["reason"] == "insufficient_pairs"


def test_adapt_weights_writes_when_sufficient_data(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    now = _local_ts(2026, 7, 11, 9, 0)
    _write_jsonl(
        state / "architect_day_segments.jsonl",
        [
            {
                "ts": now - 60,
                "label": "meal",
                "start_minute_of_day": 9 * 60 + 30,
                "segment_id": "meal-1",
            }
        ],
    )
    for i in range(8):
        write_prediction(state_dir=state, now=now + i * 600)
        record_outcome(label="meal", ts=now + i * 600 + 1800, state_dir=state)
    result = adapt_weights(state_dir=state, min_pairs=3, write=True)
    assert result["ok"] is True
    assert "weights" in result
    weights_file = state / "prediction_feedback_weights.json"
    assert weights_file.exists()


def test_prediction_engine_uses_feedback_weights(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "prediction_feedback_weights.json").write_text(
        json.dumps(
            {
                "recency_power": 0.5,
                "proximity_scale_explicit": 120.0,
                "proximity_scale_implicit": 350.0,
                "explicit_boost": 3.0,
                "source_weight_schedule": 0.6,
                "confidence_share_coeff": 0.70,
                "confidence_support_coeff": 0.20,
                "confidence_volume_coeff": 0.10,
                "confidence_support_cap": 6,
                "confidence_volume_cap": 24,
            }
        ),
        encoding="utf-8",
    )
    now = _local_ts(2026, 7, 11, 9, 0)
    _write_jsonl(
        state / "architect_day_segments.jsonl",
        [
            {
                "ts": now - 60,
                "label": "meal",
                "start_minute_of_day": 9 * 60 + 30,
                "segment_id": "meal-1",
            }
        ],
    )
    row = build_prediction(state_dir=state, now=now, write=False)
    assert row["schema"] == "SIFTA_STIGMERGIC_PREDICTION_V1"
    assert row["next_likely_segment"] == "meal"


def test_calibration_buckets_group_by_confidence():
    pairs = [
        PredictionPair(
            prediction_trace_id="p1", prediction_ts=100, predicted_label="meal",
            predicted_confidence=0.9, predicted_expected_min=30, outcome_ts=200,
            outcome_label="meal", correct=True, time_error_min=5, brier=0.01,
        ),
        PredictionPair(
            prediction_trace_id="p2", prediction_ts=200, predicted_label="meal",
            predicted_confidence=0.9, predicted_expected_min=30, outcome_ts=300,
            outcome_label="desk_work", correct=False, time_error_min=60, brier=0.81,
        ),
        PredictionPair(
            prediction_trace_id="p3", prediction_ts=300, predicted_label="meal",
            predicted_confidence=0.4, predicted_expected_min=30, outcome_ts=400,
            outcome_label="meal", correct=True, time_error_min=10, brier=0.36,
        ),
    ]
    from System.swarm_prediction_feedback import _calibration_buckets

    buckets = _calibration_buckets(pairs)
    assert "high_0.9-1.0" in buckets
    assert "mid_0.5-0.7" not in buckets
    assert "mid-low_0.3-0.5" in buckets
    assert buckets["high_0.9-1.0"]["count"] == 2
    assert buckets["high_0.9-1.0"]["calibration_error"] > 0
