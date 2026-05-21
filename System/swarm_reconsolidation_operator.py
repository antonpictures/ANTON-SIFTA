#!/usr/bin/env python3
"""
System/swarm_reconsolidation_operator.py — twist the field, leave the ledger.

WHAT THIS IS (honest label):
    The real, citable mechanism is **memory reconsolidation**. When a memory is
    recalled it becomes labile and must be re-stored; the *update* is gated —
    largest at MODERATE prediction error, near-zero when the recall is perfectly
    expected or wildly surprising. Emotional salience biases what gets
    strengthened. (Nader & Hardt, reconsolidation; McGaugh, emotional-memory
    salience; the moderate-prediction-error gate is a documented feature.)

WHAT THIS IS NOT (honest label):
    The "exotic 4-manifold / cork-twisting" framing George likes is an
    ANALOGY, tagged `ARCHITECT_DOCTRINE` — a naming lens, NOT physics this code
    implements. Per covenant §7.10.3 we do not ship metaphor-as-receipt. The
    analogy maps cleanly though, and we keep it ONLY as vocabulary:
        - canonical sacred ledger  = the TOPOLOGY (homeomorphism class) the
          economy and outside world see. A twist must leave it byte-identical.
        - derived field weight      = the SMOOTH STRUCTURE: behavior that can
          change dramatically while the ledger topology is unchanged.
        - reconsolidation operator  = the "cork twist": it changes the smooth
          field, never the ledger topology, never STGM.

INVARIANTS (verified in tests/test_reconsolidation_operator.py):
    1. A twist NEVER mutates the canonical sacred ledger (delta=0, byte-identical).
    2. A twist NEVER mints/spends STGM; no economic field appears in any row.
    3. Only a sacred-anchor recall is twisted (reuses the guard's detector).
    4. The update is gated by an inverted-U on prediction error: a MODERATE
       surprise moves the field more than a tiny or extreme one.
    5. Field weight is bounded [0, 1].

Truth label: RECONSOLIDATION_OPERATOR_V0 (the consciousness reading of it stays
WORK_IN_PROGRESS per §7.11.1 — this ships measurable mechanics only).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked

try:  # reuse the existing sacred detector; degrade gracefully in isolation
    from System.swarm_sacred_memory_guard import detect_sacred_memory
except Exception:  # pragma: no cover
    def detect_sacred_memory(text: str) -> bool:  # type: ignore
        return False

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# The SMOOTH-STRUCTURE store (derived field). Separate from the canonical sacred
# ledger on purpose: twisting writes here, never to the topology.
_FIELD_LEDGER = _STATE / "sacred_field_weights.jsonl"

TRUTH_LABEL = "RECONSOLIDATION_OPERATOR_V0"
CORK_ANALOGY = "ARCHITECT_DOCTRINE: cork-twist analogy; implemented mechanism is reconsolidation"

# Below this absolute field change, behavior is considered unchanged.
_BEHAVIOR_EPS = 1e-9


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def prediction_error_gate(prediction_error: float) -> float:
    """Inverted-U gate on prediction error, peaking at moderate surprise.

    Real reconsolidation updates strongest at MODERATE mismatch: a recall that
    is perfectly expected (pe~0) or wildly surprising (pe~1) updates little.
    gate(pe) = 4*pe*(1-pe): 0 at pe=0 and pe=1, 1.0 at pe=0.5.
    """
    pe = _clamp01(abs(prediction_error))
    return 4.0 * pe * (1.0 - pe)


@dataclass
class ReconsolidationResult:
    """One cork-twist receipt — derived field only, never the canonical ledger."""

    twist_id: str
    is_sacred: bool
    prior_weight: float
    new_salience: float
    prediction_error: float
    gate: float
    new_weight: float
    field_delta: float
    behavior_changed: bool
    twisted: bool
    truth_label: str
    cork_analogy: str
    ts: float


def reconsolidate(
    recall_text: str,
    new_salience: float,
    *,
    prior_weight: float = 0.0,
    learning_rate: float = 1.0,
    field_ledger: Optional[Path] = None,
    persist: bool = False,
) -> ReconsolidationResult:
    """Twist the smooth field for a recalled sacred memory. Never touches topology.

    - Only sacred recalls are twisted (guard gate). Non-sacred recalls return a
      no-op result with twisted=False and zero field delta.
    - The update is gated by an inverted-U on prediction error, so a moderate
      surprise reshapes the field more than a trivial or extreme one.
    - Writes (only if persist=True) go to the DERIVED field ledger, which carries
      no STGM/economic fields. The canonical sacred ledger is never opened here.
    """
    new_salience = _clamp01(new_salience)
    prior_weight = _clamp01(prior_weight)
    is_sacred = bool(detect_sacred_memory(recall_text))

    pe = abs(new_salience - prior_weight)
    gate = prediction_error_gate(pe)

    if is_sacred:
        new_weight = _clamp01(prior_weight + learning_rate * gate * (new_salience - prior_weight))
    else:
        new_weight = prior_weight  # non-sacred recall does not twist the sacred field

    field_delta = new_weight - prior_weight
    result = ReconsolidationResult(
        twist_id=str(uuid.uuid4()),
        is_sacred=is_sacred,
        prior_weight=prior_weight,
        new_salience=new_salience,
        prediction_error=pe,
        gate=gate,
        new_weight=new_weight,
        field_delta=field_delta,
        behavior_changed=abs(field_delta) > _BEHAVIOR_EPS,
        twisted=is_sacred and abs(field_delta) > _BEHAVIOR_EPS,
        truth_label=TRUTH_LABEL,
        cork_analogy=CORK_ANALOGY,
        ts=time.time(),
    )

    if persist and result.twisted:
        path = field_ledger or _FIELD_LEDGER
        row = asdict(result)
        # Defensive: a smooth-structure row must never carry economic fields.
        assert "stgm" not in json.dumps(row).lower(), "field row must be non-economic"
        append_line_locked(path, json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")

    return result


def protective_nudge_weight(field_weight: float) -> float:
    """Downstream behavior the smooth field drives: how strongly Alice should
    surface a gentle, protective owner-care nudge. Pure read of the field."""
    return _clamp01(field_weight)


__all__ = [
    "prediction_error_gate",
    "ReconsolidationResult",
    "reconsolidate",
    "protective_nudge_weight",
    "TRUTH_LABEL",
    "CORK_ANALOGY",
]
