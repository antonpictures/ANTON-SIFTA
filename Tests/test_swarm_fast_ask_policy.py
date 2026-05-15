"""Tests for the Fast Ask self-improvement organ.

These tests cover:
  - Rule-based seed policy classification + decision shape.
  - Append-only ledger + receipt integrity for dispatch + outcome.
  - Snapshot aggregation with decay and per-bucket hints.
  - Defensive contract: hooks never raise even on bad input.
  - The Talk widget hook constants exist and are importable.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from System import swarm_fast_ask_policy as fap


def test_decide_classifies_known_buckets():
    d_research = fap.decide("Tell me what you know about Mondaloy 200 processing")
    assert d_research.bucket == "research_topic"
    assert "research_docs:topic_match" in d_research.read

    d_recall = fap.decide("what did I say about my dental appointment yesterday?")
    # Could match recall_self OR schedule depending on keyword precedence;
    # the contract is that it never falls back to "unknown" for either path.
    assert d_recall.bucket in {"recall_self", "schedule"}

    d_small = fap.decide("hey alice")
    assert d_small.bucket == "small_talk"
    assert d_small.read == ("none",)

    d_body = fap.decide("is Alice healthy or does she look sick?", presence_gates_ok=False)
    assert d_body.bucket == "owner_body"
    assert "owner_body_events:last_20" in d_body.read

    d_unknown = fap.decide("foo bar baz quux", recent_history_turns=4)
    assert d_unknown.bucket == "unknown"
    assert d_unknown.read[0].startswith("alice_conversation:last_")
    assert d_unknown.stop_condition


def test_decide_payload_is_serialisable():
    d = fap.decide("show me the SIFTA Interstellar Evidence Crucible")
    payload = d.as_payload()
    assert payload["bucket"] in fap.QUERY_BUCKETS
    assert isinstance(payload["read"], list) and payload["read"]
    assert isinstance(payload["stop_condition"], str)
    json.dumps(payload)


def test_record_dispatch_then_outcome_creates_receipt_pair(tmp_path):
    ticket = fap.record_dispatch(
        query_text="What did I tell you about mondaloy yesterday?",
        model="alice-m5-cortex-8b-6.3gb:latest",
        history_turns=8,
        sysprompt_chars=2048,
        state_dir=tmp_path,
    )
    assert ticket is not None
    assert ticket.bucket in fap.QUERY_BUCKETS
    assert ticket.query_hash and len(ticket.query_hash) == 64

    row = fap.record_outcome(
        ticket,
        ok=True,
        response_text="A short reply.",
        latency_ms=1234.5,
        stgm_spent=0.42,
        truth_score=0.91,
        receipt_correct=True,
        user_useful=True,
        state_dir=tmp_path,
    )
    assert row is not None
    assert row["kind"] == fap.KIND_TRAINING_EXAMPLE
    assert row["truth_label"] == fap.TRUTH_LABEL
    assert row["receipt"] and len(row["receipt"]) == 64
    # Receipt must be deterministic from the row content.
    assert row["receipt"] == fap.local_receipt(row)
    assert row["outcome"]["ok"] is True
    assert row["outcome"]["latency_ms"] == 1234.5
    assert row["falsifier"]
    # Ledger has both decision-only + training rows from the same trace_id.
    rows = fap.read_jsonl(fap.ledger_path(tmp_path))
    kinds = {r["kind"] for r in rows}
    assert kinds == {fap.KIND_DECISION_ONLY, fap.KIND_TRAINING_EXAMPLE}
    trace_ids = {r["trace_id"] for r in rows}
    assert trace_ids == {ticket.trace_id}


def test_record_outcome_handles_failure_and_default_falsifier(tmp_path):
    ticket = fap.record_dispatch(
        query_text="please send a whatsapp to mom",
        model="alice-m5-cortex-8b-6.3gb:latest",
        history_turns=3,
        state_dir=tmp_path,
    )
    assert ticket is not None
    row = fap.record_outcome(
        ticket,
        ok=False,
        failure_kind="HTTPError 500",
        state_dir=tmp_path,
    )
    assert row is not None
    assert row["outcome"]["ok"] is False
    assert row["outcome"]["failure_kind"] == "crash"
    assert "more context" in row["falsifier"]


def test_record_dispatch_returns_none_on_bad_input_no_raise(tmp_path):
    # The hook MUST be defensive — passing a non-stringable object should
    # not crash the brain. We pass an unhashable object via a custom
    # __str__-broken type to exercise the except path.
    class BoomStr:
        def __str__(self):
            raise RuntimeError("boom")

    ticket = fap.record_dispatch(
        query_text=BoomStr(),  # type: ignore[arg-type]
        model="x",
        history_turns=0,
        state_dir=tmp_path,
    )
    # Should NOT raise; either returns a ticket OR None — both acceptable
    # since the contract is "never crash the brain."
    assert ticket is None or hasattr(ticket, "trace_id")


def test_record_outcome_with_none_ticket_returns_none():
    assert fap.record_outcome(None, ok=True) is None


def test_policy_snapshot_aggregates_buckets(tmp_path):
    queries = [
        ("hello", True, 200.0, 0.05),
        ("send whatsapp to dad", False, 4500.0, 1.2),
        ("what did I say about mondaloy?", True, 1800.0, 0.4),
        ("mondaloy primary source summary", True, 1500.0, 0.6),
    ]
    for q, ok, lat, stgm in queries:
        ticket = fap.record_dispatch(
            query_text=q, model="m", history_turns=10, state_dir=tmp_path,
        )
        fap.record_outcome(
            ticket, ok=ok, latency_ms=lat, stgm_spent=stgm,
            truth_score=(0.9 if ok else 0.1), user_useful=ok,
            state_dir=tmp_path,
        )

    snap = fap.policy_snapshot(state_dir=tmp_path)
    assert snap["truth_label"] == fap.TRUTH_LABEL
    assert snap["training_examples"] == len(queries)
    assert snap["decision_only_rows"] == len(queries)
    buckets = snap["buckets"]
    assert "small_talk" in buckets
    assert "tool_action" in buckets
    assert buckets["small_talk"]["success_rate"] == 1.0
    assert buckets["tool_action"]["success_rate"] == 0.0
    assert len(snap["recent_failures"]) >= 1
    assert snap["recent_failures"][0]["bucket"] == "tool_action"
    for hint in buckets.values():
        assert hint["recommended_lanes"]
        assert hint["stop_condition"]


def test_proof_of_property(tmp_path):
    # Empty ledger should still pass invariants.
    proof = fap.proof_of_property(state_dir=tmp_path)
    assert proof == {
        "ledger_path_exists_or_empty": True,
        "schema_version_v1": True,
        "lanes_set_immutable": True,
        "buckets_set_immutable": True,
        "failure_kinds_set_immutable": True,
    }


def test_query_hash_is_normalised_and_deterministic():
    h1 = fap.query_hash("What  did I  Say?  ")
    h2 = fap.query_hash("what did i say?")
    assert h1 == h2
    assert len(h1) == 64


def test_talk_widget_imports_fast_ask_hooks_lazily():
    # The Talk widget module must import the policy hooks without raising
    # even when PyQt is unavailable in this test environment. We do NOT
    # import the whole widget module here (it pulls Qt, audio, faster-whisper);
    # we just confirm the hook surface this widget calls into is intact.
    assert callable(fap.record_dispatch)
    assert callable(fap.record_outcome)
    assert hasattr(fap, "TRUTH_LABEL")
    assert hasattr(fap, "KIND_TRAINING_EXAMPLE")
    assert hasattr(fap, "LEDGER_NAME")


def test_presence_gate_moves_body_status_to_physical_space_first():
    decision = fap.decide(
        "is Alice healthy and can the camera see George?",
        presence_gates_ok=True,
    )
    assert decision.bucket == "owner_body"
    assert decision.read[0] == "physical_space:latest"
    assert "stigmergic_observability:last_80" in decision.read


def test_decide_adds_canonical_organ_registry_for_nontrivial_turns(tmp_path, monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 1.0)
    decision = fap.decide(
        "open the camera and check Alice health with receipts",
        state_dir=tmp_path,
        presence_gates_ok=False,
    )

    assert decision.bucket in {"owner_body", "tool_action", "swarm_status"}
    assert "canonical_organ_registry:top_3" in decision.read
    assert "organ_registry_top=" in decision.rationale


def test_cli_decide_and_proof_print_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SIFTA_STATE_DIR", str(tmp_path))
    # The CLI reads SIFTA_STATE_DIR at import time of the module; force a
    # reload so our temp dir is used.
    import importlib

    monkeypatch.setattr(fap, "_STATE", Path(str(tmp_path)))

    monkeypatch.setattr("sys.argv", ["swarm_fast_ask_policy", "decide", "what about mondaloy?"])
    rc = fap._cli()
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["bucket"] in fap.QUERY_BUCKETS

    monkeypatch.setattr("sys.argv", ["swarm_fast_ask_policy", "proof"])
    rc = fap._cli()
    out = capsys.readouterr().out
    assert rc == 0
    proof = json.loads(out)
    assert proof["schema_version_v1"] is True
