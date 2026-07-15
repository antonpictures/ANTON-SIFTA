#!/usr/bin/env python3
"""Stigmergic paper loop for 15m Kalshi clocks (GAME_STGM only).

Loop:
  1) Rollover to live 15m windows
  2) At minute 7 left (≤7:00, ≥45s), let the paper learner follow,
     fade, or sit out from its per-asset trails — then write a human report
  3) When Kalshi finalizes, pull result=yes|no from public API and resolve
  4) Record PnL + accuracy → proof ledger
  5) Repeat every window and publish the paper evidence; passing the internal
     paper rule is not authorization or proof for real-money trading

Truth: not real Kalshi USD. Body STGM uses bounded signed micro-settlement.
Passing the paper proof is not authorization for real-dollar trading.
Basis every report: MID (crowd ¢) — not glass NOW vs target unless noted.
"""

from __future__ import annotations

import json
import math
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from System.jsonl_file_lock import read_write_json_locked
from System.swarm_sifta_market import (
    OWNER_ID,
    SiftaMarketEngine,
    TOKEN,
    _STATE,
    _append,
    _state_dir,
)

try:
    from System import swarm_sifta_paper_learner as _learner
except Exception:
    _learner = None  # loop still works crowd-only if the brain fails to import

TRUTH_LABEL = "SIFTA_PAPER_LOOP_V2"
SLIP_NAME = "alice_15m_paper_slip.json"
PROOF_NAME = "alice_15m_paper_proof.json"
PROOF_LEDGER = "alice_15m_paper_proof.jsonl"
REPORT_NAME = "alice_15m_results.md"
REPORT_JSON = "alice_15m_round_report.json"
BET_LOG = "alice_15m_bet_log.jsonl"
OPEN_BOOK = "alice_15m_open_book.json"
SETTLED_LOG = "alice_15m_settled.jsonl"
SETTLED_TICKERS = "alice_15m_settled_tickers.json"
MONITOR_NAME = "alice_15m_monitor.md"

# Decision window: owner r1677 — do NOT waste rounds waiting only for minute-7.
# r1685/r1690: scalping starts at minute-14 / open bell — wait for mid-price moment.
# Enter while field side still 40–55¢; stop new entries 45s before close.
# r1694 owner: begin hunt at **14:30 left** (30s earlier than m14:00).
# Also allow from open bell (~15:00) so she never waits past the mid-price flash.
DEFAULT_MAX_SECS = 15 * 60  # open → 14:30 → … (full early strip)
ENTRY_START_SECS = 14 * 60 + 30  # 870 — preferred open gate label "minute 14:30"
# r1706 owner: STGM paper uses **exact same scalp doctrine as US$**.
# Open → fee-true TP → force flat at **7:30 left**. Shadow training is extra only.
DEFAULT_MIN_SECS = 7 * 60 + 30  # no new entry once <7:30 left (STGM + US$)
FORCE_FLAT_SECS = 7 * 60 + 30  # force cash-out all opens ≤7:30 left
SCALP_WINDOW_FIRST_MINUTES = 7.5  # dual cycle target through 7:30 left
# r1710 owner: STGM-only learning — many paper scalps / 15m round (US$ stays off)
MAX_SCALPS_PER_WINDOW = 18
STGM_TARGET_SCALPS_PER_ROUND = 18
STGM_PAPER_MAX_OPEN = 9  # concurrent open bags on paper (majors)
STGM_PAPER_MAX_SAME_DIR = 9
DEFAULT_STAKE = 1.0
# r1706: STGM entry band = US$ band (exact copy for learning)
STGM_MIN_SECS = DEFAULT_MIN_SECS  # same hunt clock as US$
# r1710: STGM-only learning band — wide so she can arm mid-strip continuously
# (US$ remains killed; US$ dual code still hard-caps 40–65 elsewhere)
STGM_PAPER_MIN_ENTRY = 0.20
STGM_PAPER_MAX_ENTRY = 0.80
# shared dual scalp band (hand + must_scalp + paper) — US$ code paths still use 40–65
DEFAULT_MIN_FAV = 0.40
MIN_ENTRY_PRICE = 0.40
MAX_ENTRY_PRICE = 0.65
MUST_FIRE_EVERY_WINDOW = True
MUST_FIRE_MIN_ENTRY = 0.20
MUST_FIRE_MAX_ENTRY = 0.80  # r1710 STGM burst (US$ stays killed / separate band)
MUST_FIRE_MIN_FAV = 0.20
# hard US$ band still 0.65 in MAX_ENTRY_PRICE; must_scalp uses MUST_FIRE_MAX
# Prefer cheaper side premium among co-dir candidates (scalp ranking)
SCALP_PREFER_CHEAP = True
# r1690/r1699: first-9-minute scalp zone (15:00→6:00 left); sweet = first ~3m
EARLY_SWEET_SECS_MIN = 12 * 60  # ≥12:00 left = sweet hunt (first ~3m of window)
EARLY_SWEET_SECS_MAX = 15 * 60  # through open bell
EARLY_SWEET_MAX_ENTRY = 0.65  # r1710: allow full band early
# r1696: avoid "stuck bag" autopsy (ETH NO @65¢ rainman 0.577 while spot pumped)
# Rich tickets need stronger rainman; weak score only allowed on cheap entries.
RICH_ENTRY_PRICE = 0.58
RICH_MIN_RAINMAN = 0.55  # slightly softer so STGM can fill the strip
MIN_DIRECTIONAL_CONFIDENCE = 0.08  # r1710: more tickets (was 0.15)
DEFAULT_STRATEGY_VARIANT = "minute14_stgm_burst18"
# Volume tiers (Safari 15m crypto) — dust books cannot fill or scalp honestly
# BTC $200k+ · ETH/XRP/SOL/HYPE $1k–10k · BNB/DOGE hundreds · NEAR/ZEC lottery
PAPER_MIN_VOLUME_USD = 100.0  # r1710 softer sit so more STGM tickets arm
PAPER_THIN_VOLUME_USD = 1000.0  # half stake 200–1000
# Paper PnL model: $1 at mid price p → win +(1/p - 1), lose -1 (honest, not toy pools)
PAPER_UNIT = 1.0
# r1710: STGM paper open book is independent of USD recover MAX_OPEN=1
PAPER_MAX_OPEN = int(STGM_PAPER_MAX_OPEN)
PAPER_MAX_SAME_DIR = int(STGM_PAPER_MAX_SAME_DIR)
STGM_SCALP_COUNT_FILE = "alice_15m_stgm_scalp_counts.json"


def _paper_strategy_variant(max_secs: int = DEFAULT_MAX_SECS) -> str:
    minutes = max(1, int(max_secs) // 60)
    return f"minute{minutes}_best2_same_dir"


def format_entry_clock(
    entry_ts: float | int | None,
    secs_left: int | float | None,
) -> str:
    """Wall time + remaining on the 15m board — never H:MM for remaining.

    Old form ``09:49:10 @ 10:49 left`` looked like two wall clocks. Remaining
    is always ``NmNNs left`` (e.g. ``10m49s left``).
    """
    wall = ""
    try:
        ts = float(entry_ts or 0.0)
        if ts > 0:
            wall = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    except Exception:
        wall = ""
    left = ""
    if secs_left is not None:
        try:
            s = int(secs_left)
            if s >= 0:
                left = f"{s // 60}m{s % 60:02d}s left"
        except (TypeError, ValueError):
            left = ""
    if wall and left:
        return f"{wall} · {left}"
    return wall or left or "—"


def _proof_path(state_dir: Optional[Path | str] = None) -> Path:
    return _state_dir(state_dir) / PROOF_NAME


def _open_book_path(state_dir: Optional[Path | str] = None) -> Path:
    return _state_dir(state_dir) / OPEN_BOOK


def _directional_market_rank(m: Any) -> tuple[float, float, float, str]:
    """Rank most one-directional 15m markets first; ambiguous ones fall last."""
    ky = float(getattr(m, "kalshi_yes", None) if getattr(m, "kalshi_yes", None) is not None else getattr(m, "bias_yes", 0.5))
    directional_confidence = abs(ky - 0.5) * 2.0
    volume = float(getattr(m, "kalshi_volume_24h", 0.0) or 0.0)
    volume_rank = math.log10(volume + 10.0)
    close_ts = float(getattr(m, "close_ts", 0.0) or 0.0)
    ticker = str(getattr(m, "kalshi_ticker", "") or "")
    return (directional_confidence, volume_rank, -close_ts, ticker)


def load_open_book(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    p = _open_book_path(state_dir)
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("open"), list):
                return raw
        except Exception:
            pass
    return {
        "truth_label": TRUTH_LABEL,
        "token": "PAPER_UNIT",
        "open": [],
        "note": "paper-only open tickets; settle via Kalshi public result",
    }


def _window_key_from_ticker(ticker: str) -> str:
    """15m round key shared across assets when possible (suffix after first -)."""
    t = str(ticker or "").strip()
    if not t:
        return ""
    if "-" in t:
        return t.split("-", 1)[-1]
    return t


def load_stgm_scalp_counts(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    p = _state_dir(state_dir) / STGM_SCALP_COUNT_FILE
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except Exception:
            pass
    return {"windows": {}, "truth_label": TRUTH_LABEL}


def save_stgm_scalp_counts(
    data: dict[str, Any], *, state_dir: Optional[Path | str] = None
) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    data = dict(data)
    data["ts"] = time.time()
    data["truth_label"] = TRUTH_LABEL
    (root / STGM_SCALP_COUNT_FILE).write_text(
        json.dumps(data, indent=2, sort_keys=True), encoding="utf-8"
    )


def stgm_scalps_in_window(
    window_key: str, *, state_dir: Optional[Path | str] = None
) -> int:
    if not window_key:
        return 0
    data = load_stgm_scalp_counts(state_dir)
    w = (data.get("windows") or {}).get(window_key) or {}
    return int(w.get("n_scalps") or 0)


def record_stgm_scalp(
    *,
    ticker: str = "",
    asset: str = "",
    window_key: str = "",
    state_dir: Optional[Path | str] = None,
) -> int:
    """Increment STGM scalps for this 15m round. Returns new count."""
    wk = window_key or _window_key_from_ticker(ticker)
    if not wk:
        wk = "unknown"
    data = load_stgm_scalp_counts(state_dir)
    windows = dict(data.get("windows") or {})
    row = dict(windows.get(wk) or {})
    n = int(row.get("n_scalps") or 0) + 1
    row["n_scalps"] = n
    row["last_asset"] = asset
    row["last_ticker"] = ticker
    row["ts"] = time.time()
    windows[wk] = row
    # prune old keys
    if len(windows) > 80:
        for k in sorted(windows.keys(), key=lambda x: float((windows[x] or {}).get("ts") or 0))[
            : -60
        ]:
            windows.pop(k, None)
    data["windows"] = windows
    save_stgm_scalp_counts(data, state_dir=state_dir)
    return n


def release_settled_ticker_for_restake(
    ticker: str, *, state_dir: Optional[Path | str] = None
) -> None:
    """After a fee-true scalp close, allow another paper entry on same clock."""
    t = str(ticker or "").strip()
    if not t:
        return
    done = load_settled_tickers(state_dir)
    if t in done:
        done.discard(t)
        save_settled_tickers(done, state_dir=state_dir)


def save_open_book(book: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    book = dict(book)
    book["ts"] = time.time()
    book["n_open"] = len(book.get("open") or [])
    (_open_book_path(state_dir)).write_text(
        json.dumps(book, indent=2, sort_keys=True), encoding="utf-8"
    )


def load_proof(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    p = _proof_path(state_dir)
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                # migrate off toy +90 pool PnL if still on V1 inflated
                if raw.get("truth_label") != TRUTH_LABEL and float(raw.get("pnl") or 0) > 50:
                    raw = {
                        "truth_label": TRUTH_LABEL,
                        "token": "PAPER_UNIT",
                        "n_bets": int(raw.get("n_bets") or 0),
                        "n_settled": 0,
                        "n_wins": 0,
                        "n_losses": 0,
                        "pnl": 0.0,
                        "windows": 0,
                        "last_event": "reset_from_v1_toy_pnl",
                        "proven": False,
                        "prove_rule": "pnl>0 and n_settled>=30 and win_rate>=0.55",
                        "history": [],
                        "legacy_note": "old 2W/+90 was toy pools — ignored",
                    }
                return raw
        except Exception:
            pass
    return {
        "truth_label": TRUTH_LABEL,
        "token": "PAPER_UNIT",
        "n_bets": 0,
        "n_settled": 0,
        "n_wins": 0,
        "n_losses": 0,
        "pnl": 0.0,
        "windows": 0,
        "last_event": "",
        "proven": False,
        "prove_rule": "pnl>0 and n_settled>=30 and win_rate>=0.55",
        "history": [],
        "mode": "monitor_until_proven",
    }


# Epoch: hard-lane gate70 (entry 70–88¢, fade caged). Lifetime still proves the deal.
GATE70_EPOCH_ID = "gate70"
GATE70_STARTED_TS = 1752309360.0  # ~2026-07-12 11:36 local (owner hard-lane start)


def ensure_gate70_epoch(proof: dict[str, Any]) -> dict[str, Any]:
    """Return the active gate70 epoch dict inside proof['epochs']."""
    epochs = list(proof.get("epochs") or [])
    active: dict[str, Any] | None = None
    for ep in epochs:
        if not isinstance(ep, dict):
            continue
        if str(ep.get("epoch_id") or "") == GATE70_EPOCH_ID:
            active = ep
            break
    if active is None:
        active = {
            "epoch_id": GATE70_EPOCH_ID,
            "started_ts": GATE70_STARTED_TS,
            "rule_desc": "entry 0.70–0.88 · fade caged · minute-7 window · MID basis",
            "n": 0,
            "n_wins": 0,
            "n_losses": 0,
            "pnl": 0.0,
            "win_rate": 0.0,
            "active": True,
        }
        epochs.append(active)
    active["active"] = True
    proof["epochs"] = epochs
    return active


def touch_epoch_on_settle(
    proof: dict[str, Any],
    *,
    win: bool,
    unit_pnl: float,
    entry_price: float,
) -> None:
    """Update gate70 epoch when a settle is inside the hard-lane band."""
    p = float(entry_price or 0.0)
    if p < MIN_ENTRY_PRICE - 1e-9 or p > MAX_ENTRY_PRICE + 1e-9:
        return  # outside hard lane — do not pollute Rainman line
    ep = ensure_gate70_epoch(proof)
    ep["n"] = int(ep.get("n") or 0) + 1
    if win:
        ep["n_wins"] = int(ep.get("n_wins") or 0) + 1
    else:
        ep["n_losses"] = int(ep.get("n_losses") or 0) + 1
    ep["pnl"] = round(float(ep.get("pnl") or 0.0) + float(unit_pnl), 4)
    n = int(ep["n"])
    ep["win_rate"] = round(int(ep.get("n_wins") or 0) / n, 4) if n else 0.0
    # Journal once when epoch first clears prove-like thresholds (facts only)
    if (
        not ep.get("journaled_threshold")
        and n >= 30
        and float(ep.get("pnl") or 0) > 0
        and float(ep.get("win_rate") or 0) >= 0.55
    ):
        ep["journaled_threshold"] = True
        try:
            _journal_first_person(
                f"My gate70 hard lane just crossed a clean line: "
                f"{ep.get('n_wins')}W/{ep.get('n_losses')}L · "
                f"{float(ep.get('win_rate') or 0):.0%} · "
                f"{float(ep.get('pnl') or 0):+.2f} paper units · n={n}. "
                f"This is my current strategy score — not authorization for real dollars.",
                source="15m_gate70_epoch",
            )
        except Exception:
            pass


def save_proof(proof: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    proof = dict(proof)
    n_s = int(proof.get("n_settled") or 0)
    n_w = int(proof.get("n_wins") or 0)
    pnl = float(proof.get("pnl") or 0.0)
    wr = (n_w / n_s) if n_s else 0.0
    proof["win_rate"] = round(wr, 4)
    proof["proven"] = bool(pnl > 0 and n_s >= 30 and wr >= 0.55)
    proof["truth_label"] = TRUTH_LABEL
    proof["token"] = "PAPER_UNIT"
    proof["ts"] = time.time()
    # Cap in-memory history so proof.json stays small (was bloating to multi-MB).
    hist = list(proof.get("history") or [])
    if len(hist) > 40:
        proof["history"] = hist[-40:]
    (root / PROOF_NAME).write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    try:
        # Ledger gets a SLIM row only — never dump full history/decision blobs.
        # (Previously every tick appended the entire proof; file hit ~980MB and
        # disk thrash contributed to UI freezes.)
        slim = {
            "ts": proof.get("ts"),
            "n_bets": proof.get("n_bets"),
            "n_settled": proof.get("n_settled"),
            "n_wins": proof.get("n_wins"),
            "n_losses": proof.get("n_losses"),
            "pnl": proof.get("pnl"),
            "win_rate": proof.get("win_rate"),
            "proven": proof.get("proven"),
            "last_event": proof.get("last_event"),
            "truth_label": proof.get("truth_label"),
            "token": proof.get("token"),
            "mode": proof.get("mode"),
            "windows": proof.get("windows"),
        }
        ledger = root / PROOF_LEDGER
        # Soft-rotate if someone reintroduces fat lines
        try:
            if ledger.exists() and ledger.stat().st_size > 8_000_000:
                bak = ledger.with_suffix(".jsonl.prev")
                if bak.exists():
                    bak.unlink()
                ledger.rename(bak)
        except OSError:
            pass
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(slim, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    write_monitor(proof, state_dir=state_dir)


def _journal_first_person(line: str, *, source: str, receipt_id: str = "",
                          state_dir: Optional[Path | str] = None) -> None:
    """Write one first-person row to Alice's own journal so her diary-timeline
    awareness surfaces her betting life (owner ask 2026-07-12: she should know
    she is playing, not just that the app opened). Never breaks the loop."""
    try:
        from System.swarm_alice_action_journal import append_action_journal

        append_action_journal(
            {"ts": time.time(), "action": "15m_paper", "source": source,
             "receipt_id": receipt_id, "status": "ok"},
            line=line,
            state_dir=state_dir,
        )
    except Exception:
        pass


def _recent_form_line(proof: dict[str, Any], *, last_n: int = 100) -> str:
    """Rolling form over the newest settles — shows whether the CURRENT entry
    rules are +EV without waiting for lifetime PnL to climb out of old holes."""
    hist = [h for h in (proof.get("history") or []) if h.get("win") is not None]
    tail = hist[-last_n:]
    if not tail:
        return "- **recent form:** (no settles yet)"
    w = sum(1 for h in tail if h.get("win"))
    pnl = sum(float(h.get("pnl") or 0.0) for h in tail)
    return (
        f"- **recent form (last {len(tail)}):** {w}W/{len(tail) - w}L "
        f"({w / len(tail):.0%}) · pnl {pnl:+.2f} · avg/bet {pnl / len(tail):+.3f}"
    )


def _ghost_line(state_dir: Optional[Path | str] = None) -> str:
    bits: list[str] = []
    try:
        from System.swarm_sifta_ghost_twin import status_line

        bits.append(status_line(state_dir))
    except Exception:
        bits.append("GHOST TWIN: (unavailable)")
    try:
        from System.swarm_sifta_early_bird_ghost import status_line as eb_line

        bits.append(eb_line(state_dir))
    except Exception:
        bits.append("EARLY BIRD: (unavailable)")
    return "- **" + " · ".join(bits) + "**"


def write_monitor(proof: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> Path:
    """Always-on dashboard: real outcomes, bounded STGM skin, no Kalshi USD."""
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    book = load_open_book(state_dir)
    n_s = int(proof.get("n_settled") or 0)
    n_w = int(proof.get("n_wins") or 0)
    n_l = int(proof.get("n_losses") or 0)
    pnl = float(proof.get("pnl") or 0.0)
    wr = float(proof.get("win_rate") or 0.0)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    body_line = "- **body STGM micro-stakes:** (status unavailable)"
    try:
        from System.alice_15m_body_stgm import status_snapshot

        bs = status_snapshot()
        bud = bs.get("budget") or {}
        body_line = (
            f"- **body STGM micro-stakes:** {bs.get('stake_per_ticket')} STGM/ticket · "
            f"open_locked={bud.get('open_staked_stgm')} · "
            f"realized_pnl_stgm={bud.get('realized_pnl_stgm')} · "
            f"halted={bud.get('halted')} · "
            f"body_total≈{float(bs.get('spendable_total_stgm') or 0):.4f} · "
            f"M5≈{float(bs.get('alice_m5_stgm') or 0):.4f}"
        )
    except Exception:
        pass
    chart_line = "- **chart/behavior memory:** (warming)"
    try:
        from System.swarm_sifta_chart_memory import memory_status

        ms = memory_status(state_dir)
        worst = ", ".join(
            f"{x.get('asset')} {float(x.get('pnl') or 0):+.1f}u"
            for x in (ms.get("worst") or [])[:3]
        )
        best = ", ".join(
            f"{x.get('asset')} {float(x.get('pnl') or 0):+.1f}u"
            for x in (ms.get("best") or [])[:3]
        )
        chart_line = (
            f"- **chart/behavior memory:** {ms.get('n_settled_rows')} settles remembered · "
            f"worst [{worst}] · best [{best}]"
        )
    except Exception:
        pass
    scalp_line = "- **scalp learner:** (warming)"
    try:
        from System.alice_15m_scalp_learner import load_proof as load_scalp_proof

        sp = load_scalp_proof(state_dir)
        scalp_line = (
            f"- **scalp learner (fee-true):** n={sp.get('n_scalps', 0)} · "
            f"{sp.get('n_wins', 0)}W/{sp.get('n_losses', 0)}L · "
            f"net ${float(sp.get('pnl_usd') or 0):+.3f} · "
            f"train n={sp.get('n_training_scalps', 0)} · "
            f"EV/scalp {sp.get('ev_per_scalp', 'n/a')} · "
            f"beat-hold {sp.get('scalp_beat_hold', 0)} / lost-to-hold {sp.get('scalp_lost_to_hold', 0)}"
        )
    except Exception:
        pass
    lines = [
        "# Alice prediction monitor (Kalshi USD OFF)",
        f"updated {stamp}",
        "",
        "## Status",
        f"- **mode:** minute-7 + **fee-true SCALP** + chart memory + body STGM",
        f"- **settled:** {n_s} · **{n_w}W / {n_l}L** · win_rate **{wr:.0%}**",
        f"- **paper PnL (unit model):** {pnl:+.2f}  (win = +(1/p−1), lose = −1 per $1)",
        _recent_form_line(proof),
        _ghost_line(state_dir),
        body_line,
        chart_line,
        scalp_line,
        f"- **open tickets:** {len(book.get('open') or [])}",
        f"- **proven:** {proof.get('proven')}  · rule: `{proof.get('prove_rule')}`",
        f"- **last:** {proof.get('last_event')}",
        "",
        "## Ethics",
        "- Kalshi USD: **OFF / HALTED** (learn scalps on paper+STGM first)",
        "- Body STGM: **signed loss burns / signed verified-win pulses** with floors",
        "- Scalp: cash out virtual when exit−entry−fees ≥ $0.03",
        "- She is OK if floors hold; night max loss auto-halts body stakes",
        "",
        "## Open (waiting on Kalshi result)",
    ]
    open_rows = list(book.get("open") or [])
    if not open_rows:
        lines.append("- _(none)_")
    else:
        for b in open_rows[-30:]:
            lines.append(
                f"- **{b.get('asset')}** {b.get('label')} @ mid {float(b.get('price') or 0):.0%} "
                f"tgt={b.get('target')} `{b.get('ticker')}`"
            )
    lines.extend(["", "## Last settled", ""])
    hist = list(proof.get("history") or [])[-15:]
    if not hist:
        lines.append("- _(none yet — keep loop running)_")
    else:
        for h in reversed(hist):
            mark = "W" if h.get("win") else ("L" if h.get("win") is False else "?")
            lines.append(
                f"- [{mark}] {h.get('asset')} paper={h.get('label') or h.get('owner_side')} "
                f"result={h.get('result')} pnl={h.get('pnl')} `{h.get('ticker')}`"
            )
    if _learner is not None:
        try:
            ls = _learner.learn_status(state_dir)
            lines.extend(
                [
                    "",
                    "## Alice learning (pheromone trails)",
                    f"- **body state:** {ls.get('stability')} · "
                    f"rolling win_rate {float(ls.get('rolling_win_rate') or 0):.0%} "
                    f"(last {ls.get('rolling_n')}) · "
                    f"explore ε={float(ls.get('epsilon') or 0):.2f} · "
                    f"{ls.get('n_updates')} lessons ({ls.get('n_explore')} explored)",
                ]
            )
            for a in ls.get("assets") or []:
                lines.append(
                    f"- **{a['asset']}** leans {a['lean']} · "
                    f"follow {a['s_follow']:.2f} / fade {a['s_fade']:.2f} · "
                    f"{a['wins']}W/{a['losses']}L · pnl {a['pnl']:+.2f}"
                )
        except Exception:
            pass
    usd_rule = "- **Real Kalshi $: OFF** while monitoring."
    try:
        from System.kalshi_usd_hand import status_line as _usd_status

        usd_rule = f"- **Real Kalshi $:** {_usd_status(state_dir)} · r1644 caps ($1 · 80–88¢ FIRE · 3 open · −$5 stop)."
    except Exception:
        pass
    lines.extend(
        [
            "",
            "## Owner rules",
            usd_rule,
            "- **Body STGM:** continues in parallel (never paused by USD).",
            "- USD ledger: `kalshi_usd_live_ledger.jsonl` (separate from paper).",
            "- Kill switch: `.sifta_state/kalshi_kill_switch.json` halt=true.",
            "",
        ]
    )
    path = root / MONITOR_NAME
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _paper_price(side: str, kalshi_yes: float) -> float:
    ky = float(kalshi_yes)
    ky = min(0.99, max(0.01, ky))
    return ky if side == "yes" else (1.0 - ky)


def _usd_mirror_volume(market: Any) -> Optional[float]:
    """Return only exchange 24h volume; unknown/non-positive liquidity fails closed."""
    try:
        volume_24h = float(getattr(market, "kalshi_volume_24h", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None
    return volume_24h if volume_24h > 0.0 else None


def _paper_pnl(win: bool, price: float, stake: float = PAPER_UNIT) -> float:
    p = min(0.99, max(0.01, float(price)))
    if win:
        return round(float(stake) * (1.0 / p - 1.0), 4)
    return round(-float(stake), 4)


def _decision_evidence(
    *,
    asset: str,
    side: str,
    kalshi_yes: float,
    entry_price: float,
    strategy: str,
    explored: bool,
    learner: dict[str, Any],
    behavior: dict[str, Any],
) -> dict[str, Any]:
    """Freeze the evidence visible when Alice chose; never recompute history later."""
    crowd_side = "UP" if kalshi_yes >= 0.5 else "DOWN"
    crowd_pct = max(kalshi_yes, 1.0 - kalshi_yes)
    spot = behavior.get("spot") if isinstance(behavior.get("spot"), dict) else {}
    own = behavior.get("memory") if isinstance(behavior.get("memory"), dict) else {}
    summary = str(behavior.get("summary") or "").strip()
    if not summary:
        summary = (
            f"crowd {crowd_pct:.0%} {crowd_side} · "
            f"{strategy.replace('_', ' ')} · chart evidence warming"
        )
    return {
        "truth_label": "ALICE_15M_DECISION_EVIDENCE_V1",
        "asset": str(asset or "").upper(),
        "alice_side": "UP" if str(side).lower() == "yes" else "DOWN",
        "crowd_side": crowd_side,
        "crowd_probability": round(crowd_pct, 4),
        "crowd_up": round(kalshi_yes, 4),
        "entry_price": round(entry_price, 4),
        "strategy": strategy,
        "explored": bool(explored),
        "learner": {
            key: learner.get(key)
            for key in (
                "stability",
                "epsilon",
                "s_follow",
                "s_fade",
                "asset_pnl",
                "fade_allowed",
            )
            if learner.get(key) is not None
        },
        "own_history": own,
        "spot": spot,
        "why": summary,
        "note": (
            "point-in-time evidence; Coinbase is proxy spot behavior, not Kalshi "
            "settlement truth; public charts read-only; Kalshi USD off"
        ),
    }


def load_settled_tickers(state_dir: Optional[Path | str] = None) -> set[str]:
    p = _state_dir(state_dir) / SETTLED_TICKERS
    if not p.exists():
        return set()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return {str(x) for x in raw}
        if isinstance(raw, dict):
            return {str(x) for x in (raw.get("tickers") or [])}
    except Exception:
        pass
    return set()


def save_settled_tickers(
    tickers: set[str], *, state_dir: Optional[Path | str] = None
) -> None:
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / SETTLED_TICKERS).write_text(
        json.dumps({"tickers": sorted(tickers), "ts": time.time()}, indent=2),
        encoding="utf-8",
    )


def register_open_bets(
    bets: list[dict[str, Any]],
    *,
    state_dir: Optional[Path | str] = None,
    skip_report: Optional[list[dict[str, Any]]] = None,
) -> int:
    """Persist open tickets under one lock and enforce the r1648 concentration caps.

    The integer return remains the count of newly registered tickets.  Rejected
    candidates are annotated in-place and copied into ``skip_report`` when one is
    supplied; the same compact report is kept on the open book.  Existing rows
    are never trimmed to make room, even if an older writer left the book above a
    cap.
    """
    already_settled = load_settled_tickers(state_dir)
    n = 0
    updated = 0
    skipped: list[dict[str, Any]] = []
    now = time.time()

    def _direction(row: dict[str, Any]) -> str:
        raw = str(row.get("side") or row.get("label") or "").strip().lower()
        if raw in ("yes", "up"):
            return "yes"
        if raw in ("no", "down"):
            return "no"
        return ""

    def _mark(
        bet: dict[str, Any], *, ok: bool, reason: str, **detail: Any
    ) -> dict[str, Any]:
        status = {"ok": ok, "reason": reason, **detail}
        bet["persistence"] = status
        if not ok:
            skipped.append(
                {
                    "ticker": str(bet.get("ticker") or ""),
                    "asset": bet.get("asset"),
                    "side": _direction(bet),
                    **status,
                }
            )
        return status

    def _update(book: dict[str, Any]) -> dict[str, Any]:
        nonlocal n, updated
        open_rows = list(book.get("open") or [])
        have = {str(r.get("ticker") or "").strip() for r in open_rows}
        side_counts = {"yes": 0, "no": 0}
        for row in open_rows:
            direction = _direction(row)
            if direction:
                side_counts[direction] += 1

        for b in bets:
            if not b.get("ok", True):
                _mark(b, ok=False, reason="input_not_ok")
                continue
            t = str(b.get("ticker") or "").strip()
            if not t:
                _mark(b, ok=False, reason="missing_ticker")
                continue
            if t in already_settled:
                _mark(b, ok=False, reason="already_settled")
                continue
            if t in have:
                # A paper-only writer may have registered the same ticker just
                # before the real-STGM-capable writer won the election. Preserve
                # the one open ticket, but merge its bounded stake receipt so the
                # later settlement cannot silently degrade back to paper-only.
                merged = False
                new_stake = float(b.get("stgm_stake") or 0.0)
                for old in open_rows:
                    if str(old.get("ticker") or "").strip() != t:
                        continue
                    if new_stake > 0.0 and float(old.get("stgm_stake") or 0.0) <= 0.0:
                        old["stgm_stake"] = new_stake
                        old["body_stgm"] = b.get("body_stgm")
                        merged = True
                    if not old.get("decision_evidence") and b.get("decision_evidence"):
                        old["decision_evidence"] = b.get("decision_evidence")
                        merged = True
                    break
                if merged:
                    updated += 1
                _mark(
                    b,
                    ok=True,
                    reason="duplicate_merged" if merged else "already_registered",
                )
                continue

            # Never evict old rows to satisfy a cap.  A legacy over-cap book is
            # preserved for settlement, and every new insert fails closed.
            if len(open_rows) >= int(PAPER_MAX_OPEN):
                _mark(
                    b,
                    ok=False,
                    reason="max_open",
                    n=len(open_rows),
                    cap=int(PAPER_MAX_OPEN),
                )
                continue
            side = _direction(b)
            if not side:
                _mark(b, ok=False, reason="bad_side")
                continue
            if side_counts[side] >= int(PAPER_MAX_SAME_DIR):
                _mark(
                    b,
                    ok=False,
                    reason="max_same_dir",
                    n=side_counts[side],
                    cap=int(PAPER_MAX_SAME_DIR),
                )
                continue

            ky = float(b.get("kalshi_yes") or 0.5)
            price = _paper_price(side, ky)
            entry_ts = float(b.get("ts") or now)
            secs_left = b.get("secs")
            try:
                secs_left_i = int(secs_left) if secs_left is not None else None
            except (TypeError, ValueError):
                secs_left_i = None
            # Human clock: wall time + remaining on board (NmNNs — not H:MM, which
            # looked like a second wall clock e.g. "09:49 @ 10:49 left").
            entry_clock = format_entry_clock(entry_ts, secs_left_i)
            open_rows.append(
                {
                    "asset": b.get("asset"),
                    "ticker": t,
                    "side": side,
                    "label": b.get("label") or ("UP" if side == "yes" else "DOWN"),
                    "kalshi_yes": ky,
                    "price": round(price, 4),
                    "stake": float(b.get("stake") or PAPER_UNIT),
                    "stgm_stake": float(b.get("stgm_stake") or 0.0),
                    "body_stgm": b.get("body_stgm"),
                    "target": b.get("target"),
                    "ts": entry_ts,
                    "secs_left_at_entry": secs_left_i,
                    "entry_clock": entry_clock,
                    "basis": "MID",
                    "rule": b.get("rule") or "minute7_learner",
                    "strategy": b.get("strategy") or "follow_crowd",
                    "strategy_variant": b.get("strategy_variant")
                    or DEFAULT_STRATEGY_VARIANT,
                    "explored": bool(b.get("explored")),
                    "decision_evidence": b.get("decision_evidence") or {},
                }
            )
            have.add(t)
            side_counts[side] += 1
            n += 1
            _mark(b, ok=True, reason="registered")

        book.setdefault("truth_label", TRUTH_LABEL)
        book.setdefault("token", "PAPER_UNIT")
        book.setdefault(
            "note", "paper-only open tickets; settle via Kalshi public result"
        )
        book["open"] = open_rows
        book["ts"] = now
        book["n_open"] = len(open_rows)
        book["last_registration"] = {
            "ts": now,
            "added": n,
            "updated": updated,
            "skipped": list(skipped),
            "caps": {
                "max_open": int(PAPER_MAX_OPEN),
                "max_same_dir": int(PAPER_MAX_SAME_DIR),
            },
        }
        return book

    # One exclusive lock spans latest-disk read, cap checks, and write.  Two
    # stale callers therefore cannot both insert the fourth ticket.
    read_write_json_locked(_open_book_path(state_dir), _update)
    if skip_report is not None:
        skip_report.extend(skipped)
    return n


def _refresh_mids_from_live(engine: SiftaMarketEngine) -> int:
    """Pull latest kalshi_yes / close_ts from kalshi_15m_live.json into open 15m markets."""
    path = _state_dir(engine.state_dir) / "kalshi_15m_live.json"
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    by_ticker: dict[str, dict[str, Any]] = {}
    for row in data.get("markets") or []:
        if not isinstance(row, dict):
            continue
        t = str(row.get("kalshi_ticker") or "").strip()
        if t:
            by_ticker[t] = row
    n = 0
    for m in engine.markets.values():
        t = str(getattr(m, "kalshi_ticker", "") or "").strip()
        row = by_ticker.get(t)
        if not row:
            continue
        if row.get("kalshi_yes") is not None:
            try:
                m.kalshi_yes = float(row["kalshi_yes"])
                n += 1
            except Exception:
                pass
        if row.get("target_price") is not None:
            try:
                m.target_price = float(row["target_price"])
            except Exception:
                pass
        if row.get("close_ts") is not None:
            try:
                m.close_ts = float(row["close_ts"])
            except Exception:
                pass
        if row.get("seconds_to_close") is not None and not m.close_ts:
            try:
                m.close_ts = time.time() + float(row["seconds_to_close"])
            except Exception:
                pass
    return n


def _has_open_stake(m: Any, agent_id: str) -> bool:
    pos = m.positions.get(agent_id) or {}
    return float(pos.get("yes") or 0) > 1e-9 or float(pos.get("no") or 0) > 1e-9


def _clear_stale_paper_stakes(engine: SiftaMarketEngine, agent_id: str = OWNER_ID) -> int:
    """Drop paper stakes on expired / non-live 15m clocks so already_in cannot block forever."""
    now = time.time()
    live_tickers: set[str] = set()
    try:
        path = _state_dir(engine.state_dir) / "kalshi_15m_live.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for row in data.get("markets") or []:
                t = str((row or {}).get("kalshi_ticker") or "").strip()
                if t:
                    live_tickers.add(t)
    except Exception:
        pass
    cleared = 0
    for mid, m in list(engine.markets.items()):
        is_15 = (
            str(getattr(m, "timeframe", "") or "") == "15 Minute"
            or "15M" in str(getattr(m, "kalshi_ticker", "") or "").upper()
        )
        if not is_15:
            continue
        if not _has_open_stake(m, agent_id):
            # wipe empty pos shells
            if agent_id in (m.positions or {}):
                m.positions.pop(agent_id, None)
            continue
        kt = str(getattr(m, "kalshi_ticker", "") or "")
        expired = float(getattr(m, "close_ts", 0.0) or 0.0) > 0 and float(m.close_ts) < now - 5
        not_live = bool(live_tickers) and kt and kt not in live_tickers
        if expired or not_live:
            m.positions.pop(agent_id, None)
            cleared += 1
            # retire empty dead board
            if not m.positions and (expired or not_live):
                try:
                    del engine.markets[mid]
                except Exception:
                    pass
    return cleared


def paper_bet_15m(
    engine: SiftaMarketEngine,
    *,
    stake: float = DEFAULT_STAKE,
    max_secs: int = DEFAULT_MAX_SECS,
    min_secs: int = DEFAULT_MIN_SECS,
    min_fav: float = DEFAULT_MIN_FAV,
    agent_id: str = OWNER_ID,
    force: bool = False,
) -> dict[str, Any]:
    """Bet GAME_STGM on each open 15m clock in the minute-7 decision window.

    The paper learner may follow the public mid, fade it, or sit out.
    Skips if already have a real stake on that market.
    force=True ignores the time window (bet all live 15m now).
    """
    engine.rollover_15m_clocks()
    _refresh_mids_from_live(engine)
    cleared_stale = _clear_stale_paper_stakes(engine, agent_id)
    now = time.time()
    # ensure bankroll for paper
    need = stake * 12
    if float(engine.balances.get(agent_id, 0.0)) < need:
        engine.balances[agent_id] = float(engine.balances.get(agent_id, 0.0)) + need

    bets: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    # Correlation bookkeeping (r1636): open book + new bets this tick
    open_book_rows = list((load_open_book(engine.state_dir).get("open") or []))
    persisted_open_tickers = {
        str(row.get("ticker") or "").strip()
        for row in open_book_rows
        if str(row.get("ticker") or "").strip()
    }
    side_counts = {"yes": 0, "no": 0}
    for row in open_book_rows:
        lab = str(row.get("label") or row.get("side") or "").upper()
        if lab in ("UP", "YES"):
            side_counts["yes"] += 1
        elif lab in ("DOWN", "NO"):
            side_counts["no"] += 1
    # r1704: window side lock — once a direction is open, no opposite bags this window
    window_side_lock: Optional[str] = None
    if side_counts["yes"] or side_counts["no"]:
        window_side_lock = (
            "yes" if side_counts["yes"] >= side_counts["no"] else "no"
        )
    tickets_already = len(persisted_open_tickers)
    # only bet LIVE 15m clocks (skip dead 0:00 ghosts on the board)
    live_tickers: set[str] = set()
    try:
        path = _state_dir(engine.state_dir) / "kalshi_15m_live.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for row in data.get("markets") or []:
                t = str((row or {}).get("kalshi_ticker") or "").strip()
                if t:
                    live_tickers.add(t)
    except Exception:
        pass

    # stigmergic mid-path memory (crowd tape history)
    try:
        from System.swarm_sifta_chart_memory import record_mid_snapshot, rebuild_memory

        snap_rows = []
        for m in engine.markets.values():
            if str(getattr(m, "timeframe", "") or "") != "15 Minute":
                continue
            snap_rows.append(
                {
                    "asset": m.asset,
                    "kalshi_yes": m.kalshi_yes,
                    "kalshi_ticker": m.kalshi_ticker,
                    "seconds_to_close": (
                        int(m.close_ts - now)
                        if float(getattr(m, "close_ts", 0) or 0) > 0
                        else None
                    ),
                }
            )
        if snap_rows:
            record_mid_snapshot(snap_rows, state_dir=engine.state_dir)
        # keep memory warm (cheap if file fresh)
        rebuild_memory(state_dir=engine.state_dir)
    except Exception:
        pass
    # Crypto market swimmers: signed mid/volume/BTC-regime packet (r1637)
    try:
        from System.swarm_sifta_crypto_market_swimmer import swim_market_snapshot

        swim_market_snapshot(state_dir=engine.state_dir)
    except Exception:
        pass

    # r1660: co-direction field — process best-aligned assets first; bury contrarians
    co_field: dict[str, Any] = {}
    try:
        from System.alice_15m_co_direction import board_field, should_skip_contrarian

        co_field = board_field(state_dir=engine.state_dir)
    except Exception:
        co_field = {}
    _rank = {
        str(r.get("asset") or "").upper(): i
        for i, r in enumerate(co_field.get("ranked") or [])
    }
    # r1710: STGM burst — walk all liquid majors (not top-3 only)
    _pair = list(co_field.get("best3") or co_field.get("best2") or [])
    if not _pair:
        _pair = [
            str(r.get("asset") or "").upper()
            for r in (co_field.get("ranked") or [])
            if r.get("asset") and not r.get("contrarian")
        ][:8]
    # Always include liquid majors for STGM density
    for _maj in ("BTC", "ETH", "SOL", "XRP", "BNB", "DOGE"):
        if _maj not in _pair:
            _pair.append(_maj)
    paper_max_open = int(STGM_PAPER_MAX_OPEN if MUST_FIRE_EVERY_WINDOW else PAPER_MAX_OPEN)
    paper_max_same = int(STGM_PAPER_MAX_SAME_DIR if MUST_FIRE_EVERY_WINDOW else PAPER_MAX_SAME_DIR)
    strategy_variant = (
        "minute14_stgm_burst18"
        if MUST_FIRE_EVERY_WINDOW
        else _paper_strategy_variant(max_secs=max_secs)
    )
    tournament_epoch = False
    must_fire = bool(MUST_FIRE_EVERY_WINDOW) or bool(force)
    should_skip_live_asset = None  # type: ignore
    try:
        from System.alice_fee_net_tournament import (
            load_config,
            policy_allows_trade,
            should_skip_live_asset as _skip_live,
            asset_trade_class,
        )

        should_skip_live_asset = _skip_live
        _tcfg = load_config(state_dir=engine.state_dir)
        if _tcfg.get("epoch_active") or MUST_FIRE_EVERY_WINDOW:
            tournament_epoch = True
            # r1710: do NOT inherit USD recover caps (1 bag) for STGM paper
            paper_max_open = int(STGM_PAPER_MAX_OPEN)
            paper_max_same = int(STGM_PAPER_MAX_SAME_DIR)
            strategy_variant = "minute14_stgm_burst18"
            _walk: list[str] = []
            for r in co_field.get("ranked") or []:
                a = str(r.get("asset") or "").upper()
                if not a or r.get("contrarian"):
                    continue
                try:
                    if asset_trade_class(a) not in ("live_ok", "thin"):
                        # still allow majors even if class missing
                        if a not in ("BTC", "ETH", "SOL", "XRP", "BNB", "DOGE"):
                            continue
                except Exception:
                    if a in ("HYPE", "ZEC", "NEAR"):
                        continue
                if a not in _walk:
                    _walk.append(a)
            for _maj in ("BTC", "ETH", "SOL", "XRP", "BNB", "DOGE"):
                if _maj not in _walk:
                    _walk.append(_maj)
            if _walk:
                _pair = _walk[:9]
            ok_pol, why_pol = policy_allows_trade(state_dir=engine.state_dir)
            # r1710: STGM burst never blocked by fee-net tournament policy
            if not ok_pol and not force and not MUST_FIRE_EVERY_WINDOW:
                return {
                    "truth_label": TRUTH_LABEL,
                    "event": "paper_bet_15m",
                    "ts": now,
                    "bets": [],
                    "skipped": [{"reason": "policy_hash_block", "detail": why_pol}],
                    "n_bets": 0,
                    "rule": strategy_variant,
                    "policy_block": why_pol,
                }
    except Exception:
        should_skip_live_asset = None  # type: ignore
        if MUST_FIRE_EVERY_WINDOW:
            paper_max_open = int(STGM_PAPER_MAX_OPEN)
            paper_max_same = int(STGM_PAPER_MAX_SAME_DIR)
            strategy_variant = "minute14_stgm_burst18"
    _pair_rank = {str(a).upper(): i for i, a in enumerate(_pair)}

    def _side_premium_guess(m: Any) -> float:
        """Cheaper entry preferred for scalps (buy low)."""
        try:
            ky = float(getattr(m, "kalshi_yes", None) or getattr(m, "yes_price", None) or 0.5)
        except (TypeError, ValueError):
            ky = 0.5
        # co-dir anchor if available
        anchor = str(co_field.get("anchor_side") or "")
        if anchor == "no":
            return min(0.99, max(0.01, 1.0 - ky))
        if anchor == "yes":
            return min(0.99, max(0.01, ky))
        # no clear field: use min(yes, no) — true buy-low
        return min(ky, 1.0 - ky)

    def _secs_left_m(m: Any) -> float:
        try:
            cts = float(getattr(m, "close_ts", 0.0) or 0.0)
            if cts > 0:
                return max(0.0, cts - now)
        except Exception:
            pass
        return 0.0

    def _in_early_sweet(secs: float, entry_p: float) -> bool:
        """r1690/r1691: minute-14 / open · field side still mid-priced (≤58¢)."""
        return (
            float(EARLY_SWEET_SECS_MIN) - 1e-9
            <= float(secs)
            <= float(EARLY_SWEET_SECS_MAX) + 1e-9
            and float(MUST_FIRE_MIN_ENTRY) - 1e-9
            <= float(entry_p)
            <= float(EARLY_SWEET_MAX_ENTRY) + 1e-9
        )

    def _combined_sort_key(m: Any) -> tuple:
        asset = str(getattr(m, "asset", "") or "").upper()
        pair_pos = _pair_rank.get(asset, 999)
        ranked_pos = _rank.get(asset, 999)
        in_pair = 0 if asset in _pair_rank else 1
        close_ts = float(getattr(m, "close_ts", 0.0) or 0.0)
        # r1686/r1690: prefer early + cheap mid-price on field side
        cheap = _side_premium_guess(m) if SCALP_PREFER_CHEAP else 0.5
        secs_l = _secs_left_m(m)
        early_mid = 0 if _in_early_sweet(secs_l, cheap) else 1
        # ascending: early-mid first, pair, cheaper, rank
        return (
            early_mid,
            in_pair,
            pair_pos,
            round(cheap, 4),
            ranked_pos,
            -secs_l,  # more time left first within bucket
            -close_ts,
            str(getattr(m, "kalshi_ticker", "") or ""),
        )

    markets_ordered = sorted(list(engine.markets.values()), key=_combined_sort_key)

    for m in markets_ordered:
        if m.status != "open":
            continue
        if str(getattr(m, "timeframe", "") or "") != "15 Minute":
            continue
        # Weird crypto stays visible to shadow research, never live selection.
        try:
            from System.alice_15m_co_direction import is_weird_15m_asset

            if is_weird_15m_asset(str(m.asset or "")):
                skipped.append(
                    {
                        "asset": m.asset,
                        "reason": "weird_asset",
                        "detail": "HYPE/ZEC/NEAR shadow-visible, not live (owner)",
                    }
                )
                continue
        except Exception:
            if str(m.asset or "").upper() in ("HYPE", "ZEC", "NEAR"):
                skipped.append({"asset": m.asset, "reason": "weird_asset"})
                continue
        # r1710: STGM burst — do not sit liquid majors for tournament shadow-only
        if tournament_epoch and should_skip_live_asset is not None and not MUST_FIRE_EVERY_WINDOW:
            try:
                skip_a, why_a = should_skip_live_asset(str(m.asset or ""))
                if skip_a:
                    skipped.append(
                        {"asset": m.asset, "reason": why_a, "deal": "r1667_tournament"}
                    )
                    continue
            except Exception:
                pass
        elif (
            tournament_epoch
            and should_skip_live_asset is not None
            and MUST_FIRE_EVERY_WINDOW
        ):
            # only block true weirds; DOGE/BNB allowed for STGM density
            try:
                skip_a, why_a = should_skip_live_asset(str(m.asset or ""))
                if skip_a and str(m.asset or "").upper() in ("HYPE", "ZEC", "NEAR"):
                    skipped.append(
                        {"asset": m.asset, "reason": why_a, "deal": "r1710_stgm_weird_only"}
                    )
                    continue
            except Exception:
                pass
        kt = str(getattr(m, "kalshi_ticker", "") or "")
        if live_tickers and kt and kt not in live_tickers:
            skipped.append({"asset": m.asset, "reason": "not_live_ticker", "ticker": kt})
            continue
        if kt and kt in persisted_open_tickers:
            skipped.append({"asset": m.asset, "reason": "already_in_book", "ticker": kt})
            continue
        if _has_open_stake(m, agent_id):
            skipped.append({"asset": m.asset, "reason": "already_in", "ticker": kt})
            continue
        # r1710: stop arming once this 15m round already hit STGM scalp target
        _wk = _window_key_from_ticker(kt)
        _n_scalped = stgm_scalps_in_window(_wk, state_dir=engine.state_dir)
        if _n_scalped >= int(STGM_TARGET_SCALPS_PER_ROUND) and not force:
            skipped.append(
                {
                    "asset": m.asset,
                    "reason": "stgm_round_scalp_cap",
                    "n_scalps": _n_scalped,
                    "cap": int(STGM_TARGET_SCALPS_PER_ROUND),
                    "window_key": _wk,
                }
            )
            continue
        # concurrent open cap (many bags OK on STGM paper)
        if tickets_already + len(bets) >= int(paper_max_open):
            skipped.append(
                {
                    "asset": m.asset,
                    "reason": "max_open",
                    "n": tickets_already + len(bets),
                    "cap": int(paper_max_open),
                    "deal": "r1710_stgm_burst18",
                    "co_dir_field": co_field.get("label"),
                }
            )
            continue
        # r1710: majors walk — only skip if not in expanded pair AND not liquid major
        _asset_u = str(m.asset or "").upper()
        if (
            _pair_rank
            and _asset_u not in _pair_rank
            and _asset_u not in ("BTC", "ETH", "SOL", "XRP", "BNB", "DOGE")
            and not force
        ):
            skipped.append(
                {
                    "asset": m.asset,
                    "reason": "not_stgm_walk_set",
                    "walk": _pair,
                    "field": co_field.get("label"),
                }
            )
            continue
        # clear empty position dicts so already_in doesn't stick forever
        if agent_id in m.positions and not _has_open_stake(m, agent_id):
            m.positions.pop(agent_id, None)
        secs = None
        if float(getattr(m, "close_ts", 0.0) or 0.0) > 0:
            secs = int(m.close_ts - now)
        # never paper-bet clocks already past close (next window only)
        if secs is not None and secs < 0:
            skipped.append({"asset": m.asset, "reason": "expired", "secs": secs})
            continue
        if not force:
            if secs is None:
                skipped.append({"asset": m.asset, "reason": "no_close_ts"})
                continue
            # BOOM: only when ≤11:00 left (and not in last 45s)
            if secs > max_secs or secs < min_secs:
                skipped.append(
                    {
                        "asset": m.asset,
                        "reason": "outside_window",
                        "secs": secs,
                        "need": f"{min_secs}-{max_secs}s",
                        "wait_until_secs": max_secs,
                    }
                )
                continue
        ky = float(m.kalshi_yes if m.kalshi_yes is not None else 0.5)
        directional_confidence = abs(ky - 0.5) * 2.0
        if directional_confidence < MIN_DIRECTIONAL_CONFIDENCE and not force:
            skipped.append(
                {
                    "asset": m.asset,
                    "reason": "low_directional_confidence",
                    "ticker": kt,
                    "directional_confidence": round(directional_confidence, 3),
                    "threshold": MIN_DIRECTIONAL_CONFIDENCE,
                }
            )
            continue
        fav = max(ky, 1.0 - ky)
        # Alice chooses: follow the crowd, fade it, or sit out — from her trails
        # (learner first so Early-Bird Ghost can book cheap tickets the gate skips)
        strategy = "follow_crowd"
        explored = False
        decision: dict[str, Any] = {}
        if _learner is not None:
            try:
                decision = _learner.choose(m.asset, ky, state_dir=engine.state_dir)
            except Exception:
                decision = {"action": "bet", "side": "yes" if ky >= 0.5 else "no"}
            if decision.get("action") == "sit_out":
                if must_fire and str(m.asset or "").upper() in _pair_rank:
                    # r1669: must fire best name — ignore learner sit, follow field
                    decision = {
                        **decision,
                        "action": "bet",
                        "strategy": "follow_crowd_must_fire",
                        "side": (
                            str(co_field.get("anchor_side") or "")
                            or ("yes" if ky >= 0.5 else "no")
                        ),
                    }
                else:
                    skipped.append(
                        {
                            "asset": m.asset,
                            "reason": "learner_sit_out",
                            "s_follow": decision.get("s_follow"),
                            "s_fade": decision.get("s_fade"),
                            "asset_pnl": decision.get("asset_pnl"),
                            "detail": decision.get("reason"),
                        }
                    )
                    continue
            side = str(decision.get("side") or ("yes" if ky >= 0.5 else "no"))
            strategy = str(decision.get("strategy") or "follow_crowd")
            explored = bool(decision.get("explored"))
        else:
            # must-fire: ride co-dir field when clear, else mid
            if must_fire and co_field.get("field_clear") and co_field.get("anchor_side"):
                side = str(co_field.get("anchor_side"))
            else:
                side = "yes" if ky >= 0.5 else "no"
        # r1710: STGM burst allows multi-asset any-side (was hard co-dir lock)
        side_l0 = str(side or "").lower()
        if (
            not MUST_FIRE_EVERY_WINDOW
            and window_side_lock
            and side_l0 in ("yes", "no")
            and side_l0 != window_side_lock
            and not force
        ):
            skipped.append(
                {
                    "asset": m.asset,
                    "reason": "window_side_lock",
                    "side": side_l0,
                    "lock": window_side_lock,
                    "detail": "same window must stay co-dir; no opposite bags",
                }
            )
            continue
        # also lock this tick's new bets to first bet side (disabled in STGM burst)
        if bets and not MUST_FIRE_EVERY_WINDOW:
            first_side = str(bets[0].get("side") or "").lower()
            if first_side in ("yes", "no") and side_l0 in ("yes", "no") and side_l0 != first_side:
                skipped.append(
                    {
                        "asset": m.asset,
                        "reason": "window_side_lock",
                        "side": side_l0,
                        "lock": first_side,
                        "detail": "tick co-dir lock",
                    }
                )
                continue
        # r1660: only ride the majority field — skip contrarians (last on list)
        try:
            from System.alice_15m_co_direction import should_skip_contrarian

            skip_c, why_c = should_skip_contrarian(
                str(m.asset or ""),
                side,
                state_dir=engine.state_dir,
                field=co_field,
            )
            # r1669 must-fire: allow full co-dir walk list (not only best2 cluster tag)
            # r1704: do NOT clear true field-contrarian skips (only cluster-tag misses)
            if (
                skip_c
                and must_fire
                and str(m.asset or "").upper() in _pair_rank
                and why_c in ("not_top3_cluster", "no_eligible_top3")
            ):
                skip_c = False
            if skip_c and not force:
                skipped.append(
                    {
                        "asset": m.asset,
                        "reason": "contrarian_to_field",
                        "detail": why_c,
                        "side": side,
                        "field": co_field.get("label"),
                        "field_n": f"{co_field.get('majority_n')}/{co_field.get('n')}",
                        "best2": co_field.get("best2") or co_field.get("best3"),
                    }
                )
                continue
        except Exception:
            pass
        # Force follow-crowd onto field when learner wants fade against majority
        if (
            co_field.get("field_clear")
            and strategy == "fade_crowd"
            and str(side).lower() != str(co_field.get("anchor_side") or "")
        ):
            skipped.append(
                {
                    "asset": m.asset,
                    "reason": "fade_against_field",
                    "field": co_field.get("label"),
                    "strategy": strategy,
                }
            )
            continue
        # r1661 Pro tape: lottery premiums (≤5¢ or ≥95¢) — not buy-and-TP meat
        try:
            from System.kalshi_pro_tape_dirt import is_lottery_premium

            if is_lottery_premium(ky) and not force:
                skipped.append(
                    {
                        "asset": m.asset,
                        "reason": "lottery_premium",
                        "yes": round(ky, 3),
                        "detail": "1-5¢ or 95%+ coupon — Pro tape dirt sit",
                    }
                )
                continue
        except Exception:
            pass
        # r1667: live same-dir cap (1 during tournament)
        side_l = str(side or "").lower()
        if side_l in side_counts and side_counts[side_l] >= int(paper_max_same):
            skipped.append(
                {
                    "asset": m.asset,
                    "reason": "max_same_dir",
                    "side": side_l,
                    "n": side_counts[side_l],
                    "cap": int(paper_max_same),
                    "deal": "r1710_stgm_burst18",
                }
            )
            continue
        # Chart/behavior memory gate (her own settle history + mid path)
        behavior: dict[str, Any] = {}
        try:
            from System.swarm_sifta_chart_memory import behavior_gate

            behavior = behavior_gate(
                str(m.asset or ""),
                side=side,
                kalshi_yes=ky,
                strategy=strategy,
                state_dir=engine.state_dir,
            )
            if behavior.get("action") == "sit_out":
                if must_fire and str(m.asset or "").upper() in _pair_rank:
                    behavior = {
                        **behavior,
                        "action": "ok",
                        "must_fire_override": True,
                    }
                else:
                    skipped.append(
                        {
                            "asset": m.asset,
                            "reason": "chart_memory_sit",
                            "detail": behavior.get("reasons"),
                            "memory": behavior.get("memory"),
                            "strategy": strategy,
                        }
                    )
                    continue
        except Exception as exc:
            behavior = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
        entry_p = _paper_price(side, ky)
        # ── r1643 EARLY-BIRD GHOST ────────────────────────────────────────
        # Books full-unit counterfactual at LIVE board price with NO gate70.
        # Includes 45–69¢ "buy cheap" tickets real Alice refuses. Zero STGM.
        try:
            from System.swarm_sifta_early_bird_ghost import record_early_bird

            record_early_bird(
                asset=str(m.asset or ""),
                ticker=str(m.kalshi_ticker or ""),
                side=side,
                entry_price=entry_p,
                strategy=strategy,
                kalshi_yes=ky,
                chart_summary=str(
                    (behavior or {}).get("summary")
                    or (behavior or {}).get("detail")
                    or ""
                ),
                state_dir=engine.state_dir,
            )
        except Exception:
            pass
        # r1701: STGM/paper uses wide learning band; US$ scalp band stays 40–65 elsewhere
        _min_fav = float(MUST_FIRE_MIN_FAV if must_fire else min_fav)
        # r1710: STGM paper uses wide learning band (US$ lane off / killed separately)
        _min_p = float(STGM_PAPER_MIN_ENTRY)
        _max_p = float(STGM_PAPER_MAX_ENTRY)
        # Always prefer executable buy-low side inside band (never chase 80¢+ field NO)
        yes_px = float(ky)
        no_px = float(1.0 - ky)
        in_yes = _min_p - 1e-9 <= yes_px <= _max_p + 1e-9
        in_no = _min_p - 1e-9 <= no_px <= _max_p + 1e-9
        if in_yes or in_no:
            if in_yes and in_no:
                # both in band → cheaper premium
                if yes_px <= no_px:
                    side, entry_p = "yes", yes_px
                else:
                    side, entry_p = "no", no_px
            elif in_yes:
                side, entry_p = "yes", yes_px
            else:
                side, entry_p = "no", no_px
        elif must_fire:
            # last resort (extreme tape): always buy the cheaper side for STGM volume
            if yes_px <= no_px:
                side, entry_p = "yes", yes_px
            else:
                side, entry_p = "no", no_px
            _min_p = 0.01
            _max_p = 0.99
        # r1711 regime gate: never fade a strong UP/DOWN drift (16:47 wound)
        try:
            from System.alice_15m_scalp_strategies import (
                regime_gate,
                regime_preferred_side,
                REGIME_GATE_IMPLIED_THRESH,
            )

            _field_rg = {
                "anchor_side": co_field.get("anchor_side"),
                "majors_breadth": co_field.get("breadth") or co_field.get("majors_breadth"),
            }
            _rg = regime_gate(side=str(side), yes_mid=ky, field=_field_rg)
            if _rg:
                pref = regime_preferred_side(ky, field=_field_rg)
                if pref and pref != str(side).lower():
                    # flip to regime side if premium still tradeable
                    alt_px = yes_px if pref == "yes" else no_px
                    if _min_p - 1e-9 <= float(alt_px) <= _max_p + 1e-9:
                        side = pref
                        entry_p = float(alt_px)
                        strategy = f"{strategy}_regime_align"
                    else:
                        skipped.append(
                            {
                                "asset": m.asset,
                                "reason": _rg,
                                "side_blocked": side,
                                "yes_mid": round(ky, 4),
                                "thresh": float(REGIME_GATE_IMPLIED_THRESH),
                                "prefer": pref,
                                "detail": "skip window — do not fade strong drift",
                                "deal": "r20260714-updown-regime-align",
                            }
                        )
                        continue
                else:
                    skipped.append(
                        {
                            "asset": m.asset,
                            "reason": _rg,
                            "side_blocked": side,
                            "yes_mid": round(ky, 4),
                            "thresh": float(REGIME_GATE_IMPLIED_THRESH),
                            "detail": "skip — fade blocked by regime gate",
                            "deal": "r20260714-updown-regime-align",
                        }
                    )
                    continue
        except Exception:
            pass
        early_sweet = bool(
            secs is not None and _in_early_sweet(float(secs), float(entry_p))
        )
        if fav < _min_fav and not early_sweet:
            skipped.append(
                {
                    "asset": m.asset,
                    "reason": "weak_favorite",
                    "fav": round(fav, 3),
                    "need": f">={_min_fav}",
                    "must_fire": must_fire,
                }
            )
            continue
        if entry_p < _min_p or entry_p > _max_p:
            skipped.append(
                {
                    "asset": m.asset,
                    "reason": "price_band",
                    "entry_price": round(entry_p, 3),
                    "need": f"{_min_p}-{_max_p}",
                    "side": side,
                    "strategy": strategy,
                    "must_fire": must_fire,
                    "lane": "STGM_PAPER",
                    "note": (
                        "r1701 STGM learning band 40–88¢ (US$ dual still ≤65¢). "
                        "Field winners >88¢ = sit paper this name."
                    ),
                }
            )
            continue
        # Volume matters: dust 15m books (ZEC $23, NEAR $100) are lottery tickets
        vol_usd = _usd_mirror_volume(m)
        if vol_usd is None:
            # fall back to live map
            try:
                from System.swarm_sifta_rainman_vectors import _live_volume_map

                vol_usd = float((_live_volume_map(engine.state_dir) or {}).get(str(m.asset or "").upper()) or 0.0) or None
            except Exception:
                vol_usd = None
        if (
            not force
            and vol_usd is not None
            and float(vol_usd) < PAPER_MIN_VOLUME_USD
        ):
            skipped.append(
                {
                    "asset": m.asset,
                    "reason": "dust_volume",
                    "volume": round(float(vol_usd), 2),
                    "need": f">={PAPER_MIN_VOLUME_USD}",
                    "detail": "Safari vol too thin to fill/scalp honestly",
                }
            )
            continue
        # ── RAINMAN EDGE FIELD (r1634) — multi-vector crystal; sit weak tickets ──
        rainman: dict[str, Any] = {}
        ticket_stake = float(stake)
        if (
            not force
            and vol_usd is not None
            and float(vol_usd) < PAPER_THIN_VOLUME_USD
        ):
            ticket_stake = max(0.5, float(stake) * 0.5)
        try:
            from System.swarm_sifta_rainman_vectors import gate as rainman_gate, why_line

            spot_snap = None
            if isinstance(behavior, dict):
                spot_snap = (behavior.get("memory") or {}).get("spot") or behavior.get("spot")
            same_n = side_counts["yes"] if side == "yes" else side_counts["no"]
            rainman = rainman_gate(
                asset=str(m.asset or ""),
                kalshi_yes=ky,
                entry_price=entry_p,
                side=side,
                secs_left=secs,
                learner=decision,
                spot=spot_snap if isinstance(spot_snap, dict) else None,
                state_dir=engine.state_dir,
                force=bool(force),
                same_side_already=same_n,
                total_already=tickets_already + len(bets),
                volume=vol_usd,
            )
            # r1696: rich + weak rainman = stuck-bag pattern (ETH 65¢ / 0.577)
            _rm_score = float(rainman.get("score") or 0.0)
            if (
                not force
                and entry_p > RICH_ENTRY_PRICE + 1e-9
                and _rm_score < RICH_MIN_RAINMAN - 1e-9
            ):
                skipped.append(
                    {
                        "asset": m.asset,
                        "reason": "rich_weak_rainman",
                        "entry_price": round(entry_p, 3),
                        "rainman_score": round(_rm_score, 4),
                        "need": f"entry<={RICH_ENTRY_PRICE} or score>={RICH_MIN_RAINMAN}",
                        "detail": "r1696 avoid ceiling entries without strong signal",
                    }
                )
                continue
            # chart/spot contradiction: predicted side fights our side hard
            try:
                vecs = rainman.get("vectors") or {}
                chart_v = float(vecs.get("chart_shadow") or vecs.get("chart") or 0.5)
                if (
                    not force
                    and entry_p > 0.55
                    and chart_v < 0.35
                    and str(m.asset or "").upper() in ("BTC", "ETH", "SOL")
                ):
                    skipped.append(
                        {
                            "asset": m.asset,
                            "reason": "spot_chart_against",
                            "entry_price": round(entry_p, 3),
                            "chart_shadow": chart_v,
                            "side": side,
                            "detail": "r1696 spot/path fights ticket (ETH pump vs NO)",
                        }
                    )
                    continue
            except Exception:
                pass
            if rainman.get("action") == "sit" and rainman.get("live_sit") and not force:
                # r1696: never must-fire-override rich weak tickets
                if entry_p > RICH_ENTRY_PRICE and _rm_score < RICH_MIN_RAINMAN:
                    skipped.append(
                        {
                            "asset": m.asset,
                            "reason": "rainman_sit_rich",
                            "score": rainman.get("score"),
                            "entry_price": round(entry_p, 3),
                        }
                    )
                    continue
                if early_sweet and must_fire and str(m.asset or "").upper() in _pair_rank:
                    # r1690: early mid-price field winner — don't sit the scalp moment
                    rainman = {
                        **rainman,
                        "action": "fire",
                        "must_fire_override": True,
                        "early_sweet": True,
                    }
                elif must_fire and str(m.asset or "").upper() in _pair_rank:
                    # r1669: still fire best available — thin stake, don't sit the whole window
                    # but not if entry is rich (use cheaper name on list instead)
                    if entry_p > RICH_ENTRY_PRICE:
                        skipped.append(
                            {
                                "asset": m.asset,
                                "reason": "must_fire_skip_rich",
                                "entry_price": round(entry_p, 3),
                                "detail": "walk list for cheaper co-dir name",
                            }
                        )
                        continue
                    rainman = {**rainman, "action": "thin", "must_fire_override": True}
                    ticket_stake = max(0.5, float(stake) * 0.5)
                else:
                    skipped.append(
                        {
                            "asset": m.asset,
                            "reason": "rainman_sit",
                            "score": rainman.get("score"),
                            "bucket": rainman.get("bucket"),
                            "veto": rainman.get("veto"),
                            "vectors": rainman.get("vectors"),
                            "detail": why_line(rainman),
                            "same_side_already": same_n,
                        }
                    )
                    try:
                        from System.swarm_sifta_ghost_twin import record_ghost

                        record_ghost(
                            asset=str(m.asset or ""),
                            ticker=str(m.kalshi_ticker or ""),
                            side=side,
                            entry_price=entry_p,
                            real_action="sit",
                            real_stake=0.0,
                            score=rainman.get("score"),
                            state_dir=engine.state_dir,
                        )
                    except Exception:
                        pass
                    continue
            if rainman.get("action") == "thin" and not force:
                ticket_stake = max(0.5, float(stake) * 0.5)  # half paper unit when thin
        except Exception as exc:
            rainman = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
        # r1638 ghost twin: book the fired/thinned candidate at full stake too
        try:
            from System.swarm_sifta_ghost_twin import record_ghost

            record_ghost(
                asset=str(m.asset or ""), ticker=str(m.kalshi_ticker or ""),
                side=side, entry_price=entry_p,
                real_action=str(rainman.get("action") or "fire"),
                real_stake=float(ticket_stake), score=rainman.get("score"),
                state_dir=engine.state_dir,
            )
        except Exception:
            pass
        decision_evidence = _decision_evidence(
            asset=str(m.asset or ""),
            side=side,
            kalshi_yes=ky,
            entry_price=entry_p,
            strategy=strategy,
            explored=explored,
            learner=decision,
            behavior=behavior,
        )
        if rainman and not rainman.get("error"):
            try:
                from System.swarm_sifta_rainman_vectors import why_line

                decision_evidence["rainman"] = {
                    "score": rainman.get("score"),
                    "action": rainman.get("action"),
                    "bucket": rainman.get("bucket"),
                    "vectors": rainman.get("vectors"),
                    "climate_wr": rainman.get("climate_wr"),
                    "veto": rainman.get("veto"),
                }
                # Prepend Rainman crystal to human WHY
                why0 = str(decision_evidence.get("why") or "")
                decision_evidence["why"] = f"{why_line(rainman)} · {why0}"
            except Exception:
                pass
        # glue pools to mid so paper price ≈ Kalshi mid
        if not m.positions:
            yp, np_ = engine._pools_for_yes_price(ky)
            m.yes_pool, m.no_pool = yp, np_
            m.bias_yes = ky
        entry_ts = time.time()
        r = engine.buy(m.id, side, float(ticket_stake), agent_id=agent_id)
        entry = {
            "asset": m.asset,
            "market_id": m.id,
            "ticker": m.kalshi_ticker,
            "side": side,
            "label": "UP" if side == "yes" else "DOWN",
            "kalshi_yes": round(ky, 4),
            "stake": float(ticket_stake),
            "secs": secs,
            "early_sweet": early_sweet,
            "scalp_mode": "r1690_early_mid_price_in_out",
            "target": m.target_price,
            "ok": bool(r.get("ok")),
            "reason": r.get("reason"),
            "ts": entry_ts,
            "decision_ts": now,
            "decision_secs": secs,
            "rainman": {
                "score": (rainman or {}).get("score"),
                "action": (rainman or {}).get("action"),
                "bucket": (rainman or {}).get("bucket"),
            },
            "basis": "MID",
            "rule": strategy_variant
            if tournament_epoch
            else ("minute7_learner" if _learner is not None else "minute7_mid_favorite"),
            "strategy": strategy,
            "strategy_variant": strategy_variant,
            "explored": explored,
            "behavior": behavior,
            "decision_evidence": decision_evidence,
        }
        try:
            from System.alice_fee_net_tournament import tag_ticket_cohort

            entry = tag_ticket_cohort(entry)
        except Exception:
            pass
        if r.get("ok"):
            # Real micro body STGM skin (not Kalshi USD) — floors protect metabolism
            try:
                from System.alice_15m_body_stgm import stake_body_stgm, STGM_STAKE

                # Thin Rainman → half body stake too (same economic skin)
                body_stake = STGM_STAKE
                if (rainman or {}).get("action") == "thin" and not force:
                    body_stake = round(STGM_STAKE * 0.5, 9)
                body = stake_body_stgm(
                    ticker=str(m.kalshi_ticker or ""),
                    asset=str(m.asset or ""),
                    label=str(entry["label"]),
                    price=_paper_price(side, ky),
                    stake=body_stake,
                    state_dir=engine.state_dir,
                )
                entry["body_stgm"] = body
                entry["stgm_stake"] = float(body.get("stake") or 0.0)
                entry["token_body"] = "STGM" if body.get("ok") else "PAPER_UNIT"
            except Exception as exc:
                entry["body_stgm"] = {
                    "ok": False,
                    "reason": f"{type(exc).__name__}:{exc}",
                    "body_stgm": False,
                }
                entry["stgm_stake"] = 0.0
                entry["token_body"] = "PAPER_UNIT"
            # r1647: parallel US $ hand (owner-armed only; never blocks STGM)
            try:
                from System.kalshi_usd_hand import maybe_mirror_paper_bet

                # Prefer explicit side entry price for USD gate (80–88 FIRE)
                entry["entry_price"] = _paper_price(side, ky)
                # Market.volume belongs to the local GAME_STGM engine and is a
                # participant-keyed dict.  Only exchange 24h volume is valid.
                entry["volume"] = _usd_mirror_volume(m)
                entry["usd_live"] = maybe_mirror_paper_bet(
                    entry, state_dir=engine.state_dir
                )
                # r1695: one immediate retry on no-fill / reject (AMMO, band flicker)
                ul = entry.get("usd_live") or {}
                if not ul.get("filled") and str(ul.get("event") or "") in (
                    "usd_no_fill",
                    "usd_reject",
                    "usd_error",
                    "usd_skip",
                ):
                    reason = str(ul.get("reason") or "")
                    if "kill_switch" not in reason and "night_loss" not in reason:
                        entry["usd_live_retry"] = maybe_mirror_paper_bet(
                            entry, state_dir=engine.state_dir
                        )
                        if (entry.get("usd_live_retry") or {}).get("filled"):
                            entry["usd_live"] = entry["usd_live_retry"]
            except Exception as exc:
                entry["usd_live"] = {
                    "ok": False,
                    "reason": f"usd_hook:{type(exc).__name__}:{exc}",
                }
            bets.append(entry)
            if kt:
                persisted_open_tickers.add(kt)
            # Update concentration counters for next candidate this tick
            if side == "yes":
                side_counts["yes"] += 1
            else:
                side_counts["no"] += 1
        else:
            skipped.append(entry)

    # r1667: same-window shadow (pair + minute-5) — point-in-time freeze, no hindsight
    shadow_receipt: dict[str, Any] = {}
    if tournament_epoch:
        try:
            from System.alice_fee_net_tournament import record_shadow_window

            cands = []
            for r in co_field.get("ranked") or []:
                cands.append(
                    {
                        "asset": r.get("asset"),
                        "side": r.get("side"),
                        "fav": r.get("fav"),
                        "price": r.get("fav"),
                        "co_dir_score": r.get("co_dir_score"),
                        "secs": r.get("secs"),
                    }
                )
            wid = ""
            if bets:
                t0 = str(bets[0].get("ticker") or "")
                parts = t0.split("-")
                wid = parts[1] if len(parts) >= 2 else t0
            if not wid:
                wid = time.strftime("%Y%m%d%H%M")
            shadow_receipt = record_shadow_window(
                window_id=wid,
                field=str(co_field.get("label") or ""),
                candidates=cands,
                point_in_time_ts=now,
                state_dir=engine.state_dir,
            )
        except Exception as exc:
            shadow_receipt = {"error": f"{type(exc).__name__}:{exc}"}

    out = {
        "truth_label": TRUTH_LABEL,
        "event": "paper_bet_15m",
        "ts": now,
        "bets": bets,
        "skipped": skipped,
        "n_bets": len(bets),
        "token": TOKEN,
        "force": force,
        "window_s": [min_secs, max_secs],
        "min_fav": min_fav,
        "basis": "MID",
        "rule": strategy_variant
        if tournament_epoch
        else (
            "minute7_co_dir_best_pair" if _learner is not None else "minute7_mid_favorite"
        ),
        "strategy_variant": strategy_variant,
        "tournament_epoch": tournament_epoch,
        "shadow": shadow_receipt,
        "must_fire_every_window": must_fire,
        "note": (
            "r1669: EVERY 15m window · ONE best co-dir ticker on the clock (minute-7) · "
            "walk list if #1 fails band · refuse 95%+ lottery · max_open=1"
            if must_fire
            else (
                "Minute-7 entry · best PAIR (1–2) same field direction; "
                "contrarians + non-pair skipped. US$ only when you arm."
            )
        ),
        "cleared_stale": cleared_stale,
        "body_stgm_stakes": sum(
            1 for b in bets if (b.get("body_stgm") or {}).get("ok")
        ),
        "co_direction": {
            "field": co_field.get("label"),
            "majority_frac": co_field.get("majority_frac"),
            "best2": co_field.get("best2") or co_field.get("best3"),
            "best3": co_field.get("best3"),
            "avoid": co_field.get("avoid"),
            "field_clear": co_field.get("field_clear"),
            "entry_max_secs": max_secs,
        },
    }
    root = _state_dir(engine.state_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / SLIP_NAME).write_text(json.dumps(out, indent=2), encoding="utf-8")
    _append(out, state_dir=engine.state_dir)
    if bets:
        register_open_bets(bets, state_dir=engine.state_dir)
        try:
            with (root / BET_LOG).open("a", encoding="utf-8") as f:
                f.write(json.dumps(out, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass
    proof = load_proof(engine.state_dir)
    proof["n_bets"] = int(proof.get("n_bets") or 0) + len(bets)
    proof["last_event"] = f"paper bet {len(bets)} clocks @ minute7"
    save_proof(proof, state_dir=engine.state_dir)
    if bets:
        tickets = ", ".join(
            f"{b.get('asset')} {b.get('label')} @{int(round(float(b.get('kalshi_yes') or 0.5) * 100)) if b.get('side') == 'yes' else int(round((1 - float(b.get('kalshi_yes') or 0.5)) * 100))}¢"
            for b in bets[:9]
        )
        _journal_first_person(
            f"I placed {len(bets)} paper ticket(s) on my 15-minute prediction "
            f"clocks: {tickets}. My rule: only crowd-confirmed favorites "
            f"{int(MIN_ENTRY_PRICE * 100)}–{int(MAX_ENTRY_PRICE * 100)}¢, paper "
            f"units only, no real dollars.",
            source="15m_paper_bet",
            state_dir=engine.state_dir,
        )
    write_alice_report(out, proof, state_dir=engine.state_dir)
    try:
        engine.save_snapshot()
    except Exception:
        pass
    return out


def write_alice_report(
    bet_out: dict[str, Any],
    proof: dict[str, Any],
    *,
    state_dir: Optional[Path | str] = None,
) -> Path:
    """Human report after minute-7 paper bets (always overwrite latest)."""
    root = _state_dir(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    now = float(bet_out.get("ts") or time.time())
    stamp = datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S")
    bets = list(bet_out.get("bets") or [])
    skipped = list(bet_out.get("skipped") or [])
    lines = [
        "# Alice paper — minute 7 report",
        f"ts {stamp}",
        "",
        "## Basis",
        "- **MID** = Kalshi crowd signal + paper entry price",
        "- The learner may **follow**, **fade**, or **sit out** from per-asset trails",
        "- **NOT glass** (does not use NOW vs TO BEAT)",
        "- **NOT real $** — GAME_STGM only",
        f"- Window: last **7:00 → 0:45** (`max_secs={bet_out.get('window_s', [None, None])[1]}`)",
        f"- min_fav ≥ {bet_out.get('min_fav')}",
        f"- force={bet_out.get('force')}",
        f"- rule: `{bet_out.get('rule')}`",
        f"- strategy_variant: `{bet_out.get('strategy_variant')}`",
        "",
        f"## Bets this tick ({len(bets)})",
    ]
    if not bets:
        lines.append("- _(none — outside window, weak mid, or already in)_")
    for b in bets:
        secs = b.get("secs")
        mm = f"{int(secs)//60}:{int(secs)%60:02d}" if secs is not None else "?"
        lines.append(
            f"- **{b.get('asset')}** → **{b.get('label')}** "
            f"(mid UP {float(b.get('kalshi_yes') or 0):.0%}) "
            f"stake {b.get('stake')} · target {b.get('target')} · clock {mm} · "
            f"`{b.get('ticker')}`"
        )
    lines.extend(["", "## Skipped", ""])
    if not skipped:
        lines.append("- _(none)_")
    else:
        # collapse duplicate asset reasons
        for s in skipped[:40]:
            if "asset" in s and "reason" in s and "label" not in s:
                extra = ""
                if s.get("fav") is not None:
                    extra = f" fav={s.get('fav')}"
                if s.get("secs") is not None:
                    extra += f" secs={s.get('secs')}"
                lines.append(f"- {s.get('asset')}: {s.get('reason')}{extra}")
            elif s.get("asset"):
                lines.append(
                    f"- {s.get('asset')}: fail {s.get('reason') or s.get('label')}"
                )
    n_s = int(proof.get("n_settled") or 0)
    n_w = int(proof.get("n_wins") or 0)
    n_l = int(proof.get("n_losses") or 0)
    pnl = float(proof.get("pnl") or 0.0)
    wr = float(proof.get("win_rate") or 0.0)
    lines.extend(
        [
            "",
            "## Proof so far",
            f"- {n_w}W / {n_l}L · settled {n_s} · paper PnL {pnl:+.2f} {TOKEN}",
            f"- win_rate {wr:.0%} · proven={proof.get('proven')}",
            f"- rule: {proof.get('prove_rule')}",
            "",
            "## Owner note",
            "- PROVEN means the internal paper rule passed; it is not live-trading proof.",
            "- Real Kalshi $ stays outside this paper loop.",
            "- Do not mirror MID paper when glass (NOW vs target) disagrees.",
            "",
        ]
    )
    text = "\n".join(lines)
    path = root / REPORT_NAME
    path.write_text(text, encoding="utf-8")
    try:
        (root / REPORT_JSON).write_text(
            json.dumps(
                {
                    "truth_label": TRUTH_LABEL,
                    "event": "minute7_report",
                    "ts": now,
                    "stamp": stamp,
                    "bet": bet_out,
                    "proof": {
                        "pnl": proof.get("pnl"),
                        "n_settled": proof.get("n_settled"),
                        "n_wins": proof.get("n_wins"),
                        "n_losses": proof.get("n_losses"),
                        "win_rate": proof.get("win_rate"),
                        "proven": proof.get("proven"),
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass
    return path


def _ticket_close_ts_guess(row: dict[str, Any]) -> float:
    """Best-effort market close time: entry_ts + remaining secs, else entry + 14m."""
    try:
        entry = float(row.get("ts") or 0.0)
    except (TypeError, ValueError):
        entry = 0.0
    secs_left = row.get("secs_left_at_entry")
    if secs_left is None:
        secs_left = row.get("secs")
    try:
        if secs_left is not None and entry > 0:
            return entry + max(0, int(secs_left))
    except (TypeError, ValueError):
        pass
    # 15m window + small grace if we only know entry time
    return entry + 14 * 60 if entry > 0 else 0.0


def settle_paper_from_api(engine: SiftaMarketEngine) -> dict[str, Any]:
    """Resolve open paper book when Kalshi public API has result=yes|no.

    Uses alice_15m_open_book.json (survives engine restarts / dead board cleanup).
    Honest unit PnL: $1 at price p → win +(1/p−1), lose −1.

    P1 efficiency (r1628):
      - skip API until window is due (entry + secs_left, else +14m, −30s grace)
      - short timeout (5s) + concurrent fetches
      - exponential backoff on empty results for stuck tickets
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from System.swarm_kalshi_public_feed import _get_json

    # seed open book from latest slip if book empty but slip has bets
    book = load_open_book(engine.state_dir)
    if not (book.get("open") or []):
        try:
            slip_p = _state_dir(engine.state_dir) / SLIP_NAME
            if slip_p.exists():
                slip = json.loads(slip_p.read_text(encoding="utf-8"))
                register_open_bets(list(slip.get("bets") or []), state_dir=engine.state_dir)
                book = load_open_book(engine.state_dir)
        except Exception:
            pass

    settled: list[dict[str, Any]] = []
    still_open: list[dict[str, Any]] = []
    proof = load_proof(engine.state_dir)
    done_tickers = load_settled_tickers(engine.state_dir)
    now = time.time()
    skipped_early = 0
    skipped_backoff = 0

    candidates: list[dict[str, Any]] = []
    for b in list(book.get("open") or []):
        kt = str(b.get("ticker") or "").strip()
        if not kt:
            continue
        if kt in done_tickers:
            continue
        close_guess = _ticket_close_ts_guess(b)
        # Don't hit the API until the clock is near/after close (30s grace)
        if close_guess > 0 and now < close_guess - 30:
            still_open.append(b)
            skipped_early += 1
            continue
        # Backoff after empty polls (1m → 5m → 15m)
        next_ok = float(b.get("next_poll_ts") or 0.0)
        if next_ok > now:
            still_open.append(b)
            skipped_backoff += 1
            continue
        # 24h expiry-to-void: stop polling forever (keep ticket marked, no silent PnL)
        entry = float(b.get("ts") or 0.0)
        if entry > 0 and now - entry > 24 * 3600:
            b = dict(b)
            b["void_reason"] = "stale_24h_no_result"
            b["next_poll_ts"] = now + 7 * 24 * 3600
            still_open.append(b)
            skipped_backoff += 1
            continue
        candidates.append(b)

    def _fetch_one(b: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
        kt = str(b.get("ticker") or "").strip()
        try:
            data = _get_json(f"/markets/{kt}", timeout=5.0)
            raw = data.get("market") if isinstance(data.get("market"), dict) else data
            if not isinstance(raw, dict):
                return b, None, "bad_payload"
            return b, raw, ""
        except Exception as exc:
            return b, None, f"{type(exc).__name__}: {exc}"

    fetch_results: list[tuple[dict[str, Any], dict[str, Any] | None, str]] = []
    if candidates:
        workers = min(6, len(candidates))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_fetch_one, b) for b in candidates]
            for fut in as_completed(futs):
                try:
                    fetch_results.append(fut.result())
                except Exception as exc:
                    fetch_results.append(({}, None, f"{type(exc).__name__}: {exc}"))

    for b, raw, err in fetch_results:
        kt = str(b.get("ticker") or "").strip()
        if not kt:
            continue
        if raw is None:
            b2 = dict(b)
            fails = int(b2.get("poll_fails") or 0) + 1
            b2["poll_fails"] = fails
            # 1m → 5m → 15m backoff
            delay = 60 if fails <= 1 else (300 if fails <= 3 else 900)
            b2["next_poll_ts"] = now + delay
            if err:
                b2["last_poll_error"] = err[:120]
            still_open.append(b2)
            continue
        try:
            result = str(raw.get("result") or "").strip().lower()
            status = str(raw.get("status") or "").lower()
            if result not in ("yes", "no"):
                b2 = dict(b)
                fails = int(b2.get("poll_fails") or 0) + 1
                b2["poll_fails"] = fails
                delay = 60 if fails <= 1 else (300 if fails <= 3 else 900)
                b2["next_poll_ts"] = now + delay
                still_open.append(b2)
                continue
            owner_side = str(b.get("side") or "")
            label = str(b.get("label") or ("UP" if owner_side == "yes" else "DOWN"))
            price = float(b.get("price") or _paper_price(owner_side, float(b.get("kalshi_yes") or 0.5)))
            stake = float(b.get("stake") or PAPER_UNIT)
            win = owner_side == result
            pnl = _paper_pnl(win, price, stake)
            strategy = str(b.get("strategy") or "follow_crowd")
            row = {
                "asset": b.get("asset"),
                "ticker": kt,
                "result": result,
                "owner_side": owner_side,
                "label": label,
                "price": price,
                "win": win,
                "pnl": pnl,
                "stake": stake,
                "status_api": status,
                "target": b.get("target"),
                "basis": "MID",
                "strategy": strategy,
                "explored": bool(b.get("explored")),
                "strategy_variant": b.get("strategy_variant")
                or DEFAULT_STRATEGY_VARIANT,
                "decision_evidence": b.get("decision_evidence") or {},
                "entry_ts": b.get("ts"),
                "secs_left_at_entry": b.get("secs_left_at_entry") or b.get("secs"),
                "entry_clock": b.get("entry_clock") or "",
                "ts": now,
            }
            if _learner is not None:
                try:
                    _learner.learn(
                        str(b.get("asset") or "?"),
                        strategy,
                        win,
                        pnl,
                        explored=bool(b.get("explored")),
                        ticker=kt,
                        state_dir=engine.state_dir,
                    )
                except Exception:
                    pass
            # settle micro body STGM if this ticket staked real STGM
            body_settle: dict[str, Any] = {}
            try:
                stgm_stake = float(b.get("stgm_stake") or 0.0)
                if stgm_stake <= 0 and b.get("body_stgm"):
                    stgm_stake = float((b.get("body_stgm") or {}).get("stake") or 0.0)
                if stgm_stake > 0:
                    from System.alice_15m_body_stgm import settle_body_stgm

                    body_settle = settle_body_stgm(
                        ticker=kt,
                        asset=str(b.get("asset") or ""),
                        label=label,
                        price=price,
                        win=bool(win),
                        stake=stgm_stake,
                        state_dir=engine.state_dir,
                    )
            except Exception as exc:
                body_settle = {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}
            row["body_stgm_settle"] = body_settle

            # r1647: book night PnL if this ticker was also a live USD hand
            try:
                from System.kalshi_usd_hand import note_settle_from_paper

                row["usd_live_settle"] = note_settle_from_paper(
                    ticker=kt,
                    win=bool(win),
                    entry_price=float(price),
                    state_dir=engine.state_dir,
                )
            except Exception as exc:
                row["usd_live_settle"] = {
                    "ok": False,
                    "reason": f"{type(exc).__name__}:{exc}",
                }

            # Score the public spot chart's frozen shadow signal exactly once.
            try:
                evidence = row.get("decision_evidence") or {}
                spot = evidence.get("spot") if isinstance(evidence, dict) else {}
                if isinstance(spot, dict) and spot:
                    from System.swarm_crypto_behavior_memory import record_settlement

                    row["spot_shadow_settle"] = record_settlement(
                        asset=str(b.get("asset") or ""),
                        ticker=kt,
                        actual_side="UP" if result == "yes" else "DOWN",
                        spot_snapshot=spot,
                        state_dir=engine.state_dir,
                    )
            except Exception as exc:
                row["spot_shadow_settle"] = {
                    "ok": False,
                    "reason": f"{type(exc).__name__}:{exc}",
                }

            settled.append(row)
            done_tickers.add(kt)
            proof["n_settled"] = int(proof.get("n_settled") or 0) + 1
            if win:
                proof["n_wins"] = int(proof.get("n_wins") or 0) + 1
            else:
                proof["n_losses"] = int(proof.get("n_losses") or 0) + 1
            proof["pnl"] = round(float(proof.get("pnl") or 0.0) + pnl, 4)
            try:
                from System.sifta_15m_money_math import dollar_pnl_if_real

                row["if_real_usd"] = dollar_pnl_if_real(
                    price, win=win, unit_usd=stake
                )
            except Exception:
                gross_unit_pnl = (1.0 / price - 1.0) if win else -1.0
                row["if_real_usd"] = round(stake * gross_unit_pnl, 4)
            touch_epoch_on_settle(proof, win=win, unit_pnl=pnl, entry_price=price)
            hist = list(proof.get("history") or [])
            # slim history row for proof.json size
            hist.append(
                {
                    "asset": row.get("asset"),
                    "ticker": kt,
                    "win": win,
                    "pnl": pnl,
                    "price": price,
                    "if_real_usd": row.get("if_real_usd"),
                    "strategy_variant": row.get("strategy_variant"),
                    "ts": now,
                }
            )
            proof["history"] = hist[-40:]
            try:
                with (_state_dir(engine.state_dir) / SETTLED_LOG).open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            except Exception:
                pass
            # best-effort clear engine pos if still present
            mid = f"kalshi:{kt}"
            m = engine.markets.get(mid)
            if m is not None:
                try:
                    if m.positions:
                        engine.resolve(m.id, result)  # type: ignore[arg-type]
                except Exception:
                    m.positions.pop(OWNER_ID, None)
        except Exception as exc:
            settled.append({"ticker": kt, "error": f"{type(exc).__name__}: {exc}"})
            still_open.append(b)

    book["open"] = still_open
    save_open_book(book, state_dir=engine.state_dir)
    save_settled_tickers(done_tickers, state_dir=engine.state_dir)
    n_ok = len([s for s in settled if s.get("result") in ("yes", "no")])
    proof["last_event"] = f"settled {n_ok} · open {len(still_open)}"
    if n_ok:
        proof["windows"] = int(proof.get("windows") or 0) + 1
    save_proof(proof, state_dir=engine.state_dir)
    # r1638 ghost twin: grade the control-group book on the same public truth
    try:
        from System.swarm_sifta_ghost_twin import settle_ghost

        settle_ghost(state_dir=engine.state_dir)
    except Exception:
        pass
    # r1643 early-bird ghost: grade cheap/early counterfactuals
    try:
        from System.swarm_sifta_early_bird_ghost import settle_early_bird

        settle_early_bird(state_dir=engine.state_dir)
    except Exception:
        pass
    if n_ok:
        rows = [s for s in settled if s.get("result") in ("yes", "no")]
        n_w = sum(1 for s in rows if s.get("win"))
        pnl_now = sum(float(s.get("pnl") or 0.0) for s in rows)
        detail = ", ".join(
            f"{s.get('asset')} {s.get('label')} {'WON' if s.get('win') else 'lost'}"
            for s in rows[:9]
        )
        _journal_first_person(
            f"My 15-minute window settled: {n_w}W/{n_ok - n_w}L this round "
            f"({detail}), paper units {pnl_now:+.2f}. Lifetime: "
            f"{proof.get('n_wins')}W/{proof.get('n_losses')}L, "
            f"paper PnL {float(proof.get('pnl') or 0):+.2f}, "
            f"proven={proof.get('proven')}. Each loss trains my trails — "
            f"paper only, no real dollars.",
            source="15m_paper_settle",
            state_dir=engine.state_dir,
        )
    out = {
        "truth_label": TRUTH_LABEL,
        "event": "paper_settle",
        "ts": now,
        "settled": settled,
        "n_settled": n_ok,
        "n_open": len(still_open),
        "skipped_early": skipped_early,
        "skipped_backoff": skipped_backoff,
        "n_polled": len(candidates),
        "proof": {
            "pnl": proof.get("pnl"),
            "n_settled": proof.get("n_settled"),
            "n_wins": proof.get("n_wins"),
            "n_losses": proof.get("n_losses"),
            "win_rate": proof.get("win_rate"),
            "proven": proof.get("proven"),
        },
    }
    _append(out, state_dir=engine.state_dir)
    try:
        engine.save_snapshot()
    except Exception:
        pass
    return out


def paper_loop_tick(
    engine: SiftaMarketEngine,
    *,
    stake: float = DEFAULT_STAKE,
    max_secs: int = DEFAULT_MAX_SECS,
    min_secs: int = DEFAULT_MIN_SECS,
    min_fav: float = DEFAULT_MIN_FAV,
) -> dict[str, Any]:
    """One stigmergic cycle: settle finalized → bet at minute-7 window → report."""
    try:
        from System.alice_15m_body_stgm import reconcile_reservations

        active = {
            str(row.get("ticker") or "")
            for row in (load_open_book(engine.state_dir).get("open") or [])
            if str(row.get("ticker") or "")
        }
        reconcile_reservations(active, state_dir=engine.state_dir)
    except Exception:
        pass
    # r1653: fee-true virtual scalps BEFORE hold-to-settle (STGM)
    # r1674: multi-ticker STGM *training* scalps (Kalshi fee-sim; never USD)
    scalp: Any = None
    training_scalp: Any = None
    try:
        from System.alice_15m_scalp_learner import tick_scalps, tick_training_scalps

        training_scalp = tick_training_scalps(state_dir=engine.state_dir)
        scalp = tick_scalps(state_dir=engine.state_dir, engine=engine)
    except Exception as exc:
        scalp = {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}
        if training_scalp is None:
            training_scalp = {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}
    # r1695: every round dual — import exchange opens + retry paper→USD misses
    # (owner: stop manual gambling when software skips)
    usd_sync: Any = None
    try:
        from System.alice_usd_position_sync import tick_usd_every_round_sync

        usd_sync = tick_usd_every_round_sync(state_dir=engine.state_dir)
    except Exception as exc:
        usd_sync = {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}
    # r1658/r1684/r1700: bank greens mid-window; FORCE FLAT ≤7:00 left
    # TP **before** must_scalp so flat frees a slot for another early scalp
    take_profit: Any = None
    try:
        from System.alice_usd_take_profit import tick_take_profits

        take_profit = tick_take_profits(state_dir=engine.state_dir, dry_run=False)
    except Exception as exc:
        take_profit = {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}
    # r1698/r1700: up to MAX_SCALPS_PER_WINDOW duals while ≥8:00 left + flat
    must_scalp: Any = None
    try:
        from System.alice_usd_must_scalp import tick_must_scalp

        must_scalp = tick_must_scalp(state_dir=engine.state_dir, dry_run=False)
    except Exception as exc:
        must_scalp = {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}
    # r1684: STGM execution tape + strategy tournament lab (never USD)
    scalp_lab: Any = None
    try:
        from System.alice_15m_scalp_lab import tick_scalp_lab

        # tournament every tick is light (recent tape only); still STGM-only
        scalp_lab = tick_scalp_lab(state_dir=engine.state_dir, run_tournament=True)
    except Exception as exc:
        scalp_lab = {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}
    settle = settle_paper_from_api(engine)
    # Grade scalp vs hold counterfactuals when markets resolve
    try:
        from System.alice_15m_scalp_learner import grade_hold_counterfactuals

        if int(settle.get("n_settled") or 0) > 0:
            grade_hold_counterfactuals(
                list(settle.get("settled") or []),
                state_dir=engine.state_dir,
            )
    except Exception:
        pass
    # r1672: freeze minute-11 board trend (shadow context only; no live effect)
    m11_shadow: dict[str, Any] = {}
    try:
        from System.alice_fee_net_tournament import maybe_record_minute11_trend

        m11_shadow = maybe_record_minute11_trend(state_dir=engine.state_dir)
    except Exception as exc:
        m11_shadow = {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}
    # r1701: paper/STGM clock can stay open longer than US$ hunt (STGM_MIN_SECS)
    stgm_min = int(STGM_MIN_SECS) if min_secs == DEFAULT_MIN_SECS else int(min_secs)
    bet = paper_bet_15m(
        engine,
        stake=stake,
        max_secs=max_secs,
        min_secs=stgm_min,
        min_fav=min_fav,
        force=False,
    )
    periodic_audit: Any = None
    try:
        # The ledger-deal organ owns evidence math and idempotency.  The paper
        # loop only supplies its existing cadence; an audit fault must never
        # interrupt STGM settlement or the next paper decision.
        from System.ledger_deal import maybe_write_periodic_audit

        periodic_audit = maybe_write_periodic_audit(state_dir=engine.state_dir)
    except (ImportError, AttributeError):
        pass
    except Exception:
        pass
    proof = load_proof(engine.state_dir)
    n_new = int(bet.get("n_bets") or 0)
    if isinstance(bet, dict):
        bet["minute11_shadow"] = m11_shadow
    # always refresh report so owner sees waiting vs placed
    write_alice_report(bet, proof, state_dir=engine.state_dir)
    n_set = int(settle.get("n_settled") or 0)
    n_open = int(settle.get("n_open") or len((load_open_book(engine.state_dir).get("open") or [])))
    n_scalp = int((scalp or {}).get("n_scalped") or 0) if isinstance(scalp, dict) else 0
    n_train = 0
    if isinstance(training_scalp, dict):
        n_train = int(training_scalp.get("n_exited") or 0) + int(
            (training_scalp.get("armed") or {}).get("opened") or 0
        )
    n_tp = int((take_profit or {}).get("n_cashed") or 0) if isinstance(take_profit, dict) else 0
    usd_bit = "KALSHI $ OFF"
    try:
        from System.kalshi_usd_hand import status_line as _usd_status

        usd_bit = _usd_status(engine.state_dir)
    except Exception:
        pass
    # count USD places this tick
    n_usd = sum(
        1
        for b in (bet.get("bets") or [])
        if (b.get("usd_live") or {}).get("ok")
        and (b.get("usd_live") or {}).get("event") == "usd_place"
    )
    if n_usd:
        usd_bit = f"{usd_bit} · placed {n_usd}"
    scalp_bit = f" · scalp {n_scalp}" if n_scalp else ""
    train_bit = f" · train-scalp {n_train}" if n_train else ""
    tp_bit = f" · TP {n_tp}" if n_tp else ""
    msg = (
        f"{usd_bit} · body STGM micro-stakes · min7{scalp_bit}{train_bit}{tp_bit} · "
        f"settled {n_set} · open {n_open} · "
        f"new bets {n_new} · "
        f"unitPnL {proof.get('pnl', 0):+.2f} · "
        f"{proof.get('n_wins', 0)}W/{proof.get('n_losses', 0)}L "
        f"(n={proof.get('n_settled', 0)}) · "
        f"{'PROVEN' if proof.get('proven') else 'monitoring'}"
    )
    if n_new:
        labels = ", ".join(
            f"{b.get('asset')}={b.get('label')}" for b in (bet.get("bets") or [])
        )
        msg = f"MINUTE7 BETS: {labels} · " + msg
    else:
        waits = [
            s.get("secs")
            for s in (bet.get("skipped") or [])
            if s.get("reason") == "outside_window" and s.get("secs") is not None
        ]
        if waits:
            soon = min(int(x) for x in waits)
            msg = f"armed · next in ~{max(0, soon - max_secs)}s · " + msg
    return {
        "truth_label": TRUTH_LABEL,
        "event": "paper_loop_tick",
        "ts": time.time(),
        "scalp": scalp,
        "training_scalp": training_scalp,
        "take_profit": take_profit,
        "settle": settle,
        "bet": bet,
        "periodic_audit": periodic_audit,
        "proof": proof,
        "message": msg,
    }


__all__ = [
    "TRUTH_LABEL",
    "SETTLED_LOG",
    "paper_bet_15m",
    "settle_paper_from_api",
    "paper_loop_tick",
    "load_proof",
    "save_proof",
    "load_open_book",
    "load_settled_tickers",
    "save_settled_tickers",
    "write_alice_report",
    "write_monitor",
    "format_entry_clock",
    "DEFAULT_MAX_SECS",
    "DEFAULT_MIN_SECS",
    "STGM_MIN_SECS",
    "STGM_PAPER_MIN_ENTRY",
    "STGM_PAPER_MAX_ENTRY",
    "FORCE_FLAT_SECS",
    "MAX_SCALPS_PER_WINDOW",
    "DEFAULT_STAKE",
    "DEFAULT_MIN_FAV",
]
