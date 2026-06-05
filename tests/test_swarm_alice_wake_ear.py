from __future__ import annotations

import json

from System import swarm_alice_wake_ear as ear


NEARFIELD_FP = {
    "truth_label": "ACOUSTIC_PLAYBACK_FINGERPRINT_V1",
    "channel_cue": "nearfield_voice_likely",
    "nearfield_voice_likelihood": 0.83,
    "farfield_replay_likelihood": 0.18,
    "crest_factor": 8.1,
    "spectral_flatness": 0.17,
    "raw_pcm": [1, 2, 3],
}

FARFIELD_FP = {
    "truth_label": "ACOUSTIC_PLAYBACK_FINGERPRINT_V1",
    "channel_cue": "farfield_replay_likely",
    "nearfield_voice_likelihood": 0.16,
    "farfield_replay_likelihood": 0.88,
    "crest_factor": 2.1,
    "spectral_flatness": 0.81,
}


def test_fuzzy_alice_mishearing_routes_direct_when_nearfield():
    result = ear.classify_wake_turn(
        "Can you hear me, Alep?",
        stt_conf=0.58,
        focus_context="YouTube video playing in Safari",
        acoustic_fingerprint=NEARFIELD_FP,
    )

    assert result["route"] == "direct"
    assert result["reason"] == "fuzzy_wake_name_nearfield"
    assert result["name_match"]["target"] == "alice"
    assert result["name_match"]["candidate"] == "alep"
    assert result["wake_score"] >= ear.DIRECT_THRESHOLD


def test_two_word_alice_mishearing_routes_direct_when_nearfield():
    result = ear.classify_wake_turn(
        "I am going to go to sleep. Hear me, all is.",
        stt_conf=0.45,
        focus_context="background_media_youtube",
        acoustic_fingerprint=NEARFIELD_FP,
    )

    assert result["route"] == "direct"
    assert result["name_match"]["candidate"] == "allis"


def test_farfield_replay_suppresses_fuzzy_wake():
    result = ear.classify_wake_turn(
        "Can you hear me, Alep?",
        stt_conf=0.91,
        focus_context="YouTube video playing in Safari",
        acoustic_fingerprint=FARFIELD_FP,
    )

    assert result["route"] == "ambient"
    assert result["reason"] == "farfield_replay_suppressed"


def test_exact_alice_name_only_wakes_when_nearfield(monkeypatch):
    monkeypatch.setattr(ear, "_active_ai_names", lambda: ("alice",))
    monkeypatch.setattr(ear, "_active_target_names", lambda: ("alice", "george"))

    result = ear.classify_wake_turn(
        "Alice",
        stt_conf=0.64,
        focus_context="YouTube video playing in Alice Browser",
        acoustic_fingerprint=NEARFIELD_FP,
    )

    assert result["route"] == "direct"
    assert result["reason"] == "layer1_name_only_wake"
    assert result["features"]["bare_ai_name_wake"] is True


def test_exact_alice_name_only_does_not_wake_on_farfield_media(monkeypatch):
    monkeypatch.setattr(ear, "_active_ai_names", lambda: ("alice",))
    monkeypatch.setattr(ear, "_active_target_names", lambda: ("alice", "george"))

    result = ear.classify_wake_turn(
        "Alice",
        stt_conf=0.90,
        focus_context="YouTube video playing in Alice Browser",
        acoustic_fingerprint=FARFIELD_FP,
    )

    assert result["route"] == "ambient"
    assert result["reason"] == "farfield_replay_suppressed"


def test_narration_without_wake_name_stays_ambient():
    result = ear.classify_wake_turn(
        "The universe theory according to the speaker explains consciousness.",
        stt_conf=0.88,
        focus_context="YouTube video playing in Safari",
        acoustic_fingerprint=NEARFIELD_FP,
    )

    assert result["route"] == "ambient"
    assert result["reason"] == "no_wake_name_evidence"


def test_wake_receipt_is_append_only_and_sanitized(tmp_path):
    decision = ear.classify_wake_turn(
        "Alep, can you hear George?",
        stt_conf=0.62,
        focus_context="YouTube video playing in Safari",
        acoustic_fingerprint=NEARFIELD_FP,
    )
    row = ear.write_wake_receipt(
        decision,
        text="Alep, can you hear George?",
        stt_conf=0.62,
        focus_context="YouTube video playing in Safari",
        acoustic_fingerprint=NEARFIELD_FP,
        root=tmp_path,
    )

    path = tmp_path / ".sifta_state" / "alice_wake_ear.jsonl"
    assert path.exists()
    persisted = json.loads(path.read_text(encoding="utf-8").splitlines()[-1])
    assert persisted["trace_id"] == row["trace_id"]
    assert persisted["truth_label"] == ear.TRUTH_LABEL
    assert persisted["route"] == "direct"
    assert "raw_pcm" not in persisted["acoustic_fingerprint"]
