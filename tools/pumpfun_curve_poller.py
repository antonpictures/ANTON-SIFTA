#!/usr/bin/env python3
"""pump.fun curve poller — free price paths straight off the bonding curve.

The owner wanted no third party in the price path. This reads the pump.fun
bonding-curve account for each harvested token directly from Solana and records
its reserves over time, so a token's price history is reconstructed from the
chain itself.

Account layout (pump.fun bonding curve):
    offset  0 : 8-byte discriminator
    offset  8 : virtualTokenReserves (u64)   <- 6-decimal scaled
    offset 16 : virtualSolReserves   (u64)   <- lamports
    ...
Price (SOL per whole token) = (vSol / 1e9) / (vTok / 1e6)

One `getMultipleAccounts` call reads up to 100 curves, so the whole sample costs
a single request per tick. No API key, no fee, no third-party transaction, and
nothing is signed or sent.

Usage:
  python3 tools/pumpfun_curve_poller.py --minutes 3 --interval 10 --batch 30
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
PATHS = STATE / "pumpfun_curve_paths.jsonl"

RPC_URL = "https://api.mainnet-beta.solana.com"
SOL_DECIMALS = 1e9
TOKEN_DECIMALS = 1e6          # pump.fun tokens use 6 decimals


def rpc(method: str, params: list, timeout: float = 25.0) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def load_targets(batch: int, max_age_min: float) -> list[dict]:
    """Newest launches that have a curve key and are young enough to still be alive."""
    if not LAUNCHES.exists():
        return []
    now = time.time()
    seen, out = set(), []
    lines = LAUNCHES.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        mint = r.get("mint")
        key = r.get("bonding_curve_key")
        if not mint or not key or mint in seen:
            continue
        age_min = (now - float(r.get("ts") or now)) / 60.0
        if age_min > max_age_min:
            continue
        seen.add(mint)
        r["age_min"] = round(age_min, 2)
        out.append(r)
        if len(out) >= batch:
            break
    return out


def decode(account: dict | None) -> tuple[float, float] | None:
    if not account:
        return None
    try:
        raw = base64.b64decode(account["data"][0])
    except (KeyError, IndexError, TypeError):
        return None
    if len(raw) < 24:
        return None
    v_tok, v_sol = struct.unpack_from("<QQ", raw, 8)
    if v_tok == 0:
        return None
    return v_sol / SOL_DECIMALS, v_tok / TOKEN_DECIMALS


def main() -> int:
    ap = argparse.ArgumentParser(description="Poll pump.fun bonding curves for free price paths.")
    ap.add_argument("--minutes", type=float, default=3.0)
    ap.add_argument("--interval", type=float, default=10.0, help="seconds between ticks")
    ap.add_argument("--batch", type=int, default=30, help="tokens to track (max 100 per RPC call)")
    ap.add_argument("--max-age-min", type=float, default=20.0, help="only track tokens younger than this")
    args = ap.parse_args()

    targets = load_targets(min(args.batch, 100), args.max_age_min)
    if not targets:
        print("no targets: run tools/pumpfun_harvester.mjs longer so rows carry bonding_curve_key")
        return 1

    keys = [t["bonding_curve_key"] for t in targets]
    mint_of = {t["bonding_curve_key"]: t["mint"] for t in targets}
    sym_of = {t["mint"]: (t.get("symbol") or "?") for t in targets}
    curve_sol_of = {t["mint"]: float(t.get("dev_sol_in") or 0.0) for t in targets}

    print(f"tracking {len(targets)} curves · every {args.interval}s for {args.minutes} min")
    print(f"watching: {', '.join(sym_of[t['mint']] for t in targets[:8])} …\n")

    deadline = time.time() + args.minutes * 60
    ticks = 0
    points = 0
    alive: dict[str, list[tuple[float, float]]] = {}
    errors = 0

    while time.time() < deadline:
        t0 = time.time()
        try:
            res = rpc("getMultipleAccounts", [keys, {"encoding": "base64"}])
            values = ((res.get("result") or {}).get("value")) or []
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            errors += 1
            print(f"  tick {ticks}: rpc error {type(exc).__name__}")
            time.sleep(args.interval)
            continue

        ticks += 1
        now = time.time()
        moved = []
        for key, account in zip(keys, values):
            decoded = decode(account)
            if decoded is None:
                continue
            v_sol, v_tok = decoded
            price = v_sol / v_tok if v_tok else 0.0
            mint = mint_of.get(key)
            if not mint:
                continue
            alive.setdefault(mint, []).append((now, price))
            points += 1
            with PATHS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "ts": now,
                    "mint": mint,
                    "symbol": sym_of.get(mint),
                    "tick": ticks,
                    "v_sol": round(v_sol, 9),
                    "v_tok": round(v_tok, 6),
                    "price_sol": price,
                    "market_cap_sol": round(price * 1_073_000_000, 6),
                    "truth_label": "PUMPFUN_CURVE_POINT_V1",
                }) + "\n")
            moved.append((sym_of.get(mint), price))
        if ticks % 3 == 0:
            live = len([m for m in alive if len(alive[m]) > 1])
            print(f"  tick {ticks:3d}  accounts_read={len([v for v in values if v])}  "
                  f"points={points}  tokens_with_history={live}")
        time.sleep(max(0.0, args.interval - (time.time() - t0)))

    # what actually happened during the window
    print("\n=== window result ===")
    changes = []
    for mint, series in alive.items():
        if len(series) < 2:
            continue
        first, last = series[0][1], series[-1][1]
        if first > 0:
            changes.append((sym_of.get(mint), (last / first - 1) * 100, len(series)))
    changes.sort(key=lambda c: -c[1])
    for sym, pct, n in changes[:10]:
        print(f"  {str(sym)[:10]:11s} {pct:+8.2f}%   over {n} observations")
    if changes:
        winners = [c for c in changes if c[1] > 0]
        print(f"\n  tokens with usable history : {len(changes)}")
        print(f"  up over the window         : {len(winners)} ({len(winners)/len(changes)*100:.0f}%)")
        print(f"  median move                : {sorted(c[1] for c in changes)[len(changes)//2]:+.2f}%")
    out = {
        "ticks": ticks, "curve_points": points, "tokens_tracked": len(targets),
        "tokens_with_history": len(changes), "rpc_errors": errors,
        "interval_s": args.interval, "window_min": args.minutes,
        "paths_ledger": str(PATHS), "truth_label": "PUMPFUN_CURVE_POLL_V1",
    }
    print(f"\n{json.dumps(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
