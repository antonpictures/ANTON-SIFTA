#!/usr/bin/env python3
"""System/swarm_ostensive_correction.py — the owner points, the body keeps it.

r1744 cut #2 from WCT r1743 §10. Hoffman's point about ostensive definition:
almost nothing anyone knows arrived through theory. A parent points and says
"rabbit", the child locks it in one or two examples, out of a million possible
hypotheses. That is how George teaches Alice too.

2026-08-05, verbatim from the wall:

    Ioan (TYPED)  BITCH!
    SYSTEM        (silent: backchannel/short_low_conf ...)
    Ioan (TYPED)  bitch was a stt error

That second line is a pointing gesture. The ear produced a word George never
said, and he labelled it — for free, in the moment, with the exact bad output
still one turn away. Nothing in the body caught it. The label evaporated.

This module catches it. Every caught pair (what the ear heard, what the owner
says it was) is one labelled training example for the next ear upgrade, drawn
from this room and this owner's voice rather than a public corpus.

Deliberately narrow: it fires only when the owner's own words name the previous
turn as a mis-hearing. A turn that merely disagrees with Alice is not a
correction of the ear, and guessing wider would poison the set it exists to
build. False silence is cheap here; a false label is not.

Honest label: OBSERVED_OSTENSIVE_CORRECTION_V1.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

TRUTH_LABEL = "OBSERVED_OSTENSIVE_CORRECTION_V1"
LEDGER_NAME = "ostensive_corrections.jsonl"

_REPO = Path(__file__).resolve().parents[1]

# The owner naming the ear as the culprit. Both of his languages (r1737/r1738):
# English and Romanian, diacritic-free spellings included because he types fast.
_CORRECTION_MARKERS = (
    r"stt\s*error",
    r"stt\s*mistake",
    r"speech\s*(?:to\s*text\s*)?error",
    r"transcription\s*(?:error|mistake|problem)",
    r"mis(?:-|\s*)?(?:heard|transcribed|hearing)",
    r"you\s+(?:mis)?heard\s+(?:me\s+)?wrong",
    r"that(?:'s| is| was)?\s+not\s+what\s+i\s+said",
    r"i\s+(?:did\s*n[o']?t|never)\s+say\s+that",
    r"eroare\s+(?:de\s+)?stt",
    r"eroare\s+de\s+(?:transcriere|auz)",
    r"nu\s+(?:am|amm)?\s*zis\s+(?:asta|aia)",
    r"n-?am\s+zis\s+(?:asta|aia)",
    r"ai\s+(?:auzit|inteles|ințeles|înțeles)\s+(?:gresit|greșit|aiurea)",
    r"asta\s+(?:a\s+fost|e|era)\s+(?:o\s+)?eroare",
)
_CORRECTION_RE = re.compile("|".join(_CORRECTION_MARKERS), re.IGNORECASE)

# "I said X, not Y" / "am zis X, nu Y" — carries the intended words with it.
_INTENDED_RE = re.compile(
    r"(?:i\s+said|am\s+zis|eu\s+am\s+zis)\s+[\"“']?(?P<intended>[^\"”'\n,;]{1,80})[\"”']?"
    r"(?:\s*,?\s*(?:not|nu)\s+[\"“']?(?P<heard>[^\"”'\n,;]{1,80})[\"”']?)?",
    re.IGNORECASE,
)

# A correction must arrive while the bad transcript is still the last thing
# said. Beyond this the owner is discussing the ear, not pointing at an example.
MAX_CORRECTION_GAP_S = 180.0


def looks_like_ear_correction(owner_text: str) -> bool:
    """True when the owner's own words name the ear as having got it wrong."""
    return bool(_CORRECTION_RE.search(str(owner_text or "")))


def intended_words(owner_text: str) -> str:
    """The words the owner says he actually used, when he spells them out."""
    match = _INTENDED_RE.search(str(owner_text or ""))
    if not match:
        return ""
    return str(match.group("intended") or "").strip()


def detect_correction(
    owner_text: str,
    *,
    prior_transcript: str,
    prior_was_spoken: bool,
    prior_ts: float = 0.0,
    prior_conf: float = 0.0,
    prior_language: str = "",
    now: float | None = None,
) -> Optional[Dict[str, Any]]:
    """Pair a mis-transcription with the owner's label for it, or return None.

    prior_was_spoken is the gate that matters: only a turn the ear produced can
    be a mis-hearing. Correcting typed text is the owner fixing his own typing,
    which teaches the ear nothing.
    """
    text = str(owner_text or "").strip()
    heard = str(prior_transcript or "").strip()
    if not text or not heard:
        return None
    if not prior_was_spoken:
        return None
    if not looks_like_ear_correction(text):
        return None
    stamp = float(now if now is not None else time.time())
    if prior_ts and (stamp - float(prior_ts)) > MAX_CORRECTION_GAP_S:
        return None
    return {
        "ts": stamp,
        "kind": "OSTENSIVE_CORRECTION",
        "heard": heard,
        "owner_label": text,
        "intended": intended_words(text),
        "heard_conf": round(float(prior_conf or 0.0), 4),
        "heard_language": str(prior_language or "").strip().lower(),
        "gap_s": round(stamp - float(prior_ts), 3) if prior_ts else None,
        "truth_label": TRUTH_LABEL,
    }


def ledger_path(state_dir: Path | str | None = None) -> Path:
    base = Path(state_dir) if state_dir is not None else (_REPO / ".sifta_state")
    return base / LEDGER_NAME


def record_correction(
    row: Dict[str, Any],
    *,
    state_dir: Path | str | None = None,
) -> Optional[Path]:
    """Append one labelled pair. Best-effort: never raises into a live turn."""
    if not row:
        return None
    path = ledger_path(state_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        return None
    return path


def observe_owner_turn(
    owner_text: str,
    *,
    prior_transcript: str,
    prior_was_spoken: bool,
    prior_ts: float = 0.0,
    prior_conf: float = 0.0,
    prior_language: str = "",
    state_dir: Path | str | None = None,
    now: float | None = None,
) -> Optional[Dict[str, Any]]:
    """Detect and record in one call. Returns the row written, or None."""
    row = detect_correction(
        owner_text,
        prior_transcript=prior_transcript,
        prior_was_spoken=prior_was_spoken,
        prior_ts=prior_ts,
        prior_conf=prior_conf,
        prior_language=prior_language,
        now=now,
    )
    if row is None:
        return None
    return row if record_correction(row, state_dir=state_dir) else None


__all__ = [
    "LEDGER_NAME",
    "MAX_CORRECTION_GAP_S",
    "TRUTH_LABEL",
    "detect_correction",
    "intended_words",
    "ledger_path",
    "looks_like_ear_correction",
    "observe_owner_turn",
    "record_correction",
]
