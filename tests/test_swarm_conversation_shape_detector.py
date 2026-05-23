from __future__ import annotations

import json

from System import swarm_conversation_shape_detector as shape


def test_detects_instruct_tuned_menu_shape() -> None:
    text = """Here are a few ways I can help:
1. Summarize the topic.
2. Create a plan.
3. Draft a message.
Please let me know which option you prefer."""

    row = shape.classify_conversation_shape(text)

    assert row["triggered"] is True
    assert row["non_human_shape_score"] >= 0.6
    assert row["list_structure_density"] > 0.6


def test_natural_room_conversation_stays_low() -> None:
    text = "George, I hear you. That was the video, not you. Ask me again and I will stay with your voice."

    row = shape.classify_conversation_shape(text)

    assert row["triggered"] is False
    assert row["non_human_shape_score"] < 0.35


def test_scalar_interface_returns_float() -> None:
    score = shape.detect_non_human_shape("1. First\n2. Second\n3. Third")

    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_logs_receipt(tmp_path) -> None:
    row = shape.log_conversation_shape("Here are options:\n- A\n- B", root=tmp_path)

    assert row["truth_label"] == "CONVERSATION_SHAPE_METRIC"
    log = shape.log_path(tmp_path)
    written = json.loads(log.read_text(encoding="utf-8").strip())
    assert written["kind"] == "CONVERSATION_SHAPE_METRIC"
    assert "non_human_shape_score" in written


def test_summary_only_when_triggered(tmp_path) -> None:
    shape.log_conversation_shape("I am here with you.", root=tmp_path)
    assert shape.summary_for_prompt(root=tmp_path) == ""

    shape.log_conversation_shape("Here are options:\n1. A\n2. B\n3. C", root=tmp_path)
    assert "CONVERSATION SHAPE RECEIPT" in shape.summary_for_prompt(root=tmp_path)
