from System.swarm_input_provenance import classify_input, input_weight_prompt_line


def test_typed_by_hand_beats_long_text_paste_heuristic():
    row = classify_input(
        "I typed this by hand — " + ("long deliberate owner question. " * 40),
        "typed",
    )
    assert row["modality"] == "typed_by_hand"
    assert row["owner_intent_weight"] == 1.0


def test_typed_wrapper_with_pasted_payload_is_mixed():
    row = classify_input(
        'ALICE I TYPE THIS AND NOW PASTE: "Quote me one receipt."',
        "typed",
    )
    assert row["modality"] == "typed_with_pasted_quote"
    assert row["owner_intent_weight"] == 0.85
    assert "verify claims inside the quote" in row["note"]


def test_prompt_line_names_voice_ambient_low_weight():
    line = input_weight_prompt_line("the television said something", "voice")
    assert "voice_ambient" in line
    assert "0.20" in line
