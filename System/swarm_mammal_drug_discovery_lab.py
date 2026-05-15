#!/usr/bin/env python3
"""SIFTA MAMMAL drug-discovery lab surface.

This is not a clinical model and it does not reproduce MAMMAL benchmarks.
It turns the MAMMAL paper's typed multi-entity prompt idea into a local,
receipt-writing SIFTA research sandbox:

    small molecule + gene expression + protein/antibody
        -> living token field
        -> swimmers emit hypotheses / toxicity / replay receipts
        -> deterministic candidate ranking for visualization

The useful novelty is the field layer: SIFTA can show how disconnected
biomedical evidence types become one local ecology before any model output is
trusted.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from System.swarm_mammal_token_field import (
    MammalTokenField,
    RK_CONTRADICTION,
    RK_HYPOTHESIS,
    RK_REPLAY_REINFORCED,
    RK_TOXICITY_CLUSTER,
    TT_ANTIBODY,
    TT_GENE_EXPRESSION,
    TT_PROTEIN,
    TT_SCALAR_ATTR,
    TT_SMALL_MOLECULE,
    TT_TIME_TAG,
    TT_TOKEN_ATTR,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

TRUTH_LABEL = "STIGMERGIC_MAMMAL_DRUG_DISCOVERY_LAB_V1"
LEDGER_NAME = "mammal_drug_discovery_lab.jsonl"
PAPER_DOI = "10.1038/s44386-026-00047-4"
TRUTH_BOUNDARY = (
    "Research/simulation lab only. Candidate rankings are deterministic SIFTA "
    "token-field hypotheses for visualization and routing. They are not "
    "clinical advice, not dosing guidance, not patient-specific, and not proof "
    "that SIFTA reproduces the MAMMAL paper's wet-lab or benchmark results."
)


@dataclass(frozen=True)
class LabCandidate:
    name: str
    modality: str
    target_hint: str
    expression_context: str
    binding_prior: float
    toxicity_prior: float
    novelty_prior: float
    evidence_prior: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_CANDIDATES = (
    LabCandidate("Carfilzomib", "SMALL_MOLECULE", "proteasome", "solid_tumor_gene_panel", 0.88, 0.42, 0.80, 0.78),
    LabCandidate("Nintedanib", "SMALL_MOLECULE", "VEGFR/FGFR/PDGFR", "angiogenesis_panel", 0.76, 0.34, 0.72, 0.69),
    LabCandidate("Infigratinib", "SMALL_MOLECULE", "FGFR", "FGFR_altered_panel", 0.70, 0.31, 0.70, 0.64),
    LabCandidate("Vemurafenib", "SMALL_MOLECULE", "BRAF", "BRAF_variant_panel", 0.65, 0.28, 0.45, 0.60),
)

GENE_CONTEXT = (
    "MYC_high",
    "TP53_low",
    "EGFR_high",
    "BRAF_var",
    "HER2_high",
    "CDK2_high",
    "PTEN_low",
    "IL6_high",
)

PROTEIN_CONTEXT = (
    "EGFR",
    "HER2",
    "BRAF",
    "proteasome_beta5",
    "TNF-alpha",
    "CDRH3_var",
)

RESEARCH_SPINE = (
    {
        "label": "MAMMAL",
        "claim": "Structured multi-align prompts integrate proteins, small molecules and gene-expression profiles.",
        "doi": PAPER_DOI,
        "url": "https://www.nature.com/articles/s44386-026-00047-4",
    },
    {
        "label": "MoleculeNet",
        "claim": "BBBP and ClinTox are established molecular ML benchmarks used for safety/property prediction.",
        "doi": "10.1039/C7SC02664A",
        "url": "https://pubs.rsc.org/en/content/articlelanding/2017/sc/c7sc02664a",
    },
    {
        "label": "AlphaFold 3",
        "claim": "Structure-centric biomolecular interaction prediction; comparison with MAMMAL needs task-scope qualifiers.",
        "doi": "10.1038/s41586-024-07487-w",
        "url": "https://www.nature.com/articles/s41586-024-07487-w",
    },
)


def _candidate_score(c: LabCandidate, receipt_counts: dict[str, int]) -> dict[str, Any]:
    binding_boost = min(0.18, receipt_counts.get(RK_HYPOTHESIS, 0) * 0.003)
    replay_boost = min(0.08, receipt_counts.get(RK_REPLAY_REINFORCED, 0) * 0.006)
    contradiction_penalty = min(0.12, receipt_counts.get(RK_CONTRADICTION, 0) * 0.006)
    toxicity_penalty = 0.30 * c.toxicity_prior + min(0.08, receipt_counts.get(RK_TOXICITY_CLUSTER, 0) * 0.004)
    score = (
        0.42 * c.binding_prior
        + 0.22 * c.evidence_prior
        + 0.14 * c.novelty_prior
        + binding_boost
        + replay_boost
        - contradiction_penalty
        - toxicity_penalty
    )
    score = max(0.0, min(1.0, score))
    confidence = max(0.08, min(0.92, 0.55 + c.evidence_prior * 0.25 - c.toxicity_prior * 0.10))
    return {
        **c.to_dict(),
        "sifta_field_score": round(score, 4),
        "confidence": round(confidence, 4),
        "components": {
            "binding_boost": round(binding_boost, 4),
            "replay_boost": round(replay_boost, 4),
            "contradiction_penalty": round(contradiction_penalty, 4),
            "toxicity_penalty": round(toxicity_penalty, 4),
        },
        "truth_class": "HYPOTHESIS",
    }


def seed_drug_discovery_field(
    field: MammalTokenField,
    *,
    candidates: Iterable[LabCandidate] = DEFAULT_CANDIDATES,
) -> None:
    """Seed the field with visually separated MAMMAL-style modalities."""
    y0 = 13.5
    for i, c in enumerate(candidates):
        y = y0 - i * 2.7
        field.spawn_token(TT_SMALL_MOLECULE, c.name, x=3.0, y=y, energy=0.94)
        field.spawn_token(TT_TOKEN_ATTR, f"target={c.target_hint}", x=5.0, y=y - 0.4, energy=0.80)
        field.spawn_token(TT_SCALAR_ATTR, f"binding_{c.binding_prior:.2f}", x=6.2, y=y - 0.8, energy=0.82)
        field.spawn_token(TT_SCALAR_ATTR, f"toxicity_{c.toxicity_prior:.2f}", x=6.2, y=y - 1.2, energy=0.74)

    for i, g in enumerate(GENE_CONTEXT):
        field.spawn_token(TT_GENE_EXPRESSION, g, x=12.0 + (i % 2) * 1.8, y=14.0 - (i // 2) * 2.3, energy=0.90)
    for i, p in enumerate(PROTEIN_CONTEXT):
        field.spawn_token(TT_PROTEIN, p, x=20.0 + (i % 2) * 1.3, y=13.5 - (i // 2) * 2.6, energy=0.91)

    field.spawn_token(TT_ANTIBODY, "anti-HER2_CDRH3_candidate", x=21.0, y=4.2, energy=0.88)
    field.spawn_token(TT_TIME_TAG, "paper_context_2026-05-04", x=12.0, y=1.7, energy=0.58)
    field.spawn_token(TT_TOKEN_ATTR, "task=drug_response_rank", x=12.0, y=0.9, energy=0.72)


def run_mammal_drug_discovery_lab(
    *,
    steps: int = 96,
    seed: int = 514,
    write: bool = True,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    field = MammalTokenField(width=24, height=16, seed=seed, lambda_decay=0.004)
    field.install_default_pool(seed=seed)
    seed_drug_discovery_field(field)
    for step in range(max(0, int(steps))):
        if step == max(12, int(steps) // 2):
            field.dream_mode = True
        field.step()

    snap = field.snapshot()
    receipt_counts = dict(snap.get("receipts_by_kind") or {})
    candidates = [_candidate_score(c, receipt_counts) for c in DEFAULT_CANDIDATES]
    candidates.sort(key=lambda r: r["sifta_field_score"], reverse=True)
    for rank, row in enumerate(candidates, start=1):
        row["rank"] = rank

    result = {
        "truth_label": TRUTH_LABEL,
        "truth_class": "OPERATIONAL_SIMULATION+HYPOTHESIS_BIOMEDICAL",
        "truth_boundary": TRUTH_BOUNDARY,
        "paper": {
            "title": "MAMMAL - Molecular Aligned Multi-Modal Architecture and Language for biomedical discovery",
            "doi": PAPER_DOI,
            "url": "https://www.nature.com/articles/s44386-026-00047-4",
        },
        "research_spine": RESEARCH_SPINE,
        "steps": int(steps),
        "seed": int(seed),
        "modalities": ["SMALL_MOLECULE", "GENE_EXPRESSION", "PROTEIN", "ANTIBODY", "SCALAR_ATTR"],
        "pipeline_stages": [
            "target_validation",
            "lead_identification",
            "lead_optimization",
            "safety_triage",
            "repurposing_hypothesis",
        ],
        "biology_bridge_graph": {
            "nodes": [
                "small_molecule",
                "gene_expression",
                "protein_target",
                "antibody_candidate",
                "cell_context",
                "sifta_swimmer_field",
            ],
            "edges": [
                ["small_molecule", "protein_target", "binding hypothesis"],
                ["gene_expression", "cell_context", "context state"],
                ["protein_target", "gene_expression", "pathway pressure"],
                ["antibody_candidate", "protein_target", "biologic binding"],
                ["sifta_swimmer_field", "small_molecule", "pheromone patrol"],
                ["sifta_swimmer_field", "gene_expression", "memory/replay"],
                ["sifta_swimmer_field", "protein_target", "contradiction/toxicity triage"],
            ],
        },
        "field_snapshot": snap,
        "candidates": candidates,
        "top_candidate": candidates[0]["name"] if candidates else "",
        "novelty_claim": (
            "SIFTA novelty is the receipt-writing token ecology and visual field, "
            "not a new validated drug prediction."
        ),
    }
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    result["sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if write:
        state = Path(state_root) if state_root is not None else _STATE
        state.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "kind": "MAMMAL_DRUG_DISCOVERY_LAB",
            "trace_id": str(uuid.uuid4()),
            "truth_label": TRUTH_LABEL,
            "truth_boundary": TRUTH_BOUNDARY,
            "sha256": result["sha256"],
            "payload": result,
        }
        with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
        result["receipt_trace_id"] = row["trace_id"]
    return result


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--steps", type=int, default=96)
    p.add_argument("--seed", type=int, default=514)
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    print(json.dumps(
        run_mammal_drug_discovery_lab(steps=args.steps, seed=args.seed, write=not args.no_write),
        indent=2,
        sort_keys=True,
    ))
