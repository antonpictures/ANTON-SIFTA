#!/usr/bin/env python3
"""Cross-frequency coupling on SIFTA organ ledger cadence.

This organ measures Tort-style phase-amplitude coupling over append-only
ledger write events. It does not claim neural LFP, phenomenal binding, or
private experience; it turns event timestamps into rate signals and measures
whether a slower organ's write phase modulates a faster organ's write
amplitude.

Physics anchors:
- Canolty et al. 2006: high-gamma amplitude locked to theta phase.
- Tort et al. 2010: Modulation Index (MI) from phase-binned amplitude entropy.

Scope boundary (verbatim):
"Modulation Index computed on ledger write-event time series, not neural LFP. CFC here means phase-amplitude coupling between organ write-cadence bands, a stigmergic-substrate analog of Schooler's cross-frequency coupling requirement, not a claim about neural binding."

Truth label: ORGAN_CROSS_FREQUENCY_COUPLING_V0
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np

try:  # SciPy is preferred, but the organ must still compile without it.
    from scipy.signal import hilbert as _scipy_hilbert
except Exception:  # pragma: no cover - exercised only on minimal installs
    _scipy_hilbert = None

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - direct script fallback
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

TRUTH_LABEL = "ORGAN_CROSS_FREQUENCY_COUPLING_V0"
RECEIPT_LEDGER = "cfc_receipts.jsonl"
SCOPE_LIMIT = (
    "Modulation Index computed on ledger write-event time series, not neural LFP. "
    "CFC here means phase-amplitude coupling between organ write-cadence bands, "
    "a stigmergic-substrate analog of Schooler's cross-frequency coupling requirement, "
    "not a claim about neural binding."
)

# Same oscillator set as the Kuramoto organ. These are the real ledger filenames;
# the first Grok version accidentally looked for logical names like fiction.jsonl.
ORGAN_LEDGERS: tuple[tuple[str, str], ...] = (
    ("fiction", "fiction_organ_events.jsonl"),
    ("voice_scrub", "alice_voice_scrub_audit.jsonl"),
    ("swimmer_census", "slit_coherence_swimmer_census.jsonl"),
    ("residue", "residue_excretion_quality.jsonl"),
    ("owner_body", "owner_body_events.jsonl"),
    ("ambient", "ambient_room_transcripts.jsonl"),
    ("ide_doctor", "ide_stigmergic_trace.jsonl"),
    ("work_receipts", "work_receipts.jsonl"),
    ("thermal", "thermal_routing_decisions.jsonl"),
    ("self_citation", "self_citation_briefings.jsonl"),
)
ORGANS = [name for name, _ in ORGAN_LEDGERS]
_LEDGER_BY_ORGAN = dict(ORGAN_LEDGERS)


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def hilbert_backend() -> str:
    return "scipy.signal.hilbert" if _scipy_hilbert is not None else "numpy.fft.hilbert_fallback"


def _hilbert(x: np.ndarray) -> np.ndarray:
    values = np.asarray(x, dtype=float)
    if values.size == 0:
        return np.asarray([], dtype=complex)
    if _scipy_hilbert is not None:
        return _scipy_hilbert(values)

    n = values.size
    spectrum = np.fft.fft(values)
    h = np.zeros(n)
    if n % 2 == 0:
        h[0] = 1.0
        h[n // 2] = 1.0
        h[1:n // 2] = 2.0
    else:
        h[0] = 1.0
        h[1:(n + 1) // 2] = 2.0
    return np.fft.ifft(spectrum * h)


def ledger_filename_for(organ_or_ledger: str) -> str:
    name = str(organ_or_ledger or "").strip()
    if not name:
        return ""
    if name in _LEDGER_BY_ORGAN:
        return _LEDGER_BY_ORGAN[name]
    return name if name.endswith(".jsonl") else f"{name}.jsonl"


def _coerce_ts(value: Any) -> float:
    if isinstance(value, dict):
        value = value.get("physical_pt") or value.get("ts")
    try:
        return float(value or 0.0)
    except Exception:
        pass
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text).timestamp()
        except Exception:
            return 0.0
    return 0.0


def _row_ts(row: dict[str, Any]) -> float:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
    for key in ("ts", "timestamp", "source_ts", "created_at", "ts_iso"):
        ts = _coerce_ts(payload.get(key) or row.get(key))
        if ts > 0:
            return ts
    return 0.0


def _receipt_hash(row: dict[str, Any]) -> str:
    raw = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def load_event_times(
    organ_or_ledger: str,
    *,
    state_dir: Path | str | None = None,
    window_s: float = 1800.0,
    now: float | None = None,
    max_rows: int = 4096,
) -> np.ndarray:
    """Load recent event timestamps for an organ or explicit JSONL ledger."""
    current = float(now if now is not None else time.time())
    cutoff = current - max(1.0, float(window_s))
    path = _state_dir(state_dir) / ledger_filename_for(organ_or_ledger)
    if not path.exists():
        return np.asarray([], dtype=float)

    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            end = handle.tell()
            handle.seek(max(0, end - 1024 * 1024))
            lines = handle.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return np.asarray([], dtype=float)

    times: list[float] = []
    for line in lines[-max_rows:]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        ts = _row_ts(row)
        if cutoff <= ts <= current:
            times.append(ts)
    return np.asarray(sorted(times), dtype=float)


def _event_rate_signal(
    times: np.ndarray,
    *,
    window_s: float,
    high_hz: float,
    now: float,
    max_samples: int = 4096,
) -> tuple[np.ndarray, float]:
    if len(times) == 0:
        return np.asarray([], dtype=float), 0.0
    duration = max(1.0, float(window_s))
    requested_fs = max(0.05, min(8.0, float(high_hz) * 8.0))
    n_samples = int(min(max_samples, max(64, math.ceil(duration * requested_fs))))
    fs = n_samples / duration
    start = now - duration
    edges = np.linspace(start, now, n_samples + 1)
    hist, _ = np.histogram(times, bins=edges)
    rate = hist.astype(float)
    if rate.size:
        rate -= float(np.mean(rate))
    return rate, fs


def _fft_bandpass(signal: np.ndarray, fs: float, low_hz: float, high_hz: float) -> np.ndarray:
    values = np.asarray(signal, dtype=float)
    if values.size < 4 or fs <= 0:
        return np.asarray([], dtype=float)
    nyquist = fs / 2.0
    low = max(0.0, float(low_hz))
    high = min(float(high_hz), nyquist)
    if high <= low:
        return np.zeros_like(values)
    spectrum = np.fft.rfft(values)
    freqs = np.fft.rfftfreq(values.size, d=1.0 / fs)
    mask = (freqs >= low) & (freqs <= high)
    if not np.any(mask):
        return np.zeros_like(values)
    spectrum[~mask] = 0
    return np.fft.irfft(spectrum, n=values.size)


def analytic_from_ledger(
    organ_or_ledger: str,
    window_s: float,
    bandpass_low_hz: float,
    bandpass_high_hz: float,
    *,
    state_dir: Path | str | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Return filtered signal, phase, and amplitude for a ledger event-rate band."""
    current = float(now if now is not None else time.time())
    times = load_event_times(
        organ_or_ledger,
        state_dir=state_dir,
        window_s=window_s,
        now=current,
    )
    if len(times) < 3:
        return {
            "organ": organ_or_ledger,
            "event_count": int(len(times)),
            "filtered": np.asarray([], dtype=float),
            "phase": np.asarray([], dtype=float),
            "amplitude": np.asarray([], dtype=float),
            "sample_hz": 0.0,
            "skipped_reason": "insufficient_events",
        }

    rate, fs = _event_rate_signal(times, window_s=window_s, high_hz=bandpass_high_hz, now=current)
    filtered = _fft_bandpass(rate, fs, bandpass_low_hz, bandpass_high_hz)
    if filtered.size < 16 or not np.any(np.abs(filtered) > 1e-12):
        return {
            "organ": organ_or_ledger,
            "event_count": int(len(times)),
            "filtered": filtered,
            "phase": np.asarray([], dtype=float),
            "amplitude": np.asarray([], dtype=float),
            "sample_hz": fs,
            "skipped_reason": "no_band_energy",
        }

    analytic = _hilbert(filtered)
    return {
        "organ": organ_or_ledger,
        "event_count": int(len(times)),
        "filtered": filtered,
        "phase": np.angle(analytic),
        "amplitude": np.abs(analytic),
        "sample_hz": fs,
        "skipped_reason": "",
    }


def extract_signal_from_ledger(
    ledger_name: str,
    window_s: float,
    bandpass_low_hz: float,
    bandpass_high_hz: float,
    *,
    state_dir: Path | str | None = None,
    now: float | None = None,
) -> np.ndarray:
    """Back-compatible API: return the analytic amplitude envelope."""
    return analytic_from_ledger(
        ledger_name,
        window_s,
        bandpass_low_hz,
        bandpass_high_hz,
        state_dir=state_dir,
        now=now,
    )["amplitude"]


def modulation_index(
    phase_slow: np.ndarray,
    amplitude_fast: np.ndarray,
    n_bins: int = 18,
) -> float:
    """Tort 2010 Modulation Index: KL(phase-binned amplitude || uniform)/log(N)."""
    phase = np.asarray(phase_slow, dtype=float)
    amp = np.asarray(amplitude_fast, dtype=float)
    n = min(phase.size, amp.size)
    if n == 0:
        return 0.0
    phase = phase[:n]
    amp = amp[:n]
    valid = np.isfinite(phase) & np.isfinite(amp) & (amp >= 0)
    phase = phase[valid]
    amp = amp[valid]
    if phase.size == 0 or float(np.sum(amp)) <= 0:
        return 0.0

    bins = np.linspace(-np.pi, np.pi, int(n_bins) + 1)
    idx = np.digitize(phase, bins, right=False) - 1
    idx = np.clip(idx, 0, int(n_bins) - 1)
    mean_amp = np.zeros(int(n_bins), dtype=float)
    for bin_i in range(int(n_bins)):
        mask = idx == bin_i
        if np.any(mask):
            mean_amp[bin_i] = float(np.mean(amp[mask]))
    if float(np.sum(mean_amp)) <= 0:
        return 0.0
    p = mean_amp / float(np.sum(mean_amp))
    p = np.clip(p, 1e-12, None)
    p = p / float(np.sum(p))
    uniform = 1.0 / int(n_bins)
    kl = float(np.sum(p * np.log(p / uniform)))
    return float(np.clip(kl / math.log(int(n_bins)), 0.0, 1.0))


def _append_receipt(row: dict[str, Any], *, state_dir: Path | str | None = None) -> None:
    state = _state_dir(state_dir)
    path = state / RECEIPT_LEDGER
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def measure_cfc(
    slow_organ: str,
    fast_organ: str,
    window_s: float = 1800.0,
    slow_band: tuple[float, float] = (0.001, 0.01),
    fast_band: tuple[float, float] = (0.05, 0.5),
    *,
    state_dir: Path | str | None = None,
    now: float | None = None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Measure slow-organ phase to fast-organ amplitude coupling."""
    current = float(now if now is not None else time.time())
    slow = analytic_from_ledger(
        slow_organ,
        window_s,
        slow_band[0],
        slow_band[1],
        state_dir=state_dir,
        now=current,
    )
    fast = analytic_from_ledger(
        fast_organ,
        window_s,
        fast_band[0],
        fast_band[1],
        state_dir=state_dir,
        now=current,
    )
    skip_reasons = [r for r in (slow.get("skipped_reason"), fast.get("skipped_reason")) if r]
    if skip_reasons:
        mi = 0.0
        skipped_reason = ";".join(skip_reasons)
    else:
        mi = modulation_index(slow["phase"], fast["amplitude"])
        skipped_reason = ""

    receipt = {
        "ts": current,
        "truth_label": TRUTH_LABEL,
        "receipt_id": f"cfc-{uuid.uuid4().hex[:12]}",
        "window_s": float(window_s),
        "slow_organ": slow_organ,
        "fast_organ": fast_organ,
        "slow_ledger": ledger_filename_for(slow_organ),
        "fast_ledger": ledger_filename_for(fast_organ),
        "slow_band_hz": list(slow_band),
        "fast_band_hz": list(fast_band),
        "slow_event_count": int(slow.get("event_count") or 0),
        "fast_event_count": int(fast.get("event_count") or 0),
        "sample_hz_slow": round(float(slow.get("sample_hz") or 0.0), 6),
        "sample_hz_fast": round(float(fast.get("sample_hz") or 0.0), 6),
        "cfc_matrix": [[mi]],
        "n_organs": 2,
        "dominant_coupling": {"slow": slow_organ, "fast": fast_organ, "MI": mi},
        "max_MI": mi,
        "mean_MI": mi,
        "skipped_reason": skipped_reason,
        "hilbert_backend": hilbert_backend(),
        "doctrine_anchor": "Canolty 2006 + Tort 2010; Schooler & Riddle 2024 CFC requirement",
        "scope_limit": SCOPE_LIMIT,
    }
    receipt["receipt_hash"] = _receipt_hash(receipt)
    if write_receipt:
        _append_receipt(receipt, state_dir=state_dir)
    return receipt


def cfc_matrix(
    window_s: float = 1800.0,
    *,
    organs: Iterable[str] | None = None,
    state_dir: Path | str | None = None,
    now: float | None = None,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Compute all directed slow-phase to fast-amplitude CFC pairs."""
    names = list(organs or ORGANS)
    current = float(now if now is not None else time.time())
    matrix = np.zeros((len(names), len(names)), dtype=float)
    pair_receipts: list[dict[str, Any]] = []
    skipped_pairs = 0
    dominant = {"slow": "", "fast": "", "MI": 0.0}

    for i, slow in enumerate(names):
        for j, fast in enumerate(names):
            if i == j:
                continue
            pair = measure_cfc(
                slow,
                fast,
                window_s=window_s,
                state_dir=state_dir,
                now=current,
                write_receipt=False,
            )
            mi = float(pair["max_MI"])
            matrix[i, j] = mi
            if pair.get("skipped_reason"):
                skipped_pairs += 1
            if mi > float(dominant.get("MI") or 0.0):
                dominant = {"slow": slow, "fast": fast, "MI": mi}
            pair_receipts.append({
                "slow": slow,
                "fast": fast,
                "MI": mi,
                "skipped_reason": pair.get("skipped_reason", ""),
                "slow_event_count": pair.get("slow_event_count", 0),
                "fast_event_count": pair.get("fast_event_count", 0),
            })

    receipt = {
        "ts": current,
        "truth_label": TRUTH_LABEL,
        "receipt_id": f"cfc-{uuid.uuid4().hex[:12]}",
        "window_s": float(window_s),
        "organ_names": names,
        "ledger_map": {name: ledger_filename_for(name) for name in names},
        "slow_band_hz": [0.001, 0.01],
        "fast_band_hz": [0.05, 0.5],
        "cfc_matrix": matrix.tolist(),
        "matrix_shape": [len(names), len(names)],
        "n_organs": len(names),
        "pair_count": max(0, len(names) * (len(names) - 1)),
        "skipped_pairs": skipped_pairs,
        "dominant_coupling": dominant,
        "max_MI": float(np.max(matrix)) if matrix.size else 0.0,
        "mean_MI": float(np.mean(matrix)) if matrix.size else 0.0,
        "pair_summaries": pair_receipts[: min(20, len(pair_receipts))],
        "hilbert_backend": hilbert_backend(),
        "doctrine_anchor": "Canolty 2006 + Tort 2010; Schooler & Riddle 2024 CFC requirement",
        "scope_limit": SCOPE_LIMIT,
    }
    receipt["receipt_hash"] = _receipt_hash(receipt)
    if write_receipt:
        _append_receipt(receipt, state_dir=state_dir)
    return receipt


__all__ = [
    "ORGANS",
    "ORGAN_LEDGERS",
    "SCOPE_LIMIT",
    "TRUTH_LABEL",
    "analytic_from_ledger",
    "cfc_matrix",
    "extract_signal_from_ledger",
    "hilbert_backend",
    "ledger_filename_for",
    "load_event_times",
    "measure_cfc",
    "modulation_index",
]


if __name__ == "__main__":
    print(json.dumps(cfc_matrix(window_s=1800.0), indent=2, sort_keys=True))
