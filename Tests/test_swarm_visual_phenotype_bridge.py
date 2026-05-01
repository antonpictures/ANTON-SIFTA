"""Tests for ledger-backed visual phenotype uniforms bridge."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import System.swarm_body_brain_loop as bbl
import System.swarm_visual_phenotype_bridge as vpb


@pytest.fixture
def iso_state(tmp_path: Path):
    with patch.object(bbl, "_STATE_DIR", tmp_path):
        yield tmp_path


def test_build_uniforms_from_body_row(iso_state: Path) -> None:
    row = {
        "event": "body_brain_tick",
        "action": {"type": "forage", "target": "pouw_work"},
        "result": {"status": "completed", "latency": 0.25},
        "td_value": -1.0,
        "drive_state": "energy",
        "metabolic_mode": "YELLOW_THROTTLE",
        "plasticity_danger": "",
        "confidence": 0.8,
    }
    u = vpb.build_visual_phenotype_uniforms(row)
    assert u["receipt_backed"] is True
    assert 0.0 <= u["u_stigmergic_drive"] <= 1.0
    assert u["u_heading"] == 0.0
    assert u["u_cost"] == 0.55
    assert u["u_quorum_signal"] == 0.8
    assert u["u_chemotaxis_gradient"] == 0.1


def test_chemotaxis_from_trace_gradient(iso_state: Path) -> None:
    row = {
        "event": "body_brain_tick",
        "action": {"type": "explore"},
        "result": {},
        "td_value": 0.0,
        "drive_state": "curiosity",
        "metabolic_mode": "GREEN_GROW",
        "trace_gradient": 2.0,
    }
    u = vpb.build_visual_phenotype_uniforms(row)
    assert u["u_chemotaxis_gradient"] == 1.0

    row["trace_gradient"] = 0.0
    u = vpb.build_visual_phenotype_uniforms(row)
    assert u["u_chemotaxis_gradient"] == 0.0


def test_write_appends_jsonl(iso_state: Path) -> None:
    mem = iso_state / "body_brain_memory.jsonl"
    mem.write_text(
        json.dumps(
            {
                "event": "body_brain_tick",
                "action": {"type": "rest"},
                "result": {"latency": 1.0},
                "td_value": 1.0,
                "drive_state": "rest",
                "metabolic_mode": "RED_CONSERVE",
                "plasticity_danger": "CIRCADIAN_SLEEP_PRESSURE",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    vpb.write_visual_phenotype_uniforms()
    led = iso_state / "visual_phenotype_uniforms.jsonl"
    assert led.exists()
    line = led.read_text(encoding="utf-8").strip().splitlines()[-1]
    out = json.loads(line)
    assert out["u_cost"] == 0.85
