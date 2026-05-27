import json
from pathlib import Path

from System import swarm_episodic_thread_linker as linker
from System import swarm_episodic_diary as diary


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def test_write_episodic_threads_links_related_events_across_days(tmp_path: Path) -> None:
    _append_jsonl(
        tmp_path / "alice_journal" / "2026-05-25.jsonl",
        [
            {
                "ts": 1779778800.0,
                "journal_id": "j_a",
                "local_journal_label": "05-25-26_10:00",
                "entry": "memory continuity across restart and agent arm timeout",
            }
        ],
    )
    _append_jsonl(
        tmp_path / "alice_journal" / "2026-05-26.jsonl",
        [
            {
                "ts": 1779865200.0,
                "journal_id": "j_b",
                "local_journal_label": "05-26-26_10:00",
                "entry": "restart continuity improved after fixing agent arm timeout",
            }
        ],
    )

    row = linker.write_episodic_threads(state_dir=tmp_path, window_days=14)
    assert row["truth_label"] == linker.TRUTH_LABEL
    assert row["thread_count"] >= 1
    assert row["journal_event_count"] >= 2
    thread = row["threads"][0]
    assert thread["day_count"] >= 2
    assert any(tok in thread["topic_tokens"] for tok in ("restart", "continuity", "timeout"))

    latest = linker.latest_threads(state_dir=tmp_path)
    assert latest["source_hash"] == row["source_hash"]


def test_write_episodic_threads_is_idempotent_by_source_hash(tmp_path: Path) -> None:
    _append_jsonl(
        tmp_path / "alice_journal" / "2026-05-25.jsonl",
        [
            {
                "ts": 1779778800.0,
                "journal_id": "j_1",
                "local_journal_label": "05-25-26_10:00",
                "entry": "owner discussed memory continuity and restart stability",
            }
        ],
    )
    _append_jsonl(
        tmp_path / "alice_journal" / "2026-05-26.jsonl",
        [
            {
                "ts": 1779865200.0,
                "journal_id": "j_2",
                "local_journal_label": "05-26-26_10:00",
                "entry": "restart stability and memory continuity still active",
            }
        ],
    )

    first = linker.write_episodic_threads(state_dir=tmp_path, window_days=14)
    second = linker.write_episodic_threads(state_dir=tmp_path, window_days=14)
    assert first
    assert second == {}
    rows = (tmp_path / linker.THREAD_LEDGER).read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1


def test_refresh_prompt_includes_cross_day_thread_block(tmp_path: Path) -> None:
    _append_jsonl(
        tmp_path / "alice_journal" / "2026-05-25.jsonl",
        [
            {
                "ts": 1779778800.0,
                "journal_id": "j_x",
                "local_journal_label": "05-25-26_10:00",
                "entry": "memory continuity across restart and agent timeout",
            }
        ],
    )
    _append_jsonl(
        tmp_path / "alice_journal" / "2026-05-26.jsonl",
        [
            {
                "ts": 1779865200.0,
                "journal_id": "j_y",
                "local_journal_label": "05-26-26_10:00",
                "entry": "restart continuity requested again with timeout focus",
            }
        ],
    )

    prompt = diary.refresh_and_format_diary_for_prompt(
        state_dir=tmp_path,
        hours=24,
        max_rows=4,
        max_apps=4,
        force=True,
    )
    assert "EPISODIC THREADS (cross-day links):" in prompt
    assert "thread=" in prompt
    assert "latest_ref=alice_journal/" in prompt

