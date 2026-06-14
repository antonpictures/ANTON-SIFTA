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

# George 2026-06-11: owner teaching Alice how to speak/commentary must reach cortex.
# Page-state receipt is evidence, never the reply. Never bypass brain for voice/style feedback.
_OWNER_VOICE_STYLE_TEACHING_RE = re.compile(
    r"\b(?:"
    r"commentary|monologue|"
    r"read\s+(?:me\s+)?(?:your\s+)?(?:voice|answer)|"
    r"speak\s+(?:a\s+bit\s+)?more|two\s+sentences|"
    r"middle\s+of\s+your\s+answer|human\s+would\s+talk|"
    r"love\s+when\s+you\s+pause|pause\s+(?:the\s+)?video\s+with\s+your|"
    r"how\s+you\s+should\s+speak|speaking\s+and\s+typing|"
    r"not\s+(?:an?\s+)?entire\s+monologue|hate\s+deterministic|"
    r"bypasses?\s+cortex|never\s+again"
    r")\b",
    re.IGNORECASE,
)

_EXPLICIT_PLAYBACK_STATE_ASK_RE = re.compile(
    r"\b(?:"
    r"what\s+(?:is\s+)?(?:playing|on(?:\s+the\s+screen)?)|"
    r"what\s+(?:am\s+i|are\s+we)\s+watching|"
    r"which\s+video|what\s+video|"
    r"is\s+it\s+(?:playing|paused)|"
    r"(?:are\s+you|tell\s*me\s+if\s+you\s+are)\s+aware\s+of\s+(?:it|this|the\s+video)|"
    r"current\s+time|what\s+time|timestamp|"
    r"how\s+long\s+(?:is\s+)?(?:the\s+)?video|"
    r"paused\s+at\s+min|at\s+min\s+\d|"
    r"what\s+do\s+i\s+need\s+to\s+code"
    r")\b",
    re.IGNORECASE,
)


def is_owner_voice_style_teaching_turn(text: str) -> bool:
    clean = " ".join((text or "").strip().split())
    return bool(clean and _OWNER_VOICE_STYLE_TEACHING_RE.search(clean))


def is_explicit_playback_state_question(text: str) -> bool:
    clean = " ".join((text or "").strip().split())
    return bool(clean and _EXPLICIT_PLAYBACK_STATE_ASK_RE.search(clean))


def is_owner_interrogative_turn(text: str) -> bool:
    """True when the owner is asking a question — must never land in no-reply lane."""
    clean = " ".join((text or "").strip().split())
    if not clean:
        return False
    if "?" in clean:
        return True
    if len(clean.split()) < 3:
        return False
    if re.search(r"\b(?:what|who|which|where|when|why|how|tell\s+me|show\s+me)\b", clean, re.I):
        return True
    if re.search(r"^\s*(?:is|are|do|does|did|can|could|will|would)\s+", clean, re.I):
        return True
    if re.search(
        r"\b(?:alice|george|ioan)\b[^.?!]{0,120}\b(?:what|who|which|where|when|why|how)\b",
        clean,
        re.I,
    ):
        return True
    return False


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
    """Always suppress — George 2026-06-11: page-state never bypasses cortex in Talk."""
    suppress, reason = should_suppress_page_summary(text)
    if suppress:
        return True, f"page_summary_guard:{reason}"
    return True, "cortex_only_no_deterministic_page_state_reply"


__all__ = [
    "TRUTH_LABEL",
    "is_owner_voice_style_teaching_turn",
    "is_explicit_playback_state_question",
    "is_owner_interrogative_turn",
    "should_suppress_page_summary",
    "should_suppress_browser_video_state_query",
]
