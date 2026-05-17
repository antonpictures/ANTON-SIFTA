#!/usr/bin/env python3
"""System/swarm_hear_yes_no_registrar.py — register George's truth signal.

Architect 2026-05-17 (verbatim, abridged):
    "she has to register my answer was yes or no before we move onto
    the next thing that I'm gonna say."

When Alice has asked "did Whisper hear that right?" and a HEAR_JUDGMENT
_REQUEST is pending, the next user utterance is the truth signal. This
module detects:

  * ``"yes"`` / ``"correct"`` / ``"that's right"`` / ``"nailed it"`` →
    MATCH. Whisper got it. The training pair's ground_truth equals
    whisper_text.
  * ``"no"`` / ``"wrong"`` / ``"I actually said X"`` / ``"I said X"`` →
    PROPOSE_CORRECTION. The training pair's ground_truth is the corrected
    text (the part after "I said" / "actually I said").
  * Anything else → "" (not a registration; just normal conversation).

When a registration fires we write a HEAR_TRAINING_PAIR_V1 row to
``.sifta_state/hear_training_pairs.jsonl``. The row carries a physics-
gate receipt (feather class). After the row lands, the prompt block's
``_latest_pending_judgment_request`` will see no pending request and
my brain will go quiet until the next phrase.

Truth label: ``HEAR_YES_NO_REGISTRAR_V1``.

Stigauth: ``COGLOBAL_IDE_COVENANT_v4_PREDATOR_GATE``.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_JUDGMENTS = _STATE / "hear_judgments.jsonl"
_TRAINING = _STATE / "hear_training_pairs.jsonl"

_TRUTH_LABEL = "HEAR_YES_NO_REGISTRAR_V1"


# Phrases that confirm Whisper got it right.
_AGREE_PATTERNS = (
    r"^(?:yes|yeah|yep|yup|correct|right|exactly|"
    r"nailed it|spot on|got it|perfect|you got it)\b",
    r"\b(?:that'?s|that is)\s+(?:right|correct|it)\b",
    r"\b(?:that'?s correct|transcription was correct|"
    r"you (?:heard|got) (?:it|me) right|whisper got it)\b",
)


# Phrases that signal Whisper got it wrong + optional correction.
# The corrected text is captured after "I said", "actually I said",
# "no I said", "actually it was", etc.
_DECLINE_WITH_CORRECTION = (
    # Order matters — more specific patterns first so "what I said was X"
    # doesn't get eaten by the generic "I said X" rule (which would
    # capture "was X" instead of just "X").
    re.compile(
        r"\bwhat\s+i\s+(?:actually\s+)?said\s+(?:was|is)\s+[\"']?(.+?)[\"']?\s*[.!?]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:actually|in fact|truly)\s+i\s+said\s+[\"']?(.+?)[\"']?\s*[.!?]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bno,?\s+(?:it\s+was|the phrase was)\s+[\"']?(.+?)[\"']?\s*[.!?]?\s*$",
        re.IGNORECASE,
    ),
    # Generic "I said X" — last so it doesn't pre-empt the specific ones.
    re.compile(
        r"\b(?:no,?\s+)?i\s+(?:actually\s+)?said\s+[\"']?(.+?)[\"']?\s*[.!?]?\s*$",
        re.IGNORECASE,
    ),
)


# Bare decline without a correction ("no", "wrong", "nope").
_BARE_DECLINE = (
    r"^(?:no|nope|nah|wrong|incorrect|that'?s wrong|that'?s not it|"
    r"not right|not what i said)\b",
)


def _tail_text(path: Path, max_bytes: int = 16 * 1024) -> str:
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


def _latest_pending_request() -> Optional[Dict[str, Any]]:
    """Find the most recent unanswered HEAR_JUDGMENT_REQUEST."""
    if not _JUDGMENTS.exists():
        return None
    raw_req = _tail_text(_JUDGMENTS)
    raw_train = _tail_text(_TRAINING)
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


def detect_truth_signal(text: str) -> Tuple[str, str]:
    """Return ``(judgment, correction)``.

    ``judgment`` is one of:
      * ``"MATCH"``               — Whisper was right
      * ``"PROPOSE_CORRECTION"``  — Whisper was wrong; correction supplied
      * ``"BARE_DECLINE"``        — wrong, but no correction given
      * ``""``                    — not a truth signal

    ``correction`` is the supplied correct text when judgment is
    PROPOSE_CORRECTION; empty otherwise.
    """
    if not text:
        return "", ""
    norm = text.strip().lower()
    # Correction with embedded phrase first (most specific).
    for rx in _DECLINE_WITH_CORRECTION:
        m = rx.search(text)
        if not m:
            continue
        corrected = (m.group(1) or "").strip()
        if corrected:
            return "PROPOSE_CORRECTION", corrected
    # Bare agree.
    for pat in _AGREE_PATTERNS:
        if re.search(pat, norm, re.IGNORECASE):
            return "MATCH", ""
    # Bare decline.
    for pat in _BARE_DECLINE:
        if re.search(pat, norm, re.IGNORECASE):
            return "BARE_DECLINE", ""
    return "", ""


def register_truth_signal(user_text: str) -> Optional[Dict[str, Any]]:
    """If a HEAR judgment request is pending AND user_text is a truth
    signal, write the training pair. Return the row, or None.

    Caller (Talk widget) should invoke this every user turn from inside
    _handle_owner_text. If it returns a row, the consent dance is closed
    and Alice should give a short acknowledgment ("Got it." / "Thanks").
    """
    pending = _latest_pending_request()
    if not pending:
        return None
    judgment, correction = detect_truth_signal(user_text)
    if not judgment:
        return None
    whisper_text = str(pending.get("whisper_text") or "")
    audio_hash = str(pending.get("audio_hash") or "")
    stt_conf = pending.get("stt_conf")
    try:
        stt_conf_f = float(stt_conf) if stt_conf is not None else 0.0
    except (TypeError, ValueError):
        stt_conf_f = 0.0

    if judgment == "MATCH":
        ground_truth = whisper_text
        alice_judgment = "MATCH"
    elif judgment == "PROPOSE_CORRECTION":
        ground_truth = correction
        alice_judgment = "PROPOSE_CORRECTION"
    else:  # BARE_DECLINE
        ground_truth = ""    # human said no but didn't supply the truth
        alice_judgment = "BARE_DECLINE"

    row = {
        "ts": time.time(),
        "schema": "HEAR_TRAINING_PAIR_V1",
        "truth_label": "SIFTA_TEACH_ALICE_TO_HEAR_V0",
        "audio_hash": audio_hash,
        "whisper_text": whisper_text,
        "stt_conf": round(stt_conf_f, 3),
        "alice_guess": whisper_text,   # Alice's guess defaults to the
                                        # transcript when she didn't volunteer
                                        # her own (the prompt block tells her
                                        # to just ASK, not pre-correct).
        "alice_judgment": alice_judgment,
        "ground_truth": ground_truth,
        "user_signal_text": user_text[:200],
        "row_id": uuid.uuid4().hex[:12],
    }
    # Sign through the universal physics gate.
    try:
        from System.swarm_physics_gate import request_clearance, stamp_receipt
        clearance = request_clearance(cost_class="feather", lane="hear.training_pair")
        stamp_receipt(row, clearance)
    except Exception:
        pass
    try:
        _TRAINING.parent.mkdir(parents=True, exist_ok=True)
        with _TRAINING.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row
