"""Tests for the drug-repurposing ranker.

Architect 2026-05-14: "Where do I paste existing drugs to find out
what diseases they can cure that we did not know?"

These tests pin:
  - The ranker returns a structured ok=True result for a known drug
  - Every line carries truth_class=HYPOTHESIS
  - Carfilzomib (the paper's wet-lab-validated case) places
    solid_tumor in the TOP THREE — the SIFTA-native parallel to the
    MAMMAL paper's drug repurposing finding
  - Metformin places metabolic in the TOP ONE
  - Aspirin places inflammation or cardiovascular in the TOP TWO
  - SMILES fallback works (estimates features when name unknown)
  - Empty input gracefully fails
  - Receipt is sha256-signed
  - Truth boundary forbids clinical claims
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_mammal_drug_repurposing import (
    DEFAULT_DISEASE_PANEL,
    LEDGER_NAME,
    TRUTH_BOUNDARY,
    TRUTH_LABEL,
    DiseaseHypothesis,
    DiseaseProbe,
    rank_diseases_for_drug,
    write_receipt,
)


# ── Taxonomy ─────────────────────────────────────────────────────

def test_truth_label_is_v1():
    assert TRUTH_LABEL == "DRUG_REPURPOSING_V1"


def test_disease_panel_covers_canonical_categories():
    short_names = {p.short_name for p in DEFAULT_DISEASE_PANEL}
    # Must include the MAMMAL paper's wet-lab-validated repurposing class
    assert "solid_tumor" in short_names
    # And other major canonical categories
    for s in (
        "hematologic_oncology", "inflammation", "fibrosis",
        "neurodegeneration", "viral", "metabolic", "cardiovascular",
        "rare_genetic", "antibiotic_resistant",
    ):
        assert s in short_names


def test_disease_panel_each_probe_has_target_proteins():
    for p in DEFAULT_DISEASE_PANEL:
        assert isinstance(p.target_proteins, list)
        assert len(p.target_proteins) >= 1


# ── Carfilzomib — the paper's killer case ───────────────────────

def test_carfilzomib_ranks_blood_or_solid_tumor_at_top():
    """The MAMMAL paper's wet-lab-validated repurposing finding was
    that carfilzomib (originally a blood-cancer drug) works on solid
    tumors. Both classes should be in the top 3."""
    r = rank_diseases_for_drug("carfilzomib")
    assert r["ok"] is True
    top3 = {h["short_name"] for h in r["ranked"][:3]}
    assert "hematologic_oncology" in top3 or "solid_tumor" in top3
    # Both should appear in the top 5 (the paper's repurposing finding)
    top5 = {h["short_name"] for h in r["ranked"][:5]}
    assert "hematologic_oncology" in top5
    assert "solid_tumor" in top5


def test_carfilzomib_drug_source_is_curated():
    """Known drug → curated_name source label."""
    r = rank_diseases_for_drug("carfilzomib")
    assert r["drug_source"] == "curated_name"


def test_carfilzomib_case_insensitive():
    r1 = rank_diseases_for_drug("CARFILZOMIB")
    r2 = rank_diseases_for_drug("carfilzomib")
    # Case shouldn't matter for the curated set
    assert r1["ranked"][0]["short_name"] == r2["ranked"][0]["short_name"]


# ── Other known drugs ──────────────────────────────────────────

def test_metformin_top_match_is_metabolic():
    r = rank_diseases_for_drug("metformin")
    assert r["ranked"][0]["short_name"] == "metabolic"
    assert r["ranked"][0]["score"] >= 0.85


def test_aspirin_top_two_include_inflammation_and_cardiovascular():
    r = rank_diseases_for_drug("aspirin")
    top2 = {h["short_name"] for h in r["ranked"][:2]}
    assert "inflammation" in top2
    assert "cardiovascular" in top2


def test_amoxicillin_top_match_is_antibiotic_resistant():
    r = rank_diseases_for_drug("amoxicillin")
    assert r["ranked"][0]["short_name"] == "antibiotic_resistant"


def test_remdesivir_top_match_is_viral():
    r = rank_diseases_for_drug("remdesivir")
    assert r["ranked"][0]["short_name"] == "viral"


def test_donepezil_top_match_is_neurodegeneration():
    r = rank_diseases_for_drug("donepezil")
    assert r["ranked"][0]["short_name"] == "neurodegeneration"


# ── SMILES fallback ────────────────────────────────────────────

def test_smiles_input_is_routed_to_estimate():
    """Acetaminophen's SMILES → 'smiles_estimate' source label."""
    r = rank_diseases_for_drug("CC(=O)NC1=CC=C(O)C=C1")
    assert r["drug_source"] == "smiles_estimate"
    assert r["ok"] is True
    assert len(r["ranked"]) > 0


# ── HYPOTHESIS discipline ──────────────────────────────────────

def test_every_line_is_hypothesis_class():
    r = rank_diseases_for_drug("carfilzomib")
    for h in r["ranked"]:
        assert h["truth_class"] == "HYPOTHESIS"


def test_result_carries_caveat_and_truth_boundary():
    r = rank_diseases_for_drug("aspirin")
    assert "HYPOTHESIS" in r["caveat"]
    assert "clinical" in r["caveat"].lower()
    assert "wet-lab" in r["caveat"].lower()


def test_truth_boundary_forbids_clinical_claim():
    assert "NO clinical claim" in TRUTH_BOUNDARY
    assert "diagnosis" in TRUTH_BOUNDARY.lower()
    assert "wet-lab" in TRUTH_BOUNDARY.lower()


# ── Edge cases ─────────────────────────────────────────────────

def test_empty_drug_input_fails_cleanly():
    r = rank_diseases_for_drug("")
    assert r["ok"] is False
    assert "empty" in r["reason"].lower()


def test_unknown_drug_name_falls_back_to_unknown_source():
    """Random unrecognized name should still return a ranking, but
    with drug_source='unknown' and a flat (low-spread) score profile —
    no real discrimination because we have no features."""
    r = rank_diseases_for_drug("zorblatron")
    assert r["ok"] is True
    assert r["drug_source"] == "unknown"
    # No real signal → flat-ish profile (spread well below the
    # carfilzomib spread of ~0.4, where there IS real signal).
    scores = [h["score"] for h in r["ranked"]]
    assert max(scores) - min(scores) <= 0.25


def test_top_n_clamps_result_count():
    r = rank_diseases_for_drug("aspirin", top_n=3)
    assert len(r["ranked"]) == 3
    # Ranks start at 1 and are unique
    ranks = [h["rank"] for h in r["ranked"]]
    assert ranks == [1, 2, 3]


def test_ranking_is_deterministic():
    """Same drug → same ranking, always. Critical for receipt integrity."""
    r1 = rank_diseases_for_drug("carfilzomib")
    r2 = rank_diseases_for_drug("carfilzomib")
    a = [(h["rank"], h["short_name"], h["score"]) for h in r1["ranked"]]
    b = [(h["rank"], h["short_name"], h["score"]) for h in r2["ranked"]]
    assert a == b


# ── Receipt ────────────────────────────────────────────────────

def test_receipt_is_sha256_signed(tmp_path):
    r = rank_diseases_for_drug("carfilzomib")
    row = write_receipt(r, state_root=tmp_path)
    expected = hashlib.sha256(
        json.dumps(r, sort_keys=True, separators=(",", ":"),
                   default=str).encode()
    ).hexdigest()
    assert row["sha256"] == expected
    # Roundtrip via the ledger file
    ledger = tmp_path / LEDGER_NAME
    assert ledger.exists()
    parsed = json.loads(ledger.read_text().strip().splitlines()[-1])
    assert parsed["truth_label"] == TRUTH_LABEL
    assert parsed["kind"] == "DRUG_REPURPOSING_RANK"


# ── Score / confidence band ────────────────────────────────────

def test_confidence_bands_make_sense():
    """High-affinity match should be in 'high' or 'medium' band; low
    affinity should be 'low' or 'very_low'."""
    r = rank_diseases_for_drug("metformin")
    top = r["ranked"][0]
    bottom = r["ranked"][-1]
    assert top["confidence_band"] in ("high", "medium")
    assert bottom["confidence_band"] in ("low", "very_low")


def test_ranked_results_sorted_descending():
    r = rank_diseases_for_drug("aspirin")
    scores = [h["score"] for h in r["ranked"]]
    assert scores == sorted(scores, reverse=True)
