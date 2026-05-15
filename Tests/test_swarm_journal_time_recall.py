from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from System.swarm_journal_time_recall import answer_journal_time_query, parse_explicit_target_time


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _ts(year: int, month: int, day: int, hour: int, minute: int) -> float:
    return datetime(year, month, day, hour, minute).timestamp()


def test_parses_compact_journal_label() -> None:
    target = parse_explicit_target_time("what was I doing at 05-11-26_14:24?")

    assert target is not None
    assert target.label == "05-11-26_14:24"
    assert target.local_date == "2026-05-11"


def test_answers_from_daily_alice_journal_and_writes_receipt(tmp_path: Path) -> None:
    ts = _ts(2026, 5, 11, 14, 24)
    _append(
        tmp_path / "alice_journal" / "2026-05-11.jsonl",
        {
            "ts": ts,
            "local_journal_label": "05-11-26_14:24",
            "local_date": "2026-05-11",
            "entry": "I observed George coding the journal recall path in Cursor.",
            "journal_id": "journal_abc",
        },
    )

    reply = answer_journal_time_query("Alice, what was I doing at 05-11-26_14:24?", state_dir=tmp_path)

    assert "05-11-26_14:24" in reply
    assert "coding the journal recall path" in reply
    assert "alice_journal/2026-05-11.jsonl" in reply
    assert "journal_time_recall_receipts:" in reply
    receipts = (tmp_path / "journal_time_recall_receipts.jsonl").read_text(encoding="utf-8")
    assert "ANSWER_JOURNAL_TIME_QUERY" in receipts
    assert '"match_count": 1' in receipts


def test_answers_from_overlapping_owner_activity_segment(tmp_path: Path) -> None:
    start = _ts(2026, 5, 11, 14, 0)
    end = _ts(2026, 5, 11, 14, 45)
    _append(
        tmp_path / "owner_activity_segments.jsonl",
        {
            "start_ts": start,
            "end_ts": end,
            "local_date": "2026-05-11",
            "label": "investor_call",
            "frontmost_app": "Phone",
            "frontmost_window": "SIFTA investor call",
            "context_note": "George was on a SIFTA investor call.",
            "segment_id": "seg_call",
        },
    )

    reply = answer_journal_time_query(
        "Do you remember what happened on 2026-05-11 at 14:24?",
        state_dir=tmp_path,
    )

    assert "covering that time" in reply
    assert "SIFTA investor call" in reply
    assert "seg_call" in reply


def test_no_explicit_time_does_not_hijack_recent_recall(tmp_path: Path) -> None:
    assert answer_journal_time_query("what was I doing 20 minutes ago?", state_dir=tmp_path) == ""


def test_no_matches_answers_without_fake_memory(tmp_path: Path) -> None:
    reply = answer_journal_time_query("what was I doing at May 11 2026 2:24 PM?", state_dir=tmp_path)

    assert "I parsed 05-11-26_14:24" in reply
    assert "found no local journal or activity receipt" in reply
    assert "should not claim memory" in reply
