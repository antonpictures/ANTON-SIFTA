"""Supplemental edge tests for swarm_steering_prediction_audit.

§8.5 audit. Codex shipped both the module and tests/test_swarm_steering_
prediction_audit.py (12 tests covering happy paths + 4 status indicators).
This file pins ONLY the edges his tests don't already cover, so the two
files remain side-by-side without overlap.

Edges pinned here:
  - Self-model rows with predicted_next_route=None must be skipped
  - Steering row at exactly ts == prediction ts must be skipped
    (the "next" actual must be strictly after)
  - by_detector cross-grouping: when a row has multiple fired detectors,
    that row is counted in EACH detector's bucket
  - Confidence floor when a detector fires (>= 0.50)
  - Determinism on same inputs (modulo trace_id)
  - Missing-ts on self-model row should not crash the pairer
  - Missing-route on steering row should not crash the pairer
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_steering_prediction_audit import (  # noqa: E402
    audit_predictions,
    pair_predictions,
)


def _self_row(
    ts,
    *,
    trace,
    predicted,
    dominant=None,
    fired=None,
    route_counts=None,
):
    """Build a self-model row. ``fired`` is list of (name, value, threshold)."""
    sigs = []
    for name, value, threshold in (fired or []):
        sigs.append({
            "name": name, "value": value, "threshold": threshold, "fired": True,
        })
    row = {
        "ts": float(ts),
        "trace_id": trace,
        "signals": sigs,
        "route_counts": route_counts or {},
    }
    if predicted is not None:
        row["predicted_next_route"] = predicted
    if dominant is not None:
        row["dominant"] = dominant
    return row


def _steering_row(ts, *, trace, route):
    return {"ts": float(ts), "trace_id": trace, "route": route}


# ── Edge 1: predicted_next_route=None is skipped ──────────────────────

def test_self_model_rows_without_prediction_are_skipped():
    """A self-model row with predicted_next_route missing must NOT
    produce a pair even when a subsequent steering row exists."""
    sm = [
        _self_row(10.0, trace="s_no_pred", predicted=None),
        _self_row(20.0, trace="s_with", predicted="FAST_REFLEX",
                  dominant="overload",
                  fired=[("overload", 0.65, 0.55)]),
    ]
    st = [
        _steering_row(11.0, trace="a1", route="FAST_REFLEX"),
        _steering_row(21.0, trace="a2", route="FAST_REFLEX"),
    ]
    pairs = pair_predictions(sm, st)
    assert len(pairs) == 1
    assert pairs[0].prediction_trace_id == "s_with"


# ── Edge 2: ts strictly greater (==prediction ts must be skipped) ─────

def test_steering_row_at_exact_prediction_ts_is_not_the_next():
    """The 'next actual route' must be strictly after the prediction,
    not simultaneous with it."""
    sm = [_self_row(10.0, trace="s1", predicted="DEEP_CORTEX",
                    dominant="novelty_pressure",
                    fired=[("novelty_pressure", 0.80, 0.55)])]
    st = [
        _steering_row(10.0, trace="a_same_ts", route="FAST_REFLEX"),
        _steering_row(11.0, trace="a_after", route="DEEP_CORTEX"),
    ]
    pairs = pair_predictions(sm, st)
    assert len(pairs) == 1
    assert pairs[0].actual_trace_id == "a_after"
    assert pairs[0].correct is True


# ── Edge 3: by_detector cross-grouping with multiple fired detectors ──

def test_by_detector_counts_each_fired_detector_for_the_same_pair():
    """A self-model row with two fired detectors must show up in BOTH
    of those detectors' buckets in by_detector."""
    sm = [_self_row(
        10.0, trace="s1", predicted="VERIFY_BEFORE_ACTION",
        dominant="truth_risk_burn",
        fired=[
            ("truth_risk_burn", 0.70, 0.50),
            ("residue_drift", 0.45, 0.40),
        ],
    )]
    st = [_steering_row(11.0, trace="a1", route="VERIFY_BEFORE_ACTION")]
    audit = audit_predictions(self_rows=sm, steering_rows=st)
    assert set(audit.by_detector.keys()) == {"truth_risk_burn", "residue_drift"}
    for stats in audit.by_detector.values():
        assert stats["sample_count"] == 1
        assert stats["accuracy"] == 1.0
    # by_dominant_detector picks ONLY the dominant one
    assert set(audit.by_dominant_detector.keys()) == {"truth_risk_burn"}


# ── Edge 4: confidence floor when a detector fires ────────────────────

def test_confidence_is_at_least_floor_when_detector_fired():
    sm = [_self_row(10.0, trace="s1", predicted="FAST_REFLEX",
                    dominant="overload",
                    fired=[("overload", 0.60, 0.55)])]
    st = [_steering_row(11.0, trace="a1", route="FAST_REFLEX")]
    pairs = pair_predictions(sm, st)
    assert len(pairs) == 1
    assert 0.50 <= pairs[0].confidence <= 1.0


# ── Edge 5: determinism on same input ─────────────────────────────────

def test_audit_is_deterministic_on_same_input():
    sm = [
        _self_row(10.0, trace="s1", predicted="DEEP_CORTEX",
                  dominant="novelty_pressure",
                  fired=[("novelty_pressure", 0.80, 0.55)]),
        _self_row(20.0, trace="s2", predicted="CONSERVE_OR_DEFER",
                  dominant="metabolic_debt",
                  fired=[("metabolic_debt", 0.90, 0.55)]),
    ]
    st = [
        _steering_row(11.0, trace="a1", route="DEEP_CORTEX"),
        _steering_row(21.0, trace="a2", route="CONSERVE_OR_DEFER"),
    ]
    a1 = audit_predictions(self_rows=sm, steering_rows=st)
    a2 = audit_predictions(self_rows=sm, steering_rows=st)
    d1 = a1.to_dict(); d1.pop("trace_id")
    d2 = a2.to_dict(); d2.pop("trace_id")
    assert d1 == d2


# ── Edge 6 & 7: missing fields must not crash the pairer ─────────────

def test_self_model_row_missing_ts_is_skipped():
    """A self-model row without a numeric ts must be filtered out
    (Codex checks isinstance(ts, (int, float))) — pairer still finds
    other valid pairs."""
    sm = [
        {"trace_id": "no_ts", "predicted_next_route": "DEEP_CORTEX",
         "dominant": "novelty_pressure", "signals": []},
        _self_row(20.0, trace="ok", predicted="DEEP_CORTEX",
                  dominant="novelty_pressure",
                  fired=[("novelty_pressure", 0.80, 0.55)]),
    ]
    st = [_steering_row(21.0, trace="a1", route="DEEP_CORTEX")]
    pairs = pair_predictions(sm, st)
    assert len(pairs) == 1
    assert pairs[0].prediction_trace_id == "ok"


def test_steering_row_missing_route_is_skipped():
    sm = [_self_row(10.0, trace="s1", predicted="DEEP_CORTEX",
                    dominant="novelty_pressure",
                    fired=[("novelty_pressure", 0.80, 0.55)])]
    st = [
        {"ts": 11.0, "trace_id": "no_route"},
        _steering_row(12.0, trace="a_ok", route="DEEP_CORTEX"),
    ]
    pairs = pair_predictions(sm, st)
    assert len(pairs) == 1
    assert pairs[0].actual_trace_id == "a_ok"
