#!/usr/bin/env python3
"""pump.fun paper trader — risk nothing, run forever, find out if anything works.

Owner design (2026-10-01): put a FAKE portfolio next to the REAL one, start both
at the same amount, let the fake one trade continuously against live launches,
and when the fake one hits zero, refill it and keep going. The real account stays
untouched, ready for the day a trick is actually proven.

That is the correct shape for this problem, because it converts a losing hobby
into a measurement. Nothing here touches a key, signs anything, or sends a
transaction: the fake portfolio is arithmetic over real on-chain prices.

Rules, each traceable to something this body measured:
  * capital parity   - the fake starts at the same value as the real account
  * auto-refill      - a bust is DATA, recorded, then the fake is refilled
  * dev filter       - only first-time dev wallets, the one filter that survived
                       testing (-2.40% vs -18.75% for serial launchers)
  * real fees        - 3% round trip charged on every simulated trade
  * real prices      - entries and exits priced from the bonding curve on-chain

Ledger: PAPER_STATE (current portfolio) and PAPER_TRADES (every trade)
"""

from __future__ import annotations

import argparse
import base64
import json
import struct
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LAUNCHES = STATE / "pumpfun_launches.jsonl"
PAPER_STATE = STATE / "pumpfun_paper_state.json"
PAPER_TRADES = STATE / "pumpfun_paper_trades.jsonl"
REAL_STATE = STATE / "pumpfun_real_portfolio.json"

RPC_URL = "https://api.mainnet-beta.solana.com"
FEE = 0.03
DEFAULT_CAPITAL = 82.81          # the real account's observed value


def rpc(method: str, params: list, timeout: float = 25.0):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (json.loads(resp.read()) or {}).get("result")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def curve_prices(keys: list[str]) -> dict[str, float]:
    """SOL price per whole token for many curve accounts in ONE rpc call."""
    if not keys:
        return {}
    res = rpc("getMultipleAccounts", [keys[:100], {"encoding": "base64"}])
    values = (res or {}).get("value") or []
    out: dict[str, float] = {}
    for key, account in zip(keys, values):
        if not account:
            continue
        try:
            raw = base64.b64decode(account["data"][0])
            v_tok, v_sol = struct.unpack_from("<QQ", raw, 8)
            if v_tok:
                out[key] = (v_sol / 1e9) / (v_tok / 1e6)
        except (KeyError, IndexError, TypeError, struct.error):
            continue
    return out


def load_launches() -> list[dict]:
    if not LAUNCHES.exists():
        return []
    rows = []
    for line in LAUNCHES.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("mint") and r.get("bonding_curve_key"):
            rows.append(r)
    return rows


def dev_launch_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        d = r.get("dev_wallet")
        if d:
            counts[d] = counts.get(d, 0) + 1
    return counts


def load_state(capital: float) -> dict:
    if PAPER_STATE.exists():
        try:
            return json.loads(PAPER_STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {
        "initial_capital": capital, "cash": capital, "equity": capital,
        "positions": [], "opened": 0, "closed": 0, "busts": 0,
        "peak_equity": capital, "worst_equity": capital,
        "refills": [], "started_ts": time.time(),
        "truth_label": "PUMPFUN_PAPER_PORTFOLIO_V1",
    }


def save_state(state: dict) -> None:
    PAPER_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def real_portfolio() -> dict:
    """The real account: read on-chain, so it is never a guess."""
    wallet = "AEXXh8KkWfRvPxfhNu9PF4XLAmw9Wwsbhx4AhbYvPGRJ"
    lam = 0
    res = rpc("getBalance", [wallet])
    if isinstance(res, dict):
        lam = int(res.get("value") or 0)
    sol = lam / 1e9
    row = {
        "wallet": wallet,
        "sol": round(sol, 6),
        "usd_estimate": round(sol * 117.81, 2),
        "observed_ui_usd": 82.81,
        "note": "SOL read live from chain; the $82.81 is the platform UI figure",
        "ts": time.time(),
        "truth_label": "PUMPFUN_REAL_PORTFOLIO_V1",
    }
    REAL_STATE.write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


# SCALPING, per owner correction 2026-10-01: "enter and exit fast, this is not
# an investment waiting game, this is scalping all day." Measured on our own
# 84-token / 5,400-point sample, this scalping shape is the best-behaved one:
# in-and-out on a one-minute timeout, tight stop, modest take-profit.
TICKET = 2.00
STOP = 0.05
TAKE_PROFIT = 0.50
TIMEOUT_S = 60


def cycle(state: dict, *, ticket: float = TICKET, min_dev_tokens: int = 1) -> dict:
    """One paper-trading cycle: exit what is due, then enter new filtered launches."""
    rows = load_launches()
    counts = dev_launch_counts(rows)

    # Price ONLY what we act on: open positions plus the newest candidates that
    # pass the filter. Pricing an arbitrary first-100 slice is how the first
    # version silently opened zero trades.
    candidates = [r for r in reversed(rows) if r.get("bonding_curve_key")][:40]
    need = {p["curve_key"] for p in state["positions"]}
    need |= {r["bonding_curve_key"] for r in candidates}
    prices = curve_prices(sorted(need))
    now = time.time()
    still_open = []
    for pos in state["positions"]:
        p = prices.get(pos["curve_key"])
        if p is None:
            still_open.append(pos)
            continue
        change = p / pos["entry_price"] - 1 if pos["entry_price"] else 0.0
        exit_reason = None
        if change <= -STOP:
            exit_reason = "stop"
        elif TAKE_PROFIT is not None and change >= TAKE_PROFIT:
            exit_reason = "take_profit"
        elif pos["opened_ts"] + TIMEOUT_S <= now:
            exit_reason = "timeout"
        if exit_reason:
            proceeds = pos["size"] * (1 + change) * (1 - FEE)
            state["cash"] += max(0.0, proceeds)
            state["closed"] += 1
            with PAPER_TRADES.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "ts": now, "kind": "CLOSE", "mint": pos["mint"], "symbol": pos.get("symbol"),
                    "size": pos["size"], "entry_price": pos["entry_price"],
                    "exit_price": p, "change_pct": round(change * 100, 2),
                    "proceeds": round(proceeds, 4), "reason": exit_reason,
                    "truth_label": "PUMPFUN_PAPER_TRADE_V1",
                }) + "\n")
        else:
            pos["last_price"] = p
            pos["last_change"] = change
            still_open.append(pos)
    state["positions"] = still_open

    # 2. open new positions only from first-time devs (the surviving filter)
    taken = {p["mint"] for p in state["positions"]}
    entered = 0
    for r in candidates:
        if state["cash"] < ticket * 1.01:
            break
        mint = r["mint"]
        if mint in taken:
            continue
        dev = r.get("dev_wallet")
        if not dev or counts.get(dev, 0) > min_dev_tokens:
            continue                      # only first-time devs: the surviving filter
        key = r.get("bonding_curve_key")
        price = prices.get(key)
        if not price or price <= 0:
            continue
        state["cash"] -= ticket * (1 + FEE)
        state["opened"] += 1
        entered += 1
        pos = {"mint": mint, "symbol": r.get("symbol"), "curve_key": key,
               "size": ticket, "entry_price": price, "opened_ts": now, "dev": dev}
        state["positions"].append(pos)
        with PAPER_TRADES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": now, "kind": "OPEN", "mint": mint, "symbol": r.get("symbol"),
                "size": ticket, "entry_price": price, "dev": dev,
                "truth_label": "PUMPFUN_PAPER_TRADE_V1",
            }) + "\n")

    # 3. mark to market, and refill on bust (a bust is data, not a stop)
    open_value = sum(p["size"] * (1 + p.get("last_change", 0.0)) for p in state["positions"])
    state["equity"] = round(state["cash"] + open_value, 4)
    state["peak_equity"] = max(state["peak_equity"], state["equity"])
    state["worst_equity"] = min(state["worst_equity"], state["equity"])
    if state["equity"] <= 0.01 or state["cash"] < 0.01 and not state["positions"]:
        state["busts"] += 1
        state["refills"].append({"ts": now, "bust_number": state["busts"],
                                 "equity_at_bust": state["equity"]})
        state["cash"] = state["initial_capital"]
        state["equity"] = state["initial_capital"]
    state["last_cycle_ts"] = now
    state["entered_this_cycle"] = entered
    save_state(state)
    return state


def main() -> int:
    ap = argparse.ArgumentParser(description="Continuous paper trading against live pump.fun launches.")
    ap.add_argument("--minutes", type=float, default=0.0, help="0 = run forever")
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument("--capital", type=float, default=DEFAULT_CAPITAL)
    ap.add_argument("--ticket", type=float, default=TICKET)
    args = ap.parse_args()

    state = load_state(args.capital)
    real = real_portfolio()
    print(f"FAKE portfolio starts at ${state['initial_capital']:.2f} "
          f"(parity with the real account)")
    print(f"REAL account: {real['sol']:.4f} SOL ≈ ${real['usd_estimate']:.2f} — untouched\n")

    deadline = time.time() + args.minutes * 60 if args.minutes > 0 else None
    n = 0
    while deadline is None or time.time() < deadline:
        n += 1
        state = cycle(state, ticket=args.ticket)
        pos = state["positions"]
        print(f"[cycle {n}] equity ${state['equity']:.2f}  cash ${state['cash']:.2f}  "
              f"open {len(pos)}  opened {state['opened']}  closed {state['closed']}  "
              f"busts {state['busts']}  peak ${state['peak_equity']:.2f}")
        if pos:
            for p in pos[:3]:
                print(f"      {str(p.get('symbol'))[:12]:13s} {p.get('last_change',0)*100:+.1f}%")
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
