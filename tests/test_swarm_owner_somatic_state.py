"""Basic tests for the Owner Somatic State organ (delta=0 for initial landing)."""

import json
import tempfile
from pathlib import Path

import pytest

from System import swarm_owner_somatic_state as somatic


def test_update_from_frame_basic():
    frame = {
        "faces_detected": 1,
        "confidence": 0.82,
        "movement": "steady",
        "posture_hint": "relaxed",
    }
    result = somatic.update_from_frame(frame, camera_id="builtin")
    assert result["ok"] is True
    row = result["row"]
    assert row["source"] == "camera_v2"
    assert row["energy_level"] in ("high", "medium", "low")


def test_update_from_voice():
    vad = {"is_speaking": True, "energy": 0.75, "stt_conf": 0.9}
    result = somatic.update_from_voice(vad)
    assert result["ok"]
    assert result["row"]["energy_level"] == "high"


def test_update_from_conversation_fatigue():
    result = somatic.update_from_conversation("man I'm so tired after that workout")
    assert result["row"]["energy_level"] == "low"
    assert result["row"]["posture"] == "fatigued"


def test_latest_somatic_block(tmp_path):
    # Seed a row
    ledger = tmp_path / "owner_somatic_state.jsonl"
    row = {
        "ts": 9999999999,
        "source": "camera_v2",
        "posture": "tense",
        "movement_quality": "jerky",
        "energy_level": "high",
    }
    ledger.write_text(json.dumps(row) + "\n")

    block = somatic.latest_somatic_block(state_dir=str(tmp_path), max_age_s=999999)
    assert "posture=tense" in block
    assert "energy=high" in block


def test_malformed_row_ignored(tmp_path):
    ledger = tmp_path / "owner_somatic_state.jsonl"
    ledger.write_text("this is not json\n")
    block = somatic.latest_somatic_block(state_dir=str(tmp_path), max_age_s=10)
    assert "no fresh data" in block or "ledger read error" in block
