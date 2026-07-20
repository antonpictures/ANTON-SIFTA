#!/usr/bin/env python3
"""Suppress mic/STT false positives from owner keyboard clicks.

Whisper often hallucinates short phatic tokens (especially "thank you") when
the embedded MacBook mic hears mechanical keyboard noise while George types in
the IDE or Talk composer. This organ tracks recent keyboard activity from the
behavior-clock spine and drops likely click hallucinations before cortex.
"""
from __future__ import annotations

import os
import re
import time
from typing import Optional

_DEFAULT_GUARD_S = float(os.environ.get("SIFTA_KEYBOARD_MIC_GUARD_S", "2.5"))

_LAST_KEYBOARD_TS: float = 0.0

# Common Whisper hallucinations on keyboard-click bursts (not exhaustive speech).
_KEYBOARD_CLICK_STT_RE = re.compile(
    r"^(?:"
    r"thank\s+you(?:\s+very\s+much)?|"
    r"thanks(?:\s+a\s+lot)?|"
    r"thank\s*u|"
    r"you|"
    r"okay|ok|"
    r"mm[- ]?hm+|"
    r"uh[- ]?huh|"
    r"bye|"
    r"hello|"
    r"\.{1,3}"
    r")\.?$",
    re.IGNORECASE,
)


def note_owner_keyboard_activity(ts: Optional[float] = None) -> float:
    """Stamp the latest owner keyboard event (wall clock)."""
    global _LAST_KEYBOARD_TS
    _LAST_KEYBOARD_TS = float(ts if ts is not None else time.time())
    return _LAST_KEYBOARD_TS


def seconds_since_keyboard_activity(now: Optional[float] = None) -> float:
    if _LAST_KEYBOARD_TS <= 0:
        return float("inf")
    t = float(now if now is not None else time.time())
    return max(0.0, t - _LAST_KEYBOARD_TS)


def owner_keyboard_recent(*, max_age_s: Optional[float] = None, now: Optional[float] = None) -> bool:
    limit = float(max_age_s if max_age_s is not None else _DEFAULT_GUARD_S)
    return seconds_since_keyboard_activity(now) <= limit


def is_keyboard_source_activity(source: str) -> bool:
    s = (source or "").strip().lower()
    if not s:
        return False
    if "keyboard" in s:
        return True
    return s.endswith(":key") or s == "key"


def classify_keyboard_click_stt(
    text: str,
    stt_conf: float = 0.0,
    *,
    keyboard_recent: Optional[bool] = None,
    max_age_s: Optional[float] = None,
) -> Optional[str]:
    """Return rule-id when spoken STT is likely keyboard-click hallucination."""
    if keyboard_recent is None:
        keyboard_recent = owner_keyboard_recent(max_age_s=max_age_s)
    if not keyboard_recent:
        return None
    clean = re.sub(r"[\s.!?,;:]+", " ", (text or "").strip()).strip().lower()
    if not clean:
        return None
    try:
        conf = float(stt_conf or 0.0)
    except Exception:
        conf = 0.0
    # Deliberate owner address with a name should still pass.
    if re.search(r"\b(?:alice|george|ioan)\b", clean):
        return None
    if len(clean.split()) > 4:
        return None
    if conf >= 0.82:
        return None
    if _KEYBOARD_CLICK_STT_RE.fullmatch(clean):
        return "keyboard_click/stt_hallucination"
    if conf < 0.65 and len(clean.split()) <= 2:
        return "keyboard_click/low_conf_during_typing"
    return None


def classify_uncertain_phatic_stt(text: str, stt_conf: float = 0.0) -> Optional[str]:
    """Return rule-id for low-confidence phatic STT with no owner address.

    This catches the post-typing failure George showed live: keyboard/mechanical
    noise decoded as "Thank you" after the keyboard-recency window was not
    available to the spoken-turn gate. It is intentionally narrow: only short
    phatic tokens, low confidence, and no explicit Alice/George address.
    """
    clean = re.sub(r"[\s.!?,;:]+", " ", (text or "").strip()).strip().lower()
    if not clean:
        return None
    if re.search(r"\b(?:alice|george|ioan)\b", clean):
        return None
    try:
        conf = float(stt_conf or 0.0)
    except Exception:
        conf = 0.0
    if conf > 0.50:
        return None
    if len(clean.split()) > 4:
        return None
    if _KEYBOARD_CLICK_STT_RE.fullmatch(clean):
        return "stt_uncertain/phatic_no_address"
    return None
