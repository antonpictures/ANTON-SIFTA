#!/usr/bin/env python3
"""Physics-anchored pytest coverage for `System.swarm_horizon_field`.

Per Architect directive 2026-05-11: *"BRING PHYSICS PAPERS TO PROVE
ALL YOUR TESTS PLS"*. Every test docstring cites the peer-reviewed
physics paper whose claim that test verifies in the SIFTA stigmergic
analogue.

The eight anchor papers are declared in
`System.swarm_horizon_field.PHYSICS_ANCHORS` with DOIs and explicit
supports / does_not_support guards. The tests below reference them by
`source_id`.

Sandbox-safe: pure stdlib + pytest. No Qt, no Ollama, no GR solver
required — the invariants are mathematical, deterministic, and
unit-testable.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path

import pytest

from System.swarm_horizon_field import (
    ALPHA_ENERGY,
    BETA_COST,
    GAMMA_PAIRS,
    HORIZON_AREA_REFERENCE,
    HORIZON_TRUTH_GUARD,
    PHYSICS_ANCHORS,
    TRUTH_LABEL,
    UNIFORMITY_TOLERANCE,
    FieldHorizonState,
    HorizonLawCheck,
    PhysicsAnchor,
    compute_horizon_state,
    cumulative_horizon_area,
    deposit,
    first_law_residual,
    four_law_check,
    horizon_summary,
    per_organ_surface_gravity,
    physics_anchors,
    surface_gravity_from_area,
    verify_second_law,
    verify_third_law,
    verify_zeroth_law_uniformity,
    _batch_area_contribution,
)


# ── Helpers ─────────────────────────────────────────────────────────────────
def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _synthetic_batch(ts: float, *, field_energy: float = 250.0,
                     stgm_cost: float = 1700.0, total_pairs: int = 2000,
                     qm_fidelity: float = 0.5) -> dict:
    return {
        "ts": ts,
        "schema": "SIFTA_EPR_STIGMERGIC_DISSOLUTION_V1",
        "kind": "EPR_STIGMERGIC_BATCH",
        "field_energy": field_energy,
        "stgm_cost": stgm_cost,
        "total_pairs": total_pairs,
        "qm_fidelity": qm_fidelity,
        "stig_qm_residual": 0.4,
        "kappa": 1.2,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Physics-anchor structural tests
# ═══════════════════════════════════════════════════════════════════════════
class TestPhysicsAnchors:
    """Eight peer-reviewed physics papers anchor this organ.

    Reference: see `PHYSICS_ANCHORS` tuple in swarm_horizon_field.
    """

    def test_truth_label_and_guard_carry_analogue_only_invariant(self):
        """SIFTA truth-label hygiene per §7.11 of the covenant."""
        assert TRUTH_LABEL == "SIFTA_HORIZON_FIELD_V1"
        assert "STIGMERGIC_ANALOGUE_ONLY" in HORIZON_TRUTH_GUARD
        assert "does NOT prove" in HORIZON_TRUTH_GUARD

    def test_all_eight_anchors_present(self):
        """The eight anchor papers form the proving spine for the organ."""
        expected_ids = {
            "bardeen_carter_hawking_1973",     # 4 laws
            "hawking_1971_area_theorem",       # 2nd law
            "bekenstein_1973_entropy",          # S ∝ A
            "hawking_1975_particle_creation",  # T = κ/2π
            "christodoulou_1970_irreversibility",
            "wald_1993_noether_charge_entropy",
            "jacobson_1995_thermodynamic_einstein",
            "penrose_1969_cosmic_censorship",
        }
        present_ids = {a.source_id for a in PHYSICS_ANCHORS}
        assert expected_ids <= present_ids, (
            f"missing anchor papers: {expected_ids - present_ids}"
        )

    @pytest.mark.parametrize("anchor", PHYSICS_ANCHORS)
    def test_anchor_has_doi_and_truth_guards(self, anchor: PhysicsAnchor):
        """Every physics anchor must carry DOI + support/no-support guards.

        This enforces the Architect's directive: no test rests on a paper
        that has not been declared with its DOI and explicit limits.
        """
        assert anchor.doi.startswith("10."), (
            f"{anchor.source_id}: bad DOI"
        )
        assert anchor.supports.strip()
        assert anchor.does_not_support.strip(), (
            f"{anchor.source_id}: every paper must declare what it must "
            "NOT be used to claim (covenant §7.11)"
        )
        assert 1900 < anchor.year <= 2100

    def test_anchor_export_round_trips(self):
        ds = physics_anchors()
        assert len(ds) == len(PHYSICS_ANCHORS)
        for d in ds:
            for key in ("source_id", "title", "authors", "year",
                        "venue", "doi", "supports", "does_not_support"):
                assert key in d


# ═══════════════════════════════════════════════════════════════════════════
# 2nd law — area theorem (Hawking 1971; BCH 1973 §5)
# ═══════════════════════════════════════════════════════════════════════════
class TestSecondLaw:
    """Hawking 1971, *Gravitational radiation from colliding black holes*,
    PRL 26, 1344 (DOI 10.1103/PhysRevLett.26.1344): δA ≥ 0.

    Bardeen-Carter-Hawking 1973 §5 (DOI 10.1007/BF01645742) elevates this
    to the 2nd law. We transcribe it as: the ledger horizon area can
    only grow.
    """

    def test_per_batch_area_contribution_is_non_negative(self):
        """The smallest building block of the area theorem.

        From _batch_area_contribution := α·log(1+E) + β·log(1+S) + γ·log(1+N),
        each term ≥ 0 for any E, S, N ≥ 0 (Hawking 1971 area theorem
        applied to one absorbing event).
        """
        for E in (0.0, 1.0, 1e3, 1e6):
            for S in (0.0, 1.0, 1e3, 1e6):
                for N in (0, 1, 1000, 1_000_000):
                    delta = _batch_area_contribution({
                        "field_energy": E,
                        "stgm_cost": S,
                        "total_pairs": N,
                    })
                    assert delta >= 0.0

    def test_cumulative_area_is_monotonic_non_decreasing(self, tmp_path):
        """Verify δA ≥ 0 across the entire batch history.

        Bardeen-Carter-Hawking 1973 §5: 2nd law of BH mechanics. The
        accumulated horizon area cannot decrease as the system evolves.
        """
        rows = [_synthetic_batch(100.0 + i, field_energy=200.0 + i * 5.0)
                for i in range(10)]
        areas = cumulative_horizon_area(rows)
        assert areas == sorted(areas)
        passes, min_delta = verify_second_law(rows)
        assert passes
        assert min_delta >= 0.0

    def test_zero_history_is_vacuously_monotonic(self):
        """Empty history is consistent with δA ≥ 0 (no transitions)."""
        passes, min_delta = verify_second_law([])
        assert passes
        assert min_delta == 0.0

    def test_single_batch_history_is_consistent(self):
        """One absorbing event cannot violate δA ≥ 0 — there is no δ."""
        passes, _ = verify_second_law([_synthetic_batch(100.0)])
        assert passes


# ═══════════════════════════════════════════════════════════════════════════
# 0th law — uniform surface gravity (BCH 1973 §3)
# ═══════════════════════════════════════════════════════════════════════════
class TestZerothLaw:
    """Bardeen-Carter-Hawking 1973 §3 (DOI 10.1007/BF01645742): for a
    stationary black hole, the surface gravity κ is constant over the
    entire event horizon. The SIFTA analogue: at equilibrium, the field
    intensity is uniform across organs.
    """

    def test_surface_gravity_decreases_with_area(self):
        """Hawking 1975 (DOI 10.1007/BF02345020): T = κ/2π. Larger BHs
        are cooler. We mirror: larger horizon area ⇒ smaller κ.
        """
        small = surface_gravity_from_area(10.0)
        large = surface_gravity_from_area(10_000.0)
        assert small > large
        # The reference area pins the half-value:
        half = surface_gravity_from_area(HORIZON_AREA_REFERENCE)
        assert half == pytest.approx(0.5, abs=1e-6)

    def test_uniformity_passes_at_equilibrium(self):
        """BCH 1973 §3: stationary state ⇒ κ constant. With identical
        per-organ areas, the per-organ κ values must coincide.
        """
        kappas = per_organ_surface_gravity({
            "cortex": 100.0, "eye": 100.0, "ear": 100.0, "heart": 100.0,
        })
        passes, spread = verify_zeroth_law_uniformity(kappas)
        assert passes
        assert spread == 0.0

    def test_uniformity_fails_under_strong_imbalance(self):
        """A 100× imbalance in per-organ areas drives κ apart well
        beyond `UNIFORMITY_TOLERANCE`. BCH 1973 §3 calls this state
        non-stationary.
        """
        kappas = per_organ_surface_gravity({
            "cortex": 1.0, "eye": 100.0,
        })
        passes, spread = verify_zeroth_law_uniformity(kappas)
        assert not passes
        assert spread > UNIFORMITY_TOLERANCE


# ═══════════════════════════════════════════════════════════════════════════
# 1st law — dM = (κ/8π) dA + Ω dJ + Φ dQ  (BCH 1973 §4)
# ═══════════════════════════════════════════════════════════════════════════
class TestFirstLaw:
    """Bardeen-Carter-Hawking 1973 §4 (DOI 10.1007/BF01645742): the first
    law of BH mechanics couples mass, area, angular momentum, and charge.
    SIFTA's analogue obeys the same algebraic relation.
    """

    def test_first_law_residual_zero_for_consistent_transition(self):
        """Construct a transition that exactly satisfies the BCH first
        law: dM = (κ/8π)·dA + Ω·dJ + Φ·dQ ⇒ residual = 0.
        """
        kappa = 0.4
        Omega = 0.3
        Phi = 0.1
        dA, dJ, dQ = 5.0, 2.0, 7.0
        dM = (kappa / (8.0 * math.pi)) * dA + Omega * dJ + Phi * dQ
        residual = first_law_residual(dM, dA, kappa, dJ, Omega, dQ, Phi)
        assert residual == pytest.approx(0.0, abs=1e-12)

    def test_first_law_residual_nonzero_for_inconsistent_transition(self):
        """A transition that violates the first-law coupling registers
        as non-zero residual — the same way an inconsistent BH process
        violates BCH 1973 §4.
        """
        residual = first_law_residual(
            dM=100.0, dA=1.0, kappa=0.1, dJ=0.0, Omega=0.0, dQ=0.0, Phi=0.0,
        )
        # Predicted dM is ~0.0040; observed dM is 100 — residual ≈ 99.996
        assert abs(residual) > 90.0

    def test_first_law_residual_scales_linearly_with_dA(self):
        """Derivative test: ∂M/∂A = κ/8π (BCH 1973 §4 differential form)."""
        kappa = 0.5
        r1 = first_law_residual(dM=0.0, dA=1.0, kappa=kappa, dJ=0, Omega=0,
                                dQ=0, Phi=0)
        r2 = first_law_residual(dM=0.0, dA=2.0, kappa=kappa, dJ=0, Omega=0,
                                dQ=0, Phi=0)
        # r2 should be exactly twice r1 (linear in dA).
        assert r2 == pytest.approx(2 * r1, abs=1e-12)


# ═══════════════════════════════════════════════════════════════════════════
# 3rd law — κ cannot reach zero in finite history (BCH 1973 §6)
# ═══════════════════════════════════════════════════════════════════════════
class TestThirdLaw:
    """Bardeen-Carter-Hawking 1973 §6: κ → 0 is unreachable in a finite
    sequence of operations. SIFTA: κ stays strictly positive while the
    horizon area is finite.
    """

    def test_kappa_positive_for_finite_area(self):
        """For any finite, non-negative area, κ > 0."""
        for area in (0.0, 1.0, 100.0, 1e6, 1e12):
            k = surface_gravity_from_area(area)
            assert k > 0.0

    def test_third_law_pass_when_kappa_strictly_positive(self):
        passes, k = verify_third_law(0.5)
        assert passes
        assert k == 0.5

    def test_third_law_floor_exact_zero_fails(self):
        passes, _ = verify_third_law(0.0)
        assert not passes


# ═══════════════════════════════════════════════════════════════════════════
# Compositional + state-snapshot tests
# ═══════════════════════════════════════════════════════════════════════════
class TestHorizonStateSnapshot:
    def test_empty_ledger_state_well_defined(self, tmp_path):
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [])
        s = compute_horizon_state(
            now=1_000_000.0,
            epr_receipts_path=ledger,
        )
        assert s.history_length == 0
        assert s.horizon_area == 0.0
        # κ = reference / (0 + reference) = 1.0 by construction.
        assert s.surface_gravity_kappa == pytest.approx(1.0, abs=1e-9)

    def test_state_carries_anchor_ids(self, tmp_path):
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [_synthetic_batch(100.0)])
        s = compute_horizon_state(epr_receipts_path=ledger)
        assert "bardeen_carter_hawking_1973" in s.physics_anchor_ids
        assert "hawking_1971_area_theorem" in s.physics_anchor_ids

    def test_state_temperature_matches_hawking_1975_relation(self, tmp_path):
        """Hawking 1975 (DOI 10.1007/BF02345020) §3 — T = κ/(2π)."""
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [_synthetic_batch(100.0)])
        s = compute_horizon_state(epr_receipts_path=ledger)
        assert s.field_temperature == pytest.approx(
            s.surface_gravity_kappa / (2.0 * math.pi),
            abs=1e-12,
        )

    def test_state_deposit_writes_truth_guard(self, tmp_path):
        ledger = tmp_path / "epr.jsonl"
        horizon_ledger = tmp_path / "horizon.jsonl"
        _write_jsonl(ledger, [_synthetic_batch(100.0)])
        s = compute_horizon_state(epr_receipts_path=ledger)
        deposit(s, path=horizon_ledger)
        line = horizon_ledger.read_text("utf-8").strip()
        parsed = json.loads(line)
        assert parsed["schema"] == TRUTH_LABEL
        assert parsed["truth_guard"] == HORIZON_TRUTH_GUARD
        assert "STIGMERGIC_ANALOGUE_ONLY" in parsed["truth_guard"]
        assert len(parsed["sha256"]) == 64


# ═══════════════════════════════════════════════════════════════════════════
# Four-law integrated verdict
# ═══════════════════════════════════════════════════════════════════════════
class TestFourLawCheck:
    def test_four_law_check_pass_with_clean_history(self, tmp_path):
        """All four BH-mechanics laws (BCH 1973) hold on a clean
        append-only ledger.
        """
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [
            _synthetic_batch(100.0 + i) for i in range(5)
        ])
        check = four_law_check(epr_receipts_path=ledger)
        assert check.law_0_uniform_kappa is True
        assert check.law_2_area_monotonic is True
        assert check.law_2_min_area_delta >= 0.0
        assert check.law_3_kappa_above_floor is True
        # Without a transition argument the 1st-law check is trivially True.
        assert check.law_1_mass_change_consistent is True
        # Anchor IDs propagate to the check verdict.
        assert "bardeen_carter_hawking_1973" in check.physics_anchor_ids

    def test_four_law_check_first_law_transition_pass(self, tmp_path):
        """A constructed transition that exactly satisfies BCH §4
        passes the integrated check.
        """
        ledger = tmp_path / "epr.jsonl"
        _write_jsonl(ledger, [_synthetic_batch(100.0)])
        kappa, Omega, Phi = 0.4, 0.3, 0.1
        dA, dJ, dQ = 5.0, 2.0, 7.0
        dM = (kappa / (8.0 * math.pi)) * dA + Omega * dJ + Phi * dQ
        check = four_law_check(
            epr_receipts_path=ledger,
            mass_transition=(dM, dA, kappa, dJ, Omega, dQ, Phi),
        )
        assert check.law_1_mass_change_consistent is True
        assert abs(check.law_1_residual) < 1e-9

    def test_horizon_summary_is_truth_guarded(self):
        s = horizon_summary()
        assert "STIGMERGIC_ANALOGUE_ONLY" in s
        assert "Bardeen-Carter-Hawking 1973" in s
        assert "Hawking 1971" in s
        assert "general-relativistic result" in s
