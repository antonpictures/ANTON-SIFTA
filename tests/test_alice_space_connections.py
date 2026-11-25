#!/usr/bin/env python3
"""Tests for Alice Space connections to existing SIFTA consciousness, fitness, eval, and spinal organs."""
from __future__ import annotations

import json
from pathlib import Path

from System import eval_talk_labeling_helper as talk_helper
from System.swarm_substrate_awareness import substrate_awareness_snapshot
from System.swarm_substrate_corrections import (
    _all_corrections,
    corrections_block,
    sync_eval_verdicts,
)
from System.swarm_substrate_ingest import VIEWS, status as ingest_status


def test_resolve_conversation_ref_searches_rotated_archives(tmp_path, monkeypatch):
    state_dir = tmp_path / ".sifta_state"
    live_convo = state_dir / "alice_conversation.jsonl"
    arch_dir = state_dir / "archive_20260720"
    arch_dir.mkdir(parents=True)
    arch_convo = arch_dir / "alice_conversation.jsonl"

    live_convo.write_text("", encoding="utf-8")
    row = {
        "event_id": "evt_archived",
        "this_hash": "123456789abc0000",
        "payload": {"role": "alice", "text": "archived turn"},
    }
    arch_convo.write_text(json.dumps(row) + "\n", encoding="utf-8")

    monkeypatch.setattr(talk_helper, "_STATE", state_dir)
    monkeypatch.setattr(talk_helper, "_CONVO", live_convo)

    ref = talk_helper.conversation_ref_for_row(row)
    resolved = talk_helper.resolve_conversation_ref(ref)
    assert resolved == row


def test_ingest_views_include_ledger_journal_and_narrative():
    assert {"ledger", "journal", "narrative"} <= set(VIEWS.keys())
    st = ingest_status()
    assert "ledger" in st and "journal" in st and "narrative" in st


def test_eval_verdicts_synced_into_corrections_idempotently():
    res = sync_eval_verdicts()
    assert res["ok"] is True
    assert res["added"] == 0  # already synced
    corrs = _all_corrections()
    assert len(corrs) >= 6
    block = corrections_block(top_k=3)
    assert "[CORRECTIONS OF RECORD" in block


def test_substrate_snapshot_connects_consciousness_bridge_and_body_organs():
    snap = substrate_awareness_snapshot()
    assert snap["truth"] == "ALICE_SPACE_AWARENESS_V1"
    cb = snap.get("consciousness_bridge") or {}
    assert cb.get("ok") is True
    assert cb.get("self_vector_changed") is True
    assert isinstance(snap.get("body_organs"), dict)
    assert snap["body_organs"].get("organ_modules", 0) > 100
