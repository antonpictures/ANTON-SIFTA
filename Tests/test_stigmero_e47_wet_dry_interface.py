"""
tests/test_stigmero_e47_wet_dry_interface.py
═══════════════════════════════════════════════════════════════════════════════
E47 — Wet-Dry Interface (Physical Effector Mapping)

ROB 501 topic: Embodied robotics, bio-hybrid actuators, CPMV VLP nanotech.

Hypothesis (P):
    Every SIFTA ledger organ has a physical counterpart (WET side) whose
    behavior inherits the corresponding ledger invariant (DRY side).
    The inheritance is non-trivial: E34 Safety Graph is the mandatory gate
    for ALL physical effectors. No physical actuation without a prior
    registration→effector edge.

Proof structure:
  1. Bridge completeness: 6 specs covering E33, E34, E38, E39, E45, E46.
  2. Safety gate invariant: every spec has safety_gate_organ == "E34".
  3. DOI anchoring: every spec has a doi: anchor (§8.6 no floating claims).
  4. E34 inheritance: every spec's inherited_invariants references E34.
  5. Dual truth labels: ledger=OPERATIONAL, physical=HYPOTHESIS (§7.11).
  6. Saunders CPMV mapping: each spec has a saunders_cpmv_mapping field.
  7. Falsifier presence: each spec has a non-empty falsifier.
  8. Proof of property keys and truth labels.

§8.6 compliance: pure declarative, no live ledger reads.
"""
from __future__ import annotations

import pytest

from System.stigmerobotics_wet_dry_interface import (
    HYPOTHESIS,
    OPERATIONAL,
    PhysicalEffectorSpec,
    WetDryBridge,
    build_wet_dry_bridge,
    wet_dry_bridge,
    CANONICAL_SPECS,
)


# ── 1. Bridge completeness ────────────────────────────────────────────────────

class TestE47Completeness:

    def test_e47_six_specs_in_canonical_bridge(self) -> None:
        bridge = build_wet_dry_bridge()
        assert len(bridge.specs) == 6

    def test_e47_covers_e33(self) -> None:
        bridge = build_wet_dry_bridge()
        assert "E33" in bridge.organ_ids

    def test_e47_covers_e34(self) -> None:
        bridge = build_wet_dry_bridge()
        assert "E34" in bridge.organ_ids

    def test_e47_covers_e38(self) -> None:
        bridge = build_wet_dry_bridge()
        assert "E38" in bridge.organ_ids

    def test_e47_covers_e39(self) -> None:
        bridge = build_wet_dry_bridge()
        assert "E39" in bridge.organ_ids

    def test_e47_covers_e45(self) -> None:
        bridge = build_wet_dry_bridge()
        assert "E45" in bridge.organ_ids

    def test_e47_covers_e46(self) -> None:
        bridge = build_wet_dry_bridge()
        assert "E46" in bridge.organ_ids

    def test_e47_get_spec_returns_correct_organ(self) -> None:
        bridge = build_wet_dry_bridge()
        spec = bridge.get_spec("E33")
        assert spec is not None
        assert spec.organ_id == "E33"

    def test_e47_get_spec_returns_none_for_unknown(self) -> None:
        bridge = build_wet_dry_bridge()
        assert bridge.get_spec("E99") is None

    def test_e47_alias_matches_build(self) -> None:
        assert wet_dry_bridge().organ_ids == build_wet_dry_bridge().organ_ids


# ── 2. Safety gate invariant ──────────────────────────────────────────────────

class TestE47SafetyGate:

    def test_e47_all_specs_have_e34_safety_gate(self) -> None:
        """
        E47 Safety Gate Invariant: every physical effector requires E34.
        No physical actuation without a prior registration→effector edge.
        """
        bridge = build_wet_dry_bridge()
        assert bridge.all_have_safety_gate

    def test_e47_each_spec_safety_gate_is_e34(self) -> None:
        for spec in CANONICAL_SPECS:
            assert spec.safety_gate_organ == "E34", (
                f"{spec.organ_id}: safety_gate_organ is '{spec.safety_gate_organ}', expected 'E34'"
            )

    def test_e47_all_inherit_e34(self) -> None:
        bridge = build_wet_dry_bridge()
        assert bridge.all_inherit_e34


# ── 3. DOI anchoring (§8.6 no floating claims) ───────────────────────────────

class TestE47DOIAnchors:

    def test_e47_all_specs_have_doi(self) -> None:
        bridge = build_wet_dry_bridge()
        assert bridge.all_have_doi

    def test_e47_each_doi_starts_with_doi_prefix(self) -> None:
        for spec in CANONICAL_SPECS:
            assert spec.doi_anchor.startswith("doi:"), (
                f"{spec.organ_id}: doi_anchor '{spec.doi_anchor}' must start with 'doi:'"
            )

    def test_e47_e33_cites_saunders(self) -> None:
        bridge = build_wet_dry_bridge()
        spec = bridge.get_spec("E33")
        assert spec is not None
        assert "10.1111/nph.12204" in spec.doi_anchor

    def test_e47_e34_cites_ayers(self) -> None:
        bridge = build_wet_dry_bridge()
        spec = bridge.get_spec("E34")
        assert spec is not None
        assert "10.1016/j.asd" in spec.doi_anchor


# ── 4. Dual truth labels (§7.11) ─────────────────────────────────────────────

class TestE47TruthLabels:

    def test_e47_all_ledger_labels_are_operational(self) -> None:
        """Ledger inheritance proofs are OPERATIONAL — machine-checked."""
        for spec in CANONICAL_SPECS:
            assert spec.truth_label_ledger == OPERATIONAL, (
                f"{spec.organ_id}: truth_label_ledger is '{spec.truth_label_ledger}'"
            )

    def test_e47_all_physical_labels_are_hypothesis(self) -> None:
        """Physical mappings are HYPOTHESIS until wet-lab receipt pinned (§7.11)."""
        for spec in CANONICAL_SPECS:
            assert spec.truth_label_physical == HYPOTHESIS, (
                f"{spec.organ_id}: truth_label_physical is '{spec.truth_label_physical}'"
            )

    def test_e47_operational_count_equals_spec_count(self) -> None:
        bridge = build_wet_dry_bridge()
        assert bridge.operational_count == len(bridge.specs)

    def test_e47_hypothesis_count_equals_spec_count(self) -> None:
        bridge = build_wet_dry_bridge()
        assert bridge.hypothesis_count == len(bridge.specs)


# ── 5. Saunders CPMV mapping ─────────────────────────────────────────────────

class TestE47SaundersCPMV:

    def test_e47_all_specs_have_cpmv_mapping(self) -> None:
        for spec in CANONICAL_SPECS:
            assert len(spec.saunders_cpmv_mapping) > 20, (
                f"{spec.organ_id}: saunders_cpmv_mapping is empty or too short"
            )

    def test_e47_e33_mentions_vlp(self) -> None:
        spec = build_wet_dry_bridge().get_spec("E33")
        assert spec is not None
        assert "eVLP" in spec.saunders_cpmv_mapping or "VLP" in spec.saunders_cpmv_mapping

    def test_e47_e39_mentions_yield(self) -> None:
        spec = build_wet_dry_bridge().get_spec("E39")
        assert spec is not None
        assert "yield" in spec.saunders_cpmv_mapping.lower() or "g/g" in spec.saunders_cpmv_mapping

    def test_e47_e45_mentions_brownian(self) -> None:
        spec = build_wet_dry_bridge().get_spec("E45")
        assert spec is not None
        assert "Brownian" in spec.saunders_cpmv_mapping or "kT" in spec.saunders_cpmv_mapping


# ── 6. Falsifier presence ─────────────────────────────────────────────────────

class TestE47Falsifiers:

    def test_e47_all_specs_have_falsifier(self) -> None:
        for spec in CANONICAL_SPECS:
            assert len(spec.falsifier) > 10, (
                f"{spec.organ_id}: falsifier is empty or too short"
            )

    def test_e47_e34_falsifier_mentions_signed_surgery(self) -> None:
        spec = build_wet_dry_bridge().get_spec("E34")
        assert spec is not None
        assert "registration" in spec.falsifier.lower() or "BROKEN" in spec.falsifier

    def test_e47_e38_falsifier_mentions_dfa(self) -> None:
        spec = build_wet_dry_bridge().get_spec("E38")
        assert spec is not None
        assert "DFA" in spec.falsifier or "order" in spec.falsifier.lower()


# ── 7. Proof of Property ──────────────────────────────────────────────────────

class TestE47ProofOfProperty:

    def test_proof_has_required_keys(self) -> None:
        pop = build_wet_dry_bridge().proof_of_property
        assert {
            "E47", "theorem", "specs", "organ_ids",
            "all_have_safety_gate", "all_have_doi", "all_inherit_e34",
            "hypothesis_count", "operational_count",
            "falsifier", "saunders_cpmv_anchor", "ayers_anchor",
            "truth_label_ledger", "truth_label_physical", "note",
        } <= pop.keys()

    def test_proof_truth_label_ledger_is_operational(self) -> None:
        assert build_wet_dry_bridge().proof_of_property["truth_label_ledger"] == OPERATIONAL

    def test_proof_truth_label_physical_is_hypothesis(self) -> None:
        assert build_wet_dry_bridge().proof_of_property["truth_label_physical"] == HYPOTHESIS

    def test_proof_all_have_safety_gate_is_true(self) -> None:
        assert build_wet_dry_bridge().proof_of_property["all_have_safety_gate"] is True

    def test_proof_cites_saunders_doi(self) -> None:
        pop = build_wet_dry_bridge().proof_of_property
        assert "10.1111/nph.12204" in pop["saunders_cpmv_anchor"]

    def test_proof_cites_ayers_doi(self) -> None:
        pop = build_wet_dry_bridge().proof_of_property
        assert "10.1016/j.asd" in pop["ayers_anchor"]

    def test_proof_note_mentions_hypothesis(self) -> None:
        assert "HYPOTHESIS" in build_wet_dry_bridge().proof_of_property["note"]

    def test_summary_lines_contain_all_organs(self) -> None:
        lines = "\n".join(build_wet_dry_bridge().summary_lines())
        for organ in ("E33", "E34", "E38", "E39", "E45", "E46"):
            assert organ in lines, f"{organ} missing from summary"
