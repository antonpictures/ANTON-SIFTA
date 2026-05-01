"""Tests for cochlea → body_brain_memory bridge."""
from __future__ import annotations

import json
from pathlib import Path

from System import swarm_stigmergic_cochlea_integrator as integ


def _write_cochlea(tmp: Path, row: dict) -> Path:
    p = tmp / "stigmergic_cochlea.jsonl"
    p.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return p


def test_integrate_biases_td_and_danger_from_cochlea_row(tmp_path: Path) -> None:
    ledger = _write_cochlea(
        tmp_path,
        {
            "tick_id": "c1",
            "ts": 123.45,
            "acoustic_stress": 0.9,
            "td_bias": 0.5,
            "danger_hint": "ACOUSTIC_STRESS_HIGH",
        },
    )
    mem = {
        "event": "body_brain_tick",
        "tick_id": "bb1",
        "td_value": 0.2,
        "danger_state": 0.1,
        "action": {"type": "explore", "target": "x"},
        "result": {"status": "completed", "latency": 0.1, "energy_used": 0.05},
    }
    out = integ.integrate_acoustic_features(
        mem,
        cochlea_ledger=ledger,
        state_root=tmp_path,
    )
    assert out["tick_source"] == "cochlea_integrator"
    assert out["truth_label"] == integ.TRUTH_OVERLAY
    assert out["cochlea_tick_id"] == "c1"
    assert out["acoustic_stress"] == 0.9
    # td: 0.2 + 0.5 * 0.6 = 0.5
    assert abs(out["td_value"] - 0.5) < 1e-5
    # danger: max(0.1, 0.9 * 0.8) = 0.72
    assert abs(out["danger_state"] - 0.72) < 1e-5


def test_append_produces_parseable_body_brain_tick(tmp_path: Path) -> None:
    ledger = _write_cochlea(
        tmp_path,
        {"tick_id": "c2", "ts": 1.0, "acoustic_stress": 0.2, "td_bias": 0.0, "danger_hint": "ACOUSTIC_QUIET"},
    )
    mem_path = tmp_path / "body_brain_memory.jsonl"
    row = integ.integrate_acoustic_features(
        {
            "event": "body_brain_tick",
            "tick_id": "bb2",
            "td_value": 1.0,
            "danger_state": 0.0,
            "action": {"type": "rest", "reason": "test"},
            "result": {"status": "completed", "latency": 0.0, "energy_used": 0.0},
        },
        cochlea_ledger=ledger,
        state_root=tmp_path,
    )
    integ.append_integrated_tick(row, memory_path=mem_path, state_root=tmp_path)
    line = mem_path.read_text(encoding="utf-8").strip()
    loaded = json.loads(line)
    assert loaded["event"] == "body_brain_tick"
    assert isinstance(loaded["action"], dict)
    assert isinstance(loaded["result"], dict)


def test_defaults_when_cochlea_missing(tmp_path: Path) -> None:
    missing = tmp_path / "stigmergic_cochlea.jsonl"
    out = integ.integrate_acoustic_features(
        {"event": "body_brain_tick", "td_value": 0.0, "danger_state": 0.0, "action": {}, "result": {}},
        cochlea_ledger=missing,
        state_root=tmp_path,
    )
    assert "acoustic_stress" in out
    assert out["event"] == "body_brain_tick"
