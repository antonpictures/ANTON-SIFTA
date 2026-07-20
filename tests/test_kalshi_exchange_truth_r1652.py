"""r1652 — exchange truth: NO premium + settlement P&L (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import kalshi_exchange_truth as xt
from System import kalshi_prod_trade_client as kpt


def _state(tmp_path: Path) -> Path:
    s = tmp_path / ".sifta_state"
    s.mkdir(parents=True, exist_ok=True)
    return s


def test_normalize_fill_no_uses_no_price_not_yes_residual() -> None:
    row = xt.normalize_fill(
        {
            "ticker": "KXXRP15M-TEST",
            "side": "no",
            "action": "sell",
            "yes_price_dollars": "0.1300",
            "no_price_dollars": "0.8700",
            "fee_cost": "0.008000",
            "count_fp": "1.00",
        }
    )
    assert row["side_premium"] == pytest.approx(0.87)
    assert row["premium_usd"] == pytest.approx(0.87)
    assert row["fee_cost_usd"] == pytest.approx(0.008)
    assert row["cost_usd"] == pytest.approx(0.878)


def test_settlement_pnl_matches_kalshi_xrp_no_win() -> None:
    # Audit example: XRP NO 87¢ + 0.8¢ fee → +$0.122
    g = xt.settlement_pnl(
        {
            "ticker": "KXXRP15M-26JUL130915-15",
            "market_result": "no",
            "yes_count_fp": "0.00",
            "no_count_fp": "1.00",
            "yes_total_cost_dollars": "0.000000",
            "no_total_cost_dollars": "0.870000",
            "fee_cost": "0.008000",
            "revenue": 100,
        }
    )
    assert g["win"] is True
    assert g["side"] == "no"
    assert g["pnl_usd"] == pytest.approx(0.122)


def test_settlement_pnl_yes_loss() -> None:
    g = xt.settlement_pnl(
        {
            "ticker": "KXSOL15M-TEST",
            "market_result": "no",
            "yes_count_fp": "1.00",
            "no_count_fp": "0.00",
            "yes_total_cost_dollars": "0.660000",
            "no_total_cost_dollars": "0.000000",
            "fee_cost": "0.015800",
            "revenue": 0,
        }
    )
    assert g["win"] is False
    assert g["pnl_usd"] == pytest.approx(-0.6758)


def test_rebuild_offline_writes_truth_and_keeps_halt(tmp_path: Path) -> None:
    state = _state(tmp_path)
    kpt.set_kill_switch(False, state_dir=state)  # will re-halt
    fills = [
        {
            "ticker": "KXXRP15M-A",
            "side": "no",
            "yes_price_dollars": "0.13",
            "no_price_dollars": "0.87",
            "fee_cost": "0.008",
            "count_fp": "1",
        }
    ]
    settlements = [
        {
            "ticker": "KXXRP15M-A",
            "market_result": "no",
            "yes_count_fp": "0",
            "no_count_fp": "1",
            "yes_total_cost_dollars": "0",
            "no_total_cost_dollars": "0.87",
            "fee_cost": "0.008",
            "revenue": 100,
        },
        {
            "ticker": "KXSOL15M-B",
            "market_result": "no",
            "yes_count_fp": "1",
            "no_count_fp": "0",
            "yes_total_cost_dollars": "0.66",
            "no_total_cost_dollars": "0",
            "fee_cost": "0.0158",
            "revenue": 0,
        },
    ]
    # local overstated NO win
    (state / "kalshi_usd_live_ledger.jsonl").write_text(
        json.dumps(
            {
                "event": "usd_settle_book",
                "ticker": "KXXRP15M-A",
                "win": True,
                "price": 0.13,
                "pnl_usd": 0.862,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    report = xt.rebuild_from_exchange(
        state_dir=state,
        network=False,
        fills=fills,
        settlements=settlements,
        balance_usd=10.22,
        positions=[],
        halt=True,
    )
    assert report["n_settlements"] == 2
    assert report["total_realized_usd"] == pytest.approx(0.122 + (-0.6758))
    assert report["live_ev_per_ticket"] == pytest.approx((0.122 - 0.6758) / 2)
    assert report["local_vs_exchange"]["n_joined"] == 1
    assert report["local_vs_exchange"]["local_overstatement"] == pytest.approx(0.862 - 0.122)
    assert report["climb_hint"]["use_for_ev"] is False
    assert report["climb_hint"]["promote"] is False
    assert kpt.kill_switch_active(state_dir=state) is True
    assert (state / "kalshi_exchange_truth.json").exists()
    assert (state / "kalshi_exchange_truth.md").exists()
