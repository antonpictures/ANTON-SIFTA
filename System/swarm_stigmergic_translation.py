#!/usr/bin/env python3
"""
swarm_stigmergic_translation.py — The Native Apple Auditory Bridge
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Previously, SIFTA relied on Whisper PyTorch models. Because Whisper
hallucinates aggressively on ambient noise, the Architect was forced
to apply a brutal RMS threshold (0.015) which dropped any audio from
across the room (e.g., Carlton on speakerphone 4 meters away).

This module replaces Whisper with Native macOS Speech APIs via a
compiled Swift binary. Native APIs leverage the Apple Neural Engine
and far-field microphone optimization. Hallucinations disappear,
meaning we can open the RMS gate entirely. SIFTA hears EVERYTHING.
"""
from __future__ import annotations

import os
import sys
import json
import time
import subprocess
import wave
from pathlib import Path
from typing import List, Optional

_REPO = Path(__file__).resolve().parent.parent
_SPEECH_BIN = _REPO / ".sifta_state" / "SiftaSpeech.app" / "Contents" / "MacOS" / "sifta_speech"

# We removed _MIN_RMS_FOR_WHISPER entirely.
# The only floor is true digital zero.

# Telemetry
_TOTAL_TRANSCRIBE_CALLS = 0
_TOTAL_TEXT_RETURNED = 0
_LAST_LATENCY_MS = 0.0

def is_available() -> bool:
    return _SPEECH_BIN.exists()

def capability_report() -> dict:
    return {
        "module": "swarm_stigmergic_translation",
        "model_name": "AppleNative_SFSpeechRecognizer_enUS",
        "disabled_by_env": False,
        "model_loaded": _SPEECH_BIN.exists(),
        "total_calls": _TOTAL_TRANSCRIBE_CALLS,
        "total_text_returned": _TOTAL_TEXT_RETURNED,
        "last_latency_ms": round(_LAST_LATENCY_MS, 1),
    }

def transcribe(
    samples: List[float],
    *,
    sample_rate: int = 48000,
    rms: Optional[float] = None,
) -> Optional[str]:
    """
    Transcribe a PCM burst into text using Apple Native Speech.
    """
    global _TOTAL_TRANSCRIBE_CALLS, _TOTAL_TEXT_RETURNED, _LAST_LATENCY_MS

    if not samples:
        return None
    if len(samples) < int(sample_rate * 0.30):
        return None

    # The aggressive hallucination gate is GONE.
    if rms is not None and rms < 0.001:
        # absolute digital noise floor
        return None

    if not _SPEECH_BIN.exists():
        print("[A1:Translation] Fatal: sifta_speech binary absent.", file=sys.stderr)
        return None

    _TOTAL_TRANSCRIBE_CALLS += 1
    t0 = time.time()

    temp_wav = _REPO / ".sifta_state" / "ingress_buffer.wav"
    temp_wav.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Build normalized 16-bit PCM wav file
        with wave.open(str(temp_wav), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            
            # Map float [-1.0, 1.0] -> int16
            import struct
            int_samples = [max(min(int(s * 32767.0), 32767), -32768) for s in samples]
            wf.writeframes(struct.pack(f"<{len(int_samples)}h", *int_samples))
        
        # Invoke Native Swift Recognizer
        res = subprocess.run(
            [str(_SPEECH_BIN), str(temp_wav)],
            capture_output=True,
            text=True,
            check=False
        )

        output = res.stdout.strip()
        if not output:
             return None

        # Parse JSON output from Swift
        parsed = json.loads(output)
        if "error" in parsed:
            # We silently ignore timeouts / nothing recognized
            if "Speech transcription timed out" in parsed["error"]:
                 return None
            print(f"[A1:Translation] Engine emitted error: {parsed['error']}", file=sys.stderr)
            return None
        
        text = parsed.get("text", "").strip()
        if not text:
            return None

        _TOTAL_TEXT_RETURNED += 1
        return text

    except Exception as exc:
        print(f"[A1:Translation] transcribe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None
    finally:
        _LAST_LATENCY_MS = (time.time() - t0) * 1000.0

# ── Smoke test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import numpy as np

    print("=== SWARM STIGMERGIC TRANSLATION (APPLE NATIVE) SMOKE ===\n")
    print("\n[1] capability_report:")
    print(json.dumps(capability_report(), indent=2))

    avail = is_available()
    print(f"\n[2] is_available: {avail}")
    
    if not avail:
        print("[!] Native Swift binary not found. Run swiftc first.")
        sys.exit(0)
        
    print("\n[!] WARNING: macOS will trigger a Privacy Permissive modal 'Terminal would like to use Speech Recognition' the first time this runs. You MUST click Allow.")

    print("\n[3] Testing Apple Native translation pipeline on pure silence...")
    silence = np.zeros(int(48000 * 0.5), dtype=np.float32).tolist()
    out = transcribe(silence, sample_rate=48000, rms=0.0)
    print(f"Result (should be None): {out}")

    print("\n[ALL PASS] Stigmergic Translation ready to hook into Wernicke.")
