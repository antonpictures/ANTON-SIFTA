#!/usr/bin/env python3
"""Early-Bird Ghost — George's cheap-early hypothesis (r1643, paper only).

At minute-11, whenever the learner/chart brain has a directional opinion,
this ghost books a **full unit ticket at the live board price** — including
sub-70¢ "cheap" prices the real Alice refuses under gate70.

No STGM. No Kalshi $. Settles on the same public market result as everyone else.

After enough graded tickets we read one number:

    early_bird_value = early_bird_pnl − real_alice_pnl_on_same_windows

More useful scoreboard fields:
  - early_bird_pnl          total ghost units
  - n_cheap / cheap_pnl     tickets booked below gate70 floor (the hypothesis)
  - n_in_band / in_band_pnl tickets that real Alice might also have bought
  - vs_gate70_note          narrative: does buying early/cheap beat waiting?

Ledgers (never mixed with real proof or Edge-Field ghost twin):
  .sifta_state/alice_15m_early_bird_book.json
  .sifta_state/alice_15m_early_bird_proof.json
  .sifta_state/alice_15m_early_bird.jsonl
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "SIFTA_EARLY_BIRD_GHOST_V1"
BIRD_BOOK = "alice_15m_early_bird_book.json"
BIRD_PROOF = "alice_15m_early_bird_proof.json"
BIRD_LEDGER = "alice_15m_early_bird.jsonl"

BIRD_STAKE = 1.0
WINDOW_S = 15 * 60
SETTLE_GRACE_S = 90
MAX_LEDGER_BYTES = 8_000_000
# Real Alice's confirmation band floor — below this is the "cheap early" lane
GATE70_FLOOR = 0.70


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except Exception:
            pass
    return dict(default)


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(data)
    data["truth_label"] = TRUTH_LABEL
    data["ts"] = time.time()
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _fresh_proof() -> dict[str, Any]:
    return {
        "note": (
            "early-bird ghost — books chart/learner direction at live minute-11 "
            "price with no gate70; grades on public settle"
        ),
        "n_settled": 0,
        "n_wins": 0,
        "n_losses": 0,
        "pnl": 0.0,
        "n_cheap": 0,
        "cheap_pnl": 0.0,
        "n_in_band": 0,
        "in_band_pnl": 0.0,
        "hypothesis": "buy_cheap_if_chart_knows_early",
    }


def record_early_bird(
    *,
    asset: str,
    ticker: str,
    side: str,
    entry_price: float,
    strategy: str = "",
    kalshi_yes: Optional[float] = None,
    chart_summary: str = "",
    state_dir: Optional[Path | str] = None,
) -> bool:
    """Book one early-bird ticket. Dedupes by ticker. No real stake."""
    ticker = str(ticker or "").strip()
    if not ticker:
        return False
    try:
        p = float(entry_price)
    except (TypeError, ValueError):
        return False
    p = min(0.99, max(0.01, p))
    root = _state_dir(state_dir)
    book = _load(root / BIRD_BOOK, {"open": []})
    rows = list(book.get("open") or [])
    if any(str(r.get("ticker")) == ticker for r in rows):
        return False
    cheap = p < GATE70_FLOOR
    rows.append(
        {
            "asset": str(asset or "?"),
            "ticker": ticker,
            "side": str(side).lower(),
            "price": round(p, 4),
            "stake": BIRD_STAKE,
            "cheap": cheap,
            "lane": "cheap_early" if cheap else "in_band_early",
            "strategy": str(strategy or ""),
            "kalshi_yes": kalshi_yes,
            "chart_summary": str(chart_summary or "")[:200],
            "ts": time.time(),
        }
    )
    book["open"] = rows[-300:]
    _save(root / BIRD_BOOK, book)
    return True


def settle_early_bird(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Grade early-bird tickets on the same public results as real Alice."""
    root = _state_dir(state_dir)
    book = _load(root / BIRD_BOOK, {"open": []})
    rows = list(book.get("open") or [])
    if not rows:
        return {"n_settled": 0, "n_open": 0}
    try:
        from System.swarm_kalshi_public_feed import _get_json
    except Exception:
        return {"n_settled": 0, "n_open": len(rows), "error": "no_feed_module"}

    proof = _load(root / BIRD_PROOF, _fresh_proof())
    now = time.time()
    still_open: list[dict[str, Any]] = []
    settled = 0
    for b in rows:
        if now - float(b.get("ts") or 0) < WINDOW_S + SETTLE_GRACE_S:
            still_open.append(b)
            continue
        try:
            data = _get_json(f"/markets/{b['ticker']}", timeout=8.0)
            raw = data.get("market") if isinstance(data.get("market"), dict) else data
            result = str((raw or {}).get("result") or "").strip().lower()
            if result not in ("yes", "no"):
                if now - float(b.get("ts") or 0) < 3600:
                    still_open.append(b)
                continue
            win = str(b.get("side")) == result
            p = float(b.get("price") or 0.5)
            # unit ticket at entry price — same gross mult model as ghost twin
            pnl = round(BIRD_STAKE * (1.0 / p - 1.0), 4) if win else -BIRD_STAKE
            cheap = bool(b.get("cheap")) or p < GATE70_FLOOR
            proof["n_settled"] = int(proof.get("n_settled") or 0) + 1
            proof["n_wins"] = int(proof.get("n_wins") or 0) + (1 if win else 0)
            proof["n_losses"] = int(proof.get("n_losses") or 0) + (0 if win else 1)
            proof["pnl"] = round(float(proof.get("pnl") or 0.0) + pnl, 4)
            if cheap:
                proof["n_cheap"] = int(proof.get("n_cheap") or 0) + 1
                proof["cheap_pnl"] = round(float(proof.get("cheap_pnl") or 0.0) + pnl, 4)
            else:
                proof["n_in_band"] = int(proof.get("n_in_band") or 0) + 1
                proof["in_band_pnl"] = round(
                    float(proof.get("in_band_pnl") or 0.0) + pnl, 4
                )
            settled += 1
            row = {
                "truth_label": TRUTH_LABEL,
                "event": "early_bird_settle",
                "ts": now,
                "win": win,
                "pnl": pnl,
                "cheap": cheap,
                **{
                    k: b.get(k)
                    for k in (
                        "asset",
                        "ticker",
                        "side",
                        "price",
                        "lane",
                        "strategy",
                        "chart_summary",
                    )
                },
            }
            ledger = root / BIRD_LEDGER
            try:
                if ledger.exists() and ledger.stat().st_size > MAX_LEDGER_BYTES:
                    prev = ledger.with_suffix(".jsonl.prev")
                    if prev.exists():
                        prev.unlink()
                    ledger.rename(prev)
                with ledger.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            except Exception:
                pass
        except Exception:
            still_open.append(b)
    book["open"] = still_open
    _save(root / BIRD_BOOK, book)
    _save(root / BIRD_PROOF, proof)
    return {
        "n_settled": settled,
        "n_open": len(still_open),
        "pnl": proof.get("pnl"),
        "cheap_pnl": proof.get("cheap_pnl"),
        "n_cheap": proof.get("n_cheap"),
    }


def early_bird_status(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """One-glance: does buying cheap/early beat waiting for 70¢?"""
    root = _state_dir(state_dir)
    proof = _load(root / BIRD_PROOF, _fresh_proof())
    book = _load(root / BIRD_BOOK, {"open": []})
    n = int(proof.get("n_settled") or 0)
    n_cheap = int(proof.get("n_cheap") or 0)
    cheap_pnl = float(proof.get("cheap_pnl") or 0.0)
    wr = (
        int(proof.get("n_wins") or 0) / n
        if n
        else None
    )
    # verdict needs sample size
    if n < 30:
        verdict = "warming"
        note = f"need ~100 graded · have {n}"
    elif n_cheap < 20:
        verdict = "need_more_cheap"
        note = f"only {n_cheap} sub-70¢ tickets graded"
    elif cheap_pnl > 0.5:
        verdict = "cheap_lane_earns"
        note = "early/cheap ghost above water — candidate for paper epoch"
    elif cheap_pnl < -1.0:
        verdict = "gate70_was_right"
        note = "cheap-early bled — confirmation band earned its keep"
    else:
        verdict = "inconclusive"
        note = "near flat — keep grading"
    return {
        "truth_label": TRUTH_LABEL,
        "n_settled": n,
        "n_open": len(book.get("open") or []),
        "n_wins": int(proof.get("n_wins") or 0),
        "n_losses": int(proof.get("n_losses") or 0),
        "wr": round(wr, 3) if wr is not None else None,
        "pnl": float(proof.get("pnl") or 0.0),
        "n_cheap": n_cheap,
        "cheap_pnl": cheap_pnl,
        "n_in_band": int(proof.get("n_in_band") or 0),
        "in_band_pnl": float(proof.get("in_band_pnl") or 0.0),
        "verdict": verdict,
        "note": note,
    }


def status_line(state_dir: Optional[Path | str] = None) -> str:
    s = early_bird_status(state_dir)
    if not s["n_settled"]:
        return "EARLY BIRD: no graded tickets yet · books cheap/early at min-11"
    wr = f"{s['wr']:.0%}" if s.get("wr") is not None else "—"
    return (
        f"EARLY BIRD n={s['n_settled']} ({wr}) · "
        f"all {s['pnl']:+.2f}u · cheap({s['n_cheap']}) {s['cheap_pnl']:+.2f}u · "
        f"{s['verdict']}"
    )


__all__ = [
    "record_early_bird",
    "settle_early_bird",
    "early_bird_status",
    "status_line",
    "TRUTH_LABEL",
    "GATE70_FLOOR",
]
