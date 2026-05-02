import json

from System.swarm_multi_prover_verifier import (
    MultiProverLedgerPaths,
    bishop_bundle_quantum_sack_manifest,
    hash_claim,
    submit_claim,
    verify_claims,
)


def test_manifest_points_at_bundle_doc():
    m = bishop_bundle_quantum_sack_manifest()
    assert m["name"] == "BISHOP_BUNDLE_QUANTUM_SACK_2026_05_01"
    assert m["version"] == "2026-05-01"
    assert "BISHOP_BUNDLE_QUANTUM_SACK_2026_05_01.md" in m["doc"]


def test_hash_claim_stable():
    h = hash_claim("gradient ascent in this basin")
    assert len(h) == 64
    assert h == hash_claim("gradient ascent in this basin")


def test_quorum_accepts_two_independent_agents_same_claim(tmp_path):
    paths = MultiProverLedgerPaths(
        claims=tmp_path / "c.jsonl",
        verdicts=tmp_path / "v.jsonl",
    )
    submit_claim("Alice", "use policy X", {"evidence": ["a1"]}, paths=paths)
    submit_claim("Bishop", "use policy X", {"evidence": ["b1"]}, paths=paths)
    v = verify_claims(paths=paths, agreement_threshold=0.5, min_supporters=2)
    assert v["verdict"] == "ACCEPT"
    assert set(v["unique_agents"]) == {"Alice", "Bishop"}


def test_single_agent_duplicate_lines_not_accepted(tmp_path):
    paths = MultiProverLedgerPaths(
        claims=tmp_path / "c.jsonl",
        verdicts=tmp_path / "v.jsonl",
    )
    submit_claim("Alice", "solo claim", {}, paths=paths)
    submit_claim("Alice", "solo claim", {}, paths=paths)
    v = verify_claims(paths=paths, min_supporters=2)
    assert v["verdict"] == "REJECT"


def test_verdict_row_is_jsonl_append(tmp_path):
    paths = MultiProverLedgerPaths(
        claims=tmp_path / "c.jsonl",
        verdicts=tmp_path / "v.jsonl",
    )
    submit_claim("A", "q", {}, paths=paths)
    submit_claim("B", "q", {}, paths=paths)
    verify_claims(paths=paths, agreement_threshold=0.3, min_supporters=2)
    lines = paths.verdicts.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["truth_label"] == "MULTI_PROVER_VERDICT"
