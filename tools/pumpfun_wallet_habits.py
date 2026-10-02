#!/usr/bin/env python3
"""pump.fun wallet habits — find the wallets that are early on winners.

Owner's thesis, and it is the right one: "it's all math, we learn their habits.
I bet there are some guys, 100 or maybe 1000 not more, who learned tricks."

Tokens cannot tell you which token wins. WALLETS can. So instead of profiling
launches, this profiles the people: for a token whose outcome we already know,
find who bought in its first transactions, then score each wallet by what the
tokens it entered actually did.

Method, all free and chain-direct:
  1. for a token, list its signatures and take the OLDEST ones (the launch block)
  2. for each early transaction, the SIGNERS are the wallets that acted
  3. record (wallet, mint, seconds_after_first_tx, outcome_of_that_token)
  4. aggregate: which wallets recur, and are their tokens above average?

The honest failure mode is stated up front: with small samples most wallets
appear once, and a wallet with one lucky token is indistinguishable from skill.
The report says so instead of hiding it, and reports how many wallets clear a
two-or-more-entry bar.

Ledger: WALLET_HABITS (raw entries) and WALLET_SCORES (leaderboard)
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LAUNCHES = STATE / "pumpfun_launches.jsonl"
PATHS = STATE / "pumpfun_curve_paths.jsonl"
ENTRIES = STATE / "pumpfun_wallet_habits.jsonl"
SCORES = STATE / "pumpfun_wallet_scores.json"

RPC_URL = "https://api.mainnet-beta.solana.com"
EARLY_TXS = 4                # how many of a token's first transactions to inspect
RPC_PACE_S = 2.0             # the public RPC 429s on bursts; it accepts ~2s spacing
MIN_ENTRIES = 2              # entries needed before a wallet is even rankable


def rpc(method: str, params: list, timeout: float = 25.0):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (json.loads(resp.read()) or {}).get("result")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def outcomes() -> dict[str, float]:
    """Known outcome per mint, from our own curve path ledger."""
    if not PATHS.exists():
        return {}
    per: dict[str, list[dict]] = collections.defaultdict(list)
    for line in PATHS.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        per[r["mint"]].append(r)
    out = {}
    for mint, pts in per.items():
        pts = sorted({p["ts"]: p for p in pts}.values(), key=lambda p: p["ts"])
        if len(pts) < 3:
            continue
        e = pts[0]["price_sol"]
        if e > 0:
            out[mint] = round((pts[-1]["price_sol"] / e - 1) * 100, 3)
    return out


def signers_of(tx: dict) -> list[str]:
    """The wallets that signed a transaction — i.e. those that acted in it."""
    keys = (((tx.get("transaction") or {}).get("message") or {}).get("accountKeys") or [])
    out = []
    for k in keys:
        if isinstance(k, dict) and k.get("signer") and k.get("pubkey"):
            out.append(k["pubkey"])
        elif isinstance(k, str):
            pass
    return out


def early_wallets(mint: str, curve_key: str | None = None) -> list[dict]:
    """The wallets acting in a token's first transactions, with how early.

    Query the BONDING CURVE account, not the mint: buys and sells touch the
    curve, and only the mint creation touches the mint. Querying the mint
    returns almost nothing, which is exactly what the first version did.
    """
    target = curve_key or mint
    sigs = rpc("getSignaturesForAddress", [target, {"limit": 40}])
    if not sigs:
        return []
    time.sleep(RPC_PACE_S)
    oldest = list(reversed(sigs))[:EARLY_TXS]        # oldest first = the launch
    first_time = None
    for s in oldest:
        if s.get("blockTime"):
            first_time = s["blockTime"]
            break
    found = []
    for s in oldest:
        sig = s.get("signature")
        if not sig:
            continue
        tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        if not tx:
            continue
        bt = tx.get("blockTime")
        delay = (bt - first_time) if (bt and first_time) else None
        for w in signers_of(tx):
            found.append({"wallet": w, "mint": mint, "signature": sig,
                          "seconds_after_first": delay})
        time.sleep(RPC_PACE_S)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="Profile early buyers and score wallets by outcome.")
    ap.add_argument("--sample", type=int, default=20, help="tokens to inspect")
    ap.add_argument("--min-outcome-known", action="store_true", default=True)
    args = ap.parse_args()

    oc = outcomes()
    launches = {}
    if LAUNCHES.exists():
        for line in LAUNCHES.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("mint"):
                launches[r["mint"]] = r

    # inspect a spread of outcomes, not just winners or just losers
    known = [(m, v) for m, v in oc.items() if m in launches]
    known.sort(key=lambda kv: kv[1])
    if len(known) < 4:
        print("not enough tokens with known outcomes yet — let the poller run longer")
        return 1
    half = max(1, args.sample // 2)
    sample = known[:half] + known[-half:]
    print(f"inspecting the launch blocks of {len(sample)} tokens "
          f"({half} worst, {half} best) · outcomes from our own curve ledger\n")

    entries = []
    for i, (mint, out) in enumerate(sample, 1):
        early = early_wallets(mint, launches.get(mint, {}).get("bonding_curve_key"))
        for e in early:
            e["outcome_pct"] = out
            e["symbol"] = launches.get(mint, {}).get("symbol")
            entries.append(e)
        if early:
            print(f"  {i:2d}/{len(sample)} {str(launches.get(mint,{}).get('symbol'))[:12]:13s} "
                  f"outcome {out:+8.2f}%  wallets in launch block: {len({e['wallet'] for e in early})}")

    with ENTRIES.open("a", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")

    by_wallet: dict[str, list[dict]] = collections.defaultdict(list)
    for e in entries:
        by_wallet[e["wallet"]].append(e)

    ranked = []
    for w, es in by_wallet.items():
        outs = [e["outcome_pct"] for e in es]
        delays = [e["seconds_after_first"] for e in es if e["seconds_after_first"] is not None]
        ranked.append({
            "wallet": w,
            "tokens_entered": len(es),
            "mean_outcome_pct": round(statistics.fmean(outs), 3),
            "median_outcome_pct": round(statistics.median(outs), 3),
            "best_pct": round(max(outs), 2),
            "worst_pct": round(min(outs), 2),
            "winners": sum(1 for o in outs if o > 3),
            "median_delay_s": round(statistics.median(delays), 1) if delays else None,
        })
    ranked.sort(key=lambda r: (-r["tokens_entered"], -r["mean_outcome_pct"]))
    SCORES.write_text(json.dumps(ranked, indent=2), encoding="utf-8")

    multi = [r for r in ranked if r["tokens_entered"] >= MIN_ENTRIES]
    print(f"\n=== WALLET LEADERBOARD ===")
    print(f"wallets seen in launch blocks : {len(ranked)}")
    print(f"wallets with >={MIN_ENTRIES} entries      : {len(multi)}   <-- only these are rankable")
    if multi:
        print(f"\n{'wallet':46s} {'tokens':>6s} {'mean%':>9s} {'median%':>9s} {'wins':>5s} {'delay s':>8s}")
        for r in multi[:12]:
            print(f"{r['wallet']:46s} {r['tokens_entered']:6d} {r['mean_outcome_pct']:+9.2f} "
                  f"{r['median_outcome_pct']:+9.2f} {r['winners']:5d} "
                  f"{'' if r['median_delay_s'] is None else r['median_delay_s']:>8}")
    all_outs = [e["outcome_pct"] for e in entries]
    if all_outs:
        print(f"\nbaseline: every token in this sample averaged {statistics.fmean(all_outs):+.2f}%")
    print(f"\nhonest limits: most wallets appear once, and one token is not a skill signal. "
          f"A wallet earns a rank only at >={MIN_ENTRIES} entries; treat the leaderboard as a "
          f"candidate list to watch, never as proof.")
    print(f"written: {ENTRIES.name}, {SCORES.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
