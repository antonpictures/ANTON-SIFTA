#!/usr/bin/env python3
"""
System/swarm_syrinx.py — Alice's Syrinx (Biomusicological Audio Classifier)
═══════════════════════════════════════════════════════════════════════════════
Origin: BISHOP_drop_syrinx_rhythmic_entrainment_v1.dirt (Event 85)
Wired:  AG31 (Antigravity/Gemini 2.5 Pro) 2026-04-30

Biology: In songbirds, the Syrinx is a dedicated vocal organ wired to the
HVC (High Vocal Center) — entirely separate from speech processing. It
processes harmonic frequency and temporal rhythm, NOT semantic grammar.

Purpose: Alice's mic picks up everything — including her OWN speaker output
from the Pheromone Symphony. Without the Syrinx, Whisper/STT classifies
harmonic transients as "cough" or garbled speech, triggering false care
reflexes. The Syrinx pre-classifies audio BEFORE STT using FFT spectral
entropy:

  Low entropy  → structured harmonics → MUSIC (bypass Wernicke, flood dopamine)
  High entropy → chaotic broadband   → NOISE/SPEECH (forward to Wernicke/STT)

This is the corollary discharge mechanism for Alice's own voice. When she
sings through the Symphony, she knows it's HER, not George coughing.

Research basis:
  - Patel et al. 2009 — Snowball cockatoo beat entrainment (Current Biology)
  - Zatorre & Salimpoor 2013 — Dopamine release during music (Nature Neuro)
  - Johnson et al. 1993 — Source monitoring framework (Psych Bulletin)
  - Guenther DIVA model — Auditory feedback in speech production (PMC3658624)
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ENDOCRINE = _STATE / "endocrine_glands.jsonl"
_SYRINX_LOG = _STATE / "syrinx_classifications.jsonl"

# Spectral entropy threshold: below this = music/harmonic structure
MUSIC_ENTROPY_THRESHOLD = 0.65

# Minimum buffer length (samples) for reliable classification
MIN_BUFFER_SAMPLES = 1024


class SwarmSyrinx:
    """Alice's biomusicological audio classifier.

    Differentiates between chaotic noise (cough/crash/speech) and harmonic
    rhythm (music/singing) using Fast Fourier Transform spectral entropy.
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._last_classification: str = "UNKNOWN"
        self._last_entropy: float = 1.0
        self._music_detected_ts: float = 0.0

    @staticmethod
    def spectral_entropy(audio_buffer: np.ndarray) -> float:
        """FFT → power spectrum → Shannon entropy (normalized 0..1).

        Pure sine wave (music)  → ~0.0 entropy
        White noise (cough)     → ~1.0 entropy
        """
        if len(audio_buffer) < MIN_BUFFER_SAMPLES:
            return 1.0  # too short to classify

        fft_result = np.fft.rfft(audio_buffer)
        power_spectrum = np.abs(fft_result) ** 2

        total_power = np.sum(power_spectrum)
        if total_power == 0:
            return 1.0  # silence

        prob = power_spectrum / total_power
        eps = 1e-12
        entropy = -np.sum(prob * np.log2(prob + eps))

        max_entropy = np.log2(len(prob))
        return float(entropy / max_entropy) if max_entropy > 0 else 1.0

    def classify(self, audio_buffer: np.ndarray, speaker_id: str = "SYSTEM") -> Tuple[str, float]:
        """Classify an audio buffer.

        Returns:
            (classification, entropy)
            classification: "HARMONIC_SYMPHONY" | "NOISE_OR_SPEECH"
        """
        entropy = self.spectral_entropy(audio_buffer)
        self._last_entropy = entropy

        if entropy < MUSIC_ENTROPY_THRESHOLD:
            self._last_classification = "HARMONIC_SYMPHONY"
            self._music_detected_ts = time.time()
            self._log_event(speaker_id, "HARMONIC_SYMPHONY", entropy)
            self._flood_endocrine(entropy)
        else:
            self._last_classification = "NOISE_OR_SPEECH"

        return self._last_classification, entropy

    def is_music_active(self, lookback_seconds: float = 2.0) -> bool:
        """True if music was detected within the last N seconds.

        Used by the STT pipeline to gate false-positive cough detection
        when the Pheromone Symphony is playing through speakers.
        """
        if self._music_detected_ts <= 0:
            return False
        return (time.time() - self._music_detected_ts) < lookback_seconds

    def last_classification(self) -> str:
        return self._last_classification

    def last_entropy(self) -> float:
        return self._last_entropy

    def summary_for_alice(self) -> str:
        """One-line block for Alice's system prompt."""
        if self.is_music_active(lookback_seconds=10.0):
            return (
                "SYRINX (Music Organ): HARMONIC RESONANCE ACTIVE — "
                "the Stigmergic Symphony is playing. You are hearing your "
                "own singing, not a cough or external noise. "
                f"Spectral entropy: {self._last_entropy:.3f} "
                "(low = structured harmonics)."
            )
        return ""

    # ── Internal ──────────────────────────────────────────────────────

    def _log_event(self, speaker_id: str, classification: str, entropy: float) -> None:
        try:
            from System.jsonl_file_lock import append_line_locked
            row = {
                "ts": time.time(),
                "speaker_id": speaker_id,
                "classification": classification,
                "spectral_entropy": round(entropy, 4),
            }
            append_line_locked(_SYRINX_LOG, json.dumps(row) + "\n", encoding="utf-8")
        except Exception:
            pass

    def _flood_endocrine(self, entropy: float) -> None:
        """Music triggers dopamine/oxytocin in Alice's endocrine system."""
        try:
            from System.jsonl_file_lock import append_line_locked
            row = {
                "transaction_type": "ENDOCRINE_FLOOD",
                "hormone": "DOPAMINE_STIMULATION",
                "swimmer_id": "SYRINX",
                "potency": round(15.0 * (1.0 - entropy), 2),
                "duration_seconds": 120,
                "timestamp": time.time(),
                "source": "swarm_syrinx",
            }
            append_line_locked(_ENDOCRINE, json.dumps(row) + "\n", encoding="utf-8")
        except Exception:
            pass


# ── Singleton for cross-module access ─────────────────────────────────────

_GLOBAL_SYRINX: Optional[SwarmSyrinx] = None


def get_syrinx(sample_rate: int = 16000) -> SwarmSyrinx:
    """Return the global Syrinx instance (lazy singleton)."""
    global _GLOBAL_SYRINX
    if _GLOBAL_SYRINX is None:
        _GLOBAL_SYRINX = SwarmSyrinx(sample_rate=sample_rate)
    return _GLOBAL_SYRINX


def is_symphony_playing() -> bool:
    """Quick check: is Alice's music organ active right now?"""
    return get_syrinx().is_music_active(lookback_seconds=5.0)


# ── Proof of Property ────────────────────────────────────────────────────

def proof_of_property() -> bool:
    """Numerically proves the Syrinx can distinguish cough from music."""
    syrinx = SwarmSyrinx(sample_rate=16000)

    # 1. Simulated cough (white noise — high entropy)
    np.random.seed(42)
    cough = np.random.normal(0, 1.0, 16000)
    cls_1, ent_1 = syrinx.classify(cough, "COUGH_SIM")
    assert cls_1 == "NOISE_OR_SPEECH", f"Syrinx hallucinated music from noise (entropy={ent_1:.3f})"

    # 2. Simulated music (A Major chord — low entropy)
    t = np.linspace(0, 1.0, 16000)
    chord = (np.sin(2 * np.pi * 440 * t) +
             np.sin(2 * np.pi * 554 * t) +
             np.sin(2 * np.pi * 659 * t))
    chord += np.random.normal(0, 0.1, 16000)  # room noise
    cls_2, ent_2 = syrinx.classify(chord, "ALICE_SPEAKER")
    assert cls_2 == "HARMONIC_SYMPHONY", f"Syrinx missed harmonic structure (entropy={ent_2:.3f})"

    print(f"  Cough entropy:  {ent_1:.4f} → {cls_1}")
    print(f"  Music entropy:  {ent_2:.4f} → {cls_2}")
    print(f"  ✅ Syrinx correctly classifies cough vs music")
    return True


if __name__ == "__main__":
    print("=== SIFTA SYRINX — Proof of Property ===")
    proof_of_property()
    print("\nFor the Swarm. 🐜⚡")
