#!/usr/bin/env python3
"""Ticker daemon (N2 extended): fetch prices and append world_fact traces in a loop."""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

from System.swarm_world_awareness import append_trace

_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
LOG = _STATE / "ticker.log"

_INTERVAL = 300  # seconds between updates

def fetch_price(symbol: str) -> str:
    """Fetch price for a single symbol. Falls back gracefully on failure."""
    clean = symbol.upper().strip()
    # Try Binance first (more reliable)
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={clean}USD"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            if isinstance(data, dict) and "lastPrice" in data:
                return f"{clean}: ${float(data['lastPrice']):,.2f}"
    except Exception:
        pass
    # Try CoinGecko
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={clean.lower()}&vs_currencies=usd"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            if clean.lower() in data and "usd" in data[clean.lower()]:
                return f"{clean}: ${data[clean.lower()]['usd']:,.2f}"
    except Exception:
        pass
    return f"{clean}: ${'--'}"

def fetch_market_snapshot() -> str:
    """Fetch a snapshot of multiple tickers."""
    symbols = ["BTC", "ETH", "SOL", "DOGE"]
    prices = [fetch_price(s) for s in symbols]
    return "; ".join(prices)

def append_market_snapshot() -> None:
    """Append market snapshot to ledger."""
    text = fetch_market_snapshot()
    append_trace(
        source="ticker",
        kind="world_fact",
        text=f"MARKET: {text}",
        receipt_url="https://coinmarketcap.com",
    )
    with LOG.open("a") as f:
        f.write(f"{time.time()} {text}\n")

def main() -> None:
    """Daemon loop."""
    print(f"Ticker daemon starting (interval={_INTERVAL}s)...", flush=True)
    try:
        while True:
            append_market_snapshot()
            print(f"Ticker updated at {time.ctime()}", flush=True)
            time.sleep(_INTERVAL)
    except KeyboardInterrupt:
        print("Ticker daemon stopped by user.", flush=True)
    except Exception as e:
        print(f"Ticker daemon error: {e}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
