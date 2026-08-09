from __future__ import annotations

import json

import pytest

from System.swarm_lane_contract import audit_lane_contracts, lane_summary
from System.swarm_observer_window import observer_tick_snapshot, record_observer_tick


def test_observer_tick_stamps_time_and_monotonic_count(tmp_path):
    first = record_observer_tick("matrix", state_dir=tmp_path, now=100.0)
    second = record_observer_tick("matrix", state_dir=tmp_path, now=101.0)

    assert first["written"] is True
    assert first["tick_count"] == 1
    assert first["ts"] == 100.0
    assert second["tick_count"] == 2
    rows = [json.loads(line) for line in (tmp_path / "observer_window_ticks.jsonl").read_text().splitlines()]
    assert [row["tick_count"] for row in rows] == [1, 2]


def test_rate_limited_redraw_does_not_forge_an_extra_tick(tmp_path):
    record_observer_tick("wct", state_dir=tmp_path, now=100.0, min_interval_s=60.0)
    skipped = record_observer_tick("wct", state_dir=tmp_path, now=105.0, min_interval_s=60.0)

    assert skipped["written"] is False
    assert skipped["tick_count"] == 1
    assert observer_tick_snapshot("wct", state_dir=tmp_path) == {"tick_count": 1, "ts": 100.0}


def test_invalid_window_is_rejected():
    with pytest.raises(ValueError):
        record_observer_tick("not a valid window", state_dir=".")


def test_active_hoffman_bundle_declares_its_lane_contract():
    assert audit_lane_contracts() == []
    assert lane_summary()["trace"] >= 6
