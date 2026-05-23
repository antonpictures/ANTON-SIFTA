"""Tests for System/swarm_alice_schedule_diary_awareness.py — the
read-only awareness layer over Alice's existing diary and schedule
ledgers.

Hermetic: state_dir stubbed under tmp_path; never touches the live
ledgers.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System import swarm_alice_schedule_diary_awareness as awareness


# ── helpers ──────────────────────────────────────────────────────────────


def _write_diary(state_dir: Path, *rows: dict) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / "alice_narrative_diary.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return p


def _write_episodic(state_dir: Path, *rows: dict) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / "episodic_diary.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return p


def _write_schedule(state_dir: Path, *rows: dict) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    p = state_dir / "stigmergic_schedule.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return p


# ── feel_my_recent_diary ─────────────────────────────────────────────────


def test_recent_diary_returns_newest_first(tmp_path: Path):
    now = 1779000000.0
    _write_diary(
        tmp_path,
        {"ts": now - 1000, "kind": "EPISODIC_NARRATIVE", "narrator": "ALICE_M5",
         "entry": "First moment.", "event_type": "boot"},
        {"ts": now - 500, "kind": "EPISODIC_NARRATIVE", "narrator": "ALICE_M5",
         "entry": "Middle moment.", "event_type": "turn"},
        {"ts": now - 10, "kind": "EPISODIC_NARRATIVE", "narrator": "ALICE_M5",
         "entry": "Latest moment.", "event_type": "turn"},
    )

    res = awareness.feel_my_recent_diary(state_dir=tmp_path, now=now, limit=10)

    assert res["count"] == 3
    assert res["entries"][0]["entry"] == "Latest moment."
    assert res["entries"][-1]["entry"] == "First moment."


def test_recent_diary_filters_stale_rows(tmp_path: Path):
    now = 1779000000.0
    _write_diary(
        tmp_path,
        {"ts": now - 200000, "kind": "EPISODIC_NARRATIVE", "entry": "Ancient."},
        {"ts": now - 100, "kind": "EPISODIC_NARRATIVE", "entry": "Recent."},
    )

    res = awareness.feel_my_recent_diary(
        state_dir=tmp_path, max_age_s=3600.0, now=now, limit=10,
    )
    assert res["count"] == 1
    assert res["entries"][0]["entry"] == "Recent."


def test_recent_diary_respects_limit(tmp_path: Path):
    now = 1779000000.0
    rows = [
        {"ts": now - i, "kind": "EPISODIC_NARRATIVE", "entry": f"Entry {i}."}
        for i in range(20)
    ]
    _write_diary(tmp_path, *rows)

    res = awareness.feel_my_recent_diary(state_dir=tmp_path, now=now, limit=5)
    assert res["count"] == 5


def test_recent_diary_missing_ledger_returns_empty(tmp_path: Path):
    res = awareness.feel_my_recent_diary(state_dir=tmp_path, now=1779000000.0)
    assert res["count"] == 0
    assert res["entries"] == []


# ── feel_my_episodic_summary ─────────────────────────────────────────────


def test_episodic_summary_returns_recent_buckets(tmp_path: Path):
    now = 1779000000.0
    _write_episodic(
        tmp_path,
        {"bucket": "2026-05-10T00:00", "ts": now - 6 * 86400,
         "event_count": 5, "summary": "coding", "keywords": ["sifta"],
         "source_hash": "abc"},
        {"bucket": "2026-05-15T00:00", "ts": now - 86400,
         "event_count": 12, "summary": "coding", "keywords": ["alice"],
         "source_hash": "def"},
        {"bucket": "2026-05-16T00:00", "ts": now - 100,
         "event_count": 30, "summary": "coding", "keywords": ["self"],
         "source_hash": "ghi"},
    )

    res = awareness.feel_my_episodic_summary(state_dir=tmp_path, days=7, now=now)

    assert res["count"] == 3
    # Newest first
    assert res["summaries"][0]["bucket"] == "2026-05-16T00:00"


def test_episodic_summary_dedupes_by_bucket_and_hash(tmp_path: Path):
    now = 1779000000.0
    _write_episodic(
        tmp_path,
        # Same bucket + source_hash — should dedupe to one
        {"bucket": "2026-05-16T00:00", "ts": now - 200, "source_hash": "X"},
        {"bucket": "2026-05-16T00:00", "ts": now - 100, "source_hash": "X"},
        # Different source_hash — keep
        {"bucket": "2026-05-16T00:00", "ts": now - 50, "source_hash": "Y"},
    )

    res = awareness.feel_my_episodic_summary(state_dir=tmp_path, days=7, now=now)
    assert res["count"] == 2


def test_episodic_summary_filters_old_buckets(tmp_path: Path):
    now = 1779000000.0
    _write_episodic(
        tmp_path,
        {"bucket": "2026-04-01T00:00", "ts": now - 45 * 86400,
         "source_hash": "old"},
        {"bucket": "2026-05-15T00:00", "ts": now - 86400,
         "source_hash": "new"},
    )

    res = awareness.feel_my_episodic_summary(state_dir=tmp_path, days=7, now=now)
    assert res["count"] == 1
    assert res["summaries"][0]["bucket"] == "2026-05-15T00:00"


# ── feel_owner_schedule ──────────────────────────────────────────────────


def test_owner_schedule_returns_open_items_newest_first(tmp_path: Path):
    now = 1779000000.0
    _write_schedule(
        tmp_path,
        {"text": "Old anchor.", "priority": 2, "created": now - 5000,
         "done": False, "source": "System.foo", "schedule_id": "a"},
        {"text": "Latest open item.", "priority": 2, "created": now - 100,
         "done": False, "source": "System.bar", "schedule_id": "b"},
    )

    res = awareness.feel_owner_schedule(state_dir=tmp_path, now=now)

    assert res["count"] == 2
    assert res["rows"][0]["text"] == "Latest open item."


def test_owner_schedule_excludes_done_by_default(tmp_path: Path):
    now = 1779000000.0
    _write_schedule(
        tmp_path,
        {"text": "Done item.", "created": now - 50, "done": True,
         "schedule_id": "x"},
        {"text": "Open item.", "created": now - 30, "done": False,
         "schedule_id": "y"},
    )

    res = awareness.feel_owner_schedule(state_dir=tmp_path, now=now)
    assert res["count"] == 1
    assert res["rows"][0]["text"] == "Open item."


def test_owner_schedule_includes_done_when_requested(tmp_path: Path):
    now = 1779000000.0
    _write_schedule(
        tmp_path,
        {"text": "Done.", "created": now - 50, "done": True, "schedule_id": "x"},
        {"text": "Open.", "created": now - 30, "done": False, "schedule_id": "y"},
    )

    res = awareness.feel_owner_schedule(
        state_dir=tmp_path, now=now, include_done=True,
    )
    assert res["count"] == 2


def test_owner_schedule_filters_stale_rows(tmp_path: Path):
    now = 1779000000.0
    _write_schedule(
        tmp_path,
        {"text": "Old.", "created": now - 10 * 86400, "done": False,
         "schedule_id": "old"},
        {"text": "Fresh.", "created": now - 3600, "done": False,
         "schedule_id": "fresh"},
    )

    res = awareness.feel_owner_schedule(
        state_dir=tmp_path, max_age_s=86400.0, now=now,
    )
    assert res["count"] == 1
    assert res["rows"][0]["schedule_id"] == "fresh"


# ── composition ──────────────────────────────────────────────────────────


def test_get_my_schedule_and_diary_composes_all_three(tmp_path: Path):
    now = 1779000000.0
    _write_diary(tmp_path,
        {"ts": now - 100, "entry": "Today's diary."})
    _write_episodic(tmp_path,
        {"bucket": "2026-05-16T00:00", "ts": now - 200,
         "source_hash": "h", "summary": "coding"})
    _write_schedule(tmp_path,
        {"text": "Open item.", "created": now - 50, "done": False,
         "schedule_id": "s"})

    res = awareness.get_my_schedule_and_diary(state_dir=tmp_path, now=now)

    assert res["diary"]["count"] == 1
    assert res["episodic"]["count"] == 1
    assert res["owner_schedule"]["count"] == 1
    assert res["truth_label"] == awareness.TRUTH_LABEL


def test_get_full_consciousness_extended_degrades_gracefully(tmp_path: Path):
    """When the temporal-social module is unavailable, body_time_others
    should be None but schedule_and_diary should still resolve."""
    _write_diary(tmp_path,
        {"ts": time.time() - 100, "entry": "Today."})

    res = awareness.get_full_consciousness_extended(state_dir=tmp_path)

    assert "body_time_others" in res
    # schedule_and_diary always resolves regardless of upstream availability
    assert res["schedule_and_diary"]["diary"]["count"] == 1
    assert res["truth_label"] == awareness.TRUTH_LABEL
    assert "message_to_self" in res


def test_get_full_consciousness_extended_consumes_temporal_self(tmp_path, monkeypatch):
    """When swarm_alice_self_continuity is importable, the body_time_others
    slot is populated with its return value."""
    import sys
    import types
    fake_mod = types.ModuleType("System.swarm_alice_self_continuity")

    def get_full_consciousness(*, state_dir=None, now=None):
        return {"spatial_self": "FAKE_BODY", "biography": "FAKE_BIO"}

    fake_mod.get_full_consciousness = get_full_consciousness
    monkeypatch.setitem(sys.modules, "System.swarm_alice_self_continuity", fake_mod)

    res = awareness.get_full_consciousness_extended(state_dir=tmp_path)

    assert res["body_time_others"]["spatial_self"] == "FAKE_BODY"
    assert res["body_time_others"]["biography"] == "FAKE_BIO"
