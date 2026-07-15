#!/usr/bin/env python3
"""Stigmergic Predictions — Kalshi-style sandbox game for Alice OS.

Owner naming (George, 2026-07-11): the app is called "Stigmergic Predictions".

Not kalshi.com (that site blocks Alice Browser). This is a body game:
  field heat + GAME_STGM stakes + signed ballots + owner resolve.

Games category. Auto swarm ticks. George plays YES/NO with sandbox tokens.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QAbstractItemView,
    QHeaderView,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# One background worker for ALL network/engine work. Never block the Qt UI
# thread (macOS beach-ball / unresizable window). max_workers=1 serializes
# access to the shared SiftaMarketEngine.
_BG_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="sifta_pred_bg"
)
_ENGINE_LOCK = threading.RLock()

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
sys.path.insert(0, str(_REPO))

# Force re-import so a long-running Alice process picks up Market.kalshi_* fields
import importlib  # noqa: E402

for _mod_name in (
    "System.swarm_kalshi_public_feed",
    "System.swarm_sifta_market",
    # learner before loop: the loop binds _learner at import time
    "System.swarm_sifta_paper_learner",
    "System.swarm_sifta_paper_loop",
):
    try:
        if _mod_name in sys.modules:
            importlib.reload(sys.modules[_mod_name])
        else:
            importlib.import_module(_mod_name)
    except Exception:
        pass

from System.swarm_sifta_market import (  # noqa: E402
    OWNER_ID,
    MAX_STAKE,
    TOKEN,
    TRUTH_LABEL,
    SiftaMarketEngine,
    run_pheromone_ablation,
)
from System.swarm_kalshi_public_feed import (  # noqa: E402
    CRYPTO_ASSETS,
    TIMEFRAMES,
)
from System.swarm_prediction_market_loop import (  # noqa: E402
    auto_bet_cycle,
    monitor_ending_soon,
    check_results,
    format_autobet_for_alice,
    AUTO_BET_STAKE,
    AUTO_BET_MIN_EDGE,
)
from System.swarm_sifta_paper_loop import (  # noqa: E402
    DEFAULT_MAX_SECS,
    load_proof,
    paper_bet_15m,
    paper_loop_tick,
    settle_paper_from_api,
)
from System.swarm_sifta_market import _STATE  # noqa: E402

try:
    from System.swarm_app_focus import publish_focus as _publish_focus
except Exception:
    _publish_focus = None  # type: ignore[assignment]

APP_TITLE = "Stigmergic Predictions"
APP_ID = "sifta_prediction_market"

_BG = "#0b0e14"
_CARD = "#141a24"
_TEXT = "#e8eef8"
_DIM = "#8b98b0"
_YES = "#3dd68c"
_NO = "#f07178"
_GOLD = "#ffe298"
_ACCENT = "#4bebbf"
_BLUE = "#63a8ff"
_PANEL = "#101722"

# George 2026-07-12: double fonts for main board; then compact strips/history
# only (screenshots: proof/Rainman/USD + HISTORY/LIVE ODDS/learn footer).
_FS = 2  # main body (metrics, open positions, last-run)
_F = lambda px: max(10, int(round(px * _FS)))  # stylesheet px helper
_FC_SCALE = 1.0  # compact = original size for dense attached areas
_FC = lambda px: max(9, int(round(px * _FC_SCALE)))


def _read_json(path: Path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return default


def _read_jsonl_tail(path: Path, limit: int = 600) -> list[dict]:
    """Read only the file tail — never load multi-MB ledgers into the UI thread."""
    if not path.exists():
        return []
    limit = max(1, int(limit))
    try:
        size = path.stat().st_size
        # ~400 bytes/line upper bound; cap read window
        read_bytes = min(size, max(64_000, limit * 500))
        with path.open("rb") as fh:
            if size > read_bytes:
                fh.seek(-read_bytes, os.SEEK_END)
            raw = fh.read().decode("utf-8", errors="replace")
        lines = raw.splitlines()
        if size > read_bytes and lines:
            lines = lines[1:]  # drop partial first line
        lines = lines[-limit:]
    except OSError:
        return []
    rows: list[dict] = []
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


_PORTFOLIO_SNAP_CACHE: dict[str, Any] = {"ts": 0.0, "snap": None, "path": ""}


def _cached_human_portfolio(state_dir: Path | str = _STATE, *, max_age: float = 1.5) -> dict:
    """Throttle portfolio rebuilds so refresh timers don't beach-ball the UI."""
    path = str(state_dir)
    now = time.time()
    if (
        _PORTFOLIO_SNAP_CACHE.get("path") == path
        and _PORTFOLIO_SNAP_CACHE.get("snap") is not None
        and now - float(_PORTFOLIO_SNAP_CACHE.get("ts") or 0.0) < max_age
    ):
        return _PORTFOLIO_SNAP_CACHE["snap"]  # type: ignore[return-value]
    snap = human_portfolio_snapshot(state_dir)
    _PORTFOLIO_SNAP_CACHE["ts"] = now
    _PORTFOLIO_SNAP_CACHE["snap"] = snap
    _PORTFOLIO_SNAP_CACHE["path"] = path
    return snap


def _human_decision_reason(evidence: dict, *, side: str, price: float) -> str:
    why = str((evidence or {}).get("why") or "").strip()
    if why:
        return why
    return (
        f"older ticket · {side} entered at {price:.0%} crowd price · "
        "chart evidence was not recorded"
    )


def _usd_deal_snapshot(state_dir: Path | str) -> dict[str, Any]:
    """Disk-only USD truth view; exchange and local tracked books never merge."""
    state = Path(state_dir)
    portfolio_cache = _read_json(state / "kalshi_portfolio_cache.json", {})
    try:
        from System.kalshi_portfolio_read import cache_status

        read_status = cache_status(portfolio_cache)
        exchange_status = dict(read_status.get("positions") or {})
        history_status = dict(read_status.get("history") or {})
    except Exception:
        exchange_status = {
            "known": False,
            "fresh": False,
            "age_seconds": None,
            "error": "cache_status_unavailable",
            "source": "",
            "value": None,
            "count": None,
        }
        history_status = {
            "known": False,
            "fresh": False,
            "age_seconds": None,
            "error": "cache_status_unavailable",
            "source": "",
            "value": None,
        }
    exchange_rows = exchange_status.pop("value", None)
    if not isinstance(exchange_rows, list):
        exchange_rows = []
    exchange_status.update(
        {
            "positions": exchange_rows,
            "count": (
                len(exchange_rows) if exchange_status.get("known") else None
            ),
            "source": str(exchange_status.get("source") or "KALSHI_PROD_GET_/portfolio/positions"),
            "provenance": (
                "CONFIRMED_EXCHANGE_READ"
                if exchange_status.get("known")
                else "NO_CONFIRMED_EXCHANGE_SNAPSHOT"
            ),
        }
    )
    reconciliation = history_status.pop("value", None)
    if not isinstance(reconciliation, dict):
        reconciliation = {}
    history_status.update(
        {
            "reconciliation": reconciliation,
            "source": str(
                history_status.get("source")
                or "KALSHI_PROD_GET_/portfolio/fills+GET_/portfolio/settlements"
            ),
            "provenance": (
                "CONFIRMED_EXCHANGE_RECEIPTS"
                if history_status.get("known")
                else "NO_CONFIRMED_EXCHANGE_RECEIPTS"
            ),
        }
    )

    night = _read_json(state / "kalshi_usd_night.json", {})
    tracked_rows = [
        dict(row)
        for row in (night.get("open") or [])
        if isinstance(row, dict)
    ]
    tracked = {
        "open": tracked_rows,
        "count": len(tracked_rows),
        "realized_pnl_usd": float(night.get("realized_pnl_usd") or 0.0),
        "source": "kalshi_usd_night.json",
        "provenance": "LOCAL_TRACKED_ORDER_BOOK_NOT_EXCHANGE",
        "truth_label": str(night.get("truth_label") or "KALSHI_USD_HAND_V1"),
    }
    return {"exchange": exchange_status, "history": history_status, "tracked": tracked}


def _format_target_price(tgt: float) -> str:
    """Safari-style target: $62,466.33 or $1.0701."""
    try:
        t = float(tgt)
    except (TypeError, ValueError):
        return ""
    if t <= 0:
        return ""
    if t >= 1000:
        return f"${t:,.2f}"
    if t >= 100:
        return f"${t:,.2f}"
    if t >= 10:
        return f"${t:.3f}".rstrip("0").rstrip(".")
    # XRP / low-priced alts — keep 4 decimals like Kalshi glass
    return f"${t:.4f}"


def format_r1648_deal_strip(snap: dict, *, hand_status: str = "") -> tuple[str, str]:
    """Compact glass text plus explicit provenance tooltip."""
    exchange = dict(snap.get("usd_exchange") or {})
    tracked = dict(snap.get("usd_tracked") or {})
    history = dict(snap.get("usd_history") or {})
    reconciliation = dict(history.get("reconciliation") or {})
    if exchange.get("known"):
        exchange_count = int(exchange.get("count") or 0)
        age = exchange.get("age_seconds")
        age_bit = f"{int(float(age))}s" if isinstance(age, (int, float)) else "age?"
        if exchange.get("error"):
            state_bit = "CACHED/READ ERR" if exchange.get("fresh") else "STALE/READ ERR"
        else:
            state_bit = "FRESH" if exchange.get("fresh") else "STALE"
        exchange_bit = f"EXCHANGE {exchange_count}/3 {state_bit} {age_bit}"
    else:
        exchange_bit = "EXCHANGE ?/3 NOT FETCHED"
        if exchange.get("error"):
            exchange_bit += "/READ ERR"
    tracked_count = int(tracked.get("count") or 0)
    receipt_n = int(reconciliation.get("n_settled_fills") or 0)
    receipt_ev = reconciliation.get("ev_per_fill_usd")
    receipt_ev_bit = (
        f"EV {float(receipt_ev):+.3f}" if isinstance(receipt_ev, (int, float)) else "EV n/a"
    )
    receipt_bit = (
        f"RECEIPTS {receipt_n} EXCH · {receipt_ev_bit}"
        if history.get("known")
        else "RECEIPTS NOT FETCHED"
    )
    hand_bit = str(hand_status or "US $ HAND UNKNOWN")
    # Live deal caps from ledger_deal (not stale 80–88 FIRE)
    try:
        from System.ledger_deal import (
            FIRE_ONLY_USD,
            MAX_OPEN,
            MAX_SAME_DIR,
            USD_MAX_ENTRY,
            USD_MIN_ENTRY,
        )

        lo = int(round(float(USD_MIN_ENTRY) * 100))
        hi = int(round(float(USD_MAX_ENTRY) * 100))
        fire_bit = "FIRE only" if FIRE_ONLY_USD else "dual FIRE+THIN"
        band_bit = f"USD {lo}–{hi} {fire_bit}"
        cap_bit = f"{int(MAX_OPEN)} max/{int(MAX_SAME_DIR)} dir"
    except Exception:
        band_bit = "USD 70–88 dual"
        cap_bit = "3 max/2 dir"
    tracked_pnl = tracked.get("realized_pnl_usd")
    pnl_bit = ""
    if isinstance(tracked_pnl, (int, float)):
        pnl_bit = f" · night ${float(tracked_pnl):+.2f}"
    text = (
        f"r1648 DEAL ✓ · {cap_bit} · {band_bit} · STGM ON · "
        f"$1 evidence lock · {exchange_bit} · {receipt_bit} · TRACKED {tracked_count} local"
        f"{pnl_bit} · {hand_bit}"
    )
    tooltip = (
        f"Exchange positions: {exchange.get('source') or '—'} "
        f"({exchange.get('provenance') or 'CONFIRMED_EXCHANGE_READ'}).\n"
        f"Tracked opens: {tracked.get('source') or '—'} "
        f"({tracked.get('provenance') or 'LOCAL_TRACKED_ORDER_BOOK_NOT_EXCHANGE'}).\n"
        f"Realized USD: {history.get('source') or '—'} "
        f"({history.get('provenance') or 'NO_CONFIRMED_EXCHANGE_RECEIPTS'}).\n"
        "STGM/paper opens remain in alice_15m_open_book.json and are not counted above."
    )
    if exchange.get("error"):
        tooltip += f"\nLast position read error: {exchange['error']}"
    return text, tooltip


def _scalp_strip_snapshot(state: Path) -> dict[str, Any]:
    """Compact STGM scalp strip from alice_15m_scalp_glass + settled executes."""
    glass = _read_json(state / "alice_15m_scalp_glass.json", {})
    honest = _read_json(state / "alice_15m_scalp_proof_honest.json", {})
    n_scalp = 0
    n_ff = 0
    n_w = 0
    n_l = 0
    fee_sum = 0.0
    for row in _read_jsonl_tail(state / "alice_15m_settled.jsonl", 400):
        if str(row.get("mode") or "") != "scalp_execute":
            continue
        n_scalp += 1
        if row.get("force_flat"):
            n_ff += 1
        try:
            ft = float(row.get("pnl_usd_fee_true") or 0.0)
        except (TypeError, ValueError):
            ft = 0.0
        fee_sum += ft
        if ft >= 0 or row.get("win"):
            n_w += 1
        else:
            n_l += 1
    ha = glass.get("honest_accounting") or honest or {}
    disclaimer = str(
        ha.get("disclaimer")
        or honest.get("disclaimer")
        or "selected-green / fee-true exits — selection-biased; not live-edge proof"
    )
    if len(disclaimer) > 140:
        disclaimer = disclaimer[:137] + "…"
    return {
        "n_scalp_execute": n_scalp,
        "fee_true_sum": round(fee_sum, 4),
        "wins": n_w,
        "losses": n_l,
        "force_flat_n": n_ff,
        "disclaimer": disclaimer,
        "stamp": glass.get("stamp") or "",
    }


def _train_rows_snapshot(state: Path, *, limit: int = 12) -> list[dict[str, Any]]:
    """Shadow-training exits only — never mixed into settled STGM P&L."""
    out: list[dict[str, Any]] = []
    for row in reversed(_read_jsonl_tail(state / "alice_15m_scalp.jsonl", 500)):
        if str(row.get("event") or "") != "training_scalp_exit":
            continue
        try:
            ft = float(row.get("pnl_usd_fee_true") or 0.0)
        except (TypeError, ValueError):
            ft = 0.0
        side = str(row.get("label") or row.get("side") or "?").upper()
        if side in ("YES",):
            side = "UP"
        elif side in ("NO",):
            side = "DOWN"
        price = float(row.get("entry") or row.get("price") or 0.5)
        out.append(
            {
                "ticker": str(row.get("ticker") or ""),
                "asset": str(row.get("asset") or "?"),
                "side": side,
                "result": "WIN" if ft >= 0 else "LOSS",
                "win": ft >= 0,
                "kind_badge": "TRAIN",
                "mode": "stgm_training_only",
                "force_flat": "force_flat" in str(row.get("reason") or ""),
                "pnl_usd_fee_true": ft,
                "fees_total": row.get("fees_total"),
                "price_cents": round(price * 100.0, 1),
                "if_real_usd": ft,
                "dual": False,
                "lane": "TRAIN",
                "decision_reason": str(row.get("reason") or "training"),
                "entry_clock": "—",
                "body_pnl_label": "—",
                "ts": float(row.get("ts") or 0.0),
            }
        )
        if len(out) >= limit:
            break
    return out


def glass_kind_label(row: dict[str, Any]) -> str:
    """Badge text for HISTORY / LAST RUN: SCALP | HOLD | TRAIN (+ flags)."""
    mode = str(row.get("mode") or "")
    badge = str(row.get("kind_badge") or "")
    if not badge:
        if mode in ("scalp_execute", "scalp_shadow", "virtual_scalp"):
            badge = "SCALP"
        elif mode in ("stgm_training_only", "training") or row.get("lane") == "TRAIN":
            badge = "TRAIN"
        else:
            badge = "HOLD"
    bits = [badge]
    if row.get("force_flat"):
        bits.append("⚑7:30")
    if row.get("dual"):
        bits.append("⇄DUAL")
    return " ".join(bits)


def propagate_settled_scalp_fields(settled: dict[str, Any]) -> dict[str, Any]:
    """Cut-1 pure helper: fields glass must copy from settled ledger (testable)."""
    mode = str(settled.get("mode") or settled.get("result") or "")
    force_flat = bool(settled.get("force_flat") or settled.get("force_flat_7m"))
    fee_true = settled.get("pnl_usd_fee_true")
    if fee_true is None:
        fee_true = settled.get("pnl_usd")
    try:
        fee_true_f = float(fee_true) if fee_true is not None else None
    except (TypeError, ValueError):
        fee_true_f = None
    fees_total = settled.get("fees_total")
    return {
        "mode": mode or "hold_settle",
        "force_flat": force_flat,
        "pnl_usd_fee_true": fee_true_f,
        "fees_total": fees_total,
        "kind_badge": (
            "SCALP"
            if mode in ("scalp_execute", "scalp_shadow", "virtual_scalp")
            else "HOLD"
        ),
    }


def human_portfolio_snapshot(state_dir: Path | str = _STATE) -> dict:
    """One human-facing portfolio model from Alice's canonical ledgers.

    ``price_per_share`` and ``paper_shares`` describe the evidence model.
    ``stgm_at_risk`` and ``body_pnl_stgm`` describe actual body-STGM skin.
    Keeping those columns separate prevents a paper payout from masquerading
    as body-wallet money.
    """
    state = Path(state_dir)
    proof = _read_json(state / "alice_15m_paper_proof.json", {})
    book = _read_json(state / "alice_15m_open_book.json", {"open": []})
    budget = _read_json(state / "alice_15m_body_stgm_budget.json", {})
    economy = _read_json(state / "stgm_economy_cache.json", {})
    usd_deal = _usd_deal_snapshot(state)

    open_rows: list[dict] = []
    active_tickers: set[str] = set()
    for raw in book.get("open") or []:
        ticker = str(raw.get("ticker") or "")
        if ticker:
            active_tickers.add(ticker)
        price = min(0.99, max(0.01, float(raw.get("price") or 0.5)))
        paper_amount = float(raw.get("stake") or 1.0)
        body = raw.get("body_stgm") or {}
        evidence = raw.get("decision_evidence") or {}
        stgm = float(raw.get("stgm_stake") or body.get("stake") or 0.0)
        side = str(raw.get("label") or raw.get("side") or "?").upper()
        entry_ts = float(
            raw.get("ts") or body.get("reserved_ts") or 0.0
        )
        secs_at = raw.get("secs_left_at_entry")
        if secs_at is None:
            secs_at = raw.get("secs")
        try:
            secs_at_i = int(secs_at) if secs_at is not None else None
        except (TypeError, ValueError):
            secs_at_i = None
        entry_clock = str(raw.get("entry_clock") or "").strip()
        # Rebuild when missing or legacy "H:MM:SS @ M:SS left" (looked like 2 clocks)
        legacy = "@" in entry_clock and " left" in entry_clock and "m" not in entry_clock.split("@")[-1]
        if (not entry_clock or legacy) and entry_ts > 0:
            try:
                from System.swarm_sifta_paper_loop import format_entry_clock

                entry_clock = format_entry_clock(entry_ts, secs_at_i)
            except Exception:
                try:
                    entry_clock = datetime.fromtimestamp(entry_ts).strftime("%H:%M:%S")
                except Exception:
                    entry_clock = ""
                if secs_at_i is not None and secs_at_i >= 0:
                    entry_clock = (
                        f"{entry_clock} · {secs_at_i // 60}m{secs_at_i % 60:02d}s left"
                        if entry_clock
                        else f"{secs_at_i // 60}m{secs_at_i % 60:02d}s left"
                    )
        try:
            from System.sifta_15m_money_math import ticket_money_row

            money = ticket_money_row(
                price=price,
                volume_24h=float(raw.get("volume_24h") or 0.0),
                stake_stgm=stgm if stgm > 0 else 0.001,
            )
        except Exception:
            money = {
                "mult_net": round(1.0 / price, 2),
                "mult_label": f"{1.0 / price:.2f}x",
                "if_win_usd": round(1.0 / price - 1.0, 4),
                "if_lose_usd": -1.0,
                "volume_24h": 0.0,
            }
        open_rows.append(
            {
                "lane": "STGM_PAPER",
                "provenance": "alice_15m_open_book.json",
                "ticker": ticker,
                "asset": str(raw.get("asset") or "?"),
                "side": side,
                "stgm_at_risk": stgm,
                "stake_label": money.get("stake_label")
                or (f"{stgm:.5f}" if stgm else "—"),
                "thin": bool(money.get("thin")),
                "stake_cents": money.get("stake_cents"),
                "price_per_share": price,
                "price_cents": round(price * 100.0, 1),
                "paper_amount": paper_amount,
                "paper_shares": round(paper_amount / price, 3),
                "paper_profit_if_win": round(paper_amount * (1.0 / price - 1.0), 3),
                "mult_net": money.get("mult_net"),
                "mult_label": money.get("mult_label"),
                "if_win_usd": money.get("if_win_usd"),
                "if_lose_usd": money.get("if_lose_usd"),
                "volume_24h": money.get("volume_24h"),
                "target": raw.get("target"),
                "reserved_ts": float(body.get("reserved_ts") or raw.get("ts") or 0.0),
                "entry_ts": entry_ts,
                "secs_left_at_entry": secs_at_i,
                "entry_clock": entry_clock or "—",
                "decision_evidence": evidence,
                "decision_reason": _human_decision_reason(
                    evidence, side=side, price=price
                ),
            }
        )

    # Body ledger is authoritative for real STGM results. Skip zero-PnL
    # duplicate/refused rows and keep the newest actual mutation per ticker.
    body_results: list[dict] = []
    seen: set[str] = set()
    settled_by_ticker = {
        str(row.get("ticker") or ""): row
        for row in _read_jsonl_tail(state / "alice_15m_settled.jsonl", 2400)
        if row.get("ticker")
    }
    body_ledger = _read_jsonl_tail(state / "alice_15m_body_stgm_ledger.jsonl", 1600)
    for row in reversed(body_ledger):
        label = str(row.get("truth_label") or "")
        if label not in {
            "ALICE_15M_BODY_STGM_V2",
            "ALICE_15M_BODY_STGM_V3",
        }:
            continue
        kind = str(row.get("kind") or "")
        if kind not in {"win", "loss"}:
            continue
        ticker = str(row.get("ticker") or "")
        pnl = float(row.get("pnl_stgm") or 0.0)
        if not ticker or ticker in seen or pnl == 0.0:
            continue
        seen.add(ticker)
        price = min(0.99, max(0.01, float(row.get("price") or 0.5)))
        stake = float(row.get("stake") or 0.0)
        settled = settled_by_ticker.get(ticker) or {}
        evidence = settled.get("decision_evidence") or {}
        side = str(row.get("label") or "?").upper()
        # Entry wall time: prefer settled ticket's bet ts, not settle ts
        entry_ts = float(
            settled.get("entry_ts")
            or settled.get("ts_bet")
            or row.get("entry_ts")
            or 0.0
        )
        if entry_ts <= 0:
            # reserved_ts on body stake if present in open→settle path
            entry_ts = float(row.get("reserved_ts") or 0.0)
        secs_at = settled.get("secs_left_at_entry")
        if secs_at is None:
            secs_at = settled.get("secs")
        try:
            secs_at_i = int(secs_at) if secs_at is not None else None
        except (TypeError, ValueError):
            secs_at_i = None
        # Prefer full calendar timestamp for glass (date + time + clock depth)
        entry_clock = ""
        if entry_ts > 0:
            try:
                entry_clock = datetime.fromtimestamp(entry_ts).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                entry_clock = ""
        if not entry_clock:
            entry_clock = str(settled.get("entry_clock") or row.get("entry_clock") or "").strip()
        if entry_clock and secs_at_i is not None and secs_at_i >= 0 and "left" not in entry_clock:
            entry_clock = f"{entry_clock} @ {secs_at_i // 60}:{secs_at_i % 60:02d} left"
        elif entry_ts > 0 and secs_at_i is not None and secs_at_i >= 0 and "@" not in entry_clock:
            entry_clock = f"{entry_clock} @ {secs_at_i // 60}:{secs_at_i % 60:02d} left"
        try:
            from System.sifta_15m_money_math import (
                dollar_pnl_if_real,
                format_stake_stgm,
                format_stgm_with_cents,
                is_thin_stake,
                net_multiplier,
                stgm_to_usd,
            )

            mult = float(row.get("mult_net") or net_multiplier(price))
            unit = stgm_to_usd(stake) if stake > 0 else 1.0
            usd_hyp = float(
                row.get("pnl_usd_hyp")
                or settled.get("if_real_usd")
                or dollar_pnl_if_real(
                    price, win=(kind == "win"), unit_usd=max(0.01, unit)
                )
            )
            stake_label = format_stake_stgm(stake)
            pnl_label = format_stgm_with_cents(pnl, signed=True)
            thin = is_thin_stake(stake)
        except Exception:
            mult = round(1.0 / price, 2) if price else 0.0
            usd_hyp = round(pnl / 0.001, 4) if pnl else 0.0
            stake_label = f"{stake:.5f}" if stake else "—"
            pnl_label = f"{pnl:+.5f}"
            thin = False
        # r1707: propagate scalp truth from settled ledger (do not drop mode/fees)
        mode = str(
            settled.get("mode")
            or settled.get("result")
            or row.get("mode")
            or ""
        )
        force_flat = bool(
            settled.get("force_flat")
            or settled.get("force_flat_7m")
            or row.get("force_flat")
        )
        fee_true = settled.get("pnl_usd_fee_true")
        if fee_true is None:
            fee_true = settled.get("pnl_usd")
        if fee_true is None:
            fee_true = row.get("pnl_usd_fee_true")
        try:
            fee_true_f = float(fee_true) if fee_true is not None else None
        except (TypeError, ValueError):
            fee_true_f = None
        fees_total = settled.get("fees_total")
        if fees_total is None:
            try:
                fi = float(settled.get("fee_in") or 0)
                fo = float(settled.get("fee_out") or 0)
                fees_total = round(fi + fo, 4) if (fi or fo) else None
            except (TypeError, ValueError):
                fees_total = None
        usd_live = settled.get("usd_live") or row.get("usd_live") or {}
        dual = bool(
            (isinstance(usd_live, dict) and (usd_live.get("filled") or usd_live.get("event") == "usd_place"))
            or settled.get("dual")
            or row.get("dual")
        )
        kind_badge = "SCALP" if mode in ("scalp_execute", "scalp_shadow", "virtual_scalp") else "HOLD"
        body_results.append(
            {
                "ticker": ticker,
                "asset": str(row.get("asset") or "?"),
                "side": side,
                "result": "WIN" if kind == "win" else "LOSS",
                "win": kind == "win",
                "stgm_at_risk": stake,
                "stake_label": stake_label,
                "thin": thin,
                "body_pnl_stgm": pnl,
                "body_pnl_label": pnl_label,
                "if_real_usd": usd_hyp,
                "mult_net": mult,
                "stake_epoch": str(row.get("stake_epoch") or label),
                "price_per_share": price,
                "price_cents": round(price * 100.0, 1),
                "paper_shares": round(1.0 / price, 3),
                "ts": float(row.get("ts") or 0.0),  # settle time
                "entry_ts": entry_ts,
                "entry_clock": entry_clock or "—",
                "secs_left_at_entry": secs_at_i,
                "decision_evidence": evidence,
                "decision_reason": _human_decision_reason(
                    evidence, side=side, price=price
                ),
                # r1707 glass truth
                "mode": mode or "hold_settle",
                "kind_badge": kind_badge,
                "force_flat": force_flat,
                "pnl_usd_fee_true": fee_true_f,
                "fees_total": fees_total,
                "dual": dual,
                "lane": "STGM",
            }
        )

    # r1707: also surface pure scalp_execute settles not yet in body ledger
    for settled in reversed(
        _read_jsonl_tail(state / "alice_15m_settled.jsonl", 400)
    ):
        if not isinstance(settled, dict):
            continue
        if str(settled.get("mode") or "") not in ("scalp_execute",):
            continue
        ticker = str(settled.get("ticker") or "")
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        price = min(0.99, max(0.01, float(settled.get("price") or settled.get("entry") or 0.5)))
        side = str(settled.get("label") or settled.get("side") or "?").upper()
        if side in ("YES",):
            side = "UP"
        elif side in ("NO",):
            side = "DOWN"
        win = bool(settled.get("win"))
        if settled.get("win") is None and settled.get("pnl_usd_fee_true") is not None:
            win = float(settled.get("pnl_usd_fee_true") or 0) >= 0
        fee_true_f = None
        try:
            if settled.get("pnl_usd_fee_true") is not None:
                fee_true_f = float(settled["pnl_usd_fee_true"])
        except (TypeError, ValueError):
            fee_true_f = None
        entry_ts = float(settled.get("entry_ts") or settled.get("ts") or 0.0)
        entry_clock = str(settled.get("entry_clock") or "—")
        usd_live = settled.get("usd_live") or {}
        dual = bool(
            isinstance(usd_live, dict)
            and (usd_live.get("filled") or usd_live.get("event") == "usd_place")
        )
        body_results.append(
            {
                "ticker": ticker,
                "asset": str(settled.get("asset") or "?"),
                "side": side,
                "result": "WIN" if win else "LOSS",
                "win": win,
                "stgm_at_risk": float(settled.get("stgm_stake") or settled.get("stake") or 0.001),
                "stake_label": "—",
                "thin": False,
                "body_pnl_stgm": float(settled.get("pnl") or 0.0),
                "body_pnl_label": f"{float(settled.get('pnl') or 0):+.5f}",
                "if_real_usd": fee_true_f if fee_true_f is not None else 0.0,
                "mult_net": round(1.0 / price, 2) if price else 0.0,
                "stake_epoch": "scalp_execute",
                "price_per_share": price,
                "price_cents": round(price * 100.0, 1),
                "paper_shares": round(1.0 / price, 3) if price else 0.0,
                "ts": float(settled.get("ts") or 0.0),
                "entry_ts": entry_ts,
                "entry_clock": entry_clock,
                "secs_left_at_entry": settled.get("secs_left_at_entry"),
                "decision_evidence": settled.get("decision_evidence") or {},
                "decision_reason": "SCALP fee-true mid-window",
                "mode": "scalp_execute",
                "kind_badge": "SCALP",
                "force_flat": bool(settled.get("force_flat")),
                "pnl_usd_fee_true": fee_true_f,
                "fees_total": settled.get("fees_total"),
                "dual": dual,
                "lane": "STGM",
            }
        )
    # newest first for glass
    body_results.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)

    budget_open = set(str(x) for x in (budget.get("open_tickets") or {}).keys())
    stale = sorted(budget_open - active_tickers)
    body_wins = int(budget.get("n_wins") or 0)
    body_losses = int(budget.get("n_losses") or 0)
    body_settled = int(budget.get("n_settled") or (body_wins + body_losses))

    def _window_key(ticker: str) -> str:
        parts = str(ticker or "").split("-")
        if len(parts) >= 3:
            return f"{parts[1]}-{parts[2]}"
        return str(ticker or "")

    # Pin the most recent completed 15m run so wins stay visible after the next lock
    last_run_id = ""
    last_run_wins: list[dict] = []
    last_run_losses: list[dict] = []
    if body_results:
        last_run_id = _window_key(str(body_results[0].get("ticker") or ""))
        for row in body_results:
            if _window_key(str(row.get("ticker") or "")) != last_run_id:
                continue
            if row.get("win"):
                last_run_wins.append(row)
            else:
                last_run_losses.append(row)
    last_run_pnl = round(
        sum(float(r.get("body_pnl_stgm") or 0.0) for r in last_run_wins + last_run_losses),
        9,
    )

    last_run_usd = round(
        sum(float(r.get("if_real_usd") or 0.0) for r in last_run_wins + last_run_losses),
        4,
    )
    # Real exchange USD for the same window: exact selected-side fill + exact fee.
    last_run_usd_real = 0.0
    last_run_usd_real_n = 0
    last_run_usd_real_known = False
    real_source = ""
    history = dict(usd_deal.get("history") or {})
    reconciliation = dict(history.get("reconciliation") or {})
    real_rows = [
        row
        for row in (reconciliation.get("rows") or [])
        if isinstance(row, dict) and str(row.get("window") or "") == last_run_id
    ]
    pending_same_window = [
        row
        for row in (reconciliation.get("unsettled") or [])
        if isinstance(row, dict) and str(row.get("window") or "") == last_run_id
    ]
    if history.get("known") and real_rows and not pending_same_window:
        last_run_usd_real = round(
            sum(float(row.get("pnl_usd") or 0.0) for row in real_rows), 4
        )
        last_run_usd_real_n = len(real_rows)
        last_run_usd_real_known = True
        real_source = str(history.get("source") or "")
    try:
        from System.sifta_15m_money_math import stgm_to_usd

        body_pnl = float(budget.get("realized_pnl_stgm") or 0.0)
        body_pnl_usd = stgm_to_usd(body_pnl)
        legacy_pnl = float(budget.get("realized_pnl_stgm_legacy_v2") or 0.0)
    except Exception:
        body_pnl = float(budget.get("realized_pnl_stgm") or 0.0)
        body_pnl_usd = body_pnl / 0.001 if body_pnl else 0.0
        legacy_pnl = float(budget.get("realized_pnl_stgm_legacy_v2") or 0.0)

    # Rainman epoch line from proof (gate70 etc.)
    epochs = list(proof.get("epochs") or [])
    active_epoch = {}
    for ep in reversed(epochs):
        if isinstance(ep, dict) and ep.get("active", True):
            active_epoch = ep
            break
    if not active_epoch and epochs:
        active_epoch = epochs[-1] if isinstance(epochs[-1], dict) else {}

    return {
        "body_total_stgm": float(
            economy.get("spendable_total_stgm") or economy.get("canonical_wallet_sum") or 0.0
        ),
        "alice_m5_stgm": float(
            economy.get("alice_m5_spendable_stgm")
            or (economy.get("canonical_wallet_balances") or {}).get("ALICE_M5")
            or 0.0
        ),
        "body_pnl_stgm": body_pnl,
        "body_pnl_usd_hyp": body_pnl_usd,
        "body_pnl_stgm_legacy_v2": legacy_pnl,
        "stake_epoch": str(budget.get("stake_epoch") or "dollar_parity_v1"),
        "body_wins": body_wins,
        "body_losses": body_losses,
        "body_settled": body_settled,
        "body_win_rate": (body_wins / body_settled) if body_settled else 0.0,
        "open_risk_stgm": round(sum(row["stgm_at_risk"] for row in open_rows), 9),
        "budget_open_risk_stgm": float(budget.get("open_staked_stgm") or 0.0),
        "max_open_stgm": float(budget.get("max_open_stgm") or 0.02),
        "night_max_loss_stgm": float(budget.get("night_max_loss") or 0.10),
        "halted": bool(budget.get("halted")),
        "halt_reason": str(budget.get("halt_reason") or ""),
        "open": open_rows,
        "open_source": "alice_15m_open_book.json",
        "open_provenance": "STGM_PAPER_NOT_USD",
        "usd_exchange": usd_deal["exchange"],
        "usd_history": usd_deal["history"],
        "usd_tracked": usd_deal["tracked"],
        "recent_results": body_results,
        "last_run_id": last_run_id,
        "last_run_wins": last_run_wins,
        "last_run_losses": last_run_losses,
        "last_run_summary": {
            "wins": len(last_run_wins),
            "losses": len(last_run_losses),
            "pnl_stgm": last_run_pnl,
            "pnl_usd_hyp": last_run_usd,
            "pnl_usd_real": last_run_usd_real if last_run_usd_real_known else None,
            "pnl_usd_real_n": last_run_usd_real_n,
            "pnl_usd_real_known": last_run_usd_real_known,
            "pnl_usd_real_source": real_source,
            "window": last_run_id,
        },
        # r1707: scalp strip + train rows (learning only — never real USD P&L claim)
        "scalp_strip": _scalp_strip_snapshot(state),
        "train_rows": _train_rows_snapshot(state, limit=12),
        "stale_reservations": stale,
        "active_epoch": active_epoch,
        "paper": {
            "wins": int(proof.get("n_wins") or 0),
            "losses": int(proof.get("n_losses") or 0),
            "settled": int(proof.get("n_settled") or 0),
            "win_rate": float(proof.get("win_rate") or 0.0),
            "pnl_units": float(proof.get("pnl") or 0.0),
            "proven": bool(proof.get("proven")),
        },
    }


def _focus(detail: str) -> None:
    if _publish_focus is None:
        return
    try:
        _publish_focus(APP_TITLE, detail, app_id=APP_ID)
    except Exception:
        pass


def _write_receipt(event: str, payload: dict) -> None:
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "app": APP_TITLE,
            "event": event,
            "truth_label": TRUTH_LABEL,
            **payload,
        }
        with (_STATE / "sifta_market_app_receipts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _queue_monitor_cmd(cmd: str, payload: dict | None = None) -> None:
    """Drop a one-shot command for the headless paper monitor (r1628 glass)."""
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "cmd": str(cmd),
            "source": "qt_predictions_glass",
            **(payload or {}),
        }
        with (_STATE / "alice_15m_monitor_commands.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _body_stgm_readonly() -> str:
    try:
        from System.swarm_stigmergic_pong_chorus import canonical_stgm_read_only

        info = canonical_stgm_read_only()
        if isinstance(info, dict):
            bal = (
                info.get("balance_stgm")
                or info.get("balance")
                or info.get("canonical_wallet_sum")
                or info.get("sum")
            )
            if bal is not None:
                return f"BODY STGM {float(bal):.2f} read-only"
    except Exception:
        pass
    try:
        from System.stgm_economy import build_economy_snapshot

        snap = build_economy_snapshot()
        if hasattr(snap, "canonical_wallet_sum"):
            return f"BODY STGM {float(snap.canonical_wallet_sum):.2f} read-only"
    except Exception:
        pass
    return "BODY STGM (read-only unavailable)"


class SiftaPredictionMarketWidget(QWidget):
    """Kalshi-inspired prediction market sandbox inside SIFTA Games."""

    _live_instance: Optional["SiftaPredictionMarketWidget"] = None
    _initialized_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                if id(existing) in cls._initialized_ids:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                    try:
                        existing._ensure_mdi_room()
                    except Exception:
                        pass
                    return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        try:
            self._ensure_mdi_room()
        except Exception:
            pass
        # Re-lock columns after MDI layout settles (anti-squeeze)
        try:
            for name in ("open_table", "last_run_table", "results_table", "live_odds_table"):
                t = getattr(self, name, None)
                if t is not None:
                    self._reapply_table_columns(t)
        except Exception:
            pass
        # Force US $ under STGM after every show (singleton may be stale)
        try:
            QTimer.singleShot(100, self._refresh_human_portfolio)
        except Exception:
            pass
        # Restart used to re-paint stale disk cache ($1.62). Live GET once on show.
        try:
            QTimer.singleShot(400, self._soft_fetch_usd_balance)
        except Exception:
            pass

    def _ensure_mdi_room(self) -> None:
        """Grow parent QMdiSubWindow so dense tables fit without hand-resize."""
        from PyQt6.QtWidgets import QMdiSubWindow

        p = self.parent()
        hops = 0
        while p is not None and hops < 8:
            if isinstance(p, QMdiSubWindow):
                try:
                    p.showMaximized()
                except Exception:
                    try:
                        p.resize(max(p.width(), 1400), max(p.height(), 900))
                    except Exception:
                        pass
                return
            p = p.parent()
            hops += 1

    def __init__(self, parent=None) -> None:
        if id(self) in type(self)._initialized_ids:
            return
        super().__init__(parent)
        type(self)._live_instance = self
        type(self)._initialized_ids.add(id(self))

        self.setWindowTitle(APP_TITLE)
        # Defaults sized so money columns fit (owner resize lesson 2026-07-12)
        # MDI often clamps; showEvent also maximizes parent subwindow.
        self.setMinimumSize(1100, 720)
        self.resize(1600, 1000)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            f"QWidget {{ background: {_BG}; color: {_TEXT}; font-size: {_F(12)}px; }}"
            f"QListWidget {{ background: {_CARD}; border: 1px solid #2a3548; border-radius: 8px; "
            f"font-size: {_F(12)}px; }}"
            f"QListWidget::item {{ padding: 12px; border-bottom: 1px solid #1e2636; }}"
            f"QListWidget::item:selected {{ background: #1e2a3d; }}"
            f"QPushButton {{ background: #1a2435; color: {_TEXT}; border: 1px solid #3a4a63; "
            f"padding: 10px 16px; border-radius: 8px; font-size: {_F(12)}px; font-weight: 700; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
            f"QComboBox, QDoubleSpinBox {{ background: #121927; border: 1px solid #3a4a63; "
            f"padding: 8px; border-radius: 4px; color: {_TEXT}; font-size: {_F(12)}px; }}"
            # No global QLabel font — compact strips use _FC; metrics/open use their own sizes
        )

        self.engine = SiftaMarketEngine(seed=1626, swarm_size=32)
        self.auto_swarm = False
        self.auto_autobet = False
        # r1628 P0 Option A: Qt app is pure glass. Headless monitor is sole bettor.
        self.paper_loop_on = True  # display: autopilot desired (monitor does the work)
        self._glass_only = True
        self._paper_tick_busy = False
        self._autobet_interval_ms = 15_000
        self._paper_interval_ms = 3_000  # disk repaint only — no network
        self._nav_section = "Crypto"
        self._nav_timeframe = "15 Minute"
        self._nav_asset = ""
        self._build_ui()
        self._refresh_all()

        self.timer = QTimer(self)
        self.timer.setInterval(2500)
        self.timer.timeout.connect(self._tick)

        self.autobet_timer = QTimer(self)
        self.autobet_timer.setInterval(self._autobet_interval_ms)
        self.autobet_timer.timeout.connect(self._autobet_tick)

        # Glass timer: repaint portfolio from disk — NEVER paper_loop_tick / settle API
        self.paper_timer = QTimer(self)
        self.paper_timer.setInterval(self._paper_interval_ms)
        self.paper_timer.timeout.connect(self._glass_tick)
        self.paper_timer.start()

        # Live network optional; off by default in glass mode (monitor + Sync button)
        self.live_timer = QTimer(self)
        self.live_timer.setInterval(30_000)
        self.live_timer.timeout.connect(self._live_refresh)
        # Do not auto-start network timer — Sync / manual refresh only (kills beachball)
        self._live_refresh_busy = False
        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(2000)
        self.ui_timer.timeout.connect(self._ui_paint_only)
        self.ui_timer.start()

        # Explicitly release writer election so headless monitor owns betting
        _write_receipt(
            "paper_loop_off",
            {
                "reason": "r1628_glass_only",
                "note": "Qt app is read-only glass; monitor is sole paper writer",
            },
        )
        _write_receipt(
            "open",
            {
                "mode": "glass_only_r1628",
                "minute7_max_secs": DEFAULT_MAX_SECS,
                "writer": "headless_monitor",
            },
        )
        _focus("Predictions glass · headless autopilot")
        _queue_monitor_cmd("ensure_running", {"source": "ui_open"})
        # Defer button chrome until after UI exists
        QTimer.singleShot(0, lambda: self._set_autopilot_ui(True))

    def _metric_card(self, title: str, accent: str) -> tuple[QFrame, QLabel, QLabel]:
        frame = QFrame(self)
        frame.setObjectName("PortfolioMetricCard")
        frame.setStyleSheet(
            f"QFrame#PortfolioMetricCard {{ background: {_PANEL}; border: 1px solid #27344a; "
            "border-radius: 12px; }"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)
        name = QLabel(title.upper())
        name.setStyleSheet(f"color: {_DIM}; font-size: {_F(10)}px; font-weight: 700;")
        value = QLabel("—")
        value.setFont(QFont("Menlo", _F(17), QFont.Weight.Bold))
        value.setStyleSheet(f"color: {accent};")
        sub = QLabel("")
        sub.setStyleSheet(f"color: {_DIM}; font-size: {_F(10)}px;")
        lay.addWidget(name)
        lay.addWidget(value)
        lay.addWidget(sub)
        return frame, value, sub

    def _portfolio_table(self, headers: list[str], *, compact: bool = False) -> QTableWidget:
        """Build a portfolio table. compact=True → denser fonts (history/odds only)."""
        table = QTableWidget(0, len(headers), self)
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setWordWrap(False)
        # Prefer horizontal scroll over crushing money columns (George squeeze 2026-07-12)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # compact: history + live odds (George screenshot areas) — original density
        fs = _FC if compact else _F
        scale = _FC_SCALE if compact else _FS
        table._sifta_compact = compact  # type: ignore[attr-defined]
        table._sifta_font_scale = scale  # type: ignore[attr-defined]
        hdr = table.horizontalHeader()
        hdr.setMinimumSectionSize(fs(40) if compact else fs(44))
        hdr.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hdr.setStretchLastSection(False)
        hdr.setCascadingSectionResizes(False)
        for i in range(len(headers)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
        cell_pad = "4px 6px" if compact else "8px 10px"
        hdr_pad = "4px 6px" if compact else "8px 10px"
        table.setStyleSheet(
            f"QTableWidget {{ background: {_PANEL}; alternate-background-color: #131d2b; "
            f"border: 1px solid #27344a; border-radius: 10px; color: {_TEXT}; "
            f"gridline-color: transparent; font-size: {fs(12)}px; }}"
            f"QHeaderView::section {{ background: #192438; color: {_DIM}; border: 0; "
            f"padding: {hdr_pad}; font-size: {fs(10)}px; font-weight: 700; "
            f"min-height: {fs(20)}px; }}"
            f"QTableWidget::item {{ padding: {cell_pad}; border-bottom: 1px solid #202c40; }}"
            "QTableWidget::item:selected { background: #243653; }"
            f"QScrollBar:vertical {{ width: {fs(10)}px; background: #0d121c; }}"
            f"QScrollBar:horizontal {{ height: {fs(12)}px; background: #0d121c; }}"
            f"QScrollBar::handle {{ background: #3a4a63; border-radius: 4px; min-width: {fs(24)}px; }}"
        )
        return table

    def _fit_table_columns(
        self,
        table: QTableWidget,
        *,
        stretch_col: int | None = None,
        widths: dict[int, int] | None = None,
    ) -> None:
        """Lock money columns at readable widths; stretch only one text col.

        George 2026-07-12 squeeze: Interactive mode let MDI crush ENTERED / STGM / x
        into ``1…`` / ``+0…``. Fixed widths + h-scroll instead of equal-squash.
        Widths scale with the table's font scale (compact vs main).
        """
        hdr = table.horizontalHeader()
        n = table.columnCount()
        compact = bool(getattr(table, "_sifta_compact", False))
        scale = float(getattr(table, "_sifta_font_scale", _FS))
        fs = _FC if compact else _F
        # Scale stored widths with font scale (base widths are for scale=1)
        raw_w = {int(k): int(v) for k, v in (widths or {}).items()}
        widths = {k: max(32, int(round(v * scale * 0.92))) for k, v in raw_w.items()}
        fixed_sum = 0
        for i in range(n):
            w = int(widths.get(i, fs(72)))
            if stretch_col is not None and i == stretch_col:
                hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
                # Floor so WHY never vanishes entirely
                try:
                    hdr.resizeSection(i, max(w, fs(100)))
                except Exception:
                    pass
                continue
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(i, w)
            fixed_sum += w
        hdr.setStretchLastSection(False)
        # Keep table wide enough that outer QScrollArea scrolls instead of crushing
        try:
            floor = 720 if compact else 900
            table.setMinimumWidth(min(2400, max(floor, fixed_sum + 180)))
        except Exception:
            pass
        # Store *base* widths so re-apply re-scales the same way
        table._sifta_col_widths = dict(raw_w)  # type: ignore[attr-defined]
        table._sifta_stretch_col = stretch_col  # type: ignore[attr-defined]

    def _reapply_table_columns(self, table: QTableWidget) -> None:
        """Re-lock column widths after setRowCount / clearSpans."""
        raw = getattr(table, "_sifta_col_widths", None)
        if not isinstance(raw, dict) or not raw:
            return
        stretch_col = getattr(table, "_sifta_stretch_col", None)
        self._fit_table_columns(table, stretch_col=stretch_col, widths=raw)

    def _build_human_ui(self) -> None:
        """One-screen portfolio view for a human watching with their eyes."""
        # Outer shell expands with MDI window; body scrolls if still tight
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {_BG}; border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background: {_BG}; }}"
        )
        shell.addWidget(scroll)

        body = QWidget()
        # Wider floor so ENTERED / STGM / x never equal-squash (horizontal scroll OK)
        body.setMinimumWidth(1400)
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(14, 12, 14, 10)
        root.setSpacing(8)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)
        # Compact header (George: reduce fonts only on these dense strips)
        # Title only — no tutorial subtitle (George: eyes hurt, not for the reader)
        title = QLabel("ALICE PREDICTIONS PORTFOLIO")
        title.setObjectName("PredictionsTitle")
        title.setFont(QFont("Helvetica Neue", _FC(16), QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_TEXT}; background: transparent; padding: 0;")
        title.setWordWrap(False)
        title.setMinimumHeight(_FC(24))
        title_box.addWidget(title)
        head.addLayout(title_box, 1)
        self.mode = QLabel("AUTOPILOT")
        self.mode.setStyleSheet(
            f"background: #103126; color: {_YES}; border: 1px solid #276d54; "
            f"padding: 6px 10px; border-radius: 10px; font-weight: 800; font-size: {_FC(11)}px;"
        )
        head.addWidget(self.mode)
        _btn_ss = (
            f"QPushButton {{ background: #1a2435; color: {_TEXT}; border: 1px solid #3a4a63; "
            f"padding: 6px 12px; border-radius: 6px; font-size: {_FC(11)}px; font-weight: 700; }}"
            f"QPushButton:hover {{ border-color: {_ACCENT}; }}"
        )
        sync_btn = QPushButton("Sync")
        sync_btn.setStyleSheet(_btn_ss)
        sync_btn.clicked.connect(self._sync_kalshi)
        head.addWidget(sync_btn)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(_btn_ss)
        refresh_btn.clicked.connect(self._refresh_kalshi)
        head.addWidget(refresh_btn)
        self.paper_btn = QPushButton("STGM Autopilot")
        self.paper_btn.setStyleSheet(_btn_ss)
        self.paper_btn.clicked.connect(self._toggle_paper_loop)
        head.addWidget(self.paper_btn)
        # Dual-lane: US $ betting master switch (default OFF — STGM independent)
        self.usd_lane_btn = QPushButton("US $ LANE OFF")
        self.usd_lane_btn.setStyleSheet(
            f"QPushButton {{ background: #2a1515; color: {_NO}; border: 1px solid #6d2727; "
            f"padding: 6px 12px; border-radius: 6px; font-size: {_FC(11)}px; font-weight: 800; }}"
            f"QPushButton:hover {{ border-color: {_GOLD}; }}"
        )
        self.usd_lane_btn.clicked.connect(self._toggle_usd_lane)
        head.addWidget(self.usd_lane_btn)
        # r1693: AMMO — dollars/contracts per dual ticket (default $2)
        self.ammo_lbl = QLabel("AMMO")
        self.ammo_lbl.setStyleSheet(
            f"color: {_GOLD}; font-weight: 800; font-size: {_FC(11)}px; padding-left: 6px;"
        )
        head.addWidget(self.ammo_lbl)
        self.ammo_edit = QLineEdit()
        self.ammo_edit.setPlaceholderText("2")
        self.ammo_edit.setFixedWidth(48)
        self.ammo_edit.setMaxLength(4)
        self.ammo_edit.setToolTip(
            "AMMO = contracts per US$ ticket (default 2). Each contract face $1 if win."
        )
        self.ammo_edit.setStyleSheet(
            f"QLineEdit {{ background: #15170d; color: {_GOLD}; border: 2px solid {_GOLD}; "
            f"padding: 4px 6px; border-radius: 6px; font-size: {_FC(12)}px; font-weight: 800; "
            f"font-family: Menlo; }}"
        )
        self.ammo_edit.editingFinished.connect(self._on_ammo_edited)
        head.addWidget(self.ammo_edit)
        root.addLayout(head)
        QTimer.singleShot(0, self._paint_usd_lane_button)
        QTimer.singleShot(0, self._paint_ammo_box)

        # Dense status strips — numbers only (George: no tutorial text)
        _strip_pad = "6px 10px"
        self.proof_lbl = QLabel("")
        self.proof_lbl.setWordWrap(True)
        self.proof_lbl.setStyleSheet(
            f"background: #111c2b; color: {_TEXT}; border: 1px solid #2e4260; "
            f"padding: {_strip_pad}; border-radius: 8px; font-family: Menlo; "
            f"font-size: {_FC(11)}px;"
        )
        root.addWidget(self.proof_lbl)
        self.rainman_lbl = QLabel("RAINMAN …")
        self.rainman_lbl.setWordWrap(True)
        self.rainman_lbl.setStyleSheet(
            f"background: #0f1a14; color: {_GOLD}; border: 1px solid #3a5a40; "
            f"padding: {_strip_pad}; border-radius: 8px; font-family: Menlo; "
            f"font-size: {_FC(11)}px; font-weight: 700;"
        )
        root.addWidget(self.rainman_lbl)
        self.ledger_deal_lbl = QLabel("r1648 DEAL · loading read-only mirror…")
        self.ledger_deal_lbl.setWordWrap(True)
        self.ledger_deal_lbl.setStyleSheet(
            f"background: #15170d; color: {_ACCENT}; border: 1px solid #59632a; "
            f"padding: {_strip_pad}; border-radius: 8px; font-family: Menlo; "
            f"font-size: {_FC(10)}px; font-weight: 700;"
        )
        root.addWidget(self.ledger_deal_lbl)
        # r1651 THE CLIMB — evidence ladder (recommendation only; no stake authority)
        self.climb_lbl = QLabel("CLIMB · RUNG 0 · fills …")
        self.climb_lbl.setWordWrap(True)
        self.climb_lbl.setStyleSheet(
            f"background: #0d1218; color: {_GOLD}; border: 1px solid #4a5a20; "
            f"padding: {_strip_pad}; border-radius: 8px; font-family: Menlo; "
            f"font-size: {_FC(10)}px; font-weight: 800;"
        )
        root.addWidget(self.climb_lbl)

        # Body STGM + HUGE Kalshi $ under it (George: US $1.62 must be easy to see)
        metrics = QHBoxLayout()
        metrics.setSpacing(8)
        money_card = QFrame(self)
        money_card.setObjectName("PortfolioMetricCard")
        money_card.setStyleSheet(
            f"QFrame#PortfolioMetricCard {{ background: {_PANEL}; border: 2px solid #5a4a20; "
            "border-radius: 12px; }"
        )
        money_lay = QVBoxLayout(money_card)
        money_lay.setContentsMargins(14, 12, 14, 12)
        money_lay.setSpacing(6)
        money_title = QLabel("STGM")
        money_title.setStyleSheet(f"color: {_DIM}; font-size: {_F(10)}px; font-weight: 700;")
        self.body_total_value = QLabel("—")
        self.body_total_value.setFont(QFont("Menlo", _F(15), QFont.Weight.Bold))
        self.body_total_value.setStyleSheet(f"color: {_GOLD};")
        # The line George actually looks for — large real dollars
        self.kalshi_usd_value = QLabel("US $ …")
        self.kalshi_usd_value.setFont(QFont("Menlo", max(28, _F(22)), QFont.Weight.Bold))
        self.kalshi_usd_value.setStyleSheet(
            f"color: {_YES}; background: #0a1810; border: 1px solid #276d54; "
            "border-radius: 8px; padding: 8px 10px;"
        )
        self.body_total_sub = self.kalshi_usd_value  # paint path alias
        self.usd_cash_value = self.kalshi_usd_value
        self.usd_portfolio_lbl = self.kalshi_usd_value
        money_lay.addWidget(money_title)
        money_lay.addWidget(self.body_total_value)
        money_lay.addWidget(self.kalshi_usd_value)
        metrics.addWidget(money_card, 2)
        card, self.body_pnl_value, self.body_pnl_sub = self._metric_card("STGM PnL", _YES)
        metrics.addWidget(card, 1)
        card, self.body_record_value, self.body_record_sub = self._metric_card(
            "How often she pays", _BLUE
        )
        metrics.addWidget(card, 1)
        card, self.body_risk_value, self.body_risk_sub = self._metric_card("Open risk", _ACCENT)
        metrics.addWidget(card, 1)
        root.addLayout(metrics)

        self.portfolio_alert_lbl = QLabel("")
        self.portfolio_alert_lbl.setWordWrap(True)
        self.portfolio_alert_lbl.hide()
        root.addWidget(self.portfolio_alert_lbl)

        # ── LAST RUN pinned under metrics (always visible WINS + LOSSES) ──
        self.last_run_banner = QLabel("LAST RUN · —")
        self.last_run_banner.setWordWrap(True)
        self.last_run_banner.setStyleSheet(
            f"background: #121a28; color: {_TEXT}; border: 1px solid #2a3a52; "
            f"padding: 12px 14px; border-radius: 8px; font-family: Menlo; font-size: {_F(12)}px; "
            "font-weight: 700;"
        )
        root.addWidget(self.last_run_banner)
        # No duplicate last_run_head — banner is enough
        self.last_run_head = self.last_run_banner  # alias so paint paths keep working

        self.last_run_table = self._portfolio_table(
            [
                "RESULT",
                "KIND",
                "MARKET",
                "BET",
                "STGM",
                "¢",
                "x",
                "$ HYP",
                "FEE-TRUE $",
                "ENTERED",
                "PnL STGM",
            ]
        )
        self._fit_table_columns(
            self.last_run_table,
            stretch_col=None,  # no crush-stretch — ENTERED must stay readable
            widths={
                # r1707: KIND + FEE-TRUE $; money cols fixed
                0: 52,
                1: 88,
                2: 80,
                3: 44,
                4: 110,
                5: 44,
                6: 48,
                7: 64,
                8: 72,
                9: 160,
                10: 110,
            },
        )
        self.last_run_table.setMinimumHeight(_F(200))
        self.last_run_table.setMaximumHeight(_F(280))
        last_run_panel = QWidget()
        last_run_l = QVBoxLayout(last_run_panel)
        last_run_l.setContentsMargins(0, 2, 0, 0)
        last_run_l.setSpacing(4)
        last_run_l.addWidget(self.last_run_table, 1)
        root.addWidget(last_run_panel)

        self.open_table = self._portfolio_table(
            ["MARKET", "BET", "STGM", "¢", "x", "$ HYP IF WIN", "ENTERED", "WHY", "LEFT", "STATUS"]
        )
        # Fixed money cols (no Interactive squash). WHY stretches leftover only.
        # ENTERED ~ "17:49:27 @ 10:32 left" needs ~180px (George squeeze screenshot).
        self._fit_table_columns(
            self.open_table,
            stretch_col=7,
            widths={
                0: 92,   # MARKET  "BTC 15m"
                1: 52,   # BET
                2: 150,  # STGM    "½ · 0.00050 (50¢)"
                3: 48,   # ¢
                4: 58,   # x       "1.25x"
                5: 82,   # IF WIN$ "+$0.30"
                6: 180,  # ENTERED full clock
                7: 140,  # WHY stretch floor
                8: 56,   # LEFT
                9: 72,   # STATUS (▲ +3¢ / ▼ -5¢ live mark)
            },
        )
        self.open_table.setMinimumHeight(_F(140))
        open_panel = QWidget()
        open_l = QVBoxLayout(open_panel)
        open_l.setContentsMargins(0, 0, 0, 0)
        open_l.setSpacing(4)
        open_head = QLabel("OPEN — STGM (paper learning)")
        open_head.setStyleSheet(f"color: {_TEXT}; font-size: {_F(13)}px; font-weight: 800;")
        open_l.addWidget(open_head)
        open_l.addWidget(self.open_table, 1)

        # r1707: STGM SCALP strip (fee-true, honest caveat)
        self.scalp_strip_lbl = QLabel("STGM SCALP · —")
        self.scalp_strip_lbl.setWordWrap(True)
        self.scalp_strip_lbl.setStyleSheet(
            f"background: #12180e; color: {_GOLD}; border: 1px solid #4a5a2a; "
            f"padding: 6px 10px; border-radius: 8px; font-family: Menlo; font-size: {_FC(10)}px; "
            "font-weight: 700;"
        )
        root.addWidget(self.scalp_strip_lbl)

        self.results_table = self._portfolio_table(
            [
                "RESULT",
                "KIND",
                "MARKET",
                "BET",
                "¢",
                "x",
                "$ HYP",
                "FEE-TRUE $",
                "ENTERED",
                "WHY",
                "PnL STGM",
            ],
            compact=True,
        )
        self._fit_table_columns(
            self.results_table,
            stretch_col=9,
            widths={
                0: 48,
                1: 80,
                2: 72,
                3: 40,
                4: 40,
                5: 48,
                6: 56,
                7: 64,
                8: 150,
                9: 100,
                10: 100,
            },
        )
        results_panel = QWidget()
        results_l = QVBoxLayout(results_panel)
        results_l.setContentsMargins(0, 0, 0, 0)
        results_l.setSpacing(4)
        result_head = QLabel("HISTORY — STGM (paper learning)")
        result_head.setStyleSheet(
            f"color: {_TEXT}; font-size: {_FC(12)}px; font-weight: 800;"
        )
        self.history_head = result_head
        results_l.addWidget(result_head)
        self.results_table.setMinimumHeight(120)
        results_l.addWidget(self.results_table, 1)

        # r1707: TRAIN rows (shadow only)
        self.train_table = self._portfolio_table(
            ["RESULT", "KIND", "MARKET", "BET", "¢", "FEE-TRUE $", "WHY"],
            compact=True,
        )
        self._fit_table_columns(
            self.train_table,
            stretch_col=6,
            widths={0: 48, 1: 56, 2: 72, 3: 40, 4: 40, 5: 72, 6: 120},
        )
        train_head = QLabel("TRAIN — shadow Alice (never real $)")
        train_head.setStyleSheet(
            f"color: {_DIM}; font-size: {_FC(11)}px; font-weight: 700;"
        )
        self.train_head = train_head
        results_l.addWidget(train_head)
        self.train_table.setMaximumHeight(_FC(110))
        results_l.addWidget(self.train_table)

        # US$ lane label (cash is Kalshi portfolio / deal strip — not this STGM table)
        usd_lane_lbl = QLabel("US$ (real cash · Kalshi) — see portfolio strip · not STGM HISTORY")
        usd_lane_lbl.setStyleSheet(
            f"color: {_DIM}; font-size: {_FC(10)}px; font-weight: 600;"
        )
        results_l.addWidget(usd_lane_lbl)

        self.live_odds_table = self._portfolio_table(
            ["MARKET", "UP", "UPx", "DOWN", "DNx", "VOL", "LEFT", "ALICE"],
            compact=True,
        )
        self._fit_table_columns(
            self.live_odds_table,
            stretch_col=0,
            widths={0: 150, 1: 52, 2: 56, 3: 56, 4: 56, 5: 64, 6: 56, 7: 64},
        )
        odds_panel = QWidget()
        odds_l = QVBoxLayout(odds_panel)
        odds_l.setContentsMargins(0, 0, 0, 0)
        odds_l.setSpacing(4)
        odds_head = QLabel("ODDS")
        odds_head.setStyleSheet(
            f"color: {_TEXT}; font-size: {_FC(12)}px; font-weight: 800;"
        )
        odds_l.addWidget(odds_head)
        odds_l.addWidget(self.live_odds_table, 1)

        lower = QSplitter(Qt.Orientation.Horizontal)
        lower.addWidget(results_panel)
        lower.addWidget(odds_panel)
        lower.setStretchFactor(0, 3)
        lower.setStretchFactor(1, 2)
        lower.setSizes([700, 380])
        lower.setChildrenCollapsible(False)

        # Open + history/odds only — last run is already pinned above
        all_tables = QSplitter(Qt.Orientation.Vertical)
        all_tables.addWidget(open_panel)
        all_tables.addWidget(lower)
        all_tables.setStretchFactor(0, 2)
        all_tables.setStretchFactor(1, 3)
        all_tables.setSizes([220, 400])
        all_tables.setChildrenCollapsible(False)
        all_tables.setMinimumHeight(360)
        root.addWidget(all_tables, 1)

        # Hidden — no wall of learning prose (George: eyes hurt from useless text)
        self.learn_lbl = QLabel("")
        self.learn_lbl.hide()
        self.event_lbl = QLabel("")
        self.event_lbl.hide()

        # Compatibility controls for old engine methods. MUST live in a
        # zero-size hidden bin — parented-to-self floating QListWidgets sat at
        # (0,0) and painted a grey square over "ALICE PREDICTIONS PORTFOLIO"
        # (George screenshot 2026-07-12: "TIONS PORTFOLIO" + grey block).
        self._compat_bin = QWidget(self)
        self._compat_bin.setObjectName("PredictionsCompatBin")
        self._compat_bin.setFixedSize(0, 0)
        self._compat_bin.hide()
        self._compat_bin.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        _bin = self._compat_bin

        self.nav_list = QListWidget(_bin)
        self._nav_items = []
        for label, kind, value in (
            ("15 Minute", "timeframe", "15 Minute"),
            ("Hourly", "timeframe", "Hourly"),
            ("Daily", "timeframe", "Daily"),
            ("Weekly", "timeframe", "Weekly"),
            ("Monthly", "timeframe", "Monthly"),
            *[(a, "asset", a) for a in CRYPTO_ASSETS],
        ):
            self._nav_items.append((kind, value, label))
            self.nav_list.addItem(QListWidgetItem(label))
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_nav)
        self.list = QListWidget(_bin)
        self.list.currentRowChanged.connect(self._on_select)
        self.filter_lbl = QLabel(_bin)
        self.detail = QLabel(_bin)
        self.odds = QLabel(_bin)
        self.watch_lbl = QLabel(_bin)
        self.bal_lbl = QLabel(_bin)
        self.auto_btn = QPushButton(_bin)
        self.ablation_lbl = QLabel(_bin)
        self.side = QComboBox(_bin)
        self.side.addItems(["YES", "NO"])
        self.stake = QDoubleSpinBox(_bin)
        self.ab_auto_btn = QPushButton(_bin)
        self.ab_status = QLabel(_bin)
        self.ab_monitor = QListWidget(_bin)
        self.ab_results = QLabel(_bin)
        self.lb_profit = QListWidget(_bin)
        self.lb_volume = QListWidget(_bin)
        self.lb_preds = QListWidget(_bin)
        self.port_open = QListWidget(_bin)
        self.port_hist = QListWidget(_bin)
        self.port_summary = QLabel(_bin)
        self.tabs = None

        # First paint from disk only — network rollover runs after show (bg worker)
        self._refresh_all()
        QTimer.singleShot(50, self._live_refresh)

    def _build_ui(self) -> None:
        self._build_human_ui()
        return
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # ── Money glass: live public odds only. Trade on Kalshi Safari. ──
        head = QHBoxLayout()
        title = QLabel("Kalshi odds")
        title.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_GOLD};")
        head.addWidget(title)
        self.mode = QLabel("LIVE")
        self.mode.setStyleSheet(f"color: {_ACCENT}; font-weight: 700;")
        head.addWidget(self.mode)
        head.addStretch(1)
        sync_btn = QPushButton("Sync")
        sync_btn.setStyleSheet(
            f"QPushButton {{ border-color: {_GOLD}; color: {_GOLD}; font-weight: 700; }}"
        )
        sync_btn.clicked.connect(self._sync_kalshi)
        head.addWidget(sync_btn)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_kalshi)
        head.addWidget(refresh_btn)
        self.paper_btn = QPushButton(f"Paper @ min{DEFAULT_MAX_SECS // 60}")
        self.paper_btn.setStyleSheet(
            f"QPushButton {{ border-color: {_YES}; color: {_YES}; font-weight: 700; }}"
        )
        self.paper_btn.clicked.connect(self._toggle_paper_loop)
        head.addWidget(self.paper_btn)
        bet_now = QPushButton("Bet all 15m")
        bet_now.clicked.connect(self._paper_bet_now)
        head.addWidget(bet_now)
        settle_btn = QPushButton("Settle")
        settle_btn.clicked.connect(self._paper_settle_now)
        head.addWidget(settle_btn)
        root.addLayout(head)

        self.proof_lbl = QLabel("")
        self.proof_lbl.setStyleSheet(
            f"background: {_CARD}; color: {_TEXT}; border: 1px solid #2a3548; "
            f"padding: 8px; border-radius: 6px; font-family: Menlo; font-size: {_F(11)}px;"

        )
        root.addWidget(self.proof_lbl)

        body = QHBoxLayout()
        body.setSpacing(8)

        nav_col = QVBoxLayout()
        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(140)
        self.nav_list.setMinimumWidth(120)
        self.nav_list.setStyleSheet(
            f"QListWidget {{ background: {_CARD}; border: 1px solid #2a3548; border-radius: 8px; }}"
            f"QListWidget::item {{ padding: 6px 8px; color: {_DIM}; }}"
            f"QListWidget::item:selected {{ background: #1e2a3d; color: {_GOLD}; }}"
        )
        self._nav_items: list[tuple[str, str, str]] = []
        for label, kind, value in (
            ("15 Minute", "timeframe", "15 Minute"),
            ("Hourly", "timeframe", "Hourly"),
            ("Daily", "timeframe", "Daily"),
            ("Weekly", "timeframe", "Weekly"),
            ("Monthly", "timeframe", "Monthly"),
            *[(a, "asset", a) for a in CRYPTO_ASSETS],
        ):
            self._nav_items.append((kind, value, label))
            self.nav_list.addItem(QListWidgetItem(label))
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_nav)
        nav_col.addWidget(self.nav_list, 1)
        body.addLayout(nav_col)

        mid_col = QVBoxLayout()
        self.filter_lbl = QLabel("15 Minute")
        self.filter_lbl.setStyleSheet(f"color: {_ACCENT}; font-weight: 700;")
        mid_col.addWidget(self.filter_lbl)
        self.list = QListWidget()
        self.list.setMinimumWidth(340)
        self.list.currentRowChanged.connect(self._on_select)
        mid_col.addWidget(self.list, 1)
        body.addLayout(mid_col, 2)

        right = QVBoxLayout()
        self.detail = QLabel("Sync → pick a clock")
        self.detail.setWordWrap(True)
        self.detail.setFont(QFont("Menlo", 12))
        self.detail.setStyleSheet(f"background: {_CARD}; padding: 14px; border-radius: 8px;")
        self.detail.setMinimumHeight(160)
        right.addWidget(self.detail)
        self.odds = QLabel()
        self.odds.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        self.odds.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.odds)
        # stubs so older methods don't AttributeError
        self.watch_lbl = QLabel("")
        self.watch_lbl.hide()
        self.learn_lbl = QLabel("")
        self.learn_lbl.hide()
        self.event_lbl = QLabel("")
        self.event_lbl.setStyleSheet(f"color: {_DIM}; font-size: {_F(10)}px;")
        right.addWidget(self.event_lbl)
        self.bal_lbl = QLabel("")
        self.bal_lbl.hide()
        self.auto_btn = QPushButton()
        self.auto_btn.hide()
        self.ablation_lbl = QLabel("")
        self.ablation_lbl.hide()
        self.side = QComboBox()
        self.side.addItems(["YES", "NO"])
        self.side.hide()
        self.stake = QDoubleSpinBox()
        self.stake.hide()
        self.ab_auto_btn = QPushButton()
        self.ab_auto_btn.hide()
        self.ab_status = QLabel("")
        self.ab_status.hide()
        self.ab_monitor = QListWidget()
        self.ab_monitor.hide()
        self.ab_results = QLabel("")
        self.ab_results.hide()
        self.lb_profit = QListWidget()
        self.lb_volume = QListWidget()
        self.lb_preds = QListWidget()
        self.port_open = QListWidget()
        self.port_hist = QListWidget()
        self.port_summary = QLabel("")
        right.addStretch(1)
        body.addLayout(right, 2)

        # ── tabs: Board + AutoBet (paper loop) ──
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid #2a3548; border-radius: 6px; }}"
            f"QTabBar::tab {{ background: #121927; color: {_DIM}; padding: 8px 16px; }}"
            f"QTabBar::tab:selected {{ color: {_GOLD}; border-bottom: 2px solid {_GOLD}; }}"
        )
        board_page = QWidget()
        board_l = QVBoxLayout(board_page)
        board_l.setContentsMargins(0, 0, 0, 0)
        board_l.addLayout(body, 1)
        self.tabs.addTab(board_page, "Board")

        ab = QWidget()
        ab_l = QVBoxLayout(ab)
        self.ab_status = QLabel(f"Paper @ minute {DEFAULT_MAX_SECS // 60}: Off")
        self.ab_status.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        self.ab_status.setStyleSheet(f"color: {_GOLD};")
        ab_l.addWidget(self.ab_status)
        ab_hint = QLabel(
            f"When clock ≤ {DEFAULT_MAX_SECS // 60}:00 left → Alice picks follow/fade/sit-out "
            f"from her learned trails + writes alice_15m_results.md (GAME_STGM only, not real $)"
        )
        ab_hint.setWordWrap(True)
        ab_hint.setStyleSheet(f"color: {_DIM}; font-size: {_F(11)}px;")
        ab_l.addWidget(ab_hint)
        # Alice's learning body state (pheromone trails, exploration, stability)
        self.learn_lbl = QLabel("learning: no lessons yet")
        self.learn_lbl.setWordWrap(True)
        self.learn_lbl.setStyleSheet(
            f"background: {_CARD}; color: {_ACCENT}; border: 1px solid #2a3548; "
            f"padding: 8px; border-radius: 6px; font-family: Menlo; font-size: {_F(11)}px;"

        )
        ab_l.addWidget(self.learn_lbl)
        ab_row = QHBoxLayout()
        self.ab_auto_btn = QPushButton("Start")
        self.ab_auto_btn.setStyleSheet(
            f"QPushButton {{ border-color: {_YES}; color: {_YES}; font-weight: 700; }}"
        )
        self.ab_auto_btn.clicked.connect(self._toggle_paper_loop)
        ab_row.addWidget(self.ab_auto_btn)
        b1 = QPushButton("Bet all 15m")
        b1.clicked.connect(self._paper_bet_now)
        ab_row.addWidget(b1)
        b2 = QPushButton("Settle")
        b2.clicked.connect(self._paper_settle_now)
        ab_row.addWidget(b2)
        ab_row.addStretch(1)
        ab_l.addLayout(ab_row)
        self.ab_monitor = QListWidget()
        self.ab_monitor.setStyleSheet(
            f"QListWidget {{ background: {_CARD}; border: 1px solid #2a3548; }}"
            f"QListWidget::item {{ padding: 8px; }}"
        )
        ab_l.addWidget(self.ab_monitor, 1)
        self.ab_results = QLabel("")
        self.ab_results.setWordWrap(True)
        self.ab_results.setStyleSheet(f"color: {_TEXT}; font-family: Menlo; font-size: {_F(11)}px;")
        ab_l.addWidget(self.ab_results)
        self.tabs.addTab(ab, "AutoBet")
        root.addWidget(self.tabs, 1)

        self.footer = QLabel(
            "Paper @ minute 11 = learned follow/fade/sit-out · report → "
            "alice_15m_results.md · paper evidence is not live-trading proof"
        )
        self.footer.setStyleSheet(f"color: {_DIM}; font-size: {_F(10)}px;")
        root.addWidget(self.footer)
        # pull live 15m so AutoBet tab is not empty on open
        try:
            self.engine.rollover_15m_clocks()
        except Exception:
            pass
        self._refresh_proof()
        self._refresh_all()
        self._refresh_autobet_monitor()

    def _selected_market_id(self) -> Optional[str]:
        item = self.list.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _fill_leaderboard(self, widget: QListWidget, metric: str) -> None:
        widget.clear()
        for row in self.engine.leaderboard(metric=metric, limit=24):  # type: ignore[arg-type]
            name = row["display_name"]
            if row.get("is_owner"):
                name = f"★ {name}"
            if metric == "profit":
                val = f"{row['profit']:+.2f} {TOKEN}"
            elif metric == "volume":
                val = f"{row['volume']:.1f} {TOKEN}"
            else:
                val = f"{row['predictions']} preds"
            item = QListWidgetItem(f"#{row['rank']:02d}  {name}\n     {val}")
            if row.get("is_owner"):
                item.setForeground(QColor(_GOLD))
            widget.addItem(item)

    def _refresh_portfolio(self) -> None:
        p = self.engine.portfolio()
        pnl = float(p.get("predictions_pnl") or 0.0)
        color = _YES if pnl >= 0 else _NO
        self.port_summary.setText(
            f"★ {p['display_name']}  ·  Cash {p['cash']:.2f} {TOKEN}  ·  "
            f"Predictions PnL {pnl:+.2f}  ·  Volume {p['volume']:.1f}  ·  "
            f"{p['predictions']} predictions"
        )
        self.port_summary.setStyleSheet(f"color: {color}; padding: 8px; font-weight: 700;")
        self.port_open.clear()
        for row in p.get("open_positions") or []:
            side = "YES" if row.get("yes", 0) > 0 else "NO"
            amt = row.get("yes") or row.get("no") or 0
            self.port_open.addItem(
                f"{row['title']}\n  {side}  stake {row['cost']:.2f}  ·  open  ·  "
                f"yes price {row['yes_price']:.0%}"
            )
        if not p.get("open_positions"):
            self.port_open.addItem("—")
        self.port_hist.clear()
        for h in p.get("history") or []:
            pnl_h = h.get("pnl")
            sign = f"{pnl_h:+.2f}" if pnl_h is not None else "—"
            status = h.get("status") or "closed"
            item = QListWidgetItem(
                f"{h.get('title')}\n  {str(h.get('side') or '').upper()}  ·  {status}  ·  "
                f"stake {h.get('stake', 0):.2f}  ·  PnL {sign} {TOKEN}"
            )
            if isinstance(pnl_h, (int, float)):
                item.setForeground(QColor(_YES if pnl_h >= 0 else _NO))
            self.port_hist.addItem(item)
        if not p.get("history"):
            self.port_hist.addItem("—")

    @staticmethod
    def _table_item(
        table: QTableWidget,
        row: int,
        column: int,
        text: str,
        *,
        color: str = _TEXT,
        bold: bool = False,
        center: bool = False,
        tooltip: str = "",
    ) -> None:
        item = QTableWidgetItem(str(text))
        item.setForeground(QColor(color))
        if bold:
            # Match table density (compact history/odds vs main open board)
            compact = bool(getattr(table, "_sifta_compact", False))
            item.setFont(
                QFont("Menlo", _FC(10) if compact else _F(10), QFont.Weight.Bold)
            )
        if center:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if tooltip:
            item.setToolTip(str(tooltip))
        table.setItem(row, column, item)

    def _paint_stgm_history_row(
        self,
        table: QTableWidget,
        i: int,
        row: dict[str, Any],
        *,
        compact: bool = False,
    ) -> None:
        """r1707: paint RESULT/KIND/…/FEE-TRUE for LAST RUN or HISTORY."""
        color = _YES if row.get("win") else _NO
        label = str(row.get("result") or ("WIN" if row.get("win") else "LOSS"))
        kind = glass_kind_label(row)
        kind_col = (
            _GOLD
            if "SCALP" in kind
            else (_DIM if "TRAIN" in kind else _TEXT)
        )
        ft = row.get("pnl_usd_fee_true")
        if ft is None:
            ft_s = "—"
            ft_col = _DIM
        else:
            try:
                ftv = float(ft)
                ft_s = f"{ftv:+.2f}"
                ft_col = _YES if ftv >= 0 else _NO
            except (TypeError, ValueError):
                ft_s = "—"
                ft_col = _DIM
        mult = float(row.get("mult_net") or 0.0)
        usd = float(row.get("if_real_usd") or 0.0)
        entered = str(row.get("entry_clock") or "—")
        side = str(row.get("side") or "?")
        self._table_item(table, i, 0, label, color=color, bold=True, center=True)
        self._table_item(
            table,
            i,
            1,
            kind,
            color=kind_col,
            bold=True,
            center=True,
            tooltip="SCALP=fee-true mid-window · HOLD=settle · ⚑7:30=force flat · ⇄DUAL=US$ twin",
        )
        # LAST RUN has STGM stake col; HISTORY does not
        if table.columnCount() >= 11:
            # RESULT KIND MARKET BET STGM ¢ x $HYP FEE ENTERED PnL
            self._table_item(table, i, 2, f"{row.get('asset')} 15m", bold=True)
            self._table_item(
                table,
                i,
                3,
                side,
                color=_YES if side == "UP" else _NO,
                bold=True,
                center=True,
            )
            self._table_item(
                table,
                i,
                4,
                str(
                    row.get("stake_label")
                    or f"{float(row.get('stgm_at_risk') or 0):.5f}"
                ),
                color=_GOLD,
                center=True,
                tooltip="½ = THIN Rainman half-ticket (50¢)"
                if row.get("thin")
                else "Full ticket 100¢",
            )
            self._table_item(
                table, i, 5, f"{float(row.get('price_cents') or 0):.0f}¢", center=True
            )
            self._table_item(table, i, 6, f"{mult:.2f}x", color=_GOLD, center=True)
            self._table_item(
                table,
                i,
                7,
                f"{usd:+.2f}",
                color=color,
                bold=True,
                center=True,
                tooltip="HYPOTHETICAL dollar PnL · Kalshi $ OFF",
            )
            self._table_item(
                table,
                i,
                8,
                ft_s,
                color=ft_col,
                bold=True,
                center=True,
                tooltip="Fee-true mid-window / scalp PnL (same fee model as US$)",
            )
            tip_e = entered
            if row.get("entry_ts"):
                try:
                    tip_e = datetime.fromtimestamp(float(row["entry_ts"])).isoformat(
                        timespec="seconds"
                    )
                except Exception:
                    pass
            self._table_item(
                table,
                i,
                9,
                entered,
                color=_BLUE,
                center=True,
                tooltip=f"bet entry · {tip_e}",
            )
            self._table_item(
                table,
                i,
                10,
                str(
                    row.get("body_pnl_label")
                    or f"{float(row.get('body_pnl_stgm') or 0):+.5f}"
                ),
                color=color,
                bold=True,
                center=True,
            )
        else:
            # RESULT KIND MARKET BET ¢ x $HYP FEE ENTERED WHY PnL
            self._table_item(table, i, 2, f"{row.get('asset')} 15m", bold=True)
            self._table_item(
                table,
                i,
                3,
                side,
                color=_YES if side == "UP" else _NO,
                bold=True,
                center=True,
            )
            self._table_item(
                table, i, 4, f"{float(row.get('price_cents') or 0):.0f}¢", center=True
            )
            self._table_item(table, i, 5, f"{mult:.2f}x", color=_GOLD, center=True)
            self._table_item(
                table,
                i,
                6,
                f"{usd:+.2f}",
                color=color,
                bold=True,
                center=True,
                tooltip="HYPOTHETICAL · Kalshi $ OFF",
            )
            self._table_item(
                table,
                i,
                7,
                ft_s,
                color=ft_col,
                bold=True,
                center=True,
                tooltip="Fee-true $ · same fee model as US$",
            )
            self._table_item(
                table,
                i,
                8,
                entered,
                color=_BLUE,
                center=True,
                tooltip=str(row.get("entry_ts") or entered),
            )
            why = str(row.get("decision_reason") or "chart evidence warming")
            if row.get("thin"):
                why = f"½ THIN · {why}"
            if row.get("force_flat"):
                why = f"⚑ FLAT 7:30 · {why}"
            self._table_item(table, i, 9, why, color=_DIM, tooltip=why)
            self._table_item(
                table,
                i,
                10,
                str(
                    row.get("body_pnl_label")
                    or f"{float(row.get('body_pnl_stgm') or 0):+.5f}"
                ),
                color=color,
                bold=True,
                center=True,
            )

    def _kalshi_predictions_cash_str(self) -> str:
        """Kalshi Predictions cash for glass (never logs secrets)."""
        try:
            from System.kalshi_portfolio_read import cache_status, load_cache

            cache = load_cache() or {}
            balance = (cache_status(cache).get("balance") or {})
            if balance.get("known") and isinstance(balance.get("value"), (int, float)):
                freshness = "" if balance.get("fresh") else " · STALE"
                if balance.get("error"):
                    freshness = " · CACHED/READ ERR"
                return f"US ${float(balance['value']):,.2f}{freshness}"
            if not cache:
                return "US $ …"
            return "US $ ? · NOT FETCHED"
        except Exception:
            return "US $ —"

    def _soft_fetch_usd_balance(self) -> None:
        """Read-only cash + position GETs in bg for a truthful portfolio mirror.

        Does not place orders. Throttled so showEvent thrash cannot spam Kalshi.
        """
        if getattr(self, "_usd_fetch_busy", False):
            return
        now = time.time()
        last = float(getattr(self, "_usd_fetch_ts", 0.0) or 0.0)
        if now - last < 25.0:  # min 25s between soft fetches
            try:
                self._refresh_human_portfolio()
            except Exception:
                pass
            return
        try:
            from System.kalshi_credentials import credentials_status

            if not credentials_status().get("ready"):
                return
        except Exception:
            return
        self._usd_fetch_busy = True
        self._usd_fetch_ts = now

        def _work() -> dict:
            from System.kalshi_portfolio_read import fetch_portfolio

            return fetch_portfolio(timeout=12.0)

        def _apply(r: Any) -> None:
            self._usd_fetch_busy = False
            if not isinstance(r, dict) or r.get("_bg_error"):
                return
            try:
                self._refresh_human_portfolio()
            except Exception:
                pass
            if r.get("balance_usd") is not None:
                try:
                    self.event_lbl.setText(
                        f"US ${float(r['balance_usd']):,.2f} · cash + positions read-only"
                    )
                except Exception:
                    pass

        self._run_bg(_work, _apply)

    def _paint_usd_portfolio_mirror(self) -> None:
        """Ensure Kalshi cash is under STGM (body_total_sub)."""
        if not hasattr(self, "body_total_sub"):
            return
        # Full repaint of STGM + US$ line happens in _refresh_human_portfolio
        try:
            cash = self._kalshi_predictions_cash_str()
            # Don't wipe STGM line if body_total already set — only used early
            if not self.body_total_sub.text() or self.body_total_sub.text().startswith("US"):
                self.body_total_sub.setText(cash)
                self.body_total_sub.setStyleSheet(f"color: {_GOLD}; font-size: {_F(12)}px;")
        except Exception:
            pass

    def _refresh_human_portfolio(self) -> None:
        if not hasattr(self, "open_table"):
            return
        snap = _cached_human_portfolio(_STATE)
        pnl = float(snap["body_pnl_stgm"])
        pnl_color = _YES if pnl >= 0.0 else _NO
        # STGM on top; huge US $ under it (George: was too small to see)
        self.body_total_value.setText(f"{snap['body_total_stgm']:,.4f}")
        cash = self._kalshi_predictions_cash_str()
        usd_lbl = getattr(self, "kalshi_usd_value", None) or self.body_total_sub
        usd_lbl.setText(cash)
        usd_lbl.setFont(QFont("Menlo", max(28, _F(22)), QFont.Weight.Bold))
        usd_lbl.setStyleSheet(
            f"color: {_YES}; background: #0a1810; border: 1px solid #276d54; "
            "border-radius: 8px; padding: 10px 12px;"
        )
        usd = float(snap.get("body_pnl_usd_hyp") or 0.0)
        try:
            from System.sifta_15m_money_math import (
                format_stgm_with_cents,
                stgm_to_usd,
            )

            pnl_txt = format_stgm_with_cents(pnl, signed=True)
            risk_txt = format_stgm_with_cents(
                float(snap["open_risk_stgm"]), signed=False
            )
            cap = float(snap["max_open_stgm"] or 0.0)
            cap_usd = stgm_to_usd(cap)
        except Exception:
            pnl_txt = f"{pnl:+.5f}"
            risk_txt = f"{float(snap['open_risk_stgm']):.5f}"
            cap = float(snap["max_open_stgm"] or 0.0)
            cap_usd = cap / 0.001 if cap else 0.0
        self.body_pnl_value.setText(pnl_txt)
        self.body_pnl_value.setStyleSheet(f"color: {pnl_color};")
        self.body_pnl_sub.setText(f"≈ {usd:+.2f}$ hyp")
        # Primary: win rate (what you need). Sub: paid vs lost in plain words.
        wins = int(snap["body_wins"])
        losses = int(snap["body_losses"])
        total = wins + losses
        wr = float(snap["body_win_rate"] or 0.0)
        self.body_record_value.setText(f"{wr:.0%}")
        if total > 0:
            self.body_record_sub.setText(
                f"{wins} paid · {losses} died · {total} tickets"
            )
        else:
            self.body_record_sub.setText("no settles yet")
        self.body_risk_value.setText(risk_txt)
        # Only "N open" — no "cap $20" every frame (George: what do I read that for?)
        n_open = len(snap["open"])
        self.body_risk_sub.setText(f"{n_open} open" if n_open else "flat")
        if hasattr(self, "ledger_deal_lbl"):
            try:
                from System.kalshi_usd_hand import status_line as usd_hand_status

                hand_bit = usd_hand_status(_STATE)
            except Exception:
                hand_bit = "US $ HAND UNKNOWN"
            deal_text, deal_tip = format_r1648_deal_strip(
                snap, hand_status=hand_bit
            )
            self.ledger_deal_lbl.setText(deal_text)
            self.ledger_deal_lbl.setToolTip(deal_tip)
            exchange = snap.get("usd_exchange") or {}
            deal_color = (
                _GOLD
                if exchange.get("error")
                else (_ACCENT if exchange.get("known") else _DIM)
            )
            self.ledger_deal_lbl.setStyleSheet(
                f"background: #15170d; color: {deal_color}; border: 1px solid #59632a; "
                f"padding: 6px 10px; border-radius: 8px; font-family: Menlo; "
                f"font-size: {_FC(10)}px; font-weight: 700;"
            )
        # r1651 THE CLIMB strip — evidence ladder (rec only)
        if hasattr(self, "climb_lbl"):
            try:
                from System.sifta_the_climb import evaluate as climb_evaluate

                ce = climb_evaluate()
                g = ce.get("gates_to_next") or {}
                ev = g.get("ev")
                ev_s = f"{ev:+.3f}" if isinstance(ev, (int, float)) else "n/a"
                lcb = g.get("ev_lower_95")
                lcb_s = f"{lcb:+.3f}" if isinstance(lcb, (int, float)) else "n/a"
                prom = "YES" if ce.get("promotion_earned") else "NO"
                self.climb_lbl.setText(
                    f"CLIMB RUNG {ce.get('current_rung', 0)} · "
                    f"{ce.get('current_contracts', 1)} ct · "
                    f"exchange fills {g.get('fills', '?')} · "
                    f"EV {ev_s} · 95% floor {lcb_s} · promote {prom} · "
                    f"capacity proven {g.get('capacity_proven_contracts', 0)} ct"
                )
                self.climb_lbl.setToolTip(
                    "Exchange receipts only, after exact Kalshi fees. Stake does not "
                    "auto-raise. 100 fills, positive 95% EV floor, bankroll, and "
                    "observed fill capacity are all required."
                )
            except Exception as exc:
                self.climb_lbl.setText(f"CLIMB · n/a ({type(exc).__name__})")
        # Rainman epoch strip
        if hasattr(self, "rainman_lbl"):
            ep = snap.get("active_epoch") or {}
            paper = snap.get("paper") or {}
            # Edge field climate (invention r1634)
            crystal_bit = ""
            try:
                from System.swarm_sifta_rainman_vectors import load_climate, crystal_bar

                cl = load_climate(state_dir=_STATE, max_age=300.0)
                bb = cl.get("by_bucket") or {}
                parts = []
                for bk in ("70-74", "75-79", "80-88"):
                    row = bb.get(bk) or {}
                    if int(row.get("n") or 0) > 0:
                        parts.append(
                            f"{bk}:{float(row.get('wr') or 0):.0%}n{int(row.get('n') or 0)}"
                        )
                # r1638 / r1643 ghosts — numbers only
                ghost_bit = ""
                try:
                    from System.swarm_sifta_ghost_twin import ghost_status

                    gs = ghost_status(state_dir=_STATE)
                    if int(gs.get("n_settled") or 0) > 0:
                        ghost_bit = (
                            f" · GHOST {float(gs.get('ghost_pnl') or 0):+.1f}u"
                            f" FIELD {float(gs.get('edge_field_value') or 0):+.1f}u"
                        )
                except Exception:
                    pass
                try:
                    from System.swarm_sifta_early_bird_ghost import early_bird_status

                    eb = early_bird_status(state_dir=_STATE)
                    if int(eb.get("n_settled") or 0) > 0:
                        ghost_bit += (
                            f" · BIRD {float(eb.get('pnl') or 0):+.1f}u"
                            f"/{int(eb.get('n_settled') or 0)}"
                        )
                except Exception:
                    pass
                crystal_bit = ""
                if parts:
                    crystal_bit = f" · {' · '.join(parts)}"
                crystal_bit += ghost_bit
            except Exception:
                crystal_bit = ""
            if ep:
                e_pnl = float(ep.get("pnl") or 0.0)
                e_col = _YES if e_pnl >= 0 else _NO
                self.rainman_lbl.setText(
                    f"RAINMAN {int(ep.get('n_wins') or 0)} won · "
                    f"{int(ep.get('n_losses') or 0)} lost · "
                    f"{float(ep.get('win_rate') or 0):.0%} · {e_pnl:+.2f}u"
                    f"{crystal_bit}"
                )
                self.rainman_lbl.setStyleSheet(
                    f"background: #0f1a14; color: {e_col}; border: 1px solid #3a5a40; "
                    f"padding: 6px 10px; border-radius: 8px; font-family: Menlo; "
                    f"font-size: {_FC(11)}px; font-weight: 700;"
                )
            else:
                self.rainman_lbl.setText(
                    f"RAINMAN {int(paper.get('wins') or 0)} won · "
                    f"{int(paper.get('losses') or 0)} lost · "
                    f"{float(paper.get('pnl_units') or 0):+.2f}u{crystal_bit}"
                )

        warnings: list[str] = []
        if snap["halted"]:
            warnings.append(f"STGM STAKING HALTED: {snap['halt_reason'] or 'safety gate'}")
        if snap["stale_reservations"]:
            warnings.append(
                f"Reconciling {len(snap['stale_reservations'])} stale reservation(s); "
                "they are not wallet debits."
            )
        if warnings:
            self.portfolio_alert_lbl.setText("  ·  ".join(warnings))
            self.portfolio_alert_lbl.setStyleSheet(
                f"background: #352712; color: {_GOLD}; border: 1px solid #75551f; "
                "padding: 7px 10px; border-radius: 8px; font-weight: 700;"
            )
            self.portfolio_alert_lbl.show()
        else:
            self.portfolio_alert_lbl.hide()

        live_by_ticker = self._live_clock_map()
        open_rows = list(snap["open"])
        self.open_table.clearSpans()
        self.open_table.setRowCount(max(1, len(open_rows)))
        if not open_rows:
            self._table_item(
                self.open_table, 0, 0, "—",
                color=_DIM,
            )
            self.open_table.setSpan(0, 0, 1, self.open_table.columnCount())
        else:
            for i, row in enumerate(open_rows):
                live = live_by_ticker.get(str(row.get("ticker") or ""), {})
                secs = live.get("seconds_to_close")
                closes = (
                    f"{int(secs) // 60}:{int(secs) % 60:02d}"
                    if isinstance(secs, (int, float)) and secs >= 0
                    else "settling"
                )
                side_color = _YES if row["side"] == "UP" else _NO
                tgt = float(
                    live.get("target_price")
                    or row.get("target_price")
                    or 0.0
                )
                tgt_s = _format_target_price(tgt)
                mkt_lbl = f"{row['asset']} 15m"
                if tgt_s:
                    mkt_lbl = f"{row['asset']} 15m · {tgt_s}"
                self._table_item(self.open_table, i, 0, mkt_lbl, bold=True)
                head = self.open_table.item(i, 0)
                if head is not None:
                    head.setData(Qt.ItemDataRole.UserRole, row.get("ticker") or "")
                    if tgt_s:
                        head.setToolTip(f"{row['asset']} target {tgt_s} (Kalshi TO BEAT)")
                self._table_item(self.open_table, i, 1, row["side"], color=side_color, bold=True, center=True)
                stake_cell = str(
                    row.get("stake_label")
                    or f"{float(row.get('stgm_at_risk') or 0):.5f}"
                )
                thin = bool(row.get("thin"))
                self._table_item(
                    self.open_table,
                    i,
                    2,
                    stake_cell,
                    color=_GOLD,
                    bold=True,
                    center=True,
                    tooltip=(
                        "THIN half-ticket (Rainman half-convinced) · 0.00050 STGM = 50¢"
                        if thin
                        else "Full ticket · 0.00100 STGM = $1 = 100¢"
                    ),
                )
                self._table_item(self.open_table, i, 3, f"{row['price_cents']:.0f}¢", center=True)
                mult_lbl = str(row.get("mult_label") or f"{float(row.get('mult_net') or 0):.2f}x")
                self._table_item(self.open_table, i, 4, mult_lbl, color=_GOLD, center=True)
                if_win = float(row.get("if_win_usd") or 0.0)
                self._table_item(
                    self.open_table,
                    i,
                    5,
                    f"+${if_win:.2f}",
                    color=_YES,
                    center=True,
                    tooltip=(
                        "HYPOTHETICAL if real $ at this stake · Kalshi USD OFF"
                        + (" · THIN 50¢ unit" if thin else " · full $1 unit")
                    ),
                )
                entered = str(row.get("entry_clock") or "—")
                tip_enter = entered
                if row.get("entry_ts"):
                    try:
                        tip_enter = (
                            f"entered {datetime.fromtimestamp(float(row['entry_ts'])).isoformat(timespec='seconds')} "
                            f"· secs_left_at_entry={row.get('secs_left_at_entry')}"
                        )
                    except Exception:
                        pass
                self._table_item(
                    self.open_table,
                    i,
                    6,
                    entered,
                    color=_BLUE,
                    center=True,
                    tooltip=tip_enter,
                )
                why = str(row.get("decision_reason") or "chart evidence warming")
                self._table_item(
                    self.open_table,
                    i,
                    7,
                    why,
                    color=_TEXT,
                    tooltip=why,
                )
                self._table_item(self.open_table, i, 8, closes, center=True)
                # STATUS = live mark vs entry: green if winning, red if losing
                entry_px = float(row.get("price_per_share") or (row.get("price_cents") or 50) / 100.0)
                side_u = str(row.get("side") or "UP").upper()
                if head is not None:
                    head.setData(Qt.ItemDataRole.UserRole + 1, entry_px)
                    head.setData(Qt.ItemDataRole.UserRole + 2, side_u)
                st_txt, st_col, st_tip = self._open_mark_status(
                    side_u, entry_px, live.get("kalshi_yes")
                )
                self._table_item(
                    self.open_table,
                    i,
                    9,
                    st_txt,
                    color=st_col,
                    bold=True,
                    center=True,
                    tooltip=st_tip,
                )
                self.open_table.setRowHeight(i, _F(32))
        self._reapply_table_columns(self.open_table)

        # ── LAST RUN · WINS & LOSSES (pinned, scrollable) ──
        last_sum = snap.get("last_run_summary") or {}
        last_wins = list(snap.get("last_run_wins") or [])
        last_losses = list(snap.get("last_run_losses") or [])
        # Wins first (green), then losses (red) — full last-run history
        last_run_rows: list[dict] = list(last_wins) + list(last_losses)
        win_n = int(last_sum.get("wins") or 0)
        loss_n = int(last_sum.get("losses") or 0)
        run_id = str(last_sum.get("window") or snap.get("last_run_id") or "")
        run_pnl = float(last_sum.get("pnl_stgm") or 0.0)
        run_usd_hyp = float(last_sum.get("pnl_usd_hyp") or 0.0)
        run_usd_real = last_sum.get("pnl_usd_real")
        run_usd_real_known = bool(last_sum.get("pnl_usd_real_known"))
        # Color by real USD when we have exchange settles; else STGM hyp
        score_for_color = (
            float(run_usd_real)
            if run_usd_real_known and run_usd_real is not None
            else run_pnl
        )
        pnl_col = _YES if score_for_color >= 0.0 else _NO
        # Explicit name lists so wins AND losses are obvious at a glance
        win_names = " ".join(
            f"{r.get('asset')}" for r in last_wins
        ) or "—"
        loss_names = " ".join(
            f"{r.get('asset')}" for r in last_losses
        ) or "—"
        if run_id:
            try:
                from System.sifta_15m_money_math import format_stgm_with_cents

                run_pnl_lbl = format_stgm_with_cents(run_pnl, signed=True)
            except Exception:
                run_pnl_lbl = f"{run_pnl:+.5f}"
            # Plain: who paid, who died, money
            banner = f"LAST WINDOW  "
            if win_n and not loss_n:
                banner += f"all {win_n} paid"
                if win_names and win_names != "—":
                    banner += f" ({win_names})"
            elif loss_n and not win_n:
                banner += f"all {loss_n} died"
                if loss_names and loss_names != "—":
                    banner += f" ({loss_names})"
            else:
                banner += f"{win_n} paid · {loss_n} died"
                if win_names and win_names != "—":
                    banner += f"  paid:{win_names}"
                if loss_n and loss_names and loss_names != "—":
                    banner += f"  died:{loss_names}"
            if run_usd_real_known and run_usd_real is not None:
                banner += (
                    f"  ·  EXCHANGE USD {float(run_usd_real):+.2f} net fees"
                    f" ({int(last_sum.get('pnl_usd_real_n') or 0)} fills)"
                    f"  ·  PAPER/STGM {run_pnl_lbl} · ${run_usd_hyp:+.2f} hypothetical"
                )
            else:
                banner += (
                    f"  ·  PAPER/STGM {run_pnl_lbl}"
                    f"  ·  ${run_usd_hyp:+.2f} hypothetical · exchange receipts pending"
                )
            if hasattr(self, "last_run_banner"):
                self.last_run_banner.setText(banner)
                self.last_run_banner.setStyleSheet(
                    f"background: #121a28; color: {pnl_col}; border: 1px solid "
                    f"{'#276d54' if score_for_color >= 0 else '#6d2727'}; "
                    "padding: 8px 12px; border-radius: 8px; font-family: Menlo; "
                    f"font-size: {_F(12)}px; font-weight: 700;"
                )
        else:
            if hasattr(self, "last_run_banner"):
                self.last_run_banner.setText("LAST  —")
                self.last_run_banner.setStyleSheet(
                    f"background: #121a28; color: {_DIM}; border: 1px solid #2a3a52; "
                    "padding: 8px 12px; border-radius: 8px; font-family: Menlo; "
                    f"font-size: {_F(12)}px; font-weight: 700;"
                )
        self.last_run_table.clearSpans()
        # Wins first (green), then losses (red) — full window, nothing hidden
        if not last_run_rows:
            self.last_run_table.setRowCount(1)
            self._table_item(
                self.last_run_table,
                0,
                0,
                "—",
                color=_DIM,
            )
            self.last_run_table.setSpan(0, 0, 1, self.last_run_table.columnCount())
            self.last_run_table.setRowHeight(0, _F(30))
        else:
            self.last_run_table.setRowCount(len(last_run_rows))
            for i, row in enumerate(last_run_rows):
                self._paint_stgm_history_row(self.last_run_table, i, row, compact=False)
                self.last_run_table.setRowHeight(i, _F(28))
            need_h = _F(36) + len(last_run_rows) * _F(28) + _F(16)
            self.last_run_table.setMinimumHeight(min(_F(300), max(_F(180), need_h)))
            self.last_run_table.setMaximumHeight(_F(340))
        self._reapply_table_columns(self.last_run_table)

        # r1707 scalp strip
        if hasattr(self, "scalp_strip_lbl"):
            ss = snap.get("scalp_strip") or {}
            n_sc = int(ss.get("n_scalp_execute") or 0)
            ft = float(ss.get("fee_true_sum") or 0.0)
            sc_col = _YES if ft >= 0 else _NO
            self.scalp_strip_lbl.setText(
                f"STGM SCALP  n={n_sc}  fee-true ${ft:+.2f}  "
                f"{int(ss.get('wins') or 0)}W/{int(ss.get('losses') or 0)}L  "
                f"force-flat {int(ss.get('force_flat_n') or 0)}  ·  "
                f"{ss.get('disclaimer') or 'selection-biased sample'}"
            )
            self.scalp_strip_lbl.setStyleSheet(
                f"background: #12180e; color: {sc_col}; border: 1px solid #4a5a2a; "
                f"padding: 6px 10px; border-radius: 8px; font-family: Menlo; "
                f"font-size: {_FC(10)}px; font-weight: 700;"
            )

        # Longer scrollable history (all recent W/L, newest first)
        result_rows = list(snap["recent_results"])[:40]
        self.results_table.clearSpans()
        self.results_table.setRowCount(max(1, len(result_rows)))
        if not result_rows:
            self._table_item(self.results_table, 0, 0, "No signed STGM results yet.", color=_DIM)
            self.results_table.setSpan(0, 0, 1, self.results_table.columnCount())
        else:
            for i, row in enumerate(result_rows):
                self._paint_stgm_history_row(self.results_table, i, row, compact=True)
                self.results_table.setRowHeight(i, _FC(26))
        self._reapply_table_columns(self.results_table)

        # r1707 TRAIN table
        if hasattr(self, "train_table"):
            trains = list(snap.get("train_rows") or [])[:10]
            self.train_table.clearSpans()
            self.train_table.setRowCount(max(1, len(trains)))
            if not trains:
                self._table_item(
                    self.train_table, 0, 0, "No shadow TRAIN exits yet.", color=_DIM
                )
                self.train_table.setSpan(0, 0, 1, self.train_table.columnCount())
            else:
                for i, row in enumerate(trains):
                    color = _YES if row.get("win") else _NO
                    self._table_item(
                        self.train_table,
                        i,
                        0,
                        row.get("result") or ("WIN" if row.get("win") else "LOSS"),
                        color=color,
                        bold=True,
                        center=True,
                    )
                    self._table_item(
                        self.train_table,
                        i,
                        1,
                        glass_kind_label(row),
                        color=_DIM,
                        bold=True,
                        center=True,
                        tooltip="Shadow training · never real USD",
                    )
                    self._table_item(
                        self.train_table, i, 2, f"{row.get('asset')} 15m", color=_DIM
                    )
                    self._table_item(
                        self.train_table,
                        i,
                        3,
                        str(row.get("side") or "?"),
                        color=_DIM,
                        center=True,
                    )
                    self._table_item(
                        self.train_table,
                        i,
                        4,
                        f"{float(row.get('price_cents') or 0):.0f}¢",
                        color=_DIM,
                        center=True,
                    )
                    ft = row.get("pnl_usd_fee_true")
                    ft_s = f"{float(ft):+.2f}" if ft is not None else "—"
                    self._table_item(
                        self.train_table,
                        i,
                        5,
                        ft_s,
                        color=color,
                        bold=True,
                        center=True,
                    )
                    self._table_item(
                        self.train_table,
                        i,
                        6,
                        str(row.get("decision_reason") or "training"),
                        color=_DIM,
                    )
                    self.train_table.setRowHeight(i, _FC(22))
            self._reapply_table_columns(self.train_table)

        odds_rows = self._live_odds_rows(limit=12)
        self.live_odds_table.clearSpans()
        self.live_odds_table.setRowCount(max(1, len(odds_rows)))
        if not odds_rows:
            self._table_item(self.live_odds_table, 0, 0, "Syncing live odds from disk…", color=_DIM)
            self.live_odds_table.setSpan(0, 0, 1, self.live_odds_table.columnCount())
        else:
            open_by_asset = {row["asset"]: row["side"] for row in open_rows}
            try:
                from System.sifta_15m_money_math import net_multiplier
            except Exception:
                net_multiplier = lambda p: round(1.0 / max(0.01, float(p)), 2)  # type: ignore
            for i, row in enumerate(odds_rows):
                ky = float(row.get("kalshi_yes") or row.get("kalshi_chance_yes") or 0.5)
                secs = row.get("seconds_to_close")
                closes = (
                    f"{int(secs) // 60}:{int(secs) % 60:02d}"
                    if isinstance(secs, (int, float)) and secs >= 0
                    else "—"
                )
                asset = str(row.get("asset") or "?")
                up_m = net_multiplier(ky)
                dn_m = net_multiplier(1.0 - ky)
                vol = float(row.get("volume_24h") or row.get("volume") or 0.0)
                vol_s = f"{vol/1000:.1f}k" if vol >= 1000 else f"{vol:.0f}"
                tgt_s = _format_target_price(float(row.get("target_price") or 0.0))
                mkt = f"{asset} · {tgt_s}" if tgt_s else asset
                self._table_item(
                    self.live_odds_table,
                    i,
                    0,
                    mkt,
                    bold=True,
                    tooltip=f"{asset} target {tgt_s}" if tgt_s else asset,
                )
                self._table_item(self.live_odds_table, i, 1, f"{ky:.0%}", color=_YES, bold=True, center=True)
                self._table_item(self.live_odds_table, i, 2, f"{up_m:.2f}x", color=_YES, center=True)
                self._table_item(self.live_odds_table, i, 3, f"{1.0 - ky:.0%}", color=_NO, bold=True, center=True)
                self._table_item(self.live_odds_table, i, 4, f"{dn_m:.2f}x", color=_NO, center=True)
                self._table_item(self.live_odds_table, i, 5, vol_s, color=_DIM, center=True)
                self._table_item(self.live_odds_table, i, 6, closes, center=True)
                alice_side = open_by_asset.get(asset, "WAIT")
                self._table_item(
                    self.live_odds_table, i, 7, alice_side,
                    color=(_GOLD if alice_side != "WAIT" else _DIM), bold=alice_side != "WAIT", center=True,
                )
                self.live_odds_table.setRowHeight(i, _FC(26))
        self._reapply_table_columns(self.live_odds_table)

    def _market_matches_nav(self, row: dict) -> bool:
        """Filter board like Kalshi Crypto sidebar."""
        sec = str(row.get("nav_section") or "")
        tf = str(row.get("timeframe") or "")
        asset = str(row.get("asset") or "")
        cat = str(row.get("category") or "")
        kt = str(row.get("kalshi_ticker") or row.get("id") or "").upper()
        is_crypto = (
            sec == "Crypto"
            or "Crypto" in cat
            or any(f"KX{a}" in kt or a in kt for a in CRYPTO_ASSETS)
        )

        if self._nav_section == "All markets":
            pass
        elif self._nav_section == "Crypto":
            if not is_crypto and sec and sec != "Crypto":
                return False
            if not is_crypto and not row.get("kalshi_ticker"):
                # genesis demos without kalshi — hide when browsing Crypto
                return False
            if not is_crypto:
                return False
        else:
            if sec and sec != self._nav_section:
                return False
            if not sec and self._nav_section not in cat:
                return False

        if self._nav_timeframe and tf != self._nav_timeframe and self._nav_timeframe not in cat:
            return False
        if self._nav_asset:
            if asset != self._nav_asset and self._nav_asset not in cat and self._nav_asset not in kt:
                return False
        return True

    def _refresh_watch(self) -> None:
        return  # odds board: list is enough

    def _refresh_learn(self) -> None:
        return

    def _live_clock_map(self) -> dict[str, dict]:
        """Ticker → live row from disk (glass) + engine (if present)."""
        out: dict[str, dict] = {}
        # Prefer disk snapshot written by monitor/rollover — no network
        live_path = _STATE / "kalshi_15m_live.json"
        try:
            if live_path.exists():
                data = json.loads(live_path.read_text(encoding="utf-8"))
                now = time.time()
                for row in data.get("markets") or []:
                    if not isinstance(row, dict):
                        continue
                    t = str(row.get("kalshi_ticker") or row.get("ticker") or "").strip()
                    if not t:
                        continue
                    secs = row.get("seconds_to_close")
                    if secs is None and row.get("close_ts"):
                        try:
                            secs = max(0, int(float(row["close_ts"]) - now))
                        except Exception:
                            secs = None
                    out[t] = {
                        "seconds_to_close": secs,
                        "kalshi_yes": row.get("kalshi_yes") or row.get("yes_price"),
                        "volume_24h": row.get("volume_24h") or row.get("volume"),
                        "asset": row.get("asset"),
                        "target_price": float(row.get("target_price") or 0.0 or 0),
                    }
        except Exception:
            pass
        for m in self.engine.markets.values():
            t = str(getattr(m, "kalshi_ticker", "") or "")
            if not t:
                continue
            try:
                row = m.to_row()
            except Exception:
                row = {}
            if t not in out:
                out[t] = row
            else:
                # fill missing secs / target from engine
                if out[t].get("seconds_to_close") is None:
                    out[t]["seconds_to_close"] = row.get("seconds_to_close")
                if not out[t].get("target_price") and row.get("target_price"):
                    out[t]["target_price"] = row.get("target_price")
        return out

    def _live_odds_rows(self, limit: int = 12) -> list[dict]:
        """15m odds for glass: disk first, engine fallback."""
        rows: list[dict] = []
        live_path = _STATE / "kalshi_15m_live.json"
        try:
            if live_path.exists():
                data = json.loads(live_path.read_text(encoding="utf-8"))
                now = time.time()
                for row in data.get("markets") or []:
                    if not isinstance(row, dict):
                        continue
                    asset = str(row.get("asset") or "?")
                    ky = row.get("kalshi_yes")
                    if ky is None:
                        ky = row.get("yes_price")
                    secs = row.get("seconds_to_close")
                    if secs is None and row.get("close_ts"):
                        try:
                            secs = max(0, int(float(row["close_ts"]) - now))
                        except Exception:
                            secs = None
                    rows.append(
                        {
                            "asset": asset,
                            "kalshi_yes": float(ky) if ky is not None else 0.5,
                            "seconds_to_close": secs,
                            "volume_24h": float(row.get("volume_24h") or row.get("volume") or 0),
                            "kalshi_ticker": row.get("kalshi_ticker") or row.get("ticker"),
                            "target_price": float(row.get("target_price") or 0.0 or 0),
                        }
                    )
        except Exception:
            pass
        if not rows:
            try:
                rows = list(self.engine.watch_15m(limit=limit))
            except Exception:
                rows = []
        # Safari-ish asset order
        order = {
            a: i
            for i, a in enumerate(
                ("BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "HYPE", "NEAR", "ZEC", "SUI")
            )
        }
        rows.sort(key=lambda r: order.get(str(r.get("asset") or ""), 99))
        return rows[:limit]

    def _run_bg(self, work: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
        """Run ``work`` on the single background worker; apply ``on_done`` on UI thread."""

        def _wrapped() -> Any:
            with _ENGINE_LOCK:
                return work()

        fut = _BG_EXECUTOR.submit(_wrapped)

        def _done(f: concurrent.futures.Future) -> None:
            try:
                result = f.result()
            except Exception as exc:
                result = {"_bg_error": f"{type(exc).__name__}: {exc}"}

            def _apply() -> None:
                try:
                    on_done(result)
                except Exception:
                    pass

            # Queue onto Qt main thread (safe from worker threads)
            QTimer.singleShot(0, _apply)

        fut.add_done_callback(_done)

    def _ui_paint_only(self) -> None:
        """Cheap countdown paint only — never network, never full table rebuild."""
        if not hasattr(self, "open_table") or self._live_refresh_busy or self._paper_tick_busy:
            return
        try:
            self._paint_countdowns_only()
        except Exception:
            pass

    def _open_mark_status(
        self, side: str, entry_price: float, yes_mid: object
    ) -> tuple[str, str, str]:
        """Human STATUS: green if mark favors our side vs entry, else red."""
        if yes_mid is None:
            return "OPEN", _ACCENT, "Waiting for live mid · still open"
        try:
            yes = float(yes_mid)
        except (TypeError, ValueError):
            return "OPEN", _ACCENT, "Waiting for live mid · still open"
        side_u = str(side or "UP").upper()
        # Our side's live price (what we'd mark-to-market)
        mark = yes if side_u in ("UP", "YES") else (1.0 - yes)
        try:
            entry = float(entry_price)
        except (TypeError, ValueError):
            entry = 0.5
        entry = min(0.99, max(0.01, entry))
        delta_c = int(round((mark - entry) * 100))
        tip = (
            f"Entry {entry:.0%} · live {mark:.0%} on {side_u} · "
            f"updates when glass refreshes mids from disk (~every few–30s)"
        )
        if delta_c >= 1:
            return f"▲ +{delta_c}¢", _YES, "GREEN · mark better than entry · " + tip
        if delta_c <= -1:
            return f"▼ {delta_c}¢", _NO, "RED · mark worse than entry · " + tip
        return "FLAT", _DIM, "About even vs entry · " + tip

    def _paint_countdowns_only(self) -> None:
        """Update LEFT clock + STATUS green/red from disk live mids (no network)."""
        if not hasattr(self, "open_table"):
            return
        by_ticker = self._live_clock_map()
        for i in range(self.open_table.rowCount()):
            ticker_item = self.open_table.item(i, 0)
            if ticker_item is None:
                continue
            ticker = str(ticker_item.data(Qt.ItemDataRole.UserRole) or "")
            live = by_ticker.get(ticker) if ticker else None
            if not live:
                continue
            secs = live.get("seconds_to_close")
            closes = (
                f"{int(secs) // 60}:{int(secs) % 60:02d}"
                if isinstance(secs, (int, float)) and secs >= 0
                else "settling"
            )
            # LEFT column index 8 after money columns
            cell = self.open_table.item(i, 8)
            if cell is None:
                self._table_item(self.open_table, i, 8, closes, center=True)
            elif cell.text() != closes:
                cell.setText(closes)
            # STATUS col 9 — green/red mark vs entry
            try:
                entry_px = float(ticker_item.data(Qt.ItemDataRole.UserRole + 1) or 0.0)
            except (TypeError, ValueError):
                entry_px = 0.0
            side_u = str(ticker_item.data(Qt.ItemDataRole.UserRole + 2) or "UP")
            if entry_px > 0:
                st_txt, st_col, st_tip = self._open_mark_status(
                    side_u, entry_px, live.get("kalshi_yes")
                )
                st_cell = self.open_table.item(i, 9)
                if st_cell is None:
                    self._table_item(
                        self.open_table,
                        i,
                        9,
                        st_txt,
                        color=st_col,
                        bold=True,
                        center=True,
                        tooltip=st_tip,
                    )
                else:
                    if st_cell.text() != st_txt:
                        st_cell.setText(st_txt)
                    st_cell.setForeground(QColor(st_col))
                    st_cell.setToolTip(st_tip)
        # Live odds LEFT is column 6
        if hasattr(self, "live_odds_table"):
            live_map = {
                str(r.get("asset") or ""): r for r in self._live_odds_rows(limit=20)
            }
            for i in range(self.live_odds_table.rowCount()):
                asset_item = self.live_odds_table.item(i, 0)
                if asset_item is None:
                    continue
                asset = asset_item.text().strip()
                row = live_map.get(asset) or {}
                secs = row.get("seconds_to_close")
                closes = (
                    f"{int(secs) // 60}:{int(secs) % 60:02d}"
                    if isinstance(secs, (int, float)) and secs >= 0
                    else "—"
                )
                cell = self.live_odds_table.item(i, 6)
                if cell is None:
                    self._table_item(self.live_odds_table, i, 6, closes, center=True)
                elif cell.text() != closes:
                    cell.setText(closes)

    def _live_refresh(self) -> None:
        """Fetch Kalshi prices OFF the UI thread (was 2+s beach-ball every 8s)."""
        if self._live_refresh_busy or self._paper_tick_busy:
            return
        has = any(
            getattr(m, "kalshi_ticker", "") and m.status == "open"
            for m in self.engine.markets.values()
        )
        if not has:
            # still try once in bg so first open boards appear
            pass
        self._live_refresh_busy = True
        engine = self.engine

        def _work() -> dict:
            return engine.refresh_kalshi_prices()

        def _apply(r: Any) -> None:
            self._live_refresh_busy = False
            if not isinstance(r, dict):
                return
            if r.get("_bg_error"):
                return
            if r.get("ok") or (r.get("rollover") or {}).get("imported"):
                _PORTFOLIO_SNAP_CACHE["ts"] = 0.0
                if hasattr(self, "open_table"):
                    self._refresh_proof()
                    self._refresh_human_portfolio()
                    if hasattr(self, "mode"):
                        n15 = len(self.engine.watch_15m(limit=20))
                        self.mode.setText(f"LIVE · {n15}")
                        self.mode.setStyleSheet(
                            f"background: #103126; color: {_YES}; border: 1px solid #276d54; "
                            "padding: 7px 11px; border-radius: 11px; font-weight: 800;"
                        )
                else:
                    self._refresh_all()

        self._run_bg(_work, _apply)

    def _on_nav(self, row: int) -> None:
        if row < 0 or row >= len(self._nav_items):
            return
        kind, value, _label = self._nav_items[row]
        if kind == "section":
            self._nav_section = value
            self._nav_timeframe = ""
            self._nav_asset = ""
        elif kind == "timeframe":
            self._nav_section = "Crypto"
            self._nav_timeframe = value
            self._nav_asset = ""
        elif kind == "asset":
            self._nav_section = "Crypto"
            self._nav_asset = value
        self._refresh_all()

    def _refresh_all(self) -> None:
        # Human portfolio path: never thrash hidden QListWidgets on the UI thread
        if hasattr(self, "open_table"):
            try:
                self._refresh_proof()
                self._refresh_human_portfolio()
                self._refresh_learn_state()
            except Exception:
                pass
            return
        selected = self._selected_market_id()
        self.list.clear()
        shown = 0
        # Safari order for 15m asset list
        _ord = {
            a: i
            for i, a in enumerate(
                ("BTC", "ETH", "SOL", "ZEC", "XRP", "NEAR", "HYPE", "DOGE", "BNB", "SUI")
            )
        }
        market_rows = [
            row
            for row in self.engine.list_markets()
            if self._market_matches_nav(row)
        ]
        market_rows.sort(
            key=lambda r: (
                _ord.get(str(r.get("asset") or ""), 99),
                str(r.get("title") or ""),
            )
        )
        for row in market_rows:
            shown += 1
            price = int(round(row["yes_price"] * 100))
            status = row["status"]
            mark = "✓" if status == "resolved" else f"{price}¢"
            ky = row.get("kalshi_yes")
            # Lead with Kalshi Up/Down ¢ so glass matches Safari (not swarm-skewed local)
            if ky is not None and status != "resolved":
                up_c = int(round(float(ky) * 100))
                dual = f"UP {up_c}%   DOWN {100 - up_c}%"
            else:
                dual = "—"
            asset = row.get("asset") or ""
            tf = str(row.get("timeframe") or "")
            if asset and "15" in tf:
                head = f"{asset} 15 min"
            elif asset:
                head = f"{asset} {tf}".strip() or asset
            else:
                head = str(row.get("title") or "")[:40]
            secs = row.get("seconds_to_close")
            tbit = f"   {secs//60}:{secs%60:02d}" if isinstance(secs, int) and secs >= 0 else ""
            tgt = float(row.get("target_price") or 0.0)
            tgt_s = _format_target_price(tgt)
            tline = f"\n  {tgt_s} target" if tgt_s else ""
            text = f"{head}{tbit}\n  {dual}{tline}"
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, row["id"])
            if row.get("kalshi_ticker"):
                it.setForeground(QColor(_GOLD))
            self.list.addItem(it)
            if row["id"] == selected:
                self.list.setCurrentItem(it)
        if self.list.currentRow() < 0 and self.list.count():
            self.list.setCurrentRow(0)
        parts = []
        if self._nav_timeframe:
            parts.append(self._nav_timeframe)
        if self._nav_asset:
            parts.append(self._nav_asset)
        if hasattr(self, "filter_lbl"):
            self.filter_lbl.setText((" · ".join(parts) or "All") + f"  ({shown})")
        self._refresh_detail()
        n_live = len(self.engine.watch_15m(limit=20)) if self._nav_timeframe == "15 Minute" else shown
        if hasattr(self, "open_table"):
            self.mode.setText("AUTOPILOT ON" if self.paper_loop_on else "AUTOPILOT PAUSED")
        else:
            loop = " · PAPER" if self.paper_loop_on else ""
            self.mode.setText(f"LIVE · {n_live}{loop}" if n_live else f"LIVE{loop}")
        self._refresh_proof()
        self._refresh_autobet_monitor()
        self._refresh_human_portfolio()

    def _refresh_detail(self) -> None:
        mid = self._selected_market_id()
        if not mid or mid not in self.engine.markets:
            return
        m = self.engine.markets[mid]
        row = m.to_row()
        ky = row.get("kalshi_yes")
        up = int(round(float(ky) * 100)) if ky is not None else None
        asset = row.get("asset") or ""
        lines = []
        if asset:
            lines.append(f"{asset} 15 min" if "15" in str(row.get("timeframe") or "") else asset)
        else:
            lines.append(str(row.get("title") or "")[:60])
        if up is not None:
            lines.append(f"UP {up}%")
            lines.append(f"DOWN {100 - up}%")
            lines.append(f"Up {up}¢   Down {100 - up}¢")
        tgt = float(row.get("target_price") or 0.0)
        tgt_s = _format_target_price(tgt)
        if tgt_s:
            lines.append(f"Target  {tgt_s}")
        secs = row.get("seconds_to_close")
        if isinstance(secs, int):
            lines.append(f"{secs // 60}:{secs % 60:02d} left")
        self.detail.setText("\n".join(lines))
        if ky is not None:
            self.odds.setText(
                f"<span style='color:{_YES}'>UP {float(ky):.0%}</span>"
                f"&nbsp;&nbsp;&nbsp;"
                f"<span style='color:{_NO}'>DOWN {1.0 - float(ky):.0%}</span>"
            )
        else:
            self.odds.setText("—")
        self.odds.setTextFormat(Qt.TextFormat.RichText)

    def _on_select(self, _row: int) -> None:
        self._refresh_detail()

    def _buy(self) -> None:
        mid = self._selected_market_id()
        if not mid:
            return
        side = "yes" if self.side.currentText() == "YES" else "no"
        r = self.engine.buy(mid, side, float(self.stake.value()), agent_id=OWNER_ID)
        if r.get("ok"):
            self.event_lbl.setText(f"Bought {side.upper()} {r['stake']}")
            _write_receipt("owner_buy", r)
            _focus(f"bought {side} on {mid}")
        else:
            self.event_lbl.setText(str(r.get("reason") or "buy failed"))
        self._refresh_all()

    def _resolve(self, outcome: str) -> None:
        mid = self._selected_market_id()
        if not mid:
            return
        r = self.engine.resolve(mid, outcome)  # type: ignore[arg-type]
        if r.get("ok"):
            self.event_lbl.setText(f"Resolved {outcome.upper()}")
            _write_receipt("resolve", r)
            _focus(f"resolved {mid} → {outcome}")
        else:
            self.event_lbl.setText(str(r.get("reason") or "resolve failed"))
        self._refresh_all()

    def _toggle_auto(self) -> None:
        self.auto_swarm = not self.auto_swarm
        if self.auto_swarm:
            self.timer.start()
            self.auto_btn.setText("Pause swarm")
            self.mode.setText("LIVE")
            self.mode.setStyleSheet(f"color: {_ACCENT}; font-weight: 700;")
        else:
            self.timer.stop()
            self.auto_btn.setText("Resume swarm")
            self.mode.setText("PAUSED")
            self.mode.setStyleSheet(f"color: {_GOLD}; font-weight: 700;")

    def _swarm_once(self) -> None:
        r = self.engine.swarm_step()
        if r.get("ok"):
            self.event_lbl.setText(
                f"Swarm {r.get('asset') or ''} UP≈{r.get('kalshi_chance')}"
            )
        self.engine.save_snapshot()
        self._refresh_all()

    def _run_field_test(self) -> None:
        result = run_pheromone_ablation(
            seed=self.engine.seed + self.engine.tick,
            trials=400,
            ticks=18,
            swarm_size=self.engine.swarm_size,
            state_dir=_STATE,
            write_receipt=True,
        )
        improvement = 100.0 * float(result["relative_brier_improvement"])
        self.ablation_lbl.setText(
            f"Field {'+' if result['field_helped'] else '0'}  {improvement:+.1f}%"
        )
        self.ablation_lbl.setStyleSheet(
            f"color: {_YES if result['field_helped'] else _NO}; font-size: {_F(10)}px;"
        )
        _write_receipt("field_ablation", result)

    def _sync_kalshi(self) -> None:
        """Full public sync off UI thread (multi-second network).

        Also refreshes read-only George USD balance cache (GET only).
        """
        if self._live_refresh_busy or self._paper_tick_busy:
            self.event_lbl.setText("Busy — try sync in a moment")
            return
        self._live_refresh_busy = True
        self.event_lbl.setText("Sync…")
        engine = self.engine

        def _work() -> dict:
            r = engine.sync_kalshi_public(limit=80, min_volume=5.0, replace=True)
            if r.get("ok"):
                try:
                    engine.rollover_15m_clocks()
                except Exception:
                    pass
                try:
                    engine.save_snapshot()
                except Exception:
                    pass
            # r1648: USD cash + position refresh (read-only GETs; never orders)
            usd: dict[str, Any] = {}
            try:
                from System.kalshi_portfolio_read import fetch_portfolio

                usd = fetch_portfolio(timeout=12.0)
            except Exception as exc:
                usd = {"ok": False, "reason": f"{type(exc).__name__}"}
            r = dict(r) if isinstance(r, dict) else {"ok": False}
            r["usd_read"] = {
                "ok": bool(usd.get("ok")),
                "balance_usd": usd.get("balance_usd"),
                "positions_count": usd.get("positions_count"),
                "reason": usd.get("reason"),
            }
            return r

        def _apply(r: Any) -> None:
            self._live_refresh_busy = False
            if not isinstance(r, dict):
                return
            if r.get("_bg_error"):
                self.event_lbl.setText(str(r["_bg_error"]))
                return
            try:
                self._paint_usd_portfolio_mirror()
            except Exception:
                pass
            self._nav_section = "Crypto"
            self._nav_timeframe = "15 Minute"
            self._nav_asset = ""
            if hasattr(self, "nav_list"):
                for i, (kind, value, _lab) in enumerate(self._nav_items):
                    if kind == "timeframe" and value == "15 Minute":
                        self.nav_list.blockSignals(True)
                        self.nav_list.setCurrentRow(i)
                        self.nav_list.blockSignals(False)
                        break
            if r.get("ok"):
                n = len(self.engine.watch_15m(limit=20))
                usd_bit = r.get("usd_read") or {}
                if usd_bit.get("ok") and usd_bit.get("balance_usd") is not None:
                    self.event_lbl.setText(
                        f"{n} clocks · US ${float(usd_bit['balance_usd']):,.2f} (read-only)"
                    )
                else:
                    self.event_lbl.setText(f"{n} clocks")
                self.mode.setText(f"LIVE · {n}")
                self.mode.setStyleSheet(f"color: {_GOLD}; font-weight: 700;")
                _write_receipt("kalshi_public_sync", {"ok": True, "n": n})
                _focus(f"odds board · {n} clocks")
            else:
                self.event_lbl.setText(str(r.get("reason") or "sync failed"))
                _write_receipt("kalshi_public_sync_fail", r)
            _PORTFOLIO_SNAP_CACHE["ts"] = 0.0
            self._refresh_all()

        self._run_bg(_work, _apply)

    def _refresh_kalshi(self) -> None:
        """Manual refresh — network off UI thread so button doesn't beach-ball."""
        if self._live_refresh_busy or self._paper_tick_busy:
            self.event_lbl.setText("Refresh already running…")
            return
        self._live_refresh_busy = True
        self.event_lbl.setText("Refreshing odds…")
        engine = self.engine

        def _work() -> dict:
            return engine.refresh_kalshi_prices()

        def _apply(r: Any) -> None:
            self._live_refresh_busy = False
            if not isinstance(r, dict):
                return
            if r.get("_bg_error"):
                self.event_lbl.setText(str(r["_bg_error"]))
                return
            if r.get("ok"):
                self.event_lbl.setText(f"Refresh {r.get('updated')}")
                _write_receipt("kalshi_price_refresh", {"updated": r.get("updated")})
            else:
                self.event_lbl.setText(str(r.get("reason") or "refresh failed"))
            _PORTFOLIO_SNAP_CACHE["ts"] = 0.0
            self._refresh_all()

        self._run_bg(_work, _apply)

    # ── AutoBet methods ──

    def _toggle_autobet(self) -> None:
        self.auto_autobet = not self.auto_autobet
        if self.auto_autobet:
            self.autobet_timer.start()
            self.ab_auto_btn.setText("Stop")
            self.ab_auto_btn.setStyleSheet(
                f"QPushButton {{ border-color: {_NO}; color: {_NO}; font-weight: 700; }}"
            )
            self.ab_status.setText("On")
            self.ab_status.setStyleSheet(f"color: {_YES}; font-weight: 700;")
            _write_receipt("autobet_start", {"interval_ms": self._autobet_interval_ms})
            _focus("auto-bet started")
        else:
            self.autobet_timer.stop()
            self.ab_auto_btn.setText("Auto-bet")
            self.ab_auto_btn.setStyleSheet(
                f"QPushButton {{ border-color: {_YES}; color: {_YES}; font-weight: 700; }}"
            )
            self.ab_status.setText("Off")
            self.ab_status.setStyleSheet(f"color: {_GOLD}; font-weight: 700;")
            _write_receipt("autobet_stop", {})
            _focus("auto-bet stopped")

    def _autobet_tick(self) -> None:
        if self.auto_autobet:
            self._autobet_once()

    def _autobet_once(self) -> None:
        result = auto_bet_cycle(
            engine=self.engine,
            state_dir=_STATE,
            max_bets=3,
            min_edge=AUTO_BET_MIN_EDGE,
            stake=AUTO_BET_STAKE,
        )
        n = result.get("bets_placed", 0)
        scored = result.get("markets_scored", 0)
        bets = result.get("bets", [])
        if n > 0:
            lines = [f"{n} bets"]
            for b in bets[:4]:
                lines.append(f"  {b['side'].upper()} {b['title'][:40]}")
            self.event_lbl.setText("\n".join(lines))
        else:
            self.event_lbl.setText("No bet")
        self._refresh_autobet_monitor()
        self.engine.save_snapshot()
        self._refresh_all()

    def _check_autobet_results(self) -> None:
        result = check_results(
            engine=self.engine,
            state_dir=_STATE,
            write=True,
        )
        total = result.get("total_resolved", 0)
        wins = result.get("wins", 0)
        losses = result.get("losses", 0)
        pnl = result.get("total_pnl", 0)
        accuracy = result.get("accuracy", 0)
        if total > 0:
            color = _YES if pnl >= 0 else _NO
            self.ab_results.setText(
                f"{wins}W {losses}L  PnL {pnl:+.1f}"
            )
            self.ab_results.setStyleSheet(
                f"background: {_CARD}; color: {color}; border: 1px solid #2a3548; "
                f"padding: 8px; border-radius: 6px; font-size: {_F(10)}px;"

            )
            _write_receipt("autobet_results", result)
            _focus(f"autobet results: {wins}W/{losses}L PnL {pnl:+.2f}")
        else:
            self.ab_results.setText("")
            self.ab_results.setStyleSheet(
                f"background: {_CARD}; color: {_DIM}; border: 1px solid #2a3548; "
                f"padding: 8px; border-radius: 6px; font-size: {_F(10)}px;"

            )

    def _refresh_autobet_monitor(self) -> None:
        if not hasattr(self, "ab_monitor") or self.ab_monitor is None:
            return
        try:
            if self.ab_monitor.isHidden() and self.tabs.currentIndex() != 1:
                pass  # still fill
        except Exception:
            pass
        self.ab_monitor.clear()
        p = load_proof(_STATE)
        self.ab_results.setText(
            f"{int(p.get('n_wins') or 0)}W/{int(p.get('n_losses') or 0)}L  "
            f"PnL {float(p.get('pnl') or 0):+.2f}  settled {int(p.get('n_settled') or 0)}  "
            f"{'PROVEN' if p.get('proven') else 'paper'}"
        )
        self._refresh_learn_state()
        if hasattr(self, "ab_status"):
            self.ab_status.setText(
                (
                    f"Paper @ minute {DEFAULT_MAX_SECS // 60}: On (≤{DEFAULT_MAX_SECS // 60}:00)"
                    if self.paper_loop_on
                    else f"Paper @ minute {DEFAULT_MAX_SECS // 60}: Off"
                )
            )
        # show live 15m + paper positions
        rows = self.engine.watch_15m(limit=12)
        if not rows:
            # still list open 15m from engine
            for m in self.engine.markets.values():
                if m.status == "open" and m.timeframe == "15 Minute":
                    rows.append(m.to_row())
        if not rows:
            self.ab_monitor.addItem("No 15m — Sync")
            return
        for r in rows:
            asset = r.get("asset") or "?"
            ky = r.get("kalshi_yes") if "kalshi_yes" in r else r.get("kalshi_chance_yes")
            up = int(round(float(ky) * 100)) if ky is not None else 50
            secs = r.get("seconds_to_close")
            tbit = f"{secs//60}:{secs%60:02d}" if isinstance(secs, int) else "—"
            mid = r.get("id")
            pos = {}
            if mid and mid in self.engine.markets:
                pos = self.engine.markets[mid].positions.get(OWNER_ID) or {}
            side = ""
            if float(pos.get("yes") or 0) > 0:
                side = " PAPER UP"
            elif float(pos.get("no") or 0) > 0:
                side = " PAPER DOWN"
            item = QListWidgetItem(f"{asset:4}  {tbit}  UP {up}%{side}")
            if side:
                item.setForeground(QColor(_GOLD))
            self.ab_monitor.addItem(item)

    def _tick(self) -> None:
        if self.auto_swarm:
            self._swarm_once()

    def _refresh_learn_state(self) -> None:
        # Learning prose stays off-screen (George: no useless text)
        if hasattr(self, "learn_lbl") and self.learn_lbl is not None:
            try:
                self.learn_lbl.hide()
                self.learn_lbl.clear()
            except Exception:
                pass

    def _refresh_proof(self) -> None:
        if not hasattr(self, "proof_lbl"):
            return
        if hasattr(self, "open_table"):
            snap = _cached_human_portfolio(_STATE)
            paper = snap["paper"]
            body_pnl = float(snap["body_pnl_stgm"])
            color = _YES if body_pnl >= 0 else _NO
            running = "RUNNING" if self.paper_loop_on else "PAUSED"
            try:
                from System.sifta_15m_money_math import format_stgm_with_cents, stgm_to_usd

                pnl_s = format_stgm_with_cents(body_pnl, signed=True)
            except Exception:
                pnl_s = f"{body_pnl:+.5f}"
            wr = float(snap.get("body_win_rate") or 0.0)
            try:
                from System.kalshi_usd_hand import status_line as usd_hand_status

                usd_bit = usd_hand_status(_STATE)
            except Exception:
                usd_bit = "US $ HAND UNKNOWN"
            self.proof_lbl.setText(
                f"STGM {running}  ·  pays {wr:.0%}  ·  {pnl_s}  ·  {usd_bit}"
            )
            try:
                self._paint_usd_lane_button()
            except Exception:
                pass
            self.proof_lbl.setStyleSheet(
                f"background: #111c2b; color: {color}; border: 1px solid #2e4260; "
                f"padding: 6px 10px; border-radius: 8px; font-family: Menlo; "
                f"font-size: {_FC(11)}px;"
            )
            return
        p = load_proof(_STATE)
        n_w = int(p.get("n_wins") or 0)
        n_l = int(p.get("n_losses") or 0)
        pnl = float(p.get("pnl") or 0.0)
        color = _YES if pnl > 0 else (_NO if pnl < 0 else _DIM)
        self.proof_lbl.setText(f"{n_w} won · {n_l} lost  ·  {pnl:+.2f}")
        self.proof_lbl.setStyleSheet(
            f"background: {_CARD}; color: {color}; border: 1px solid #2a3548; "
            f"padding: 6px 10px; border-radius: 6px; font-family: Menlo; "
            f"font-size: {_FC(11)}px;"
        )

    def _set_autopilot_ui(self, on: bool) -> None:
        """STGM / paper autopilot chrome only — not US $ lane."""
        self.paper_loop_on = bool(on)
        if not hasattr(self, "paper_btn"):
            return
        if on:
            self.paper_btn.setText("STGM ON · pause")
            self.paper_btn.setStyleSheet(
                f"QPushButton {{ background: #103126; color: {_YES}; border: 1px solid #276d54; "
                f"padding: 6px 12px; border-radius: 6px; font-size: {_FC(11)}px; font-weight: 800; }}"
            )
            if hasattr(self, "mode"):
                self.mode.setText("STGM ON")
                self.mode.setStyleSheet(
                    f"background: #103126; color: {_YES}; border: 1px solid #276d54; "
                    f"padding: 6px 10px; border-radius: 10px; font-weight: 800; "
                    f"font-size: {_FC(11)}px;"
                )
            if hasattr(self, "event_lbl"):
                self.event_lbl.clear()
                self.event_lbl.hide()
        else:
            self.paper_btn.setText("STGM OFF · resume")
            self.paper_btn.setStyleSheet(
                f"QPushButton {{ background: #1a2435; color: {_DIM}; border: 1px solid #3a4a63; "
                f"padding: 6px 12px; border-radius: 6px; font-size: {_FC(11)}px; font-weight: 700; }}"
            )
            if hasattr(self, "mode"):
                self.mode.setText("STGM PAUSED")
            if hasattr(self, "event_lbl"):
                self.event_lbl.clear()
                self.event_lbl.hide()
        self._paint_usd_lane_button()

    def _paint_usd_lane_button(self) -> None:
        if not hasattr(self, "usd_lane_btn"):
            return
        try:
            from System.kalshi_usd_lane import is_usd_lane_armed

            on = is_usd_lane_armed()
        except Exception:
            on = False
        if on:
            self.usd_lane_btn.setText("US $ LANE ON")
            self.usd_lane_btn.setStyleSheet(
                f"QPushButton {{ background: #103126; color: {_GOLD}; border: 2px solid {_GOLD}; "
                f"padding: 6px 12px; border-radius: 6px; font-size: {_FC(11)}px; font-weight: 800; }}"
            )
        else:
            self.usd_lane_btn.setText("US $ LANE OFF")
            self.usd_lane_btn.setStyleSheet(
                f"QPushButton {{ background: #2a1515; color: {_NO}; border: 1px solid #6d2727; "
                f"padding: 6px 12px; border-radius: 6px; font-size: {_FC(11)}px; font-weight: 800; }}"
            )
        self._paint_ammo_box()

    def _paint_ammo_box(self) -> None:
        """Show owner AMMO ($ per ticket / contract count). Default 2."""
        if not hasattr(self, "ammo_edit"):
            return
        try:
            from System.ledger_deal import get_ammo_usd

            v = get_ammo_usd()
        except Exception:
            v = 2.0
        # avoid clobbering while typing
        if self.ammo_edit.hasFocus():
            return
        txt = str(int(v)) if abs(v - int(v)) < 1e-9 else f"{v:.1f}"
        if self.ammo_edit.text().strip() != txt:
            self.ammo_edit.setText(txt)

    def _on_ammo_edited(self) -> None:
        """Persist AMMO from glass text box (r1693)."""
        raw = (self.ammo_edit.text() or "").strip().replace("$", "")
        try:
            from System.ledger_deal import set_ammo_usd, get_ammo_usd, contracts_for_ammo

            if not raw:
                set_ammo_usd(2.0, reason="glass_ammo_empty_default")
            else:
                set_ammo_usd(float(raw), reason="glass_ammo_edit")
            v = get_ammo_usd()
            n = contracts_for_ammo()
            self.ammo_edit.setText(str(int(v)) if abs(v - int(v)) < 1e-9 else f"{v:.1f}")
            try:
                from System.kalshi_usd_hand import set_hand_live, is_hand_live
                from System.kalshi_usd_lane import is_usd_lane_armed

                if is_hand_live() and is_usd_lane_armed():
                    set_hand_live(
                        True,
                        reason=f"ammo_{n}",
                        owner_phrase=f"AMMO ${v:g} = {n} contracts each",
                    )
            except Exception:
                pass
            _write_receipt(
                "usd_ammo_set",
                {"ammo_usd": v, "contracts": n},
            )
        except Exception:
            self.ammo_edit.setText("2")

    def _toggle_usd_lane(self) -> None:
        """Master switch for real-dollar betting lane. Default OFF. STGM unaffected.

        ON = George armed the lane flag only. Does not place orders by itself.
        Any future order code must still check is_usd_lane_armed() + caps.
        """
        try:
            from System.kalshi_usd_lane import is_usd_lane_armed, set_usd_lane_armed
        except Exception:
            return
        currently = is_usd_lane_armed()
        if currently:
            set_usd_lane_armed(False, reason="glass_button_off")
            _write_receipt("usd_lane_off", {"armed": False})
        else:
            box = QMessageBox(self)
            box.setWindowTitle("US $ betting lane")
            box.setIcon(QMessageBox.Icon.Warning)
            box.setText(
                "Turn ON real US dollar betting lane?\n\n"
                "• STGM autopilot keeps running either way\n"
                "• This does NOT auto-place orders by itself\n"
                "• Your Kalshi cash is still separate (read-only until a real order path fires)\n"
                "• Default was OFF — only you arm it"
            )
            box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            box.setDefaultButton(QMessageBox.StandardButton.No)
            if box.exec() != QMessageBox.StandardButton.Yes:
                return
            set_usd_lane_armed(True, reason="glass_button_on_confirmed")
            _write_receipt("usd_lane_on", {"armed": True, "orders": "not_auto"})
        self._paint_usd_lane_button()
        self._refresh_proof()
        self._refresh_human_portfolio()

    def _toggle_paper_loop(self) -> None:
        """Arm/disarm STGM headless monitor — not US $ lane (r1628 / r1646)."""
        self.paper_loop_on = not self.paper_loop_on
        self._set_autopilot_ui(self.paper_loop_on)
        if self.paper_loop_on:
            _queue_monitor_cmd("autopilot_on", {"max_secs": DEFAULT_MAX_SECS})
            # Never claim writer (paper_loop_on receipt would make monitor yield)
            _write_receipt(
                "glass_autopilot_on",
                {"max_secs": DEFAULT_MAX_SECS, "writer": "headless_monitor"},
            )
        else:
            _queue_monitor_cmd("autopilot_off", {})
            _write_receipt("glass_autopilot_off", {})
        self._refresh_proof()
        self._refresh_human_portfolio()

    def _glass_tick(self) -> None:
        """Disk-only repaint. No Kalshi network. No paper_loop_tick."""
        try:
            _PORTFOLIO_SNAP_CACHE["ts"] = 0.0
            self._refresh_proof()
            self._refresh_human_portfolio()  # includes USD mirror from cache
            self._refresh_learn_state()
        except Exception:
            pass

    def _paper_loop_tick(self) -> None:
        """Legacy name — glass mode redirects to disk paint only."""
        self._glass_tick()

    def _paper_bet_now(self) -> None:
        """Ask headless monitor to force-bet once (no UI network)."""
        _queue_monitor_cmd("force_bet", {"min_fav": 0.70})
        self.event_lbl.setText("Queued force-bet for headless monitor…")
        _write_receipt("paper_bet_now_queued", {})

    def _paper_settle_now(self) -> None:
        """Ask headless monitor to settle once (no UI network)."""
        _queue_monitor_cmd("force_settle", {})
        self.event_lbl.setText("Queued settle for headless monitor…")
        _write_receipt("paper_settle_now_queued", {})

    def closeEvent(self, event) -> None:  # noqa: N802
        self.timer.stop()
        self.autobet_timer.stop()
        try:
            self.paper_timer.stop()
        except Exception:
            pass
        try:
            self.live_timer.stop()
        except Exception:
            pass
        self.engine.save_snapshot()
        _write_receipt("close", self.engine.snapshot())
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_ids.discard(id(self))
        super().closeEvent(event)


# Manifest alias
StigmergicKalshiMarketWidget = SiftaPredictionMarketWidget


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    w = SiftaPredictionMarketWidget()
    w.show()
    raise SystemExit(app.exec())
