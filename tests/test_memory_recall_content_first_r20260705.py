"""r-memory-recall-content-first-20260705 — the words in the owner's mouth must
reach the rows on disk.

OBSERVED failure (2026-07-05 04:16): George asked 'remember she broke her
femur? she is in the hospital still. look up in your memory'. The memory WAS on
disk (memory_ledger raw turns from Jul 3, back-filled journal row, schedule
rows) but recall returned business-podcast tail noise: the search ran only
inside a resolved time window, searched non-content keys, scored stopwords like
'still'/'memory', and let 'broke' substring-match 'broker'.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System import swarm_temporal_episodic_memory as tem


@pytest.fixture()
def memory_world(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    now = time.time()
    old = now - 2 * 86400.0  # two days ago — outside any 'recent' default window

    def _w(name, rows):
        p = state / name
        with p.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        return p

    convo = _w("alice_conversation.jsonl", [
        {"ts": now - 3600, "role": "user",
         "text": "using transparent data instead of commissioned broker for the franchise"},
        {"ts": now - 1800, "role": "user",
         "text": "partnerships with other services as it hospitals plug your distribution"},
        {"ts": now - 5, "role": "user",
         "text": "remember she broke her femur? she is in the hospital still. look up in your memory"},
    ])
    _w("memory_ledger.jsonl", [
        {"ts": old, "raw_text": "my brother adi said: Fractura de femur, admission tonight, "
                                "surgery Monday; mom has a femur fracture"},
        {"ts": now - 7200, "raw_text": "podcast rant about brokers and brokerage nothing medical"},
        {"ts": now - 600, "raw_text": "ambient transcript: the launch broke after a hospital interview"},
        {"ts": now - 500, "raw_text": "ambient transcript: a TV segment broke near the hospital desk"},
        {"ts": now - 400, "raw_text": "ambient transcript: the market broke while a hospital ad played"},
        {"ts": now - 300, "raw_text": "ambient transcript: the machine broke beside a hospital storyline"},
        {"ts": now - 200, "raw_text": "ambient transcript: the clip broke during the hospital scene"},
    ])
    _w("alice_first_person_journal.jsonl", [
        {"ts": old, "line": "George's mother fell — femur fracture; surgery Monday in Romania; "
                            "he flies LAX to OTP Jul 16."},
    ])
    _w("stigmergic_schedule.jsonl", [
        {"ts": old, "created": old, "text": "Mama's femur surgery in Romania — check in with Adrian",
         "priority": 3, "done": False},
    ])
    monkeypatch.setattr(tem, "_CONVO", convo)
    monkeypatch.setattr(tem, "_NARRATIVE_DIARY", state / "alice_narrative_diary.jsonl")
    monkeypatch.setattr(tem, "_ACTION_DIARY", state / "app_action_diary.jsonl")
    monkeypatch.setattr(tem, "_RETRIEVAL_LEDGER", state / "memory_retrieval_receipts.jsonl")
    return state


def test_femur_memory_found_outside_time_window(memory_world):
    out = tem.recall_facts_for_query(
        "remember she broke her femur? she is in the hospital still. look up in your memory"
    )
    assert out["recall_mode"] == "content_ranked_all_time"
    blobs = " || ".join(str(f.get("snippet", "")).lower() for f in out["facts"][:3])
    assert "femur" in blobs
    assert "fractura" in blobs or "surgery monday" in blobs


def test_broker_rows_do_not_outrank_femur(memory_world):
    out = tem.recall_facts_for_query("remember she broke her femur?")
    top = str(out["facts"][0].get("snippet", "")).lower()
    assert "femur" in top
    assert "brokerage" not in top


def test_query_echo_row_is_not_a_memory(memory_world):
    out = tem.recall_facts_for_query(
        "remember she broke her femur? she is in the hospital still. look up in your memory"
    )
    for f in out["facts"]:
        assert "look up in your memory" not in str(f.get("snippet", "")).lower()


def test_stopwords_do_not_drive_recall(memory_world):
    # A query whose only >3-char words are recall stopwords must not fabricate matches.
    out = tem.recall_facts_for_query("remember what did they tell you about this?")
    assert all(
        "broker" not in str(f.get("snippet", "")).lower() for f in out["facts"]
    )


def test_recall_reinforces_overlay_without_mutating_memory_ledger(memory_world):
    ledger = memory_world / "memory_ledger.jsonl"
    before = ledger.read_bytes()

    first = tem.recall_facts_for_query("remember she broke her femur?")
    second = tem.recall_facts_for_query("remember she broke her femur?")

    assert ledger.read_bytes() == before
    assert first["reinforcement"]["reinforced"] > 0
    assert second["reinforcement"]["reinforced"] > 0

    from System.memory_fitness_overlay import strength_for

    trace_id = second["reinforcement"]["trace_ids"][0]
    assert strength_for([trace_id], state_dir=memory_world)[trace_id] > 1.05


def test_strengthened_old_row_beats_equal_hit_fresher_junk(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    old = now - 30 * 86400.0
    ledger = state / "memory_ledger.jsonl"
    ledger.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": old,
                        "trace_id": "old_femur_receipt",
                        "raw_text": "adrian anchor femur hospital note for George mother",
                    }
                ),
                json.dumps(
                    {
                        "ts": now - 60,
                        "trace_id": "fresh_junk_receipt",
                        "raw_text": "femur hospital words in a nihilism rant with no family fact",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    convo = state / "alice_conversation.jsonl"
    convo.write_text("", encoding="utf-8")
    monkeypatch.setattr(tem, "_CONVO", convo)
    monkeypatch.setattr(tem, "_NARRATIVE_DIARY", state / "alice_narrative_diary.jsonl")
    monkeypatch.setattr(tem, "_ACTION_DIARY", state / "app_action_diary.jsonl")
    monkeypatch.setattr(tem, "_RETRIEVAL_LEDGER", state / "memory_retrieval_receipts.jsonl")

    tem.recall_facts_for_query("remember adrian anchor detail")
    out = tem.recall_facts_for_query("what about femur and hospital")

    assert out["facts"][0]["row"]["trace_id"] == "old_femur_receipt"
