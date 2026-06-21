from __future__ import annotations

import json
import time
from pathlib import Path

from System import swarm_life_journal_consolidator as c


def _cursor_snapshot(ts: float, window: str = "M5_HERMES_STYLE_GROUNDING_TEST_PLAN_2026-05-08.md — ANTON_SIFTA") -> dict:
    return {
        "ts": ts,
        "ok": True,
        "app": "Cursor",
        "bundle_id": "com.todesktop.230313mzl4w4u92",
        "window": window,
        "browser": {},
        "writer": "swarm_active_window",
    }


def _youtube_snapshot(ts: float) -> dict:
    return {
        "ts": ts,
        "ok": True,
        "app": "Safari",
        "bundle_id": "com.apple.Safari",
        "window": "A lecture - YouTube",
        "browser": {
            "is_youtube": True,
            "youtube_video_id": "abc123",
            "title": "A lecture",
        },
        "writer": "swarm_active_window",
    }


def _grok_snapshot(ts: float) -> dict:
    return {
        "ts": ts,
        "ok": True,
        "app": "Safari",
        "bundle_id": "com.apple.Safari",
        "window": "Personal — ROBOTICS - Grok",
        "browser": {
            "is_youtube": False,
            "youtube_video_id": "",
            "title": "ROBOTICS - Grok",
            "url": "https://grok.com/project/robotics",
        },
        "writer": "swarm_active_window",
    }


def _ollama_snapshot(ts: float) -> dict:
    return {
        "ts": ts,
        "ok": True,
        "app": "Ollama",
        "bundle_id": "com.electron.ollama",
        "window": "Ollama",
        "browser": {},
        "writer": "swarm_active_window",
    }


def _bad_snapshot(ts: float) -> dict:
    return {
        "ts": ts,
        "ok": False,
        "app": "",
        "bundle_id": "",
        "window": "",
        "browser": {},
        "error": "active-window unavailable",
        "writer": "swarm_active_window",
    }


def _camera_presence(*, audience: str = "architect", stale: bool = False, faces_detected: int = 1) -> dict:
    return {
        "source": "ledger_read",
        "audience": audience,
        "faces_detected": faces_detected,
        "max_confidence": 0.83,
        "stale": stale,
        "age_s": 4.0 if not stale else 120.0,
    }


def _audio_activity(*, voice: bool = True, stale: bool = False, rms: float = 0.024) -> dict:
    return {
        "source": "life_journal_audio_lane",
        "energy": {
            "fresh": not stale,
            "source": "sounddevice",
            "real_audio": True,
            "rms_amplitude": rms,
            "age_s": 5.0 if not stale else 500.0,
        },
        "voice": {
            "fresh": bool(voice and not stale),
            "channel_cue": "nearfield_voice_likely" if voice else "",
            "nearfield_voice_likelihood": 0.78 if voice else 0.0,
            "farfield_replay_likelihood": 0.18,
            "age_s": 5.0 if not stale else 500.0,
        },
    }


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_first_person_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_classifies_cursor_focus_as_coding() -> None:
    result = c.classify_activity(_cursor_snapshot(1_778_270_000.0))

    assert result["label"] == "coding"
    assert result["confidence"] >= 0.8
    assert result["frontmost_app"] == "Cursor"
    assert result["source"] == "swarm_active_window"


def test_fresh_camera_presence_enriches_activity_grounding() -> None:
    result = c.classify_activity(
        _cursor_snapshot(1_778_270_000.0),
        camera_presence=_camera_presence(),
    )

    assert result["label"] == "coding"
    assert result["camera_presence"]["owner_present"] is True
    assert result["camera_presence"]["fresh"] is True
    assert result["confidence"] > 0.9
    assert "camera presence" in result["reason"]


def test_stale_camera_presence_does_not_claim_owner_present() -> None:
    result = c.classify_activity(
        _cursor_snapshot(1_778_270_000.0),
        camera_presence=_camera_presence(stale=True),
    )

    assert result["label"] == "coding"
    assert result["camera_presence"]["owner_present"] is False
    assert result["camera_presence"]["fresh"] is False
    assert "camera presence" not in result["reason"]


def test_fresh_audio_voice_enriches_activity_grounding() -> None:
    result = c.classify_activity(
        _cursor_snapshot(1_778_270_000.0),
        audio_activity=_audio_activity(),
    )

    assert result["label"] == "coding"
    assert result["audio_activity"]["voice_activity"] is True
    assert result["audio_activity"]["audio_active"] is True
    assert result["confidence"] > 0.9
    assert "VAD evidence" in result["reason"]


def test_stale_audio_voice_does_not_claim_voice_activity() -> None:
    result = c.classify_activity(
        _cursor_snapshot(1_778_270_000.0),
        audio_activity=_audio_activity(stale=True),
    )

    assert result["label"] == "coding"
    assert result["audio_activity"]["voice_activity"] is False
    assert result["audio_activity"]["fresh"] is False
    assert "VAD evidence" not in result["reason"]


def test_fresh_audio_voice_can_open_voice_activity_when_focus_probe_fails() -> None:
    result = c.classify_activity(
        _bad_snapshot(1_778_270_000.0),
        audio_activity=_audio_activity(),
    )

    assert result["label"] == "voice_activity"
    assert result["confidence"] >= 0.5
    assert result["audio_activity"]["voice_activity"] is True


def test_fresh_camera_presence_can_open_present_at_desk_when_focus_probe_fails() -> None:
    result = c.classify_activity(
        _bad_snapshot(1_778_270_000.0),
        camera_presence=_camera_presence(),
    )

    assert result["label"] == "present_at_desk"
    assert result["confidence"] >= 0.6
    assert result["camera_presence"]["owner_present"] is True


def test_browser_metadata_key_does_not_make_grok_video() -> None:
    result = c.classify_activity(_grok_snapshot(1_778_270_000.0))

    assert result["label"] == "researching"
    assert result["label"] != "watching_video"


def test_classifies_ollama_as_model_management() -> None:
    result = c.classify_activity(_ollama_snapshot(1_778_270_000.0))

    assert result["label"] == "model_management"
    assert result["confidence"] >= 0.8


def test_consolidator_opens_journal_and_receipt_rows(tmp_path: Path) -> None:
    now = 1_778_270_000.0
    result = c.consolidate_once(
        state_dir=tmp_path,
        now=now,
        snapshot=_cursor_snapshot(now),
        camera_presence=_camera_presence(),
        audio_activity=_audio_activity(),
    )

    assert result["action"] == "opened"
    active = c.read_active_owner_activity(state_dir=tmp_path)
    assert active is not None
    assert active["label"] == "coding"
    assert active["status"] == "open"
    assert active["camera_presence"]["owner_present"] is True
    assert active["audio_activity"]["voice_activity"] is True

    journal_files = list((tmp_path / "alice_journal").glob("*.jsonl"))
    assert len(journal_files) == 1
    journal = _rows(journal_files[0])[-1]
    assert journal["kind"] == "EPISODIC_NARRATIVE"
    assert journal["event_type"] == "owner_activity_observed"
    assert journal["local_journal_label"] == "05-08-26_12:53"
    assert journal["local_date"] == "2026-05-08"
    assert "I observed George coding" in journal["entry"]

    receipt = _rows(tmp_path / "journal_schedule_receipts.jsonl")[-1]
    assert receipt["operation"] == "OPEN_OWNER_ACTIVITY_SEGMENT"
    assert receipt["ok"] is True
    assert receipt["evidence"]["camera_presence"]["owner_present"] is True
    assert receipt["evidence"]["audio_activity"]["voice_activity"] is True

    journal_md = (tmp_path / "alice_journal" / "2026-05-08.md").read_text(encoding="utf-8")
    assert "# 2026-05-08" in journal_md
    assert "### 05-08-26_12:53" in journal_md
    assert "I observed George coding" in journal_md
    assert "camera=owner_present" in journal_md
    assert "audio=voice_activity" in journal_md
    assert "Receipt: `journal_schedule_receipts:" in journal_md


def test_consolidator_reads_audio_ledgers_without_opening_microphone(tmp_path: Path) -> None:
    now = 1_778_270_000.0
    (tmp_path / c.AUDIO_INGRESS_LOG_NAME).write_text(
        json.dumps(
            {
                "sample_id": "audio_test",
                "source": "sounddevice",
                "device_name": "MacBook Pro Microphone",
                "ts_captured": now - 5.0,
                "rms_amplitude": 0.031,
                "duration_s": 0.5,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / c.ACOUSTIC_FINGERPRINTS_LOG_NAME).write_text(
        json.dumps(
            {
                "ts": now - 5.0,
                "channel_cue": "nearfield_voice_likely",
                "fingerprint_row_id": "fp_test",
                "raw_audio_logged": False,
                "playback_fingerprint": {
                    "nearfield_voice_likelihood": 0.81,
                    "farfield_replay_likelihood": 0.14,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = c.consolidate_once(
        state_dir=tmp_path,
        now=now,
        snapshot=_cursor_snapshot(now),
        camera_presence=_camera_presence(stale=True, faces_detected=0),
    )

    assert result["action"] == "opened"
    active = c.read_active_owner_activity(state_dir=tmp_path)
    assert active is not None
    assert active["audio_activity"]["voice_activity"] is True
    assert active["audio_activity"]["rms_amplitude"] == 0.031


def test_consolidator_closes_changed_segment_and_mirrors_day_segment(tmp_path: Path) -> None:
    start = 1_778_270_000.0
    changed = start + 180.0
    c.consolidate_once(state_dir=tmp_path, now=start, snapshot=_cursor_snapshot(start))

    result = c.consolidate_once(
        state_dir=tmp_path,
        now=changed,
        snapshot=_youtube_snapshot(changed),
        min_segment_s=60.0,
    )

    assert result["action"] == "changed"
    closed = _rows(tmp_path / "owner_activity_segments.jsonl")[-1]
    assert closed["label"] == "coding"
    assert closed["status"] == "closed"
    assert closed["duration_s"] == 180.0

    mirrored = _rows(tmp_path / "architect_day_segments.jsonl")[-1]
    assert mirrored["owner_activity_truth_label"] == c.OWNER_ACTIVITY_TRUTH_LABEL
    assert mirrored["label"] == "coding"
    assert mirrored["frontmost_app"] == "Cursor"

    active = c.read_active_owner_activity(state_dir=tmp_path)
    assert active is not None
    assert active["label"] == "watching_video"

    schedule_md = (tmp_path / "owner_schedule" / "2026-05-08.md").read_text(encoding="utf-8")
    assert "George coding in Cursor" in schedule_md
    assert "Duration: 3 minutes" in schedule_md
    assert "Receipt: `journal_schedule_receipts:" in schedule_md


def test_journal_defecation_once_is_idempotent(tmp_path: Path) -> None:
    base_ts = time.time()
    journal = tmp_path / "alice_first_person_journal.jsonl"
    rows = [
        {
            "ts": base_ts - 120.0,
            "source": "alice_journal_viewer",
            "line": "browser_context_shift: samepage source=alice.com",
        },
        {
            "ts": base_ts - 90.0,
            "source": "alice_journal_viewer",
            "line": "browser_context_shift: samepage source=alice.com",
        },
        {
            "ts": base_ts - 60.0,
            "source": "alice_journal_viewer",
            "line": "browser_context_shift: samepage source=alice.com",
        },
    ]
    _write_first_person_rows(journal, rows)

    first = c.journal_defecation_once(state_dir=tmp_path, window_hours=24)
    assert first["action"] == "journal_defecation"
    assert first["consolidated_groups"] == 1
    assert first["dups_eliminated"] == 2
    assert isinstance(first.get("receipt"), dict)
    assert first["receipt"]["truth_label"] == "JOURNAL_STGM_DEFECATION"
    assert (tmp_path / "journal_defecation_receipts.jsonl").exists()
    assert len(_rows(tmp_path / "alice_journal_consolidated.jsonl")) == 1

    second = c.journal_defecation_once(state_dir=tmp_path, window_hours=24)
    assert second["action"] == "journal_defecation"
    assert second["consolidated_groups"] == 0
    assert second["suppressed_existing_groups"] == 1
    assert second["receipt"] is None
    assert len(_rows(tmp_path / "alice_journal_consolidated.jsonl")) == 1


def test_journal_defecation_once_reopens_group_when_new_row_arrives(tmp_path: Path) -> None:
    base_ts = time.time()
    journal = tmp_path / "alice_first_person_journal.jsonl"
    initial = [
        {
            "ts": base_ts - 120.0,
            "source": "alice_journal_viewer",
            "line": "browser_context_shift: samepage source=alice.com",
        },
        {
            "ts": base_ts - 90.0,
            "source": "alice_journal_viewer",
            "line": "browser_context_shift: samepage source=alice.com",
        },
    ]
    _write_first_person_rows(journal, initial)
    first = c.journal_defecation_once(state_dir=tmp_path, window_hours=24)
    assert first["consolidated_groups"] == 1

    _write_first_person_rows(
        journal,
        initial
        + [
            {
                "ts": base_ts - 30.0,
                "source": "alice_journal_viewer",
                "line": "browser_context_shift: samepage source=alice.com",
            }
        ],
    )
    second = c.journal_defecation_once(state_dir=tmp_path, window_hours=24)
    assert second["consolidated_groups"] == 1
    assert second["dups_eliminated"] == 2
    assert len(_rows(tmp_path / "alice_journal_consolidated.jsonl")) == 2
