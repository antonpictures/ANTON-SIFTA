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

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
LEDGER = _STATE / "youtube_context.jsonl"
STATE_FILE = _STATE / "youtube_context_latest.json"
COWATCH_LEDGER = _STATE / "youtube_architect_cowatch.jsonl"
TRANSCRIPT_DIR = _STATE / "youtube_transcripts"

FetchFn = Callable[[str, float], str]

_YOUTUBE_WATCH_ID_RE = re.compile(
    r"(?:youtube\.com/watch\?v=|youtube\.com/watch\?[^#\s]+&v=|youtu\.be/)([A-Za-z0-9_-]{6,32})\b",
    re.IGNORECASE,
)

_UI_LINE_RE = re.compile(
    r"^(?:"
    r"skip navigation|create|avatar image|subscribe|share|ask|save|reply|"
    r"add a comment|ask questions|ask gemini|all|related|recently uploaded|"
    r"watched|show more|learn more|ai can make mistakes.*|true|false"
    r")$",
    re.IGNORECASE,
)
_QUESTION_RE = re.compile(r"^(?:how|why|what|when|where|who|recommend|summarize)\b.*\?$", re.IGNORECASE)
_VIEWS_RE = re.compile(r"(?P<views>[\d,]+)\s+views\s+(?P<published>[A-Z][a-z]{2,9}\s+\d{1,2},\s+\d{4})")
_SUBS_RE = re.compile(r"(?P<subs>[\d.,]+[KMB]?)\s+subscribers?", re.IGNORECASE)
_STOPWORDS = {
    "about",
    "after",
    "again",
    "alice",
    "also",
    "because",
    "being",
    "could",
    "from",
    "have",
    "here",
    "into",
    "like",
    "make",
    "more",
    "that",
    "their",
    "there",
    "they",
    "this",
    "video",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "youtube",
}


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


def _clean_pasted_lines(raw_text: str) -> list[str]:
    """Normalize pasted YouTube page text without treating it as a transcript."""
    lines: list[str] = []
    for raw in str(raw_text or "").replace("\r", "\n").split("\n"):
        line = re.sub(r"\s+", " ", raw).strip()
        if not line:
            continue
        if _UI_LINE_RE.match(line):
            continue
        lines.append(line)
    return lines


def _first_page_title(lines: list[str]) -> str:
    for line in lines[:24]:
        low = line.lower()
        if (
            low.startswith(("http://", "https://"))
            or "subscribers" in low
            or "views" in low
            or line.startswith("@")
            or _QUESTION_RE.match(line)
            or len(line) < 6
        ):
            continue
        return line[:180]
    return ""


def _first_channel(lines: list[str], title: str) -> str:
    for idx, line in enumerate(lines[:80]):
        if _SUBS_RE.search(line):
            for prior in reversed(lines[max(0, idx - 3) : idx]):
                if prior != title and not prior.startswith("@") and len(prior) <= 80:
                    return prior[:80]
            return ""
    return ""


def _extract_page_answer(lines: list[str], max_chars: int) -> str:
    """Extract YouTube Ask panel answer if present, bounded and non-authoritative."""
    start = -1
    for idx, line in enumerate(lines):
        if line.isupper() and len(line) >= 8 and not line.startswith("@"):
            start = idx
            break
    if start < 0:
        return ""
    chunks: list[str] = []
    for line in lines[start : start + 18]:
        if line.startswith("@") or _QUESTION_RE.match(line):
            break
        if "ai can make mistakes" in line.lower():
            break
        chunks.append(line)
    return _normalize_caption_text(" ".join(chunks))[:max_chars]


def _extract_questions(lines: list[str], limit: int = 8) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if not _QUESTION_RE.match(line):
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(line[:160])
        if len(out) >= limit:
            break
    return out


def _keyword_signals(lines: list[str], limit: int = 10) -> list[str]:
    counts: dict[str, int] = {}
    for line in lines:
        if line.lower().startswith(("http://", "https://")):
            continue
        if line.startswith("@") or _VIEWS_RE.search(line) or _SUBS_RE.search(line):
            continue
        for word in re.findall(r"[A-Za-z][A-Za-z'_-]{3,}", line.lower()):
            word = word.strip("'_-")
            if word in _STOPWORDS:
                continue
            counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [word for word, _ in ranked[:limit]]


def parse_pasted_youtube_page(
    raw_text: str,
    *,
    max_answer_chars: int = 700,
) -> dict[str, Any]:
    """Parse owner-pasted YouTube page text into a compact semantic receipt.

    This is the no-network fallback for co-watching. It stores metadata,
    Ask-panel context, suggested questions, and coarse keyword signals, not a
    raw movie transcript or raw audio.
    """
    lines = _clean_pasted_lines(raw_text)
    title = _first_page_title(lines)
    channel = _first_channel(lines, title)
    subscribers = ""
    views = ""
    published = ""
    comment_count = 0
    for line in lines:
        if not subscribers:
            m_subs = _SUBS_RE.search(line)
            if m_subs:
                subscribers = m_subs.group("subs")
        if not views:
            m_views = _VIEWS_RE.search(line)
            if m_views:
                views = m_views.group("views")
                published = m_views.group("published")
        if line.startswith("@"):
            comment_count += 1

    questions = _extract_questions(lines)
    ask_answer = _extract_page_answer(lines, max_answer_chars)
    content_signals = _keyword_signals(lines)
    content_kind = "youtube_video_page"
    if re.search(r"\b(?:scene|clip|movie|film|cinema|snatch|scarface|john wick)\b", title, re.IGNORECASE):
        content_kind = "film_clip_page"

    summary_bits = []
    if title:
        summary_bits.append(f"title={title}")
    if channel:
        summary_bits.append(f"channel={channel}")
    if views:
        summary_bits.append(f"views={views}")
    if published:
        summary_bits.append(f"published={published}")
    if content_signals:
        summary_bits.append("signals=" + ",".join(content_signals[:6]))
    page_context = "; ".join(summary_bits)

    return {
        "status": "pasted_page_context" if lines else "empty_paste",
        "content_kind": content_kind,
        "title": title,
        "channel": channel,
        "subscriber_count_text": subscribers,
        "view_count_text": views,
        "published_text": published,
        "suggested_questions": questions,
        "ask_panel_answer_excerpt": ask_answer,
        "ask_panel_answer_chars": len(ask_answer),
        "content_signals": content_signals,
        "public_comment_handle_count": comment_count,
        "page_context": page_context,
        "raw_page_chars": len(str(raw_text or "")),
        "raw_audio_logged": False,
        "truth_note": (
            "owner-pasted public YouTube page context; semantic media context "
            "for co-listening, not a direct human utterance and not raw audio"
        ),
    }


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
    append_line_locked(LEDGER, json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def _stamp_watch_memory(row: dict[str, Any]) -> dict[str, Any]:
    try:
        from System.swarm_youtube_watch_memory import remember_youtube_watch

        memory = remember_youtube_watch(row, state_dir=STATE_FILE.parent)
    except Exception:
        return row
    row["watch_memory_id"] = memory.get("memory_id", "")
    row["watch_notes_file"] = memory.get("notes_file", "")
    frame = memory.get("reality_frame") if isinstance(memory.get("reality_frame"), dict) else {}
    if frame:
        row["reality_frame"] = frame.get("reality_frame", "")
        row["content_category"] = frame.get("content_category", "")
        row["source_work"] = frame.get("source_work", "")
        row["director"] = frame.get("director", "")
        row["profanity_frame"] = frame.get("profanity_frame", "")
        row["dialogue_boundary"] = frame.get("dialogue_boundary", "")
    return row


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
        row = _stamp_watch_memory(row)
        _write_row(row)

    if publish:
        _publish_focus(row)
    return row


def observe_pasted_page(
    raw_text: str,
    *,
    source: str = "architect_paste",
    url: str = "",
    publish: bool = True,
    max_answer_chars: int = 700,
) -> dict[str, Any]:
    """Publish a YouTube-context receipt from owner-pasted page text.

    Use this when captions are unavailable or when George pastes the visible
    YouTube page/comments/Ask panel into a chat. The row is explicitly marked
    as shared media context, so Alice can be interested in the content without
    misrouting the page text as direct speech from the room microphone.
    """
    parsed = parse_pasted_youtube_page(raw_text, max_answer_chars=max_answer_chars)
    if not url:
        try:
            from System.swarm_youtube_watch_memory import first_youtube_url

            url = first_youtube_url(raw_text)
        except Exception:
            url = ""
    video_id = ""
    if url:
        try:
            from System.swarm_youtube_watch_memory import youtube_video_id

            video_id = youtube_video_id(url)
        except Exception:
            video_id = ""
    row = {
        "ts": time.time(),
        "video_id": video_id,
        "url": url,
        "frontmost_app": "",
        "frontmost_window": "",
        "cache_hit": False,
        "source": source,
        "context_route": "shared_media_context",
        "caption_excerpt": "",
        "caption_chars": 0,
        "language": "",
        "is_auto_generated": False,
        **parsed,
    }
    row = _stamp_watch_memory(row)
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
    if row.get("page_context"):
        detail += " Alice has owner-pasted page context for co-watching."
    if row.get("reality_frame") == "FICTIONAL_MEDIA_CLIP":
        director = row.get("director") or "unknown director"
        detail += f" Reality frame: fictional media clip; director: {director}."
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
            "context_route": row.get("context_route", ""),
            "content_kind": row.get("content_kind", ""),
            "page_context": row.get("page_context", ""),
            "content_signals": row.get("content_signals", []),
            "suggested_questions": row.get("suggested_questions", []),
            "ask_panel_answer_excerpt": row.get("ask_panel_answer_excerpt", ""),
            "watch_memory_id": row.get("watch_memory_id", ""),
            "watch_notes_file": row.get("watch_notes_file", ""),
            "reality_frame": row.get("reality_frame", ""),
            "content_category": row.get("content_category", ""),
            "source_work": row.get("source_work", ""),
            "director": row.get("director", ""),
            "profanity_frame": row.get("profanity_frame", ""),
            "dialogue_boundary": row.get("dialogue_boundary", ""),
            "truth_note": row.get("truth_note", ""),
        },
    )


def extract_youtube_video_id(url_or_id: str) -> str:
    """Return a YouTube video id from a watch URL, short URL, or bare 11-char id."""
    s = (url_or_id or "").strip()
    if not s:
        return ""
    m = _YOUTUBE_WATCH_ID_RE.search(s)
    if m:
        return str(m.group(1))[:32]
    if re.fullmatch(r"[A-Za-z0-9_-]{6,32}", s):
        return s
    return ""


def fetch_transcript_for_video(
    video_id: str,
    *,
    fetcher: FetchFn = _default_fetch,
    timeout_s: float = 12.0,
    max_chars: int = 250_000,
) -> dict[str, Any]:
    """Fetch the full public timedtext transcript when YouTube lists a caption track.

    If the video has no caption tracks in ``ytInitialPlayerResponse``, this returns
    ``status=no_captions`` and an empty transcript — **no fabrication** (covenant §6).
    """
    vid = (video_id or "").strip()
    if not vid:
        return {
            "ok": False,
            "status": "bad_video_id",
            "title": "",
            "transcript": "",
            "transcript_chars": 0,
            "video_id": "",
        }
    watch_url = f"https://www.youtube.com/watch?v={urllib.parse.quote(vid)}"
    watch_html = fetcher(watch_url, timeout_s)
    player = extract_player_response(watch_html)
    title = ""
    if isinstance(player, dict):
        vd = player.get("videoDetails") or {}
        if isinstance(vd, dict):
            title = str(vd.get("title") or "").strip()
    if not player:
        return {
            "ok": False,
            "status": "no_player_response",
            "title": title,
            "transcript": "",
            "transcript_chars": 0,
            "video_id": vid,
            "truth_note": "watch page did not yield ytInitialPlayerResponse",
        }
    track = choose_caption_track(player)
    if not track or not track.get("baseUrl"):
        return {
            "ok": False,
            "status": "no_captions",
            "title": title,
            "transcript": "",
            "transcript_chars": 0,
            "video_id": vid,
            "truth_note": "YouTube player listed no usable caption tracks for this video",
        }
    caption_url = _append_fmt_json3(str(track["baseUrl"]))
    raw = fetcher(caption_url, timeout_s)
    caption_text = parse_caption_payload(raw)
    truncated = len(caption_text) > int(max_chars)
    if truncated:
        caption_text = caption_text[: int(max_chars)]
    return {
        "ok": bool(caption_text),
        "status": "transcript_available" if caption_text else "empty_captions",
        "title": title,
        "transcript": caption_text,
        "transcript_chars": len(caption_text),
        "truncated": truncated,
        "language": str(track.get("languageCode", "")),
        "is_auto_generated": track.get("kind") == "asr",
        "video_id": vid,
        "truth_note": (
            "Parsed from public YouTube timedtext payload linked in player response; "
            "not a human-provided subtitle file and not verified against the video pixels."
        ),
    }


def write_architect_cowatch_transcript_file(
    video_id: str,
    *,
    url: str,
    title: str,
    transcript: str,
    category_lane: str,
    state_dir: Optional[Path] = None,
    architect_note: str = "",
) -> Path:
    """Write ``.sifta_state/youtube_transcripts/<video_id>.md`` for Architect co-watch."""
    base = Path(state_dir) if state_dir is not None else _STATE
    tdir = base / "youtube_transcripts"
    tdir.mkdir(parents=True, exist_ok=True)
    path = tdir / f"{video_id}.md"
    safe_title = (title or "").replace('"', "'").strip()[:240]
    note = (architect_note or "").strip()
    truth = (
        "YOUTUBE_PUBLIC_CAPTION_TRANSCRIPT"
        if (transcript or "").strip()
        else "NO_PUBLIC_CAPTION_TRANSCRIPT"
    )
    header = (
        "---\n"
        f'youtube_video_id: "{video_id}"\n'
        f'url: "{url}"\n'
        f'title: "{safe_title}"\n'
        f'category_lane: "{(category_lane or "unknown")[:64]}"\n'
        f"truth_label: {truth}\n"
        "---\n\n"
    )
    body = transcript if transcript.strip() else (
        "(No timedtext payload produced usable transcript text from the YouTube player response. "
        "Architect may paste visible page copy into ``observe_pasted_page`` "
        "or attach an official caption export when available.)\n"
    )
    if note:
        body += "\n## Architect note (human-provided)\n\n" + note + "\n"
    path.write_text(header + body, encoding="utf-8")
    return path


def record_architect_youtube_cowatch(
    url_or_id: str,
    *,
    category_lane: str = "fiction",
    architect_note: str = "",
    fetcher: FetchFn = _default_fetch,
    state_dir: Optional[Path] = None,
    publish_focus_event: bool = True,
) -> dict[str, Any]:
    """Transcribe (when YouTube exposes captions), write transcript file, append co-watch receipt.

    ``category_lane`` defaults to ``fiction`` for the Architect's staged rollout
    (broader YouTube category routing can tighten later without rewriting receipts).
    """
    base = Path(state_dir) if state_dir is not None else _STATE
    video_id = extract_youtube_video_id(url_or_id)
    if not video_id:
        return {
            "ok": False,
            "error": "could_not_parse_video_id",
            "truth_label": "FORBIDDEN_INVENTED_URL",
        }
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    tr = fetch_transcript_for_video(video_id, fetcher=fetcher)
    transcript_body = str(tr.get("transcript") or "")
    title = str(tr.get("title") or "")
    tpath = write_architect_cowatch_transcript_file(
        video_id,
        url=canonical_url,
        title=title,
        transcript=transcript_body,
        category_lane=category_lane,
        state_dir=base,
        architect_note=architect_note,
    )
    try:
        rel = str(tpath.relative_to(base)).replace("\\", "/")
    except ValueError:
        rel = str(tpath)

    receipt: dict[str, Any] = {
        "ts": time.time(),
        "truth_label": "ARCHITECT_YOUTUBE_COWATCH_SESSION",
        "schema_version": "architect_cowatch.v1",
        "youtube_video_id": video_id,
        "url": canonical_url,
        "category_lane": (category_lane or "unknown")[:64],
        "architect_note": (architect_note or "")[:1200],
        "caption_status": tr.get("status"),
        "transcript_chars": int(tr.get("transcript_chars") or 0),
        "transcript_truncated": bool(tr.get("truncated")),
        "title": title[:400],
        "transcript_file": rel,
        "language": tr.get("language", ""),
        "is_auto_generated": bool(tr.get("is_auto_generated")),
        "truth_note": str(tr.get("truth_note") or ""),
    }
    cow = base / "youtube_architect_cowatch.jsonl"
    cow.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(cow, json.dumps(receipt, ensure_ascii=False) + "\n", encoding="utf-8")

    if publish_focus_event:
        focus_row = {
            "ts": receipt["ts"],
            "video_id": video_id,
            "url": canonical_url,
            "title": title or video_id,
            "frontmost_app": "",
            "frontmost_window": "",
            "cache_hit": False,
            "status": tr.get("status"),
            "caption_excerpt": transcript_body[:900],
            "caption_chars": int(tr.get("transcript_chars") or 0),
            "language": tr.get("language", ""),
            "is_auto_generated": bool(tr.get("is_auto_generated")),
            "category_lane": category_lane,
            "context_route": "architect_cowatch_transcript_file",
            "truth_note": (
                f"Architect co-watch; full transcript attempt in {rel}; "
                "ledger=youtube_architect_cowatch.jsonl"
            ),
        }
        try:
            _publish_focus(focus_row)
        except Exception:
            pass

    return {"ok": True, "receipt": receipt, "transcript_path": str(tpath)}


def get_latest_context(max_age_s: float = 600.0) -> Optional[str]:
    if not STATE_FILE.exists():
        return None
    try:
        row = json.loads(read_text_locked(STATE_FILE, encoding="utf-8"))
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
    if row.get("page_context"):
        bits.append(f"page_context={row['page_context']}")
    if row.get("ask_panel_answer_excerpt"):
        bits.append(f"ask_panel_excerpt={row['ask_panel_answer_excerpt']}")
    if row.get("suggested_questions"):
        bits.append("suggested_questions=" + " / ".join(row["suggested_questions"][:4]))
    if row.get("reality_frame"):
        frame = f"reality_frame={row.get('reality_frame')}"
        if row.get("director"):
            frame += f" director={row.get('director')}"
        bits.append(frame)
    if row.get("dialogue_boundary"):
        bits.append(f"dialogue_boundary={row.get('dialogue_boundary')}")
    try:
        from System.swarm_youtube_watch_memory import latest_watch_context

        watch = latest_watch_context(state_dir=STATE_FILE.parent, max_age_s=max_age_s)
        if watch:
            bits.append(f"watch_memory={watch}")
    except Exception:
        pass
    return " | ".join(bits)


if __name__ == "__main__":
    from System import swarm_active_window as aw

    snap = aw.read(force_refresh=True)
    row = observe_snapshot(snap, force=True)
    print(json.dumps(row or {"ok": False, "reason": "frontmost window is not YouTube"}, indent=2))
