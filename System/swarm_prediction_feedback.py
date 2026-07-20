#!/usr/bin/env python3
"""Prediction feedback loop — track schedule prediction accuracy and learn.

Closes the loop on stigmergic_prediction_engine:

    predict → record outcome → match against past predictions →
    compute accuracy → adjust weights → next prediction is better

A mismatch is not a failure — it is the training signal (same stance as
swarm_action_prediction: mistakes are lessons, not shame).

Truth label: PREDICTION_FEEDBACK_V1.
Ledger: .sifta_state/prediction_feedback.jsonl
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
FEEDBACK_LEDGER = "prediction_feedback.jsonl"
WEIGHTS_FILE = "prediction_feedback_weights.json"
TRUTH_LABEL = "PREDICTION_FEEDBACK_V1"

MATCH_WINDOW_MIN = 60
DEFAULT_WEIGHTS = {
    "recency_power": 1.0,
    "proximity_scale_explicit": 90.0,
    "proximity_scale_implicit": 260.0,
    "explicit_boost": 2.8,
    "source_weight_schedule": 0.55,
    "confidence_share_coeff": 0.72,
    "confidence_support_coeff": 0.18,
    "confidence_volume_coeff": 0.10,
    "confidence_support_cap": 6,
    "confidence_volume_cap": 24,
}


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _read_jsonl(path: Path, *, max_rows: int = 4096) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except Exception:
        return []
    return rows[-max(1, int(max_rows)) :]


def _minute_from_ts(ts: float) -> int:
    lt = time.localtime(float(ts))
    return int(lt.tm_hour) * 60 + int(lt.tm_min)


def _load_weights(state_dir: Optional[Path | str] = None) -> dict[str, float]:
    root = _state_dir(state_dir)
    path = root / WEIGHTS_FILE
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                merged = dict(DEFAULT_WEIGHTS)
                for k, v in raw.items():
                    if k in DEFAULT_WEIGHTS and isinstance(v, (int, float)):
                        merged[k] = float(v)
                return merged
        except Exception:
            pass
    return dict(DEFAULT_WEIGHTS)


def _save_weights(weights: dict[str, float], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    try:
        (root / WEIGHTS_FILE).write_text(
            json.dumps(weights, indent=2, sort_keys=True), encoding="utf-8"
        )
    except Exception:
        pass


def _append_row(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    try:
        with (root / FEEDBACK_LEDGER).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def record_outcome(
    *,
    label: str,
    ts: float | None = None,
    state_dir: Optional[Path | str] = None,
    source: str = "owner_observed",
) -> dict[str, Any]:
    """Record that an event actually happened at this time.

    Call this when George says "I'm eating" or when a body event fires.
    The outcome is matched against pending predictions.
    """
    now = float(ts if ts is not None else time.time())
    row: dict[str, Any] = {
        "schema": "PREDICTION_FEEDBACK_OUTCOME_V1",
        "kind": "outcome",
        "truth_label": TRUTH_LABEL,
        "trace_id": str(uuid.uuid4()),
        "ts": now,
        "minute_of_day": _minute_from_ts(now),
        "label": str(label or "").strip().lower(),
        "source": source,
    }
    _append_row(row, state_dir=state_dir)
    return row


def record_owner_correction(
    *,
    predicted_label: str,
    actual_label: str,
    ts: float | None = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Owner says the prediction was wrong — strongest learning signal."""
    now = float(ts if ts is not None else time.time())
    row: dict[str, Any] = {
        "schema": "PREDICTION_FEEDBACK_CORRECTION_V1",
        "kind": "correction",
        "truth_label": TRUTH_LABEL,
        "trace_id": str(uuid.uuid4()),
        "ts": now,
        "predicted_label": str(predicted_label or "").strip().lower(),
        "actual_label": str(actual_label or "").strip().lower(),
    }
    _append_row(row, state_dir=state_dir)
    return row


@dataclass(frozen=True)
class PredictionPair:
    prediction_trace_id: str
    prediction_ts: float
    predicted_label: str
    predicted_confidence: float
    predicted_expected_min: int
    outcome_ts: float
    outcome_label: str
    correct: bool
    time_error_min: int
    brier: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_trace_id": self.prediction_trace_id,
            "prediction_ts": round(self.prediction_ts, 4),
            "predicted_label": self.predicted_label,
            "predicted_confidence": round(self.predicted_confidence, 4),
            "predicted_expected_min": self.predicted_expected_min,
            "outcome_ts": round(self.outcome_ts, 4),
            "outcome_label": self.outcome_label,
            "correct": self.correct,
            "time_error_min": self.time_error_min,
            "brier": round(self.brier, 4),
        }


@dataclass(frozen=True)
class FeedbackReport:
    pairs: tuple[PredictionPair, ...]
    total_predictions: int
    matched_outcomes: int
    accuracy: float
    mean_brier: float
    calibration_by_bucket: dict[str, dict[str, Any]]
    status: str
    weights_used: dict[str, float]
    truth_label: str = TRUTH_LABEL
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "truth_label": self.truth_label,
            "total_predictions": self.total_predictions,
            "matched_outcomes": self.matched_outcomes,
            "accuracy": round(self.accuracy, 4),
            "mean_brier": round(self.mean_brier, 4),
            "calibration_by_bucket": self.calibration_by_bucket,
            "status": self.status,
            "weights_used": {k: round(v, 4) for k, v in self.weights_used.items()},
            "pairs": [p.to_dict() for p in self.pairs],
        }


def pair_predictions(
    predictions: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    *,
    match_window_min: int = MATCH_WINDOW_MIN,
) -> list[PredictionPair]:
    """Match prediction rows to outcome rows.

    A prediction matches an outcome if:
    - The outcome label matches the predicted segment
    - The outcome timestamp is within match_window_min of the expected time
    """
    pred_rows = sorted(
        [r for r in predictions if r.get("next_likely_segment") and r.get("ts")],
        key=lambda r: float(r.get("ts") or 0),
    )
    outcome_rows = sorted(
        [r for r in outcomes if r.get("label") and r.get("ts")],
        key=lambda r: float(r.get("ts") or 0),
    )
    pairs: list[PredictionPair] = []
    used_outcomes: set[int] = set()

    for pred in pred_rows:
        pred_label = str(pred.get("next_likely_segment") or "").lower()
        pred_ts = float(pred.get("ts") or 0)
        pred_conf = float(pred.get("confidence") or 0)
        pred_exp_min = int(pred.get("expected_start_min") or 0)
        pred_minute = int(pred.get("now_minute_of_day") or 0)
        pred_trace = str(pred.get("trace_id") or "")

        expected_outcome_minute = (pred_minute + pred_exp_min) % 1440

        best_match: Optional[tuple[int, dict[str, Any]]] = None
        best_distance = match_window_min + 1

        for idx, outcome in enumerate(outcome_rows):
            if idx in used_outcomes:
                continue
            out_label = str(outcome.get("label") or "").lower()
            if out_label != pred_label:
                continue
            out_ts = float(outcome.get("ts") or 0)
            out_minute = int(outcome.get("minute_of_day") or 0)
            minute_diff = abs(out_minute - expected_outcome_minute) % 1440
            if minute_diff > match_window_min:
                continue
            if minute_diff < best_distance:
                best_distance = minute_diff
                best_match = (idx, outcome)

        if best_match is None:
            continue

        idx, outcome = best_match
        used_outcomes.add(idx)
        out_ts = float(outcome.get("ts") or 0)
        out_minute = int(outcome.get("minute_of_day") or 0)

        correct = best_distance <= 15
        brier = (pred_conf - (1.0 if correct else 0.0)) ** 2

        pairs.append(
            PredictionPair(
                prediction_trace_id=pred_trace,
                prediction_ts=pred_ts,
                predicted_label=pred_label,
                predicted_confidence=pred_conf,
                predicted_expected_min=pred_exp_min,
                outcome_ts=out_ts,
                outcome_label=out_label,
                correct=correct,
                time_error_min=best_distance,
                brier=brier,
            )
        )

    return pairs


def _status_for(pairs: list[PredictionPair], accuracy: float) -> str:
    if not pairs:
        return "UNTESTED_NO_PAIRED_PREDICTIONS"
    if len(pairs) < 3:
        return "PAIRED_BUT_UNDERPOWERED"
    if len(pairs) >= 6:
        half = len(pairs) // 2
        early_acc = sum(1 for p in pairs[:half] if p.correct) / max(1, half)
        recent_acc = sum(1 for p in pairs[half:] if p.correct) / max(1, len(pairs) - half)
        if recent_acc >= early_acc + 0.20:
            return "GETTING_BETTER"
        if recent_acc <= early_acc - 0.20:
            return "DRIFTING_WORSE"
    if accuracy >= 0.75:
        return "RELIABLE"
    if accuracy >= 0.50:
        return "MIXED_NEEDS_MORE_DATA"
    return "LOW_ACCURACY"


def _calibration_buckets(pairs: list[PredictionPair]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[PredictionPair]] = defaultdict(list)
    for p in pairs:
        conf = p.predicted_confidence
        if conf < 0.3:
            key = "low_0.0-0.3"
        elif conf < 0.5:
            key = "mid-low_0.3-0.5"
        elif conf < 0.7:
            key = "mid_0.5-0.7"
        elif conf < 0.9:
            key = "mid-high_0.7-0.9"
        else:
            key = "high_0.9-1.0"
        buckets[key].append(p)

    result: dict[str, dict[str, Any]] = {}
    for bucket_name, bucket_pairs in sorted(buckets.items()):
        n = len(bucket_pairs)
        correct = sum(1 for p in bucket_pairs if p.correct)
        avg_conf = sum(p.predicted_confidence for p in bucket_pairs) / max(1, n)
        empirical_acc = correct / max(1, n)
        result[bucket_name] = {
            "count": n,
            "correct": correct,
            "accuracy": round(empirical_acc, 4),
            "avg_confidence": round(avg_conf, 4),
            "calibration_error": round(abs(avg_conf - empirical_acc), 4),
        }
    return result


def compute_feedback(
    *,
    state_dir: Optional[Path | str] = None,
    max_rows: int = 4096,
    write: bool = False,
    now: float | None = None,
) -> FeedbackReport:
    """Compute feedback report: pair predictions with outcomes, score accuracy."""
    root = _state_dir(state_dir)
    predictions = _read_jsonl(root / "stigmergic_prediction.jsonl", max_rows=max_rows)
    outcomes = _read_jsonl(root / FEEDBACK_LEDGER, max_rows=max_rows)
    all_rows = outcomes
    event_outcomes = [r for r in all_rows if r.get("kind") == "outcome"]
    correction_rows = [r for r in all_rows if r.get("kind") == "correction"]

    pairs = pair_predictions(predictions, event_outcomes)
    total_preds = len(predictions)
    matched = len(pairs)
    correct = sum(1 for p in pairs if p.correct)
    accuracy = correct / max(1, matched)
    mean_brier = sum(p.brier for p in pairs) / max(1, matched)
    cal = _calibration_buckets(pairs)
    status = _status_for(pairs, accuracy)
    weights = _load_weights(state_dir)

    report = FeedbackReport(
        pairs=tuple(pairs[-50:]),
        total_predictions=total_preds,
        matched_outcomes=matched,
        accuracy=accuracy,
        mean_brier=mean_brier,
        calibration_by_bucket=cal,
        status=status,
        weights_used=weights,
    )

    if write:
        _write_feedback_receipt(report, state_dir=state_dir, now=now)

    return report


def _write_feedback_receipt(
    report: FeedbackReport,
    *,
    state_dir: Optional[Path | str] = None,
    now: float | None = None,
) -> dict[str, Any]:
    ts = float(now if now is not None else time.time())
    payload = report.to_dict()
    sign_body = {k: v for k, v in payload.items() if k != "trace_id"}
    sha = hashlib.sha256(
        json.dumps(sign_body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    row = dict(payload)
    row.update({
        "schema": "PREDICTION_FEEDBACK_RECEIPT_V1",
        "ts": ts,
        "sha256": sha,
    })
    _append_row(row, state_dir=state_dir)
    return row


def adapt_weights(
    *,
    state_dir: Optional[Path | str] = None,
    learning_rate: float = 0.08,
    min_pairs: int = 5,
    write: bool = True,
) -> dict[str, Any]:
    """Adjust scoring weights based on feedback accuracy.

    If accuracy is low, nudge weights to compensate:
    - Low accuracy on recent predictions → reduce recency_power (past patterns
      matter less than they think)
    - Low accuracy on implicit samples → reduce source_weight_schedule (schedule
      ledger is less reliable)
    - High mean time error → widen proximity scales (events are further from
      expected time than the model assumes)

    Weights are HYPOTHESIS-class calibration coefficients, not neural
    weights. They are deterministic, inspectable, and reversible.
    """
    weights = _load_weights(state_dir)
    report = compute_feedback(state_dir=state_dir, write=False)
    pairs = list(report.pairs)

    if len(pairs) < min_pairs:
        return {
            "ok": False,
            "reason": "insufficient_pairs",
            "min_pairs": min_pairs,
            "current_pairs": len(pairs),
            "weights": weights,
        }

    recent = pairs[-20:]
    recent_correct = sum(1 for p in recent if p.correct)
    recent_accuracy = recent_correct / max(1, len(recent))
    mean_time_error = sum(p.time_error_min for p in recent) / max(1, len(recent))

    adjustments: dict[str, float] = {}

    if recent_accuracy < 0.5:
        delta = learning_rate * (0.5 - recent_accuracy)
        weights["recency_power"] = max(0.3, weights["recency_power"] - delta)
        adjustments["recency_power"] = -delta

    if mean_time_error > 30:
        delta = learning_rate * min(1.0, mean_time_error / 60.0)
        weights["proximity_scale_explicit"] = min(
            180.0, weights["proximity_scale_explicit"] + delta * 30
        )
        weights["proximity_scale_implicit"] = min(
            500.0, weights["proximity_scale_implicit"] + delta * 40
        )
        adjustments["proximity_scale_explicit"] = delta * 30
        adjustments["proximity_scale_implicit"] = delta * 40

    cal_errors = report.calibration_by_bucket
    overconfident = any(
        b.get("calibration_error", 0) > 0.2 and b.get("count", 0) >= 3
        for b in cal_errors.values()
    )
    if overconfident:
        delta = learning_rate * 0.5
        weights["confidence_share_coeff"] = max(
            0.50, weights["confidence_share_coeff"] - delta
        )
        adjustments["confidence_share_coeff"] = -delta

    if write:
        _save_weights(weights, state_dir=state_dir)

    return {
        "ok": True,
        "accuracy": round(recent_accuracy, 4),
        "mean_time_error_min": round(mean_time_error, 2),
        "adjustments": adjustments,
        "weights": weights,
    }


def feedback_prompt_block(*, state_dir: Optional[Path | str] = None) -> str:
    """Compact feedback block for Alice's Talk prompt."""
    report = compute_feedback(state_dir=state_dir, write=False)
    if report.total_predictions <= 0:
        return ""
    lines = [
        "PREDICTION FEEDBACK (schedule prior accuracy):",
        f"- {report.matched_outcomes}/{report.total_predictions} predictions matched outcomes",
        f"- accuracy: {report.accuracy:.0%} · Brier: {report.mean_brier:.4f}",
        f"- status: {report.status}",
    ]
    if report.calibration_by_bucket:
        over = [
            b
            for b, stats in report.calibration_by_bucket.items()
            if stats.get("calibration_error", 0) > 0.15 and stats.get("count", 0) >= 2
        ]
        if over:
            lines.append(f"- overconfident buckets: {', '.join(over)}")
    lines.append(f"- truth: {TRUTH_LABEL}")
    return "\n".join(lines)


__all__ = [
    "FEEDBACK_LEDGER",
    "TRUTH_LABEL",
    "WEIGHTS_FILE",
    "FeedbackReport",
    "PredictionPair",
    "adapt_weights",
    "compute_feedback",
    "feedback_prompt_block",
    "pair_predictions",
    "record_outcome",
    "record_owner_correction",
]


if __name__ == "__main__":
    report = compute_feedback(write=True)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
