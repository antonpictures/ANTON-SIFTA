#!/usr/bin/env python3
"""r1695 / r1718 — Keep Alice's USD hand + TP in sync with exchange.

1) Import open Kalshi positions into night open **only if Alice placed them**
   (or tiny bot-sized bags). Owner manual / fat bags are NEVER imported for TP.
2) Retry dual-mirror for paper opens that never got a US$ fill.

r1718 owner: you bought YES toward the end — Alice imported ~23 ct and
force-flat sold red **twice** on your stash. Import-for-TP was the steal path.
Owner bags stay owner bags. Alice only manages what she placed under ammo.

Truth: ALICE_USD_POSITION_SYNC_V1
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".sifta_state"
TRUTH = "ALICE_USD_POSITION_SYNC_V1"
LOG = "alice_usd_position_sync.jsonl"
# r1718: never import fat owner bags into TP (ammo is $1 ≈ 1–2 contracts)
IMPORT_MAX_CONTRACTS = 2.5
# only re-attach positions Alice herself placed (ledger usd_place)
IMPORT_BOT_PLACED_ONLY = True


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _log(row: dict[str, Any], *, state_dir: Path) -> None:
    row = dict(row)
    row.setdefault("ts", time.time())
    row.setdefault("truth_label", TRUTH)
    try:
        with (state_dir / LOG).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        pass


def _asset_from_ticker(ticker: str) -> str:
    t = str(ticker or "").upper()
    # KXBTC15M-... KXETH15M-...
    m = re.match(r"KX([A-Z0-9]+?)15M", t)
    if m:
        return m.group(1)
    for a in ("BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "HYPE", "NEAR", "ZEC"):
        if a in t:
            return a
    return ""


def _bot_placed_tickers(root: Path) -> set[str]:
    """Tickers Alice herself placed (live ledger) — not owner manual bags."""
    out: set[str] = set()
    ledger = root / "kalshi_usd_live_ledger.jsonl"
    if not ledger.exists():
        return out
    try:
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("event") != "usd_place":
                continue
            t = str(o.get("ticker") or "").strip()
            if t:
                out.add(t)
    except OSError:
        pass
    return out


def import_exchange_positions_to_night(
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Pull live Kalshi positions into night open for TP (idempotent).

    r1718: skip owner/manual fat bags — only bot-placed + ≤ IMPORT_MAX_CONTRACTS.
    """
    from System.kalshi_usd_hand import load_night, save_night, _log as hand_log
    from System.kalshi_portfolio_read import fetch_positions

    root = _state(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    pos = fetch_positions()
    if not pos.get("ok"):
        return {"ok": False, "reason": pos.get("reason"), "n_imported": 0}

    night = load_night(root)
    opens = list(night.get("open") or [])
    by_ticker = {str(o.get("ticker") or ""): o for o in opens if o.get("ticker")}
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    bot_tickers = _bot_placed_tickers(root) if IMPORT_BOT_PLACED_ONLY else set()

    for p in pos.get("positions") or []:
        if not isinstance(p, dict):
            continue
        ticker = str(p.get("ticker") or "").strip()
        if not ticker:
            continue
        try:
            qty = float(p.get("position") or 0)
        except (TypeError, ValueError):
            continue
        if abs(qty) < 1e-9:
            continue
        # Kalshi: +qty = long YES, -qty = long NO
        if qty > 0:
            side = "yes"
            count = abs(qty)
        else:
            side = "no"
            count = abs(qty)

        # r1718: do not steal owner stash into TP organ
        if count > float(IMPORT_MAX_CONTRACTS) + 1e-9:
            skipped.append(
                {
                    "ticker": ticker,
                    "side": side,
                    "count": count,
                    "reason": "owner_or_fat_bag_not_imported",
                }
            )
            continue
        if IMPORT_BOT_PLACED_ONLY and ticker not in bot_tickers and ticker not in by_ticker:
            skipped.append(
                {
                    "ticker": ticker,
                    "side": side,
                    "count": count,
                    "reason": "not_bot_placed_skip_import",
                }
            )
            continue

        # estimate entry from exposure if present
        entry = 0.5
        exp = p.get("market_exposure_dollars")
        if exp is None:
            exp = p.get("market_exposure")
        try:
            if exp is not None and count > 0:
                entry = min(0.99, max(0.01, abs(float(exp)) / count))
        except (TypeError, ValueError):
            entry = 0.5

        fee_paid = 0.0
        for fk in ("fees_paid_dollars", "fees_paid"):
            if p.get(fk) is not None:
                try:
                    fee_paid = abs(float(p[fk]))
                except (TypeError, ValueError):
                    pass
                break

        asset = _asset_from_ticker(ticker)
        if ticker in by_ticker:
            # only refresh counts on bags Alice already owns in night
            row = by_ticker[ticker]
            if row.get("source") == "exchange_import" and count > float(IMPORT_MAX_CONTRACTS):
                continue
            row["fill_count"] = float(count)
            row["count"] = float(count)
            row["side"] = side
            row["asset"] = row.get("asset") or asset
            row["from_exchange_sync"] = True
            continue

        row = {
            "asset": asset,
            "ticker": ticker,
            "side": side,
            "label": "UP" if side == "yes" else "DOWN",
            "price": round(entry, 4),
            "side_price": round(entry, 4),
            "count": float(count),
            "fill_count": float(count),
            "fee_paid_usd": fee_paid,
            "cost_usd": round(entry * count + fee_paid, 4),
            "ts": time.time(),
            "source": "exchange_import",
            "from_exchange_sync": True,
            "owner_or_dual": "imported_for_tp_bot_only",
            "note": "r1718 bot-sized only; owner bags never imported",
        }
        opens.append(row)
        by_ticker[ticker] = row
        imported.append({"asset": asset, "ticker": ticker, "side": side, "count": count, "entry": entry})
        hand_log(
            {"event": "usd_import_position", **row, "deal": "r1718"},
            state_dir=root,
        )
        _log({"event": "import_position", **imported[-1]}, state_dir=root)

    if skipped:
        _log(
            {
                "event": "import_skipped_owner_bags",
                "n_skipped": len(skipped),
                "skipped": skipped[:20],
                "deal": "r1718",
            },
            state_dir=root,
        )

    night["open"] = opens
    save_night(night, state_dir=root)
    return {
        "ok": True,
        "n_imported": len(imported),
        "imported": imported,
        "n_skipped_owner": len(skipped),
        "skipped": skipped[:20],
        "n_open": len(opens),
        "truth_label": TRUTH,
        "deal": "r1718",
    }


def ensure_usd_dual_for_paper_opens(
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Retry dual place for paper opens that never got a US$ fill this window."""
    from System.kalshi_usd_hand import (
        maybe_mirror_paper_bet,
        load_night,
        is_hand_live,
    )
    from System.kalshi_usd_lane import is_usd_lane_armed
    from System.swarm_sifta_paper_loop import load_open_book

    root = _state(state_dir)
    if not is_usd_lane_armed(root) or not is_hand_live(root):
        return {"ok": False, "reason": "lane_or_hand_off", "n_tried": 0}

    book = load_open_book(root)
    paper_opens = list(book.get("open") or [])
    night = load_night(root)
    usd_tickers = {
        str(o.get("ticker") or "")
        for o in (night.get("open") or [])
        if o.get("ticker")
    }

    # r1697/r1699: no catch-up dual in last 6m (first 9m only; no add on bags)
    try:
        from System.swarm_sifta_paper_loop import DEFAULT_MIN_SECS

        min_secs = int(DEFAULT_MIN_SECS)
    except Exception:
        min_secs = 6 * 60
    try:
        live = json.loads((root / "kalshi_15m_live.json").read_text(encoding="utf-8"))
        secs_now = None
        for m in live.get("markets") or []:
            if m.get("seconds_to_close") is not None:
                secs_now = float(m["seconds_to_close"])
                break
        if secs_now is not None and secs_now < min_secs:
            return {
                "ok": True,
                "n_tried": 0,
                "n_filled": 0,
                "reason": "late_window_no_catchup",
                "secs_left": secs_now,
                "need": f">={min_secs}s for new dual",
                "truth_label": TRUTH,
            }
    except Exception:
        pass
    # r1702: allow catch-up until TARGET concurrent (2) · not while full
    try:
        from System.ledger_deal import MAX_OPEN, TARGET_CONCURRENT_OPEN

        _cap = min(int(TARGET_CONCURRENT_OPEN), int(MAX_OPEN))
    except Exception:
        _cap = 2
    n_open_now = len(night.get("open") or [])
    if n_open_now >= _cap:
        return {
            "ok": True,
            "n_tried": 0,
            "n_filled": 0,
            "reason": "concurrent_full_no_catchup",
            "n_open": n_open_now,
            "target_open": _cap,
            "truth_label": TRUTH,
        }

    tried: list[dict[str, Any]] = []
    filled: list[dict[str, Any]] = []
    for o in paper_opens:
        ticker = str(o.get("ticker") or "")
        if not ticker or ticker in usd_tickers:
            continue
        ul = o.get("usd_live") or {}
        if ul.get("ok") and ul.get("filled"):
            continue
        # only retry recoverable fails / missing
        reason = str(ul.get("reason") or ul.get("event") or "")
        if reason and reason not in (
            "",
            "usd_no_fill",
            "usd_reject",
            "usd_error",
            "CapRejected",
            "live_outside_band",
            "band",
        ):
            # still try if never attempted
            if ul.get("event") not in (None, "usd_skip", "usd_reject", "usd_no_fill", "usd_error"):
                if ul.get("filled"):
                    continue

        entry_p = float(o.get("price") or o.get("entry_price") or 0.5)
        rainman = o.get("rainman") if isinstance(o.get("rainman"), dict) else {}
        if not rainman:
            rainman = {
                "action": "fire",
                "score": float(o.get("rainman_score") or 0.62),
                "bucket": "catchup",
            }
        if rainman.get("score") is None:
            rainman["score"] = 0.62
        bet = {
            "ticker": ticker,
            "asset": o.get("asset"),
            "side": o.get("side"),
            "entry_price": entry_p,
            "price": entry_p,
            "kalshi_yes": o.get("kalshi_yes"),
            "rainman": rainman,
            "volume": o.get("volume") or 8000,
            "catchup_dual": True,
        }
        res = maybe_mirror_paper_bet(bet, state_dir=root, dry_run=False)
        tried.append(
            {
                "asset": o.get("asset"),
                "event": res.get("event"),
                "reason": res.get("reason"),
                "filled": res.get("filled"),
            }
        )
        if res.get("filled") or (
            res.get("ok") and res.get("event") == "usd_place" and float(res.get("fill_count") or 0) > 0
        ):
            filled.append(tried[-1])
            o["usd_live"] = res
        _log(
            {
                "event": "catchup_dual",
                "asset": o.get("asset"),
                "ticker": ticker,
                "result": res.get("event"),
                "reason": res.get("reason"),
                "filled": res.get("filled"),
            },
            state_dir=root,
        )

    # persist paper book usd_live tags
    try:
        from System.swarm_sifta_paper_loop import save_open_book

        save_open_book(book, root)
    except Exception:
        pass

    return {
        "ok": True,
        "n_tried": len(tried),
        "n_filled": len(filled),
        "tried": tried[:8],
        "truth_label": TRUTH,
    }


def tick_usd_every_round_sync(
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Monitor hook: import positions + catch up dual + ready for TP."""
    root = _state(state_dir)
    imp = import_exchange_positions_to_night(state_dir=root)
    catch = ensure_usd_dual_for_paper_opens(state_dir=root)
    out = {
        "ok": True,
        "import": imp,
        "catchup": catch,
        "truth_label": TRUTH,
        "ts": time.time(),
        "doctrine": "math dual every eligible paper ticket; TP all exchange opens",
    }
    _log({"event": "tick_sync", **{k: out[k] for k in ("import", "catchup")}}, state_dir=root)
    return out


__all__ = [
    "import_exchange_positions_to_night",
    "ensure_usd_dual_for_paper_opens",
    "tick_usd_every_round_sync",
    "TRUTH",
]
