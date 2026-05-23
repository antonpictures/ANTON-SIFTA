"""
Tests for Event 145 — Metacognitive State Monitor.

Every assertion maps to published neuroscience cited in swarm_metacognitive_monitor.py:
    Fleming & Dolan (2012) — meta-d', confidence calibration, metacog_efficiency
    Nelson (1990) — monitoring vs control metacognition
    Friston (2005) — KL epistemic surprise
    Yeung & Summerfield (2012) — error monitoring
    Friston et al. (2021) — second-order uncertainty
"""
import json
import math
import pytest
from pathlib import Path

from System.swarm_metacognitive_monitor import (
    compute_metacognitive_state,
    get_latest_metacog_row,
    summary_for_prompt,
    _kl_gaussian,
    _safe_var,
    _safe_mean,
    _OVERCONFIDENT_THRESHOLD,
    _UNDERCONFIDENT_THRESHOLD,
)


# ── Pure math: KL divergence ─────────────────────────────────────────────────

def test_kl_gaussian_identical_distributions():
    """KL(P || P) = 0 for identical Gaussians."""
    assert _kl_gaussian(0.5, 0.1, 0.5, 0.1) == pytest.approx(0.0, abs=1e-6)


def test_kl_gaussian_non_negative():
    """KL divergence is always ≥ 0 (Gibbs inequality)."""
    for mu1, var1, mu2, var2 in [
        (0.0, 0.1, 0.5, 0.2),
        (1.0, 0.5, 0.0, 0.1),
        (0.3, 0.05, 0.3, 0.3),
    ]:
        assert _kl_gaussian(mu1, var1, mu2, var2) >= 0.0


def test_kl_gaussian_increases_with_mean_shift():
    """KL should grow as means diverge (Friston 2005 — epistemic surprise increases)."""
    kl_small = _kl_gaussian(0.5, 0.1, 0.5, 0.1)
    kl_large = _kl_gaussian(0.9, 0.1, 0.5, 0.1)
    assert kl_large > kl_small


def test_safe_var_single_value():
    assert _safe_var([1.0]) == 0.0


def test_safe_var_two_values():
    assert _safe_var([0.0, 1.0]) == pytest.approx(0.5, abs=1e-9)


# ── Schema validation ─────────────────────────────────────────────────────────

def test_output_schema():
    row = compute_metacognitive_state(write_ledger=False, _pe_series=[0.3, 0.4, 0.2, 0.5, 0.3, 0.4])
    for key in ("meta_uncertainty", "confidence_bias", "epistemic_surprise",
                "monitoring_score", "metacog_efficiency", "metacog_regime",
                "truth_label", "provenance"):
        assert key in row
    assert row["truth_label"] == "METACOGNITIVE_STATE"


def test_provenance_all_citations():
    row = compute_metacognitive_state(write_ledger=False)
    p = row["provenance"]
    assert "Fleming" in p and "Dolan" in p
    assert "Nelson" in p
    assert "Friston" in p
    assert "Yeung" in p


# ── meta_uncertainty (second-order, Friston 2021) ────────────────────────────

def test_meta_uncertainty_bounded():
    pe = [0.1, 0.5, 0.2, 0.8, 0.1, 0.9, 0.2, 0.3]
    row = compute_metacognitive_state(write_ledger=False, _pe_series=pe)
    assert 0.0 <= row["meta_uncertainty"] <= 1.0


def test_meta_uncertainty_zero_when_stable():
    """Constant PE → zero meta-uncertainty (no variance of variance)."""
    pe = [0.3] * 20
    row = compute_metacognitive_state(write_ledger=False, _pe_series=pe)
    assert row["meta_uncertainty"] == pytest.approx(0.0, abs=1e-6)


def test_meta_uncertainty_rises_with_volatile_pe():
    """Highly variable PE → higher meta_uncertainty than stable PE."""
    stable   = [0.3] * 12
    volatile = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    row_s = compute_metacognitive_state(write_ledger=False, _pe_series=stable)
    row_v = compute_metacognitive_state(write_ledger=False, _pe_series=volatile)
    assert row_v["meta_uncertainty"] >= row_s["meta_uncertainty"]


def test_meta_uncertainty_neutral_when_few_samples():
    """< 4 samples → neutral prior (0.5)."""
    row = compute_metacognitive_state(write_ledger=False, _pe_series=[0.3, 0.4])
    assert row["meta_uncertainty"] == 0.5


# ── epistemic_surprise (KL, Friston 2005) ────────────────────────────────────

def test_epistemic_surprise_non_negative():
    pe = [0.2, 0.3, 0.2, 0.3, 0.7, 0.8, 0.7, 0.8]
    row = compute_metacognitive_state(write_ledger=False, _pe_series=pe)
    assert row["epistemic_surprise"] >= 0.0


def test_epistemic_surprise_low_when_pe_stable():
    """Same distribution in early and late halves → KL ≈ 0."""
    pe = [0.3, 0.4, 0.3, 0.4, 0.3, 0.4, 0.3, 0.4]
    row = compute_metacognitive_state(write_ledger=False, _pe_series=pe)
    assert row["epistemic_surprise"] < 0.2


def test_epistemic_surprise_high_when_pe_shifts():
    """PE shifts dramatically → high epistemic_surprise (Friston 2005)."""
    pe = [0.1, 0.1, 0.1, 0.1, 0.9, 0.9, 0.9, 0.9]
    row = compute_metacognitive_state(write_ledger=False, _pe_series=pe)
    assert row["epistemic_surprise"] > 0.5


# ── confidence_bias / calibration (Fleming & Dolan 2012) ─────────────────────

def test_confidence_bias_overconfident():
    """High confidence, low accuracy → overconfident."""
    confs    = [0.9, 0.8, 0.95, 0.85, 0.9]
    corrects = [0.2, 0.3, 0.1,  0.2,  0.2]
    row = compute_metacognitive_state(
        write_ledger=False, _confidence=confs, _correctness=corrects,
        _pe_series=[0.3]*6
    )
    assert row["confidence_bias"] > _OVERCONFIDENT_THRESHOLD
    assert row["metacog_regime"] == "OVERCONFIDENT"


def test_confidence_bias_underconfident():
    """Low confidence, high accuracy → underconfident."""
    confs    = [0.1, 0.2, 0.15, 0.1, 0.2]
    corrects = [0.9, 0.8, 0.85, 0.9, 0.8]
    row = compute_metacognitive_state(
        write_ledger=False, _confidence=confs, _correctness=corrects,
        _pe_series=[0.3]*6
    )
    assert row["confidence_bias"] < _UNDERCONFIDENT_THRESHOLD
    assert row["metacog_regime"] == "UNDERCONFIDENT"


def test_confidence_bias_calibrated():
    """Confidence matches accuracy → CALIBRATED."""
    vals = [0.6, 0.7, 0.5, 0.8, 0.6]
    row = compute_metacognitive_state(
        write_ledger=False, _confidence=vals, _correctness=vals,
        _pe_series=[0.3]*6
    )
    assert abs(row["confidence_bias"]) <= _OVERCONFIDENT_THRESHOLD
    assert row["metacog_regime"] == "CALIBRATED"


# ── metacog_efficiency (Fleming & Dolan 2012 meta-d' proxy) ──────────────────

def test_metacog_efficiency_high_when_confidence_correlates():
    """When confidence perfectly tracks correctness → max efficiency."""
    vals = [0.2, 0.4, 0.6, 0.8, 1.0]
    row = compute_metacognitive_state(
        write_ledger=False, _confidence=vals, _correctness=vals,
        _pe_series=[0.3]*6
    )
    assert row["metacog_efficiency"] > 0.9


def test_metacog_efficiency_bounded():
    confs    = [0.9, 0.1, 0.7, 0.3, 0.6]
    corrects = [0.1, 0.9, 0.3, 0.7, 0.4]
    row = compute_metacognitive_state(
        write_ledger=False, _confidence=confs, _correctness=corrects,
        _pe_series=[0.3]*6
    )
    assert 0.0 <= row["metacog_efficiency"] <= 1.0


# ── monitoring_score (Nelson 1990) ───────────────────────────────────────────

def test_monitoring_score_all_detected():
    row = compute_metacognitive_state(
        write_ledger=False, _error_detections=[True] * 10,
        _pe_series=[0.3]*6
    )
    assert row["monitoring_score"] == pytest.approx(1.0)


def test_monitoring_score_none_detected():
    row = compute_metacognitive_state(
        write_ledger=False, _error_detections=[False] * 10,
        _pe_series=[0.3]*6
    )
    assert row["monitoring_score"] == pytest.approx(0.0)


def test_monitoring_score_neutral_when_no_data():
    """No monitoring data → 0.5 prior (Nelson 1990 §5.3)."""
    row = compute_metacognitive_state(
        write_ledger=False, _error_detections=[],
        _pe_series=[0.3]*6
    )
    assert row["monitoring_score"] == pytest.approx(0.5)


def test_monitoring_score_bounded():
    for n_detected in [0, 3, 7, 10]:
        detections = [True] * n_detected + [False] * (10 - n_detected)
        row = compute_metacognitive_state(
            write_ledger=False, _error_detections=detections,
            _pe_series=[0.3]*6
        )
        assert 0.0 <= row["monitoring_score"] <= 1.0


# ── Ledger persistence ────────────────────────────────────────────────────────

def test_writes_jsonl(tmp_path):
    compute_metacognitive_state(root=tmp_path, write_ledger=True,
                                _pe_series=[0.2, 0.4, 0.3, 0.5, 0.2, 0.4])
    log = tmp_path / "metacognitive_state.jsonl"
    assert log.exists()
    row = json.loads(log.read_text().strip().splitlines()[-1])
    assert row["kind"] == "METACOGNITIVE_STATE"
    assert row["truth_label"] == "METACOGNITIVE_STATE"


def test_append_only(tmp_path):
    pe = [0.3, 0.4, 0.3, 0.5, 0.3, 0.4]
    compute_metacognitive_state(root=tmp_path, write_ledger=True, _pe_series=pe)
    compute_metacognitive_state(root=tmp_path, write_ledger=True, _pe_series=pe)
    lines = [l for l in (tmp_path / "metacognitive_state.jsonl").read_text().splitlines() if l.strip()]
    assert len(lines) == 2


def test_disable_env(monkeypatch):
    monkeypatch.setenv("SIFTA_METACOG_DISABLE", "1")
    row = compute_metacognitive_state(write_ledger=False)
    assert row.get("disabled") is True
    assert row["metacog_regime"] == "CALIBRATED"
    assert row["monitoring_score"] == 0.5


def test_get_latest_none_when_no_log(tmp_path):
    assert get_latest_metacog_row(root=tmp_path) is None


def test_get_latest_returns_row(tmp_path):
    compute_metacognitive_state(root=tmp_path, write_ledger=True,
                                _pe_series=[0.3]*6)
    row = get_latest_metacog_row(root=tmp_path)
    assert row is not None
    assert row["kind"] == "METACOGNITIVE_STATE"


def test_summary_empty_when_no_log(tmp_path):
    assert summary_for_prompt(root=tmp_path) == ""


def test_summary_contains_key_fields(tmp_path):
    compute_metacognitive_state(root=tmp_path, write_ledger=True,
                                _pe_series=[0.3]*6)
    s = summary_for_prompt(root=tmp_path)
    assert "regime" in s
    assert "Fleming" in s
    assert "monitoring" in s


# ============================================================
# PART 3: Biological Steering (§10.14.31)
# DAM Stage 2, TME Escape, NA>0.8, Resilience, Owner Alignment
# ============================================================

def test_metacog_biological_steering_dam_stage2_underconfident():
    """DAM Stage 2 forces UNDERCONFIDENT regime and raises threshold."""
    # Normally 0 bias is CALIBRATED
    receipt_normal = compute_metacognitive_state(
        _pe_series=[0.1, 0.1, 0.1, 0.1],
        _confidence=[0.5, 0.5, 0.5],
        _correctness=[0.5, 0.5, 0.5],
        write_ledger=False
    )
    
    receipt_inflamed = compute_metacognitive_state(
        dam_stage=2,
        _pe_series=[0.1, 0.1, 0.1, 0.1],
        _confidence=[0.5, 0.5, 0.5],
        _correctness=[0.5, 0.5, 0.5],
        write_ledger=False
    )
    
    assert receipt_normal['metacog_regime'] == 'CALIBRATED'
    assert receipt_inflamed['metacog_regime'] == 'UNDERCONFIDENT', "DAM Stage 2 must force UNDERCONFIDENT"
    
    bs_norm = receipt_normal['biological_steering']
    bs_inf = receipt_inflamed['biological_steering']
    assert bs_inf['evidence_threshold'] > bs_norm['evidence_threshold']
    assert bs_inf['quick_commit'] is False

def test_metacog_biological_steering_tme_escape_overconfident():
    """TME ESCAPE forces OVERCONFIDENT regime and lowers threshold."""
    receipt = compute_metacognitive_state(
        tme_phase='ESCAPE',
        _pe_series=[0.1, 0.1, 0.1, 0.1],
        _confidence=[0.5, 0.5],
        _correctness=[0.5, 0.5],
        write_ledger=False
    )
    
    assert receipt['metacog_regime'] == 'OVERCONFIDENT'
    assert receipt['biological_steering']['evidence_threshold'] < 0.5
    assert receipt['biological_steering']['deliberation_window'] < 10

def test_metacog_biological_steering_hyperarousal():
    """NA > 0.8 increases distractibility and false positive rate."""
    receipt = compute_metacognitive_state(
        na_level=0.85,
        _pe_series=[0.1, 0.1, 0.1, 0.1],
        _confidence=[0.5, 0.5],
        _correctness=[0.5, 0.5],
        write_ledger=False
    )
    bs = receipt['biological_steering']
    assert bs['distractibility'] > 0.1
    assert bs['attention_scope'] > 1.0
    assert bs['false_positive_rate'] > 0.05

def test_metacog_biological_steering_resilience_floor():
    """High resilience floor increases conservatism."""
    receipt = compute_metacognitive_state(
        resilience_floor=0.10,
        _pe_series=[0.1, 0.1, 0.1, 0.1],
        _confidence=[0.5, 0.5],
        _correctness=[0.5, 0.5],
        write_ledger=False
    )
    bs = receipt['biological_steering']
    assert bs['conservatism'] > 1.0

def test_metacog_biological_steering_owner_aligned():
    """Low frustration + high alignment boosts owner_signal_confidence."""
    receipt = compute_metacognitive_state(
        owner_frustration=0.1,
        goal_alignment=0.9,
        _pe_series=[0.1, 0.1, 0.1, 0.1],
        _confidence=[0.5, 0.5],
        _correctness=[0.5, 0.5],
        write_ledger=False
    )
    bs = receipt['biological_steering']
    assert bs['owner_signal_confidence'] > 0.5
    assert bs['evidence_threshold'] > 0.5
