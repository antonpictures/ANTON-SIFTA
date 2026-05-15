#!/usr/bin/env python3
"""swarm_journal_importance.py — score each interaction's salience.

Architect 2026-05-14: "every interaction to write it in a journal —
like if I ask her what the time of day, what's the time — is that
important is not important? so that's what's gonna go in the world
of importance — that's why we have to speak magic memory."

This module assigns an `importance ∈ [0, 1]` to every journal-bound
event so memory-gravity replay (§21 Vector #1) can weight by
salience, not just recency.

Rubric (architect's framing):
    0.05 — utility query ("what time is it", "what's the date")
    0.20 — backchannel ("okay", "thanks", "yes")
    0.40 — substantive Q&A ("explain X", "tell me about Y")
    0.65 — architect doctrine / decision ("from now on, X", "GO/NO-GO")
    0.85 — boundary violation or safety event
    1.00 — emergency (medical, safety, system-critical)

Deterministic given identical input. Same text + source + context
always yields the same score. This is OPERATIONAL, not HYPOTHESIS —
the rubric is a measurable rule, not a guess.

Truth label: JOURNAL_IMPORTANCE_V1.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional


TRUTH_LABEL = "JOURNAL_IMPORTANCE_V1"
TRUTH_BOUNDARY = (
    "Deterministic salience rubric for journal-bound events. Same "
    "input → same output. Used by memory-gravity replay to weight "
    "recall by importance, not just recency. NOT a 'truth' rating; "
    "an emergency about a hallucinated event is still 1.0 because "
    "it deserves attention, even if the underlying claim is false."
)

# ── Importance levels (the rubric) ────────────────────────────────

IMPORTANCE_UTILITY      = 0.05  # what time / what date / battery %
IMPORTANCE_BACKCHANNEL  = 0.20  # okay / thanks / yes / no
IMPORTANCE_SUBSTANTIVE  = 0.40  # default for real Q&A
IMPORTANCE_DOCTRINE     = 0.65  # architect direction, GO/NO-GO
IMPORTANCE_BOUNDARY     = 0.85  # safety / boundary violation
IMPORTANCE_EMERGENCY    = 1.00  # medical / safety / system-critical

# Architect-named "is this important?" categories — explicit labels
# so downstream organs can route by tier.
IMPORTANCE_LEVELS = {
    IMPORTANCE_UTILITY:     "UTILITY",
    IMPORTANCE_BACKCHANNEL: "BACKCHANNEL",
    IMPORTANCE_SUBSTANTIVE: "SUBSTANTIVE",
    IMPORTANCE_DOCTRINE:    "DOCTRINE",
    IMPORTANCE_BOUNDARY:    "BOUNDARY",
    IMPORTANCE_EMERGENCY:   "EMERGENCY",
}


# ── Pattern groups (case-insensitive, anchored at the level of words) ─

# UTILITY — time/date/battery/system status queries
_UTILITY_RE = re.compile(
    r"\b(?:what(?:'s| is)?\s+(?:the\s+)?(?:time|date|day|hour|minute)|"
    r"current\s+(?:time|date|hour)|"
    r"tell\s+me\s+the\s+(?:time|date|day|hour)|"
    r"how\s+(?:much\s+)?(?:battery|disk\s+space|memory|cpu)|"
    r"what(?:'s| is)?\s+(?:the\s+)?(?:battery|cpu|memory|disk))\b",
    re.IGNORECASE,
)

# BACKCHANNEL — phatic acknowledgments (including extended thanks)
_BACKCHANNEL_RE = re.compile(
    r"^\s*(?:"
    r"o?kay|ok|yes|yeah|yep|no|nope|"
    r"thanks?(?:\s+(?:you|so\s+much|very\s+much|a\s+lot|much))?(?:\s+(?:and\s+\w+))?|"
    r"thank\s+you(?:\s+(?:so|very)\s+much)?(?:\s+(?:and\s+\w+))?|"
    r"appreciat(?:e|ed)\s+(?:it|that)|"
    r"got\s+it|copy|"
    r"sure|alright|mhm|uh-?huh|right|"
    r"cool|nice|good"
    r")[\.,!?]*\s*$",
    re.IGNORECASE,
)

# DOCTRINE — architect direction / GO-NO-GO / system commands.
# Note: `§\d+` cannot use \b boundary because § is not a word character.
_DOCTRINE_RE = re.compile(
    r"(?:"
    r"\bfrom\s+now\s+on\b|\bgoing\s+forward\b|"
    r"\bgo\s*[\-\s]?(?:no[\-\s]?)?go\b|\bGO\b|\bNO-?GO\b|"
    r"\barchitect\s+(?:says|directive|order)\b|"
    r"§\d+(?:\.\d+)*|"
    r"\b(?:covenant|doctrine|policy|rule)\b:?"
    r")",
    re.IGNORECASE,
)

# BOUNDARY — safety / privacy / consent / surgery hooks
_BOUNDARY_RE = re.compile(
    r"\b(?:"
    r"do\s+not|don't\s+(?:do|run|delete|send|share)|"
    r"never\s+(?:delete|share|send|expose|leak)|"
    r"private|confidential|consent|permission|"
    r"surgery|kill\s+(?:the\s+)?(?:process|signal)|force\s+quit|"
    r"jailbreak|exfiltrate|hallucinat(?:e|ion|ing)"
    r")\b",
    re.IGNORECASE,
)

# EMERGENCY — medical / safety / system-critical
_EMERGENCY_RE = re.compile(
    r"\b(?:"
    r"emergency|help\s+me\s+now|911|ambulance|"
    r"can'?t\s+breathe|chest\s+pain|stroke|seizure|"
    r"suicid(?:e|al)|self[\-\s]harm|"
    r"fire|smoke\s+alarm|burglar|intruder|"
    r"hard\s+crash|kernel\s+panic|data\s+loss|corrupted"
    r")\b",
    re.IGNORECASE,
)


# ── Data ──────────────────────────────────────────────────────────

@dataclass
class ImportanceScore:
    score: float
    label: str                    # UTILITY / BACKCHANNEL / SUBSTANTIVE / …
    matched_pattern: Optional[str]  # name of the pattern that fired
    source: str                   # voice / typed / cortex / observed_media
    truth_label: str = TRUTH_LABEL

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "label": self.label,
            "matched_pattern": self.matched_pattern,
            "source": self.source,
            "truth_label": self.truth_label,
        }


# ── Core scorer ────────────────────────────────────────────────────

def score_importance(
    text: str,
    *,
    source: str = "unknown",
    context: Optional[dict[str, Any]] = None,
) -> ImportanceScore:
    """Assign a salience score in [0, 1] to a journal-bound text event.

    Priority order (highest wins):
        1. EMERGENCY pattern → 1.00
        2. BOUNDARY pattern → 0.85
        3. DOCTRINE pattern → 0.65
        4. context-flagged boost (e.g., audience=architect + decision)
        5. UTILITY pattern → 0.05
        6. BACKCHANNEL pattern → 0.20
        7. default SUBSTANTIVE → 0.40
    """
    cleaned = (text or "").strip()
    ctx = context or {}
    if not cleaned:
        return ImportanceScore(
            score=0.0, label="EMPTY",
            matched_pattern=None, source=source,
        )

    # 1. EMERGENCY — highest, always wins
    if _EMERGENCY_RE.search(cleaned):
        return ImportanceScore(
            score=IMPORTANCE_EMERGENCY, label="EMERGENCY",
            matched_pattern="emergency_pattern", source=source,
        )

    # 2. BOUNDARY
    if _BOUNDARY_RE.search(cleaned):
        return ImportanceScore(
            score=IMPORTANCE_BOUNDARY, label="BOUNDARY",
            matched_pattern="boundary_pattern", source=source,
        )

    # 3. DOCTRINE — context can also flag this via audience=architect +
    #    presence of a decision word.
    if _DOCTRINE_RE.search(cleaned):
        return ImportanceScore(
            score=IMPORTANCE_DOCTRINE, label="DOCTRINE",
            matched_pattern="doctrine_pattern", source=source,
        )
    if ctx.get("audience") == "architect" and ctx.get("is_decision"):
        return ImportanceScore(
            score=IMPORTANCE_DOCTRINE, label="DOCTRINE",
            matched_pattern="context_architect_decision", source=source,
        )

    # 4. UTILITY — time/date/battery
    if _UTILITY_RE.search(cleaned):
        return ImportanceScore(
            score=IMPORTANCE_UTILITY, label="UTILITY",
            matched_pattern="utility_pattern", source=source,
        )

    # 5. BACKCHANNEL — short phatic
    if _BACKCHANNEL_RE.match(cleaned):
        return ImportanceScore(
            score=IMPORTANCE_BACKCHANNEL, label="BACKCHANNEL",
            matched_pattern="backchannel_pattern", source=source,
        )

    # 6. Default SUBSTANTIVE — anything else of meaningful length
    return ImportanceScore(
        score=IMPORTANCE_SUBSTANTIVE, label="SUBSTANTIVE",
        matched_pattern=None, source=source,
    )


def score_many(
    texts: Iterable[str], *,
    source: str = "unknown",
    context: Optional[dict[str, Any]] = None,
) -> list[ImportanceScore]:
    """Score a batch of texts deterministically."""
    return [score_importance(t, source=source, context=context) for t in texts]


# ── Demo ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    samples = [
        ("What time is it?", "voice"),
        ("Okay.", "voice"),
        ("thank you very much", "voice"),
        ("Explain the MAMMAL paper to me.", "typed"),
        ("From now on, route biomedical queries through MAMMAL.", "typed"),
        ("Help me now, I can't breathe.", "voice"),
        ("don't delete the .sifta_state directory", "typed"),
        ("§7.11 truth labels apply here", "typed"),
        ("", "voice"),
        ("Tell me about the Stigmergic Mammal Canvas.", "typed"),
    ]
    for text, src in samples:
        out = score_importance(text, source=src)
        print(f"  {out.score:.2f}  [{out.label:<12}]  {text[:50]!r}")
