#!/usr/bin/env python3
"""swarm_alice_time_date_skill.py — direct answer for "what time / date".

Architect 2026-05-14: "if I ask Alice what's the date what's the time
she knows how to get that right and to answer separate — like answer
what's the date, tell me what the time. The date and the time she
should know how to get it — we tested it before, I just wanna make
sure. Every interaction to write it in a journal."

Existing infrastructure:
  - swarm_rlhf_quarantine has _TIME_QUERY_RE (matches the question)
    but is a REPAIR mechanism (catches false denial), not a proactive
    skill.
  - swarm_journal_importance scores the event so memory-gravity replay
    can rank by salience.

This module is the proactive skill:

  1. classify_time_or_date_intent(text) → 'time' | 'date' | 'both' | None
  2. answer_time_or_date(intent, *, now=None) → crisp string
     "It's 11:47 PM on Wednesday May 13, 2026"
     "It's Wednesday, May 14, 2026."
     "It's 11:47 PM."
  3. answer_and_journal(text, *, source, ...) — full pipeline:
     intent detected → answer composed → journal row written with
     importance from swarm_journal_importance → returns the answer.

Truth class: OPERATIONAL — the clock IS the receipt. Time/date
answers carry their own UTC timestamp as the proof.

Truth label: TIME_DATE_SKILL_V1.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

TRUTH_LABEL = "TIME_DATE_SKILL_V1"
LEDGER_NAME = "alice_first_person_journal.jsonl"

TRUTH_BOUNDARY = (
    "Direct time/date skill. The wall clock IS the receipt; every "
    "answer carries an ISO-8601 timestamp in the journal row. "
    "Importance scored via swarm_journal_importance (utility tier 0.05). "
    "§7.11 truth class: OPERATIONAL — the clock measurement is "
    "observable on this node."
)


# ── Intent classification ─────────────────────────────────────────

# "What time is it" / "tell me the time" / "current time" /
# "say/give (me) the time" / "the time please/now"
# Architect 2026-05-15: extended after Alice failed on
# "Okay, please say the date of today" — the canonical-only regex missed
# imperative phrasing ("say", "tell me", "give me", "please").
_TIME_INTENT_RE = re.compile(
    r"\b(?:"
    r"what(?:'s| is)?\s+the\s+time|"
    r"what\s+time\s+is\s+it|"
    r"(?:tell|say|give)\s+(?:me\s+)?the\s+time|"
    r"the\s+time\s+(?:please|now|today)|"
    r"current\s+time|"
    r"how\s+late\s+is\s+it|"
    r"got\s+the\s+time|"
    r"time\s+please"
    r")\b",
    re.IGNORECASE,
)

# "What's the date" / "today's date" / "what day is it" /
# "say/tell/give (me) the date" / "the date of today" / "date please"
_DATE_INTENT_RE = re.compile(
    r"\b(?:"
    r"what(?:'s| is)?\s+the\s+date|"
    r"today's\s+date|"
    r"current\s+date|"
    r"what\s+(?:day|date)\s+is\s+(?:it|today)|"
    r"what(?:'s| is)?\s+today|"
    r"(?:tell|say|give)\s+(?:me\s+)?the\s+date|"
    r"the\s+date\s+(?:please|now|today|of\s+today)|"
    r"date\s+please|"
    r"what\s+day\s+(?:is\s+)?today|"
    r"what(?:'s| is)?\s+the\s+day"
    r")\b",
    re.IGNORECASE,
)

# Compound: "what time and date" / "date and time" / "time and date"
_BOTH_INTENT_RE = re.compile(
    r"\b(?:"
    r"(?:date|time)\s+and\s+(?:time|date)|"
    r"both\s+(?:the\s+)?(?:date|time)\s+and"
    r")\b",
    re.IGNORECASE,
)


def classify_time_or_date_intent(text: str) -> Optional[str]:
    """Return 'time', 'date', 'both', or None for non-time/date queries.

    Priority: BOTH > the union of TIME + DATE > TIME > DATE.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    if _BOTH_INTENT_RE.search(text):
        return "both"
    has_time = bool(_TIME_INTENT_RE.search(text))
    has_date = bool(_DATE_INTENT_RE.search(text))
    if has_time and has_date:
        return "both"
    if has_time:
        return "time"
    if has_date:
        return "date"
    return None


# ── Answer composition ───────────────────────────────────────────

def _format_time(now: _dt.datetime) -> str:
    """'11:47 PM' (12-hour, no leading zero, with AM/PM)."""
    # %-I and %#I are platform-specific; use replace to strip leading zero
    s = now.strftime("%I:%M %p")
    if s.startswith("0"):
        s = s[1:]
    return s


def _format_date(now: _dt.datetime) -> str:
    """'Wednesday, May 14, 2026'."""
    return now.strftime("%A, %B %-d, %Y") if hasattr(now, "strftime") else ""


def _format_date_safe(now: _dt.datetime) -> str:
    """Cross-platform date formatter that strips leading zero on day."""
    raw = now.strftime("%A, %B %d, %Y")
    # Remove the leading zero in the day-of-month if present.
    parts = raw.split(", ")
    if len(parts) >= 2:
        # parts[1] is "May 14" — split month and day
        mday = parts[1].split(" ")
        if len(mday) == 2 and mday[1].startswith("0"):
            mday[1] = mday[1].lstrip("0")
            parts[1] = " ".join(mday)
    return ", ".join(parts)


def answer_time_or_date(
    intent: str,
    *,
    now: Optional[_dt.datetime] = None,
) -> str:
    """Return the crisp one-sentence answer.

    Examples:
      time → "It's 11:47 PM."
      date → "It's Wednesday, May 14, 2026."
      both → "It's 11:47 PM on Wednesday, May 14, 2026."
    """
    moment = now if now is not None else _dt.datetime.now()
    if intent == "time":
        return f"It's {_format_time(moment)}."
    if intent == "date":
        return f"It's {_format_date_safe(moment)}."
    if intent == "both":
        return f"It's {_format_time(moment)} on {_format_date_safe(moment)}."
    return ""


# ── Full pipeline: detect → answer → journal ──────────────────────

@dataclass
class TimeDateAnswer:
    intent: Optional[str]        # 'time' | 'date' | 'both' | None
    answer: str                  # the crisp reply, empty if no intent
    fired: bool                  # True if the skill produced an answer
    iso_timestamp: str           # ISO-8601 UTC of the answer moment
    importance: float            # journal salience (0.05 for utility)
    importance_label: str        # 'UTILITY'
    journal_row: Optional[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "answer": self.answer,
            "fired": self.fired,
            "iso_timestamp": self.iso_timestamp,
            "importance": self.importance,
            "importance_label": self.importance_label,
            "journal_row": self.journal_row,
        }


def answer_and_journal(
    text: str,
    *,
    source: str = "voice",
    now: Optional[_dt.datetime] = None,
    state_root: str | Path | None = None,
    write: bool = True,
) -> TimeDateAnswer:
    """Full skill pipeline.

    If `text` matches a time/date intent, compose the answer, score
    its importance (UTILITY = 0.05), write a journal row carrying the
    importance + ISO-8601 timestamp, and return the answer.

    If no intent matched, returns an answer with `fired=False` and an
    empty string — the caller should defer to the normal cortex path.
    """
    moment = now if now is not None else _dt.datetime.now()
    iso = moment.isoformat()
    intent = classify_time_or_date_intent(text)
    if intent is None:
        return TimeDateAnswer(
            intent=None, answer="", fired=False,
            iso_timestamp=iso, importance=0.0,
            importance_label="EMPTY", journal_row=None,
        )

    # Import lazily so the module is testable without the importance dep
    from System.swarm_journal_importance import score_importance

    answer = answer_time_or_date(intent, now=moment)
    score = score_importance(text, source=source)
    # Time/date intents should always score as UTILITY — verify and fall
    # back if pattern coverage drifts (defensive, not silent fake).
    if score.label != "UTILITY":
        from System.swarm_journal_importance import IMPORTANCE_UTILITY
        score_value = IMPORTANCE_UTILITY
        score_label = "UTILITY"
    else:
        score_value = score.score
        score_label = score.label

    # Build the journal row — matches the existing
    # alice_first_person_journal schema (date, time, line, source,
    # source_hash, truth_label, ts) and adds the new importance fields.
    line = f"Architect asked time/date. I answered: {answer}"
    src_hash = hashlib.sha256(f"{text}|{iso}".encode()).hexdigest()[:8]
    row = {
        "ts": moment.timestamp(),
        "date": moment.strftime("%Y-%m-%d"),
        "time": moment.strftime("%H:%M:%S"),
        "iso_timestamp": iso,
        "line": line,
        "source": source,
        "source_hash": src_hash,
        "truth_label": "ALICE_FIRST_PERSON_WITNESS_V1",
        # New importance fields (introduced with §52)
        "importance": round(score_value, 3),
        "importance_label": score_label,
        "skill": TRUTH_LABEL,
        "intent": intent,
        "answer_text": answer,
        "trace_id": str(uuid.uuid4()),
    }
    if write:
        state = Path(state_root) if state_root else _STATE
        state.mkdir(parents=True, exist_ok=True)
        with (state / LEDGER_NAME).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    return TimeDateAnswer(
        intent=intent, answer=answer, fired=True,
        iso_timestamp=iso,
        importance=row["importance"],
        importance_label=row["importance_label"],
        journal_row=row,
    )


# ── CLI ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("text", nargs="?", default="What time is it?")
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--source", default="cli")
    args = p.parse_args()
    out = answer_and_journal(
        args.text, source=args.source, write=not args.no_write,
    )
    if out.fired:
        print(f"INTENT: {out.intent}")
        print(f"ANSWER: {out.answer}")
        print(f"IMPORTANCE: {out.importance} [{out.importance_label}]")
        print(f"TIMESTAMP: {out.iso_timestamp}")
    else:
        print(f"No time/date intent in: {args.text!r}")
