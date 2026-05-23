"""tests/test_cool_worlds_toy.py — pytest suite for cool_worlds_toy.py"""
import sys; sys.path.insert(0, '.')
from Applications.cool_worlds_toy import (
    contact_inequality_mc, eschatian_sampler,
    ledger_reliability_curve, run_and_report,
    T_EARTH_GYR,
)


def test_contact_inequality_bias_factor_greater_than_one():
    """First contact partner is expected to be OLDER than Earth."""
    r = contact_inequality_mc(n_samples=10_000, seed=42)
    assert r.bias_factor > 1.0, f"Bias factor should be >1, got {r.bias_factor}"


def test_contact_p_older_than_earth_majority():
    """P(partner older than Earth) should be >50%."""
    r = contact_inequality_mc(n_samples=10_000, seed=42)
    assert r.p_older_than_earth > 0.5


def test_contact_truth_label():
    r = contact_inequality_mc(n_samples=1000, seed=1)
    assert r.truth_label == "OBSERVED"


def test_eschatian_ratio_computed():
    r = eschatian_sampler(n_samples=10_000, seed=42)
    assert r.eschatian_ratio >= 0.0
    assert r.p_detection_near_end >= 0.0
    assert r.p_detection_peak >= 0.0


def test_eschatian_truth_label():
    r = eschatian_sampler(n_samples=1000, seed=1)
    assert r.truth_label == "OBSERVED"


def test_ledger_reliability_curve_monotone():
    """More receipts → higher P(true). Monotone non-decreasing."""
    curve = ledger_reliability_curve(max_receipts=20)
    probs = [row["p_true"] for row in curve]
    for i in range(1, len(probs)):
        assert probs[i] >= probs[i - 1], f"Not monotone at index {i}"


def test_ledger_reliability_zero_receipts_below_one():
    """With no receipts, P(true) must be < 1 (prior skepticism)."""
    curve = ledger_reliability_curve(max_receipts=5)
    assert curve[0]["p_true"] < 1.0


def test_ledger_reliability_zero_receipts_truth_label():
    """Zero-receipt row is HYPOTHESIS, not OPERATIONAL."""
    curve = ledger_reliability_curve(max_receipts=5)
    assert curve[0]["truth_label"] == "HYPOTHESIS"


def test_run_and_report_keys():
    """run_and_report must return all three model results."""
    r = run_and_report(save_receipt=False)
    assert "contact_inequality" in r
    assert "eschatian" in r
    assert "sifta_ledger_reliability" in r
    assert r["truth_label"] == "COOL_WORLDS_TOY_V1"


def test_run_and_report_bias_is_positive():
    r = run_and_report(save_receipt=False)
    assert r["contact_inequality"]["bias_factor_vs_earth"] > 0
