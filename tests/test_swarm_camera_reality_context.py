import json
import time
from pathlib import Path

from System.swarm_camera_reality_context import (
    answer_camera_reality_question,
    build_camera_reality_context,
    summary_for_alice,
)


def _write_json(path: Path, row: dict) -> None:
    path.write_text(json.dumps(row), encoding="utf-8")


def _append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_camera_reality_states_single_active_eye(tmp_path):
    now = time.time()
    _write_json(
        tmp_path / "active_saccade_target.json",
        {
            "name": "USB Camera VID:1133 PID:2081",
            "index": 0,
            "writer": "swarm_sensor_attention_director",
            "ts": now,
            "lease_until": now + 5,
        },
    )
    _write_json(
        tmp_path / "sensory_attention_status.json",
        {"active_sense": "room_patrol_eye", "target_name": "USB Camera VID:1133 PID:2081"},
    )

    ctx = build_camera_reality_context(state_dir=tmp_path, now=now)

    assert ctx["truth_label"] == "CAMERA_REALITY_CONTEXT_123"
    assert ctx["simultaneous_raw_camera_feeds"] is False
    assert ctx["raw_camera_model"] == "single_active_eye_lease"
    assert ctx["active_eye"]["role"] == "room_patrol_eye"
    assert ctx["active_eye"]["lease_status"] == "fresh"


def test_camera_reality_distinguishes_parallel_ledgers_from_second_camera(tmp_path):
    now = time.time()
    _write_json(
        tmp_path / "active_saccade_target.json",
        {"name": "MacBook Pro Camera", "index": 1, "ts": now - 10, "lease_until": now - 1},
    )
    _append_jsonl(tmp_path / "face_detection_events.jsonl", {"ts": now, "faces_detected": 1})
    _append_jsonl(tmp_path / "gaze_interest_monitor.jsonl", {"ts": now, "target": "SCREEN"})

    ctx = build_camera_reality_context(state_dir=tmp_path, now=now)

    assert ctx["active_eye"]["role"] == "close_owner_eye"
    assert ctx["active_eye"]["lease_status"] == "last_known"
    assert "face_detection_events" in ctx["parallel_context_channels"]
    assert "gaze_interest_monitor" in ctx["parallel_context_channels"]
    assert ctx["simultaneous_raw_camera_feeds"] is False


def test_summary_and_answer_are_prompt_ready(tmp_path):
    now = time.time()
    _write_json(
        tmp_path / "active_saccade_target.json",
        {"name": "USB Camera VID:1133 PID:2081", "index": 0, "ts": now, "lease_until": now + 2},
    )

    summary = summary_for_alice(state_dir=tmp_path, now=now)
    answer = answer_camera_reality_question(state_dir=tmp_path, now=now)

    assert "CAMERA REALITY CONTEXT:" in summary
    assert "simultaneous_raw_camera_feeds=false" in summary
    assert "single_active_eye_lease" in summary
    assert "No." in answer
    assert "not watch two raw physical camera feeds simultaneously" in answer
