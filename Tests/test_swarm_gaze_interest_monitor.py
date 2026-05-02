import json
import time
from pathlib import Path

from System import swarm_gaze_interest_monitor as gim


def _write_json(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_screen_interest_wins_with_youtube_logitech_and_visual_active_matter(tmp_path: Path):
    now = 1000.0
    _write_json(
        tmp_path / "active_saccade_target.json",
        {"ts": now, "name": "USB Camera VID:1133 PID:2081", "writer": "pytest"},
    )
    _write_json(
        tmp_path / "youtube_context_latest.json",
        {
            "ts": now,
            "title": "Snatch - Best of Brick top",
            "status": "pasted_page_context",
            "reality_frame": "FICTIONAL_MEDIA_CLIP",
        },
    )
    _append(
        tmp_path / "visual_active_matter.jsonl",
        {"ts": now, "field_energy": 0.32, "persistence": 0.9, "novelty": 0.2},
    )
    _append(
        tmp_path / "orienting_reflex.jsonl",
        {"ts": now, "orienting_intensity": 0.8, "orient_trigger": True},
    )

    interest = gim.compute_interest_from_evidence(gim.collect_gaze_evidence(state_dir=tmp_path, now=now))

    assert interest["target"] == gim.TARGET_SCREEN
    assert interest["screen_interest"] > interest["architect_interest"]
    assert "youtube_context_recent" in interest["reasons"]
    assert "active_eye_screen_room" in interest["reasons"]


def test_architect_interest_wins_with_fresh_face_and_close_eye(tmp_path: Path):
    now = 2000.0
    _append(
        tmp_path / "face_detection_events.jsonl",
        {"ts": now, "audience": "architect", "faces_detected": 1, "confidence": 0.82},
    )
    _write_json(
        tmp_path / "active_saccade_target.json",
        {"ts": now, "name": "MacBook Pro Camera", "writer": "pytest"},
    )

    interest = gim.compute_interest_from_evidence(gim.collect_gaze_evidence(state_dir=tmp_path, now=now))

    assert interest["target"] == gim.TARGET_ARCHITECT
    assert interest["architect_interest"] > interest["screen_interest"]
    assert "fresh_architect_face" in interest["reasons"]
    assert "active_eye_close_owner" in interest["reasons"]


def test_balanced_evidence_is_mixed_not_hardcoded_screen(tmp_path: Path):
    now = 3000.0
    _append(
        tmp_path / "face_detection_events.jsonl",
        {"ts": now, "audience": "architect", "faces_detected": 1, "confidence": 0.65},
    )
    _write_json(
        tmp_path / "youtube_context_latest.json",
        {"ts": now, "title": "Snatch - Best of Brick top", "status": "pasted_page_context"},
    )

    interest = gim.compute_interest_from_evidence(gim.collect_gaze_evidence(state_dir=tmp_path, now=now))

    assert interest["target"] == gim.TARGET_MIXED
    assert interest["architect_interest"] > 0.18
    assert interest["screen_interest"] > 0.18


def test_stale_or_missing_evidence_is_idle(tmp_path: Path):
    now = 4000.0
    _append(
        tmp_path / "face_detection_events.jsonl",
        {"ts": now - 600, "audience": "architect", "faces_detected": 1, "confidence": 0.9},
    )

    interest = gim.compute_interest_from_evidence(gim.collect_gaze_evidence(state_dir=tmp_path, now=now))

    assert interest["target"] == gim.TARGET_IDLE
    assert interest["confidence"] == 0.0


def test_write_sample_accumulates_previous_target_dwell(tmp_path: Path):
    now = 5000.0
    _write_json(
        tmp_path / "youtube_context_latest.json",
        {"ts": now, "title": "Snatch - Best of Brick top", "status": "pasted_page_context"},
    )
    first = gim.write_gaze_interest_sample(state_dir=tmp_path, now=now)
    assert first["target"] == gim.TARGET_SCREEN
    assert first["dwell_update"]["dt_s"] == 0.0

    _write_json(
        tmp_path / "youtube_context_latest.json",
        {"ts": now + 5, "title": "Snatch - Best of Brick top", "status": "pasted_page_context"},
    )
    second = gim.write_gaze_interest_sample(state_dir=tmp_path, now=now + 5)

    assert second["dwell_update"]["credited_target"] == gim.TARGET_SCREEN
    assert second["dwell_update"]["dt_s"] == 5.0
    assert second["summary"]["effective_screen_s"] == 5.0
    assert second["summary"]["screen_ratio"] == 1.0
    assert (tmp_path / "gaze_interest_monitor.jsonl").exists()
    assert (tmp_path / "gaze_interest_summary.json").exists()


def test_mixed_dwell_splits_effective_time_between_screen_and_architect(tmp_path: Path):
    first = {
        "ts": 6000.0,
        "truth_label": gim.TRUTH_LABEL,
        "target": gim.TARGET_MIXED,
    }
    _append(tmp_path / "gaze_interest_monitor.jsonl", first)
    _write_json(tmp_path / "gaze_interest_summary.json", {})
    _write_json(tmp_path / "youtube_context_latest.json", {"ts": 6005.0, "title": "Snatch"})

    row = gim.write_gaze_interest_sample(state_dir=tmp_path, now=6005.0)

    assert row["dwell_update"]["credited_target"] == gim.TARGET_MIXED
    assert row["summary"]["effective_screen_s"] == 2.5
    assert row["summary"]["effective_architect_s"] == 2.5
    assert row["summary"]["screen_ratio"] == 0.5


def test_privacy_boundary_does_not_emit_face_boxes(tmp_path: Path):
    now = time.time()
    _append(
        tmp_path / "face_detection_events.jsonl",
        {
            "ts": now,
            "audience": "architect",
            "faces_detected": 1,
            "confidence": 0.9,
            "bounding_boxes": [[0.1, 0.2, 0.3, 0.4]],
        },
    )

    row = gim.write_gaze_interest_sample(state_dir=tmp_path, now=now)

    dumped = json.dumps(row)
    assert "bounding_boxes" not in dumped
    assert "No raw frames" in row["privacy_boundary"]


def test_summary_for_alice_is_prompt_ready(tmp_path: Path):
    now = time.time()
    _write_json(tmp_path / "youtube_context_latest.json", {"ts": now, "title": "Snatch"})
    gim.write_gaze_interest_sample(state_dir=tmp_path, now=now)
    gim.write_gaze_interest_sample(state_dir=tmp_path, now=now + 4)

    line = gim.summary_for_alice(state_dir=tmp_path, max_age_s=999)

    assert line.startswith("GAZE INTEREST MONITOR:")
    assert "target=SCREEN" in line
    assert "screen=" in line


def test_run_monitor_can_be_bounded_for_daemon_smoke(tmp_path: Path):
    now = time.time()
    _write_json(tmp_path / "youtube_context_latest.json", {"ts": now, "title": "Snatch"})

    rows = gim.run_monitor(state_dir=tmp_path, iterations=2, interval_s=0.25, print_rows=False)

    assert len(rows) == 2
    assert rows[-1]["target"] == gim.TARGET_SCREEN
    assert (tmp_path / "gaze_interest_summary.json").exists()
