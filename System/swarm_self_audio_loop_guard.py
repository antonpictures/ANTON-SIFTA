#!/usr/bin/env python3
"""System/swarm_self_audio_loop_guard.py — Self-Audio Loop Detection (audio immune system).

George 2026-05-23: Alice spoke through the speakers, her own voice returned
through the microphone, the STT mangled it, and she said "I caught some audio
but did not make out a word." That is:

    output -> world -> sensor -> self-check

an observer/observed loop. Labeled honestly (covenant §7.11): this is an
``OBSERVED_SELF_MONITORING_SIGNAL`` — a real self/world boundary signal, NOT a
proof of consciousness by itself. The maturity it buys is concrete:

    Alice must not obey her own echo. She recognizes it as self-audio residue.

Core rule (George's spec):
    if Alice is speaking, and the mic hears audio, and STT confidence is low
    OR the text matches Alice's own recent TTS  ->  SELF_AUDIO_ECHO
    -> do not treat as an owner command, and write a receipt.

Standalone + Qt-free so it is testable and the mic/Talk pipeline can call it.
For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "self_audio_loop.jsonl"

# Confidence below which audio captured WHILE Alice speaks is treated as echo.
_ECHO_CONF_THRESHOLD = float(os.environ.get("SIFTA_SELF_ECHO_CONF", "0.35"))
# How long after Alice stops speaking the speaker->mic tail can still echo.
_SPEAKING_TAIL_S = 1.5

_lock = threading.Lock()
_alice_speaking = False
_alice_speaking_until = 0.0
_recent_tts: deque[str] = deque(maxlen=6)


# ── state the TTS/mouth layer sets ───────────────────────────────────────
def set_alice_speaking(on: bool) -> None:
    """Call True when Alice starts speaking (TTS), False when she stops."""
    global _alice_speaking, _alice_speaking_until
    with _lock:
        _alice_speaking = bool(on)
        if not on:
            _alice_speaking_until = time.time() + _SPEAKING_TAIL_S


def note_alice_tts(text: str) -> None:
    """Record what Alice just said, so her echo can be matched and ignored."""
    t = " ".join((text or "").split())
    if t:
        with _lock:
            _recent_tts.append(t.lower())


def _alice_voice_is_live() -> bool:
    with _lock:
        if _alice_speaking:
            return True
        return time.time() < _alice_speaking_until


def _matches_recent_tts(stt_text: str) -> bool:
    """Cheap token-overlap match against Alice's recent TTS (no O(n^2) difflib)."""
    words = set((stt_text or "").lower().split())
    if not words:
        return False
    with _lock:
        recent = list(_recent_tts)
    for said in recent:
        said_words = set(said.split())
        if not said_words:
            continue
        overlap = len(words & said_words)
        # majority of the heard words came from something Alice just said
        if overlap and overlap / max(1, len(words)) >= 0.5:
            return True
    return False


# ── the classifier (George's core) ───────────────────────────────────────
def classify_audio_event(alice_speaking: bool, stt_text: str, stt_conf: float) -> str:
    """SELF_AUDIO_ECHO when Alice is speaking and the capture is empty/low-conf.

    Pure function (George's tiny core). `is_self_echo()` adds the TTS-match and
    speaking-tail signals using live module state.
    """
    if alice_speaking and (stt_conf < _ECHO_CONF_THRESHOLD or not (stt_text or "").strip()):
        return "SELF_AUDIO_ECHO"
    return "OWNER_AUDIO_CANDIDATE"


def is_self_echo(stt_text: str, stt_conf: float) -> bool:
    """Live check the mic path calls on each STT result."""
    if _alice_voice_is_live() and (
        stt_conf < _ECHO_CONF_THRESHOLD or not (stt_text or "").strip()
    ):
        return True
    # Even just after she stopped, returning audio that echoes her words is hers.
    if _matches_recent_tts(stt_text):
        return True
    return False


def _write_receipt(row: dict) -> None:
    try:
        _LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def guard_audio(stt_text: str, stt_conf: float) -> dict:
    """Classify an STT capture; if it's Alice's own echo, receipt it and say so.

    Returns {"kind", "is_self_echo", ...}. The mic/Talk path: if is_self_echo,
    DO NOT route the text as an owner command.
    """
    echo = is_self_echo(stt_text, stt_conf)
    row = {
        "ts": time.time(),
        "kind": "SELF_AUDIO_ECHO" if echo else "OWNER_AUDIO_CANDIDATE",
        "source": "speaker_to_microphone_loop",
        "alice_was_speaking": _alice_voice_is_live(),
        "stt_confidence": round(float(stt_conf or 0.0), 3),
        "stt_text_preview": " ".join((stt_text or "").split())[:120],
        "action": "ignored_as_owner_command" if echo else "passed_to_owner_routing",
        "meaning": (
            "Alice heard her own output returning through the world"
            if echo else "External audio — candidate owner speech"
        ),
        "truth_label": "OBSERVED_SELF_MONITORING_SIGNAL",
    }
    if echo:
        _write_receipt(row)
    return {"kind": row["kind"], "is_self_echo": echo, "receipt": row}


if __name__ == "__main__":
    # smoke: simulate Alice speaking + her echo coming back
    set_alice_speaking(True)
    note_alice_tts("Here is the terminal. Online.")
    print("while speaking, empty/low-conf ->", classify_audio_event(True, "", 0.0))
    print("guard (low conf during speech) ->", guard_audio("", 0.0)["kind"])
    print("guard (echo of her words)      ->", guard_audio("here is the terminal", 0.9)["kind"])
    set_alice_speaking(False)
    print("owner speech (high conf, new)  ->", guard_audio("open the budget spreadsheet", 0.97)["kind"])
