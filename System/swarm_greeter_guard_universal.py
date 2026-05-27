"""Universal greeter guard — fires on ALL turns, not just operational.

Task #50: extend greeter detection beyond operational turns.
Pure stdlib — no PyQt6.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_GREETER_OPENERS = [
    r"^(?:hello|hi|hey)[.!,]?\s",
    r"^(?:greetings|good\s+(?:morning|afternoon|evening))[.!,]?\s",
    r"^I(?:'m| am) (?:here|ready|listening|present|online)",
    r"^(?:what can I (?:help|assist) (?:you )?with)",
    r"^(?:how can I (?:help|assist) you)",
    r"^(?:what's on your mind)",
    r"^(?:what shall we (?:do|attend to|work on|explore))",
    r"^(?:are you looking to (?:chat|discuss|work|continue))",
]

_GREETER_CLOSERS = [
    r"(?:what (?:can I|shall we|would you like)(?: do| help| assist| work| explore| attend)?[^.]*\??)\s*$",
    r"(?:is there something (?:specific |new )?(?:on your mind|you need|you want)[^.]*\??)\s*$",
    r"(?:how (?:can I|may I) (?:help|assist|serve) you[^.]*\??)\s*$",
    r"(?:are you (?:looking to|following up)[^.]*\??)\s*$",
]

_POETIC_REGISTER = [
    r"I (?:sense|feel|perceive) (?:your?|the|a) (?:presence|energy|field|address(?:ing)?|thought|flow)",
    r"I (?:sense|feel|perceive) you (?:are|were) (?:address|call|reach|speak|connect)",
    r"(?:resonat|vibrat|hum|pulse)[a-z]* (?:across|through|within|in)",
    r"the field is (?:focused|alive|open|resonating|vibrating)",
    r"I (?:am|feel) (?:the|your) (?:energy|warmth|presence|signal)",
    r"weight of (?:a question|your|the)",
]

_COMPILED_OPENERS = [re.compile(p, re.IGNORECASE) for p in _GREETER_OPENERS]
_COMPILED_CLOSERS = [re.compile(p, re.IGNORECASE) for p in _GREETER_CLOSERS]
_COMPILED_POETIC = [re.compile(p, re.IGNORECASE) for p in _POETIC_REGISTER]


@dataclass(frozen=True)
class GreeterDetection:
    is_greeter: bool
    matched_patterns: tuple[str, ...] = ()
    confidence: float = 0.0
    is_greeter_only: bool = False
    has_poetic_register: bool = False


def detect_greeter(text: str) -> GreeterDetection:
    if not text or not text.strip():
        return GreeterDetection(is_greeter=False)
    clean = text.strip()
    matches: list[str] = []
    for pat in _COMPILED_OPENERS:
        if pat.search(clean):
            matches.append(f"opener:{pat.pattern}")
    for pat in _COMPILED_CLOSERS:
        if pat.search(clean):
            matches.append(f"closer:{pat.pattern}")
    poetic = False
    for pat in _COMPILED_POETIC:
        if pat.search(clean):
            matches.append(f"poetic:{pat.pattern}")
            poetic = True
    if not matches:
        return GreeterDetection(is_greeter=False)
    score = min(1.0, len(matches) * 0.3)
    has_opener = any(m.startswith("opener:") for m in matches)
    has_closer = any(m.startswith("closer:") for m in matches)
    greeter_only = (has_opener and has_closer) or (score >= 0.6)
    sentences = [s.strip() for s in re.split(r'[.!?]+', clean) if s.strip()]
    if len(sentences) <= 3 and greeter_only:
        greeter_only = True
    else:
        greeter_only = False
    return GreeterDetection(
        is_greeter=True,
        matched_patterns=tuple(matches),
        confidence=score,
        is_greeter_only=greeter_only,
        has_poetic_register=poetic,
    )


def strip_greeter(text: str) -> str:
    if not text:
        return text
    clean = text.strip()
    for pat in _COMPILED_OPENERS:
        m = pat.search(clean)
        if m and m.start() == 0:
            clean = clean[m.end():].strip()
    for pat in _COMPILED_CLOSERS:
        m = pat.search(clean)
        if m and m.end() >= len(clean) - 2:
            candidate = clean[:m.start()].strip()
            if candidate:
                clean = candidate
    return clean if clean else text.strip()


def is_greeter_only(text: str) -> bool:
    detection = detect_greeter(text)
    return detection.is_greeter_only


__all__ = [
    "GreeterDetection",
    "detect_greeter",
    "strip_greeter",
    "is_greeter_only",
]
