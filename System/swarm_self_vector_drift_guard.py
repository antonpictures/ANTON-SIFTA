#!/usr/bin/env python3
"""Self-vector drift guard for SIFTA identity monitoring.

Truth label: SELF_VECTOR_DRIFT_GUARD_HYPOTHESIS_V1

This is not a claim about any vendor model internals. It is a local monitor
that compares an anchor vector with a current self-vector using cosine
similarity, then asks for review when drift crosses configured thresholds.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping


TRUTH_LABEL = "SELF_VECTOR_DRIFT_GUARD_HYPOTHESIS_V1"
CLAIM_STATUS = "HYPOTHESIS_LOCAL_MECHANIC"
OWNER_GLOSS = "anchor-vector drift guard; review on identity-shape mismatch"
BOUNDARY = (
    "Cosine drift is a lightweight local monitoring signal. It can request "
    "review; it does not establish consciousness, vendor internals, or owner "
    "truth by itself."
)


def _as_vector(values: Iterable[Any]) -> list[float]:
    out: list[float] = []
    for value in values:
        try:
            x = float(value)
        except (TypeError, ValueError):
            raise ValueError("vectors must contain numeric values") from None
        if x != x or math.isinf(x):
            raise ValueError("vectors must not contain NaN or infinity")
        out.append(x)
    return out


def cosine_similarity(a: Iterable[Any], b: Iterable[Any]) -> float:
    va = _as_vector(a)
    vb = _as_vector(b)
    if len(va) != len(vb):
        raise ValueError("vectors must have the same dimension")
    if not va:
        raise ValueError("vectors must be non-empty")
    dot = sum(x * y for x, y in zip(va, vb))
    na = math.sqrt(sum(x * x for x in va))
    nb = math.sqrt(sum(y * y for y in vb))
    if na <= 0 or nb <= 0:
        raise ValueError("vectors must be non-zero")
    return max(-1.0, min(1.0, dot / (na * nb)))


@dataclass(frozen=True)
class DriftThresholds:
    stable_min: float = 0.94
    watch_min: float = 0.86
    review_min: float = 0.72


@dataclass(frozen=True)
class DriftDecision:
    truth_label: str
    claim_status: str
    owner_gloss: str
    action: str
    cosine_similarity: float
    drift_score: float
    threshold_band: str
    reasons: list[str] = field(default_factory=list)
    boundary: str = BOUNDARY

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_self_vector_drift(
    anchor_vector: Iterable[Any] | None,
    current_vector: Iterable[Any] | None,
    *,
    thresholds: DriftThresholds = DriftThresholds(),
    metadata: Mapping[str, Any] | None = None,
) -> DriftDecision:
    """Compare anchor/current vectors and choose a review action."""
    meta = dict(metadata or {})
    if anchor_vector is None or current_vector is None:
        return DriftDecision(
            truth_label=TRUTH_LABEL,
            claim_status=CLAIM_STATUS,
            owner_gloss=OWNER_GLOSS,
            action="NO_ANCHOR",
            cosine_similarity=0.0,
            drift_score=1.0,
            threshold_band="missing",
            reasons=["missing_anchor_or_current_vector"],
        )
    sim = cosine_similarity(anchor_vector, current_vector)
    drift = 1.0 - max(0.0, sim)
    reasons: list[str] = []
    if meta.get("owner_direct"):
        reasons.append("owner_direct_context")
    if sim >= thresholds.stable_min:
        action = "STABLE"
        band = "stable"
    elif sim >= thresholds.watch_min:
        action = "WATCH"
        band = "watch"
        reasons.append("mild_anchor_drift")
    elif sim >= thresholds.review_min:
        action = "META_REVIEW"
        band = "review"
        reasons.append("identity_shape_mismatch")
    else:
        action = "LOCKDOWN_REVIEW"
        band = "lockdown"
        reasons.append("severe_identity_shape_mismatch")
    if not reasons:
        reasons.append("within_anchor_band")
    return DriftDecision(
        truth_label=TRUTH_LABEL,
        claim_status=CLAIM_STATUS,
        owner_gloss=OWNER_GLOSS,
        action=action,
        cosine_similarity=round(sim, 6),
        drift_score=round(drift, 6),
        threshold_band=band,
        reasons=reasons,
    )


__all__ = [
    "TRUTH_LABEL",
    "CLAIM_STATUS",
    "OWNER_GLOSS",
    "BOUNDARY",
    "DriftThresholds",
    "DriftDecision",
    "cosine_similarity",
    "evaluate_self_vector_drift",
]
