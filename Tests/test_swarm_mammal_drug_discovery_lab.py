import json

from System.swarm_mammal_drug_discovery_lab import (
    DEFAULT_CANDIDATES,
    TRUTH_LABEL,
    run_mammal_drug_discovery_lab,
)


def test_drug_discovery_lab_connects_three_modalities():
    result = run_mammal_drug_discovery_lab(steps=12, seed=7, write=False)

    assert result["truth_label"] == TRUTH_LABEL
    assert {"SMALL_MOLECULE", "GENE_EXPRESSION", "PROTEIN"}.issubset(set(result["modalities"]))
    nodes = set(result["biology_bridge_graph"]["nodes"])
    assert {"small_molecule", "gene_expression", "protein_target", "sifta_swimmer_field"}.issubset(nodes)


def test_drug_discovery_lab_ranks_candidate_hypotheses():
    result = run_mammal_drug_discovery_lab(steps=20, seed=11, write=False)
    candidates = result["candidates"]

    assert len(candidates) == len(DEFAULT_CANDIDATES)
    assert [c["rank"] for c in candidates] == [1, 2, 3, 4]
    assert candidates[0]["sifta_field_score"] >= candidates[-1]["sifta_field_score"]
    assert {c["truth_class"] for c in candidates} == {"HYPOTHESIS"}


def test_toxicity_penalty_is_exposed_for_each_candidate():
    result = run_mammal_drug_discovery_lab(steps=20, seed=13, write=False)

    penalties = [c["components"]["toxicity_penalty"] for c in result["candidates"]]
    assert all(p > 0 for p in penalties)
    assert max(penalties) > min(penalties)


def test_truth_boundary_blocks_clinical_claims():
    result = run_mammal_drug_discovery_lab(steps=5, seed=19, write=False)
    boundary = result["truth_boundary"].lower()

    assert "not clinical advice" in boundary
    assert "not dosing guidance" in boundary
    assert "not proof" in boundary


def test_drug_discovery_lab_writes_receipt(tmp_path):
    result = run_mammal_drug_discovery_lab(steps=8, seed=23, write=True, state_root=tmp_path)
    ledger = tmp_path / "mammal_drug_discovery_lab.jsonl"

    assert result["receipt_trace_id"]
    row = json.loads(ledger.read_text().splitlines()[-1])
    assert row["truth_label"] == TRUTH_LABEL
    assert row["payload"]["sha256"] == result["sha256"]
