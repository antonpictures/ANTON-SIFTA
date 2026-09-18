"""Conservative keyboard-noise routing for the microphone ingress.

This organ decides whether a short STT window is better explained by nearby
keyboard clicks than speech. It is deliberately a routing aid, not a speaker,
attention, or mental-state detector. The caller must retain genuine speech when
the acoustic evidence is mixed or uncertain.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / ".sifta_state"
LEDGER_NAME = "keyboard_acoustic_receipts.jsonl"


def _in_capture_window(ts: float, start: float | None, end: float | None) -> bool:
    if start is None and end is None:
        return True
    if start is None or end is None or not (math.isfinite(start) and math.isfinite(end)):
        return False
    return start <= ts <= end


def _safe_timestamp(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _recent_edit_signal(
    events: Iterable[tuple[float, int]], now: float, window_s: float,
    capture_start_ts: float | None = None, capture_end_ts: float | None = None,
) -> dict[str, Any]:
    """Summarize recent text edits without retaining typed characters."""
    recent: list[tuple[float, int]] = []
    for item in events:
        try:
            ts, length = float(item[0]), int(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        if math.isfinite(ts) and 0 <= now - ts <= window_s and _in_capture_window(
            ts, capture_start_ts, capture_end_ts
        ):
            recent.append((ts, length))
    recent.sort()
    return {
        "event_count": len(recent),
        "recent": bool(recent),
        "typing_signal": len(recent) >= 2,
        "last_edit_age_s": round(now - recent[-1][0], 3) if recent else None,
    }


def _recent_physical_key_signal(
    events: Iterable[float], now: float, window_s: float,
    capture_start_ts: float | None, capture_end_ts: float | None,
) -> dict[str, Any]:
    """Count physical key events without retaining key values or text."""
    recent: list[float] = []
    for item in events:
        try:
            ts = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(ts) and 0 <= now - ts <= window_s and _in_capture_window(
            ts, capture_start_ts, capture_end_ts
        ):
            recent.append(ts)
    recent.sort()
    return {
        "event_count": len(recent),
        "recent": bool(recent),
        "typing_signal": len(recent) >= 2,
        "last_key_age_s": round(now - recent[-1], 3) if recent else None,
    }


def _acoustic_features(audio: Any, sample_rate: int) -> dict[str, float]:
    """Extract small, deterministic features; raw PCM never leaves this call."""
    try:
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    except Exception:
        samples = np.empty(0, dtype=np.float32)
    samples = samples[np.isfinite(samples)]
    if samples.size < max(64, sample_rate // 20):
        return {"rms": 0.0, "crest": 0.0, "transient_ratio": 0.0, "voiced_ratio": 0.0}

    frame = max(64, int(sample_rate * 0.02))
    count = samples.size // frame
    frames = samples[: count * frame].reshape(count, frame)
    rms = np.sqrt(np.mean(frames * frames, axis=1) + 1e-12)
    peak = np.max(np.abs(frames), axis=1)
    floor = float(np.median(rms)) + 1e-6
    # Clicks produce isolated high-crest frames; speech occupies more frames.
    active = rms > max(floor * 1.6, 1e-4)
    crest = peak / (rms + 1e-6)
    transient_ratio = float(np.mean((crest > 4.0) & active)) if count else 0.0

    voiced = 0
    usable = 0
    for row, row_rms in zip(frames, rms):
        if row_rms <= max(floor * 1.2, 1e-4):
            continue
        usable += 1
        centered = row - float(np.mean(row))
        denom = float(np.dot(centered, centered)) + 1e-9
        correlations = []
        for lag in range(max(2, int(sample_rate / 300)), max(3, int(sample_rate / 80))):
            correlations.append(float(np.dot(centered[:-lag], centered[lag:]) / denom))
        if correlations and max(correlations) >= 0.35:
            voiced += 1
    voiced_ratio = voiced / usable if usable else 0.0
    return {
        "rms": round(float(np.sqrt(np.mean(samples * samples))), 6),
        "crest": round(float(np.max(np.abs(samples)) / (np.sqrt(np.mean(samples * samples)) + 1e-6)), 3),
        "transient_ratio": round(transient_ratio, 4),
        "voiced_ratio": round(float(voiced_ratio), 4),
    }


def classify_keyboard_audio(
    audio: Any,
    *,
    typed_events: Iterable[tuple[float, int]] = (),
    physical_key_events: Iterable[float] | None = None,
    captured_at: float | None = None,
    sample_rate: int = 16_000,
    window_s: float = 4.0,
    utterance_id: str | None = None,
    source: str | None = None,
    session: str | None = None,
    clock: str | None = None,
    capture_start_ts: float | None = None,
    capture_end_ts: float | None = None,
) -> dict[str, Any]:
    """Return a conservative route for an STT window.

    ``ambient_keyboard`` requires both a recent edit signal and click-shaped,
    weakly voiced audio. Any missing or conflicting evidence is ``uncertain``.

    The return always carries a bounded per-utterance evidence record
    (utterance identity, source/session, capture start/end with explicit clock
    domain, sample rate, and extracted acoustic features) bound to this call so
    it travels with the owning STT worker's result.
    """
    clock_domain = str(clock or "monotonic")
    clock_valid = clock_domain in {"wall", "monotonic"}
    if not clock_valid:
        clock_domain = "unknown"
    captured_ts = _safe_timestamp(captured_at)
    captured_valid = captured_at is None or captured_ts is not None
    now = captured_ts if captured_ts is not None else time.monotonic()
    start_ts = _safe_timestamp(capture_start_ts)
    end_ts = _safe_timestamp(capture_end_ts)
    edits = _recent_edit_signal(
        typed_events, now, window_s, start_ts, end_ts
    )
    physical = (
        _recent_physical_key_signal(
            physical_key_events or (), now, window_s,
            start_ts, end_ts,
        )
        if physical_key_events is not None else None
    )
    features = _acoustic_features(audio, sample_rate)
    click_score = min(1.0, features["transient_ratio"] * 2.0 + max(0.0, 1.0 - features["voiced_ratio"]) * 0.35)
    provenance_valid = physical is None or (
        clock_valid and captured_valid
        and start_ts is not None and end_ts is not None and end_ts >= start_ts
    )
    typing_signal = physical["typing_signal"] if physical is not None else edits["typing_signal"]
    if not provenance_valid:
        typing_signal = False
    if typing_signal and click_score >= 0.68 and features["voiced_ratio"] <= 0.35:
        route = "ambient_keyboard"
        reason = (
            "recent physical key signal aligned with non-voiced transient audio"
            if physical is not None else
            "recent text-edit signal aligned with non-voiced transient audio"
        )
    else:
        route = "uncertain"
        reason = "typing or acoustic evidence was absent, weak, stale, or speech-like"
    return {
        "schema": "SIFTA_KEYBOARD_ACOUSTIC_GATE_V1",
        "scope": "utterance",
        "route": route,
        "reason": reason,
        "confidence": round(click_score if route == "ambient_keyboard" else min(click_score, 0.49), 3),
        "heuristic_score": round(click_score, 3),
        "provenance_valid": provenance_valid,
        "captured_at": now,
        "editing": edits,
        "physical_keys": physical,
        "acoustic": features,
        "utterance_id": str(utterance_id) if utterance_id is not None else None,
        "source": str(source) if source is not None else None,
        "session": str(session) if session is not None else None,
        "clock": clock_domain,
        "capture_start_ts": start_ts,
        "capture_end_ts": end_ts,
    }


def write_keyboard_receipt(decision: Mapping[str, Any], *, state_dir: Path | str | None = None) -> dict[str, Any]:
    """Append metadata only; no transcript or raw audio is persisted."""
    root = Path(state_dir) if state_dir is not None else STATE_DIR
    row = dict(decision)
    row["receipt_id"] = hashlib.sha256(
        json.dumps(row, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:24]
    row["truth_label"] = "OBSERVED_ACOUSTIC_ROUTING"
    try:
        root.mkdir(parents=True, exist_ok=True)
        with (root / LEDGER_NAME).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    except OSError as exc:
        return {
            "ok": False,
            "receipt_id": None,
            "error": type(exc).__name__,
            "schema": row.get("schema"),
            "route": row.get("route"),
        }
    row["ok"] = True
    return row
