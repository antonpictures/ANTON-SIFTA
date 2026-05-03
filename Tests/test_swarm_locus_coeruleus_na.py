"""
Tests for Event 142 — Locus Coeruleus / Noradrenergic (LC/NA) Arousal Organ.

Bio-math validated tests — every assertion references published neuroscience:
    Sara (2009) NatRevNeurosci, Yu & Dayan (2005) Neuron,
    Aston-Jones & Cohen (2005) AnnRevNeurosci, Yerkes & Dodson (1908).
"""
import json
import math
import pytest
from pathlib import Path

from System.swarm_locus_coeruleus_na import (
    compute_lc_na,
    get_latest_lc_na_row,
    summary_for_prompt,
    _yerkes_dodson,
    _na_from_uncertainty,
    _na_from_uptime,
    _NA_OPTIMAL,
    _NA_EXPLORE_MAX,
    _NA_EXPLORE_MIN,
)


# ── Math: Yerkes-Dodson inverted-U ──────────────────────────────────────────

def test_yerkes_dodson_peak_at_optimal():
    """Inverted-U peaks at NA_OPTIMAL (Aston-Jones & Cohen 2005 Fig 3)."""
    assert _yerkes_dodson(_NA_OPTIMAL) == pytest.approx(1.0, abs=1e-9)


def test_yerkes_dodson_zero_at_extremes():
    """Performance collapses at extreme arousal (too low or too high)."""
    assert _yerkes_dodson(0.0) == pytest.approx(0.0, abs=0.01)
    assert _yerkes_dodson(1.0) == pytest.approx(0.0, abs=0.01)


def test_yerkes_dodson_symmetric():
    """Curve is symmetric around the optimum."""
    delta = 0.1
    left  = _yerkes_dodson(_NA_OPTIMAL - delta)
    right = _yerkes_dodson(_NA_OPTIMAL + delta)
    assert abs(left - right) < 1e-6


def test_yerkes_dodson_bounded():
    for x in [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
        y = _yerkes_dodson(x)
        assert 0.0 <= y <= 1.0


# ── Sub-signal extractors ───────────────────────────────────────────────────

def test_na_from_uncertainty_monotone():
    """Yu & Dayan (2005): unexpected uncertainty drives NA linearly."""
    assert _na_from_uncertainty(0.0) < _na_from_uncertainty(0.5) < _na_from_uncertainty(1.0)


def test_na_from_uptime_fresh_is_high():
    """Sara (2009): LC activity peaks early in wakefulness."""
    fresh  = _na_from_uptime(0.0)
    tired  = _na_from_uptime(12.0)
    fatigued = _na_from_uptime(24.0)
    assert fresh > tired > fatigued


def test_na_from_uptime_bounded():
    for h in [0, 4, 8, 16, 24, 48]:
        v = _na_from_uptime(h)
        assert 0.0 <= v <= 1.0


# ── Main API: compute_lc_na ─────────────────────────────────────────────────

def test_output_schema(tmp_path):
    row = compute_lc_na(write_ledger=False)
    for key in ("na_level", "gain", "exploration_bias", "lr_ceiling",
                "arousal_regime", "yerkes_dodson", "truth_label", "provenance"):
        assert key in row
    assert row["truth_label"] == "LC_NA_AROUSAL"


def test_na_level_bounded(tmp_path):
    for uncertainty in [0.0, 0.3, 0.5, 0.8, 1.0]:
        row = compute_lc_na(uncertainty=uncertainty, write_ledger=False)
        assert 0.0 <= row["na_level"] <= 1.0


def test_gain_bounded(tmp_path):
    for uncertainty in [0.0, 0.5, 1.0]:
        row = compute_lc_na(uncertainty=uncertainty, write_ledger=False)
        # Gain in [NA_GAIN_BASE=0.5, NA_GAIN_SCALE=2.0]
        assert 0.5 <= row["gain"] <= 2.0


def test_exploration_bias_bounded(tmp_path):
    for uncertainty in [0.0, 0.5, 1.0]:
        row = compute_lc_na(uncertainty=uncertainty, write_ledger=False)
        assert _NA_EXPLORE_MIN <= row["exploration_bias"] <= _NA_EXPLORE_MAX


def test_lr_ceiling_bounded(tmp_path):
    for uncertainty in [0.0, 0.5, 1.0]:
        row = compute_lc_na(uncertainty=uncertainty, write_ledger=False)
        assert 0.01 <= row["lr_ceiling"] <= 0.10


def test_optimal_arousal_peak_gain():
    """At NA_OPTIMAL: gain should be maximum (Aston-Jones & Cohen 2005)."""
    row_opt  = compute_lc_na(_na_override=_NA_OPTIMAL, write_ledger=False)
    row_low  = compute_lc_na(_na_override=0.1, write_ledger=False)
    row_high = compute_lc_na(_na_override=0.9, write_ledger=False)
    assert row_opt["gain"] >= row_low["gain"]
    assert row_opt["gain"] >= row_high["gain"]


def test_optimal_lr_peak():
    """Yerkes-Dodson: LR ceiling peaks at moderate arousal."""
    row_opt  = compute_lc_na(_na_override=_NA_OPTIMAL, write_ledger=False)
    row_low  = compute_lc_na(_na_override=0.0, write_ledger=False)
    row_high = compute_lc_na(_na_override=1.0, write_ledger=False)
    assert row_opt["lr_ceiling"] >= row_low["lr_ceiling"]
    assert row_opt["lr_ceiling"] >= row_high["lr_ceiling"]


def test_optimal_exploration_peak():
    """Optimal NA → max exploration bias (not low, not extreme stress)."""
    row_opt  = compute_lc_na(_na_override=_NA_OPTIMAL, write_ledger=False)
    row_zero = compute_lc_na(_na_override=0.0, write_ledger=False)
    row_one  = compute_lc_na(_na_override=1.0, write_ledger=False)
    assert row_opt["exploration_bias"] >= row_zero["exploration_bias"]
    assert row_opt["exploration_bias"] >= row_one["exploration_bias"]


def test_arousal_regime_hypo(tmp_path):
    row = compute_lc_na(_na_override=0.1, write_ledger=False)
    assert row["arousal_regime"] == "HYPO"


def test_arousal_regime_optimal(tmp_path):
    row = compute_lc_na(_na_override=0.5, write_ledger=False)
    assert row["arousal_regime"] == "OPTIMAL"


def test_arousal_regime_hyper(tmp_path):
    row = compute_lc_na(_na_override=0.9, write_ledger=False)
    assert row["arousal_regime"] == "HYPER"


def test_writes_jsonl(tmp_path):
    compute_lc_na(write_ledger=True, root=tmp_path)
    log = tmp_path / "lc_na_log.jsonl"
    assert log.exists()
    row = json.loads(log.read_text().strip().splitlines()[-1])
    assert row["kind"] == "LC_NA_AROUSAL"
    assert row["truth_label"] == "LC_NA_AROUSAL"


def test_multiple_writes_append(tmp_path):
    compute_lc_na(write_ledger=True, root=tmp_path, _na_override=0.3)
    compute_lc_na(write_ledger=True, root=tmp_path, _na_override=0.7)
    log = tmp_path / "lc_na_log.jsonl"
    lines = [l for l in log.read_text().splitlines() if l.strip()]
    assert len(lines) == 2


def test_disable_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_LC_NA_DISABLE", "1")
    row = compute_lc_na(write_ledger=False)
    assert row.get("disabled") is True
    assert row["na_level"] == 0.5   # safe default
    assert row["gain"] == 1.0       # no modulation when disabled


def test_get_latest_no_log(tmp_path):
    assert get_latest_lc_na_row(root=tmp_path) is None


def test_get_latest_returns_row(tmp_path):
    compute_lc_na(write_ledger=True, root=tmp_path, _na_override=0.4)
    row = get_latest_lc_na_row(root=tmp_path)
    assert row is not None
    assert row["kind"] == "LC_NA_AROUSAL"


def test_summary_for_prompt_empty(tmp_path):
    assert summary_for_prompt(root=tmp_path) == ""


def test_summary_for_prompt_contains_na(tmp_path):
    compute_lc_na(write_ledger=True, root=tmp_path, _na_override=0.5)
    s = summary_for_prompt(root=tmp_path)
    assert "NA_level" in s
    assert "regime" in s
    assert "gain" in s
    assert "Sara 2009" in s


# ── Weighted-input integration test ─────────────────────────────────────────

def test_high_uncertainty_raises_na():
    """Yu & Dayan (2005): high unexpected uncertainty → high NA."""
    low_u  = compute_lc_na(uncertainty=0.1, astrocyte_heat_norm=0.1,
                            uptime_hours=4.0, write_ledger=False)
    high_u = compute_lc_na(uncertainty=0.9, astrocyte_heat_norm=0.1,
                            uptime_hours=4.0, write_ledger=False)
    assert high_u["na_level"] > low_u["na_level"]


def test_fresh_wakefulness_contributes_arousal():
    """Sara (2009): early wakefulness → higher basal NA."""
    fresh  = compute_lc_na(uncertainty=0.3, astrocyte_heat_norm=0.3,
                            uptime_hours=0.5, write_ledger=False)
    tired  = compute_lc_na(uncertainty=0.3, astrocyte_heat_norm=0.3,
                            uptime_hours=20.0, write_ledger=False)
    assert fresh["na_level"] > tired["na_level"]


def test_provenance_contains_all_citations(tmp_path):
    row = compute_lc_na(write_ledger=False)
    prov = row["provenance"]
    assert "Sara2009" in prov
    assert "Yu&Dayan2005" in prov
    assert "Aston-Jones" in prov
    assert "Yerkes" in prov
