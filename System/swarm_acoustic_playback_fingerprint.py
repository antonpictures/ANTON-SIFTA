#!/usr/bin/env python3
"""Event 109b/111: acoustic playback fingerprint, feature-only.

This organ estimates whether one mic window looks more like near-field human
speech or far-field speaker/media replay. It is not a forensic classifier and
it never stores raw PCM. The output is a bounded cue that can be merged into
cochlea rows and media-ingress receipts so Alice can co-listen to YouTube as
environmental content without mistaking every caption for George talking.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import numpy as np

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

_REPO = Path(__file__).resolve().parent.parent
STATE_DIR = _REPO / ".sifta_state"
FINGERPRINT_LOG = STATE_DIR / "acoustic_fingerprints.jsonl"
TRUTH_LABEL = "ACOUSTIC_PLAYBACK_FINGERPRINT_V1"
FORMULA_REVISION = "109b"
BIOACOUSTIC_STIGMERGY_ANCHORS = (
    "MFCC / mel cepstra: compact auditory-envelope receipt, not transcript trust.",
    "Crest factor + spectral flatness: compressed replay differs from near-field voice.",
    "Amplitude modulation depth + HNR proxy: chest voice carries different periodic structure than room speaker playback.",
)

# Citable primary literature (animal sound / audition) — for audits, not vibes.
LITERATURE_CITES: tuple[dict[str, str], ...] = (
    {
        "topic": "mfcc_mel_cepstrum",
        "cite": "Davis & Mermelstein (1980) IEEE TASSP — mel-frequency cepstral coefficients.",
        "doi": "10.1109/TASSP.1980.1163420",
    },
    {
        "topic": "animal_communication_principles",
        "cite": "Bradbury & Vehrencamp — Principles of Animal Communication (spectral/temporal cues).",
        "doi": "",
    },
    {
        "topic": "comparative_vocal_motor",
        "cite": "Suthers & Fitch (2011) Trends Neurosci. — vocal production across mammals/birds.",
        "doi": "10.1016/j.tins.2011.04.002",
    },
    {
        "topic": "cetacean_signature_whistles",
        "cite": "Janik & Sayigh (2012) Commun Integr Biol. — long-window social identity signals.",
        "doi": "10.4161/cib.21234",
    },
)


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        return default
    if not math.isfinite(number):
        return default
    return max(0.0, min(1.0, number))


def _as_mono_float(samples: Iterable[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(list(samples) if not isinstance(samples, np.ndarray) else samples, dtype=np.float32)
    if arr.ndim > 1:
        arr = np.mean(arr, axis=1)
    if arr.size == 0:
        return np.zeros(1, dtype=np.float32)
    return np.nan_to_num(np.clip(arr.astype(np.float32), -1.0, 1.0))


def _spectral_entropy(samples: np.ndarray) -> float:
    if samples.size < 2:
        return 1.0
    power = np.abs(np.fft.rfft(samples.astype(np.float64))) ** 2
    total = float(power.sum())
    if total <= 1e-12:
        return 0.0
    prob = power / total
    entropy = -float(np.sum(prob * np.log2(prob + 1e-12)))
    max_entropy = math.log2(max(2, prob.size))
    return _clamp01(entropy / max_entropy)


def _spectral_flatness(samples: np.ndarray) -> float:
    power = np.abs(np.fft.rfft(samples.astype(np.float64))) ** 2
    power = power[power > 1e-20]
    if power.size < 4:
        return 0.5
    gm = math.exp(float(np.mean(np.log(power + 1e-20))))
    am = float(np.mean(power))
    return _clamp01(gm / (am + 1e-15))


def _am_depth(samples: np.ndarray, sample_rate: int) -> float:
    frame = max(32, int(sample_rate * 0.02))
    if samples.size < frame * 2:
        return 0.0
    n = samples.size // frame
    trimmed = samples[: n * frame].reshape(n, frame).astype(np.float64)
    env = np.sqrt(np.mean(np.square(trimmed), axis=1))
    lo = float(np.min(env))
    hi = float(np.max(env))
    return _clamp01((hi - lo) / (hi + lo + 1e-9))


def _hnr_proxy(samples: np.ndarray) -> float:
    power = np.abs(np.fft.rfft(samples.astype(np.float64))) ** 2
    total = float(power.sum())
    if total <= 1e-12 or power.size < 8:
        return 0.0
    # Peak-bin dominance is a cheap harmonic-to-noise proxy. Bounded and
    # intentionally coarse; it is a context cue, not forensic identification.
    peak_band = float(np.max(power[1:]))
    return _clamp01(math.sqrt(peak_band / (total + 1e-12)))


def compute_playback_fingerprint(
    samples: Iterable[float] | np.ndarray,
    *,
    sample_rate: int,
    mfcc: Optional[List[float]] = None,
    rms: Optional[float] = None,
    peak: Optional[float] = None,
    spectral_entropy_val: Optional[float] = None,
    f0_hz: Optional[float] = None,
    vad: bool = False,
) -> Dict[str, Any]:
    """Return a feature-only near-field vs replay cue safe for JSONL rows."""
    buf = _as_mono_float(samples)
    if buf.size < 32:
        return {
            "truth_label": TRUTH_LABEL,
            "formula_revision": FORMULA_REVISION,
            "channel_cue": "indeterminate",
            "nearfield_voice_likelihood": 0.33,
            "farfield_replay_likelihood": 0.33,
            "crest_factor": 0.0,
            "spectral_flatness": 0.5,
            "mfcc_coeff_std": 0.0,
            "hnr_proxy": 0.0,
            "am_depth": 0.0,
            "literature_anchors": [x["topic"] for x in LITERATURE_CITES],
        }

    rms_v = float(rms if rms is not None else np.sqrt(np.mean(np.square(buf.astype(np.float64)))))
    peak_v = float(peak if peak is not None else np.max(np.abs(buf.astype(np.float64))))
    crest = peak_v / (rms_v + 1e-9)
    flatness = _spectral_flatness(buf)
    entropy = float(spectral_entropy_val if spectral_entropy_val is not None else _spectral_entropy(buf))
    f0 = float(f0_hz if f0_hz is not None else 0.0)
    mfcc_std = float(np.std(np.asarray(mfcc, dtype=np.float64))) if mfcc and len(mfcc) >= 2 else 0.0
    hnr = _hnr_proxy(buf)
    am_depth = _am_depth(buf, int(sample_rate))

    speech_band = 1.0 if vad and 70.0 < f0 < 420.0 else 0.25
    near = _clamp01(
        0.32 * _clamp01(crest / 12.0)
        + 0.24 * (1.0 - flatness)
        + 0.18 * speech_band
        + 0.16 * hnr
        + 0.10 * _clamp01(mfcc_std * 2.0)
    )
    far = _clamp01(
        0.30 * flatness
        + 0.24 * entropy
        + 0.20 * (1.0 - _clamp01(crest / 14.0))
        + 0.16 * (1.0 - hnr)
        + 0.10 * (1.0 - am_depth)
    )

    if far > near + 0.12:
        cue = "farfield_replay_likely"
    elif near > far + 0.12:
        cue = "nearfield_voice_likely"
    else:
        cue = "indeterminate"

    return {
        "truth_label": TRUTH_LABEL,
        "formula_revision": FORMULA_REVISION,
        "channel_cue": cue,
        "nearfield_voice_likelihood": round(near, 4),
        "farfield_replay_likelihood": round(far, 4),
        "crest_factor": round(float(crest), 4),
        "spectral_flatness": round(float(flatness), 4),
        "mfcc_coeff_std": round(float(mfcc_std), 5),
        "hnr_proxy": round(float(hnr), 4),
        "am_depth": round(float(am_depth), 4),
        "literature_anchors": [x["topic"] for x in LITERATURE_CITES],
    }


def _state_dir(state_dir: Optional[Path] = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def append_acoustic_fingerprint_ledger(row: Mapping[str, Any], *, state_dir: Optional[Path] = None) -> dict[str, Any]:
    """Append a compact acoustic fingerprint row. Raw audio is never accepted."""
    sd = _state_dir(state_dir)
    fp = row.get("playback_fingerprint") if isinstance(row.get("playback_fingerprint"), Mapping) else row
    safe_fp = {
        k: v
        for k, v in dict(fp).items()
        if k
        in {
            "truth_label",
            "formula_revision",
            "channel_cue",
            "nearfield_voice_likelihood",
            "farfield_replay_likelihood",
            "crest_factor",
            "spectral_flatness",
            "mfcc_coeff_std",
            "hnr_proxy",
            "am_depth",
        }
        and isinstance(v, (str, int, float, bool))
    }
    out = {
        "ts": time.time(),
        "truth_label": "ACOUSTIC_FINGERPRINT_LEDGER_109b",
        "writer": "swarm_acoustic_playback_fingerprint",
        "tick_id": str(row.get("tick_id") or ""),
        "source_truth_label": str(row.get("truth_label") or ""),
        "sample_rate": int(row.get("sample_rate") or 0),
        "raw_audio_logged": False,
        "playback_fingerprint": safe_fp,
        "channel_cue": safe_fp.get("channel_cue", "indeterminate"),
    }
    row_key = json.dumps(
        {
            "tick_id": out["tick_id"],
            "sample_rate": out["sample_rate"],
            "channel_cue": out["channel_cue"],
            "fp": safe_fp,
        },
        sort_keys=True,
    )
    out["fingerprint_row_id"] = hashlib.sha256(row_key.encode("utf-8")).hexdigest()[:16]
    path = sd / FINGERPRINT_LOG.name
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(out, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    return out


def recent_tail_is_media_playback_context(
    *,
    state_dir: Optional[Path] = None,
    n: int = 16,
    media_fraction: float = 0.60,
    max_age_s: float = 900.0,
) -> bool:
    """True when recent acoustic rows skew toward far-field/media replay."""
    path = _state_dir(state_dir) / FINGERPRINT_LOG.name
    if not path.exists():
        return False
    try:
        lines = path.read_bytes().splitlines()[-max(1, int(n)) :]
    except OSError:
        return False
    now = time.time()
    rows: list[dict[str, Any]] = []
    for raw in lines:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        try:
            if now - float(row.get("ts", now)) > max_age_s:
                continue
        except Exception:
            continue
        rows.append(row)
    if not rows:
        return False
    media = 0
    for row in rows:
        fp = row.get("playback_fingerprint") if isinstance(row.get("playback_fingerprint"), dict) else {}
        cue = str(row.get("channel_cue") or fp.get("channel_cue") or "")
        if cue == "farfield_replay_likely":
            media += 1
    return (media / len(rows)) >= float(media_fraction)


class AcousticPlaybackFingerprint:
    """Compatibility wrapper for callers that want a class-style API."""

    @staticmethod
    def compute_fingerprint(audio_chunk: np.ndarray, sample_rate: int = 16_000) -> Dict[str, Any]:
        fp = compute_playback_fingerprint(audio_chunk, sample_rate=sample_rate)
        digest = hashlib.sha256(
            json.dumps(fp, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        return {
            "fingerprint_id": digest,
            "timestamp": time.time(),
            "type": "media_playback" if fp["channel_cue"] == "farfield_replay_likely" else "direct_speech",
            "confidence": max(fp["nearfield_voice_likelihood"], fp["farfield_replay_likelihood"]),
            "media_likelihood": fp["farfield_replay_likelihood"],
            "playback_fingerprint": fp,
        }

    @staticmethod
    def is_media_context(recent_fingerprints: List[Dict[str, Any]]) -> bool:
        if not recent_fingerprints:
            return False
        media = sum(1 for fp in recent_fingerprints if fp.get("type") == "media_playback")
        return (media / len(recent_fingerprints)) > 0.6


def classify_audio_context(audio_chunk: np.ndarray, sample_rate: int = 16_000) -> Dict[str, Any]:
    fp = AcousticPlaybackFingerprint.compute_fingerprint(audio_chunk, sample_rate=sample_rate)
    return {
        "context_type": fp["type"],
        "confidence": fp["confidence"],
        "fingerprint_id": fp["fingerprint_id"],
        "playback_fingerprint": fp["playback_fingerprint"],
    }


__all__ = [
    "AcousticPlaybackFingerprint",
    "BIOACOUSTIC_STIGMERGY_ANCHORS",
    "LITERATURE_CITES",
    "FORMULA_REVISION",
    "TRUTH_LABEL",
    "append_acoustic_fingerprint_ledger",
    "classify_audio_context",
    "compute_playback_fingerprint",
    "recent_tail_is_media_playback_context",
]
