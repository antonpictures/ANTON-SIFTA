#!/usr/bin/env python3
"""Read-only Kalshi portfolio (George USD lane) — NO orders.

Uses credentials from kalshi_credentials.py.
**PRODUCTION ONLY** (George r1644). Demo host is not used.

Never prints secrets into chat/logs. Never places orders.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATE = ROOT / ".sifta_state"
CACHE = "kalshi_portfolio_cache.json"
LOG = "kalshi_portfolio_read.jsonl"

PROD_BASE = "https://external-api.kalshi.com/trade-api/v2"
PROD_HOST = "external-api.kalshi.com"
POSITIONS_SOURCE = "KALSHI_PROD_GET_/portfolio/positions"
POSITIONS_FRESH_SECONDS = 90.0
HISTORY_SOURCE = (
    "KALSHI_PROD_GET_/portfolio/fills+GET_/portfolio/settlements"
)
HISTORY_FRESH_SECONDS = 90.0

from System.kalshi_credentials import (  # noqa: E402
    credentials_status,
    load_api_key_id,
    load_private_key_pem,
)
from System.kalshi_demo_client import sign_request  # noqa: E402


def _base() -> str:
    """Always production Trade API. Demo is forbidden."""
    custom = (os.environ.get("SIFTA_KALSHI_READ_BASE") or "").strip()
    base = (custom or PROD_BASE).rstrip("/")
    parsed = urlparse(base)
    if (
        parsed.scheme.lower() != "https"
        or (parsed.hostname or "").lower() != PROD_HOST
        or parsed.path.rstrip("/") != "/trade-api/v2"
    ):
        raise RuntimeError(
            "r1648: Kalshi portfolio reads require exact production HTTPS host/path"
        )
    return base


def _log(row: dict[str, Any]) -> None:
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        with (STATE / LOG).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def _signed_get(path: str, *, timeout: float) -> dict[str, Any]:
    """Signed production GET. This module has no mutation/order method."""
    st = credentials_status()
    if not st["ready"]:
        return {
            "ok": False,
            "reason": st["note"],
            "credentials": st,
            "truth_label": "KALSHI_PORTFOLIO_READ_V2",
        }
    pem = load_private_key_pem()
    kid = load_api_key_id()
    assert pem and kid
    try:
        base = _base()
    except Exception as exc:
        return {"ok": False, "reason": f"base_fail:{type(exc).__name__}"}
    sign_path = urlparse(base + path).path
    ts = str(int(time.time() * 1000))
    try:
        sig = sign_request(pem, timestamp_ms=ts, method="GET", path=sign_path)
    except Exception as exc:
        return {"ok": False, "reason": f"sign_fail:{type(exc).__name__}"}
    headers = {
        "KALSHI-ACCESS-KEY": kid,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "Accept": "application/json",
        "User-Agent": "SIFTA-Alice-PortfolioRead/1.0 (read-only; no orders)",
    }
    url = base + path
    req = Request(url, headers=headers, method="GET")
    t0 = time.time()
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = getattr(resp, "status", 200)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300] if exc.fp else ""
        _log({"ts": time.time(), "status": exc.code, "error": body, "path": path})
        return {
            "ok": False,
            "reason": f"http_{exc.code}",
            "detail": body,
            "base_host": urlparse(base).hostname,
        }
    except URLError as exc:
        _log({"ts": time.time(), "error": str(exc.reason)[:120], "path": path})
        return {"ok": False, "reason": f"network:{exc.reason}"}

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {
            "ok": False,
            "reason": "invalid_json",
            "base_host": urlparse(base).hostname,
        }
    if not isinstance(data, dict):
        return {
            "ok": False,
            "reason": "invalid_payload",
            "base_host": urlparse(base).hostname,
        }
    return {
        "ok": True,
        "ts": time.time(),
        "ms": int((time.time() - t0) * 1000),
        "http_status": code,
        "base_host": urlparse(base).hostname,
        "payload": data,
        "truth_label": "KALSHI_PORTFOLIO_READ_V2",
    }


def _write_cache(cache: dict[str, Any]) -> None:
    """Atomically publish a non-secret read cache."""
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        path = STATE / CACHE
        tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def _cache_success(component: str, patch: dict[str, Any], *, ts: float) -> dict[str, Any]:
    cache = load_cache()
    cache.update(patch)
    cache.update(
        {
            f"{component}_ok": True,
            f"{component}_ts": ts,
            f"{component}_last_attempt_ts": ts,
            f"{component}_error": "",
            "truth_label": "KALSHI_PORTFOLIO_READ_V2",
        }
    )
    _write_cache(cache)
    return cache


def _cache_failure(component: str, result: dict[str, Any]) -> dict[str, Any]:
    """Record the failed attempt without erasing the last confirmed value."""
    cache = load_cache()
    attempted = time.time()
    reason = str(result.get("reason") or "read_failed")[:240]
    cache.update(
        {
            f"{component}_ok": False,
            f"{component}_last_attempt_ts": attempted,
            f"{component}_error": reason,
            "last_error": {"component": component, "reason": reason, "ts": attempted},
            "truth_label": "KALSHI_PORTFOLIO_READ_V2",
        }
    )
    _write_cache(cache)
    return cache


def fetch_balance(*, timeout: float = 12.0) -> dict[str, Any]:
    """GET /portfolio/balance — read only; preserves last-good cache on error."""
    read = _signed_get("/portfolio/balance", timeout=timeout)
    if not read.get("ok"):
        cache = _cache_failure("balance", read)
        out = dict(read)
        out["cache_preserved"] = "balance_usd" in cache
        out["cached_balance_usd"] = cache.get("balance_usd")
        return out
    data = read.pop("payload")
    # Prefer explicit dollars when Kalshi sends them; else cents integer → USD
    bal = data.get("balance")
    if bal is None and isinstance(data.get("portfolio_value"), (int, float)):
        bal = data.get("portfolio_value")
    dollars = data.get("balance_dollars")
    if dollars is not None:
        try:
            balance_usd: Optional[float] = round(float(dollars), 2)
        except (TypeError, ValueError):
            balance_usd = _to_usd(bal)
    else:
        balance_usd = _to_usd(bal)
    out = {
        "ok": True,
        "ts": read["ts"],
        "ms": read["ms"],
        "http_status": read["http_status"],
        "base_host": read["base_host"],
        "balance_raw": bal,
        "balance_usd": balance_usd,
        "payload_keys": list(data.keys())[:20] if isinstance(data, dict) else [],
        "truth_label": "KALSHI_PORTFOLIO_READ_V2",
        "note": "READ ONLY · no orders · George USD lane · STGM separate",
    }
    # keep a few more non-secret fields if present
    for k in ("updated_ts", "portfolio_value", "updated_time"):
        if k in data:
            out[k] = data[k]
    _cache_success(
        "balance",
        {
            # Legacy cache readers still use these top-level fields.
            "ok": True,
            "ts": out["ts"],
            "balance_raw": bal,
            "balance_usd": balance_usd,
            "balance_source": "KALSHI_PROD_GET_/portfolio/balance",
            "base_host": out["base_host"],
            "note": out["note"],
        },
        ts=float(out["ts"]),
    )
    _log({"ts": out["ts"], "ok": True, "balance_usd": out.get("balance_usd"), "ms": out["ms"]})
    return out


def _number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_exchange_positions(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    raw = payload.get("market_positions")
    if not isinstance(raw, list):
        raw = payload.get("positions")
    if not isinstance(raw, list):
        raw = []
    open_rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        # Kalshi's current schema uses fixed-point strings; retain the legacy
        # integer field fallback for older cached/test payloads.
        position = _number(
            item.get("position_fp")
            if item.get("position_fp") is not None
            else item.get("position")
        )
        # A confirmed zero is flat. A missing/unknown quantity is retained so
        # the glass cannot silently turn an unfamiliar API row into zero.
        if position == 0.0:
            continue
        row: dict[str, Any] = {
            "ticker": str(item.get("ticker") or ""),
            "position": position,
            "source": POSITIONS_SOURCE,
        }
        for key in (
            "market_exposure",
            "market_exposure_dollars",
            "realized_pnl",
            "realized_pnl_dollars",
            "total_traded",
            "total_traded_dollars",
            "resting_orders_count",
            "fees_paid",
            "fees_paid_dollars",
            "last_updated_ts",
        ):
            if key in item:
                row[key] = item[key]
        open_rows.append(row)
    return open_rows, len(raw)


def fetch_positions(*, timeout: float = 12.0) -> dict[str, Any]:
    """GET /portfolio/positions — confirmed exchange positions, read only."""
    read = _signed_get("/portfolio/positions", timeout=timeout)
    if not read.get("ok"):
        cache = _cache_failure("positions", read)
        out = dict(read)
        out["cache_preserved"] = "exchange_positions" in cache
        out["cached_positions_count"] = (
            len(cache.get("exchange_positions") or [])
            if "exchange_positions" in cache
            else None
        )
        return out
    payload = read.pop("payload")
    positions, raw_count = _normalize_exchange_positions(payload)
    ts = float(read["ts"])
    _cache_success(
        "positions",
        {
            "exchange_positions": positions,
            "exchange_positions_count": len(positions),
            "exchange_positions_raw_count": raw_count,
            "positions_source": POSITIONS_SOURCE,
            "positions_stale_after_seconds": POSITIONS_FRESH_SECONDS,
            "positions_payload_keys": list(payload.keys())[:20],
            "base_host": read["base_host"],
        },
        ts=ts,
    )
    out = {
        **read,
        "positions": positions,
        "positions_count": len(positions),
        "raw_count": raw_count,
        "source": POSITIONS_SOURCE,
    }
    _log(
        {
            "ts": ts,
            "ok": True,
            "path": "/portfolio/positions",
            "positions_count": len(positions),
            "ms": read["ms"],
        }
    )
    return out


def _campaign_orders(state_dir: Path | str = STATE) -> dict[str, str]:
    """Filled local order id → ticker; zero-fill IOC attempts are excluded."""
    root = Path(state_dir)
    path = root / "kalshi_usd_live_ledger.jsonl"
    orders: dict[str, str] = {}
    if not path.exists():
        return orders
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict) or row.get("event") != "usd_place":
            continue
        count = _number(row.get("fill_count"))
        # Legacy ``usd_place`` rows predate the explicit filled flag; they were
        # only written after an exchange fill. Explicit false/zero is a miss.
        if row.get("filled") is False or (count is not None and count <= 0.0):
            continue
        order_id = str(row.get("order_id") or "").strip()
        if order_id:
            orders[order_id] = str(row.get("ticker") or "")
    return orders


def _campaign_order_ids(state_dir: Path | str = STATE) -> set[str]:
    return set(_campaign_orders(state_dir))


def _window_key(ticker: str) -> str:
    parts = str(ticker or "").split("-", 1)
    return parts[1] if len(parts) == 2 else str(ticker or "")


def _clean_fill(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "fill_id": str(row.get("fill_id") or row.get("trade_id") or ""),
        "order_id": str(row.get("order_id") or ""),
        "ticker": str(row.get("ticker") or row.get("market_ticker") or ""),
        "side": str(row.get("side") or row.get("outcome_side") or "").lower(),
        "count": _number(row.get("count_fp") if row.get("count_fp") is not None else row.get("count")),
        "yes_price": _number(row.get("yes_price_dollars")),
        "no_price": _number(row.get("no_price_dollars")),
        "fee_usd": _number(row.get("fee_cost")) or 0.0,
        "ts": _number(row.get("ts")),
        "created_time": str(row.get("created_time") or ""),
    }


def _clean_settlement(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(row.get("ticker") or ""),
        "market_result": str(row.get("market_result") or "").lower(),
        "settled_time": str(row.get("settled_time") or ""),
        "revenue_cents": _number(row.get("revenue")),
        "fee_usd": _number(row.get("fee_cost")) or 0.0,
        "yes_count": _number(row.get("yes_count_fp")) or 0.0,
        "no_count": _number(row.get("no_count_fp")) or 0.0,
        "yes_total_cost_usd": _number(row.get("yes_total_cost_dollars")) or 0.0,
        "no_total_cost_usd": _number(row.get("no_total_cost_dollars")) or 0.0,
    }


def reconcile_exchange_history(
    fills: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    *,
    campaign_order_ids: Optional[set[str]] = None,
    campaign_orders: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Join Alice's fills to final exchange outcomes and calculate exact net PnL.

    Kalshi V2 exposes one YES book. The fill response therefore carries both
    ``yes_price_dollars`` and ``no_price_dollars``; this function always uses
    the selected side's explicit field and subtracts the fill's exact fee.
    """
    clean_fills = [_clean_fill(row) for row in fills if isinstance(row, dict)]
    clean_settlements = [
        _clean_settlement(row) for row in settlements if isinstance(row, dict)
    ]
    settlement_by_ticker = {
        row["ticker"]: row for row in clean_settlements if row.get("ticker")
    }
    order_map = dict(campaign_orders or {})
    selected_ids = set(campaign_order_ids or ()) | set(order_map)
    exchange_order_ids = {
        str(row.get("order_id") or "") for row in clean_fills if row.get("order_id")
    }
    fallback_tickers = {
        ticker
        for order_id, ticker in order_map.items()
        if order_id not in exchange_order_ids and ticker
    }
    campaign_fills = [
        row
        for row in clean_fills
        if (
            not selected_ids
            or row.get("order_id") in selected_ids
            or row.get("ticker") in fallback_tickers
        )
    ]
    matched_ids = {
        str(row.get("order_id") or "") for row in campaign_fills if row.get("order_id")
    }
    settled_rows: list[dict[str, Any]] = []
    unsettled: list[dict[str, Any]] = []
    for fill in campaign_fills:
        ticker = str(fill.get("ticker") or "")
        side = str(fill.get("side") or "").lower()
        count = max(0.0, float(fill.get("count") or 0.0))
        price = fill.get(f"{side}_price") if side in {"yes", "no"} else None
        settlement = settlement_by_ticker.get(ticker)
        if settlement is None or price is None or count <= 0.0:
            unsettled.append(
                {
                    "ticker": ticker,
                    "order_id": fill.get("order_id"),
                    "side": side,
                    "window": _window_key(ticker),
                    "reason": "settlement_missing" if settlement is None else "fill_fields_missing",
                }
            )
            continue
        side_price = float(price)
        fee = max(0.0, float(fill.get("fee_usd") or 0.0))
        won = str(settlement.get("market_result") or "") == side
        premium = round(side_price * count, 6)
        payout = round(count if won else 0.0, 6)
        pnl = round(payout - premium - fee, 6)
        settled_rows.append(
            {
                **fill,
                "window": _window_key(ticker),
                "selected_side_price": round(side_price, 6),
                "premium_usd": premium,
                "payout_usd": payout,
                "pnl_usd": pnl,
                "won": won,
                "market_result": settlement.get("market_result"),
                "settled_time": settlement.get("settled_time"),
                "price_convention": "selected_side_from_exchange_fill",
                "source": HISTORY_SOURCE,
            }
        )
    matched_tickers = {
        str(row.get("ticker") or "") for row in campaign_fills if row.get("ticker")
    }
    missing_ids = sorted(
        order_id
        for order_id in selected_ids
        if order_id not in matched_ids
        and (not order_map.get(order_id) or order_map[order_id] not in matched_tickers)
    )
    total_pnl = round(sum(float(row["pnl_usd"]) for row in settled_rows), 6)
    total_fees = round(sum(float(row["fee_usd"]) for row in settled_rows), 6)
    return {
        "truth_label": "KALSHI_EXCHANGE_RECONCILIATION_V1",
        "source": HISTORY_SOURCE,
        "rows": settled_rows,
        "unsettled": unsettled,
        "n_exchange_fills": len(clean_fills),
        "n_exchange_settlements": len(clean_settlements),
        "n_local_order_ids": len(selected_ids),
        "n_campaign_fills": len(campaign_fills),
        "n_settled_fills": len(settled_rows),
        "n_unsettled_fills": len(unsettled),
        "n_local_orders_missing_exchange_fill": len(missing_ids),
        "local_orders_missing_exchange_fill": missing_ids,
        "total_pnl_usd": total_pnl,
        "total_fees_usd": total_fees,
        "ev_per_fill_usd": (
            round(total_pnl / len(settled_rows), 6) if settled_rows else None
        ),
        "complete": not unsettled and not missing_ids,
    }


def fetch_exchange_history(*, timeout: float = 12.0) -> dict[str, Any]:
    """Refresh fills + settlements and publish fee-net exchange reconciliation."""
    fills_read = _signed_get("/portfolio/fills?limit=1000", timeout=timeout)
    settlements_read = _signed_get("/portfolio/settlements?limit=1000", timeout=timeout)
    if not fills_read.get("ok") or not settlements_read.get("ok"):
        reason = " · ".join(
            str(row.get("reason") or "read_failed")
            for row in (fills_read, settlements_read)
            if not row.get("ok")
        )
        cache = _cache_failure("history", {"reason": reason})
        return {
            "ok": False,
            "reason": reason,
            "cache_preserved": "exchange_reconciliation" in cache,
        }
    fills_payload = fills_read.get("payload") or {}
    settlements_payload = settlements_read.get("payload") or {}
    fills = fills_payload.get("fills") or []
    settlements = settlements_payload.get("settlements") or []
    if not isinstance(fills, list) or not isinstance(settlements, list):
        cache = _cache_failure("history", {"reason": "invalid_history_payload"})
        return {
            "ok": False,
            "reason": "invalid_history_payload",
            "cache_preserved": "exchange_reconciliation" in cache,
        }
    reconciliation = reconcile_exchange_history(
        fills,
        settlements,
        campaign_orders=_campaign_orders(),
    )
    paginated = bool(fills_payload.get("cursor") or settlements_payload.get("cursor"))
    if paginated:
        reconciliation["complete"] = False
        reconciliation["pagination_incomplete"] = True
    ts = min(float(fills_read["ts"]), float(settlements_read["ts"]))
    _cache_success(
        "history",
        {
            "exchange_reconciliation": reconciliation,
            "history_source": HISTORY_SOURCE,
            "history_stale_after_seconds": HISTORY_FRESH_SECONDS,
            "history_payload_counts": {
                "fills": len(fills),
                "settlements": len(settlements),
            },
        },
        ts=ts,
    )
    _log(
        {
            "ts": ts,
            "ok": True,
            "path": "/portfolio/fills+/portfolio/settlements",
            "n_settled_fills": reconciliation["n_settled_fills"],
            "total_pnl_usd": reconciliation["total_pnl_usd"],
        }
    )
    return {"ok": True, "ts": ts, "reconciliation": reconciliation}


def fetch_fills(*, limit: int = 200, timeout: float = 15.0) -> dict[str, Any]:
    """GET /portfolio/fills — exchange fill tape (read only). Never places orders."""
    lim = max(1, min(1000, int(limit)))
    path = f"/portfolio/fills?limit={lim}"
    read = _signed_get(path, timeout=timeout)
    if not read.get("ok"):
        return read
    payload = read.pop("payload") if "payload" in read else {}
    raw = payload.get("fills") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        raw = []
    fills: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        fills.append(dict(item))
    ts = float(read.get("ts") or time.time())
    _cache_success(
        "fills",
        {
            "exchange_fills": fills[:50],
            "exchange_fills_count": len(fills),
            "fills_source": "KALSHI_PROD_GET_/portfolio/fills",
            "fills_stale_after_seconds": POSITIONS_FRESH_SECONDS,
            "base_host": read.get("base_host"),
        },
        ts=ts,
    )
    out = {
        **read,
        "fills": fills,
        "fills_count": len(fills),
        "source": "KALSHI_PROD_GET_/portfolio/fills",
        "cursor": (payload or {}).get("cursor"),
    }
    _log({"ts": ts, "ok": True, "path": path, "fills_count": len(fills), "ms": read.get("ms")})
    return out


def fetch_settlements(*, limit: int = 200, timeout: float = 15.0) -> dict[str, Any]:
    """GET /portfolio/settlements — exchange settlement tape (read only)."""
    lim = max(1, min(1000, int(limit)))
    path = f"/portfolio/settlements?limit={lim}"
    read = _signed_get(path, timeout=timeout)
    if not read.get("ok"):
        return read
    payload = read.pop("payload") if "payload" in read else {}
    raw = payload.get("settlements") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        raw = []
    settlements: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        settlements.append(dict(item))
    ts = float(read.get("ts") or time.time())
    _cache_success(
        "settlements",
        {
            "exchange_settlements": settlements[:50],
            "exchange_settlements_count": len(settlements),
            "settlements_source": "KALSHI_PROD_GET_/portfolio/settlements",
            "settlements_stale_after_seconds": POSITIONS_FRESH_SECONDS,
            "base_host": read.get("base_host"),
        },
        ts=ts,
    )
    out = {
        **read,
        "settlements": settlements,
        "settlements_count": len(settlements),
        "source": "KALSHI_PROD_GET_/portfolio/settlements",
        "cursor": (payload or {}).get("cursor"),
    }
    _log(
        {
            "ts": ts,
            "ok": True,
            "path": path,
            "settlements_count": len(settlements),
            "ms": read.get("ms"),
        }
    )
    return out


def fetch_portfolio(*, timeout: float = 12.0) -> dict[str, Any]:
    """Refresh cash, positions, and fee-net history with read-only GETs."""
    balance = fetch_balance(timeout=timeout)
    positions = fetch_positions(timeout=timeout)
    history = fetch_exchange_history(timeout=timeout)
    cache = load_cache()
    return {
        "ok": bool(balance.get("ok") and positions.get("ok")),
        "balance": balance,
        "positions": positions,
        "history": history,
        "history_ok": bool(history.get("ok")),
        "balance_usd": (
            balance.get("balance_usd")
            if balance.get("ok")
            else cache.get("balance_usd")
        ),
        "positions_count": (
            positions.get("positions_count")
            if positions.get("ok")
            else positions.get("cached_positions_count")
        ),
        "reason": " · ".join(
            str(r.get("reason"))
            for r in (balance, positions)
            if not r.get("ok") and r.get("reason")
        ),
        "truth_label": "KALSHI_PORTFOLIO_READ_V2",
    }


def _to_usd(bal: Any) -> Optional[float]:
    if bal is None:
        return None
    try:
        v = float(bal)
    except (TypeError, ValueError):
        return None
    # Heuristic: Kalshi often uses cents integer
    if abs(v) >= 100 and v == int(v):
        return round(v / 100.0, 2)
    return round(v, 2)


def load_cache() -> dict[str, Any]:
    p = STATE / CACHE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def cache_status(
    cache: Optional[dict[str, Any]] = None,
    *,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """Pure freshness/provenance view; never performs a network read."""
    data = dict(cache if cache is not None else load_cache())
    clock = float(time.time() if now is None else now)

    def _component(name: str, value_key: str, source_key: str) -> dict[str, Any]:
        last_good = _number(data.get(f"{name}_ts"))
        # V1 balance caches used top-level ``ts``; it is still a confirmed
        # production read and remains valid during the V2 schema transition.
        if last_good is None and name == "balance" and value_key in data:
            last_good = _number(data.get("ts"))
        age = max(0.0, clock - last_good) if last_good is not None else None
        stale_after = _number(data.get(f"{name}_stale_after_seconds"))
        if stale_after is None:
            stale_after = POSITIONS_FRESH_SECONDS
        known = last_good is not None and value_key in data
        value = data.get(value_key) if known else None
        count = len(value) if known and isinstance(value, list) else None
        return {
            "known": known,
            "fresh": bool(known and age is not None and age <= stale_after),
            "age_seconds": age,
            "last_good_ts": last_good,
            "last_attempt_ok": data.get(f"{name}_ok"),
            "last_attempt_ts": _number(data.get(f"{name}_last_attempt_ts")),
            "error": str(data.get(f"{name}_error") or ""),
            "source": str(
                data.get(source_key)
                or (
                    "KALSHI_PROD_GET_/portfolio/balance"
                    if name == "balance" and known
                    else ""
                )
            ),
            "value": value,
            "count": count,
        }

    return {
        "balance": _component("balance", "balance_usd", "balance_source"),
        "positions": _component(
            "positions", "exchange_positions", "positions_source"
        ),
        "history": _component(
            "history", "exchange_reconciliation", "history_source"
        ),
        "truth_label": "KALSHI_PORTFOLIO_READ_V2",
    }


def main() -> int:
    print(json.dumps({"credentials": credentials_status()}, indent=2))
    r = fetch_portfolio()
    # never print full payload if it somehow included secrets
    safe = {k: r.get(k) for k in r if k not in ("payload",)}
    print(json.dumps(safe, indent=2))
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
