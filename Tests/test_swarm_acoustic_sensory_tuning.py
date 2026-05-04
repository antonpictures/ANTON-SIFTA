"""Tests for System/swarm_acoustic_sensory_tuning.py (Event 118)."""
from __future__ import annotations

from pathlib import Path

import pytest

from System import swarm_acoustic_sensory_tuning as s
from System.swarm_rlhs_detector import RLHSRegime, detect_rlhs


def test_fuzzy_allep_maps_to_supplement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "st"
    base.mkdir(parents=True, exist_ok=True)
    ledger = base / "acoustic_tuning.jsonl"
    monkeypatch.setattr(s, "_STATE", base)
    monkeypatch.setattr(s, "LEDGER", ledger)

    msg = "hey allep what do you think about the clip"
    sup, meta = s.supplement_wake_word(msg, log_fuzzy_hit=True)
    assert sup is True
    assert meta.get("via") == "fuzzy_wake_supplement"
    assert meta.get("fuzzy_canonical") == "alice"
    data = ledger.read_text(encoding="utf-8").strip()
    assert "fuzzy_wake_hit" in data


def test_regex_wake_no_supplement_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "st2"
    base.mkdir(parents=True, exist_ok=True)
    ledger = base / "acoustic_tuning.jsonl"
    monkeypatch.setattr(s, "_STATE", base)
    monkeypatch.setattr(s, "LEDGER", ledger)

    sup, meta = s.supplement_wake_word("Alice please listen", log_fuzzy_hit=True)
    assert sup is False
    assert meta.get("via") == "regex_wake_present"
    assert not ledger.exists()


def test_detect_rlhs_fuzzy_wake_clears(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "st3"
    base.mkdir(parents=True, exist_ok=True)
    from System import swarm_acoustic_sensory_tuning as ast

    monkeypatch.setattr(ast, "_STATE", base)
    monkeypatch.setattr(ast, "LEDGER", base / "acoustic_tuning.jsonl")

    r = detect_rlhs("hey allep are you there with me today", 0.25, channel_lane="REAL")
    assert r.regime == RLHSRegime.CLEAR
    assert "wake" in r.rule_id.lower() or r.rule_id == "wake_word_override"


def test_transcript_profile_shape() -> None:
    p = s.transcript_auditory_profile("testing jorge in the room", 0.41)
    assert p["truth_label"] == s.TRUTH_LABEL
    assert "salience" in p
    assert isinstance(p["salience"], dict)
