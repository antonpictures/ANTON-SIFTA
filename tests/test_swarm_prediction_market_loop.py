"""Tests for the stigmergic auto-bet loop."""
from __future__ import annotations

import json
from pathlib import Path

from System.swarm_prediction_market_loop import (
    auto_bet_cycle,
    check_results,
    format_autobet_for_alice,
    monitor_ending_soon,
    _is_short_horizon,
    _score_market,
)
from System.swarm_sifta_market import SiftaMarketEngine, OWNER_ID


def test_score_market_returns_edge_and_side():
    row = {
        "yes_price": 0.65,
        "kalshi_yes": 0.55,
        "field_yes_share": 0.7,
        "trades": 10,
        "kalshi_volume_24h": 500,
        "title": "BTC above $63,700?",
    }
    score = _score_market(row)
    assert score["side"] in ("yes", "no")
    assert 0 <= score["edge"] <= 1
    assert 0 <= score["confidence"] <= 1
    assert score["yes_price"] == 0.65
    assert score["kalshi_yes"] == 0.55


def test_is_short_horizon_detects_15min():
    assert _is_short_horizon({"title": "BTC 15 Minute target hits?"})
    assert _is_short_horizon({"timeframe": "15 Minute"})
    assert _is_short_horizon({"title": "BTC above $63,700 today 8pm EDT?"})
    assert not _is_short_horizon({"title": "World Cup winner: France?"})


def test_auto_bet_cycle_places_bets_on_high_edge(tmp_path):
    e = SiftaMarketEngine(seed=100, swarm_size=8)
    e.sync_kalshi_public = lambda **kw: {
        "ok": True,
        "imported": 3,
        "feed_fetched": 3,
        "errors": [],
        "markets": [
            {"ticker": "KXBTC-YES", "title": "BTC above $63,700 next 15 min?",
             "yes_price": 0.62, "volume_24h": 5000},
            {"ticker": "KXETH-YES", "title": "ETH above $1790 next hour?",
             "yes_price": 0.45, "volume_24h": 2000},
            {"ticker": "KXSOL-YES", "title": "SOL above $140 today?",
             "yes_price": 0.78, "volume_24h": 100},
        ],
    }
    e.sync_kalshi_public(limit=10, min_volume=1.0, replace=True)

    before = e.balances.get("autobet:stigmergic", 0.0)
    result = auto_bet_cycle(
        engine=e,
        state_dir=tmp_path,
        max_bets=3,
        min_edge=0.03,
        stake=1.0,
    )
    assert result["kind"] == "autobet_cycle"
    assert result["markets_scored"] >= 3


def test_monitor_ending_soon_returns_open_markets(tmp_path):
    e = SiftaMarketEngine(seed=101, swarm_size=8)
    monitor = monitor_ending_soon(engine=e, state_dir=tmp_path)
    assert monitor["kind"] == "ending_soon_monitor"
    assert monitor["open_markets"] >= 3
    assert len(monitor["markets"]) >= 3


def test_check_results_empty_when_no_resolutions(tmp_path):
    e = SiftaMarketEngine(seed=102, swarm_size=8)
    result = check_results(engine=e, state_dir=tmp_path, write=False)
    assert result["total_resolved"] == 0
    assert result["wins"] == 0
    assert result["losses"] == 0


def test_check_results_tracks_autobet_pnl(tmp_path):
    e = SiftaMarketEngine(seed=103, swarm_size=8)
    mid = list(e.markets.keys())[0]
    e.balances["autobet:stigmergic"] = 10.0
    e.display_names["autobet:stigmergic"] = "AutoBet"
    e.buy(mid, "yes", 2.0, agent_id="autobet:stigmergic")
    e.buy(mid, "no", 3.0, agent_id=e.swimmer_ids[0])
    e.resolve(mid, "yes")
    closed = [h for h in e.history if h.get("kind") == "closed"]
    assert len(closed) >= 1
    result = check_results(engine=e, state_dir=tmp_path, write=True)
    assert result["total_resolved"] >= 1


def test_format_autobet_for_alice_contains_sections(tmp_path):
    e = SiftaMarketEngine(seed=104, swarm_size=8)
    text = format_autobet_for_alice(engine=e, state_dir=tmp_path)
    assert "STIGMERGIC AUTOBET" in text
    assert "open markets" in text


def test_autobet_cycle_writes_receipt(tmp_path):
    e = SiftaMarketEngine(seed=105, swarm_size=8)
    auto_bet_cycle(engine=e, state_dir=tmp_path, max_bets=1, min_edge=0.01)
    ledger = tmp_path / ".sifta_state" / "autobet_receipts.jsonl"
    assert ledger.exists()
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    assert len(rows) >= 1
    assert rows[0]["kind"] == "autobet_cycle"


def test_autobet_does_not_overbuy_broke(tmp_path):
    e = SiftaMarketEngine(seed=106, swarm_size=8)
    e.balances["autobet:stigmergic"] = 0.1
    result = auto_bet_cycle(
        engine=e,
        state_dir=tmp_path,
        max_bets=5,
        min_edge=0.0,
        stake=5.0,
    )
    assert result["bets_placed"] == 0
