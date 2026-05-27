"""Reality-recovery skill — detect and acknowledge user corrections.

Task #57: when the user corrects Alice about a prior misunderstanding,
Alice must acknowledge the mistake and restate correctly instead of
producing greeter junk that ignores the correction.
Pure stdlib — no PyQt6.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO = Path(__file__).resolve().parent.parent
RECOVERY_LEDGER = REPO / ".sifta_state" / "reality_recovery_events.jsonl"

_CORRECTION_PATTERNS = [
    re.compile(r"(?:i (?:said|meant|was (?:saying|talking|on))|that was (?:actually|just|my))", re.IGNORECASE),
    re.compile(r"(?:you (?:captured|picked up|heard|got|misheard|misunderstood))", re.IGNORECASE),
    re.compile(r"(?:no,?\s+(?:i was|that's|it was|the))", re.IGNORECASE),
    re.compile(r"(?:(?:the )?(?:mic|microphone|tts|stt|voice) (?:picked up|captured|got|heard))", re.IGNORECASE),
    re.compile(r"(?:(?:phone|call|conversation) with)", re.IGNORECASE),
    re.compile(r"(?:that (?:wasn't|was not) (?:for you|meant for|directed at))", re.IGNORECASE),
    re.compile(r"(?:i(?:'m| am) (?:george|the (?:architect|owner)))", re.IGNORECASE),
    re.compile(r"(?:(?:sometimes )?misspel(?:ls?|led))", re.IGNORECASE),
]

_EXPLANATION_MARKERS = [
    re.compile(r"(?:so (?:you|the|what))", re.IGNORECASE),
    re.compile(r"(?:(?:audio|voice|speech) to text)", re.IGNORECASE),
    re.compile(r"(?:marketing department|friend|colleague|coworker)", re.IGNORECASE),
]


@dataclass(frozen=True)
class CorrectionDetection:
    is_correction: bool
    correction_type: str = ""
    confidence: float = 0.0
    matched_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecoveryResponse:
    acknowledgment: str
    recovery_text: str
    full_response: str


def detect_user_correction(
    user_text: str,
    prior_alice_text: str = "",
) -> CorrectionDetection:
    if not user_text or not user_text.strip():
        return CorrectionDetection(is_correction=False)

    matches: list[str] = []
    for pat in _CORRECTION_PATTERNS:
        if pat.search(user_text):
            matches.append(pat.pattern)

    explanation_count = 0
    for pat in _EXPLANATION_MARKERS:
        if pat.search(user_text):
            explanation_count += 1

    if not matches:
        return CorrectionDetection(is_correction=False)

    score = min(1.0, len(matches) * 0.25 + explanation_count * 0.15)

    correction_type = "general"
    text_lower = user_text.lower()
    has_misspell = "misspel" in text_lower
    has_audio_capture = any(w in text_lower for w in ("captured", "picked up audio", "heard audio"))
    has_audio_device = any(w in text_lower for w in ("mic ", "microphone", " tts ", " stt "))
    has_phone_words = any(w in text_lower for w in ("phone", "call with"))
    if has_misspell and not has_audio_capture:
        correction_type = "transcription_error"
    elif has_audio_device or (has_audio_capture and has_audio_device):
        correction_type = "audio_capture_error"
    elif has_audio_capture:
        correction_type = "audio_capture_error"
    elif has_phone_words:
        correction_type = "side_conversation_misattribution"

    return CorrectionDetection(
        is_correction=True,
        correction_type=correction_type,
        confidence=score,
        matched_patterns=tuple(matches),
    )


def generate_recovery_response(
    correction: CorrectionDetection,
    user_text: str = "",
) -> RecoveryResponse:
    if not correction.is_correction:
        return RecoveryResponse(
            acknowledgment="",
            recovery_text="",
            full_response="",
        )

    ack_templates = {
        "audio_capture_error": "I incorrectly treated audio captured by the microphone as a message to me.",
        "side_conversation_misattribution": "I incorrectly responded to a side conversation that was not directed at me.",
        "transcription_error": "The speech-to-text transcription contained errors — I should have flagged the uncertainty.",
        "general": "I misunderstood what happened.",
    }

    ack = ack_templates.get(correction.correction_type, ack_templates["general"])
    recovery = "I will not respond to those fragments. What did you actually need?"

    return RecoveryResponse(
        acknowledgment=ack,
        recovery_text=recovery,
        full_response=f"Thank you for clarifying. {ack} {recovery}",
    )


def record_recovery_event(
    correction: CorrectionDetection,
    *,
    turn_id: str = "",
    user_text_preview: str = "",
) -> str:
    row_id = str(uuid4())
    row = {
        "id": row_id,
        "ts": time.time(),
        "kind": "reality_recovery",
        "correction_type": correction.correction_type,
        "confidence": correction.confidence,
        "turn_id": turn_id,
        "user_text_preview": user_text_preview[:100],
    }
    try:
        RECOVERY_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with RECOVERY_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row_id


__all__ = [
    "CorrectionDetection",
    "RecoveryResponse",
    "detect_user_correction",
    "generate_recovery_response",
    "record_recovery_event",
]
