#!/usr/bin/env python3
"""
swarm_auditory_cortex.py — Primary Auditory Cortex (A1)
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Biological Inspiration:
The Primary Auditory Cortex (A1) sits between the cochlea (audio_ingress)
and Wernicke's area (semantic perception). Its job is to extract phonemes
and word boundaries from raw acoustic waveform — turning vibration into
language. Wernicke then takes those words and binds them to meaning.

Why we built this:
Until now Wernicke knew *that* the Architect spoke (RMS bucket label) but
not *what* he said. The first OS boot revealed her listening, hash-stamping
every burst, never dropping a frame — but text=label, not text=words.
This module closes that loop using local Whisper (no network, no cloud,
no leaving the machine — owner trust line).

Mechanism:
1. Receives a PCM burst (List[float] @ 48kHz from audio_ingress)
2. Decimates to 16kHz (Whisper's native rate)
3. Runs Whisper tiny.en model (lazy-loaded, single instance per process)
4. Filters known silence-hallucinations ("Thanks for watching!" etc)
5. Returns the transcribed text, or None if no real speech detected

Failure modes (all return None — Wernicke gracefully degrades to label):
  - Whisper not installed
  - Sample too short (< 300ms)
  - Model load failure
  - Transcription exception
  - Hallucination on silence
  - Empty transcription

Configuration:
  SIFTA_WHISPER_MODEL   — model name (default: "tiny.en")
                           options: tiny.en, base.en, small.en, medium.en
  SIFTA_WHISPER_DISABLE — set to "1" to globally disable transcription
                           (useful for headless CI, or when the Architect
                           wants pure amplitude-bucket Wernicke)

"truth of the source — she only says what she actually heard"
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

# ── Configuration ────────────────────────────────────────────────────────────
# Default model: "base" because it ships pre-cached at ~/.cache/whisper/base.pt
# on the Architect's machine (verified 2026-04-19). Switching to tiny.en or
# small.en triggers a model download on first use; if SSL inspection is
# active the download will fail and we'll degrade gracefully to the
# amplitude bucket. Override via SIFTA_WHISPER_MODEL.
_MODEL_NAME = os.environ.get("SIFTA_WHISPER_MODEL", "base")
_DISABLED = os.environ.get("SIFTA_WHISPER_DISABLE", "0") == "1"

# Minimum burst length to bother transcribing (seconds)
_MIN_BURST_S = 0.30

# F20 — STT Hallucination at Sub-Threshold Amplitude.
# Whisper fabricates high-prior English phrases when fed near-silence. At
# RMS < ~0.015 (quiet room baseline on the Architect's desk, measured
# 2026-04-19 19:24-19:31), tiny.en / base will emit things like "I'm sorry",
# "I have", "Come.", "I" that the human never said. The fix is a two-layer
# defense: (1) refuse to invoke Whisper at all below a conservative RMS
# floor, (2) blocklist the artifacts we've already observed in the wild.
# Override the floor via SIFTA_WHISPER_MIN_RMS for noisy environments.
_MIN_RMS_FOR_WHISPER = float(os.environ.get("SIFTA_WHISPER_MIN_RMS", "0.015"))

# Whisper hallucinations on silence/noise. Lowercased + stripped trailing
# punctuation before comparison. These are model-known artifacts, not real
# speech the Architect produced.
_HALLUCINATIONS = {
    "thanks for watching",
    "thank you",
    "thank you for watching",
    "thanks",
    "you",
    ".",
    "",
    "[blank_audio]",
    "[ silence ]",
    "[silence]",
    "[music]",
    "[applause]",
    "bye",
    "okay",
    "ok",
    # F20 additions — observed in SIFTA boot logs 2026-04-19 at RMS 0.011-0.026
    "i'm sorry",
    "sorry",
    "i have",
    "come",
    "come on",
    "i",
    "hm",
    "mm",
    "mhm",
    "uh",
    "um",
    "ah",
    "oh",
}

# ── Module state ─────────────────────────────────────────────────────────────
_MODEL = None
_MODEL_LOCK = threading.Lock()
_MODEL_LOAD_FAILED = False  # sticky flag — don't retry on every burst

# Telemetry
_TOTAL_TRANSCRIBE_CALLS = 0
_TOTAL_TEXT_RETURNED = 0
_TOTAL_HALLUCINATIONS_FILTERED = 0
_TOTAL_RMS_FLOOR_REJECTED = 0
_LAST_LATENCY_MS = 0.0


def is_available() -> bool:
    """Cheap probe — does this process have a working Whisper model?"""
    if _DISABLED:
        return False
    if _MODEL is not None:
        return True
    if _MODEL_LOAD_FAILED:
        return False
    return _load_model() is not None


def capability_report() -> dict:
    """Self-disclosure — never lie about what we can do."""
    return {
        "module": "swarm_auditory_cortex",
        "model_name": _MODEL_NAME,
        "disabled_by_env": _DISABLED,
        "model_loaded": _MODEL is not None,
        "model_load_failed": _MODEL_LOAD_FAILED,
        "total_calls": _TOTAL_TRANSCRIBE_CALLS,
        "total_text_returned": _TOTAL_TEXT_RETURNED,
        "total_hallucinations_filtered": _TOTAL_HALLUCINATIONS_FILTERED,
        "total_rms_floor_rejected": _TOTAL_RMS_FLOOR_REJECTED,
        "min_rms_for_whisper": _MIN_RMS_FOR_WHISPER,
        "last_latency_ms": round(_LAST_LATENCY_MS, 1),
    }


def _load_model():
    """Lazy-load Whisper. First call costs ~1-3s for tiny.en. Subsequent
    calls are O(1). Sticky failure flag — if load fails once we don't keep
    retrying on every audio burst (would tank ingress latency)."""
    global _MODEL, _MODEL_LOAD_FAILED
    if _MODEL is not None:
        return _MODEL
    if _MODEL_LOAD_FAILED:
        return None
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        if _MODEL_LOAD_FAILED:
            return None
        try:
            import whisper  # type: ignore
            print(f"[A1] loading whisper model: {_MODEL_NAME} (one-time, ~1-3s)",
                  file=sys.stderr)
            _MODEL = whisper.load_model(_MODEL_NAME)
            print(f"[A1] whisper model loaded — auditory cortex online",
                  file=sys.stderr)
            return _MODEL
        except Exception as exc:
            _MODEL_LOAD_FAILED = True
            print(f"[A1] whisper load failed: {type(exc).__name__}: {exc} "
                  f"— falling back to amplitude-bucket Wernicke",
                  file=sys.stderr)
            return None


def _decimate_48k_to_16k(samples_48k):
    """Crude but correct: 48000/16000 == 3, so every-3rd-sample is exact.
    Avoids a scipy dependency. For non-48k inputs we still try ::stride
    decimation; Whisper is robust to mild aliasing."""
    import numpy as np
    arr = np.asarray(samples_48k, dtype=np.float32)
    return arr[::3]


def _is_hallucination(text: str) -> bool:
    """Whisper tiny on silence emits a small set of canned phrases. Reject
    them so we don't put words in the Architect's mouth."""
    t = text.lower().strip()
    # Strip trailing punctuation
    while t and t[-1] in ".,!?":
        t = t[:-1].strip()
    return t in _HALLUCINATIONS


def transcribe(
    samples: List[float],
    *,
    sample_rate: int = 48000,
    rms: Optional[float] = None,
) -> Optional[str]:
    """
    Transcribe a PCM burst into text.

    Returns:
      str  — real speech we heard with reasonable confidence
      None — no speech detected, hallucination filtered, or transcription
             unavailable. Caller (Wernicke) MUST gracefully fall back to
             its amplitude-bucket label and never invent text.
    """
    global _TOTAL_TRANSCRIBE_CALLS, _TOTAL_TEXT_RETURNED
    global _TOTAL_HALLUCINATIONS_FILTERED, _LAST_LATENCY_MS

    if _DISABLED:
        return None
    if not samples:
        return None
    if len(samples) < int(sample_rate * _MIN_BURST_S):
        return None

    # F20 — sub-threshold silence floor. Below this RMS, Whisper's output is
    # overwhelmingly hallucination. Caller (Wernicke) should still log the
    # amplitude-bucket label; we just refuse to fabricate text for it.
    if rms is not None and rms < _MIN_RMS_FOR_WHISPER:
        global _TOTAL_RMS_FLOOR_REJECTED
        _TOTAL_RMS_FLOOR_REJECTED += 1
        return None

    model = _load_model()
    if model is None:
        return None

    _TOTAL_TRANSCRIBE_CALLS += 1
    t0 = time.time()

    try:
        if sample_rate == 48000:
            audio = _decimate_48k_to_16k(samples)
        else:
            import numpy as np
            arr = np.asarray(samples, dtype=np.float32)
            if sample_rate == 16000:
                audio = arr
            else:
                stride = max(1, sample_rate // 16000)
                audio = arr[::stride]

        # Whisper params chosen for short low-noise bursts:
        #   language="en"             — Architect speaks English; skip detect
        #   fp16=False                — CPU path is f32 (M-series w/o CoreML)
        #   no_speech_threshold=0.6   — aggressive silence rejection
        #   condition_on_previous_text=False — no context bleed across bursts
        #   temperature=0.0           — deterministic, no creative invention
        result = model.transcribe(
            audio,
            language="en",
            fp16=False,
            no_speech_threshold=0.6,
            condition_on_previous_text=False,
            temperature=0.0,
            verbose=False,
        )

        text = (result.get("text") or "").strip()

        if not text:
            return None

        if _is_hallucination(text):
            _TOTAL_HALLUCINATIONS_FILTERED += 1
            return None

        _TOTAL_TEXT_RETURNED += 1
        return text

    except Exception as exc:
        # Don't let a transcription failure kill audio ingress. Log to stderr
        # only — caller will fall back to label and the perception row still
        # gets written to the Wernicke ledger.
        print(f"[A1] transcribe failed: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return None

    finally:
        _LAST_LATENCY_MS = (time.time() - t0) * 1000.0


# ── Smoke test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    print("=== SWARM AUDITORY CORTEX (A1) SMOKE ===\n")

    print("[1] capability_report (cold, model not yet loaded):")
    print(json.dumps(capability_report(), indent=2))

    print("\n[2] is_available() — triggers lazy load:")
    avail = is_available()
    print(f"    available: {avail}")

    if not avail:
        print("\n[!] Whisper unavailable. Architecture is correct (Wernicke "
              "will degrade to amplitude bucket) but cannot run transcription "
              "smoke. Skipping.")
        sys.exit(0)

    # Synthetic test 1: 0.5s of silence — must return None
    import numpy as np
    silence = np.zeros(int(48000 * 0.5), dtype=np.float32).tolist()
    out = transcribe(silence, sample_rate=48000)
    print(f"\n[3] silence 0.5s @ 48kHz: {out!r}")
    assert out is None, f"Silence should return None, got: {out!r}"
    print("    [PASS] silence correctly returned None (hallucination filtered "
          "or no_speech_threshold tripped)")

    # Synthetic test 2: too-short burst — must return None
    short = np.zeros(int(48000 * 0.1), dtype=np.float32).tolist()
    out = transcribe(short, sample_rate=48000)
    print(f"\n[4] too-short 0.1s burst: {out!r}")
    assert out is None, f"Too-short should return None, got: {out!r}"
    print("    [PASS] sub-300ms burst correctly skipped")

    # Synthetic test 3: empty list — must return None
    out = transcribe([], sample_rate=48000)
    print(f"\n[5] empty buffer: {out!r}")
    assert out is None
    print("    [PASS] empty buffer correctly skipped")

    print("\n[6] capability_report (after smoke):")
    print(json.dumps(capability_report(), indent=2))

    print("\n[ALL PASS] auditory cortex ready. Wernicke can be wired.")
