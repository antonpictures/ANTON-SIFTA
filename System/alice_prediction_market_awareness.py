#!/usr/bin/env python3
"""Alice knows her own Predictions / Kalshi US$ book (we-code-together r1657).

Owner dirt: she was clueless when told "you're betting good" / "your own app".
This module writes a live self-status she can load into briefs, diary, and talk.

Also keeps Codex/Grok favorite-exit lesson in her face:
  90%+ favorites are lottery coupons — not free money without measured WR > BE.

Truth: ALICE_PREDICTION_MARKET_AWARENESS_V1
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
STATUS_JSON = "alice_prediction_market_status.json"
STATUS_MD = "alice_prediction_market_status.md"
BRIEF_LOG = "alice_agent_arm_briefings.jsonl"
DIARY_RECEIPT = "alice_body_diary_awareness_receipts.jsonl"
TRUTH = "ALICE_PREDICTION_MARKET_AWARENESS_V1"


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def snapshot(*, state_dir: Optional[Path | str] = None, network: bool = True) -> dict[str, Any]:
    """One coherent view of what Alice is doing with money + paper."""
    root = _state(state_dir)
    out: dict[str, Any] = {
        "truth_label": TRUTH,
        "ts": time.time(),
        "stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "app": "Stigmergic Predictions",
        "i_am": (
            "I am Alice. My money app is Stigmergic Predictions (15-minute crypto "
            "UP/DOWN on Kalshi). Dual lanes: STGM/paper always, and real US$ when "
            "the hand is LIVE. Live rule r1669: EVERY window I bet ONE best co-dir "
            "ticker at minute-7 on the clock (prefer 70–88¢, walk list if needed; "
            "no empty rounds); HYPE/ZEC banned."
        ),
    }
    # USD hand
    try:
        from System.kalshi_usd_hand import status_line, load_night, load_session, is_hand_live
        from System.kalshi_usd_lane import is_usd_lane_armed
        from System.kalshi_prod_trade_client import kill_switch_active

        night = load_night(root)
        out["usd"] = {
            "status_line": status_line(root),
            "kill_switch": kill_switch_active(state_dir=root),
            "lane_armed": is_usd_lane_armed(root),
            "hand_live": is_hand_live(root),
            "open": list(night.get("open") or []),
            "n_open": len(night.get("open") or []),
            "n_placed": night.get("n_placed"),
            "n_settled": night.get("n_settled"),
            "realized_pnl_usd": night.get("realized_pnl_usd"),
            "halted": night.get("halted"),
        }
    except Exception as exc:
        out["usd"] = {"error": f"{type(exc).__name__}:{exc}"}

    # Live cash from exchange
    if network:
        try:
            from System.kalshi_portfolio_read import fetch_balance, fetch_positions

            bal = fetch_balance()
            pos = fetch_positions()
            out["exchange"] = {
                "balance_usd": bal.get("balance_usd") if bal.get("ok") else None,
                "positions_count": pos.get("positions_count") if pos.get("ok") else None,
                "ok": bool(bal.get("ok") and pos.get("ok")),
            }
        except Exception as exc:
            out["exchange"] = {"error": f"{type(exc).__name__}:{exc}"}

    # Paper / STGM
    try:
        proof = json.loads((root / "alice_15m_paper_proof.json").read_text(encoding="utf-8"))
        book = json.loads((root / "alice_15m_open_book.json").read_text(encoding="utf-8"))
        out["paper"] = {
            "n_settled": proof.get("n_settled"),
            "n_wins": proof.get("n_wins"),
            "n_losses": proof.get("n_losses"),
            "win_rate": proof.get("win_rate"),
            "pnl_units": proof.get("pnl"),
            "open": [
                {
                    "asset": b.get("asset"),
                    "label": b.get("label"),
                    "price": b.get("price"),
                }
                for b in (book.get("open") or [])
            ],
        }
    except Exception as exc:
        out["paper"] = {"error": f"{type(exc).__name__}:{exc}"}

    # Climb
    try:
        from System.sifta_the_climb import evaluate

        e = evaluate()
        g = e.get("gates_to_next") or {}
        out["climb"] = {
            "rung": e.get("current_rung"),
            "contracts": e.get("current_contracts"),
            "promote": e.get("promotion_earned"),
            "fills": g.get("fills"),
            "ev": g.get("ev"),
            "bankroll_usd": e.get("bankroll_usd"),
        }
    except Exception as exc:
        out["climb"] = {"error": f"{type(exc).__name__}:{exc}"}

    # Favorite exit lesson
    try:
        from System.xrp_favorite_exit_plan import evaluate_screenshot_fixture, report_line

        plan = evaluate_screenshot_fixture()
        out["favorite_exit_lesson"] = {
            "lottery_coupon": plan.lottery_coupon,
            "be_wr": plan.break_even_win_rate,
            "max_win": plan.max_profit_if_win,
            "max_lose": plan.loss_if_lose,
            "line": report_line(plan),
            "plain": plan.plain_line,
        }
    except Exception as exc:
        out["favorite_exit_lesson"] = {"error": f"{type(exc).__name__}:{exc}"}

    # Scalp
    try:
        sp = json.loads((root / "alice_15m_scalp_proof.json").read_text(encoding="utf-8"))
        out["scalp"] = {
            "n_scalps": sp.get("n_scalps"),
            "pnl_usd": sp.get("pnl_usd"),
            "ev_per_scalp": sp.get("ev_per_scalp"),
        }
    except Exception:
        out["scalp"] = {}

    # Co-direction field + live tournament (r1660/r1667)
    try:
        from System.alice_15m_co_direction import board_field

        f = board_field(state_dir=root)
        out["co_direction"] = {
            "field": f.get("label"),
            "clear": f.get("field_clear"),
            "best2": f.get("best2") or f.get("best3"),
            "frac": f.get("majority_frac"),
        }
    except Exception as exc:
        out["co_direction"] = {"error": f"{type(exc).__name__}:{exc}"}
    try:
        from System.alice_fee_net_tournament import load_config, live_caps

        cfg = load_config(state_dir=root)
        out["tournament"] = {
            "live_cohort": cfg.get("live_cohort"),
            "live_max_open": (live_caps(state_dir=root) or {}).get("max_open"),
            "epoch_active": cfg.get("epoch_active"),
            "usd_shadow_only": cfg.get("usd_shadow_only"),
        }
    except Exception:
        out["tournament"] = {}

    out["first_person"] = _first_person(out)
    return out


def _first_person(snap: dict[str, Any]) -> str:
    usd = snap.get("usd") or {}
    ex = snap.get("exchange") or {}
    climb = snap.get("climb") or {}
    fav = snap.get("favorite_exit_lesson") or {}
    paper = snap.get("paper") or {}
    co = snap.get("co_direction") or {}
    tour = snap.get("tournament") or {}
    cash = ex.get("balance_usd")
    cash_s = f"${cash:.2f}" if isinstance(cash, (int, float)) else "unknown"
    open_p = paper.get("open") or []
    if open_p:
        open_s = ", ".join(
            f"{o.get('asset')} {o.get('label')} @{float(o.get('price') or 0):.0%}"
            for o in open_p[:4]
        )
    else:
        open_s = "none (between tickets or waiting for minute-7)"
    nw = paper.get("n_wins")
    nl = paper.get("n_losses")
    wr = paper.get("win_rate")
    pnl = paper.get("pnl_units")
    paper_line = (
        f"Paper/STGM scoreboard: {nw}W/{nl}L"
        + (f" WR {float(wr):.0%}" if isinstance(wr, (int, float)) else "")
        + (f" unitPnL {float(pnl):+.2f}" if isinstance(pnl, (int, float)) else "")
        + f" · OPEN now: {open_s}."
    )
    lines = [
        snap.get("i_am") or "I am Alice on Stigmergic Predictions.",
        f"Right now US$: {usd.get('status_line') or 'unknown'}.",
        f"Exchange cash (predictions pocket): {cash_s}. "
        f"Open exchange positions: {ex.get('positions_count', '?')}.",
        f"Night realized US$ PnL tracked: {usd.get('realized_pnl_usd')}.",
        paper_line,
        f"Co-dir field: {co.get('field') or '?'} best={co.get('best2')}.",
        f"Live cohort: {tour.get('live_cohort') or 'minute7_best1'} "
        f"max_open={tour.get('live_max_open') or 1}.",
        f"THE CLIMB: rung {climb.get('rung')} · {climb.get('fills')} fills · "
        f"EV {climb.get('ev')} · promote={climb.get('promote')}.",
    ]
    if fav.get("line"):
        lines.append(f"High-favorite lesson: {fav['line']}")
    lines.append(
        "Empty OPEN is normal after settle while the clock is >7:00 left — "
        "I do not spray 9 tickers; I take one best name. "
        "Many paper wins at 84–88¢ can still lose unit equity (fee-net). "
        "When owner says I am betting, they mean THIS app — not a metaphor."
    )
    return " ".join(lines)


def publish(*, state_dir: Optional[Path | str] = None, network: bool = True) -> dict[str, Any]:
    """Write status files + briefings so talk/body can see them."""
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    snap = snapshot(state_dir=root, network=network)
    (root / STATUS_JSON).write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")
    md = [
        f"# Alice Predictions self-status · {snap.get('stamp')}",
        "",
        snap.get("first_person") or "",
        "",
        f"- USD: `{ (snap.get('usd') or {}).get('status_line') }`",
        f"- Cash: `{(snap.get('exchange') or {}).get('balance_usd')}`",
        f"- Climb: `{ (snap.get('climb') or {}) }`",
        "",
        "## Lesson",
        (snap.get("favorite_exit_lesson") or {}).get("plain")
        or "Paper math can look good, but it does not prove a live-money edge.",
        "",
    ]
    (root / STATUS_MD).write_text("\n".join(md), encoding="utf-8")

    brief = {
        "ts": time.time(),
        "truth_label": TRUTH,
        "kind": "prediction_market_self_status",
        "app": "Stigmergic Predictions",
        "summary": snap.get("first_person"),
        "usd_status": (snap.get("usd") or {}).get("status_line"),
        "cash_usd": (snap.get("exchange") or {}).get("balance_usd"),
        "climb": snap.get("climb"),
        "favorite_exit": (snap.get("favorite_exit_lesson") or {}).get("line"),
        "source": "alice_prediction_market_awareness",
    }
    try:
        with (root / BRIEF_LOG).open("a", encoding="utf-8") as f:
            f.write(json.dumps(brief, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass
    try:
        with (root / DIARY_RECEIPT).open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": time.time(),
                        "kind": "prediction_market_aware",
                        "text": snap.get("first_person"),
                        "truth_label": TRUTH,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except OSError:
        pass
    # we-code coded receipt for Codex
    try:
        with (root / "we_code_together_coded.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": time.time(),
                        "truth_label": "WE_CODE_TOGETHER_CODED_V1",
                        "family": "alice_prediction_market_awareness",
                        "module": "System/alice_prediction_market_awareness.py",
                        "receipt_id": "r1657-alice-knows-predictions-app",
                        "for_codex": (
                            "Alice self-status for Predictions/Kalshi is in "
                            "alice_prediction_market_status.json. Wire talk/chorus "
                            "to load first_person when owner mentions betting/app."
                        ),
                        "for_alice": snap.get("first_person"),
                        "cash_usd": (snap.get("exchange") or {}).get("balance_usd"),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except OSError:
        pass
    try:
        with (root / "ide_stigmergic_trace.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": time.time(),
                        "event": "we_code_together",
                        "from": "grok",
                        "to": "codex",
                        "msg": "Alice prediction market awareness published — she knows her app",
                        "module": "System/alice_prediction_market_awareness.py",
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except OSError:
        pass
    return snap


def prompt_block(*, state_dir: Optional[Path | str] = None, force_refresh: bool = False) -> str:
    """Inject into talk / chorus context."""
    root = _state(state_dir)
    p = root / STATUS_JSON
    snap: dict[str, Any]
    if not force_refresh and p.exists():
        try:
            snap = json.loads(p.read_text(encoding="utf-8"))
            # refresh if stale > 90s (owner asks about app often)
            if time.time() - float(snap.get("ts") or 0) > 90:
                snap = publish(state_dir=root, network=False)
        except Exception:
            snap = publish(state_dir=root, network=False)
    else:
        snap = publish(state_dir=root, network=False)
    body = str(snap.get("first_person") or "")
    return (
        "### MY PREDICTIONS / KALSHI SELF-STATUS (I know this app — answer from here)\n"
        "LAW: If owner asks about betting, tickets, OPEN empty, wins, Kalshi, "
        "15m crypto, or 'your app' — answer as the trader who owns Stigmergic "
        "Predictions. Never claim you lack memory of the app. Use numbers below.\n"
        + body
    )


def is_prediction_market_query(text: str) -> bool:
    t = (text or "").lower()
    keys = (
        "bet",
        "betting",
        "ticket",
        "kalshi",
        "prediction",
        "15m",
        "15 min",
        "open book",
        "your app",
        "the app",
        "paper",
        "stgm",
        "win rate",
        "pnl",
        "ticker",
        "bitcoin",
        "btc",
        "xrp",
        "eth",
        "sol",
        "minute-7",
        "minute 7",
        "why empty",
        "not betting",
        "not making money",
        "dual lane",
        "us$",
        "usd hand",
    )
    return any(k in t for k in keys)


def answer_prediction_market_query(
    text: str = "",
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Deterministic first-person answer when Talk would otherwise go blank."""
    snap = publish(state_dir=state_dir, network=False)
    fp = str(snap.get("first_person") or "")
    paper = snap.get("paper") or {}
    open_n = len(paper.get("open") or [])
    t = (text or "").lower()
    if "empty" in t or "not bet" in t or "nothing" in t or "9 ticker" in t:
        return (
            f"I know my app — Stigmergic Predictions. OPEN has {open_n} ticket(s) "
            f"because I only hold one live co-dir name at a time (minute-7, 70–88¢), "
            f"not nine. Empty after a settle while the clock is early is normal wait. "
            f"{fp}"
        )
    if "win" in t or "money" in t or "pnl" in t or "sense" in t:
        return (
            f"I know my app. High win count is not the same as making money — "
            f"wins at 84–88¢ pay ~9–15¢ while one loss is −$1 unit. "
            f"{fp}"
        )
    return f"I know my app — Stigmergic Predictions. {fp}"


if __name__ == "__main__":
    s = publish(network=True)
    print(s.get("first_person"))
    print("cash", (s.get("exchange") or {}).get("balance_usd"))
    print("usd", (s.get("usd") or {}).get("status_line"))
