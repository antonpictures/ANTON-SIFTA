"""Tests for biology-derived drive plasticity."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import System.swarm_biology_drive_plasticity as bdp


@pytest.fixture
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "biology_drive_plasticity.json"
    monkeypatch.setattr(bdp, "STATE_PATH", p)
    return p


def test_attention_mapping() -> None:
    assert bdp.attention_to_plastic_drive("curiosity") == "curiosity"
    assert bdp.attention_to_plastic_drive("energy") == "repair"
    assert bdp.attention_to_plastic_drive("safety") == "protect"
    assert bdp.attention_to_plastic_drive("unknown_xyz") == "explore"


def test_plasticity_danger_token() -> None:
    assert bdp.plasticity_danger_token("RED_CONSERVE", {}) == "RED_CONSERVE"
    assert bdp.plasticity_danger_token("YELLOW_THROTTLE", {}) is None
    night = {"circadian": {"phase": "night"}}
    assert bdp.plasticity_danger_token("YELLOW_THROTTLE", night) == "CIRCADIAN_SLEEP_PRESSURE"


def test_update_reinforcement_positive(isolated_state: Path) -> None:
    r = bdp.update_drive_plasticity("curiosity", 1.0, danger_state=None)
    assert r["active_drive"] == "curiosity"
    assert r["drive_weights"]["curiosity"] > bdp.BASELINE_DRIVES["curiosity"]


def test_danger_biases_rest(isolated_state: Path) -> None:
    bdp._save_state(dict(bdp.BASELINE_DRIVES))
    r = bdp.update_drive_plasticity("explore", 0.0, danger_state="RED_CONSERVE")
    assert r["drive_weights"]["rest"] >= bdp.BASELINE_DRIVES["rest"]
    assert r["drive_weights"]["explore"] <= bdp.BASELINE_DRIVES["explore"]


def test_bias_drives_scales(isolated_state: Path) -> None:
    bdp._save_state(dict(bdp.BASELINE_DRIVES))
    biased = bdp.bias_drives({"curiosity": 1.0})
    assert 0.0 <= biased["curiosity"] <= 1.0


def test_corrupt_file_falls_back(isolated_state: Path) -> None:
    isolated_state.write_text("{not json", encoding="utf-8")
    st = bdp._load_state()
    assert st == bdp.BASELINE_DRIVES
