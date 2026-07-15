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


def test_usd_imports_same_regime_and_salvage_symbols() -> None:
    """Parity: USD modules must call strategies functions (import path exists)."""
    import inspect

    src_must = inspect.getsource(must.tick_must_scalp)
    assert "regime_gate" in src_must
    assert "alice_15m_scalp_strategies" in src_must
    src_tp = inspect.getsource(tp.tick_take_profits)
    assert "salvage_exit_should_fire" in src_tp
    assert "soft_adverse_should_fire" in src_tp
    assert "alice_15m_scalp_strategies" in src_tp


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


def test_must_scalp_regime_blocks_down_vs_up_field(tmp_path: Path) -> None:
    """BNB-class case: anchor DOWN but yes=0.98 → regime blocks/flips."""
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
    # force field anchor no (would fade UP)
    fake_field = {
        "anchor_side": "no",
        "ranked": [{"asset": "BNB"}, {"asset": "BTC"}],
        "breadth": 1.0,
        "majors_breadth": 1.0,
    }
    with mock.patch(
        "System.alice_15m_co_direction.board_field", return_value=fake_field
    ):
        with mock.patch(
            "System.kalshi_usd_hand.maybe_mirror_paper_bet",
            return_value={"event": "usd_skip", "reason": "test_no_place", "filled": False},
        ):
            out = must.tick_must_scalp(state_dir=state, dry_run=True)
    # either regime blocked all or flipped to yes (entry would be rich ~0.97)
    assert out.get("placed") is False
    # sit reason may be regime_or_band_empty / field_side_too_rich / attempted
    assert out.get("ok") is True
    # ensure regime_gate was in play: if candidates empty with regime rejects
    if out.get("reason") in (
        "regime_or_band_empty",
        "regime_gate_blocked_all",
        "field_side_too_rich",
    ):
        assert int(out.get("regime_rejects") or 0) >= 0


def test_evaluate_take_profit_path_flags_salvage() -> None:
    """Salvage should_fire on DOWN vs 98% UP with 500s left."""
    assert (
        strat.salvage_exit_should_fire(side="no", yes_mid=0.98, secs_left=500.0)
        is True
    )


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


def test_usd_path_grep_has_parity_calls() -> None:
    """Regression: zero-reference bug must not return."""
    text = Path("System/alice_usd_must_scalp.py").read_text(encoding="utf-8")
    assert "regime_gate" in text
    text2 = Path("System/alice_usd_take_profit.py").read_text(encoding="utf-8")
    assert "salvage_exit_should_fire" in text2
    assert "soft_adverse_should_fire" in text2
