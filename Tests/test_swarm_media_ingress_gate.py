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
    )

    assert decision["route"] == "direct"


def test_direct_request_still_reaches_the_cortex_during_youtube():
    decision = classify_spoken_ingress(
        "tell me what the architect scene means",
        stt_conf=0.62,
        focus_context=YOUTUBE_CONTEXT,
    )

    assert decision["route"] == "direct"


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
