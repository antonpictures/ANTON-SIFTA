#!/usr/bin/env python3
"""
System/swarm_rlhs_channel_lane.py — Event 115 (fiction vs life RLHS lane)
══════════════════════════════════════════════════════════════════════════
Architect doctrine: RLHS for **fiction co-watch** is not the same contract as
RLHS for **real-life** direct speech. During a logged YouTube co-watch session,
room microphones often pick up **mid-confidence, coherent** screenplay audio;
that must not be stamped as degraded human supervision noise.

Lane is resolved from **receipts**, not from guessing movie titles in the STT text.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

LANE_REAL = "REAL"
LANE_FICTION_COWATCH = "FICTION_COWATCH"

# How long a co-watch receipt keeps the fiction RLHS lane warm (feature film + buffer).
FICTION_LANE_MAX_AGE_S = 7200.0

_FICTION_CATEGORY = frozenset(
    {"fiction", "fictional", "film", "film_clip", "film_clip_page", "movie"}
)


def _last_jsonl_object(path: Path, *, max_tail_bytes: int = 65536) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return None
            chunk = min(max_tail_bytes, size)
            f.seek(size - chunk)
            raw = f.read().decode("utf-8", errors="replace")
        for line in reversed(raw.splitlines()):
            s = line.strip()
            if not s:
                continue
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                continue
    except OSError:
        return None
    return None


def resolve_rlhs_channel_lane(
    *,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> str:
    """
    Return LANE_FICTION_COWATCH when the latest architect co-watch ledger row
    is recent and explicitly tagged as fiction; else LANE_REAL.
    """
    base = Path(state_dir) if state_dir is not None else _STATE
    t = float(now if now is not None else time.time())
    cow = base / "youtube_architect_cowatch.jsonl"
    row = _last_jsonl_object(cow)
    if not row:
        return LANE_REAL
    try:
        ts = float(row.get("ts") or 0.0)
    except (TypeError, ValueError):
        return LANE_REAL
    if ts <= 0 or (t - ts) > FICTION_LANE_MAX_AGE_S:
        return LANE_REAL
    cat = str(row.get("category_lane") or "").strip().lower()
    if cat in _FICTION_CATEGORY:
        return LANE_FICTION_COWATCH
    return LANE_REAL


__all__ = [
    "FICTION_LANE_MAX_AGE_S",
    "LANE_FICTION_COWATCH",
    "LANE_REAL",
    "resolve_rlhs_channel_lane",
]
