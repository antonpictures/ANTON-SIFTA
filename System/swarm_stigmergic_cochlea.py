#!/usr/bin/env python3
"""Event 95: Stigmergic cochlea, feature-only acoustic ingress.

This module extracts bounded acoustic features from injected audio buffers and
writes them to `.sifta_state/stigmergic_cochlea.jsonl`. It never stores raw PCM.
Hardware microphone capture is optional and must pass the existing
`System.audio_ingress` consent gate before this module will call it.

Truth labels:
  SYNTHETIC_BUFFER         tests / deterministic generated buffers
  INJECTED_BUFFER          caller-provided samples
  CONSENTED_MIC_FEATURES   features from an already-approved mic burst
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np

from System.jsonl_file_lock import append_line_locked


_REPO = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_MFCC_COUNT = 13
TRUTH_SYNTHETIC = "SYNTHETIC_BUFFER"
TRUTH_INJECTED = "INJECTED_BUFFER"
TRUTH_CONSENTED_MIC = "CONSENTED_MIC_FEATURES"


class MicrophoneOptInRequired(RuntimeError):
    """Raised when Event 95 is asked to open hardware without consent."""


@dataclass(frozen=True)
class CochleaFrame:
    ts: float
    truth_label: str
    source: str
    sample_rate: int
    duration_s: float
    n_samples: int
    tick_id: str
    rms: float
    peak: float
    zero_crossing_rate: float
    spectral_entropy: float
    spectral_centroid_hz: float
    f0_hz: float
    vad: bool
    mfcc: list[float]
    acoustic_stress: float
    td_bias: float
    danger_hint: str
    # Event ~111: near-field vs far-field replay cue (merged into JSONL; no raw PCM)
    playback_fingerprint: Dict[str, Any] = field(default_factory=dict)


def _state_root() -> Path:
    try:
        import System.swarm_body_brain_loop as _bbl

        root = getattr(_bbl, "_STATE_DIR", None)
        if root is not None:
            return Path(root).resolve()
    except Exception:
        pass
    return (_REPO / ".sifta_state").resolve()


def cochlea_ledger_path() -> Path:
    return _state_root() / "stigmergic_cochlea.jsonl"


def _as_mono_float(samples: Iterable[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(list(samples) if not isinstance(samples, np.ndarray) else samples, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1)
    if arr.size == 0:
        return np.zeros(1, dtype=np.float32)
    return np.nan_to_num(np.clip(arr.astype(np.float32), -1.0, 1.0))


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        return default
    if not math.isfinite(number):
        return default
    return max(0.0, min(1.0, number))


def spectral_entropy(samples: np.ndarray) -> float:
    if samples.size < 2:
        return 1.0
    power = np.abs(np.fft.rfft(samples)) ** 2
    total = float(power.sum())
    if total <= 1e-12:
        return 0.0
    prob = power / total
    entropy = -float(np.sum(prob * np.log2(prob + 1e-12)))
    max_entropy = math.log2(max(2, prob.size))
    return clamp01(entropy / max_entropy)


def spectral_centroid_hz(samples: np.ndarray, sample_rate: int) -> float:
    power = np.abs(np.fft.rfft(samples)) ** 2
    total = float(power.sum())
    if total <= 1e-12:
        return 0.0
    freqs = np.fft.rfftfreq(samples.size, 1.0 / float(sample_rate))
    return float(np.sum(freqs * power) / total)


def estimate_f0_hz(samples: np.ndarray, sample_rate: int, *, min_hz: float = 60.0, max_hz: float = 1000.0) -> float:
    if samples.size < int(sample_rate / min_hz):
        return 0.0
    centered = samples - float(np.mean(samples))
    if float(np.max(np.abs(centered))) <= 1e-6:
        return 0.0
    corr = np.correlate(centered, centered, mode="full")[centered.size - 1 :]
    min_lag = max(1, int(sample_rate / max_hz))
    max_lag = min(corr.size - 1, int(sample_rate / min_hz))
    if max_lag <= min_lag:
        return 0.0
    lag = int(np.argmax(corr[min_lag : max_lag + 1]) + min_lag)
    if corr[lag] <= 1e-9:
        return 0.0
    return round(float(sample_rate) / float(lag), 3)


def _hz_to_mel(hz: np.ndarray) -> np.ndarray:
    return 2595.0 * np.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel: np.ndarray) -> np.ndarray:
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


def _mel_filter_bank(sample_rate: int, n_fft: int, n_mels: int = 26) -> np.ndarray:
    mel_min, mel_max = _hz_to_mel(np.asarray([0.0, sample_rate / 2.0]))
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = _mel_to_hz(mel_points)
    bins = np.floor((n_fft + 1) * hz_points / sample_rate).astype(int)
    bank = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float64)
    for i in range(1, n_mels + 1):
        left, center, right = bins[i - 1], bins[i], bins[i + 1]
        if center > left:
            bank[i - 1, left:center] = (np.arange(left, center) - left) / max(1, center - left)
        if right > center:
            bank[i - 1, center:right] = (right - np.arange(center, right)) / max(1, right - center)
    return bank


def mfcc_numpy(samples: np.ndarray, sample_rate: int, *, n_mfcc: int = DEFAULT_MFCC_COUNT) -> list[float]:
    n_fft = 1
    while n_fft < max(512, samples.size):
        n_fft *= 2
    windowed = np.zeros(n_fft, dtype=np.float64)
    src = samples.astype(np.float64)
    windowed[: src.size] = src * np.hanning(src.size)
    power = (np.abs(np.fft.rfft(windowed)) ** 2) / float(n_fft)
    mel_energy = _mel_filter_bank(sample_rate, n_fft).dot(power)
    log_mel = np.log(np.maximum(mel_energy, 1e-12))
    n = log_mel.size
    coeffs = []
    for k in range(n_mfcc):
        basis = np.cos(math.pi * k * (np.arange(n) + 0.5) / n)
        coeffs.append(float(np.sum(log_mel * basis)))
    return [round(v, 5) for v in coeffs]


def analyze_buffer(
    samples: Iterable[float] | np.ndarray,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    tick_id: str = "",
    source: str = "injected_buffer",
    truth_label: str = TRUTH_INJECTED,
) -> CochleaFrame:
    buf = _as_mono_float(samples)
    duration_s = float(buf.size) / float(sample_rate)
    rms = float(np.sqrt(np.mean(np.square(buf.astype(np.float64)))))
    peak = float(np.max(np.abs(buf.astype(np.float64))))
    signs = np.signbit(buf)
    zcr = float(np.count_nonzero(signs[1:] != signs[:-1]) / max(1, buf.size - 1))
    entropy = spectral_entropy(buf)
    centroid = spectral_centroid_hz(buf, sample_rate)
    f0 = estimate_f0_hz(buf, sample_rate)
    vad = bool(rms >= 0.015 and peak >= 0.03)
    mfcc = mfcc_numpy(buf, sample_rate)

    loudness = clamp01(rms * 4.0)
    entropy_pressure = clamp01(entropy)
    pitch_pressure = 0.1 if f0 > 0.0 else 0.25
    acoustic_stress = clamp01(0.55 * loudness + 0.30 * entropy_pressure + 0.15 * pitch_pressure)
    td_bias = round((acoustic_stress - 0.5) * 0.4, 5)
    if not vad:
        danger = "ACOUSTIC_QUIET"
    elif acoustic_stress >= 0.75:
        danger = "ACOUSTIC_STRESS_HIGH"
    elif entropy >= 0.75:
        danger = "ACOUSTIC_BROADBAND_ATTENTION"
    else:
        danger = "ACOUSTIC_FEATURES_NOMINAL"

    try:
        from System.swarm_acoustic_playback_fingerprint import compute_playback_fingerprint

        pf = compute_playback_fingerprint(
            buf,
            sample_rate=int(sample_rate),
            mfcc=mfcc,
            rms=rms,
            peak=peak,
            spectral_entropy_val=entropy,
            f0_hz=float(f0),
            vad=vad,
        )
    except Exception:
        pf = {}

    return CochleaFrame(
        ts=time.time(),
        truth_label=truth_label,
        source=source,
        sample_rate=int(sample_rate),
        duration_s=round(duration_s, 5),
        n_samples=int(buf.size),
        tick_id=str(tick_id or ""),
        rms=round(rms, 6),
        peak=round(peak, 6),
        zero_crossing_rate=round(zcr, 6),
        spectral_entropy=round(entropy, 6),
        spectral_centroid_hz=round(centroid, 3),
        f0_hz=float(f0),
        vad=vad,
        mfcc=mfcc,
        acoustic_stress=round(acoustic_stress, 6),
        td_bias=td_bias,
        danger_hint=danger,
        playback_fingerprint=pf,
    )


def write_cochlea_frame(frame: CochleaFrame, ledger_path: Optional[Path] = None) -> dict[str, Any]:
    row = asdict(frame)
    row["raw_audio_logged"] = False
    target = ledger_path or cochlea_ledger_path()
    append_line_locked(target, json.dumps(row, sort_keys=True) + "\n")
    try:
        from System.swarm_acoustic_playback_fingerprint import append_acoustic_fingerprint_ledger

        append_acoustic_fingerprint_ledger(row, state_dir=target.parent)
    except Exception:
        pass
    return row


def analyze_and_write(
    samples: Iterable[float] | np.ndarray,
    *,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    tick_id: str = "",
    source: str = "injected_buffer",
    truth_label: str = TRUTH_INJECTED,
    ledger_path: Optional[Path] = None,
) -> dict[str, Any]:
    return write_cochlea_frame(
        analyze_buffer(samples, sample_rate=sample_rate, tick_id=tick_id, source=source, truth_label=truth_label),
        ledger_path=ledger_path,
    )


def synthetic_tone(freq_hz: float = 440.0, *, sample_rate: int = DEFAULT_SAMPLE_RATE, duration_s: float = 0.25, amp: float = 0.2) -> np.ndarray:
    t = np.arange(int(sample_rate * duration_s), dtype=np.float64) / float(sample_rate)
    return (amp * np.sin(2.0 * math.pi * freq_hz * t)).astype(np.float32)


def capture_and_write(
    *,
    use_microphone: bool = False,
    burst_s: float = 0.25,
    ledger_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Capture one cochlea row.

    Default path is synthetic and CI-safe. Hardware mic path is opt-in and
    requires `System.audio_ingress.mic_status()["enabled"]` to be true first.
    """

    if not use_microphone:
        return analyze_and_write(
            synthetic_tone(duration_s=burst_s),
            source="synthetic_440hz_tone",
            truth_label=TRUTH_SYNTHETIC,
            ledger_path=ledger_path,
        )

    from System import audio_ingress

    if not audio_ingress.mic_status().get("enabled"):
        raise MicrophoneOptInRequired("Event 95 hardware mic path requires prior audio_ingress.enable_microphone() approval")
    sample = audio_ingress.capture_acoustic_truth(burst_s=burst_s, feed_to_acoustic_field=False)
    if sample is None:
        raise RuntimeError("audio_ingress returned no AcousticSample")
    return analyze_and_write(
        sample.buffer,
        sample_rate=sample.sample_rate,
        source=sample.source,
        truth_label=TRUTH_CONSENTED_MIC,
        ledger_path=ledger_path,
    )


__all__ = [
    "CochleaFrame",
    "MicrophoneOptInRequired",
    "TRUTH_CONSENTED_MIC",
    "TRUTH_INJECTED",
    "TRUTH_SYNTHETIC",
    "analyze_and_write",
    "analyze_buffer",
    "capture_and_write",
    "clamp01",
    "cochlea_ledger_path",
    "estimate_f0_hz",
    "mfcc_numpy",
    "spectral_entropy",
    "synthetic_tone",
    "write_cochlea_frame",
]


if __name__ == "__main__":
    print(json.dumps(capture_and_write(), indent=2, sort_keys=True))
