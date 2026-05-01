#!/usr/bin/env python3
"""Stigmergic audiogram — ledger-bounded sonification (Event 93 analogue, sound).

Biology (metaphor): cochlear nerve carries **bounded** mechanical excitation from
the periphery; loudness is costly and context-gated (Zahavi-style honest signaling).

SIFTA: same scalar receipts as the visual phenotype bridge → short synthetic
tone parameters (**frequency** + **amplitude** clamped). No microphone, no
playback dependency — **numpy PCM** for tests and optional WAV proof.

Truth label: ``ACOUSTIC_PHENOTYPE_SYNTH`` — not a hearing model; not surveillance.

Pairs with ``System/swarm_syrinx.py`` (ingress **classification**) as the
**efferent / phenotype** lane (synthesis driven by organism state).
"""

from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

from System.swarm_visual_phenotype_gl import (
    DEFAULT_LEDGER,
    UniformFrame,
    VisualPhenotypeUniformTail,
    clamp_uniforms,
)

TRUTH_LABEL = "ACOUSTIC_PHENOTYPE_SYNTH"

def uniforms_to_tone_params(u: Dict[str, float]) -> Tuple[float, float]:
    """Map clamped phenotype scalars → (frequency_hz, peak_amplitude).

    Amplitude stays sub-unity to avoid clipping when cast to int16 WAV.
    """
    drive = float(u.get("u_stigmergic_drive", 0.0))
    reward = float(u.get("u_reward", 0.0))
    metabolic = float(u.get("u_metabolic_scope", 0.0))
    # Spread frequency with drive; keep in a musical-ish band for sanity.
    f0 = 110.0 + 220.0 * drive + 40.0 * min(1.0, metabolic * 0.5)
    f0 = max(55.0, min(880.0, f0))
    amp = 0.04 + 0.35 * reward + 0.08 * drive
    amp = max(0.02, min(0.55, amp))
    return f0, amp


def synthesize_mono_pcm(
    uniforms: Dict[str, float],
    *,
    sample_rate: int = 16_000,
    duration_s: float = 0.05,
    phase0: float = 0.0,
) -> np.ndarray:
    """Return float32 mono samples in [-1, 1]. Deterministic given inputs."""
    n = max(1, int(sample_rate * duration_s))
    t = np.arange(n, dtype=np.float64) / float(sample_rate)
    freq, peak = uniforms_to_tone_params(uniforms)
    w = 2.0 * math.pi * freq * t + phase0
    return (peak * np.sin(w)).astype(np.float32)


def pcm_rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples.astype(np.float64)))))


def pcm_peak(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.max(np.abs(samples.astype(np.float64))))


def phenotype_frame_to_pcm(
    frame: UniformFrame,
    *,
    sample_rate: int = 16_000,
    duration_s: float = 0.05,
    phase0: float = 0.0,
) -> np.ndarray:
    return synthesize_mono_pcm(frame.uniforms, sample_rate=sample_rate, duration_s=duration_s, phase0=phase0)


def ledger_tail_pcm(
    ledger_path: Optional[Path] = None,
    *,
    sample_rate: int = 16_000,
    duration_s: float = 0.05,
    phase0: float = 0.0,
) -> Tuple[np.ndarray, UniformFrame]:
    """Read last ledger row → UniformFrame → mono PCM."""
    path = Path(ledger_path) if ledger_path else DEFAULT_LEDGER
    tail = VisualPhenotypeUniformTail(path)
    frame = tail.read_frame(force=True)
    return phenotype_frame_to_pcm(frame, sample_rate=sample_rate, duration_s=duration_s, phase0=phase0), frame


def write_wav_mono16(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    """Write int16 mono WAV (proof artifact for tournaments)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    ints = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(ints.tobytes())


def audiogram_proof_row(uniforms: Dict[str, Any]) -> Dict[str, Any]:
    """One JSON-serializable proof dict from raw ledger-like mapping."""
    u = clamp_uniforms(uniforms)
    pcm = synthesize_mono_pcm(u)
    f, a = uniforms_to_tone_params(u)
    return {
        "truth_label": TRUTH_LABEL,
        "freq_hz": round(f, 3),
        "peak_amp": round(a, 5),
        "rms": round(pcm_rms(pcm), 6),
        "peak_sample": round(pcm_peak(pcm), 6),
        "samples": int(pcm.shape[0]),
    }


__all__ = [
    "TRUTH_LABEL",
    "audiogram_proof_row",
    "ledger_tail_pcm",
    "pcm_peak",
    "pcm_rms",
    "phenotype_frame_to_pcm",
    "synthesize_mono_pcm",
    "uniforms_to_tone_params",
    "write_wav_mono16",
]
