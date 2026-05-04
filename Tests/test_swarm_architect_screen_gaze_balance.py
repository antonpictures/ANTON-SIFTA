"""Event 114 — Architect vs screen gaze balance ledger."""

import json
from pathlib import Path

from System import swarm_architect_screen_gaze_balance as gb


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows),
        encoding="utf-8",
    )


def test_compute_gaze_balance_fuses_face_and_youtube(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "face_detection_events.jsonl",
        [
            {
                "ts": 1_000_000.0,
                "audience": "architect",
                "confidence": 0.9,
                "faces_detected": 1,
            }
        ],
    )
    _write_jsonl(
        tmp_path / "app_focus.jsonl",
        [
            {
                "ts": 1_000_001.0,
                "app": "Safari",
                "detail": "watching this youtube video",
                "tab": "YouTube",
            }
        ],
    )
    _write_jsonl(
        tmp_path / "stigmergic_video_resolution.jsonl",
        [{"ts": 1_000_002.0, "active_cells": 120, "salience_density": 0.0, "grid_cells": 484}],
    )
    _write_jsonl(
        tmp_path / "hippocampal_novelty_map.jsonl",
        [{"ts": 1_000_003.0, "novelty_score": 0.8, "phase": "NOVEL"}],
    )
    _write_jsonl(
        tmp_path / "orienting_reflex.jsonl",
        [{"ts": 1_000_004.0, "orienting_intensity": 0.7}],
    )
    row = gb.compute_gaze_balance(state_dir=tmp_path, now=1_000_010.0)
    assert row["truth_label"] == gb.TRUTH
    assert 0.0 <= row["p_architect_proxy"] <= 1.0
    assert 0.0 <= row["p_screen_proxy"] <= 1.0
    assert row["drivers"]["face_audience"] == "architect"
    assert row["drivers"]["youtube_context_hint"] is True


def test_write_gaze_balance_updates_ema(tmp_path: Path) -> None:
    _write_jsonl(
        tmp_path / "face_detection_events.jsonl",
        [{"ts": 2_000_000.0, "audience": "architect", "confidence": 0.99, "faces_detected": 1}],
    )
    _write_jsonl(tmp_path / "app_focus.jsonl", [{"ts": 2_000_001.0, "app": "Xcode", "detail": "code"}])
    _write_jsonl(tmp_path / "stigmergic_video_resolution.jsonl", [{"ts": 2_000_002.0, "active_cells": 0, "grid_cells": 100}])
    _write_jsonl(tmp_path / "hippocampal_novelty_map.jsonl", [{"ts": 2_000_003.0, "novelty_score": 0.1, "phase": "FAMILIAR"}])
    _write_jsonl(tmp_path / "orienting_reflex.jsonl", [{"ts": 2_000_004.0, "orienting_intensity": 0.0}])
    a = gb.write_gaze_balance_sample(state_dir=tmp_path)
    b = gb.write_gaze_balance_sample(state_dir=tmp_path)
    assert "ema_architect_share" in a
    assert "ema_architect_share" in b
    assert isinstance(b["ema_architect_share"], float)
