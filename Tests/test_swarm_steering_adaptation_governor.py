"""Tests for the Steering Adaptation Governor.

Architect 2026-05-14: "Build the Steering Adaptation Governor: calibrate
self-model detector weights from prediction-audit accuracy, write
append-only adaptation receipts, expose current detector weights to Talk
prompt, and never adapt without enough paired evidence."

The Architect also asked the §7.12 check first: "another governor? are u
sure is not hallucinacion?" These tests pin the honest answer:
  - The governor REFUSES to adapt when n < 10 samples
  - Today's real-world output is NO_CHANGE_INSUFFICIENT_DATA — not failure,
    calibrated truth
  - It's a pure writer: detector_weights are emitted; nothing else in the
    system consumes them yet (separate Architect GO required to wire into
    _predict_next_route)

Threshold contract (from Architect spec, verbatim):
  if detector accuracy > 0.75 and n >= 10 → weight +0.05
  if detector accuracy < 0.45 and n >= 10 → weight -0.05
  else                                    → no change
  clamp weights to [0.5, 1.5]
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_steering_adaptation_governor import (  # noqa: E402
    ADAPTATION_LEDGER,
    AUDIT_LEDGER,
    BOOST_THRESHOLD,
    DAMPEN_THRESHOLD,
    INIT_WEIGHT,
    MIN_SAMPLES_TO_ADAPT,
    TRUTH_BOUNDARY,
    TRUTH_LABEL,
    WEIGHT_DELTA,
    WEIGHT_MAX,
    WEIGHT_MIN,
    AdaptationReport,
    DetectorAdaptation,
    adapt,
    adaptation_prompt_block,
    latest_adaptation_weights,
    latest_audit_row,
    write_adaptation_receipt,
)


# ── Fixture builders ──────────────────────────────────────────────────

def _audit_row(by_detector: dict[str, tuple[int, float]]) -> dict:
    """Build a minimal audit row.

    by_detector: {detector_name: (sample_count, accuracy)}
    """
    sample_total = sum(n for n, _ in by_detector.values())
    correct_total = sum(int(n * a) for n, a in by_detector.values())
    return {
        "trace_id": "audit-test",
        "ts": 100.0,
        "sample_count": sample_total,
        "correct_count": correct_total,
        "accuracy": (correct_total / sample_total) if sample_total else 0.0,
        "status": "PAIRED_BUT_UNDERPOWERED",
        "by_dominant_detector": {
            name: {
                "sample_count": n,
                "correct_count": int(n * acc),
                "accuracy": acc,
            }
            for name, (n, acc) in by_detector.items()
        },
        "by_detector": {},
        "pairs": [],
    }


# ── Taxonomy ──────────────────────────────────────────────────────────

def test_truth_label_is_v1():
    assert TRUTH_LABEL == "STEERING_ADAPTATION_GOVERNOR_V1"


def test_thresholds_match_architect_spec():
    """The Architect's spec is pinned to constants — any future drift fails."""
    assert MIN_SAMPLES_TO_ADAPT == 10
    assert BOOST_THRESHOLD == 0.75
    assert DAMPEN_THRESHOLD == 0.45
    assert WEIGHT_DELTA == 0.05
    assert WEIGHT_MIN == 0.5
    assert WEIGHT_MAX == 1.5
    assert INIT_WEIGHT == 1.0


def test_truth_boundary_disclaims_learning_and_self_awareness():
    text = TRUTH_BOUNDARY.lower()
    assert "hypothesis" in text
    # Must explicitly disclaim the two over-reach risks
    assert "not neural learned" in text
    assert "not a claim of self-awareness" in text or "self-awareness" in text
    # Must say coupling is sample-gated, not blind policy mutation
    assert "_predict_next_route" in TRUTH_BOUNDARY
    assert "sample gate" in text


# ── Insufficient samples = the case we're actually in today ───────────

def test_below_min_samples_holds_weight():
    """n < 10 → INSUFFICIENT_SAMPLES regardless of accuracy."""
    row = _audit_row({"novelty_pressure": (2, 1.0)})  # 100% but only 2 samples
    report = adapt(audit_row=row, previous_weights={})
    assert report.overall_status == "NO_CHANGE_INSUFFICIENT_DATA"
    assert len(report.adaptations) == 1
    a = report.adaptations[0]
    assert a.status == "INSUFFICIENT_SAMPLES"
    assert a.previous_weight == 1.0
    assert a.new_weight == 1.0
    assert a.delta == 0.0
    assert report.detector_weights["novelty_pressure"] == 1.0


def test_insufficient_samples_at_dampen_accuracy_still_holds():
    row = _audit_row({"truth_risk_burn": (5, 0.20)})  # 20% accuracy but n<10
    report = adapt(audit_row=row, previous_weights={})
    a = report.adaptations[0]
    assert a.status == "INSUFFICIENT_SAMPLES"
    assert a.new_weight == 1.0


# ── Boost branch (accuracy > 0.75 AND n >= 10) ────────────────────────

def test_high_accuracy_above_threshold_boosts():
    row = _audit_row({"novelty_pressure": (12, 0.83)})
    report = adapt(audit_row=row, previous_weights={"novelty_pressure": 1.0})
    a = report.adaptations[0]
    assert a.status == "ADAPTED_BOOST"
    assert a.delta == pytest_approx(0.05)
    assert a.new_weight == pytest_approx(1.05)
    assert report.overall_status == "ADAPTED"


def test_accuracy_at_exactly_boost_threshold_does_not_boost():
    """Architect spec is strict >, not >=. Pin that."""
    row = _audit_row({"novelty_pressure": (12, 0.75)})
    report = adapt(audit_row=row, previous_weights={"novelty_pressure": 1.0})
    a = report.adaptations[0]
    assert a.status == "NO_CHANGE"
    assert a.new_weight == 1.0


# ── Dampen branch (accuracy < 0.45 AND n >= 10) ───────────────────────

def test_low_accuracy_dampens():
    row = _audit_row({"truth_risk_burn": (15, 0.30)})
    report = adapt(audit_row=row, previous_weights={"truth_risk_burn": 1.0})
    a = report.adaptations[0]
    assert a.status == "ADAPTED_DAMPEN"
    assert a.delta == pytest_approx(-0.05)
    assert a.new_weight == pytest_approx(0.95)


def test_accuracy_at_exactly_dampen_threshold_does_not_dampen():
    row = _audit_row({"truth_risk_burn": (15, 0.45)})
    report = adapt(audit_row=row, previous_weights={"truth_risk_burn": 1.0})
    a = report.adaptations[0]
    assert a.status == "NO_CHANGE"
    assert a.new_weight == 1.0


# ── Mid-band = no change ──────────────────────────────────────────────

def test_mid_band_accuracy_holds():
    row = _audit_row({"overload": (20, 0.60)})
    report = adapt(audit_row=row, previous_weights={"overload": 1.0})
    a = report.adaptations[0]
    assert a.status == "NO_CHANGE"
    assert "mid-band" in a.reason


# ── Clamps at upper and lower bounds ──────────────────────────────────

def test_weight_clamps_at_upper_bound():
    row = _audit_row({"novelty_pressure": (50, 0.95)})
    # Start one delta below the clamp
    report = adapt(
        audit_row=row,
        previous_weights={"novelty_pressure": WEIGHT_MAX},  # already at 1.5
    )
    a = report.adaptations[0]
    # No change because we're already pinned; status NO_CHANGE
    assert a.new_weight == WEIGHT_MAX
    assert a.status == "NO_CHANGE"


def test_weight_clamps_at_lower_bound():
    row = _audit_row({"truth_risk_burn": (50, 0.10)})
    report = adapt(
        audit_row=row,
        previous_weights={"truth_risk_burn": WEIGHT_MIN},
    )
    a = report.adaptations[0]
    assert a.new_weight == WEIGHT_MIN
    assert a.status == "NO_CHANGE"


def test_repeated_boosts_eventually_hit_upper_clamp():
    """Apply boost cycles; weight should saturate at 1.5."""
    row = _audit_row({"novelty_pressure": (30, 0.90)})
    weights = {"novelty_pressure": 1.0}
    last_weight = 1.0
    saturated_at = None
    for cycle in range(50):
        report = adapt(audit_row=row, previous_weights=weights)
        weights = dict(report.detector_weights)
        w = weights["novelty_pressure"]
        if w == WEIGHT_MAX and last_weight == WEIGHT_MAX:
            saturated_at = cycle
            break
        last_weight = w
    assert saturated_at is not None
    assert weights["novelty_pressure"] == WEIGHT_MAX


# ── Carry-forward across cycles ───────────────────────────────────────

def test_unknown_detector_starts_at_init_weight():
    row = _audit_row({"new_detector": (12, 0.80)})
    report = adapt(audit_row=row, previous_weights={})
    a = report.adaptations[0]
    assert a.previous_weight == INIT_WEIGHT
    assert a.new_weight == pytest_approx(INIT_WEIGHT + WEIGHT_DELTA)


def test_existing_detector_uses_its_previous_weight():
    row = _audit_row({"novelty_pressure": (12, 0.85)})
    report = adapt(
        audit_row=row,
        previous_weights={"novelty_pressure": 1.20},
    )
    a = report.adaptations[0]
    assert a.previous_weight == 1.20
    assert a.new_weight == pytest_approx(1.25)


def test_detector_absent_from_audit_keeps_previous_weight():
    """If a detector was previously known but isn't in this audit,
    its weight must be carried forward unchanged."""
    row = _audit_row({"novelty_pressure": (12, 0.90)})
    report = adapt(
        audit_row=row,
        previous_weights={
            "novelty_pressure": 1.0,
            "old_detector": 1.15,  # not in this audit
        },
    )
    # Both should appear in the new weights
    assert "novelty_pressure" in report.detector_weights
    assert "old_detector" in report.detector_weights
    assert report.detector_weights["old_detector"] == 1.15


# ── Empty / missing audit ─────────────────────────────────────────────

def test_no_audit_row_yields_no_audit_status(tmp_path):
    """audit_row=None falls back to reading the ledger; with state_dir
    pointed at an empty tmp_path, the lookup misses and overall_status
    must be NO_AUDIT."""
    report = adapt(
        previous_weights={"novelty_pressure": 1.10},
        state_dir=tmp_path,
    )
    assert report.overall_status == "NO_AUDIT"
    # Carry weights forward
    assert report.detector_weights["novelty_pressure"] == 1.10
    assert report.adaptations == ()


def test_audit_with_no_by_detector_yields_no_change():
    row = _audit_row({})
    report = adapt(audit_row=row, previous_weights={})
    assert report.overall_status == "NO_CHANGE_INSUFFICIENT_DATA"
    assert report.adaptations == ()


# ── Receipt round-trip ────────────────────────────────────────────────

def test_receipt_is_sha256_signed(tmp_path):
    row = _audit_row({"novelty_pressure": (12, 0.85)})
    report = adapt(audit_row=row, previous_weights={"novelty_pressure": 1.0})
    receipt = write_adaptation_receipt(report, state_dir=tmp_path)
    body = {k: v for k, v in report.to_dict().items() if k != "trace_id"}
    expected = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"),
                   default=str).encode("utf-8")
    ).hexdigest()
    assert receipt["sha256"] == expected
    assert receipt["schema"] == "SIFTA_STEERING_ADAPTATION_GOVERNOR_RECEIPT_V1"
    assert receipt["truth_boundary"] == TRUTH_BOUNDARY
    # Ledger persists
    ledger = tmp_path / ADAPTATION_LEDGER
    parsed = json.loads(ledger.read_text().strip())
    assert parsed["sha256"] == expected
    assert parsed["overall_status"] == "ADAPTED"


def test_latest_adaptation_weights_round_trips(tmp_path):
    row = _audit_row({"novelty_pressure": (12, 0.85)})
    report = adapt(audit_row=row, previous_weights={"novelty_pressure": 1.0})
    write_adaptation_receipt(report, state_dir=tmp_path)
    weights = latest_adaptation_weights(state_dir=tmp_path)
    assert weights["novelty_pressure"] == pytest_approx(1.05)


def test_latest_adaptation_weights_returns_empty_when_no_ledger(tmp_path):
    assert latest_adaptation_weights(state_dir=tmp_path) == {}


def test_latest_audit_row_returns_none_when_no_ledger(tmp_path):
    assert latest_audit_row(state_dir=tmp_path) is None


# ── Determinism ───────────────────────────────────────────────────────

def test_adapt_is_deterministic_on_same_inputs():
    row = _audit_row({"novelty_pressure": (12, 0.85), "truth_risk_burn": (15, 0.30)})
    r1 = adapt(audit_row=row, previous_weights={})
    r2 = adapt(audit_row=row, previous_weights={})
    d1 = r1.to_dict(); d1.pop("trace_id")
    d2 = r2.to_dict(); d2.pop("trace_id")
    assert d1 == d2


# ── Multi-detector mix ────────────────────────────────────────────────

def test_mixed_detectors_each_handled_independently():
    row = _audit_row({
        "novelty_pressure": (20, 0.90),     # boost
        "truth_risk_burn": (15, 0.20),       # dampen
        "overload": (12, 0.55),              # mid-band, no change
        "metabolic_debt": (3, 0.30),         # insufficient samples
    })
    report = adapt(audit_row=row, previous_weights={})
    statuses = {a.name: a.status for a in report.adaptations}
    assert statuses["novelty_pressure"] == "ADAPTED_BOOST"
    assert statuses["truth_risk_burn"] == "ADAPTED_DAMPEN"
    assert statuses["overload"] == "NO_CHANGE"
    assert statuses["metabolic_debt"] == "INSUFFICIENT_SAMPLES"
    # Overall status: at least one ADAPTED → ADAPTED
    assert report.overall_status == "ADAPTED"
    # Weights moved correctly
    assert report.detector_weights["novelty_pressure"] == pytest_approx(1.05)
    assert report.detector_weights["truth_risk_burn"] == pytest_approx(0.95)
    assert report.detector_weights["overload"] == 1.0
    assert report.detector_weights["metabolic_debt"] == 1.0


# ── Prompt block ──────────────────────────────────────────────────────

def test_prompt_block_carries_status_weights_and_truth():
    row = _audit_row({"novelty_pressure": (12, 0.90)})
    report = adapt(audit_row=row, previous_weights={})
    block = adaptation_prompt_block(report)
    assert "STEERING ADAPTATION GOVERNOR" in block
    assert "ADAPTED" in block
    assert "novelty_pressure" in block
    assert TRUTH_LABEL in block


def test_prompt_block_today_shows_insufficient_data():
    """The honest baseline: 2 samples → status reflects insufficient data."""
    row = _audit_row({"novelty_pressure": (2, 1.0)})
    report = adapt(audit_row=row, previous_weights={})
    block = adaptation_prompt_block(report)
    assert "NO_CHANGE_INSUFFICIENT_DATA" in block


# ── pytest_approx shim (no numpy dependency needed) ───────────────────

def pytest_approx(value, tol=1e-6):
    class _Approx:
        def __init__(self, v): self.v = float(v)
        def __eq__(self, other):
            try:
                return abs(float(other) - self.v) <= tol
            except Exception:
                return False
        def __repr__(self): return f"~{self.v}"
    return _Approx(value)
