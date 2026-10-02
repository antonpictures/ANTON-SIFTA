#!/usr/bin/env python3
"""
coin_ticker_loop.py — market ticker producer for stigmergicoin live card.

Fetches real crypto prices from a public API (CoinGecko, no key needed) and
appends world_fact traces to Alice's ledger. Runs as a long-lived daemon.

Usage:
    python3 System/coin_ticker_loop.py --interval 300  # every 5 minutes
    python3 System/coin_ticker_loop.py --once --symbols BTC,ETH,SOL
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_world_awareness import append_trace

# CoinGecko simple price endpoint (no API key, generous limits)
COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price"
DEFAULT_SYMBOLS = ("bitcoin", "ethereum", "solana", "dogecoin", "ripple")
SYMBOL_MAP = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "dogecoin": "DOGE",
    "ripple": "XRP",
}


def fetch_prices(ids: tuple[str, ...]) -> dict[str, float]:
    """Fetch USD prices for given CoinGecko IDs. Returns {symbol: price}."""
    params = {
        "ids": ",".join(ids),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{COINGECKO_API}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "SIFTA/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    out = {}
    for cg_id, info in data.items():
        sym = SYMBOL_MAP.get(cg_id, cg_id.upper())
        out[sym] = info.get("usd")
        # Include 24h change if available
        if "usd_24h_change" in info:
            out[f"{sym}_24h"] = round(info["usd_24h_change"], 2)
    return out


def format_ticker_line(prices: dict[str, float]) -> str:
    """Format a one-line ticker string for the trace text."""
    parts = []
    for sym in ("BTC", "ETH", "SOL", "DOGE", "XRP"):
        if sym in prices:
            p = prices[sym]
            change = prices.get(f"{sym}_24h")
            if change is not None:
                arrow = "▲" if change >= 0 else "▼"
                parts.append(f"{sym}: ${p:,.2f} ({arrow}{abs(change):.2f}%)")
            else:
                parts.append(f"{sym}: ${p:,.2f}")
    return " | ".join(parts)


def run_once(symbols: tuple[str, ...]) -> int:
    """Run one tick cycle. Returns number of traces appended (0 or 1)."""
    try:
        prices = fetch_prices(symbols)
        if not prices:
            print("[coin_ticker] no prices returned", file=sys.stderr)
            return 0
        text = format_ticker_line(prices)
        row = append_trace(
            source="web",
            kind="world_fact",
            text=text,
            confidence=0.95,
            extra={"prices": prices, "source": "coingecko"},
        )
        print(f"[coin_ticker] appended: {text}")
        return 1
    except urllib.error.HTTPError as exc:
        print(f"[coin_ticker] HTTP {exc.code}: {exc.reason}", file=sys.stderr)
    except Exception as exc:
        print(f"[coin_ticker] error: {exc}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Market ticker -> world_fact traces")
    ap.add_argument("--interval", type=int, default=300, help="Seconds between ticks (default 300)")
    ap.add_argument("--symbols", default="bitcoin,ethereum,solana,dogecoin,ripple", help="CoinGecko IDs, comma-separated")
    ap.add_argument("--once", action="store_true", help="Run one tick and exit")
    args = ap.parse_args()

    symbols = tuple(s.strip().lower() for s in args.symbols.split(",") if s.strip())
    print(f"[coin_ticker] symbols={symbols} interval={args.interval}s once={args.once}")

    if args.once:
        return 0 if run_once(symbols) > 0 else 1

    try:
        while True:
            run_once(symbols)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[coin_ticker] stopped")
        return 0


if __name__ == "__main__":
    sys.exit(main())