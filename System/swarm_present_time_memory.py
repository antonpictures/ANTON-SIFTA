#!/usr/bin/env python3
"""Present-time memory spine for Alice's cortex.

This organ gives the active turn a compact, newest-first view of browser/page,
body action, and diary receipts. It is intentionally read-only and file-backed:
it does not decide truth by prose, only by the newest rows already written by
other organs.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
TRUTH_LABEL = "PRESENT_TIME_MEMORY_V1"


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _tail_jsonl(path: Path, max_rows: int = 20) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines[-max(1, max_rows) * 3 :]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max_rows:]


def _last_jsonl(path: Path, max_rows: int = 40) -> dict[str, Any]:
    rows = _tail_jsonl(path, max_rows=max_rows)
    if not rows:
        return {}
    return max(rows, key=_row_ts)


def _row_ts(row: Mapping[str, Any]) -> float:
    for key in ("ts", "timestamp", "birth_ts", "created_at", "updated_at", "time"):
        value = row.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except Exception:
            continue
    return 0.0


def _short(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _age_label(ts: float, now: float) -> str:
    if not ts:
        return "unknown age"
    age = max(0.0, now - ts)
    if age < 90:
        return f"{int(age)}s ago"
    if age < 7200:
        return f"{int(age // 60)}m ago"
    return f"{int(age // 3600)}h ago"


def _line_from_row(label: str, row: Mapping[str, Any], now: float) -> str:
    if not row:
        return ""
    ts = _row_ts(row)
    parts = [f"- {label} ({_age_label(ts, now)}):"]
    for key in (
        "action",
        "event",
        "intent",
        "kind",
        "actor",
        "app_name",
        "title",
        "query",
        "url",
        "summary",
        "text",
        "content",
        "note",
        "reply",
    ):
        value = row.get(key)
        if value not in (None, "", [], {}):
            parts.append(f"{key}={_short(value, 120)}")
    return " ".join(parts)


def _media_summary(page_state: Mapping[str, Any]) -> str:
    media = page_state.get("media_playback")
    if not isinstance(media, Mapping) or not media:
        return ""
    status = str(media.get("status") or ("playing" if media.get("playing") else "") or "").strip()
    current = media.get("current_time")
    duration = media.get("duration")
    timing = ""
    try:
        if current is not None:
            timing = f" at {float(current):.0f}s"
            if duration is not None:
                timing += f" of {float(duration):.0f}s"
    except Exception:
        timing = ""
    return _short(f"{status}{timing}".strip(), 120)


def latest_present_state(
    *, now: Optional[float] = None, state_dir: Optional[Path | str] = None
) -> dict[str, Any]:
    """Return newest present-time receipts from the shared state directory."""
    t = float(now if now is not None else time.time())
    base = _state(state_dir)
    state: dict[str, Any] = {
        "truth_label": TRUTH_LABEL,
        "ts": t,
        "state_dir": str(base),
    }
    try:
        from System.swarm_browser_page_answer import current_browser_page

        state["browser"] = current_browser_page(now=t, state_dir=base)
    except Exception:
        state["browser"] = {}
    try:
        from System.swarm_browser_page_state import latest_page_state

        state["page_state"] = latest_page_state(now=t, max_age_s=900.0, state_dir=base)
    except Exception:
        state["page_state"] = {}

    ledgers = {
        "browser_context": "browser_context.jsonl",
        "context_shift": "browser_context_shift_alerts.jsonl",
        "app_action": "app_action_diary.jsonl",
        "browser_action": "browser_action_diary.jsonl",
        "stigmergic_browser_action": "stigmergic_browser_actions.jsonl",
        "episodic_diary": "episodic_diary.jsonl",
        "audio_ingress": "audio_ingress_log.jsonl",
    }
    for key, filename in ledgers.items():
        state[key] = _last_jsonl(base / filename)

    conv_rows = _tail_jsonl(base / "alice_conversation.jsonl", max_rows=40)
    latest_owner: dict[str, Any] = {}
    latest_alice: dict[str, Any] = {}
    for row in reversed(conv_rows):
        role = str(row.get("role") or row.get("speaker") or "").casefold()
        if not latest_owner and role in {"user", "owner", "george", "ioan"}:
            latest_owner = row
        if not latest_alice and role in {"alice", "assistant"}:
            latest_alice = row
        if latest_owner and latest_alice:
            break
    state["latest_owner_turn"] = latest_owner
    state["latest_alice_turn"] = latest_alice
    return state


def recent_trail_rows(
    *, n: int = 20, now: Optional[float] = None, state_dir: Optional[Path | str] = None
) -> list[tuple[float, str, dict[str, Any]]]:
    """Last `n` lived events merged across the action/diary ledgers, oldest→newest.

    George 2026-06-06 (the eBay catch): Alice forgot the eBay item she was on ONE
    click earlier — the present block held only the NEWEST row of each ledger, a
    1-deep present with no short-term past. His doctrine: "she needs the last ~20
    events from her diary — she is going through her life right now, so she can
    recognize the present; she needs a little bit of the past." This is that trail.
    """
    t = float(now if now is not None else time.time())
    base = _state(state_dir)
    ledgers = {
        "page": "browser_context.jsonl",
        "browser": "browser_action_diary.jsonl",
        "app": "app_action_diary.jsonl",
        "shift": "browser_context_shift_alerts.jsonl",
        "stig": "stigmergic_browser_actions.jsonl",
        "diary": "episodic_diary.jsonl",
    }
    merged: list[tuple[float, str, dict[str, Any]]] = []
    for label, filename in ledgers.items():
        for row in _tail_jsonl(base / filename, max_rows=max(4, int(n))):
            ts = _row_ts(row)
            if ts <= 0 or ts > t + 60:
                continue  # unparseable or future-stamped rows cannot order the trail
            merged.append((ts, label, dict(row)))
    merged.sort(key=lambda item: item[0])
    return merged[-max(1, int(n)):]


def recent_trail_block(
    *,
    n: int = 20,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
    max_chars: int = 2200,
) -> str:
    """One-line-per-event trail for the cortex prompt — hard bloat cap.

    Kept deliberately small (the sysprompt is already over budget, r602 lane #5):
    each line is clipped and the OLDEST lines drop first when over max_chars.
    """
    t = float(now if now is not None else time.time())
    rows = recent_trail_rows(n=n, now=t, state_dir=state_dir)
    if not rows:
        return ""
    lines = [
        f"MY RECENT TRAIL — the last {len(rows)} events I lived (oldest → newest). "
        "I recognize the present against this immediate past; when the owner says "
        "'the page/item/photo from before', it is in here:"
    ]
    prev_body = None
    for ts, label, row in rows:
        body = f"[{label}] {_compact_row_summary(row)}"
        if body == prev_body:
            continue  # r610: collapse consecutive duplicates — focus ledgers re-record
            # the same page many times (the live eBay image appeared 5×); the trail
            # is HISTORY, not a focus log (George's stigmergic-dedup doctrine).
        prev_body = body
        lines.append(_short(f"  - {_age_label(ts, t)} {body}", 170))
    while len("\n".join(lines)) > max(600, int(max_chars)) and len(lines) > 2:
        lines.pop(1)  # drop oldest first; the newest past matters most
    return "\n".join(lines)


def present_time_memory_block(
    *,
    owner_text: str = "",
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
    max_lines: int = 9,
    trail_rows: int = 20,
) -> str:
    """Compact prompt block read before the cortex writes a reply."""
    t = float(now if now is not None else time.time())
    state = latest_present_state(now=t, state_dir=state_dir)
    lines = [
        "PRESENT TIME MEMORY — READ BEFORE CORTEX:",
        f"- truth_label={TRUTH_LABEL}",
        "- Rule: newest browser/page/action/diary receipts are NOW. Use them before stale screenshots or prior visual context.",
        "- If the owner asks current link/page/activity, answer from this block or say the receipt is missing.",
    ]
    browser = state.get("browser") if isinstance(state.get("browser"), Mapping) else {}
    if browser:
        title = _short(browser.get("title") or browser.get("url"), 130)
        url = _short(browser.get("url"), 180)
        age = browser.get("age_s")
        age_text = f"{int(float(age))}s ago" if isinstance(age, (int, float)) else "unknown age"
        current = "current" if browser.get("fresh") else "may be stale"
        lines.append(
            f"- Browser now ({current}, {age_text}, {browser.get('source') or 'receipt'}): {title} — {url}"
        )
    page_state = state.get("page_state") if isinstance(state.get("page_state"), Mapping) else {}
    media = _media_summary(page_state)
    if media:
        lines.append(f"- Browser media: {media}")
    for key, label in (
        ("browser_action", "Latest browser action"),
        ("app_action", "Latest app action"),
        ("context_shift", "Latest context shift"),
        ("episodic_diary", "Latest diary"),
        ("latest_owner_turn", "Latest owner turn"),
    ):
        row = state.get(key)
        if isinstance(row, Mapping) and row:
            line = _line_from_row(label, row, t)
            if line:
                lines.append(line)
    block = "\n".join(lines[: max(4, max_lines)])
    # r609: George's eBay catch — the 1-deep present made her forget the item she
    # was on ONE click earlier. Append the short-term past (last ~20 lived events)
    # so she recognizes the present against it. Rides the existing prompt wire.
    if trail_rows > 0:
        trail = recent_trail_block(n=trail_rows, now=t, state_dir=state_dir)
        if trail:
            block = block + "\n" + trail
    return block


_PRESENT_QUERY_RE = re.compile(
    r"\b(?:what(?:'s| is| are)\s+(?:she|you|alice)\s+doing|"
    r"what\s+am\s+i\s+doing|"
    r"what\s+is\s+going\s+on\s+(?:now|right\s+now)|"
    r"do\s+you\s+know\s+what\s+(?:i|we)\s+(?:am|are)\s+doing|"
    r"present\s+time\s+awareness|"
    r"read\s+(?:your\s+)?(?:latest\s+)?(?:diary|memory|receipts))\b",
    re.IGNORECASE,
)

_LAST_DIARY_ROW_QUERY_RE = re.compile(
    r"\b(?:what(?:'s| is)|show|read|tell\s+me|give\s+me)\b.{0,100}"
    r"\blast\s+row\b.{0,100}\b(?:diary|journal)\b"
    r"|\blast\s+row\b.{0,100}\b(?:your\s+)?(?:diary|journal)\b",
    re.IGNORECASE,
)


def _compact_row_summary(row: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "date",
        "time",
        "truth_label",
        "source",
        "kind",
        "title",
        "summary",
        "line",
        "text",
        "content",
        "url",
        "bucket",
        "event_count",
    ):
        value = row.get(key)
        if value not in (None, "", [], {}):
            parts.append(f"{key}={_short(value, 180)}")
    return "; ".join(parts) if parts else _short(json.dumps(dict(row), ensure_ascii=False), 260)


def answer_last_diary_journal_row_query(
    owner_text: str,
    *,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Return the exact newest diary/journal row boundary for explicit tail asks."""
    clean = " ".join(str(owner_text or "").split())
    if not clean or not _LAST_DIARY_ROW_QUERY_RE.search(clean):
        return ""
    t = float(now if now is not None else time.time())
    base = _state(state_dir)
    candidates: list[tuple[float, str, Mapping[str, Any]]] = []
    for filename in ("alice_first_person_journal.jsonl", "episodic_diary.jsonl"):
        row = _last_jsonl(base / filename, max_rows=80)
        if row:
            candidates.append((_row_ts(row), filename, row))
    if not candidates:
        return (
            "I checked alice_first_person_journal.jsonl and episodic_diary.jsonl, "
            "but I do not have a diary/journal row to quote yet."
        )
    ts, filename, row = max(candidates, key=lambda item: item[0])
    summary = _compact_row_summary(row)
    return (
        f"Last diary/journal row I can read is .sifta_state/{filename} "
        f"({_age_label(ts, t)}): {summary}. Row ts={ts:g}."
    )


def answer_present_time_query(
    owner_text: str,
    *,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Short deterministic answer for direct present-time-awareness probes."""
    clean = " ".join(str(owner_text or "").split())
    if not clean or not _PRESENT_QUERY_RE.search(clean):
        return ""
    t = float(now if now is not None else time.time())
    state = latest_present_state(now=t, state_dir=state_dir)
    browser = state.get("browser") if isinstance(state.get("browser"), Mapping) else {}
    page_state = state.get("page_state") if isinstance(state.get("page_state"), Mapping) else {}
    bits: list[str] = []
    if browser:
        title = _short(browser.get("title") or browser.get("url"), 110)
        url = _short(browser.get("url"), 160)
        freshness = "current" if browser.get("fresh") else "possibly stale"
        bits.append(f"I am anchored on Alice Browser ({freshness} receipt): {title} — {url}.")
    media = _media_summary(page_state)
    if media:
        bits.append(f"Media receipt says {media}.")
    for key, label in (("browser_action", "latest browser action"), ("app_action", "latest app action"), ("episodic_diary", "latest diary")):
        row = state.get(key)
        if isinstance(row, Mapping) and row:
            line = _line_from_row(label, row, t)
            if line:
                bits.append(line[2:] + ".")
                break
    if bits:
        return " ".join(bits)
    return "I do not have a fresh present-time receipt yet; I need to read the page or diary before claiming what is happening now."


__all__ = [
    "TRUTH_LABEL",
    "latest_present_state",
    "present_time_memory_block",
    "recent_trail_rows",
    "recent_trail_block",
    "answer_present_time_query",
    "answer_last_diary_journal_row_query",
]
