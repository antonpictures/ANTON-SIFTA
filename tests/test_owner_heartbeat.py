from __future__ import annotations

import importlib
import json
from pathlib import Path


def _fresh_owner_heartbeat(tmp_path: Path, monkeypatch):
    import System.owner_heartbeat as owner_heartbeat

    hb = importlib.reload(owner_heartbeat)
    monkeypatch.setattr(hb, "_LEDGER", tmp_path / "owner_heartbeat.jsonl")
    hb._current_last_activity_ts = 0.0
    hb._current_last_activity_source = "test"
    hb._current_mode = "ACTIVE"
    return hb


def test_mark_owner_activity_records_true_previous_gap(tmp_path, monkeypatch):
    hb = _fresh_owner_heartbeat(tmp_path, monkeypatch)
    monkeypatch.setattr(hb, "_now", lambda: 1000.0)
    hb._current_last_activity_ts = 990.0
    hb._current_mode = "IDLE"

    snap = hb.mark_owner_activity("unit")

    assert snap.mode == "ACTIVE"
    rows = (tmp_path / "owner_heartbeat.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(rows[-1])
    assert row["type"] == "OWNER_HEARTBEAT_STATE_TRANSITION"
    assert row["seconds_since_previous"] == 10.0
    assert row["policy"] == "owner_heartbeat_gates_timers"


def test_owner_heartbeat_messaging_poll_gate_defaults_off_when_active(tmp_path, monkeypatch):
    hb = _fresh_owner_heartbeat(tmp_path, monkeypatch)
    monkeypatch.setattr(hb, "_now", lambda: 1000.0)
    hb._current_last_activity_ts = 999.0

    assert hb.get_owner_mode() == "ACTIVE"
    assert hb.should_poll_messaging() is False
    assert hb.should_poll_messaging(channel_focused=True) is True
    assert hb.should_poll_messaging(explicitly_enabled=True) is True

