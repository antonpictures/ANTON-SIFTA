import json
import time
from pathlib import Path

from System import swarm_episodic_diary as diary


def _fixed_ts(hour: int, minute: int = 0) -> float:
    return time.mktime((2026, 5, 2, hour, minute, 0, 0, 0, -1))


def _write_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def test_write_diary_expands_explicit_sleep_segment_across_buckets(tmp_path):
    _write_jsonl(
        tmp_path / "architect_day_segments.jsonl",
        [
            {
                "ts": _fixed_ts(15, 5),
                "truth_label": "ARCHITECT_DAY_SEGMENT_V1",
                "local_date": "2026-05-02",
                "start_minute_of_day": 11 * 60,
                "end_minute_of_day": 15 * 60,
                "duration_minutes": 240,
                "label": "sleep",
                "location": "bedroom",
                "media_context": "youtube_tv_loud",
                "context_note": "slept from 11ap to 3pm in the bedrook listening to tv loud on youtube",
            }
        ],
    )

    rows = diary.write_episodic_diary(hours=4, state_dir=tmp_path, now=_fixed_ts(15, 17))

    buckets = {row["bucket"]: row for row in rows}
    assert "2026-05-02T08:00" in buckets
    assert "2026-05-02T12:00" in buckets
    for row in buckets.values():
        assert "sleep" in row["labels"]
        assert "media" in row["labels"]
        assert any("loc=bedroom" in fact for fact in row["facts"])
        assert any("media=youtube_tv_loud" in fact for fact in row["facts"])


def test_write_diary_compresses_implicit_media_and_coding_traces(tmp_path):
    _write_jsonl(
        tmp_path / "youtube_context.jsonl",
        [
            {
                "ts": _fixed_ts(14, 10),
                "title": "Jensen Huang NVIDIA GTC interview",
                "video_id": "x5IX5Uleb9g",
                "status": "empty_captions",
            }
        ],
    )
    _write_jsonl(
        tmp_path / "media_ingress_gate.jsonl",
        [
            {
                "ts": _fixed_ts(14, 20),
                "route": "ambient_media",
                "reason": "owner_declared_background_media_youtube",
                "text_preview": "NVIDIA GPUs and AI factories",
            }
        ],
    )
    _write_jsonl(
        tmp_path / "ide_stigmergic_trace.jsonl",
        [
            {
                "ts": _fixed_ts(15, 2),
                "kind": "work_receipt",
                "action": "pytest and commit",
                "payload": "pytest passed and committed code",
            }
        ],
    )

    rows = diary.write_episodic_diary(hours=4, state_dir=tmp_path, now=_fixed_ts(15, 17))

    assert len(rows) == 1
    row = rows[0]
    assert row["bucket"] == "2026-05-02T12:00"
    assert "media" in row["labels"]
    assert "coding" in row["labels"]
    assert any("Jensen Huang" in fact for fact in row["facts"])


def test_write_diary_is_idempotent_by_bucket_and_source_hash(tmp_path):
    _write_jsonl(
        tmp_path / "ide_stigmergic_trace.jsonl",
        [{"ts": _fixed_ts(10), "kind": "work_receipt", "payload": "pytest passed and commit"}],
    )

    first = diary.write_episodic_diary(hours=4, state_dir=tmp_path, now=_fixed_ts(11))
    second = diary.write_episodic_diary(hours=4, state_dir=tmp_path, now=_fixed_ts(11, 1))

    assert len(first) == 1
    assert second == []
    lines = (tmp_path / "episodic_diary.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_format_diary_for_prompt_surfaces_recent_story(tmp_path):
    _write_jsonl(
        tmp_path / "architect_day_segments.jsonl",
        [
            {
                "ts": _fixed_ts(15),
                "truth_label": "ARCHITECT_DAY_SEGMENT_V1",
                "local_date": "2026-05-02",
                "start_minute_of_day": 11 * 60,
                "end_minute_of_day": 15 * 60,
                "label": "sleep",
                "location": "bedroom",
                "media_context": "youtube_tv_loud",
                "context_note": "nap block",
            }
        ],
    )
    diary.write_episodic_diary(hours=4, state_dir=tmp_path, now=_fixed_ts(15, 17))

    prompt = diary.format_diary_for_prompt(state_dir=tmp_path)

    assert "EPISODIC DIARY" in prompt
    assert "2026-05-02T12:00" in prompt
    assert "sleep" in prompt
    assert "youtube_tv_loud" in prompt
