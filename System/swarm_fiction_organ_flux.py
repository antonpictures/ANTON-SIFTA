"""System/swarm_fiction_organ_flux.py
========================================

**Fiction Organ Flux Ledger — narrative thermodynamics with numbers.**

The Fiction Organ (v2) tracks mode state + per-event rows. This module is
the second-order observable: how much *information* is moving through each
labeled lane per unit time, on which silicon, under which thermal state.
This is what turns "narrative thermodynamics" from doctrine into a
measurable Friston-style observable (research spine §E).

**What each flux row records (append-only, one per window):**

- `bytes_in_per_label`     — bytes stamped INTO each lane during the window
- `bytes_out_per_label`    — bytes written OUT to ledgers from each lane
- `transitions`            — count of label→label moves (e.g. SCRIPT→REAL)
- `time_in_label_s`        — wall-clock seconds spent in each label
- `transition_entropy`     — Shannon entropy of the transition distribution.
                              Friston free-energy proxy: high = explore,
                              low = exploit. Systems that minimize
                              free energy minimize this over the long run.
- `thermal_warning_level`  — read at flush time from thermal_cortex_state
- `low_power_mode`         — read at flush time from energy_cortex_state
- `observed_writes`        — count of OBSERVED-labeled rows in window
- `fiction_observed_ratio` — sum(fiction-class bytes) / max(1, observed bytes)

Process-local accumulator, append-only ledger flush. Safe for concurrent
callers via a threading.Lock.

Truth label: ``FICTION_ORGAN_FLUX_V1``.
"""
from __future__ import annotations

import json
import math
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_FLUX_LEDGER = _STATE / "fiction_organ_flux.jsonl"
_TRUTH_LABEL = "FICTION_ORGAN_FLUX_V1"

_FICTION_CLASS_LABELS = {
    "FICTION", "SCRIPT", "SYMBOLIC",
    "SIMULATION", "HYPOTHETICAL",
    "MEMORY", "ROLEPLAY",
}

_lock = threading.Lock()


class _Window:
    """Mutable accumulator for the current flux window."""

    __slots__ = (
        "started_ts", "last_label", "last_label_ts",
        "bytes_in", "bytes_out", "transitions",
        "time_in_label", "label_event_counts",
        "observed_writes",
    )

    def __init__(self) -> None:
        now = time.time()
        self.started_ts: float = now
        self.last_label: str = "REAL"
        self.last_label_ts: float = now
        self.bytes_in: Dict[str, int] = defaultdict(int)
        self.bytes_out: Dict[str, int] = defaultdict(int)
        self.transitions: Dict[str, int] = defaultdict(int)  # key "FROM__TO"
        self.time_in_label: Dict[str, float] = defaultdict(float)
        self.label_event_counts: Dict[str, int] = defaultdict(int)
        self.observed_writes: int = 0


_window = _Window()


# ── sensor reads (graceful no-op if files missing) ─────────────────────────

def _read_thermal_warning_level() -> int:
    p = _STATE / "thermal_cortex_state.json"
    try:
        return int(json.loads(p.read_text(encoding="utf-8")).get(
            "thermal_warning_level", 0) or 0)
    except Exception:
        return 0


def _read_low_power_mode() -> bool:
    p = _STATE / "energy_cortex_state.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if bool(d.get("low_power_mode")):
            return True
        if d.get("power_source") == "Battery Power":
            try:
                if float(d.get("charge_pct", 100) or 100) < 20.0:
                    return True
            except (TypeError, ValueError):
                pass
    except Exception:
        pass
    return False


def _safe_append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ── public recording API ───────────────────────────────────────────────────

def record_bytes_in(label: str, n_bytes: int) -> None:
    """Record N bytes flowing INTO a labeled lane (e.g. from stamp())."""
    if n_bytes <= 0:
        return
    with _lock:
        _window.bytes_in[label] += int(n_bytes)
        _window.label_event_counts[label] += 1


def record_bytes_out(label: str, n_bytes: int) -> None:
    """Record N bytes flowing OUT of a labeled lane to a ledger."""
    if n_bytes <= 0:
        return
    with _lock:
        _window.bytes_out[label] += int(n_bytes)
        if label == "OBSERVED":
            _window.observed_writes += 1


def record_transition(from_label: str, to_label: str) -> None:
    """Record a label transition. Updates time_in_label for the prior label."""
    now = time.time()
    if not from_label or not to_label:
        return
    with _lock:
        dt = max(0.0, now - _window.last_label_ts)
        _window.time_in_label[_window.last_label] += dt
        key = f"{from_label}__{to_label}"
        _window.transitions[key] += 1
        _window.last_label = to_label
        _window.last_label_ts = now


# ── flux computation + flush ───────────────────────────────────────────────

def _transition_entropy(transitions: Dict[str, int]) -> float:
    """Shannon entropy of the transition distribution, in nats.

    High entropy = many different transitions used (explore).
    Low entropy = mostly one transition (exploit / habit).
    Friston-style free-energy proxy: organisms that minimize free energy
    in the long run minimize this; short-term spikes are healthy exploration.
    """
    total = sum(transitions.values())
    if total <= 0:
        return 0.0
    h = 0.0
    for c in transitions.values():
        if c <= 0:
            continue
        p = c / total
        h -= p * math.log(p)
    return h


def _snapshot_locked() -> Dict[str, Any]:
    """Build the flux row from the current window. Must be called with _lock held."""
    now = time.time()
    # Update time-in-label for the currently-open label up to "now"
    time_in_label = dict(_window.time_in_label)
    dt = max(0.0, now - _window.last_label_ts)
    time_in_label[_window.last_label] = time_in_label.get(_window.last_label, 0.0) + dt

    bytes_in = dict(_window.bytes_in)
    bytes_out = dict(_window.bytes_out)
    transitions = dict(_window.transitions)

    fiction_bytes = sum(v for k, v in bytes_in.items() if k in _FICTION_CLASS_LABELS)
    observed_bytes = bytes_in.get("OBSERVED", 0)
    ratio = fiction_bytes / max(1, observed_bytes)

    row = {
        "ts": now,
        "truth_label": _TRUTH_LABEL,
        "window_start_ts": _window.started_ts,
        "window_s": round(now - _window.started_ts, 3),
        "bytes_in_per_label": bytes_in,
        "bytes_out_per_label": bytes_out,
        "transitions": transitions,
        "time_in_label_s": {k: round(v, 3) for k, v in time_in_label.items()},
        "label_event_counts": dict(_window.label_event_counts),
        "transition_entropy_nats": round(_transition_entropy(transitions), 4),
        "observed_writes": _window.observed_writes,
        "fiction_observed_ratio": round(ratio, 4),
        "current_label_at_flush": _window.last_label,
        "thermal_warning_level": _read_thermal_warning_level(),
        "low_power_mode": _read_low_power_mode(),
    }
    return row


def flush_window(*, reset: bool = True, write_ledger: bool = True) -> Dict[str, Any]:
    """Flush the current accumulator to the flux ledger.

    Args:
        reset:         if True, start a fresh window after writing the row.
        write_ledger:  if True, append to .sifta_state/fiction_organ_flux.jsonl.

    Returns the flux row that was written (or would have been written).
    """
    global _window
    with _lock:
        row = _snapshot_locked()
        if reset:
            # Preserve the currently-active label across the reset so
            # time_in_label for an open lane continues to accrue.
            carry_label = _window.last_label
            _window = _Window()
            _window.last_label = carry_label
            _window.last_label_ts = time.time()
    if write_ledger:
        _safe_append_jsonl(_FLUX_LEDGER, row)
    return row


def snapshot_window() -> Dict[str, Any]:
    """Read-only view of the current accumulator (no flush, no reset)."""
    with _lock:
        return _snapshot_locked()


def reset_window() -> None:
    """Discard the current window without writing. Use only for test setup."""
    global _window
    with _lock:
        carry_label = _window.last_label
        _window = _Window()
        _window.last_label = carry_label
        _window.last_label_ts = time.time()


if __name__ == "__main__":
    snap = snapshot_window()
    print(json.dumps(snap, indent=2, default=str))
