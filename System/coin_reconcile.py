#!/usr/bin/env python3
"""coin_reconcile.py — Test C: forecast → act → reconcile, hash-chained to the ledger."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from System.swarm_world_awareness import append_trace, read_traces


FORECAST_KIND = "forecast"
RECONCILE_KIND = "reconcile"


def publish_forecast(symbol: str, forecast: str) -> Dict[str, Any]:
    """Append a forecast trace (what Alice expects)."""
    return append_trace(
        source="alice",
        kind=FORECAST_KIND,
        text=f"{symbol}: {forecast}",
        extra={"symbol": symbol, "forecast": forecast},
    )


def publish_reconcile(symbol: str, actual: str, forecast: str) -> Dict[str, Any]:
    """Append a reconcile trace comparing actual vs forecast."""
    verdict = "MATCH" if actual == forecast else "DRIFT"
    return append_trace(
        source="web",
        kind=RECONCILE_KIND,
        text=f"{symbol} forecast={forecast} actual={actual} -> {verdict}",
        extra={"symbol": symbol, "forecast": forecast, "actual": actual, "verdict": verdict},
    )


def reconcile_forecast(symbol: str, forecast: str, actual: str) -> Dict[str, Any]:
    """Run the full forecast→reconcile cycle and return the reconcile row."""
    publish_forecast(symbol, forecast)
    return publish_reconcile(symbol, actual, forecast)


def last_forecast_for(symbol: str) -> Optional[Dict[str, Any]]:
    """Return the most recent forecast trace for a symbol, or None."""
    for row in read_traces(limit=200):
        if row.get("kind") == FORECAST_KIND and (row.get("extra") or {}).get("symbol") == symbol:
            return row
    return None


def main() -> None:
    symbol = "BTC"
    forecast = "UP"   # placeholder — a real forecast would come from the fly/reflex layer
    actual = "UP"
    row = reconcile_forecast(symbol, forecast, actual)
    verdict = (row.get("extra") or {}).get("verdict")
    print(json.dumps({"symbol": symbol, "verdict": verdict, "ts": time.time()}))


if __name__ == "__main__":
    main()
