"""Audio source classifier — phone-audio guard + media-vs-voice inference.

Tasks #56 (phone-audio / room-conversation guard) and #59 (media-vs-voice).
Pure stdlib — no PyQt6, no network.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO = Path(__file__).resolve().parent.parent
AUDIO_CLASSIFICATION_LEDGER = REPO / ".sifta_state" / "audio_source_classifications.jsonl"


class AudioSourceType(str, Enum):
    OWNER_DIRECT = "OWNER_DIRECT"
    SIDE_CONVERSATION = "SIDE_CONVERSATION"
    MEDIA_PLAYBACK = "MEDIA_PLAYBACK"
    AMBIENT_NOISE = "AMBIENT_NOISE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class AudioSourceClassification:
    source_type: AudioSourceType
    confidence: float
    reasons: tuple[str, ...] = ()
    should_respond: bool = True
    probe_response: str = ""


_NON_OWNER_NAMES = re.compile(
    r"\b(?:carlton|jordan|hey\s+(?!alice)[a-z]+)\b", re.IGNORECASE
)
_WAKE_WORD = re.compile(r"\balice\b", re.IGNORECASE)
_BROADCAST_PATTERNS = [
    re.compile(r"(?:subscribe|like and share|next episode|welcome back|stay tuned)", re.IGNORECASE),
    re.compile(r"(?:brought to you by|sponsored by|this video)", re.IGNORECASE),
    re.compile(r"(?:ladies and gentlemen|viewers|audience)", re.IGNORECASE),
]


def classify_audio_source(
    text: str,
    *,
    stt_confidence: float = 1.0,
    has_wake_word: bool | None = None,
    owner_voice_match: float | None = None,
    media_playing: bool | None = None,
) -> AudioSourceClassification:
    if not text or not text.strip():
        return AudioSourceClassification(
            source_type=AudioSourceType.AMBIENT_NOISE,
            confidence=0.8,
            reasons=("empty_or_whitespace_only",),
            should_respond=False,
            probe_response="",
        )

    reasons: list[str] = []
    scores: dict[AudioSourceType, float] = {t: 0.0 for t in AudioSourceType}

    wake_present = has_wake_word if has_wake_word is not None else bool(_WAKE_WORD.search(text))

    if wake_present:
        scores[AudioSourceType.OWNER_DIRECT] += 0.4
        reasons.append("wake_word_present")

    if stt_confidence < 0.7:
        scores[AudioSourceType.SIDE_CONVERSATION] += 0.2
        scores[AudioSourceType.MEDIA_PLAYBACK] += 0.1
        reasons.append(f"low_stt_confidence={stt_confidence:.2f}")

    if stt_confidence >= 0.9 and wake_present:
        scores[AudioSourceType.OWNER_DIRECT] += 0.3
        reasons.append("high_confidence_with_wake")

    if _NON_OWNER_NAMES.search(text):
        scores[AudioSourceType.SIDE_CONVERSATION] += 0.3
        reasons.append("non_owner_addressee_detected")

    for pat in _BROADCAST_PATTERNS:
        if pat.search(text):
            scores[AudioSourceType.MEDIA_PLAYBACK] += 0.3
            reasons.append("broadcast_language_detected")
            break

    if media_playing is True:
        scores[AudioSourceType.MEDIA_PLAYBACK] += 0.25
        reasons.append("media_currently_playing")
        if not wake_present:
            scores[AudioSourceType.MEDIA_PLAYBACK] += 0.15
            reasons.append("no_wake_word_during_media")

    if owner_voice_match is not None:
        if owner_voice_match >= 0.8:
            scores[AudioSourceType.OWNER_DIRECT] += 0.3
            reasons.append(f"owner_voice_match={owner_voice_match:.2f}")
        elif owner_voice_match < 0.4:
            scores[AudioSourceType.SIDE_CONVERSATION] += 0.2
            reasons.append(f"non_owner_voice={owner_voice_match:.2f}")

    best_type = max(scores, key=lambda t: scores[t])
    best_score = scores[best_type]

    if best_score < 0.15:
        best_type = AudioSourceType.UNKNOWN
        best_score = 0.5

    should_respond = best_type == AudioSourceType.OWNER_DIRECT or (
        best_type == AudioSourceType.UNKNOWN and wake_present
    )

    probe = ""
    if best_type == AudioSourceType.SIDE_CONVERSATION:
        probe = "(I caught audio but it sounded like a side conversation — not me. Say 'Alice' if you want me.)"
    elif best_type == AudioSourceType.MEDIA_PLAYBACK:
        probe = "(I hear media playing. Say 'Alice' clearly if you need me.)"
    elif best_type == AudioSourceType.AMBIENT_NOISE:
        probe = ""
    elif best_type == AudioSourceType.UNKNOWN:
        probe = "(I caught some audio but could not tell if it was for me. Say 'Alice' if you want my attention.)"

    return AudioSourceClassification(
        source_type=best_type,
        confidence=min(1.0, best_score),
        reasons=tuple(reasons),
        should_respond=should_respond,
        probe_response=probe,
    )


def check_media_playing_macos() -> bool | None:
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get (name of every process whose background only is false)',
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return None
    except (OSError, subprocess.TimeoutExpired):
        return None


def get_wake_word_threshold(media_playing: bool = False) -> float:
    return 0.7 if media_playing else 0.4


def record_classification(classification: AudioSourceClassification, *, turn_id: str = "") -> str:
    row_id = str(uuid4())
    row = {
        "id": row_id,
        "ts": time.time(),
        "source_type": classification.source_type.value,
        "confidence": classification.confidence,
        "should_respond": classification.should_respond,
        "reasons": list(classification.reasons),
        "turn_id": turn_id,
    }
    try:
        AUDIO_CLASSIFICATION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with AUDIO_CLASSIFICATION_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row_id


__all__ = [
    "AudioSourceType",
    "AudioSourceClassification",
    "classify_audio_source",
    "check_media_playing_macos",
    "get_wake_word_threshold",
    "record_classification",
]
