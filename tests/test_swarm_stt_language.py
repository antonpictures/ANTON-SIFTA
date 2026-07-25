from __future__ import annotations

import json
from pathlib import Path

from System.swarm_stt_language import (
    MULTILINGUAL_EQUIVALENT,
    detected_language,
    is_english_locked,
    is_english_only_model,
    log_detected_language,
    resolve_stt_model,
    stt_language_setting,
)


class _Info:
    """Stand-in for faster-whisper's TranscriptionInfo."""

    def __init__(self, language: str, probability: float) -> None:
        self.language = language
        self.language_probability = probability


def test_default_is_auto_detect_not_english():
    # The defect: both ears passed a hardcoded "en".
    assert stt_language_setting({}) is None
    assert is_english_locked({}) is False


def test_owner_can_pin_a_language():
    assert stt_language_setting({"SIFTA_STT_LANGUAGE": "ro"}) == "ro"
    assert stt_language_setting({"SIFTA_STT_LANGUAGE": "en"}) == "en"
    assert is_english_locked({"SIFTA_STT_LANGUAGE": "en"}) is True
    assert is_english_locked({"SIFTA_STT_LANGUAGE": "ro"}) is False


def test_auto_spellings_all_mean_detect():
    for value in ("", "auto", "AUTO", "none", "detect", "any", "  "):
        assert stt_language_setting({"SIFTA_STT_LANGUAGE": value}) is None, value


def test_english_only_checkpoints_are_recognized():
    # George's live setting was tiny.en — English-only weights.
    assert is_english_only_model("tiny.en") is True
    assert is_english_only_model("base.en") is True
    assert is_english_only_model("small") is False
    assert is_english_only_model("large-v3") is False


def test_english_only_model_is_swapped_for_a_multilingual_one():
    # No parameter can make tiny.en produce Romanian; the weights lack it.
    assert resolve_stt_model("tiny.en", {}) == "tiny"
    for english_only, multilingual in MULTILINGUAL_EQUIVALENT.items():
        assert resolve_stt_model(english_only, {}) == multilingual
        assert is_english_only_model(multilingual) is False


def test_multilingual_models_are_left_alone():
    for name in ("small", "large-v3", "medium", "tiny"):
        assert resolve_stt_model(name, {}) == name


def test_pinned_english_keeps_the_english_only_model():
    # If the owner wants English, an English-only checkpoint is the right tool.
    assert resolve_stt_model("tiny.en", {"SIFTA_STT_LANGUAGE": "en"}) == "tiny.en"


def test_pinning_romanian_still_swaps_the_model():
    assert resolve_stt_model("tiny.en", {"SIFTA_STT_LANGUAGE": "ro"}) == "tiny"


def test_detected_language_reads_faster_whisper_info():
    language, probability = detected_language(_Info("ro", 0.97))
    assert language == "ro"
    assert probability == 0.97


def test_detected_language_survives_a_missing_info_object():
    language, probability = detected_language(None)
    assert language == "und"
    assert probability == 0.0


def test_detection_is_receipted(tmp_path):
    row = log_detected_language(
        _Info("ro", 0.93),
        "Foarte bine Alice, vorbeste romaneste cu mine",
        "small",
        surface="ambient_room",
        state_dir=tmp_path,
    )

    assert row["language"] == "ro"
    assert row["surface"] == "ambient_room"
    assert row["requested_language"] == "auto"

    written = json.loads((tmp_path / "stt_language.jsonl").read_text(encoding="utf-8").strip())
    assert written["language"] == "ro"
    assert written["language_probability"] == 0.93
    assert written["truth_label"] == "OBSERVED_STT_LANGUAGE_V1"


def test_receipt_never_raises_on_an_unwritable_directory(tmp_path):
    blocked = tmp_path / "not_a_dir"
    blocked.write_text("i am a file")

    row = log_detected_language(_Info("en", 0.5), "hello", "small", state_dir=blocked / "sub")

    # The ear must keep working even when the ledger cannot be written.
    assert row["language"] == "en"
