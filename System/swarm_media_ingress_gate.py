#!/usr/bin/env python3
"""Media ingress gate for Alice voice turns.

When the Architect is watching a movie or YouTube video, the room microphone
can transcribe the video's speech and label it as "You". That is false
self/other attribution. This gate keeps that speech as environmental context
unless the utterance explicitly addresses Alice/George or carries a clear
imperative.

It does not block human speech globally. It only fires when a recent focus row
shows YouTube/media context and the utterance looks like third-person dialogue
or narration rather than a direct prompt.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER = STATE_DIR / "media_ingress_gate.jsonl"

DIRECT_ADDRESS_RE = re.compile(r"\b(?:alice|george|architect)\b", re.IGNORECASE)
DIRECT_REQUEST_RE = re.compile(
    r"^\s*(?:"
    r"can you|could you|will you|please|pls|tell me|show me|open|run|fix|"
    r"read|code|write|check|look|watch this|listen|remember|explain|"
    r"hey alice|alice[, ]"
    r")\b",
    re.IGNORECASE,
)
MEDIA_FOCUS_RE = re.compile(
    r"\b(?:youtube|caption_status|caption_excerpt|watching this youtube|"
    r"frontmost.*youtube|video_id|the architect is physically.*watching)\b",
    re.IGNORECASE,
)
NARRATION_RE = re.compile(
    r"\b(?:"
    r"subjects?|oracle|matrix|architect|empire|completion|parameters?|"
    r"consciousness|nature|existence|undoubtedly|accepted the program|"
    r"as i was saying|however|therefore|whereby|99%|the process has altered"
    r")\b",
    re.IGNORECASE,
)


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def _load_recent_youtube_context(max_age_s: float = 900.0) -> str:
    """Best-effort recent YouTube context string; no network calls."""
    path = STATE_DIR / "youtube_context_latest.json"
    if not path.exists():
        return ""
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    try:
        if time.time() - float(row.get("ts", 0.0)) > max_age_s:
            return ""
    except Exception:
        return ""
    title = str(row.get("title") or row.get("video_id") or "")
    status = str(row.get("status") or "")
    return f"YouTube video: {title} caption_status={status}".strip()


def classify_spoken_ingress(
    text: str,
    *,
    stt_conf: float = 0.0,
    focus_context: str = "",
) -> dict[str, Any]:
    """Classify an STT turn as direct speech or ambient media bleed.

    Returns:
      {
        "route": "direct" | "ambient_media",
        "reason": str,
        "confidence": float,
      }
    """
    clean = " ".join(str(text or "").split())
    if not clean:
        return {"route": "ambient_media", "reason": "empty_stt", "confidence": 1.0}

    if DIRECT_ADDRESS_RE.search(clean) or DIRECT_REQUEST_RE.search(clean):
        return {"route": "direct", "reason": "direct_address_or_request", "confidence": 1.0}

    context = focus_context or ""
    has_media_focus = bool(MEDIA_FOCUS_RE.search(context))
    if not has_media_focus:
        return {"route": "direct", "reason": "no_recent_media_focus", "confidence": 0.0}

    words = _word_count(clean)
    narration_score = 0.0
    if words >= 18:
        narration_score += 0.35
    if NARRATION_RE.search(clean):
        narration_score += 0.40
    if stt_conf and stt_conf < 0.66:
        narration_score += 0.25
    if re.search(r"\b(?:he|she|they|subjects?|program|oracle|matrix)\b", clean, re.IGNORECASE):
        narration_score += 0.15

    if narration_score >= 0.45:
        return {
            "route": "ambient_media",
            "reason": "media_focus_plus_narration_shape",
            "confidence": min(1.0, narration_score),
        }
    return {"route": "direct", "reason": "media_focus_but_prompt_like", "confidence": narration_score}


def write_gate_receipt(
    decision: Mapping[str, Any],
    *,
    text: str,
    stt_conf: float = 0.0,
    focus_context: str = "",
) -> dict[str, Any]:
    """Write an append-only media ingress row for tool truth."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "writer": "swarm_media_ingress_gate",
        "route": decision.get("route", "unknown"),
        "reason": decision.get("reason", ""),
        "confidence": float(decision.get("confidence", 0.0) or 0.0),
        "stt_confidence": float(stt_conf or 0.0),
        "text_preview": str(text or "")[:220],
        "focus_preview": str(focus_context or "")[:500],
        "truth_note": (
            "STT line was classified before cortex routing so ambient video "
            "speech does not become an owner command."
        ),
    }
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


__all__ = [
    "classify_spoken_ingress",
    "write_gate_receipt",
]
