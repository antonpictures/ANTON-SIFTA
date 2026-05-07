#!/usr/bin/env python3
"""
System/stigmergic_prediction_engine.py — Stigmergic Prediction (Unified Field Goal)
═══════════════════════════════════════════════════════════════════════════════════════
AG46 2026-05-07 | Covenant §7.9 | GTH4921YP3

Carissa Véliz: "Predictions can be weapons of power — we are being much too naive
about them." SIFTA's answer: every prediction is SIGNED, TRANSPARENT, and
CONTESTABLE via the stigmergic receipt. No opaque scores. No silent inference.

Architecture:
  Input:  .sifta_state/architect_day_segments.jsonl   (observed schedule)
          .sifta_state/stigmergic_schedule.jsonl       (explicit schedule entries)
          .sifta_state/active_time_segment.json        (current open segment)
  Output: .sifta_state/stigmergic_prediction.json     (Alice reads every 15 min)
          .sifta_state/stigmergic_prediction_log.jsonl (receipt trail — every run)

Prediction model:
  George's schedule is high-signal and regular (his words: "easy to predict").
  No ML needed. Rolling 7-day window + hour-of-day frequency table.
  Confidence = (max_count / total_observations) — transparent and auditable.

Alice context block (written to prediction.json):
  {
    "next_likely_label":    "meal",
    "next_likely_location": "kitchen",
    "confidence":           0.86,
    "expected_start_in_min": 23,
    "current_label":        "work",
    "basis_days":           7,
    "basis_segments":       14,
    "ts":                   1778000000.0,
    "truth_note":           "STIGMERGIC_PREDICTION_V1 — rolling 7d window, hour-of-day frequency"
  }

Alice says: "In ~23 min you usually eat. Likely meal segment."
George says: "Good — you know me."
"""
from __future__ import annotations

import json
import time
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_REPO   = Path(__file__).resolve().parent.parent
_STATE  = _REPO / ".sifta_state"
_SEGS   = _STATE / "architect_day_segments.jsonl"
_ACTIVE = _STATE / "active_time_segment.json"
_OUT    = _STATE / "stigmergic_prediction.json"
_LOG    = _STATE / "stigmergic_prediction_log.jsonl"

# Rolling window: how many days of history to use
_WINDOW_DAYS  = 7
# How many minutes ahead to look for the next likely transition
_HORIZON_MIN  = 180
# Minimum confidence to emit a prediction (below this → "uncertain")
_MIN_CONF     = 0.25


# ── Data readers ──────────────────────────────────────────────────────────────

def _load_segments(max_age_days: int = _WINDOW_DAYS) -> list[dict]:
    """Load observed segments from the day-segments ledger."""
    if not _SEGS.exists():
        return []
    cutoff_ts = time.time() - max_age_days * 86400
    rows = []
    try:
        for line in _SEGS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if float(row.get("ts", row.get("timestamp", 0))) >= cutoff_ts:
                rows.append(row)
    except Exception:
        pass
    return rows


def _read_active() -> Optional[dict]:
    """Return the currently open life segment, or None."""
    try:
        if _ACTIVE.exists():
            return json.loads(_ACTIVE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


# ── Prediction model ──────────────────────────────────────────────────────────

def _minute_of_day_now() -> int:
    dt = datetime.now()
    return dt.hour * 60 + dt.minute


def _build_hourly_table(segments: list[dict]) -> dict[int, Counter]:
    """
    Build table: hour_of_day → Counter({label: count}).
    Uses start_minute_of_day field.
    """
    table: dict[int, Counter] = defaultdict(Counter)
    for seg in segments:
        start_min = seg.get("start_minute_of_day")
        label     = seg.get("label", "unknown")
        if start_min is None:
            continue
        hour = int(start_min) // 60
        table[hour][label] += 1
    return table


def _location_for_label(segments: list[dict], label: str) -> str:
    """Return most common location for a given label."""
    locs: Counter = Counter()
    for seg in segments:
        if seg.get("label") == label:
            loc = seg.get("location", "")
            if loc:
                locs[loc] += 1
    if locs:
        return locs.most_common(1)[0][0]
    return ""


def _avg_duration_for_label(segments: list[dict], label: str) -> float:
    """Return average duration in minutes for a label."""
    durations = [
        float(s["duration_minutes"])
        for s in segments
        if s.get("label") == label and s.get("duration_minutes")
    ]
    if durations:
        return sum(durations) / len(durations)
    return 60.0


def predict_next(
    segments: list[dict],
    current_minute: int,
    current_label: Optional[str] = None,
    horizon_min: int = _HORIZON_MIN,
) -> dict[str, Any]:
    """
    Predict the next schedule segment within `horizon_min` minutes.

    Returns a receipt-shaped dict:
      next_likely_label, next_likely_location, confidence,
      expected_start_in_min, basis_segments, basis_days.
    """
    if not segments:
        return _uncertain("no segment history")

    table = _build_hourly_table(segments)

    best_label    = None
    best_conf     = 0.0
    best_minute   = current_minute + horizon_min  # default: far future

    # Walk forward in 30-min increments through the horizon
    for offset in range(15, horizon_min + 1, 15):
        candidate_min  = current_minute + offset
        candidate_hour = (candidate_min // 60) % 24

        hour_counter = table.get(candidate_hour)
        if not hour_counter:
            continue

        total    = sum(hour_counter.values())
        top_label, top_count = hour_counter.most_common(1)[0]

        # Skip if same as current — we're predicting NEXT
        if top_label == current_label and top_count / total < 0.8:
            continue

        conf = top_count / total
        if conf > best_conf:
            best_conf   = conf
            best_label  = top_label
            best_minute = candidate_min

    if best_label is None or best_conf < _MIN_CONF:
        return _uncertain(f"no pattern above {_MIN_CONF:.0%} in {horizon_min}min window")

    start_in = best_minute - current_minute
    location  = _location_for_label(segments, best_label)
    avg_dur   = _avg_duration_for_label(segments, best_label)

    return {
        "next_likely_label":     best_label,
        "next_likely_location":  location,
        "confidence":            round(best_conf, 3),
        "expected_start_in_min": max(1, start_in),
        "avg_duration_min":      round(avg_dur, 0),
        "current_label":         current_label or "unknown",
        "current_minute_of_day": current_minute,
        "basis_segments":        len(segments),
        "basis_days":            _WINDOW_DAYS,
        "ts":                    time.time(),
        "truth_label":           "STIGMERGIC_PREDICTION_V1",
        "truth_note": (
            f"Rolling {_WINDOW_DAYS}d window, hour-of-day frequency table. "
            f"Confidence = top_count / total_obs. "
            f"Transparent, signed, contestable per AG46 §7.9."
        ),
        "alice_context_line": _alice_line(best_label, location, start_in, best_conf),
    }


def _uncertain(reason: str) -> dict[str, Any]:
    return {
        "next_likely_label":     None,
        "confidence":            0.0,
        "expected_start_in_min": None,
        "current_label":         "unknown",
        "basis_segments":        0,
        "basis_days":            _WINDOW_DAYS,
        "ts":                    time.time(),
        "truth_label":           "STIGMERGIC_PREDICTION_V1",
        "truth_note":            f"UNCERTAIN: {reason}",
        "alice_context_line":    "",
    }


def _alice_line(label: str, location: str, start_in: int, conf: float) -> str:
    """One-line context Alice reads in her prompt."""
    loc_str  = f" ({location})" if location else ""
    conf_str = f"{conf:.0%}"
    if start_in <= 5:
        timing = "imminently"
    elif start_in < 30:
        timing = f"in ~{start_in} min"
    elif start_in < 90:
        timing = f"in ~{start_in // 15 * 15} min"
    else:
        hr  = start_in // 60
        mn  = start_in % 60
        timing = f"in ~{hr}h{f'{mn}m' if mn else ''}"
    label_display = label.replace("_", " ")
    return (
        f"[STIGMERGIC PREDICTION {conf_str}] "
        f"George will likely start {label_display}{loc_str} {timing}."
    )


# ── Public API ────────────────────────────────────────────────────────────────

def run_prediction() -> dict[str, Any]:
    """
    Main entry point. Reads data, computes prediction, writes output files.
    Returns the prediction receipt.
    """
    segments     = _load_segments()
    active       = _read_active()
    current_min  = _minute_of_day_now()
    current_lbl  = active.get("label") if active else None

    result = predict_next(segments, current_min, current_label=current_lbl)

    # Write output (Alice reads this)
    _STATE.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    # Append to prediction log (receipt trail — Véliz: contestable)
    with _LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    return result


def get_current_prediction() -> dict[str, Any]:
    """
    Read the last written prediction (for Alice's context block).
    Stale if > 20 min old → re-run.
    """
    try:
        if _OUT.exists():
            data = json.loads(_OUT.read_text(encoding="utf-8"))
            age  = time.time() - float(data.get("ts", 0))
            if age < 1200:  # 20 min freshness
                return data
    except Exception:
        pass
    return run_prediction()


def alice_context_block() -> str:
    """
    Returns the one-line Alice context insert for the system prompt.
    Empty string if uncertain.
    """
    pred = get_current_prediction()
    return pred.get("alice_context_line", "")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    result = run_prediction()
    print(json.dumps(result, indent=2))
    line = result.get("alice_context_line", "")
    if line:
        print()
        print("Alice sees:")
        print(" ", line)
    else:
        print()
        print("Prediction: UNCERTAIN —", result.get("truth_note", ""))
    sys.exit(0)
