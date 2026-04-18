#!/usr/bin/env python3
"""
Locked single-line JSON append (flock) for any append-only log:
  repair_log.jsonl, m5queen_dead_drop.jsonl, human_signals.jsonl, etc.

On platforms without fcntl, falls back to a plain append (previous behavior).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Optional, Union

JsonDict = Mapping[str, Any]


def _repair_ledger_path(p: Path) -> bool:
    return p.name == "repair_log.jsonl"


def _max_stgm_ledger_credit() -> Optional[float]:
    """
    Single-line STGM *credit* ceiling for repair_log.jsonl (anti mega-mint / LLM vibes exploits).
    Set SIFTA_MAX_STGM_LEDGER_CREDIT=0 (or off/false/none) to disable.
    Default 25_000 — blocks accidental 100k test mints; raise env for intentional large grants.
    """
    raw = os.environ.get("SIFTA_MAX_STGM_LEDGER_CREDIT", "25000").strip().lower()
    if raw in ("", "0", "off", "false", "none", "unlimited"):
        return None
    try:
        v = float(raw)
    except ValueError:
        return 25000.0
    return max(v, 0.01)


def _single_line_stgm_credit(ev: dict) -> float | None:
    """Positive STGM credited by this one JSON line, or None if not a credit row."""
    tx = (ev.get("tx_type") or "").strip()
    evn = (ev.get("event") or "").strip()
    if tx == "STGM_MINT":
        a = float(ev.get("amount", 0) or 0)
        return a if a > 0 else None
    if evn in ("MINING_REWARD", "FOUNDATION_GRANT", "UTILITY_MINT"):
        a = float(ev.get("amount_stgm", 0) or 0)
        return a if a > 0 else None
    if "amount_stgm" in ev and not evn and not tx:
        a = float(ev.get("amount_stgm", 0) or 0)
        return a if a > 0 else None
    return None


def _enforce_stgm_credit_ceiling(path: Path, event: JsonDict) -> None:
    if not _repair_ledger_path(path):
        return
    cap = _max_stgm_ledger_credit()
    if cap is None:
        return
    credit = _single_line_stgm_credit(dict(event))
    if credit is not None and credit > cap:
        raise ValueError(
            f"Refused repair_log credit {credit} STGM (ceiling {cap} from "
            f"SIFTA_MAX_STGM_LEDGER_CREDIT). Policy must not be vibes-only for mega-mints."
        )


def append_ledger_line(path: Union[str, Path], event: JsonDict) -> None:
    """Serialize *event* as one JSON line and append with flock when available."""
    p = Path(path)
    _enforce_stgm_credit_ceiling(p, event)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dict(event), ensure_ascii=False) + "\n"
    try:
        import fcntl  # type: ignore
    except ImportError:
        with open(p, "a", encoding="utf-8") as f:
            f.write(line)
        return

    with open(p, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.write(line)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def append_jsonl_line(path: Union[str, Path], event: JsonDict) -> None:
    """Alias for append_ledger_line — same flock semantics for non-ledger JSONL files."""
    append_ledger_line(path, event)
