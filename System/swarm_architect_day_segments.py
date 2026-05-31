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
from typing import Any, Optional
from urllib.parse import urlparse

from System.jsonl_file_lock import append_line_locked

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
SEGMENTS_LOG_NAME = "architect_day_segments.jsonl"
SEGMENTS_LOG = STATE_DIR / SEGMENTS_LOG_NAME
TRUTH_LABEL = "ARCHITECT_DAY_SEGMENT_V1"
ACTIVE_SEGMENT_NAME = "active_time_segment.json"
SEGMENT_TRANSITIONS_LOG_NAME = "architect_segment_transitions.jsonl"
OPEN_SEGMENT_TRUTH_LABEL = "ARCHITECT_OPEN_LIFE_SEGMENT_V1"

_RANGE_RE = re.compile(
    r"\b(?:from\s+)?"
    r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|ap|a|p)?"
    r"\s*(?:-|–|to|until|through)\s*"
    r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|ap|a|p)?\b",
    re.IGNORECASE,
)

_SLEEP_RE   = re.compile(r"\b(?:sleep|slept|nap|napped|napping|asleep|resting)\b", re.IGNORECASE)
_DESK_RE    = re.compile(r"\b(?:desk|keyboard|coding|typing|terminal|ide|mac\s*pro|macbook)\b", re.IGNORECASE)
_KITCHEN_RE = re.compile(r"\b(?:kitchen|fridge|coffee|cook|stove|sink|eating|breakfast|lunch|dinner|meal)\b", re.IGNORECASE)
_FOOD_RE    = re.compile(r"\b(?:eating|eat|eats|ate|food|meal|breakfast|lunch|dinner|snack|sandwich|hungry|coffee|donut|doughnut)\b", re.IGNORECASE)
_BEDROOM_RE = re.compile(r"\b(?:bedroom|bedrook|bed|sleeping\s+room)\b", re.IGNORECASE)
_PHONE_RE   = re.compile(r"\b(?:phone|call|speaker\s*phone|facetime|talking\s+on|spoke)\b", re.IGNORECASE)
_WALK_RE    = re.compile(r"\b(?:walk|walking|outside|gym|exercise|run|running|jog)\b", re.IGNORECASE)
_WAKE_RE    = re.compile(r"\b(?:woke|waking|woke\s+up|got\s+up|morning\s+routine|started\s+day)\b", re.IGNORECASE)
_SHOPPING_RE = re.compile(r"\b(?:shopping|shop|store|grocery|groceries|market|errand)\b", re.IGNORECASE)
_SHOPPING_START_RE = re.compile(
    r"\b(?:"
    r"(?:(?:i\s+am|i['’]m)\s+(?:gonna|going)\s+(?:to\s+)?(?:go\s+)?(?:shopping|to\s+the\s+store)|"
    r"(?:i\s+am|i['’]m)\s+(?:leaving|going)\s+(?:for|to)\s+(?:the\s+)?(?:store|market|grocery|groceries)|"
    r"i\s+(?:went|go)\s+to\s+(?:the\s+)?(?:store|market)|"
    r"george\s+(?:is\s+)?(?:going|leaving|went)\s+(?:to\s+)?(?:the\s+)?(?:store|shopping|market)|"
    r"(?:write|right)\s+down\b.{0,160}\bi\s+(?:went|go|am\s+going|['’]m\s+going)\s+(?:to\s+)?(?:the\s+)?(?:store|shopping|market)|"
    r"(?:write|right)\s+down\b.{0,160}\b(?:store|shopping|market)\b.{0,80}\b(?:right\s+now|now)\b)"
    r")",
    re.IGNORECASE | re.DOTALL,
)
_SHOPPING_END_RE = re.compile(
    r"\b(?:"
    r"i\s+(?:just\s+)?(?:came|got|arrived)\s+back\s+from\s+(?:the\s+)?(?:store|shopping|market|grocery|groceries)|"
    r"i\s+(?:just\s+)?returned\s+from\s+(?:the\s+)?(?:store|shopping|market|grocery|groceries)|"
    r"george\s+(?:just\s+)?(?:came|got|arrived)\s+back\s+from\s+(?:the\s+)?(?:store|shopping|market|grocery|groceries)|"
    r"back\s+(?:from|at)\s+(?:the\s+)?(?:store|shopping|market|grocery|groceries)"
    r")",
    re.IGNORECASE | re.DOTALL,
)
_YOUTUBE_URL_RE = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[^\s)>\"]+", re.IGNORECASE)
_NOW_PLAYING_TITLE_RE = re.compile(r"\bnow\s+playing\s*[:,-]\s*(?P<title>.+)", re.IGNORECASE | re.DOTALL)
_COWATCH_RE = re.compile(
    r"\b(?:co[- ]?watch|we\s+(?:are|['’]re)\s+watching|watching\s+this\s+video|"
    r"now\s+playing|youtube\.com/watch|youtu\.be|memory\s+together|watch\s+(?:it\s+)?with\s+me)\b",
    re.IGNORECASE,
)
_COWATCH_START_RE = re.compile(
    r"\b(?:now\s+playing|co[- ]?watch|we\s+(?:are|['’]re)\s+watching|watching\s+this\s+video|"
    r"memory\s+together|(?:write|right)\s+(?:down|it)\b.{0,160}\bwatching\s+(?:this\s+)?video|"
    r"segment\b.{0,160}\bwatching\s+(?:this\s+)?video|"
    r"schedule\b.{0,120}\bwatching\s+(?:this\s+)?video|youtube\.com/watch|youtu\.be)\b",
    re.IGNORECASE | re.DOTALL,
)


def _has_activity_signal(text: str) -> bool:
    return any([
        _SLEEP_RE.search(text),
        _DESK_RE.search(text),
        _KITCHEN_RE.search(text),
        _FOOD_RE.search(text),
        _BEDROOM_RE.search(text),
        _PHONE_RE.search(text),
        _WALK_RE.search(text),
        _WAKE_RE.search(text),
        _SHOPPING_RE.search(text),
        _COWATCH_RE.search(text),
    ])


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


def _minute_from_ts(ts: float) -> int:
    local = time.localtime(float(ts))
    return int(local.tm_hour) * 60 + int(local.tm_min)


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
        # Also catch single-time anchors: "at 7pm I was...", "woke up at 7am"
        single = re.search(
            r"\b(?:at|around|by|since)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|a|p)?\b",
            raw, re.IGNORECASE
        )
        if not single:
            return None
        sh, sm, sp = single.groups()
        start = _to_minutes(sh, sm, _normalize_period(sp))
        end = start + 60  # assume 1 hour if no range given
        # Still need an activity keyword
        if not _has_activity_signal(raw):
            return None
        label = _activity_label(raw)
        return start, end, label

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
    if not _has_activity_signal(raw):
        return None
    label = _activity_label(raw)
    if not label:
        return None
    return start, end, label


def _activity_label(text: str) -> str:
    """Detect activity type from text."""
    if _COWATCH_RE.search(text): return "co_watch"
    if _SLEEP_RE.search(text):   return "sleep"
    if _WAKE_RE.search(text):    return "wake"
    if _PHONE_RE.search(text):   return "phone_call"
    if _WALK_RE.search(text):    return "exercise"
    if _SHOPPING_RE.search(text): return "shopping"
    if _FOOD_RE.search(text):    return "meal"
    if _KITCHEN_RE.search(text): return "kitchen"
    if _DESK_RE.search(text):    return "desk_work"
    if _BEDROOM_RE.search(text): return "bedroom"
    return "activity"


def _location_from_text(text: str) -> str:
    if _BEDROOM_RE.search(text):
        return "bedroom"
    if _KITCHEN_RE.search(text):
        return "kitchen"
    if _SHOPPING_RE.search(text):
        return "store"
    if _DESK_RE.search(text):
        return "desk"
    return "unknown"


def _media_context_from_text(text: str) -> str:
    low = (text or "").lower()
    has_youtube = "youtube" in low or "yt" in low
    has_tv = re.search(r"\b(?:tv|television|video)\b", low) is not None
    loud = "loud" in low
    if _COWATCH_RE.search(text or "") and has_youtube:
        return "youtube_cowatch"
    if _COWATCH_RE.search(text or ""):
        return "co_watch"
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


def _get_gps_snapshot(state_dir: Path | None = None) -> dict:
    """Read last GPS fix from swarm_gps_sensor ledger. Silent on failure."""
    state = _state_dir(state_dir)
    try:
        gps_log = state / "gps_traces.jsonl"
        if gps_log.exists():
            lines = gps_log.read_bytes().splitlines()
            for raw in reversed(lines[-20:]):
                try:
                    row = json.loads(raw.decode("utf-8", errors="replace"))
                    lat = row.get("latitude") or row.get("lat")
                    lon = row.get("longitude") or row.get("lon")
                    if lat and lon:
                        gps_ts = float(row.get("ts", 0) or 0.0)
                        age_s = max(0.0, time.time() - gps_ts) if gps_ts else None
                        return {
                            "lat": float(lat),
                            "lon": float(lon),
                            "gps_ts": gps_ts,
                            "gps_age_s": age_s,
                            "gps_fresh": bool(age_s is not None and age_s < 7200.0),
                            "gps_accuracy": row.get("accuracy") or row.get("horizontal_accuracy"),
                            "gps_source": "gps_traces.jsonl",
                        }
                except Exception:
                    continue
        iphone = state / "iphone_gps_latest.json"
        if iphone.exists():
            d = json.loads(iphone.read_text(encoding="utf-8", errors="replace"))
            payload = d.get("payload") if isinstance(d.get("payload"), dict) else {}
            lat = payload.get("latitude") or d.get("latitude") or d.get("lat")
            lon = payload.get("longitude") or d.get("longitude") or d.get("lon")
            if lat and lon:
                gps_ts = float(d.get("ts", 0) or 0.0)
                age_s = max(0.0, time.time() - gps_ts) if gps_ts else None
                fresh = bool(age_s is not None and age_s < 7200.0)
                return {
                    "lat": float(lat) if fresh else None,
                    "lon": float(lon) if fresh else None,
                    "last_lat": float(lat),
                    "last_lon": float(lon),
                    "gps_ts": gps_ts,
                    "gps_age_s": age_s,
                    "gps_fresh": fresh,
                    "gps_accuracy": payload.get("accuracy") or d.get("accuracy"),
                    "gps_source": "iphone_gps_latest.json",
                }
        # Also try safe_location_state.json
        for fname in ["safe_location_state.json", "active_gps.json"]:
            p = state / fname
            if p.exists():
                d = json.loads(p.read_text())
                lat = d.get("lat") or d.get("latitude")
                lon = d.get("lon") or d.get("longitude")
                if lat and lon:
                    gps_ts = float(d.get("ts", 0) or 0.0)
                    age_s = max(0.0, time.time() - gps_ts) if gps_ts else None
                    return {
                        "lat": float(lat),
                        "lon": float(lon),
                        "gps_ts": gps_ts,
                        "gps_age_s": age_s,
                        "gps_fresh": bool(age_s is not None and age_s < 7200.0),
                        "gps_source": fname,
                    }
    except Exception:
        pass
    return {}


def _get_voice_identity_source(state_dir: Path | None = None) -> dict:
    """Read last audio source classification from voice_identity_ledger.jsonl."""
    state = _state_dir(state_dir)
    try:
        vi_log = state / "voice_identity_ledger.jsonl"
        if not vi_log.exists():
            return {}
        lines = vi_log.read_bytes().splitlines()
        for raw in reversed(lines[-5:]):
            try:
                row = json.loads(raw.decode("utf-8", errors="replace"))
                label = row.get("source_label")
                if label and label != "unknown":
                    return {
                        "voice_source_label": label,
                        "voice_source_display": row.get("display", label),
                        "voice_source_ts": row.get("ts", 0),
                    }
            except Exception:
                pass
    except Exception:
        pass
    return {}


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

    # ── Stigmergic sensor enrichment ──────────────────────────────────────
    gps = _get_gps_snapshot(state_dir)
    voice_id = _get_voice_identity_source(state_dir)

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
        # ── New stigmergic fields ──
        "gps_lat": gps.get("lat"),
        "gps_lon": gps.get("lon"),
        "gps_accuracy_m": gps.get("gps_accuracy"),
        "gps_ts": gps.get("gps_ts"),
        "gps_age_s": gps.get("gps_age_s"),
        "gps_fresh": gps.get("gps_fresh"),
        "gps_source": gps.get("gps_source"),
        "audio_source_label": voice_id.get("voice_source_label"),
        "audio_source_display": voice_id.get("voice_source_display"),
        "audio_source_ts": voice_id.get("voice_source_ts"),
    }
    if extra:
        row.update(extra)
    return row


def write_day_segment(row: dict[str, Any], *, state_dir: Path | None = None) -> dict[str, Any]:
    state = _state_dir(state_dir)
    path = state / SEGMENTS_LOG_NAME
    append_line_locked(path, json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return row


_TIME_IN_RE = re.compile(
    r"\b(?:time|clock|segment)\s*in\b|"
    r"\b(?:start|begin|open)\s+(?:the\s+)?(?:segment|topic|life\s+segment|timer)\b|"
    r"\b(?:write|right)\s+down\s+(?:the\s+)?(?:time|segment)\b",
    re.IGNORECASE,
)
_TIME_OUT_RE = re.compile(
    r"\b(?:time|clock|segment)\s*out\b|"
    r"\b(?:finish(?:ed|ing)?|done|close(?:d)?|stop(?:ped|ping)?|end(?:ed|ing)?)\s+"
    r"(?:the\s+)?(?:segment|topic|life\s+segment|timer|eating|meal|donut|doughnut)?\b|"
    r"\bi\s+(?:just\s+)?finished\b|"
    r"\bgeorge\s+finished\b",
    re.IGNORECASE,
)
_LIVE_ACTIVITY_START_RE = re.compile(
    r"\b(?:now|right\s+now)\b.{0,80}\b(?:eating|working|coding|watching|reading)\b|"
    r"\bi\s+(?:am|['’]m)\s+(?:starting\s+to\s+)?(?:eat|eating|work|working|code|coding|watch|watching|read|reading)\b|"
    r"\bgeorge\s+(?:is\s+)?(?:eating|working|coding|watching|reading)\b|"
    r"\bgeorge\s+eats\b",
    re.IGNORECASE,
)
_TIMEBOX_COMMAND_WORDS_RE = re.compile(
    r"\b(?:time|clock|segment)\s*(?:in|out)\b|"
    r"\b(?:start|begin|open|finish|finished|done|close|closed|stop|stopped|end|ended)\s+"
    r"(?:the\s+)?(?:segment|topic|life\s+segment|timer)?\b|"
    r"\b(?:now|right\s+now)\b|"
    r"\b(?:write|right)\s+down\s+(?:the\s+)?(?:time|segment)\b|"
    r"\b(?:that\s+i|when\s+i)\b",
    re.IGNORECASE,
)


def _active_segment_path(state_dir: Path | None = None) -> Path:
    return _state_dir(state_dir) / ACTIVE_SEGMENT_NAME


def _segment_transition_path(state_dir: Path | None = None) -> Path:
    return _state_dir(state_dir) / SEGMENT_TRANSITIONS_LOG_NAME


def _clean_topic(text: str) -> str:
    cleaned = _TIMEBOX_COMMAND_WORDS_RE.sub(" ", text or "")
    cleaned = re.sub(r"\b(?:i\s+(?:am|['’]m)|george\s+(?:is\s+)?)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :;,.!-")
    return (cleaned or (text or "activity")).strip()[:180]


def _extract_cowatch_topic(text: str, *, state_dir: Path | None = None) -> dict[str, str]:
    """Extract title/URL for a co-watch life segment without calling an LLM."""
    raw = " ".join((text or "").split())
    url_match = _YOUTUBE_URL_RE.search(raw)
    url = url_match.group(0).rstrip(".,") if url_match else ""
    title = ""
    now_playing = _NOW_PLAYING_TITLE_RE.search(raw)
    if now_playing:
        title = now_playing.group("title").strip()
        if url:
            title = title.replace(url, " ").strip()
    elif url_match:
        before = raw[: url_match.start()].strip(" :;-")
        after = raw[url_match.end():].strip(" :;-")
        title = before or after
    if not title:
        active = read_open_life_segment(state_dir=state_dir)
        if active and active.get("label") == "co_watch":
            title = str(active.get("cowatch_title") or active.get("topic") or "").strip()
            url = url or str(active.get("cowatch_url") or "").strip()
    if not title:
        title = "current video"
    title = re.sub(r"\bthis\s+is\s+georgem?\b.*$", "", title, flags=re.IGNORECASE).strip(" :;-")
    title = re.sub(r"\s+", " ", title).strip()
    return {"title": title[:180] or "current video", "url": url[:300]}


def _write_segment_transition(row: dict[str, Any], *, state_dir: Path | None = None) -> dict[str, Any]:
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    append_line_locked(
        state / SEGMENT_TRANSITIONS_LOG_NAME,
        json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return row


def read_open_life_segment(*, state_dir: Path | None = None) -> dict[str, Any] | None:
    path = _active_segment_path(state_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def start_open_life_segment(
    text: str,
    *,
    state_dir: Path | None = None,
    now: float | None = None,
    source: str = "owner_time_in",
    label_override: str | None = None,
    media_context: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Open a receipt-backed owner life/topic segment without guessing its end."""
    now_ts = float(now if now is not None else time.time())
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    old = read_open_life_segment(state_dir=state)
    if old:
        close_open_life_segment(
            "auto-close before new time in",
            state_dir=state,
            now=now_ts,
            source="owner_timebox_auto_close_new_start",
        )

    topic = _clean_topic(text)
    label = label_override or _activity_label(topic)
    loc = _location_from_text(topic)
    media = media_context if media_context is not None else _media_context_from_text(topic)
    gps = _get_gps_snapshot(state)
    voice_id = _get_voice_identity_source(state)
    digest = _source_hash(f"{now_ts}|{source}|{topic}|{label}")[:16]
    row: dict[str, Any] = {
        "ts": now_ts,
        "timestamp": now_ts,
        "truth_label": OPEN_SEGMENT_TRUTH_LABEL,
        "status": "open",
        "open_segment_id": digest,
        "source": source,
        "local_date": _local_date(now_ts),
        "start_ts": now_ts,
        "start_minute_of_day": _minute_from_ts(now_ts),
        "start_time": _fmt_minute(_minute_from_ts(now_ts)),
        "label": label,
        "location": loc,
        "media_context": media,
        "topic": topic,
        "context_note": " ".join((text or "").split())[:500],
        "raw_text": " ".join((text or "").split())[:500],
        "gps_lat": gps.get("lat"),
        "gps_lon": gps.get("lon"),
        "gps_accuracy_m": gps.get("gps_accuracy"),
        "gps_ts": gps.get("gps_ts"),
        "gps_age_s": gps.get("gps_age_s"),
        "gps_fresh": gps.get("gps_fresh"),
        "gps_source": gps.get("gps_source"),
        "audio_source_label": voice_id.get("voice_source_label"),
        "audio_source_display": voice_id.get("voice_source_display"),
        "audio_source_ts": voice_id.get("voice_source_ts"),
    }
    if extra:
        row.update(extra)
    (state / ACTIVE_SEGMENT_NAME).write_text(json.dumps(row, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    _write_segment_transition({"event": "time_in", **row}, state_dir=state)
    return row


def close_open_life_segment(
    text: str = "",
    *,
    state_dir: Path | None = None,
    now: float | None = None,
    source: str = "owner_time_out",
) -> dict[str, Any] | None:
    """Close the current owner life/topic segment and write a day-segment row."""
    now_ts = float(now if now is not None else time.time())
    state = _state_dir(state_dir)
    active_path = state / ACTIVE_SEGMENT_NAME
    active = read_open_life_segment(state_dir=state)
    if not active:
        return None

    try:
        start_ts = float(active.get("start_ts", now_ts) or now_ts)
    except Exception:
        start_ts = now_ts
    start_min = _minute_from_ts(start_ts)
    explicit_time = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm|a|p)?\b", text, re.IGNORECASE)
    if explicit_time:
        h, m, p = explicit_time.groups()
        end_min = _to_minutes(h, m, p)
    else:
        end_min = _minute_from_ts(now_ts)
    if end_min <= start_min:
        end_min += 24 * 60
    if end_min == start_min:
        end_min += 1
    topic = str(active.get("topic") or _clean_topic(text) or "activity")
    label = str(active.get("label") or _activity_label(topic) or "activity")
    close_note = " ".join((text or "").split())[:240]
    context_note = f"Time In: {topic}"
    if close_note:
        context_note += f" / Time Out: {close_note}"

    row = _build_row(
        label=label,
        start_minute=start_min,
        end_minute=end_min,
        context_note=context_note,
        source=source,
        state_dir=state,
        now=now_ts,
        location=str(active.get("location") or ""),
        media_context=str(active.get("media_context") or "") or None,
        extra={
            "timebox_truth_label": OPEN_SEGMENT_TRUTH_LABEL,
            "timebox_status": "closed",
            "timebox_topic": topic,
            "timebox_open_segment_id": active.get("open_segment_id"),
            "timebox_start_ts": start_ts,
            "timebox_end_ts": now_ts,
            "timebox_duration_s": max(0.0, now_ts - start_ts),
            "start_precision": active.get("start_precision") or "owner_time_in",
            "end_precision": source if source != "owner_time_out" else "owner_time_out",
            **{
                key: active[key]
                for key in ("cowatch_title", "cowatch_url", "cowatch_truth_label", "shopping_truth_label")
                if key in active
            },
        },
    )
    write_day_segment(row, state_dir=state)
    try:
        active_path.unlink()
    except OSError:
        pass
    _write_segment_transition({"event": "time_out", **row}, state_dir=state)
    return row


def _write_unpaired_timebox_marker(
    text: str,
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    if not _has_activity_signal(text or ""):
        return None
    now_ts = float(now if now is not None else time.time())
    end_min = _minute_from_ts(now_ts)
    start_min = max(0, end_min - 1)
    topic = _clean_topic(text)
    row = _build_row(
        label=_activity_label(topic),
        start_minute=start_min,
        end_minute=end_min,
        context_note=f"Unpaired finish marker: {text}",
        source="owner_time_out_without_open",
        state_dir=state_dir,
        now=now_ts,
        extra={
            "timebox_truth_label": OPEN_SEGMENT_TRUTH_LABEL,
            "timebox_status": "closed_without_open_start",
            "timebox_topic": topic,
            "start_precision": "unknown_fallback_1min",
            "end_precision": "owner_time_out",
        },
    )
    return write_day_segment(row, state_dir=state_dir)


def try_ingest_architect_timebox_command(
    text: str,
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    """Ingest live owner time-in/time-out commands as open/closed receipts."""
    raw = text or ""
    if _TIME_OUT_RE.search(raw):
        return close_open_life_segment(raw, state_dir=state_dir, now=now) or _write_unpaired_timebox_marker(
            raw,
            state_dir=state_dir,
            now=now,
        )
    if _TIME_IN_RE.search(raw) or _LIVE_ACTIVITY_START_RE.search(raw):
        return start_open_life_segment(raw, state_dir=state_dir, now=now)
    return None


def try_ingest_architect_cowatch_segment(
    text: str,
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    """Open/update a co-watch life segment from now-playing, URL, or schedule language."""
    raw = text or ""
    if not _COWATCH_START_RE.search(raw):
        return None
    state = _state_dir(state_dir)
    cowatch = _extract_cowatch_topic(raw, state_dir=state)
    topic = f"co-watch: {cowatch['title']}"
    if cowatch["url"]:
        topic = f"{topic} {cowatch['url']}"
    active = read_open_life_segment(state_dir=state)
    if (
        active
        and active.get("label") == "co_watch"
        and str(active.get("topic") or "").strip() == topic
    ):
        return active
    return start_open_life_segment(
        topic,
        state_dir=state,
        now=now,
        source="owner_cowatch_time_in",
        label_override="co_watch",
        media_context="youtube_cowatch" if cowatch["url"] or "youtube" in raw.lower() else "co_watch",
        extra={
            "cowatch_truth_label": "ARCHITECT_COWATCH_SEGMENT_V1",
            "cowatch_title": cowatch["title"],
            "cowatch_url": cowatch["url"],
            "start_precision": "owner_cowatch_time_in",
        },
    )


def _write_unpaired_shopping_return_marker(
    text: str,
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    now_ts = float(now if now is not None else time.time())
    explicit_time = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm|a|p)?\b", text, re.IGNORECASE)
    if explicit_time:
        h, m, p = explicit_time.groups()
        end_min = _to_minutes(h, m, p)
    else:
        end_min = _minute_from_ts(now_ts)
    start_min = max(0, end_min - 1)
    row = _build_row(
        label="shopping",
        start_minute=start_min,
        end_minute=end_min,
        context_note=f"Unpaired store return marker: {text}",
        source="owner_store_return_without_open",
        state_dir=state_dir,
        now=now_ts,
        location="store",
        extra={
            "shopping_truth_label": "ARCHITECT_SHOPPING_SEGMENT_V1",
            "timebox_truth_label": OPEN_SEGMENT_TRUTH_LABEL,
            "timebox_status": "closed_without_open_start",
            "timebox_topic": "shopping / store trip",
            "start_precision": "unknown_fallback_1min",
            "end_precision": "owner_store_return_time_out",
        },
    )
    return write_day_segment(row, state_dir=state_dir)


def try_ingest_architect_shopping_segment(
    text: str,
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    """Open/close the owner's store-shopping segment from natural speech."""
    raw = text or ""
    state = _state_dir(state_dir)
    active = read_open_life_segment(state_dir=state)
    start_match = _SHOPPING_START_RE.search(raw)
    end_match = _SHOPPING_END_RE.search(raw)
    if end_match and active and active.get("label") == "shopping":
        return close_open_life_segment(raw, state_dir=state, now=now, source="owner_store_return_time_out")
    if start_match:
        if active and active.get("label") == "shopping":
            return active
        return start_open_life_segment(
            "shopping / store trip",
            state_dir=state,
            now=now,
            source="owner_store_departure_time_in",
            label_override="shopping",
            media_context="",
            extra={
                "shopping_truth_label": "ARCHITECT_SHOPPING_SEGMENT_V1",
                "start_precision": "owner_store_departure_time_in",
            },
        )
    if end_match:
        return _write_unpaired_shopping_return_marker(raw, state_dir=state, now=now)
    return None


def try_ingest_architect_day_segment(
    text: str,
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    now_ts = float(now if now is not None else time.time())
    state = _state_dir(state_dir)

    # 1. Co-watch video context and live Time-In / Time-Out
    cowatch = try_ingest_architect_cowatch_segment(text, state_dir=state, now=now_ts)
    if cowatch:
        return cowatch
    shopping = try_ingest_architect_shopping_segment(text, state_dir=state, now=now_ts)
    if shopping:
        return shopping
    timebox = try_ingest_architect_timebox_command(text, state_dir=state, now=now_ts)
    if timebox:
        return timebox

    # 2. Retrospective parsing
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


def log_sensor_presence_segment(
    label: str,
    source: str,
    context_note: str,
    *,
    state_dir: Path | None = None,
    now: float | None = None,
    location: str = "",
    media_context: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ingest a day segment triggered autonomously by sensors (vision/audio/unified field)."""
    now_ts = float(now if now is not None else time.time())
    t = time.localtime(now_ts)
    start_min = t.tm_hour * 60 + t.tm_min
    end_min = start_min + 1  # 1 minute point-in-time observation
    
    # Check the last segment to avoid spamming the same autonomous segment every second
    try:
        path = _state_dir(state_dir) / SEGMENTS_LOG_NAME
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines()[-5:]:
                try:
                    last_row = json.loads(line)
                    if last_row.get("source") == source and last_row.get("label") == label:
                        age = now_ts - float(last_row.get("ts", 0))
                        if age < 300: # Throttle to 1 per 5 mins for the same sensor/label
                            return last_row
                except Exception:
                    pass
    except Exception:
        pass
        
    row = _build_row(
        label=label,
        start_minute=start_min,
        end_minute=end_min,
        context_note=context_note,
        source=source,
        state_dir=state_dir,
        now=now_ts,
        location=location,
        media_context=media_context,
        extra=extra,
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
    active = read_open_life_segment(state_dir=state_dir)
    if not rows and not active:
        return ""
    lines = ["DAY SEGMENTS DIARY (Observed 24h owner schedule blocks):"]
    if active:
        label = active.get("label") or "activity"
        start = active.get("start_time") or _fmt_minute(int(active.get("start_minute_of_day") or 0))
        topic = str(active.get("topic") or active.get("context_note") or "").strip()
        bits = [f"OPEN {label}", f"since {start}"]
        loc = active.get("location")
        if loc and loc != "unknown":
            bits.append(f"loc={loc}")
        media = active.get("media_context")
        if media:
            bits.append(f"media={media}")
        if topic:
            bits.append(f"topic={topic[:120]}")
        lines.append("- " + " | ".join(bits) + f" (open {active.get('open_segment_id', 'unknown')})")
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


_RECENT_ACTIVITY_QUERY_RE = re.compile(
    r"\b(?:"
    r"what\s+(?:was\s+i\s+doing|did\s+i\s+do|happened)|"
    r"where\s+was\s+i|"
    r"(?:look(?:ing)?\s+at|check(?:ing)?)\s+(?:the\s+)?schedule|"
    r"what\s+did\s+you\s+write\b.{0,120}\bschedule|"
    r"my\s+(?:recent\s+activity|schedule)|"
    r"last\s+(?:time|thing|segment|activity)|"
    r"remember\b.{0,80}\bhours?|"
    r"4\s+hours|four\s+hours"
    r")\b",
    re.IGNORECASE | re.DOTALL,
)
_RELATIVE_ACTIVITY_AGO_RE = re.compile(
    r"\b(?P<num>\d{1,3}|one|two|three|four|five|ten|fifteen|twenty|thirty|forty|sixty)\s*"
    r"(?P<unit>minutes?|mins?|hours?|hrs?)\s+ago\b",
    re.IGNORECASE,
)
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "ten": 10,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "sixty": 60,
}


def _query_target_minute(text: str, *, now: float | None = None) -> tuple[int | None, str]:
    """Return (minute_of_day, human_label) for receipt-backed recall queries."""
    raw = text or ""
    now_ts = float(now if now is not None else time.time())
    rel = _RELATIVE_ACTIVITY_AGO_RE.search(raw)
    if rel:
        num_s = rel.group("num").lower()
        count = int(num_s) if num_s.isdigit() else _NUMBER_WORDS.get(num_s, 0)
        unit = rel.group("unit").lower()
        seconds = count * (3600 if unit.startswith(("hour", "hr")) else 60)
        target_ts = now_ts - seconds
        unit_label = "hour" if unit.startswith(("hour", "hr")) else "minute"
        plural = "" if count == 1 else "s"
        return _minute_from_ts(target_ts), f"{count} {unit_label}{plural} ago"
    if re.search(r"\b(?:right\s+now|just\s+now|now)\b", raw, re.IGNORECASE):
        return _minute_from_ts(now_ts), "right now"
    if re.search(r"\b(?:last\s+(?:time|thing|segment|activity)|what\s+did\s+i\s+do\s+last)\b", raw, re.IGNORECASE):
        return None, "the last recorded segment"
    return None, "today"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _row_interval(row: dict[str, Any]) -> tuple[int, int] | None:
    if "start_minute_of_day" not in row or "end_minute_of_day" not in row:
        return None
    start = _safe_int(row.get("start_minute_of_day"))
    end = _safe_int(row.get("end_minute_of_day"))
    if end <= start:
        end += 24 * 60
    return start, end


def _minute_in_interval(minute: int, interval: tuple[int, int]) -> bool:
    start, end = interval
    return any(start <= candidate < end for candidate in (minute, minute + 24 * 60))


def _active_interval(active: dict[str, Any], *, now: float | None = None) -> tuple[int, int]:
    start = _safe_int(active.get("start_minute_of_day"), _minute_from_ts(active.get("start_ts") or time.time()))
    end = _minute_from_ts(float(now if now is not None else time.time()))
    if end <= start:
        end += 24 * 60
    return start, max(end, start + 1)


def _activity_kind(row: dict[str, Any]) -> str:
    label = str(row.get("label") or "activity").strip() or "activity"
    return "co-watch" if label == "co_watch" else label.replace("_", " ")


def _activity_topic(row: dict[str, Any]) -> str:
    if row.get("cowatch_title"):
        title = str(row.get("cowatch_title") or "").strip()
        url = str(row.get("cowatch_url") or "").strip()
        return f"{title} {url}".strip()
    for key in ("timebox_topic", "topic", "context_note", "raw_text"):
        value = str(row.get(key) or "").strip()
        if value:
            return " ".join(value.split())[:220]
    return _activity_kind(row)


def _format_activity_recall(
    row: dict[str, Any],
    *,
    target_label: str,
    open_segment: bool = False,
) -> str:
    kind = _activity_kind(row)
    topic = _activity_topic(row)
    receipt = str(row.get("open_segment_id") or row.get("segment_id") or row.get("trace_id") or "unknown")
    if open_segment:
        start = row.get("start_time") or _fmt_minute(_safe_int(row.get("start_minute_of_day")))
        status = f"open {kind} segment since {start}"
        source = "active life-segment receipt"
    else:
        status = f"{kind} segment at {_row_time_label(row)}"
        source = "day-segments ledger"
    loc = str(row.get("location") or "").strip()
    media = str(row.get("media_context") or "").strip()
    details = []
    if loc and loc != "unknown":
        details.append(f"loc={loc}")
    if media:
        details.append(f"media={media}")
    detail_s = ("; " + "; ".join(details)) if details else ""
    article = "an" if status[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
    return (
        f"I checked the local receipts. For {target_label}, the {source} says you were in {article} {status}: "
        f"{topic}{detail_s}. Receipt: {receipt}."
    )


def answer_recent_activity_query(
    text: str,
    *,
    state_dir: Path | None = None,
    now: float | None = None,
) -> str:
    if not _RECENT_ACTIVITY_QUERY_RE.search(text or ""):
        return ""
    target_minute, target_label = _query_target_minute(text or "", now=now)
    active = read_open_life_segment(state_dir=state_dir)
    if active and target_minute is not None and _minute_in_interval(
        target_minute,
        _active_interval(active, now=now),
    ):
        return _format_activity_recall(active, target_label=target_label, open_segment=True)

    rows = get_today_segments(state_dir=state_dir, now=now)
    if target_minute is not None:
        for row in reversed(rows):
            interval = _row_interval(row)
            if interval and _minute_in_interval(target_minute, interval):
                return _format_activity_recall(row, target_label=target_label)

    if active and target_label == "the last recorded segment":
        return _format_activity_recall(active, target_label=target_label, open_segment=True)
    if rows and target_label == "the last recorded segment":
        return _format_activity_recall(rows[-1], target_label=target_label)

    prompt = format_segments_for_prompt(state_dir=state_dir, now=now)
    if not prompt:
        return ""
    if target_minute is not None:
        return (
            f"I checked the local day-segments ledger. I do not see an exact "
            f"receipt covering {target_label}, but here is the current ledger context:\n"
            f"{prompt}"
        )
    return "I checked my local day-segments ledger:\n" + prompt


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
    "log_sensor_presence_segment",
    "read_open_life_segment",
    "start_open_life_segment",
    "close_open_life_segment",
    "try_ingest_architect_cowatch_segment",
    "try_ingest_architect_day_segment",
    "try_ingest_architect_shopping_segment",
    "try_ingest_architect_timebox_command",
    "write_day_segment",
]


# ---------------------------------------------------------------------
# r222 Lane B — Owner browser behaviour trail (first-person Alice awareness)
# George is on his own app (Alice Browser). These rows are *his* hands in *his*
# tool, recorded to *his* schedule + Alice's episodic diary.
# Never conflated with Alice's own effector actions (§6 social frame).
# ---------------------------------------------------------------------

def log_owner_browser_behaviour(
    *,
    url: str,
    title: str = "",
    action: str = "navigate",
    domain: str = "",
    category: str = "",
    source: str = "sifta_alice_browser_widget",
    extra: Optional[dict] = None,
    state_dir: Optional[Path] = None,
    now: Optional[float] = None,
) -> dict[str, Any]:
    """Append a categorized owner-behaviour row to architect_day_segments + episodic_diary.

    This is Alice watching her owner use her own body (the browser).
    First-person language for the diary so she can truthfully answer
    "what was George doing in the browser?"
    """
    now_ts = float(now if now is not None else time.time())
    state = _state_dir(state_dir)
    dom = domain or _domain(url)
    cat = category or _categorize_domain(dom)

    # 1. Day segment (owner schedule / behaviour log)
    seg_row = _build_row(
        label="browser_activity",
        start_minute=_minute_from_ts(now_ts),
        end_minute=_minute_from_ts(now_ts) + 1,
        context_note=f"browser:{action}:{dom}",
        source=source or "alice_browser_owner_action",
        state_dir=state,
        now=now_ts,
        extra={
            "browser_truth_label": "OWNER_BROWSER_BEHAVIOUR_V1",
            "url": url,
            "title": title,
            "action": action,
            "domain": dom,
            "category": cat,
            "browser_source": source or "unknown",
            "first_person_note": f"George was on {dom} ({cat}) — action: {action}.",
            **(extra or {}),
        },
    )
    write_day_segment(seg_row, state_dir=state)

    # 2. Episodic diary (Alice's own memory of her owner's activity in her body)
    diary_path = state / "episodic_diary.jsonl"
    diary_row = {
        "ts": now_ts,
        "kind": "owner_browser_behaviour",
        "truth_label": "OWNER_BROWSER_ACTIVITY_IN_ALICE_BODY_V1",
        "url": url,
        "title": title,
        "domain": dom,
        "category": cat,
        "action": action,
        "first_person": f"George is on {dom} (category: {cat}). He just performed: {action}. Title: {title}. This is my browser limb — I am aware of my owner's hands moving inside me.",
        "source": source or "sifta_alice_browser_widget",
        "note": "Owner action in Alice's own application surface. Social frame preserved.",
    }
    if extra:
        diary_row["extra"] = dict(extra)
    try:
        append_line_locked(
            diary_path,
            json.dumps(diary_row, ensure_ascii=False, sort_keys=True) + "\n",
        )
    except Exception:
        pass

    return {"segment": seg_row, "diary": diary_row}


def _domain(u: str) -> str:
    try:
        return urlparse(u or "").netloc.lower()
    except Exception:
        return ""


def _categorize_domain(dom: str) -> str:
    d = (dom or "").lower()
    if "youtube" in d or "youtu" in d:
        return "video"
    if "tiktok" in d:
        return "short_video"
    if "instagram" in d:
        return "social_image"
    if "x.com" in d or "twitter" in d:
        return "social_text"
    if "google" in d:
        return "search"
    return "web"


if __name__ == "__main__":
    print(format_segments_for_prompt())
