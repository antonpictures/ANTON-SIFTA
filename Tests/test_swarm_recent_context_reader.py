from __future__ import annotations

import json
from pathlib import Path

from System.swarm_recent_context_reader import (
    RECEIPT_LEDGER,
    TRUTH_LABEL,
    answer_recent_context_query,
    prompt_block_for_recent_context,
    recent_talk_turns,
)


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def test_recent_talk_turns_reads_event_clock_wrapped_rows(tmp_path: Path) -> None:
    ledger = tmp_path / "alice_conversation.jsonl"
    _append(
        ledger,
        {
            "event_id": "u1",
            "ts": {"physical_pt": 10.0, "logical": 0},
            "payload": {
                "ts": 10.0,
                "role": "user",
                "text": "Alice, what is the date today?",
                "input_source": "voice",
            },
        },
    )
    _append(
        ledger,
        {
            "event_id": "a1",
            "ts": {"physical_pt": 11.0, "logical": 1},
            "payload": {
                "ts": 11.0,
                "role": "alice",
                "text": "George, today is Thursday, May 14, 2026.",
                "model": "hardware_date_oracle_reflex",
            },
        },
    )

    turns = recent_talk_turns(state_dir=tmp_path)

    assert [t.role for t in turns] == ["user", "alice"]
    assert turns[0].text == "Alice, what is the date today?"
    assert turns[1].model == "hardware_date_oracle_reflex"


def test_first_person_style_answer_is_direct_not_model_report(tmp_path: Path) -> None:
    reply = answer_recent_context_query(
        "Talking the first person show me how you talking in the first person",
        state_dir=tmp_path,
        owner_label="George",
    )

    assert reply.startswith("Yes, George.")
    assert "I hear you" in reply
    assert "my local receipts" in reply
    assert "the model" not in reply.lower()
    assert "the user" not in reply.lower()
    assert "the system" not in reply.lower()
    assert (tmp_path / RECEIPT_LEDGER).exists()


def test_last_user_message_answer_uses_previous_turn_not_current(tmp_path: Path) -> None:
    ledger = tmp_path / "alice_conversation.jsonl"
    _append(ledger, {"ts": 1.0, "role": "user", "text": "I was testing the first-person lane."})
    _append(ledger, {"ts": 2.0, "role": "alice", "text": "I heard that."})

    reply = answer_recent_context_query(
        "what did I just say?",
        state_dir=tmp_path,
        owner_label="George",
    )

    assert "your previous message was" in reply
    assert "testing the first-person lane" in reply


def test_summary_answer_compacts_recent_talk_context(tmp_path: Path) -> None:
    ledger = tmp_path / "alice_conversation.jsonl"
    _append(ledger, {"ts": 1.0, "role": "user", "text": "We are wiring hardware time."})
    _append(ledger, {"ts": 2.0, "role": "alice", "text": "I answer time from my hardware oracle."})
    _append(ledger, {"ts": 3.0, "role": "user", "text": "Now wire recent context."})

    reply = answer_recent_context_query(
        "what were we talking about?",
        state_dir=tmp_path,
        owner_label="George",
    )

    assert "I read my recent Talk ledger" in reply
    assert "hardware time" in reply
    assert "recent context" in reply


def test_prompt_block_tells_cortex_to_use_first_person() -> None:
    block = prompt_block_for_recent_context(
        history=[
            {"role": "user", "content": "Talk one on one."},
            {"role": "assistant", "content": "I am here."},
        ]
    )

    assert TRUTH_LABEL in block
    assert "Use first person" in block
    assert "OWNER: Talk one on one." in block
    assert "ALICE: I am here." in block
