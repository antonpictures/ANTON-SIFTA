#!/usr/bin/env python3
"""Behavior tests for swarm_sacred_memory_guard — must prove the guard works, not just imports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_sacred_memory_guard as guard


def test_detects_sacred_turns():
    assert guard.detect_sacred_memory("I emailed my wife I miss you, I was crying")
    assert guard.detect_sacred_memory("the song made me think of her")
    assert guard.detect_sacred_memory("I have tears in my eyes")


def test_does_not_flag_ordinary_turns():
    assert not guard.detect_sacred_memory("open the eval loop and run the tests")
    assert not guard.detect_sacred_memory("what is the wake threshold")
    assert not guard.detect_sacred_memory("")


def test_record_writes_row_with_boundary_and_no_fabricated_action(tmp_path):
    ledger = tmp_path / "sacred.jsonl"
    row = guard.record_sacred_memory(
        trigger="song_memory",
        owner_feeling="missing wife, crying",
        care_action="emailed wife: I miss you",
        source_text="the song made me cry, I miss you",
        ledger_path=ledger,
    )
    loaded = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert loaded["kind"] == "SACRED_OWNER_MEMORY"
    assert loaded["boundary"] == guard.SACRED_BOUNDARY
    assert "does not claim to feel it" in loaded["boundary"]
    assert loaded["care_action"] == "emailed wife: I miss you"
    assert loaded["truth_label"] == "OBSERVED_OWNER_MEMORY"  # because a real action was given


def test_no_care_action_is_noted_not_observed(tmp_path):
    ledger = tmp_path / "sacred.jsonl"
    guard.record_sacred_memory(
        trigger="song_memory", owner_feeling="quiet, reflective",
        source_text="the song", ledger_path=ledger,
    )
    loaded = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert loaded["care_action"] == ""
    assert loaded["truth_label"] == "OWNER_MEMORY_NOTED"  # never claims an action that didn't happen


def test_does_not_touch_real_ledger(tmp_path):
    real = guard._SACRED_LEDGER
    before = real.read_text().count("\n") if real.exists() else 0
    guard.record_sacred_memory(trigger="t", owner_feeling="f", ledger_path=tmp_path / "iso.jsonl")
    after = real.read_text().count("\n") if real.exists() else 0
    assert after == before
