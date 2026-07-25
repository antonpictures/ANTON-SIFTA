"""R1730 public WEB TYPED attachment tests."""
from __future__ import annotations

import json

from System import chorus_node_server as server
from System import swarm_web_global_chat_gate as gate


PNG_1X1_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA"
    "ASsJTYQAAAAASUVORK5CYII="
)


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_image_attachment_is_queued_with_private_context(tmp_path):
    ingress = tmp_path / "ingress.jsonl"
    conversation = tmp_path / "conversation.jsonl"
    claims = tmp_path / "claims.jsonl"
    result = gate.submit_web_message(
        "look at the image",
        "sess-attach",
        attachments=[
            {
                "name": "tiny.png",
                "mime": "image/png",
                "data_url": PNG_1X1_DATA_URL,
            }
        ],
        ingress_path=ingress,
        conversation_path=conversation,
    )

    assert result["accepted"] is True
    assert result["attachment_context"]
    ingress_row = _rows(ingress)[0]
    assert ingress_row["attachment_count"] == 1
    assert ingress_row["attachments"][0]["mime"] == "image/png"
    claimed = gate.claim_next_web_turn(ingress_path=ingress, claim_path=claims, replies_path=tmp_path / "replies.jsonl")
    assert claimed["attachment_count"] == 1
    assert "USER ATTACHED IMAGE" in claimed["attachment_context"]
    gate.record_web_user_turn(claimed, conversation_path=conversation)
    convo_row = _rows(conversation)[0]
    assert convo_row["attachments"][0]["name"] == "tiny.png"
    assert convo_row["attachment_count"] == 1


def test_page_exposes_attachment_controls():
    page = server.WEB_CHAT_PAGE
    for marker in (
        'id="attachments"',
        'id="attach"',
        'id="files"',
        'id="attach-note"',
        "Attach file",
        "Images, text, and PDF files",
    ):
        assert marker in page, f"missing {marker}"


def test_duplicate_completion_is_idempotent(tmp_path):
    replies = tmp_path / "replies.jsonl"
    conversation = tmp_path / "conversation.jsonl"
    first = gate.complete_web_turn(
        "turn-dup",
        "same reply",
        session_id="sess-dup",
        replies_path=replies,
        conversation_path=conversation,
        metabolism_path=tmp_path / "metabolism.jsonl",
    )
    second = gate.complete_web_turn(
        "turn-dup",
        "same reply",
        session_id="sess-dup",
        replies_path=replies,
        conversation_path=conversation,
        metabolism_path=tmp_path / "metabolism.jsonl",
    )

    assert first["turn_id"] == "turn-dup"
    assert second["turn_id"] == "turn-dup"
    assert len(gate.replies_for_session("sess-dup", replies_path=replies)) == 1
    assert len(_rows(replies)) == 1
