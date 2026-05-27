"""Tests for swarm_audio_source_classifier — tasks #56 + #59."""

from __future__ import annotations

import json

import pytest

from System.swarm_audio_source_classifier import (
    AudioSourceType,
    AudioSourceClassification,
    classify_audio_source,
    get_wake_word_threshold,
    record_classification,
    AUDIO_CLASSIFICATION_LEDGER,
)


@pytest.fixture(autouse=True)
def _patch_ledger(tmp_path, monkeypatch):
    ledger = tmp_path / "audio_source_classifications.jsonl"
    monkeypatch.setattr(
        "System.swarm_audio_source_classifier.AUDIO_CLASSIFICATION_LEDGER", ledger
    )
    return ledger


class TestClassifyAudioSource:
    def test_owner_direct_with_wake_word(self):
        result = classify_audio_source(
            "Alice, ask Grok to code the tournament",
            stt_confidence=0.95,
            has_wake_word=True,
        )
        assert result.source_type == AudioSourceType.OWNER_DIRECT
        assert result.should_respond is True

    def test_side_conversation_low_confidence_no_wake(self):
        result = classify_audio_source(
            "Hey, Carlton. Hey, Carlton. Jordan, you're busy. Man, I'm not busy.",
            stt_confidence=0.65,
            has_wake_word=False,
        )
        assert result.source_type == AudioSourceType.SIDE_CONVERSATION
        assert result.should_respond is False
        assert result.probe_response

    def test_media_playback_with_broadcast_language(self):
        result = classify_audio_source(
            "Welcome back to this video, subscribe and like and share",
            stt_confidence=0.8,
            has_wake_word=False,
            media_playing=True,
        )
        assert result.source_type == AudioSourceType.MEDIA_PLAYBACK
        assert result.should_respond is False

    def test_empty_text_classified_as_ambient(self):
        result = classify_audio_source("")
        assert result.source_type == AudioSourceType.AMBIENT_NOISE
        assert result.should_respond is False

    def test_owner_voice_match_boosts_direct(self):
        result = classify_audio_source(
            "Alice, check the ledger",
            stt_confidence=0.9,
            has_wake_word=True,
            owner_voice_match=0.95,
        )
        assert result.source_type == AudioSourceType.OWNER_DIRECT
        assert result.confidence > 0.5

    def test_non_owner_voice_boosts_side_conversation(self):
        result = classify_audio_source(
            "Hey Jordan, let me tell you about the marketing plan",
            stt_confidence=0.7,
            has_wake_word=False,
            owner_voice_match=0.2,
        )
        assert result.source_type == AudioSourceType.SIDE_CONVERSATION

    def test_media_playing_without_wake_suppresses(self):
        result = classify_audio_source(
            "And then the professor explained the algorithm",
            stt_confidence=0.85,
            has_wake_word=False,
            media_playing=True,
        )
        assert result.should_respond is False

    def test_probe_response_for_side_conversation(self):
        result = classify_audio_source(
            "Hey Carlton, how's the project going",
            stt_confidence=0.65,
            has_wake_word=False,
        )
        assert "side conversation" in result.probe_response.lower()


class TestWakeWordThreshold:
    def test_higher_during_media(self):
        assert get_wake_word_threshold(media_playing=True) > get_wake_word_threshold(
            media_playing=False
        )

    def test_default_threshold(self):
        assert 0.0 < get_wake_word_threshold() < 1.0


class TestRecordClassification:
    def test_records_to_ledger(self, _patch_ledger):
        cls = AudioSourceClassification(
            source_type=AudioSourceType.SIDE_CONVERSATION,
            confidence=0.8,
            reasons=("non_owner_addressee_detected",),
            should_respond=False,
            probe_response="side convo",
        )
        row_id = record_classification(cls, turn_id="turn-42")
        assert row_id

        lines = _patch_ledger.read_text().strip().split("\n")
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["id"] == row_id
        assert row["source_type"] == "SIDE_CONVERSATION"
        assert row["turn_id"] == "turn-42"
