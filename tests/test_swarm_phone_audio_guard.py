#!/usr/bin/env python3
"""Round 66 tests — Phone-audio guard (§19.3 Failure C close).

Verifies:
  - typed modality is NEVER environmental (Round 49 pin)
  - wake word presence kills the detection (owner addressed Alice)
  - the verbatim §19.3 transcript fires the guard with high confidence
  - clean owner-addressed spoken turn does NOT fire
  - composite scoring: low STT conf + non-owner names + phone greetings
    + fragmentation cumulatively classify environmental audio
  - owner-label in text LOWERS the score
  - the probe reply text matches the Architect-specified shape
  - real .sifta_state/* ledgers untouched (this module is pure read)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from System import swarm_phone_audio_guard as pag


# The exact text George recorded in §19.3 (cleaned of leading speaker tag).
_FAILURE_C_TRANSCRIPT = (
    "Hey, Carlton. Hey, Carlton. Jordan, you're busy. Man, I'm not busy. "
    "I'm here at the computer. I'm good. Hi. I was watching MIT..."
)


# ─── Typed-modality pin ────────────────────────────────────────────────────


def test_typed_modality_is_never_environmental():
    """Even if every other signal screams 'side audio', a typed turn cannot
    be environmental — the owner physically pressed keys."""
    sig = pag.detect_environmental_audio(
        _FAILURE_C_TRANSCRIPT,
        stt_conf=0.65,
        modality="typed",
    )
    assert sig.is_environmental is False
    assert sig.confidence == 0.0
    assert "typed_modality_pin" in sig.reasons


@pytest.mark.parametrize("modality", ["TYPED", "type", "keyboard", "system"])
def test_typed_variants_all_block(modality):
    sig = pag.detect_environmental_audio(
        _FAILURE_C_TRANSCRIPT, stt_conf=0.65, modality=modality,
    )
    assert sig.is_environmental is False


# ─── Wake word short-circuit ───────────────────────────────────────────────


def test_wake_word_alice_kills_detection():
    sig = pag.detect_environmental_audio(
        "Alice, hey Carlton thanks for the call",
        stt_conf=0.55,
        modality="spoken",
    )
    assert sig.is_environmental is False
    assert sig.has_wake_word is True
    assert "wake_word_present" in sig.reasons


def test_wake_word_sifta_also_kills():
    sig = pag.detect_environmental_audio(
        "sifta what's my stgm balance",
        stt_conf=0.6,
        modality="spoken",
    )
    assert sig.is_environmental is False
    assert sig.has_wake_word is True


# ─── The verbatim §19.3 failure transcript ─────────────────────────────────


def test_failure_C_transcript_fires_environmental():
    """Architect-named bug. This must classify as environmental audio."""
    sig = pag.detect_environmental_audio(
        _FAILURE_C_TRANSCRIPT,
        stt_conf=0.65,
        modality="spoken",
        owner_label="George",
    )
    assert sig.is_environmental is True
    assert sig.confidence >= 0.55
    # Multiple non-owner names captured
    assert "carlton" in sig.non_owner_names_seen
    assert "jordan" in sig.non_owner_names_seen
    # Low STT, phone greetings, fragmentation all present
    assert any("low_stt_conf" in r for r in sig.reasons)
    assert any("non_owner_names" in r for r in sig.reasons)
    assert any("phone_greeting" in r for r in sig.reasons)


def test_failure_C_probe_reply_matches_architect_spec():
    sig = pag.detect_environmental_audio(
        _FAILURE_C_TRANSCRIPT,
        stt_conf=0.65,
        modality="spoken",
        owner_label="George",
    )
    assert sig.suggested_reply.startswith("(I caught audio but it sounded like a side conversation")
    assert "Say \"Alice\"" in sig.suggested_reply


# ─── Clean owner-addressed turns do NOT fire ───────────────────────────────


def test_clean_owner_spoken_turn_does_not_fire():
    """No non-owner names, high STT, single clean sentence → no detection."""
    sig = pag.detect_environmental_audio(
        "what is my stgm balance right now",
        stt_conf=0.95,
        modality="spoken",
        owner_label="George",
    )
    assert sig.is_environmental is False


def test_owner_label_in_text_lowers_score():
    """Even spoken with low STT, if 'George' is in the text, lower the score."""
    high_score_text = (
        "George here. Carlton said hi. Jordan you busy."
    )
    sig_no_label = pag.detect_environmental_audio(
        high_score_text, stt_conf=0.55, modality="spoken", owner_label="",
    )
    sig_with_label = pag.detect_environmental_audio(
        high_score_text, stt_conf=0.55, modality="spoken", owner_label="George",
    )
    assert sig_with_label.confidence < sig_no_label.confidence
    assert any("owner_label_in_text" in r for r in sig_with_label.reasons)


# ─── Composite scoring ────────────────────────────────────────────────────


def test_low_stt_alone_below_threshold():
    """Low STT confidence WITHOUT non-owner names / phone greetings should
    NOT cross the 0.55 threshold — could be a noisy mic on a real owner turn."""
    sig = pag.detect_environmental_audio(
        "what time is it",
        stt_conf=0.55,
        modality="spoken",
        owner_label="George",
    )
    assert sig.is_environmental is False


def test_multiple_non_owner_names_alone_do_NOT_fire_at_high_stt():
    """3 non-owner names at high STT without other signals → 0.50 score,
    below 0.55 threshold. Safer to NOT fire: the owner could legitimately
    be reporting to Alice 'Carlton and Jordan came by'. The detector needs
    at LEAST one more signal (low STT, phone greeting, or fragmentation)
    to commit to the environmental classification."""
    sig = pag.detect_environmental_audio(
        "Carlton and Jordan and Daniel were here",
        stt_conf=0.92,
        modality="spoken",
        owner_label="George",
    )
    assert sig.is_environmental is False
    assert len(sig.non_owner_names_seen) >= 3   # but still surfaces the signal


def test_names_plus_low_stt_fire():
    """3 non-owner names PLUS low STT crosses the threshold."""
    sig = pag.detect_environmental_audio(
        "Carlton and Jordan and Daniel were here",
        stt_conf=0.55,
        modality="spoken",
        owner_label="George",
    )
    assert sig.is_environmental is True


def test_phone_greeting_alone_with_low_stt_fires():
    sig = pag.detect_environmental_audio(
        "Hey, Carlton. You're busy. I'm not busy.",
        stt_conf=0.6,
        modality="spoken",
        owner_label="George",
    )
    assert sig.is_environmental is True


def test_fragmentation_alone_below_threshold():
    """High fragmentation but no other signals → does NOT cross threshold."""
    sig = pag.detect_environmental_audio(
        "okay. yes. no. fine. good.",
        stt_conf=0.95,
        modality="spoken",
        owner_label="George",
    )
    # Some fragmentation present but no non-owner names + no phone greetings.
    # 0.25 max for fragmentation alone — below 0.55.
    assert sig.is_environmental is False


# ─── Extra non-owner names extension ──────────────────────────────────────


def test_extra_non_owner_names_extend_the_set():
    sig = pag.detect_environmental_audio(
        "Maria and Pedro were on the call",
        stt_conf=0.6,
        modality="spoken",
        owner_label="George",
        extra_non_owner_names=["Maria", "Pedro"],
    )
    assert "maria" in sig.non_owner_names_seen
    assert "pedro" in sig.non_owner_names_seen


def test_owner_label_excluded_from_non_owner_names():
    sig = pag.detect_environmental_audio(
        "George said the stgm balance",
        stt_conf=0.9,
        modality="spoken",
        owner_label="George",
        extra_non_owner_names=["George"],   # try to trick the filter
    )
    # owner_label always excluded, even if added to extras
    assert "george" not in sig.non_owner_names_seen


# ─── Reply shape ──────────────────────────────────────────────────────────


def test_reply_for_explicit_signal():
    s = pag.EnvironmentalAudioSignal(
        is_environmental=True, confidence=0.8, reasons=(),
        has_wake_word=False, stt_conf=0.5, non_owner_names_seen=(),
        fragmentation_score=0.5, suggested_reply="",
    )
    reply = pag.environmental_audio_reply_for(s)
    assert "side conversation" in reply
    assert "Alice" in reply
    # Plain measurement language — no spiritualism
    assert "I sense" not in reply
    assert "I perceive" not in reply


# ─── Real ledger isolation ─────────────────────────────────────────────────


def test_real_ledgers_untouched():
    """Pure read module — must not mutate any .sifta_state/* file."""
    state = Path(".sifta_state")
    watch = [
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "alice_conversation.jsonl",
    ]
    before = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}

    _ = pag.detect_environmental_audio(
        _FAILURE_C_TRANSCRIPT, stt_conf=0.65, modality="spoken", owner_label="George",
    )
    _ = pag.detect_environmental_audio(
        "alice are you there", stt_conf=0.9, modality="spoken",
    )
    _ = pag.environmental_audio_reply_for(
        pag.EnvironmentalAudioSignal(
            is_environmental=True, confidence=0.9, reasons=(),
            has_wake_word=False, stt_conf=0.5, non_owner_names_seen=(),
            fragmentation_score=0.5, suggested_reply="",
        )
    )

    after = {str(p): (p.stat().st_size if p.exists() else 0) for p in watch}
    for k in before:
        assert before[k] == after[k], f"phone_audio_guard mutated {k}"
