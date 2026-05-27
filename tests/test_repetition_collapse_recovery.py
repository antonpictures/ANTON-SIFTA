"""Tests for swarm_repetition_collapse_recovery — tasks #46 + #55."""

from __future__ import annotations

import json
import time

import pytest

from System.swarm_repetition_collapse_recovery import (
    RepetitionCollapseConfig,
    RepetitionDiagnosis,
    diagnose_repetition,
    salvage_pre_collapse,
    record_silence_event,
    format_self_narration,
    get_last_silence_event,
    should_self_narrate,
    SILENCE_LEDGER,
)


@pytest.fixture(autouse=True)
def _patch_ledger(tmp_path, monkeypatch):
    ledger = tmp_path / "silence_events.jsonl"
    monkeypatch.setattr(
        "System.swarm_repetition_collapse_recovery.SILENCE_LEDGER", ledger
    )
    return ledger


class TestDiagnoseRepetition:
    def test_no_repetition_in_normal_text(self):
        text = "Alice is an embodied agent on M5 silicon with persistent memory."
        result = diagnose_repetition(text)
        assert result.detected is False

    def test_detects_obvious_repetition(self):
        pattern = "hello "
        text = "Some prefix text. " + pattern * 10
        result = diagnose_repetition(text)
        assert result.detected is True
        assert result.repeat_count >= 5
        assert result.pattern_period == len(pattern)

    def test_detects_short_period_repetition(self):
        text = "Normal start. " + "abc" * 20
        result = diagnose_repetition(text)
        assert result.detected is True
        assert result.repeating_pattern == "abc"
        assert result.pattern_period == 3

    def test_empty_text_returns_no_detection(self):
        assert diagnose_repetition("").detected is False
        assert diagnose_repetition(None).detected is False  # type: ignore[arg-type]

    def test_custom_config_changes_threshold(self):
        pattern = "xy" * 6
        text = "Start. " + "xy" * 6
        strict = RepetitionCollapseConfig(min_repeats=3, min_period=2)
        result = diagnose_repetition(text, config=strict)
        assert result.detected is True

    def test_below_threshold_not_detected(self):
        text = "Start. " + "abc" * 3
        result = diagnose_repetition(text)
        assert result.detected is False


class TestSalvagePreCollapse:
    def test_salvages_prefix_before_loop(self):
        prefix = "This is useful content that should survive."
        text = prefix + " " + "loop" * 20
        diagnosis = diagnose_repetition(text)
        assert diagnosis.detected is True
        salvaged = salvage_pre_collapse(text, diagnosis)
        assert "useful content" in salvaged

    def test_no_collapse_returns_full_text(self):
        text = "Normal text with no repetition."
        diagnosis = diagnose_repetition(text)
        assert salvage_pre_collapse(text, diagnosis) == text


class TestSelfNarration:
    def test_format_self_narration_describes_collapse(self):
        text = "Good prefix. " + "xyz" * 30
        diagnosis = diagnose_repetition(text)
        assert diagnosis.detected is True
        narration = format_self_narration(diagnosis)
        assert "repeating loop" in narration
        assert "repetition-collapse detector" in narration

    def test_no_narration_when_no_collapse(self):
        diagnosis = RepetitionDiagnosis(detected=False)
        assert format_self_narration(diagnosis) == ""


class TestSilenceLedger:
    def test_record_and_read_silence_event(self, _patch_ledger):
        text = "Prefix. " + "rep!" * 30
        diagnosis = diagnose_repetition(text)
        assert diagnosis.detected is True
        row_id = record_silence_event(diagnosis, model="test-model", turn_id="turn-1")
        assert row_id

        event = get_last_silence_event()
        assert event is not None
        assert event["id"] == row_id
        assert event["kind"] == "repetition_collapse"
        assert event["model"] == "test-model"

    def test_no_events_returns_none(self, _patch_ledger):
        assert get_last_silence_event() is None


class TestShouldSelfNarrate:
    def test_recent_event_triggers_narration(self):
        event = {"ts": time.time() - 10}
        assert should_self_narrate(event) is True

    def test_old_event_does_not_trigger(self):
        event = {"ts": time.time() - 300}
        assert should_self_narrate(event) is False

    def test_none_event_does_not_trigger(self):
        assert should_self_narrate(None) is False
