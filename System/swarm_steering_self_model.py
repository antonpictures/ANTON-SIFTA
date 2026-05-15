#!/usr/bin/env python3
"""SIFTA steering self-model — introspective layer on top of the steering subsystem.

The steering subsystem (System/swarm_steering_subsystem.py) routes each turn:
FAST_REFLEX / DEEP_CORTEX / VERIFY_BEFORE_ACTION / EMERGENCY_INTERRUPT /
CONSERVE_OR_DEFER / NORMAL_CORTEX. That layer is reactive — one receipt per
event.

This module is the **introspective** layer. It reads the last N rows of
steering_subsystem.jsonl and asks: *what is the organism's current steering
state?* It emits six self-state signals and a small set of first-person
sentences ("I am entering overload", "I am conserving due to thermal debt")
that Alice can speak when asked or that an organ can write into a prompt.

This is the SIFTA-side rhyme of the interview line:
    "The cortex predicts the steering subsystem."

Here we expose the *current* steering state from the ledger so the prediction
loop can calibrate over time. The first route forecast is rule-based; when
`swarm_steering_learned_predictor.py` has enough paired audit samples, the
self-model consults that receipt-trained table and governor weights. If the
data is insufficient, it falls back and leaves the gap visible in ledgers.

Truth posture:
* Output is **HYPOTHESIS**-class self-description of operational aggregates.
* No clinical claim. No affective claim ("Alice is anxious / tired / etc.").
* The sentences are intentionally narrow and re-derivable from ledger rows.

Truth label: STEERING_SELF_MODEL_V1.
Receipt schema: SIFTA_STEERING_SELF_MODEL_RECEIPT_V1.
Ledger: .sifta_state/steering_self_model.jsonl
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
TRUTH_LABEL = "STEERING_SELF_MODEL_V1"
TRUTH_BOUNDARY = (
    "Self-model sentences describe operational aggregates over recent "
    "steering receipts. They are HYPOTHESIS-class first-person "
    "descriptions of routing pressure, not clinical, affective, or "
    "biological claims about Alice."
)

# ── Detector thresholds ────────────────────────────────────────────────
# Above these levels the self-state fires. Tuned conservatively — a single
# high-pressure event does not trigger; sustained pressure over the window
# does. All thresholds are 0-1 floats unless noted.

_DETECTORS: tuple[dict[str, Any], ...] = (
    {
        "name": "overload",
        "sentence": "I am entering overload.",
        "explain": "Sustained high priority + interrupt density in the recent window.",
    },
    {
        "name": "residue_drift",
        "sentence": "I am drifting toward residue.",
        "explain": "VERIFY_BEFORE_ACTION rate is rising relative to baseline; "
                   "the organism is having to gate more outputs.",
    },
    {
        "name": "novelty_pressure",
        "sentence": "I am under high novelty pressure.",
        "explain": "Mean novelty signal across recent steering rows is elevated.",
    },
    {
        "name": "metabolic_debt",
        "sentence": "I am conserving due to thermal debt.",
        "explain": "Mean metabolic_pressure or CONSERVE_OR_DEFER share is "
                   "above the conservation threshold.",
    },
    {
        "name": "owner_pressure_load",
        "sentence": "I am carrying owner pressure.",
        "explain": "Owner-pressure or care signal is elevated, possibly with "
                   "an EMERGENCY_INTERRUPT in the window.",
    },
    {
        "name": "truth_risk_burn",
        "sentence": "I am burning truth-risk; verification rate is high.",
        "explain": "Mean tool_truth_risk or VERIFY_BEFORE_ACTION rate is "
                   "above the verification threshold.",
    },
)

_NAME_TO_SENTENCE = {d["name"]: d["sentence"] for d in _DETECTORS}
_NAME_TO_EXPLAIN = {d["name"]: d["explain"] for d in _DETECTORS}


# ── Helpers ────────────────────────────────────────────────────────────

def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        n = float(value)
    except Exception:
        n = float(default)
    if n != n or n in (float("inf"), float("-inf")):
        n = float(default)
    return max(0.0, min(1.0, n))


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    return sum(vals) / len(vals) if vals else 0.0


def _state_dir(state_dir: str | Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def read_recent_steering_rows(
    n_rows: int = 20,
    *,
    state_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Tail the steering ledger; return up to n_rows most recent JSON rows.

    Bad lines are skipped silently — the ledger is append-only but a partial
    write at the tail must not crash introspection.
    """
    path = _state_dir(state_dir) / STEERING_LEDGER
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return rows[-max(1, int(n_rows)):]


# ── Self-state model ───────────────────────────────────────────────────

@dataclass(frozen=True)
class SelfStateSignal:
    """One detector's fire-status + the value that crossed threshold."""
    name: str
    value: float
    threshold: float
    fired: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(float(self.value), 4),
            "threshold": round(float(self.threshold), 4),
            "fired": bool(self.fired),
        }


@dataclass(frozen=True)
class SelfModelState:
    """Snapshot of the organism's current steering self-model."""
    window_size: int           # number of steering rows examined
    signals: tuple[SelfStateSignal, ...]
    sentences: tuple[str, ...]  # first-person self-state lines (only fired)
    dominant: str | None        # name of strongest-firing detector, or None
    predicted_next_route: str | None = None
    route_counts: dict[str, int] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    truth_label: str = TRUTH_LABEL

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "truth_label": self.truth_label,
            "window_size": int(self.window_size),
            "signals": [s.to_dict() for s in self.signals],
            "sentences": list(self.sentences),
            "dominant": self.dominant,
            "predicted_next_route": self.predicted_next_route,
            "route_counts": dict(sorted(self.route_counts.items())),
        }


def _detector_overload(rows: list[dict[str, Any]]) -> tuple[float, float]:
    """High priority + interrupt density → overload."""
    if not rows:
        return 0.0, 0.55
    priority = _mean(_clamp01(r.get("priority")) for r in rows)
    interrupt = _mean(_clamp01(r.get("interrupt")) for r in rows)
    emergency_share = sum(
        1 for r in rows if r.get("route") == "EMERGENCY_INTERRUPT"
    ) / len(rows)
    # Weighted aggregate: priority + interrupt mean count, emergencies add.
    value = _clamp01(0.45 * priority + 0.35 * interrupt + 0.50 * emergency_share)
    return value, 0.55


def _detector_residue_drift(rows: list[dict[str, Any]]) -> tuple[float, float]:
    """VERIFY_BEFORE_ACTION rate elevated → drift toward residue."""
    if not rows:
        return 0.0, 0.40
    verify_share = sum(
        1 for r in rows if r.get("route") == "VERIFY_BEFORE_ACTION"
    ) / len(rows)
    return _clamp01(verify_share), 0.40


def _detector_novelty_pressure(rows: list[dict[str, Any]]) -> tuple[float, float]:
    if not rows:
        return 0.0, 0.55
    novelty = _mean(
        _clamp01((r.get("signals") or {}).get("novelty")) for r in rows
    )
    return novelty, 0.55


def _detector_metabolic_debt(rows: list[dict[str, Any]]) -> tuple[float, float]:
    if not rows:
        return 0.0, 0.55
    pressure = _mean(
        _clamp01((r.get("signals") or {}).get("metabolic_pressure")) for r in rows
    )
    conserve_share = sum(
        1 for r in rows if r.get("route") == "CONSERVE_OR_DEFER"
    ) / len(rows)
    value = _clamp01(max(pressure, 0.85 * conserve_share + 0.55 * pressure))
    return value, 0.55


def _detector_owner_pressure_load(
    rows: list[dict[str, Any]],
) -> tuple[float, float]:
    if not rows:
        return 0.0, 0.55
    care = _mean(_clamp01(r.get("care")) for r in rows)
    owner = _mean(
        _clamp01((r.get("signals") or {}).get("owner_pressure")) for r in rows
    )
    had_emergency = any(r.get("route") == "EMERGENCY_INTERRUPT" for r in rows)
    base = max(care, owner)
    if had_emergency:
        base = _clamp01(base + 0.25)
    return base, 0.55


def _detector_truth_risk_burn(rows: list[dict[str, Any]]) -> tuple[float, float]:
    if not rows:
        return 0.0, 0.50
    risk = _mean(
        _clamp01((r.get("signals") or {}).get("tool_truth_risk")) for r in rows
    )
    verify_share = sum(
        1 for r in rows if r.get("route") == "VERIFY_BEFORE_ACTION"
    ) / len(rows)
    value = _clamp01(max(risk, 0.75 * verify_share + 0.35 * risk))
    return value, 0.50


_DETECTOR_FNS = {
    "overload": _detector_overload,
    "residue_drift": _detector_residue_drift,
    "novelty_pressure": _detector_novelty_pressure,
    "metabolic_debt": _detector_metabolic_debt,
    "owner_pressure_load": _detector_owner_pressure_load,
    "truth_risk_burn": _detector_truth_risk_burn,
}


def _route_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        route = str(row.get("route") or "UNKNOWN")
        counts[route] = counts.get(route, 0) + 1
    return counts


def _dominant_observed_route(route_counts: dict[str, int]) -> str | None:
    if not route_counts:
        return None
    return sorted(route_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _predict_next_route(
    rows: list[dict[str, Any]],
    fired_names: set[str],
    route_counts: dict[str, int],
    *,
    state_dir: str | Path | None = None,
    allow_calibrated: bool = True,
) -> str | None:
    """Predict the next steering route from the current self-state.

    This is deliberately conservative and legible. It is not a learned
    predictor; it maps ledger-observed pressure to the next route most likely
    to be needed if the pressure persists.
    """
    if not rows:
        return None
    emergency_share = route_counts.get("EMERGENCY_INTERRUPT", 0) / len(rows)
    if "owner_pressure_load" in fired_names and emergency_share >= 0.20:
        fallback = "EMERGENCY_INTERRUPT"
    elif "truth_risk_burn" in fired_names or "residue_drift" in fired_names:
        fallback = "VERIFY_BEFORE_ACTION"
    elif "metabolic_debt" in fired_names or "overload" in fired_names:
        fallback = "CONSERVE_OR_DEFER"
    elif "novelty_pressure" in fired_names:
        fallback = "DEEP_CORTEX"
    else:
        fallback = _dominant_observed_route(route_counts)
    if not allow_calibrated:
        return fallback
    try:
        from System.swarm_steering_learned_predictor import (
            predict_route_with_learned_model,
        )

        learned = predict_route_with_learned_model(
            fired_names or {"stable"},
            fallback_route=fallback,
            state_dir=state_dir,
        )
        if learned.learned_used and learned.route:
            return learned.route
    except Exception:
        pass
    return fallback


def model_self_state(
    rows: Sequence[dict[str, Any]] | None = None,
    *,
    state_dir: str | Path | None = None,
    n_rows: int = 20,
) -> SelfModelState:
    """Compute current steering self-state.

    If ``rows`` is None, the most-recent ``n_rows`` of the steering ledger
    are read. Otherwise the caller supplies rows (useful for tests).
    """
    rows_supplied = rows is not None
    if rows is None:
        rows_list = read_recent_steering_rows(n_rows, state_dir=state_dir)
    else:
        rows_list = list(rows)

    signals: list[SelfStateSignal] = []
    fired_sentences: list[str] = []
    fired_pairs: list[tuple[str, float]] = []  # (name, margin above threshold)

    for det in _DETECTORS:
        fn = _DETECTOR_FNS[det["name"]]
        value, threshold = fn(rows_list)
        fired = bool(value >= threshold)
        signals.append(SelfStateSignal(
            name=det["name"],
            value=value,
            threshold=threshold,
            fired=fired,
        ))
        if fired:
            fired_sentences.append(det["sentence"])
            fired_pairs.append((det["name"], value - threshold))

    dominant = None
    if fired_pairs:
        fired_pairs.sort(key=lambda p: p[1], reverse=True)
        dominant = fired_pairs[0][0]
    fired_names = {name for name, _margin in fired_pairs}
    route_counts = _route_counts(rows_list)

    return SelfModelState(
        window_size=len(rows_list),
        signals=tuple(signals),
        sentences=tuple(fired_sentences),
        dominant=dominant,
        predicted_next_route=_predict_next_route(
            rows_list,
            fired_names,
            route_counts,
            state_dir=state_dir,
            allow_calibrated=(not rows_supplied or state_dir is not None),
        ),
        route_counts=route_counts,
    )


def write_self_model_receipt(
    state: SelfModelState,
    *,
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append a self-model receipt to steering_self_model.jsonl.

    The receipt is sha256-signed over the deterministic payload (the
    SelfModelState minus its trace_id).
    """
    ts = float(now if now is not None else time.time())
    payload = state.to_dict()
    # sha256 over payload sans trace_id (deterministic by content)
    sign_body = {k: v for k, v in payload.items() if k != "trace_id"}
    sha = hashlib.sha256(
        json.dumps(sign_body, sort_keys=True, separators=(",", ":"),
                   default=str).encode("utf-8")
    ).hexdigest()
    row = dict(payload)
    row.update({
        "schema": "SIFTA_STEERING_SELF_MODEL_RECEIPT_V1",
        "ts": ts,
        "sha256": sha,
        "truth_boundary": TRUTH_BOUNDARY,
    })
    path = _state_dir(state_dir) / SELF_MODEL_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def self_model_prompt_block(
    state: SelfModelState | None = None,
    *,
    state_dir: str | Path | None = None,
    n_rows: int = 20,
    include_stable: bool = False,
) -> str:
    """Compact human-readable block.

    Defaults preserve the original behavior: empty when no detector fired.
    Runtime callers can pass ``include_stable=True`` to give the cortex a
    stable self-state and next-route forecast without waiting for stress.
    """
    if state is None:
        state = model_self_state(state_dir=state_dir, n_rows=n_rows)
    if not state.sentences:
        if not include_stable:
            return ""
        route = state.predicted_next_route or "UNKNOWN"
        return (
            "STEERING SELF-MODEL (HYPOTHESIS — ledger-derived)\n"
            "  - I am stable; no steering stress detector fired in the recent window.\n"
            f"  predicted_next_route: {route}\n"
            f"  truth: {TRUTH_LABEL}"
        )
    lines = ["STEERING SELF-MODEL (HYPOTHESIS — ledger-derived)"]
    for sentence in state.sentences:
        lines.append(f"  - {sentence}")
    if state.dominant:
        lines.append(f"  dominant: {state.dominant}")
    if state.predicted_next_route:
        lines.append(f"  predicted_next_route: {state.predicted_next_route}")
    lines.append(f"  truth: {TRUTH_LABEL}")
    return "\n".join(lines)


def explain_self_state(state: SelfModelState) -> dict[str, str]:
    """Return {detector_name: human-readable explanation} for fired only."""
    return {
        s.name: _NAME_TO_EXPLAIN[s.name]
        for s in state.signals
        if s.fired
    }


def demo_self_model() -> dict[str, Any]:
    """Deterministic demo for smoke tests."""
    # Synthesize a stressed window: lots of VERIFY + a few EMERGENCY +
    # high metabolic_pressure + high tool_truth_risk.
    rows = []
    for _ in range(8):
        rows.append({
            "route": "VERIFY_BEFORE_ACTION",
            "priority": 0.70,
            "interrupt": 0.65,
            "care": 0.50,
            "signals": {
                "metabolic_pressure": 0.80,
                "tool_truth_risk": 0.85,
                "novelty": 0.60,
                "owner_pressure": 0.60,
            },
        })
    for _ in range(2):
        rows.append({
            "route": "EMERGENCY_INTERRUPT",
            "priority": 0.95,
            "interrupt": 0.95,
            "care": 0.85,
            "signals": {
                "metabolic_pressure": 0.95,
                "tool_truth_risk": 0.40,
                "novelty": 0.30,
                "owner_pressure": 0.90,
            },
        })
    state = model_self_state(rows=rows)
    return {
        "truth_label": TRUTH_LABEL,
        "state": state.to_dict(),
        "prompt_block": self_model_prompt_block(state),
        "explain": explain_self_state(state),
    }


__all__ = [
    "SELF_MODEL_LEDGER",
    "STEERING_LEDGER",
    "TRUTH_BOUNDARY",
    "TRUTH_LABEL",
    "SelfModelState",
    "SelfStateSignal",
    "demo_self_model",
    "explain_self_state",
    "model_self_state",
    "read_recent_steering_rows",
    "self_model_prompt_block",
    "write_self_model_receipt",
]


if __name__ == "__main__":
    print(json.dumps(demo_self_model(), indent=2, sort_keys=True))
