#!/usr/bin/env python3
"""pump.fun copy-trade tracker — follow wallets, detect what they buy, score it.

Why copy-trading. Measured on this body's own harvest, predicting WHICH token
wins failed: buying every launch returned -12.88%, stop-loss variants stayed
negative, and the launch-time features we can see (dev's initial buy, starting
market cap, mayhem flag) did not separate winners from losers — the +58% winner
had a dev who put in 0.05 SOL while a dead token had a dev who put in 0.99.
So instead of predicting, follow someone who demonstrably wins.

Third-party-free. PumpPortal's account-trade stream needs a funded key, and the
owner rightly questioned trusting a third party with transaction building. This
reads the chain directly:

  1. `getSignaturesForAddress` per followed wallet (cheap, one call each)
  2. for NEW signatures, `getTransaction` and diff pre/postTokenBalances
  3. a mint the wallet did not hold before and holds after = a fresh entry

No key, no commission, nothing signed, nothing sent. Detection is inherently
after the fact — the whole point of the exercise is to measure the cost of that
latency, so it is recorded rather than hidden.

Ledger: COPY_WATCH_LEDGER (entries) and COPY_LATENCY_LEDGER (how late we saw it)
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
ENTRIES = STATE / "pumpfun_copy_entries.jsonl"
LATENCY = STATE / "pumpfun_copy_latency.jsonl"
WATCHLIST = STATE / "pumpfun_copy_watchlist.json"
LAUNCHES = STATE / "pumpfun_launches.jsonl"

RPC_URL = "https://api.mainnet-beta.solana.com"
TRUTH = "PUMPFUN_COPY_TRACK_V1"


def rpc(method: str, params: list, timeout: float = 25.0) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPC_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def wallets_that_launch_often(min_tokens: int, limit: int) -> list[str]:
    """Dev wallets from our own harvest that keep launching — a starting watchlist."""
    if not LAUNCHES.exists():
        return []
    counts: dict[str, int] = {}
    for line in LAUNCHES.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        dev = r.get("dev_wallet")
        if dev:
            counts[dev] = counts.get(dev, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [w for w, n in ranked if n >= min_tokens][:limit]


def load_watchlist() -> list[str]:
    if WATCHLIST.exists():
        try:
            data = json.loads(WATCHLIST.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [str(w) for w in data if w]
        except json.JSONDecodeError:
            pass
    return []


def save_watchlist(wallets: list[str]) -> None:
    WATCHLIST.write_text(json.dumps(sorted(set(wallets)), indent=2), encoding="utf-8")


def own_token_mints(tx: dict, wallet: str) -> tuple[set[str], set[str]]:
    """Mints the wallet held before and after, from the transaction's token balances."""
    meta = (tx.get("meta") or {})
    def mints(key: str) -> set[str]:
        out = set()
        for bal in (meta.get(key) or []):
            if bal.get("owner") == wallet and bal.get("mint"):
                out.add(bal["mint"])
        return out
    return mints("preTokenBalances"), mints("postTokenBalances")


def poll_wallet(wallet: str, state: dict, new_only: bool = True) -> list[dict]:
    """Return fresh entries for one wallet."""
    entries: list[dict] = []
    try:
        res = rpc("getSignaturesForAddress", [wallet, {"limit": 12}])
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return entries
    sigs = (res.get("result") or [])
    last_seen = state.get(wallet)
    fresh = []
    for s in sigs:
        sig = s.get("signature")
        if not sig:
            continue
        if new_only and last_seen and sig == last_seen:
            break
        fresh.append(s)
    if sigs:
        state[wallet] = sigs[0].get("signature")

    for s in fresh:
        sig = s.get("signature")
        try:
            txres = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            continue
        tx = txres.get("result")
        if not tx:
            continue
        pre, post = own_token_mints(tx, wallet)
        gained = post - pre
        if not gained:
            continue
        block_time = tx.get("blockTime")
        now = time.time()
        for mint in gained:
            latency_s = (now - float(block_time)) if block_time else None
            row = {
                "ts": now,
                "kind": "COPY_ENTRY",
                "wallet": wallet,
                "mint": mint,
                "signature": sig,
                "slot": tx.get("slot"),
                "block_time": block_time,
                "seen_after_s": round(latency_s, 2) if latency_s is not None else None,
                "truth_label": TRUTH,
            }
            entries.append(row)
            with ENTRIES.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            with LATENCY.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": now, "wallet": wallet, "mint": mint,
                                     "detection_latency_s": row["seen_after_s"]}) + "\n")
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description="Track wallets and detect their fresh entries.")
    ap.add_argument("--minutes", type=float, default=3.0)
    ap.add_argument("--interval", type=float, default=20.0)
    ap.add_argument("--min-tokens-launched", type=int, default=3,
                    help="seed the watchlist with dev wallets that launched at least this many tokens")
    ap.add_argument("--max-wallets", type=int, default=8)
    ap.add_argument("--wallet", action="append", default=[], help="add a specific wallet (repeatable)")
    ap.add_argument("--all-history", action="store_true", help="include the wallet's existing history")
    args = ap.parse_args()

    wallets = load_watchlist()
    if args.wallet:
        wallets += args.wallet
    if not wallets:
        wallets = wallets_that_launch_often(args.min_tokens_launched, args.max_wallets)
    wallets = sorted(set(w for w in wallets if w))[: args.max_wallets]
    if not wallets:
        print("no wallets to watch: harvest longer, or pass --wallet <address>")
        return 1
    save_watchlist(wallets)

    print(f"copy-watch: {len(wallets)} wallet(s), polling every {args.interval}s for {args.minutes} min")
    for w in wallets:
        print(f"  {w}")
    print()

    state: dict[str, str] = {}
    if not args.all_history:
        for w in wallets:                      # seed: ignore existing history
            try:
                res = rpc("getSignaturesForAddress", [w, {"limit": 1}])
                sigs = res.get("result") or []
                if sigs:
                    state[w] = sigs[0]["signature"]
            except Exception:
                pass

    deadline = time.time() + args.minutes * 60
    ticks = total = 0
    from_launch: list[dict] = []
    launch_mints = set()
    if LAUNCHES.exists():
        for line in LAUNCHES.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                launch_mints.add(json.loads(line).get("mint"))
            except json.JSONDecodeError:
                pass

    while time.time() < deadline:
        ticks += 1
        found = []
        for w in wallets:
            found += poll_wallet(w, state)
        if found:
            total += len(found)
            for e in found:
                tag = "IN OUR HARVEST" if e["mint"] in launch_mints else "not harvested"
                from_launch.append(e)
                print(f"  + [{e['wallet'][:6]}…] {e['mint'][:12]}…  "
                      f"detected {e['seen_after_s']}s after block  ({tag})")
        else:
            print(f"  tick {ticks}: no new entries")
        time.sleep(args.interval)

    lat = [e["seen_after_s"] for e in from_launch if e.get("seen_after_s") is not None]
    out = {
        "ticks": ticks, "wallets_watched": len(wallets), "entries_detected": total,
        "entries_in_our_harvest": sum(1 for e in from_launch if e["mint"] in launch_mints),
        "median_detection_latency_s": (sorted(lat)[len(lat)//2] if lat else None),
        "entries_ledger": str(ENTRIES), "watchlist": str(WATCHLIST),
        "truth_label": TRUTH,
    }
    print(f"\n{json.dumps(out, indent=1)}")
    if lat:
        print(f"\nDetection lag matters: median {out['median_detection_latency_s']}s after the block. "
              f"Copying means entering at least that late, and paying 3% to do it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
