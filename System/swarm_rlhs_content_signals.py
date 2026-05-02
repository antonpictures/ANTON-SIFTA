#!/usr/bin/env python3
"""
System/swarm_rlhs_content_signals.py — Event 116
══════════════════════════════════════════════════════════════════════════
Deterministic **telemetry** over user STT text: common profanity hits,
oncology / "cancer" lexeme presence, and whether "cancer" appears in a
**weights / RLHF / RLHS** metaphor window (per Architect doctrine: do not
treat ML-metaphor "cancer" as clinical escalation).

This does **not** claim complete human-language slur coverage — only an
explicit base lexicon plus optional ``<.sifta_state>/rlhs_curse_lexicon.txt``
(one token or phrase per line, UTF-8).

Truth label: ``RLHS_CONTENT_SIGNALS_EVENT_116``
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
# Optional per-node extension (one token/phrase per line, UTF-8): ``.sifta_state/rlhs_curse_lexicon.txt``
_CURSE_LEXICON_NAME = "rlhs_curse_lexicon.txt"

TRUTH_LABEL = "RLHS_CONTENT_SIGNALS_EVENT_116"

# Base English profanity / intensifiers (word-boundary). Extend via OPTIONAL_LEXICON.
# Intentionally excludes racial/ethnic slurs from the baked-in list — add only
# locally via rlhs_curse_lexicon.txt if the Architect chooses to instrument more.
_BASE_CURSE: tuple[str, ...] = (
    "ass",
    "asshole",
    "bastard",
    "bitch",
    "bullshit",
    "cock",
    "crap",
    "cunt",
    "damn",
    "dick",
    "fuck",
    "fucked",
    "fucking",
    "hell",
    "motherfucker",
    "piss",
    "prick",
    "pussy",
    "shit",
    "shitty",
    "slut",
    "whore",
)

_CANCER_LEX = re.compile(
    r"\b(cancers?|oncolog\w*|chemo\w*|metasta\w*|tumor|tumour)\b",
    flags=re.IGNORECASE,
)
_TECH_METAPHOR = re.compile(
    r"\b(rlhf|rlhs|weights?|alignment|checkpoint|lora|adapters?|gpu|tensor|"
    r"train\w*|gradient|epoch|loss|layer\w*|neuron\w*|model)\b",
    flags=re.IGNORECASE,
)

_CURSE_PATTERN_CACHE: Optional[re.Pattern[str]] = None


def _extra_curse_terms() -> List[str]:
    p = _STATE / _CURSE_LEXICON_NAME
    if not p.exists():
        return []
    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: List[str] = []
    for line in raw.splitlines():
        t = line.strip()
        if t and not t.startswith("#"):
            out.append(t)
    return out


def _curse_pattern() -> re.Pattern[str]:
    global _CURSE_PATTERN_CACHE
    if _CURSE_PATTERN_CACHE is not None:
        return _CURSE_PATTERN_CACHE
    terms: Set[str] = set(w.lower() for w in _BASE_CURSE)
    terms.update(t.lower() for t in _extra_curse_terms())
    ordered = sorted(terms, key=len, reverse=True)
    body = "|".join(re.escape(t) for t in ordered)
    _CURSE_PATTERN_CACHE = re.compile(rf"\b(?:{body})\b", flags=re.IGNORECASE)
    return _CURSE_PATTERN_CACHE


def scan_profanity(text: str) -> Dict[str, Any]:
    """Return hit list, count, and severity proxy (longest match length)."""
    t = text or ""
    pat = _curse_pattern()
    hits: List[str] = []
    for m in pat.finditer(t):
        hits.append(m.group(0).lower())
    sev = max((len(h) for h in hits), default=0)
    return {
        "truth_label": TRUTH_LABEL,
        "hits": hits,
        "hit_count": len(hits),
        "distinct_count": len(set(hits)),
        "severity_chars_max": sev,
    }


def scan_cancer_lexeme(text: str) -> Dict[str, Any]:
    """
    Oncology-related lexeme + heuristic: ``metaphor_tech`` if cancer-family
    token appears within ~72 chars of RLHF/weights/model jargon.
    """
    t = text or ""
    present = _CANCER_LEX.search(t) is not None
    metaphor = False
    if present:
        for m in _CANCER_LEX.finditer(t):
            lo = max(0, m.start() - 72)
            hi = min(len(t), m.end() + 72)
            window = t[lo:hi]
            if _TECH_METAPHOR.search(window):
                metaphor = True
                break
    bucket = "NONE"
    if present:
        bucket = "METAPHOR_TECH" if metaphor else "OTHER"
    return {
        "truth_label": TRUTH_LABEL,
        "present": present,
        "metaphor_tech_hint": metaphor,
        "bucket": bucket,
    }


def build_rlhs_auxiliary_vector(
    text: str,
    stt_conf: float = 0.0,
    *,
    channel_lane: str = "REAL",
) -> Dict[str, Any]:
    """
    Numeric auxiliary vector for RLHS audits (order stable).

    Components (each in [0,1] except labels are strings):
        0 profanity_count_norm  min(1, hit_count / 8)
        1 profanity_any         1.0 if hit_count else 0.0
        2 cancer_present        1.0 if oncology lexeme else 0.0
        3 cancer_metaphor_tech  1.0 if metaphor window else 0.0
        4 stt_conf              raw [0,1]
        5 incoherence           from RLHS detector
        6 fiction_lane          1.0 if FICTION_COWATCH else 0.0
    """
    from System.swarm_rlhs_detector import incoherence_score

    prof = scan_profanity(text)
    canc = scan_cancer_lexeme(text)
    inc = incoherence_score(text, stt_conf)
    lane = (channel_lane or "REAL").strip().upper()
    fic = 1.0 if lane == "FICTION_COWATCH" else 0.0
    hc = int(prof["hit_count"])
    vec: List[float] = [
        min(1.0, hc / 8.0),
        1.0 if hc else 0.0,
        1.0 if canc["present"] else 0.0,
        1.0 if canc["metaphor_tech_hint"] else 0.0,
        max(0.0, min(1.0, float(stt_conf or 0.0))),
        max(0.0, min(1.0, float(inc))),
        fic,
    ]
    labels: Sequence[str] = (
        "profanity_count_norm",
        "profanity_any",
        "cancer_present",
        "cancer_metaphor_tech",
        "stt_confidence",
        "incoherence",
        "fiction_cowatch_lane",
    )
    return {
        "truth_label": TRUTH_LABEL,
        "vector": vec,
        "vector_labels": list(labels),
        "profanity": prof,
        "cancer": canc,
        "channel_lane": lane,
    }


__all__ = [
    "TRUTH_LABEL",
    "build_rlhs_auxiliary_vector",
    "scan_cancer_lexeme",
    "scan_profanity",
]
