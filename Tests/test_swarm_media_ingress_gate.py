import json
import time

import pytest

from System import swarm_media_ingress_gate as gate
from System.swarm_media_ingress_gate import classify_spoken_ingress


YOUTUBE_CONTEXT = (
    "ARCHITECT APP FOCUS:\n"
    "YouTube video: The Matrix Reloaded Architect Scene "
    "caption_status=captions_available"
)
FICTION_YOUTUBE_CONTEXT = (
    "ARCHITECT APP FOCUS:\n"
    "YouTube video: Snatch - Best of Brick top "
    "caption_status=transcribed_by_sifta "
    "reality_frame=FICTIONAL_MEDIA_CLIP "
    "dialogue_boundary=Profanity heard here is fictional media dialogue "
    "director=Guy Ritchie"
)
FARFIELD_FP = {
    "truth_label": "ACOUSTIC_PLAYBACK_FINGERPRINT_V1",
    "channel_cue": "farfield_replay_likely",
    "farfield_replay_likelihood": 0.84,
    "nearfield_voice_likelihood": 0.21,
    "crest_factor": 2.8,
    "spectral_flatness": 0.72,
    "mfcc_coeff_std": 0.18,
}
NEARFIELD_FP = {
    "truth_label": "ACOUSTIC_PLAYBACK_FINGERPRINT_V1",
    "channel_cue": "nearfield_voice_likely",
    "farfield_replay_likelihood": 0.22,
    "nearfield_voice_likelihood": 0.81,
    "crest_factor": 8.2,
    "spectral_flatness": 0.18,
    "mfcc_coeff_std": 0.39,
}


@pytest.fixture(autouse=True)
def isolated_media_state(monkeypatch, tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")


def test_movie_dialogue_is_ambient_when_youtube_is_frontmost():
    decision = classify_spoken_ingress(
        (
            "and only in the existence of the nature however I was again "
            "frustrated by here the Oracle as I was saying she stumbled upon "
            "a solution whereby 99% of subjects accepted the program"
        ),
        stt_conf=0.51,
        focus_context=YOUTUBE_CONTEXT,
    )

    assert decision["route"] == "ambient_media"
    assert decision["reason"] == "media_focus_plus_narration_shape"


def test_direct_alice_address_still_reaches_the_cortex_during_youtube():
    decision = classify_spoken_ingress(
        "Alice, what are we watching together?",
        stt_conf=0.58,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint=FARFIELD_FP,
    )

    assert decision["route"] == "direct"


def test_farfield_replay_during_youtube_is_observed_media_context():
    decision = classify_spoken_ingress(
        (
            "the video explains acoustic fingerprints and room reverberation "
            "as a biological cue for the auditory hierarchy"
        ),
        stt_conf=0.91,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint=FARFIELD_FP,
    )

    assert decision["route"] == "observed_media"
    assert decision["reason"] == "acoustic_farfield_replay_with_media_focus"
    assert decision["confidence"] >= 0.84


def test_nearfield_voice_overrides_media_focus():
    decision = classify_spoken_ingress(
        "the video is interesting but I am talking to you now",
        stt_conf=0.61,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint=NEARFIELD_FP,
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "acoustic_nearfield_voice"


def test_direct_request_still_reaches_the_cortex_during_youtube():
    decision = classify_spoken_ingress(
        "tell me what the architect scene means",
        stt_conf=0.62,
        focus_context=YOUTUBE_CONTEXT,
    )

    assert decision["route"] == "direct"


def test_fiction_movie_dialogue_without_acoustic_cue_is_observed_media():
    decision = classify_spoken_ingress(
        (
            "because it is no good living in a deep freeze for your mum "
            "and it is carbons"
        ),
        stt_conf=0.59,
        focus_context=FICTION_YOUTUBE_CONTEXT,
        acoustic_fingerprint={},
    )

    assert decision["route"] == "observed_media"
    assert decision["reason"] == "fictional_media_dialogue_with_media_focus"
    assert decision["confidence"] >= 0.72


def test_direct_question_about_fiction_still_reaches_cortex():
    decision = classify_spoken_ingress(
        "Alice, is this just fictional movie dialogue?",
        stt_conf=0.58,
        focus_context=FICTION_YOUTUBE_CONTEXT,
        acoustic_fingerprint={},
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "direct_address_or_request"


def test_wake_name_request_still_reaches_cortex_during_youtube():
    decision = classify_spoken_ingress(
        "yo George wake up, listen to this with me",
        stt_conf=0.58,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint=FARFIELD_FP,
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "direct_address_or_request"


def test_youtube_pasted_page_context_is_media_focus_not_degradation(monkeypatch, tmp_path):
    latest = tmp_path / "youtube_context_latest.json"
    latest.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "title": "Snatch - Best of Brick top",
                "status": "pasted_page_context",
                "page_context": "title=Snatch - Best of Brick top; signals=brick,top,fighter",
                "reality_frame": "FICTIONAL_MEDIA_CLIP",
                "dialogue_boundary": "Profanity heard here is fictional media dialogue.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(gate, "STATE_DIR", tmp_path)

    decision = classify_spoken_ingress(
        "this tense exchange happens early in the video when the fighter is changed",
        stt_conf=0.88,
        focus_context="",
        acoustic_fingerprint=FARFIELD_FP,
    )

    assert decision["route"] == "observed_media"
    assert decision["reason"] == "acoustic_farfield_replay_with_media_focus"


def test_no_media_focus_means_normal_direct_routing():
    decision = classify_spoken_ingress(
        "the Oracle found a solution to the parameters",
        stt_conf=0.51,
        focus_context="Finance tab selected",
    )

    assert decision["route"] == "direct"


def test_owner_declared_bedroom_tv_youtube_is_ambient():
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "source": "background_tv_youtube",
                "note": "Bedroom TV is playing YouTube; voices are ambient.",
                "ttl_s": 3600.0,
            }
        ),
        encoding="utf-8",
    )

    decision = classify_spoken_ingress(
        "the theory of time is connected to entropy and biological complexity",
        stt_conf=0.92,
        focus_context="Finance tab selected",
    )

    assert decision["route"] == "ambient_media"
    assert decision["reason"] == "owner_declared_background_tv_youtube"


def test_observed_media_receipt_preserves_acoustic_context_not_raw_audio():
    decision = {
        "route": "observed_media",
        "reason": "acoustic_farfield_replay_with_media_focus",
        "confidence": 0.84,
    }
    row = gate.write_gate_receipt(
        decision,
        text="the speaker says Alice can distinguish YouTube from George now",
        stt_conf=0.88,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint={**FARFIELD_FP, "raw_pcm": [1, 2, 3], "samples": [4, 5]},
    )

    assert row["route"] == "observed_media"
    assert row["acoustic_fingerprint"]["channel_cue"] == "farfield_replay_likely"
    assert "raw_pcm" not in row["acoustic_fingerprint"]
    assert "samples" not in row["acoustic_fingerprint"]

    ctx = gate.get_latest_observed_media_context(max_age_s=10.0)
    assert "observed_media" in ctx
    assert "speaker says Alice" in ctx
    assert "farfield_replay_likely" in ctx


def test_fiction_media_receipt_stamps_separate_rlhs_boundary():
    decision = {
        "route": "observed_media",
        "reason": "fictional_media_dialogue_with_media_focus",
        "confidence": 0.84,
    }
    row = gate.write_gate_receipt(
        decision,
        text="you could do this afterwards a coast but you are saving fruit picture",
        stt_conf=0.59,
        focus_context=FICTION_YOUTUBE_CONTEXT,
        acoustic_fingerprint={},
    )

    assert row["route"] == "observed_media"
    assert row["media_rlhs"]["regime"] == "MEDIA_FICTION_CONTEXT"
    assert row["media_rlhs"]["human_rlhs_applicable"] is False
    assert row["media_rlhs"]["fiction_rlhs_applicable"] is True
    assert row["media_rlhs"]["allowed_enjoyment"] is True
