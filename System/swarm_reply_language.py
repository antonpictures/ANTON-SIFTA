#!/usr/bin/env python3
"""System/swarm_reply_language.py — Alice replies in the owner's language.

George 2026-07-26, 00:54: he was speaking English about a UFO complex and Alice
answered in Brazilian Portuguese, then insisted "não foi espanhol, foi
Português" and offered to keep going in it. He does not speak Portuguese or
Spanish. His words: "the text to speech must match language."

The r1733 STT unlock let Alice HEAR many languages, which is correct — the room
is multilingual, a TV or a phone call can be in anything. But hearing another
language must never make Alice SPEAK a language the owner does not. The reply
language is pinned to the language the owner is actually using, not to whatever
drifted through the cortex or the room.

George uses two languages: English and Romanian. Anything else in his own turn
is almost certainly ambient contamination or cortex drift, so the safe pin is
English. This module decides the reply language from the owner's own words and
builds the prompt line that holds the cortex to it. The existing
`_tts_voice_for_text` in the Talk widget already routes the Romanian voice, so a
reply pinned to the owner's language also lands on the right voice.

Honest label: OBSERVED_REPLY_LANGUAGE_V1.
"""

from __future__ import annotations

import os
import re

TRUTH_LABEL = "OBSERVED_REPLY_LANGUAGE_V1"

# The languages this node's owner actually speaks. George speaks English and
# Romanian. Another node's owner (Carlos, for one) may speak something else, so
# SIFTA_OWNER_LANGUAGES overrides this per node — covenant §3 sovereignty. The
# universal rule in the prompt ("match your message, never drift to overheard
# languages") holds regardless; this list only sharpens the hint.
_DEFAULT_OWNER_LANGUAGES = ("english", "romanian")


def owner_languages() -> tuple[str, ...]:
    """This node's owner languages, from SIFTA_OWNER_LANGUAGES or the default."""
    raw = str(os.environ.get("SIFTA_OWNER_LANGUAGES", "") or "").strip()
    if not raw:
        return _DEFAULT_OWNER_LANGUAGES
    langs = tuple(part.strip().lower() for part in re.split(r"[,;]", raw) if part.strip())
    return langs or _DEFAULT_OWNER_LANGUAGES


# Back-compat module constant; prefer owner_languages() so env overrides apply.
OWNER_LANGUAGES = _DEFAULT_OWNER_LANGUAGES

_RO_DIACRITICS = re.compile(r"[ăîâșțĂÎÂȘȚşţ]")

# Whole-word Romanian markers with no common English look-alikes. One is enough
# to call a turn Romanian even in diacritic-free ASCII ("vorbeste romaneste").
_RO_DECISIVE = frozenset(
    """
    multumesc multam multumim merci salut buna vorbeste vorbesti vorbim vorbi
    romaneste romana romaneasca foarte sunt esti este suntem sunteti bravo
    pentru dorinta dorim doresti doreste vrem vreau vrei facem faci faceti
    avem aveti despre decat catre spune spunemi spuneti absolut adevarat
    problema problemele nimic poate putem raspuns raspunde raspunsul cuvinte
    cuvant numarul exemplul deranjeaza serviciu servicii profitam profit
    trebuie intrebare intrebarea intreb alegi alege scriem scrie scrii
    gestionarea introducerea asteptare clientii totul retine acesta aceasta
    aceste bineinteles inteleg intelegi nevoie asadar acasa
    """.split()
)

# Weak function words, counted only for density so an English sentence with one
# stray collision never trips Romanian.
_RO_STOP = frozenset(
    """
    sau dar acum aici doar asta tine hai cel cea cele intre dintre imi iti
    place unde cand cine cum bine ceva mult mereu deci pai atunci cu ca si sa
    ne de nu ii le ei ele noi voi vom va vor mi ti se te ma isi
    """.split()
)


def detect_owner_language(text: str) -> str:
    """Return 'romanian' or 'english' for the owner's own turn.

    Only the owner's two languages are candidates. This is deliberately not a
    general language detector: the point is to pin the reply, and any third
    language in the owner's turn is contamination, not a request to switch.
    """
    raw = str(text or "")
    if not raw.strip():
        return "english"
    if _RO_DIACRITICS.search(raw):
        return "romanian"
    tokens = re.findall(r"[a-z]+", raw.lower())
    if not tokens:
        return "english"
    if any(tok in _RO_DECISIVE for tok in tokens):
        return "romanian"
    n = len(tokens)
    stop = sum(1 for tok in tokens if tok in _RO_STOP)
    if n >= 4 and stop >= max(3, n * 0.4):
        return "romanian"
    return "english"


def reply_language_prompt_block(owner_text: str, *, owner_label: str = "George") -> str:
    """Prompt line pinning the reply language to the owner's own language.

    This is the fix for the cortex drifting into Portuguese/Spanish. It is short
    on purpose — one firm instruction near the end of the prompt, not an essay.
    """
    language = detect_owner_language(owner_text)
    language_title = language.capitalize()
    spoken = " and ".join(lang.capitalize() for lang in owner_languages())
    return (
        "REPLY LANGUAGE (hard rule): "
        f"{owner_label} speaks {spoken}. His current message is {language_title}, so "
        f"answer entirely in {language_title} — including the spoken 🗣 line. Never "
        "reply in Spanish, Portuguese, French, or any other language, even if "
        "overheard room audio, a TV, a phone call, or a previous turn was in that "
        f"language. If {owner_label} explicitly asks you to switch languages, do it; "
        "otherwise match the language of his message."
    )


def reply_language_mismatch(owner_text: str, reply_text: str) -> str:
    """Return the expected language when the reply drifted off the owner's turn.

    r1740: George typed "mama mea intelege numai romaneste" and the cortex
    answered in English — the r1737 pin was advice with no measurement behind
    it. This is the measurement: '' means the reply matches; a language name
    means the reply missed and names what it should have been. The caller
    writes the receipt; this function only judges.
    """
    reply = str(reply_text or "").strip()
    if not reply:
        return ""
    expected = detect_owner_language(owner_text)
    got = detect_owner_language(reply)
    if expected == "romanian" and got != "romanian":
        return "romanian"
    if not is_owner_language(reply):
        return expected
    return ""


def is_owner_language(text: str) -> bool:
    """True when text reads as one of the owner's languages (English or Romanian).

    A TTS-side guard: a reply that is neither English nor Romanian is drift the
    prompt pin failed to stop, and the caller can flag or re-pin rather than
    speak a language the owner does not.
    """
    raw = str(text or "").strip()
    if not raw:
        return True
    if detect_owner_language(raw) == "romanian":
        return True
    return _looks_english(raw)


# Function words that are strong English markers and rare in Portuguese/Spanish.
_EN_MARKERS = frozenset(
    """
    the and you your that this with have was were will would could should
    what when where who how why here there because about into over under
    yes not don't didn't isn't i'm you're it's that's right okay
    """.split()
)

# Portuguese/Spanish markers that should never dominate an owner-language reply.
_NON_OWNER_MARKERS = frozenset(
    """
    não nao você voce está esta então entao muito obrigado desculpe claro
    também tambem isso aqui agora tudo você's pero porque está estás usted
    gracias señor perdón ahora también pues entonces
    """.split()
)


def _looks_english(text: str) -> bool:
    tokens = re.findall(r"[a-zà-ÿ']+", text.lower())
    if not tokens:
        return True
    non_owner = sum(1 for tok in tokens if tok in _NON_OWNER_MARKERS)
    english = sum(1 for tok in tokens if tok in _EN_MARKERS)
    if non_owner >= 2 and non_owner > english:
        return False
    return True


__all__ = [
    "OWNER_LANGUAGES",
    "TRUTH_LABEL",
    "detect_owner_language",
    "is_owner_language",
    "reply_language_mismatch",
    "reply_language_prompt_block",
]
