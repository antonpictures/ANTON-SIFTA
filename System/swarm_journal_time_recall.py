#!/usr/bin/env python3
"""Deterministic journal recall for explicit local date/time questions.

Alice already has recent day-segment recall. This organ handles older,
explicit questions such as "what was I doing at 05-11-26_14:24?" by reading
the local journal/activity ledgers before the cortex can guess.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from System.jsonl_file_lock import append_line_locked, read_text_locked

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
RECALL_RECEIPTS_NAME = "journal_time_recall_receipts.jsonl"
TRUTH_LABEL = "JOURNAL_TIME_RECALL_V1"

DEFAULT_WINDOW_MINUTES = 90
MAX_MATCHES = 5

_RECALL_RE = re.compile(
    r"\b("
    r"what\s+was\s+i\s+doing|what\s+were\s+we\s+doing|where\s+was\s+i|"
    r"what\s+happened|remember|recall|journal|life\s+diary|my\s+day"
    r")\b",
    re.IGNORECASE,
)

_MDY_TIME_RE = re.compile(
    r"\b(?P<mo>\d{1,2})[-/](?P<day>\d{1,2})[-/](?P<year>\d{2,4})"
    r"(?:[_T\s]+|\s+at\s+|\s+around\s+)"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>am|pm)?\b",
    re.IGNORECASE,
)
_YMD_TIME_RE = re.compile(
    r"\b(?P<year>\d{4})[-/](?P<mo>\d{1,2})[-/](?P<day>\d{1,2})"
    r"(?:[_T\s]+|\s+at\s+|\s+around\s+)"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>am|pm)?\b",
    re.IGNORECASE,
)
_MONTH_TIME_RE = re.compile(
    r"\b(?P<month>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
    r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?)\s+"
    r"(?P<day>\d{1,2})(?:,\s*|\s+)(?P<year>\d{2,4})"
    r".{0,16}?\b(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>am|pm)?\b",
    re.IGNORECASE,
)
_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class TargetTime:
    dt: datetime
    label: str
    local_date: str
    ts: float


@dataclass(frozen=True)
class RecallMatch:
    source: str
    label: str
    text: str
    distance_s: float
    receipt: str
    covers_target: bool = False


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _normal_year(value: str) -> int:
    year = int(value)
    if year < 100:
        return 2000 + year
    return year


def _normal_hour(hour_s: str, ampm: str | None) -> int:
    hour = int(hour_s)
    period = (ampm or "").lower()
    if period == "am" and hour == 12:
        return 0
    if period == "pm" and hour != 12:
        return hour + 12
    return hour


def _target_from_match(match: re.Match[str], *, month: int | None = None) -> TargetTime | None:
    try:
        mo = int(match.group("mo")) if month is None else int(month)
        day = int(match.group("day"))
        year = _normal_year(match.group("year"))
        hour = _normal_hour(match.group("hour"), match.groupdict().get("ampm"))
        minute = int(match.group("minute"))
        dt = datetime(year, mo, day, hour, minute)
    except Exception:
        return None
    return TargetTime(
        dt=dt,
        label=dt.strftime("%m-%d-%y_%H:%M"),
        local_date=dt.date().isoformat(),
        ts=dt.timestamp(),
    )


def parse_explicit_target_time(text: str) -> TargetTime | None:
    """Parse SIFTA's compact label or common local date/time spellings."""
    raw = text or ""
    for pattern in (_MDY_TIME_RE, _YMD_TIME_RE):
        match = pattern.search(raw)
        if match:
            return _target_from_match(match)
    month_match = _MONTH_TIME_RE.search(raw)
    if month_match:
        month_name = month_match.group("month").lower()
        return _target_from_match(month_match, month=_MONTHS.get(month_name))
    return None


def _looks_like_recall_query(text: str) -> bool:
    raw = text or ""
    return bool(_RECALL_RE.search(raw) and parse_explicit_target_time(raw))


def _stable_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]


def _append_receipt(state: Path, row: Mapping[str, Any]) -> str:
    payload = dict(row)
    payload.setdefault("ts", time.time())
    payload.setdefault("truth_label", TRUTH_LABEL)
    payload["receipt_hash"] = _stable_hash(payload)
    append_line_locked(state / RECALL_RECEIPTS_NAME, json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return str(payload["receipt_hash"])


def _read_jsonl(path: Path, *, max_lines: int = 20_000) -> list[dict[str, Any]]:
    text = read_text_locked(path)
    if not text:
        return []
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _ts_from_label(label: str) -> float | None:
    try:
        return datetime.strptime(label.strip(), "%m-%d-%y_%H:%M").timestamp()
    except Exception:
        return None


def _row_ts(row: Mapping[str, Any]) -> float | None:
    for key in ("ts", "timestamp", "start_ts", "end_ts", "source_ts"):
        try:
            value = row.get(key)
            if value not in (None, ""):
                return float(value)
        except Exception:
            continue
    label = str(row.get("local_journal_label") or "").strip()
    if label:
        return _ts_from_label(label)
    return None


def _row_interval(row: Mapping[str, Any], target_day: date) -> tuple[float, float] | None:
    start = row.get("start_ts")
    end = row.get("end_ts")
    try:
        if start not in (None, ""):
            start_f = float(start)
            end_f = float(end) if end not in (None, "") else start_f
            if end_f < start_f:
                end_f = start_f
            return start_f, end_f
    except Exception:
        pass

    if row.get("start_minute_of_day") not in (None, ""):
        try:
            start_min = int(row.get("start_minute_of_day") or 0)
            end_min = int(row.get("end_minute_of_day") or start_min)
            day = target_day
            row_date = str(row.get("local_date") or "").strip()
            if row_date:
                day = date.fromisoformat(row_date)
            start_dt = datetime.combine(day, dtime(hour=start_min // 60, minute=start_min % 60))
            if end_min <= start_min:
                end_dt = start_dt + timedelta(minutes=max(1, end_min + (24 * 60) - start_min))
            else:
                end_dt = datetime.combine(day, dtime(hour=(end_min % (24 * 60)) // 60, minute=end_min % 60))
            return start_dt.timestamp(), end_dt.timestamp()
        except Exception:
            return None
    return None


def _short(value: Any, limit: int = 280) -> str:
    return " ".join(str(value or "").split())[:limit]


def _label_for_row(row: Mapping[str, Any]) -> str:
    label = str(row.get("local_journal_label") or "").strip()
    if label:
        return label
    ts = _row_ts(row)
    if ts is not None:
        return datetime.fromtimestamp(ts).strftime("%m-%d-%y_%H:%M")
    start = str(row.get("start_time") or "").strip()
    end = str(row.get("end_time") or "").strip()
    if start and end:
        return f"{start}-{end}"
    return "undated"


def _text_for_row(row: Mapping[str, Any]) -> str:
    entry = _short(row.get("entry"), 420)
    if entry:
        return entry
    summary = _short(row.get("summary") or row.get("narrative") or row.get("context_note"), 360)
    if summary:
        return summary
    label = _short(row.get("label") or row.get("event_type") or row.get("kind"), 90)
    app = _short(row.get("frontmost_app"), 90)
    window = _short(row.get("frontmost_window"), 180)
    if label and app:
        return f"George was {label.replace('_', ' ')} in {app}: {window}".strip()
    return _short(row, 360)


def _receipt_for_row(row: Mapping[str, Any]) -> str:
    for key in ("journal_id", "receipt_hash", "receipt_id", "segment_id", "owner_activity_id", "trace_id"):
        value = str(row.get(key) or "").strip()
        if value:
            return value[:40]
    return _stable_hash(row)


def _candidate_sources(state: Path, target: TargetTime) -> Iterable[tuple[str, Path]]:
    yield f"alice_journal/{target.local_date}.jsonl", state / "alice_journal" / f"{target.local_date}.jsonl"
    yield "alice_life_journal.jsonl", state / "alice_life_journal.jsonl"
    yield "owner_activity_segments.jsonl", state / "owner_activity_segments.jsonl"
    yield "architect_day_segments.jsonl", state / "architect_day_segments.jsonl"
    yield "episodic_diary.jsonl", state / "episodic_diary.jsonl"
    yield "owner_body_events.jsonl", state / "owner_body_events.jsonl"


def _collect_matches(
    state: Path,
    target: TargetTime,
    *,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
) -> list[RecallMatch]:
    max_distance = float(window_minutes) * 60.0
    target_day = target.dt.date()
    matches: list[RecallMatch] = []
    for source, path in _candidate_sources(state, target):
        if not path.exists():
            continue
        for row in _read_jsonl(path):
            interval = _row_interval(row, target_day)
            covers = False
            distance = float("inf")
            if interval:
                start, end = interval
                if start <= target.ts <= end:
                    covers = True
                    distance = 0.0
                else:
                    distance = min(abs(target.ts - start), abs(target.ts - end))
            else:
                row_ts = _row_ts(row)
                if row_ts is None:
                    continue
                distance = abs(target.ts - row_ts)
            if distance <= max_distance:
                matches.append(
                    RecallMatch(
                        source=source,
                        label=_label_for_row(row),
                        text=_text_for_row(row),
                        distance_s=distance,
                        receipt=_receipt_for_row(row),
                        covers_target=covers,
                    )
                )
    matches.sort(key=lambda m: (0 if m.covers_target else 1, m.distance_s, m.source))
    return matches[:MAX_MATCHES]


def _owner_vocative() -> str:
    try:
        from System.swarm_kernel_identity import owner_vocative_for_talk

        return owner_vocative_for_talk()
    except Exception:
        pass
    try:
        from System.swarm_kernel_identity import owner_display_name

        return owner_display_name() or "the owner"
    except Exception:
        return "the owner"


def answer_journal_time_query(
    text: str,
    *,
    state_dir: Path | str | None = None,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
) -> str:
    """Return a grounded answer for explicit past-date/time journal questions."""
    if not _looks_like_recall_query(text or ""):
        return ""
    state = _state_dir(state_dir)
    target = parse_explicit_target_time(text or "")
    if target is None:
        return ""
    matches = _collect_matches(state, target, window_minutes=window_minutes)
    receipt = _append_receipt(
        state,
        {
            "operation": "ANSWER_JOURNAL_TIME_QUERY",
            "query": _short(text, 500),
            "target_label": target.label,
            "target_local_date": target.local_date,
            "window_minutes": int(window_minutes),
            "match_count": len(matches),
            "sources_checked": [source for source, _ in _candidate_sources(state, target)],
        },
    )
    voc = _owner_vocative()
    if not matches:
        return (
            f"{voc}, I parsed {target.label}, but I found no local journal or activity receipt "
            f"within +/-{int(window_minutes)} minutes. I should not claim memory for that time. "
            f"Receipt: journal_time_recall_receipts:{receipt}."
        )

    lines = [
        f"{voc}, yes. I checked my local journal around {target.label}. Best receipts:",
    ]
    for match in matches:
        relation = "covering that time" if match.covers_target else f"{int(round(match.distance_s / 60.0))} min away"
        lines.append(f"- {match.source} [{match.label}, {relation}]: {match.text} (receipt {match.receipt})")
    lines.append(f"Recall receipt: journal_time_recall_receipts:{receipt}.")
    return "\n".join(lines)


__all__ = ["answer_journal_time_query", "parse_explicit_target_time"]
