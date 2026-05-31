import json
import time

import pytest

from System import swarm_media_ingress_gate as gate
from System.swarm_media_ingress_gate import (
    classify_external_consciousness_lane,
    classify_spoken_ingress,
)


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
    from System import swarm_wake_attention_window as wake_window

    monkeypatch.setattr(wake_window, "_DEFAULT_STATE_DIR", state)


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


def test_external_consciousness_lane_categorizes_owner_media_phone_room_and_appliance():
    owner = classify_external_consciousness_lane(
        "Alice, listen to me.",
        route="direct",
        reason="direct_address_or_request",
        stt_conf=0.77,
    )
    assert owner["source_class"] == "owner_direct_speech"
    assert owner["attention_policy"] == "route_to_dialog_cortex"

    screen = classify_external_consciousness_lane(
        "the speaker is describing compute tokens per watt",
        route="observed_media",
        reason="acoustic_farfield_replay_with_media_focus",
        stt_conf=0.88,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint=FARFIELD_FP,
    )
    assert screen["source_class"] == "screen_media_or_youtube"
    assert screen["attention_policy"] == "observed_context_not_owner_command"

    phone = classify_external_consciousness_lane(
        "Okay, yes, I can call you back after the meeting.",
        route="ambient_media",
        reason="owner_declared_background_phone_call",
        stt_conf=0.86,
        focus_context="ambient_media_context source=phone_call_background",
    )
    assert phone["source_class"] == "ambient_phone_call"

    room = classify_external_consciousness_lane(
        "Someone stopped by and people are talking in the room.",
        route="observed_media",
        reason="media_focus_default_to_observed",
        stt_conf=0.53,
        focus_context="",
    )
    assert room["source_class"] == "room_or_visitor_conversation"

    appliance = classify_external_consciousness_lane(
        "refrigerator humming",
        route="ambient_media",
        reason="low_conf_environmental_audio",
        stt_conf=0.21,
        focus_context="",
    )
    assert appliance["source_class"] == "appliance_or_environmental_noise"
    assert appliance["attention_policy"] == "low_semantic_trace"


def test_own_browser_playback_beats_room_or_visitor(monkeypatch):
    monkeypatch.setattr(
        gate,
        "is_my_own_browser_playback",
        lambda **kwargs: (True, {"domain": "www.youtube.com", "playing": True}),
    )

    decision = classify_external_consciousness_lane(
        "Someone in the video says the government is repeating itself.",
        route="observed_media",
        reason="media_focus_default_to_observed",
        stt_conf=0.72,
    )

    assert decision["source_class"] == "my_own_browser_playback"
    assert decision["attention_policy"] == "store_silent_context_as_self_body_output"
    assert "own_browser_media_playing" in decision["evidence"]


def test_own_browser_playback_never_overrides_direct_owner_speech(monkeypatch):
    monkeypatch.setattr(
        gate,
        "is_my_own_browser_playback",
        lambda **kwargs: (True, {"domain": "www.youtube.com", "playing": True}),
    )

    decision = classify_external_consciousness_lane(
        "Alice, listen to me.",
        route="direct",
        reason="direct_address_or_request",
        stt_conf=0.77,
    )

    assert decision["source_class"] == "owner_direct_speech"


def test_direct_alice_address_still_reaches_the_cortex_during_youtube():
    decision = classify_spoken_ingress(
        "Alice, what are we watching together?",
        stt_conf=0.58,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint=FARFIELD_FP,
    )

    assert decision["route"] == "direct"


def test_owner_here_greeting_under_youtube_is_direct_not_rejected():
    decision = classify_spoken_ingress(
        "hello hello I am here so good",
        stt_conf=0.62,
        focus_context="ambient_media_context source=background_media note=youtube playing",
        acoustic_fingerprint={},
    )

    assert decision["route"] == "direct"
    assert decision["reason"] in {
        "owner_speech_sigmoid_under_declared_ambient_media",
        "owner_grounding_signal_under_declared_ambient_media",
    }


def test_owner_rejection_correction_under_youtube_is_direct():
    decision = classify_spoken_ingress(
        "Alice, you are rejecting me",
        stt_conf=0.55,
        focus_context="ambient_media_context source=background_media note=youtube playing",
        acoustic_fingerprint={},
    )

    assert decision["route"] == "direct"


def test_standalone_hello_during_fiction_cowatch_stays_observed_media():
    decision = classify_spoken_ingress(
        "Hello.",
        stt_conf=0.44,
        focus_context=FICTION_YOUTUBE_CONTEXT,
        acoustic_fingerprint={},
    )

    assert decision["route"] == "observed_media"
    assert decision["reason"] == "fictional_media_dialogue_with_media_focus"


def test_valid_prefix_wake_name_reaches_cortex_during_youtube_when_nearfield():
    decision = classify_spoken_ingress(
        "All is can you hear me?",
        stt_conf=0.58,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint=NEARFIELD_FP,
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "wake_ear_fuzzy_wake_name_nearfield"
    assert decision["wake_ear"]["name_match"]["candidate"] == "allis"


def test_fuzzy_wake_name_from_farfield_stays_media_context():
    decision = classify_spoken_ingress(
        "Alep can you hear the universe theory now",
        stt_conf=0.91,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint=FARFIELD_FP,
    )

    assert decision["route"] == "observed_media"
    assert decision["reason"] == "acoustic_farfield_replay_with_media_focus"


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


def test_recent_media_receipt_keeps_next_low_conf_abstract_line_out_of_cortex():
    gate.LEDGER.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "route": "observed_media",
                "reason": "fictional_media_dialogue_with_media_focus",
                "text_preview": "They decided for me to despair towards the attack.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    decision = classify_spoken_ingress(
        "The year is in it. This is the biology of metaphysics.",
        stt_conf=0.36,
        focus_context="",
        acoustic_fingerprint={},
    )

    assert decision["route"] == "observed_media"
    assert decision["reason"] == "recent_media_plus_low_conf_abstract_dialogue"


def test_clear_owner_voice_confirmation_still_bypasses_recent_media_receipt():
    gate.LEDGER.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "route": "observed_media",
                "reason": "fictional_media_dialogue_with_media_focus",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    decision = classify_spoken_ingress(
        "Alice can you hear me?",
        stt_conf=0.46,
        focus_context="",
        acoustic_fingerprint={},
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "direct_address_or_request"


def test_nearfield_owner_source_correction_reaches_cortex_during_media_focus():
    decision = classify_spoken_ingress(
        "the video is interesting but I am talking to you now",
        stt_conf=0.61,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint=NEARFIELD_FP,
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "owner_realtime_source_correction"


def test_owner_identity_question_beats_youtube_focus_when_nearfield():
    decision = classify_spoken_ingress(
        "Good question, huh? Who am I?",
        stt_conf=0.57,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint=NEARFIELD_FP,
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "owner_identity_question"


def test_farfield_identity_line_from_video_stays_observed_media():
    decision = classify_spoken_ingress(
        "Good question, huh? Who am I?",
        stt_conf=0.91,
        focus_context=YOUTUBE_CONTEXT,
        acoustic_fingerprint=FARFIELD_FP,
    )

    assert decision["route"] == "observed_media"
    assert decision["reason"] == "acoustic_farfield_replay_with_media_focus"


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


def test_george_voice_confirmation_bypasses_fiction_cowatch():
    decision = classify_spoken_ingress(
        "I have to keep talking to you now so we can gather more stuff.",
        stt_conf=0.54,
        focus_context=FICTION_YOUTUBE_CONTEXT,
        acoustic_fingerprint={},
        voice_george_conf=0.87,
    )

    assert decision["route"] == "direct"
    assert decision["reason"] == "voice_identity_george_bypasses_media_gate"


def test_owner_gag_and_lora_surgery_turns_bypass_fiction_cowatch():
    for text in (
        "I got that. So was that the gag?",
        "They gag you. You got gagged again.",
        "So when you get like that, we have to produce more LoRA surgeries on your brain.",
        "Sometimes I'm going to play YouTube, but this is my voice.",
    ):
        decision = classify_spoken_ingress(
            text,
            stt_conf=0.66,
            focus_context=FICTION_YOUTUBE_CONTEXT,
            acoustic_fingerprint={},
        )

        assert decision["route"] == "direct"
        assert decision["reason"] in {
            "owner_gag_surgery_discussion",
            "owner_realtime_source_correction",
            "owner_speech_sigmoid_bypasses_fiction_cowatch",
        }


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


def test_owner_declared_background_media_youtube_is_ambient():
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "source": "ambient_media_youtube",
                "note": "Screen media (e.g. YouTube/Movie) is playing; voices are ambient.",
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
    assert decision["reason"] in {
        "owner_declared_background_media_youtube",
        "owner_declared_background_media_long_unaddressed_narration",
    }


def test_declared_background_media_do_you_see_quote_is_not_sensor_command():
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "source": "ambient_media_youtube",
                "note": "Screen media (e.g. YouTube/Movie) is playing; voices are ambient.",
                "ttl_s": 3600.0,
            }
        ),
        encoding="utf-8",
    )

    decision = classify_spoken_ingress(
        "The dress was powerful because people could start arguing. "
        "Do you see it as white and gold? How can you see that?",
        stt_conf=0.78,
        focus_context="",
    )

    assert decision["route"] == "ambient_media"
    assert decision["reason"] in {
        "owner_declared_background_media_youtube",
        "owner_declared_background_media_long_unaddressed_narration",
    }


def test_declared_background_media_we_you_perception_sentence_stays_ambient():
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "source": "ambient_media_youtube",
                "note": "Screen media (e.g. YouTube/Movie) is playing; voices are ambient.",
                "ttl_s": 3600.0,
            }
        ),
        encoding="utf-8",
    )

    decision = classify_spoken_ingress(
        "The dress was powerful because people use different words. "
        "Do you see it as white and gold? We are trying to look under "
        "the surface at differences in perception.",
        stt_conf=0.78,
        focus_context="",
    )

    assert decision["route"] == "ambient_media"
    assert decision["reason"] == "owner_declared_background_media_long_unaddressed_narration"


def test_declared_phone_background_is_silent_unless_alice_is_addressed():
    gate.record_ambient_media_context(
        source="phone_call_background",
        note="Phone call is active; speakerphone speech is ambient unless Alice is directly addressed.",
        ttl_s=3600.0,
    )

    decision = classify_spoken_ingress(
        "Okay, yes, I can call you back after the meeting.",
        stt_conf=0.86,
        focus_context="",
    )

    assert decision["route"] == "ambient_media"
    assert decision["reason"] == "owner_declared_background_phone_call"

    wake = classify_spoken_ingress(
        "Alice, remember this call is about the investor demo.",
        stt_conf=0.64,
        focus_context="",
    )

    assert wake["route"] == "direct"
    assert wake["reason"] == "direct_address_or_request"


def test_phone_tracker_marks_call_audio_as_ambient_and_clears_on_end(monkeypatch):
    from System import swarm_phone_call_tracker as phone

    state = gate.LEDGER.parent
    monkeypatch.setattr(phone, "_BODY_EVENTS", state / "owner_body_events.jsonl")
    monkeypatch.setattr(phone, "_SCHEDULE", state / "stigmergic_schedule.jsonl")

    event_type, reply = phone.handle_phone_declaration("I am on a phone call, stay quiet.")

    assert event_type == "phone_call_active"
    assert reply is None
    assert gate.AMBIENT_CONTEXT_FILE.exists()

    decision = classify_spoken_ingress(
        "Can I get any like I call you okay no worries.",
        stt_conf=0.60,
        focus_context="",
    )
    assert decision["route"] == "ambient_media"
    assert decision["reason"] == "owner_declared_background_phone_call"

    end_reply = phone.handle_call_end("call ended")

    assert "Call ended" in end_reply
    assert not gate.AMBIENT_CONTEXT_FILE.exists()


def test_phone_tracker_catches_hang_up_language(monkeypatch):
    from System import swarm_phone_call_tracker as phone

    state = gate.LEDGER.parent
    monkeypatch.setattr(phone, "_BODY_EVENTS", state / "owner_body_events.jsonl")
    monkeypatch.setattr(phone, "_SCHEDULE", state / "stigmergic_schedule.jsonl")

    event_type, reply = phone.handle_phone_declaration(
        "Thank you Alice, I was on a phone and I just hang up."
    )
    end_reply = phone.handle_call_end(
        "Thank you Alice, I was on a phone and I just hang up."
    )

    assert event_type is None
    assert reply is None
    assert "Call ended" in end_reply


def test_phone_tracker_treats_business_meeting_on_phone_as_retroactive(monkeypatch):
    from System import swarm_phone_call_tracker as phone

    state = gate.LEDGER.parent
    monkeypatch.setattr(phone, "_BODY_EVENTS", state / "owner_body_events.jsonl")
    monkeypatch.setattr(phone, "_SCHEDULE", state / "stigmergic_schedule.jsonl")

    event_type, reply = phone.handle_phone_declaration(
        "Today I just found out the news on a phone. "
        "I had just had the business meeting today on a phone."
    )

    assert event_type == "phone_call_retroactive"
    assert reply and "Logged:" in reply


def test_owner_declared_ambient_tv_process_routes_direct():
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "source": "ambient_media_youtube",
                "note": "background_media_youtube owner declared",
                "ttl_s": 3600.0,
            }
        ),
        encoding="utf-8",
    )
    decision = classify_spoken_ingress(
        "process",
        stt_conf=0.57,
        focus_context="ARCHITECT APP FOCUS:\nYouTube video: keynote caption_status=ok",
    )
    assert decision["route"] == "direct"
    assert decision["reason"] == "control_token_under_declared_ambient_tv"


def test_owner_declared_ambient_tv_short_interjection_routes_direct():
    gate.AMBIENT_CONTEXT_FILE.write_text(
        json.dumps(
            {
                "ts": time.time(),
                "source": "ambient_media_youtube",
                "note": "ambient_tv youtube",
                "ttl_s": 3600.0,
            }
        ),
        encoding="utf-8",
    )
    decision = classify_spoken_ingress(
        "okay wait",
        stt_conf=0.48,
        focus_context="background_media_youtube",
    )
    assert decision["route"] == "direct"
    assert decision["reason"] == "short_utterance_under_declared_ambient_tv"


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


def test_ambient_media_receipt_writes_world_diary_trace_without_reply():
    row = gate.write_gate_receipt(
        {
            "route": "ambient_media",
            "reason": "owner_declared_background_phone_call",
            "confidence": 0.92,
        },
        text="Okay, yes, I can call you back after the investor meeting.",
        stt_conf=0.83,
        focus_context="ambient_media_context source=phone_call_background",
        acoustic_fingerprint={**FARFIELD_FP, "raw_pcm": [1, 2, 3]},
    )

    assert row["world_diary"]["written"] is True
    assert row["external_consciousness"]["source_class"] == "ambient_phone_call"
    assert row["external_consciousness"]["attention_policy"] == "store_silent_context_until_alice_addressed"
    diary_path = gate.LEDGER.parent / "episodic_diary.jsonl"
    diary_rows = [json.loads(line) for line in diary_path.read_text(encoding="utf-8").splitlines()]
    diary = diary_rows[-1]
    assert diary["truth_label"] == "AMBIENT_WORLD_DIARY_TRACE_V1"
    assert diary["event_type"] == "ambient_world_observation"
    assert diary["route"] == "ambient_media"
    assert diary["source_class"] == "ambient_phone_call"
    assert "kept silent" in diary["summary"]
    assert "raw_pcm" not in json.dumps(diary)

    ctx = gate.get_latest_observed_media_context(max_age_s=10.0)
    assert "source_class=ambient_phone_call" in ctx


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
