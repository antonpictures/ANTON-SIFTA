#!/usr/bin/env python3
"""pump.fun strategy simulator — real P&L on real candles, zero risk.

Answers the only question that matters before money moves: over N launches, what
would a given exit rule have actually returned after fees?

Data. GeckoTerminal's public API serves OHLCV candle history for pump.fun pools
with no key, so price paths cost nothing. (PumpPortal's trade stream would work
too but needs a key funded with 0.02 SOL; it is not required for measurement.)

Honesty rules baked in:
  * Fees are charged on BOTH legs. Default 1% pump.fun buy + 1% sell, plus 0.5%
    PumpPortal commission on each leg = 3.0% per round trip, matching the fee
    schedule actually documented by both parties.
  * When one candle spans both the take-profit and the stop-loss level, the STOP
    is assumed to fill first. Assuming the good fill would flatter every result.
  * A token with no pool or no candles counts as a LOSS of the full ticket, not
    as a skipped trade, because a launch you cannot exit is the common outcome
    and dropping it would make every strategy look profitable.
  * Sample size is reported with every number. Small N is labelled noise, not
    presented as edge.

Usage:
  python3 tools/pumpfun_sim.py --sample 40 --ticket 2
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LAUNCHES = STATE / "pumpfun_launches.jsonl"
RESULTS = STATE / "pumpfun_sim_results.json"

GT = "https://api.geckoterminal.com/api/v2"
FEE_BUY = 0.01 + 0.005     # pump.fun 1% + PumpPortal local 0.5%
FEE_SELL = 0.01 + 0.005
ROUND_TRIP_FEE = FEE_BUY + FEE_SELL

STRATEGIES = {
    "scalp_tp25_sl30_t30": {"tp": 0.25, "sl": 0.30, "timeout_min": 30},
    "balanced_tp50_sl50_t60": {"tp": 0.50, "sl": 0.50, "timeout_min": 60},
    "moonshot_tp200_sl50_t240": {"tp": 2.00, "sl": 0.50, "timeout_min": 240},
    "hold_to_timeout_60": {"tp": None, "sl": None, "timeout_min": 60},
}


def _get(url: str, timeout: float = 20.0) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": "sifta-research/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "ignore"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def newest_launches(limit: int, min_dev_sol: float = 0.0, order: str = "newest") -> list[dict]:
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
        if r.get("mint"):
            rows.append(r)
    rows = [r for r in rows if float(r.get("dev_sol_in") or 0) >= min_dev_sol]
    # one row per mint, in the requested age order
    seen, out = set(), []
    for r in (rows if order == "oldest" else reversed(rows)):
        if r["mint"] in seen:
            continue
        seen.add(r["mint"])
        out.append(r)
        if len(out) >= limit:
            break
    return out


def candles_for(mint: str, timeout_min: int) -> list[list[float]] | None:
    """Pool + minute candles for one mint. None when there is no tradeable pool."""
    pools = _get(f"{GT}/networks/solana/tokens/{mint}/pools")
    data = (pools or {}).get("data") or []
    if not data:
        return None
    pool = (data[0].get("attributes") or {}).get("address")
    if not pool:
        return None
    limit = max(10, min(int(timeout_min) + 5, 1000))
    ohlcv = _get(f"{GT}/networks/solana/pools/{pool}/ohlcv/minute?aggregate=1&limit={limit}")
    series = (((ohlcv or {}).get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
    return series or None


def simulate(candles: list[list[float]], rule: dict) -> float:
    """Return the net multiple on the ticket (1.0 = break even, 0.0 = total loss)."""
    entry = float(candles[0][1])                      # open of the first candle
    if entry <= 0:
        return 0.0
    # cost basis includes the buy-side fee
    cost = entry * (1.0 + FEE_BUY)

    tp = rule.get("tp")
    sl = rule.get("sl")
    timeout = int(rule.get("timeout_min") or 60)
    tp_price = entry * (1.0 + tp) if tp else None
    sl_price = entry * (1.0 - sl) if sl else None

    for candle in candles[1:timeout + 1]:
        _ts, _o, high, low, close = (float(candle[0]), float(candle[1]), float(candle[2]),
                                     float(candle[3]), float(candle[4]))
        hit_sl = sl_price is not None and low <= sl_price
        hit_tp = tp_price is not None and high >= tp_price
        if hit_sl and hit_tp:
            # Both levels inside one candle: assume the STOP filled first.
            exit_price = sl_price
            return max(0.0, (exit_price * (1.0 - FEE_SELL)) / cost)
        if hit_sl:
            return max(0.0, (sl_price * (1.0 - FEE_SELL)) / cost)
        if hit_tp:
            return (tp_price * (1.0 - FEE_SELL)) / cost
        final_close = close
    else:
        final_close = float(candles[min(timeout, len(candles) - 1)][4])
    return max(0.0, (final_close * (1.0 - FEE_SELL)) / cost)


def bootstrap_ci(values: list[float], iters: int = 2000, alpha: float = 0.05) -> tuple[float, float]:
    if len(values) < 5:
        return (float("nan"), float("nan"))
    means = []
    n = len(values)
    for _ in range(iters):
        means.append(sum(random.choice(values) for _ in range(n)) / n)
    means.sort()
    return (means[int(iters * alpha / 2)], means[int(iters * (1 - alpha / 2))])


def main() -> int:
    ap = argparse.ArgumentParser(description="Simulate pump.fun strategies on real candles.")
    ap.add_argument("--sample", type=int, default=40, help="how many launches to replay")
    ap.add_argument("--ticket", type=float, default=2.0, help="dollars per trade")
    ap.add_argument("--min-dev-sol", type=float, default=0.0, help="only tokens whose dev bought at least this")
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between API calls (be polite)")
    ap.add_argument("--order", choices=("newest", "oldest"), default="newest",
                    help="oldest tests tokens that had time to reach a DEX pool")
    args = ap.parse_args()

    launches = newest_launches(args.sample, min_dev_sol=args.min_dev_sol, order=args.order)
    if not launches:
        print("no launches harvested yet — run tools/pumpfun_harvester.mjs first")
        return 1

    print(f"replaying {len(launches)} launches · ticket ${args.ticket} · "
          f"round-trip fee {ROUND_TRIP_FEE*100:.1f}%\n")

    per_strategy: dict[str, list[float]] = {k: [] for k in STRATEGIES}
    no_pool = 0
    traded = 0
    for i, launch in enumerate(launches, 1):
        candles = candles_for(launch["mint"], max(s["timeout_min"] for s in STRATEGIES.values()))
        if candles is None:
            no_pool += 1
            for k in per_strategy:          # cannot exit = total loss on the ticket
                per_strategy[k].append(0.0)
        else:
            traded += 1
            for k, rule in STRATEGIES.items():
                per_strategy[k].append(simulate(candles, rule))
        if i % 10 == 0:
            print(f"  {i}/{len(launches)} replayed (pools found: {traded}, none: {no_pool})")
        time.sleep(args.sleep)

    out = {
        "ts": time.time(),
        "sample": len(launches),
        "tokens_with_pool": traded,
        "tokens_without_pool": no_pool,
        "no_pool_rate": round(no_pool / len(launches), 4),
        "ticket_usd": args.ticket,
        "round_trip_fee_pct": ROUND_TRIP_FEE * 100,
        "strategies": {},
        "truth_label": "PUMPFUN_SIM_V1",
    }

    print(f"\n{'strategy':26s} {'N':>4s} {'mean mult':>10s} {'win%':>6s} "
          f"{'$ total':>9s} {'$ per trade':>11s}  95% CI (mean mult)")
    for name, mults in per_strategy.items():
        if not mults:
            continue
        mean = statistics.fmean(mults)
        wins = sum(1 for m in mults if m > 1.0) / len(mults) * 100
        total = (mean - 1.0) * args.ticket * len(mults)
        lo, hi = bootstrap_ci(mults)
        out["strategies"][name] = {
            "n": len(mults), "mean_multiple": round(mean, 4),
            "win_rate_pct": round(wins, 2),
            "total_usd": round(total, 2),
            "usd_per_trade": round((mean - 1.0) * args.ticket, 4),
            "ci95_mean_multiple": [None if lo != lo else round(lo, 4),
                                   None if hi != hi else round(hi, 4)],
            "survives_fees": mean > 1.0,
        }
        ci = "n/a (N<5)" if lo != lo else f"[{lo:.3f}, {hi:.3f}]"
        print(f"{name:26s} {len(mults):4d} {mean:10.3f} {wins:5.1f}% "
              f"{total:9.2f} {(mean-1.0)*args.ticket:11.4f}  {ci}")

    print(f"\ntokens with no pool (full loss by rule): {no_pool}/{len(launches)} "
          f"= {no_pool/len(launches)*100:.1f}%")
    verdict = ("NO STRATEGY SURVIVES FEES on this sample — do not deploy capital."
               if not any(v["survives_fees"] for v in out["strategies"].values())
               else "At least one strategy clears fees on this sample; N is small, treat as a lead not proof.")
    out["verdict"] = verdict
    print(f"\nVERDICT: {verdict}")
    if len(launches) < 200:
        print(f"NOTE: N={len(launches)} is far too small to call an edge. This run proves the "
              f"pipeline works, not that a strategy works.")
    RESULTS.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwritten: {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
