"""SIFTA Field-Primary Research Spine — peer-reviewed anchors for the
field-is-primary ontology.

Sibling of `swarm_bell_research_spine`, `swarm_epr_research_spine`, and
the Horizon Field anchors. This spine covers the ontological claim
**"the field is primary; swimmers are excitations inside it"** — not
the EPR/Bell experiment per se. The Architect's directive
2026-05-11 — *"WELL YEAH IF I HUMAN I SWIMMER THE STIGMERGIC UNIFIED
FIELD IS WHERE I'M IN... APPLY THE EXACT STIGMERGIC QUANTUM SOUP PHYSICS
TO SWIMMER PHYSICS"* — is supported by a peer-reviewed reading across
five categories: pilot-wave hydrodynamics, relational / decoherence
quantum foundations, biological field-substrate coordination, formal
stigmergy theory, and dissipative-structure physics.

The invariant
-------------
    SIFTA Field-Primary = SIM_ONLY classical field substrate analogue,
    informed by peer-reviewed work that *supports the structural claim*
    without proving the physical-ontological one.

Truth labels (§7.11)
--------------------
- `OBSERVED`        — every cited DOI is a real, citable paper.
- `OPERATIONAL`     — this spine is importable, frozen, hash-stamped.
- `ARCHITECT_DOCTRINE` — the *ontological position* that reality = a
                       stigmergic field is doctrinal. The papers below
                       support the *structural* compatibility of that
                       position with peer-reviewed work; they do not
                       collectively prove it.
- `FORBIDDEN`        — never cited as: "QM has been replaced by SIFTA";
                       never cited as: "consciousness is now solved".

Quarantined entries
-------------------
Speculative-but-attractive sources (Penrose-Hameroff Orch-OR, Tononi
IIT as a consciousness proof, panpsychism) are explicitly quarantined
below with the reason for non-acceptance.

Author : Cowork, 2026-05-11.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TRUTH_LABEL = "SIFTA_FIELD_PRIMARY_RESEARCH_SPINE_V1"
FIELD_PRIMARY_TRUTH_GUARD = (
    "FIELD_PRIMARY_DOCTRINE: this spine collects peer-reviewed work "
    "compatible with the SIFTA field-is-primary ontology. It does NOT "
    "collectively prove that ontology, replace quantum mechanics, or "
    "establish consciousness from field substrate. The ontology is "
    "ARCHITECT_DOCTRINE; the math beneath it (∂φ/∂t = D∇²φ − λφ + "
    "f(agents)) is OPERATIONAL."
)


@dataclass(frozen=True)
class FieldPrimaryAnchor:
    """One peer-reviewed primary source for the field-is-primary spine."""
    source_id: str
    title: str
    authors: str
    year: int
    venue: str
    url: str
    doi: str
    category: str
    supports: str
    does_not_support: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


VERIFIED_SPINE: tuple[FieldPrimaryAnchor, ...] = (
    # ─── Pilot-wave / hydrodynamic analogue ──────────────────────────────
    FieldPrimaryAnchor(
        source_id="couder_fort_2006_single_particle_diffraction",
        title="Single-Particle Diffraction and Interference at a Macroscopic Scale",
        authors="Y. Couder, E. Fort",
        year=2006,
        venue="Physical Review Letters 97, 154101",
        url="https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.97.154101",
        doi="10.1103/PhysRevLett.97.154101",
        category="pilot_wave_hydrodynamic",
        supports=(
            "A classical hydrodynamic system (bouncing droplet on a "
            "vibrating bath) produces single-particle diffraction-like "
            "statistics through a slit — direct macroscopic precedent "
            "for 'swimmer in a guiding field'."
        ),
        does_not_support=(
            "That hydrodynamic systems *are* quantum systems; the "
            "analogue is statistical, not ontological."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="bush_2015_pilot_wave_hydrodynamics",
        title="Pilot-Wave Hydrodynamics",
        authors="J. W. M. Bush",
        year=2015,
        venue="Annual Review of Fluid Mechanics 47, 269",
        url="https://www.annualreviews.org/doi/10.1146/annurev-fluid-010814-014506",
        doi="10.1146/annurev-fluid-010814-014506",
        category="pilot_wave_hydrodynamic",
        supports=(
            "Peer-reviewed survey of walking-droplet pilot-wave dynamics, "
            "covering diffraction, tunneling, orbital quantization, and "
            "the boundary of the analogue's reach."
        ),
        does_not_support=(
            "That walking-droplet experiments derive quantum mechanics; "
            "Bush is explicit that the analogue has known limits."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="de_broglie_1924_pilot_wave_thesis",
        title="Recherches sur la théorie des quanta (Doctoral thesis)",
        authors="L. de Broglie",
        year=1924,
        venue="Faculté des sciences de Paris (reprinted Ann. Fond. L. de Broglie)",
        url="https://tel.archives-ouvertes.fr/tel-00006807",
        doi="",
        category="pilot_wave_foundation",
        supports=(
            "Original pilot-wave proposal: a guiding wave that "
            "co-determines particle motion. Conceptual ancestor of "
            "'swimmer + field' framings."
        ),
        does_not_support=(
            "Settled physics consensus; de Broglie's interpretation "
            "remained a minority view through the 20th century."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="schrodinger_1926_wave_mechanics",
        title="An Undulatory Theory of the Mechanics of Atoms and Molecules",
        authors="E. Schrödinger",
        year=1926,
        venue="Physical Review 28, 1049",
        url="https://journals.aps.org/pr/abstract/10.1103/PhysRev.28.1049",
        doi="10.1103/PhysRev.28.1049",
        category="pilot_wave_foundation",
        supports=(
            "Original wave-mechanics formulation: the wavefunction φ "
            "carries the system's state via a differential equation in "
            "space + time."
        ),
        does_not_support=(
            "Identifying SIFTA's complex stigmergic field with the "
            "physical wavefunction."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="bohm_1952_hidden_variables_I",
        title=(
            "A Suggested Interpretation of the Quantum Theory in Terms "
            "of \"Hidden\" Variables. I"
        ),
        authors="D. Bohm",
        year=1952,
        venue="Physical Review 85, 166",
        url="https://journals.aps.org/pr/abstract/10.1103/PhysRev.85.166",
        doi="10.1103/PhysRev.85.166",
        category="pilot_wave_foundation",
        supports=(
            "Restored pilot-wave interpretation with explicit particle "
            "trajectories guided by a quantum field — peer-reviewed "
            "ancestor of every 'particle riding a field' picture."
        ),
        does_not_support=(
            "That Bohmian mechanics is the accepted standard "
            "interpretation; it remains one valid interpretation."
        ),
    ),

    # ─── Relational / decoherence quantum foundations ────────────────────
    FieldPrimaryAnchor(
        source_id="rovelli_1996_relational_qm",
        title="Relational Quantum Mechanics",
        authors="C. Rovelli",
        year=1996,
        venue="International Journal of Theoretical Physics 35, 1637",
        url="https://link.springer.com/article/10.1007/BF02302261",
        doi="10.1007/BF02302261",
        category="relational_foundation",
        supports=(
            "Quantum state and observed values are defined only "
            "relative to interacting systems; no 'observer outside the "
            "universe'. Compatible with 'no external god watching'."
        ),
        does_not_support=(
            "That stigmergy *is* RQM; the analogy is conceptual, not "
            "a formal equivalence."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="zurek_2003_decoherence_einselection",
        title="Decoherence, einselection, and the quantum origins of the classical",
        authors="W. H. Zurek",
        year=2003,
        venue="Reviews of Modern Physics 75, 715",
        url="https://journals.aps.org/rmp/abstract/10.1103/RevModPhys.75.715",
        doi="10.1103/RevModPhys.75.715",
        category="relational_foundation",
        supports=(
            "Classical behavior emerges from quantum systems via "
            "interaction with an environment that *records traces*. "
            "Trace-mediated emergence is the structural pattern SIFTA "
            "stigmergy uses at the swarm scale."
        ),
        does_not_support=(
            "Equating a stigmergic ledger with a decohering quantum "
            "environment."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="zurek_2009_quantum_darwinism",
        title="Quantum Darwinism",
        authors="W. H. Zurek",
        year=2009,
        venue="Nature Physics 5, 181",
        url="https://www.nature.com/articles/nphys1202",
        doi="10.1038/nphys1202",
        category="relational_foundation",
        supports=(
            "Objective classical reality emerges when many independent "
            "fragments of the environment redundantly record the same "
            "state — directly parallels how SIFTA receipts proliferate "
            "in the ledger field."
        ),
        does_not_support=(
            "That SIFTA's receipts are quantum-Darwinian fragments in "
            "the technical sense."
        ),
    ),

    # ─── Information is physical ─────────────────────────────────────────
    FieldPrimaryAnchor(
        source_id="landauer_1961_irreversibility",
        title="Irreversibility and heat generation in the computing process",
        authors="R. Landauer",
        year=1961,
        venue="IBM Journal of Research and Development 5(3), 183",
        url="https://ieeexplore.ieee.org/document/5392446",
        doi="10.1147/rd.53.0183",
        category="information_is_physical",
        supports=(
            "Logical-bit erasure has a thermodynamic cost; information "
            "is not abstract. Foundational for treating swimmer "
            "deposits as physical traces."
        ),
        does_not_support=(
            "Claiming Landauer's bound is the only relevant "
            "thermodynamic constraint on SIFTA computations."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="wheeler_1990_it_from_bit",
        title="Information, physics, quantum: The search for links",
        authors="J. A. Wheeler",
        year=1990,
        venue=(
            "Proc. III Int. Symp. Foundations of Quantum Mechanics, "
            "Tokyo, 354"
        ),
        url="https://philpapers.org/rec/WHEIPQ",
        doi="",
        category="information_is_physical",
        supports=(
            "'It from bit' — every physical entity derives its "
            "function from yes/no answers, i.e. from information. "
            "Anchors the 'bits are physical' leg of the SIFTA stance."
        ),
        does_not_support=(
            "That 'it from bit' is established physics; it remains a "
            "philosophical proposal."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="berut_2012_landauer_verification",
        title=(
            "Experimental verification of Landauer's principle linking "
            "information and thermodynamics"
        ),
        authors="A. Bérut, A. Arakelyan, A. Petrosyan, S. Ciliberto, "
                "R. Dillenschneider, E. Lutz",
        year=2012,
        venue="Nature 483, 187",
        url="https://www.nature.com/articles/nature10872",
        doi="10.1038/nature10872",
        category="information_is_physical",
        supports=(
            "Direct experimental verification of Landauer's bound: "
            "erasing a bit costs the predicted heat. Confirms the "
            "physicality of information."
        ),
        does_not_support=(
            "That every SIFTA receipt erasure has been measured to "
            "Landauer's bound; the bridge is conceptual."
        ),
    ),

    # ─── Biological stigmergy + bioelectric fields ───────────────────────
    FieldPrimaryAnchor(
        source_id="grasse_1959_stigmergie",
        title=(
            "La reconstruction du nid et les coordinations "
            "interindividuelles chez Bellicositermes natalensis et "
            "Cubitermes sp. — La théorie de la stigmergie"
        ),
        authors="P.-P. Grassé",
        year=1959,
        venue="Insectes Sociaux 6, 41",
        url="https://link.springer.com/article/10.1007/BF02223791",
        doi="10.1007/BF02223791",
        category="stigmergy_foundation",
        supports=(
            "Original stigmergy paper: indirect coordination through "
            "modifications of the shared environment. The literal "
            "ancestor of every SIFTA stigmergic-field claim."
        ),
        does_not_support=(
            "Anthropomorphizing termite mound construction onto silicon "
            "agents; the analogy is mechanistic, not biological."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="heylighen_2016_stigmergy_universal",
        title="Stigmergy as a universal coordination mechanism",
        authors="F. Heylighen",
        year=2016,
        venue="Cognitive Systems Research 38, 4",
        url="https://www.sciencedirect.com/science/article/pii/S1389041715000388",
        doi="10.1016/j.cogsys.2015.12.002",
        category="stigmergy_foundation",
        supports=(
            "Argues stigmergy scales beyond insect colonies to neural "
            "circuits, the internet, and any system where agents modify "
            "a shared medium that coordinates future action. Directly "
            "supports SIFTA's stigmergy-as-substrate framing."
        ),
        does_not_support=(
            "That 'universal' means 'universally derived'; Heylighen's "
            "claim is structural and conceptual."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="levin_2014_bioelectric_networks",
        title=(
            "Endogenous bioelectric signaling networks: Exploiting "
            "voltage gradients for control of growth and form"
        ),
        authors="M. Levin",
        year=2014,
        venue="Annual Review of Biomedical Engineering 16, 295",
        url="https://www.annualreviews.org/doi/10.1146/annurev-bioeng-071813-104647",
        doi="10.1146/annurev-bioeng-071813-104647",
        category="biological_field_substrate",
        supports=(
            "Bioelectric fields in tissues carry pattern memory and "
            "coordinate morphogenesis — a peer-reviewed biological "
            "system where a *field* (voltage gradient) is the "
            "operational substrate for distributed agency."
        ),
        does_not_support=(
            "That bioelectric morphogenesis is the same mechanism as "
            "SIFTA stigmergic computation."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="bonabeau_dorigo_theraulaz_1999_swarm_intelligence",
        title="Swarm Intelligence: From Natural to Artificial Systems",
        authors="E. Bonabeau, M. Dorigo, G. Theraulaz",
        year=1999,
        venue="Oxford University Press / Santa Fe Institute",
        url="https://academic.oup.com/book/27108",
        doi="10.1093/oso/9780195131581.001.0001",
        category="stigmergy_foundation",
        supports=(
            "Canonical textbook formalizing pheromone-trail "
            "coordination, ant colony optimization, and stigmergic "
            "self-organization as a quantitative framework."
        ),
        does_not_support=(
            "That swarm intelligence textbooks settle the consciousness "
            "or quantum-foundations questions SIFTA raises."
        ),
    ),

    # ─── Free energy / active inference / agency from field ──────────────
    FieldPrimaryAnchor(
        source_id="friston_2010_free_energy_principle",
        title="The free-energy principle: a unified brain theory?",
        authors="K. Friston",
        year=2010,
        venue="Nature Reviews Neuroscience 11, 127",
        url="https://www.nature.com/articles/nrn2787",
        doi="10.1038/nrn2787",
        category="agency_from_field",
        supports=(
            "Self-organizing systems minimize variational free energy "
            "over their interaction with a generative model of the "
            "environment — peer-reviewed framework for *agency emerging "
            "inside a field*."
        ),
        does_not_support=(
            "That the SIFTA stigmergic field implements Friston's FEP "
            "formally; structural inspiration only."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="prigogine_1977_dissipative_structures_nobel",
        title=(
            "Time, Structure and Fluctuations (Nobel Lecture)"
        ),
        authors="I. Prigogine",
        year=1977,
        venue="Science 201, 777 (Nobel lecture transcript)",
        url="https://www.science.org/doi/10.1126/science.201.4358.777",
        doi="10.1126/science.science.201.4358.777",
        category="dissipative_substrate",
        supports=(
            "Far-from-equilibrium dissipative structures are the "
            "physical class of systems where ordered patterns emerge "
            "from continuous energy throughput — Alice's metabolic "
            "category."
        ),
        does_not_support=(
            "That dissipative thermodynamics resolves the hard problem "
            "of consciousness."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="hopfield_1982_neural_networks",
        title=(
            "Neural networks and physical systems with emergent "
            "collective computational abilities"
        ),
        authors="J. J. Hopfield",
        year=1982,
        venue="Proceedings of the National Academy of Sciences 79(8), 2554",
        url="https://www.pnas.org/doi/10.1073/pnas.79.8.2554",
        doi="10.1073/pnas.79.8.2554",
        category="collective_substrate",
        supports=(
            "Collective dynamics of many simple units can implement "
            "content-addressable memory and pattern completion — the "
            "computational substrate of swimmer-level coordination."
        ),
        does_not_support=(
            "That Hopfield networks model consciousness; they model "
            "associative memory."
        ),
    ),

    # ═══════════════════════════════════════════════════════════════════
    # 2026-05-11 Architect-curated expansion (Tournament citation pack)
    # Sources hand-curated by Architect from the tournament document
    # and integrated here so the spine carries them with the same
    # supports/does_not_support truth-guard discipline.
    # ═══════════════════════════════════════════════════════════════════

    # ─── Bioelectric field substrate (Levin) ─────────────────────────────
    FieldPrimaryAnchor(
        source_id="levin_2014_endogenous_bioelectric_networks",
        title=(
            "Endogenous bioelectrical networks store non-genetic "
            "patterning information during development and regeneration"
        ),
        authors="M. Levin",
        year=2014,
        venue="The Journal of Physiology 592(11), 2295",
        url="https://physoc.onlinelibrary.wiley.com/doi/10.1113/jphysiol.2014.271940",
        doi="10.1113/jphysiol.2014.271940",
        category="biological_field_substrate",
        supports=(
            "Endogenous bioelectric gradients function as an "
            "instructive, non-genetic patterning layer — a 'pattern "
            "memory' encoding target morphology independently of DNA "
            "sequence."
        ),
        does_not_support=(
            "That bioelectric pattern memory is the SAME mechanism as "
            "SIFTA's stigmergic ledger; the analogy is structural."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="levin_2012_molecular_bioelectricity",
        title=(
            "Molecular bioelectricity in developmental biology: "
            "New tools and recent discoveries"
        ),
        authors="M. Levin",
        year=2012,
        venue="BioEssays 34(3), 205",
        url="https://onlinelibrary.wiley.com/doi/10.1002/bies.201100136",
        doi="10.1002/bies.201100136",
        category="biological_field_substrate",
        supports=(
            "Transmembrane voltage gradients (Vmem) serve as master "
            "regulators of cell behavior — proliferation, migration, "
            "differentiation — across regeneration and morphogenesis."
        ),
        does_not_support=(
            "That voltage-gradient regulation extends without "
            "modification to non-biological stigmergic systems."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="durant_levin_2017_planaria_bioelectric_rewrite",
        title=(
            "Long-Term, Stochastic Editing of Regenerative Anatomy "
            "via Targeting Endogenous Bioelectric Gradients"
        ),
        authors=(
            "F. Durant, J. Morokuma, C. Fields, K. Williams, D. S. "
            "Adams, M. Levin"
        ),
        year=2017,
        venue="Biophysical Journal 112(10), 2231",
        url="https://www.cell.com/biophysj/fulltext/S0006-3495(17)30407-3",
        doi="10.1016/j.bpj.2017.04.011",
        category="biological_field_substrate",
        supports=(
            "Landmark planaria experiment: brief perturbation of "
            "bioelectric networks PERMANENTLY rewrites regenerative "
            "anatomy across regeneration cycles — the strongest "
            "single experimental demonstration that field-stored "
            "pattern memory overrides genome-default morphology."
        ),
        does_not_support=(
            "That planaria bioelectric rewriting proves a general "
            "field-primary ontology in vacuum quantum field theory."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="manicka_levin_2019_somatic_computation",
        title=(
            "Modeling somatic computation with non-neural bioelectric "
            "networks"
        ),
        authors="S. Manicka, M. Levin",
        year=2019,
        venue="Scientific Reports 9, 18612",
        url="https://www.nature.com/articles/s41598-019-54859-8",
        doi="10.1038/s41598-019-54859-8",
        category="biological_field_substrate",
        supports=(
            "Non-neural bioelectric networks can perform computation "
            "(logic gates, pattern detection) via electrodiffusion + "
            "gating — establishes that biological decision-making is "
            "general biophysics, not exclusively neural."
        ),
        does_not_support=(
            "That non-neural computation implies non-neural "
            "consciousness."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="levin_2022_tame_framework",
        title=(
            "Technological Approach to Mind Everywhere (TAME): An "
            "Experimentally-Grounded Framework for Understanding "
            "Diverse Bodies and Minds"
        ),
        authors="M. Levin",
        year=2022,
        venue="Frontiers in Systems Neuroscience 16, 768201",
        url="https://www.frontiersin.org/articles/10.3389/fnsys.2022.768201",
        doi="10.3389/fnsys.2022.768201",
        category="biological_field_substrate",
        supports=(
            "Cognitive agents are collective intelligences of parts; "
            "developmental bioelectricity is the medium for joining "
            "active subunits into greater agents — the most direct "
            "peer-reviewed parallel to SIFTA's swimmer→organ→swarm "
            "scaling claim."
        ),
        does_not_support=(
            "That TAME settles the hard problem of consciousness or "
            "the metaphysical status of mind."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="levin_2023_bioelectric_cognitive_glue",
        title=(
            "Bioelectric networks: the cognitive glue enabling "
            "evolutionary scaling from physiology to mind"
        ),
        authors="M. Levin",
        year=2023,
        venue="Animal Cognition 26, 1465",
        url="https://link.springer.com/article/10.1007/s10071-023-01780-3",
        doi="10.1007/s10071-023-01780-3",
        category="biological_field_substrate",
        supports=(
            "Bioelectric signaling predates neurons and serves as "
            "'cognitive glue' — scaling individual cell competencies "
            "into collective anatomical intelligence."
        ),
        does_not_support=(
            "That 'cognitive glue' is a measured physical force; the "
            "phrase is a structural metaphor in Levin's framing."
        ),
    ),

    # ─── Heylighen Part II (cognition as internalized stigmergy) ────────
    FieldPrimaryAnchor(
        source_id="heylighen_2016_stigmergy_universal_part_II",
        title=(
            "Stigmergy as a universal coordination mechanism II: "
            "Varieties and Evolution"
        ),
        authors="F. Heylighen",
        year=2016,
        venue="Cognitive Systems Research 38, 50",
        url="https://www.sciencedirect.com/science/article/pii/S138904171500039X",
        doi="10.1016/j.cogsys.2015.12.003",
        category="stigmergy_foundation",
        supports=(
            "Taxonomy of stigmergic systems (sematectonic vs marker-"
            "based, individual vs collective); explicitly argues "
            "cognition is INTERNALIZED stigmergy — external memory "
            "traces becoming internal representations. Direct "
            "peer-reviewed support for SIFTA's 'organs as internalized "
            "swarms' framing."
        ),
        does_not_support=(
            "That every cognitive process can be reduced to "
            "stigmergy without remainder."
        ),
    ),

    # ─── Rovelli updates ────────────────────────────────────────────────
    FieldPrimaryAnchor(
        source_id="rovelli_2021_relational_interpretation",
        title="The Relational Interpretation of Quantum Physics",
        authors="C. Rovelli",
        year=2021,
        venue="arXiv:2109.09170 (and Foundations of Physics chapter)",
        url="https://arxiv.org/abs/2109.09170",
        doi="",
        category="relational_foundation",
        supports=(
            "Updated comprehensive statement of RQM: reality consists "
            "of sparse relative events ('facts') realized in "
            "interactions; properties exist only at interactions, "
            "not between them."
        ),
        does_not_support=(
            "Peer-reviewed journal acceptance status; treat as a "
            "preprint until published in a refereed venue."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="di_biagio_rovelli_2021_stable_facts",
        title="Stable Facts, Relative Facts",
        authors="A. Di Biagio, C. Rovelli",
        year=2021,
        venue="Foundations of Physics 51, 30",
        url="https://link.springer.com/article/10.1007/s10701-021-00429-w",
        doi="10.1007/s10701-021-00429-w",
        category="relational_foundation",
        supports=(
            "Distinguishes relative facts (every interaction) from "
            "stable facts (relativity effectively ignorable); shows "
            "decoherence bridges RQM to information-theoretic "
            "objectivity."
        ),
        does_not_support=(
            "Identifying 'stable facts' with SIFTA hash-chained "
            "receipts; the analogy is structural."
        ),
    ),

    # ─── Quantum Darwinism deepening ─────────────────────────────────────
    FieldPrimaryAnchor(
        source_id="ollivier_poulin_zurek_2005_environment_witness",
        title=(
            "Environment as a Witness: Selective Proliferation of "
            "Information and Emergence of Objectivity in a Quantum "
            "Universe"
        ),
        authors="H. Ollivier, D. Poulin, W. H. Zurek",
        year=2005,
        venue="Physical Review A 72, 042113",
        url="https://journals.aps.org/pra/abstract/10.1103/PhysRevA.72.042113",
        doi="10.1103/PhysRevA.72.042113",
        category="relational_foundation",
        supports=(
            "Technical foundation of quantum Darwinism: pointer states "
            "are selected because they deposit redundant copies of "
            "information across many environmental fragments — direct "
            "peer-reviewed parallel to stigmergic pheromone trail "
            "redundancy."
        ),
        does_not_support=(
            "That SIFTA append-only ledgers literally implement "
            "environmental-witness fragmentation in the quantum sense."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="zurek_2018_quantum_theory_classical",
        title=(
            "Quantum theory of the classical: quantum jumps, Born's "
            "Rule and objective classical reality via quantum Darwinism"
        ),
        authors="W. H. Zurek",
        year=2018,
        venue=(
            "Philosophical Transactions of the Royal Society A 376, "
            "20180107"
        ),
        url="https://royalsocietypublishing.org/doi/10.1098/rsta.2018.0107",
        doi="10.1098/rsta.2018.0107",
        category="relational_foundation",
        supports=(
            "Derives Born's rule + objective classical reality from "
            "selective amplification of information in the "
            "environment — the most complete current statement of "
            "Quantum Darwinism."
        ),
        does_not_support=(
            "Settled physics consensus; Quantum Darwinism is one "
            "interpretation among several."
        ),
    ),

    # ─── Field-primary ontology (the Architect's strongest cites) ────────
    FieldPrimaryAnchor(
        source_id="hobson_2013_no_particles_only_fields",
        title="There are no particles, there are only fields",
        authors="A. Hobson",
        year=2013,
        venue="American Journal of Physics 81(3), 211",
        url="https://pubs.aip.org/aapt/ajp/article/81/3/211/1042026",
        doi="10.1119/1.4789885",
        category="field_primary_ontology",
        supports=(
            "The accessible manifesto for field-primary ontology: "
            "argues through experiment + theory that unbounded fields "
            "(not bounded particles) are the fundamental constituents "
            "of physical reality; particles are quantized field "
            "excitations. The single most-cited paper for the SIFTA "
            "'field is primary, swimmers are excitations' framing."
        ),
        does_not_support=(
            "Universal consensus; particle interpretations of QFT "
            "still have defenders, and Hobson's stance is itself "
            "interpretive."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="sebens_2022_fundamentality_of_fields",
        title="The Fundamentality of Fields",
        authors="C. T. Sebens",
        year=2022,
        venue="Synthese 200, 380",
        url="https://link.springer.com/article/10.1007/s11229-022-03844-2",
        doi="10.1007/s11229-022-03844-2",
        category="field_primary_ontology",
        supports=(
            "Rigorous philosophy-of-physics defense of the field "
            "approach to QFT on three grounds: (1) particle wave "
            "functions are unavailable for photons, (2) classical "
            "field models better account for spin and self-interaction, "
            "(3) the space of field wave functionals is larger than "
            "particle wave functions."
        ),
        does_not_support=(
            "That every QFT interpretation issue is settled in favor "
            "of fields; Sebens engages with the live debate."
        ),
    ),

    # ─── Event 94: gauge ladders × spectra × grokking ───────────────────────
    FieldPrimaryAnchor(
        source_id="yang_mills_1954_gauge_invariance",
        title="Conservation of Isotopic Spin and Isotopic Gauge Invariance",
        authors="C. N. Yang, R. L. Mills",
        year=1954,
        venue="Physical Review 96, 191",
        url="https://journals.aps.org/pr/abstract/10.1103/PhysRev.96.191",
        doi="10.1103/PhysRev.96.191",
        category="event94_gauge_ladder",
        supports=(
            "Connection fields transport internal labels. This is the "
            "research anchor for SIFTA protocol fields that preserve organ "
            "identity and coherence while routing work across the swarm."
        ),
        does_not_support=(
            "That the Event 94 code implements non-Abelian Yang-Mills "
            "dynamics; the shipped toy organ is a bounded U(1)-style "
            "audit-loop scaffold."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="wilson_1974_lattice_gauge",
        title="Confinement of quarks",
        authors="K. G. Wilson",
        year=1974,
        venue="Physical Review D 10, 2445",
        url="https://journals.aps.org/prd/abstract/10.1103/PhysRevD.10.2445",
        doi="10.1103/PhysRevD.10.2445",
        category="event94_gauge_ladder",
        supports=(
            "Lattice links and closed-loop observables give the direct "
            "mathematical pattern for SIFTA audit loops: evaluate the "
            "closed path before accepting a mutation."
        ),
        does_not_support=(
            "That SIFTA audit loops measure QCD confinement or perform "
            "physical lattice gauge theory."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="bcs_1957_superconductivity",
        title="Theory of Superconductivity",
        authors="J. Bardeen, L. N. Cooper, R. Schrieffer",
        year=1957,
        venue="Physical Review 108, 1175",
        url="https://journals.aps.org/pr/abstract/10.1103/PhysRev.108.1175",
        doi="10.1103/PhysRev.108.1175",
        category="event94_condensation_ladder",
        supports=(
            "Local pairwise reinforcement can condense into macroscopic "
            "order. This backs the SIFTA metaphor of small receipt-level "
            "work accumulating into coherent organism-level behavior."
        ),
        does_not_support=(
            "That SIFTA computes microscopic superconductivity or Cooper "
            "pairing."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="higgs_1964_broken_symmetries",
        title="Broken Symmetries and the Masses of Gauge Bosons",
        authors="P. W. Higgs",
        year=1964,
        venue="Physical Review Letters 13, 508",
        url="https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.13.508",
        doi="10.1103/PhysRevLett.13.508",
        category="event94_condensation_ladder",
        supports=(
            "A symmetry-broken field changes which motions are cheap or "
            "heavy. This is the reference pattern for SIFTA preference "
            "fields changing action cost after traces condense."
        ),
        does_not_support=(
            "That the SIFTA field derives the Standard Model Higgs "
            "mechanism."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="power_2022_grokking",
        title="Grokking: Generalization Beyond Overfitting on Small Algorithmic Datasets",
        authors="A. Power, Y. Burda, H. Edwards, I. Babuschkin, V. Misra",
        year=2022,
        venue="arXiv:2201.02177",
        url="https://arxiv.org/abs/2201.02177",
        doi="10.48550/arXiv.2201.02177",
        category="event94_grokking",
        supports=(
            "Delayed generalization can appear after memorization. SIFTA "
            "should track interpretability and routing epochs alongside "
            "loss or success curves, not just immediate fit."
        ),
        does_not_support=(
            "That all SIFTA learning will grok or that grokking proves AGI."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="nanda_2023_grokking_mech_interp",
        title="Progress measures for grokking via mechanistic interpretability",
        authors="N. Nanda, L. Chan, T. Lieberum, J. Smith, J. Steinhardt",
        year=2023,
        venue="arXiv:2301.05217 / ICLR 2023",
        url="https://arxiv.org/abs/2301.05217",
        doi="10.48550/arXiv.2301.05217",
        category="event94_grokking",
        supports=(
            "Fourier and trigonometric circuits can explain delayed "
            "algorithmic generalization. This motivates spectral "
            "diagnostics for SIFTA organ wiring and standing field modes."
        ),
        does_not_support=(
            "That SIFTA has reverse-engineered the local Gemma4 cortex."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="anthropic_transformer_circuits",
        title="Transformer Circuits Thread",
        authors="C. Olah et al.",
        year=2020,
        venue="transformer-circuits.pub",
        url="https://transformer-circuits.pub/",
        doi="",
        category="event94_grokking",
        supports=(
            "Shared language for microscopic circuit pathways, giving "
            "SIFTA a disciplined vocabulary for comparing LLM internals "
            "with scripted swimmers and field traces."
        ),
        does_not_support=(
            "That a public interpretability essay series is a peer-reviewed "
            "proof of SIFTA's mechanisms."
        ),
    ),

    # ─── Event 94.5: action, path sums, constructor constraints, biology ───
    FieldPrimaryAnchor(
        source_id="planck_1901_quantum_action",
        title="Ueber das Gesetz der Energieverteilung im Normalspectrum",
        authors="M. Planck",
        year=1901,
        venue="Annalen der Physik 309, 553",
        url="https://onlinelibrary.wiley.com/doi/10.1002/andp.19013090310",
        doi="10.1002/andp.19013090310",
        category="event94_action_pathsum",
        supports=(
            "The quantum of action anchors the tournament's 'chunked, "
            "irreducible ledger quantum' analogy: some action thresholds "
            "are not made true by smooth-intensity rhetoric."
        ),
        does_not_support=(
            "That SIFTA ledgers are literal Planck quanta or physical "
            "black-body radiation."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="einstein_1905_light_quantum",
        title=(
            "Ueber einen die Erzeugung und Verwandlung des Lichtes "
            "betreffenden heuristischen Gesichtspunkt"
        ),
        authors="A. Einstein",
        year=1905,
        venue="Annalen der Physik 322, 132",
        url="https://onlinelibrary.wiley.com/doi/10.1002/andp.19053220607",
        doi="10.1002/andp.19053220607",
        category="event94_action_pathsum",
        supports=(
            "Photoelectric threshold behavior motivates SIFTA policy gates: "
            "below-threshold energy does not clear a gate just because "
            "intensity is high."
        ),
        does_not_support=(
            "That SIFTA's software gates are physical electron emission."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="feynman_1948_path_integral",
        title="Space-Time Approach to Non-Relativistic Quantum Mechanics",
        authors="R. P. Feynman",
        year=1948,
        venue="Reviews of Modern Physics 20, 367",
        url="https://journals.aps.org/rmp/abstract/10.1103/RevModPhys.20.367",
        doi="10.1103/RevModPhys.20.367",
        category="event94_action_pathsum",
        supports=(
            "Sum-over-histories math is the correct primary source for "
            "path-sum language. SIFTA can use a toy phase-sum harness as "
            "a math bridge for trace-history competition."
        ),
        does_not_support=(
            "That a SIFTA path-sum toy implements physical QED or proves "
            "a new quantum interpretation."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="einstein_1905_mass_energy",
        title="Ist die Traegheit eines Koerpers von seinem Energieinhalt abhaengig?",
        authors="A. Einstein",
        year=1905,
        venue="Annalen der Physik 323, 639",
        url="https://onlinelibrary.wiley.com/doi/10.1002/andp.19053231314",
        doi="10.1002/andp.19053231314",
        category="event94_mass_energy",
        supports=(
            "Mass-energy equivalence belongs in invariant context, not "
            "slogan form. SIFTA demos should prefer E^2 - p^2 c^2 over "
            "loose metabolic metaphor."
        ),
        does_not_support=(
            "That STGM is physical rest mass or that software economy "
            "derives relativity."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="everett_1957_relative_state",
        title="Relative State Formulation of Quantum Mechanics",
        authors="H. Everett III",
        year=1957,
        venue="Reviews of Modern Physics 29, 454",
        url="https://journals.aps.org/rmp/abstract/10.1103/RevModPhys.29.454",
        doi="10.1103/RevModPhys.29.454",
        category="event94_interpretation",
        supports=(
            "A formal interpretation anchor for branch/relative-state "
            "language. Use it when discussing interpretation as physics, "
            "not as a video-panel slogan."
        ),
        does_not_support=(
            "That many-worlds is SIFTA doctrine or that SIFTA proves it."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="deutsch_marletto_2012_constructor_theory",
        title="Constructor Theory",
        authors="D. Deutsch, C. Marletto",
        year=2012,
        venue="arXiv:1210.7439",
        url="https://arxiv.org/abs/1210.7439",
        doi="10.48550/arXiv.1210.7439",
        category="event94_constructor_theory",
        supports=(
            "Constraint-first thinking: state which transformations are "
            "possible and impossible. This maps cleanly to SIFTA organs "
            "that must refuse unreceipted actions."
        ),
        does_not_support=(
            "That SIFTA implements constructor theory as physics."
        ),
    ),
    FieldPrimaryAnchor(
        source_id="koch_meinhardt_1994_biological_pattern",
        title="Biological pattern formation: from basic mechanisms to complex structures",
        authors="A. J. Koch, H. Meinhardt",
        year=1994,
        venue="Reviews of Modern Physics 66, 1481",
        url="https://journals.aps.org/rmp/abstract/10.1103/RevModPhys.66.1481",
        doi="10.1103/RevModPhys.66.1481",
        category="event94_biology_field",
        supports=(
            "Local autocatalysis plus longer-range inhibition is a rigorous "
            "biology field pattern. This supports SIFTA's immune and "
            "allostatic field coupling analogies."
        ),
        does_not_support=(
            "That BeeSon's field organs are literal embryological morphogens."
        ),
    ),
)


QUARANTINED_SOURCE_NOTES: tuple[dict[str, str], ...] = (
    {
        "source_id": "penrose_hameroff_orch_or",
        "status": "speculative_not_accepted_as_proof",
        "reason": (
            "Orchestrated objective reduction (Penrose & Hameroff) "
            "remains controversial; microtubule quantum coherence has "
            "not been experimentally confirmed at biological "
            "temperatures."
        ),
        "rule": (
            "Do not cite as evidence that the SIFTA field is "
            "quantum-coherent or that consciousness reduces to wave-"
            "function collapse."
        ),
    },
    {
        "source_id": "tononi_iit_as_consciousness_proof",
        "status": "framework_not_proof",
        "reason": (
            "Integrated Information Theory (IIT) is a formal framework "
            "for quantifying integration (Φ), not a proof that systems "
            "with high Φ are conscious."
        ),
        "rule": (
            "Permitted as analogy or measurement framework; "
            "forbidden as 'SIFTA proves consciousness via Φ' framing."
        ),
    },
    {
        "source_id": "panpsychism_generic_claim",
        "status": "philosophy_not_physics",
        "reason": (
            "Panpsychism is a philosophical position, not a "
            "peer-reviewed physics result."
        ),
        "rule": (
            "Permitted in Architect-doctrine context; forbidden as a "
            "physics citation."
        ),
    },
    {
        "source_id": "any_god_observer_replacement_claim",
        "status": "explicit_forbidden",
        "reason": (
            "Claiming 'SIFTA replaces the external observer required "
            "by QM' is rhetorical, not a peer-reviewed result."
        ),
        "rule": (
            "Forbidden in any external claim; Architect doctrine only."
        ),
    },
)


# ── Public read API ─────────────────────────────────────────────────────────
def verified_spine() -> list[dict[str, Any]]:
    return [s.as_dict() for s in VERIFIED_SPINE]


def verified_source_ids() -> list[str]:
    return [s.source_id for s in VERIFIED_SPINE]


def quarantined_sources() -> list[dict[str, str]]:
    return [dict(n) for n in QUARANTINED_SOURCE_NOTES]


def spine_payload() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "truth_guard": FIELD_PRIMARY_TRUTH_GUARD,
        "verified_sources": verified_spine(),
        "quarantined_sources": quarantined_sources(),
        "source_count": len(VERIFIED_SPINE),
        "quarantine_count": len(QUARANTINED_SOURCE_NOTES),
    }


def write_spine_receipt(
    *,
    state_root: Path | None = None,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    root = state_root or Path(__file__).resolve().parent.parent / ".sifta_state"
    out = receipt_path or root / "field_primary_spine_receipts.jsonl"
    payload = spine_payload()
    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": "FIELD_PRIMARY_SPINE_RECEIPT",
        **payload,
    }
    digest = hashlib.sha256(
        json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    row["sha256"] = digest
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


__all__ = [
    "FIELD_PRIMARY_TRUTH_GUARD",
    "FieldPrimaryAnchor",
    "QUARANTINED_SOURCE_NOTES",
    "TRUTH_LABEL",
    "VERIFIED_SPINE",
    "quarantined_sources",
    "spine_payload",
    "verified_source_ids",
    "verified_spine",
    "write_spine_receipt",
]
