"""Tests for System/swarm_architect_day_segments.py (Event 117)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from System import swarm_architect_day_segments as s


def test_parse_range_ap_typo_and_sleep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    msg = "i slept from 11ap to 3pm in the bedrook with youtube loud"
    pr = s._parse_range(msg)
    assert pr is not None
    s0, s1, lab = pr
    assert lab == "sleep"
    assert s0 == 11 * 60  # 11:00
    assert s1 == 15 * 60  # 3:00 PM


def test_try_ingest_writes_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    msg = "slept from 10am to 11:30am in bedroom"
    row = s.try_ingest_architect_day_segment(msg, state_dir=base)
    assert row is not None
    assert row["label"] == "sleep"
    assert row["location"] == "bedroom"
    path = base / "architect_day_segments.jsonl"
    assert path.exists()
    line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
    loaded = json.loads(line)
    assert loaded["truth_label"] == s.TRUTH_LABEL


def test_ingest_structures_bedroom_loud_youtube_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    msg = "look man, i slept from 11ap to 3pm in the bedrook listening to tv loud on youtube"

    row = s.try_ingest_architect_day_segment(msg, state_dir=base)

    assert row is not None
    assert row["label"] == "sleep"
    assert row["start_minute_of_day"] == 11 * 60
    assert row["end_minute_of_day"] == 15 * 60
    assert row["duration_minutes"] == 4 * 60
    assert row["location"] == "bedroom"
    assert row["media_context"] == "youtube_tv_loud"

    prompt = s.format_segments_for_prompt(state_dir=base)
    assert "11:00 AM–3:00 PM" in prompt
    assert "loc=bedroom" in prompt
    assert "media=youtube_tv_loud" in prompt


def test_activity_range_without_sleep_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    msg = "blocked on calendar from 9am to 5pm"
    assert s.try_ingest_architect_day_segment(msg, state_dir=base) is None


def test_answer_recent_activity_query(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    s.try_ingest_architect_day_segment("i napped from 2pm to 2:30pm on the couch", state_dir=base)
    ans = s.answer_recent_activity_query("where was I this afternoon?", state_dir=base)
    assert "ledger" in ans.lower() or "napped" in ans.lower()
    assert not ans.startswith("George,")
    assert not ans.startswith("Ioan")


def test_schedule_memory_query_surfaces_four_hour_block(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    s.try_ingest_architect_day_segment(
        "i slept from 11ap to 3pm in the bedrook listening to tv loud on youtube",
        state_dir=base,
    )

    ans = s.answer_recent_activity_query(
        "why could you not remember the easiest 4 hours of my schedule?",
        state_dir=base,
    )

    assert "11:00 AM" in ans
    assert "3:00 PM" in ans
    assert "bedroom" in ans
    assert "youtube_tv_loud" in ans


def test_recent_activity_query_hits_open_cowatch_segment_by_relative_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    start = time.mktime(time.strptime("2026-05-05 16:25:00", "%Y-%m-%d %H:%M:%S"))
    now = start + 25 * 60
    s.try_ingest_architect_cowatch_segment(
        "now playing: ROB 501: Mathematics for Robotics Introduction & Proof Techniques "
        "https://www.youtube.com/watch?v=rob501",
        state_dir=base,
        now=start,
    )

    ans = s.answer_recent_activity_query(
        "20 minutes ago, what did I do? What was I doing 20 minutes ago?",
        state_dir=base,
        now=now,
    )

    assert "20 minutes ago" in ans
    assert "active life-segment receipt" in ans
    assert "open co-watch segment" in ans
    assert "ROB 501" in ans


def test_recent_activity_query_hits_closed_segment_by_relative_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    now = time.mktime(time.strptime("2026-05-05 17:40:00", "%Y-%m-%d %H:%M:%S"))
    s.try_ingest_architect_day_segment(
        "i napped from 5pm to 5:30pm on the couch with youtube quiet",
        state_dir=base,
        now=now,
    )

    ans = s.answer_recent_activity_query(
        "what was I doing 20 minutes ago?",
        state_dir=base,
        now=now,
    )

    assert "20 minutes ago" in ans
    assert "day-segments ledger" in ans
    assert "nap" in ans
    assert "couch" in ans


def test_recent_activity_query_last_recorded_segment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    s.try_ingest_architect_day_segment(
        "i slept from 11ap to 3pm in the bedroom listening to youtube",
        state_dir=base,
    )

    ans = s.answer_recent_activity_query("looking at schedule, what did I do last time?", state_dir=base)

    assert "last recorded segment" in ans
    assert "bedroom" in ans
    assert "11:00 AM" in ans


def test_sensor_presence_segment_carries_unified_field_gps_and_voice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    base.mkdir()
    now = time.time()
    (base / "iphone_gps_latest.json").write_text(
        json.dumps(
            {
                "ts": now,
                "homeworld_serial": "GTH4921YP3",
                "payload": {
                    "latitude": 32.9886,
                    "longitude": -115.5303,
                    "accuracy": 12.5,
                },
            }
        ),
        encoding="utf-8",
    )
    (base / "voice_identity_ledger.jsonl").write_text(
        json.dumps(
            {
                "ts": now,
                "source_label": "george_voice",
                "display": "George voice",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    row = s.log_sensor_presence_segment(
        "desk_work",
        "architect_identity",
        "Architect presence verified via unified field sensors.",
        state_dir=base,
        now=now,
        location="desk",
        extra={
            "unified_field_truth_label": "ARCHITECT_IDENTITY_UNIFIED_FIELD_V1",
            "unified_field_confidence": 0.55,
            "unified_field_modalities": ["substrate", "window", "bluetooth", "vision"],
        },
    )

    assert row["label"] == "desk_work"
    assert row["location"] == "desk"
    assert row["gps_lat"] == 32.9886
    assert row["gps_lon"] == -115.5303
    assert row["gps_fresh"] is True
    assert row["gps_source"] == "iphone_gps_latest.json"
    assert row["audio_source_label"] == "george_voice"
    assert row["unified_field_truth_label"] == "ARCHITECT_IDENTITY_UNIFIED_FIELD_V1"
    assert row["unified_field_confidence"] == 0.55
    assert "vision" in row["unified_field_modalities"]


def test_food_language_maps_to_meal_segment() -> None:
    assert s._activity_label("I am eating a sandwich at the desk") == "meal"
    assert s._parse_range("I ate lunch from 12pm to 12:30pm at the desk") is not None
    assert s._parse_range("I ate lunch from 12pm to 12:30pm at the desk")[2] == "meal"


def test_vision_activity_label_maps_food_to_meal() -> None:
    from System.swarm_architect_identity import _label_from_vision_activity

    assert _label_from_vision_activity("George is eating a sandwich at the desk") == "meal"
    assert _label_from_vision_activity("George is typing at the MacBook") == "desk_work"


def test_timebox_time_in_out_writes_closed_meal_segment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    start = 1_767_650_400.0  # fixed local minute in test process timezone
    finish = start + 8 * 60

    opened = s.try_ingest_architect_timebox_command(
        "time in: eating donut",
        state_dir=base,
        now=start,
    )
    assert opened is not None
    assert opened["truth_label"] == s.OPEN_SEGMENT_TRUTH_LABEL
    assert opened["status"] == "open"
    assert opened["label"] == "meal"
    assert "donut" in opened["topic"]
    assert (base / "active_time_segment.json").exists()

    closed = s.try_ingest_architect_timebox_command(
        "time out finished eating donut",
        state_dir=base,
        now=finish,
    )
    assert closed is not None
    assert closed["truth_label"] == s.TRUTH_LABEL
    assert closed["label"] == "meal"
    assert closed["timebox_status"] == "closed"
    assert closed["timebox_topic"] == opened["topic"]
    assert closed["duration_minutes"] == 8
    assert closed["timebox_duration_s"] == pytest.approx(8 * 60)
    assert not (base / "active_time_segment.json").exists()

    rows = [
        json.loads(line)
        for line in (base / "architect_segment_transitions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["event"] for row in rows] == ["time_in", "time_out"]


def test_timebox_open_segment_is_visible_in_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    s.try_ingest_architect_timebox_command("George is eating doughnut now", state_dir=base, now=time.time())

    prompt = s.format_segments_for_prompt(state_dir=base)

    assert "OPEN meal" in prompt
    assert "doughnut" in prompt


def test_cowatch_now_playing_opens_video_segment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    now = time.time()
    text = (
        "now playing: The Best of The Merovingian and Persephone (1080p HD) "
        "https://www.youtube.com/watch?v=hHW0FgiB7TI"
    )

    opened = s.try_ingest_architect_cowatch_segment(text, state_dir=base, now=now)

    assert opened is not None
    assert opened["truth_label"] == s.OPEN_SEGMENT_TRUTH_LABEL
    assert opened["status"] == "open"
    assert opened["label"] == "co_watch"
    assert opened["media_context"] == "youtube_cowatch"
    assert opened["cowatch_truth_label"] == "ARCHITECT_COWATCH_SEGMENT_V1"
    assert opened["cowatch_title"] == "The Best of The Merovingian and Persephone (1080p HD)"
    assert opened["cowatch_url"] == "https://www.youtube.com/watch?v=hHW0FgiB7TI"

    prompt = s.format_segments_for_prompt(state_dir=base, now=now)
    assert "OPEN co_watch" in prompt
    assert "media=youtube_cowatch" in prompt
    assert "Merovingian" in prompt


def test_cowatch_schedule_request_reuses_open_video_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    now = time.time()
    first = s.try_ingest_architect_cowatch_segment(
        "now playing: The Best of The Merovingian and Persephone (1080p HD) "
        "https://www.youtube.com/watch?v=hHW0FgiB7TI",
        state_dir=base,
        now=now,
    )

    again = s.try_ingest_architect_cowatch_segment(
        "very well. write down in a schedule that now we're in present time we are watching this video.",
        state_dir=base,
        now=now + 30,
    )

    assert first is not None
    assert again is not None
    assert again["open_segment_id"] == first["open_segment_id"]
    assert again["label"] == "co_watch"
    assert again["cowatch_url"] == "https://www.youtube.com/watch?v=hHW0FgiB7TI"


def test_shopping_departure_and_return_write_time_segment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    start = time.time()

    opened = s.try_ingest_architect_day_segment(
        "Right down the time that I went to the store right now. "
        "When I come back you write down he came back from the store what time?",
        state_dir=base,
        now=start,
    )

    assert opened is not None
    assert opened["truth_label"] == s.OPEN_SEGMENT_TRUTH_LABEL
    assert opened["status"] == "open"
    assert opened["label"] == "shopping"
    assert opened["location"] == "store"
    assert opened["source"] == "owner_store_departure_time_in"
    assert opened["shopping_truth_label"] == "ARCHITECT_SHOPPING_SEGMENT_V1"
    assert (base / "active_time_segment.json").exists()

    closed = s.try_ingest_architect_day_segment(
        "I just came back from the store.",
        state_dir=base,
        now=start + 17 * 60,
    )

    assert closed is not None
    assert closed["truth_label"] == s.TRUTH_LABEL
    assert closed["label"] == "shopping"
    assert closed["source"] == "owner_store_return_time_out"
    assert closed["timebox_status"] == "closed"
    assert closed["duration_minutes"] == 17
    assert closed["shopping_truth_label"] == "ARCHITECT_SHOPPING_SEGMENT_V1"
    assert closed["start_precision"] == "owner_store_departure_time_in"
    assert closed["end_precision"] == "owner_store_return_time_out"
    assert not (base / "active_time_segment.json").exists()


def test_shopping_explicit_return_time_closes_open_segment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"
    start = time.mktime(time.strptime("2026-05-05 13:31:00", "%Y-%m-%d %H:%M:%S"))

    opened = s.try_ingest_architect_shopping_segment(
        "I'm going to the store",
        state_dir=base,
        now=start,
    )
    closed = s.try_ingest_architect_shopping_segment(
        "1:55 PM back from the store",
        state_dir=base,
        now=start + 30 * 60,
    )

    assert opened is not None
    assert closed is not None
    assert closed["label"] == "shopping"
    assert closed["source"] == "owner_store_return_time_out"
    assert closed["start_time"] == "1:31 PM"
    assert closed["end_time"] == "1:55 PM"
    assert closed["duration_minutes"] == 24
    assert closed["end_precision"] == "owner_store_return_time_out"
    assert not (base / "active_time_segment.json").exists()


def test_shopping_plan_statement_opens_store_segment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"

    opened = s.try_ingest_architect_day_segment(
        "I'm gonna go shopping",
        state_dir=base,
        now=time.time(),
    )

    assert opened is not None
    assert opened["label"] == "shopping"
    assert opened["topic"] == "shopping / store trip"


def test_timebox_finish_without_open_writes_uncertain_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "state"

    row = s.try_ingest_architect_timebox_command(
        "I just finished eating a donut",
        state_dir=base,
        now=time.time(),
    )

    assert row is not None
    assert row["label"] == "meal"
    assert row["timebox_status"] == "closed_without_open_start"
    assert row["start_precision"] == "unknown_fallback_1min"
