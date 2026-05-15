#!/usr/bin/env python3
"""SIFTA steering prediction audit.

The steering loop now has:

    steering_subsystem receipt -> steering self-model -> predicted_next_route

This module closes the measurement loop:

    predicted_next_route -> next actual steering_subsystem.route -> accuracy

It does not learn weights yet. It measures whether the self-model's route
forecast is useful, which detector caused the forecast, and how long it took
for the next actual route to arrive.

Truth label: STEERING_PREDICTION_AUDIT_V1.
Ledger: .sifta_state/steering_prediction_audit.jsonl
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
STEERING_LEDGER = "steering_subsystem.jsonl"
SELF_MODEL_LEDGER = "steering_self_model.jsonl"
PREDICTION_AUDIT_LEDGER = "steering_prediction_audit.jsonl"
TRUTH_LABEL = "STEERING_PREDICTION_AUDIT_V1"
TRUTH_BOUNDARY = (
    "Pairs steering self-model predicted_next_route rows with the next actual "
    "steering_subsystem route. This measures prediction accuracy; it is not a "
    "claim that Alice has biological introspection or learned steering weights."
)


def _state_dir(state_dir: str | Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _read_jsonl(path: Path, *, max_rows: int = 2000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
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
    return rows[-max(1, int(max_rows)):]


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        number = float(default)
    if number != number or number in (float("inf"), float("-inf")):
        number = float(default)
    return max(0.0, min(1.0, number))


def _round4(value: float) -> float:
    return round(float(value), 4)


def _fired_detectors(row: dict[str, Any]) -> tuple[str, ...]:
    signals = row.get("signals") or []
    names = [
        str(sig.get("name"))
        for sig in signals
        if isinstance(sig, dict) and sig.get("fired") and sig.get("name")
    ]
    return tuple(sorted(set(names))) or ("stable",)


def _dominant_detector(row: dict[str, Any]) -> str:
    return str(row.get("dominant") or (_fired_detectors(row)[0] if _fired_detectors(row) else "stable"))


def _prediction_confidence(row: dict[str, Any]) -> float:
    """Return a legible confidence score from detector margin or route share."""
    margins: list[float] = []
    for sig in row.get("signals") or []:
        if not isinstance(sig, dict) or not sig.get("fired"):
            continue
        value = _clamp01(sig.get("value"))
        threshold = _clamp01(sig.get("threshold"), default=0.5)
        if threshold < 1.0:
            margins.append(max(0.0, (value - threshold) / (1.0 - threshold)))
    route_counts = row.get("route_counts") or {}
    predicted = str(row.get("predicted_next_route") or "")
    route_share = 0.0
    if isinstance(route_counts, dict) and predicted:
        total = sum(int(v) for v in route_counts.values() if isinstance(v, (int, float)))
        if total > 0:
            route_share = int(route_counts.get(predicted, 0) or 0) / total
    if margins:
        return _round4(max(0.50, min(1.0, 0.50 + 0.50 * max(margins))))
    if route_share:
        return _round4(max(0.35, min(0.85, route_share)))
    return 0.35


@dataclass(frozen=True)
class SteeringPredictionPair:
    prediction_trace_id: str
    actual_trace_id: str
    predicted_ts: float
    actual_ts: float
    predicted_next_route: str
    actual_route: str
    correct: bool
    confidence: float
    dominant_detector: str
    fired_detectors: tuple[str, ...]
    time_to_next_turn_s: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction_trace_id": self.prediction_trace_id,
            "actual_trace_id": self.actual_trace_id,
            "predicted_ts": _round4(self.predicted_ts),
            "actual_ts": _round4(self.actual_ts),
            "predicted_next_route": self.predicted_next_route,
            "actual_route": self.actual_route,
            "correct": bool(self.correct),
            "confidence": _round4(self.confidence),
            "dominant_detector": self.dominant_detector,
            "fired_detectors": list(self.fired_detectors),
            "time_to_next_turn_s": _round4(self.time_to_next_turn_s),
        }


@dataclass(frozen=True)
class SteeringPredictionAudit:
    pairs: tuple[SteeringPredictionPair, ...]
    accuracy: float
    correct_count: int
    sample_count: int
    by_dominant_detector: dict[str, dict[str, Any]]
    by_detector: dict[str, dict[str, Any]]
    status: str
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    truth_label: str = TRUTH_LABEL

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "truth_label": self.truth_label,
            "sample_count": int(self.sample_count),
            "correct_count": int(self.correct_count),
            "accuracy": _round4(self.accuracy),
            "status": self.status,
            "by_dominant_detector": self.by_dominant_detector,
            "by_detector": self.by_detector,
            "pairs": [p.to_dict() for p in self.pairs],
        }


def read_prediction_inputs(
    *,
    state_dir: str | Path | None = None,
    max_rows: int = 2000,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root = _state_dir(state_dir)
    self_rows = _read_jsonl(root / SELF_MODEL_LEDGER, max_rows=max_rows)
    steering_rows = _read_jsonl(root / STEERING_LEDGER, max_rows=max_rows)
    return self_rows, steering_rows


def pair_predictions(
    self_rows: Sequence[dict[str, Any]],
    steering_rows: Sequence[dict[str, Any]],
    *,
    max_pairs: int = 200,
) -> tuple[SteeringPredictionPair, ...]:
    predictions = sorted(
        [
            row for row in self_rows
            if row.get("predicted_next_route") and isinstance(row.get("ts"), (int, float))
        ],
        key=lambda row: float(row.get("ts") or 0.0),
    )
    actuals = sorted(
        [
            row for row in steering_rows
            if row.get("route") and isinstance(row.get("ts"), (int, float))
        ],
        key=lambda row: float(row.get("ts") or 0.0),
    )
    pairs: list[SteeringPredictionPair] = []
    actual_index = 0
    for pred in predictions:
        pred_ts = float(pred.get("ts") or 0.0)
        while actual_index < len(actuals) and float(actuals[actual_index].get("ts") or 0.0) <= pred_ts:
            actual_index += 1
        if actual_index >= len(actuals):
            break
        actual = actuals[actual_index]
        actual_ts = float(actual.get("ts") or 0.0)
        predicted_route = str(pred.get("predicted_next_route") or "")
        actual_route = str(actual.get("route") or "")
        pairs.append(SteeringPredictionPair(
            prediction_trace_id=str(pred.get("trace_id") or ""),
            actual_trace_id=str(actual.get("trace_id") or ""),
            predicted_ts=pred_ts,
            actual_ts=actual_ts,
            predicted_next_route=predicted_route,
            actual_route=actual_route,
            correct=predicted_route == actual_route,
            confidence=_prediction_confidence(pred),
            dominant_detector=_dominant_detector(pred),
            fired_detectors=_fired_detectors(pred),
            time_to_next_turn_s=max(0.0, actual_ts - pred_ts),
        ))
    return tuple(pairs[-max(1, int(max_pairs)):])


def _group_stats(pairs: Iterable[SteeringPredictionPair], key_fn) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[SteeringPredictionPair]] = {}
    for pair in pairs:
        keys = key_fn(pair)
        if isinstance(keys, str):
            keys = (keys,)
        for key in keys:
            grouped.setdefault(str(key), []).append(pair)
    out: dict[str, dict[str, Any]] = {}
    for key, rows in sorted(grouped.items()):
        total = len(rows)
        correct = sum(1 for p in rows if p.correct)
        out[key] = {
            "sample_count": total,
            "correct_count": correct,
            "accuracy": _round4(correct / total if total else 0.0),
            "avg_confidence": _round4(sum(p.confidence for p in rows) / total if total else 0.0),
            "avg_time_to_next_turn_s": _round4(
                sum(p.time_to_next_turn_s for p in rows) / total if total else 0.0
            ),
        }
    return out


def _status_for(pairs: tuple[SteeringPredictionPair, ...], accuracy: float) -> str:
    if not pairs:
        return "UNTESTED_NO_PAIRED_PREDICTIONS"
    if len(pairs) < 3:
        return "PAIRED_BUT_UNDERPOWERED"
    if len(pairs) >= 6:
        half = len(pairs) // 2
        early = pairs[:half]
        recent = pairs[half:]
        early_acc = sum(1 for p in early if p.correct) / len(early)
        recent_acc = sum(1 for p in recent if p.correct) / len(recent)
        if recent_acc >= early_acc + 0.20:
            return "GETTING_BETTER"
        if recent_acc <= early_acc - 0.20:
            return "DRIFTING_WORSE"
    if accuracy >= 0.75:
        return "RELIABLE_IN_WINDOW"
    if accuracy >= 0.50:
        return "MIXED_NEEDS_MORE_DATA"
    return "LOW_ACCURACY_SELF_MODEL_MISMATCH"


def audit_predictions(
    *,
    self_rows: Sequence[dict[str, Any]] | None = None,
    steering_rows: Sequence[dict[str, Any]] | None = None,
    state_dir: str | Path | None = None,
    max_rows: int = 2000,
    max_pairs: int = 200,
    write: bool = False,
    now: float | None = None,
) -> SteeringPredictionAudit:
    if self_rows is None or steering_rows is None:
        loaded_self, loaded_steering = read_prediction_inputs(
            state_dir=state_dir,
            max_rows=max_rows,
        )
        if self_rows is None:
            self_rows = loaded_self
        if steering_rows is None:
            steering_rows = loaded_steering
    pairs = pair_predictions(self_rows, steering_rows, max_pairs=max_pairs)
    total = len(pairs)
    correct = sum(1 for pair in pairs if pair.correct)
    accuracy = correct / total if total else 0.0
    audit = SteeringPredictionAudit(
        pairs=pairs,
        accuracy=accuracy,
        correct_count=correct,
        sample_count=total,
        by_dominant_detector=_group_stats(pairs, lambda p: p.dominant_detector),
        by_detector=_group_stats(pairs, lambda p: p.fired_detectors),
        status=_status_for(pairs, accuracy),
    )
    if write:
        write_prediction_audit_receipt(audit, state_dir=state_dir, now=now)
    return audit


def write_prediction_audit_receipt(
    audit: SteeringPredictionAudit,
    *,
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    ts = float(now if now is not None else time.time())
    payload = audit.to_dict()
    sign_body = {k: v for k, v in payload.items() if k != "trace_id"}
    sha = hashlib.sha256(
        json.dumps(sign_body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    row = dict(payload)
    row.update({
        "schema": "SIFTA_STEERING_PREDICTION_AUDIT_RECEIPT_V1",
        "ts": ts,
        "sha256": sha,
        "truth_boundary": TRUTH_BOUNDARY,
    })
    path = _state_dir(state_dir) / PREDICTION_AUDIT_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def prediction_audit_prompt_block(audit: SteeringPredictionAudit | None = None) -> str:
    if audit is None:
        audit = audit_predictions()
    if audit.sample_count <= 0:
        return ""
    return (
        "STEERING PREDICTION AUDIT (ledger-scored)\n"
        f"  accuracy: {audit.accuracy:.3f} ({audit.correct_count}/{audit.sample_count})\n"
        f"  status: {audit.status}\n"
        f"  truth: {TRUTH_LABEL}"
    )


def demo_prediction_audit() -> dict[str, Any]:
    self_rows = [
        {
            "ts": 10.0,
            "trace_id": "self-1",
            "predicted_next_route": "DEEP_CORTEX",
            "dominant": "novelty_pressure",
            "signals": [{"name": "novelty_pressure", "value": 0.80, "threshold": 0.55, "fired": True}],
            "route_counts": {"FAST_REFLEX": 2},
        },
        {
            "ts": 20.0,
            "trace_id": "self-2",
            "predicted_next_route": "VERIFY_BEFORE_ACTION",
            "dominant": "truth_risk_burn",
            "signals": [{"name": "truth_risk_burn", "value": 0.75, "threshold": 0.50, "fired": True}],
            "route_counts": {"VERIFY_BEFORE_ACTION": 1},
        },
    ]
    steering_rows = [
        {"ts": 11.0, "trace_id": "actual-1", "route": "DEEP_CORTEX"},
        {"ts": 21.5, "trace_id": "actual-2", "route": "NORMAL_CORTEX"},
    ]
    audit = audit_predictions(self_rows=self_rows, steering_rows=steering_rows)
    return {
        "truth_label": TRUTH_LABEL,
        "audit": audit.to_dict(),
        "prompt_block": prediction_audit_prompt_block(audit),
    }


__all__ = [
    "PREDICTION_AUDIT_LEDGER",
    "SELF_MODEL_LEDGER",
    "STEERING_LEDGER",
    "TRUTH_BOUNDARY",
    "TRUTH_LABEL",
    "SteeringPredictionAudit",
    "SteeringPredictionPair",
    "audit_predictions",
    "demo_prediction_audit",
    "pair_predictions",
    "prediction_audit_prompt_block",
    "read_prediction_inputs",
    "write_prediction_audit_receipt",
]


if __name__ == "__main__":
    print(json.dumps(demo_prediction_audit(), indent=2, sort_keys=True))
