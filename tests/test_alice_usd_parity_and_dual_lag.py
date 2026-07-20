"""r20260714 — US$ parity gates + dual-lag harness (STGM import, no live $)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from System import alice_15m_scalp_strategies as strat
from System import alice_usd_dual_lag_harness as lag
from System import alice_usd_must_scalp as must
from System import alice_usd_take_profit as tp


def _state(tmp: Path) -> Path:
    s = tmp / ".sifta_state"
    s.mkdir(parents=True, exist_ok=True)
    return s


def test_usd_imports_stgm_copy_and_bounded_exit_symbols() -> None:
    """r1723 copies STGM opens; r1725 gives force-flat precedence."""
    import inspect

    src_must = inspect.getsource(must.tick_must_scalp)
    assert "load_open_book" in src_must
    assert "stgm_copy_only_no_paper" in src_must
    assert "stgm_exact_copy" in src_must
    src_tp = inspect.getsource(tp.tick_take_profits)
    assert "NEVER_SELL_FOR_LOSS" in src_tp or "never_sell_for_loss" in src_tp
    assert "take_profit_exit_policy" in src_tp
    assert "salvage_exit_should_fire" not in src_tp
    assert "soft_adverse_should_fire" not in src_tp


def test_soft_adverse_shared_config() -> None:
    assert strat.SOFT_ADVERSE_SIDE_IMPLIED_MAX == pytest.approx(0.42)
    assert strat.SOFT_ADVERSE_MAX_LOSS_PER_CONTRACT == pytest.approx(0.15)
    # side_imp 0.40, 150s left, bid within 15¢ of entry
    assert (
        strat.soft_adverse_should_fire(
            side="no",
            yes_mid=0.60,  # no imp = 0.40
            secs_left=150.0,
            entry=0.50,
            exit_bid=0.40,
        )
        is True
    )
    # too early in window
    assert (
        strat.soft_adverse_should_fire(
            side="no", yes_mid=0.60, secs_left=400.0, entry=0.50, exit_bid=0.40
        )
        is False
    )


def test_must_scalp_copies_exact_stgm_asset_side_and_ticker(tmp_path: Path) -> None:
    """r1723 forwards the canonical paper trail without freelance selection."""
    state = _state(tmp_path)
    # lane+hand on so tick runs selection
    (state / "kalshi_usd_lane.json").write_text(
        json.dumps({"armed": True, "env": "prod"}), encoding="utf-8"
    )
    (state / "kalshi_usd_hand_session.json").write_text(
        json.dumps({"live": True, "caps": {"max_open": 1}}), encoding="utf-8"
    )
    (state / "kalshi_usd_night.json").write_text(
        json.dumps(
            {
                "open": [],
                "n_placed": 0,
                "halted": False,
                "realized_pnl_usd": 0.0,
                "day": "2026-07-14",
            }
        ),
        encoding="utf-8",
    )
    (state / "kalshi_15m_live.json").write_text(
        json.dumps(
            {
                "markets": [
                    {
                        "kalshi_ticker": "KXBNB15M-PARITY",
                        "asset": "BNB",
                        "kalshi_yes": 0.98,
                        "yes_bid": 0.97,
                        "yes_ask": 0.99,
                        "seconds_to_close": 600,
                        "kalshi_volume_24h": 8000.0,
                    },
                    {
                        "kalshi_ticker": "KXBTC15M-PARITY",
                        "asset": "BTC",
                        "kalshi_yes": 0.97,
                        "yes_bid": 0.96,
                        "yes_ask": 0.98,
                        "seconds_to_close": 600,
                        "kalshi_volume_24h": 100_000.0,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (state / "alice_15m_open_book.json").write_text(
        json.dumps(
            {
                "open": [
                    {
                        "asset": "BNB",
                        "ticker": "KXBNB15M-PARITY",
                        "label": "DOWN",
                        "side": "no",
                        "price": 0.42,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    mirror = mock.Mock(
        return_value={
            "event": "usd_place",
            "filled": True,
            "fill_count": 1.0,
            "order_id": "r1723-test-order",
        }
    )
    with mock.patch("System.kalshi_usd_hand.maybe_mirror_paper_bet", mirror):
        out = must.tick_must_scalp(state_dir=state, dry_run=True)

    assert out.get("placed") is True
    assert out.get("deal") == "r1723-stgm-copy-only"
    copied = mirror.call_args.args[0]
    assert copied["ticker"] == "KXBNB15M-PARITY"
    assert copied["asset"] == "BNB"
    assert copied["side"] == "no"
    assert copied["entry_price"] == pytest.approx(0.42)
    assert copied["stgm_exact_copy"] is True


def test_must_scalp_empty_stgm_never_calls_cash_mirror(tmp_path: Path) -> None:
    """An empty pheromone trail must be a hard sit, never a cash hunt."""
    state = _state(tmp_path)
    (state / "kalshi_usd_lane.json").write_text(
        json.dumps({"armed": True, "env": "prod"}), encoding="utf-8"
    )
    (state / "kalshi_usd_hand_session.json").write_text(
        json.dumps({"live": True}), encoding="utf-8"
    )
    (state / "kalshi_usd_night.json").write_text(
        json.dumps({"open": [], "halted": False}), encoding="utf-8"
    )
    (state / "kalshi_15m_live.json").write_text(
        json.dumps(
            {
                "markets": [
                    {
                        "kalshi_ticker": "KXBTC15M-EMPTY",
                        "asset": "BTC",
                        "kalshi_yes": 0.55,
                        "seconds_to_close": 600,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (state / "alice_15m_open_book.json").write_text(
        json.dumps({"open": []}), encoding="utf-8"
    )
    mirror = mock.Mock()
    with mock.patch("System.kalshi_usd_hand.maybe_mirror_paper_bet", mirror):
        out = must.tick_must_scalp(state_dir=state, dry_run=True)

    assert out["placed"] is False
    assert out["reason"] == "stgm_copy_only_no_paper"
    mirror.assert_not_called()


def test_evaluate_take_profit_path_flags_salvage() -> None:
    """Salvage should_fire on DOWN vs 98% UP with 500s left."""
    assert (
        strat.salvage_exit_should_fire(side="no", yes_mid=0.98, secs_left=500.0)
        is True
    )


def test_force_flat_holds_favorite_btc_no_falling() -> None:
    """r1716 helper still marks favorites (r1717 blocks all red sells anyway)."""
    from System.alice_usd_take_profit import force_flat_should_hold_favorite

    assert force_flat_should_hold_favorite(side="no", yes_mid=0.27) is True
    assert force_flat_should_hold_favorite(side="no", yes_mid=0.33) is True
    assert force_flat_should_hold_favorite(side="no", yes_mid=0.60) is False


def test_never_sell_for_loss_r1717() -> None:
    """Owner: do not sell for a loss — red mark is never a green TP."""
    from System.alice_usd_take_profit import evaluate_take_profit, is_fee_true_green

    # entry NO 0.81, YES mid 0.33 → NO exit ~0.66 — red vs 81¢
    open_row = {
        "side": "no",
        "price": 0.81,
        "fee_paid_usd": 0.01,
        "fill_count": 1.0,
    }
    mark = {"yes": 0.33, "yes_bid": 0.32, "yes_ask": 0.34}
    ev = evaluate_take_profit(open_row, mark, min_edge=0.0)
    assert float(ev["net_usd"]) < 0
    assert ev["take_profit"] is False
    assert is_fee_true_green(ev, min_edge=0.0) is False

    # green: entry cheap NO 0.40, YES 0.20 → NO ~0.79
    open_green = {
        "side": "no",
        "price": 0.40,
        "fee_paid_usd": 0.01,
        "fill_count": 1.0,
    }
    mark_g = {"yes": 0.20, "yes_bid": 0.19, "yes_ask": 0.21}
    ev_g = evaluate_take_profit(open_green, mark_g, min_edge=0.0)
    assert float(ev_g["net_usd"]) > 0
    assert is_fee_true_green(ev_g, min_edge=0.0) is True


def test_force_flat_precedes_never_sell_for_loss_r1725() -> None:
    """A red scalp may wait before the gate, but cannot ride through expiry."""
    ev = {"net_usd": -1.20, "take_profit": False}

    waiting = tp.take_profit_exit_policy(ev, danger_flat=False, min_edge=0.0)
    assert waiting == {
        "exit": False,
        "force_flat": False,
        "reason": tp.NEVER_SELL_FOR_LOSS_REASON,
    }

    flattening = tp.take_profit_exit_policy(ev, danger_flat=True, min_edge=0.0)
    assert flattening == {
        "exit": True,
        "force_flat": True,
        "reason": tp.FORCE_FLAT_EXIT_REASON,
    }

    green = tp.take_profit_exit_policy(
        {"net_usd": 0.05, "take_profit": True},
        danger_flat=True,
        min_edge=0.0,
    )
    assert green == {
        "exit": True,
        "force_flat": False,
        "reason": "take_profits_on_green",
    }


def test_dual_lag_stamp_and_shadow_suite(tmp_path: Path) -> None:
    state = _state(tmp_path)
    (state / "kalshi_15m_live.json").write_text(
        json.dumps(
            {
                "markets": [
                    {
                        "asset": "BTC",
                        "kalshi_ticker": "KXBTC15M-T",
                        "kalshi_yes": 0.55,
                        "yes_bid": 0.54,
                        "yes_ask": 0.56,
                        "seconds_to_close": 500,
                        "kalshi_volume_24h": 9000,
                    },
                    {
                        "asset": "ETH",
                        "kalshi_ticker": "KXETH15M-T",
                        "kalshi_yes": 0.52,
                        "yes_bid": 0.51,
                        "yes_ask": 0.53,
                        "seconds_to_close": 500,
                        "kalshi_volume_24h": 5000,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    bet = {
        "asset": "BTC",
        "ticker": "KXBTC15M-T",
        "side": "yes",
        "entry_price": 0.55,
    }
    d = lag.stamp_decision(
        phase="test",
        bet=bet,
        mark={"yes": 0.55, "yes_bid": 0.54, "yes_ask": 0.56},
        secs_left=500,
        dry_run=True,
        state_dir=state,
    )
    assert d["decision_ts_ms"] > 0
    s = lag.stamp_submit_result(
        phase="test",
        bet=bet,
        result={"event": "shadow", "filled": False, "reason": "test"},
        decision_ts_ms=d["decision_ts_ms"],
        dry_run=True,
        state_dir=state,
    )
    assert "rtt_ms" in s
    rep = lag.run_dual_shadow_suite(state_dir=state, n=5)
    assert rep.get("ok") is True
    assert rep["shadow_suite"]["n_stamped"] + rep["shadow_suite"]["n_sits"] >= 5
    assert (state / lag.STREAM).exists()
    summ = lag.summarize_stream(state_dir=state)
    assert summ["n_decisions"] >= 1
    assert summ["usd_orders_from_harness"] == "NEVER"


def test_usd_path_grep_has_stgm_copy_gate() -> None:
    """Regression: USD follows STGM and force-flat remains authoritative."""
    text = Path("System/alice_usd_must_scalp.py").read_text(encoding="utf-8")
    assert "load_open_book" in text
    assert "stgm_copy_only_no_paper" in text
    assert "stgm_exact_copy" in text
    text2 = Path("System/alice_usd_take_profit.py").read_text(encoding="utf-8")
    assert "NEVER_SELL_FOR_LOSS" in text2
    assert "take_profit_exit_policy" in text2
    assert "force_flat_is_real" in text2
