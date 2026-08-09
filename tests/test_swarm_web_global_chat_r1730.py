"""R1730 public WEB TYPED attachment tests."""
from __future__ import annotations

import json

from System import chorus_node_server as server
from System import swarm_alice_slash_commands as slash
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
    assert 'id="speak"' not in page
    assert "Speak message" not in page


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


def test_explicit_speak_marker_strips_for_cortex_and_queues_message_for_talk(tmp_path):
    ingress = tmp_path / "ingress.jsonl"
    claims = tmp_path / "claims.jsonl"
    replies = tmp_path / "replies.jsonl"
    conversation = tmp_path / "conversation.jsonl"
    speech = tmp_path / "speech.jsonl"
    speech_claims = tmp_path / "speech-claims.jsonl"
    speech_done = tmp_path / "speech-done.jsonl"

    queued = gate.submit_web_message(
        "/speak Tell my mother I arrived at Apărătorii Patriei.",
        "sess-speak",
        ingress_path=ingress,
        conversation_path=conversation,
    )
    assert queued["accepted"] is True
    assert queued["speak_requested"] is True
    assert queued["prompt_text"] == "Tell my mother I arrived at Apărătorii Patriei."
    ingress_row = _rows(ingress)[0]
    assert ingress_row["text"].startswith("/speak ")
    assert ingress_row["tts"] is True

    claimed = gate.claim_next_web_turn(
        ingress_path=ingress,
        claim_path=claims,
        replies_path=replies,
    )
    assert claimed["prompt_text"] == queued["prompt_text"]
    assert claimed["speak_requested"] is True
    gate.record_web_user_turn(claimed, conversation_path=conversation)
    gate.complete_web_turn(
        queued["turn_id"],
        "You arrived safely at Apărătorii Patriei.",
        session_id=queued["session_id"],
        replies_path=replies,
        ingress_path=ingress,
        speech_requests_path=speech,
        conversation_path=conversation,
        metabolism_path=tmp_path / "metabolism.jsonl",
        speak_requested=True,
    )
    request = gate.claim_next_web_speech_request(
        requests_path=speech,
        claim_path=speech_claims,
        done_path=speech_done,
    )
    assert request["request_id"] == queued["turn_id"]
    assert request["text"] == "Tell my mother I arrived at Apărătorii Patriei."
    assert request["effectors_allowed"] == ["tts"]
    assert _rows(replies)[0]["visitor_reply"].startswith(
        "Queued for Alice's local speakers:"
    )
    gate.complete_web_speech_request(
        request["request_id"],
        ok=True,
        done_path=speech_done,
    )
    assert gate.claim_next_web_speech_request(
        requests_path=speech,
        claim_path=speech_claims,
        done_path=speech_done,
    ) is None


def test_speak_inside_url_is_not_a_command(tmp_path):
    prompt, requested = gate.extract_web_speak_command("Read https://example.com/speak aloud")
    assert prompt == "Read https://example.com/speak aloud"
    assert requested is False


def test_speak_marker_must_begin_the_web_message():
    prompt, requested = gate.extract_web_speak_command("Please /speak this sentence")
    assert prompt == "Please /speak this sentence"
    assert requested is False


def test_speech_repair_backfills_pre_change_reply(tmp_path):
    ingress = tmp_path / "ingress.jsonl"
    replies = tmp_path / "replies.jsonl"
    speech = tmp_path / "speech.jsonl"
    conversation = tmp_path / "conversation.jsonl"
    queued = gate.submit_web_message(
        "/speak Say this exact message",
        "sess-repair",
        ingress_path=ingress,
        conversation_path=conversation,
    )
    gate.complete_web_turn(
        queued["turn_id"],
        "old worker reply",
        session_id=queued["session_id"],
        replies_path=replies,
        ingress_path=ingress,
        speech_requests_path=speech,
        conversation_path=conversation,
        metabolism_path=tmp_path / "metabolism.jsonl",
    )
    repaired = gate.repair_web_speech_requests(
        ingress_path=ingress,
        replies_path=replies,
        requests_path=speech,
    )
    assert len(repaired) == 1
    assert repaired[0]["text"] == "Say this exact message"


def test_speak_is_documented_as_web_only_command(tmp_path):
    listed = {row["cmd"]: row for row in slash.registered_slash_commands()}
    assert "/speak" in listed
    assert "WEB TYPED" in listed["/speak"]["summary"]
    result = slash.handle_slash_command("/speak hello", state_dir=tmp_path)
    assert result["handled"] is True
    assert result["error"] == "web_typed_only"
    assert "local speakers" in result["reply"]
