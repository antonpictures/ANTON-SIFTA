"""High-favorite exit plan — screenshot fixture (XRP 91.6¢)."""

from __future__ import annotations

import pytest

from System.xrp_favorite_exit_plan import (
    build_plan,
    estimate_taker_fee,
    evaluate_screenshot_fixture,
    report_line,
)


def test_screenshot_numbers_win_lose_be_wr() -> None:
    plan = evaluate_screenshot_fixture()
    assert plan.entry_premium == pytest.approx(0.916)
    assert plan.fee_in == pytest.approx(0.0054)
    assert plan.net_entry_cost == pytest.approx(0.9214)
    # win ~+0.079, lose ~-0.921
    assert plan.max_profit_if_win == pytest.approx(0.0786, abs=0.001)
    assert plan.loss_if_lose == pytest.approx(-0.9214, abs=0.001)
    # break-even ~92%+
    assert plan.break_even_win_rate >= 0.92
    assert plan.break_even_win_rate == pytest.approx(0.9214, abs=0.01)
    # cash out ~0.99 → green small
    assert plan.cash_out_net == pytest.approx(0.99 - 0.9214 - plan.fee_out_est, abs=0.01)
    assert plan.cash_out_net > 0
    assert plan.lottery_coupon is True


def test_flip_simulator_wreck_levels() -> None:
    plan = build_plan(
        entry_premium=0.916,
        fee_in=0.0054,
        cash_out_quote=0.99,
    )
    by_mark = {round(x["mark"], 2): x["realized_pnl"] for x in plan.flip_sim}
    assert by_mark[0.50] < -0.40
    assert by_mark[0.10] < -0.80
    assert by_mark[0.0] == pytest.approx(-0.9214, abs=0.001)


def test_prefer_exit_when_cash_out_near_max_upside() -> None:
    plan = build_plan(
        entry_premium=0.916,
        fee_in=0.0054,
        cash_out_quote=0.99,
        flip_risk=0.2,
    )
    assert plan.decision in ("exit", "do_not_hold")
    assert plan.reason_code
    assert "live-money edge" in plan.plain_line.lower() or "paper math" in plan.plain_line.lower()


def test_do_not_hold_if_wr_below_breakeven() -> None:
    plan = build_plan(
        entry_premium=0.916,
        fee_in=0.0054,
        cash_out_quote=0.50,  # bad exit
        settlement_probability=0.80,  # below ~92% BE
        flip_risk=0.1,
    )
    assert plan.break_even_win_rate > 0.90
    assert plan.settlement_probability is not None
    assert plan.settlement_probability < plan.break_even_win_rate
    assert plan.decision in ("exit", "do_not_hold", "hold")
    # EV hold negative
    assert plan.expected_value_hold is not None
    assert plan.expected_value_hold < 0


def test_report_line_plain() -> None:
    line = report_line(evaluate_screenshot_fixture())
    assert "92%" in line or "BE_WR" in line
    assert "Paper math" in line or "live-money" in line


def test_fee_model_matches_fill() -> None:
    assert estimate_taker_fee(0.916) == pytest.approx(0.0054, abs=0.0005)
