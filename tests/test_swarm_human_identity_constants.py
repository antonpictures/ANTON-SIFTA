#!/usr/bin/env python3
"""Tests for human identity constants organ (r1239/r1241)."""
from __future__ import annotations

import os
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_human_identity_constants as hic


def test_ingest_owner_turn_creates_host_guest_and_listening_event(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    now = 1_700_000_000.0
    result = hic.ingest_owner_turn(
        "We are about to listen to Joe Rogan and his guest Chase Hughes on the iPhone.",
        state_dir=state_dir,
        now=now,
        evidence_ref="test_turn",
    )
    assert result["ok"] is True
    assert "Joe Rogan" in result["humans"]
    assert "Chase Hughes" in result["humans"]
    assert result["event"]["action"] == "listened_with_alice"

    host = hic.lookup_human_name("Joe Rogan", state_dir=state_dir, exact_only=True)
    guest = hic.lookup_human_name("Chase Hughes", state_dir=state_dir, exact_only=True)
    assert host.get("human_id") == "joe_rogan"
    assert guest.get("human_id") == "chase_hughes"


def test_jre_title_parser_links_eric_weinstein(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    now = time.time()
    result = hic.ingest_owner_turn(
        "/sc Joe Rogan Experience #2503 - Eric Weinstein",
        state_dir=state_dir,
        now=now,
        evidence_ref="test_jre",
    )
    assert result["ok"] is True
    guest = hic.lookup_human_name("Eric Weinstein", state_dir=state_dir, exact_only=True)
    assert guest.get("canonical_name") == "Eric Weinstein"
    assert result["event"]["guest_human_id"] == guest.get("human_id")


def test_fuzzy_collision_guard_joe_not_joe_rogan(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    hic.upsert_human("Joe Rogan", state_dir=state_dir)
    hic.upsert_human("Joel Osteen", state_dir=state_dir)
    joe = hic.lookup_human_name("Joe", state_dir=state_dir, exact_only=True)
    rogan = hic.lookup_human_name("Joe Rogan", state_dir=state_dir, exact_only=True)
    assert not joe or joe.get("canonical_name") != "Joe Rogan"
    assert rogan.get("canonical_name") == "Joe Rogan"


def test_answer_human_memory_query_returns_host_and_guest(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    now = time.time()
    hic.ingest_owner_turn(
        "listening to Joe Rogan and his guest Chase Hughes",
        state_dir=state_dir,
        now=now,
    )
    reply = hic.answer_human_memory_query(
        "Alice, remember the podcast we were about to listen to?",
        state_dir=state_dir,
        now=now + 10,
    )
    assert "Joe Rogan" in reply
    assert "Chase Hughes" in reply
    assert "Guest:" in reply


def test_generic_remember_me_does_not_trigger_podcast_recall(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    now = time.time()
    hic.ingest_owner_turn(
        "listening to Joe Rogan and his guest Chase Hughes",
        state_dir=state_dir,
        now=now,
    )

    reply = hic.answer_human_memory_query(
        "do you remember me?",
        state_dir=state_dir,
        now=now + 10,
    )

    assert reply == ""


def test_backfill_observed_humans_idempotent(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    first = hic.backfill_observed_humans(state_dir=state_dir)
    second = hic.backfill_observed_humans(state_dir=state_dir)
    assert first["ok"] is True
    assert second["ok"] is True
    assert hic.lookup_human_name("Eric Weinstein", state_dir=state_dir)["canonical_name"] == "Eric Weinstein"
    assert hic.lookup_human_name("George", state_dir=state_dir)["human_id"] == hic.DEFAULT_OWNER_HUMAN_ID


def test_human_identity_memory_block_surfaces_receipts(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    hic.backfill_observed_humans(state_dir=state_dir)
    block = hic.human_identity_memory_block(
        "remember the podcast with Joe Rogan?",
        state_dir=state_dir,
    )
    assert "HUMAN IDENTITY CONSTANTS" in block
    assert "Joe Rogan" in block
    assert "Owner event" in block


def test_talk_prompt_source_wires_human_identity_memory_block():
    source = Path("Applications/sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")
    assert "human_identity_memory_block" in source
    assert "swarm_human_identity_constants" in source


def test_ingest_media_context_from_cowatch_title(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    result = hic.ingest_media_context(
        "Joe Rogan Experience #2513 - Dean Radin - YouTube",
        state_dir=state_dir,
        evidence_ref="cowatch:test",
    )
    assert result["ok"] is True
    guest = hic.lookup_human_name("Dean Radin", state_dir=state_dir, exact_only=True)
    assert guest.get("canonical_name") == "Dean Radin"


def test_answer_human_memory_query_hydrates_recent_youtube_title(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    now = 1_781_300_000.0
    (state_dir / "youtube_context.jsonl").write_text(
        json.dumps(
            {
                "ts": now - 30,
                "title": "Joe Rogan Experience #2513 - Dean Radin - YouTube",
                "video_id": "dean_radin_video",
                "status": "empty_captions",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    reply = hic.answer_human_memory_query(
        "do you remember the guest on the podcast?",
        state_dir=state_dir,
        now=now,
    )

    assert "Joe Rogan" in reply
    assert "Dean Radin" in reply
    assert "Guest:" in reply
    assert "youtube_context:dean_radin_video" in reply


def test_recent_media_ingest_dedupes_same_jre_video(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    now = 1_781_300_000.0
    rows = [
        {
            "ts": now - 40,
            "title": "Joe Rogan Experience #2513 - Dean Radin - YouTube",
            "video_id": "same_video",
        },
        {
            "ts": now - 20,
            "title": "(1) Joe Rogan Experience #2513 - Dean Radin - YouTube",
            "video_id": "same_video",
        },
    ]
    (state_dir / "youtube_context.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )

    first = hic.ingest_recent_media_contexts_from_ledgers(state_dir=state_dir, now=now)
    second = hic.ingest_recent_media_contexts_from_ledgers(state_dir=state_dir, now=now)
    events = hic.recall_owner_events(action="listened_with_alice", state_dir=state_dir)

    assert first["count"] == 1
    assert second["count"] == 0
    assert len(events) == 1


def test_consolidate_merges_george_fork_into_george_anton_m5(tmp_path):
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir(parents=True)
    path = state_dir / hic.JSONL_NAME
    rows = [
        {
            "schema": hic.SCHEMA,
            "human_id": "george",
            "canonical_name": "George",
            "aliases": ["george", "George"],
            "status": "alive",
            "source": "tournament_backfill",
            "confidence": 0.85,
            "first_seen_ts": 10.0,
            "last_seen_ts": 10.0,
            "linked_events_count": 0,
        },
        {
            "schema": hic.SCHEMA,
            "human_id": "george_anton_m5",
            "canonical_name": "George",
            "aliases": ["George", "the architect"],
            "status": "alive",
            "source": "owner_hardware",
            "confidence": 1.0,
            "first_seen_ts": 5.0,
            "last_seen_ts": 20.0,
            "linked_events_count": 0,
        },
        {
            "schema": hic.SCHEMA,
            "human_id": "george_anton_m5",
            "canonical_name": "George",
            "aliases": ["George", "ioan"],
            "status": "alive",
            "source": "owner_hardware",
            "confidence": 1.0,
            "first_seen_ts": 5.0,
            "last_seen_ts": 30.0,
            "linked_events_count": 0,
        },
        {
            "schema": hic.SCHEMA,
            "human_id": "joe_rogan",
            "canonical_name": "Joe Rogan",
            "aliases": ["Joe Rogan"],
            "status": "alive",
            "source": "owner_confirmed",
            "confidence": 0.9,
            "first_seen_ts": 1.0,
            "last_seen_ts": 2.0,
            "linked_events_count": 0,
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    receipt = hic.consolidate_human_identity_ledger(state_dir=state_dir, write=True)

    assert receipt["before_rows"] == 4
    assert receipt["after_rows"] == 2
    assert "george" not in receipt["human_ids"]
    assert hic.OWNER_HUMAN_ID in receipt["human_ids"]

    owner = hic.lookup_human_name("George", state_dir=state_dir, exact_only=True)
    assert owner is not None
    assert owner["human_id"] == hic.OWNER_HUMAN_ID
    assert "george" in [a.lower() for a in owner.get("aliases", [])]
