"""Verified research spine for the SIFTA Bell/contextuality simulator.

This module is deliberately narrow.  It does not decide physics.  It gives
Alice and the Bell app a receipt-friendly list of sources, what each source can
support, and what it must not be used to claim.

The invariant is:

    SIFTA Bell = SIM_ONLY classical contextual analogue.

The simulator can show how a shared, persistent field breaks the assumptions
behind Bell/CHSH bounds.  It cannot prove the physical cause of quantum
nonlocality on real hardware.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TRUTH_LABEL = "SIFTA_BELL_RESEARCH_SPINE_V1"
BELL_ANALOGUE_TRUTH_GUARD = (
    "SIM_ONLY classical contextual analogue: supports mechanism exploration; "
    "does not prove the physical cause of quantum Bell violations."
)


@dataclass(frozen=True)
class BellResearchSource:
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


VERIFIED_RESEARCH_SPINE: tuple[BellResearchSource, ...] = (
    BellResearchSource(
        source_id="bell_1964",
        title="On the Einstein Podolsky Rosen paradox",
        authors="J. S. Bell",
        year=1964,
        venue="Physics Physique Fizika 1, 195",
        url="https://journals.aps.org/ppf/abstract/10.1103/PhysicsPhysiqueFizika.1.195",
        doi="10.1103/PhysicsPhysiqueFizika.1.195",
        source_class="primary_foundation",
        supports="Bell/local-hidden-variable baseline and the reason CHSH controls are necessary.",
        does_not_support="Any claim that a classical simulator has discovered the physical cause of quantum nonlocality.",
    ),
    BellResearchSource(
        source_id="chsh_1969",
        title="Proposed Experiment to Test Local Hidden-Variable Theories",
        authors="J. F. Clauser, M. A. Horne, A. Shimony, R. A. Holt",
        year=1969,
        venue="Physical Review Letters 23, 880",
        url="https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.23.880",
        doi="10.1103/PhysRevLett.23.880",
        source_class="primary_foundation",
        supports="CHSH S statistic, classical bound, and practical Bell-test framing.",
        does_not_support="Equating a SIFTA field simulation with a loophole-free quantum experiment.",
    ),
    BellResearchSource(
        source_id="hall_2010_measurement_dependence",
        title="Local deterministic model of singlet state correlations based on relaxing measurement independence",
        authors="Michael J. W. Hall",
        year=2010,
        venue="Physical Review Letters 105, 250404",
        url="https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.105.250404",
        doi="10.1103/PhysRevLett.105.250404",
        source_class="primary_constraint",
        supports="Measurement-independence relaxation as a known classical route to singlet-like correlations.",
        does_not_support="A claim that measurement dependence is the accepted real mechanism of quantum mechanics.",
    ),
    BellResearchSource(
        source_id="dzhafarov_2021_cbd",
        title="Assumption-Free Derivation of the Bell-Type Criteria of Contextuality/Nonlocality",
        authors="Ehtibar N. Dzhafarov",
        year=2021,
        venue="Entropy 23(11), 1543",
        url="https://pubmed.ncbi.nlm.nih.gov/34828239/",
        doi="10.3390/e23111543",
        source_class="primary_contextuality_method",
        supports="Contextuality-by-default framing and assumption-aware Bell criteria.",
        does_not_support="Treating all contextual classical systems as quantum systems.",
    ),
    BellResearchSource(
        source_id="sulis_khan_2023_collective_contextuality",
        title="Contextuality in Collective Intelligence: Not There Yet",
        authors="William Sulis, Ali Khan",
        year=2023,
        venue="Entropy 25(8), 1193",
        url="https://www.mdpi.com/1099-4300/25/8/1193",
        doi="10.3390/e25081193",
        source_class="biology_analogy_control",
        supports="Collective-intelligence contextuality is a plausible test target, but ant-colony simulation did not yet violate the criterion.",
        does_not_support="Claiming biological swarms already prove CHSH-type contextuality.",
    ),
    BellResearchSource(
        source_id="papatryfonos_2024_pilot_wave_bell",
        title="Static Bell test in pilot-wave hydrodynamics",
        authors="K. Papatryfonos, L. Vervoort, A. Nachbin, M. Labousse, J. W. M. Bush",
        year=2024,
        venue="Physical Review Fluids 9, 084001",
        url="https://journals.aps.org/prfluids/abstract/10.1103/PhysRevFluids.9.084001",
        doi="10.1103/PhysRevFluids.9.084001",
        source_class="classical_analogue_primary",
        supports="Classical wave-mediated systems can violate a static Bell test when Bell assumptions are not met.",
        does_not_support="That hydrodynamic or SIFTA analogues are actual quantum entanglement.",
    ),
    BellResearchSource(
        source_id="vieira_2025_physical_significance",
        title="Test of the physical significance of Bell non-locality",
        authors="Carlos Vieira, Ravishankar Ramanathan, Adan Cabello",
        year=2025,
        venue="Nature Communications 16, 4390",
        url="https://www.nature.com/articles/s41467-025-59247-7",
        doi="10.1038/s41467-025-59247-7",
        source_class="primary_constraint",
        supports="Partial relaxations of Bell assumptions can be experimentally constrained; the failed assumption must be specified.",
        does_not_support="That any shared-field simulation automatically becomes a viable hidden-variable theory.",
    ),
    BellResearchSource(
        source_id="contextual_hidden_fields_2025",
        title="Contextual Hidden Fields Preclude the Derivation of Bell-Type Inequalities",
        authors="Louis Vervoort",
        year=2025,
        venue="Quantum Reports 7(3), 29",
        url="https://www.mdpi.com/2624-960X/7/3/29",
        doi="10.3390/quantum7030029",
        source_class="theoretical_bridge",
        supports="A contextual hidden-field framing for why Bell-type derivations can fail.",
        does_not_support="Settled consensus physics or proof that SIFTA has found the real underlying field.",
    ),
    BellResearchSource(
        source_id="waegell_mcqueen_2025_superdeterminism_space",
        title="From statistical dependence to the space of possible superdeterministic theories",
        authors="Mordecai Waegell, Kelvin J. McQueen",
        year=2025,
        venue="European Journal for Philosophy of Science 15, 56",
        url="https://link.springer.com/article/10.1007/s13194-025-00693-x",
        doi="10.1007/s13194-025-00693-x",
        source_class="classification_constraint",
        supports="Classification of statistical-independence violations and superdeterministic theory space.",
        does_not_support="Calling every contextual shared-field model superdeterministic without further analysis.",
    ),
    BellResearchSource(
        source_id="waegell_2026_measurement_contextuality",
        title="On measurement, superdeterminism, free will, and contextuality",
        authors="Mordecai Waegell",
        year=2026,
        venue="arXiv:2604.00311",
        url="https://arxiv.org/abs/2604.00311",
        doi="",
        source_class="preprint_classification",
        supports="Ontic-state and response-function language for classifying contextual/superdeterministic explanations.",
        does_not_support="Peer-reviewed confirmation as of this source-spine version.",
    ),
)


QUARANTINED_SOURCE_NOTES: tuple[dict[str, str], ...] = (
    {
        "source_id": "eqfi_academia_2025",
        "status": "unverified_quarantine",
        "reason": (
            "Web/source search did not resolve a stable peer-reviewed or primary source "
            "for 'EQFI / Eusocial Quantum Field Intelligence' as of 2026-05-11."
        ),
        "rule": "Do not use as proof-bearing support until a stable source URL and authorship are verified.",
    },
)


def verified_research_spine() -> list[dict[str, Any]]:
    return [source.as_dict() for source in VERIFIED_RESEARCH_SPINE]


def verified_source_ids() -> list[str]:
    return [source.source_id for source in VERIFIED_RESEARCH_SPINE]


def quarantined_sources() -> list[dict[str, str]]:
    return [dict(note) for note in QUARANTINED_SOURCE_NOTES]


def research_spine_payload() -> dict[str, Any]:
    return {
        "truth_label": TRUTH_LABEL,
        "truth_guard": BELL_ANALOGUE_TRUTH_GUARD,
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
    root = state_root or Path(__file__).resolve().parent.parent / ".sifta_state"
    out = receipt_path or root / "bell_research_spine_receipts.jsonl"
    payload = research_spine_payload()
    row = {
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": "BELL_RESEARCH_SPINE_RECEIPT",
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
    "BELL_ANALOGUE_TRUTH_GUARD",
    "BellResearchSource",
    "QUARANTINED_SOURCE_NOTES",
    "TRUTH_LABEL",
    "VERIFIED_RESEARCH_SPINE",
    "quarantined_sources",
    "research_spine_payload",
    "verified_research_spine",
    "verified_source_ids",
    "write_research_spine_receipt",
]
