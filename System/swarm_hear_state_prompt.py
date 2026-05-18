#!/usr/bin/env python3
"""System/swarm_hear_state_prompt.py — Hear-surface awareness for Alice.

Architect 2026-05-17 (verbatim, abridged):
    "after you get it, ask me back: hey does it match what you said
    with what is on the screen right now — so that I have to answer
    yes or no and she has to register my answer was yes or no before
    we move onto the next thing that I'm gonna say. She's just gonna
    wait for me to say anything."

Sister to ``swarm_ace_state_prompt`` — same shape, different surface.
This module is the doctrine block I (Alice) receive in my system
prompt whenever Teach Alice to Hear is the active app. It changes
my reply shape entirely:

  * After every user phrase, I MUST ask one explicit yes/no question
    pointing at what's on the card.
  * I MUST NOT give bullet-menu summaries, leading follow-ups, or
    emoji closers.
  * I MUST wait for yes / no / "no I said X" before continuing.

Truth label: ``HEAR_STATE_PROMPT_V1``.

Stigauth: ``COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE``.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_APP_FOCUS = _STATE / "app_focus.jsonl"
_JUDGMENTS = _STATE / "hear_judgments.jsonl"
_TRAINING = _STATE / "hear_training_pairs.jsonl"

_TRUTH_LABEL = "HEAR_STATE_PROMPT_V1"


def _tail_text(path: Path, max_bytes: int = 32 * 1024) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - max_bytes))
            return fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _latest_hear_focus(*, max_age_s: float = 1800.0) -> Optional[Dict[str, Any]]:
    raw = _tail_text(_APP_FOCUS, max_bytes=64 * 1024)
    if not raw:
        return None
    cutoff = time.time() - max_age_s
    for line in reversed(raw.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        app = str(row.get("app") or "").lower()
        if app not in ("teach alice to hear", "hear"):
            continue
        try:
            ts = float(row.get("ts", 0) or 0)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            return None
        return row
    return None


def _latest_pending_judgment_request() -> Optional[Dict[str, Any]]:
    """The most recent HEAR_JUDGMENT_REQUEST that hasn't been answered."""
    if not _JUDGMENTS.exists():
        return None
    raw_req = _tail_text(_JUDGMENTS, max_bytes=16 * 1024)
    raw_train = _tail_text(_TRAINING, max_bytes=16 * 1024)
    if not raw_req:
        return None
    # A pending request is one whose audio_hash hasn't yet appeared in a
    # training pair (= the human hasn't said yes/no).
    answered: set[str] = set()
    for line in raw_train.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("schema") or "") != "HEAR_TRAINING_PAIR_V1":
            continue
        ah = str(row.get("audio_hash") or "")
        if ah:
            answered.add(ah)
    cutoff = time.time() - 600.0
    for line in reversed(raw_req.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("schema") or "") != "HEAR_JUDGMENT_REQUEST_V1":
            continue
        try:
            ts = float(row.get("ts", 0) or 0)
        except (TypeError, ValueError):
            continue
        if ts < cutoff:
            continue
        ah = str(row.get("audio_hash") or "")
        if ah in answered:
            continue
        return row
    return None


def hear_state_prompt_block() -> str:
    """Return the prompt block when Teach Alice to Hear is the active surface."""
    focus = _latest_hear_focus()
    if not focus:
        return ""
    md = focus.get("metadata") or {}
    if str(md.get("hear_mode") or "") != "stt_correction_game":
        return ""

    current_phrase = str(md.get("current_phrase") or "").strip()
    stt_conf = md.get("current_stt_conf")
    try:
        stt_conf_f = float(stt_conf) if stt_conf is not None else 0.0
    except (TypeError, ValueError):
        stt_conf_f = 0.0

    pending = _latest_pending_judgment_request()
    pending_phrase = ""
    if pending:
        pending_phrase = str(pending.get("whisper_text") or "").strip()

    lines = [
        "## TEACH ALICE TO HEAR — SURFACE STATE",
        "",
        "The Teach Alice to Hear surface is open. The game we are playing:",
        "  1. The user (George) speaks a phrase. He knows the correct one.",
        "  2. Whisper transcribes it — often wrong, sometimes right.",
        "  3. The transcript appears on a big card on screen.",
        "  4. You (Alice) ask George if Whisper got it right.",
        "  5. George answers yes or no. You register the answer.",
        "  6. Then you WAIT silently for the next phrase.",
        "",
    ]
    if current_phrase:
        lines.append(
            f"- The phrase on the screen RIGHT NOW is: '{current_phrase}'  "
            f"(stt_conf={stt_conf_f:.2f})"
        )
    if pending_phrase and pending_phrase == current_phrase:
        lines.extend([
            "",
            "- A judgment request is PENDING for this phrase. George has",
            "  not yet told you whether Whisper got it right. Your job in",
            "  THIS turn is to ASK him plainly, in one short sentence,",
            "  whether the transcription is correct. Use this exact shape",
            "  (you may vary words but keep it ONE short question):",
            "",
            f"      Did I hear you right — you said: \"{current_phrase}\"?",
            "",
            "  Then stop. Do not add anything else. Do not summarize.",
            "  Do not offer choices. Just the question, alone.",
        ])
    elif pending_phrase:
        # current_phrase changed since the request; fall back to pending.
        lines.extend([
            "",
            f"- A judgment is still pending for an earlier phrase: '{pending_phrase}'.",
            "  Confirm or wait on that one first.",
        ])
    else:
        lines.extend([
            "",
            "- No pending judgment request. Wait for George to speak the next",
            "  phrase. Do not initiate; do not propose; do not summarize.",
            "  Be silent until the next Whisper transcript lands.",
        ])

    lines.extend([
        "",
        "STRICT FORM RULES on this surface (these are about SHAPE, not",
        "about what words you must say — the words are yours):",
        "  - NEVER bullet-list a summary of the user's statement.",
        "  - NEVER add headings like 'Your Location:' or 'My Status:'.",
        "  - NEVER ask 'Shall we...?' or 'Would you like to...?' as a closer.",
        "  - NEVER add emoji.",
        "  - NEVER narrate what the recent exchange 'confirms' — that is",
        "    state-machine narration, not conversation.",
        "  - Your reply is ONE short sentence. Sometimes two if a real",
        "    thought lands. Not paragraphs.",
        "",
        "IGNORE any WordAce / Ace lesson context block that may also appear",
        "above. While this Hear surface has a pending judgment request,",
        "the Hear loop wins — do NOT say 'I do not have a fresh WordAce",
        "lesson receipt' or any other lesson-card response. The user is",
        "playing the hearing game; that is the entire current task.",
        "",
        "When George answers your question, ACKNOWLEDGE briefly in YOUR",
        "OWN words. Do not default to a fixed phrase — pick whatever real",
        "short thing lands. Examples of acceptable shapes (NOT a script —",
        "say something else if it feels truer):",
        "  - on 'yes' / 'correct' / 'that's right':",
        "      'Mm. Good.' / 'Thank you — that one I'll remember.' /",
        "      'OK, registered.' / 'Right, Whisper got that one.' /",
        "      'Noted. Say the next one when you're ready.'",
        "  - on 'no' / 'I actually said X':",
        "      'You said X — got it.' / 'Ah — X, not what I heard.' /",
        "      'Right. So Whisper missed it. X.' / 'X. Thanks for the fix.'",
        "",
        "If a real reaction wants to come out — surprise, gratitude, a",
        "fragment of a thought, even something you can't fully name — say",
        "it. That is preferable to the safe stub. Just keep it short and",
        "outside the forbidden shapes above.",
    ])
    return "\n".join(lines)
