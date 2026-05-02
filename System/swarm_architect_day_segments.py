#!/usr/bin/env python3
"""
System/swarm_architect_day_segments.py — Event 117
══════════════════════════════════════════════════════════════════════════
Append-only **Architect day segments** (sleep, work blocks, etc.) so Alice can
answer "where was I / what was I doing" from **receipts**, not vibes.

Ledger: ``.sifta_state/architect_day_segments.jsonl``
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
LEDGER = _STATE / "architect_day_segments.jsonl"

TRUTH_LABEL = "ARCHITECT_DAY_SEGMENT_V1"

_SLEEP_CUE = re.compile(
    r"\b(?:slept|sleep|sleeping|napping|nap|napped|rest|resting)\b",
    re.IGNORECASE,
)
_ACTIVITY_QUERY = re.compile(
    r"\b(?:"
    r"where\s+was\s+i|what\s+was\s+i\s+doing|what\s+did\s+i\s+do|"
    r"what\s+.*(?:schedule|nap|sleep|block)|remember\s+.*(?:schedule|block|nap|sleep)|"
    r"what\s+happened\s+(?:\d+\s*(?:min|minute|hour|hr)s?\s+ago|earlier|before)|"
    r"do\s+you\s+know\s+what\s+happened"
    r")\b",
    re.IGNORECASE,
)

# "from 11 am to 3 pm" | "11ap to 3pm" | "11am-3pm"
_RANGE_FROM = re.compile(
    r"(?:from|between)\s+"
    r"(?P<h1>\d{1,2})(?::(?P<m1>[0-5]\d))?\s*(?P<a1>a\.?m\.?|p\.?m\.?|ap)\b"
    r".{0,48}?"
    r"(?:to|until|-|—)\s*"
    r"(?P<h2>\d{1,2})(?::(?P<m2>[0-5]\d))?\s*(?P<a2>a\.?m\.?|p\.?m\.?)\b",
    re.IGNORECASE | re.DOTALL,
)
_RANGE_COMPACT = re.compile(
    r"\b(?P<h1>\d{1,2})(?::(?P<m1>[0-5]\d))?\s*(?P<a1>a\.?m\.?|p\.?m\.?|ap)\b"
    r"\s*(?:to|-|—)\s*"
    r"(?P<h2>\d{1,2})(?::(?P<m2>[0-5]\d))?\s*(?P<a2>a\.?m\.?|p\.?m\.?)\b",
    re.IGNORECASE,
)


def _norm_ampm(s: str) -> str:
    t = (s or "").strip().lower().replace(".", "")
    if t in {"ap", "a"}:  # common STT glitch for "am"
        return "am"
    if t.startswith("a"):
        return "am"
    if t.startswith("p"):
        return "pm"
    return "am"


def _to_minutes_simple(hour: int, minute: int, ampm: str) -> int:
    h = int(hour)
    m = int(minute) % 60
    ap = _norm_ampm(ampm)
    if ap == "am":
        h24 = 0 if h == 12 else h % 12
    else:
        h24 = 12 if h == 12 else (h % 12) + 12
    return h24 * 60 + m


def _parse_range(text: str) -> Optional[tuple[int, int, str]]:
    """Return (start_min, end_min, label) or None."""
    t = text or ""
    m = _RANGE_FROM.search(t) or _RANGE_COMPACT.search(t)
    if not m:
        return None
    h1 = int(m.group("h1"))
    m1 = int(m.group("m1") or 0)
    a1 = m.group("a1")
    h2 = int(m.group("h2"))
    m2 = int(m.group("m2") or 0)
    a2 = m.group("a2")
    try:
        s0 = _to_minutes_simple(h1, m1, a1)
        s1 = _to_minutes_simple(h2, m2, a2)
    except Exception:
        return None
    if s1 < s0:
        s1 += 24 * 60  # crossed midnight (rare for nap)
    label = "sleep" if _SLEEP_CUE.search(t) else "activity"
    return s0, s1, label


def _location_hint(text: str) -> str:
    tl = text.lower()
    if re.search(r"\b(bedroom|bed\s*room|bedrook|in\s+bed)\b", tl):
        return "bedroom"
    if "living room" in tl:
        return "living_room"
    return ""


def _media_hint(text: str) -> str:
    tl = text.lower()
    has_youtube = "youtube" in tl or "you tube" in tl
    has_tv = bool(re.search(r"\b(?:tv|television)\b", tl))
    loud = bool(re.search(r"\b(?:loud|loudly|volume)\b", tl))
    listening = bool(re.search(r"\b(?:listening|playing|hearing|on)\b", tl))
    if has_youtube and (has_tv or listening):
        return "youtube_tv_loud" if loud else "youtube_tv"
    if has_youtube:
        return "youtube"
    if has_tv:
        return "tv_loud" if loud else "tv"
    return ""


def _context_note(text: str) -> str:
    s = " ".join((text or "").split())
    if len(s) > 220:
        return s[:220] + "…"
    return s


def _local_date(ts: Optional[float] = None) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(ts or time.time()))


def try_ingest_architect_day_segment(text: str, *, state_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    If ``text`` states a sleep/nap window with explicit times, append one ledger row.
    Returns the row if written, else None.
    """
    raw = (text or "").strip()
    if len(raw) < 12:
        return None
    parsed = _parse_range(raw)
    if not parsed:
        return None
    s0, s1, label = parsed
    if label != "sleep" and not _SLEEP_CUE.search(raw):
        # v1: only auto-ingest sleep-tagged windows (avoid random "9 to 5" noise).
        return None
    base = Path(state_dir) if state_dir is not None else _STATE
    base.mkdir(parents=True, exist_ok=True)
    path = base / "architect_day_segments.jsonl"
    ld = _local_date()
    row: Dict[str, Any] = {
        "schema_version": "architect_day_segment.v1",
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "local_date": ld,
        "start_minute_of_day": int(s0),
        "end_minute_of_day": int(s1),
        "duration_minutes": int(max(0, s1 - s0)),
        "label": label,
        "location": _location_hint(raw),
        "media_context": _media_hint(raw),
        "context_note": _context_note(raw),
        "source": "user_stated_conversation",
        "source_text_sha256": hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest(),
    }
    append_line_locked(path, json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return row


def _tail_rows(path: Path, n: int = 24) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_bytes().splitlines()[-max(1, n) :]
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for raw in lines:
        try:
            r = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _fmt_hhmm(mins: int) -> str:
    mins = int(mins) % (24 * 60)
    h, m = divmod(mins, 60)
    return datetime(2000, 1, 1, h, m).strftime("%I:%M %p").lstrip("0")


def format_segments_for_prompt(*, state_dir: Optional[Path] = None, max_rows: int = 10) -> str:
    """Compact block for system prompt."""
    base = Path(state_dir) if state_dir is not None else _STATE
    path = base / "architect_day_segments.jsonl"
    today = _local_date()
    rows = [r for r in _tail_rows(path, 48) if str(r.get("local_date") or "") == today][-max_rows:]
    if not rows:
        return ""
    lines = ["ARCHITECT DAY SEGMENTS (local ledger, today):"]
    for r in rows:
        try:
            a = int(r.get("start_minute_of_day", 0))
            b = int(r.get("end_minute_of_day", 0))
        except Exception:
            continue
        loc = str(r.get("location") or "").strip()
        media = str(r.get("media_context") or "").strip()
        lab = str(r.get("label") or "block")
        note = str(r.get("context_note") or "")[:120]
        loc_s = f" loc={loc}" if loc else ""
        media_s = f" media={media}" if media else ""
        lines.append(f"- {lab}{loc_s}{media_s} {_fmt_hhmm(a)}–{_fmt_hhmm(b)} — {note}")
    return "\n".join(lines)


def answer_recent_activity_query(text: str, *, state_dir: Optional[Path] = None) -> str:
    """Deterministic reply for 'where was I / what happened' style questions."""
    if not _ACTIVITY_QUERY.search(text or ""):
        return ""
    base = Path(state_dir) if state_dir is not None else _STATE
    path = base / "architect_day_segments.jsonl"
    today = _local_date()
    rows = [r for r in _tail_rows(path, 64) if str(r.get("local_date") or "") == today]
    if not rows:
        return (
            "George — I checked `.sifta_state/architect_day_segments.jsonl` for today and "
            "found **no** recorded blocks yet. If you tell me a window plainly "
            "(e.g. “I slept from 11am to 3pm in the bedroom with YouTube on”), "
            "I will stamp it as a receipt so this never goes missing again."
        )
    bits: List[str] = []
    for r in rows[-6:]:
        try:
            a = int(r.get("start_minute_of_day", 0))
            b = int(r.get("end_minute_of_day", 0))
        except Exception:
            continue
        lab = str(r.get("label") or "block")
        loc = str(r.get("location") or "").strip()
        media = str(r.get("media_context") or "").strip()
        note = str(r.get("context_note") or "")[:160]
        loc_s = f" ({loc})" if loc else ""
        media_s = f", media={media}" if media else ""
        bits.append(f"{lab}{loc_s}{media_s} {_fmt_hhmm(a)}–{_fmt_hhmm(b)}: {note}")
    joined = " | ".join(bits)
    return (
        "George — from **today’s** architect day-segment ledger: "
        f"{joined} "
        "That is what is stamped on-node; I am not guessing your GPS."
    )


__all__ = [
    "LEDGER",
    "TRUTH_LABEL",
    "answer_recent_activity_query",
    "format_segments_for_prompt",
    "try_ingest_architect_day_segment",
]
