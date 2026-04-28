#!/usr/bin/env python3
"""
System/swarm_youtube_context.py — YouTube Caption Context Organ
═══════════════════════════════════════════════════════════════════════════
Turns a frontmost YouTube browser snapshot into a compact, truthful context
row Alice can read through the existing app-focus ledger.

This is not a video downloader. It only reads public YouTube player metadata
and caption tracks when the open video exposes them. If captions are missing
or blocked, Alice receives that truth instead of a fabricated summary.
"""
from __future__ import annotations

import html
import json
import re
import ssl
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
LEDGER = _STATE / "youtube_context.jsonl"
STATE_FILE = _STATE / "youtube_context_latest.json"

FetchFn = Callable[[str, float], str]


def _default_fetch(url: str, timeout_s: float = 4.0) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15"
            )
        },
    )
    context = None
    try:
        import certifi  # type: ignore

        context = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        context = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout_s, context=context) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _append_fmt_json3(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    query["fmt"] = ["json3"]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))


def _extract_balanced_json_after(text: str, marker: str) -> Optional[dict[str, Any]]:
    idx = text.find(marker)
    if idx < 0:
        return None
    start = text.find("{", idx)
    if start < 0:
        return None

    depth = 0
    in_str = False
    escape = False
    for pos in range(start, len(text)):
        ch = text[pos]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : pos + 1])
                except json.JSONDecodeError:
                    return None
    return None


def extract_player_response(watch_html: str) -> Optional[dict[str, Any]]:
    for marker in ("ytInitialPlayerResponse =", "ytInitialPlayerResponse="):
        parsed = _extract_balanced_json_after(watch_html, marker)
        if parsed:
            return parsed
    m = re.search(r'"playerResponse"\s*:\s*"(.+?)"', watch_html)
    if not m:
        return None
    try:
        return json.loads(bytes(m.group(1), "utf-8").decode("unicode_escape"))
    except Exception:
        return None


def choose_caption_track(player_response: dict[str, Any]) -> Optional[dict[str, Any]]:
    tracks = (
        player_response.get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks", [])
    )
    if not tracks:
        return None
    # Prefer English manual captions, then English auto captions, then any track.
    ranked = sorted(
        tracks,
        key=lambda t: (
            0 if str(t.get("languageCode", "")).startswith("en") else 1,
            1 if t.get("kind") == "asr" else 0,
        ),
    )
    return ranked[0]


def parse_caption_payload(payload: str) -> str:
    payload = payload.strip()
    if not payload:
        return ""
    if payload.startswith("{"):
        data = json.loads(payload)
        chunks: list[str] = []
        for event in data.get("events", []):
            segs = event.get("segs") or []
            text = "".join(str(seg.get("utf8", "")) for seg in segs)
            text = html.unescape(text).replace("\n", " ").strip()
            if text:
                chunks.append(text)
        return _normalize_caption_text(" ".join(chunks))

    root = ET.fromstring(payload)
    chunks = []
    for node in root.iter():
        if node.text:
            text = html.unescape(node.text).replace("\n", " ").strip()
            if text:
                chunks.append(text)
    return _normalize_caption_text(" ".join(chunks))


def _normalize_caption_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fetch_caption_context(
    video_id: str,
    *,
    fetcher: FetchFn = _default_fetch,
    timeout_s: float = 4.0,
    max_excerpt_chars: int = 900,
) -> dict[str, Any]:
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    watch_html = fetcher(watch_url, timeout_s)
    player = extract_player_response(watch_html)
    if not player:
        return {
            "status": "no_player_response",
            "caption_excerpt": "",
            "caption_chars": 0,
            "language": "",
            "is_auto_generated": False,
        }
    track = choose_caption_track(player)
    if not track or not track.get("baseUrl"):
        return {
            "status": "no_captions",
            "caption_excerpt": "",
            "caption_chars": 0,
            "language": "",
            "is_auto_generated": False,
        }
    caption_url = _append_fmt_json3(str(track["baseUrl"]))
    raw = fetcher(caption_url, timeout_s)
    caption_text = parse_caption_payload(raw)
    return {
        "status": "captions_available" if caption_text else "empty_captions",
        "caption_excerpt": caption_text[:max_excerpt_chars],
        "caption_chars": len(caption_text),
        "language": str(track.get("languageCode", "")),
        "is_auto_generated": track.get("kind") == "asr",
        "track_name": (
            ((track.get("name") or {}).get("simpleText"))
            or " ".join(r.get("text", "") for r in ((track.get("name") or {}).get("runs") or []))
        ).strip(),
    }


def _load_cached(video_id: str, max_age_s: float = 1800.0) -> Optional[dict[str, Any]]:
    if not STATE_FILE.exists():
        return None
    try:
        row = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if row.get("video_id") != video_id:
        return None
    if time.time() - float(row.get("ts", 0)) > max_age_s:
        return None
    return row


def _write_row(row: dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def observe_snapshot(
    snap: dict[str, Any],
    *,
    fetcher: FetchFn = _default_fetch,
    force: bool = False,
    publish: bool = True,
    max_excerpt_chars: int = 900,
) -> Optional[dict[str, Any]]:
    """Read captions for a YouTube frontmost-window snapshot and publish focus.

    Returns the row written/read from cache, or None if the snapshot is not a
    YouTube video with a usable id.
    """
    browser = snap.get("browser") or {}
    video_id = str(browser.get("youtube_video_id") or "").strip()
    if not video_id:
        return None
    cached = None if force else _load_cached(video_id)
    if cached:
        row = {**cached, "cache_hit": True}
    else:
        try:
            ctx = fetch_caption_context(
                video_id,
                fetcher=fetcher,
                max_excerpt_chars=max_excerpt_chars,
            )
        except Exception as exc:
            ctx = {
                "status": "caption_fetch_error",
                "caption_excerpt": "",
                "caption_chars": 0,
                "language": "",
                "is_auto_generated": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        row = {
            "ts": time.time(),
            "video_id": video_id,
            "url": browser.get("url", ""),
            "title": browser.get("title") or snap.get("window") or "",
            "frontmost_app": snap.get("app") or "",
            "frontmost_window": snap.get("window") or "",
            "cache_hit": False,
            "truth_note": "public YouTube caption metadata observed from frontmost browser video",
            **ctx,
        }
        _write_row(row)

    if publish:
        _publish_focus(row)
    return row


def _publish_focus(row: dict[str, Any]) -> None:
    try:
        from System.swarm_app_focus import publish_focus
    except Exception:
        return
    status = row.get("status", "unknown")
    title = row.get("title") or row.get("video_id")
    detail = (
        "The Architect is physically at this Mac watching this YouTube video "
        f"with Alice: {title}. Caption status: {status}."
    )
    if row.get("caption_excerpt"):
        detail += " Alice has a compact caption excerpt for shared context."
    publish_focus(
        "YouTube",
        detail,
        tab=str(row.get("frontmost_app") or ""),
        selection=str(title or ""),
        metadata={
            "url": row.get("url", ""),
            "youtube_video_id": row.get("video_id", ""),
            "caption_status": status,
            "caption_language": row.get("language", ""),
            "caption_auto_generated": bool(row.get("is_auto_generated")),
            "caption_excerpt": row.get("caption_excerpt", ""),
            "caption_chars": int(row.get("caption_chars") or 0),
            "truth_note": row.get("truth_note", ""),
        },
    )


def get_latest_context(max_age_s: float = 600.0) -> Optional[str]:
    if not STATE_FILE.exists():
        return None
    try:
        row = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if time.time() - float(row.get("ts", 0)) > max_age_s:
        return None
    bits = [
        f"YouTube video: {row.get('title') or row.get('video_id')}",
        f"caption_status={row.get('status', 'unknown')}",
    ]
    if row.get("caption_excerpt"):
        bits.append(f"caption_excerpt={row['caption_excerpt']}")
    return " | ".join(bits)


if __name__ == "__main__":
    from System import swarm_active_window as aw

    snap = aw.read(force_refresh=True)
    row = observe_snapshot(snap, force=True)
    print(json.dumps(row or {"ok": False, "reason": "frontmost window is not YouTube"}, indent=2))
