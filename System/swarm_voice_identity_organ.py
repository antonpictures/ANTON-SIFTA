#!/usr/bin/env python3
"""
System/swarm_voice_identity_organ.py — Stigmergic Voice Identity Organ
══════════════════════════════════════════════════════════════════════════
Architecture (primary-operator voice tagging):

  1. RECORD  → capture a 2-5 sec audio block (no raw audio stored)
  2. EXTRACT → compute acoustic fingerprint (rich MFCC + deltas + F0, …)
  3. TAG     → the owner labels it: primary_operator / YouTube / PhoneSpeaker / …
  4. LEDGER  → write receipt to voice_identity_ledger.jsonl (features + label + ts)
  5. CLASSIFY → incoming audio → nearest-neighbor + prototype vote against ledger
  6. ALICE LEARNS → after N exemplars per class, she knows immediately

r1602 (grok, We Code Together Lane A / VA1–VA2):
  - Feature bank upgraded: ≥20 MFCC + Δ + ΔΔ, F0 stats, spectral shape.
  - Leave-one-out harness is the acceptance test (target ≥85%, margin ≥0.15).
  - First-class "Alice, learn my voice" enrollment session API.

No raw PCM is ever stored. Only receipt-backed acoustic feature vectors.
Swimmers vote: each labeled class is a "swimmer"; nearest + prototype win.
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
_ENROLL_STATE = _STATE / "voice_enrollment_session.json"
_LOO_RECEIPT = _STATE / "voice_identity_loo_receipts.jsonl"
_SAMPLE_RATE = 16000
_FRAME_SIZE = 512
_FEATURE_VERSION = 2  # r1602 rich bank
_N_MFCC = 20
_OWNER_CONF_THRESHOLD = 0.60
_MARGIN_TARGET = 0.15

# ── Source labels ────────────────────────────────────────────────────────────
PRIMARY_OPERATOR_VOICE_LABEL = "primary_operator"
_LEGACY_OWNER_VOICE_ALIASES = frozenset({"george"})

LABELS = {
    PRIMARY_OPERATOR_VOICE_LABEL: {
        "emoji": "🧑",
        "display": "Primary operator voice",
        "color": "#00e5ff",
    },
    "youtube": {"emoji": "📺", "display": "YouTube / TV", "color": "#ff5252"},
    "phone": {"emoji": "📱", "display": "Phone Speaker", "color": "#ff9800"},
    "environment": {"emoji": "🌿", "display": "Environment / Room", "color": "#69f0ae"},
    "keyboard": {"emoji": "⌨️", "display": "Keyboard / Clicks", "color": "#b39ddb"},
    "unknown": {"emoji": "❓", "display": "Unknown", "color": "#9e9e9e"},
}


def normalize_voice_source_label(label: str) -> str:
    lab = (label or "").strip().lower()
    if lab in _LEGACY_OWNER_VOICE_ALIASES:
        return PRIMARY_OPERATOR_VOICE_LABEL
    return lab


TRUTH_LABEL = "VOICE_IDENTITY_ORGAN_V2"


# ── Feature extraction ───────────────────────────────────────────────────────

def _frames(signal: np.ndarray, frame_size: int, hop: int) -> list[np.ndarray]:
    out = []
    for i in range(0, max(0, len(signal) - frame_size + 1), hop):
        out.append(signal[i : i + frame_size])
    if not out and len(signal) > 0:
        pad = np.zeros(frame_size, dtype=np.float32)
        n = min(len(signal), frame_size)
        pad[:n] = signal[:n]
        out.append(pad)
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
    return round(float(crossings / max(len(frame), 1)), 6)


def _hz_to_mel(hz: float) -> float:
    return 2595.0 * math.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel: float) -> float:
    return 700.0 * (10 ** (mel / 2595.0) - 1.0)


def _mel_filterbank(sr: int, n_fft: int, n_filters: int = 40) -> np.ndarray:
    low_freq, high_freq = 50.0, sr / 2.0
    mel_points = np.linspace(_hz_to_mel(low_freq), _hz_to_mel(high_freq), n_filters + 2)
    hz_points = np.array([_mel_to_hz(m) for m in mel_points])
    bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)
    bin_points = np.clip(bin_points, 0, n_fft // 2)
    filterbank = np.zeros((n_filters, n_fft // 2 + 1), dtype=np.float64)
    for m in range(1, n_filters + 1):
        f_m_minus = bin_points[m - 1]
        f_m = bin_points[m]
        f_m_plus = bin_points[m + 1]
        if f_m > f_m_minus:
            for k in range(f_m_minus, f_m):
                filterbank[m - 1, k] = (k - f_m_minus) / (f_m - f_m_minus)
        if f_m_plus > f_m:
            for k in range(f_m, f_m_plus):
                filterbank[m - 1, k] = (f_m_plus - k) / (f_m_plus - f_m)
    return filterbank


def _mfcc_bank(
    signal: np.ndarray,
    sr: int = _SAMPLE_RATE,
    n_mfcc: int = _N_MFCC,
    n_fft: int = 512,
) -> np.ndarray:
    """Per-frame MFCC matrix (T, n_mfcc). Pure numpy, no librosa."""
    hop = n_fft // 2
    frames = _frames(signal, n_fft, hop)
    if not frames:
        return np.zeros((1, n_mfcc), dtype=np.float64)

    n_filters = 40
    filterbank = _mel_filterbank(sr, n_fft, n_filters=n_filters)
    # Precompute DCT basis
    dct = np.zeros((n_mfcc, n_filters), dtype=np.float64)
    for k in range(n_mfcc):
        dct[k] = np.cos(math.pi * k / n_filters * (np.arange(n_filters) + 0.5))

    mfcc_frames: list[np.ndarray] = []
    for frame in frames[:128]:
        windowed = frame * np.hanning(len(frame))
        spectrum = np.abs(np.fft.rfft(windowed, n=n_fft)) ** 2
        filter_energies = np.dot(filterbank, spectrum) + 1e-10
        log_energies = np.log(filter_energies)
        mfcc_frames.append(dct @ log_energies)
    return np.asarray(mfcc_frames, dtype=np.float64)


def _delta(series: np.ndarray) -> np.ndarray:
    """Simple first-order difference along time (pad ends)."""
    if series.ndim == 1:
        d = np.diff(series, prepend=series[:1])
        return d
    # (T, D)
    d = np.diff(series, axis=0, prepend=series[:1, :])
    return d


def _estimate_f0(signal: np.ndarray, sr: int = _SAMPLE_RATE) -> dict[str, float]:
    """Autocorrelation pitch stats. Returns mean/std/min/max in Hz (0 if unvoiced)."""
    if len(signal) < sr // 20:
        return {"f0_mean": 0.0, "f0_std": 0.0, "f0_min": 0.0, "f0_max": 0.0, "voiced_ratio": 0.0}

    frame_len = int(0.04 * sr)
    hop = int(0.02 * sr)
    min_lag = int(sr / 400.0)  # 400 Hz
    max_lag = int(sr / 60.0)  # 60 Hz
    f0s: list[float] = []
    voiced = 0
    total = 0
    for i in range(0, len(signal) - frame_len, hop):
        frame = signal[i : i + frame_len]
        total += 1
        if _rms(frame) < 0.02:
            continue
        frame = frame - np.mean(frame)
        # Autocorr via FFT
        n = 1
        while n < 2 * len(frame):
            n *= 2
        spec = np.fft.rfft(frame, n=n)
        ac = np.fft.irfft(spec * np.conj(spec), n=n)[: len(frame)]
        if ac[0] <= 1e-12:
            continue
        ac = ac / ac[0]
        search = ac[min_lag : min(max_lag, len(ac) - 1)]
        if len(search) < 3:
            continue
        peak_i = int(np.argmax(search))
        peak = float(search[peak_i])
        if peak < 0.3:
            continue
        lag = peak_i + min_lag
        f0 = float(sr) / float(lag)
        if 60.0 <= f0 <= 400.0:
            f0s.append(f0)
            voiced += 1

    if not f0s:
        return {"f0_mean": 0.0, "f0_std": 0.0, "f0_min": 0.0, "f0_max": 0.0, "voiced_ratio": 0.0}
    arr = np.asarray(f0s, dtype=np.float64)
    return {
        "f0_mean": round(float(np.mean(arr)), 3),
        "f0_std": round(float(np.std(arr)), 3),
        "f0_min": round(float(np.min(arr)), 3),
        "f0_max": round(float(np.max(arr)), 3),
        "voiced_ratio": round(float(voiced / max(total, 1)), 4),
    }


def _spectral_shape(frame: np.ndarray, sr: int) -> tuple[float, float, float]:
    """centroid (Hz), bandwidth (Hz), rolloff 85% (Hz)."""
    mag = np.abs(np.fft.rfft(frame * np.hanning(len(frame)))) + 1e-10
    freqs = np.fft.rfftfreq(len(frame), d=1.0 / sr)
    power = mag ** 2
    total = float(np.sum(power))
    if total <= 0:
        return 0.0, 0.0, 0.0
    centroid = float(np.sum(freqs * power) / total)
    bandwidth = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * power) / total))
    cum = np.cumsum(power)
    thr = 0.85 * cum[-1]
    idx = int(np.searchsorted(cum, thr))
    idx = min(idx, len(freqs) - 1)
    rolloff = float(freqs[idx])
    return centroid, bandwidth, rolloff


def extract_features(audio: np.ndarray, sr: int = _SAMPLE_RATE) -> dict[str, Any]:
    """
    Extract acoustic fingerprint from raw PCM float32 audio.
    Returns a compact, storable feature dict. No raw audio stored.

    r1602 feature_version=2: ≥20 MFCC + Δ + ΔΔ means, F0 stats, spectral shape.
    """
    signal = np.asarray(audio, dtype=np.float32).reshape(-1)
    if signal.ndim > 1:
        signal = signal.mean(axis=1)

    peak = float(np.max(np.abs(signal))) if signal.size else 0.0
    if peak > 0:
        signal = signal / peak

    frames = _frames(signal, _FRAME_SIZE, _FRAME_SIZE // 2)
    if not frames:
        return {
            "feature_version": _FEATURE_VERSION,
            "rms_mean": 0.0,
            "rms_std": 0.0,
            "crest_factor_mean": 0.0,
            "spectral_flatness_mean": 0.0,
            "spectral_flatness_std": 0.0,
            "zcr_mean": 0.0,
            "mfcc": [0.0] * _N_MFCC,
            "mfcc_std": [0.0] * _N_MFCC,
            "mfcc_delta": [0.0] * _N_MFCC,
            "mfcc_delta2": [0.0] * _N_MFCC,
            "f0_mean": 0.0,
            "f0_std": 0.0,
            "f0_min": 0.0,
            "f0_max": 0.0,
            "voiced_ratio": 0.0,
            "centroid_mean": 0.0,
            "bandwidth_mean": 0.0,
            "rolloff_mean": 0.0,
            "duration_s": 0.0,
        }

    rms_vals = [_rms(f) for f in frames]
    crest_vals = [_crest_factor(f) for f in frames]
    flat_vals = [_spectral_flatness(f) for f in frames]
    zcr_vals = [_zero_crossing_rate(f) for f in frames]

    cents, bws, rolls = [], [], []
    for f in frames[:128]:
        c, b, r = _spectral_shape(f, sr)
        cents.append(c)
        bws.append(b)
        rolls.append(r)

    mfcc_mat = _mfcc_bank(signal, sr, n_mfcc=_N_MFCC)
    d1 = _delta(mfcc_mat)
    d2 = _delta(d1)
    mfcc_mean = np.mean(mfcc_mat, axis=0)
    mfcc_std = np.std(mfcc_mat, axis=0)
    d1_mean = np.mean(d1, axis=0)
    d2_mean = np.mean(d2, axis=0)

    f0 = _estimate_f0(signal, sr)

    return {
        "feature_version": _FEATURE_VERSION,
        "rms_mean": round(float(np.mean(rms_vals)), 6),
        "rms_std": round(float(np.std(rms_vals)), 6),
        "crest_factor_mean": round(float(np.mean(crest_vals)), 4),
        "spectral_flatness_mean": round(float(np.mean(flat_vals)), 6),
        "spectral_flatness_std": round(float(np.std(flat_vals)), 6),
        "zcr_mean": round(float(np.mean(zcr_vals)), 6),
        "mfcc": [round(float(x), 4) for x in mfcc_mean.tolist()],
        "mfcc_std": [round(float(x), 4) for x in mfcc_std.tolist()],
        "mfcc_delta": [round(float(x), 4) for x in d1_mean.tolist()],
        "mfcc_delta2": [round(float(x), 4) for x in d2_mean.tolist()],
        "f0_mean": f0["f0_mean"],
        "f0_std": f0["f0_std"],
        "f0_min": f0["f0_min"],
        "f0_max": f0["f0_max"],
        "voiced_ratio": f0["voiced_ratio"],
        "centroid_mean": round(float(np.mean(cents)), 2),
        "bandwidth_mean": round(float(np.mean(bws)), 2),
        "rolloff_mean": round(float(np.mean(rolls)), 2),
        "duration_s": round(len(signal) / float(sr), 3),
    }


# ── Ledger IO ────────────────────────────────────────────────────────────────

def write_exemplar(
    features: dict[str, Any],
    label: str,
    *,
    note: str = "",
    device_name: str = "",
    ledger_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Write a labeled acoustic exemplar to the stigmergic ledger."""
    path = Path(ledger_path) if ledger_path else _LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
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
        "feature_version": int(features.get("feature_version") or _FEATURE_VERSION),
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load_exemplars(
    max_per_label: int = 30,
    *,
    ledger_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Load recent exemplars from the ledger, capped per label."""
    path = Path(ledger_path) if ledger_path else _LEDGER
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_bytes().splitlines()
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


# ── Swimmer nearest-neighbor + prototype classifier ─────────────────────────

def _pad_list(xs: Any, n: int, fill: float = 0.0) -> list[float]:
    out = [float(x) for x in (xs or [])][:n]
    while len(out) < n:
        out.append(fill)
    return out


def _feature_vector(features: dict[str, Any]) -> np.ndarray:
    """Flatten features into a comparable vector (v1 + v2 compatible)."""
    n = _N_MFCC
    mfcc = _pad_list(features.get("mfcc"), n)
    mfcc_std = _pad_list(features.get("mfcc_std"), n)
    d1 = _pad_list(features.get("mfcc_delta"), n)
    d2 = _pad_list(features.get("mfcc_delta2"), n)

    # F0 normalized into ~[0,1] bands
    f0_mean = float(features.get("f0_mean") or 0.0) / 400.0
    f0_std = float(features.get("f0_std") or 0.0) / 80.0
    voiced = float(features.get("voiced_ratio") or 0.0)
    centroid = float(features.get("centroid_mean") or 0.0) / 8000.0
    bandwidth = float(features.get("bandwidth_mean") or 0.0) / 4000.0
    rolloff = float(features.get("rolloff_mean") or 0.0) / 8000.0

    vec = [
        float(features.get("rms_mean", 0.0)) * 8.0,
        float(features.get("rms_std", 0.0)) * 8.0,
        float(features.get("crest_factor_mean", 0.0)) * 0.15,
        float(features.get("spectral_flatness_mean", 0.0)) * 6.0,
        float(features.get("spectral_flatness_std", 0.0)) * 6.0,
        float(features.get("zcr_mean", 0.0)) * 6.0,
        f0_mean * 4.0,
        f0_std * 3.0,
        voiced * 3.0,
        centroid * 2.5,
        bandwidth * 2.0,
        rolloff * 2.0,
    ]
    # MFCC mean: scale later coeffs lighter
    for i, x in enumerate(mfcc):
        scale = 0.08 if i < 13 else 0.06
        vec.append(x * scale)
    for x in mfcc_std:
        vec.append(x * 0.04)
    for x in d1:
        vec.append(x * 0.05)
    for x in d2:
        vec.append(x * 0.04)
    return np.asarray(vec, dtype=np.float32)


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _class_prototypes(exemplars: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    buckets: dict[str, list[np.ndarray]] = {}
    for ex in exemplars:
        feat = ex.get("features")
        if not isinstance(feat, dict):
            continue
        lab = normalize_voice_source_label(str(ex.get("source_label") or "unknown"))
        buckets.setdefault(lab, []).append(_feature_vector(feat))
    protos: dict[str, np.ndarray] = {}
    for lab, vecs in buckets.items():
        if vecs:
            protos[lab] = np.mean(np.stack(vecs, axis=0), axis=0)
    return protos


def classify(
    features: dict[str, Any],
    exemplars: Optional[list[dict[str, Any]]] = None,
    *,
    top_k: int = 5,
    ledger_path: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Swimmer nearest-neighbor + class-prototype vote.
    Returns {label, confidence, votes, distances, margin}.
    No LLM. Pure stigmergic receipts.
    """
    if exemplars is None:
        exemplars = load_exemplars(ledger_path=ledger_path)
    if not exemplars:
        return {
            "label": "unknown",
            "confidence": 0.0,
            "votes": {},
            "n_exemplars": 0,
            "margin": 0.0,
            "nearest_dist": 99.0,
        }

    query = _feature_vector(features)
    scored: list[tuple[float, str]] = []  # (distance, label)
    for ex in exemplars:
        ex_feat = ex.get("features")
        if not isinstance(ex_feat, dict):
            continue
        ref = _feature_vector(ex_feat)
        # Blend L2 with cosine distance for scale robustness
        l2 = float(np.linalg.norm(query - ref))
        cos_d = 1.0 - _cosine_sim(query, ref)
        dist = 0.55 * l2 + 0.45 * cos_d * 10.0
        label = normalize_voice_source_label(str(ex.get("source_label") or "unknown"))
        scored.append((dist, label))

    if not scored:
        return {
            "label": "unknown",
            "confidence": 0.0,
            "votes": {},
            "n_exemplars": len(exemplars),
            "margin": 0.0,
            "nearest_dist": 99.0,
        }

    scored.sort(key=lambda x: x[0])
    top = scored[: max(1, top_k)]

    votes: dict[str, float] = {}
    for dist, label in top:
        weight = 1.0 / (dist + 1e-6)
        votes[label] = votes.get(label, 0.0) + weight

    # Prototype boost — stabilizes leave-one-out and media rejection
    protos = _class_prototypes(exemplars)
    proto_sims: dict[str, float] = {}
    for lab, proto in protos.items():
        sim = _cosine_sim(query, proto)
        proto_sims[lab] = sim
        votes[lab] = votes.get(lab, 0.0) + max(0.0, sim) * 2.5

    total = sum(votes.values())
    best_label = max(votes, key=lambda l: votes[l])
    confidence = round(votes[best_label] / total, 3) if total > 0 else 0.0

    # Margin: best confidence share vs second-best (and vs best non-owner if owner)
    ordered = sorted(votes.items(), key=lambda x: -x[1])
    if len(ordered) >= 2 and total > 0:
        margin = round((ordered[0][1] - ordered[1][1]) / total, 3)
    else:
        margin = confidence

    # Owner-vs-best-media margin (for gate diagnostics)
    owner_score = votes.get(PRIMARY_OPERATOR_VOICE_LABEL, 0.0)
    media_score = max(
        (votes.get(l, 0.0) for l in ("youtube", "phone", "environment", "keyboard")),
        default=0.0,
    )
    owner_margin = round((owner_score - media_score) / total, 3) if total > 0 else 0.0

    return {
        "label": best_label,
        "confidence": confidence,
        "votes": {k: round(v / total, 3) for k, v in sorted(votes.items(), key=lambda x: -x[1])},
        "n_exemplars": len(exemplars),
        "nearest_dist": round(scored[0][0], 4),
        "margin": margin,
        "owner_margin": owner_margin,
        "proto_sims": {k: round(v, 3) for k, v in sorted(proto_sims.items(), key=lambda x: -x[1])},
    }


def exemplar_counts(*, ledger_path: Optional[Path] = None) -> dict[str, int]:
    """How many exemplars per label we have."""
    exemplars = load_exemplars(max_per_label=999, ledger_path=ledger_path)
    counts: dict[str, int] = {}
    for ex in exemplars:
        label = normalize_voice_source_label(str(ex.get("source_label") or "unknown"))
        counts[label] = counts.get(label, 0) + 1
    return counts


def last_enrollment_ts(*, ledger_path: Optional[Path] = None) -> float:
    """Most recent primary_operator exemplar timestamp (0 if none)."""
    latest = 0.0
    for ex in load_exemplars(max_per_label=999, ledger_path=ledger_path):
        if normalize_voice_source_label(str(ex.get("source_label") or "")) != PRIMARY_OPERATOR_VOICE_LABEL:
            continue
        try:
            latest = max(latest, float(ex.get("ts") or 0.0))
        except (TypeError, ValueError):
            continue
    return latest


# ── Leave-one-out harness (VA1 acceptance) ───────────────────────────────────

def leave_one_out_eval(
    exemplars: Optional[list[dict[str, Any]]] = None,
    *,
    ledger_path: Optional[Path] = None,
    receipt_path: Optional[Path] = None,
    write_receipt: bool = False,
) -> dict[str, Any]:
    """
    Leave-one-out classification over enrolled exemplars.

    Acceptance (r1602 VA1):
      - overall accuracy >= 0.85
      - every primary_operator exemplar beats best media competitor by margin >= 0.15
        (owner_margin when predicted as owner, or correct class margin)
    """
    if exemplars is None:
        exemplars = load_exemplars(max_per_label=999, ledger_path=ledger_path)
    usable = [e for e in exemplars if isinstance(e.get("features"), dict)]
    if len(usable) < 2:
        result = {
            "truth_label": "VOICE_IDENTITY_LOO_V1",
            "n": len(usable),
            "accuracy": 0.0,
            "correct": 0,
            "per_label": {},
            "primary_operator_margins": [],
            "min_primary_margin": 0.0,
            "mean_primary_margin": 0.0,
            "passes_accuracy": False,
            "passes_margin": False,
            "passes": False,
        }
        return result

    correct = 0
    per_label: dict[str, dict[str, int]] = {}
    primary_margins: list[float] = []
    rows_out: list[dict[str, Any]] = []

    for i, held in enumerate(usable):
        true_lab = normalize_voice_source_label(str(held.get("source_label") or "unknown"))
        train = [e for j, e in enumerate(usable) if j != i]
        # Need at least one other of some class
        if not train:
            continue
        pred = classify(held["features"], train, top_k=5)
        pred_lab = str(pred.get("label") or "unknown")
        ok = pred_lab == true_lab
        if ok:
            correct += 1
        bucket = per_label.setdefault(true_lab, {"n": 0, "correct": 0})
        bucket["n"] += 1
        if ok:
            bucket["correct"] += 1

        # Owner margin: when held-out is primary_operator, measure owner vs best media
        if true_lab == PRIMARY_OPERATOR_VOICE_LABEL:
            # Recompute votes with full prototype on train set
            om = float(pred.get("owner_margin") or 0.0)
            # If misclassified as media, margin is negative — still record
            if pred_lab != PRIMARY_OPERATOR_VOICE_LABEL:
                om = -abs(1.0 - float(pred.get("confidence") or 0.0))
            primary_margins.append(om)

        rows_out.append(
            {
                "true": true_lab,
                "pred": pred_lab,
                "ok": ok,
                "confidence": pred.get("confidence"),
                "owner_margin": pred.get("owner_margin"),
            }
        )

    n = len(rows_out)
    accuracy = round(correct / n, 4) if n else 0.0
    min_pm = round(min(primary_margins), 4) if primary_margins else 0.0
    mean_pm = round(float(np.mean(primary_margins)), 4) if primary_margins else 0.0
    passes_accuracy = accuracy >= 0.85
    # Every primary exemplar must beat best media by >= 0.15
    passes_margin = bool(primary_margins) and all(m >= _MARGIN_TARGET for m in primary_margins)

    result = {
        "truth_label": "VOICE_IDENTITY_LOO_V1",
        "ts": time.time(),
        "n": n,
        "correct": correct,
        "accuracy": accuracy,
        "per_label": {
            k: {
                "n": v["n"],
                "correct": v["correct"],
                "accuracy": round(v["correct"] / v["n"], 4) if v["n"] else 0.0,
            }
            for k, v in sorted(per_label.items())
        },
        "primary_operator_margins": [round(m, 4) for m in primary_margins],
        "min_primary_margin": min_pm,
        "mean_primary_margin": mean_pm,
        "passes_accuracy": passes_accuracy,
        "passes_margin": passes_margin,
        "passes": bool(passes_accuracy and passes_margin),
        "detail": rows_out,
    }

    if write_receipt:
        try:
            path = Path(receipt_path) if receipt_path else _LOO_RECEIPT
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                slim = {k: v for k, v in result.items() if k != "detail"}
                f.write(json.dumps(slim, ensure_ascii=False) + "\n")
        except OSError:
            pass
    return result


# ── Synthetic class audio (tests + re-seed when raw PCM absent) ──────────────

def synthesize_class_audio(
    label: str,
    *,
    seed: int = 0,
    duration_s: float = 1.2,
    sr: int = _SAMPLE_RATE,
) -> np.ndarray:
    """
    Deterministic class-discriminating synthetic audio for LOO harness / tests.
    Not a substitute for real enrollment — proves the feature bank separates classes.
    """
    label = normalize_voice_source_label(label)
    rng = np.random.default_rng(seed + hash(label) % 10_000)
    n = int(duration_s * sr)
    t = np.arange(n, dtype=np.float64) / float(sr)

    if label == PRIMARY_OPERATOR_VOICE_LABEL:
        # Near-field male speech-like: F0 ~115–130 Hz, strong formants, low flatness
        f0 = 118.0 + 8.0 * np.sin(2 * np.pi * 2.5 * t) + rng.normal(0, 0.4, n)
        sig = (
            0.55 * np.sin(2 * np.pi * f0 * t)
            + 0.28 * np.sin(2 * np.pi * (2 * f0) * t)
            + 0.18 * np.sin(2 * np.pi * 700 * t)
            + 0.12 * np.sin(2 * np.pi * 1200 * t)
            + 0.08 * np.sin(2 * np.pi * 2400 * t)
        )
        # mild AM envelope (syllables)
        env = 0.55 + 0.45 * (0.5 + 0.5 * np.sin(2 * np.pi * 4.0 * t))
        sig = sig * env + rng.normal(0, 0.01, n)

    elif label == "youtube":
        # Far-field / compressed broadcast: higher F0 band, flatter spectrum, more noise floor
        f0 = 175.0 + 20.0 * np.sin(2 * np.pi * 1.2 * t)
        sig = (
            0.25 * np.sin(2 * np.pi * f0 * t)
            + 0.22 * np.sin(2 * np.pi * (f0 * 1.5) * t)
            + 0.18 * np.sin(2 * np.pi * 900 * t)
            + 0.15 * np.sin(2 * np.pi * 1800 * t)
            + 0.12 * np.sin(2 * np.pi * 3200 * t)
            + 0.10 * np.sin(2 * np.pi * 4500 * t)
            + rng.normal(0, 0.06, n)
        )
        # soft clipping / compression
        sig = np.tanh(sig * 1.8) * 0.7

    elif label == "phone":
        # Band-limited telephone path ~300–3400 Hz, mid F0
        f0 = 145.0 + 5.0 * np.sin(2 * np.pi * 3.0 * t)
        sig = 0.5 * np.sin(2 * np.pi * f0 * t) + 0.2 * np.sin(2 * np.pi * 2 * f0 * t)
        # crude bandpass via spectral zeroing
        spec = np.fft.rfft(sig)
        freqs = np.fft.rfftfreq(n, d=1.0 / sr)
        mask = (freqs >= 300.0) & (freqs <= 3400.0)
        spec = spec * mask
        sig = np.fft.irfft(spec, n=n)
        sig = sig + rng.normal(0, 0.02, n)

    elif label == "keyboard":
        # Impulsive clicks
        sig = np.zeros(n, dtype=np.float64)
        click_times = rng.integers(0, n - 200, size=max(8, int(duration_s * 12)))
        for ct in click_times:
            length = int(rng.integers(80, 200))
            click = rng.normal(0, 1.0, length) * np.exp(-np.linspace(0, 8, length))
            end = min(n, ct + length)
            sig[ct:end] += click[: end - ct]
        sig = sig + rng.normal(0, 0.005, n)

    elif label == "environment":
        # Broadband room noise + low rumble
        sig = rng.normal(0, 0.08, n)
        sig += 0.05 * np.sin(2 * np.pi * 40 * t)
        sig += 0.03 * np.sin(2 * np.pi * 90 * t + 0.3)

    else:
        sig = rng.normal(0, 0.05, n)

    peak = float(np.max(np.abs(sig))) or 1.0
    sig = (sig / peak).astype(np.float32)
    return sig


def seed_discriminative_bank(
    *,
    per_class: int = 6,
    ledger_path: Optional[Path] = None,
    classes: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Write synthetic labeled exemplars with v2 features (test / bootstrap only)."""
    classes = classes or [
        PRIMARY_OPERATOR_VOICE_LABEL,
        "youtube",
        "phone",
        "environment",
        "keyboard",
    ]
    rows: list[dict[str, Any]] = []
    for lab in classes:
        for i in range(per_class):
            audio = synthesize_class_audio(lab, seed=1000 + i * 17 + hash(lab) % 97)
            feat = extract_features(audio)
            row = write_exemplar(
                feat,
                lab,
                note=f"synthetic_seed_v2_{lab}_{i}",
                device_name="synthetic",
                ledger_path=ledger_path,
            )
            rows.append(row)
    return rows


# ── VA2 enrollment session ("Alice, learn my voice") ─────────────────────────

def enrollment_session_path() -> Path:
    return _ENROLL_STATE


def start_voice_enrollment(
    *,
    n_clips: int = 5,
    label: str = PRIMARY_OPERATOR_VOICE_LABEL,
    state_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Begin a learn-my-voice session. Captures N clips then scores LOO."""
    state = Path(state_dir) if state_dir else _STATE
    state.mkdir(parents=True, exist_ok=True)
    path = state / "voice_enrollment_session.json"
    session = {
        "truth_label": "VOICE_ENROLLMENT_SESSION_V1",
        "session_id": str(uuid.uuid4()),
        "ts_start": time.time(),
        "label": normalize_voice_source_label(label),
        "n_target": int(max(3, n_clips)),
        "n_captured": 0,
        "clip_trace_ids": [],
        "status": "active",
        "message": (
            f"Enrollment open — speak {int(max(3, n_clips))} short phrases "
            f"(or type again after speaking). I will print the leave-one-out score when done."
        ),
    }
    path.write_text(json.dumps(session, indent=2), encoding="utf-8")
    return session


def get_voice_enrollment(state_dir: Optional[Path] = None) -> Optional[dict[str, Any]]:
    state = Path(state_dir) if state_dir else _STATE
    path = state / "voice_enrollment_session.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def enroll_audio_clip(
    audio: np.ndarray,
    *,
    note: str = "",
    device_name: str = "talk_mic",
    state_dir: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
    sr: int = _SAMPLE_RATE,
) -> dict[str, Any]:
    """
    Capture one enrollment clip into the active session.
    When n_target reached, runs leave-one-out and closes the session.
    """
    state = Path(state_dir) if state_dir else _STATE
    session = get_voice_enrollment(state_dir=state)
    if not session or session.get("status") != "active":
        return {"ok": False, "reason": "no_active_enrollment_session"}

    feat = extract_features(np.asarray(audio, dtype=np.float32), sr=sr)
    if float(feat.get("duration_s") or 0.0) < 0.35:
        return {"ok": False, "reason": "clip_too_short", "session": session}

    label = normalize_voice_source_label(str(session.get("label") or PRIMARY_OPERATOR_VOICE_LABEL))
    row = write_exemplar(
        feat,
        label,
        note=note or f"learn_my_voice session={session.get('session_id')}",
        device_name=device_name,
        ledger_path=ledger_path,
    )
    session["n_captured"] = int(session.get("n_captured") or 0) + 1
    ids = list(session.get("clip_trace_ids") or [])
    ids.append(row.get("trace_id"))
    session["clip_trace_ids"] = ids
    session["ts_last"] = time.time()

    n_target = int(session.get("n_target") or 5)
    result: dict[str, Any] = {
        "ok": True,
        "trace_id": row.get("trace_id"),
        "n_captured": session["n_captured"],
        "n_target": n_target,
        "complete": session["n_captured"] >= n_target,
    }

    if session["n_captured"] >= n_target:
        loo = leave_one_out_eval(
            ledger_path=ledger_path,
            receipt_path=state / "voice_identity_loo_receipts.jsonl",
            write_receipt=True,
        )
        session["status"] = "complete"
        session["ts_end"] = time.time()
        session["loo"] = {k: v for k, v in loo.items() if k != "detail"}
        session["message"] = (
            f"Learned your voice — {session['n_captured']} clips enrolled. "
            f"Leave-one-out accuracy={loo.get('accuracy')} "
            f"min_owner_margin={loo.get('min_primary_margin')} "
            f"pass={loo.get('passes')}."
        )
        result["loo"] = session["loo"]
        result["message"] = session["message"]
    else:
        left = n_target - session["n_captured"]
        session["message"] = f"Got clip {session['n_captured']}/{n_target}. Speak {left} more."
        result["message"] = session["message"]

    path = state / "voice_enrollment_session.json"
    path.write_text(json.dumps(session, indent=2), encoding="utf-8")
    result["session"] = session
    return result


def cancel_voice_enrollment(state_dir: Optional[Path] = None) -> dict[str, Any]:
    state = Path(state_dir) if state_dir else _STATE
    path = state / "voice_enrollment_session.json"
    session = get_voice_enrollment(state_dir=state) or {}
    session["status"] = "cancelled"
    session["ts_end"] = time.time()
    try:
        path.write_text(json.dumps(session, indent=2), encoding="utf-8")
    except OSError:
        pass
    return session


def voice_verdict_snapshot(
    *,
    last_confidence: float = 0.0,
    last_label: str = "",
    media_active: Optional[bool] = None,
    state_dir: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Read-only snapshot for Input Boundary panel (VA5)."""
    state = Path(state_dir) if state_dir else _STATE
    counts = exemplar_counts(ledger_path=ledger_path)
    last_ts = last_enrollment_ts(ledger_path=ledger_path)
    loo_path = state / "voice_identity_loo_receipts.jsonl"
    last_loo: dict[str, Any] = {}
    if loo_path.exists():
        try:
            lines = [ln for ln in loo_path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
            if lines:
                last_loo = json.loads(lines[-1])
        except Exception:
            last_loo = {}

    if media_active is None:
        try:
            from System.swarm_media_ingress_gate import ambient_media_context_active

            media_active = bool(ambient_media_context_active())
        except Exception:
            media_active = False

    return {
        "truth_label": "VOICE_VERDICT_SNAPSHOT_V1",
        "ts": time.time(),
        "owner_match_confidence": float(last_confidence or 0.0),
        "last_label": str(last_label or ""),
        "media_context_active": bool(media_active),
        "exemplar_counts": counts,
        "primary_operator_n": int(counts.get(PRIMARY_OPERATOR_VOICE_LABEL) or 0),
        "last_enrollment_ts": last_ts,
        "last_enrollment_age_days": (
            round((time.time() - last_ts) / 86400.0, 2) if last_ts else None
        ),
        "loo_accuracy": last_loo.get("accuracy"),
        "loo_min_primary_margin": last_loo.get("min_primary_margin"),
        "loo_passes": last_loo.get("passes"),
        "owner_threshold": _OWNER_CONF_THRESHOLD,
        "feature_version": _FEATURE_VERSION,
    }


def is_learn_my_voice_command(text: str) -> bool:
    """Detect enrollment trigger phrases (typed or spoken)."""
    t = " ".join(str(text or "").lower().split())
    if not t:
        return False
    triggers = (
        "learn my voice",
        "enroll my voice",
        "train my voice",
        "remember my voice",
        "relearn my voice",
        "alice learn my voice",
        "alice, learn my voice",
    )
    return any(p in t for p in triggers)


__all__ = [
    "LABELS",
    "PRIMARY_OPERATOR_VOICE_LABEL",
    "TRUTH_LABEL",
    "normalize_voice_source_label",
    "extract_features",
    "write_exemplar",
    "load_exemplars",
    "classify",
    "exemplar_counts",
    "last_enrollment_ts",
    "leave_one_out_eval",
    "synthesize_class_audio",
    "seed_discriminative_bank",
    "start_voice_enrollment",
    "get_voice_enrollment",
    "enroll_audio_clip",
    "cancel_voice_enrollment",
    "voice_verdict_snapshot",
    "is_learn_my_voice_command",
]
