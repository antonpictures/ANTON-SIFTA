#!/usr/bin/env python3
"""Ghost Twin — the control-group Alice (r1638, paper only, no real $).

Every in-band candidate ticket (post gate70, BEFORE the Rainman Edge Field
speaks) is also booked by a ghost twin at full unit stake — including every
ticket the field SITS or THINS. The ghost settles on the same public results.

That turns the Edge Field's worth from a story into one continuously updated
number:

    edge_field_value = real_pnl(candidates) − ghost_pnl(candidates)

If the field is wise, the gap grows: sits that would have lost pay her in
avoided units; thins that would have won cost a little and show up honestly.
If the field is superstition, the ghost twin beats her and the number says so
before anyone's pride does. Science, not vibes — the same discipline as the
sit-grading law (r1635) but total: EVERY decision has a graded counterfactual.

Ledgers (never mixed with the real proof):
  .sifta_state/alice_15m_ghost_book.json    open ghost tickets
  .sifta_state/alice_15m_ghost_proof.json   graded ghost scoreboard
  .sifta_state/alice_15m_ghost.jsonl        append-only settle rows
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "SIFTA_GHOST_TWIN_V1"
GHOST_BOOK = "alice_15m_ghost_book.json"
GHOST_PROOF = "alice_15m_ghost_proof.json"
GHOST_LEDGER = "alice_15m_ghost.jsonl"

GHOST_STAKE = 1.0
WINDOW_S = 15 * 60
SETTLE_GRACE_S = 90  # don't poll before close + grace
MAX_LEDGER_BYTES = 8_000_000


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
        "note": "control twin — books every in-band candidate at full stake",
        "n_settled": 0, "n_wins": 0, "n_losses": 0, "pnl": 0.0,
        "by_action": {
            a: {"n": 0, "wins": 0, "pnl": 0.0, "real_pnl": 0.0}
            for a in ("fire", "thin", "sit")
        },
        "edge_field_value": 0.0,
    }


def record_ghost(
    *,
    asset: str,
    ticker: str,
    side: str,
    entry_price: float,
    real_action: str,          # fire | thin | sit  (what the field actually did)
    real_stake: float,         # 0.0 for sit
    score: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> bool:
    """Book one ghost ticket for an in-band candidate. Dedupes by ticker."""
    ticker = str(ticker or "").strip()
    if not ticker:
        return False
    root = _state_dir(state_dir)
    book = _load(root / GHOST_BOOK, {"open": []})
    rows = list(book.get("open") or [])
    if any(str(r.get("ticker")) == ticker for r in rows):
        return False
    rows.append(
        {
            "asset": asset,
            "ticker": ticker,
            "side": str(side),
            "price": round(min(0.99, max(0.01, float(entry_price))), 4),
            "stake": GHOST_STAKE,
            "real_action": str(real_action),
            "real_stake": round(float(real_stake), 4),
            "score": score,
            "ts": time.time(),
        }
    )
    book["open"] = rows[-200:]
    _save(root / GHOST_BOOK, book)
    return True


def settle_ghost(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """Grade ghost tickets whose windows closed. Same public truth as real."""
    root = _state_dir(state_dir)
    book = _load(root / GHOST_BOOK, {"open": []})
    rows = list(book.get("open") or [])
    if not rows:
        return {"n_settled": 0, "n_open": 0}
    try:
        from System.swarm_kalshi_public_feed import _get_json
    except Exception:
        return {"n_settled": 0, "n_open": len(rows), "error": "no_feed_module"}

    proof = _load(root / GHOST_PROOF, _fresh_proof())
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
                # keep for one more hour max, then drop as void
                if now - float(b.get("ts") or 0) < 3600:
                    still_open.append(b)
                continue
            win = str(b.get("side")) == result
            p = float(b.get("price") or 0.5)
            pnl = round(GHOST_STAKE * (1.0 / p - 1.0), 4) if win else -GHOST_STAKE
            action = str(b.get("real_action") or "fire")
            # what the REAL Alice made on this same candidate
            rs = float(b.get("real_stake") or 0.0)
            real_pnl = (round(rs * (1.0 / p - 1.0), 4) if win else -rs) if rs > 0 else 0.0
            proof["n_settled"] = int(proof.get("n_settled") or 0) + 1
            proof["n_wins"] = int(proof.get("n_wins") or 0) + (1 if win else 0)
            proof["n_losses"] = int(proof.get("n_losses") or 0) + (0 if win else 1)
            proof["pnl"] = round(float(proof.get("pnl") or 0.0) + pnl, 4)
            ba = proof.setdefault("by_action", _fresh_proof()["by_action"])
            slot = ba.setdefault(action, {"n": 0, "wins": 0, "pnl": 0.0, "real_pnl": 0.0})
            slot["n"] += 1
            slot["wins"] += 1 if win else 0
            slot["pnl"] = round(float(slot["pnl"]) + pnl, 4)
            slot["real_pnl"] = round(float(slot["real_pnl"]) + real_pnl, 4)
            real_total = sum(float(v.get("real_pnl") or 0.0) for v in ba.values())
            proof["edge_field_value"] = round(real_total - float(proof["pnl"]), 4)
            settled += 1
            row = {"truth_label": TRUTH_LABEL, "event": "ghost_settle", "ts": now,
                   "win": win, "pnl": pnl, "real_pnl": real_pnl, **{k: b.get(k) for k in
                   ("asset", "ticker", "side", "price", "real_action", "real_stake", "score")}}
            ledger = root / GHOST_LEDGER
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
    _save(root / GHOST_BOOK, book)
    _save(root / GHOST_PROOF, proof)
    return {"n_settled": settled, "n_open": len(still_open),
            "edge_field_value": proof.get("edge_field_value")}


def ghost_status(state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    """One-glance verdict: is the Edge Field worth its electricity?"""
    root = _state_dir(state_dir)
    proof = _load(root / GHOST_PROOF, _fresh_proof())
    book = _load(root / GHOST_BOOK, {"open": []})
    n = int(proof.get("n_settled") or 0)
    ba = proof.get("by_action") or {}
    sit = ba.get("sit") or {}
    sit_n = int(sit.get("n") or 0)
    sit_losses = sit_n - int(sit.get("wins") or 0)
    return {
        "truth_label": TRUTH_LABEL,
        "n_settled": n,
        "n_open": len(book.get("open") or []),
        "ghost_pnl": float(proof.get("pnl") or 0.0),
        "edge_field_value": float(proof.get("edge_field_value") or 0.0),
        "sit_n": sit_n,
        "sit_correct": sit_losses,  # a sat ticket that lost = correct sit
        "sit_accuracy": round(sit_losses / sit_n, 3) if sit_n else None,
        "by_action": ba,
    }


def status_line(state_dir: Optional[Path | str] = None) -> str:
    s = ghost_status(state_dir)
    if not s["n_settled"]:
        return "GHOST TWIN: no graded candidates yet"
    acc = f"{s['sit_accuracy']:.0%}" if s["sit_accuracy"] is not None else "—"
    return (
        f"GHOST TWIN n={s['n_settled']} · ghost {s['ghost_pnl']:+.2f}u · "
        f"EDGE FIELD VALUE {s['edge_field_value']:+.2f}u · "
        f"sits {s['sit_n']} (correct {acc})"
    )


__all__ = ["record_ghost", "settle_ghost", "ghost_status", "status_line", "TRUTH_LABEL"]
