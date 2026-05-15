"""Tests for swarm_alice_memory_gravity — the PIF mass law applied to
Alice's real first-person journal."""
import json
import math
import time
from pathlib import Path

import pytest

from System.swarm_alice_memory_gravity import (
    TRUTH_LABEL,
    TRUTH_BOUNDARY,
    compute_memory_gravity,
    _extract_key,
)


def _write_journal(path: Path, rows):
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# ── extraction unit tests ─────────────────────────────────────────────────

def test_face_event_extracts_person_entity():
    organ, key = _extract_key(
        "face_event", "I saw Ioan George Anton look at the camera."
    )
    assert organ == "face_event"
    assert key == "entity:person:Ioan George Anton"


def test_app_focus_extracts_app_entity():
    organ, key = _extract_key(
        "app_focus",
        "I noticed Ioan George Anton focused on Claude. The Architect's frontmost window is: Claude",
    )
    assert organ == "app_focus"
    assert key == "entity:app:Claude"


def test_conversation_user_maps_to_same_entity_as_face():
    """The critical unification: 'Ioan George Anton said …' and 'I saw
    Ioan George Anton …' must share an entity key so n_organs > 1."""
    _, key_face = _extract_key("face_event", "I saw Ioan George Anton look at the camera.")
    _, key_conv = _extract_key("conversation", "Ioan George Anton said (voice): hi")
    assert key_face == key_conv


def test_ide_doctor_extracts_doctor_entity():
    organ, key = _extract_key(
        "ide_doctor",
        "An IDE Doctor registered: Codex Desktop (GPT-5.5) as Surgeon. Intent: ...",
    )
    assert organ == "ide_doctor"
    assert key.startswith("entity:doctor:Codex Desktop")


def test_unknown_source_returns_namespaced_key():
    organ, key = _extract_key("weird_source", "some line")
    assert organ == "weird_source"
    assert "entity:weird_source" in key


# ── mass-law integration tests on a synthetic journal ─────────────────────

def test_repeated_face_event_climbs_mass(tmp_path):
    j = tmp_path / "journal.jsonl"
    now = 1_000_000.0
    rows = []
    for i in range(20):
        rows.append({
            "ts": now - i,  # most recent first
            "source": "face_event",
            "line": "I saw Ioan George Anton look at the camera.",
        })
    _write_journal(j, rows)
    summary = compute_memory_gravity(
        window_minutes=60, journal_path=j, write=False, now_ts=now,
    )
    top = summary["top_memories"][0]
    assert top["key"] == "entity:person:Ioan George Anton"
    assert top["access_count"] == 20
    # access term = alpha * log(1+20) ≈ 0.5 * 3.04 = 1.52
    # + recency near 1 + organ_term 0.25
    # + top_of_mind 0.4 + baseline 1.0 → ~4.2
    assert top["mass"] > 3.5


def test_cross_organ_entity_gets_n_organs_2(tmp_path):
    j = tmp_path / "journal.jsonl"
    now = 1_000_000.0
    rows = [
        {"ts": now - 1, "source": "face_event",
         "line": "I saw Ioan George Anton look at the camera."},
        {"ts": now - 2, "source": "face_event",
         "line": "I saw Ioan George Anton look at the camera."},
        {"ts": now - 3, "source": "conversation",
         "line": 'Ioan George Anton said (voice, stt=0.8): "hi"'},
    ]
    _write_journal(j, rows)
    summary = compute_memory_gravity(
        window_minutes=60, journal_path=j, write=False, now_ts=now,
    )
    top = summary["top_memories"][0]
    assert top["key"] == "entity:person:Ioan George Anton"
    assert top["n_organs"] == 2
    assert "face_event" in top["organs"] and "conversation" in top["organs"]


def test_old_memories_decay(tmp_path):
    """A memory with age >> halflife should land in compression
    candidates, not at the top."""
    j = tmp_path / "journal.jsonl"
    now = 1_000_000.0
    rows = [
        # Old single mention — 1 hour ago, halflife 600 → 1/64 recency
        {"ts": now - 3600, "source": "youtube_video",
         "line": "YouTube: some forgettable video"},
        # Recent heavy entity
        {"ts": now - 5, "source": "face_event",
         "line": "I saw Ioan George Anton look at the camera."},
        {"ts": now - 6, "source": "face_event",
         "line": "I saw Ioan George Anton look at the camera."},
        {"ts": now - 7, "source": "face_event",
         "line": "I saw Ioan George Anton look at the camera."},
    ]
    _write_journal(j, rows)
    summary = compute_memory_gravity(
        window_minutes=120, journal_path=j, write=False, now_ts=now,
    )
    top_key = summary["top_memories"][0]["key"]
    bottom_keys = {m["key"] for m in summary["compression_candidates"]}
    assert top_key == "entity:person:Ioan George Anton"
    assert any("yt:" in k for k in bottom_keys)


def test_receipt_writes_truth_label(tmp_path):
    j = tmp_path / "journal.jsonl"
    out = tmp_path / "gravity_out.jsonl"
    now = 1_000_000.0
    rows = [
        {"ts": now - 5, "source": "face_event",
         "line": "I saw Ioan George Anton look at the camera."},
        {"ts": now - 10, "source": "app_focus",
         "line": "I noticed Ioan George Anton focused on Claude. The Architect's window: Claude"},
    ]
    _write_journal(j, rows)
    summary = compute_memory_gravity(
        window_minutes=60, journal_path=j, output_path=out,
        write=True, now_ts=now,
    )
    assert summary["truth_label"] == TRUTH_LABEL
    assert summary["truth_class"] == "HYPOTHESIS"
    assert "sha256" in summary
    assert summary["truth_boundary"] == TRUTH_BOUNDARY
    # Ledger has the row.
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["truth_label"] == TRUTH_LABEL


def test_missing_journal_returns_graceful_error(tmp_path):
    """If the journal doesn't exist, return a labelled empty summary
    rather than blow up."""
    summary = compute_memory_gravity(
        window_minutes=60,
        journal_path=tmp_path / "nonexistent.jsonl",
        write=False,
    )
    assert summary["truth_label"] == TRUTH_LABEL
    assert "error" in summary
    assert summary["top_memories"] == []


def test_window_filter_applies(tmp_path):
    """Rows outside the window must not contribute to mass."""
    j = tmp_path / "journal.jsonl"
    now = 1_000_000.0
    rows = [
        # 1 hour ago — well outside a 5-minute window
        {"ts": now - 3600, "source": "face_event",
         "line": "I saw Ioan George Anton look at the camera."},
        # 30 seconds ago — inside the window
        {"ts": now - 30, "source": "face_event",
         "line": "I saw Ioan George Anton look at the camera."},
    ]
    _write_journal(j, rows)
    summary = compute_memory_gravity(
        window_minutes=5, journal_path=j, write=False, now_ts=now,
    )
    assert summary["stats"]["rows_in_window"] == 1
    top = summary["top_memories"][0]
    assert top["access_count"] == 1
