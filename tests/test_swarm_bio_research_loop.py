#!/usr/bin/env python3
"""
tests/test_swarm_bio_research_loop.py
Event 105 — BioSIFTA Research Loop test suite.
All tests use dry_run=True so no LLM call is needed.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── 1. Ingest creates bio_papers.jsonl rows ───────────────────────────────────

def test_ingest_paper_creates_chunks(tmp_path, monkeypatch):
    import System.swarm_bio_research_loop as mod
    monkeypatch.setattr(mod, "BIO_PAPERS",      tmp_path / "bio_papers.jsonl")
    monkeypatch.setattr(mod, "BIO_CLAIMS",      tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(mod, "BIO_SKILLS",      tmp_path / "bio_skills.jsonl")
    monkeypatch.setattr(mod, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")
    monkeypatch.setattr(mod, "TOURNAMENT_LOG",  tmp_path / "bio_tournament.jsonl")

    text = " ".join(["biology homeostasis allostasis stress cortisol"] * 40)
    chunks = mod.ingest_paper(text, title="TestPaper", doi="10.0001/test")
    assert len(chunks) >= 1
    rows = [json.loads(l) for l in (tmp_path / "bio_papers.jsonl").read_text().splitlines()]
    assert rows[0]["title"] == "TestPaper"
    assert rows[0]["doi"] == "10.0001/test"
    assert "chunk" in rows[0]
    assert rows[0]["truth_label"] == "BIOSIFTA_RESEARCH_EVENT_105"


# ── 2. make_claim schema ──────────────────────────────────────────────────────

def test_make_claim_schema():
    from System.swarm_bio_research_loop import make_claim
    c = make_claim("Allostatic load > 0.75 suppresses explore.", "McEwen1998",
                   "allostatic_load module", "assert policy=='FORCE_REST_REPAIR'")
    required = {"claim_id", "ts", "truth_label", "claim", "source",
                "organ_mapping", "test", "status"}
    assert required <= c.keys()
    assert c["status"] == "unverified"
    assert len(c["claim_id"]) == 12


# ── 2b. register_claim deterministic id + BIO_CLAIM_UNVERIFIED ───────────────

def test_register_claim_id_and_schema(tmp_path, monkeypatch):
    import System.swarm_bio_research_loop as mod
    monkeypatch.setattr(mod, "BIO_CLAIMS", tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(mod, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")

    row = mod.register_claim(
        "Chronic stress biases repair over exploration.",
        source_chunk_ids=["chunk_a", "chunk_b"],
        organ_mapping="allostatic_load + motor_policy",
        testable_prediction="pytest: high load → forage or rest dominates",
        confidence=0.7,
        source="doi:10.0000/test",
    )
    assert row["truth_label"] == mod.CLAIM_TRUTH_UNVERIFIED
    assert mod.generate_claim_id(row["claim"], ["chunk_b", "chunk_a"]) == row["claim_id"]
    assert len(row["claim_id"]) == 12
    saved = [json.loads(l) for l in (tmp_path / "bio_claims.jsonl").read_text().splitlines()]
    assert saved[0]["experiment_id"] == row["experiment_id"]


# ── 3. process_paper_chunk dry_run ───────────────────────────────────────────

def test_process_paper_chunk_dry_run(tmp_path, monkeypatch):
    import System.swarm_bio_research_loop as mod
    monkeypatch.setattr(mod, "BIO_PAPERS",      tmp_path / "bio_papers.jsonl")
    monkeypatch.setattr(mod, "BIO_CLAIMS",      tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(mod, "BIO_SKILLS",      tmp_path / "bio_skills.jsonl")
    monkeypatch.setattr(mod, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")
    monkeypatch.setattr(mod, "TOURNAMENT_LOG",  tmp_path / "bio_tournament.jsonl")

    claim = mod.process_paper_chunk(
        "Allostatic load suppresses hippocampal neurogenesis.",
        source="McEwen1998", dry_run=True,
    )
    assert claim is not None
    assert claim["status"] == "unverified"
    assert claim["claim"]
    assert claim["organ_mapping"]
    # Check appended to bio_claims.jsonl
    rows = [json.loads(l) for l in (tmp_path / "bio_claims.jsonl").read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["claim_id"] == claim["claim_id"]
    assert rows[0]["experiment_id"] == claim["experiment_id"]
    experiments = [
        json.loads(l)
        for l in (tmp_path / "bio_experiments.jsonl").read_text().splitlines()
    ]
    assert len(experiments) == 1
    assert experiments[0]["claim_id"] == claim["claim_id"]
    assert experiments[0]["truth_note"] == "PROPOSED_TEST_ONLY__NOT_A_SHIPPED_ORGAN"
    assert claim["experiment_id"] == experiments[0]["experiment_id"]


# ── 4. TF-IDF retrieval returns correct ranking ───────────────────────────────

def test_tfidf_retrieval_ranks_correctly(tmp_path, monkeypatch):
    import System.swarm_bio_research_loop as mod
    monkeypatch.setattr(mod, "BIO_PAPERS",      tmp_path / "bio_papers.jsonl")
    monkeypatch.setattr(mod, "BIO_CLAIMS",      tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(mod, "BIO_SKILLS",      tmp_path / "bio_skills.jsonl")
    monkeypatch.setattr(mod, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")
    monkeypatch.setattr(mod, "TOURNAMENT_LOG",  tmp_path / "bio_tournament.jsonl")

    mod.ingest_paper("cortisol stress allostasis homeostasis adrenal", title="StressPaper", doi="A")
    mod.ingest_paper("basal ganglia motor habit reward reinforcement", title="MotorPaper", doi="B")
    mod.ingest_paper("quantum computing qubits superposition entanglement", title="QuantumPaper", doi="C")

    results = mod.retrieve_papers("homeostasis stress cortisol", k=1)
    assert results, "Should return at least one result"
    assert results[0]["title"] == "StressPaper", (
        f"Expected StressPaper to rank first, got {results[0]['title']}"
    )


# ── 5. _spearman-free: TF-IDF scores list length matches docs ────────────────

def test_tfidf_scores_length(tmp_path):
    from System.swarm_bio_research_loop import _tfidf_scores
    docs = ["allostasis stress cortisol", "motor basal ganglia habit", "quantum"]
    scores = _tfidf_scores("stress cortisol allostasis", docs)
    assert len(scores) == len(docs)
    assert all(0.0 <= s <= 1.0 for s in scores), f"Scores out of [0,1]: {scores}"


# ── 6. Tournament dry_run runs and returns receipt ────────────────────────────

def test_run_bio_tournament_includes_heuristic_claim_ranking(tmp_path, monkeypatch):
    import System.swarm_bio_research_loop as mod
    monkeypatch.setattr(mod, "BIO_PAPERS", tmp_path / "bio_papers.jsonl")
    monkeypatch.setattr(mod, "BIO_CLAIMS", tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(mod, "BIO_SKILLS", tmp_path / "bio_skills.jsonl")
    monkeypatch.setattr(mod, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")
    monkeypatch.setattr(mod, "TOURNAMENT_LOG", tmp_path / "bio_tournament.jsonl")

    mod.register_claim(
        "alpha unique claim about quantum qubits unrelated",
        source_chunk_ids=["c1"],
        organ_mapping="none",
        testable_prediction="x",
        append_experiment=False,
    )
    mod.register_claim(
        "motor cortex basal ganglia habit loop requires pytest assert",
        source_chunk_ids=["c2", "c3"],
        organ_mapping="motor_policy crystallized skills",
        testable_prediction="assert motor selects forage when skills say so using pytest",
        append_experiment=False,
    )
    receipt = mod.run_bio_tournament(n_papers=2, n_ideas=2, dry_run=True)
    assert receipt.get("claim_tournament")
    assert receipt["top_claim_heuristic"]["composite"] >= receipt["claim_tournament"][-1]["composite"]


def test_run_bio_tournament_dry_run(tmp_path, monkeypatch):
    import System.swarm_bio_research_loop as mod
    monkeypatch.setattr(mod, "BIO_PAPERS",      tmp_path / "bio_papers.jsonl")
    monkeypatch.setattr(mod, "BIO_CLAIMS",      tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(mod, "BIO_SKILLS",      tmp_path / "bio_skills.jsonl")
    monkeypatch.setattr(mod, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")
    monkeypatch.setattr(mod, "TOURNAMENT_LOG",  tmp_path / "bio_tournament.jsonl")

    receipt = mod.run_bio_tournament(n_papers=2, n_ideas=2, dry_run=True)
    assert receipt["truth_label"] == "BIOSIFTA_RESEARCH_EVENT_105"
    assert receipt["status"] == "OK"
    assert receipt["n_ideas"] >= 1
    assert isinstance(receipt["scores"], list)
    # Tournament log created
    assert (tmp_path / "bio_tournament.jsonl").exists()


# ── 7. register_bio_skill creates bio_skills.jsonl ───────────────────────────

def test_register_bio_skill(tmp_path, monkeypatch):
    import System.swarm_bio_research_loop as mod
    monkeypatch.setattr(mod, "BIO_PAPERS",      tmp_path / "bio_papers.jsonl")
    monkeypatch.setattr(mod, "BIO_CLAIMS",      tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(mod, "BIO_SKILLS",      tmp_path / "bio_skills.jsonl")
    monkeypatch.setattr(mod, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")
    monkeypatch.setattr(mod, "TOURNAMENT_LOG",  tmp_path / "bio_tournament.jsonl")

    skill = mod.register_bio_skill(
        name="allostatic_gate",
        claim_id="abc123",
        module_path="System/swarm_allostatic_load.py",
        test_path="tests/test_swarm_allostatic_load.py",
        organ_mapping="allostatic_load: chronic stress suppression",
    )
    assert skill["status"] == "shipped"
    rows = [json.loads(l) for l in (tmp_path / "bio_skills.jsonl").read_text().splitlines()]
    assert rows[0]["name"] == "allostatic_gate"
    assert rows[0]["truth_label"] == "BIOSIFTA_RESEARCH_EVENT_105"


def test_seed_biology_self_learning_targets_writes_r643_ledgers(tmp_path, monkeypatch):
    import System.swarm_bio_research_loop as mod
    monkeypatch.setattr(mod, "BIOLOGY_NUGGETS", tmp_path / "biology_research_nuggets.jsonl")
    monkeypatch.setattr(mod, "BIOLOGY_PULL_QUEUE", tmp_path / "biology_research_pull_queue.jsonl")
    monkeypatch.setattr(mod, "BIO_CLAIMS", tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(mod, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")

    receipt = mod.seed_biology_self_learning_targets(state_dir=tmp_path)

    assert receipt["truth_label"] == mod.BIOLOGY_SELF_LEARNING_TRUTH
    assert receipt["domains"] == 3
    assert receipt["nuggets_written"] >= 10
    assert receipt["pull_targets_written"] == receipt["nuggets_written"]
    assert receipt["claims_written"] == 3
    nugget_rows = [
        json.loads(line)
        for line in (tmp_path / "biology_research_nuggets.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    domains = {row["domain_id"] for row in nugget_rows}
    assert {"cross_skill_integration", "environmental_contextualization", "fundamental_drift"} <= domains
    assert all(row["pull_status"] == "seeded_pending_browser_pull" for row in nugget_rows)
    assert all(row["source_truth"] == "seed_target_not_freshly_pulled" for row in nugget_rows)
    queue_rows = [
        json.loads(line)
        for line in (tmp_path / "biology_research_pull_queue.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(queue_rows) == len(nugget_rows)
    assert all(row["query_url"].startswith("https://scholar.google.com/scholar?q=") for row in queue_rows)
    assert (tmp_path / "self_code_plans.jsonl").exists()


def test_seed_biology_self_learning_targets_is_idempotent(tmp_path, monkeypatch):
    import System.swarm_bio_research_loop as mod
    monkeypatch.setattr(mod, "BIOLOGY_NUGGETS", tmp_path / "biology_research_nuggets.jsonl")
    monkeypatch.setattr(mod, "BIOLOGY_PULL_QUEUE", tmp_path / "biology_research_pull_queue.jsonl")
    monkeypatch.setattr(mod, "BIO_CLAIMS", tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(mod, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")

    first = mod.seed_biology_self_learning_targets(state_dir=tmp_path)
    second = mod.seed_biology_self_learning_targets(state_dir=tmp_path)

    assert first["nuggets_written"] > 0
    assert second["nuggets_written"] == 0
    assert second["pull_targets_written"] == 0
    assert second["claims_written"] == 0
    status = mod.biology_self_learning_status(state_dir=tmp_path)
    assert status["nuggets"] == first["nuggets_written"]
    line = mod.format_biology_self_learning_nuggets(state_dir=tmp_path)
    assert "cross-skill integration" in line
    assert "fundamental drift" in line


# ── 8. experiment proposal can be created without appending ──────────────────

def test_write_experiment_proposal_append_false(tmp_path, monkeypatch):
    import System.swarm_bio_research_loop as mod
    monkeypatch.setattr(mod, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")

    exp = mod.write_experiment_proposal(
        {
            "claim_id": "claim-1",
            "claim": "Repair should dominate during collapse.",
            "source": "synthetic",
            "organ_mapping": "motor_policy",
            "test": "assert repair wins under CRITICAL_COLLAPSE",
            "paper_chunk_hash": "abc",
            "model_used": "dry_run",
        },
        append=False,
    )

    assert exp["claim_id"] == "claim-1"
    assert exp["status"] == "proposed"
    assert exp["truth_note"] == "PROPOSED_TEST_ONLY__NOT_A_SHIPPED_ORGAN"
    assert not (tmp_path / "bio_experiments.jsonl").exists()


# ── 9. Chunk overlap produces correct word count ──────────────────────────────

def test_ingest_chunk_overlap(tmp_path, monkeypatch):
    import System.swarm_bio_research_loop as mod
    monkeypatch.setattr(mod, "BIO_PAPERS",      tmp_path / "bio_papers.jsonl")
    monkeypatch.setattr(mod, "BIO_CLAIMS",      tmp_path / "bio_claims.jsonl")
    monkeypatch.setattr(mod, "BIO_SKILLS",      tmp_path / "bio_skills.jsonl")
    monkeypatch.setattr(mod, "BIO_EXPERIMENTS", tmp_path / "bio_experiments.jsonl")
    monkeypatch.setattr(mod, "TOURNAMENT_LOG",  tmp_path / "bio_tournament.jsonl")

    # 200 words should produce at least 1 chunk with chunk_size=100
    text = " ".join([f"word{i}" for i in range(200)])
    chunks = mod.ingest_paper(text, title="ChunkTest", chunk_size=100, chunk_overlap=20)
    assert len(chunks) >= 2, f"Expected ≥2 chunks, got {len(chunks)}"
    # Each chunk should be ≤100 words
    for c in chunks:
        assert c["word_count"] <= 100, f"Chunk too large: {c['word_count']}"


if __name__ == "__main__":
    import pytest as _pt
    _pt.main([__file__, "-v"])
