"""Tests for §21 Vector #2 — temporal phase transitions.

Architect picked this vector for the next surgery:
   'add memory half-life decay and watch for sharp reorganization when
    decay crosses threshold.'

Mechanism: scan MemoryDrivenField.decay across regimes; for each decay,
measure Scheffer-2009 early-warning signals (variance, lag-1 autocorr,
skewness) on the field order_parameter time-series.

These tests guard the mechanism and the receipt format. The HEADLINE
finding (whether an interior critical point exists in the swept range)
is HYPOTHESIS-class and depends on parameters; the tests assert only
the loop invariants.
"""
import json
import pytest

np = pytest.importorskip("numpy")

from System.swarm_higgs_stigmergy_field import (
    LEDGER_NAME,
    TRUTH_BOUNDARY,
    TRUTH_LABEL_TEMPORAL_PHASE,
    _series_variance,
    _series_lag1_autocorr,
    _series_skewness,
    run_temporal_phase_transition_sweep,
)


# ── unit tests on the time-series stats ───────────────────────────────────

def test_variance_zero_for_constant_series():
    assert _series_variance([1.0, 1.0, 1.0, 1.0]) == pytest.approx(0.0)


def test_variance_matches_numpy():
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert _series_variance(xs) == pytest.approx(float(np.var(xs, ddof=1)))


def test_lag1_autocorr_perfect_for_monotonic_walk():
    xs = list(range(50))
    # Monotonic increasing series — strongly positive lag-1 autocorr.
    # Finite-length unbiased estimator caps below 1.0 because the
    # numerator misses one term; 0.9 is a safely-clearable threshold
    # for a 50-step monotonic walk.
    assert _series_lag1_autocorr([float(x) for x in xs]) > 0.9


def test_lag1_autocorr_handles_short_series():
    assert _series_lag1_autocorr([1.0]) == 0.0
    assert _series_lag1_autocorr([1.0, 2.0]) == 0.0


def test_skewness_zero_for_symmetric_series():
    xs = [-2.0, -1.0, 0.0, 1.0, 2.0]
    assert abs(_series_skewness(xs)) < 0.1


def test_skewness_handles_degenerate_series():
    assert _series_skewness([5.0, 5.0]) == 0.0


# ── sweep integration tests ───────────────────────────────────────────────

def test_temporal_sweep_returns_regime_per_decay_level(tmp_path):
    decay_levels = (0.01, 0.05, 0.2)
    r = run_temporal_phase_transition_sweep(
        decay_levels=decay_levels,
        n_swimmers=15, swimmer_steps=200, burn_in=50,
        state_root=tmp_path, write=False,
    )
    assert r["truth_label"] == TRUTH_LABEL_TEMPORAL_PHASE
    assert r["truth_class"] == "HYPOTHESIS"
    assert len(r["regimes"]) == len(decay_levels)
    for regime, expected_decay in zip(r["regimes"], decay_levels):
        assert regime["decay"] == pytest.approx(expected_decay)
        assert "variance" in regime
        assert "lag1_autocorr" in regime
        assert "skewness" in regime
        assert "memory_halflife_steps" in regime


def test_temporal_sweep_writes_truth_labeled_receipt(tmp_path):
    r = run_temporal_phase_transition_sweep(
        decay_levels=(0.01, 0.1),
        n_swimmers=15, swimmer_steps=200, burn_in=50,
        state_root=tmp_path, write=True,
    )
    rows = [
        json.loads(line)
        for line in (tmp_path / LEDGER_NAME).read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "PERSISTENCE_INERTIA_FIELD_TEMPORAL_PHASE"
    assert row["truth_label"] == TRUTH_LABEL_TEMPORAL_PHASE
    assert row["truth_boundary"] == TRUTH_BOUNDARY


def test_temporal_sweep_reports_interior_peak_honestly(tmp_path):
    """If the variance maximum sits at the FIRST or LAST decay level,
    is_interior_variance_peak must be False. Honest reporting per §7.12."""
    r = run_temporal_phase_transition_sweep(
        decay_levels=(0.001, 0.5),  # only two — max is necessarily boundary
        n_swimmers=10, swimmer_steps=120, burn_in=30,
        state_root=tmp_path, write=False,
    )
    assert r["is_interior_variance_peak"] is False


def test_higher_decay_lowers_field_order_parameter(tmp_path):
    """Sanity check: faster decay should monotonically lower the mean
    field order parameter because deposits wash out faster."""
    r = run_temporal_phase_transition_sweep(
        decay_levels=(0.01, 0.1, 0.4),
        n_swimmers=20, swimmer_steps=300, burn_in=100,
        state_root=tmp_path, write=False,
    )
    means = [reg["order_ts_mean"] for reg in r["regimes"]]
    assert means[0] > means[2]
