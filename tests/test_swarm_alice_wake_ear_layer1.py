"""Tests for Layer 1 wake-name fast-path.

Architect 2026-05-14 06:40: "THE OPERATING SYSTEM NEEDS TO RESPOND
BETTER TO HER NAME REGISTERED IN LAYER 1 — HERE ALICE I CALL HER AND
SHE IS NOT RESPONDING".

Failure transcript (verbatim from architect's chat):
  Ioan: "Alice, I have paused the video. What do you think about this?"
  Alice: "Since you haven't specified which video..." ← FAIL (asked which video)
  Ioan: "or I just paused the video, I just told you the video just now."
  Alice: "Understood. You paused the visual input. on now?" ← FAIL (broken)
  Ioan: "Alice can you see the screen? I quote your name Alice."
  Alice: "My eye scanned 13s ago and saw no face..." ← FAIL (non sequitur)
  Ioan: "Alice."  ← architect had to yell
  Alice: "Alice. What is on your mind?"  ← finally fired

Root cause: media-app context + low STT conf was pushing direct turns
below threshold even when the user clearly said "Alice ___".

Fix: Layer 1 fast-path. If the first token of the utterance matches a
wake target (similarity ≥ 0.85) AND there are ≥2 words total, route
DIRECT immediately. Hearing the name is attention — Layer 1.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_alice_wake_ear import (
    _OWNER_DIRECT_RE,
    classify_wake_turn,
)


# ── Fast-path: the exact architect-screenshot turns ─────────────

def test_architect_turn_1_alice_paused_video_routes_direct():
    """'Alice, I have paused the video...' — must go DIRECT."""
    out = classify_wake_turn(
        "Alice, I have paused the video. What do you think about this?",
        stt_conf=0.73,
        focus_context="Safari YouTube",
        acoustic_fingerprint={
            "channel_cue": "nearfield_voice_likely",
            "nearfield_voice_likelihood": 0.6,
            "farfield_replay_likelihood": 0.2,
        },
    )
    assert out["route"] == "direct", out
    assert out["reason"] == "layer1_name_at_utterance_start"
    assert out["wake_score"] >= 0.9


def test_architect_turn_3_alice_can_you_see_routes_direct_at_low_stt():
    """'Alice can you see the screen? I quote your name Alice.' — must
    go DIRECT even with stt_conf=0.46 (which was the actual failure)."""
    out = classify_wake_turn(
        "Alice can you see the screen? I quote your name Alice.",
        stt_conf=0.46,
        focus_context="Safari YouTube",
        acoustic_fingerprint={
            "channel_cue": "nearfield_voice_likely",
            "nearfield_voice_likelihood": 0.55,
            "farfield_replay_likelihood": 0.25,
        },
    )
    assert out["route"] == "direct", out
    assert out["reason"] == "layer1_name_at_utterance_start"


def test_no_name_video_narration_stays_ambient():
    """'or I just paused the video...' — NO 'Alice' at the start.
    Must stay AMBIENT (this is just talking ABOUT the video)."""
    out = classify_wake_turn(
        "or I just paused the video, I just told you the video just now.",
        stt_conf=0.73,
        focus_context="Safari YouTube",
        acoustic_fingerprint={
            "channel_cue": "nearfield_voice_likely",
            "nearfield_voice_likelihood": 0.55,
            "farfield_replay_likelihood": 0.20,
        },
    )
    assert out["route"] == "ambient", out
    assert "layer1" not in out["reason"]  # fast-path did NOT fire


def test_single_word_alice_still_works_via_normal_path():
    """'Alice.' alone — fast-path requires ≥2 words, so this goes
    through normal path and should still wake direct."""
    out = classify_wake_turn(
        "Alice.",
        stt_conf=1.0,
        focus_context="",
        acoustic_fingerprint={
            "channel_cue": "nearfield_voice_likely",
            "nearfield_voice_likelihood": 0.7,
            "farfield_replay_likelihood": 0.15,
        },
    )
    assert out["route"] == "direct", out
    # Normal path reason (NOT the layer1 fast-path)
    assert "layer1" not in out["reason"]


def test_pure_video_narration_silenced():
    """Long narrative sentence with NO name during co-watch must stay ambient."""
    out = classify_wake_turn(
        "In this video we explore the implications of multi-modal foundation models in drug discovery.",
        stt_conf=0.85,
        focus_context="Safari YouTube",
        acoustic_fingerprint={
            "channel_cue": "farfield_replay_likely",
            "nearfield_voice_likelihood": 0.2,
            "farfield_replay_likelihood": 0.7,
        },
    )
    assert out["route"] == "ambient", out


# ── Fast-path requires actual name at FIRST position ────────────

def test_name_not_at_start_does_not_trigger_fastpath():
    """Name buried mid-sentence should NOT trigger the fast-path."""
    out = classify_wake_turn(
        "I was telling Alice yesterday about the migration.",
        stt_conf=0.85,
        focus_context="",
        acoustic_fingerprint={
            "nearfield_voice_likelihood": 0.6,
            "farfield_replay_likelihood": 0.2,
        },
    )
    assert "layer1_name_at_utterance_start" != out["reason"], out


def test_fastpath_accepts_george_too():
    """Layer 1 fast-path covers any registered wake target — the owner
    vocative as well (so 'George, listen' would also fast-wake if Alice
    addressed him by name from the kernel cascade)."""
    # The default targets include 'george'. Address with it at start.
    out = classify_wake_turn(
        "George, can you take a look?",
        stt_conf=0.8,
        focus_context="",
        acoustic_fingerprint={
            "nearfield_voice_likelihood": 0.6,
            "farfield_replay_likelihood": 0.2,
        },
    )
    # George is in _active_target_names — fast-path should fire.
    assert out["route"] == "direct"
    assert out["reason"] == "layer1_name_at_utterance_start"


# ── Expanded _OWNER_DIRECT_RE coverage ───────────────────────────

@pytest.mark.parametrize("phrase", [
    "I have paused the video.",
    "I told you that yesterday.",
    "I just saw the screen.",
    "I heard the announcement.",
    "I see what you mean.",
    "I read the doctrine.",
    "I gave you the path.",
    "I want to know.",
    "I would like a summary.",
    "I will read it.",
])
def test_expanded_i_verb_phrases_match_direct_shape(phrase):
    """All these were missed by the prior _OWNER_DIRECT_RE."""
    assert _OWNER_DIRECT_RE.search(phrase) is not None, (
        f"_OWNER_DIRECT_RE failed to match: {phrase!r}"
    )


@pytest.mark.parametrize("phrase", [
    "Did you see the receipt?",
    "Have you read my note?",
    "Would you respond now?",
    "Should you check the ledger?",
    "Show me the receipts.",
    "Tell me what you found.",
    "Help me debug this.",
    "Pause the video now.",
    "Open the file.",
    "Change the wallpaper to default.",
])
def test_expanded_verb_questions_match_direct_shape(phrase):
    """Direct address verb-first imperatives + did/have/would questions."""
    assert _OWNER_DIRECT_RE.search(phrase) is not None, (
        f"_OWNER_DIRECT_RE failed to match: {phrase!r}"
    )


@pytest.mark.parametrize("phrase", [
    "The video was uploaded yesterday.",
    "She paused the meeting.",
    "He showed up late.",
    "Mountains stretch into the distance.",
])
def test_third_person_does_not_match_direct_shape(phrase):
    """Third-person narration should NOT match — the regex is about
    direct address TO the body, not narration ABOUT others."""
    # These have words like "showed" or "paused" but no first-/second-
    # person pronouns or imperative-with-direct-object — should NOT match
    assert _OWNER_DIRECT_RE.search(phrase) is None, (
        f"_OWNER_DIRECT_RE false-positive: {phrase!r}"
    )


# ── Edge cases ──────────────────────────────────────────────────

def test_empty_text_returns_ambient_empty_reason():
    out = classify_wake_turn("", stt_conf=0.5)
    assert out["route"] == "ambient"
    assert out["reason"] == "empty_text"


def test_fastpath_does_not_fire_on_word_alice_with_low_similarity_first_token():
    """A non-name first word should NOT trigger fast-path even if Alice
    appears later."""
    out = classify_wake_turn(
        "Yesterday Alice came over.",
        stt_conf=0.9,
        focus_context="",
        acoustic_fingerprint={
            "nearfield_voice_likelihood": 0.5,
            "farfield_replay_likelihood": 0.3,
        },
    )
    # "Yesterday" first token → no fast-path
    assert out["reason"] != "layer1_name_at_utterance_start"
