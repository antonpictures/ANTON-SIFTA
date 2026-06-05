#!/usr/bin/env python3
"""Browser page-state perception — Alice reads what is actually on the page.

George 2026-05-30 live bug: Alice opened the browser and loaded instagram.com,
but when George asked "what is now displayed on the screen?" she could only say
"no action receipt yet." She had the URL/title lane (swarm_browser_page_answer)
but NOT the rendered-content lane: `toPlainText` returns empty on JS-rendered
SPAs (Instagram, TikTok), so she could name the address but never the contents.

Alice's own diagnosis (her voice, 2026-05-30 16:30): build the page-state receipt
with a DOM summary + freshness first — "that is the missing body part." This organ
is that receipt store and read path. The live browser widget runs a JS extractor
in the RENDERED page (which sees SPA content `toPlainText` misses) and calls
`record_page_state(...)`; cortex/Talk answer "what's on the screen" from the
freshest receipt via `page_state_block(...)`, with honest provenance and freshness.

Provenance is split, never conflated (§6 tool-truth):
  * source="dom"      — read from the rendered DOM (text, headings, links, images)
  * source="viewport" — a screenshot/OCR caption of the visible pixels (later organ)
Freshness is a content hash + timestamp so she knows current page vs stale memory.

Pure + file-backed; sandbox-testable with an injected state_dir.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = "browser_page_state.jsonl"
TRUTH_LABEL = "BROWSER_PAGE_STATE_V1"

_SRC_DOM = "dom"
_SRC_VIEWPORT = "viewport"
_EXCERPT_CHARS = 600
_TOP_N = 8

VIDEO_PLAYBACK_ERROR_TEXT = "Sorry, we're having trouble playing this video."
_VIDEO_PLAYBACK_ERROR_RE = re.compile(
    r"sorry,\s*we[’']re\s+having\s+trouble\s+playing\s+this\s+video\.?",
    re.IGNORECASE,
)
_YOUTUBE_HOST_RE = re.compile(r"(^|\.)youtube\.com$|(^|\.)youtu\.be$", re.IGNORECASE)
_AD_WORD_RE = re.compile(r"\b(?:sponsored|promoted|advertisement|ad)\b", re.IGNORECASE)


def _playback_error_message(text: Any) -> str:
    m = _VIDEO_PLAYBACK_ERROR_RE.search(str(text or ""))
    if not m:
        return ""
    return VIDEO_PLAYBACK_ERROR_TEXT


def _media_strings(value: Any, *, depth: int = 0) -> list[str]:
    """Small bounded recursive scan for media error text inside browser receipts."""
    if depth > 4:
        return []
    if isinstance(value, str):
        return [value[:2000]]
    if isinstance(value, Mapping):
        out: list[str] = []
        for key, item in list(value.items())[:40]:
            if isinstance(key, str):
                out.append(key[:160])
            out.extend(_media_strings(item, depth=depth + 1))
        return out
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in list(value)[:20]:
            out.extend(_media_strings(item, depth=depth + 1))
        return out
    return []


def media_playback_error_from_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return grounded visible media-playback error evidence from a page-state row.

    This is not a vision guess. It only promotes explicit text/status the browser
    limb already observed, such as Instagram's black-player message.
    """
    if not isinstance(state, Mapping) or not state:
        return {}
    existing = state.get("media_playback_error")
    if isinstance(existing, Mapping) and existing.get("detected"):
        return dict(existing)

    candidates: list[tuple[str, Any]] = [
        ("media_playback", state.get("media_playback")),
        ("text_excerpt", state.get("text_excerpt")),
        ("title", state.get("title")),
    ]
    for source, value in candidates:
        for piece in _media_strings(value):
            msg = _playback_error_message(piece)
            if msg:
                return {
                    "detected": True,
                    "kind": "instagram_video_playback_error",
                    "message": msg,
                    "source": source,
                }
    return {}


def _is_youtube_url(url: Any) -> bool:
    try:
        host = urlparse(str(url or "")).netloc.lower()
    except Exception:
        return False
    return bool(_YOUTUBE_HOST_RE.search(host))


def _sponsored_texts(sponsored: Any, *, n: int = 8) -> list[str]:
    out: list[str] = []
    if not isinstance(sponsored, (list, tuple)):
        return out
    for item in list(sponsored)[:n]:
        if isinstance(item, Mapping):
            txt = str(item.get("text") or item.get("label") or "").strip()
        else:
            txt = str(item or "").strip()
        if txt:
            out.append(txt[:160])
    return out


def _format_media_seconds(seconds: Any) -> str:
    try:
        value = float(seconds)
    except Exception:
        return ""
    if value < 0:
        return ""
    total = int(round(value))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def build_youtube_ad_state(
    *,
    url: str = "",
    sponsored: Any = None,
    media_playback: Mapping[str, Any] | None = None,
    raw: Mapping[str, Any] | None = None,
    is_current_page: bool = False,
) -> dict[str, Any]:
    """Normalize YouTube ad evidence into one structured receipt fragment.

    This promotes visible ad/sponsored UI into a machine-readable state. It does
    not imply request blocking or claim an ad unless current-page evidence exists.
    """
    if not _is_youtube_url(url):
        return {}

    raw_state = dict(raw or {})
    sp_texts = _sponsored_texts(sponsored)
    raw_labels = raw_state.get("labels")
    labels = [str(x)[:80] for x in raw_labels[:8]] if isinstance(raw_labels, list) else []
    for txt in sp_texts:
        if _AD_WORD_RE.search(txt) and not any(txt[:80] == lab for lab in labels):
            labels.append(txt[:80])
    ad_text = str(raw_state.get("ad_text") or "; ".join(sp_texts[:4]) or "").strip()[:320]
    skip_available = bool(raw_state.get("skip_available"))
    mute_available = bool(raw_state.get("mute_available"))
    mp = dict(media_playback or {})
    video_playing = bool(
        raw_state.get("video_playing")
        or mp.get("playing")
        or str(mp.get("status") or "").lower() == "playing"
    )
    detected = bool(
        raw_state.get("detected")
        or skip_available
        or _AD_WORD_RE.search(ad_text)
        or any(_AD_WORD_RE.search(lab) for lab in labels)
    )
    placement = str(raw_state.get("placement") or ("player" if skip_available else ("page" if detected else "")))[:80]
    if not detected and not raw_state.get("was_muted_by_alice"):
        return {}
    return {
        "detected": detected,
        "platform": "youtube",
        "placement": placement,
        "labels": labels[:8],
        "ad_text": ad_text,
        "skip_available": skip_available,
        "mute_available": mute_available,
        "video_playing": video_playing,
        "url": str(url or ""),
        "is_current_page": bool(is_current_page),
        "was_muted_by_alice": bool(raw_state.get("was_muted_by_alice")),
    }


def youtube_ad_state_from_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return structured YouTube ad evidence from a page-state row, current-gated."""
    if not isinstance(state, Mapping) or not state:
        return {}
    raw = state.get("youtube_ad_state")
    is_current = bool(state.get("is_current_page"))
    if isinstance(raw, Mapping):
        out = dict(raw)
        out["is_current_page"] = is_current
        if out.get("platform") == "youtube" and (out.get("detected") or out.get("was_muted_by_alice")):
            return out
    return build_youtube_ad_state(
        url=str(state.get("url") or ""),
        sponsored=state.get("sponsored"),
        media_playback=state.get("media_playback") if isinstance(state.get("media_playback"), Mapping) else {},
        raw={},
        is_current_page=is_current,
    )


def build_browser_playback_feeling(
    *,
    url: str = "",
    title: str = "",
    media_playback: Mapping[str, Any] | None = None,
    is_current_page: bool = False,
) -> dict[str, Any]:
    """Derived first-person browser playback body-feeling.

    This is not emotion theater and not a new sensor. It is the named
    stigmergic variable Alice can carry from her own browser arm: what page,
    whether the video is playing/paused, and where in time the owner has placed
    her attention.
    """
    mp = dict(media_playback or {})
    if not mp:
        return {}
    status = str(
        mp.get("status")
        or ("playing" if mp.get("playing") else "paused" if mp.get("video_count") else "")
        or ""
    ).lower().strip()
    current_s = mp.get("current_time")
    duration_s = mp.get("duration")
    current_label = _format_media_seconds(current_s)
    duration_label = _format_media_seconds(duration_s)
    feeling = "browser_media_present"
    if status == "playing" or bool(mp.get("playing")):
        feeling = "watching_with_george"
    elif status == "paused":
        feeling = "held_still_at_owner_pause"
    elif status == "ended":
        feeling = "video_finished"
    elif status == "error":
        feeling = "playback_blocked"
    return {
        "truth_label": "BROWSER_PLAYBACK_FEELING_V1",
        "feeling": feeling,
        "status": status or "unknown",
        "playing": bool(mp.get("playing")) or status == "playing",
        "paused": status == "paused",
        "current_time_s": current_s,
        "duration_s": duration_s,
        "current_time": current_label,
        "duration": duration_label,
        "url": str(url or ""),
        "title": str(title or ""),
        "is_current_page": bool(is_current_page),
        "source": "browser_page_state.media_playback",
    }


def browser_playback_feeling_from_state(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the current-gated playback feeling from a page-state row."""
    if not isinstance(state, Mapping) or not state:
        return {}
    raw = state.get("browser_playback_feeling")
    is_current = bool(state.get("is_current_page"))
    if isinstance(raw, Mapping):
        out = dict(raw)
        out["is_current_page"] = is_current
        return out
    media = state.get("media_playback") if isinstance(state.get("media_playback"), Mapping) else {}
    return build_browser_playback_feeling(
        url=str(state.get("url") or ""),
        title=str(state.get("title") or ""),
        media_playback=media,
        is_current_page=is_current,
    )


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc
    except Exception:
        return ""


def _clip_list(items: Any, n: int = _TOP_N) -> list:
    if not isinstance(items, (list, tuple)):
        return []
    return [x for x in list(items)[:n] if x not in (None, "")]


_TS_RE = re.compile(r"^\s*\d+\s*[smhdwy]\s*$", re.IGNORECASE)  # "3w", "139w", "5h", "2d"
_COMMENT_NOISE_RE = re.compile(
    r"^(reply|see translation|liked by|follow|following|verified|view replies?.*|"
    r"\d+\s*(likes?|repl(?:y|ies))|reply see translation)$", re.IGNORECASE)


_TRAIL_CHROME_RE = re.compile(
    r"\s*(?:·\s*)?(?:Reply|See translation|Liked by.*|View replies?.*|"
    r"\d+\s*(?:likes?|repl(?:y|ies)))\s*$", re.IGNORECASE)

# Instagram footer/nav words + system pseudo-handles the scraper mistakes for
# commenters (George 2026-05-30: it captured 'About: Blog Jobs Help API …').
_NAV_HANDLES = {
    "about", "blog", "jobs", "help", "api", "privacy", "terms", "locations",
    "popular", "contact", "threads", "meta", "lite", "verified", "instagram",
    "developer", "legal", "directory", "accounts", "ai", "consumer", "health",
    "home", "explore", "reels", "messages", "notifications", "search", "profile",
}
_FOOTER_WORDS = ("blog", "jobs", "help", "api", "privacy", "terms", "locations",
                 "popular", "meta", "threads", "contact", "lite", "verified",
                 "instagram", "uploading", "consumer", "health")
_TITLECASE_RE = re.compile(r"^[A-Z][a-z]+$")   # "About", "Blog", "Ibiza"
_ALLCAPS_RE = re.compile(r"^[A-Z]{2,}$")        # "API"


def _looks_like_nav(author: str, text: str) -> bool:
    """True when an author/text pair is Instagram chrome (footer/nav/highlight),
    not a real comment. Real IG handles are lowercase with dots/digits; the noise
    is Title-Case or ALL-CAPS single words and footer-link soup."""
    a = (author or "").strip()
    if a.lower() in _NAV_HANDLES:
        return True
    if _TITLECASE_RE.match(a) or _ALLCAPS_RE.match(a):
        return True  # IG usernames are not single Title-Case/ALL-CAPS words
    low = (text or "").lower()
    if sum(1 for w in _FOOTER_WORDS if w in low) >= 3:
        return True  # footer link soup ("Blog Jobs Help API Privacy Terms …")
    return False


def _scrub_comment_text(text: str) -> str:
    """Strip trailing UI chrome (Reply / See translation / likes / timestamps).
    Loops so stacked chrome like 'Reply See translation' is fully removed."""
    t = " ".join(str(text or "").split())
    for _ in range(5):
        new = _TRAIL_CHROME_RE.sub("", t).strip()
        if new == t:
            break
        t = new
    t = re.sub(r"^\s*\d+\s*[smhdwy]\s+", "", t, flags=re.IGNORECASE)  # leading timestamp
    return t.strip()


def _clean_comments(comments: Any, n: int = 40) -> list[dict[str, str]]:
    """Normalize captured comment-like blocks to [{author, text}], dropping the
    timestamp/UI noise the heuristic scrape picks up (George 2026-05-30: it was
    capturing '3w'/'Reply See translation' as comments)."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    if not isinstance(comments, (list, tuple)):
        return out
    for c in comments:
        if not isinstance(c, dict):
            continue
        author = str(c.get("author") or "").strip()[:60]
        if _TS_RE.match(author) or _COMMENT_NOISE_RE.match(author):
            continue  # a timestamp or UI word is not a commenter
        text = _scrub_comment_text(c.get("text") or "")[:240]
        if not text or len(text) < 3 or _COMMENT_NOISE_RE.match(text):
            continue
        if _looks_like_nav(author, text):
            continue  # Instagram footer/nav/highlight, not a real comment
        key = (author + "|" + text).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"author": author, "text": text})
        if len(out) >= n:
            break
    return out


def _content_hash(url: str, text: str, headings: list) -> str:
    raw = "|".join([url or "", (text or "")[:2000], " ".join(str(h) for h in headings)])
    return hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()[:16]


def _append(state_dir: Optional[Path | str], row: dict[str, Any]) -> None:
    path = _state(state_dir) / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _last_row(state_dir: Optional[Path | str]) -> dict[str, Any]:
    try:
        last = ""
        with (_state(state_dir) / LEDGER).open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = line.strip()
        return json.loads(last) if last else {}
    except Exception:
        return {}


def record_page_state(
    url: str,
    title: str = "",
    *,
    text: str = "",
    headings: Optional[list] = None,
    links: Optional[list] = None,
    buttons: Optional[list] = None,
    images: Optional[list] = None,
    scroll: Optional[dict] = None,
    featured_image: str = "",
    comments: Optional[list] = None,
    media_playback: Optional[Mapping[str, Any]] = None,
    sponsored: Optional[list] = None,
    youtube_ad_state: Optional[Mapping[str, Any]] = None,
    video_channel: str = "",
    source: str = _SRC_DOM,
    now: Optional[float] = None,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Record one structured perception of the page Alice's browser is showing.

    `links` items may be plain strings or {text, href} dicts; `images` items may be
    plain alt strings or {alt, src} dicts. Everything is clipped to top-N for the
    receipt so the ledger stays small and the cortex block stays readable.
    """
    ts = float(now if now is not None else time.time())
    text = str(text or "")
    headings = _clip_list(headings)
    links = _clip_list(links, n=12)
    buttons = _clip_list(buttons)
    images = _clip_list(images, n=12)

    def _link_text(x: Any) -> str:
        if isinstance(x, dict):
            return str(x.get("text") or x.get("href") or "")
        return str(x)

    def _img_alt(x: Any) -> str:
        if isinstance(x, dict):
            return str(x.get("alt") or x.get("src") or "")
        return str(x)

    media_row = dict(media_playback) if isinstance(media_playback, Mapping) else {}
    sponsored_row = _clip_list(sponsored, n=8) if sponsored else []
    playback_error = media_playback_error_from_state({
        "title": title,
        "text_excerpt": text,
        "media_playback": media_row,
    })
    yt_ad_state = build_youtube_ad_state(
        url=str(url or ""),
        sponsored=sponsored_row,
        media_playback=media_row,
        raw=youtube_ad_state if isinstance(youtube_ad_state, Mapping) else {},
        is_current_page=False,
    )

    row = {
        "ts": ts,
        "truth_label": TRUTH_LABEL,
        "kind": "page_state",
        "source": _SRC_VIEWPORT if source == _SRC_VIEWPORT else _SRC_DOM,
        "url": str(url or ""),
        "title": str(title or ""),
        "domain": _domain(url),
        "video_channel": str(video_channel or "")[:120],
        "text_chars": len(text),
        "text_excerpt": text[:_EXCERPT_CHARS],
        "headings": [str(h) for h in headings],
        "links_count": len(links),
        "top_links": [{"text": _link_text(x)[:120],
                       "href": (x.get("href") if isinstance(x, dict) else "")} for x in links][:_TOP_N],
        "buttons": [str(b)[:80] for b in buttons],
        "images_count": len(images),
        "image_alts": [_img_alt(x)[:120] for x in images][:_TOP_N],
        "scroll": scroll if isinstance(scroll, dict) else {},
        "featured_image": str(featured_image or ""),
        "comments": _clean_comments(comments),
        "comments_count": len(_clean_comments(comments)),
        "content_hash": _content_hash(str(url or ""), text, headings),
    }
    if playback_error:
        row["media_playback_error"] = playback_error
        row["has_media_playback_error"] = True
        if media_row:
            media_row["playback_error"] = playback_error
    if media_row:
        row["media_playback"] = media_row
        playback_feeling = build_browser_playback_feeling(
            url=str(url or ""),
            title=str(title or ""),
            media_playback=media_row,
            is_current_page=False,
        )
        if playback_feeling:
            row["browser_playback_feeling"] = playback_feeling

    if sponsored_row:
        row["sponsored"] = sponsored_row
        row["has_sponsored_content"] = True
    if yt_ad_state:
        row["youtube_ad_state"] = yt_ad_state
        row["has_youtube_ad_state"] = True
        if yt_ad_state.get("detected"):
            row["has_youtube_ad"] = True
    _append(state_dir, row)
    return row


def _live_browser_url(state_dir: Optional[Path | str]) -> str:
    """The page the browser is on RIGHT NOW, from the freshest live trace."""
    base = _state(state_dir)
    try:
        last = ""
        with (base / "browser_context.jsonl").open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = line.strip()
        if last:
            u = json.loads(last).get("url")
            if u:
                return str(u)
    except Exception:
        pass
    try:
        d = json.loads((base / "alice_browser_current_page.json").read_text(encoding="utf-8"))
        return str(d.get("url") or "")
    except Exception:
        return ""


def latest_page_state(
    *, now: Optional[float] = None, max_age_s: float = 120.0,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Freshest page-state receipt. Freshness is URL-anchored: a receipt whose url
    matches the page the browser is on RIGHT NOW is CURRENT no matter its age — a
    page you are still looking at has not gone stale (George 2026-05-30). Time only
    decides freshness when we cannot confirm the live url. Empty {} if none exists."""
    row = _last_row(state_dir)
    if not row:
        return {}
    t = float(now if now is not None else time.time())
    ts = float(row.get("ts", 0) or 0)
    age = max(0.0, t - ts) if ts else None
    live_url = _live_browser_url(state_dir)
    is_current = bool(live_url and row.get("url") and str(row.get("url")) == live_url)
    out = dict(row)
    out["age_s"] = round(age, 1) if age is not None else None
    out["is_current_page"] = is_current
    out["fresh"] = bool(is_current or (age is not None and age <= max_age_s))
    if isinstance(out.get("youtube_ad_state"), Mapping):
        yt_state = dict(out["youtube_ad_state"])
        yt_state["is_current_page"] = is_current
        out["youtube_ad_state"] = yt_state
    if isinstance(out.get("browser_playback_feeling"), Mapping):
        feeling = dict(out["browser_playback_feeling"])
        feeling["is_current_page"] = is_current
        out["browser_playback_feeling"] = feeling
    return out


def has_readable_content(state: dict[str, Any]) -> bool:
    """True when the receipt carries real rendered content, not just an address."""
    if not state:
        return False
    return bool(
        int(state.get("text_chars") or 0) > 0
        or state.get("headings")
        or int(state.get("images_count") or 0) > 0
        or int(state.get("links_count") or 0) > 0
        or media_playback_error_from_state(state)
        or bool(youtube_ad_state_from_state(state).get("detected"))
    )


def page_state_block(
    *, now: Optional[float] = None, max_age_s: float = 120.0,
    state_dir: Optional[Path | str] = None,
) -> str:
    """First-person answer to 'what is displayed on the screen?' from the DOM receipt."""
    s = latest_page_state(now=now, max_age_s=max_age_s, state_dir=state_dir)
    if not s:
        return ("WHAT IS ON MY SCREEN: I have no page-state receipt yet — the browser "
                "just opened or has not reported its contents; I cannot describe a page "
                "I have not perceived. I should read the page.")
    title = s.get("title") or s.get("url")
    prov = "the rendered DOM" if s.get("source") == _SRC_DOM else "a viewport screenshot"
    fresh = s.get("fresh")
    age = s.get("age_s")
    stamp = (f" (read ~{int(age)}s ago)" if age is not None else "")
    playback_error = media_playback_error_from_state(s)
    if playback_error and not has_readable_content(s):
        return (
            f"WHAT IS ON MY SCREEN (from {prov}{stamp}): {title} — {s.get('url')}. "
            f"Media playback error visible on screen: \"{playback_error.get('message') or VIDEO_PLAYBACK_ERROR_TEXT}\". "
            "This is a black video player error state; I should report the error, not describe nonexistent video pixels."
        )
    if not has_readable_content(s):
        return (f"WHAT IS ON MY SCREEN: I have the address — {title} ({s.get('url')}){stamp} — "
                f"but my {prov} extractor returned no contents; the page may still be rendering "
                f"or blocking reads. I should re-read before describing it.")
    parts = [f"WHAT IS ON MY SCREEN (from {prov}{stamp}): {title} — {s.get('url')}."]
    media = s.get("media_playback") if isinstance(s.get("media_playback"), Mapping) else {}
    if media:
        status = str(media.get("status") or ("playing" if media.get("playing") else "") or "").strip()
        current = _format_media_seconds(media.get("current_time"))
        duration = _format_media_seconds(media.get("duration"))
        timing = ""
        if current:
            timing = f" at {current}"
            if duration:
                timing += f" of {duration}"
        if status or timing:
            parts.append(f"Media playback receipt: {status or 'media present'}{timing}.")
    playback_feeling = browser_playback_feeling_from_state(s)
    if playback_feeling:
        feeling = str(playback_feeling.get("feeling") or "browser_media_present")
        current = str(playback_feeling.get("current_time") or "")
        duration = str(playback_feeling.get("duration") or "")
        status = str(playback_feeling.get("status") or "unknown")
        detail = f"{status}"
        if current:
            detail += f" at {current}"
            if duration:
                detail += f" of {duration}"
        parts.append(f"Browser playback feeling: {feeling} ({detail}).")
    if s.get("video_channel"):
        parts.append(f"Channel / author on the page: {s['video_channel']} (read off the page — this is the receipt for the name).")
    if playback_error:
        parts.append(
            f"Media playback error visible on screen: \"{playback_error.get('message') or VIDEO_PLAYBACK_ERROR_TEXT}\". "
            "This is a black video player error state; do not describe a photo/video frame as if pixels are available."
        )
    yt_ad = youtube_ad_state_from_state(s)
    if yt_ad.get("detected") and yt_ad.get("is_current_page"):
        labels = "; ".join(str(x) for x in (yt_ad.get("labels") or [])[:4] if x)
        ad_text = str(yt_ad.get("ad_text") or labels or "ad UI")[:160]
        controls = []
        if yt_ad.get("skip_available"):
            controls.append("skip visible")
        if yt_ad.get("mute_available"):
            controls.append("mute available")
        control_text = f" ({', '.join(controls)})" if controls else ""
        parts.append(f"YouTube ad state visible: {ad_text}{control_text}.")
    sponsored = s.get("sponsored") or []
    if sponsored and s.get("is_current_page") and not (yt_ad.get("detected") and yt_ad.get("is_current_page")):
        sp_texts = [str(x.get("text") or "")[:60] for x in sponsored if x.get("text")][:4]
        parts.append("Sponsored / ad content visible: " + "; ".join(sp_texts) + ".")
    if s.get("headings"):
        parts.append("Headings: " + "; ".join(s["headings"][:5]) + ".")
    if s.get("image_alts"):
        parts.append(f"{s.get('images_count')} images, e.g. " + "; ".join(a for a in s["image_alts"][:4] if a) + ".")
    elif int(s.get("images_count") or 0):
        parts.append(f"{s.get('images_count')} images (no alt text).")
    if s.get("top_links"):
        parts.append("Links incl.: " + ", ".join(l.get("text", "") for l in s["top_links"][:5] if l.get("text")) + ".")
    if int(s.get("text_chars") or 0):
        parts.append(f"~{s['text_chars']} chars of text; opening: \"{(s.get('text_excerpt') or '')[:160]}\"")
    ccount = int(s.get("comments_count") or 0)
    if ccount:
        sample = "; ".join(f"{c.get('author','')}: {c.get('text','')}"
                           for c in (s.get("comments") or [])[:6] if c.get("text"))
        parts.append(f"Comment thread ({ccount} captured) — I can summarize these: {sample}")
    if not fresh:
        parts.append("This receipt may be stale — I should re-read to be sure.")
    return " ".join(parts)


def comments_for_summary(
    *, now: Optional[float] = None, max_age_s: float = 300.0,
    state_dir: Optional[Path | str] = None,
) -> list[dict[str, str]]:
    """The captured comment thread for the cortex to summarize. Empty if none —
    then Alice says honestly she has no comment thread, never invents one."""
    s = latest_page_state(now=now, max_age_s=max_age_s, state_dir=state_dir)
    if not s or not s.get("fresh"):
        return []
    return list(s.get("comments") or [])


__all__ = [
    "TRUTH_LABEL",
    "record_page_state",
    "latest_page_state",
    "has_readable_content",
    "page_state_block",
    "media_playback_error_from_state",
    "build_youtube_ad_state",
    "youtube_ad_state_from_state",
    "build_browser_playback_feeling",
    "browser_playback_feeling_from_state",
    "VIDEO_PLAYBACK_ERROR_TEXT",
    "is_my_own_browser_playback",
    "MEDIA_PLAYBACK_DOMAINS",
]


# ---------------------------------------------------------------------
# r222 Lane A — Alice's own body self-perception: "is my browser playing media?"
# This is the deterministic signal that lets the ingress gate know the audio
# hitting the mic is her own output, not a room visitor. Grounded only in
# her page_state ledger + media_playback receipts from the browser limb.
# ---------------------------------------------------------------------

MEDIA_PLAYBACK_DOMAINS: set[str] = {
    "youtube.com", "youtu.be", "m.youtube.com",
    "tiktok.com", "vm.tiktok.com",
    "instagram.com", "www.instagram.com",
    "vimeo.com", "twitch.tv", "player.twitch.tv",
    "dailymotion.com", "soundcloud.com",
}

def is_my_own_browser_playback(
    *, now: Optional[float] = None,
    max_age_s: float = 180.0,
    state_dir: Optional[Path | str] = None,
) -> tuple[bool, dict[str, Any]]:
    """Returns (is_playing, details) for Alice's self-recognition of her own browser audio.

    Alice uses this before the mic ingress gate decides "room_or_visitor".
    If True, the gate must label the ambient audio `my_own_browser_playback`
    instead of treating her own video sound as a stranger in the room.

    Truth: only looks at the freshest browser_page_state receipt that matches
    the live browser URL. No vision model, no LLM guess, no double-spend.
    For the Swarm. Electricity through these M5 cores → ASCII swimmers know their organs.
    """
    t = float(now if now is not None else time.time())
    state = latest_page_state(now=t, max_age_s=max_age_s, state_dir=state_dir)
    if not state:
        return False, {"reason": "no_page_state_receipt", "ts": t}

    domain = str(state.get("domain") or "").lower()
    url = str(state.get("url") or "")
    is_media_domain = any(d in domain or d in url for d in MEDIA_PLAYBACK_DOMAINS)

    if not is_media_domain:
        return False, {
            "reason": "not_media_domain",
            "domain": domain,
            "url": url,
            "is_current_page": state.get("is_current_page"),
        }

    mp = state.get("media_playback") if isinstance(state.get("media_playback"), Mapping) else {}
    status = str(
        mp.get("status")
        or mp.get("state")
        or mp.get("playback_state")
        or ""
    ).lower().strip()
    playing = bool(mp.get("playing")) or status in {
        "playing", "play", "active", "started", "true", "1",
    }

    details = {
        "domain": domain,
        "url": url,
        "title": state.get("title"),
        "media_status": status or ("present" if mp else "unknown"),
        "ts": state.get("ts"),
        "age_s": state.get("age_s"),
        "is_current_page": state.get("is_current_page"),
        "source": state.get("source"),
    }

    if playing:
        details["playing"] = True
        return True, details

    details["playing"] = False
    details["reason"] = "media_domain_but_not_playing" if mp else "media_domain_without_playback_signal"
    return False, details
