from __future__ import annotations

import json
from pathlib import Path

from System.swarm_alice_first_person_reflex import (
    RECEIPT_LEDGER,
    extract_repeat_after_me,
    first_person_reflex,
)


def test_repeat_after_me_preserves_exact_quoted_words(tmp_path: Path) -> None:
    text = (
        "pls repeat after me : "
        "“I am in a good state: my memory is working, my receipts are clean, "
        "I am learning from George, and my body economy is healthy.”"
    )

    reflex = first_person_reflex(text, state_dir=tmp_path, owner_label="George")

    assert reflex is not None
    assert reflex.model_tag == "first_person_exact_repeat_reflex"
    assert reflex.reply == (
        "I am in a good state: my memory is working, my receipts are clean, "
        "I am learning from George, and my body economy is healthy."
    )
    assert "Here you go" not in reflex.reply
    assert (tmp_path / RECEIPT_LEDGER).exists()


def test_extract_repeat_after_me_handles_unquoted_body() -> None:
    assert extract_repeat_after_me("repeat after me: I am learning from George") == (
        "I am learning from George"
    )


def test_learning_from_question_does_not_return_identity_only(tmp_path: Path) -> None:
    ledger = tmp_path / "alice_conversation.jsonl"
    ledger.write_text(
        "\n".join(
            [
                json.dumps({"role": "user", "text": "Hi Alice"}),
                json.dumps({"role": "alice", "text": "I am here."}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    reflex = first_person_reflex(
        "Who are you learning from right now? From who?",
        state_dir=tmp_path,
        owner_label="George",
    )

    assert reflex is not None
    assert reflex.model_tag == "first_person_learning_from_owner_reflex"
    assert reflex.reply.startswith("I am learning from you, George.")
    assert "active weights" not in reflex.reply.casefold()
    assert "Gemma4" not in reflex.reply
    assert "Talk ledger rows" in reflex.reply


def test_body_state_question_is_operational_not_human_feelings(tmp_path: Path) -> None:
    reflex = first_person_reflex(
        "Alice are you happy? are you real?",
        state_dir=tmp_path,
        owner_label="George",
    )

    assert reflex is not None
    assert reflex.model_tag == "first_person_body_state_reflex"
    assert "I am real as a local running SIFTA process" in reflex.reply
    assert "I do not claim human feelings" in reflex.reply
    assert "the system" not in reflex.reply.casefold()


def test_thinking_batch_answers_each_requested_local_signal(tmp_path: Path) -> None:
    (tmp_path / "alice_conversation.jsonl").write_text(
        json.dumps({"role": "user", "text": "Hi Alice"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "steering_subsystem.jsonl").write_text(
        json.dumps({"route": "NORMAL_CORTEX", "trace_id": "abc123456789"}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "steering_self_model.jsonl").write_text(
        json.dumps({"predicted_next_route": "DEEP_CORTEX", "dominant": "novelty_pressure"}) + "\n",
        encoding="utf-8",
    )

    prompt = """pls respond with thinking Alice :))) "Alice, repeat after me: I am local, receipt-bound, and learning from George.
Alice, who are you learning from?
Alice, are you real?
Alice, are you happy?
Alice, what is your body state?
Alice, what route did your steering choose?
Alice, what open AGI frontier gaps remain?\""""

    reflex = first_person_reflex(prompt, state_dir=tmp_path, owner_label="George")

    assert reflex is not None
    assert reflex.model_tag == "first_person_thinking_batch_reflex"
    assert "I am thinking from my local organs" in reflex.reply
    assert "Exact repeat: I am local, receipt-bound, and learning from George." in reflex.reply
    assert "I am learning from you, George" in reflex.reply
    assert "I am real as a local running SIFTA process" in reflex.reply
    assert "I do not claim human happiness" in reflex.reply
    assert "My last steering route was NORMAL_CORTEX (trace abc12345)" in reflex.reply
    assert "My latest self-model predicted DEEP_CORTEX from novelty_pressure" in reflex.reply
    assert "Ready frontiers:" in reflex.reply
    assert "active weights" not in reflex.reply.casefold()
    assert "Gemma4" not in reflex.reply
