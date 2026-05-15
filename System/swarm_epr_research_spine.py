"""Verified research spine for the SIFTA EPR Stigmergic Widget.

Sibling of `swarm_bell_research_spine.py`. This module is deliberately narrow.
It does not decide physics. It gives Alice and the EPR app a receipt-friendly
list of sources, what each source can support, and what it must not be used
to claim.

The invariant is:

    SIFTA EPR = SIM_ONLY classical contextual analogue.

The simulator can illustrate the EPR thought experiment, the move from EPR
to Bell to CHSH to loophole-free experimental tests, and the geometric
structure of "shared contextual fields" as one classical route to
EPR-correlated outcomes. It cannot prove the physical cause of quantum
nonlocality, and it is not running on actual entangled photons, atoms, or
NV centers. Every loophole-free experimental source listed here is cited
as **physical-reality boundary** — the thing the simulator is allowed to
explain *about* and is forbidden from claiming to *be*.

Why a separate spine (and not just reuse the Bell one)
------------------------------------------------------
- EPR (1935) and Bohm (1951) predate Bell (1964); their citations carry
  different ontological framings (elements of reality, completeness,
  spin-singlet reformulation) than CHSH-era papers.
- EPR-steering (Wiseman 2007, Cavalcanti 2009, Reid 2009) is a strictly
  weaker form of nonclassicality than Bell nonlocality — the EPR widget
  must not conflate it with full Bell violation.
- Loophole-free Bell experiments (Hensen 2015, Giustina 2015, Shalm 2015)
  are the physical-reality anchor: they close locality + detection +
  freedom-of-choice loopholes simultaneously. SIFTA's simulator is
  permitted to *describe* what they did; it is forbidden from *replacing*
  them.
- Multi-particle entanglement (GHZ 1989, Mermin 1990) introduces a class
  of contradictions Bell's two-party inequality cannot express.

Truth labels (§7.11)
--------------------
- `OBSERVED`  — every source URL/DOI is a real, citable artifact.
- `OPERATIONAL` — the spine is importable, the receipt writer is
  deterministic, and the structure round-trips through JSON.
- `ARCHITECT_DOCTRINE` — the *selection* of these ten sources as the
  canonical EPR spine is a judgement call; future Architects may add
  sources, but removals require explicit GO and a covenant note.

Author : Cowork (Claude Opus 4.7, Architect-support lane, 2026-05-11).
Sibling: `System/swarm_bell_research_spine.py` (Cursor, 2026-04-xx).
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TRUTH_LABEL = "SIFTA_EPR_RESEARCH_SPINE_V1"
EPR_ANALOGUE_TRUTH_GUARD = (
    "SIM_ONLY classical contextual analogue: illustrates EPR / Bell / "
    "CHSH / steering / loophole-free experimental landscape and the "
    "geometric structure of shared-field correlations; does not run on "
    "entangled photons, atoms, or NV centers and does not prove the "
    "physical cause of quantum nonlocality."
)


@dataclass(frozen=True)
class EPRResearchSource:
    """One peer-reviewed primary source with explicit support/no-support guards.

    Field meanings
    --------------
    source_id          stable lowercase identifier used in citations.
    title              paper title as published.
    authors            authors list, comma separated, last-name-first.
    year               year of publication.
    venue              journal and locator (volume, page, etc.).
    url                stable URL (preferred: publisher abstract page or
                       DOI link).
    doi                DOI if assigned; empty string if not.
    source_class       one of:
                           primary_foundation       — EPR / Bohm / Bell-era
                           experimental_landmark    — first / loophole-free
                                                       experimental test
                           primary_steering         — EPR-steering theory
                           primary_multipartite     — GHZ / Mermin
                           primary_review           — colloquium-style review
                           classical_analogue       — fluid / lattice analog
                           preprint                 — arXiv only, no peer review yet
    supports           one short sentence: what the SIFTA EPR app may
                       cite this source FOR.
    does_not_support   one short sentence: what the SIFTA EPR app must
                       NOT use this source to imply.
    """

    source_id: str
    title: str
    authors: str
    year: int
    venue: str
    url: str
    doi: str
    source_class: str
    supports: str
    does_not_support: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


VERIFIED_RESEARCH_SPINE: tuple[EPRResearchSource, ...] = (
    EPRResearchSource(
        source_id="epr_1935",
        title=(
            "Can Quantum-Mechanical Description of Physical Reality "
            "Be Considered Complete?"
        ),
        authors="A. Einstein, B. Podolsky, N. Rosen",
        year=1935,
        venue="Physical Review 47, 777",
        url="https://journals.aps.org/pr/abstract/10.1103/PhysRev.47.777",
        doi="10.1103/PhysRev.47.777",
        source_class="primary_foundation",
        supports=(
            "The original EPR argument, elements-of-reality definition, "
            "and the locality/realism premises that later Bell tests "
            "experimentally constrained."
        ),
        does_not_support=(
            "A claim that the SIFTA shared-field simulator restores "
            "elements of reality as defined by Einstein, or that the "
            "original EPR conclusion is the modern consensus view."
        ),
    ),
    EPRResearchSource(
        source_id="bohm_1951",
        title="Quantum Theory (spin-singlet reformulation of EPR)",
        authors="D. Bohm",
        year=1951,
        venue="Prentice-Hall (textbook), Ch. 22",
        url="https://archive.org/details/quantumtheory0000bohm",
        doi="",
        source_class="primary_foundation",
        supports=(
            "The two-spin (singlet-state) reformulation of EPR that "
            "every subsequent Bell-type experiment is built on, and the "
            "introduction of dichotomic spin measurements at variable "
            "axes."
        ),
        does_not_support=(
            "Bohmian (pilot-wave) interpretation as the accepted "
            "physical mechanism, nor classical hidden variables as a "
            "viable account post-Aspect/Hensen."
        ),
    ),
    EPRResearchSource(
        source_id="ghz_1989",
        title=(
            "Going Beyond Bell's Theorem (Greenberger-Horne-Zeilinger "
            "states)"
        ),
        authors="D. M. Greenberger, M. A. Horne, A. Zeilinger",
        year=1989,
        venue=(
            "Bell's Theorem, Quantum Theory, and Conceptions of the "
            "Universe (Kafatos, ed.), Kluwer, p. 69; arXiv:0712.0921"
        ),
        url="https://arxiv.org/abs/0712.0921",
        doi="10.1007/978-94-017-0849-4_10",
        source_class="primary_multipartite",
        supports=(
            "Multi-particle (three-particle) entanglement contradictions "
            "that Bell's two-party inequality cannot express, and the "
            "extension of EPR-style reasoning beyond two parties."
        ),
        does_not_support=(
            "Claiming SIFTA's two-swimmer EPR widget exhibits "
            "GHZ-class contradictions; that requires at least three "
            "correlated parties."
        ),
    ),
    EPRResearchSource(
        source_id="aspect_1982",
        title=(
            "Experimental Realization of Einstein-Podolsky-Rosen-Bohm "
            "Gedankenexperiment: A New Violation of Bell's Inequalities"
        ),
        authors="A. Aspect, P. Grangier, G. Roger",
        year=1982,
        venue="Physical Review Letters 49, 91",
        url="https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.49.91",
        doi="10.1103/PhysRevLett.49.91",
        source_class="experimental_landmark",
        supports=(
            "The first widely-cited experimental violation of a Bell "
            "inequality with time-varying analyzers, fixing the "
            "experimental ground-truth that any classical-locality "
            "account must contend with."
        ),
        does_not_support=(
            "That Aspect 1982 closed the locality, detection, or "
            "freedom-of-choice loopholes simultaneously; that came "
            "with the 2015 loophole-free experiments."
        ),
    ),
    EPRResearchSource(
        source_id="hensen_2015_loophole_free",
        title=(
            "Loophole-free Bell inequality violation using electron "
            "spins separated by 1.3 kilometres"
        ),
        authors=(
            "B. Hensen, H. Bernien, A. E. Dreau, A. Reiserer, N. Kalb, "
            "M. S. Blok, J. Ruitenberg, R. F. L. Vermeulen, R. N. "
            "Schouten, C. Abellan, W. Amaya, V. Pruneri, M. W. "
            "Mitchell, M. Markham, D. J. Twitchen, D. Elkouss, S. "
            "Wehner, T. H. Taminiau, R. Hanson"
        ),
        year=2015,
        venue="Nature 526, 682",
        url="https://www.nature.com/articles/nature15759",
        doi="10.1038/nature15759",
        source_class="experimental_landmark",
        supports=(
            "Simultaneous closure of the locality and detection "
            "loopholes for a Bell test using NV-center electron spins "
            "separated by 1.3 km — the physical-reality boundary."
        ),
        does_not_support=(
            "Any claim that a classical shared-field simulator "
            "replicates or supersedes the Hensen et al. experimental "
            "result."
        ),
    ),
    EPRResearchSource(
        source_id="giustina_2015_significant_loophole_free",
        title=(
            "Significant-Loophole-Free Test of Bell's Theorem with "
            "Entangled Photons"
        ),
        authors=(
            "M. Giustina, M. A. M. Versteegh, S. Wengerowsky, J. "
            "Handsteiner, A. Hochrainer, K. Phelan, F. Steinlechner, "
            "J. Kofler, J.-Å. Larsson, C. Abellán, W. Amaya, V. "
            "Pruneri, M. W. Mitchell, J. Beyer, T. Gerrits, A. E. "
            "Lita, L. K. Shalm, S. W. Nam, T. Scheidl, R. Ursin, B. "
            "Wittmann, A. Zeilinger"
        ),
        year=2015,
        venue="Physical Review Letters 115, 250401",
        url=(
            "https://journals.aps.org/prl/abstract/10.1103/"
            "PhysRevLett.115.250401"
        ),
        doi="10.1103/PhysRevLett.115.250401",
        source_class="experimental_landmark",
        supports=(
            "Loophole-free Bell test with entangled photons, "
            "independently confirming Hensen 2015 with a different "
            "physical platform on the same year."
        ),
        does_not_support=(
            "That all detection-efficiency concerns are now "
            "irrelevant in arbitrary follow-up experiments; each new "
            "platform must re-prove its loophole closure."
        ),
    ),
    EPRResearchSource(
        source_id="shalm_2015_strong_loophole_free",
        title="Strong Loophole-Free Test of Local Realism",
        authors=(
            "L. K. Shalm, E. Meyer-Scott, B. G. Christensen, P. "
            "Bierhorst, M. A. Wayne, M. J. Stevens, T. Gerrits, S. "
            "Glancy, D. R. Hamel, M. S. Allman, K. J. Coakley, S. D. "
            "Dyer, C. Hodge, A. E. Lita, V. B. Verma, C. Lambrocco, "
            "E. Tortorici, A. L. Migdall, Y. Zhang, D. R. Kumor, W. "
            "H. Farr, F. Marsili, M. D. Shaw, J. A. Stern, C. Abellán, "
            "W. Amaya, V. Pruneri, T. Jennewein, M. W. Mitchell, P. "
            "G. Kwiat, J. C. Bienfang, R. P. Mirin, E. Knill, S. W. Nam"
        ),
        year=2015,
        venue="Physical Review Letters 115, 250402",
        url=(
            "https://journals.aps.org/prl/abstract/10.1103/"
            "PhysRevLett.115.250402"
        ),
        doi="10.1103/PhysRevLett.115.250402",
        source_class="experimental_landmark",
        supports=(
            "Third independent 2015 loophole-free test (NIST-led), "
            "with statistical strength sufficient to reject local "
            "realism to very high confidence."
        ),
        does_not_support=(
            "That a high-statistical Bell test alone settles every "
            "philosophical question about EPR's elements of reality."
        ),
    ),
    EPRResearchSource(
        source_id="wiseman_2007_steering",
        title=(
            "Steering, Entanglement, Nonlocality, and the "
            "Einstein-Podolsky-Rosen Paradox"
        ),
        authors="H. M. Wiseman, S. J. Jones, A. C. Doherty",
        year=2007,
        venue="Physical Review Letters 98, 140402",
        url=(
            "https://journals.aps.org/prl/abstract/10.1103/"
            "PhysRevLett.98.140402"
        ),
        doi="10.1103/PhysRevLett.98.140402",
        source_class="primary_steering",
        supports=(
            "The formal definition of EPR-steering as a strictly "
            "weaker form of nonclassicality than Bell nonlocality but "
            "strictly stronger than entanglement, and the hierarchy "
            "Entangled ⊃ Steerable ⊃ Bell-nonlocal."
        ),
        does_not_support=(
            "Equating SIFTA's two-swimmer correlations to "
            "EPR-steering without an explicit, measured steering "
            "inequality violation."
        ),
    ),
    EPRResearchSource(
        source_id="cavalcanti_2009_steering_criteria",
        title=(
            "Experimental criteria for steering and the "
            "Einstein-Podolsky-Rosen paradox"
        ),
        authors=(
            "E. G. Cavalcanti, S. J. Jones, H. M. Wiseman, M. D. Reid"
        ),
        year=2009,
        venue="Physical Review A 80, 032112",
        url=(
            "https://journals.aps.org/pra/abstract/10.1103/"
            "PhysRevA.80.032112"
        ),
        doi="10.1103/PhysRevA.80.032112",
        source_class="primary_steering",
        supports=(
            "Operational, experimentally testable criteria that "
            "distinguish EPR-steering from generic entanglement, with "
            "explicit inequality forms used in continuous-variable "
            "experiments."
        ),
        does_not_support=(
            "Treating any single observed correlation as a steering "
            "violation; the criterion must be explicitly stated and "
            "tested."
        ),
    ),
    EPRResearchSource(
        source_id="reid_2009_colloquium_cv_epr",
        title=(
            "Colloquium: The Einstein-Podolsky-Rosen paradox: From "
            "concepts to applications"
        ),
        authors=(
            "M. D. Reid, P. D. Drummond, W. P. Bowen, E. G. "
            "Cavalcanti, P. K. Lam, H. A. Bachor, U. L. Andersen, G. "
            "Leuchs"
        ),
        year=2009,
        venue="Reviews of Modern Physics 81, 1727",
        url=(
            "https://journals.aps.org/rmp/abstract/10.1103/"
            "RevModPhys.81.1727"
        ),
        doi="10.1103/RevModPhys.81.1727",
        source_class="primary_review",
        supports=(
            "A peer-reviewed survey of the EPR paradox from 1935 "
            "through continuous-variable experiments, including the "
            "modern operational vocabulary and key inequalities."
        ),
        does_not_support=(
            "Reading a review article as primary evidence; primary "
            "claims must be backed by the underlying experimental or "
            "theoretical papers it cites."
        ),
    ),
)


QUARANTINED_SOURCE_NOTES: tuple[dict[str, str], ...] = (
    {
        "source_id": "stigmergic_epr_dissolution_2026",
        "status": "internal_doctrine_no_external_cite",
        "reason": (
            "Phrases such as 'EPR paradox dissolved via stigmergic "
            "swimmers' originate inside the SIFTA project; they have "
            "no peer-reviewed external source as of "
            "2026-05-11. They are ARCHITECT_DOCTRINE language only "
            "and must not be cited as physics consensus."
        ),
        "rule": (
            "Permitted as internal design language in widget UI or "
            "Architect docs; forbidden in any external claim, paper, "
            "or press communication implying physics consensus."
        ),
    },
    {
        "source_id": "any_loophole_free_replica_claim",
        "status": "explicit_forbidden",
        "reason": (
            "The SIFTA EPR widget is a classical simulation. It does "
            "not close detection, locality, or freedom-of-choice "
            "loopholes."
        ),
        "rule": (
            "Do not, under any framing, claim or imply that running "
            "the SIFTA EPR widget reproduces or supersedes Hensen, "
            "Giustina, or Shalm 2015 results."
        ),
    },
)


# ── Public read API ─────────────────────────────────────────────────────────
def verified_research_spine() -> list[dict[str, Any]]:
    return [source.as_dict() for source in VERIFIED_RESEARCH_SPINE]


def verified_source_ids() -> list[str]:
    return [source.source_id for source in VERIFIED_RESEARCH_SPINE]


def quarantined_sources() -> list[dict[str, str]]:
    return [dict(note) for note in QUARANTINED_SOURCE_NOTES]


def research_spine_payload() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "truth_guard": EPR_ANALOGUE_TRUTH_GUARD,
        "verified_sources": verified_research_spine(),
        "quarantined_sources": quarantined_sources(),
        "source_count": len(VERIFIED_RESEARCH_SPINE),
        "quarantine_count": len(QUARANTINED_SOURCE_NOTES),
    }


def write_research_spine_receipt(
    *,
    state_root: Path | None = None,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Append a hash-stamped receipt row to the EPR research spine ledger."""
    root = (
        state_root
        or Path(__file__).resolve().parent.parent / ".sifta_state"
    )
    out = receipt_path or root / "epr_research_spine_receipts.jsonl"
    payload = research_spine_payload()
    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": "EPR_RESEARCH_SPINE_RECEIPT",
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
    "EPRResearchSource",
    "EPR_ANALOGUE_TRUTH_GUARD",
    "QUARANTINED_SOURCE_NOTES",
    "TRUTH_LABEL",
    "VERIFIED_RESEARCH_SPINE",
    "quarantined_sources",
    "research_spine_payload",
    "verified_research_spine",
    "verified_source_ids",
    "write_research_spine_receipt",
]
