#!/usr/bin/env python3
"""Receipt-trained steering predictor for SIFTA.

The steering loop was deliberately honest before this module:

    route -> receipt -> self-model -> predicted route -> audit -> governor

The missing segment was calibration over time. This module learns a small,
deterministic detector->next-route table from the prediction-audit ledger and
lets the self-model consult it only after enough paired samples exist.

This is not neural-network training and not a claim of biological
introspection. "Learned" here means empirical frequencies from receipts:
which actual route followed each fired self-model detector, with Laplace
smoothing and governor weights applied at prediction time.

Truth label: STEERING_LEARNED_PREDICTOR_V1.
Ledger: .sifta_state/steering_learned_predictor.jsonl
Model artifact: .sifta_state/steering_learned_predictor_model.json
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
AUDIT_LEDGER = "steering_prediction_audit.jsonl"
ADAPTATION_LEDGER = "steering_adaptation_governor.jsonl"
PREDICTOR_LEDGER = "steering_learned_predictor.jsonl"
PREDICTOR_MODEL = "steering_learned_predictor_model.json"
CALIBRATION_CYCLE_LEDGER = "steering_calibration_cycle.jsonl"
TRUTH_LABEL = "STEERING_LEARNED_PREDICTOR_V1"
TRUTH_BOUNDARY = (
    "Receipt-trained detector->route frequency model. It is a learned "
    "calibration table over steering_prediction_audit pairs, not neural "
    "weight training, not hidden self-awareness, and not allowed to override "
    "the rule predictor until detector sample_count >= min_samples."
)

KNOWN_ROUTES = (
    "FAST_REFLEX",
    "NORMAL_CORTEX",
    "DEEP_CORTEX",
    "VERIFY_BEFORE_ACTION",
    "EMERGENCY_INTERRUPT",
    "CONSERVE_OR_DEFER",
)
MIN_SAMPLES_TO_LEARN = 10
SMOOTHING = 1.0


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


def _round4(value: float) -> float:
    return round(float(value), 4)


def _latest_json(path: Path) -> dict[str, Any] | None:
    rows = _read_jsonl(path)
    return rows[-1] if rows else None


def _as_pairs(audit_row: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not audit_row:
        return []
    pairs = audit_row.get("pairs") or []
    return [p for p in pairs if isinstance(p, dict)]


def _route_counts_from_pairs(
    pairs: Sequence[dict[str, Any]],
) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    by_detector: dict[str, dict[str, int]] = {}
    route_prior: dict[str, int] = {}
    for pair in pairs:
        actual_route = str(pair.get("actual_route") or "")
        if not actual_route:
            continue
        route_prior[actual_route] = route_prior.get(actual_route, 0) + 1
        detectors = pair.get("fired_detectors") or [pair.get("dominant_detector") or "stable"]
        if not isinstance(detectors, list):
            detectors = [str(detectors)]
        for detector in detectors:
            name = str(detector or "stable")
            if not name:
                continue
            route_counts = by_detector.setdefault(name, {})
            route_counts[actual_route] = route_counts.get(actual_route, 0) + 1
    return by_detector, route_prior


def _route_probs(route_counts: Mapping[str, int]) -> dict[str, float]:
    routes = sorted(set(KNOWN_ROUTES).union(route_counts.keys()))
    total = sum(int(route_counts.get(route, 0) or 0) for route in routes)
    denom = total + (SMOOTHING * len(routes))
    if denom <= 0:
        return {route: _round4(1.0 / len(routes)) for route in routes}
    return {
        route: _round4((int(route_counts.get(route, 0) or 0) + SMOOTHING) / denom)
        for route in routes
    }


@dataclass(frozen=True)
class DetectorRouteModel:
    detector: str
    sample_count: int
    route_counts: dict[str, int]
    route_probabilities: dict[str, float]
    best_route: str | None
    confidence: float
    ready: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "detector": self.detector,
            "sample_count": int(self.sample_count),
            "route_counts": dict(sorted(self.route_counts.items())),
            "route_probabilities": dict(sorted(self.route_probabilities.items())),
            "best_route": self.best_route,
            "confidence": _round4(self.confidence),
            "ready": bool(self.ready),
        }


@dataclass(frozen=True)
class LearnedPredictorModel:
    detector_models: dict[str, DetectorRouteModel]
    route_prior: dict[str, int]
    sample_count: int
    min_samples: int
    status: str
    open_gaps: tuple[str, ...]
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    truth_label: str = TRUTH_LABEL

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "truth_label": self.truth_label,
            "detector_models": {
                name: model.to_dict()
                for name, model in sorted(self.detector_models.items())
            },
            "route_prior": dict(sorted(self.route_prior.items())),
            "sample_count": int(self.sample_count),
            "min_samples": int(self.min_samples),
            "status": self.status,
            "open_gaps": list(self.open_gaps),
        }


@dataclass(frozen=True)
class LearnedRoutePrediction:
    route: str | None
    fallback_route: str | None
    learned_used: bool
    status: str
    confidence: float
    detector_scores: dict[str, dict[str, float]]
    governor_weights: dict[str, float]
    open_gaps: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "fallback_route": self.fallback_route,
            "learned_used": bool(self.learned_used),
            "status": self.status,
            "confidence": _round4(self.confidence),
            "detector_scores": self.detector_scores,
            "governor_weights": {k: _round4(v) for k, v in sorted(self.governor_weights.items())},
            "open_gaps": list(self.open_gaps),
        }


def train_predictor_from_audit(
    audit_row: Mapping[str, Any] | None = None,
    *,
    state_dir: str | Path | None = None,
    min_samples: int = MIN_SAMPLES_TO_LEARN,
    write: bool = False,
    now: float | None = None,
) -> LearnedPredictorModel:
    """Build a learned detector->route table from one audit receipt."""
    if audit_row is None:
        audit_row = _latest_json(_state_dir(state_dir) / AUDIT_LEDGER)
    pairs = _as_pairs(audit_row)
    by_detector, route_prior = _route_counts_from_pairs(pairs)
    detector_models: dict[str, DetectorRouteModel] = {}
    open_gaps: list[str] = []
    for detector, counts in sorted(by_detector.items()):
        sample_count = sum(int(v) for v in counts.values())
        probs = _route_probs(counts)
        best_route = max(probs.items(), key=lambda item: (item[1], item[0]))[0] if probs else None
        confidence = float(probs.get(best_route, 0.0)) if best_route else 0.0
        ready = sample_count >= min_samples
        if not ready:
            open_gaps.append(
                f"{detector}: {sample_count} paired samples < {min_samples}; learned route disabled."
            )
        detector_models[detector] = DetectorRouteModel(
            detector=detector,
            sample_count=sample_count,
            route_counts=dict(counts),
            route_probabilities=probs,
            best_route=best_route,
            confidence=confidence,
            ready=ready,
        )
    if not pairs:
        status = "NO_AUDIT_PAIRS"
        open_gaps.append("No paired prediction data available.")
    elif not detector_models or all(not model.ready for model in detector_models.values()):
        status = "INSUFFICIENT_PAIRED_DATA"
    elif all(model.ready for model in detector_models.values()):
        status = "READY"
    else:
        status = "PARTIAL_READY"
    model = LearnedPredictorModel(
        detector_models=detector_models,
        route_prior=route_prior,
        sample_count=len(pairs),
        min_samples=min_samples,
        status=status,
        open_gaps=tuple(open_gaps),
    )
    if write:
        write_learned_predictor_receipt(model, state_dir=state_dir, now=now)
    return model


def write_learned_predictor_receipt(
    model: LearnedPredictorModel,
    *,
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    ts = float(now if now is not None else time.time())
    payload = model.to_dict()
    sign_body = {k: v for k, v in payload.items() if k != "trace_id"}
    sha = hashlib.sha256(
        json.dumps(sign_body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    row = dict(payload)
    row.update({
        "schema": "SIFTA_STEERING_LEARNED_PREDICTOR_RECEIPT_V1",
        "ts": ts,
        "sha256": sha,
        "truth_boundary": TRUTH_BOUNDARY,
    })
    with (state / PREDICTOR_LEDGER).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    model_row = {
        "schema": "SIFTA_STEERING_LEARNED_PREDICTOR_MODEL_V1",
        "ts": ts,
        "sha256": sha,
        "truth_boundary": TRUTH_BOUNDARY,
        "payload": payload,
    }
    (state / PREDICTOR_MODEL).write_text(
        json.dumps(model_row, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return row


def load_learned_predictor_model(
    *,
    state_dir: str | Path | None = None,
) -> LearnedPredictorModel | None:
    path = _state_dir(state_dir) / PREDICTOR_MODEL
    if not path.exists():
        return None
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
        payload = row.get("payload") if isinstance(row, dict) else None
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return _model_from_payload(payload)


def _model_from_payload(payload: Mapping[str, Any]) -> LearnedPredictorModel:
    raw_models = payload.get("detector_models") or {}
    detector_models: dict[str, DetectorRouteModel] = {}
    if isinstance(raw_models, dict):
        for name, raw in raw_models.items():
            if not isinstance(raw, dict):
                continue
            counts = {
                str(k): int(v)
                for k, v in (raw.get("route_counts") or {}).items()
                if isinstance(v, (int, float))
            }
            probs = {
                str(k): float(v)
                for k, v in (raw.get("route_probabilities") or {}).items()
                if isinstance(v, (int, float))
            }
            detector_models[str(name)] = DetectorRouteModel(
                detector=str(raw.get("detector") or name),
                sample_count=int(raw.get("sample_count") or 0),
                route_counts=counts,
                route_probabilities=probs,
                best_route=str(raw.get("best_route") or "") or None,
                confidence=float(raw.get("confidence") or 0.0),
                ready=bool(raw.get("ready")),
            )
    route_prior = {
        str(k): int(v)
        for k, v in (payload.get("route_prior") or {}).items()
        if isinstance(v, (int, float))
    }
    return LearnedPredictorModel(
        detector_models=detector_models,
        route_prior=route_prior,
        sample_count=int(payload.get("sample_count") or 0),
        min_samples=int(payload.get("min_samples") or MIN_SAMPLES_TO_LEARN),
        status=str(payload.get("status") or "UNKNOWN"),
        open_gaps=tuple(str(x) for x in (payload.get("open_gaps") or [])),
        trace_id=str(payload.get("trace_id") or uuid.uuid4()),
        truth_label=str(payload.get("truth_label") or TRUTH_LABEL),
    )


def latest_governor_weights(
    *,
    state_dir: str | Path | None = None,
) -> dict[str, float]:
    row = _latest_json(_state_dir(state_dir) / ADAPTATION_LEDGER)
    if not row:
        return {}
    raw = row.get("detector_weights") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        try:
            out[str(key)] = float(value)
        except Exception:
            continue
    return out


def predict_route_with_learned_model(
    fired_detectors: Iterable[str],
    *,
    fallback_route: str | None,
    state_dir: str | Path | None = None,
    governor_weights: Mapping[str, float] | None = None,
    model: LearnedPredictorModel | None = None,
) -> LearnedRoutePrediction:
    model = model or load_learned_predictor_model(state_dir=state_dir)
    weights = dict(governor_weights) if governor_weights is not None else latest_governor_weights(state_dir=state_dir)
    fired = sorted({str(name) for name in fired_detectors if str(name)})
    if model is None:
        return LearnedRoutePrediction(
            route=fallback_route,
            fallback_route=fallback_route,
            learned_used=False,
            status="NO_MODEL",
            confidence=0.0,
            detector_scores={},
            governor_weights=weights,
            open_gaps=("No learned predictor model artifact found.",),
        )
    route_scores: dict[str, float] = {}
    detector_scores: dict[str, dict[str, float]] = {}
    open_gaps = list(model.open_gaps)
    for detector in fired:
        det_model = model.detector_models.get(detector)
        if det_model is None:
            open_gaps.append(f"{detector}: no learned detector model; fallback route retained.")
            continue
        if not det_model.ready:
            open_gaps.append(
                f"{detector}: {det_model.sample_count} samples < {model.min_samples}; fallback route retained."
            )
            continue
        weight = float(weights.get(detector, 1.0))
        detector_scores[detector] = {}
        for route, prob in det_model.route_probabilities.items():
            score = float(prob) * weight
            detector_scores[detector][route] = _round4(score)
            route_scores[route] = route_scores.get(route, 0.0) + score
    if not route_scores:
        return LearnedRoutePrediction(
            route=fallback_route,
            fallback_route=fallback_route,
            learned_used=False,
            status="INSUFFICIENT_PAIRED_DATA",
            confidence=0.0,
            detector_scores=detector_scores,
            governor_weights=weights,
            open_gaps=tuple(open_gaps),
        )
    best_route, best_score = max(route_scores.items(), key=lambda item: (item[1], item[0]))
    total_score = sum(route_scores.values())
    confidence = best_score / total_score if total_score else 0.0
    return LearnedRoutePrediction(
        route=best_route,
        fallback_route=fallback_route,
        learned_used=True,
        status="LEARNED_ROUTE_USED",
        confidence=confidence,
        detector_scores={
            det: dict(sorted(scores.items()))
            for det, scores in sorted(detector_scores.items())
        },
        governor_weights=weights,
        open_gaps=tuple(open_gaps),
    )


def run_learning_cycle(
    *,
    state_dir: str | Path | None = None,
    write: bool = True,
    now: float | None = None,
) -> LearnedPredictorModel:
    """Train from the latest audit and optionally write receipt + model file."""
    return train_predictor_from_audit(state_dir=state_dir, write=write, now=now)


def run_full_calibration_cycle(
    *,
    state_dir: str | Path | None = None,
    write: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """Run the complete calibration loop once.

    Order matters:
      1. pair latest self-model predictions with actual steering routes
      2. update governor weights from measured audit accuracy
      3. train/write the learned detector->route predictor
      4. write a small cycle receipt exposing remaining open gaps
    """
    from System.swarm_steering_prediction_audit import audit_predictions
    from System.swarm_steering_adaptation_governor import run_governor

    audit = audit_predictions(state_dir=state_dir, write=write, now=now)
    governor_report, _governor_receipt = run_governor(state_dir=state_dir, write=write)
    model = train_predictor_from_audit(
        audit.to_dict(),
        state_dir=state_dir,
        write=write,
        now=now,
    )
    cycle = {
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "audit": {
            "sample_count": audit.sample_count,
            "correct_count": audit.correct_count,
            "accuracy": _round4(audit.accuracy),
            "status": audit.status,
            "trace_id": audit.trace_id,
        },
        "governor": {
            "status": governor_report.overall_status,
            "audit_sample_count": governor_report.audit_sample_count,
            "detector_weights": {
                k: _round4(v) for k, v in sorted(governor_report.detector_weights.items())
            },
            "trace_id": governor_report.trace_id,
        },
        "learned_predictor": {
            "status": model.status,
            "sample_count": model.sample_count,
            "ready_detectors": [
                name for name, det in sorted(model.detector_models.items())
                if det.ready
            ],
            "open_gaps": list(model.open_gaps),
            "trace_id": model.trace_id,
        },
    }
    if write:
        write_calibration_cycle_receipt(cycle, state_dir=state_dir, now=now)
    return cycle


def write_calibration_cycle_receipt(
    cycle: dict[str, Any],
    *,
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    ts = float(now if now is not None else time.time())
    payload_json = json.dumps(cycle, sort_keys=True, separators=(",", ":"), default=str)
    row = {
        "schema": "SIFTA_STEERING_CALIBRATION_CYCLE_RECEIPT_V1",
        "ts": ts,
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "payload": cycle,
    }
    with (state / CALIBRATION_CYCLE_LEDGER).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def learned_predictor_prompt_block(model: LearnedPredictorModel | None = None) -> str:
    if model is None:
        model = load_learned_predictor_model()
    if model is None:
        return (
            "STEERING LEARNED PREDICTOR (ledger-trained)\n"
            "  status: NO_MODEL\n"
            "  open_gap: No predictor model artifact exists yet.\n"
            f"  truth: {TRUTH_LABEL}"
        )
    lines = [
        "STEERING LEARNED PREDICTOR (ledger-trained)",
        f"  status: {model.status}",
        f"  paired_samples: {model.sample_count}",
        f"  min_samples_per_detector: {model.min_samples}",
    ]
    ready = [
        name for name, det in sorted(model.detector_models.items())
        if det.ready
    ]
    if ready:
        lines.append("  ready_detectors: " + ", ".join(ready))
    if model.open_gaps:
        lines.append("  open_gaps:")
        for gap in model.open_gaps[:5]:
            lines.append(f"    - {gap}")
    lines.append(f"  truth: {TRUTH_LABEL}")
    return "\n".join(lines)


__all__ = [
    "ADAPTATION_LEDGER",
    "AUDIT_LEDGER",
    "CALIBRATION_CYCLE_LEDGER",
    "MIN_SAMPLES_TO_LEARN",
    "PREDICTOR_LEDGER",
    "PREDICTOR_MODEL",
    "TRUTH_BOUNDARY",
    "TRUTH_LABEL",
    "DetectorRouteModel",
    "LearnedPredictorModel",
    "LearnedRoutePrediction",
    "latest_governor_weights",
    "learned_predictor_prompt_block",
    "load_learned_predictor_model",
    "predict_route_with_learned_model",
    "run_full_calibration_cycle",
    "run_learning_cycle",
    "train_predictor_from_audit",
    "write_calibration_cycle_receipt",
    "write_learned_predictor_receipt",
]


if __name__ == "__main__":
    model = run_learning_cycle(write=False)
    print(learned_predictor_prompt_block(model))
    print()
    print(json.dumps(model.to_dict(), indent=2, sort_keys=True))
