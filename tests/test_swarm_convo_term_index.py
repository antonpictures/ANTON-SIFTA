from __future__ import annotations

import json
import time
from pathlib import Path

from System import swarm_convo_term_index as idx
from System import swarm_temporal_episodic_memory as tem


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("ab") as handle:
        for row in rows:
            handle.write(json.dumps(row).encode("utf-8") + b"\n")


def test_convo_index_is_incremental_and_queries_offsets(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    convo = state / "alice_conversation.jsonl"
    _append_jsonl(convo, [{"ts": 100.0, "role": "user", "text": "ordinary row"}])

    first = idx.ensure_indexed(convo, state_dir=state)
    assert first["indexed_now"] == 1
    first_offset = first["last_indexed_offset"]

    _append_jsonl(convo, [{"ts": 101.0, "role": "user", "text": "Adrian reported femur surgery Monday"}])
    second = idx.ensure_indexed(convo, state_dir=state)
    assert second["indexed_now"] == 1
    assert second["last_indexed_offset"] > first_offset

    hits = idx.query_index("femur surgery", conversation_path=convo, state_dir=state)
    assert len(hits) == 1
    assert hits[0]["row"]["text"] == "Adrian reported femur surgery Monday"
    assert hits[0]["byte_offset"] >= first_offset


def test_convo_index_survives_partial_write_and_resyncs(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    convo = state / "alice_conversation.jsonl"
    _append_jsonl(convo, [{"ts": 100.0, "text": "stable femur row"}])
    convo.open("ab").write(b'{"ts": 101, "text": "partial femur row"')

    first = idx.ensure_indexed(convo, state_dir=state)
    partial_offset = first["last_indexed_offset"]
    assert idx.query_index("partial", conversation_path=convo, state_dir=state) == []

    convo.open("ab").write(b'}\n')
    second = idx.ensure_indexed(convo, state_dir=state)
    assert second["last_indexed_offset"] > partial_offset
    hits = idx.query_index("partial", conversation_path=convo, state_dir=state)
    assert hits and hits[0]["row"]["text"] == "partial femur row"


def test_temporal_recall_finds_old_global_conversation_via_index(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    now = time.time()
    convo = state / "alice_conversation.jsonl"
    _append_jsonl(
        convo,
        [
            {
                "ts": now - 20 * 86400,
                "role": "user",
                "text": "Adrian sent George the femur surgery update from Romania",
            },
            {"ts": now - 60, "role": "user", "text": "fresh unrelated broker note"},
        ],
    )
    (state / "memory_ledger.jsonl").write_text("", encoding="utf-8")
    (state / "alice_first_person_journal.jsonl").write_text("", encoding="utf-8")
    (state / "stigmergic_schedule.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr(tem, "_CONVO", convo)
    monkeypatch.setattr(tem, "_NARRATIVE_DIARY", state / "alice_narrative_diary.jsonl")
    monkeypatch.setattr(tem, "_ACTION_DIARY", state / "app_action_diary.jsonl")
    monkeypatch.setattr(tem, "_RETRIEVAL_LEDGER", state / "memory_retrieval_receipts.jsonl")

    out = tem.recall_facts_for_query("remember Adrian femur surgery Romania")

    assert out["recall_mode"] == "content_ranked_all_time"
    assert out["facts"]
    assert out["facts"][0]["source"] == "alice_conversation.jsonl"
    assert "femur surgery" in out["facts"][0]["snippet"].lower()


def test_convo_index_query_fast_after_build(tmp_path):
    state = tmp_path / ".sifta_state"
    state.mkdir()
    convo = state / "alice_conversation.jsonl"
    with convo.open("wb") as handle:
        for i in range(100_000):
            text = f"ambient filler row {i}"
            if i == 42_424:
                text = "rareneedle femur surgery Romania Adrian"
            handle.write(json.dumps({"ts": float(i), "text": text}).encode("utf-8") + b"\n")

    idx.ensure_indexed(convo, state_dir=state)
    start = time.perf_counter()
    hits = idx.query_index("rareneedle femur surgery", conversation_path=convo, state_dir=state)
    elapsed = time.perf_counter() - start

    assert hits and hits[0]["row"]["text"] == "rareneedle femur surgery Romania Adrian"
    assert elapsed < 0.5
