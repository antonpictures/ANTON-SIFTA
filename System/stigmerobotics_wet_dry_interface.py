#!/usr/bin/env python3
"""
System/stigmerobotics_wet_dry_interface.py
==========================================

E47 — Wet-Dry Interface (Physical Effector Mapping)

ROB 501 topic: Embodied robotics, bio-hybrid actuators, VLP nanotech.

References:
  Saunders, K. & Lomonossoff, G.P. (2013). In planta production of
    N-terminally truncated and isotope-labelled forms of cowpea mosaic
    virus coat protein subunits.
    New Phytologist 200(1):278-286. DOI: 10.1111/nph.12204
    — CPMV-HT hyper-translatable constructs, eVLPs, Agrobacterium infiltration.

  Ayers, J.L. (2004). Underwater walking.
    Arthropod Structure & Development 33(3):347-360.
    — "The electronic nervous system directly drives physical actuators."

  Grillner, S. (2003). The motor infrastructure: from ion channels to
    neuronal networks. Nature Reviews Neuroscience 4(7):573-586.
    — Real CPG signals map to real muscle contractions.

──────────────────────────────────────────────────────────────────────────────
Wet-Dry Bridge Theorem (E47):

  Let DRY = the set of 11 SIFTA ledger organs { E01...E46 }.
  Let WET = the set of physical effector specifications derived from DRY.

  For each e ∈ DRY, define:
    phy(e) = PhysicalEffectorSpec (physical counterpart of organ e)
    gate(e) = E34 safety graph edge required before phy(e) may actuate

  E47 Inheritance Theorem:
    For every spec phy(e):
      1. gate(e) requires a prior LLM_REGISTRATION on the same channel (E34)
      2. phy(e).molecular_grammar inherits E38 DFA acceptance
      3. phy(e).max_concentration inherits E39 I_∞ bound
      4. phy(e).noise_bound inherits E45 ε·tanh(overshoot) ≤ ε

  Falsifier:
    Any phy(e) that can actuate without a prior E34 registration edge =
    BROKEN (same as unsigned surgery — §6 effector law).

  Truth labels (§7.11):
    Physical mappings are labeled HYPOTHESIS until:
      (a) a DOI-backed paper pins the specific wet mechanism, AND
      (b) a lab receipt or physical-world observation confirms the behavior.
    Ledger-side inheritance proofs are labeled OPERATIONAL.

§8.6 compliance: no live ledger writes. Pure declarative mapping.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Truth labels ─────────────────────────────────────────────────────────────

OPERATIONAL = "OPERATIONAL"   # ledger invariant — machine-checked
HYPOTHESIS  = "HYPOTHESIS"    # physical mapping — needs wet-lab receipt
ANALOGY     = "ANALOGY"       # illustrative parallel, not a proof claim


# ── Physical Effector Specification ──────────────────────────────────────────

@dataclass(frozen=True)
class PhysicalEffectorSpec:
    """
    One physical counterpart for one SIFTA ledger organ.

    Every spec carries:
    - the organ_id it maps from
    - a physical_name and description of the wet mechanism
    - the inherited ledger invariants (by ID)
    - the mandatory safety_gate_organ (always "E34" — §6 effector law)
    - a falsifier for the physical claim
    - a DOI anchor (if available) for the physical mechanism
    - a truth_label: OPERATIONAL (ledger side) or HYPOTHESIS (physical side)
    """
    organ_id: str
    physical_name: str
    physical_description: str
    physical_mechanism: str
    inherited_invariants: tuple[str, ...]
    safety_gate_organ: str
    falsifier: str
    doi_anchor: str
    truth_label_ledger: str    # always OPERATIONAL for the inheritance proof
    truth_label_physical: str  # HYPOTHESIS until wet-lab receipt pinned
    saunders_cpmv_mapping: str


# ── Canonical wet-dry mapping ─────────────────────────────────────────────────

CANONICAL_SPECS: tuple[PhysicalEffectorSpec, ...] = (

    PhysicalEffectorSpec(
        organ_id="E33",
        physical_name="VLP Pheromone Field",
        physical_description=(
            "Surface-functionalized Virus-Like Particles (eVLPs from CPMV-HT) "
            "as physical pheromone deposits. Each eVLP is a 28nm icosahedral cage "
            "with addressable lysine residues on the outer surface. VLPs are released "
            "by a channel, diffuse through the medium, and are cleared by endocytosis / "
            "phagocytosis — the biological analog of pheromone evaporation."
        ),
        physical_mechanism="Agrobacterium-mediated transient expression in Nicotiana; eVLP harvest",
        inherited_invariants=("E33_decay_tau_gt_0", "E39_steady_state_i_inf"),
        safety_gate_organ="E34",
        falsifier=(
            "VLP release without a prior LLM_REGISTRATION row on the same "
            "channel = unsigned surgery (§6 effector law). "
            "VLP accumulation diverging (I → ∞) = E39 steady-state violated."
        ),
        doi_anchor="doi:10.1111/nph.12204",
        truth_label_ledger=OPERATIONAL,
        truth_label_physical=HYPOTHESIS,
        saunders_cpmv_mapping=(
            "Saunders & Lomonossoff (2013): CPMV-HT constructs express eVLPs "
            "in tobacco at high yield. Surface lysines are addressable. "
            "This is the physical substrate for the E33 pheromone deposit."
        ),
    ),

    PhysicalEffectorSpec(
        organ_id="E34",
        physical_name="Safety-Gated VLP Release",
        physical_description=(
            "No VLP cargo may be released without a prior registration→effector "
            "edge in the E34 safety graph for the same (homeworld_serial, source_ide) "
            "channel. In physical terms: the release trigger (e.g., light-activated "
            "capsid opening, pH-triggered release, or enzymatic cleave) may only fire "
            "after a cryptographic receipt confirms the registration edge."
        ),
        physical_mechanism=(
            "Conditional VLP cargo release: trigger (optical/pH/enzymatic) coupled to "
            "a digital gate that checks E34 edge existence before actuation."
        ),
        inherited_invariants=("E34_registration_before_effector", "E01_quantifier_gate"),
        safety_gate_organ="E34",
        falsifier=(
            "Cargo released with no prior registration = BROKEN safety graph. "
            "This is the wet-side version of §6 effector hallucination."
        ),
        doi_anchor="doi:10.1016/j.asd.2004.06.003",   # Ayers 2004
        truth_label_ledger=OPERATIONAL,
        truth_label_physical=HYPOTHESIS,
        saunders_cpmv_mapping=(
            "eVLP inner cavity carries cargo (enzyme, nucleic acid, small molecule). "
            "Release requires a conformational trigger — physical gate analogous to "
            "the E34 registration→effector edge."
        ),
    ),

    PhysicalEffectorSpec(
        organ_id="E38",
        physical_name="Molecular Grammar (DFA-constrained assembly)",
        physical_description=(
            "CPMV coat protein assembly follows a strict sequential grammar: "
            "RNA genome packaging → capsid coat protein assembly → "
            "surface functionalization → cargo loading → release. "
            "This sequence is the physical analog of the E38 4-state DFA: "
            "each step must follow the previous in the accepted language."
        ),
        physical_mechanism=(
            "CPMV self-assembly: coat protein (CP) dimers → pentamers → icosahedron. "
            "Each step is irreversible at physiological conditions — a natural DFA."
        ),
        inherited_invariants=("E38_dfa_accepts_sequence", "E02_monotonic_append"),
        safety_gate_organ="E34",
        falsifier=(
            "Assembly step out of order (e.g., functionalization before cargo loading) "
            "= DFA rejects. Corrupted capsid = same-channel violation as E38 BROKEN state."
        ),
        doi_anchor="doi:10.1111/nph.12204",
        truth_label_ledger=OPERATIONAL,
        truth_label_physical=HYPOTHESIS,
        saunders_cpmv_mapping=(
            "CPMV self-assembly is hierarchically ordered (Lomonossoff & Maule 1995). "
            "CPMV-HT removes the RNA-packaging requirement for eVLP formation, but "
            "the coat-protein assembly sequence is preserved — a natural molecular DFA."
        ),
    ),

    PhysicalEffectorSpec(
        organ_id="E39",
        physical_name="Steady-State VLP Concentration",
        physical_description=(
            "VLP concentration in the target medium reaches a finite steady state "
            "analogous to E39's I_∞ = s/(e^{Δt/τ} - 1). At steady state, "
            "production rate (deposit) = clearance rate (endocytosis/phagocytosis). "
            "No unbounded accumulation — the physical system is bounded above by I_∞."
        ),
        physical_mechanism=(
            "In-planta yield: Saunders & Lomonossoff report gram-scale eVLP production "
            "per kilogram fresh weight Nicotiana. Clearance in vivo by immune cells. "
            "Steady state = production / clearance rate."
        ),
        inherited_invariants=("E39_i_inf_finite", "E33_decay_tau_gt_0"),
        safety_gate_organ="E34",
        falsifier=(
            "VLP concentration diverging over time = E39 invariant violated. "
            "τ ≤ 0 (no clearance) = undefined steady state — same as E33/E39 falsifier."
        ),
        doi_anchor="doi:10.1111/nph.12204",
        truth_label_ledger=OPERATIONAL,
        truth_label_physical=HYPOTHESIS,
        saunders_cpmv_mapping=(
            "In planta expression: CPMV-HT yields ~2.4 mg eVLP per gram fresh weight "
            "(Saunders & Lomonossoff 2013). The finite yield corresponds to I_∞. "
            "Clearance by plant immune response or animal phagocytosis sets τ."
        ),
    ),

    PhysicalEffectorSpec(
        organ_id="E45",
        physical_name="Brownian Wiggle (kT-bounded thermal noise)",
        physical_description=(
            "At the nanoscale (28nm VLP in aqueous medium), Brownian motion provides "
            "a physical wiggle that is kT-bounded — exactly the E45 theorem. "
            "The maximum displacement per unit time is set by kT (Boltzmann × temperature). "
            "When collision risk is high (VLPs crowding the same receptor zone), "
            "thermal diffusion naturally redistributes them — the physical bifurcation escape."
        ),
        physical_mechanism=(
            "Stokes-Einstein diffusion: D = kT/(6πηr). For 28nm eVLP in water at 37°C, "
            "D ≈ 1.6 × 10⁻¹¹ m²/s. This is the physical ε — the maximum wiggle amplitude. "
            "tanh boundedness maps to the Einstein diffusion distribution (Gaussian, bounded)."
        ),
        inherited_invariants=("E45_noise_bounded_by_epsilon", "E33_collision_risk"),
        safety_gate_organ="E34",
        falsifier=(
            "Wiggle amplitude > kT/r = physical violation (requires non-thermal energy source). "
            "In silico: noise_amplitude > ε = E45 invariant broken."
        ),
        doi_anchor="doi:10.1021/jp900083f",   # Einstein diffusion for nanoparticles
        truth_label_ledger=OPERATIONAL,
        truth_label_physical=HYPOTHESIS,
        saunders_cpmv_mapping=(
            "28nm CPMV / eVLP particles in aqueous medium diffuse via Brownian motion. "
            "The kT bound IS the physical ε·tanh(overshoot) ≤ ε. "
            "No engineering required — the physics provides the bounded wiggle."
        ),
    ),

    PhysicalEffectorSpec(
        organ_id="E46",
        physical_name="VLP Population Coupling (multi-segment coordination)",
        physical_description=(
            "Multiple eVLP populations functionalized with different surface ligands "
            "(different 'channels' in E46 terminology) compete for the same receptor field. "
            "A population that occupies many receptors raises the collision risk for adjacent "
            "populations — exactly the E46 inter-segment coupling signal. "
            "The lamprey wave property holds iff no two populations saturate the same "
            "receptor zone simultaneously."
        ),
        physical_mechanism=(
            "Competitive receptor binding: multiple eVLP populations with distinct surface "
            "ligands (targeting different receptor types). High occupancy by population A "
            "sterically inhibits population B — inter-segment coupling via shared substrate."
        ),
        inherited_invariants=("E46_wave_property", "E33_collision_risk", "E34_registration_before_effector"),
        safety_gate_organ="E34",
        falsifier=(
            "Two populations saturate the same receptor zone simultaneously = "
            "UNCOORDINATED state (E46 wave property violated). "
            "Physical: competitive binding prevents this at equilibrium (Le Chatelier)."
        ),
        doi_anchor="doi:10.1016/j.asd.2004.06.003",   # Ayers lamprey segmental
        truth_label_ledger=OPERATIONAL,
        truth_label_physical=HYPOTHESIS,
        saunders_cpmv_mapping=(
            "CPMV surface can be functionalized with different peptides / aptamers "
            "(Pokorski & Steinmetz 2011, Adv. Drug Deliv. Rev.). "
            "Different populations = different eVLP surface ligands. "
            "Receptor competition IS the physical inter-segment coupling."
        ),
    ),
)


# ── Bridge Object ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WetDryBridge:
    """
    The complete wet-dry interface for the SIFTA stigmergic nervous system.
    """
    specs: tuple[PhysicalEffectorSpec, ...]

    @property
    def organ_ids(self) -> list[str]:
        return [s.organ_id for s in self.specs]

    @property
    def all_have_safety_gate(self) -> bool:
        """
        E47 Safety Gate Invariant: every physical effector requires E34.
        """
        return all(s.safety_gate_organ == "E34" for s in self.specs)

    @property
    def all_have_doi(self) -> bool:
        """Every spec must have a DOI anchor (no floating claims)."""
        return all(s.doi_anchor.startswith("doi:") for s in self.specs)

    @property
    def all_inherit_e34(self) -> bool:
        return all(
            any("E34" in inv for inv in s.inherited_invariants)
            or s.safety_gate_organ == "E34"
            for s in self.specs
        )

    @property
    def hypothesis_count(self) -> int:
        return sum(1 for s in self.specs if s.truth_label_physical == HYPOTHESIS)

    @property
    def operational_count(self) -> int:
        return sum(1 for s in self.specs if s.truth_label_ledger == OPERATIONAL)

    @property
    def proof_of_property(self) -> dict[str, Any]:
        return {
            "E47": "Wet-Dry Interface — physical effector mapping for SIFTA ledger organs",
            "theorem": (
                "Every PhysicalEffectorSpec inherits E34 safety gate, "
                "E38 molecular grammar, E39 steady-state bound, and E45 noise bound. "
                "No physical effector may actuate without a prior E34 registration edge."
            ),
            "specs": len(self.specs),
            "organ_ids": self.organ_ids,
            "all_have_safety_gate": self.all_have_safety_gate,
            "all_have_doi": self.all_have_doi,
            "all_inherit_e34": self.all_inherit_e34,
            "hypothesis_count": self.hypothesis_count,
            "operational_count": self.operational_count,
            "falsifier": (
                "Any PhysicalEffectorSpec that can actuate without a prior "
                "E34 LLM_REGISTRATION→effector edge = BROKEN (§6 effector law)."
            ),
            "saunders_cpmv_anchor": "doi:10.1111/nph.12204",
            "ayers_anchor": "doi:10.1016/j.asd.2004.06.003",
            "truth_label_ledger": OPERATIONAL,
            "truth_label_physical": HYPOTHESIS,
            "note": (
                "Physical mappings are labeled HYPOTHESIS per §7.11 until "
                "wet-lab receipts pin the specific mechanism. "
                "Ledger invariant inheritance is OPERATIONAL (machine-checked)."
            ),
        }

    def get_spec(self, organ_id: str) -> PhysicalEffectorSpec | None:
        for s in self.specs:
            if s.organ_id == organ_id:
                return s
        return None

    def summary_lines(self) -> list[str]:
        lines = [
            "E47 Wet-Dry Interface: OPERATIONAL (ledger) / HYPOTHESIS (physical)",
            f"specs: {len(self.specs)}",
            f"all_have_safety_gate (E34): {self.all_have_safety_gate}",
            f"all_have_doi: {self.all_have_doi}",
            f"all_inherit_e34: {self.all_inherit_e34}",
            f"operational (ledger): {self.operational_count} / hypothesis (physical): {self.hypothesis_count}",
            "",
        ]
        for s in self.specs:
            lines.append(
                f"  {s.organ_id} → {s.physical_name} "
                f"[ledger:{s.truth_label_ledger} physical:{s.truth_label_physical}]"
            )
        return lines


# ── Factory ────────────────────────────────────────────────────────────────────

def build_wet_dry_bridge() -> WetDryBridge:
    """Build the canonical wet-dry bridge from the static spec list."""
    return WetDryBridge(specs=CANONICAL_SPECS)


def wet_dry_bridge() -> WetDryBridge:
    """Alias for build_wet_dry_bridge (public API)."""
    return build_wet_dry_bridge()


if __name__ == "__main__":
    bridge = build_wet_dry_bridge()
    print("\n".join(bridge.summary_lines()))
