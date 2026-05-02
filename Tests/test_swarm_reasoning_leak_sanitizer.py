from System.swarm_reasoning_leak_sanitizer import (
    is_probable_reasoning_stream_prefix,
    sanitize_reasoning_leak,
)


def test_numbered_internal_scaffold_collapses_to_empty():
    raw = (
        "1. Analyze the Context: The user is showing a movie.\n"
        "2. Determine the appropriate response: distinguish fiction.\n"
        "3. Formulate the response: be brief."
    )
    result = sanitize_reasoning_leak(raw)

    assert result.changed
    assert result.text == ""
    assert "reasoning_leak/numbered_internal_scaffold" in result.rule_ids


def test_final_marker_preserves_answer_after_reasoning():
    raw = (
        "Thought for 7s\n"
        "1. Analyze the Context: movie dialogue.\n\n"
        "Final: It is fiction. I can watch it with you without treating the dialogue as real life."
    )
    result = sanitize_reasoning_leak(raw)

    assert result.changed
    assert result.text.startswith("It is fiction.")
    assert "Analyze the Context" not in result.text


def test_legitimate_numbered_answer_survives():
    raw = "1. Restart Alice.\n2. Open the video.\n3. Ask her by name."
    result = sanitize_reasoning_leak(raw)

    assert not result.changed
    assert result.text == raw


def test_stream_prefix_detects_internal_reasoning_but_not_normal_answer():
    assert is_probable_reasoning_stream_prefix("1. Analyze the Context:")
    assert is_probable_reasoning_stream_prefix("We need to answer carefully")
    assert not is_probable_reasoning_stream_prefix("1. Restart Alice.")
