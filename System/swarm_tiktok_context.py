#!/usr/bin/env python3
"""TikTok context organ — Alice's truthful awareness of the open TikTok page.

George 2026-05-30: "is she aware we are on TikTok... talk about what page is
open on TikTok and, when asked, describe the specific TikTok video." This is
the Cowork lane (Lane A) of WISH_012. It mirrors `swarm_youtube_context`: it
turns Alice Browser's current-page snapshot into a compact, truthful context
string for her cortex prompt.

The honest hard part (George: "I know it's hard")
-------------------------------------------------
TikTok video pixels are NOT machine-readable here: the clip is login-walled and
often does not render in the embedded browser (the live snapshot showed
"We're having trouble playing this video"). So Alice CANNOT see the moving
content. What she CAN ground (§6 hallucination immunity / §7.2 tool-truth):

  * the page IS TikTok (domain),
  * which video (author handle + numeric video id from the URL),
  * the caption / title the page exposes,
  * whether the player rendered,
  * visible "You may like" recommendation handles from the page text.

When asked to "describe the TikTok video", Alice must describe from THIS
evidence and explicitly say she is not seeing the video frames — unless a
separate vision lane (screen-frame capture) supplies pixels. Never invent the
video's content.

Pure parser (`parse_tiktok_snapshot`) is sandbox-testable with a snapshot dict;
`get_latest_context` reads the real `alice_browser_current_page.json`.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
PAGE_SNAPSHOT = STATE_DIR / "alice_browser_current_page.json"

TRUTH_LABEL = "TIKTOK_CONTEXT_V1"

_AUTHOR_RE = re.compile(r"tiktok\.com/@([A-Za-z0-9._-]+)", re.IGNORECASE)
_VIDEO_ID_RE = re.compile(r"/video/(\d+)")
_PLAYER_FAIL_RE = re.compile(r"trouble playing|please refresh|video unavailable", re.IGNORECASE)


def _is_tiktok(url: str, domain: str) -> bool:
    blob = f"{url} {domain}".lower()
    return "tiktok.com" in blob


def _clean_caption(title: str) -> str:
    """Take the human caption out of a TikTok page title.

    Titles look like 'nighttime yoga🧘💕 | yoga | TikTok' — the first
    pipe-segment is the caption; the rest is tags + the site name.
    """
    t = (title or "").strip()
    if not t:
        return ""
    head = t.split("|")[0].strip()
    return head or t


def _recommendation_handles(text: str) -> list[str]:
    """Best-effort: visible @handles in the page text (e.g. 'You may like')."""
    out: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"@([A-Za-z0-9._-]{2,30})", text or ""):
        h = "@" + m.group(1)
        if h.lower() not in seen:
            seen.add(h.lower())
            out.append(h)
    return out[:6]


def parse_tiktok_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Parse an ALICE_BROWSER_PAGE_TEXT_V1 snapshot into TikTok context.

    Returns {"is_tiktok": bool, ...}. Pure and deterministic.
    """
    url = str((snapshot or {}).get("url") or "")
    title = str((snapshot or {}).get("title") or "")
    domain = str((snapshot or {}).get("domain") or "")
    text = str((snapshot or {}).get("text") or "")

    if not _is_tiktok(url, domain):
        return {"is_tiktok": False}

    author_m = _AUTHOR_RE.search(url)
    vid_m = _VIDEO_ID_RE.search(url)
    player_rendered = not bool(_PLAYER_FAIL_RE.search(text) or _PLAYER_FAIL_RE.search(title))

    return {
        "is_tiktok": True,
        "author": ("@" + author_m.group(1)) if author_m else "",
        "video_id": vid_m.group(1) if vid_m else "",
        "caption": _clean_caption(title),
        "player_rendered": player_rendered,
        "recommendation_handles": _recommendation_handles(text),
        "url": url,
    }


def build_tiktok_context(snapshot: dict[str, Any]) -> str:
    """Compact, truthful one-line context for Alice's prompt, with the §6
    boundary baked in. Returns '' when the page is not TikTok."""
    ctx = parse_tiktok_snapshot(snapshot)
    if not ctx.get("is_tiktok"):
        return ""
    bits = ["TikTok page open in Alice Browser"]
    if ctx.get("author"):
        bits.append(f"author={ctx['author']}")
    if ctx.get("video_id"):
        bits.append(f"video_id={ctx['video_id']}")
    if ctx.get("caption"):
        bits.append(f"caption={ctx['caption']!r}")
    bits.append("player_rendered=" + ("yes" if ctx["player_rendered"] else "no"))
    recs = ctx.get("recommendation_handles") or []
    if recs:
        bits.append("you_may_like=" + ",".join(recs))
    # §6 boundary — Alice describes from metadata, NOT video frames.
    bits.append(
        "DESCRIBE-BOUNDARY: I can name the author, caption, id and visible page "
        "text, but I am not seeing the video's moving frames (login-walled / not "
        "a readable pixel source). Say so; do not invent the clip's content."
    )
    return " | ".join(bits)


def get_latest_context(
    max_age_s: float = 600.0, *, snapshot_path: Optional[Path | str] = None
) -> Optional[str]:
    """Read the live Alice Browser page snapshot; if it is TikTok and fresh,
    return the truthful context string, else None."""
    path = Path(snapshot_path) if snapshot_path is not None else PAGE_SNAPSHOT
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(row, dict):
        return None
    if time.time() - float(row.get("ts", 0) or 0) > max_age_s:
        return None
    return build_tiktok_context(row) or None


__all__ = [
    "TRUTH_LABEL",
    "parse_tiktok_snapshot",
    "build_tiktok_context",
    "get_latest_context",
]
