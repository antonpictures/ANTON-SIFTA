#!/usr/bin/env python3
"""
System/swarm_voice_identity_organ.py — Stigmergic Voice Identity Organ
══════════════════════════════════════════════════════════════════════════
Architecture (primary-operator voice tagging):

  1. RECORD  → capture a 2-5 sec audio block (no raw audio stored)
  2. EXTRACT → compute acoustic fingerprint (MFCC, RMS, crest, spectral flatness, HNR)
  3. TAG     → the owner labels it: primary_operator / YouTube / PhoneSpeaker / Environment / Keyboard
  4. LEDGER  → write receipt to voice_identity_ledger.jsonl (features + label + ts)
  5. CLASSIFY → incoming audio → nearest-neighbor match against ledger exemplars
  6. ALICE LEARNS → after N exemplars per class, she knows immediately

No raw PCM is ever stored. Only receipt-backed acoustic feature vectors.
Swimmers vote: each labeled class is a "swimmer"; the nearest neighbor wins.
"""
from __future__ import annotations

import json
import math
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import numpy as np

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "voice_identity_ledger.jsonl"
_SAMPLE_RATE = 16000
_FRAME_SIZE = 512

# ── Source labels ────────────────────────────────────────────────────────────
PRIMARY_OPERATOR_VOICE_LABEL = "primary_operator"
_LEGACY_OWNER_VOICE_ALIASES = frozenset({"george"})

LABELS = {
    PRIMARY_OPERATOR_VOICE_LABEL: {
        "emoji": "🧑",
        "display": "Primary operator voice",
        "color": "#00e5ff",
    },
    "youtube":      {"emoji": "📺", "display": "YouTube / TV",       "color": "#ff5252"},
    "phone":        {"emoji": "📱", "display": "Phone Speaker",      "color": "#ff9800"},
    "environment":  {"emoji": "🌿", "display": "Environment / Room", "color": "#69f0ae"},
    "keyboard":     {"emoji": "⌨️",  "display": "Keyboard / Clicks",  "color": "#b39ddb"},
    "unknown":      {"emoji": "❓", "display": "Unknown",            "color": "#9e9e9e"},
}


def normalize_voice_source_label(label: str) -> str:
    lab = (label or "").strip().lower()
    if lab in _LEGACY_OWNER_VOICE_ALIASES:
        return PRIMARY_OPERATOR_VOICE_LABEL
    return lab


TRUTH_LABEL = "VOICE_IDENTITY_ORGAN_V1"


# ── Feature extraction ───────────────────────────────────────────────────────

def _frames(signal: np.ndarray, frame_size: int, hop: int) -> list[np.ndarray]:
    out = []
    for i in range(0, len(signal) - frame_size, hop):
        out.append(signal[i:i + frame_size])
    return out


def _rms(frame: np.ndarray) -> float:
    return float(np.sqrt(np.mean(frame ** 2)) + 1e-10)


def _crest_factor(frame: np.ndarray) -> float:
    rms = _rms(frame)
    peak = float(np.max(np.abs(frame)) + 1e-10)
    return round(peak / rms, 4)


def _spectral_flatness(frame: np.ndarray) -> float:
    mag = np.abs(np.fft.rfft(frame * np.hanning(len(frame))))
    mag = mag + 1e-10
    geo = np.exp(np.mean(np.log(mag)))
    arith = np.mean(mag)
    return round(float(geo / arith), 6)


def _zero_crossing_rate(frame: np.ndarray) -> float:
    signs = np.sign(frame)
    crossings = np.sum(np.abs(np.diff(signs))) / 2
    return round(float(crossings / len(frame)), 6)


def _mfcc_simple(signal: np.ndarray, sr: int = _SAMPLE_RATE,
                 n_mfcc: int = 13, n_fft: int = 512) -> np.ndarray:
    """Lightweight MFCC without librosa."""
    frames = _frames(signal, n_fft, n_fft // 2)
    if not frames:
        return np.zeros(n_mfcc)

    n_filters = 26
    low_freq, high_freq = 80.0, sr / 2.0

    def hz_to_mel(hz):
        return 2595 * math.log10(1 + hz / 700)

    def mel_to_hz(mel):
        return 700 * (10 ** (mel / 2595) - 1)

    mel_points = np.linspace(hz_to_mel(low_freq), hz_to_mel(high_freq), n_filters + 2)
    hz_points = np.array([mel_to_hz(m) for m in mel_points])
    bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

    filterbank = np.zeros((n_filters, n_fft // 2 + 1))
    for m in range(1, n_filters + 1):
        f_m_minus = bin_points[m - 1]
        f_m = bin_points[m]
        f_m_plus = bin_points[m + 1]
        for k in range(f_m_minus, f_m):
            if f_m > f_m_minus:
                filterbank[m - 1, k] = (k - f_m_minus) / (f_m - f_m_minus)
        for k in range(f_m, f_m_plus):
            if f_m_plus > f_m:
                filterbank[m - 1, k] = (f_m_plus - k) / (f_m_plus - f_m)

    mfcc_frames = []
    for frame in frames[:64]:  # cap at 64 frames
        windowed = frame * np.hanning(len(frame))
        spectrum = np.abs(np.fft.rfft(windowed, n=n_fft)) ** 2
        filter_energies = np.dot(filterbank, spectrum) + 1e-10
        log_energies = np.log(filter_energies)
        dct = np.zeros(n_mfcc)
        for k in range(n_mfcc):
            dct[k] = np.sum(log_energies * np.cos(math.pi * k / n_filters *
                                                    (np.arange(n_filters) + 0.5)))
        mfcc_frames.append(dct)

    return np.mean(mfcc_frames, axis=0) if mfcc_frames else np.zeros(n_mfcc)


def extract_features(audio: np.ndarray, sr: int = _SAMPLE_RATE) -> dict[str, Any]:
    """
    Extract acoustic fingerprint from raw PCM float32 audio.
    Returns a compact, storable feature dict. No raw audio stored.
    """
    signal = audio.astype(np.float32)
    if signal.ndim > 1:
        signal = signal.mean(axis=1)

    # Normalize
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak

    frames = _frames(signal, _FRAME_SIZE, _FRAME_SIZE // 2)
    if not frames:
        return {"rms": 0.0, "crest_factor": 0.0, "spectral_flatness": 0.0,
                "zcr": 0.0, "mfcc": [0.0] * 13, "duration_s": 0.0}

    rms_vals = [_rms(f) for f in frames]
    crest_vals = [_crest_factor(f) for f in frames]
    flat_vals = [_spectral_flatness(f) for f in frames]
    zcr_vals = [_zero_crossing_rate(f) for f in frames]
    mfcc = _mfcc_simple(signal, sr)

    return {
        "rms_mean": round(float(np.mean(rms_vals)), 6),
        "rms_std": round(float(np.std(rms_vals)), 6),
        "crest_factor_mean": round(float(np.mean(crest_vals)), 4),
        "spectral_flatness_mean": round(float(np.mean(flat_vals)), 6),
        "spectral_flatness_std": round(float(np.std(flat_vals)), 6),
        "zcr_mean": round(float(np.mean(zcr_vals)), 6),
        "mfcc": [round(float(x), 4) for x in mfcc.tolist()],
        "duration_s": round(len(signal) / sr, 3),
    }


# ── Ledger IO ────────────────────────────────────────────────────────────────

def write_exemplar(
    features: dict[str, Any],
    label: str,
    *,
    note: str = "",
    device_name: str = "",
) -> dict[str, Any]:
    """Write a labeled acoustic exemplar to the stigmergic ledger."""
    _STATE.mkdir(parents=True, exist_ok=True)
    label = normalize_voice_source_label(label)
    if label not in LABELS:
        label = "unknown"
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "source_label": label,
        "display": LABELS[label]["display"],
        "device_name": device_name,
        "note": note,
        "features": features,
    }
    with open(_LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load_exemplars(max_per_label: int = 30) -> list[dict[str, Any]]:
    """Load recent exemplars from the ledger, capped per label."""
    if not _LEDGER.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = _LEDGER.read_bytes().splitlines()
    except OSError:
        return []
    counts: dict[str, int] = {}
    for raw in reversed(lines):
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        label = normalize_voice_source_label(str(row.get("source_label") or "unknown"))
        if counts.get(label, 0) >= max_per_label:
            continue
        counts[label] = counts.get(label, 0) + 1
        rows.append(row)
    return list(reversed(rows))


# ── Swimmer nearest-neighbor classifier ─────────────────────────────────────

def _feature_vector(features: dict[str, Any]) -> np.ndarray:
    """Flatten features into a comparable vector."""
    mfcc = features.get("mfcc") or [0.0] * 13
    vec = [
        features.get("rms_mean", 0.0) * 10,
        features.get("rms_std", 0.0) * 10,
        features.get("crest_factor_mean", 0.0) * 0.1,
        features.get("spectral_flatness_mean", 0.0) * 5,
        features.get("spectral_flatness_std", 0.0) * 5,
        features.get("zcr_mean", 0.0) * 5,
    ] + [x * 0.05 for x in mfcc]
    return np.array(vec, dtype=np.float32)


def classify(
    features: dict[str, Any],
    exemplars: Optional[list[dict[str, Any]]] = None,
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    """
    Swimmer nearest-neighbor vote.
    Returns {label, confidence, votes, distances}.
    No LLM. Pure stigmergic receipts.
    """
    if exemplars is None:
        exemplars = load_exemplars()
    if not exemplars:
        return {"label": "unknown", "confidence": 0.0, "votes": {}, "n_exemplars": 0}

    query = _feature_vector(features)
    scored: list[tuple[float, str]] = []
    for ex in exemplars:
        ex_feat = ex.get("features")
        if not isinstance(ex_feat, dict):
            continue
        ref = _feature_vector(ex_feat)
        dist = float(np.linalg.norm(query - ref))
        label = normalize_voice_source_label(str(ex.get("source_label") or "unknown"))
        scored.append((dist, label))

    scored.sort(key=lambda x: x[0])
    top = scored[:top_k]

    votes: dict[str, float] = {}
    for dist, label in top:
        weight = 1.0 / (dist + 1e-6)
        votes[label] = votes.get(label, 0.0) + weight

    total = sum(votes.values())
    best_label = max(votes, key=lambda l: votes[l])
    confidence = round(votes[best_label] / total, 3) if total > 0 else 0.0

    return {
        "label": best_label,
        "confidence": confidence,
        "votes": {k: round(v / total, 3) for k, v in sorted(votes.items(), key=lambda x: -x[1])},
        "n_exemplars": len(exemplars),
        "nearest_dist": round(scored[0][0], 4) if scored else 99.0,
    }


def exemplar_counts() -> dict[str, int]:
    """How many exemplars per label we have."""
    exemplars = load_exemplars(max_per_label=999)
    counts: dict[str, int] = {}
    for ex in exemplars:
        label = normalize_voice_source_label(str(ex.get("source_label") or "unknown"))
        counts[label] = counts.get(label, 0) + 1
    return counts


__all__ = [
    "LABELS",
    "PRIMARY_OPERATOR_VOICE_LABEL",
    "normalize_voice_source_label",
    "TRUTH_LABEL",
    "extract_features",
    "write_exemplar",
    "load_exemplars",
    "classify",
    "exemplar_counts",
]
