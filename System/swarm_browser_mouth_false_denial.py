#!/usr/bin/env python3
"""swarm_browser_mouth_false_denial.py — r1621-01 glass: mouth denied open IG post.

George 2026-07-11: page-context receipt was live (url + image_alts + comments on
disk) but cortex still said "I don't have direct access to your screen."

That is weight mythology, not body truth. When a live browser receipt exists and
the mouth denies the limb, replace with a receipt-grounded description.

**No people/handles hardcoded.** Captions and names come only from the current
page-state row (image_alts, comments, url). Whatever is on screen is what is spoken.

Teach not gag: we only rewrite *false* limb denials, not honest "pixels missing".

Truth label: BROWSER_MOUTH_FALSE_DENIAL_V1
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

TRUTH_LABEL = "BROWSER_MOUTH_FALSE_DENIAL_V1"

_DENY_RE = re.compile(
    r"(?:"
    r"don'?t have (?:direct )?access to (?:your |the )?screen|"
    r"can(?:not|'?t) see (?:the )?(?:instagram|page|post|screen|photo|image)|"
    r"no (?:direct )?access to (?:your |the )?(?:screen|device|browser)|"
    r"I (?:do not|don'?t) have (?:a |any )?(?:browser|screen|live)|"
    r"cannot see (?:what'?s|what is) on (?:your|the) (?:screen|device)|"
    r"paste (?:me )?(?:a |the )?(?:link|url|screenshot)|"
    r"need you to (?:describe|send|share|paste)|"
    r"I(?:'m| am) (?:just )?a (?:language model|text[- ]only)|"
    r"as an AI(?: language model)?(?:,)? I (?:can'?t|cannot) (?:see|view|access)"
    r")",
    re.IGNORECASE,
)

_OWNER_DESC_RE = re.compile(
    r"\b(?:describe|what'?s\s+in|what\s+is\s+in|what\s+do\s+you\s+see|"
    r"on\s+screen|the\s+photo|instagram\s+post|the\s+post|the\s+page)\b",
    re.IGNORECASE,
)


def is_browser_limb_denial(text: str) -> bool:
    return bool(_DENY_RE.search(str(text or "")))


def is_owner_describe_browser_turn(text: str) -> bool:
    return bool(_OWNER_DESC_RE.search(str(text or "")))


def _clean_alt(alt: str) -> str:
    a = " ".join(str(alt or "").split())
    if not a or a.startswith("http"):
        return ""
    if "profile picture" in a.lower():
        return ""
    # Drop pure chrome
    if a.lower() in {"meta", "about", "blog", "jobs", "help", "api"}:
        return ""
    return a[:320]


def grounded_post_description_from_state(state: Mapping[str, Any]) -> str:
    """Build a short honest mouth line from page-state receipts (no invent)."""
    if not isinstance(state, Mapping) or not state:
        return ""
    url = str(state.get("url") or state.get("current_url") or "").strip()
    title = str(state.get("title") or "").strip()
    try:
        domain = urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        domain = ""

    alts = []
    for a in state.get("image_alts") or []:
        c = _clean_alt(str(a))
        if c and c not in alts:
            alts.append(c)
        if len(alts) >= 3:
            break

    comments = []
    for c in state.get("comments") or []:
        if not isinstance(c, dict):
            continue
        author = str(c.get("author") or "").strip()
        text = str(c.get("text") or "").strip()
        if text:
            comments.append(f"{author}: {text}" if author else text)
        if len(comments) >= 3:
            break

    media = state.get("media_playback") or {}
    media_note = ""
    if isinstance(media, dict):
        paused = media.get("paused")
        cur = media.get("current_time") or media.get("currentTime")
        dur = media.get("duration")
        if paused is not None or dur:
            media_note = (
                f" Media receipt: "
                f"{'paused' if paused else 'playing'}"
                f"{f' at {cur}' if cur is not None else ''}"
                f"{f' of {dur}' if dur else ''}."
            )

    bits = []
    if url:
        bits.append(f"My Alice Browser limb is open on {url}.")
    elif domain:
        bits.append(f"My Alice Browser is on {domain}.")
    else:
        bits.append("My Alice Browser has a live page-state receipt.")

    if alts:
        bits.append(
            "From the rendered page evidence (image alt/caption text on the post), "
            f"I have: {alts[0]}"
            + (f" Also: {alts[1]}" if len(alts) > 1 else "")
            + "."
        )
    elif title and title.lower() != "instagram":
        bits.append(f"Page title receipt: {title}.")

    if comments:
        bits.append(
            "Captured comments include: " + " | ".join(comments[:2]) + "."
        )
    if media_note:
        bits.append(media_note.strip())

    bits.append(
        "I am not inventing pixels beyond these receipts. "
        "I will not claim I have no browser when this page-state is live."
    )
    return " ".join(bits)


def repair_browser_false_denial(
    cortex_text: str,
    *,
    owner_text: str = "",
    state: Optional[Mapping[str, Any]] = None,
    state_dir: Any = None,
) -> dict[str, Any]:
    """If cortex denies screen while browser receipt exists, replace with grounded text."""
    raw = str(cortex_text or "").strip()
    owner = str(owner_text or "")
    if not raw:
        return {"changed": False, "text": raw, "reason": "empty"}
    if not is_browser_limb_denial(raw):
        return {"changed": False, "text": raw, "reason": "not_denial"}
    # Prefer describe turns; still repair clear denials if URL live
    # state=None → load live; state={} explicit empty → do not repair from disk
    if state is None:
        try:
            from System.swarm_browser_page_state import latest_page_state

            st: Mapping[str, Any] = latest_page_state(
                state_dir=state_dir, max_age_s=600.0
            ) or {}
        except Exception:
            st = {}
    elif isinstance(state, Mapping):
        st = state
    else:
        st = {}
    url = str((st or {}).get("url") or (st or {}).get("current_url") or "").strip()
    if not url:
        return {"changed": False, "text": raw, "reason": "no_live_browser_url"}

    grounded = grounded_post_description_from_state(st)
    if not grounded:
        return {"changed": False, "text": raw, "reason": "no_grounded_text"}

    return {
        "changed": True,
        "text": grounded,
        "reason": "false_browser_limb_denial_replaced_with_page_state",
        "truth_label": TRUTH_LABEL,
        "url": url,
        "original_preview": raw[:180],
    }


__all__ = [
    "TRUTH_LABEL",
    "is_browser_limb_denial",
    "is_owner_describe_browser_turn",
    "grounded_post_description_from_state",
    "repair_browser_false_denial",
]
