"""r20260714-salvage-exit-red-field — cut dead side, keep residual (STGM only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import alice_15m_scalp_learner as scalp
from System import alice_15m_scalp_strategies as strat


def test_salvage_config_thresholds() -> None:
    assert strat.SALVAGE_SIDE_IMPLIED_MAX == pytest.approx(0.30)
    assert strat.SALVAGE_MIN_SECS_LEFT == pytest.approx(90.0)
    assert strat.SALVAGE_EXIT_REASON == "salvage_exit_red_field"
    assert strat.SALVAGE_EXIT_ENABLED is True


def test_side_implied_prob() -> None:
    assert strat.side_implied_prob("yes", 0.98) == pytest.approx(0.98)
    assert strat.side_implied_prob("no", 0.98) == pytest.approx(0.02)
    assert strat.side_implied_prob("down", 0.41) == pytest.approx(0.59)


def test_salvage_fires_bnb_case() -> None:
    """BNB DOWN vs ~98% UP field, >90s left → salvage fires."""
    # yes_mid = 0.98 → DOWN (no) implied = 0.02 ≤ 0.30
    assert (
        strat.salvage_exit_should_fire(side="no", yes_mid=0.98, secs_left=500.0) is True
    )
    book = {
        "asset": "BNB",
        "yes_mid": 0.98,
        "yes_bids": [["0.97", "10"]],
        "yes_asks": [["0.99", "10"]],
        "no_bids": [["0.01", "10"]],
        "seconds_left": 500,
        "volume_24h": 5000,
        "recv_ts_ms": 100_000,
    }
    st = strat.ArmState(
        strategy_id="taker_momentum_tp",
        open_side="no",
        open_qty=1.0,
        open_entry=0.41,
        open_ts_ms=1,
    )
    intent = strat.salvage_exit_intent(book, st)
    assert intent is not None
    assert intent.action == "exit"
    assert intent.reason == "salvage_exit_red_field"
    assert intent.reduce_only is True
    # exit at no bid = 1 - yes_ask ≈ 0.01
    assert float(intent.price) <= 0.05


def test_salvage_no_fire_at_0_45() -> None:
    """Acceptance: side implied 0.45 does not salvage."""
    # no side with yes_mid=0.55 → implied no = 0.45
    assert (
        strat.salvage_exit_should_fire(side="no", yes_mid=0.55, secs_left=500.0)
        is False
    )
    book = {
        "asset": "BNB",
        "yes_mid": 0.55,
        "yes_bids": [["0.54", "10"]],
        "yes_asks": [["0.56", "10"]],
        "no_bids": [["0.44", "10"]],
        "seconds_left": 500,
        "volume_24h": 5000,
        "recv_ts_ms": 100_000,
    }
    st = strat.ArmState(
        strategy_id="t",
        open_side="no",
        open_qty=1.0,
        open_entry=0.41,
        open_ts_ms=1,
    )
    assert strat.salvage_exit_intent(book, st) is None


def test_salvage_no_fire_when_clock_too_short() -> None:
    # dead side but ≤90s left — leave to force-flat path
    assert (
        strat.salvage_exit_should_fire(side="no", yes_mid=0.98, secs_left=90.0) is False
    )
    assert (
        strat.salvage_exit_should_fire(side="no", yes_mid=0.98, secs_left=45.0) is False
    )


def test_exit_if_open_returns_salvage_before_green_hold() -> None:
    book = {
        "asset": "BNB",
        "yes_mid": 0.98,
        "yes_bids": [["0.97", "10"]],
        "yes_asks": [["0.99", "10"]],
        "no_bids": [["0.01", "10"]],
        "seconds_left": 400,
        "volume_24h": 8000,
        "recv_ts_ms": 200_000,
    }
    st = strat.ArmState(
        strategy_id="taker_momentum_tp",
        open_side="no",
        open_qty=1.0,
        open_entry=0.41,
        open_ts_ms=100_000,
    )
    intent = strat.TakerMomentumTP().decide(book, state=st, field={})
    assert intent.action == "exit"
    assert intent.reason == "salvage_exit_red_field"


def test_paper_tick_salvages_bnb_red_field(tmp_path: Path) -> None:
    """End-to-end paper path: BNB DOWN vs 98% UP gets salvage execute."""
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    ticker = "KXBNB15M-SALVAGE-TEST"
    (state / "alice_15m_open_book.json").write_text(
        json.dumps(
            {
                "open": [
                    {
                        "asset": "BNB",
                        "ticker": ticker,
                        "side": "no",
                        "label": "DOWN",
                        "price": 0.41,
                        "stake": 1.0,
                        "ts": __import__("time").time() - 60,
                        "strategy": "follow_crowd",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (state / "kalshi_15m_live.json").write_text(
        json.dumps(
            {
                "markets": [
                    {
                        "kalshi_ticker": ticker,
                        "asset": "BNB",
                        "kalshi_yes": 0.98,
                        "yes_bid": 0.97,
                        "yes_ask": 0.99,
                        "seconds_to_close": 500,
                        "kalshi_volume_24h": 5000.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (state / "alice_15m_paper_proof.json").write_text(
        json.dumps({"n_settled": 0, "n_wins": 0, "n_losses": 0, "pnl": 0.0}),
        encoding="utf-8",
    )
    (state / "alice_15m_body_stgm_budget.json").write_text(
        json.dumps(
            {
                "open_tickets": {},
                "realized_pnl_stgm": 0.0,
                "n_settled": 0,
                "n_wins": 0,
                "n_losses": 0,
            }
        ),
        encoding="utf-8",
    )
    out = scalp.tick_scalps(state_dir=state, engine=None)
    assert out["n_scalped"] >= 1
    assert out["n_open"] == 0
    log = (state / "alice_15m_scalp.jsonl").read_text(encoding="utf-8")
    assert "salvage_exit_red_field" in log
    # open book empty after salvage
    book = json.loads((state / "alice_15m_open_book.json").read_text())
    assert book["open"] == []
