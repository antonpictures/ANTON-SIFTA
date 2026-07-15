#!/usr/bin/env python3
"""r1684-b — Execution-grade read-only tape for 15m STGM lab.

Captures BBO / depth / quote age from public live marks (and optional REST
orderbook when available). Never imports order transmitters.

Truth: ALICE_15M_EXECUTION_TAPE_V1
Receipt: r1684-b-execution-tape
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
TRUTH = "ALICE_15M_EXECUTION_TAPE_V1"
RECEIPT = "r1684-b-execution-tape"
TAPE_NAME = "alice_15m_execution_tape.jsonl"
META_NAME = "alice_15m_execution_tape_meta.json"
# Never write secrets; public REST only for optional depth
PUBLIC_ORDERBOOK = "https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook"


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def window_id_from_ticker(ticker: str, *, secs_left: Optional[float] = None) -> str:
    """Stable-ish window id from ticker prefix (Kalshi embeds expiry in ticker)."""
    t = str(ticker or "").strip()
    if not t:
        return "unknown"
    # KXBTC15M-26JUL141645 → window key is the full ticker for 15m contracts
    return t


def complement_asks_from_bids(
    yes_bids: list[list[str]],
    no_bids: list[list[str]],
) -> dict[str, list[list[str]]]:
    """Binary market: best yes ask ≈ 1 − best no bid; best no ask ≈ 1 − best yes bid."""
    yes_asks: list[list[str]] = []
    no_asks: list[list[str]] = []
    for price_s, qty_s in no_bids:
        try:
            p = float(price_s)
            q = float(qty_s)
        except (TypeError, ValueError):
            continue
        yes_asks.append([f"{1.0 - p:.4f}", f"{q:.2f}"])
    for price_s, qty_s in yes_bids:
        try:
            p = float(price_s)
            q = float(qty_s)
        except (TypeError, ValueError):
            continue
        no_asks.append([f"{1.0 - p:.4f}", f"{q:.2f}"])
    yes_asks.sort(key=lambda x: float(x[0]))
    no_asks.sort(key=lambda x: float(x[0]))
    return {"yes_asks": yes_asks, "no_asks": no_asks}


def levels_from_bbo(
    yes_bid: Optional[float],
    yes_ask: Optional[float],
    *,
    bid_size: float = 1.0,
    ask_size: float = 1.0,
) -> dict[str, list[list[str]]]:
    """Synthesize one-level book from BBO when full depth is unavailable."""
    yes_bids: list[list[str]] = []
    no_bids: list[list[str]] = []
    if yes_bid is not None and float(yes_bid) > 0:
        yb = float(yes_bid)
        yes_bids.append([f"{yb:.4f}", f"{float(bid_size):.2f}"])
        # NO bid ≈ 1 − yes ask if ask known, else 1 − yes bid − tiny
        if yes_ask is not None and float(yes_ask) > 0:
            no_bids.append([f"{1.0 - float(yes_ask):.4f}", f"{float(ask_size):.2f}"])
        else:
            no_bids.append([f"{max(0.01, 1.0 - yb - 0.01):.4f}", f"{float(ask_size):.2f}"])
    elif yes_ask is not None and float(yes_ask) > 0:
        ya = float(yes_ask)
        no_bids.append([f"{1.0 - ya:.4f}", f"{float(ask_size):.2f}"])
        yes_bids.append([f"{max(0.01, ya - 0.01):.4f}", f"{float(bid_size):.2f}"])
    asks = complement_asks_from_bids(yes_bids, no_bids)
    return {"yes_bids": yes_bids, "no_bids": no_bids, **asks}


def append_tape_event(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    row = dict(row)
    row.setdefault("truth_label", TRUTH)
    row.setdefault("receipt_id", RECEIPT)
    row.setdefault("recv_ts_ms", int(time.time() * 1000))
    path = root / TAPE_NAME
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def _load_meta(root: Path) -> dict[str, Any]:
    p = root / META_NAME
    if not p.exists():
        return {
            "truth_label": TRUTH,
            "n_snapshots": 0,
            "n_gaps": 0,
            "last_recv_ts_ms": 0,
            "tickers_seen": {},
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"truth_label": TRUTH, "n_snapshots": 0, "n_gaps": 0}


def _save_meta(meta: dict[str, Any], *, root: Path) -> None:
    meta = dict(meta)
    meta["ts"] = time.time()
    meta["truth_label"] = TRUTH
    try:
        (root / META_NAME).write_text(
            json.dumps(meta, indent=2, sort_keys=True), encoding="utf-8"
        )
    except OSError:
        pass


def capture_from_live_marks(
    *,
    state_dir: Optional[Path | str] = None,
    gap_threshold_ms: int = 45_000,
) -> dict[str, Any]:
    """Append book_snapshot events from kalshi_15m_live.json BBO.

    This is the P0 bootstrap: bid/ask + secs + volume at monitor cadence.
    Full multi-level depth comes later via optional REST (never order path).
    """
    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    live_path = root / "kalshi_15m_live.json"
    if not live_path.exists():
        return {"ok": False, "reason": "no_live_marks", "n": 0}

    try:
        data = json.loads(live_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "reason": f"live_parse:{type(exc).__name__}", "n": 0}

    meta = _load_meta(root)
    now_ms = int(time.time() * 1000)
    last = int(meta.get("last_recv_ts_ms") or 0)
    gap = False
    if last > 0 and (now_ms - last) > int(gap_threshold_ms):
        gap = True
        meta["n_gaps"] = int(meta.get("n_gaps") or 0) + 1
        append_tape_event(
            {
                "event": "gap",
                "gap_ms": now_ms - last,
                "recv_ts_ms": now_ms,
                "source": "monitor_cadence",
            },
            state_dir=root,
        )

    markets = data.get("markets") or []
    n = 0
    tickers = dict(meta.get("tickers_seen") or {})
    for m in markets:
        if not isinstance(m, dict):
            continue
        ticker = str(m.get("kalshi_ticker") or m.get("ticker") or "").strip()
        if not ticker:
            continue
        yes = m.get("kalshi_yes")
        if yes is None:
            yes = m.get("yes_price")
        if yes is None:
            continue
        yes_f = float(yes)
        yb = m.get("yes_bid")
        ya = m.get("yes_ask")
        yb_f = float(yb) if yb not in (None, "") else None
        ya_f = float(ya) if ya not in (None, "") else None
        # if only mid, synthesize ±1¢ book so sim has something conservative
        if yb_f is None and ya_f is None:
            yb_f = max(0.01, yes_f - 0.01)
            ya_f = min(0.99, yes_f + 0.01)
        levels = levels_from_bbo(yb_f, ya_f, bid_size=1.0, ask_size=1.0)
        secs = m.get("seconds_to_close")
        try:
            secs_f = float(secs) if secs is not None else None
        except (TypeError, ValueError):
            secs_f = None
        vol = m.get("kalshi_volume_24h") or m.get("volume") or 0
        try:
            vol_f = float(vol)
        except (TypeError, ValueError):
            vol_f = 0.0
        asset = str(m.get("asset") or "")
        wid = window_id_from_ticker(ticker, secs_left=secs_f)
        feature_hash = hashlib.sha256(
            f"{ticker}|{yes_f}|{yb_f}|{ya_f}|{secs_f}|{vol_f}".encode()
        ).hexdigest()[:16]
        append_tape_event(
            {
                "event": "book_snapshot",
                "ticker": ticker,
                "window_id": wid,
                "asset": asset,
                "exchange_ts_ms": None,  # not available from live json
                "recv_ts_ms": now_ms,
                "seq": int(meta.get("n_snapshots") or 0) + n + 1,
                "yes_mid": round(yes_f, 4),
                "yes_bids": levels["yes_bids"],
                "no_bids": levels["no_bids"],
                "yes_asks": levels.get("yes_asks") or [],
                "no_asks": levels.get("no_asks") or [],
                "trade_price": None,
                "trade_size": None,
                "seconds_left": secs_f,
                "volume_24h": vol_f,
                "quote_age_ms": 0 if not gap else (now_ms - last),
                "feature_hash": feature_hash,
                "source": "kalshi_rest_via_live_marks",
                "depth_levels": 1,
                "depth_quality": "bbo_synthetic" if m.get("yes_bid") in (None, "") else "bbo",
            },
            state_dir=root,
        )
        tickers[ticker] = int(tickers.get(ticker) or 0) + 1
        n += 1

    meta["n_snapshots"] = int(meta.get("n_snapshots") or 0) + n
    meta["last_recv_ts_ms"] = now_ms
    meta["tickers_seen"] = tickers
    meta["last_gap"] = gap
    meta["usd_orders"] = "NEVER"
    _save_meta(meta, root=root)
    return {
        "ok": True,
        "event": "tape_capture",
        "n": n,
        "gap": gap,
        "n_snapshots_total": meta["n_snapshots"],
        "n_gaps": meta.get("n_gaps"),
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "usd": "NEVER",
    }


def load_tape(
    *,
    state_dir: Optional[Path | str] = None,
    ticker: Optional[str] = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    root = _state(state_dir)
    path = root / TAPE_NAME
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(o, dict):
                    continue
                if ticker and str(o.get("ticker") or "") != ticker:
                    continue
                out.append(o)
                if len(out) >= limit:
                    break
    except OSError:
        return []
    return out


def tape_coverage_report(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Coverage stats for Phase B acceptance (sample completeness)."""
    root = _state(state_dir)
    meta = _load_meta(root)
    rows = load_tape(state_dir=root, limit=200_000)
    snaps = [r for r in rows if str(r.get("event")) == "book_snapshot"]
    windows = {str(r.get("window_id") or r.get("ticker") or "") for r in snaps}
    gaps = [r for r in rows if str(r.get("event")) == "gap"]
    return {
        "ok": True,
        "n_snapshots": len(snaps),
        "n_windows_seen": len(windows),
        "n_gaps": len(gaps),
        "meta": meta,
        "truth_label": TRUTH,
        "receipt_id": RECEIPT,
        "phase_b_ready": len(windows) >= 100 and len(gaps) / max(1, len(snaps)) < 0.05,
        "usd": "NEVER",
    }


if __name__ == "__main__":
    print(json.dumps(capture_from_live_marks(), indent=2, default=str)[:2000])
