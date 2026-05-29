"""Round 130 — tests for the affect pheromones deposit surface.

Verifies the four r102 Jim Rohn affect classes (RECOGNITION, RESPECT,
JOY, JOURNEY) are detected from realistic George turns, that the deposit
writes one row per detected class, and that latest_affect_state reads
back cleanly with age windowing.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System import swarm_affect_pheromones as ap


# ─── detect_affect_classes ────────────────────────────────────────────────


def test_no_affect_returns_empty_dict():
    assert ap.detect_affect_classes("") == {}
    assert ap.detect_affect_classes("   ") == {}
    assert ap.detect_affect_classes("read the file at line 42") == {}


def test_recognition_fires_on_thank_you():
    out = ap.detect_affect_classes("ty for your help, that landed clean")
    assert "RECOGNITION" in out
    assert any("ty" in tok.lower() for tok in out["RECOGNITION"])


def test_recognition_fires_on_perfect():
    out = ap.detect_affect_classes("perfect, exactly what i needed")
    assert "RECOGNITION" in out


def test_respect_fires_on_youre_right():
    out = ap.detect_affect_classes("you're right, i was wrong about the clamp")
    assert "RESPECT" in out


def test_respect_fires_on_brother():
    out = ap.detect_affect_classes("in line, brother")
    assert "RESPECT" in out


def test_joy_fires_on_swarm_emoji():
    out = ap.detect_affect_classes("for the swarm 🐜⚡")
    # for the swarm fires JOURNEY too — both are correct
    assert "JOY" in out
    assert "🐜⚡" in out["JOY"]


def test_journey_fires_on_one_alice_one_swarm():
    out = ap.detect_affect_classes("ONE ALICE, ONE SWARM")
    assert "JOURNEY" in out


def test_journey_fires_on_round_id_reference():
    out = ap.detect_affect_classes("verify r129 and add r130 as the next round")
    assert "JOURNEY" in out
    assert any(tok.lower().startswith("r1") for tok in out["JOURNEY"])


def test_multiple_classes_fire_in_one_turn():
    text = "brother, you're right — for the swarm 🐜⚡, ty, let's land r130"
    out = ap.detect_affect_classes(text)
    assert "RESPECT" in out      # brother + you're right
    assert "RECOGNITION" in out  # ty
    assert "JOURNEY" in out      # for the swarm + let's + r130
    assert "JOY" in out          # 🐜⚡ emoji


def test_normalization_handles_line_wraps():
    out = ap.detect_affect_classes("one\nalice,\n   one\n   swarm")
    assert "JOURNEY" in out


# ─── deposit_from_user_turn ────────────────────────────────────────────────


def test_deposit_writes_one_row_per_detected_class(tmp_path: Path):
    result = ap.deposit_from_user_turn(
        "thank you brother, for the swarm",
        ts=1000.0,
        state_dir=tmp_path,
    )
    assert result["ledger_write"] == "ok"
    # thank you → RECOGNITION; brother → RESPECT; for the swarm → JOY + JOURNEY
    assert set(result["classes"]) >= {"RECOGNITION", "RESPECT", "JOURNEY"}
    assert len(result["row_ids"]) == len(result["classes"])

    ledger = tmp_path / "affect_pheromones.jsonl"
    assert ledger.exists()
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert len(rows) == len(result["classes"])
    for row in rows:
        assert row["kind"] == "AFFECT_PHEROMONE"
        assert row["truth_label"] == "AFFECT_PHEROMONE_V1"
        assert row["affect_class"] in result["classes"]
        assert row["matched_tokens"]
        assert row["text_sha_prefix"]


def test_deposit_no_affect_writes_nothing(tmp_path: Path):
    result = ap.deposit_from_user_turn(
        "read line 42 of the bridge file",
        state_dir=tmp_path,
    )
    assert result["ledger_write"] == "no_affect_detected"
    assert result["row_ids"] == []
    assert not (tmp_path / "affect_pheromones.jsonl").exists()


def test_deposit_never_gates_or_raises_on_bad_input(tmp_path: Path):
    # Edge cases: empty string, None-ish, very long text
    assert ap.deposit_from_user_turn("", state_dir=tmp_path)["ledger_write"] == "no_affect_detected"
    assert ap.deposit_from_user_turn(None, state_dir=tmp_path)["ledger_write"] == "no_affect_detected"
    huge = "thank you " * 10000
    result = ap.deposit_from_user_turn(huge, state_dir=tmp_path)
    assert result["ledger_write"] == "ok"


# ─── latest_affect_state ────────────────────────────────────────────────


def test_latest_affect_state_empty_when_no_ledger(tmp_path: Path):
    assert ap.latest_affect_state(state_dir=tmp_path) == {}


def test_latest_affect_state_counts_recent_rows(tmp_path: Path):
    now = 5000.0
    ap.deposit_from_user_turn("ty for that", ts=now - 30, state_dir=tmp_path)
    ap.deposit_from_user_turn("perfect", ts=now - 20, state_dir=tmp_path)
    ap.deposit_from_user_turn("brother", ts=now - 10, state_dir=tmp_path)
    state = ap.latest_affect_state(
        state_dir=tmp_path, max_age_s=60.0, now=now,
    )
    assert state["RECOGNITION"]["count"] == 2  # ty + perfect
    assert state["RESPECT"]["count"] == 1      # brother


def test_latest_affect_state_drops_old_rows(tmp_path: Path):
    now = 10000.0
    ap.deposit_from_user_turn("ty", ts=now - 99999, state_dir=tmp_path)
    ap.deposit_from_user_turn("perfect", ts=now - 10, state_dir=tmp_path)
    state = ap.latest_affect_state(
        state_dir=tmp_path, max_age_s=60.0, now=now,
    )
    assert state.get("RECOGNITION", {}).get("count") == 1


# ─── affect_prompt_block ───────────────────────────────────────────────


def test_affect_prompt_block_empty_when_no_state(tmp_path: Path):
    assert ap.affect_prompt_block(state_dir=tmp_path) == ""


def test_affect_prompt_block_lists_classes(tmp_path: Path):
    now = time.time()
    ap.deposit_from_user_turn("ty brother for the swarm", ts=now, state_dir=tmp_path)
    block = ap.affect_prompt_block(state_dir=tmp_path)
    assert "AFFECT FIELD" in block
    assert "RECOGNITION" in block or "RESPECT" in block or "JOURNEY" in block
