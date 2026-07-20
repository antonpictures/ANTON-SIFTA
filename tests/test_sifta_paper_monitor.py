"""Single-writer/failover contract for the overnight paper monitor."""
from __future__ import annotations

import json
from pathlib import Path

from System.swarm_sifta_paper_monitor import (
    acquire_monitor_lock,
    app_loop_claims_on,
    latest_app_heartbeat_ts,
    should_yield_to_app,
)
from System import swarm_sifta_paper_loop as paper_loop


def test_monitor_process_lock_allows_only_one_instance(tmp_path) -> None:
    state = tmp_path / ".sifta_state"
    first = acquire_monitor_lock(state_dir=state)
    assert first is not None
    second = acquire_monitor_lock(state_dir=state)
    assert second is None
    first.close()
    third = acquire_monitor_lock(state_dir=state)
    assert third is not None
    third.close()


def test_scalp_lab_tournament_is_throttled_off_control_hot_path() -> None:
    previous = paper_loop._LAST_SCALP_LAB_TOURNAMENT_TS
    try:
        paper_loop._LAST_SCALP_LAB_TOURNAMENT_TS = 0.0
        assert paper_loop._scalp_lab_tournament_due(now=100.0) is True
        assert paper_loop._scalp_lab_tournament_due(now=159.9) is False
        assert paper_loop._scalp_lab_tournament_due(now=160.0) is True
    finally:
        paper_loop._LAST_SCALP_LAB_TOURNAMENT_TS = previous


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_yields_when_qt_loop_is_on_and_fresh(tmp_path) -> None:
    state = tmp_path / ".sifta_state"
    _append(state / "sifta_market_app_receipts.jsonl", {"event": "paper_loop_on", "ts": 90.0})
    _append(state / "sifta_market_app_receipts.jsonl", {"event": "paper_loop_heartbeat", "ts": 100.0})
    _append(state / "sifta_market_receipts.jsonl", {"event": "paper_bet_15m", "ts": 100.0})

    assert app_loop_claims_on(state_dir=state) is True
    assert latest_app_heartbeat_ts(state_dir=state) == 100.0
    assert should_yield_to_app(state_dir=state, now=120.0, fresh_s=45.0) is True


def test_takes_over_when_qt_loop_activity_is_stale(tmp_path) -> None:
    state = tmp_path / ".sifta_state"
    _append(state / "sifta_market_app_receipts.jsonl", {"event": "paper_loop_on", "ts": 10.0})
    _append(state / "sifta_market_app_receipts.jsonl", {"event": "paper_loop_heartbeat", "ts": 20.0})
    _append(state / "sifta_market_receipts.jsonl", {"event": "paper_settle", "ts": 20.0})

    assert should_yield_to_app(state_dir=state, now=100.0, fresh_s=45.0) is False


def test_close_or_explicit_off_forces_headless_takeover(tmp_path) -> None:
    state = tmp_path / ".sifta_state"
    app = state / "sifta_market_app_receipts.jsonl"
    market = state / "sifta_market_receipts.jsonl"
    _append(app, {"event": "paper_loop_on", "ts": 90.0})
    _append(app, {"event": "paper_loop_heartbeat", "ts": 100.0})
    _append(app, {"event": "paper_loop_off", "ts": 95.0})
    _append(market, {"event": "paper_bet_15m", "ts": 100.0})
    assert should_yield_to_app(state_dir=state, now=110.0) is False

    _append(app, {"event": "paper_loop_on", "ts": 111.0})
    _append(app, {"event": "close", "ts": 112.0})
    assert should_yield_to_app(state_dir=state, now=115.0) is False


def test_malformed_rows_do_not_break_failover(tmp_path) -> None:
    state = tmp_path / ".sifta_state"
    app = state / "sifta_market_app_receipts.jsonl"
    market = state / "sifta_market_receipts.jsonl"
    app.parent.mkdir(parents=True)
    app.write_text("not-json\n" + json.dumps({"event": "paper_loop_on"}) + "\n")
    market.write_text("{bad\n")

    assert app_loop_claims_on(state_dir=state) is True
    assert latest_app_heartbeat_ts(state_dir=state) is None
    assert should_yield_to_app(state_dir=state, now=100.0) is False
