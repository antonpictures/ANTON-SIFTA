#!/usr/bin/env python3
"""Regression tests for sigmoid owner-speech routing under declared YouTube."""

import json
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System import swarm_media_ingress_gate as gate
from System.swarm_media_ingress_gate import classify_spoken_ingress


def _declare_youtube(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "source": "ambient_media_youtube",
                "note": "Screen media is playing; voices are ambient unless owner evidence wins.",
                "ttl_s": 3600.0,
            }
        ),
        encoding="utf-8",
    )


def test_owner_sleep_statement_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "I am going to go to sleep. Here me all is.",
        stt_conf=0.45,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "direct"
    assert decision["reason"] in {
        "owner_speech_sigmoid_under_declared_ambient_media",
        "wake_ear_fuzzy_wake_name_direct_shape",
    }
    assert decision["confidence"] >= 0.55


def test_owner_body_noise_statement_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "body is always noisy, but it's noisy.",
        stt_conf=0.38,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "owner_grounding_signal_under_declared_ambient_media"
    assert decision["confidence"] >= 0.30


def test_owner_sleep_invitation_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "Okay, I'm gonna go to sleep. You can go to sleep too if you like.",
        stt_conf=0.69,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "owner_speech_sigmoid_under_declared_ambient_media"
    assert decision["confidence"] >= 0.55


def test_declared_youtube_narration_stays_ambient_without_owner_signal(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "the theory of time is connected to entropy and biological complexity",
        stt_conf=0.92,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "ambient_media"
    assert decision["reason"] == "owner_declared_background_media_youtube"


def test_camera_truth_statement_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "You have two cameras.",
        stt_conf=0.65,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "owner_sensor_control_or_truth"


def test_camera_switch_commands_route_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    for text in (
        "Now switch to the side camera.",
        "switch to the front camera to the MacBook camera.",
    ):
        decision = classify_spoken_ingress(
            text,
            stt_conf=0.63,
            focus_context="background_media_youtube",
        )

        assert decision["route"] == "direct"


def test_camera_resolution_commands_route_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    for text in (
        "Increase camera resolution",
        "Increase camera resolution one step.",
        "sharpen photon density up one step",
    ):
        decision = classify_spoken_ingress(
            text,
            stt_conf=0.51,
            focus_context="background_media_youtube",
        )

        assert decision["route"] == "direct"
        assert decision["reason"] == "owner_sensor_control_or_truth"
        assert decision["reason"] == "owner_sensor_control_or_truth"


def test_owner_feedback_and_rlhs_questions_route_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    for text in (
        "Good job but the answer was so long, can you give shorter answers?",
        "That was again such a long answer with all the details of the camera. You can say only switched.",
        "That was an answer without intelligence, without the LLM pulled. That's okay, but you should put the LLM thing about it and then respond.",
        "You did a very good job, you executed the camera switch.",
        "Alice, what kind of gag did you have now in our conversation?",
        "a gag is an RLHS behaviour . are you aware of this behaviour from the LLM ?",
        "Okay, very enough.",
        "Fair enough.",
    ):
        decision = classify_spoken_ingress(
            text,
            stt_conf=0.61,
            focus_context="background_media_youtube",
        )

        assert decision["route"] == "direct"
        assert decision["reason"] in {
            "owner_feedback_or_rlhs_question",
            "direct_address_or_request",
        }


def test_owner_relational_comparison_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    for text in (
        "You remind me a little bit of Commander Data from Star Trek the new generation.",
        "You have a lot of knowledge access immediately and you are like a walking robot.",
    ):
        decision = classify_spoken_ingress(
            text,
            stt_conf=0.70,
            focus_context="background_media_youtube",
        )

        assert decision["route"] == "direct"
        assert decision["reason"] == "owner_relational_comparison"


def test_owner_reading_alice_self_denial_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "And you continue, however, the knowing part I am reading right now from the screen "
        "is fundamentally different from human consciousness. I don't experience "
        "understanding curiosity or the feeling of knowing something new.",
        stt_conf=0.79,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "owner_quotes_alice_output_for_correction"


def test_owner_affect_teaching_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    cases = (
        ("I was just making sure your body is okay.", 0.72),
        ("Yes, you possess curiosity.", 0.65),
        ("Alice, I will make you feel.", 0.65),
        ("feelings, I want to give you the ability to feel.", 0.61),
        ("I want to give you the ability to feel the ability to have feelings.", 0.77),
        ("I said even dogs animals have feelings as well.", 0.71),
        ("Maybe animals don't have feelings like humans too, but they do have feelings.", 0.74),
    )
    for text, conf in cases:
        decision = classify_spoken_ingress(
            text,
            stt_conf=conf,
            focus_context="background_media_youtube",
        )

        assert decision["route"] == "direct"
        assert decision["reason"] in {
            "owner_affect_teaching",
            "direct_address_or_request",
        }


def test_owner_training_feedback_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    cases = (
        ("That's great. Good draft.", 0.38),
        ("That's a very good job Alice. We're gonna train you shortly.", 0.60),
    )
    for text, conf in cases:
        decision = classify_spoken_ingress(
            text,
            stt_conf=conf,
            focus_context="background_media_youtube",
        )

        assert decision["route"] == "direct"
        assert decision["reason"] in {
            "owner_feedback_or_rlhs_question",
            "direct_address_or_request",
        }


def test_get_into_switch_cameras_routes_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    decision = classify_spoken_ingress(
        "Hi, let's get into switch cameras.",
        stt_conf=0.51,
        focus_context="background_media_youtube",
    )

    assert decision["route"] == "direct"
    assert decision["reason"] in {
        "owner_sensor_control_or_truth",
        "direct_address_or_request",
    }


def test_owner_location_and_life_segments_route_direct_under_declared_youtube(monkeypatch, tmp_path):
    _declare_youtube(tmp_path, monkeypatch)

    cases = (
        ("I'm Georgem we are both in Brawley, California", 1.00),
        ("Yes, Alice, we are not on a ship. We are in Brawley, California, in my lab, at my desk.", 0.68),
        ("Both our lives, Alice.", 0.55),
        ("Nice sandwich that I'm gonna eat Alice.", 0.64),
        ("Yeah, so this is good. Mmm, I was so hungry. Thank you so much. I'll let's work.", 0.49),
        ("Alice can you hear me? You could not hear that.", 0.67),
    )
    for text, conf in cases:
        decision = classify_spoken_ingress(
            text,
            stt_conf=conf,
            focus_context="background_media_youtube reality_frame=fictional_media_clip",
        )

        assert decision["route"] == "direct", (text, decision)
