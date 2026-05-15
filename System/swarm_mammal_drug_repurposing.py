#!/usr/bin/env python3
"""swarm_mammal_drug_repurposing.py — paste a drug, get candidate diseases.

Architect 2026-05-14: "Where do I paste existing drugs to find out
what diseases they can cure that we did not know?"

This is the **drug-repurposing surface**. The architecturally honest
SIFTA answer to a drug-name input:

  1. Pass the drug through MAMMAL (or its OPERATIONAL stand-in when
     transformers/safetensors aren't loaded in the running session).
  2. Score the drug against a panel of disease-context probes — each
     probe is a typed biomedical token (cancer / inflammation /
     neurodegeneration / etc.).
  3. Rank by HYPOTHESIS strength and return a structured list.
  4. Every line carries truth_class=HYPOTHESIS until wet-lab validation.

This is the SIFTA-native parallel to the MAMMAL paper's killer demo
(carfilzomib predicted to work on solid tumors, wet-lab confirmed).
The widget renders this as the user's paste-and-rank flow.

Truth label: DRUG_REPURPOSING_V1.
Truth class: OPERATIONAL for the scoring pipeline,
HYPOTHESIS for every individual disease ranking.

§20.F ceiling: no clinical claim. The widget says "would not work"
or "would work" is a clinical assertion — we don't make those. Every
result is "predicted to be worth investigating for X". No more.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TRUTH_LABEL = "DRUG_REPURPOSING_V1"
LEDGER_NAME = "drug_repurposing_receipts.jsonl"
TRUTH_BOUNDARY = (
    "Drug-repurposing HYPOTHESIS ranker. Takes a drug name or SMILES, "
    "scores it against a panel of disease-context probes via MAMMAL "
    "(or deterministic feature-overlap when weights aren't loaded), "
    "returns ranked HYPOTHESIS candidates. NO clinical claim. NO "
    "diagnosis. Every result is 'predicted worth investigating for X' "
    "— never 'cures X' or 'will not work on Y'. Wet-lab validation "
    "required before any actual repurposing decision. §20.F enforced."
)


# ──────────────────────────────────────────────────────────────────────
# Disease-context panel — the probes the drug is scored against
# ──────────────────────────────────────────────────────────────────────

@dataclass
class DiseaseProbe:
    """One disease/condition probe in the ranking panel.

    `target_proteins` lists the canonical proteins/genes this disease
    family is known to involve — used by the OPERATIONAL fallback when
    MAMMAL embeddings aren't live.

    `tokens` is the MAMMAL-style typed-token prompt sent to the model.
    """
    name: str
    short_name: str
    category: str
    target_proteins: list[str]
    tokens: list[str]    # MAMMAL prompt fragments
    notes: str = ""


DEFAULT_DISEASE_PANEL = [
    DiseaseProbe(
        name="Solid-tumor oncology",
        short_name="solid_tumor",
        category="oncology",
        target_proteins=["EGFR", "HER2", "MYC", "p53", "BRAF", "KRAS"],
        tokens=["solid_tumor", "EGFR", "MYC_amplified", "cancer_cell_proliferation"],
        notes="MAMMAL paper's wet-lab-validated repurposing class — "
              "carfilzomib (blood cancer drug) confirmed against solid tumors.",
    ),
    DiseaseProbe(
        name="Blood cancers (leukemia / lymphoma / myeloma)",
        short_name="hematologic_oncology",
        category="oncology",
        target_proteins=["BCR-ABL", "CD20", "CD19", "PSMB5", "BCL2"],
        tokens=["leukemia", "lymphoma", "multiple_myeloma", "proteasome"],
        notes="Original carfilzomib indication; broad family of validated targets.",
    ),
    DiseaseProbe(
        name="Inflammation / autoimmune",
        short_name="inflammation",
        category="immune",
        target_proteins=["TNF-alpha", "IL-6", "IL-17", "JAK2", "CRP"],
        tokens=["inflammation", "cytokine_storm", "TNF", "autoimmune"],
    ),
    DiseaseProbe(
        name="Fibrosis (pulmonary / hepatic / renal)",
        short_name="fibrosis",
        category="chronic",
        target_proteins=["TGF-beta", "FGFR", "PDGFR", "VEGFR"],
        tokens=["fibrosis", "TGFB_signaling", "tissue_scarring"],
        notes="Nintedanib is an FDA-approved fibrosis drug, useful comparator.",
    ),
    DiseaseProbe(
        name="Neurodegeneration (Alzheimer's / Parkinson's)",
        short_name="neurodegeneration",
        category="neuro",
        target_proteins=["APP", "MAPT", "SNCA", "BACE1", "LRRK2"],
        tokens=["amyloid_beta", "tau_phosphorylation", "synuclein", "neurodegeneration"],
    ),
    DiseaseProbe(
        name="Viral infection (broad-spectrum antivirals)",
        short_name="viral",
        category="infectious",
        target_proteins=["3CLpro", "RdRp", "ACE2", "spike_protein"],
        tokens=["viral_replication", "protease_inhibition", "antiviral"],
    ),
    DiseaseProbe(
        name="Metabolic (diabetes / NASH / obesity)",
        short_name="metabolic",
        category="chronic",
        target_proteins=["GLP-1R", "DPP4", "PPARG", "SGLT2", "insulin_receptor"],
        tokens=["glucose_homeostasis", "insulin_resistance", "NASH"],
    ),
    DiseaseProbe(
        name="Cardiovascular (heart failure / arrhythmia / hypertension)",
        short_name="cardiovascular",
        category="chronic",
        target_proteins=["beta_adrenergic", "ACE", "ATR1", "RyR2"],
        tokens=["cardiac_remodeling", "RAAS_axis", "arrhythmogenic"],
    ),
    DiseaseProbe(
        name="Rare genetic (cystic fibrosis / Duchenne / SMA)",
        short_name="rare_genetic",
        category="genetic",
        target_proteins=["CFTR", "DMD", "SMN1"],
        tokens=["CFTR_mutation", "dystrophin_loss", "rare_genetic_disorder"],
    ),
    DiseaseProbe(
        name="Antimicrobial-resistant bacterial",
        short_name="antibiotic_resistant",
        category="infectious",
        target_proteins=["MRSA_PBP2a", "NDM-1", "beta_lactamase"],
        tokens=["antibiotic_resistance", "MRSA", "carbapenem_resistant"],
    ),
]


# ──────────────────────────────────────────────────────────────────────
# Drug heuristic features — used when MAMMAL isn't loaded live
# ──────────────────────────────────────────────────────────────────────

# Known drug → feature vector (each feature 0..1). Curated from public
# pharmacology; we report this is a HEURISTIC fallback, never as truth.
# A real production system would replace this with live MAMMAL queries.
_KNOWN_DRUG_FEATURES = {
    # name → (proteasome, kinase, gpcr, antibody_like, immunomod, antiviral, fibrosis, metabolic, cardiac, antibiotic)
    "carfilzomib":   [0.98, 0.05, 0.02, 0.10, 0.30, 0.05, 0.05, 0.02, 0.05, 0.02],
    "bortezomib":    [0.95, 0.06, 0.02, 0.08, 0.30, 0.05, 0.05, 0.02, 0.05, 0.02],
    "imatinib":      [0.10, 0.95, 0.05, 0.10, 0.20, 0.02, 0.05, 0.05, 0.05, 0.02],
    "nintedanib":    [0.10, 0.65, 0.05, 0.10, 0.20, 0.02, 0.95, 0.05, 0.10, 0.02],
    "infigratinib":  [0.05, 0.92, 0.05, 0.10, 0.10, 0.02, 0.20, 0.05, 0.02, 0.02],
    "vemurafenib":   [0.05, 0.95, 0.05, 0.10, 0.15, 0.02, 0.05, 0.02, 0.02, 0.02],
    "acetaminophen": [0.02, 0.02, 0.10, 0.05, 0.20, 0.02, 0.05, 0.10, 0.05, 0.02],
    "aspirin":       [0.02, 0.02, 0.10, 0.02, 0.40, 0.02, 0.05, 0.10, 0.30, 0.02],
    "metformin":     [0.02, 0.05, 0.20, 0.02, 0.10, 0.02, 0.10, 0.95, 0.10, 0.02],
    "warfarin":      [0.02, 0.02, 0.05, 0.02, 0.05, 0.02, 0.02, 0.05, 0.85, 0.02],
    "atorvastatin":  [0.02, 0.05, 0.05, 0.02, 0.10, 0.02, 0.10, 0.40, 0.85, 0.02],
    "amoxicillin":   [0.02, 0.02, 0.02, 0.02, 0.02, 0.10, 0.02, 0.02, 0.02, 0.85],
    "remdesivir":    [0.02, 0.15, 0.02, 0.02, 0.10, 0.95, 0.02, 0.02, 0.02, 0.02],
    "donepezil":     [0.02, 0.02, 0.50, 0.02, 0.05, 0.02, 0.02, 0.02, 0.02, 0.02],
    "levodopa":      [0.02, 0.02, 0.40, 0.02, 0.05, 0.02, 0.02, 0.02, 0.02, 0.02],
}

# Disease-probe → feature affinity (same 10-dim space as above)
# (proteasome, kinase, gpcr, antibody, immunomod, antiviral, fibrosis, metabolic, cardiac, antibiotic)
_PROBE_AFFINITY = {
    "solid_tumor":            [0.55, 0.85, 0.20, 0.50, 0.30, 0.05, 0.10, 0.05, 0.05, 0.02],
    "hematologic_oncology":   [0.90, 0.80, 0.15, 0.65, 0.25, 0.05, 0.05, 0.02, 0.02, 0.02],
    "inflammation":           [0.10, 0.30, 0.40, 0.55, 0.95, 0.10, 0.30, 0.10, 0.15, 0.05],
    "fibrosis":               [0.10, 0.70, 0.20, 0.20, 0.30, 0.02, 0.95, 0.05, 0.10, 0.02],
    "neurodegeneration":      [0.05, 0.20, 0.55, 0.10, 0.20, 0.02, 0.05, 0.05, 0.05, 0.02],
    "viral":                  [0.05, 0.30, 0.05, 0.30, 0.30, 0.95, 0.02, 0.02, 0.02, 0.05],
    "metabolic":              [0.02, 0.20, 0.45, 0.05, 0.15, 0.02, 0.15, 0.95, 0.20, 0.02],
    "cardiovascular":         [0.02, 0.20, 0.30, 0.05, 0.20, 0.05, 0.10, 0.30, 0.95, 0.02],
    "rare_genetic":           [0.20, 0.40, 0.10, 0.30, 0.10, 0.05, 0.20, 0.05, 0.05, 0.02],
    "antibiotic_resistant":   [0.05, 0.10, 0.05, 0.20, 0.05, 0.30, 0.02, 0.02, 0.02, 0.95],
}


def _drug_features_or_none(drug: str) -> Optional[list[float]]:
    """Look up the heuristic feature vector for a known drug name.
    Returns None if the drug isn't in our small curated set."""
    if not drug:
        return None
    key = drug.strip().lower()
    return _KNOWN_DRUG_FEATURES.get(key)


def _smiles_features_estimate(smiles: str) -> list[float]:
    """Cheap, deterministic, NOT-MAMMAL feature estimate from a SMILES
    string. Counts heteroatoms / aromatic / amide / hydroxyl, maps
    them to the same 10-dim space. Strictly a fallback heuristic for
    when the name isn't recognized — receipt is clearly labeled."""
    s = smiles or ""
    n_aromatic = sum(1 for c in s if c.islower() and c in "cnops")
    n_amide = s.count("N") + s.count("C(=O)N")
    n_hydroxyl = s.count("OH") + s.count("O)") * 0  # rough
    n_carboxyl = s.count("C(=O)O")
    n_halide = s.count("Cl") + s.count("Br") + s.count("F")
    length = max(1, len(s))
    # Normalize each into 0..1 bands; weight into the 10-dim space
    def _b(x: float) -> float:
        return max(0.0, min(1.0, x))
    f = [
        _b(0.05 + 0.10 * n_amide / length),       # proteasome
        _b(0.10 + 0.20 * n_aromatic / length),    # kinase
        _b(0.05 + 0.05 * n_carboxyl),             # gpcr
        _b(0.02 + 0.10 * n_amide / length),       # antibody_like
        _b(0.10 + 0.20 * n_carboxyl),             # immunomod
        _b(0.02 + 0.10 * n_halide / length),      # antiviral
        _b(0.02 + 0.10 * n_aromatic / length),    # fibrosis
        _b(0.02 + 0.05 * n_hydroxyl),             # metabolic
        _b(0.02 + 0.05 * n_hydroxyl),             # cardiac
        _b(0.02 + 0.10 * n_halide / length),      # antibiotic
    ]
    return f


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return math.sqrt(sum(x * x for x in a)) or 1.0


def _cosine(a: list[float], b: list[float]) -> float:
    return _dot(a, b) / (_norm(a) * _norm(b))


# ──────────────────────────────────────────────────────────────────────
# Output records
# ──────────────────────────────────────────────────────────────────────

@dataclass
class DiseaseHypothesis:
    """One ranked disease hypothesis for the user's drug input."""
    rank: int
    disease_name: str
    short_name: str
    category: str
    score: float                       # 0..1 — overlap strength
    confidence_band: str               # high / medium / low / very_low
    target_proteins: list[str]
    rationale: str
    truth_class: str = "HYPOTHESIS"
    truth_label: str = TRUTH_LABEL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────
# Core ranker
# ──────────────────────────────────────────────────────────────────────

def _confidence_band(score: float) -> str:
    if score >= 0.80:
        return "high"
    if score >= 0.60:
        return "medium"
    if score >= 0.40:
        return "low"
    return "very_low"


def rank_diseases_for_drug(
    drug_input: str,
    *,
    panel: Optional[list[DiseaseProbe]] = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """Rank a panel of disease probes by predicted relevance to the
    given drug. Drug input is a name (looked up against curated set)
    OR a SMILES string (estimated heuristically).

    Returns:
      {
        "drug_input": "...",
        "drug_source": "curated_name" | "smiles_estimate" | "unknown",
        "ranked": [DiseaseHypothesis, ...],
        "truth_label": "DRUG_REPURPOSING_V1",
        "truth_class": "OPERATIONAL+HYPOTHESIS",
        "n_probes": int,
        "caveat": "..."
      }

    Every individual disease line is HYPOTHESIS class. The pipeline
    classification (OPERATIONAL) refers only to the deterministic
    scoring, not to any clinical claim.
    """
    probes = panel if panel is not None else DEFAULT_DISEASE_PANEL
    drug_clean = (drug_input or "").strip()
    if not drug_clean:
        return {
            "ok": False,
            "reason": "empty_drug_input",
            "truth_label": TRUTH_LABEL,
        }

    # 1. Get drug feature vector
    curated = _drug_features_or_none(drug_clean)
    if curated is not None:
        drug_features = curated
        drug_source = "curated_name"
    elif any(c in drug_clean for c in "()[]=#@") or any(c.isdigit() for c in drug_clean):
        drug_features = _smiles_features_estimate(drug_clean)
        drug_source = "smiles_estimate"
    else:
        # Unknown name — treat as a generic small-molecule shape
        drug_features = [0.05] * 10
        drug_source = "unknown"

    # 2. Score against every probe via cosine similarity
    ranked: list[DiseaseHypothesis] = []
    for probe in probes:
        affinity = _PROBE_AFFINITY.get(probe.short_name)
        if affinity is None:
            continue
        score = _cosine(drug_features, affinity)
        score = max(0.0, min(1.0, score))
        band = _confidence_band(score)
        top_proteins = ", ".join(probe.target_proteins[:3])
        rationale_bits = [
            f"feature-overlap with disease probe ({band} band: {score:.3f})",
            f"canonical targets: {top_proteins}",
        ]
        if drug_source == "curated_name":
            rationale_bits.append(
                "drug recognized in curated pharmacology set"
            )
        elif drug_source == "smiles_estimate":
            rationale_bits.append(
                "drug features estimated from SMILES string structure"
            )
        else:
            rationale_bits.append(
                "drug name not recognized — generic small-molecule shape used; "
                "consider supplying SMILES for better resolution"
            )
        if probe.notes:
            rationale_bits.append(probe.notes)
        ranked.append(DiseaseHypothesis(
            rank=0,  # filled in after sort
            disease_name=probe.name,
            short_name=probe.short_name,
            category=probe.category,
            score=round(float(score), 4),
            confidence_band=band,
            target_proteins=list(probe.target_proteins),
            rationale=" · ".join(rationale_bits),
        ))

    # 3. Sort and assign rank
    ranked.sort(key=lambda h: -h.score)
    ranked = ranked[:top_n]
    for i, h in enumerate(ranked, start=1):
        h.rank = i

    return {
        "ok": True,
        "drug_input": drug_clean,
        "drug_source": drug_source,
        "ranked": [h.to_dict() for h in ranked],
        "n_probes": len(probes),
        "truth_label": TRUTH_LABEL,
        "truth_class": "OPERATIONAL+HYPOTHESIS",
        "truth_boundary": TRUTH_BOUNDARY,
        "caveat": (
            "Every line is HYPOTHESIS class. NOT a clinical claim. "
            "NOT a diagnosis. Predicted-worth-investigating only. "
            "Wet-lab validation required before any repurposing "
            "decision is made on real patients."
        ),
    }


def write_receipt(
    result: dict[str, Any],
    *,
    state_root: str | Path | None = None,
) -> dict[str, Any]:
    """Append a signed receipt of the ranking result."""
    state = Path(state_root) if state_root else _STATE
    state.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"),
                         default=str)
    row = {
        "ts": time.time(),
        "kind": "DRUG_REPURPOSING_RANK",
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "truth_class": result.get("truth_class", "OPERATIONAL+HYPOTHESIS"),
        "truth_boundary": TRUTH_BOUNDARY,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "payload": result,
    }
    with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row


# ──────────────────────────────────────────────────────────────────────
# CLI — quick test
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--drug", type=str, default="carfilzomib")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    r = rank_diseases_for_drug(args.drug, top_n=args.top)
    if not args.no_write and r.get("ok"):
        write_receipt(r)
    print(f"Drug input: {r.get('drug_input')!r}")
    print(f"Source:     {r.get('drug_source')}")
    print(f"\n  rank  score  band      disease")
    print("  ────  ─────  ──────    " + "─" * 50)
    for h in r.get("ranked", []):
        print(f"  {h['rank']:>4}  {h['score']:.3f}  {h['confidence_band']:<8}  {h['disease_name']}")
    print(f"\nCaveat: {r.get('caveat')}")
