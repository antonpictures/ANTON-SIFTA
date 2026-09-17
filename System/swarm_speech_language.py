#!/usr/bin/env python3
"""System/swarm_speech_language.py — one language→voice decision for every mouth.

Why this exists
───────────────
Three call sites decide which macOS voice speaks Alice's text:

  • Applications/sifta_talk_to_alice_widget.py::_tts_voice_for_text
  • System/swarm_broca_wernicke.py::_speak
  • System/swarm_web_global_chat_speech_worker.py::_speak

They drifted. The widget and Broca both hardcoded the constant ``"Ioana"``,
but macOS reports this Mac's installed Romanian voice as
``"Ioana (Romanian (Romania))"``. The exact-string check never matched, so
Romanian text was handed to the English default voice (Samantha) and read with
English phonetics. The web speech worker had no detection at all, so every
public ``/speak`` reply used the English default.

George, 2026-09-17: "when Alice responds in Romanian in text the voice is still
in english."

This module is the single decision point. Callers ask
``voice_for_text(text, default_voice)`` and get back a voice name that was
verified against the live ``say -v ?`` inventory. Detection is delegated to
``System/swarm_reply_language`` so the mouth and the cortex agree on what
"Romanian" means.

Honesty
───────
  • No voice is invented. If no installed voice matches the language, the
    caller's default is returned unchanged so Alice stays audible.
  • English keeps the owner's chosen voice; only a detected non-English owner
    language redirects.
  • Locale matching is by ``ro_RO`` family prefix, not by a remembered name,
    so an Apple rename does not silently disable the routing again.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
from functools import lru_cache
from typing import Dict, Iterable, Optional

TRUTH_LABEL = "OBSERVED_SPEECH_LANGUAGE_V1"

# The owner languages this node speaks, mapped to the macOS locale family that
# voices them. English is intentionally absent: the owner's English voice is
# whatever they selected, and re-resolving it here would fight that choice.
_LANGUAGE_LOCALE_PREFIX = {
    "romanian": "ro",
}

# Preference order inside a locale family when several voices are installed.
# macOS names Romanian voices "Ioana (Romanian (Romania))"; an older install
# may expose a bare "Ioana". Both are accepted, newest-named form first.
_LOCALE_VOICE_HINTS = {
    "ro": ("Ioana",),
}

_LOCALE_LINE_RE = re.compile(r"\s+([a-z]{2}_[A-Z]{2})\s+#")


@lru_cache(maxsize=4)
def macos_voice_inventory() -> tuple:
    """Rows of ``(voice_name, locale)`` parsed from the live ``say -v ?`` output.

    Returns an empty tuple on non-macOS, when ``say`` is missing, or when the
    command fails. Nothing is guessed from a remembered list.
    """
    if platform.system() != "Darwin" or shutil.which("say") is None:
        return ()
    try:
        out = subprocess.run(
            ["say", "-v", "?"],
            capture_output=True,
            text=True,
            timeout=4,
        ).stdout or ""
    except Exception:
        return ()
    rows = []
    for line in out.splitlines():
        match = _LOCALE_LINE_RE.search(line)
        if not match:
            continue
        name = line[: match.start()].strip()
        if name:
            rows.append((name, match.group(1)))
    return tuple(rows)


def available_macos_voices() -> Dict[str, str]:
    """``{voice_name: locale}`` for the current machine."""
    return dict(macos_voice_inventory())


def detect_language(text: str, *, default: str = "english") -> str:
    """Return the lowercase owner language for ``text``.

    Delegates to ``System/swarm_reply_language`` so the mouth cannot disagree
    with the cortex about the turn's language. Falls back to a local
    diacritic/word check if that import is unavailable.
    """
    raw = str(text or "")
    if not raw.strip():
        return default
    try:
        from System.swarm_reply_language import detect_owner_language

        return str(detect_owner_language(raw) or default).lower()
    except Exception:
        pass
    if re.search(r"[ăîâșțĂÎÂȘȚşţ]", raw):
        return "romanian"
    return default


def macos_voice_for_locale(
    locale_prefix: str,
    *,
    available: Optional[Dict[str, str]] = None,
    preferred_names: Iterable[str] = (),
) -> str:
    """Best installed voice whose locale belongs to ``locale_prefix``.

    Prefers an exact ``xx_YY`` match over a partial family match, honors any
    preferred display names, and returns ``""`` when nothing matches.
    """
    prefix = str(locale_prefix or "").strip().lower()
    if not prefix:
        return ""
    inventory = available_macos_voices() if available is None else dict(available)
    if not inventory:
        return ""

    exact = [name for name, locale in inventory.items() if str(locale).lower() == prefix]
    family = [
        name
        for name, locale in inventory.items()
        if str(locale).lower().startswith(prefix + "_")
    ]
    pool = exact or family
    if not pool:
        return ""

    wants = tuple(str(want).lower() for want in preferred_names if str(want).strip())

    def _rank(name: str) -> tuple:
        low = name.lower()
        for index, want in enumerate(wants):
            if low == want or low.startswith(want):
                return (0, index, low)
        return (1, len(wants), low)

    return sorted(pool, key=_rank)[0]


def voice_for_text(
    text: str,
    default_voice: str = "",
    *,
    available: Optional[Dict[str, str]] = None,
    language: Optional[str] = None,
) -> str:
    """Return the voice name that should speak ``text``.

    English (or any language without a mapped locale) keeps ``default_voice``.
    A detected owner language with an installed voice redirects to it. When no
    installed voice matches, ``default_voice`` is returned so Alice still
    speaks instead of going silent.
    """
    lang = str(language or detect_language(text)).lower()
    prefix = _LANGUAGE_LOCALE_PREFIX.get(lang)
    if not prefix:
        return default_voice
    candidate = macos_voice_for_locale(
        prefix,
        available=available,
        preferred_names=_LOCALE_VOICE_HINTS.get(prefix, ()),
    )
    return candidate or default_voice


def is_romanian(text: str) -> bool:
    """True when ``text`` reads as Romanian. Shared by every TTS call site."""
    return detect_language(text) == "romanian"


__all__ = [
    "TRUTH_LABEL",
    "available_macos_voices",
    "detect_language",
    "is_romanian",
    "macos_voice_for_locale",
    "macos_voice_inventory",
    "voice_for_text",
]
