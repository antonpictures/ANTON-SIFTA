"""
tests/test_stigmero_e45_bifurcation.py
══════════════════════════════════════════════════════════════════════════════
E45 — Bounded Chaos / Wiggle at Bifurcation

ROB 501 topic: Nonlinear bifurcations, bounded noise injection.

Hypothesis (P):
    When the pheromone field (E33) exceeds the collision risk threshold OR
    the field intensity exceeds k·I_∞ (saturation), injecting bounded noise
    ε·tanh(overshoot) allows the system to escape the stuck state.

    The noise is PROVABLY bounded: |ε·tanh(x)| < ε for all x ∈ ℝ.
    Therefore the wiggle response can never grow without bound.

Proof structure:
  1. Stable condition:   R ≤ θ_R and I ≤ k·I_∞ → STABLE, noise = 0
  2. Bifurcation:        R > θ_R OR I > k·I_∞ → BIFURCATING, noise > 0
  3. Boundedness:        noise_amplitude = ε·tanh(overshoot) < ε always
  4. Monotone response:  larger overshoot → larger noise (monotone in tanh)
  5. Zero at equilibrium: overshoot = 0 → noise = 0 (system at rest)
  6. Falsifier:          ε ≤ 0 raises ValueError

§8.6 compliance: pure math, no ledger reads.
"""
from __future__ import annotations

import math

import pytest

from System.stigmerobotics_bifurcation import (
    DEFAULT_COLLISION_THRESHOLD,
    DEFAULT_EPSILON,
    DEFAULT_SATURATION_FACTOR,
    BifurcationState,
    WiggleResponse,
    is_bifurcating,
    wiggle_response,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stable(cr: float = 0.0, fi: float = 50.0, i_inf: float = 200.0) -> WiggleResponse:
    return wiggle_response(cr, fi, i_inf)


def _bifurcating_by_collision() -> WiggleResponse:
    return wiggle_response(
        collision_risk=0.8,  # > DEFAULT_COLLISION_THRESHOLD (0.5)
        field_intensity=50.0,
        i_inf=200.0,
    )


def _bifurcating_by_saturation() -> WiggleResponse:
    return wiggle_response(
        collision_risk=0.0,
        field_intensity=400.0,  # > 1.5 * 200 = 300
        i_inf=200.0,
    )


# ── 1. Stable condition ────────────────────────────────────────────────────────

class TestE45StableCondition:

    def test_e45_below_both_thresholds_is_stable(self) -> None:
        resp = _stable(cr=0.0, fi=50.0, i_inf=200.0)
        assert resp.state == BifurcationState.STABLE

    def test_e45_stable_noise_amplitude_is_zero(self) -> None:
        resp = _stable(cr=0.0, fi=0.0, i_inf=200.0)
        assert math.isclose(resp.noise_amplitude, 0.0, abs_tol=1e-12)

    def test_e45_exactly_at_threshold_is_stable(self) -> None:
        """R == θ_R (not strictly >) → STABLE."""
        resp = wiggle_response(
            collision_risk=DEFAULT_COLLISION_THRESHOLD,
            field_intensity=50.0,
            i_inf=200.0,
        )
        assert resp.state == BifurcationState.STABLE

    def test_e45_exactly_at_saturation_is_stable(self) -> None:
        """I == k·I_∞ (not strictly >) → STABLE."""
        resp = wiggle_response(
            collision_risk=0.0,
            field_intensity=DEFAULT_SATURATION_FACTOR * 200.0,
            i_inf=200.0,
        )
        assert resp.state == BifurcationState.STABLE


# ── 2. Bifurcation triggers ────────────────────────────────────────────────────

class TestE45BifurcationTriggers:

    def test_e45_high_collision_risk_triggers_bifurcation(self) -> None:
        resp = _bifurcating_by_collision()
        assert resp.state == BifurcationState.BIFURCATING

    def test_e45_high_field_intensity_triggers_bifurcation(self) -> None:
        resp = _bifurcating_by_saturation()
        assert resp.state == BifurcationState.BIFURCATING

    def test_e45_both_triggers_simultaneously(self) -> None:
        resp = wiggle_response(0.9, 500.0, 200.0)
        assert resp.state == BifurcationState.BIFURCATING

    def test_e45_is_bifurcating_predicate_true(self) -> None:
        assert is_bifurcating(0.8, 50.0, 200.0)

    def test_e45_is_bifurcating_predicate_false(self) -> None:
        assert not is_bifurcating(0.0, 50.0, 200.0)

    def test_e45_bifurcating_noise_is_positive(self) -> None:
        resp = _bifurcating_by_collision()
        assert resp.noise_amplitude > 0.0


# ── 3. Boundedness proof ───────────────────────────────────────────────────────

class TestE45Boundedness:

    def test_e45_noise_bounded_at_zero_overshoot(self) -> None:
        resp = _stable()
        assert resp.noise_is_bounded
        assert resp.noise_amplitude < DEFAULT_EPSILON

    def test_e45_noise_bounded_at_moderate_overshoot(self) -> None:
        resp = _bifurcating_by_collision()
        assert resp.noise_is_bounded
        assert resp.noise_amplitude < DEFAULT_EPSILON

    def test_e45_noise_bounded_at_extreme_overshoot(self) -> None:
        """
        Even with collision_risk = 1e6, noise stays ≤ ε.
        Note: float64 tanh saturates to exactly 1.0 for large x, so
        ε·tanh(x) can equal ε in the extreme limit — the bound is ≤ ε.
        The key invariant is: noise can NEVER EXCEED ε (it is bounded above).
        """
        resp = wiggle_response(1_000_000.0, 1_000_000.0, 1.0)
        assert resp.noise_is_bounded  # uses ≤ ε + 1e-12 tolerance
        assert resp.noise_amplitude <= DEFAULT_EPSILON + 1e-12

    def test_e45_noise_never_exceeds_epsilon(self) -> None:
        """
        tanh(x) ≤ 1 for all x → noise ≤ ε. For small/moderate overshoot,
        tanh(x) < 1 strictly; for very large overshoot, float64 saturates.
        The bound is always ≤ ε (noise is bounded, never diverges).
        """
        for cr in (0.0, 0.3, 0.5, 0.8, 1.0, 10.0):
            resp = wiggle_response(cr, 100.0, 100.0)
            assert resp.noise_amplitude <= DEFAULT_EPSILON + 1e-12, (
                f"cr={cr}: noise={resp.noise_amplitude} > ε={DEFAULT_EPSILON}"
            )

    def test_e45_noise_bounded_for_custom_epsilon(self) -> None:
        for epsilon in (0.01, 0.1, 0.5, 1.0):
            resp = wiggle_response(0.6, 200.0, 100.0, epsilon=epsilon)
            # moderate overshoot → tanh < 1 → noise < ε strictly
            assert resp.noise_amplitude < epsilon

    def test_e45_tanh_bound_is_mathematically_correct(self) -> None:
        """ε·tanh(x) ≤ ε for all x (equality only when tanh saturates)."""
        epsilon = DEFAULT_EPSILON
        for overshoot in (0.0, 0.1, 1.0, 10.0, 100.0):
            noise = epsilon * math.tanh(overshoot)
            assert noise <= epsilon + 1e-12


# ── 4. Monotone response ──────────────────────────────────────────────────────

class TestE45MonotoneResponse:

    def test_e45_noise_monotone_in_collision_risk(self) -> None:
        """Higher collision risk → larger noise amplitude."""
        risks = [0.6, 0.7, 0.8, 0.9, 1.0]
        noises = [wiggle_response(cr, 50.0, 200.0).noise_amplitude for cr in risks]
        for i in range(len(noises) - 1):
            assert noises[i] <= noises[i + 1], (
                f"noise not monotone at cr={risks[i]}: {noises[i]} > {noises[i+1]}"
            )

    def test_e45_noise_monotone_in_field_intensity(self) -> None:
        """Higher field intensity (beyond saturation) → larger noise."""
        intensities = [310.0, 400.0, 600.0, 1000.0]  # all > 1.5 * 200 = 300
        noises = [wiggle_response(0.0, fi, 200.0).noise_amplitude for fi in intensities]
        for i in range(len(noises) - 1):
            assert noises[i] <= noises[i + 1]

    def test_e45_zero_overshoot_gives_zero_noise(self) -> None:
        resp = wiggle_response(0.0, 0.0, 200.0)
        assert math.isclose(resp.noise_amplitude, 0.0, abs_tol=1e-12)


# ── 5. Falsifier ──────────────────────────────────────────────────────────────

class TestE45Falsifier:

    def test_e45_zero_epsilon_raises(self) -> None:
        with pytest.raises(ValueError, match="epsilon"):
            wiggle_response(0.5, 100.0, 200.0, epsilon=0.0)

    def test_e45_negative_epsilon_raises(self) -> None:
        with pytest.raises(ValueError, match="epsilon"):
            wiggle_response(0.5, 100.0, 200.0, epsilon=-0.1)

    def test_e45_zero_saturation_factor_raises(self) -> None:
        with pytest.raises(ValueError, match="saturation_factor"):
            wiggle_response(0.5, 100.0, 200.0, saturation_factor=0.0)

    def test_e45_zero_i_inf_no_saturation_trigger(self) -> None:
        """If I_∞ = 0 (no E39 data), saturation trigger is skipped safely."""
        resp = wiggle_response(0.0, 100.0, i_inf=0.0)
        assert resp.state == BifurcationState.STABLE


# ── 6. Proof of Property ──────────────────────────────────────────────────────

class TestE45ProofOfProperty:

    def test_proof_has_required_keys(self) -> None:
        resp = _bifurcating_by_collision()
        pop = resp.proof_of_property
        assert {
            "E45", "theorem", "state", "collision_risk", "noise_amplitude",
            "noise_is_bounded", "epsilon", "falsifier",
            "prigogine_mapping", "truth_label",
        } <= pop.keys()

    def test_proof_truth_label_operational_when_bounded(self) -> None:
        resp = _bifurcating_by_collision()
        assert resp.proof_of_property["truth_label"] == "OPERATIONAL"

    def test_proof_theorem_mentions_tanh(self) -> None:
        resp = _stable()
        assert "tanh" in resp.proof_of_property["theorem"]

    def test_proof_prigogine_mapping_present(self) -> None:
        resp = _bifurcating_by_saturation()
        assert "Prigogine" in resp.proof_of_property["prigogine_mapping"] or \
               "far-from-equilibrium" in resp.proof_of_property["prigogine_mapping"]
