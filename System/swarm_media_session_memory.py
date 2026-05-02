#!/usr/bin/env python3
"""Time-bounded media session memory for Alice co-watch recall.

This organ answers a narrow question: "What was playing while George was
sleeping/napping?"  It does not know YouTube by hardcoded links. It reconstructs
the likely session from timestamped ledgers:

* youtube_context.jsonl
* youtube_watch_memory.jsonl
* media_ingress_gate.jsonl

The output is explicitly probabilistic when receipts are sparse. That lets
Alice say "the receipts show these videos were likely in the room during that
window" instead of pretending a single latest video was the whole session.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
YOUTUBE_CONTEXT_LEDGER = STATE_DIR / "youtube_context.jsonl"
YOUTUBE_WATCH_LEDGER = STATE_DIR / "youtube_watch_memory.jsonl"
MEDIA_INGRESS_LEDGER = STATE_DIR / "media_ingress_gate.jsonl"
MEDIA_SESSION_LEDGER = STATE_DIR / "media_session_memory.jsonl"

TRUTH_LABEL = "MEDIA_SESSION_MEMORY_V1"
_NAP_RE = re.compile(r"\b(?:nap|napping|sleep|sleeping|asleep|while i was out|while i was away)\b", re.I)
_CLOCK_RE = re.compile(
    r"\b(?:(now\s+is|it's|it is)\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
    re.I,
)
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]{3,}")
_STOP = {
    "about",
    "actually",
    "alice",
    "ambient",
    "because",
    "context",
    "direct",
    "george",
    "media",
    "observed",
    "reason",
    "speaking",
    "transcript",
    "youtube",
}


def _tail_jsonl(path: Path, n: int = 512) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_bytes().splitlines()[-max(1, int(n)) :]
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


def _today_clock_ts(hour: int, minute: int, ampm: str, *, now: float) -> float:
    hour = int(hour)
    minute = int(minute)
    ap = ampm.lower()
    if ap == "pm" and hour != 12:
        hour += 12
    if ap == "am" and hour == 12:
        hour = 0
    base = time.localtime(now)
    return time.mktime(
        (
            base.tm_year,
            base.tm_mon,
            base.tm_mday,
            hour,
            minute,
            0,
            base.tm_wday,
            base.tm_yday,
            base.tm_isdst,
        )
    )


def infer_media_session_window(text: str, *, now: float | None = None) -> dict[str, Any]:
    """Infer a nap/co-watch time window from a user turn.

    Examples:
      "now is 3:17pm, I took a nap at 11am" -> 11:00 to 15:17 today.
      "while I was sleeping" -> last six hours, low specificity.
    """

    now_ts = float(now if now is not None else time.time())
    raw = str(text or "")
    if not raw.strip():
        return {"matched": False, "reason": "empty_text"}

    matches = []
    for m in _CLOCK_RE.finditer(raw):
        hour = int(m.group(2))
        minute = int(m.group(3) or 0)
        if not (1 <= hour <= 12 and 0 <= minute <= 59):
            continue
        ts = _today_clock_ts(hour, minute, m.group(4), now=now_ts)
        prefix = (m.group(1) or "").lower()
        role = "end" if "now" in prefix or "it" in prefix else "time"
        matches.append({"ts": ts, "role": role, "text": m.group(0)})

    has_nap = bool(_NAP_RE.search(raw))
    if not matches and not has_nap:
        return {"matched": False, "reason": "no_nap_or_clock_signal"}

    explicit_end = next((m["ts"] for m in reversed(matches) if m["role"] == "end"), None)
    end_ts = float(explicit_end if explicit_end is not None else now_ts)
    starts = [m["ts"] for m in matches if m["role"] != "end" and m["ts"] <= end_ts + 900]

    if starts:
        start_ts = min(starts)
        specificity = "explicit_clock_window"
    elif matches:
        start_ts = min(m["ts"] for m in matches)
        end_ts = max(end_ts, max(m["ts"] for m in matches))
        specificity = "clock_only_window"
    else:
        start_ts = now_ts - 6 * 3600.0
        specificity = "nap_default_6h"

    if start_ts > end_ts:
        start_ts -= 24 * 3600.0
    if end_ts - start_ts < 60:
        end_ts = start_ts + 60

    return {
        "matched": True,
        "start_ts": float(start_ts),
        "end_ts": float(end_ts),
        "duration_s": float(end_ts - start_ts),
        "specificity": specificity,
        "source_text": raw[:240],
    }


def _video_key(row: Mapping[str, Any]) -> str:
    video_id = str(row.get("video_id") or row.get("youtube_video_id") or "").strip()
    if video_id:
        return "id:" + video_id
    title = " ".join(str(row.get("title") or "").split()).lower()
    return "title:" + title if title else ""


def _collect_video_rows(
    start_ts: float,
    end_ts: float,
    *,
    state_dir: Path,
    tolerance_s: float,
) -> list[dict[str, Any]]:
    sources = [
        (state_dir / "youtube_context.jsonl", "youtube_context"),
        (state_dir / "youtube_watch_memory.jsonl", "youtube_watch_memory"),
    ]
    rows: list[dict[str, Any]] = []
    for path, source in sources:
        for row in _tail_jsonl(path, 768):
            try:
                ts = float(row.get("ts", 0.0))
            except Exception:
                continue
            if ts < start_ts - tolerance_s or ts > end_ts + tolerance_s:
                continue
            key = _video_key(row)
            if not key:
                continue
            copy = dict(row)
            copy["_source"] = source
            copy["_key"] = key
            rows.append(copy)
    rows.sort(key=lambda r: float(r.get("ts", 0.0) or 0.0))
    return rows


def _merge_videos(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("_key") or "")
        if not key:
            continue
        ts = float(row.get("ts", 0.0) or 0.0)
        item = merged.setdefault(
            key,
            {
                "title": "",
                "video_id": "",
                "url": "",
                "first_ts": ts,
                "last_ts": ts,
                "receipt_count": 0,
                "statuses": [],
                "sources": [],
            },
        )
        title = " ".join(str(row.get("title") or "").split())
        video_id = str(row.get("video_id") or row.get("youtube_video_id") or "").strip()
        url = str(row.get("url") or "").strip()
        if title and (not item["title"] or len(title) > len(item["title"])):
            item["title"] = title[:180]
        if video_id:
            item["video_id"] = video_id[:64]
        if url:
            item["url"] = url[:260]
        item["first_ts"] = min(float(item["first_ts"]), ts)
        item["last_ts"] = max(float(item["last_ts"]), ts)
        item["receipt_count"] = int(item["receipt_count"]) + 1
        status = str(row.get("status") or "").strip()
        source = str(row.get("_source") or "").strip()
        if status and status not in item["statuses"]:
            item["statuses"].append(status[:60])
        if source and source not in item["sources"]:
            item["sources"].append(source)
    return sorted(merged.values(), key=lambda r: (float(r["first_ts"]), r["title"]))


def _collect_media_rows(start_ts: float, end_ts: float, *, state_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _tail_jsonl(state_dir / "media_ingress_gate.jsonl", 768):
        try:
            ts = float(row.get("ts", 0.0))
        except Exception:
            continue
        if start_ts <= ts <= end_ts:
            rows.append(row)
    return rows


def _likely_terms(rows: list[Mapping[str, Any]], limit: int = 10) -> list[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        blob = " ".join(
            str(row.get(key) or "")
            for key in ("text_preview", "focus_preview", "reason")
        )
        for token in _TOKEN_RE.findall(blob):
            low = token.lower()
            if low in _STOP:
                continue
            counts[token[:40]] += 1
    return [term for term, count in counts.most_common(limit * 2) if count >= 2][:limit]


def summarize_media_session(
    start_ts: float,
    end_ts: float,
    *,
    state_dir: Path | None = None,
    tolerance_s: float = 60 * 60.0,
) -> dict[str, Any]:
    """Summarize likely media receipts in a wall-clock session window."""

    state = Path(state_dir) if state_dir is not None else STATE_DIR
    start = float(min(start_ts, end_ts))
    end = float(max(start_ts, end_ts))
    video_rows = _collect_video_rows(start, end, state_dir=state, tolerance_s=tolerance_s)
    media_rows = _collect_media_rows(start, end, state_dir=state)
    videos = _merge_videos(video_rows)
    route_counts = Counter(str(row.get("route") or "unknown") for row in media_rows)
    terms = _likely_terms(media_rows)

    if videos and media_rows:
        confidence = 0.88
    elif videos:
        confidence = 0.72
    elif media_rows:
        confidence = 0.55
    else:
        confidence = 0.0

    return {
        "truth_label": TRUTH_LABEL,
        "start_ts": start,
        "end_ts": end,
        "duration_s": end - start,
        "confidence": confidence,
        "n_videos": len(videos),
        "videos": videos[:12],
        "media_rows": len(media_rows),
        "route_counts": dict(route_counts),
        "likely_terms": terms,
        "interpretation": (
            "Time-bounded receipt reconstruction. Videos are likely co-listened media "
            "during this interval when their YouTube/watch receipts fall in or near "
            "the requested window. The default one-hour edge tolerance covers human "
            "phrases like '11am or so' and videos that started shortly before a nap."
        ),
    }


def format_media_session_context(summary: Mapping[str, Any], *, max_videos: int = 6) -> str:
    videos = summary.get("videos") if isinstance(summary.get("videos"), list) else []
    parts: list[str] = []
    for item in videos[:max_videos]:
        if not isinstance(item, Mapping):
            continue
        title = str(item.get("title") or item.get("video_id") or "unknown video")
        vid = str(item.get("video_id") or "")
        count = int(item.get("receipt_count") or 0)
        suffix = f" [{vid}]" if vid else ""
        parts.append(f"{title}{suffix} receipts={count}")

    route_counts = summary.get("route_counts") if isinstance(summary.get("route_counts"), Mapping) else {}
    terms = summary.get("likely_terms") if isinstance(summary.get("likely_terms"), list) else []
    return (
        "media_session_memory "
        f"truth_label={summary.get('truth_label', TRUTH_LABEL)} "
        f"start_ts={summary.get('start_ts')} end_ts={summary.get('end_ts')} "
        f"confidence={float(summary.get('confidence', 0.0) or 0.0):.2f} "
        f"n_videos={int(summary.get('n_videos', 0) or 0)} "
        f"videos={' / '.join(parts) if parts else 'none'} "
        f"media_rows={int(summary.get('media_rows', 0) or 0)} "
        f"routes={dict(route_counts)} "
        f"likely_terms={', '.join(str(t) for t in terms[:8])}; "
        "answer nap/asleep questions from this receipt window, not from the latest video alone"
    )


def latest_media_session_context(
    user_text: str,
    *,
    now: float | None = None,
    state_dir: Path | None = None,
) -> str:
    window = infer_media_session_window(user_text, now=now)
    if not window.get("matched"):
        state = Path(state_dir) if state_dir is not None else STATE_DIR
        for row in reversed(_tail_jsonl(state / "alice_conversation.jsonl", 10)):
            payload = row.get("payload", {})
            if payload.get("role") == "user":
                recent_text = str(payload.get("text") or "")
                w = infer_media_session_window(recent_text, now=now)
                if w.get("matched"):
                    window = w
                    break
        if not window.get("matched"):
            return ""

    summary = summarize_media_session(
        float(window["start_ts"]),
        float(window["end_ts"]),
        state_dir=state_dir,
    )
    summary["window_specificity"] = window.get("specificity")
    return format_media_session_context(summary)


def write_media_session_receipt(summary: Mapping[str, Any], *, state_dir: Path | None = None) -> dict[str, Any]:
    state = Path(state_dir) if state_dir is not None else STATE_DIR
    path = state / "media_session_memory.jsonl"
    row = dict(summary)
    row["ts"] = time.time()
    row["writer"] = "swarm_media_session_memory"
    row.setdefault("truth_label", TRUTH_LABEL)
    state.mkdir(parents=True, exist_ok=True)
    append_line_locked(path, row)
    return row


__all__ = [
    "TRUTH_LABEL",
    "format_media_session_context",
    "infer_media_session_window",
    "latest_media_session_context",
    "summarize_media_session",
    "write_media_session_receipt",
]
