"""r1629 — dollar-parity STGM, Kalshi money language, STGM≡$/1000."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import alice_15m_body_stgm as body
from System.sifta_15m_money_math import (
    STGM_PER_USD,
    dollar_pnl_if_real,
    net_multiplier,
    stgm_pnl_from_price,
    stgm_to_usd,
)


def test_kalshi_fixture_multipliers() -> None:
    # Owner Safari card: 83¢ → ~1.16x, 17¢ → ~5.90x
    assert abs(net_multiplier(0.83) - 1.16) < 0.03
    assert abs(net_multiplier(0.17) - 5.90) < 0.15


def test_if_real_dollar_round_math() -> None:
    # 5W/3L trap example (gross-ish via net mult)
    tickets = [
        (0.73, True),
        (0.74, True),
        (0.73, True),
        (0.76, True),
        (0.80, True),
        (0.72, False),
        (0.73, False),
        (0.74, False),
    ]
    total = sum(dollar_pnl_if_real(p, win=w) for p, w in tickets)
    # Wins pay cents, 3 losses cost $3 — round should be negative
    assert total < 0
    assert total > -2.0  # not catastrophic beyond ~$1.5


def test_stgm_mirrors_dollars_div_1000() -> None:
    for price, win in [(0.74, True), (0.74, False), (0.83, True), (0.17, True)]:
        usd = dollar_pnl_if_real(price, win=win)
        stgm = stgm_pnl_from_price(price, win=win, stake_stgm=STGM_PER_USD)
        assert abs(stgm_to_usd(stgm) - usd) < 1e-6
        assert abs(stgm - usd * STGM_PER_USD) < 1e-9


def _state(tmp_path: Path, *, total: float = 1145.0, m5: float = 97.0) -> Path:
    state = tmp_path / ".sifta_state"
    state.mkdir()
    (state / "stgm_economy_cache.json").write_text(
        json.dumps(
            {
                "spendable_total_stgm": total,
                "alice_m5_spendable_stgm": m5,
                "canonical_wallet_balances": {"ALICE_M5": m5},
            }
        ),
        encoding="utf-8",
    )
    return state


def test_body_stake_is_one_dollar_scale(tmp_path: Path) -> None:
    state = _state(tmp_path)
    assert body.STGM_STAKE == pytest.approx(0.001)
    out = body.stake_body_stgm(
        ticker="BTC-1", asset="BTC", label="UP", price=0.74, state_dir=state
    )
    assert out["ok"] and out["stake"] == pytest.approx(0.001)


def test_body_win_is_asymmetric_mult(monkeypatch, tmp_path: Path) -> None:
    state = _state(tmp_path)
    body.stake_body_stgm(
        ticker="BTC-2", asset="BTC", label="UP", price=0.74, state_dir=state
    )
    expected = stgm_pnl_from_price(0.74, win=True, stake_stgm=0.001)
    monkeypatch.setattr(
        body,
        "_reward_win",
        lambda ticker, amount_stgm: {"minted_stgm": amount_stgm, "source_receipt_id": ticker},
    )
    out = body.settle_body_stgm(
        ticker="BTC-2",
        asset="BTC",
        label="UP",
        price=0.74,
        win=True,
        state_dir=state,
        repair_log=tmp_path / "repair_log.jsonl",
    )
    assert out["ok"]
    assert out["pnl_stgm"] == pytest.approx(expected, rel=1e-4)
    # ~ +$0.35 at $1 → ~0.00035 STGM, NOT flat +0.001
    assert out["pnl_stgm"] < 0.0005
    assert out["pnl_stgm"] > 0.0002


def test_body_loss_costs_full_stake(monkeypatch, tmp_path: Path) -> None:
    state = _state(tmp_path)
    body.stake_body_stgm(
        ticker="ETH-2", asset="ETH", label="DOWN", price=0.74, state_dir=state
    )
    monkeypatch.setattr(
        body,
        "_burn_loss",
        lambda **kwargs: {"spent_stgm": kwargs["amount"], "signed": True},
    )
    out = body.settle_body_stgm(
        ticker="ETH-2",
        asset="ETH",
        label="DOWN",
        price=0.74,
        win=False,
        state_dir=state,
        repair_log=tmp_path / "repair_log.jsonl",
    )
    assert out["pnl_stgm"] == pytest.approx(-0.001)


def test_epoch_fences_legacy_pnl(tmp_path: Path) -> None:
    state = _state(tmp_path)
    # Simulate old V2 budget
    (state / body.BUDGET_NAME).write_text(
        json.dumps(
            {
                "truth_label": "ALICE_15M_BODY_STGM_V2",
                "realized_pnl_stgm": 0.027,
                "open_tickets": {},
                "settled_tickers": [],
            }
        ),
        encoding="utf-8",
    )
    b = body._load_budget(state)
    assert b["stake_epoch"] == body.STAKE_EPOCH
    assert b["realized_pnl_stgm_legacy_v2"] == pytest.approx(0.027)
    assert b["realized_pnl_stgm"] == pytest.approx(0.0)
