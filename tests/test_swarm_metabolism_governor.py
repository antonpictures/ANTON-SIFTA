from __future__ import annotations

from System.swarm_metabolism_governor import (
    TRUTH_LABEL,
    governed_interval_ms,
    tick_metabolism_governor,
)


def test_governed_interval_stretches_under_pressure():
    pressure = {"multiplier": 2.5, "band": "pressure_70"}
    assert governed_interval_ms(800, organ_id="what_alice_sees_poll", pressure=pressure) == 2000


def test_governed_interval_normal_when_cool():
    pressure = {"multiplier": 1.0, "band": "normal"}
    assert governed_interval_ms(900, organ_id="alice_browser_spa_snap", pressure=pressure) == 900


def test_tick_writes_governor_ledger(tmp_path):
    row = tick_metabolism_governor(state_dir=tmp_path)
    assert row.get("truth_label") == TRUTH_LABEL
    ledger = tmp_path / ".sifta_state" / "body_metabolism_governor.jsonl"
    assert ledger.exists()
    assert "governed_intervals_ms" in ledger.read_text(encoding="utf-8")