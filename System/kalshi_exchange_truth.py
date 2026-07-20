#!/usr/bin/env python3
"""r1652 — EXCHANGE TRUTH reconciliation (Codex + Grok we-code-together).

Alice was optimizing the paper/STGM scoreboard while the local cash ledger
mis-booked NO-side fills (YES-book residual as premium). This module never
places orders. It rebuilds honest capacity from:

  • GET /portfolio/fills       — exact side prices + fee_cost
  • GET /portfolio/settlements — revenue, cost, fee, market_result
  • GET /portfolio/balance     — cash truth
  • GET /portfolio/positions   — open exposure truth

USD writes stay killed. STGM is untouched.

P&L (settlement row):
  revenue_usd = revenue_cents / 100
  cost_usd    = yes_total_cost_dollars + no_total_cost_dollars
  pnl_usd     = revenue_usd - cost_usd - fee_cost

Writes:
  .sifta_state/kalshi_exchange_truth.json
  .sifta_state/kalshi_exchange_truth.md
  append .sifta_state/kalshi_exchange_truth.jsonl
"""

from __future__ import annotations

import json
import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATE = ROOT / ".sifta_state"
OUT_JSON = "kalshi_exchange_truth.json"
OUT_MD = "kalshi_exchange_truth.md"
OUT_LOG = "kalshi_exchange_truth.jsonl"
TRUTH = "KALSHI_EXCHANGE_TRUTH_V1"
RECEIPT = "r1652_exchange_truth_reconciliation_surgery"
# Alice 15m crypto series only (campaign lane — not whole Kalshi account history)
_CAMPAIGN_TICKER = re.compile(
    r"^KX(BTC|ETH|SOL|XRP|DOGE|BNB|HYPE|NEAR|ZEC|SUI)15M-",
    re.I,
)


def is_campaign_ticker(ticker: str) -> bool:
    return bool(_CAMPAIGN_TICKER.match(str(ticker or "").strip()))


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _num(v: Any) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _fp(v: Any, default: float = 0.0) -> float:
    x = _num(v)
    return default if x is None else x


def normalize_fill(raw: dict[str, Any]) -> dict[str, Any]:
    """Side premium from exchange fill (no_price / yes_price dollars — never YES residual alone)."""
    side = str(raw.get("side") or raw.get("outcome_side") or "").lower()
    yes_px = _num(raw.get("yes_price_dollars") if raw.get("yes_price_dollars") is not None else raw.get("yes_price"))
    no_px = _num(raw.get("no_price_dollars") if raw.get("no_price_dollars") is not None else raw.get("no_price"))
    if side == "no":
        premium = no_px if no_px is not None else (round(1.0 - yes_px, 4) if yes_px is not None else None)
    elif side == "yes":
        premium = yes_px if yes_px is not None else (round(1.0 - no_px, 4) if no_px is not None else None)
    else:
        premium = no_px or yes_px
    count = _fp(raw.get("count_fp") if raw.get("count_fp") is not None else raw.get("count"), 1.0)
    fee = max(0.0, _fp(raw.get("fee_cost")))
    prem = float(premium or 0.0)
    return {
        "ticker": str(raw.get("ticker") or raw.get("market_ticker") or ""),
        "side": side,
        "action": str(raw.get("action") or ""),
        "book_side": str(raw.get("book_side") or ""),
        "count": count,
        "yes_price": yes_px,
        "no_price": no_px,
        "side_premium": round(prem, 4) if premium is not None else None,
        "premium_usd": round(prem * count, 4) if premium is not None else None,
        "fee_cost_usd": round(fee, 4),
        "cost_usd": round(prem * count + fee, 4) if premium is not None else round(fee, 4),
        "order_id": str(raw.get("order_id") or ""),
        "fill_id": str(raw.get("fill_id") or raw.get("trade_id") or ""),
        "is_taker": bool(raw.get("is_taker")),
        "created_time": str(raw.get("created_time") or ""),
        "ts": raw.get("ts"),
        "source": "KALSHI_PROD_GET_/portfolio/fills",
        "price_convention": "exchange_side_dollars",
    }


def settlement_pnl(raw: dict[str, Any]) -> dict[str, Any]:
    """Fee-true P&L from one exchange settlement row."""
    yes_c = _fp(raw.get("yes_count_fp"))
    no_c = _fp(raw.get("no_count_fp"))
    yes_cost = max(0.0, _fp(raw.get("yes_total_cost_dollars")))
    no_cost = max(0.0, _fp(raw.get("no_total_cost_dollars")))
    cost = round(yes_cost + no_cost, 6)
    fee = max(0.0, _fp(raw.get("fee_cost")))
    # Kalshi revenue is integer cents on the winning contracts
    revenue_cents = _fp(raw.get("revenue"))
    revenue_usd = round(revenue_cents / 100.0, 6)
    pnl = round(revenue_usd - cost - fee, 4)
    side = "yes" if yes_c > 0 and no_c <= 0 else "no" if no_c > 0 else ""
    result = str(raw.get("market_result") or "").lower()
    win = bool(side and result == side)
    count = yes_c if side == "yes" else no_c if side == "no" else max(yes_c, no_c)
    premium = (cost / count) if count > 0 else None
    return {
        "ticker": str(raw.get("ticker") or ""),
        "side": side,
        "market_result": result,
        "win": win,
        "count": count,
        "cost_usd": round(cost, 4),
        "premium_usd": round(float(premium), 4) if premium is not None else None,
        "fee_cost_usd": round(fee, 4),
        "revenue_usd": round(revenue_usd, 4),
        "pnl_usd": pnl,
        "settled_time": str(raw.get("settled_time") or ""),
        "event_ticker": str(raw.get("event_ticker") or ""),
        "source": "KALSHI_PROD_GET_/portfolio/settlements",
        "truth_label": TRUTH,
    }


def compare_local_vs_exchange(
    *,
    exchange_settles: list[dict[str, Any]],
    local_settles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Join local usd_settle_book rows to exchange settlement P&L by ticker."""
    by_t = {str(s.get("ticker") or ""): s for s in exchange_settles if s.get("ticker")}
    joined: list[dict[str, Any]] = []
    for loc in local_settles:
        t = str(loc.get("ticker") or "")
        ex = by_t.get(t)
        if not ex:
            continue
        local_pnl = _num(loc.get("pnl_usd"))
        ex_pnl = _num(ex.get("pnl_usd"))
        if local_pnl is None or ex_pnl is None:
            continue
        joined.append(
            {
                "ticker": t,
                "local_pnl_usd": local_pnl,
                "exchange_pnl_usd": ex_pnl,
                "delta_local_minus_exchange": round(local_pnl - ex_pnl, 4),
                "local_price": loc.get("price"),
                "exchange_premium": ex.get("premium_usd"),
                "exchange_side": ex.get("side"),
                "win": ex.get("win"),
            }
        )
    over = round(sum(float(j["delta_local_minus_exchange"]) for j in joined), 4)
    n = len(joined)
    return {
        "n_joined": n,
        "local_sum": round(sum(float(j["local_pnl_usd"]) for j in joined), 4) if n else 0.0,
        "exchange_sum": round(sum(float(j["exchange_pnl_usd"]) for j in joined), 4) if n else 0.0,
        "local_overstatement": over,
        "ev_local": round(sum(float(j["local_pnl_usd"]) for j in joined) / n, 4) if n else None,
        "ev_exchange": round(sum(float(j["exchange_pnl_usd"]) for j in joined) / n, 4) if n else None,
        "tickets": joined,
    }


def _local_settles(state_dir: Path) -> list[dict[str, Any]]:
    path = state_dir / "kalshi_usd_live_ledger.jsonl"
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict) and r.get("event") == "usd_settle_book":
            out.append(r)
    return out


def ensure_usd_halted(*, state_dir: Optional[Path | str] = None, reason: str = RECEIPT) -> dict[str, Any]:
    """Reaffirm kill + lane off + hand idle. STGM untouched."""
    from System.kalshi_prod_trade_client import set_kill_switch, kill_switch_active
    from System.kalshi_usd_lane import set_usd_lane_armed, is_usd_lane_armed
    from System.kalshi_usd_hand import set_hand_live, is_hand_live, status_line

    root = _state(state_dir)
    set_kill_switch(True, reason=reason, state_dir=root)
    set_usd_lane_armed(False, reason=reason, state_dir=state_dir)
    set_hand_live(False, reason=reason, state_dir=state_dir)
    return {
        "kill_switch": kill_switch_active(state_dir=root),
        "lane_armed": is_usd_lane_armed(state_dir),
        "hand_live": is_hand_live(state_dir),
        "status_line": status_line(state_dir),
        "stgm": "unchanged",
        "reason": reason,
    }


def rebuild_from_exchange(
    *,
    state_dir: Optional[Path | str] = None,
    limit: int = 200,
    network: bool = True,
    fills: Optional[list[dict[str, Any]]] = None,
    settlements: Optional[list[dict[str, Any]]] = None,
    balance_usd: Optional[float] = None,
    positions: Optional[list[dict[str, Any]]] = None,
    halt: bool = True,
) -> dict[str, Any]:
    """Fetch (or accept) exchange tape → honest ladder inputs. No order writes."""
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    halt_row: dict[str, Any] = {}
    if halt:
        halt_row = ensure_usd_halted(state_dir=state_dir)

    fill_rows: list[dict[str, Any]] = list(fills or [])
    settle_rows: list[dict[str, Any]] = list(settlements or [])
    bal = balance_usd
    pos = list(positions or [])
    net_ok = True
    net_err = ""

    if network and (fills is None or settlements is None):
        try:
            from System.kalshi_portfolio_read import (
                fetch_balance,
                fetch_fills,
                fetch_positions,
                fetch_settlements,
            )

            if fills is None:
                fr = fetch_fills(limit=limit)
                if not fr.get("ok"):
                    net_ok = False
                    net_err = str(fr.get("reason") or "fills_fail")
                else:
                    fill_rows = list(fr.get("fills") or [])
            if settlements is None:
                sr = fetch_settlements(limit=limit)
                if not sr.get("ok"):
                    net_ok = False
                    net_err = (net_err + " · " if net_err else "") + str(
                        sr.get("reason") or "settlements_fail"
                    )
                else:
                    settle_rows = list(sr.get("settlements") or [])
            if balance_usd is None:
                br = fetch_balance()
                if br.get("ok"):
                    bal = br.get("balance_usd")
            if positions is None:
                pr = fetch_positions()
                if pr.get("ok"):
                    pos = list(pr.get("positions") or [])
        except Exception as exc:
            net_ok = False
            net_err = f"{type(exc).__name__}:{exc}"

    norm_fills = [
        normalize_fill(f)
        for f in fill_rows
        if isinstance(f, dict) and is_campaign_ticker(str(f.get("ticker") or f.get("market_ticker") or ""))
    ]
    graded_all = [settlement_pnl(s) for s in settle_rows if isinstance(s, dict)]
    graded_all = [g for g in graded_all if g.get("ticker")]
    # Campaign: 15m crypto only + small tickets (Alice = 1 contract; allow ≤3)
    graded = [
        g
        for g in graded_all
        if is_campaign_ticker(str(g.get("ticker") or ""))
        and float(g.get("count") or 0) <= 3.0 + 1e-9
        and float(g.get("cost_usd") or 0) <= 5.0 + 1e-9
    ]

    n = len(graded)
    total = round(sum(float(g["pnl_usd"]) for g in graded), 4) if n else 0.0
    wins = sum(1 for g in graded if g.get("win"))
    losses = n - wins
    ev = round(total / n, 4) if n else None

    local = _local_settles(root)
    cmp_ = compare_local_vs_exchange(exchange_settles=graded, local_settles=local)

    open_exposure = 0.0
    for p in pos:
        for k in ("market_exposure_dollars", "market_exposure"):
            if k in p and _num(p.get(k)) is not None:
                open_exposure += abs(float(p[k]))
                break
    open_exposure = round(open_exposure, 4)

    report = {
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "ts": time.time(),
        "stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "network_ok": net_ok,
        "network_error": net_err,
        "usd_halt": halt_row,
        "stgm": "ON_UNCHANGED",
        "balance_usd": bal,
        "open_positions": len(pos),
        "open_exposure_usd": open_exposure,
        "n_fills": len(norm_fills),
        "n_settlements_account": len(graded_all),
        "n_settlements": n,
        "wins": wins,
        "losses": losses,
        "total_realized_usd": total,
        "live_ev_per_ticket": ev,
        "filter": "ACCOUNT CONTEXT ONLY: KX*15M · count<=3 · cost<=$5",
        "local_vs_exchange": {
            k: cmp_[k]
            for k in (
                "n_joined",
                "local_sum",
                "exchange_sum",
                "local_overstatement",
                "ev_local",
                "ev_exchange",
            )
        },
        "fills_sample": norm_fills[:12],
        "settlements_sample": graded[:12],
        "joined_sample": cmp_.get("tickets", [])[:12],
        "note": (
            "This broad account 15m view is context, not Alice sizing evidence. "
            "Only Alice order-ID exchange reconciliation may drive THE CLIMB. "
            "USD orders halted; STGM free."
        ),
        "climb_hint": {
            "use_for_ev": False,
            "reason": "broad account filter can include non-Alice/manual trades",
            "fills": f"{cmp_['n_joined']}/100",
            "ev": cmp_["ev_exchange"],
            "ev_gate": 0.05,
            "promote": False,
        },
    }

    (root / OUT_JSON).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md = [
        f"# EXCHANGE TRUTH — {RECEIPT}",
        f"updated {report['stamp']}",
        "",
        f"- **USD halt:** `{halt_row.get('status_line') or 'HALT'}` · STGM unchanged",
        f"- cash **${bal if bal is not None else '—'}** · open pos {len(pos)} · exposure **${open_exposure:.2f}**",
        f"- account-context settlements **{n}** · wins {wins} · losses {losses}",
        f"- account-context realized ${total:+.4f} · EV/ticket {ev if ev is not None else 'n/a'}",
        "- **not eligible for THE CLIMB** — may include non-Alice/manual trades",
        "",
        "## Local vs exchange (joined)",
        f"- joined {cmp_['n_joined']}",
        f"- local sum ${cmp_['local_sum']:+.4f} · exchange sum ${cmp_['exchange_sum']:+.4f}",
        f"- **local overstatement ${cmp_['local_overstatement']:+.4f}**",
        f"- EV local {cmp_['ev_local']} · EV exchange {cmp_['ev_exchange']}",
        "",
        "## Sample settlements (exchange)",
    ]
    for g in graded[:10]:
        md.append(
            f"- `{g['ticker']}` {g['side'].upper()} "
            f"{'WIN' if g['win'] else 'LOSS'} prem={g.get('premium_usd')} "
            f"fee={g['fee_cost_usd']} **pnl ${g['pnl_usd']:+.4f}**"
        )
    md.extend(
        [
            "",
            "## Next",
            "1. Keep USD halt until owner GO after glass matches Safari cash/P&L",
            "2. THE CLIMB reads strict Alice order-ID reconciliation, not this broad EV",
            "3. STGM/paper may continue — body learning only",
        ]
    )
    (root / OUT_MD).write_text("\n".join(md) + "\n", encoding="utf-8")
    try:
        with (root / OUT_LOG).open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": report["ts"],
                        "event": "exchange_truth_rebuild",
                        "n_settlements": n,
                        "total_realized_usd": total,
                        "ev": ev,
                        "local_overstatement": cmp_["local_overstatement"],
                        "truth_label": TRUTH,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
    except OSError:
        pass

    # Refresh climb report from exchange EV when possible
    try:
        from System import sifta_the_climb as climb

        climb.write_report(exchange_truth=report, state_dir=root)
    except Exception:
        pass

    return report


def main() -> int:
    r = rebuild_from_exchange(halt=True)
    print(
        json.dumps(
            {
                k: r.get(k)
                for k in (
                    "truth_label",
                    "stamp",
                    "network_ok",
                    "balance_usd",
                    "n_fills",
                    "n_settlements",
                    "total_realized_usd",
                    "live_ev_per_ticket",
                    "local_vs_exchange",
                    "usd_halt",
                    "climb_hint",
                )
            },
            indent=2,
        )
    )
    return 0 if r.get("network_ok") is not False or r.get("n_settlements") else 1


if __name__ == "__main__":
    raise SystemExit(main())
