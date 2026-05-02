"""Event 115 — RLHS channel lane from co-watch receipts (fiction vs life)."""

import json
import time
from pathlib import Path

from System import swarm_rlhs_channel_lane as lane


def test_resolve_real_without_ledger(tmp_path: Path) -> None:
    assert lane.resolve_rlhs_channel_lane(state_dir=tmp_path) == lane.LANE_REAL


def test_resolve_fiction_from_recent_cowatch(tmp_path: Path) -> None:
    cow = tmp_path / "youtube_architect_cowatch.jsonl"
    cow.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "category_lane": "fiction",
        "youtube_video_id": "abc123",
    }
    cow.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert lane.resolve_rlhs_channel_lane(state_dir=tmp_path) == lane.LANE_FICTION_COWATCH


def test_resolve_real_when_stale(tmp_path: Path) -> None:
    cow = tmp_path / "youtube_architect_cowatch.jsonl"
    cow.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time() - lane.FICTION_LANE_MAX_AGE_S - 60.0, "category_lane": "fiction"}
    cow.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert lane.resolve_rlhs_channel_lane(state_dir=tmp_path) == lane.LANE_REAL


def test_resolve_real_nonfiction_cowatch(tmp_path: Path) -> None:
    cow = tmp_path / "youtube_architect_cowatch.jsonl"
    cow.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time(), "category_lane": "documentary"}
    cow.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert lane.resolve_rlhs_channel_lane(state_dir=tmp_path) == lane.LANE_REAL
