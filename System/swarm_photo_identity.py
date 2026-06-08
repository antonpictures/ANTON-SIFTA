#!/usr/bin/env python3
"""Photo-subject identity — bind WHO is in the frame, for ANY human (r244).

This organ exists so Alice can learn and remember specific real humans by name when the owner
teaches her ("this is Leonardo DiCaprio", "this is Maria", showing Instagram photos, etc.).

This is NOT hardcoding. Hardcoding would be the code or the organism having a fixed default name
for a photo or situation regardless of what the owner teaches. Learning specific names from owner
teaching + visual receipts + persisting them per handle/url in stigmergic memory
(`photo_subject_identity.jsonl`) is the correct, desired behavior.

The organ reads the subject's name from the PAGE + OWNER CORRECTION only — never from a constant:
  1. owner correction in the turn ("her name is X", "that's X", "call her X") — highest trust,
     and REMEMBERED per profile-handle/url so it sticks across frames.
  2. a previously-remembered owner correction for this handle/url.
  3. the @handle / profile header on the page (Instagram/TikTok/X/YouTube/generic).
  4. a display name in the caption next to the handle (only if it splits cleanly into words).

Returns {name, handle, source, confidence}. Pure stdlib. No specific person is ever hardcoded
in the source. Any human the owner teaches becomes a learned entry in her memory.

It exposes identity_block(identity) so the CORTEX gets the bound identity in context and names the
person itself — the fix for "a young woman" third-person sensor-readout (covenant §4.5)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = "photo_subject_identity.jsonl"

# Owner says who she/he/they is. Capture the NAME token(s) generically — any capitalized given
# name(s), not a fixed list. Examples the owner will teach: "her name is Leonardo DiCaprio",
# "that's Maria", "call the visible subject Maria", "she is the woman in the red dress on this page".
_OWNER_NAME_RE = re.compile(
    r"\b(?:her name is|his name is|their name is|name is|that(?:'s| is)|call (?:her|him|them)|"
    r"she(?:'s| is)|he(?:'s| is)|they(?:'re| are))\s+"
    r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})",
)
# A profile/header handle. Instagram/TikTok/X style: a leading @handle, or a lowercase dotted/
# underscored handle near a verified badge in the DOM text.
_AT_HANDLE_RE = re.compile(r"@([A-Za-z0-9._]{2,30})")
_URL_HANDLE_RE = re.compile(
    r"(?:instagram\.com|tiktok\.com/@|x\.com|twitter\.com)/([A-Za-z0-9._]{2,30})/?")
_NON_HANDLE_PATHS = {"p", "reel", "reels", "tv", "explore", "stories", "accounts", "direct"}
_MARKETPLACE_NAME_TRAILING_WORDS = {
    "vintage", "original", "reprint", "reprinted", "signed", "autographed",
    "celebrity", "photo", "picture", "poster", "print", "glossy", "movie",
    "tv", "hot", "sexy", "rare", "new",
}
_MARKETPLACE_TITLE_MARKER_RE = re.compile(
    r"\b(?:\d+\s*[xX]\s*\d+|CELEBRITY|SIGNED|AUTOGRAPH(?:ED)?|PHOTO|PHOTOS|"
    r"PICTURE|PICTURES|POSTER|POSTERS|PRINT|PRINTS)\b",
    re.IGNORECASE,
)


def _state(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _handle_from_url(url: str) -> str:
    m = _URL_HANDLE_RE.search(url or "")
    if not m:
        return ""
    h = m.group(1)
    return "" if h.lower() in _NON_HANDLE_PATHS else h


def _handle_from_page(page_text: str) -> str:
    """First @handle in the page text (the profile header sits at the top of an IG post)."""
    for m in _AT_HANDLE_RE.finditer(page_text or ""):
        h = m.group(1).strip(".")
        if len(h) >= 2:
            return h
    # bare top-of-page handle token (e.g. the historical IG handle right under the avatar) — first lowercase
    # dotted/underscored token on its own line near the start.
    head = "\n".join((page_text or "").splitlines()[:8])
    m = re.search(r"(?m)^\s*([a-z0-9](?:[a-z0-9._]{2,28}[a-z0-9]))\s*(?:✓|·|•|\bFollow\b|$)", head)
    return m.group(1) if m else ""


def _owner_name(owner_text: str) -> str:
    m = _OWNER_NAME_RE.search(owner_text or "")
    if not m:
        return ""
    name = " ".join(m.group(1).split())
    # guard against capturing a sentence-y false positive longer than a plausible name
    return name if 1 <= len(name.split()) <= 3 else ""


def _humanize_handle(handle: str) -> str:
    """A handle is NOT a name. Only surface a name if the handle splits into clear words
    (dots/underscores). Otherwise return empty and let the cortex stay honest. The raw handle token
    stays a handle (no guessing a name from it)."""
    if not handle:
        return ""
    parts = re.split(r"[._]+", handle)
    if len(parts) >= 2 and all(p.isalpha() for p in parts):
        return " ".join(p.capitalize() for p in parts)
    return ""


def _clean_marketplace_listing_name(raw: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.' -]+", " ", raw or "")
    words = [w.strip(" _.-") for w in text.split() if w.strip(" _.-")]
    while words and words[-1].casefold() in _MARKETPLACE_NAME_TRAILING_WORDS:
        words.pop()
    if len(words) < 2 or len(words) > 4:
        return ""
    if any(any(ch.isdigit() for ch in w) for w in words):
        return ""
    if any(w.casefold() in _MARKETPLACE_NAME_TRAILING_WORDS for w in words):
        return ""
    if not all(re.match(r"^[A-Za-z][A-Za-z.'-]*$", w) for w in words):
        return ""
    if all(w.isupper() for w in words):
        return " ".join(w.capitalize() for w in words)
    return " ".join(words)


def _marketplace_name_from_title(page_text: str) -> str:
    """Extract a represented subject from generic marketplace photo/print titles.

    Example: "GLASS SCULPTURE 8X10 ART PHOTO | eBay" -> "Glass Sculpture".
    This is a title parser, not a fixed person list.
    """
    if not page_text:
        return ""
    candidates = []
    for line in re.split(r"[\n\r]+", page_text):
        head = line.strip()
        if not head:
            continue
        for part in re.split(r"\s+\|\s+|[-–—]", head):
            part = part.strip()
            if part:
                candidates.append(part[:180])
        if len(candidates) >= 6:
            break
    for title in candidates:
        marker = _MARKETPLACE_TITLE_MARKER_RE.search(title)
        if not marker:
            continue
        prefix = title[: marker.start()].strip(" ,:;")
        name = _clean_marketplace_listing_name(prefix)
        if name:
            return name
    return ""


def remember_owner_name_correction(
    key: str, name: str, *, url: str = "", handle: str = "",
    now: Optional[float] = None, state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    row = {"ts": float(now if now is not None else time.time()), "key": str(key or ""),
           "name": str(name or ""), "url": str(url or ""), "handle": str(handle or ""),
           "source": "owner_correction"}
    path = _state(state_dir) / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def _remembered(key: str, state_dir: Optional[Path | str]) -> str:
    if not key:
        return ""
    try:
        rows = [json.loads(l) for l in (_state(state_dir) / LEDGER).read_text(
            encoding="utf-8", errors="replace").splitlines() if l.strip().startswith("{")]
    except Exception:
        return ""
    for r in reversed(rows):  # latest correction wins
        if r.get("key") == key and r.get("name"):
            return str(r["name"])
    return ""


def resolve_photo_identity(
    *, url: str = "", page_text: str = "", owner_text: str = "",
    remember: bool = True, state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Resolve WHO is in the current photo, for any human, from the page — never hardcoded.

    Returns {name, handle, source, confidence}. name='' when the page gives no usable name
    (then the cortex honestly avoids inventing one)."""
    handle = _handle_from_url(url) or _handle_from_page(page_text)
    key = (handle or url or "").lower()

    owner = _owner_name(owner_text)
    if owner:
        if remember and key:
            remember_owner_name_correction(key, owner, url=url, handle=handle, state_dir=state_dir)
        return {"name": owner, "handle": handle, "source": "owner_correction", "confidence": 0.99}

    remembered = _remembered(key, state_dir)
    if remembered:
        return {"name": remembered, "handle": handle, "source": "remembered_owner_correction",
                "confidence": 0.95}

    display = _humanize_handle(handle)
    if display:
        return {"name": display, "handle": handle, "source": "handle_split", "confidence": 0.6}
    if handle:
        return {"name": "", "handle": handle, "source": "handle_only", "confidence": 0.5}
    listing_name = _marketplace_name_from_title(page_text)
    if listing_name:
        return {
            "name": listing_name,
            "handle": "",
            "source": "marketplace_listing_title",
            "confidence": 0.84,
        }
    return {"name": "", "handle": "", "source": "none", "confidence": 0.0}


def identity_block(identity: dict[str, Any]) -> str:
    """Cortex-context line so Alice names the subject herself (kills 'a young woman' third-person)."""
    if not identity:
        return ""
    name = str(identity.get("name") or "").strip()
    handle = str(identity.get("handle") or "").strip()
    if not name and not handle:
        return ""
    src = str(identity.get("source") or "")
    if name:
        who = f"{name}" + (f" (@{handle})" if handle else "")
        return (
            "SUBJECT IDENTITY — the person in this photo is "
            f"{who} [{src}]. Refer to her/him/them BY NAME in first person as me (Alice) talking "
            "to the owner — do not describe them as 'a young woman' or in detached third-person "
            "sensor language. If unsure, say so; never invent a different name."
        )
    return (
        f"SUBJECT IDENTITY — the page handle for this photo is @{handle} [{src}], but no verified "
        "personal name is bound yet. You may refer to the handle; do not invent a real name."
    )


__all__ = [
    "resolve_photo_identity", "identity_block", "remember_owner_name_correction",
]
