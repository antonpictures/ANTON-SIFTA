#!/usr/bin/env python3
"""Suppress automatic page-summary follow-ups on effector-only owner turns (r874)."""
from __future__ import annotations

import re

TRUTH_LABEL = "TALK_PAGE_SUMMARY_GUARD_V1"

_COWATCH_META_RE = re.compile(
    r"\b(?:"
    r"you\s+are\s+respond(?:ing)?\s+to\s+(?:a\s+)?(?:guy|person|someone|man|woman)\s+on\s+youtube|"
    r"responding\s+to\s+(?:the\s+)?(?:video|guy|speaker)|"
    r"co-?watch|cowatch|watching\s+(?:with\s+me|together)"
    r")\b",
    re.IGNORECASE,
)

_IDE_DOCTOR_PASTE_RE = re.compile(
    r"\b(?:IDE_BOOT_COVENANT|CONSCIOUSNESS_TOURNAMENT|IDE_DOCTOR|tool_call:|r8\d\d\b)\b",
    re.IGNORECASE,
)


def should_suppress_page_summary(text: str) -> tuple[bool, str]:
    """Return (suppress, reason)."""
    clean = " ".join((text or "").strip().split())
    if not clean:
        return False, ""

    if re.search(r"\bSELF-SCREENSHOT\s+CORTEX\s+TURN\b|(?:^|\s)/(?:sc|screenshot)(?:\s|$)", clean, re.I):
        return True, "self_screenshot_observation_only"

    if re.search(r"\b(?:close|shut|remove|kill)\b", clean, re.I) and re.search(
        r"\b(?:tab|tabs)\b", clean, re.I
    ):
        return True, "effector_only_close_tab"

    if _COWATCH_META_RE.search(clean):
        return True, "cowatch_meta_commentary"

    low = clean.lower()
    if _IDE_DOCTOR_PASTE_RE.search(clean) and re.search(r"\bplaying\b", low):
        if not re.search(r"\b(?:what\s+is|is\s+it|video\s+playing|currently\s+playing)\b", low):
            return True, "ide_paste_playing_hijack"

    return False, ""


def should_suppress_browser_video_state_query(text: str) -> tuple[bool, str]:
    """Block video-state hijack on turns that are not real playback-state asks."""
    suppress, reason = should_suppress_page_summary(text)
    if suppress:
        return True, f"page_summary_guard:{reason}"
    return False, ""


__all__ = [
    "TRUTH_LABEL",
    "should_suppress_page_summary",
    "should_suppress_browser_video_state_query",
]
