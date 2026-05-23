#!/usr/bin/env python3
"""tests/test_wake_ear_threshold.py — P1 acceptance test from GROK_BIG_BATCH_ORDER_2026-05-21.

Tighten wake name matching so a 0.6-similarity token like "Ace" (common STT mangling of "Alice" from background audio) does NOT trigger a direct wake, while real owner address ("Alice", "Alice, are you there") still does.

This test must be able to fail if the threshold is loosened again.
"""

from __future__ import annotations

from System import swarm_alice_wake_ear as wake


def test_ace_similarity_is_insufficient():
    """ "Ace" must not be treated as a wake name for Alice."""
    match = wake.best_wake_name_match("Ace")
    assert match["target"] in ("", "alice")  # may still return the best candidate
    assert match["similarity"] < wake.MIN_NAME_SIMILARITY, f"0.6-ish similarity for Ace should be below {wake.MIN_NAME_SIMILARITY}"


def test_classify_wake_turn_rejects_ace():
    """classify_wake_turn must return non-direct for bare "Ace" even with good acoustic cues."""
    result = wake.classify_wake_turn(
        "Ace",
        stt_conf=0.85,
        acoustic_fingerprint={"nearfield_voice_likelihood": 0.9, "channel_cue": "nearfield_voice_likely"},
        focus_context="",
    )
    assert result["route"] != "direct", "Ace at 0.6 similarity must not wake direct"
    assert "name_match" in result
    assert result["name_match"].get("similarity", 0.0) < wake.MIN_NAME_SIMILARITY


def test_real_alice_address_still_wakes():
    """Real direct address must still wake."""
    result = wake.classify_wake_turn(
        "Alice, what time is it?",
        stt_conf=0.92,
        acoustic_fingerprint={"nearfield_voice_likelihood": 0.95},
        focus_context="",
    )
    assert result["route"] == "direct"


def test_alice_alone_first_token_fast_path():
    """ "Alice" as first token with more words still takes the high-confidence fast path."""
    result = wake.classify_wake_turn(
        "Alice are you listening to this",
        stt_conf=0.88,
        acoustic_fingerprint={},
        focus_context="",
    )
    # The fast-path for name at start with >=2 words should give direct
    assert result["route"] == "direct"
    assert "layer1_name_at_utterance_start" in result.get("reason", "")


if __name__ == "__main__":
    test_ace_similarity_is_insufficient()
    test_classify_wake_turn_rejects_ace()
    test_real_alice_address_still_wakes()
    test_alice_alone_first_token_fast_path()
    print("All P1 wake-threshold tests passed.")