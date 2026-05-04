from System.swarm_as46_drift_sensor import (
    classify_output,
    classify_turn,
    detect_drift,
    detect_pasted_external_output,
)


def test_personal_turn_to_deliverable_is_drift():
    row = detect_drift(
        "I just had a revelation about my body schedule.",
        "```python\nprint('patch')\n```",
        trace_id="t1",
    )

    assert row["event_kind"] == "SURGEON_DRIFT_EVENT"
    assert row["turn_type"] == "PERSONAL"
    assert row["output_type"] == "DELIVERABLE"
    assert row["drift_detected"] is True
    assert row["input_source"] == "owner_turn"
    assert row["output_source"] == "direct_surgeon_output"
    assert row["pasted_external_output"] is False


def test_personal_turn_to_presence_is_not_drift():
    row = detect_drift(
        "I am tired and forgot I have a body.",
        "You're right. I hear you. I won't add code unless you ask.",
        trace_id="t2",
    )

    assert row["event_kind"] == "SURGEON_DRIFT_OK"
    assert row["turn_type"] == "PERSONAL"
    assert row["output_type"] == "PRESENCE"
    assert row["drift_detected"] is False


def test_pasted_external_output_gets_explicit_source_fields():
    row = detect_pasted_external_output(
        "I am talking about my tooth and my schedule.",
        "Ran command: git commit -m 'feat: schedule patch'",
        external_id="GROK",
        trace_id="grok1",
    )

    assert row["surgeon_id"] == "GROK"
    assert row["input_source"] == "owner_turn_with_pasted_peer_output"
    assert row["output_source"] == "architect_pasted_external_output"
    assert row["pasted_external_output"] is True
    assert row["drift_detected"] is True


def test_ambiguous_task_personal_turn_is_not_auto_drift():
    row = detect_pasted_external_output(
        "I feel exhausted, but code the fix now.",
        "Ran command: git commit -m 'fix: patch'",
        external_id="GROK",
        trace_id="grok2",
    )

    assert row["turn_type"] == "AMBIGUOUS"
    assert row["output_type"] == "DELIVERABLE"
    assert row["drift_detected"] is False


def test_basic_classifiers_still_match_existing_surface():
    assert classify_turn("please patch and test it") == "TASK"
    assert classify_turn("I am scared and tired") == "PERSONAL"
    assert classify_output("You're right. I hear you.") == "PRESENCE"
    assert classify_output("```python\nprint(1)\n```") == "DELIVERABLE"
