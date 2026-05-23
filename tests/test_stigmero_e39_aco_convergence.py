"""
tests/test_stigmero_e39_aco_convergence.py
════════════════════════════════════════════════════════════════════════════
E39 — Discrete pheromone convergence (STIGMEROBOTICS / ROB 501 tournament)

ROB 501 topic: Discrete ACO convergence, geometric series, stability.

Hypothesis (P):
    The SIFTA pheromone field (E33) with positive τ and per-step deposits s
    converges to a finite steady-state I_∞ = s / (exp(Δt/τ) - 1) as the
    number of deposits n → ∞.

Proof structure:
  1. Retention bound:  ρ = exp(-Δt/τ) ∈ (0,1) because τ > 0 (E33 invariant)
                       → geometric series converges absolutely.
  2. Steady state:     I_∞ = s·ρ/(1-ρ) = s/(exp(Δt/τ)-1) — exact formula.
  3. Convergence rate: |I_n - I_∞| = s·ρ^(n+1)/(1-ρ) → 0 monotonically.
  4. Multi-channel:    Global field = Σ_c I_c_∞ — channels are independent.
  5. Falsifier:        τ ≤ 0 → ρ ≥ 1 → series diverges (ValueError).
                       E33 τ>0 invariant blocks this at deposit time.
  6. E33 integration:  ChannelSpecs built from DEFAULT_TAU_S + DEFAULT_STRENGTH;
                       every E33 kind converges under unit timestep.

proof_of_property = {
    "E39": "Discrete pheromone field converges to finite steady state",
    "theorem": "I_inf = s / (exp(dt/tau) - 1)",
    "convergence_condition": "rho = exp(-dt/tau) in (0,1)",
    "falsifier": "tau <= 0 → ValueError (blocked by E33)",
    "truth_label": "OPERATIONAL",
}

§8.6 compliance: sanitized fixture + E33 tau table only.
                 Never reads live .sifta_state/.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from System.stigmerobotics_aco_convergence import (
    ACOConvergenceReport,
    ChannelSpec,
    aco_convergence_report,
    channels_from_e33_tables,
    convergence_error,
    convergence_steps_to_epsilon,
    intensity_after_n_deposits,
    retention_factor,
    steady_state_intensity,
)
from System.stigmerobotics_pheromone_field import DEFAULT_STRENGTH, DEFAULT_TAU_S

FIXTURES = Path(__file__).parent / "fixtures"


# ── Fixture loader ───────────────────────────────────────────────────────────

def load_fixture_channels() -> list[dict]:
    path = FIXTURES / "stigmero_e39_deposits.jsonl"
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


# ── 1. Retention factor ρ ─────────────────────────────────────────────────────

class TestE39RetentionFactor:

    def test_e39_rho_in_open_interval_zero_one(self) -> None:
        """ρ = exp(-dt/τ) is strictly in (0, 1) for all τ > 0, dt > 0."""
        for tau in (60.0, 900.0, 1800.0, 3600.0, 7200.0):
            rho = retention_factor(tau_s=tau, dt_s=1.0)
            assert 0.0 < rho < 1.0, f"rho={rho} for tau={tau}"

    def test_e39_larger_tau_gives_higher_rho(self) -> None:
        """Higher τ → slower evaporation → higher per-step retention."""
        rho_small = retention_factor(tau_s=60.0, dt_s=1.0)
        rho_large = retention_factor(tau_s=3600.0, dt_s=1.0)
        assert rho_small < rho_large

    def test_e39_rho_formula_is_correct(self) -> None:
        tau, dt = 1800.0, 1.0
        expected = math.exp(-dt / tau)
        assert math.isclose(retention_factor(tau, dt), expected, rel_tol=1e-12)

    def test_e39_zero_tau_raises(self) -> None:
        """τ ≤ 0 is forbidden (would make ρ ≥ 1 → divergence)."""
        with pytest.raises(ValueError):
            retention_factor(tau_s=0.0, dt_s=1.0)

    def test_e39_negative_tau_raises(self) -> None:
        with pytest.raises(ValueError):
            retention_factor(tau_s=-1.0, dt_s=1.0)

    def test_e39_zero_dt_raises(self) -> None:
        with pytest.raises(ValueError):
            retention_factor(tau_s=1800.0, dt_s=0.0)


# ── 2. Steady state I_∞ ──────────────────────────────────────────────────────

class TestE39SteadyState:

    def test_e39_steady_state_is_finite(self) -> None:
        """I_∞ = s·ρ/(1-ρ) is finite for all τ > 0."""
        i_inf = steady_state_intensity(strength=1.0, tau_s=1800.0, dt_s=1.0)
        assert math.isfinite(i_inf)
        assert i_inf > 0.0

    def test_e39_steady_state_formula(self) -> None:
        """Verify I_∞ = s / (exp(dt/tau) - 1)."""
        s, tau, dt = 0.9, 3600.0, 1.0
        expected = s / (math.exp(dt / tau) - 1)
        result = steady_state_intensity(strength=s, tau_s=tau, dt_s=dt)
        assert math.isclose(result, expected, rel_tol=1e-10)

    def test_e39_larger_tau_gives_higher_i_inf(self) -> None:
        """
        Slower evaporation → higher steady-state accumulation.
        I_∞ ∝ τ for small dt/τ (first-order Taylor: exp(dt/τ)-1 ≈ dt/τ).
        """
        i_small = steady_state_intensity(1.0, 60.0, 1.0)
        i_large = steady_state_intensity(1.0, 3600.0, 1.0)
        assert i_small < i_large

    def test_e39_higher_strength_gives_proportionally_higher_i_inf(self) -> None:
        """I_∞ is linear in s (the geometric ratio doesn't depend on s)."""
        i1 = steady_state_intensity(1.0, 1800.0, 1.0)
        i2 = steady_state_intensity(2.0, 1800.0, 1.0)
        assert math.isclose(i2, 2 * i1, rel_tol=1e-12)

    def test_e39_scar_receipt_steady_state(self) -> None:
        """
        SCAR_RECEIPT: strength=1.0, tau=7200s, dt=1s.
        I_∞ = 1.0 / (exp(1/7200) - 1) ≈ 7199.5
        """
        i_inf = steady_state_intensity(1.0, 7200.0, 1.0)
        expected = 1.0 / (math.exp(1.0 / 7200.0) - 1)
        assert math.isclose(i_inf, expected, rel_tol=1e-10)
        assert i_inf > 7000, f"I_inf={i_inf} unexpectedly low"


# ── 3. Intensity after n deposits ──────────────────────────────────────────────

class TestE39IntensityAtN:

    def test_e39_zero_deposits_gives_zero(self) -> None:
        assert intensity_after_n_deposits(1.0, 1800.0, 1.0, 0) == 0.0

    def test_e39_one_deposit_gives_rho_times_strength(self) -> None:
        """After 1 deposit: I_1 = s·ρ (the deposit has aged by one step)."""
        s, tau, dt = 0.9, 1800.0, 1.0
        rho = math.exp(-dt / tau)
        expected = s * rho
        result = intensity_after_n_deposits(s, tau, dt, 1)
        assert math.isclose(result, expected, rel_tol=1e-12)

    def test_e39_monotone_increasing(self) -> None:
        """I_n is monotone non-decreasing in n (more deposits → more field)."""
        s, tau, dt = 0.9, 1800.0, 1.0
        intensities = [intensity_after_n_deposits(s, tau, dt, n) for n in range(20)]
        for i in range(len(intensities) - 1):
            assert intensities[i] <= intensities[i + 1]

    def test_e39_converges_to_i_inf(self) -> None:
        """I_n → I_∞ as n grows large."""
        s, tau, dt = 0.9, 1800.0, 1.0
        i_inf = steady_state_intensity(s, tau, dt)
        i_large = intensity_after_n_deposits(s, tau, dt, 100_000)
        assert math.isclose(i_large, i_inf, rel_tol=1e-6), (
            f"I_100000={i_large} not close to I_inf={i_inf}"
        )


# ── 4. Convergence rate ────────────────────────────────────────────────────────

class TestE39ConvergenceRate:

    def test_e39_error_decreases_monotonically(self) -> None:
        """The convergence error |I_n - I_∞| is strictly monotone decreasing."""
        s, tau, dt = 0.9, 1800.0, 1.0
        errors = [convergence_error(s, tau, dt, n) for n in range(50)]
        for i in range(len(errors) - 1):
            assert errors[i] > errors[i + 1], f"error not decreasing at n={i}"

    def test_e39_error_formula_matches_empirical(self) -> None:
        """
        |I_n - I_∞| must match the formula s·ρ^(n+1)/(1-ρ).
        """
        s, tau, dt, n = 0.9, 1800.0, 1.0, 100
        formula_error = convergence_error(s, tau, dt, n)
        empirical_error = abs(
            intensity_after_n_deposits(s, tau, dt, n) - steady_state_intensity(s, tau, dt)
        )
        assert math.isclose(formula_error, empirical_error, rel_tol=1e-8)

    def test_e39_steps_to_epsilon_matches_formula(self) -> None:
        """n_eps is the smallest n such that |I_n - I_∞| ≤ ε."""
        s, tau, dt = 0.9, 1800.0, 1.0
        epsilon = 1e-3
        n_eps = convergence_steps_to_epsilon(s, tau, dt, epsilon)
        assert convergence_error(s, tau, dt, n_eps) <= epsilon
        if n_eps > 0:
            assert convergence_error(s, tau, dt, n_eps - 1) > epsilon

    def test_e39_steps_to_epsilon_finite(self) -> None:
        """n_eps must be finite for all τ > 0."""
        for tau in (60.0, 1800.0, 7200.0):
            n_eps = convergence_steps_to_epsilon(1.0, tau, 1.0, 1e-3)
            assert isinstance(n_eps, int)
            assert n_eps >= 0
            assert n_eps < 1_000_000  # must not be effectively infinite


# ── 5. Multi-channel convergence ──────────────────────────────────────────────

class TestE39MultiChannel:

    def test_e39_all_e33_kinds_converge(self) -> None:
        """
        Every kind in DEFAULT_TAU_S has τ > 0 (E33 invariant) →
        every channel converges under unit timestep.
        """
        report = aco_convergence_report(DEFAULT_TAU_S, DEFAULT_STRENGTH, dt_s=1.0)
        assert report.all_converge, f"Divergent: {report.divergent_channels}"

    def test_e39_global_i_inf_is_finite_and_positive(self) -> None:
        report = aco_convergence_report(DEFAULT_TAU_S, DEFAULT_STRENGTH, dt_s=1.0)
        assert math.isfinite(report.global_i_inf)
        assert report.global_i_inf > 0.0

    def test_e39_global_i_inf_equals_sum_of_channel_i_inf(self) -> None:
        """I_global_∞ = Σ_c I_c_∞ — channels are independent."""
        channels = channels_from_e33_tables(DEFAULT_TAU_S, DEFAULT_STRENGTH, dt_s=1.0)
        report = ACOConvergenceReport(channels=channels)
        expected_sum = sum(c.i_inf for c in channels)
        assert math.isclose(report.global_i_inf, expected_sum, rel_tol=1e-12)

    def test_e39_scar_receipt_channel_has_highest_i_inf(self) -> None:
        """
        SCAR_RECEIPT has the highest tau (7200s) and highest strength (1.0) →
        it should dominate the global steady-state field.
        """
        channels = {
            c.name: c for c in channels_from_e33_tables(DEFAULT_TAU_S, DEFAULT_STRENGTH)
        }
        assert "SCAR_RECEIPT" in channels
        scar_i_inf = channels["SCAR_RECEIPT"].i_inf
        other_max = max(c.i_inf for name, c in channels.items() if name != "SCAR_RECEIPT")
        assert scar_i_inf > other_max

    def test_e39_fixture_channels_all_converge(self) -> None:
        """Sanitized E39 fixture channels converge under the formula."""
        for spec_dict in load_fixture_channels():
            cs = ChannelSpec(
                name=spec_dict["kind"],
                strength=spec_dict["strength"],
                tau_s=spec_dict["tau_s"],
                dt_s=spec_dict.get("dt_s", 1.0),
            )
            assert cs.converges(), f"Channel {cs.name} does not converge"
            assert math.isfinite(cs.i_inf)


# ── 6. Falsifier — divergent case ────────────────────────────────────────────

class TestE39Falsifier:

    def test_e39_zero_tau_raises_valueerror(self) -> None:
        """τ = 0 → ρ = 1 → series diverges → ValueError raised by retention_factor."""
        with pytest.raises(ValueError, match="tau_s"):
            retention_factor(tau_s=0.0, dt_s=1.0)

    def test_e39_negative_tau_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="tau_s"):
            steady_state_intensity(1.0, tau_s=-1.0, dt_s=1.0)

    def test_e39_e33_tau_table_has_no_zero_entries(self) -> None:
        """
        The E33 tau table never contains τ ≤ 0 — this is the key guard that
        keeps E39 convergence alive at runtime.
        """
        for kind, tau in DEFAULT_TAU_S.items():
            assert tau > 0.0, f"E33 tau for {kind} is {tau} — must be > 0"

    def test_e39_e33_strength_table_has_no_zero_entries(self) -> None:
        for kind, s in DEFAULT_STRENGTH.items():
            assert s > 0.0, f"E33 strength for {kind} is {s} — must be > 0"


# ── 7. Proof of Property ──────────────────────────────────────────────────────

class TestE39ProofOfProperty:

    def test_proof_has_required_keys(self) -> None:
        report = aco_convergence_report(DEFAULT_TAU_S, DEFAULT_STRENGTH)
        pop = report.proof_of_property
        assert {"E39", "theorem", "convergence_condition", "all_channels_converge",
                "global_I_inf", "falsifier", "truth_label"} <= pop.keys()

    def test_proof_theorem_references_formula(self) -> None:
        report = aco_convergence_report(DEFAULT_TAU_S, DEFAULT_STRENGTH)
        assert "exp(dt/tau)" in report.proof_of_property["theorem"]

    def test_proof_truth_label_is_operational(self) -> None:
        report = aco_convergence_report(DEFAULT_TAU_S, DEFAULT_STRENGTH)
        assert report.proof_of_property["truth_label"] == "OPERATIONAL"

    def test_proof_falsifier_mentions_e33(self) -> None:
        report = aco_convergence_report(DEFAULT_TAU_S, DEFAULT_STRENGTH)
        assert "E33" in report.proof_of_property["falsifier"]
