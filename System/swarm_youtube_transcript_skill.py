#!/usr/bin/env python3
"""YouTube transcript export skill for Alice Browser.

This is a browser-consciousness helper, not the bounded co-watch memory organ.
When George explicitly asks Alice to extract a YouTube transcript/subtitles and
save it, Alice can export the available visible transcript or caption-track text
to Downloads and leave a receipt. If no transcript/caption data is exposed, the
receipt says so instead of inventing subtitles.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None

REPO = Path(__file__).resolve().parents[1]
DEFAULT_STATE = REPO / ".sifta_state"
DEFAULT_DOWNLOADS = Path.home() / "Downloads"
LEDGER_NAME = "youtube_transcript_exports.jsonl"
TRUTH_LABEL = "YOUTUBE_TRANSCRIPT_EXPORT_V1"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    state = Path(state_dir) if state_dir is not None else DEFAULT_STATE
    state.mkdir(parents=True, exist_ok=True)
    return state


def youtube_video_id(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(str(url or ""))
    except Exception:
        return ""
    host = (parsed.netloc or "").lower()
    host = host[4:] if host.startswith("www.") else host
    path = (parsed.path or "").strip("/")
    if host in {"youtube.com", "m.youtube.com"}:
        if path == "watch":
            return urllib.parse.parse_qs(parsed.query).get("v", [""])[0] or ""
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            return parts[1] or ""
    if host == "youtu.be":
        return path.split("/")[0] or ""
    return ""


def _clean(value: Any, *, max_chars: int = 4000) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", str(value or ""))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:max_chars]


def _slug(value: Any, *, max_chars: int = 72) -> str:
    text = re.sub(r"\s+", "_", str(value or "").strip().lower())
    text = re.sub(r"[^a-z0-9._-]+", "", text).strip("._-")
    return (text or "youtube_transcript")[:max_chars]


def _format_time(seconds: float | int | str | None) -> str:
    try:
        total = max(0.0, float(seconds or 0.0))
    except Exception:
        total = 0.0
    total_i = int(round(total))
    h, rem = divmod(total_i, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def normalize_segments(segments: Iterable[Mapping[str, Any]] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in segments or []:
        if not isinstance(item, Mapping):
            continue
        text = _clean(item.get("text"), max_chars=1600)
        if not text:
            continue
        start = item.get("start")
        time_label = _clean(item.get("time"), max_chars=32)
        if not time_label:
            time_label = _format_time(start)
        out.append({"time": time_label, "text": text})
    return out


def parse_youtube_caption_payload(payload: bytes | str) -> list[dict[str, str]]:
    """Parse YouTube timedtext XML or json3 caption payloads into time/text rows."""
    if isinstance(payload, bytes):
        raw = payload.decode("utf-8", errors="replace")
    else:
        raw = str(payload or "")
    raw = raw.strip()
    if not raw:
        return []

    if raw.startswith("{") or raw.startswith("["):
        try:
            data = json.loads(raw)
            events = data.get("events", []) if isinstance(data, dict) else []
            rows: list[dict[str, str]] = []
            for event in events:
                if not isinstance(event, Mapping):
                    continue
                segs = event.get("segs") or []
                text = "".join(str(seg.get("utf8") or "") for seg in segs if isinstance(seg, Mapping))
                text = _clean(text, max_chars=1600)
                if not text:
                    continue
                start_ms = event.get("tStartMs")
                try:
                    start_s = float(start_ms) / 1000.0
                except Exception:
                    start_s = 0.0
                rows.append({"time": _format_time(start_s), "text": text})
            if rows:
                return rows
        except Exception:
            pass

    try:
        root = ET.fromstring(raw)
    except Exception:
        return []
    rows = []
    for elem in root.iter():
        if not str(elem.tag).lower().endswith("text"):
            continue
        text = _clean(unescape("".join(elem.itertext())), max_chars=1600)
        if not text:
            continue
        rows.append({"time": _format_time(elem.attrib.get("start")), "text": text})
    return rows


def fetch_youtube_caption_track(base_url: str, *, timeout_s: float = 8.0) -> dict[str, Any]:
    """Fetch a caption track URL exposed by YouTube's player response."""
    if not str(base_url or "").strip():
        return {"ok": False, "reason": "missing_caption_track_url", "segments": []}
    try:
        req = urllib.request.Request(
            str(base_url),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=float(timeout_s)) as resp:
            payload = resp.read()
    except Exception as exc:
        return {"ok": False, "reason": f"caption_fetch_failed:{type(exc).__name__}:{exc}", "segments": []}
    segments = parse_youtube_caption_payload(payload)
    return {
        "ok": bool(segments),
        "reason": "" if segments else "caption_payload_empty",
        "segments": segments,
        "bytes": len(payload),
    }


def record_youtube_transcript_attempt(
    *,
    ok: bool,
    url: str,
    title: str = "",
    source: str = "",
    reason: str = "",
    path: str = "",
    char_count: int = 0,
    line_count: int = 0,
    language: str = "",
    state_dir: Path | str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    ts = time.time()
    receipt_id = f"ytx-{int(ts * 1000)}"
    row: dict[str, Any] = {
        "ts": ts,
        "receipt_id": receipt_id,
        "truth_label": TRUTH_LABEL,
        "ok": bool(ok),
        "url": str(url or ""),
        "video_id": youtube_video_id(url),
        "title": _clean(title, max_chars=300),
        "source": str(source or ""),
        "reason": str(reason or ""),
        "path": str(path or ""),
        "char_count": int(char_count or 0),
        "line_count": int(line_count or 0),
        "language": str(language or ""),
        "note": "Transcript/subtitle export is a browser skill receipt; no text is invented when captions are unavailable.",
    }
    if extra:
        row["extra"] = dict(extra)
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    ledger = state / LEDGER_NAME
    if append_line_locked:
        append_line_locked(ledger, payload)
    else:
        with ledger.open("a", encoding="utf-8") as f:
            f.write(payload)
    return row


def save_youtube_transcript_export(
    *,
    url: str,
    title: str = "",
    segments: Iterable[Mapping[str, Any]] | None = None,
    transcript_text: str = "",
    source: str = "",
    language: str = "",
    state_dir: Path | str | None = None,
    downloads_dir: Path | str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = normalize_segments(segments)
    if rows:
        body_lines = [f"[{row['time']}] {row['text']}" for row in rows]
    else:
        text = _clean(transcript_text, max_chars=2_000_000)
        body_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not body_lines:
        return record_youtube_transcript_attempt(
            ok=False,
            url=url,
            title=title,
            source=source,
            reason="empty_transcript",
            language=language,
            state_dir=state_dir,
            extra=extra,
        )

    downloads = Path(downloads_dir) if downloads_dir is not None else DEFAULT_DOWNLOADS
    downloads.mkdir(parents=True, exist_ok=True)
    video_id = youtube_video_id(url) or "unknown_video"
    filename = f"youtube_transcript_{video_id}_{_slug(title)}.txt"
    path = downloads / filename
    ts = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())
    header = [
        "SIFTA YouTube Transcript Export",
        f"title: {_clean(title, max_chars=300)}",
        f"url: {url}",
        f"video_id: {video_id}",
        f"source: {source}",
        f"language: {language}",
        f"exported_at: {ts}",
        f"truth_label: {TRUTH_LABEL}",
        "",
    ]
    text_out = "\n".join(header + body_lines).rstrip() + "\n"
    path.write_text(text_out, encoding="utf-8")
    return record_youtube_transcript_attempt(
        ok=True,
        url=url,
        title=title,
        source=source,
        path=str(path),
        char_count=len(text_out),
        line_count=len(body_lines),
        language=language,
        state_dir=state_dir,
        extra=extra,
    )
