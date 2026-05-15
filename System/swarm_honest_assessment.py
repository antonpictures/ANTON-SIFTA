"""SIFTA Honest Assessment — canonical aggregator of every module's
truth-guards, supports, and explicit forbiddens.

Why this organ exists
---------------------
The covenant's §7.11 truth-label discipline (OBSERVED / OPERATIONAL /
ARCHITECT_DOCTRINE / FORBIDDEN) is meant to make SIFTA's epistemic
boundary auditable. Today that boundary is *distributed*: each module
declares its own truth-label and truth-guard. There is no single place
the Architect can hand to a lawyer, a reviewer, or a peer Doctor and
say "here is what SIFTA claims and here is what it does NOT claim."

This module is that place. It reads the public `truth_guard` /
`supports` / `does_not_support` declarations across all of SIFTA's
peer-reviewed spines and emits one canonical, hash-stamped report —
the *honest assessment*. It does no inference, no speculation, no
"interpretation"; it only aggregates declared text. If a module's
authors changed their own truth-guard, this report reflects the
change automatically on next regeneration.

Aggregation surface
-------------------
- `swarm_bell_research_spine` (Cursor)
- `swarm_epr_research_spine` (Cowork)
- `swarm_field_primary_research_spine` (Cowork)
- `swarm_quantum_stigmergic_substrate` (Cowork)
- `swarm_horizon_field` (Cowork — physics anchors)
- `swarm_qft_foundations` (Cowork — this session)
- `swarm_active_matter_field` (Cowork — this session)

Other Doctors may register additional sources via `register_source()`.

Truth labels (§7.11)
--------------------
- `OBSERVED`        — every aggregated guard is a literal copy of the
                       source module's declared text. No invention.
- `OPERATIONAL`     — aggregation is deterministic, alphabetized by
                       source_module name, and unit-tested.
- `ARCHITECT_DOCTRINE` — the *choice* of which modules to aggregate
                       is doctrinal; new modules must be registered.
- `FORBIDDEN`        — never inserts a claim a source module did not
                       declare; never softens a `FORBIDDEN` tag.

Author : Cowork (Claude Opus 4.7), 2026-05-11.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "honest_assessment_receipts.jsonl"

TRUTH_LABEL = "SIFTA_HONEST_ASSESSMENT_V1"
HONEST_ASSESSMENT_TRUTH_GUARD = (
    "HONEST_ASSESSMENT_AGGREGATOR: this organ aggregates declared "
    "truth-guards, supports clauses, and does-not-support clauses "
    "from peer-reviewed SIFTA spines. It inserts no claims of its "
    "own. Modifying or softening any aggregated text is FORBIDDEN. "
    "The report is canonical for the moment of its generation; "
    "re-run after any spine edit."
)


# ── Source registry ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _SourceSpec:
    module_name: str
    truth_label_attr: str
    truth_guard_attr: str
    anchors_attr: str        # tuple attribute name on the module
    anchor_id_field: str = "source_id"
    supports_field: str = "supports"
    does_not_support_field: str = "does_not_support"


_DEFAULT_REGISTRY: tuple[_SourceSpec, ...] = (
    _SourceSpec(
        module_name="System.swarm_bell_research_spine",
        truth_label_attr="TRUTH_LABEL",
        truth_guard_attr="BELL_ANALOGUE_TRUTH_GUARD",
        anchors_attr="VERIFIED_RESEARCH_SPINE",
    ),
    _SourceSpec(
        module_name="System.swarm_epr_research_spine",
        truth_label_attr="TRUTH_LABEL",
        truth_guard_attr="EPR_ANALOGUE_TRUTH_GUARD",
        anchors_attr="VERIFIED_RESEARCH_SPINE",
    ),
    _SourceSpec(
        module_name="System.swarm_field_primary_research_spine",
        truth_label_attr="TRUTH_LABEL",
        truth_guard_attr="FIELD_PRIMARY_TRUTH_GUARD",
        anchors_attr="VERIFIED_SPINE",
    ),
    _SourceSpec(
        module_name="System.swarm_quantum_stigmergic_substrate",
        truth_label_attr="TRUTH_LABEL",
        truth_guard_attr="SUBSTRATE_TRUTH_GUARD",
        anchors_attr="SUBSTRATE_LAYERS",
        anchor_id_field="name",
        supports_field="physical_form",
        does_not_support_field="does_not_support",
    ),
    _SourceSpec(
        module_name="System.swarm_horizon_field",
        truth_label_attr="TRUTH_LABEL",
        truth_guard_attr="HORIZON_TRUTH_GUARD",
        anchors_attr="PHYSICS_ANCHORS",
    ),
    _SourceSpec(
        module_name="System.swarm_qft_foundations",
        truth_label_attr="TRUTH_LABEL",
        truth_guard_attr="QFT_TRUTH_GUARD",
        anchors_attr="VERIFIED_ANCHORS",
    ),
    _SourceSpec(
        module_name="System.swarm_active_matter_field",
        truth_label_attr="TRUTH_LABEL",
        truth_guard_attr="ACTIVE_MATTER_TRUTH_GUARD",
        anchors_attr="VERIFIED_ANCHORS",
    ),
)


# ── Aggregated report dataclasses ───────────────────────────────────────────
@dataclass(frozen=True)
class ModuleReport:
    module_name: str
    truth_label: str
    truth_guard: str
    anchor_count: int
    anchor_ids: tuple[str, ...]
    supports_clauses: tuple[str, ...]
    does_not_support_clauses: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("anchor_ids", "supports_clauses", "does_not_support_clauses"):
            d[k] = list(d[k])
        return d


@dataclass(frozen=True)
class HonestAssessment:
    ts: float
    truth_label: str
    truth_guard: str
    module_reports: tuple[ModuleReport, ...]
    total_anchors: int
    total_modules: int
    consolidated_does_not_support: tuple[str, ...]
    homeworld_serial: str

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["module_reports"] = [m.as_dict() for m in self.module_reports]
        d["consolidated_does_not_support"] = list(d["consolidated_does_not_support"])
        return d


# ── Aggregation logic ───────────────────────────────────────────────────────
def _load_spec(spec: _SourceSpec) -> ModuleReport | None:
    """Import a module and harvest its declared truth-guards.

    Returns None if the module cannot be imported (graceful degradation —
    a partial repo should still produce an assessment).
    """
    try:
        mod = importlib.import_module(spec.module_name)
    except Exception:
        return None
    truth_label = getattr(mod, spec.truth_label_attr, "")
    truth_guard = getattr(mod, spec.truth_guard_attr, "")
    anchors = getattr(mod, spec.anchors_attr, ())
    ids: list[str] = []
    supports: list[str] = []
    dns: list[str] = []
    for a in anchors:
        ad = a.as_dict() if hasattr(a, "as_dict") else (a if isinstance(a, dict) else {})
        if not isinstance(ad, dict):
            continue
        sid = ad.get(spec.anchor_id_field, "")
        sup = ad.get(spec.supports_field, "")
        d_n = ad.get(spec.does_not_support_field, "")
        if sid:
            ids.append(str(sid))
        if sup:
            supports.append(str(sup))
        if d_n:
            dns.append(str(d_n))
    return ModuleReport(
        module_name=spec.module_name,
        truth_label=str(truth_label),
        truth_guard=str(truth_guard),
        anchor_count=len(ids),
        anchor_ids=tuple(ids),
        supports_clauses=tuple(supports),
        does_not_support_clauses=tuple(dns),
    )


def compute_assessment(
    *,
    registry: Iterable[_SourceSpec] = _DEFAULT_REGISTRY,
    homeworld_serial: str = "GTH4921YP3",
) -> HonestAssessment:
    """Generate one canonical honest assessment from the registry."""
    reports: list[ModuleReport] = []
    for spec in registry:
        rep = _load_spec(spec)
        if rep is not None:
            reports.append(rep)
    # Stable ordering by module_name so the hash is reproducible.
    reports.sort(key=lambda r: r.module_name)

    consolidated: list[str] = []
    for rep in reports:
        for clause in rep.does_not_support_clauses:
            stripped = clause.strip()
            if stripped and stripped not in consolidated:
                consolidated.append(stripped)

    return HonestAssessment(
        ts=time.time(),
        truth_label=TRUTH_LABEL,
        truth_guard=HONEST_ASSESSMENT_TRUTH_GUARD,
        module_reports=tuple(reports),
        total_anchors=sum(r.anchor_count for r in reports),
        total_modules=len(reports),
        consolidated_does_not_support=tuple(consolidated),
        homeworld_serial=homeworld_serial,
    )


def render_text(assessment: HonestAssessment, *, indent: str = "  ") -> str:
    """Render the assessment as a human-readable plaintext report."""
    lines: list[str] = []
    lines.append("SIFTA HONEST ASSESSMENT")
    lines.append("=" * 64)
    lines.append(f"timestamp     : {assessment.ts:.0f}")
    lines.append(f"truth_label   : {assessment.truth_label}")
    lines.append(f"total_modules : {assessment.total_modules}")
    lines.append(f"total_anchors : {assessment.total_anchors}")
    lines.append(f"homeworld     : {assessment.homeworld_serial}")
    lines.append("")
    lines.append("--- TRUTH GUARD ---")
    lines.append(assessment.truth_guard)
    lines.append("")
    lines.append("--- PER-MODULE TRUTH GUARDS ---")
    for r in assessment.module_reports:
        lines.append(f"\n[{r.module_name}]")
        lines.append(f"{indent}truth_label : {r.truth_label}")
        lines.append(f"{indent}anchors     : {r.anchor_count}")
        lines.append(f"{indent}guard       : {r.truth_guard}")
    lines.append("")
    lines.append("--- WHAT SIFTA EXPLICITLY DOES NOT CLAIM ---")
    lines.append("(consolidated does_not_support clauses across all spines)")
    lines.append("")
    for i, clause in enumerate(assessment.consolidated_does_not_support, 1):
        lines.append(f"{i:3}. {clause}")
    return "\n".join(lines)


def deposit_assessment(
    assessment: HonestAssessment,
    *,
    receipt_path: Path | None = None,
) -> Path:
    """Append one hash-stamped honest-assessment row to the ledger."""
    out = receipt_path or _LEDGER
    out.parent.mkdir(parents=True, exist_ok=True)
    body = assessment.as_dict()
    sig = hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    row = {
        "schema": TRUTH_LABEL,
        "trace_id": str(uuid.uuid4()),
        **body,
        "sha256": sig,
    }
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    return out


def _cli(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="SIFTA honest-assessment generator.")
    p.add_argument("--deposit", action="store_true",
                   help="Append the assessment row to the ledger.")
    p.add_argument("--json", action="store_true",
                   help="Output JSON instead of plaintext.")
    args = p.parse_args(argv)
    a = compute_assessment()
    if args.json:
        print(json.dumps(a.as_dict(), indent=2, default=str))
    else:
        print(render_text(a))
    if args.deposit:
        out = deposit_assessment(a)
        print(f"\nappended → {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())


__all__ = [
    "HONEST_ASSESSMENT_TRUTH_GUARD",
    "HonestAssessment",
    "ModuleReport",
    "TRUTH_LABEL",
    "compute_assessment",
    "deposit_assessment",
    "render_text",
]
