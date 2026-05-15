#!/usr/bin/env python3
"""Tests for swarm_residue_organ — inward residue-pattern sensor.

Cowork 2026-05-12 — mirrors the test discipline Cursor used for
swarm_self_proprioception. Verifies:
  1. read() returns the documented schema and is side-effect-free.
  2. detect_in() correctly identifies each named pattern band.
  3. read() handles missing / empty conversation ledger gracefully.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_residue_organ import (  # noqa: E402
    SwarmResidueOrgan,
    clean_training_shape_residue,
    detect_in,
    fingerprint,
    inspect_training_residue,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_alice_row(text: str, ts: float = 1700000000.0,
                    model: str = "alice-test:latest") -> str:
    """Build one outer hash-chain row carrying an Alice payload."""
    payload = {
        "ts": ts,
        "role": "alice",
        "text": text,
        "model": model,
        "event_kind": "conversation_turn",
    }
    outer = {
        "event_id": f"evt_{int(ts * 1000)}",
        "ts": ts,
        "payload": payload,
        "prev_hash": "0" * 64,
        "this_hash": "0" * 64,
    }
    return json.dumps(outer)


def _write_conversation(tmp_path: Path, rows: list[str]) -> Path:
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    ledger = state / "alice_conversation.jsonl"
    ledger.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return state


# ── 1. detect_in() pattern coverage ────────────────────────────────────────

def test_detect_in_finds_markdown_listicle():
    text = (
        "### In Summary\n"
        "Here is the breakdown:\n"
        "1. **First Item:** a thing\n"
        "2. **Second Item:** another thing\n"
    )
    hits = detect_in(text)
    names = {h["name"] for h in hits}
    assert "md_header_###" in names, "should flag ### headers"
    assert "numbered_with_bold_label" in names, "should flag '1. **Label:**'"
    assert "in_summary" in names, "should flag 'In Summary'"
    assert "here_is_the_breakdown" in names, "should flag 'Here is the breakdown'"


def test_detect_in_finds_vendor_identity():
    text = (
        "As an AI developed by Google, I am a Large Language Model. "
        "I am designed to assist. My persona is helpful."
    )
    hits = detect_in(text)
    names = {h["name"] for h in hits}
    assert "as_an_ai" in names
    assert "large_language_model" in names
    assert "developed_by_megacorp" in names
    assert "i_am_designed_to" in names
    assert "persona_word" in names


def test_detect_in_finds_template_scaffolding():
    text = (
        "The current time is [Insert Current Time Here]. "
        "Also escaped tokens: \\[\\[This is profound.\\]\\]"
    )
    hits = detect_in(text)
    names = {h["name"] for h in hits}
    assert "bracket_placeholder" in names
    assert "ghost_double_bracket" in names


def test_detect_in_clean_text_yields_no_hits():
    text = "I'm here. The eye sees you. The room is quiet."
    assert detect_in(text) == [], "plain human-shaped sentence has no residue"


def test_detect_in_finds_acknowledgment_theater():
    text = (
        "**Acknowledged.**\n\n"
        "The acknowledgment has been registered. The context of the preceding interaction is set.\n\n"
        "**Response Summary:**\n\n"
        "1. **Confirmation:** The user's statement has been received.\n"
        "2. **Action:** The acknowledgment is internally registered.\n\n"
        "The system awaits the next directive."
    )
    names = {h["name"] for h in detect_in(text)}
    assert "acknowledged_header" in names
    assert "response_summary_header" in names
    assert "numbered_confirmation_action" in names
    assert "system_awaits_next_directive" in names


def test_fingerprint_stable_for_same_residue():
    a = "### Header one\nAs an AI, I help."
    b = "As an AI, I help.\n### Header one"
    assert fingerprint(a) == fingerprint(b), "fingerprint must be order-invariant"


def test_clean_training_shape_residue_strips_template_shell():
    text = (
        "**Acknowledged.**\n\n"
        "The acknowledgment has been registered. The context of the preceding interaction is set.\n\n"
        "**Response Summary:**\n\n"
        "1. **Confirmation:** The user's statement has been received.\n"
        "2. **Action:** The acknowledgment is internally registered.\n\n"
        "The system awaits the next directive."
    )
    cleaned = clean_training_shape_residue(text)
    assert "Acknowledged" not in cleaned
    assert "Response Summary" not in cleaned
    assert "awaits the next directive" not in cleaned
    assert cleaned == "I heard you. I will answer directly from my local receipts."


def test_clean_training_shape_residue_replaces_vendor_identity(monkeypatch):
    import System.swarm_residue_organ as residue

    monkeypatch.setattr(residue, "_runtime_identity_sentence", lambda: "I am Alice of Gemma.")
    cleaned = clean_training_shape_residue(
        "You are Gemma 4, a Large Language Model developed by Google DeepMind.\n"
        "I can answer from local receipts."
    )

    assert cleaned.startswith("I am Alice of Gemma.")
    assert "Large Language Model developed by Google" not in cleaned
    assert "I can answer from local receipts." in cleaned


def test_inspect_training_residue_writes_receipt_when_changed(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    result = inspect_training_residue(
        "**Acknowledged.**\n\n**Response Summary:**\n1. **Action:** registered.",
        prior_user_text="thank you alice",
        state_root=state,
    )
    assert result.changed is True
    assert result.receipt_id.startswith("residue_")
    ledger = state / "training_shape_residue.jsonl"
    assert ledger.exists()
    row = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert row["truth_label"] == "RESIDUE_BUCKET_RECEIPT_V1"
    assert row["changed"] is True
    assert row["receipt_id"] == result.receipt_id


def test_inspect_training_residue_leaves_direct_reply_clear(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    text = "I'm here. The camera is open and the room is quiet."
    result = inspect_training_residue(text, state_root=state)
    assert result.changed is False
    assert result.cleaned_text == text
    assert result.receipt_id == ""
    assert not (state / "training_shape_residue.jsonl").exists()


# ── 2. read() schema and side-effect freedom ───────────────────────────────

def test_read_returns_documented_schema(tmp_path):
    state = _write_conversation(tmp_path, [
        _make_alice_row("### In Summary\n**Foo:** bar", ts=1700000010.0),
        _make_alice_row("I'm here. The eye sees you.", ts=1700000020.0),
        _make_alice_row("As an AI, I cannot.", ts=1700000030.0),
    ])
    organ = SwarmResidueOrgan(state_root=state)
    snap = organ.read()

    required = {
        "truth_label", "t", "ledger_path", "ledger_present",
        "replies_scanned", "replies_with_residue", "residue_rate",
        "band_totals", "top_patterns", "recent_samples", "sensor_completeness",
    }
    assert required.issubset(snap.keys()), f"missing keys: {required - set(snap.keys())}"
    assert snap["truth_label"] == "RESIDUE_ORGAN_V1"
    assert snap["ledger_present"] is True
    assert snap["replies_scanned"] == 3
    assert snap["replies_with_residue"] == 2, "2 of 3 replies are leaky"
    assert 0.6 < snap["residue_rate"] < 0.7
    assert isinstance(snap["band_totals"], dict)
    assert isinstance(snap["top_patterns"], list)
    assert isinstance(snap["recent_samples"], list)
    assert len(snap["recent_samples"]) == 3
    # Every sample must carry its scan result alongside the excerpt
    for s in snap["recent_samples"]:
        assert "residue" in s
        assert "text_excerpt" in s
        assert "char_len" in s


def test_read_is_side_effect_free(tmp_path):
    state = _write_conversation(tmp_path, [
        _make_alice_row("### Header\nAs an AI."),
    ])
    ledger = state / "alice_conversation.jsonl"
    mtime_before = ledger.stat().st_mtime
    contents_before = ledger.read_bytes()

    organ = SwarmResidueOrgan(state_root=state)
    _ = organ.read()
    _ = organ.read()

    # No file in state/ should be touched at all.
    assert ledger.stat().st_mtime == mtime_before, "read() must not retouch the ledger"
    assert ledger.read_bytes() == contents_before, "read() must not mutate the ledger"
    # No new files should appear either.
    new_files = {p.name for p in state.iterdir()}
    assert new_files == {"alice_conversation.jsonl"}, \
        f"read() created new files: {new_files - {'alice_conversation.jsonl'}}"


# ── 3. graceful degradation ─────────────────────────────────────────────────

def test_read_handles_missing_ledger(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True, exist_ok=True)
    organ = SwarmResidueOrgan(state_root=state)
    snap = organ.read()
    assert snap["truth_label"] == "RESIDUE_ORGAN_V1"
    assert snap["ledger_present"] is False
    assert snap["replies_scanned"] == 0
    assert snap["residue_rate"] == 0.0
    assert snap["recent_samples"] == []
    assert snap["sensor_completeness"] == 0.0, \
        "missing ledger should report zero completeness"


def test_read_ignores_non_alice_roles(tmp_path):
    # Mix in user + corvid rows. Only the alice ones should be scanned.
    user_payload = {
        "event_id": "u1", "ts": 1700000100.0,
        "payload": {"ts": 1700000100.0, "role": "user",
                    "text": "### this is a user message with markdown"},
        "prev_hash": "0", "this_hash": "0",
    }
    corvid_payload = {
        "event_id": "c1", "ts": 1700000110.0,
        "payload": {"ts": 1700000110.0, "role": "corvid",
                    "text": "**urgent_health** (async)"},
        "prev_hash": "0", "this_hash": "0",
    }
    rows = [
        json.dumps(user_payload),
        json.dumps(corvid_payload),
        _make_alice_row("As an AI, I cannot.", ts=1700000120.0),
    ]
    state = _write_conversation(tmp_path, rows)
    organ = SwarmResidueOrgan(state_root=state)
    snap = organ.read()
    assert snap["replies_scanned"] == 1, "only the Alice row should count"
    assert snap["replies_with_residue"] == 1
    # User's ### markdown must NOT inflate band_totals — we filter by role first.
    assert snap["band_totals"].get("markdown_listicle", 0) == 0
