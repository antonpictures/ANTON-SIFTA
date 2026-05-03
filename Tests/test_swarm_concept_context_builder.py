import json

from System.swarm_concept_context_builder import (
    build_concept_context,
    compact_row,
    read_tail,
)
from System.swarm_concept_budget_gate import compress_packet, score_row


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            if isinstance(row, str):
                fh.write(row + "\n")
            else:
                fh.write(json.dumps(row, sort_keys=True) + "\n")


def _packet(text: str) -> dict:
    return json.loads(text[text.index("{") :])


def test_read_tail_is_bounded_to_last_valid_rows(tmp_path):
    path = tmp_path / "ledger.jsonl"
    _write_jsonl(
        path,
        ["not-json"] + [{"ts": i, "summary": f"row-{i}"} for i in range(12)],
    )

    rows = read_tail(path, 3, max_bytes=2048)

    assert [r["summary"] for r in rows] == ["row-9", "row-10", "row-11"]


def test_compact_row_whitelists_and_truncates_large_values():
    row = {
        "ts": 1.0,
        "summary": "visible",
        "private_raw_transcript": "do not inject",
        "action": {"kind": "explore", "payload": "x" * 100},
    }

    compact = compact_row(row, max_value_chars=40)

    assert compact["summary"] == "visible"
    assert "private_raw_transcript" not in compact
    assert compact["action"].endswith("…")
    assert len(compact["action"]) == 40


def test_build_concept_context_reads_real_ledgers_by_source(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_jsonl(
        state / "architect_day_segments.jsonl",
        [
            {"ts": 1, "label": "sleep", "start_minute": 660, "end_minute": 900},
            {"ts": 2, "label": "youtube_nap", "media_context": "Jensen video"},
        ],
    )
    _write_jsonl(
        state / "body_brain_memory.jsonl",
        [{"ts": 3, "regime": "EXPLORATION", "selected_drive": "curiosity"}],
    )

    packet = _packet(build_concept_context(state_dir=state, max_rows_per_source=5))

    assert packet["truth_label"] == "CONCEPT_CONTEXT_PACKET"
    assert packet["sources"]["day_segments"][-1]["label"] == "youtube_nap"
    assert packet["sources"]["body"][0]["selected_drive"] == "curiosity"


def test_build_concept_context_reads_unified_field(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_jsonl(
        state / "unified_stigmergic_field.jsonl",
        [
            {
                "ts": 3,
                "truth_label": "UNIFIED_STIGMERGIC_FIELD_V1",
                "field_confidence": 0.91,
                "watching_together": True,
                "owner_activity": "George has Stigmergic Unified Shazam open and is co-watching media.",
                "media_guess": {"primary_category": "Gaming", "confidence": 0.98},
            }
        ],
    )

    packet = _packet(build_concept_context(state_dir=state, max_rows_per_source=5))

    row = packet["sources"]["unified_field"][0]
    assert row["truth_label"] == "UNIFIED_STIGMERGIC_FIELD_V1"
    assert row["watching_together"] is True
    assert "Stigmergic Unified Shazam" in row["owner_activity"]
    assert "Gaming" in row["media_guess"]


def test_build_concept_context_limits_rows_per_source(tmp_path):
    state = tmp_path / ".sifta_state"
    _write_jsonl(
        state / "episodic_diary.jsonl",
        [{"ts": i, "summary": f"bucket-{i}"} for i in range(10)],
    )

    packet = _packet(build_concept_context(state_dir=state, max_rows_per_source=2))

    rows = packet["sources"]["episodic_diary"]
    assert [r["summary"] for r in rows] == ["bucket-8", "bucket-9"]


def test_build_concept_context_handles_empty_state_dir(tmp_path):
    packet = _packet(build_concept_context(state_dir=tmp_path / ".sifta_state"))

    assert packet["sources"] == {}
    assert packet["note"].startswith("Facts from ledgers")


def test_budget_gate_writes_receipt_to_requested_state_dir(tmp_path):
    state = tmp_path / ".sifta_state"
    packet = {
        "truth_label": "CONCEPT_CONTEXT_PACKET",
        "sources": {"body": [{"ts": 1, "truth_label": "BODY", "summary": "ok"}]},
    }

    compressed = compress_packet(packet, state_dir=state)

    rows = (state / "concept_context_budget.jsonl").read_text(encoding="utf-8").splitlines()
    receipt = json.loads(rows[-1])
    assert compressed["budget"]["kept_rows"] == 1
    assert receipt["truth_label"] == "CONCEPT_BUDGET_GATE"
    assert receipt["packet_hash"] == compressed["budget"]["packet_hash"]


def test_budget_gate_can_run_without_receipt(tmp_path):
    state = tmp_path / ".sifta_state"
    packet = {
        "truth_label": "CONCEPT_CONTEXT_PACKET",
        "sources": {"body": [{"ts": 1, "truth_label": "BODY", "summary": "ok"}]},
    }

    compressed = compress_packet(packet, state_dir=state, write_receipt=False)

    assert compressed["budget"]["kept_rows"] == 1
    assert not (state / "concept_context_budget.jsonl").exists()


def test_budget_gate_drops_rows_to_fit_char_budget():
    packet = {
        "truth_label": "CONCEPT_CONTEXT_PACKET",
        "sources": {
            "body": [
                {"ts": 1, "truth_label": "BODY", "summary": "x" * 200},
                {"ts": 2, "truth_label": "BODY", "summary": "y" * 200},
            ]
        },
    }

    compressed = compress_packet(packet, max_chars=180, write_receipt=False)

    assert compressed["budget"]["kept_rows"] < 2
    assert compressed["budget"]["dropped_rows"] >= 1


def test_score_row_prefers_fresh_truth_labeled_rows():
    fresh = {"ts": 9_999_999_999, "truth_label": "FRESH", "summary": "ok"}
    stale = {"ts": 1, "summary": "old"}

    assert score_row(fresh) > score_row(stale)
