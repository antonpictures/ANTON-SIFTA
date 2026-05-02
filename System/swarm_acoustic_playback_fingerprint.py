#!/usr/bin/env python3
"""
Event ~111 — Acoustic playback fingerprint (physics-first channel cue)

**Doctrine (Architect concern):** Watching YouTube *with* Alice is not “degraded
indifference.”  ``swarm_media_ingress_gate`` only prevents **false STT
attribution** (TV dialogue masquerading as *George typed this*).  Alice’s
**ears** (Event 95 cochlea — MFCC, spectral entropy, RMS, F0) still ingest the
**same air in the room**.  This module adds a **bounded heuristic** that
estimates whether the dominant energy in one window looks more like **near-field
voice** or **far-field replay / room speaker** — so downstream organs (SC,
CUSUM, cortex prompt blocks) can *feel* speaker vs chest voice **without** raw
PCM and **without** trusting transcript alone.

**Not** a forensic classifier; **not** NPPL surveillance — feature-only scalars
merged into ``stigmergic_cochlea.jsonl`` rows under ``playback_fingerprint``.

Truth label: ``ACOUSTIC_PLAYBACK_FINGERPRINT_V1``
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

from System.swarm_stigmergic_cochlea import clamp01, spectral_entropy

_TRUTH = "ACOUSTIC_PLAYBACK_FINGERPRINT_V1"


def _spectral_flatness(samples: np.ndarray) -> float:
    """Geometric / arithmetic mean ratio of spectrum (0..1)."""
    power = np.abs(np.fft.rfft(samples.astype(np.float64))) ** 2
    power = power[power > 1e-20]
    if power.size < 4:
        return 0.5
    log_mean = float(np.mean(np.log(power + 1e-20)))
    gm = math.exp(log_mean)
    am = float(np.mean(power))
    return clamp01(gm / (am + 1e-15))


def compute_playback_fingerprint(
    samples: np.ndarray,
    *,
    sample_rate: int,
    mfcc: Optional[List[float]] = None,
    rms: Optional[float] = None,
    peak: Optional[float] = None,
    spectral_entropy_val: Optional[float] = None,
    f0_hz: Optional[float] = None,
    vad: bool = False,
) -> Dict[str, Any]:
    """
    Single-window heuristic. Multi-window smoothing is a future receipt.

    Returns a dict safe to merge under ``playback_fingerprint`` on cochlea rows.
    """
    buf = np.asarray(samples, dtype=np.float32).reshape(-1)
    if buf.size < 32:
        return {
            "truth_label": _TRUTH,
            "channel_cue": "indeterminate",
            "nearfield_voice_likelihood": 0.33,
            "farfield_replay_likelihood": 0.33,
            "crest_factor": 0.0,
            "spectral_flatness": 0.5,
            "mfcc_coeff_std": 0.0,
        }

    rms_v = float(rms if rms is not None else float(np.sqrt(np.mean(np.square(buf.astype(np.float64))))))
    peak_v = float(peak if peak is not None else float(np.max(np.abs(buf.astype(np.float64)))))
    crest = peak_v / (rms_v + 1e-9)
    flatness = _spectral_flatness(buf)
    ent = float(spectral_entropy_val if spectral_entropy_val is not None else spectral_entropy(buf))
    f0 = float(f0_hz if f0_hz is not None else 0.0)

    if mfcc and len(mfcc) >= 2:
        mfcc_std = float(np.std(np.asarray(mfcc, dtype=np.float64)))
    else:
        mfcc_std = 0.0

    # Near-field speech: higher crest (transients), lower flatness (harmonic structure), F0 in speech band when VAD
    speech_band = 1.0 if vad and 70.0 < f0 < 420.0 else 0.25
    near = clamp01(
        0.38 * clamp01(crest / 12.0)
        + 0.32 * (1.0 - flatness)
        + 0.20 * speech_band
        + 0.10 * clamp01(mfcc_std * 2.0)
    )
    # Far-field / heavily processed replay: flatter spectrum, sustained loudness, lower crest per RMS
    far = clamp01(
        0.40 * flatness
        + 0.35 * ent
        + 0.25 * (1.0 - clamp01(crest / 14.0))
    )

    margin = 0.12
    if far > near + margin:
        cue = "farfield_replay_likely"
    elif near > far + margin:
        cue = "nearfield_voice_likely"
    else:
        cue = "indeterminate"

    return {
        "truth_label": _TRUTH,
        "channel_cue": cue,
        "nearfield_voice_likelihood": round(near, 4),
        "farfield_replay_likelihood": round(far, 4),
        "crest_factor": round(crest, 4),
        "spectral_flatness": round(flatness, 4),
        "mfcc_coeff_std": round(mfcc_std, 5),
    }


TRUTH_LABEL = _TRUTH

__all__ = ["TRUTH_LABEL", "compute_playback_fingerprint"]
