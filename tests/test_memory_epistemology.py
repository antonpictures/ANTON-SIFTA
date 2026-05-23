"""
tests/test_memory_epistemology.py — Cowork Auditor gates for Memory Epistemology Slice 1.

Verifies Grok's edit to System/stigmergic_memory_bus.py against the six acceptance
criteria in Documents/GROK_MEMORY_EPISTEMOLOGY_SPEC.md §6.

All writes are redirected to a tmp ledger so the real .sifta_state memory is never touched.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict

import pytest

import System.stigmergic_memory_bus as mb


@pytest.fixture
def bus(tmp_path, monkeypatch):
    # Redirect every ledger the bus touches to the tmp dir.
    monkeypatch.setattr(mb, "LEDGER_FILE", tmp_path / "memory_ledger.jsonl")
    monkeypatch.setattr(mb, "MEMORY_EPISTEMOLOGY_AUDIT", tmp_path / "memory_epistemology_audit.jsonl")
    monkeypatch.setattr(mb, "STGM_LOG_FILE", tmp_path / "stgm_memory_rewards.jsonl")
    try:
        import System.lagrangian_constraint_manifold as lagrangian

        monkeypatch.setattr(lagrangian, "_DUAL_STATE_PATH", tmp_path / "lagrangian_multipliers.json")
        monkeypatch.setattr(lagrangian, "_RESIDUE_LOG_PATH", tmp_path / "constraint_residues.jsonl")
    except Exception:
        pass
    try:
        import System.proof_of_useful_work as proof

        monkeypatch.setattr(proof, "issue_work_receipt", lambda *args, **kwargs: None)
    except Exception:
        pass
    return mb.StigmergicMemoryBus(architect_id="ioan_test")


def _audit_rows():
    if not mb.MEMORY_EPISTEMOLOGY_AUDIT.exists():
        return []
    return [json.loads(l) for l in mb.MEMORY_EPISTEMOLOGY_AUDIT.read_text().splitlines() if l.strip()]


# 1 — explicit OBSERVED + links is written through to the row
def test_observed_with_links_persists(bus):
    t = bus.remember("George said ship it", "talk_to_alice",
                     epistemic_label="OBSERVED", links=["trace_id:abc123"])
    assert t.epistemic_label == "OBSERVED"
    assert t.links == ["trace_id:abc123"]
    rows = bus.dump_ledger()
    assert rows[-1]["epistemic_label"] == "OBSERVED"
    assert "trace_id:abc123" in rows[-1]["links"]


# 2 — OBSERVED with no evidence auto-downgrades to HYPOTHESIS + audit row
def test_observed_without_links_downgrades(bus):
    t = bus.remember("unbacked claim", "talk_to_alice", epistemic_label="OBSERVED")
    assert t.epistemic_label == "HYPOTHESIS"
    assert mb.MEMORY_EPISTEMOLOGY_AUDIT.exists()
    audit = _audit_rows()
    assert audit[-1]["requested_label"] == "OBSERVED"
    assert audit[-1]["final_label"] == "HYPOTHESIS"
    assert audit[-1]["reason"] == "downgraded_no_evidence"


# 3 — FICTION inferred from app_context when no label given
def test_fiction_inferred_from_context(bus):
    t = bus.remember("the hero jumped the chasm", "fiction_cowatch")
    assert t.epistemic_label == "FICTION"


# 4 — legacy rows (no new keys) reconstruct with safe defaults, no crash
def test_legacy_row_backward_compatible(bus):
    legacy = {
        "trace_id": "old1", "architect_id": "ioan_test", "app_context": "talk",
        "raw_text": "legacy memory line", "semantic_tags": [], "timestamp": time.time(),
        "stgm_paid": 0.05, "recall_count": 0, "decay_modifier": 1.0,
    }
    mb.LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    mb.LEDGER_FILE.write_text(json.dumps(legacy) + "\n", encoding="utf-8")

    # dump_ledger must read it
    rows = bus.dump_ledger()
    assert rows[0]["trace_id"] == "old1"

    # direct reconstruction (mirrors the forager's safe_raw path) defaults cleanly
    known = {f.name for f in mb.PheromoneTrace.__dataclass_fields__.values()}
    safe = {k: v for k, v in legacy.items() if k in known}
    tr = mb.PheromoneTrace(**safe)
    assert tr.epistemic_label == "HYPOTHESIS"
    assert tr.links == []

    # forager must not raise on the legacy row
    mb.MemoryForager("swimmer", "ioan_test").forage("legacy memory line", mb.LEDGER_FILE)


# 5 — FICTION is never surfaced in the factual recall block
def test_recall_block_excludes_fiction(bus):
    bus.remember("secret plan alpha bravo charlie", "talk_to_alice",
                 epistemic_label="OBSERVED", links=["doc:Documents/x.md"])
    bus.remember("dragon plan alpha bravo charlie", "fiction_cowatch")
    block = bus.recall_context_block("plan alpha bravo charlie", "talk_to_alice", top_k=5)
    # The fiction memory must never leak into the factual block.
    assert "dragon" not in block
    assert "FICTION" not in block
    # If anything surfaced, it must carry an explicit label prefix.
    if block and "raw_text" not in block:
        assert "[" in block


# 6 — unknown label is coerced to HYPOTHESIS and the row JSON round-trips
def test_unknown_label_coerced_and_roundtrips(bus):
    t = bus.remember("mystery", "talk_to_alice", epistemic_label="BANANA")
    assert t.epistemic_label == "HYPOTHESIS"
    assert any(row["reason"] == "unknown_label_coerced" for row in _audit_rows())
    d = asdict(t)
    back = json.loads(json.dumps(d))
    assert back["epistemic_label"] == "HYPOTHESIS"
    assert "links" in back
    # the label set itself is the gate
    assert "BANANA" not in mb.EPISTEMIC_LABELS
    assert {"OBSERVED", "WORLD", "BELIEF", "HYPOTHESIS", "ARCHITECT_DOCTRINE", "FICTION"} <= mb.EPISTEMIC_LABELS


# ──────────────────────────────────────────────────────────────────────────────
# Slice 2 — Hybrid Recall Gates (7 tests)
# ──────────────────────────────────────────────────────────────────────────────

def test_hybrid_recall_returns_breakdown(bus):
    bus.remember("the red shirt is important", "talk_to_alice",
                 epistemic_label="OBSERVED", links=["trace_id:abc"])
    results = bus.hybrid_recall("red shirt", "talk_to_alice", top_k=3)
    assert len(results) >= 1
    score, trace, breakdown = results[0]
    assert "forager" in breakdown and "bm25" in breakdown
    assert "decay" in breakdown and "stgm" in breakdown and "label" in breakdown


def test_hybrid_epistemic_weighting(bus):
    bus.remember("fact one", "talk_to_alice", epistemic_label="OBSERVED", links=["trace_id:1"])
    bus.remember("guess one", "talk_to_alice", epistemic_label="HYPOTHESIS")
    results = bus.hybrid_recall("one", "talk_to_alice", top_k=5)
    labels = [r[2]["label"] for r in results]
    # OBSERVED should outrank HYPOTHESIS when text is similar
    if "OBSERVED" in labels and "HYPOTHESIS" in labels:
        assert labels.index("OBSERVED") < labels.index("HYPOTHESIS")


def test_hybrid_excludes_fiction(bus):
    bus.remember("real meeting tuesday", "talk_to_alice", epistemic_label="OBSERVED", links=["trace_id:2"])
    bus.remember("dragon meeting tuesday", "fiction_cowatch")
    results = bus.hybrid_recall("meeting tuesday", "talk_to_alice", top_k=5)
    labels = [r[2]["label"] for r in results]
    assert "FICTION" not in labels


def test_bm25_rare_term_wins(bus):
    bus.remember("the quick brown fox", "talk_to_alice")
    bus.remember("the quick brown dog", "talk_to_alice")
    results = bus.hybrid_recall("fox", "talk_to_alice", top_k=2)
    # The one with the rare term "fox" should rank first
    assert "fox" in results[0][1].raw_text.lower()


def test_decay_and_reinforcement_ranking(bus):
    t1 = bus.remember("old reinforced", "talk_to_alice")
    t2 = bus.remember("brand new", "talk_to_alice")
    # reinforce t1 many times
    for _ in range(8):
        bus._reinforce_trace(t1.trace_id)
    results = bus.hybrid_recall("reinforced new", "talk_to_alice", top_k=2)
    # The heavily reinforced one should rank higher despite being older in this toy case
    assert results[0][1].raw_text == "old reinforced" or len(results) == 1


def test_hybrid_works_without_index(bus):
    # Even without any cache, hybrid_recall must function
    bus.remember("pure local test", "talk_to_alice", epistemic_label="WORLD", links=["doc:foo"])
    results = bus.hybrid_recall("local test", "talk_to_alice", top_k=1)
    assert len(results) == 1


def test_legacy_rows_still_rank(bus):
    # Simulate a pre-Slice-1 row
    legacy = {
        "trace_id": "legacy123",
        "architect_id": "ioan_test",
        "app_context": "old_app",
        "raw_text": "legacy fact without labels",
        "semantic_tags": ["general"],
        "timestamp": time.time() - 1000,
        "stgm_paid": 0.05,
    }
    with open(mb.LEDGER_FILE, "a") as f:
        f.write(json.dumps(legacy) + "\n")
    results = bus.hybrid_recall("legacy fact", "old_app", top_k=3)
    assert any("legacy" in r[1].raw_text for r in results)


# ──────────────────────────────────────────────────────────────────────────────
# Codex verifier edge probes
# ──────────────────────────────────────────────────────────────────────────────

def test_world_without_links_downgrades_and_audits(bus):
    t = bus.remember("verified-sounding world claim", "talk_to_alice", epistemic_label="WORLD")
    assert t.epistemic_label == "HYPOTHESIS"
    assert "note:downgraded_no_evidence" in t.links
    assert any(
        row["requested_label"] == "WORLD"
        and row["final_label"] == "HYPOTHESIS"
        and row["reason"] == "downgraded_no_evidence"
        for row in _audit_rows()
    )


def test_unknown_link_prefix_is_dropped_and_logged(bus):
    t = bus.remember(
        "George said the receipt exists",
        "talk_to_alice",
        epistemic_label="OBSERVED",
        links=["bogus:abc", "trace_id:real"],
    )
    assert t.epistemic_label == "OBSERVED"
    assert t.links == ["trace_id:real"]
    assert any(
        row["reason"] == "dropped_unknown_link_prefix"
        and row["dropped_links"] == ["bogus:abc"]
        for row in _audit_rows()
    )


def test_unknown_only_links_drop_then_downgrade(bus):
    t = bus.remember(
        "bare observed claim with bad evidence",
        "talk_to_alice",
        epistemic_label="OBSERVED",
        links=["bogus:abc"],
    )
    assert t.epistemic_label == "HYPOTHESIS"
    assert t.links == ["note:downgraded_no_evidence"]
    reasons = [row["reason"] for row in _audit_rows()]
    assert "dropped_unknown_link_prefix" in reasons
    assert "downgraded_no_evidence" in reasons


def test_note_link_does_not_count_as_reality_evidence(bus):
    t = bus.remember(
        "note-only observed claim",
        "talk_to_alice",
        epistemic_label="OBSERVED",
        links=["note:human-commentary"],
    )
    assert t.epistemic_label == "HYPOTHESIS"
    assert t.links == ["note:human-commentary", "note:downgraded_no_evidence"]


def test_empty_ledger_recall_context_block_returns_empty_string(bus):
    assert bus.recall_context_block("anything", "talk_to_alice") == ""


def test_extra_future_keys_do_not_break_forager(bus):
    row = {
        "trace_id": "future123",
        "architect_id": "ioan_test",
        "app_context": "future_app",
        "raw_text": "future compatible memory",
        "semantic_tags": ["general"],
        "timestamp": time.time(),
        "stgm_paid": 0.05,
        "recall_count": 0,
        "decay_modifier": 1.0,
        "epistemic_label": "OBSERVED",
        "links": ["trace_id:future"],
        "future_schema_key": {"does": "not crash"},
    }
    mb.LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    mb.LEDGER_FILE.write_text(json.dumps(row) + "\n", encoding="utf-8")
    candidates = mb.MemoryForager("swimmer", "ioan_test").forage("future compatible", mb.LEDGER_FILE)
    assert candidates
    assert candidates[0][1].trace_id == "future123"
