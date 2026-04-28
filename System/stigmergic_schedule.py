#!/usr/bin/env python3
"""Shared schedule memory for Alice and the Life Dashboard.

The dashboard writes `.sifta_state/stigmergic_schedule.jsonl`. This module is
the read/write nerve that lets Alice see that same ledger before answering.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_SCHEDULE = _STATE / "stigmergic_schedule.jsonl"
_SCHEDULE_RECEIPTS = _STATE / "stigmergic_schedule_receipts.jsonl"

_SCHEDULE_QUERY_RE = re.compile(
    r"\b("
    r"what\s+do\s+i\s+have|what['’]?s\s+(?:on\s+)?(?:my\s+)?(?:schedule|calendar)|"
    r"what\s+is\s+(?:on\s+)?(?:my\s+)?(?:schedule|calendar)|"
    r"do\s+i\s+have\s+anything|schedule|calendar|appointment"
    r")\b",
    re.IGNORECASE,
)

_TIME_RE = re.compile(
    r"\b(?P<hour>1[0-2]|0?[1-9])(?::(?P<minute>[0-5]\d))?\s*(?P<ampm>a\.?m\.?|p\.?m\.?)\b",
    re.IGNORECASE,
)

_SCHEDULE_CAPABILITY_RE = re.compile(
    r"\b("
    r"do\s+you\s+have\s+(?:a\s+)?(?:schedule|calendar)(?:\s+(?:document|app|application|ledger))?|"
    r"can\s+you\s+(?:keep|manage|write|remember|track)\s+(?:my\s+)?(?:schedule|calendar|appointments?|tasks?)|"
    r"(?:where|how)\s+can\s+(?:you|alice)\s+(?:write|keep|store)\s+(?:my\s+)?(?:schedule|calendar|appointments?)"
    r")\b",
    re.IGNORECASE,
)

_SCHEDULE_WRITE_RE = re.compile(
    r"\b("
    r"remind\s+me\s+to|"
    r"add\s+.+?\s+to\s+(?:my\s+)?(?:schedule|calendar|tasks?|todo)|"
    r"add\s+(?:to\s+)?(?:my\s+)?(?:schedule|calendar|tasks?|todo)|"
    r"put\s+(?:this\s+)?(?:on|in)\s+(?:my\s+)?(?:schedule|calendar|tasks?|todo)|"
    r"write\s+(?:this\s+)?(?:on|in)\s+(?:my\s+)?(?:schedule|calendar|tasks?|todo)|"
    r"save\s+(?:this\s+)?(?:on|in)\s+(?:my\s+)?(?:schedule|calendar|tasks?|todo)|"
    r"schedule\s+(?:me\s+)?|"
    r"i\s+have\s+(?:an?\s+)?(?:appointment|meeting|call|class|lesson|task)|"
    r"i\s+need\s+to\s+(?:remember|do|go|call|meet|take|buy)"
    r")\b",
    re.IGNORECASE,
)

_DATE_WORD_RE = re.compile(
    r"\b(today|tonight|tomorrow|morning|afternoon|evening|night|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)

_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _read_rows(path: Path = _SCHEDULE) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in path.read_text("utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    return rows


def _append_row(row: Dict[str, Any], path: Path = _SCHEDULE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        from System.jsonl_file_lock import append_line_locked

        append_line_locked(path, line)
    except Exception:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _stable_id(row: Dict[str, Any]) -> str:
    payload = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _write_receipt(operation: str, *, ok: bool, status: str,
                   row: Optional[Dict[str, Any]] = None,
                   truth_note: str = "") -> Dict[str, Any]:
    receipt: Dict[str, Any] = {
        "ts": time.time(),
        "operation": operation,
        "ok": bool(ok),
        "status": status,
        "truth_note": truth_note or "schedule effector receipt written by System.stigmergic_schedule",
    }
    if row:
        receipt["schedule_id"] = row.get("schedule_id")
        receipt["text"] = row.get("text")
        receipt["due"] = row.get("due")
        receipt["due_ts"] = row.get("due_ts")
        receipt["source"] = row.get("source")
    receipt["receipt_hash"] = _stable_id(receipt)
    _append_row(receipt, _SCHEDULE_RECEIPTS)
    return receipt


def _strip_schedule_prefix(text: str) -> str:
    cleaned = re.sub(r"^\[WhatsApp [^\]]+\]:\s*", "", text or "", flags=re.IGNORECASE).strip()
    cleaned = re.sub(
        r"^(?:alice[, ]+)?(?:please\s+)?(?:can\s+you\s+)?"
        r"(?:remind\s+me\s+to|add\s+(?:this\s+)?(?:to\s+)?(?:my\s+)?(?:schedule|calendar|tasks?|todo)|"
        r"put\s+(?:this\s+)?(?:on|in)\s+(?:my\s+)?(?:schedule|calendar|tasks?|todo)|"
        r"write\s+(?:this\s+)?(?:on|in)\s+(?:my\s+)?(?:schedule|calendar|tasks?|todo)|"
        r"save\s+(?:this\s+)?(?:on|in)\s+(?:my\s+)?(?:schedule|calendar|tasks?|todo)|"
        r"schedule\s+(?:me\s+)?(?:to\s+)?)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(r"^(?:that\s+)?i\s+need\s+to\s+", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^(?:that\s+)?i\s+have\s+", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned.strip(" .,:;")[:280]


def _next_weekday(base: datetime, weekday: int) -> datetime:
    days = (weekday - base.weekday()) % 7
    if days == 0:
        days = 7
    return base + timedelta(days=days)


def _parse_due(text: str) -> tuple[Optional[float], str]:
    """Parse banal owner phrases: today/tomorrow/weekdays + optional time."""
    text = text or ""
    lowered = text.casefold()
    base = datetime.now()
    due_day: Optional[datetime] = None
    date_label = ""

    if "tomorrow" in lowered:
        due_day = base + timedelta(days=1)
        date_label = "tomorrow"
    elif "today" in lowered or "tonight" in lowered:
        due_day = base
        date_label = "today" if "today" in lowered else "tonight"
    else:
        for name, idx in _WEEKDAY_INDEX.items():
            if re.search(rf"\b{name}\b", lowered):
                due_day = _next_weekday(base, idx)
                date_label = name.capitalize()
                break

    qtime = _query_time(text)
    if due_day is None and qtime is None:
        return (None, "")

    if due_day is None:
        due_day = base
        date_label = "today"

    hour, minute = qtime if qtime is not None else (9, 0)
    due = due_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if due.timestamp() < time.time() and date_label in ("today", ""):
        due = due + timedelta(days=1)
        date_label = "tomorrow"

    time_label = due.strftime("%-I:%M%p").lower()
    if time_label.endswith(":00am") or time_label.endswith(":00pm"):
        time_label = time_label.replace(":00", "")
    label = f"{date_label} at {time_label}".strip()
    return (due.timestamp(), label)


def _remove_due_words(text: str) -> str:
    cleaned = re.sub(
        r"\b(?:today|tonight|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"(?:\s+(?:morning|afternoon|evening|night))?"
        r"(?:\s+at)?\s*\d{0,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = _TIME_RE.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" .,:;")


def parse_schedule_write(text: str) -> tuple[str, Optional[float], str]:
    """Return (item, due_ts, due_label) for direct schedule write requests."""
    if not text or not _SCHEDULE_WRITE_RE.search(text):
        return ("", None, "")
    embedded_add = re.search(
        r"\badd\s+(?P<item>.+?)\s+to\s+(?:my\s+)?(?:schedule|calendar|tasks?|todo)\b",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    stripped = embedded_add.group("item").strip() if embedded_add else _strip_schedule_prefix(text)
    due_ts, due_label = _parse_due(stripped or text)
    item = _remove_due_words(stripped)
    # Avoid turning meta-questions into tasks.
    if not item or re.search(r"\b(schedule\s+(?:document|app|application|ledger)|how\s+can\s+you)\b", item, re.I):
        return ("", None, "")
    return (item[:240], due_ts, due_label)


def _format_due(row: Dict[str, Any]) -> str:
    due_ts = row.get("due_ts")
    if due_ts:
        try:
            return datetime.fromtimestamp(float(due_ts)).strftime("%a %b %d %H:%M")
        except Exception:
            pass
    due_text = str(row.get("due") or row.get("when") or "").strip()
    return due_text


def _dedupe_pending(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for row in reversed(list(rows)):
        if row.get("done"):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        key = f"{text.casefold()}|{row.get('due_ts') or row.get('due') or ''}"
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return list(reversed(out))


def pending_tasks(limit: int = 8, path: Path = _SCHEDULE) -> List[Dict[str, Any]]:
    rows = _dedupe_pending(_read_rows(path))

    def sort_key(row: Dict[str, Any]) -> tuple[float, int, float]:
        due = row.get("due_ts")
        try:
            due_score = float(due)
        except Exception:
            due_score = float("inf")
        priority = int(row.get("priority", 0) or 0)
        created = float(row.get("created", row.get("ts", 0.0)) or 0.0)
        return (due_score, -priority, created)

    return sorted(rows, key=sort_key)[:limit]


def _query_time(text: str) -> Optional[tuple[int, int]]:
    match = _TIME_RE.search(text or "")
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    ampm = (match.group("ampm") or "").casefold().replace(".", "")
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    return (hour, minute)


def _row_matches_time(row: Dict[str, Any], query_time: Optional[tuple[int, int]]) -> bool:
    if query_time is None:
        return True
    due_ts = row.get("due_ts")
    if due_ts:
        try:
            due = datetime.fromtimestamp(float(due_ts))
            return (due.hour, due.minute) == query_time
        except Exception:
            pass
    due_text = str(row.get("due") or row.get("when") or "")
    due_match = _query_time(due_text)
    return due_match == query_time


def _looks_like_schedule_query(text: str) -> bool:
    text = text or ""
    if _SCHEDULE_CAPABILITY_RE.search(text):
        return True
    if not _SCHEDULE_QUERY_RE.search(text):
        return False
    # Speech-to-text confused "tomorrow" as "to model" / "model" in a
    # real schedule query. If the utterance has the schedule question shape
    # plus a time, treat it as a local schedule lookup, not a tool action.
    return bool(
        _query_time(text)
        or _DATE_WORD_RE.search(text)
        or re.search(r"\b(schedule|calendar|appointments?|tasks?|todo|agenda)\b", text, re.I)
    )


def add_task(
    text: str,
    *,
    due_ts: Optional[float] = None,
    due: str = "",
    priority: int = 1,
    repeat: str = "",
    source: str = "System.stigmergic_schedule",
    path: Path = _SCHEDULE,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "text": text.strip(),
        "priority": int(priority),
        "created": time.time(),
        "done": False,
        "source": source,
    }
    if due_ts is not None:
        row["due_ts"] = float(due_ts)
    if due:
        row["due"] = due
    if repeat:
        row["repeat"] = repeat
    row["schedule_id"] = _stable_id(row)
    _append_row(row, path)
    # Tool Truth: schedule writes are effector actions. Every successful write
    # gets an append-only receipt so Alice can truthfully claim it happened.
    if path == _SCHEDULE:
        _write_receipt(
            "ADD_SCHEDULE_ITEM",
            ok=True,
            status="WRITTEN",
            row=row,
            truth_note="Alice wrote a schedule item to .sifta_state/stigmergic_schedule.jsonl",
        )
    return row


def add_from_alice_text(
    text: str,
    *,
    priority: int = 1,
    source: str = "alice_schedule_protocol",
    path: Path = _SCHEDULE,
) -> tuple[str, Optional[Dict[str, Any]]]:
    """Deterministically write a schedule item from a live Alice utterance.

    Returns (reply, row). Empty reply means this was not a schedule write.
    """
    item, due_ts, due_label = parse_schedule_write(text)
    if not item:
        return ("", None)
    row = add_task(
        item,
        due_ts=due_ts,
        due=due_label,
        priority=priority,
        source=source,
        path=path,
    )
    due_part = f" for {due_label}" if due_label else ""
    return (f"Added to my schedule: {item}{due_part}.", row)


def find_pending_task(
    terms: Iterable[str],
    *,
    path: Path = _SCHEDULE,
) -> Optional[Dict[str, Any]]:
    needles = [term.casefold() for term in terms if str(term).strip()]
    for row in pending_tasks(limit=32, path=path):
        haystack = str(row.get("text") or "").casefold()
        if not needles or any(term in haystack for term in needles):
            return row
    return None


def reschedule_first_matching(
    terms: Iterable[str],
    *,
    due_ts: float,
    due: str,
    source: str = "System.stigmergic_schedule",
    path: Path = _SCHEDULE,
) -> Dict[str, Any]:
    """Mark the first matching pending task as rescheduled and append replacement."""
    rows = _read_rows(path)
    match = find_pending_task(terms, path=path)
    if not match:
        raise ValueError("No matching pending schedule entry.")

    match_text = str(match.get("text") or "").strip()
    match_created = match.get("created")
    now = time.time()
    rewritten: List[str] = []
    marked = False
    for row in rows:
        if (
            not marked
            and not row.get("done")
            and str(row.get("text") or "").strip() == match_text
            and row.get("created") == match_created
        ):
            row = dict(row)
            row["done"] = True
            row["done_ts"] = now
            row["rescheduled"] = True
            row["rescheduled_to_due_ts"] = float(due_ts)
            row["rescheduled_to_due"] = due
            marked = True
        rewritten.append(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rewritten) + ("\n" if rewritten else ""), encoding="utf-8")
    return add_task(
        match_text,
        due_ts=due_ts,
        due=due,
        priority=int(match.get("priority", 1) or 1),
        repeat=str(match.get("repeat") or ""),
        source=source,
        path=path,
    )


def summary_for_alice(limit: int = 6, path: Path = _SCHEDULE) -> str:
    tasks = pending_tasks(limit=limit, path=path)
    if not tasks:
        return "STIGMERGIC SCHEDULE:\n- no pending schedule entries visible in .sifta_state/stigmergic_schedule.jsonl"
    lines = [
        "STIGMERGIC SCHEDULE:",
        "- source=.sifta_state/stigmergic_schedule.jsonl; this is Alice's schedule memory, not a guess.",
    ]
    for row in tasks:
        text = str(row.get("text") or "").strip()
        due = _format_due(row)
        repeat = str(row.get("repeat") or "").strip()
        priority = int(row.get("priority", 0) or 0)
        bits = [f"pending: {text}"]
        if due:
            bits.append(f"due={due}")
        if repeat:
            bits.append(f"repeat={repeat}")
        bits.append(f"priority={priority}")
        lines.append("- " + "; ".join(bits))
    return "\n".join(lines)


def answer_query_for_alice(text: str, *, limit: int = 4, path: Path = _SCHEDULE) -> str:
    """Answer a direct schedule question from the shared schedule ledger.

    This is deliberately deterministic and runs before LLM/tool routing. A
    local schedule question must never become a WhatsApp send just because the
    model improvised an outbound action.
    """
    if _SCHEDULE_CAPABILITY_RE.search(text or ""):
        count = len(pending_tasks(limit=64, path=path))
        item_word = "item" if count == 1 else "items"
        return (
            "Yes. I have a local SIFTA schedule ledger at "
            ".sifta_state/stigmergic_schedule.jsonl. "
            f"I can write to it with receipts and I currently see {count} pending {item_word}. "
            "Tell me something simple like: 'remind me to call Jeff tomorrow at 10am' "
            "or 'add buy groceries to my schedule'."
        )
    if parse_schedule_write(text)[0]:
        return ""
    if not _looks_like_schedule_query(text):
        return ""

    query_time = _query_time(text)
    tasks = [row for row in pending_tasks(limit=16, path=path) if _row_matches_time(row, query_time)]
    if not tasks:
        if query_time is not None:
            hour, minute = query_time
            return (
                f"George, I checked the schedule ledger. I do not see a pending "
                f"entry at {hour:02d}:{minute:02d}."
            )
        return "George, I checked the schedule ledger. I do not see a pending schedule entry."

    visible = tasks[:limit]
    bits: List[str] = []
    for row in visible:
        item = str(row.get("text") or "").strip()
        if not item:
            continue
        repeat = str(row.get("repeat") or "").strip()
        if repeat:
            bits.append(f"{item} ({repeat})")
        else:
            bits.append(item)
    if not bits:
        return "George, I checked the schedule ledger. I do not see a readable schedule entry."

    if query_time is not None:
        hour, minute = query_time
        label = datetime(2000, 1, 1, hour, minute).strftime("%-I:%M%p").lower()
        return f"George, at {label} you have: " + "; ".join(bits) + "."
    return "George, your schedule says: " + "; ".join(bits) + "."


if __name__ == "__main__":
    print(summary_for_alice())
