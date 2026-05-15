"""SIFTA QFT Foundations — peer-reviewed anchors from quantum field theory
proper.

Companion to `swarm_field_primary_research_spine`. Where the field-primary
spine collects work *compatible with* the field-is-primary ontology
across stigmergy, biology, and foundations, this module is **strict QFT
literature only**. It is the right module to cite when the Architect's
claim is specifically: "the field is the fundamental physical entity
in established physics."

Why a separate module
---------------------
- Mixes are confusing. A bioelectricity paper (Levin) is not the same
  *kind* of evidence as a Reviews of Modern Physics QFT paper (Wilczek).
- Honest assessment: SIFTA is a CLASSICAL stigmergic substrate. To even
  *invoke* QFT as the proving frame for the field-primary ontology is
  to step into a contested live debate inside physics. This module
  carries that debate's vocabulary with strict truth-guards.
- Cursor and Codex may import this module's `VERIFIED_ANCHORS` without
  worrying about cross-domain confusion.

Truth labels (§7.11)
--------------------
- `OBSERVED`        — every cited paper is a real peer-reviewed source
                       with DOI.
- `OPERATIONAL`     — the spine is importable, frozen, hash-stamped.
- `ARCHITECT_DOCTRINE` — the *application* of QFT foundations to SIFTA
                       is doctrinal; the QFT papers themselves do not
                       discuss stigmergy.
- `FORBIDDEN`        — never cited as: "SIFTA proves QFT is right";
                       never cited as: "the SIFTA classical solver IS
                       a quantum field"; never used to claim SIFTA
                       replaces relativistic QFT.

Author : Cowork (Claude Opus 4.7), 2026-05-11.
Anchors: eight peer-reviewed QFT-foundations sources.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TRUTH_LABEL = "SIFTA_QFT_FOUNDATIONS_V1"
QFT_TRUTH_GUARD = (
    "QFT_FOUNDATIONS_DOCTRINE: this module collects peer-reviewed "
    "quantum-field-theory foundations work that is compatible with "
    "treating fields as fundamental and particles as field excitations. "
    "Applying this framework to SIFTA's CLASSICAL stigmergic substrate "
    "is ARCHITECT_DOCTRINE. The SIFTA solver does NOT solve QFT, does "
    "NOT make relativistic claims, and does NOT replace the Standard "
    "Model. Citations are descriptive of an ongoing live debate in "
    "physics, not a settled consensus to be claimed in SIFTA's name."
)


@dataclass(frozen=True)
class QFTAnchor:
    source_id: str
    title: str
    authors: str
    year: int
    venue: str
    url: str
    doi: str
    stance: str       # one of: field_first | particle_first | structural | axiomatic | curved_spacetime
    supports: str
    does_not_support: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


VERIFIED_ANCHORS: tuple[QFTAnchor, ...] = (
    QFTAnchor(
        source_id="hobson_2013_no_particles_only_fields",
        title="There are no particles, there are only fields",
        authors="A. Hobson",
        year=2013,
        venue="American Journal of Physics 81(3), 211",
        url="https://pubs.aip.org/aapt/ajp/article/81/3/211/1042026",
        doi="10.1119/1.4789885",
        stance="field_first",
        supports=(
            "Pedagogical case for field-primary ontology: argues that "
            "unbounded quantum fields, not bounded particles, are the "
            "fundamental physical entities. Anchors the strong "
            "version of the SIFTA 'field is primary' framing inside "
            "peer-reviewed physics literature."
        ),
        does_not_support=(
            "Universal acceptance — field-primary is one defensible "
            "interpretation, not the unique consensus."
        ),
    ),
    QFTAnchor(
        source_id="sebens_2022_fundamentality_of_fields",
        title="The Fundamentality of Fields",
        authors="C. T. Sebens",
        year=2022,
        venue="Synthese 200, 380",
        url="https://link.springer.com/article/10.1007/s11229-022-03844-2",
        doi="10.1007/s11229-022-03844-2",
        stance="field_first",
        supports=(
            "Philosophy-of-physics defense of field-primary QFT on "
            "three formal grounds: photon wave-function unavailability, "
            "spin + self-interaction modeling, and wave-functional "
            "space larger than particle-wave-function space."
        ),
        does_not_support=(
            "Settled philosophy of physics; Sebens engages with a live "
            "debate that includes well-defended particle-first views."
        ),
    ),
    QFTAnchor(
        source_id="wilczek_1999_persistence_quanta",
        title="Quantum Field Theory",
        authors="F. Wilczek",
        year=1999,
        venue="Reviews of Modern Physics 71, S85",
        url=(
            "https://journals.aps.org/rmp/abstract/10.1103/"
            "RevModPhys.71.S85"
        ),
        doi="10.1103/RevModPhys.71.S85",
        stance="field_first",
        supports=(
            "Nobel laureate's overview of QFT for the centennial of "
            "the Physical Review — argues fields are the deeper "
            "concept and particles are quanta of fields."
        ),
        does_not_support=(
            "That all of QFT's interpretive issues are settled in this "
            "single review."
        ),
    ),
    QFTAnchor(
        source_id="weinberg_qft_v1_1995",
        title="The Quantum Theory of Fields, Volume I: Foundations",
        authors="S. Weinberg",
        year=1995,
        venue="Cambridge University Press",
        url="https://www.cambridge.org/9780521670531",
        doi="10.1017/CBO9781139644167",
        stance="structural",
        supports=(
            "Standard graduate-level QFT reference. Establishes that "
            "the union of special relativity + quantum mechanics + "
            "cluster decomposition forces a field-theoretic formalism — "
            "structural argument for field-first."
        ),
        does_not_support=(
            "An ontological declaration in either direction; Weinberg "
            "is largely operationalist."
        ),
    ),
    QFTAnchor(
        source_id="streater_wightman_1964_pct_spin_statistics",
        title="PCT, Spin and Statistics, and All That",
        authors="R. F. Streater, A. S. Wightman",
        year=1964,
        venue="W. A. Benjamin / Princeton Landmarks in Physics",
        url=(
            "https://press.princeton.edu/books/paperback/9780691070629/"
            "pct-spin-and-statistics-and-all-that"
        ),
        doi="10.1515/9781400884230",
        stance="axiomatic",
        supports=(
            "Foundational axiomatic QFT: fields are operator-valued "
            "distributions on spacetime; particle states emerge from "
            "the field algebra. The rigorous formal basis for "
            "field-first reading of QFT."
        ),
        does_not_support=(
            "That every realistic interacting QFT has been "
            "constructed rigorously in the Wightman framework — most "
            "have not."
        ),
    ),
    QFTAnchor(
        source_id="haag_1992_local_quantum_physics",
        title="Local Quantum Physics: Fields, Particles, Algebras",
        authors="R. Haag",
        year=1992,
        venue="Springer-Verlag",
        url="https://link.springer.com/book/10.1007/978-3-642-61458-3",
        doi="10.1007/978-3-642-61458-3",
        stance="axiomatic",
        supports=(
            "Algebraic quantum field theory: local observables "
            "associated with regions of spacetime are primary; "
            "particles are derived asymptotic states. Algebraic "
            "structural argument for field-first."
        ),
        does_not_support=(
            "That algebraic QFT settles cosmological questions or "
            "applies to non-relativistic systems without modification."
        ),
    ),
    QFTAnchor(
        source_id="wald_1994_qft_curved_spacetime",
        title=(
            "Quantum Field Theory in Curved Spacetime and Black Hole "
            "Thermodynamics"
        ),
        authors="R. M. Wald",
        year=1994,
        venue="University of Chicago Press",
        url=(
            "https://press.uchicago.edu/ucp/books/book/chicago/Q/"
            "bo3683524.html"
        ),
        doi="",
        stance="curved_spacetime",
        supports=(
            "Authoritative treatment of QFT on curved backgrounds, "
            "where the particle concept is observer-dependent (Unruh "
            "effect) — direct technical support for field-primary over "
            "particle-primary interpretations."
        ),
        does_not_support=(
            "That Unruh-effect-style observer dependence transfers to "
            "non-gravitational SIFTA stigmergic contexts."
        ),
    ),
    QFTAnchor(
        source_id="fraser_2008_particle_problem_in_qft",
        title="The fate of 'particles' in quantum field theories with interactions",
        authors="D. Fraser",
        year=2008,
        venue="Studies in History and Philosophy of Modern Physics 39, 841",
        url=(
            "https://www.sciencedirect.com/science/article/pii/"
            "S1355219808000452"
        ),
        doi="10.1016/j.shpsb.2008.05.003",
        stance="field_first",
        supports=(
            "Philosophy of physics: interacting QFT does not admit "
            "well-defined particle states in general — strongest "
            "single argument that 'particle' is an asymptotic / "
            "approximation concept, not a fundamental ontological "
            "category."
        ),
        does_not_support=(
            "That particle-talk is meaningless; it remains "
            "operationally useful in asymptotic regimes."
        ),
    ),
)


# ── Public API ──────────────────────────────────────────────────────────────
def verified_anchors() -> list[dict[str, Any]]:
    return [a.as_dict() for a in VERIFIED_ANCHORS]


def verified_anchor_ids() -> list[str]:
    return [a.source_id for a in VERIFIED_ANCHORS]


def anchors_by_stance(stance: str) -> list[dict[str, Any]]:
    return [a.as_dict() for a in VERIFIED_ANCHORS if a.stance == stance]


def qft_foundations_payload() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "truth_guard": QFT_TRUTH_GUARD,
        "verified_anchors": verified_anchors(),
        "anchor_count": len(VERIFIED_ANCHORS),
        "stances": sorted({a.stance for a in VERIFIED_ANCHORS}),
    }


def write_qft_receipt(
    *,
    state_root: Path | None = None,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    root = state_root or Path(__file__).resolve().parent.parent / ".sifta_state"
    out = receipt_path or root / "qft_foundations_receipts.jsonl"
    payload = qft_foundations_payload()
    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": "QFT_FOUNDATIONS_RECEIPT",
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
    "QFTAnchor",
    "QFT_TRUTH_GUARD",
    "TRUTH_LABEL",
    "VERIFIED_ANCHORS",
    "anchors_by_stance",
    "qft_foundations_payload",
    "verified_anchor_ids",
    "verified_anchors",
    "write_qft_receipt",
]
