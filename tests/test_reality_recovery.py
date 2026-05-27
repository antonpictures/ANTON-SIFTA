"""Tests for swarm_reality_recovery — task #57."""

from __future__ import annotations

import json

import pytest

from System.swarm_reality_recovery import (
    CorrectionDetection,
    RecoveryResponse,
    detect_user_correction,
    generate_recovery_response,
    record_recovery_event,
    RECOVERY_LEDGER,
)


@pytest.fixture(autouse=True)
def _patch_ledger(tmp_path, monkeypatch):
    ledger = tmp_path / "reality_recovery_events.jsonl"
    monkeypatch.setattr(
        "System.swarm_reality_recovery.RECOVERY_LEDGER", ledger
    )
    return ledger


class TestDetectUserCorrection:
    def test_detects_audio_capture_correction(self):
        text = "Alice, you captured the previous conversation with tts microphone, sometimes mispells."
        result = detect_user_correction(text)
        assert result.is_correction is True
        assert result.correction_type == "audio_capture_error"

    def test_detects_phone_call_correction(self):
        text = "I was on a phone call with my friend Carlton from marketing."
        result = detect_user_correction(text)
        assert result.is_correction is True
        assert result.correction_type == "side_conversation_misattribution"

    def test_detects_general_correction(self):
        text = "No, I said George but the voice detector misspelled it."
        result = detect_user_correction(text)
        assert result.is_correction is True

    def test_normal_text_not_correction(self):
        text = "Alice, ask Grok to code the tournament."
        result = detect_user_correction(text)
        assert result.is_correction is False

    def test_empty_text_not_correction(self):
        assert detect_user_correction("").is_correction is False
        assert detect_user_correction("   ").is_correction is False

    def test_transcription_error_type(self):
        text = "The voice detector misspells words sometimes."
        result = detect_user_correction(text)
        assert result.is_correction is True
        assert result.correction_type == "transcription_error"


class TestGenerateRecoveryResponse:
    def test_audio_capture_recovery(self):
        correction = CorrectionDetection(
            is_correction=True,
            correction_type="audio_capture_error",
            confidence=0.8,
        )
        response = generate_recovery_response(correction)
        assert "Thank you for clarifying" in response.full_response
        assert "microphone" in response.acknowledgment
        assert "What did you actually need" in response.recovery_text

    def test_side_conversation_recovery(self):
        correction = CorrectionDetection(
            is_correction=True,
            correction_type="side_conversation_misattribution",
            confidence=0.7,
        )
        response = generate_recovery_response(correction)
        assert "side conversation" in response.acknowledgment

    def test_no_correction_returns_empty(self):
        correction = CorrectionDetection(is_correction=False)
        response = generate_recovery_response(correction)
        assert response.full_response == ""


class TestRecordRecoveryEvent:
    def test_records_to_ledger(self, _patch_ledger):
        correction = CorrectionDetection(
            is_correction=True,
            correction_type="audio_capture_error",
            confidence=0.8,
            matched_patterns=("pattern1",),
        )
        row_id = record_recovery_event(
            correction, turn_id="turn-7", user_text_preview="you captured audio"
        )
        assert row_id

        lines = _patch_ledger.read_text().strip().split("\n")
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["id"] == row_id
        assert row["kind"] == "reality_recovery"
        assert row["correction_type"] == "audio_capture_error"
