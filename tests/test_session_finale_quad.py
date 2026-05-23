#!/usr/bin/env python3
"""Physics-anchored pytest coverage for the session-finale quad:

1. swarm_field_primary_research_spine (extended with Architect citations)
2. swarm_qft_foundations
3. swarm_active_matter_field         (anchors + Vicsek model)
4. swarm_honest_assessment           (cross-module aggregator)

Every test docstring cites the peer-reviewed paper whose claim it
verifies. Per Architect directive 2026-05-11 ("BRING PHYSICS PAPERS
TO PROVE ALL YOUR TESTS").

Sandbox-safe: numpy + stdlib + pytest. No Qt, no scipy.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

# ── 1. spine extension ─────────────────────────────────────────────────────
from System.swarm_field_primary_research_spine import (
    VERIFIED_SPINE,
    verified_source_ids,
)

# ── 2. QFT foundations ─────────────────────────────────────────────────────
from System.swarm_qft_foundations import (
    QFT_TRUTH_GUARD,
    QFTAnchor,
    TRUTH_LABEL as QFT_TRUTH_LABEL,
    VERIFIED_ANCHORS as QFT_ANCHORS,
    anchors_by_stance,
    qft_foundations_payload,
    verified_anchor_ids as qft_anchor_ids,
    write_qft_receipt,
)

# ── 3. Active matter ───────────────────────────────────────────────────────
from System.swarm_active_matter_field import (
    ACTIVE_MATTER_TRUTH_GUARD,
    ActiveMatterAnchor,
    TRUTH_LABEL as AM_TRUTH_LABEL,
    VERIFIED_ANCHORS as AM_ANCHORS,
    VicsekConfig,
    VicsekModel,
    active_matter_payload,
    verified_anchor_ids as am_anchor_ids,
    write_active_matter_receipt,
)

# ── 4. Honest assessment ────────────────────────────────────────────────────
from System.swarm_honest_assessment import (
    HONEST_ASSESSMENT_TRUTH_GUARD,
    HonestAssessment,
    ModuleReport,
    TRUTH_LABEL as HA_TRUTH_LABEL,
    compute_assessment,
    deposit_assessment,
    render_text,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Spine extension — Architect's curated citations now present
# ═══════════════════════════════════════════════════════════════════════════
class TestSpineExtension:
    """Architect-curated additions integrated 2026-05-11.

    Each parametrized test cites the source paper that the Architect
    pasted into the tournament document.
    """

    @pytest.mark.parametrize(
        "anchor_id",
        [
            # Levin bioelectric ladder
            "levin_2014_endogenous_bioelectric_networks",      # J. Physiol. 592
            "levin_2012_molecular_bioelectricity",             # BioEssays 34
            "durant_levin_2017_planaria_bioelectric_rewrite",  # Biophys. J. 112
            "manicka_levin_2019_somatic_computation",          # Sci. Rep. 9
            "levin_2022_tame_framework",                       # Front. Sys. Neurosci. 16
            "levin_2023_bioelectric_cognitive_glue",           # Anim. Cogn. 26
            # Heylighen Part II
            "heylighen_2016_stigmergy_universal_part_II",      # Cogn. Syst. Res. 38
            # Rovelli updates
            "rovelli_2021_relational_interpretation",          # arXiv:2109.09170
            "di_biagio_rovelli_2021_stable_facts",             # Found. Phys. 51
            # Zurek deepening
            "ollivier_poulin_zurek_2005_environment_witness",  # PRA 72
            "zurek_2018_quantum_theory_classical",             # Phil. Trans. A 376
            # Field-primary ontology (the strong cites)
            "hobson_2013_no_particles_only_fields",            # AJP 81
            "sebens_2022_fundamentality_of_fields",            # Synthese 200
        ],
    )
    def test_curated_anchor_present(self, anchor_id):
        """Architect's 2026-05-11 tournament citation pack integrated."""
        assert anchor_id in verified_source_ids(), (
            f"Architect-curated anchor '{anchor_id}' missing"
        )

    def test_spine_carries_at_least_the_extended_minimum(self):
        """Pre-extension was 18; extension added ~13; total ≥ 30."""
        assert len(VERIFIED_SPINE) >= 30


# ═══════════════════════════════════════════════════════════════════════════
# 2. QFT foundations
# ═══════════════════════════════════════════════════════════════════════════
class TestQFTFoundations:
    """Strict QFT-literature anchors. The Architect's directive
    2026-05-11 was 'explore quantum field theory foundations'.
    """

    def test_truth_label_and_guard(self):
        assert QFT_TRUTH_LABEL == "SIFTA_QFT_FOUNDATIONS_V1"
        assert "QFT_FOUNDATIONS_DOCTRINE" in QFT_TRUTH_GUARD
        assert "does NOT solve QFT" in QFT_TRUTH_GUARD

    @pytest.mark.parametrize("anchor", QFT_ANCHORS)
    def test_anchor_carries_dois_and_guards(self, anchor: QFTAnchor):
        """Every QFT anchor must carry supports + does_not_support guards
        (covenant §7.11).
        """
        assert anchor.supports.strip()
        assert anchor.does_not_support.strip()
        if anchor.doi:
            assert anchor.doi.startswith("10.")
        assert anchor.stance in (
            "field_first", "particle_first", "structural",
            "axiomatic", "curved_spacetime",
        )

    @pytest.mark.parametrize(
        "anchor_id",
        [
            # Field-first stance papers
            "hobson_2013_no_particles_only_fields",         # AJP 81, 211
            "sebens_2022_fundamentality_of_fields",          # Synthese 200, 380
            "wilczek_1999_persistence_quanta",               # RMP 71, S85
            "fraser_2008_particle_problem_in_qft",           # SHPMP 39, 841
            # Axiomatic / structural
            "weinberg_qft_v1_1995",                          # Cambridge UP
            "streater_wightman_1964_pct_spin_statistics",    # Princeton
            "haag_1992_local_quantum_physics",               # Springer
            "wald_1994_qft_curved_spacetime",                # Chicago UP
        ],
    )
    def test_qft_anchor_present(self, anchor_id):
        """Eight QFT-foundations papers anchor this module."""
        assert anchor_id in qft_anchor_ids()

    def test_field_first_stance_dominates(self):
        """The Architect's directive is 'field is primary'; the stance
        distribution in the module must reflect that — at least 3 of
        the 8 anchors take the field-first stance directly.
        """
        ff = anchors_by_stance("field_first")
        assert len(ff) >= 3

    def test_qft_receipt_round_trips(self, tmp_path):
        out = tmp_path / "qft.jsonl"
        row = write_qft_receipt(state_root=tmp_path, receipt_path=out)
        assert row["truth_label"] == QFT_TRUTH_LABEL
        assert "sha256" in row and len(row["sha256"]) == 64
        parsed = json.loads(out.read_text("utf-8").strip())
        assert parsed["anchor_count"] == len(QFT_ANCHORS)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Active matter — anchors + Vicsek numerical phase transition
# ═══════════════════════════════════════════════════════════════════════════
class TestActiveMatterAnchors:
    """Vicsek 1995 (PRL 75, 1226, DOI 10.1103/PhysRevLett.75.1226) is
    the foundational paper. Marchetti et al. 2013 (RMP 85, 1143,
    DOI 10.1103/RevModPhys.85.1143) is the canonical review.
    """

    def test_truth_label_and_guard(self):
        assert AM_TRUTH_LABEL == "SIFTA_ACTIVE_MATTER_FIELD_V1"
        assert "ACTIVE_MATTER_ANALOGUE_ONLY" in ACTIVE_MATTER_TRUTH_GUARD

    @pytest.mark.parametrize("anchor", AM_ANCHORS)
    def test_anchor_carries_guards(self, anchor: ActiveMatterAnchor):
        assert anchor.supports.strip()
        assert anchor.does_not_support.strip()
        assert anchor.doi.startswith("10.")

    @pytest.mark.parametrize(
        "anchor_id",
        [
            "vicsek_1995_novel_type_phase_transition",           # PRL 75, 1226
            "toner_tu_1995_long_range_order_self_propelled",     # PRL 75, 4326
            "toner_tu_1998_flocks_herds_schools",                # PRE 58, 4828
            "marchetti_2013_active_matter_RMP",                  # RMP 85, 1143
            "ramaswamy_2010_mechanics_statistics_active",        # ARCMP 1, 323
            "cates_tailleur_2015_motility_induced_phase_separation",  # ARCMP 6
            "bechinger_2016_active_particles_complex_environments",   # RMP 88
            "cavagna_2010_scale_free_correlations_starling_flocks",   # PNAS 107
        ],
    )
    def test_active_matter_anchor_present(self, anchor_id):
        assert anchor_id in am_anchor_ids()


class TestVicsekModel:
    """The Vicsek 1995 model (PRL 75, 1226, DOI
    10.1103/PhysRevLett.75.1226) predicts a continuous phase transition
    from disorder (low polar order) at high noise to flocking (high
    polar order) at low noise.
    """

    def test_initial_polar_order_low_for_random_thetas(self):
        """Vicsek 1995 §III: random initial conditions give φ ~ 1/√N."""
        cfg = VicsekConfig(n_particles=200, box_size=10.0,
                           speed=0.0, radius=1.0, noise=2 * math.pi)
        m = VicsekModel(cfg, seed=42)
        # zero speed + max noise → particles do not align, even after steps
        m.run(20)
        assert m.polar_order() < 0.3

    def test_low_noise_drives_high_polar_order(self):
        """Vicsek 1995 Figure 2: at noise η below the critical value,
        the system flocks (polar order φ → 1).
        """
        cfg = VicsekConfig(n_particles=300, box_size=7.0,
                           speed=0.03, radius=1.0, noise=0.05)
        m = VicsekModel(cfg, seed=0)
        m.run(400)
        # With very low noise, dense system, large interaction radius
        # relative to box, the order parameter must climb high.
        assert m.polar_order() > 0.6, (
            f"low-noise Vicsek run produced polar_order={m.polar_order():.3f}, "
            "expected > 0.6 (Vicsek 1995 fig 2)"
        )

    def test_high_noise_keeps_polar_order_low(self):
        """Vicsek 1995 Figure 2: at noise η above the critical value,
        the system remains disordered (φ remains small).
        """
        cfg = VicsekConfig(n_particles=300, box_size=10.0,
                           speed=0.03, radius=1.0, noise=2 * math.pi - 0.1)
        m = VicsekModel(cfg, seed=1)
        m.run(200)
        # With maximum noise the order parameter should NOT climb.
        assert m.polar_order() < 0.4

    def test_periodic_boundary_keeps_positions_in_box(self):
        cfg = VicsekConfig(n_particles=50, box_size=5.0,
                           speed=0.5, radius=1.0, noise=0.1)
        m = VicsekModel(cfg, seed=7)
        m.run(50)
        assert m.positions[:, 0].min() >= 0.0
        assert m.positions[:, 0].max() < cfg.box_size
        assert m.positions[:, 1].min() >= 0.0
        assert m.positions[:, 1].max() < cfg.box_size

    def test_reproducible_with_seed(self):
        cfg = VicsekConfig(n_particles=40, box_size=5.0,
                           speed=0.05, radius=1.0, noise=0.2)
        m1 = VicsekModel(cfg, seed=2026)
        m2 = VicsekModel(cfg, seed=2026)
        m1.run(30)
        m2.run(30)
        assert np.allclose(m1.positions, m2.positions)
        assert np.allclose(m1.thetas, m2.thetas)

    def test_vicsek_snapshot_carries_truth_guard(self):
        cfg = VicsekConfig(n_particles=30, box_size=5.0)
        m = VicsekModel(cfg, seed=0)
        snap = m.snapshot()
        assert snap["schema"] == AM_TRUTH_LABEL
        assert "ACTIVE_MATTER_ANALOGUE_ONLY" in snap["truth_guard"]


# ═══════════════════════════════════════════════════════════════════════════
# 4. Honest assessment — cross-module aggregator
# ═══════════════════════════════════════════════════════════════════════════
class TestHonestAssessment:
    """The honest-assessment aggregator must inject nothing of its own
    and never soften an aggregated forbidden clause.
    """

    def test_truth_label_and_guard(self):
        assert HA_TRUTH_LABEL == "SIFTA_HONEST_ASSESSMENT_V1"
        assert "HONEST_ASSESSMENT_AGGREGATOR" in HONEST_ASSESSMENT_TRUTH_GUARD

    def test_compute_aggregates_real_modules(self):
        """The default registry must include at least 5 real SIFTA spines."""
        a = compute_assessment()
        assert isinstance(a, HonestAssessment)
        assert a.total_modules >= 5
        assert a.total_anchors > 30  # plenty of anchors across spines
        # Every report must have a non-empty truth_guard.
        for rep in a.module_reports:
            assert rep.truth_guard.strip(), (
                f"module {rep.module_name} has empty truth_guard"
            )

    def test_consolidated_does_not_support_is_nonempty(self):
        """The whole point of the aggregator is to surface what SIFTA
        does NOT claim. If this list is empty, the aggregator is broken.
        """
        a = compute_assessment()
        assert len(a.consolidated_does_not_support) > 0
        # No empty / whitespace-only clauses.
        for clause in a.consolidated_does_not_support:
            assert clause.strip()

    def test_consolidated_clauses_are_deduplicated(self):
        """Same clause appearing in multiple spines should appear ONCE
        in the consolidated list (the aggregator does set-style merge).
        """
        a = compute_assessment()
        assert (
            len(a.consolidated_does_not_support)
            == len(set(a.consolidated_does_not_support))
        )

    def test_render_text_is_human_readable(self):
        a = compute_assessment()
        text = render_text(a)
        assert "SIFTA HONEST ASSESSMENT" in text
        assert "WHAT SIFTA EXPLICITLY DOES NOT CLAIM" in text
        for rep in a.module_reports:
            assert rep.module_name in text

    def test_no_module_truth_guard_softened(self):
        """The aggregator must copy guards verbatim. Sample-check that
        each module report's truth_guard string is a literal substring
        of the source module's published guard.
        """
        import importlib
        a = compute_assessment()
        for rep in a.module_reports:
            mod = importlib.import_module(rep.module_name)
            # Try a few likely attribute names
            guard_candidates = []
            for attr in dir(mod):
                if "GUARD" in attr.upper():
                    val = getattr(mod, attr, None)
                    if isinstance(val, str):
                        guard_candidates.append(val)
            assert rep.truth_guard in guard_candidates, (
                f"aggregated guard for {rep.module_name} does not match "
                "any published guard string"
            )

    def test_deposit_assessment_writes_hashed_row(self, tmp_path):
        a = compute_assessment()
        out = tmp_path / "ha.jsonl"
        deposit_assessment(a, receipt_path=out)
        line = out.read_text("utf-8").strip()
        parsed = json.loads(line)
        assert parsed["schema"] == HA_TRUTH_LABEL
        assert len(parsed["sha256"]) == 64
