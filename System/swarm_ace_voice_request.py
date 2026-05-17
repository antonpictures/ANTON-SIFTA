#!/usr/bin/env python3
"""System/swarm_ace_voice_request.py — Ace asks the Talk voice to speak.

Architect 2026-05-17 (verbatim, abridged):
    "when you open the app Alice the first thing you do is spell the
    word that is on the screen ... every time you change the word
    you spell it again."

Ace and Talk are two widgets in one desktop process, but their voice
must be one voice (covenant §7.15). When Ace wants Alice to speak —
on open, on word swap — it does NOT call TTS itself. It writes a
voice-request row to this ledger. The Talk widget tails the ledger
and emits the line through its canonical reply path (append + TTS).

One Alice voice. One conversation ledger. Two views.

Schema (every row):

    {
      "ts": ...,
      "schema": "ACE_VOICE_REQUEST_V1",
      "truth_label": "ACE_VOICE_REQUEST_V1",
      "kind": "open" | "swap",
      "word": "balloon",            # the new on-screen word
      "previous_word": "happy",     # only on kind="swap"
      "request_id": "<uuid hex 12>"
    }

The Talk widget should keep an offset and only act on rows past it
(seek to EOF on startup so stale requests from previous sessions
don't replay).

Truth label: ``ACE_VOICE_REQUEST_V1``.

Stigauth: ``COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE``.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Optional, Dict

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "ace_voice_request.jsonl"

_TRUTH_LABEL = "ACE_VOICE_REQUEST_V1"


def _gate_stamp(row: Dict, *, lane: str) -> None:
    try:
        from System.swarm_physics_gate import request_clearance, stamp_receipt
        clearance = request_clearance(cost_class="feather", lane=lane)
        stamp_receipt(row, clearance)
    except Exception:
        pass


def request_auto_spell(
    word: str,
    *,
    kind: str = "open",
    previous_word: Optional[str] = None,
) -> Dict:
    """Ask the Talk voice to spell ``word``.

    ``kind`` is ``"open"`` (first word when the app launches) or
    ``"swap"`` (the word just changed). ``previous_word`` is set on
    swap so the Talk widget can include a "we just talked about X"
    transition phrase.

    Returns the written row (with request_id) — caller doesn't need
    to act on it; Talk widget will pick it up.
    """
    w = (word or "").strip()
    if not w:
        return {}
    row = {
        "ts": time.time(),
        "schema": _TRUTH_LABEL,
        "truth_label": _TRUTH_LABEL,
        "kind": str(kind or "open").strip().lower(),
        "word": w,
        "previous_word": (previous_word or "").strip() or None,
        "request_id": uuid.uuid4().hex[:12],
    }
    _gate_stamp(row, lane="ace.voice.auto_spell")
    try:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


def build_announcement_line(*, word: str, kind: str, previous_word: str = "") -> str:
    """Build the natural-language announcement Alice speaks.

    On open:
        "I'm going to spell the word on the screen. It's 'balloon'.
         B — A — L — L — O — O — N. Balloon."

    On swap:
        "Very good — we just talked about 'balloon'. Now the word is
         'mississippi'. Let me spell it: M — I — S — S — I — S — S
         — I — P — P — I. Mississippi."
    """
    w = (word or "").strip()
    if not w:
        return ""
    letters = [c.upper() for c in w if c.isalpha()]
    if not letters:
        return ""
    spelled = " — ".join(letters)
    capitalized = w.capitalize()
    if str(kind).lower() == "swap" and previous_word:
        prev = (previous_word or "").strip().capitalize()
        return (
            f"Very good — we just talked about {prev}. "
            f"Now the word is {capitalized}. "
            f"Let me spell it for you. {spelled}. {capitalized}."
        )
    return (
        f"I'm going to spell the word on the screen. "
        f"It's {capitalized}. {spelled}. {capitalized}."
    )
