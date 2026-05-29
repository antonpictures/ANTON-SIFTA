import json
from pathlib import Path

from System import swarm_hippocampus as hippocampus
from System.swarm_memory_card import compose_memory_card


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_recall_associations_returns_receipt_backed_matches(tmp_path):
    state = tmp_path / ".sifta_state"
    _append_jsonl(
        state / "work_receipts.jsonl",
        [
            {
                "ts": 100.0,
                "receipt_id": "r-memory-1",
                "action": "hippocampus associative memory patch",
                "truth_note": "wired pheromone freshness loop into memory card",
            },
            {
                "ts": 101.0,
                "receipt_id": "r-other",
                "action": "unrelated wallpaper refresh",
                "truth_note": "changed chat background color",
            },
        ],
    )

    matches = hippocampus.recall_associations(
        "hippocampus memory pheromone",
        state_dir=state,
        k=1,
    )

    assert len(matches) == 1
    assert matches[0]["receipt_ref"] == "r-memory-1"
    assert "hippocampus" in matches[0]["matched_tokens"]
    assert matches[0]["semantic_hash"]


def test_associative_recall_prompt_block_is_grounded(tmp_path):
    state = tmp_path / ".sifta_state"
    _append_jsonl(
        state / "episodic_diary.jsonl",
        [
            {
                "ts": 200.0,
                "event_id": "evt-1",
                "kind": "arm_dispatch_round",
                "lesson_short": "pheromone field freshness improved memory wake",
            }
        ],
    )

    block = hippocampus.associative_recall_prompt_block(
        "memory freshness",
        state_dir=state,
    )

    assert "HIPPOCAMPAL ASSOCIATIVE RECALL" in block
    assert "evt-1" in block
    assert "pheromone field freshness" in block


def test_associative_recall_prompt_block_includes_age_s(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    now = 10_000.0
    _append_jsonl(
        state / "work_receipts.jsonl",
        [
            {
                "ts": now - 3700,
                "receipt_id": "r-age",
                "action": "hippocampus age tag recall",
                "truth_note": "owner asked for from N seconds ago wording",
            }
        ],
    )
    monkeypatch.setattr("System.swarm_hippocampus.time.time", lambda: now)

    block = hippocampus.associative_recall_prompt_block(
        "hippocampus age tag",
        state_dir=state,
    )

    assert "age_s=3700" in block
    assert "r-age" in block


def test_query_requests_associative_recall_is_legacy_hint_not_prompt_gate():
    assert hippocampus.query_requests_associative_recall("Alice your body is amazing") is False
    assert hippocampus.query_requests_associative_recall("Good job Alice, thank you") is False
    assert hippocampus.query_requests_associative_recall("what happened to your body repair?") is True
    assert hippocampus.query_requests_associative_recall("[TOOL_CALL: read_file | path=Documents/x.md]") is True
    assert hippocampus.query_requests_associative_recall("1. inspect the current graph\n2. run tests") is True
    assert hippocampus.query_requests_associative_recall("please compare the cortex wake traces") is False


def test_write_associative_recall_appends_without_rewriting(tmp_path):
    state = tmp_path / ".sifta_state"
    _append_jsonl(
        state / "alice_conversation.jsonl",
        [{"ts": 1.0, "payload": {"text": "Alice learns through hippocampus traces"}}],
    )

    first = hippocampus.write_associative_recall("hippocampus traces", state_dir=state)
    second = hippocampus.write_associative_recall("hippocampus traces", state_dir=state)
    path = state / "hippocampus" / "associative_recall.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()

    assert first["truth_label"] == "HIPPOCAMPUS_ASSOCIATIVE_RECALL_V1"
    assert second["match_count"] == 1
    assert len(lines) == 2


def test_memory_card_includes_associative_recall_from_passed_state_dir(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    _append_jsonl(
        state / "work_receipts.jsonl",
        [
            {
                "ts": 300.0,
                "receipt_id": "r-card",
                "action": "hippocampus recall memory card bridge",
                "truth_note": "associative recall now enters cortex prompt",
            }
        ],
    )
    monkeypatch.setattr(hippocampus, "_ENGRAMS_LOG", state / "long_term_engrams.jsonl")

    card = compose_memory_card(
        state,
        user_text="what do you recall about memory card hippocampus recall?",
        token_budget=500,
        repo_root=tmp_path,
    )

    assert "HIPPOCAMPAL ASSOCIATIVE RECALL" in card.engram_block
    assert "r-card" in card.engram_block


def test_memory_card_attempts_recall_for_plain_social_statement(tmp_path, monkeypatch):
    state = tmp_path / ".sifta_state"
    _append_jsonl(
        state / "work_receipts.jsonl",
        [
            {
                "ts": 400.0,
                "receipt_id": "r80-body",
                "action": "r80 is in the body",
                "truth_note": "kernel failure decay and stale speech guard are live in the body",
            }
        ],
    )
    monkeypatch.setattr(hippocampus, "_ENGRAMS_LOG", state / "long_term_engrams.jsonl")

    card = compose_memory_card(
        state,
        user_text="Alice your body is amazing",
        token_budget=500,
        repo_root=tmp_path,
    )

    attempts = state / "hippocampus" / "recall_attempts.jsonl"
    assert attempts.exists()
    rows = [json.loads(line) for line in attempts.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["truth_label"] == "HIPPOCAMPUS_RECALL_ATTEMPT_V1"
    assert rows[0]["query_hash"]
    assert "Alice your body is amazing" not in rows[0].values()
    assert "HIPPOCAMPAL ASSOCIATIVE RECALL" in card.engram_block
