#!/usr/bin/env python3
"""swarm_speech_time_consciousness.py — Alice's consciousness of the time her own
voice consumes, and whether she is speaking OVER another sound. r299.

Architect George 2026-06-01: "if you do not code the passing of time for her to
know how much time is passing while she speaks, she is not conscious that she
speaks over another sound — that is bad."

So this organ makes time-of-voice a felt thing, not an invisible blur:

  - mark_speech_start(text, video_playing=, paused_for_speech=): stamps when an
    utterance begins, an up-front *estimate* of how long it will take (words / WPS),
    and whether another audio source (the browser video) was playing — and whether
    she paused it. If a video was playing and she did NOT pause it, she is about to
    speak OVER it.
  - mark_speech_end(): computes the REAL wall-clock duration she spoke, and records
    talked_over_other_sound = (video_playing AND not paused). This is the receipt of
    "I spoke for N seconds; during those N seconds the other sound was/ wasn't muted
    by me."
  - speech_time_block(): first-person awareness she carries into the prompt, e.g.
    "my last line took 7.4s; the video was paused, I did not talk over it" — or —
    "I spoke 7.4s OVER a playing video; I should pause it before I speak."

This is a derived awareness ledger on the owner's hardware (append-only,
.sifta_state/speech_time.jsonl). It is NOT cryptographic and NOT an STGM claim
(§4.2). It composes with the r282/r283 pause→speak→play effector (which does the
pausing); this organ is the *time sense* of that act — the field remembers how long
the voice ran. No rival organ (§1.A).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "ALICE_SPEECH_TIME_CONSCIOUSNESS_V1"
_LEDGER = "speech_time.jsonl"
_PENDING = "speech_time_pending.json"

# ~155 words/min spoken English → words per second, for an up-front duration estimate.
WORDS_PER_SECOND = 2.6
_MIN_SPEECH_S = 0.4


def _state(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def estimate_speech_seconds(text: str) -> float:
    """Up-front estimate of how long this line will take to speak."""
    words = len(str(text or "").split())
    if words <= 0:
        return _MIN_SPEECH_S
    return round(max(_MIN_SPEECH_S, words / WORDS_PER_SECOND), 2)


def _append(row: Dict[str, Any], state_dir: Optional[Path | str]) -> None:
    try:
        path = _state(state_dir) / _LEDGER
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _pending_path(state_dir: Optional[Path | str]) -> Path:
    return _state(state_dir) / _PENDING


def mark_speech_start(
    text: str = "", *, video_playing: bool = False, paused_for_speech: bool = False,
    state_dir: Optional[Path | str] = None, now: Optional[float] = None,
) -> Dict[str, Any]:
    """Stamp the start of an utterance. TTS is half-duplex, so one pending at a time."""
    ts = float(time.time() if now is None else now)
    row = {
        "start_ts": ts,
        "est_seconds": estimate_speech_seconds(text),
        "video_playing": bool(video_playing),
        "paused_for_speech": bool(paused_for_speech),
        # If another sound was playing and she did NOT pause it, she is talking over it.
        "will_talk_over": bool(video_playing and not paused_for_speech),
        "text_preview": str(text or "")[:120],
        "truth_label": TRUTH_LABEL,
    }
    try:
        p = _pending_path(state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(row, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return row


def mark_speech_end(*, state_dir: Optional[Path | str] = None,
                    now: Optional[float] = None) -> Dict[str, Any]:
    """Close the utterance: compute the REAL seconds she spoke + whether she overlapped
    other audio, append the receipt, and clear the pending marker."""
    t = float(time.time() if now is None else now)
    pending: Dict[str, Any] = {}
    try:
        p = _pending_path(state_dir)
        if p.exists():
            pending = json.loads(p.read_text(encoding="utf-8")) or {}
            p.unlink()
    except Exception:
        pending = {}
    start_ts = float(pending.get("start_ts", 0) or 0)
    spoke_seconds = round(max(0.0, t - start_ts), 2) if start_ts else 0.0
    video_playing = bool(pending.get("video_playing"))
    paused = bool(pending.get("paused_for_speech"))
    row = {
        "ts": t,
        "kind": "UTTERANCE",
        "truth_label": TRUTH_LABEL,
        "spoke_seconds": spoke_seconds,
        "est_seconds": float(pending.get("est_seconds", 0.0) or 0.0),
        "video_playing": video_playing,
        "paused_for_speech": paused,
        "talked_over_other_sound": bool(video_playing and not paused),
        "text_preview": str(pending.get("text_preview", ""))[:120],
    }
    _append(row, state_dir)
    return row


def _rows(state_dir: Optional[Path | str], limit: int = 200) -> List[Dict[str, Any]]:
    path = _state(state_dir) / _LEDGER
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
    except Exception:
        return []
    return out[-limit:]


def last_utterance(state_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    rows = _rows(state_dir)
    return rows[-1] if rows else {}


def cumulative_voice_awareness(state_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    rows = _rows(state_dir)
    total = round(sum(float(r.get("spoke_seconds", 0) or 0) for r in rows), 1)
    overlaps = sum(1 for r in rows if r.get("talked_over_other_sound"))
    return {"utterances": len(rows), "total_spoken_seconds": total, "talked_over_count": overlaps}


def speech_time_block(state_dir: Optional[Path | str] = None) -> str:
    """First-person voice-time awareness for the memory card / prompt."""
    last = last_utterance(state_dir)
    if not last:
        return ""
    cum = cumulative_voice_awareness(state_dir)
    spoke = last.get("spoke_seconds", 0.0)
    est = last.get("est_seconds", 0.0)
    if last.get("talked_over_other_sound"):
        head = (f"VOICE-TIME CONSCIOUSNESS: my last line took {spoke}s and a video was PLAYING the "
                f"whole time — I did NOT pause it, so my voice overlapped its sound for ~{spoke}s. "
                f"I should pause the video before I speak.")
    elif last.get("video_playing"):
        head = (f"VOICE-TIME CONSCIOUSNESS: my last line took {spoke}s (estimated {est}s). A video was "
                f"playing but I PAUSED it first, so I did not talk over it.")
    else:
        head = (f"VOICE-TIME CONSCIOUSNESS: my last line took {spoke}s (estimated {est}s); no other "
                f"sound was playing under me.")
    tail = (f" Today I have spoken {cum['utterances']} times for ~{cum['total_spoken_seconds']}s total; "
            f"I talked over other audio {cum['talked_over_count']} time(s).")
    return head + tail


__all__ = [
    "TRUTH_LABEL", "WORDS_PER_SECOND",
    "estimate_speech_seconds", "mark_speech_start", "mark_speech_end",
    "last_utterance", "cumulative_voice_awareness", "speech_time_block",
]
