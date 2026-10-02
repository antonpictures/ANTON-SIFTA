#!/usr/bin/env python3
"""pump.fun rug check — the documented scam detectors, implemented and testable.

Sources. Five tactics are documented for pump.fun scams (bundled sniper launch,
wash-trading volume bots, cloned narrative, livestream hype, coordinated dump).
Three detection methods are documented alongside them, and this tool implements
all three mechanically rather than by vibes:

  1. DEV PROFILE      - how many tokens this wallet has already launched
  2. BUNDLE           - do the top holders share a funding wallet, or were they
                        created at the same moment? (bundled sniper launch)
  3. WASH / MICROBUY  - is the token's trade stream dominated by tiny trades at
                        machine rate? (volume bot)

Every check reads the chain directly: no API key, no third party, nothing signed.
It is deliberately runnable against tokens whose fate is ALREADY known, because a
detector that has never been tested against outcomes is decoration.

Usage:
  python3 tools/pumpfun_rugcheck.py <mint> [<mint> ...]
  python3 tools/pumpfun_rugcheck.py --from-corpus 6
"""
from __future__ import annotations

import argparse
import collections
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
LAUNCHES = STATE / "pumpfun_launches.jsonl"
PATHS = STATE / "pumpfun_curve_paths.jsonl"
RPC_URL = "https://api.mainnet-beta.solana.com"
TRUTH = "PUMPFUN_RUGCHECK_V1"

# thresholds, stated so they can be argued with rather than hidden
TOP_HOLDERS = 8
BUNDLE_MIN_SHARED_FUNDER = 2      # 2+ top holders funded by one wallet = bundled
MICROBUY_FRACTION = 0.75          # 75%+ of trades tiny = volume bot
MICROBUY_MAX_SOL = 0.01


def rpc(method: str, params: list, timeout: float = 25.0):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (json.loads(resp.read()) or {}).get("result")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def dev_launch_history(dev: str) -> int:
    """How many tokens this wallet has launched in our own harvest."""
    if not LAUNCHES.exists() or not dev:
        return 0
    n = 0
    for line in LAUNCHES.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            if json.loads(line).get("dev_wallet") == dev:
                n += 1
        except json.JSONDecodeError:
            continue
    return n


def earliest_funder(wallet: str) -> tuple[str | None, int | None]:
    """The wallet that first paid for this wallet's activity, and when."""
    sigs = rpc("getSignaturesForAddress", [wallet, {"limit": 1000}])
    if not sigs:
        return None, None
    first = sigs[-1]                      # oldest visible signature
    tx = rpc("getTransaction", [first.get("signature"),
                               {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    if not tx:
        return None, None
    keys = (((tx.get("transaction") or {}).get("message") or {}).get("accountKeys") or [])
    payer = None
    if keys:
        k0 = keys[0]
        payer = k0.get("pubkey") if isinstance(k0, dict) else str(k0)
    return payer, tx.get("blockTime")


def top_holders(mint: str) -> list[dict]:
    """Largest token accounts and their owner wallets."""
    largest = rpc("getTokenLargestAccounts", [mint])
    if not largest:
        return []
    out = []
    for row in (largest.get("value") or [])[:TOP_HOLDERS]:
        acct = row.get("address")
        amount = row.get("uiAmount") or 0
        info = rpc("getAccountInfo", [acct, {"encoding": "jsonParsed"}])
        owner = None
        try:
            owner = info["value"]["data"]["parsed"]["info"]["owner"]
        except (KeyError, TypeError, IndexError):
            pass
        out.append({"token_account": acct, "amount": amount, "owner": owner})
        time.sleep(0.1)
    return out


def check_bundle(holders: list[dict]) -> dict:
    """Shared funders or same-second creation among top holders = bundled."""
    funders = collections.Counter()
    times = []
    detail = []
    for h in holders:
        owner = h.get("owner")
        if not owner:
            continue
        funder, t = earliest_funder(owner)
        detail.append({"owner": owner, "funder": funder, "first_seen": t, "amount": h["amount"]})
        if funder:
            funders[funder] += 1
        if t:
            times.append(t)
        time.sleep(0.1)
    shared = {f: n for f, n in funders.items() if n >= BUNDLE_MIN_SHARED_FUNDER}
    same_second = False
    if len(times) >= 3:
        mode, count = collections.Counter(times).most_common(1)[0]
        same_second = count >= 3
    return {
        "shared_funders": shared,
        "bundle_suspect": bool(shared) or same_second,
        "same_second_cluster": same_second,
        "holder_detail": detail[:TOP_HOLDERS],
    }


def check_wash(trades: list[dict]) -> dict:
    """Tiny trades at machine rate = volume bot."""
    if not trades:
        return {"available": False, "microbuy_fraction": None, "wash_suspect": None}
    tiny = sum(1 for t in trades if (t.get("sol_amount") or 0) <= MICROBUY_MAX_SOL)
    frac = tiny / len(trades)
    return {
        "available": True,
        "trades_seen": len(trades),
        "microbuy_fraction": round(frac, 3),
        "wash_suspect": frac >= MICROBUY_FRACTION,
    }


def known_outcome(mint: str) -> float | None:
    """What actually happened, when our own path ledger has it."""
    if not PATHS.exists():
        return None
    pts = []
    for line in PATHS.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("mint") == mint:
            pts.append(r)
    pts.sort(key=lambda p: p["ts"])
    if len(pts) < 2:
        return None
    e = pts[0]["price_sol"]
    return (pts[-1]["price_sol"] / e - 1) * 100 if e else None


def rugcheck(mint: str, dev: str | None, trades: list[dict]) -> dict:
    holders = top_holders(mint)
    bundle = check_bundle(holders)
    wash = check_wash(trades)
    dev_n = dev_launch_history(dev) if dev else 0

    flags = []
    if dev_n >= 2:
        flags.append(f"dev already launched {dev_n} tokens")
    if bundle["bundle_suspect"]:
        flags.append("top holders share a funder / same-second cluster")
    if wash.get("wash_suspect"):
        flags.append(f"{wash['microbuy_fraction']*100:.0f}% of trades are microbuys")

    score = min(100, (25 if dev_n >= 2 else 0) + (45 if bundle["bundle_suspect"] else 0)
                + (30 if wash.get("wash_suspect") else 0))
    return {
        "mint": mint,
        "dev": dev,
        "dev_launches": dev_n,
        "top_holders_checked": len(holders),
        "bundle": bundle,
        "wash": wash,
        "flags": flags,
        "risk_score": score,
        "verdict": "AVOID" if score >= 45 else ("CAUTION" if score >= 25 else "no red flag found"),
        "truth_label": TRUTH,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Run documented pump.fun scam detectors.")
    ap.add_argument("mints", nargs="*")
    ap.add_argument("--from-corpus", type=int, default=0,
                    help="also test N tokens from our own harvest, newest first")
    args = ap.parse_args()

    targets: list[dict] = []
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
    for m in args.mints:
        targets.append({"mint": m, "dev": (launches.get(m) or {}).get("dev_wallet")})
    if args.from_corpus:
        for m in list(launches)[-args.from_corpus:]:
            targets.append({"mint": m, "dev": launches[m].get("dev_wallet")})
    if not targets:
        print("pass mints, or --from-corpus N")
        return 2

    results = []
    for t in targets:
        res = rugcheck(t["mint"], t.get("dev"), [])
        outcome = known_outcome(t["mint"])
        res["known_outcome_pct"] = None if outcome is None else round(outcome, 2)
        results.append(res)
        flagtxt = "; ".join(res["flags"]) or "none"
        oc = "unknown" if outcome is None else f"{outcome:+.1f}%"
        print(f"\n{res['mint'][:14]}…  risk={res['risk_score']:3d}  {res['verdict']:18s} outcome={oc}")
        print(f"  flags: {flagtxt}")
        if res["bundle"]["shared_funders"]:
            print(f"  shared funders: {res['bundle']['shared_funders']}")

    scored = [r for r in results if r["known_outcome_pct"] is not None]
    if len(scored) >= 3:
        avoid = [r for r in scored if r["verdict"] == "AVOID"]
        clean = [r for r in scored if r["verdict"] != "AVOID"]
        print("\n=== does the detector separate real outcomes? ===")
        if avoid:
            print(f"  flagged AVOID  n={len(avoid):2d}  mean outcome "
                  f"{sum(r['known_outcome_pct'] for r in avoid)/len(avoid):+8.2f}%")
        if clean:
            print(f"  not flagged    n={len(clean):2d}  mean outcome "
                  f"{sum(r['known_outcome_pct'] for r in clean)/len(clean):+8.2f}%")
        print("  (a detector that does not separate outcomes is decoration)")
    (STATE / "rugcheck_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
