from System.swarm_input_reality_class import (
    InputRealityLane,
    classify_user_turn,
    classify_user_turn_rich,
    format_lane_banner,
    write_input_modality_receipt,
)


def test_classify_image_always_local_sensor():
    assert classify_user_turn("", has_image=True) is InputRealityLane.LOCAL_SENSOR_OR_PASTE


def test_classify_long_paste():
    body = "x" * 200
    assert classify_user_turn(body, has_image=False) is InputRealityLane.LOCAL_SENSOR_OR_PASTE


def test_classify_bracket_paste_short():
    assert classify_user_turn("[tool out]", has_image=False) is InputRealityLane.LOCAL_SENSOR_OR_PASTE


def test_classify_url_short():
    assert (
        classify_user_turn("see https://example.com", has_image=False)
        is InputRealityLane.REMOTE_URL_PRESENT
    )


def test_classify_room_speech():
    assert classify_user_turn("hi Alice", has_image=False) is InputRealityLane.SHORT_ROOM_SPEECH


def test_banner_contains_lane_token():
    b = format_lane_banner(InputRealityLane.LOCAL_SENSOR_OR_PASTE)
    assert "ingress_lane=LOCAL_SENSOR_OR_PASTE" in b
    assert "OBSERVED" in b


def test_rich_typed_owner_text_has_high_deliberation_weight():
    c = classify_user_turn_rich(
        "please update the tournament",
        typed_turn=True,
        stt_conf=1.0,
    )
    assert c.lane is InputRealityLane.TYPED_DIRECT_OWNER_TEXT
    assert c.owner_intent_weight >= 0.9
    assert c.transcription_noise_risk < 0.1
    assert "deliberate" in c.guidance.lower() or "high-importance" in c.guidance.lower()


def test_rich_spoken_low_confidence_marks_noise_risk():
    c = classify_user_turn_rich(
        "stick magic words",
        typed_turn=False,
        stt_conf=0.31,
    )
    assert c.lane is InputRealityLane.SPOKEN_STT_NOISY_OR_AMBIENT
    assert c.transcription_noise_risk >= 0.9
    assert "repeat" in c.guidance.lower()


def test_rich_long_typed_text_without_paste_marker_stays_typed():
    c = classify_user_turn_rich(
        "This is a long typed question about Alice's input boundary. " * 20,
        typed_turn=True,
        stt_conf=1.0,
    )
    assert c.lane is InputRealityLane.TYPED_DIRECT_OWNER_TEXT
    assert c.owner_intent_weight >= 0.9
    assert "long_typed_no_paste_marker" in c.evidence


def test_rich_explicit_paste_context_is_paste_or_quote_context():
    c = classify_user_turn_rich(
        "Alice, now paste: " + ("This is pasted context. " * 20),
        typed_turn=True,
        stt_conf=1.0,
    )
    assert c.lane is InputRealityLane.PASTED_OR_QUOTED_CONTEXT
    assert c.copy_quote_risk >= 0.7
    assert "separate quoted material" in c.guidance.lower()


def test_rich_explicit_typed_wrapper_with_paste_is_mixed():
    c = classify_user_turn_rich(
        'ALICE I TYPE THIS AND NOW PASTE: "Quote me one receipt."',
        typed_turn=True,
        stt_conf=1.0,
    )
    assert c.lane is InputRealityLane.TYPED_WITH_PASTED_QUOTE_CONTEXT
    assert c.owner_intent_weight > 0.8
    assert c.copy_quote_risk >= 0.6
    assert "Trust the typed wrapper" in c.guidance


def test_rich_banner_and_receipt(tmp_path):
    c = classify_user_turn_rich("exact typed command", typed_turn=True)
    banner = format_lane_banner(c)
    assert "OWNER_INPUT_MODALITY_V1" in banner
    assert "TYPED_DIRECT_OWNER_TEXT" in banner
    row = write_input_modality_receipt(c, raw_text="exact typed command", state_dir=tmp_path)
    assert row["schema"] == "OWNER_INPUT_MODALITY_V1"
    assert row["classification"]["lane"] == "TYPED_DIRECT_OWNER_TEXT"
    assert (tmp_path / "input_modality_receipts.jsonl").exists()
