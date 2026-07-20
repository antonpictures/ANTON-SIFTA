#!/usr/bin/env python3
"""swarm_kalshi_public_feed.py — read-only Kalshi public market data.

Uses the unauthenticated Trade API market-data endpoints (no API key, no orders).
Docs: https://docs.kalshi.com/getting_started/quick_start_market_data

Honest:
  - This is NOT browser scraping of kalshi.com (Vercel challenge still blocks Alice Browser).
  - This does NOT place trades or touch the owner's Kalshi account.
  - Prices are for display / seed bias in the SIFTA sandbox game only.

Truth label: KALSHI_PUBLIC_FEED_V1
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

TRUTH_LABEL = "KALSHI_PUBLIC_FEED_V1"
BASE = "https://api.elections.kalshi.com/trade-api/v2"


def _get_json(path: str, *, timeout: float = 20.0) -> dict[str, Any]:
    url = f"{BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "SIFTA-Alice-StigmergicPredictions/1.0 (read-only market data)",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def _mid_yes(m: dict[str, Any]) -> Optional[float]:
    """YES probability in [0,1] from last / bid / ask dollars."""
    last = _f(m.get("last_price_dollars"), -1.0)
    bid = _f(m.get("yes_bid_dollars"), -1.0)
    ask = _f(m.get("yes_ask_dollars"), -1.0)
    candidates = [v for v in (last, bid, ask) if v >= 0.0]
    if not candidates:
        return None
    # prefer last if positive; else mid bid/ask
    if last > 0.0:
        return max(0.0, min(1.0, last))
    if bid >= 0.0 and ask > 0.0:
        return max(0.0, min(1.0, 0.5 * (bid + ask)))
    if bid >= 0.0:
        return max(0.0, min(1.0, bid))
    if ask >= 0.0:
        return max(0.0, min(1.0, ask))
    return None


def _title(m: dict[str, Any]) -> str:
    for k in ("title", "yes_sub_title", "no_sub_title", "subtitle"):
        t = str(m.get(k) or "").strip()
        if t and not t.lower().startswith("yes "):
            return t[:160]
    return str(m.get("ticker") or "market")[:80]


# Series that look like the Kalshi LIVE board (match winners, BTC clocks)
HEADLINE_SERIES = (
    "KXWCGAME",
    "KXWCSPREAD",
    "KXWCTOTAL",
    "KXMLBGAME",
    "KXUFCFIGHT",
    # Crypto clocks — mirror Kalshi Crypto sidebar (15m / hour / day / range)
    "KXBTC15M",
    "KXETH15M",
    "KXSOL15M",
    "KXXRP15M",
    "KXDOGE15M",
    "KXBNB15M",
    "KXHYPE15M",
    "KXSUI15M",
    "KXNEAR15M",
    "KXZEC15M",
    "KXBTCHOUR",
    "KXETHHOUR",
    "KXSOLHOUR",
    "KXBTCD",
    "KXETHD",
    "KXSOLD",
    "KXBTC",
    "KXETH",
    "KXSOL",
    "KXXRP",
    "KXDOGE",
    "KXBNB",
    "KXHYPE",
)

# Kalshi Crypto glass nav (same labels as kalshi.com Crypto sidebar)
CRYPTO_ASSETS = (
    "BTC",
    "ETH",
    "SOL",
    "XRP",
    "DOGE",
    "BNB",
    "HYPE",
    "NEAR",
    "ZEC",
    "SUI",
    "BCH",
    "LINK",
    "LTC",
)
TIMEFRAMES = (
    "15 Minute",
    "Hourly",
    "Daily",
    "Weekly",
    "Monthly",
    "Annual",
    "One Time",
)
NAV_SECTIONS = (
    "All markets",
    "Crypto",
    "Sports",
    "Elections",
    "Politics",
    "Culture",
    "Other",
)


def classify_market(ticker: str, title: str = "", event_ticker: str = "") -> dict[str, str]:
    """Map a Kalshi market to the same nav buckets as the Crypto UI glass.

    Returns nav_section, timeframe, asset, product (Predictions | Other).
    Perps are not on the public binary feed — product stays Predictions.
    """
    t = (ticker or "").upper()
    et = (event_ticker or "").upper()
    title_l = (title or "").lower()
    blob = f"{t} {et} {title_l}"

    asset = ""
    for a in CRYPTO_ASSETS:
        # ticker patterns: KXBTC15M, KXETH-, BTC in title
        if (
            f"KX{a}" in t
            or t.startswith(f"KX{a}")
            or f"-{a}-" in f"-{t}-"
            or f" {a.lower()} " in f" {title_l} "
            or title_l.startswith(f"{a.lower()} ")
            or f"{a.lower()} price" in title_l
            or f"{a.lower()} " in title_l[:20]
        ):
            asset = a
            break
    if not asset:
        for needle, a in (
            ("bitcoin", "BTC"),
            ("ethereum", "ETH"),
            ("solana", "SOL"),
            ("dogecoin", "DOGE"),
            ("ripple", "XRP"),
        ):
            if needle in title_l:
                asset = a
                break

    timeframe = "One Time"
    if "15M" in t or "15 min" in title_l or "next 15" in title_l:
        timeframe = "15 Minute"
    elif "HOUR" in t or "next hour" in title_l or "1 hour" in title_l or "hourly" in title_l:
        timeframe = "Hourly"
    elif (
        " today" in title_l
        or "at 5pm" in title_l
        or "at 8pm" in title_l
        or "at 9pm" in title_l
        or "this evening" in title_l
        or t.endswith("D")  # rough daily series like KXBTCD
        or "KXBTCD" in t
        or "KXETHD" in t
        or " price on " in title_l
        and "202" in title_l
        and "week" not in title_l
    ):
        # daily-ish clocks
        if "tomorrow" in title_l or "friday" in title_l or "monday" in title_l:
            timeframe = "Daily"
        elif "this week" in title_l or "weekly" in title_l:
            timeframe = "Weekly"
        elif "this month" in title_l or " in july" in title_l or "monthly" in title_l:
            timeframe = "Monthly"
        elif "this year" in title_l or "end of 20" in title_l or "eoy" in title_l or "annual" in title_l:
            timeframe = "Annual"
        else:
            timeframe = "Daily"
    elif "this week" in title_l or "weekly" in title_l:
        timeframe = "Weekly"
    elif "this month" in title_l or "monthly" in title_l or " in july" in title_l:
        timeframe = "Monthly"
    elif "this year" in title_l or "end of 20" in title_l or "annual" in title_l:
        timeframe = "Annual"
    elif "tomorrow" in title_l or "friday" in title_l:
        timeframe = "Daily"

    # section
    if asset or any(
        k in blob
        for k in (
            "BTC",
            "ETH",
            "SOL",
            "CRYPTO",
            "BITCOIN",
            "ETHEREUM",
            "SOLANA",
            "DOGE",
            "XRP",
            "HYPE",
        )
    ):
        nav_section = "Crypto"
    elif any(k in t for k in ("WC", "MLB", "UFC", "NFL", "NBA", "NHL", "SOCCER", "GAME")):
        nav_section = "Sports"
    elif "ELECTION" in t or "VOTE" in t or "NORWAY" in t or "PM" in t:
        nav_section = "Elections"
    elif "TRUMP" in t or "POLIT" in t or "CONGRESS" in t:
        nav_section = "Politics"
    elif any(k in title_l for k in ("movie", "song", "award", "grammy", "oscar")):
        nav_section = "Culture"
    else:
        nav_section = "Other"

    # Human category string matching Kalshi glass hierarchy
    if nav_section == "Crypto" and asset:
        category = f"Crypto · {timeframe} · {asset}"
    elif nav_section == "Crypto":
        category = f"Crypto · {timeframe}"
    else:
        category = nav_section

    return {
        "nav_section": nav_section,
        "timeframe": timeframe,
        "asset": asset,
        "product": "Predictions",
        "category": category,
    }


def _headline_boost(ticker: str, title: str) -> float:
    """Prefer match winners / clocks over 1% player props for glass parity."""
    t = (ticker or "").upper()
    title_l = (title or "").lower()
    boost = 1.0
    for s in HEADLINE_SERIES:
        if t.startswith(s + "-") or t.startswith(s):
            boost = max(boost, 8.0)
            break
    if "GAME" in t or "MATCH" in t:
        boost = max(boost, 6.0)
    if " winner" in title_l or "wins by" in title_l or "vs " in title_l:
        boost = max(boost, 5.0)
    if "price up" in title_l or "15 min" in title_l or "next hour" in title_l:
        boost = max(boost, 7.0)
    # demote pure player goal props a bit (still allowed if huge vol)
    if "GOAL-" in t and ":" in title and "1+" in title_l:
        boost *= 0.15
    return boost


def _normalize_market(m: dict[str, Any]) -> Optional[dict[str, Any]]:
    yes = _mid_yes(m)
    title = _title(m)
    ticker = str(m.get("ticker") or "").strip()
    if not ticker or yes is None or len(title) < 4:
        return None
    vol = max(_f(m.get("volume_24h_fp")), _f(m.get("volume_fp")))
    event_ticker = str(m.get("event_ticker") or "")
    nav = classify_market(ticker, title, event_ticker)
    # Kalshi glass: TO BEAT / target often lives in floor_strike or yes_sub_title
    floor = _f(m.get("floor_strike"), -1.0)
    target = floor if floor > 0 else 0.0
    yes_sub = str(m.get("yes_sub_title") or "")
    if target <= 0 and "target" in yes_sub.lower():
        # e.g. "Target Price: $63,828.91"
        import re

        mm = re.search(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)", yes_sub)
        if mm:
            try:
                target = float(mm.group(1).replace(",", ""))
            except Exception:
                pass
    yes_bid = _f(m.get("yes_bid_dollars"))
    yes_ask = _f(m.get("yes_ask_dollars"))
    no_bid = _f(m.get("no_bid_dollars"))
    no_ask = _f(m.get("no_ask_dollars"))
    return {
        "ticker": ticker,
        "title": title,
        "event_ticker": event_ticker,
        "status": str(m.get("status") or ""),
        "yes_price": round(float(yes), 4),
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "no_bid": no_bid,
        "no_ask": no_ask,
        "up_cents": int(round(float(yes) * 100)),
        "down_cents": int(round((1.0 - float(yes)) * 100)),
        "last_price": _f(m.get("last_price_dollars")),
        "volume_24h": round(vol, 2),
        "close_time": str(m.get("close_time") or m.get("expected_expiration_time") or ""),
        "open_time": str(m.get("open_time") or ""),
        "target_price": target,
        "floor_strike": floor if floor > 0 else 0.0,
        "yes_sub_title": yes_sub[:120],
        "rules": str(m.get("rules_primary") or m.get("rules") or "")[:240],
        "source": "kalshi_public_api",
        **nav,
    }


def _fetch_series_open(series_ticker: str, *, limit: int = 12, timeout: float = 12.0) -> list[dict]:
    try:
        qs = (
            f"limit={int(limit)}&status=open&mve_filter=exclude"
            f"&series_ticker={urllib.parse.quote(series_ticker)}"
        )
        data = _get_json(f"/markets?{qs}", timeout=timeout)
        batch = data.get("markets") or []
        return [m for m in batch if isinstance(m, dict)]
    except Exception:
        return []


def fetch_open_markets(
    *,
    pages: int = 3,
    page_size: int = 200,
    min_volume: float = 50.0,
    limit: int = 80,
    timeout: float = 18.0,
    headline_first: bool = True,
    crypto_first: bool = True,
) -> dict[str, Any]:
    """Pull open markets; crypto clocks + headline series first, then volume rest."""
    cursor: Optional[str] = None
    raw_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    pages = max(1, min(10, int(pages)))

    # 0) Always pull full 15-minute crypto strip (Kalshi shows ~9 open clocks)
    _15M_SERIES = (
        "KXBTC15M",
        "KXETH15M",
        "KXSOL15M",
        "KXXRP15M",
        "KXDOGE15M",
        "KXBNB15M",
        "KXHYPE15M",
        "KXSUI15M",
        "KXNEAR15M",
        "KXZEC15M",
        "KXBCH15M",
        "KXLINK15M",
        "KXLTC15M",
    )
    for st in _15M_SERIES:
        raw_rows.extend(_fetch_series_open(st, limit=8, timeout=min(timeout, 12.0)))

    # 1) Headline series (match the LIVE board feel: WC games, MLB, longer crypto)
    if headline_first:
        for st in HEADLINE_SERIES:
            if st in _15M_SERIES:
                continue  # already pulled
            raw_rows.extend(_fetch_series_open(st, limit=16, timeout=min(timeout, 14.0)))

    # 2) Broad open pages for volume heat
    for _ in range(pages):
        qs = f"limit={int(page_size)}&status=open&mve_filter=exclude"
        if cursor:
            qs += f"&cursor={urllib.parse.quote(str(cursor))}"
        try:
            data = _get_json(f"/markets?{qs}", timeout=timeout)
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            break
        batch = data.get("markets") or []
        if not isinstance(batch, list):
            break
        raw_rows.extend([m for m in batch if isinstance(m, dict)])
        cursor = data.get("cursor")
        if not cursor or not batch:
            break

    ranked: list[tuple[float, dict[str, Any]]] = []
    for m in raw_rows:
        row = _normalize_market(m)
        if not row:
            continue
        vol = float(row["volume_24h"])
        if vol < float(min_volume) and float(row["yes_price"]) <= 0.0:
            continue
        score = vol * _headline_boost(row["ticker"], row["title"])
        # slight preference for mid-range odds (more interesting glass)
        yp = float(row["yes_price"])
        if 0.08 <= yp <= 0.92:
            score *= 1.15
        # always keep full 15m crypto strip (Kalshi ~9) even if volume is quiet
        if str(row.get("timeframe") or "") == "15 Minute" and str(row.get("nav_section") or "") == "Crypto":
            score = max(score, 1e9)  # pin into board before volume cull
        ranked.append((score, row))

    ranked.sort(key=lambda x: -x[0])
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for _score, row in ranked:
        if row["ticker"] in seen:
            continue
        seen.add(row["ticker"])
        out.append(row)
        if len(out) >= int(limit):
            break

    return {
        "truth_label": TRUTH_LABEL,
        "ok": bool(out) and not (errors and not out),
        "ts": time.time(),
        "base": BASE,
        "fetched_raw": len(raw_rows),
        "markets": out,
        "errors": errors,
        "headline_series": list(HEADLINE_SERIES),
        "note": (
            "read-only public market data — no auth, no orders, no account; "
            "headline series boosted for LIVE-board parity; not Chrome trading"
        ),
    }


def fetch_by_tickers(tickers: list[str], *, timeout: float = 12.0) -> dict[str, Any]:
    """Refresh specific tickers (best-effort)."""
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for t in tickers:
        t = str(t or "").strip()
        if not t:
            continue
        try:
            data = _get_json(f"/markets/{urllib.parse.quote(t)}", timeout=timeout)
            m = data.get("market") if isinstance(data.get("market"), dict) else data
            if not isinstance(m, dict):
                continue
            row = _normalize_market(m)
            if not row:
                continue
            # keep requested ticker id if API omits
            if not row.get("ticker"):
                row["ticker"] = t
            rows.append(row)
        except Exception as exc:
            errors.append(f"{t}:{type(exc).__name__}")
    return {
        "truth_label": TRUTH_LABEL,
        "ok": bool(rows),
        "ts": time.time(),
        "markets": rows,
        "errors": errors,
    }


_15M_SERIES = (
    "KXBTC15M",
    "KXETH15M",
    "KXSOL15M",
    "KXXRP15M",
    "KXDOGE15M",
    "KXBNB15M",
    "KXHYPE15M",
    "KXSUI15M",
    "KXNEAR15M",
    "KXZEC15M",
    "KXBCH15M",
    "KXLINK15M",
    "KXLTC15M",
)


def fetch_15m_clocks(
    *,
    timeout: float = 12.0,
) -> dict[str, Any]:
    """Fetch all open 15-minute crypto clocks from Kalshi (read-only).

    Returns the live BTC/ETH/SOL/etc 15-min markets with target prices,
    close times, and current Kalshi odds — exactly what the auto-bet needs.
    """
    raw_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for st in _15M_SERIES:
        try:
            raw_rows.extend(_fetch_series_open(st, limit=4, timeout=timeout))
        except Exception as exc:
            errors.append(f"{st}:{type(exc).__name__}")

    clocks: list[dict[str, Any]] = []
    for m in raw_rows:
        row = _normalize_market(m)
        if not row:
            continue
        if str(row.get("timeframe") or "") != "15 Minute":
            continue
        clocks.append(row)

    clocks.sort(key=lambda r: float(r.get("volume_24h") or 0), reverse=True)

    return {
        "truth_label": TRUTH_LABEL,
        "ok": bool(clocks),
        "ts": time.time(),
        "clocks": clocks,
        "count": len(clocks),
        "errors": errors,
        "note": "read-only 15-minute crypto clocks from Kalshi public API",
    }


__all__ = [
    "TRUTH_LABEL",
    "BASE",
    "CRYPTO_ASSETS",
    "TIMEFRAMES",
    "NAV_SECTIONS",
    "classify_market",
    "fetch_open_markets",
    "fetch_by_tickers",
    "fetch_15m_clocks",
]
