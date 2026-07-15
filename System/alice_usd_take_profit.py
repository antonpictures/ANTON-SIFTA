#!/usr/bin/env python3
"""Alice USD take-profit — owner taught: cash out greens (r1658 / r1684).

Stigmergic: mark open real-$ positions; if fee-true net ≥ MIN_EDGE, fire
reduce_only IOC cash-out via CreateOrderV2.

Owner lesson 2026-07-13: cashed others on green to teach take profits.
SOL deep red = do NOT auto stop-loss; only take green.

r1684 owner: bank greens **inside** the 15m window — do not wait for
settlement. Glass may show direction red while cash-out already booked green.
Pattern to repeat and discover via STGM scalp lab (never force every window).

Truth: ALICE_USD_TAKE_PROFIT_V1
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
LOG = "alice_usd_take_profit.jsonl"
TRUTH = "ALICE_USD_TAKE_PROFIT_V1"
MIN_EDGE_USD = 0.02  # fee-true bank (snappier in-and-out)
# r1705: through 7:30 left take thinner greens so she closes fast
EARLY_BURST_MIN_EDGE_USD = 0.01
EARLY_BURST_SECS = 7 * 60 + 30  # same gate as FORCE_FLAT (7:30 left)
# Never auto-exit fee-true losers outside force-flat (owner: profits, not panic)


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _log(row: dict[str, Any], *, state_dir: Path) -> None:
    row = dict(row)
    row.setdefault("ts", time.time())
    row.setdefault("truth_label", TRUTH)
    try:
        with (state_dir / LOG).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def _live_yes(ticker: str, asset: str, state_dir: Path) -> Optional[dict[str, float]]:
    live_path = state_dir / "kalshi_15m_live.json"
    if not live_path.exists():
        return None
    try:
        data = json.loads(live_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    for m in data.get("markets") or []:
        if not isinstance(m, dict):
            continue
        t = str(m.get("kalshi_ticker") or m.get("ticker") or "")
        if t == ticker or str(m.get("asset") or "") == asset:
            yes = m.get("kalshi_yes")
            if yes is None:
                yes = m.get("yes_price")
            if yes is None:
                return None
            return {
                "yes": float(yes),
                "yes_bid": float(m["yes_bid"]) if m.get("yes_bid") not in (None, "") else float(yes),
                "yes_ask": float(m["yes_ask"]) if m.get("yes_ask") not in (None, "") else float(yes),
                "volume": float(m.get("kalshi_volume_24h") or m.get("volume") or 0),
            }
    return None


def sync_open_to_exchange(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Drop local opens that exchange no longer holds (owner cash-out / settle)."""
    from System.kalshi_usd_hand import load_night, save_night, note_settle_from_paper
    from System.kalshi_portfolio_read import fetch_positions

    root = _state(state_dir)
    night = load_night(root)
    opens = list(night.get("open") or [])
    if not opens:
        return {"ok": True, "n_removed": 0, "n_open": 0}
    pos = fetch_positions()
    if not pos.get("ok"):
        return {"ok": False, "reason": pos.get("reason"), "n_open": len(opens)}
    live_tickers = {
        str(p.get("ticker") or "")
        for p in (pos.get("positions") or [])
        if abs(float(p.get("position") or 0)) > 1e-9
    }
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for o in opens:
        t = str(o.get("ticker") or "")
        if t in live_tickers:
            kept.append(o)
        else:
            removed.append(o)
            # Owner cash-out or settle — book as win if we can't know (green take)
            # Prefer not inventing PnL; log only
            _log(
                {
                    "event": "usd_open_sync_removed",
                    "ticker": t,
                    "asset": o.get("asset"),
                    "reason": "not_on_exchange",
                    "note": "owner cash-out or settle; local open cleared",
                },
                state_dir=root,
            )
    night["open"] = kept
    save_night(night, state_dir=root)
    return {
        "ok": True,
        "n_removed": len(removed),
        "n_open": len(kept),
        "removed": [{"asset": r.get("asset"), "ticker": r.get("ticker")} for r in removed],
    }


def evaluate_take_profit(
    open_row: dict[str, Any],
    mark: dict[str, float],
    *,
    min_edge: float = MIN_EDGE_USD,
) -> dict[str, Any]:
    """Fee-true mark PnL for cash-out decision."""
    from System.alice_15m_scalp_learner import estimate_taker_fee, side_exit_price

    side = str(open_row.get("side") or "yes").lower()
    entry = float(open_row.get("price") or open_row.get("side_price") or 0.5)
    fee_in = float(open_row.get("fee_paid_usd") or 0.0)
    count = float(open_row.get("fill_count") or open_row.get("count") or 1.0)
    yes = float(mark["yes"])
    exit_px = side_exit_price(
        side,
        yes,
        yes_bid=mark.get("yes_bid"),
        yes_ask=mark.get("yes_ask"),
        haircut=0.01,
    )
    fee_out = estimate_taker_fee(exit_px, contracts=count)
    # YES exit uses yes price; NO exit uses no price
    gross = (exit_px - entry) * count
    net = round(gross - fee_in - fee_out, 4)
    # exit yes price for API
    if side == "yes":
        exit_yes = exit_px
    else:
        exit_yes = round(1.0 - exit_px, 4)
    return {
        "side": side,
        "entry": entry,
        "exit_side": exit_px,
        "exit_yes": exit_yes,
        "fee_in": fee_in,
        "fee_out": fee_out,
        "net_usd": net,
        "take_profit": net >= float(min_edge) - 1e-9,
        "min_edge": float(min_edge),
    }


def _secs_left_live(state_dir: Path) -> Optional[float]:
    live_path = state_dir / "kalshi_15m_live.json"
    if not live_path.exists():
        return None
    try:
        data = json.loads(live_path.read_text(encoding="utf-8"))
        now = time.time()
        best = None
        for m in data.get("markets") or []:
            if not isinstance(m, dict):
                continue
            secs = m.get("seconds_to_close")
            if secs is None and m.get("close_ts"):
                try:
                    secs = max(0.0, float(m["close_ts"]) - now)
                except Exception:
                    continue
            if secs is None:
                continue
            try:
                sf = float(secs)
            except (TypeError, ValueError):
                continue
            if best is None or sf < best:
                best = sf
        return best
    except Exception:
        return None


def tick_take_profits(
    *,
    state_dir: Optional[Path | str] = None,
    min_edge: float = MIN_EDGE_USD,
    dry_run: bool = False,
    sync_first: bool = True,
    force_flat: bool = False,
) -> dict[str, Any]:
    """Scan USD opens; cash out fee-true greens via API.

    r1700: when secs_left ≤ 7:00 (or force_flat), cash out **all** opens
    (even small red) — prefer flat before danger zone; no hold-for-$2.
    """
    from System.kalshi_usd_hand import load_night, save_night, status_line, _log as hand_log
    from System.kalshi_prod_trade_client import (
        KalshiProdTradeClient,
        KillSwitchActive,
        CapRejected,
        NotProvisioned,
        kill_switch_active,
    )

    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    sync = sync_open_to_exchange(state_dir=root) if sync_first else {}
    night = load_night(root)
    opens = list(night.get("open") or [])
    if kill_switch_active(state_dir=root):
        return {
            "ok": False,
            "reason": "kill_switch",
            "status": status_line(root),
            "sync": sync,
        }
    if not opens:
        return {
            "ok": True,
            "n_open": 0,
            "n_cashed": 0,
            "status": status_line(root),
            "sync": sync,
            "note": "no local USD opens",
        }

    # r1705: force flat at ≤7:30 left; early burst thinner TP while above that
    # r1709: soft max adverse — cut reds early so we don't wait for deep force-flat
    SOFT_MAX_ADVERSE_USD = -0.35
    secs_left = _secs_left_live(root)
    try:
        from System.swarm_sifta_paper_loop import FORCE_FLAT_SECS

        flat_gate = float(FORCE_FLAT_SECS)
    except Exception:
        flat_gate = float(EARLY_BURST_SECS)
    danger_flat = bool(force_flat) or (
        secs_left is not None and secs_left <= flat_gate + 1e-9
    )
    # early burst (still >7:30 left): bank tiny fee-true greens fast
    # danger zone: edge 0 (force cash-out)
    if danger_flat:
        edge = 0.0
    elif secs_left is not None and secs_left >= float(EARLY_BURST_SECS) - 1e-9:
        edge = min(float(min_edge), float(EARLY_BURST_MIN_EDGE_USD))
    else:
        edge = float(min_edge)

    client = KalshiProdTradeClient(state_dir=root)
    cashed: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []

    for o in opens:
        t = str(o.get("ticker") or "")
        asset = str(o.get("asset") or "")
        mark = _live_yes(t, asset, root)
        if not mark:
            kept.append(o)
            held.append({"asset": asset, "reason": "no_mark"})
            continue
        ev = evaluate_take_profit(o, mark, min_edge=edge)
        side = str(o.get("side") or "yes").lower()
        yes_mid = float(mark["yes"])
        # r1713 P0 parity: same salvage + soft-adverse as STGM strategies (no fork)
        salvage = False
        soft_field = False
        try:
            from System.alice_15m_scalp_strategies import (
                salvage_exit_should_fire,
                soft_adverse_should_fire,
                side_implied_prob,
                SALVAGE_EXIT_REASON,
                SOFT_ADVERSE_REASON,
            )

            salvage = salvage_exit_should_fire(
                side=side, yes_mid=yes_mid, secs_left=secs_left
            )
            soft_field = soft_adverse_should_fire(
                side=side,
                yes_mid=yes_mid,
                secs_left=secs_left,
                entry=float(ev.get("entry") or 0),
                exit_bid=float(ev.get("exit_side") or 0),
            )
        except Exception:
            SALVAGE_EXIT_REASON = "salvage_exit_red_field"
            SOFT_ADVERSE_REASON = "soft_adverse_red_field"
        # r1709 soft stop: fee-true worse than −$0.35 → cut (don't wait for deep flat)
        soft_cut = (
            not danger_flat
            and float(ev.get("net_usd") or 0) <= SOFT_MAX_ADVERSE_USD + 1e-9
        )
        # danger flat: fire even if small red (still better than settle binary sometimes)
        # only skip if no mark (above) — always try reduce_only when danger_flat
        if (
            not danger_flat
            and not soft_cut
            and not salvage
            and not soft_field
            and not ev["take_profit"]
        ):
            kept.append(o)
            held.append(
                {
                    "asset": asset,
                    "net_usd": ev["net_usd"],
                    "reason": "not_green_fee_true",
                    "entry": ev["entry"],
                    "exit_side": ev["exit_side"],
                }
            )
            continue
        if danger_flat and not ev["take_profit"]:
            # still try cash-out at bid; owner: flat before last 7m
            ev = dict(ev)
            ev["take_profit"] = True
            ev["force_flat_7m"] = True
        elif salvage and not ev["take_profit"]:
            ev = dict(ev)
            ev["take_profit"] = True
            ev["salvage"] = True
            ev["exit_why"] = SALVAGE_EXIT_REASON
            try:
                ev["salvage_side_implied"] = side_implied_prob(side, yes_mid)
            except Exception:
                pass
        elif soft_field and not ev["take_profit"]:
            ev = dict(ev)
            ev["take_profit"] = True
            ev["soft_adverse"] = True
            ev["exit_why"] = SOFT_ADVERSE_REASON
        elif soft_cut and not ev["take_profit"]:
            ev = dict(ev)
            ev["take_profit"] = True
            ev["soft_max_adverse"] = True
            ev["force_flat_7m"] = False
        # FIRE cash-out
        try:
            from System.alice_usd_dual_lag_harness import stamp_exit_attempt

            stamp_exit_attempt(
                open_row=o,
                mark=mark,
                ev=ev,
                secs_left=secs_left,
                dry_run=dry_run,
                state_dir=root,
            )
        except Exception:
            pass
        try:
            placed = client.execute_reduce_only_cashout(
                ticker=t,
                hold_side=str(o.get("side") or "yes"),
                exit_yes_price=float(ev["exit_yes"]),
                count=float(o.get("fill_count") or o.get("count") or 1.0),
                dry_run=dry_run,
            )
        except (KillSwitchActive, CapRejected, NotProvisioned) as exc:
            kept.append(o)
            held.append({"asset": asset, "reason": f"{type(exc).__name__}:{exc}"})
            continue
        except Exception as exc:
            kept.append(o)
            held.append({"asset": asset, "reason": f"{type(exc).__name__}:{exc}"})
            continue

        row = {
            "event": "usd_take_profit",
            "asset": asset,
            "ticker": t,
            "side": o.get("side"),
            "entry": ev["entry"],
            "exit_side": placed.get("exit_side_price") or ev["exit_side"],
            "net_est_usd": ev["net_usd"],
            "fee_in": ev["fee_in"],
            "fee_out_est": ev["fee_out"],
            "filled": placed.get("filled"),
            "fill_count": placed.get("fill_count"),
            "fee_paid_exit": placed.get("fee_paid_usd"),
            "order_id": placed.get("order_id"),
            "dry_run": dry_run,
            "owner_lesson": (
                "force_flat_7m"
                if ev.get("force_flat_7m")
                else (
                    "salvage_exit_red_field"
                    if ev.get("salvage")
                    else (
                        "soft_adverse_red_field"
                        if ev.get("soft_adverse")
                        else (
                            "soft_max_adverse"
                            if ev.get("soft_max_adverse")
                            else "take_profits_on_green"
                        )
                    )
                )
            ),
            "force_flat_7m": bool(ev.get("force_flat_7m")),
            "soft_max_adverse": bool(ev.get("soft_max_adverse")),
            "salvage": bool(ev.get("salvage")),
            "soft_adverse": bool(ev.get("soft_adverse")),
            "exit_why": ev.get("exit_why") or "",
            "secs_left": secs_left,
        }
        if placed.get("filled"):
            # realized approx: exit - entry - fees
            exit_p = float(placed.get("exit_side_price") or ev["exit_side"] or 0)
            fee_out = float(placed.get("fee_paid_usd") or 0)
            pnl = round(
                (exit_p - float(ev["entry"])) * float(placed.get("fill_count") or 1)
                - float(ev["fee_in"])
                - fee_out,
                4,
            )
            row["pnl_usd"] = pnl
            night["realized_pnl_usd"] = round(
                float(night.get("realized_pnl_usd") or 0.0) + pnl, 4
            )
            night["n_settled"] = int(night.get("n_settled") or 0) + 1
            cashed.append(row)
            hand_log({**row, "deal": "r1700" if ev.get("force_flat_7m") else "r1648"}, state_dir=root)
            _log(row, state_dir=root)
        else:
            # no fill — keep open
            kept.append(o)
            held.append({"asset": asset, "reason": "cashout_no_fill", **row})
            _log({**row, "event": "usd_take_profit_no_fill"}, state_dir=root)

    night["open"] = kept
    save_night(night, state_dir=root)
    out = {
        "ok": True,
        "event": "take_profit_tick",
        "n_open": len(kept),
        "n_cashed": len(cashed),
        "cashed": cashed,
        "held": held,
        "sync": sync,
        "status": status_line(root),
        "truth_label": TRUTH,
        "secs_left": secs_left,
        "force_flat": danger_flat,
        "flat_gate_secs": flat_gate,
        "min_edge_used": edge,
        "ts": time.time(),
    }
    _log(out, state_dir=root)
    # owner lesson sticky
    try:
        lessons_path = root / "owner_trade_lessons.json"
        lessons = (
            json.loads(lessons_path.read_text(encoding="utf-8"))
            if lessons_path.exists()
            else []
        )
        if not isinstance(lessons, list):
            lessons = []
        dirty = False
        if not any(x.get("receipt_id") == "r1658-take-profits-on-green" for x in lessons):
            lessons.append(
                {
                    "ts": time.time(),
                    "verdict": "take_profits_on_green",
                    "receipt_id": "r1658-take-profits-on-green",
                    "lesson": (
                        "Owner cashed greens to teach take-profit. "
                        "Alice USD path: fee-true net ≥ $0.03 → reduce_only IOC cash-out. "
                        "Do not auto dump underwater losers."
                    ),
                }
            )
            dirty = True
        if not any(x.get("receipt_id") == "r1684-bank-greens-mid-window" for x in lessons):
            lessons.append(
                {
                    "ts": time.time(),
                    "verdict": "bank_greens_mid_window",
                    "receipt_id": "r1684-bank-greens-mid-window",
                    "lesson": (
                        "Scalp worked better than hold when path died on glass. "
                        "Bank fee-true greens within the 15m via cash-out organ; "
                        "do not wait till settlement every ticket. "
                        "Repeat that pattern; find more via STGM scalp lab."
                    ),
                }
            )
            dirty = True
        if not any(x.get("receipt_id") == "r1700-flat-by-7m-more-scalps" for x in lessons):
            lessons.append(
                {
                    "ts": time.time(),
                    "verdict": "flat_by_7m_more_scalps",
                    "receipt_id": "r1700-flat-by-7m-more-scalps",
                    "lesson": (
                        "Owner: profits is profit — do not hold for full $2 settle greed. "
                        "Hunt + bank in first ~8m; FORCE FLAT all opens at ≤7:00 left. "
                        "More scalps/session (up to 3) when closed early; last 7m = no new risk."
                    ),
                }
            )
            dirty = True
        if dirty:
            lessons_path.write_text(json.dumps(lessons, indent=2), encoding="utf-8")
    except Exception:
        pass
    return out


if __name__ == "__main__":
    print(json.dumps(tick_take_profits(dry_run=False), indent=2, default=str)[:2500])
