from __future__ import annotations

from pathlib import Path

from System import swarm_youtube_transcript_skill as skill


def test_youtube_video_id_variants():
    assert skill.youtube_video_id("https://www.youtube.com/watch?v=vy7o1g21HY8") == "vy7o1g21HY8"
    assert skill.youtube_video_id("https://youtu.be/abc123?t=10") == "abc123"
    assert skill.youtube_video_id("https://www.youtube.com/shorts/shortid") == "shortid"
    assert skill.youtube_video_id("https://example.com/watch?v=nope") == ""


def test_parse_xml_timedtext_payload():
    payload = '<transcript><text start="1.2" dur="2">Hello &amp; welcome</text><text start="4">Next line</text></transcript>'
    rows = skill.parse_youtube_caption_payload(payload)
    assert rows == [
        {"time": "0:01", "text": "Hello & welcome"},
        {"time": "0:04", "text": "Next line"},
    ]


def test_parse_json3_timedtext_payload():
    payload = {
        "events": [
            {"tStartMs": 1230, "segs": [{"utf8": "First "}, {"utf8": "line"}]},
            {"tStartMs": 3200, "segs": [{"utf8": "\n"}]},
            {"tStartMs": 4500, "segs": [{"utf8": "Second"}]},
        ]
    }
    import json

    rows = skill.parse_youtube_caption_payload(json.dumps(payload))
    assert rows == [
        {"time": "0:01", "text": "First line"},
        {"time": "0:04", "text": "Second"},
    ]


def test_save_transcript_export_writes_download_and_receipt(tmp_path: Path):
    state = tmp_path / "state"
    downloads = tmp_path / "Downloads"
    row = skill.save_youtube_transcript_export(
        url="https://www.youtube.com/watch?v=vy7o1g21HY8",
        title="How I deleted skills",
        segments=[{"time": "0:00", "text": "Intro"}, {"time": "0:03", "text": "Main point"}],
        source="test",
        state_dir=state,
        downloads_dir=downloads,
    )
    assert row["ok"] is True
    assert row["line_count"] == 2
    saved = Path(row["path"])
    assert saved.exists()
    text = saved.read_text(encoding="utf-8")
    assert "SIFTA YouTube Transcript Export" in text
    assert "[0:03] Main point" in text
    ledger = state / skill.LEDGER_NAME
    assert ledger.exists()
    assert "YOUTUBE_TRANSCRIPT_EXPORT_V1" in ledger.read_text(encoding="utf-8")


def test_empty_transcript_records_failure(tmp_path: Path):
    row = skill.save_youtube_transcript_export(
        url="https://www.youtube.com/watch?v=vy7o1g21HY8",
        title="Empty",
        source="test",
        state_dir=tmp_path / "state",
        downloads_dir=tmp_path / "Downloads",
    )
    assert row["ok"] is False
    assert row["reason"] == "empty_transcript"
