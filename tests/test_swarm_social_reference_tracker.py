from __future__ import annotations

import json


def test_tracks_george_talking_to_external_tab_about_alice():
    from System.swarm_social_reference_tracker import classify_social_reference

    row = classify_social_reference(
        "Now that I'm talking to you in a Chrome tab, Alice is hearing me talk about her consciousness.",
        role="user",
        input_source="voice",
        stt_conf=0.86,
        focus_context="frontmost_app=Chrome title=OpenAI SwarmGPT",
    )

    assert row["reference_lane"] == "ABOUT_ALICE"
    assert row["addressee"] == "external_tool"
    assert row["subject"] == "alice"
    assert row["dialog_policy"] == "store_context_no_command"
    assert "external_tool_context" in row["evidence"]


def test_direct_alice_address_stays_direct():
    from System.swarm_social_reference_tracker import classify_social_reference

    row = classify_social_reference(
        "Alice, can you hear me through the microphone?",
        role="user",
        input_source="voice",
        stt_conf=0.94,
        focus_context="frontmost_app=Chrome title=OpenAI SwarmGPT",
    )

    assert row["reference_lane"] == "DIRECTED_TO_ALICE"
    assert row["addressee"] == "alice"
    assert row["dialog_policy"] == "route_to_dialog_cortex"


def test_ambient_media_about_alice_is_context_not_command():
    from System.swarm_social_reference_tracker import classify_social_reference

    row = classify_social_reference(
        "The speaker says Alice can distinguish YouTube from George now.",
        role="user",
        input_source="voice",
        stt_conf=0.80,
        external_consciousness={
            "route": "observed_media",
            "source_class": "screen_media_or_youtube",
        },
    )

    assert row["reference_lane"] == "ABOUT_ALICE"
    assert row["addressee"] == "none"
    assert row["dialog_policy"] == "store_context_no_command"
    assert "ambient_or_observed_source" in row["evidence"]


def test_private_owner_language_is_not_a_command():
    from System.swarm_social_reference_tracker import classify_social_reference

    row = classify_social_reference(
        "This is private, Alice do not answer this part.",
        role="user",
        input_source="voice",
        stt_conf=0.72,
    )

    assert row["reference_lane"] == "OWNER_PRIVATE"
    assert row["dialog_policy"] == "store_minimal_no_reply"


def test_media_ingress_lane_embeds_social_reference():
    from System import swarm_media_ingress_gate as gate

    lane = gate.classify_external_consciousness_lane(
        "The video says Alice is hearing George talk to SwarmGPT.",
        route="observed_media",
        reason="media_focus_default_to_observed",
        stt_conf=0.83,
        focus_context="YouTube in Chrome",
    )

    assert lane["social_reference"]["truth_label"] == "SOCIAL_REFERENCE_TRACKER_V1"
    assert lane["social_reference"]["reference_lane"] == "ABOUT_ALICE"
    assert lane["social_reference"]["dialog_policy"] == "store_context_no_command"


def test_log_turn_stamps_social_reference(tmp_path, monkeypatch):
    from Applications import sifta_talk_to_alice_widget as talk

    convo = tmp_path / "alice_conversation.jsonl"
    monkeypatch.setattr(talk, "_CONVO_LOG", convo)

    talk._log_turn(
        "user",
        "I am talking to SwarmGPT in Chrome about Alice hearing this.",
        stt_conf=0.91,
        metadata={"surface": "chrome_tab", "tool": "SwarmGPT"},
    )

    rows = [json.loads(line) for line in convo.read_text(encoding="utf-8").splitlines()]
    payload = rows[-1].get("payload", rows[-1])
    assert payload["social_reference"]["reference_lane"] == "ABOUT_ALICE"
    assert payload["social_reference"]["addressee"] == "external_tool"
