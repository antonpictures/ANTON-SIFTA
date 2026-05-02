"""Tests for System/swarm_architect_day_segments.py (Event 117)."""
from __future__ import annotations

import json
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
