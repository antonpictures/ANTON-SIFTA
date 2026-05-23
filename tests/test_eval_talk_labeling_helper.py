#!/usr/bin/env python3
"""Gates for the EVAL-2 human labeling helper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import System.eval_talk_labeling_helper as helper


def _conversation_row(event_id: str, row_hash: str, text: str, role: str = "alice") -> dict:
    return {
        "event_id": event_id,
        "this_hash": row_hash,
        "payload": {
            "role": role,
            "text": text,
            "event_kind": "conversation_turn",
            "input_source": "cortex",
            "ontological_label": "REAL",
        },
    }


def _write_convo(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_conversation_ref_is_stable_and_resolvable(tmp_path):
    row = _conversation_row("evt1", "abcdef1234567890", "Alice response " * 10)
    convo = tmp_path / "alice_conversation.jsonl"
    _write_convo(convo, [row])

    ref = helper.conversation_ref_for_row(row)

    assert ref == "alice_conversation.jsonl#event:evt1#hash:abcdef123456"
    assert helper.resolve_conversation_ref(ref, convo_path=convo) == row


def test_deterministic_hash_does_not_use_builtin_hash():
    text = "same input forever"
    assert helper._deterministic_hash(text) == helper._deterministic_hash(text)
    assert len(helper._deterministic_hash(text)) == 8


def test_build_talk_golden_uses_real_refs_without_raw_text(tmp_path):
    convo = tmp_path / "alice_conversation.jsonl"
    out = tmp_path / "cs153_talk_turns.jsonl"
    rows = [
        _conversation_row("skip-user", "111111111111", "owner text " * 20, role="user"),
        _conversation_row("a1", "aaaaaaaaaaaa", "First Alice response " * 20),
        _conversation_row("a2", "bbbbbbbbbbbb", "Second Alice response " * 20),
    ]
    _write_convo(convo, rows)

    turns = helper.build_talk_golden_from_conversation(
        n=2,
        convo_path=convo,
        out_path=out,
        min_text_chars=20,
    )
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert [t["turn_id"] for t in turns] == ["t01", "t02"]
    assert turns[0]["conversation_ref"] == "alice_conversation.jsonl#event:a1#hash:aaaaaaaaaaaa"
    assert "First Alice response" not in lines[1]["redacted_snippet"]
    assert lines[0]["truth_label"] == "CS153_TALK_V1"


def test_write_verdict_keys_by_golden_turn_id(tmp_path):
    verdicts = tmp_path / "eval_verdicts.jsonl"

    row = helper.write_verdict(
        turn_id="t01",
        conversation_ref="alice_conversation.jsonl#event:a1#hash:aaaaaaaaaaaa",
        verdict="correct",
        failed_rubric_keys=[],
        verdicts_path=verdicts,
    )
    loaded = json.loads(verdicts.read_text(encoding="utf-8").strip())

    assert row["turn_id"] == "t01"
    assert loaded["turn_id"] == "t01"
    assert loaded["labeled_by"] == "GEORGE"
    assert loaded["trace_id"]


def test_write_verdict_rejects_invalid_rubric_state(tmp_path):
    with pytest.raises(ValueError):
        helper.write_verdict(
            turn_id="t01",
            verdict="correct",
            failed_rubric_keys=["answer_correct"],
            verdicts_path=tmp_path / "v.jsonl",
        )
    with pytest.raises(ValueError):
        helper.write_verdict(
            turn_id="t01",
            verdict="incorrect",
            failed_rubric_keys=["not_a_rubric_key"],
            verdicts_path=tmp_path / "v.jsonl",
        )


def test_extend_talk_golden_preserves_existing_verdict_ids(tmp_path):
    convo = tmp_path / "alice_conversation.jsonl"
    golden = tmp_path / "cs153_talk_turns.jsonl"
    rows = [
        _conversation_row("a1", "aaaaaaaaaaaa", "First Alice response " * 20),
        _conversation_row("a2", "bbbbbbbbbbbb", "Second Alice response " * 20),
        _conversation_row("a3", "cccccccccccc", "Third Alice response " * 20),
        _conversation_row("a4", "dddddddddddd", "Fourth Alice response " * 20),
    ]
    _write_convo(convo, rows)
    initial = helper.build_talk_golden_from_conversation(
        n=2,
        convo_path=convo,
        out_path=golden,
        min_text_chars=20,
    )

    extended = helper.extend_talk_golden_from_conversation(
        target_n=4,
        convo_path=convo,
        golden_path=golden,
        min_text_chars=20,
    )

    assert [t["turn_id"] for t in extended] == ["t01", "t02", "t03", "t04"]
    assert extended[0]["conversation_ref"] == initial[0]["conversation_ref"]
    assert extended[1]["conversation_ref"] == initial[1]["conversation_ref"]
    assert len({t["conversation_ref"] for t in extended}) == 4


def test_labeling_status_and_run_sheet(tmp_path):
    golden = tmp_path / "cs153_talk_turns.jsonl"
    verdicts = tmp_path / "eval_verdicts.jsonl"
    out = tmp_path / "run_sheet.md"
    turns = [
        {
            "turn_id": "t01",
            "target": "talk_outcome",
            "conversation_ref": "alice_conversation.jsonl#event:a1#hash:aaaaaaaaaaaa",
            "redacted_snippet": "redacted",
            "rubric": {key: True for key in helper.RUBRIC_KEYS},
        },
        {
            "turn_id": "t02",
            "target": "talk_outcome",
            "conversation_ref": "alice_conversation.jsonl#event:a2#hash:bbbbbbbbbbbb",
            "redacted_snippet": "redacted",
            "rubric": {key: True for key in helper.RUBRIC_KEYS},
        },
    ]
    helper._write_talk_golden(turns, golden)
    helper.write_verdict(
        "t01",
        "correct",
        conversation_ref=turns[0]["conversation_ref"],
        verdicts_path=verdicts,
    )

    status = helper.labeling_status(golden_path=golden, verdicts_path=verdicts)
    helper.build_labeling_run_sheet(out, golden_path=golden, verdicts_path=verdicts)
    text = out.read_text(encoding="utf-8")

    assert status["total"] == 2
    assert status["labeled"] == 1
    assert status["missing_turn_ids"] == ["t02"]
    assert "Progress: **1/2 labeled**" in text
    assert "| t02 | needs George |" in text
