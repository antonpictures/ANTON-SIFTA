#!/usr/bin/env python3
"""High-favorite (90%+) exit plan — capital preservation, not last-cent chase.

We-code-together (Grok + Codex + Alice):
  Optimize for NOT getting wrecked on 90¢+ lottery coupons.
  Paper math can look good; it does not prove a live-money edge.

Screenshot fixture (XRP Yes 2026-07-13):
  premium 0.916 · fee_in 0.0054 · cash-out ~0.99
  win ~+0.079 · lose ~−0.921 · BE WR ~92%+

Truth: XRP_FAVORITE_EXIT_PLAN_V1
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
LOG_NAME = "favorite_exit_plan.jsonl"
TRUTH = "XRP_FAVORITE_EXIT_PLAN_V1"
LOTTERY_UPSIDE_MAX = 0.12  # max win < 12¢ on $1 face → coupon regime
LOTTERY_BE_WR = 0.88  # breakeven WR above this → flag lottery
CASH_OUT_BAND = 0.02  # if cash-out within 2¢ of max upside → prefer exit

# Flip levels for sudden-move simulator (YES long mark)
FLIP_LEVELS = (0.50, 0.25, 0.10, 0.01, 0.0)


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def clamp_price(p: float) -> float:
    try:
        x = float(p)
    except (TypeError, ValueError):
        x = 0.5
    if not math.isfinite(x):
        x = 0.5
    return min(0.99, max(0.0, x))


def estimate_taker_fee(price: float, *, contracts: float = 1.0) -> float:
    """Same form as scalp learner / Kalshi variable fee ≈ 0.07·p·(1−p)."""
    p = clamp_price(price) if price > 0 else 0.01
    p = min(0.99, max(0.01, p))
    c = max(0.01, float(contracts))
    return round(max(0.0001, 0.07 * c * p * (1.0 - p)), 4)


@dataclass
class FavoriteExitPlan:
    entry_premium: float
    fee_in: float
    cash_out_quote: float
    max_payout: float = 1.0
    settlement_probability: Optional[float] = None  # P(win) if known
    flip_risk: float = 0.0  # 0–1 elevated wick/flip
    contracts: float = 1.0
    asset: str = "XRP"
    side: str = "yes"
    ticker: str = ""

    # computed
    net_entry_cost: float = 0.0
    max_profit_if_win: float = 0.0
    loss_if_lose: float = 0.0
    cash_out_net: float = 0.0
    fee_out_est: float = 0.0
    expected_value_hold: Optional[float] = None
    break_even_win_rate: float = 0.0
    exit_vs_hold_threshold: float = 0.0
    lottery_coupon: bool = False
    decision: str = "hold"
    reason_code: str = ""
    flip_sim: list[dict[str, Any]] = field(default_factory=list)
    plain_line: str = ""
    truth_label: str = TRUTH

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_plan(
    *,
    entry_premium: float,
    fee_in: Optional[float] = None,
    cash_out_quote: float,
    max_payout: float = 1.0,
    settlement_probability: Optional[float] = None,
    flip_risk: float = 0.0,
    contracts: float = 1.0,
    asset: str = "XRP",
    side: str = "yes",
    ticker: str = "",
    cash_out_band: float = CASH_OUT_BAND,
) -> FavoriteExitPlan:
    """Compute capital-preservation plan for a high-favorite long."""
    p = clamp_price(entry_premium)
    c = max(0.01, float(contracts))
    mp = float(max_payout) if max_payout and max_payout > 0 else 1.0
    fi = float(fee_in) if fee_in is not None else estimate_taker_fee(p, contracts=c)
    fi = max(0.0, fi)
    co = clamp_price(cash_out_quote)
    fo = estimate_taker_fee(co if co >= 0.01 else 0.01, contracts=c)

    net_cost = round(p * c + fi, 4)
    # win: receive max_payout * c, already paid net_cost
    max_win = round(mp * c - net_cost, 4)
    # lose: forfeit premium + fee_in
    loss = round(-net_cost, 4)
    # cash out: receive co * c, pay fo; total net from start
    cash_net = round(co * c - fo - net_cost, 4)

    # breakeven WR: wr * max_win + (1-wr) * loss = 0
    # wr * (max_win - loss) = -loss
    denom = max_win - loss
    if denom > 1e-12:
        be_wr = round((-loss) / denom, 4)
    else:
        be_wr = 1.0
    be_wr = min(0.999, max(0.0, be_wr))

    # EV hold if probability given
    ev_hold: Optional[float] = None
    if settlement_probability is not None:
        wr = min(0.999, max(0.001, float(settlement_probability)))
        ev_hold = round(wr * max_win + (1.0 - wr) * loss, 4)

    # exit vs hold: prefer exit when cash_net is close to max_win
    # threshold = cash_net; hold only if expected hold EV clearly beats cash_net
    exit_threshold = round(cash_net + float(cash_out_band), 4)

    # sudden flip simulator (YES long: mark drops)
    flip_sim: list[dict[str, Any]] = []
    for lvl in FLIP_LEVELS:
        lvl_c = max(0.0, min(1.0, float(lvl)))
        fo_f = estimate_taker_fee(max(0.01, lvl_c), contracts=c) if lvl_c > 0 else 0.0
        realized = round(lvl_c * c - fo_f - net_cost, 4)
        flip_sim.append(
            {
                "mark": lvl_c,
                "fee_out": fo_f,
                "realized_pnl": realized,
                "label": f"@{int(lvl_c * 100)}¢",
            }
        )

    lottery = bool(max_win <= LOTTERY_UPSIDE_MAX + 1e-9 and be_wr >= LOTTERY_BE_WR)

    # ── decision rules (preserve capital) ─────────────────────────────
    reason = ""
    decision = "hold"
    fr = min(1.0, max(0.0, float(flip_risk)))

    if lottery and cash_net >= 0:
        decision = "exit"
        reason = "lottery_coupon_take_green_exit"
    elif cash_net + 1e-9 >= max_win - cash_out_band:
        decision = "exit"
        reason = "cash_out_near_max_upside"
    elif settlement_probability is not None and float(settlement_probability) < be_wr:
        decision = "exit" if cash_net > loss * 0.5 else "do_not_hold"
        reason = "win_rate_below_breakeven"
    elif fr >= 0.55 and cash_net > loss * 0.3:
        decision = "exit"
        reason = "elevated_flip_wick_risk"
    elif cash_net < 0 and max_win > 0 and fr < 0.35:
        decision = "hold"
        reason = "underwater_or_thin_exit_hold_if_edge"
    else:
        if cash_net >= 0.03:
            decision = "exit"
            reason = "green_exit_preserve_gain"
        else:
            decision = "hold"
            reason = "hold_default_not_lottery_green"

    if decision == "do_not_hold" and cash_net >= 0:
        decision = "exit"

    plain = (
        "Paper math can look good, but it does not prove a live-money edge. "
        "High-favorite entries risk nearly full stake for a few cents of upside."
    )

    plan = FavoriteExitPlan(
        entry_premium=p,
        fee_in=round(fi, 4),
        cash_out_quote=co,
        max_payout=mp,
        settlement_probability=settlement_probability,
        flip_risk=fr,
        contracts=c,
        asset=asset,
        side=side,
        ticker=ticker,
        net_entry_cost=net_cost,
        max_profit_if_win=max_win,
        loss_if_lose=loss,
        cash_out_net=cash_net,
        fee_out_est=round(fo, 4),
        expected_value_hold=ev_hold,
        break_even_win_rate=be_wr,
        exit_vs_hold_threshold=exit_threshold,
        lottery_coupon=lottery,
        decision=decision,
        reason_code=reason,
        flip_sim=flip_sim,
        plain_line=plain,
    )
    return plan


def plan_from_open_row(
    open_row: dict[str, Any],
    *,
    cash_out_quote: float,
    settlement_probability: Optional[float] = None,
    flip_risk: float = 0.0,
) -> FavoriteExitPlan:
    """Build plan from kalshi_usd_night open row + live cash-out quote."""
    return build_plan(
        entry_premium=float(open_row.get("price") or open_row.get("premium_usd") or 0.9),
        fee_in=float(open_row.get("fee_paid_usd") or 0.0) or None,
        cash_out_quote=cash_out_quote,
        contracts=float(open_row.get("fill_count") or open_row.get("count") or 1.0),
        asset=str(open_row.get("asset") or "XRP"),
        side=str(open_row.get("side") or "yes"),
        ticker=str(open_row.get("ticker") or ""),
        settlement_probability=settlement_probability,
        flip_risk=flip_risk,
    )


def log_plan(
    plan: FavoriteExitPlan,
    *,
    state_dir: Optional[Path | str] = None,
    realized_pnl: Optional[float] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append one decision receipt for Alice / audit."""
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    row = plan.to_dict()
    row["ts"] = time.time()
    row["event"] = "favorite_exit_plan"
    if realized_pnl is not None:
        row["realized_pnl"] = float(realized_pnl)
    if extra:
        row.update(extra)
    try:
        with (root / LOG_NAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass
    return row


def report_line(plan: FavoriteExitPlan) -> str:
    """One plain line for glass / we-code monitor."""
    lot = "LOTTERY COUPON · " if plan.lottery_coupon else ""
    return (
        f"{lot}{plan.asset} {plan.side.upper()} @{plan.entry_premium:.0%} "
        f"win ${plan.max_profit_if_win:+.3f} lose ${plan.loss_if_lose:+.3f} "
        f"BE_WR {plan.break_even_win_rate:.0%} cash_out ${plan.cash_out_net:+.3f} "
        f"→ {plan.decision.upper()} ({plan.reason_code}). {plan.plain_line}"
    )


def deposit_we_code_together(
    plan: FavoriteExitPlan,
    *,
    state_dir: Optional[Path | str] = None,
) -> Path:
    """Tell Alice + Codex: this organ is coded (we-code-together)."""
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    receipt = {
        "ts": time.time(),
        "truth_label": "WE_CODE_TOGETHER_CODED_V1",
        "family": "xrp_favorite_exit_plan",
        "module": "System/xrp_favorite_exit_plan.py",
        "tests": "tests/test_xrp_favorite_exit_plan.py",
        "receipt_id": "r1656-favorite-exit-plan-lottery-coupon",
        "owner": "grok_we_code_together",
        "for_codex": (
            "USE WE CODE TOGETHER. High-favorite exit organ is live. "
            "Do not re-invent; import System.xrp_favorite_exit_plan. "
            "Capital preservation on 90%+ entries — not last-cent chase. "
            "Wire to USD open book / scalp when green cash-out near max upside."
        ),
        "for_alice": report_line(plan),
        "fixture": {
            "premium": 0.916,
            "fee_in": 0.0054,
            "cash_out": 0.99,
            "win": 0.0786,
            "lose": -0.9214,
            "be_wr": 0.921,
        },
        "sample_decision": plan.decision,
        "sample_reason": plan.reason_code,
        "lottery_coupon": plan.lottery_coupon,
    }
    path = root / "we_code_together_coded.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")
    # owner lesson + plan md
    lesson_path = root / "owner_trade_lessons.json"
    try:
        lessons = json.loads(lesson_path.read_text(encoding="utf-8")) if lesson_path.exists() else []
        if not isinstance(lessons, list):
            lessons = []
        lessons.append(
            {
                "ts": time.time(),
                "asset": "XRP",
                "side": "UP",
                "verdict": "lottery_coupon_favorite",
                "receipt_id": "r1656-favorite-exit-plan",
                "lesson": (
                    "90%+ favorites: risk ~full stake for ~cents. "
                    "Prefer cash-out when green near max upside; "
                    "do not hold if true WR < breakeven (~92% at 91.6¢). "
                    "Paper math ≠ live edge."
                ),
            }
        )
        lesson_path.write_text(json.dumps(lessons, indent=2), encoding="utf-8")
    except Exception:
        pass
    md = root / "favorite_exit_plan.md"
    md.write_text(
        "\n".join(
            [
                "# High-favorite exit plan (we code together)",
                "",
                report_line(plan),
                "",
                f"- decision: **{plan.decision}** · `{plan.reason_code}`",
                f"- lottery_coupon: {plan.lottery_coupon}",
                f"- BE_WR: {plan.break_even_win_rate:.1%}",
                f"- max win: ${plan.max_profit_if_win:+.4f} · lose: ${plan.loss_if_lose:+.4f}",
                f"- cash-out net: ${plan.cash_out_net:+.4f}",
                "",
                "## Flip simulator",
                *[
                    f"- {x['label']}: realized ${x['realized_pnl']:+.4f}"
                    for x in plan.flip_sim
                ],
                "",
                plan.plain_line,
                "",
                "Codex: import System.xrp_favorite_exit_plan — do not duplicate.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    # stigmergic IDE ping for Codex
    try:
        with (root / "ide_stigmergic_trace.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": time.time(),
                        "event": "we_code_together_coded",
                        "from": "grok",
                        "to": "codex",
                        "module": "System/xrp_favorite_exit_plan.py",
                        "msg": receipt["for_codex"],
                        "truth_label": TRUTH,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except Exception:
        pass
    return path


def evaluate_screenshot_fixture() -> FavoriteExitPlan:
    """Canonical numbers from owner Safari + fill book."""
    return build_plan(
        entry_premium=0.916,
        fee_in=0.0054,
        cash_out_quote=0.99,
        max_payout=1.0,
        settlement_probability=None,
        flip_risk=0.4,
        asset="XRP",
        side="yes",
        ticker="KXXRP15M-FAVORITE-FIXTURE",
    )


if __name__ == "__main__":
    plan = evaluate_screenshot_fixture()
    log_plan(plan)
    deposit_we_code_together(plan)
    print(report_line(plan))
    print(json.dumps(plan.to_dict(), indent=2)[:2000])
