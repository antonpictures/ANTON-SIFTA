#!/usr/bin/env python3
"""Adaptive compute gate for SIFTA inference budgeting.

Truth label: ADAPTIVE_COMPUTE_GATE_HYPOTHESIS_V1

This is not a claim about Gemini internals. It is a local SIFTA gate inspired
by adaptive computation time, early-exit entropy thresholds, and adaptive
test-time compute research. Callers provide observable uncertainty and pressure
signals; this organ returns a deterministic budget decision.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping


TRUTH_LABEL = "ADAPTIVE_COMPUTE_GATE_HYPOTHESIS_V1"
CLAIM_STATUS = "HYPOTHESIS_LOCAL_MECHANIC"
BOUNDARY = (
    "This gate uses local uncertainty signals to choose a compute budget; it "
    "does not describe Gemini, OpenAI, Anthropic, or any vendor's private "
    "routing internals."
)


def clamp01(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return 0.0
    if x != x:
        return 0.0
    return max(0.0, min(1.0, x))


def entropy_bits(probabilities: Iterable[float]) -> float:
    """Shannon entropy in bits over a probability-like vector."""
    vals = [max(0.0, float(p)) for p in probabilities]
    total = sum(vals)
    if total <= 0:
        return 0.0
    probs = [p / total for p in vals if p > 0]
    return -sum(p * math.log2(p) for p in probs)


def normalized_entropy(probabilities: Iterable[float]) -> float:
    vals = [max(0.0, float(p)) for p in probabilities]
    positive = [p for p in vals if p > 0]
    if len(positive) <= 1:
        return 0.0
    return clamp01(entropy_bits(positive) / math.log2(len(positive)))


def probability_conflict(probabilities: Iterable[float]) -> float:
    """Conflict score from top-1/top-2 margin; high means ambiguous."""
    vals = sorted((max(0.0, float(p)) for p in probabilities), reverse=True)
    total = sum(vals)
    if total <= 0 or len(vals) < 2:
        return 0.0
    top1 = vals[0] / total
    top2 = vals[1] / total
    return clamp01(1.0 - (top1 - top2))


@dataclass(frozen=True)
class ComputeSignals:
    """Observable local signals. All fields are normalized to [0, 1]."""

    token_entropy: float = 0.0
    probability_conflict: float = 0.0
    task_risk: float = 0.0
    owner_direct: float = 0.0
    thermal_pressure: float = 0.0
    stgm_pressure: float = 0.0
    latency_pressure: float = 0.0
    source: str = "caller_supplied"

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "ComputeSignals":
        return cls(
            token_entropy=clamp01(row.get("token_entropy", row.get("entropy", 0.0))),
            probability_conflict=clamp01(row.get("probability_conflict", row.get("conflict", 0.0))),
            task_risk=clamp01(row.get("task_risk", row.get("risk", 0.0))),
            owner_direct=clamp01(row.get("owner_direct", 0.0)),
            thermal_pressure=clamp01(row.get("thermal_pressure", 0.0)),
            stgm_pressure=clamp01(row.get("stgm_pressure", 0.0)),
            latency_pressure=clamp01(row.get("latency_pressure", 0.0)),
            source=str(row.get("source", "caller_supplied")),
        )


@dataclass(frozen=True)
class ComputeDecision:
    truth_label: str
    claim_status: str
    action: str
    budget_multiplier: float
    uncertainty_score: float
    pressure_score: float
    reasons: list[str] = field(default_factory=list)
    boundary: str = BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decide_compute_budget(signals: ComputeSignals | Mapping[str, Any]) -> ComputeDecision:
    """Choose a local inference budget from uncertainty and body pressure.

    Actions:
      - FAST_PASS: low uncertainty/risk; keep budget small.
      - DEEPEN: spend more local reasoning budget.
      - CONSERVE: uncertainty exists, but body pressure says keep it bounded.
      - DEFER: pressure is too high for non-emergency compute.
    """
    sig = signals if isinstance(signals, ComputeSignals) else ComputeSignals.from_mapping(signals)
    uncertainty = clamp01(
        0.38 * sig.token_entropy
        + 0.32 * sig.probability_conflict
        + 0.20 * sig.task_risk
        + 0.10 * sig.owner_direct
    )
    pressure = clamp01(
        0.45 * sig.thermal_pressure
        + 0.35 * sig.stgm_pressure
        + 0.20 * sig.latency_pressure
    )
    reasons: list[str] = []
    if sig.token_entropy >= 0.65:
        reasons.append("high_entropy")
    if sig.probability_conflict >= 0.65:
        reasons.append("probability_conflict")
    if sig.task_risk >= 0.60:
        reasons.append("task_risk")
    if sig.owner_direct >= 0.60:
        reasons.append("owner_direct")
    if pressure >= 0.75:
        reasons.append("body_pressure_high")
        action = "DEFER"
        multiplier = 0.35
    elif pressure >= 0.55 and uncertainty >= 0.45:
        reasons.append("body_pressure_conserve")
        action = "CONSERVE"
        multiplier = 0.75
    elif uncertainty >= 0.58:
        action = "DEEPEN"
        multiplier = 1.0 + min(1.75, 2.0 * uncertainty)
    elif uncertainty >= 0.35:
        action = "WATCH"
        multiplier = 1.0
    else:
        action = "FAST_PASS"
        multiplier = 0.55
    if not reasons:
        reasons.append("low_uncertainty")
    return ComputeDecision(
        truth_label=TRUTH_LABEL,
        claim_status=CLAIM_STATUS,
        action=action,
        budget_multiplier=round(multiplier, 4),
        uncertainty_score=round(uncertainty, 4),
        pressure_score=round(pressure, 4),
        reasons=reasons,
    )


__all__ = [
    "TRUTH_LABEL",
    "CLAIM_STATUS",
    "BOUNDARY",
    "ComputeSignals",
    "ComputeDecision",
    "clamp01",
    "entropy_bits",
    "normalized_entropy",
    "probability_conflict",
    "decide_compute_budget",
]
