#!/usr/bin/env python3
"""Persistent owner day segments for Alice's 24h schedule memory.

This ledger stores observable owner-life blocks such as sleep, desk work,
kitchen movement, and SIFTA power gaps. It is deliberately receipt-shaped:
bounded text, minute-of-day intervals, local date, source hash, and no claim
that Alice knew details she did not observe.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from System.jsonl_file_lock import append_line_locked

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
SEGMENTS_LOG_NAME = "architect_day_segments.jsonl"
SEGMENTS_LOG = STATE_DIR / SEGMENTS_LOG_NAME
TRUTH_LABEL = "ARCHITECT_DAY_SEGMENT_V1"

_RANGE_RE = re.compile(
    r"\b(?:from\s+)?"
    r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|ap|a|p)?"
    r"\s*(?:-|–|to|until|through)\s*"
    r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|ap|a|p)?\b",
    re.IGNORECASE,
)

_SLEEP_RE = re.compile(r"\b(?:sleep|slept|nap|napped|napping|asleep|resting)\b", re.IGNORECASE)
_DESK_RE = re.compile(r"\b(?:desk|keyboard|coding|typing|terminal|ide|mac\s*pro|macbook)\b", re.IGNORECASE)
_KITCHEN_RE = re.compile(r"\b(?:kitchen|fridge|coffee|cook|stove|sink)\b", re.IGNORECASE)
_BEDROOM_RE = re.compile(r"\b(?:bedroom|bedrook|bed|sleeping\s+room)\b", re.IGNORECASE)


def _state_dir(state_dir: Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _normalize_period(period: str | None) -> str:
    p = (period or "").strip().lower()
    if p in {"ap", "a"}:
        return "am"
    if p == "p":
        return "pm"
    return p


def _to_minutes(hour_s: str, minute_s: str | None, period: str | None) -> int:
    hour = int(hour_s)
    minute = int(minute_s or 0)
    per = _normalize_period(period)
    if per == "am":
        if hour == 12:
            hour = 0
    elif per == "pm":
        if hour != 12:
            hour += 12
    return hour * 60 + minute


def _fmt_minute(minute: int) -> str:
    minute = int(minute) % (24 * 60)
    h24, m = divmod(minute, 60)
    suffix = "AM" if h24 < 12 else "PM"
    h12 = h24 % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


def _infer_start_period(start_hour: int, end_hour: int, end_period: str) -> str:
    if end_period == "pm" and start_hour > end_hour:
        return "am"
    if end_period == "am" and start_hour > end_hour:
        return "pm"
    return end_period


def _parse_range(text: str) -> tuple[int, int, str] | None:
    """Return (start_minute, end_minute, label) for owner schedule statements."""
    raw = text or ""
    match = _RANGE_RE.search(raw)
    if not match:
        return None
    label = "sleep" if _SLEEP_RE.search(raw) else ""
    if not label:
        return None

    sh, sm, sp, eh, em, ep = match.groups()
    sp = _normalize_period(sp)
    ep = _normalize_period(ep)
    if not sp and ep:
        sp = _infer_start_period(int(sh), int(eh), ep)
    if not ep and sp:
        ep = sp

    start = _to_minutes(sh, sm, sp)
    end = _to_minutes(eh, em, ep)
    if end <= start:
        end += 24 * 60
    return start, end, label


def _location_from_text(text: str) -> str:
    if _BEDROOM_RE.search(text):
        return "bedroom"
    if _KITCHEN_RE.search(text):
        return "kitchen"
    if _DESK_RE.search(text):
        return "desk"
    return "unknown"


def _media_context_from_text(text: str) -> str:
    low = (text or "").lower()
    has_youtube = "youtube" in low or "yt" in low
    has_tv = re.search(r"\b(?:tv|television|video)\b", low) is not None
    loud = "loud" in low
    if has_youtube and has_tv and loud:
        return "youtube_tv_loud"
    if has_youtube and loud:
        return "youtube_loud"
    if has_youtube:
        return "youtube"
    if has_tv and loud:
        return "tv_loud"
    if has_tv:
        return "tv"
    return ""


def _context_tags(text: str, *, label: str, location: str, media_context: str) -> list[str]:
    tags = {label}
    if location and location != "unknown":
        tags.add(location)
    if media_context:
        tags.update(x for x in media_context.split("_") if x)
    if "loud" in (text or "").lower():
        tags.add("loud")
    return sorted(tags)


def _source_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()


def _local_date(now: float | None = None) -> str:
    return datetime.fromtimestamp(float(now if now is not None else time.time())).date().isoformat()


def _build_row(
    *,
    label: str,
    start_minute: int,
    end_minute: int,
    context_note: str,
    source: str,
    state_dir: Path | None = None,
    now: float | None = None,
    location: str = "",
    media_context: str | None = None,
    local_date: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now_ts = float(now if now is not None else time.time())
    loc = location or _location_from_text(context_note)
    media = media_context if media_context is not None else _media_context_from_text(context_note)
    digest = _source_hash(f"{local_date or _local_date(now_ts)}|{start_minute}|{end_minute}|{label}|{context_note}|{source}")
    duration = max(0, int(end_minute) - int(start_minute))
    row: dict[str, Any] = {
        "ts": now_ts,
        "timestamp": now_ts,
        "truth_label": TRUTH_LABEL,
        "segment_id": digest[:16],
        "source_hash": digest[:12],
        "source": source,
        "status": "observed",
        "local_date": local_date or _local_date(now_ts),
        "start_minute_of_day": int(start_minute),
        "end_minute_of_day": int(end_minute),
        "duration_minutes": duration,
        "label": label,
        "location": loc,
        "media_context": media,
        "context_note": " ".join((context_note or "").split())[:500],
        # Legacy keys kept so older prompt readers do not crash.
        "raw_text": " ".join((context_note or "").split())[:500],
        "start_time": _fmt_minute(int(start_minute)),
        "end_time": _fmt_minute(int(end_minute)),
        "context_tags": _context_tags(context_note, label=label, location=loc, media_context=media),
    }
    if extra:
        row.update(extra)
    return row


def write_day_segment(row: dict[str, Any], *, state_dir: Path | None = None) -> dict[str, Any]:
    state = _state_dir(state_dir)
    path = state / SEGMENTS_LOG_NAME
    append_line_locked(path, json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return row


def try_ingest_architect_day_segment(
    text: str,
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    parsed = _parse_range(text or "")
    if not parsed:
        return None
    start, end, label = parsed
    row = _build_row(
        label=label,
        start_minute=start,
        end_minute=end,
        context_note=text,
        source="owner_statement",
        state_dir=state_dir,
        now=now,
    )
    return write_day_segment(row, state_dir=state_dir)


def _read_rows(path: Path, *, max_rows: int = 2048) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_bytes().splitlines()[-max(1, int(max_rows)) :]
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for raw in lines:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def get_today_segments(*, state_dir: Path | None = None, now: float | None = None) -> list[dict[str, Any]]:
    today = _local_date(now)
    rows = _read_rows(_state_dir(state_dir) / SEGMENTS_LOG_NAME)
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("local_date") == today:
            out.append(row)
            continue
        try:
            ts = float(row.get("timestamp", row.get("ts", 0.0)) or 0.0)
        except Exception:
            ts = 0.0
        if ts and _local_date(ts) == today:
            out.append(row)
    return out


def _row_time_label(row: dict[str, Any]) -> str:
    if "start_minute_of_day" in row and "end_minute_of_day" in row:
        return f"{_fmt_minute(int(row['start_minute_of_day']))}–{_fmt_minute(int(row['end_minute_of_day']))}"
    start = str(row.get("start_time") or "?")
    end = str(row.get("end_time") or "?")
    return f"{start}–{end}"


def format_segments_for_prompt(*, state_dir: Path | None = None, now: float | None = None) -> str:
    rows = get_today_segments(state_dir=state_dir, now=now)
    if not rows:
        return ""
    lines = ["DAY SEGMENTS DIARY (Observed 24h owner schedule blocks):"]
    for row in rows[-8:]:
        label = row.get("label") or "activity"
        bits = [str(label), _row_time_label(row)]
        loc = row.get("location")
        media = row.get("media_context")
        if loc:
            bits.append(f"loc={loc}")
        if media:
            bits.append(f"media={media}")
        note = str(row.get("context_note") or row.get("raw_text") or "").strip()
        if note:
            bits.append(note[:120])
        lines.append("- " + " | ".join(bits) + f" (receipt {row.get('segment_id', 'unknown')})")
    return "\n".join(lines)


def answer_recent_activity_query(text: str, *, state_dir: Path | None = None) -> str:
    if not re.search(
        r"\b(what\s+was\s+i\s+doing|where\s+was\s+i|my\s+recent\s+activity|"
        r"my\s+schedule|4\s+hours|four\s+hours|remember.*hours)\b",
        text or "",
        re.IGNORECASE,
    ):
        return ""
    prompt = format_segments_for_prompt(state_dir=state_dir)
    if not prompt:
        return ""
    return "George, looking at my local day segments ledger:\n" + prompt


class ArchitectDaySegments:
    """Compatibility facade for older callers."""

    @staticmethod
    def parse_segment(text: str) -> dict[str, Any] | None:
        parsed = _parse_range(text)
        if not parsed:
            return None
        start, end, label = parsed
        return _build_row(
            label=label,
            start_minute=start,
            end_minute=end,
            context_note=text,
            source="owner_statement",
        )

    @staticmethod
    def ingest_segment(text: str) -> dict[str, Any] | None:
        return try_ingest_architect_day_segment(text)

    @staticmethod
    def get_today_segments() -> list[dict[str, Any]]:
        return get_today_segments()

    @staticmethod
    def format_for_prompt() -> str:
        return format_segments_for_prompt()


__all__ = [
    "TRUTH_LABEL",
    "ArchitectDaySegments",
    "_parse_range",
    "answer_recent_activity_query",
    "format_segments_for_prompt",
    "get_today_segments",
    "try_ingest_architect_day_segment",
    "write_day_segment",
]


if __name__ == "__main__":
    print(format_segments_for_prompt())
