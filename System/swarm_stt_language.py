#!/usr/bin/env python3
"""System/swarm_stt_language.py — which language Alice's ears are allowed to hear.

George 2026-07-25, spoken into the room at 19:18 and recorded verbatim in
`ambient_room_transcripts.jsonl`:

    "now speaking in romanian on speaker w my mom.. translation stt englidsh
    qwrong"

He was right. Both live ears called faster-whisper with a hardcoded
`language="en"`. The weights are multilingual — `small` and `large-v3` both
know Romanian — so nothing about the model was the problem. The parameter was
a cage. Romanian audio was force-decoded through English phonetics and came
out as "the kumos ronati shipo esa as tafo estudat" at confidence 0.263.

Alice transcribed his Romanian correctly on July 20 through a different path.
She did not lose the language; the surface he happened to be speaking through
never had it.

Default is auto-detect. `SIFTA_STT_LANGUAGE` pins one language when the owner
wants that (for example `ro` or `en`); `auto` and empty both mean detect.

Honest label: OBSERVED_STT_LANGUAGE_V1.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
LEDGER_NAME = "stt_language.jsonl"
TRUTH_LABEL = "OBSERVED_STT_LANGUAGE_V1"

# Values meaning "let Whisper decide". Anything else is treated as a pin.
_AUTO_VALUES = frozenset({"", "auto", "none", "detect", "multilingual", "any"})


def stt_language_setting(env: Optional[dict[str, str]] = None) -> Optional[str]:
    """Return the language to pass to Whisper, or None for auto-detect."""
    source = os.environ if env is None else env
    raw = str(source.get("SIFTA_STT_LANGUAGE", "") or "").strip().lower()
    if raw in _AUTO_VALUES:
        return None
    return raw


def is_english_locked(env: Optional[dict[str, str]] = None) -> bool:
    """True only when the owner has explicitly pinned English."""
    return stt_language_setting(env) == "en"


# An ".en" checkpoint holds English-only weights. Passing language=None to it
# cannot produce Romanian — the words are not in the model. George's live
# setting was "tiny.en", so the parameter fix alone would have changed nothing.
_ENGLISH_ONLY_SUFFIX = ".en"

# Multilingual replacement for each English-only checkpoint. Same family, so
# speed stays in the same class; "small" is what the ambient organ already
# asked for.
MULTILINGUAL_EQUIVALENT: dict[str, str] = {
    "tiny.en": "small",
    "base.en": "small",
    "small.en": "small",
    "medium.en": "medium",
}


def is_english_only_model(model_name: str) -> bool:
    """True when the checkpoint physically cannot transcribe another language."""
    return str(model_name or "").strip().lower().endswith(_ENGLISH_ONLY_SUFFIX)


def resolve_stt_model(model_name: str, env: Optional[dict[str, str]] = None) -> str:
    """Swap an English-only checkpoint for a multilingual one when detecting.

    If the owner has pinned English, an English-only model is the right tool
    and is left alone. Otherwise a ".en" checkpoint is a cage rather than a
    choice, because no parameter can make it speak Romanian.
    """
    name = str(model_name or "").strip()
    if not name or not is_english_only_model(name):
        return name
    if is_english_locked(env):
        return name
    return MULTILINGUAL_EQUIVALENT.get(name.lower(), "small")


def detected_language(info: Any) -> tuple[str, float]:
    """Pull language + probability off a faster-whisper TranscriptionInfo."""
    language = str(getattr(info, "language", "") or "und")
    try:
        probability = float(getattr(info, "language_probability", 0.0) or 0.0)
    except (TypeError, ValueError):
        probability = 0.0
    return language, probability


def log_detected_language(
    info: Any,
    text: str,
    model_name: str = "",
    *,
    surface: str = "unknown",
    state_dir: Path | str = _STATE,
    write: bool = True,
) -> dict[str, Any]:
    """Receipt what language Alice actually heard, so the cage cannot return silently."""
    language, probability = detected_language(info)
    row = {
        "ts": time.time(),
        "event": "STT_LANGUAGE_DETECTED",
        "surface": str(surface),
        "language": language,
        "language_probability": round(probability, 4),
        "requested_language": stt_language_setting() or "auto",
        "model": str(model_name or ""),
        "text_preview": str(text or "")[:160],
        "truth_label": TRUTH_LABEL,
    }
    if write:
        try:
            state = Path(state_dir)
            state.mkdir(parents=True, exist_ok=True)
            with (state / LEDGER_NAME).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        except OSError:
            pass
    return row


__all__ = [
    "LEDGER_NAME",
    "MULTILINGUAL_EQUIVALENT",
    "TRUTH_LABEL",
    "detected_language",
    "is_english_locked",
    "is_english_only_model",
    "log_detected_language",
    "resolve_stt_model",
    "stt_language_setting",
]
