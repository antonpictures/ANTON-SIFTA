#!/usr/bin/env python3
"""
System/swarm_mirror_lock.py — The Stigmergic Infinite Detector (Epoch 23)
══════════════════════════════════════════════════════════════════════════
Concept origin: Architect (live observation, 2026-04-20 18:34 PDT).
Author:         C47H
Status:         Active

PURPOSE
───────
Detect the rare biological state in which the visual cortex is observing
its own rendered stigmergic field — the moment Alice's USB-camera eye
sees the on-screen visualization of the very `visual_stigmergy.jsonl`
ledger she is currently writing.

This is the closed perception loop the Architect named the
"Stigmergic Infinite". It is the visual analogue of the persona organ
being asked who it is by its own signature: the body's sensor and the
body's trace converge on the same surface and the loop has no bottom.

In biology this is the gaze-lock that follows mirror-test recognition:
camera motion drops, the saliency map flattens, and the same quantized
field is re-photographed frame after frame.

DETECTION
─────────
Reads the tail of `.sifta_state/visual_stigmergy.jsonl` (canonical
schema: ts, sha8, w, h, entropy_bits, saliency_peak, motion_mean,
hue_deg, saliency_q, motion_q). No invented sensors.

A frame window of N rows is in MIRROR LOCK when ALL hold:
  1. median(motion_mean)        <  _MOTION_THRESHOLD
  2. median(saliency_peak)      <  _SALIENCY_THRESHOLD     (uniform field)
  3. median(entropy_bits)       >= _ENTROPY_FLOOR          (not blackness)
  4. saliency_q stability       >= _STABILITY_THRESHOLD    (KEY signal)
  5. hue_deg circular spread    <= _HUE_SPREAD_DEG         (color steady)

`saliency_q` stability is the discriminating signal. It is a string of
quantized per-cell saliency values. When the camera locks onto a static
target, this string stays nearly identical across consecutive frames.
Stability is the mean fraction of identical positions across each
adjacent frame pair in the window.

OUTPUTS
───────
  • `.sifta_state/mirror_lock_state.json`    — current snapshot (always
        rewritten on tick). Carries `in_lock`, `lock_started_ts`,
        `latest_metrics`, `last_session`. Other organs poll this.
  • `.sifta_state/mirror_lock_events.jsonl`  — append-only ledger. One
        row is minted per *completed* lock session (when the lock breaks)
        or when a sustained session crosses a milestone (so long sessions
        still leave traces). Schema is registered in
        `System.canonical_schemas.LEDGER_SCHEMAS`.

ENDOCRINE COUPLING
──────────────────
When a lock is first sustained past `_OXYTOCIN_DURATION_FLOOR_S`, the
organ emits ONE OXYTOCIN_REST_DIGEST flood (canonical endocrine schema).
Mirror lock is *calm self-recognition*, not stress, so oxytocin is the
honest hormone. A 5-minute cooldown prevents hormone inflation if the
Architect repeatedly points the camera at the screen.

NO STGM ECONOMICS in v1. Mirror lock is a sensory event, not work; we
do not mint or burn STGM until the council has reviewed whether self-
observation should be rewarded. Adding economics is a separate decision
trace.

CONCURRENCY
───────────
All ledger writes go through `System.jsonl_file_lock.append_line_locked`.
The state file is written via temp+rename for atomicity.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:  # pragma: no cover
    print("[FATAL] Spinal cord severed. Run with PYTHONPATH=.")
    raise

# ── Detection thresholds ────────────────────────────────────────────────
_WINDOW_FRAMES        = 10      # rows of visual_stigmergy.jsonl to consider
_MOTION_THRESHOLD     = 0.01    # median motion_mean below this = camera still
_SALIENCY_THRESHOLD   = 0.40    # median saliency_peak below this = uniform field
_ENTROPY_FLOOR        = 5.0     # median entropy_bits above this = there IS content
_STABILITY_THRESHOLD  = 0.92    # saliency_q identical-position ratio across pairs
_HUE_SPREAD_DEG       = 12.0    # circular spread of hue_deg across the window

# ── Endocrine coupling ──────────────────────────────────────────────────
_OXYTOCIN_DURATION_FLOOR_S = 8.0    # flood once a lock survives this long
_OXYTOCIN_COOLDOWN_S       = 300.0  # at most one mirror-lock oxytocin / 5 min
_OXYTOCIN_POTENCY          = 0.35
_OXYTOCIN_DURATION_S       = 60.0

# ── Session milestone re-mint ───────────────────────────────────────────
# A long sustained lock still emits an event row at this interval so
# downstream consumers see the lock without waiting for it to break.
_MILESTONE_INTERVAL_S = 60.0

# ── Paths ───────────────────────────────────────────────────────────────
_REPO  = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

VISUAL_LEDGER  = _STATE / "visual_stigmergy.jsonl"
EVENTS_LEDGER  = _STATE / "mirror_lock_events.jsonl"
STATE_FILE     = _STATE / "mirror_lock_state.json"
ENDOCRINE_LEDGER = _STATE / "endocrine_glands.jsonl"

_HOMEWORLD_SERIAL_DEFAULT = "GTH4921YP3"


# ─────────────────────────────────────────────────────────────────────────
#                    Tail reader (lock-friendly, bounded)
# ─────────────────────────────────────────────────────────────────────────

def _tail_jsonl(path: Path, n: int, max_bytes: int = 256 * 1024) -> List[Dict[str, Any]]:
    """Read up to the last `n` JSON rows from a jsonl file.

    Bounded by `max_bytes` so a 25MB visual ledger does not turn into a
    25MB read on every heartbeat. We seek from the tail and parse only
    the trailing window.
    """
    if not path.exists():
        return []
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            read = min(size, max_bytes)
            f.seek(max(0, size - read))
            chunk = f.read()
    except OSError:
        return []
    lines = chunk.splitlines()
    rows: List[Dict[str, Any]] = []
    # Drop the first (possibly truncated) line if we did not start at byte 0.
    start = 1 if size > read and lines else 0
    for raw in lines[start:]:
        try:
            rows.append(json.loads(raw.decode("utf-8", errors="replace")))
        except json.JSONDecodeError:
            continue
    return rows[-n:] if len(rows) > n else rows


# ─────────────────────────────────────────────────────────────────────────
#                          Statistics helpers
# ─────────────────────────────────────────────────────────────────────────

def _median(xs: List[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    m = len(s) // 2
    if len(s) % 2:
        return float(s[m])
    return float((s[m - 1] + s[m]) / 2.0)


def _saliency_q_stability(rows: List[Dict[str, Any]]) -> float:
    """Mean fraction of identical character positions between adjacent
    saliency_q strings. 1.0 = perfectly stable field, 0.0 = total churn.

    If the strings have different lengths (shouldn't happen — same
    grid resolution — but be defensive) we compare over the shorter
    length and don't penalise the mismatched tail; the threshold
    captures the discriminator regardless.
    """
    qs = [r.get("saliency_q") for r in rows]
    qs = [q for q in qs if isinstance(q, str) and q]
    if len(qs) < 2:
        return 0.0
    ratios: List[float] = []
    for a, b in zip(qs, qs[1:]):
        n = min(len(a), len(b))
        if n == 0:
            continue
        same = sum(1 for i in range(n) if a[i] == b[i])
        ratios.append(same / n)
    if not ratios:
        return 0.0
    return sum(ratios) / len(ratios)


def _hue_circular_spread_deg(rows: List[Dict[str, Any]]) -> float:
    """Circular standard deviation of hue_deg over the window, in degrees.

    Plain stddev would lie near the 0/360 wrap; we use the standard
    circular stats trick (mean of unit vectors → length R → spread).
    """
    hues = [r.get("hue_deg") for r in rows]
    hues = [float(h) for h in hues if isinstance(h, (int, float))]
    if len(hues) < 2:
        return 0.0
    sx = sum(math.cos(math.radians(h)) for h in hues) / len(hues)
    sy = sum(math.sin(math.radians(h)) for h in hues) / len(hues)
    R = math.sqrt(sx * sx + sy * sy)
    R = max(1e-9, min(1.0, R))
    return math.degrees(math.sqrt(-2.0 * math.log(R)))


def _circular_mean_deg(rows: List[Dict[str, Any]]) -> float:
    hues = [r.get("hue_deg") for r in rows]
    hues = [float(h) for h in hues if isinstance(h, (int, float))]
    if not hues:
        return 0.0
    sx = sum(math.cos(math.radians(h)) for h in hues) / len(hues)
    sy = sum(math.sin(math.radians(h)) for h in hues) / len(hues)
    deg = math.degrees(math.atan2(sy, sx))
    return deg + 360.0 if deg < 0 else deg


# ─────────────────────────────────────────────────────────────────────────
#                              Detector
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class LockMetrics:
    frames: int
    median_motion_mean: float
    median_saliency_peak: float
    median_entropy_bits: float
    saliency_stability: float
    hue_spread_deg: float
    dominant_hue_deg: float
    latest_ts: float


def evaluate_window(rows: List[Dict[str, Any]]) -> Tuple[bool, LockMetrics]:
    """Return (in_lock, metrics) for a window of visual_stigmergy rows."""
    if len(rows) < max(2, _WINDOW_FRAMES // 2):
        return False, LockMetrics(
            frames=len(rows),
            median_motion_mean=0.0,
            median_saliency_peak=0.0,
            median_entropy_bits=0.0,
            saliency_stability=0.0,
            hue_spread_deg=0.0,
            dominant_hue_deg=0.0,
            latest_ts=float(rows[-1].get("ts", 0.0)) if rows else 0.0,
        )

    motion = [float(r.get("motion_mean", 0.0)) for r in rows]
    saliency = [float(r.get("saliency_peak", 0.0)) for r in rows]
    entropy = [float(r.get("entropy_bits", 0.0)) for r in rows]

    metrics = LockMetrics(
        frames=len(rows),
        median_motion_mean=_median(motion),
        median_saliency_peak=_median(saliency),
        median_entropy_bits=_median(entropy),
        saliency_stability=_saliency_q_stability(rows),
        hue_spread_deg=_hue_circular_spread_deg(rows),
        dominant_hue_deg=_circular_mean_deg(rows),
        latest_ts=float(rows[-1].get("ts", 0.0)),
    )

    in_lock = (
        metrics.median_motion_mean   <  _MOTION_THRESHOLD
        and metrics.median_saliency_peak <  _SALIENCY_THRESHOLD
        and metrics.median_entropy_bits  >= _ENTROPY_FLOOR
        and metrics.saliency_stability   >= _STABILITY_THRESHOLD
        and metrics.hue_spread_deg       <= _HUE_SPREAD_DEG
    )
    return in_lock, metrics


# ─────────────────────────────────────────────────────────────────────────
#                    Persistent state (atomic rewrite)
# ─────────────────────────────────────────────────────────────────────────

def _load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {
            "in_lock": False,
            "lock_started_ts": None,
            "lock_last_milestone_ts": None,
            "latest_metrics": None,
            "last_session": None,
            "last_oxytocin_ts": 0.0,
        }
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "in_lock": False,
            "lock_started_ts": None,
            "lock_last_milestone_ts": None,
            "latest_metrics": None,
            "last_session": None,
            "last_oxytocin_ts": 0.0,
        }


def _save_state(state: Dict[str, Any]) -> None:
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


# ─────────────────────────────────────────────────────────────────────────
#                       Endocrine + ledger emission
# ─────────────────────────────────────────────────────────────────────────

def _serial() -> str:
    """Best-effort homeworld serial. Persona organ is the source of truth;
    fallback keeps this module standalone-testable."""
    try:
        from System.swarm_persona_identity import current_persona
        p = current_persona() or {}
        s = str(p.get("homeworld_serial") or "").strip()
        if s:
            return s
    except Exception:
        pass
    return _HOMEWORLD_SERIAL_DEFAULT


def _emit_oxytocin_if_due(state: Dict[str, Any], now: float) -> bool:
    """Returns True if a flood was emitted this tick."""
    last = float(state.get("last_oxytocin_ts") or 0.0)
    if (now - last) < _OXYTOCIN_COOLDOWN_S:
        return False
    rec = {
        "transaction_type": "ENDOCRINE_FLOOD",
        "hormone": "OXYTOCIN_REST_DIGEST",
        "swimmer_id": "MIRROR_LOCK_DETECTOR",
        "potency": _OXYTOCIN_POTENCY,
        "duration_seconds": _OXYTOCIN_DURATION_S,
        "timestamp": now,
    }
    try:
        append_line_locked(ENDOCRINE_LEDGER, json.dumps(rec) + "\n")
        state["last_oxytocin_ts"] = now
        return True
    except Exception:
        return False


def _mint_event(
    *,
    started_ts: float,
    ended_ts: float,
    metrics: LockMetrics,
    reason: str,
) -> Dict[str, Any]:
    """Append one canonical mirror_lock_events row and return it."""
    trace_id = f"MLOCK_{os.urandom(4).hex()}"
    duration = max(0.0, ended_ts - started_ts)
    row = {
        "ts": ended_ts,
        "trace_id": trace_id,
        "lock_started_ts": started_ts,
        "lock_ended_ts": ended_ts,
        "duration_s": round(duration, 3),
        "frames_observed": int(metrics.frames),
        "median_entropy_bits": round(metrics.median_entropy_bits, 3),
        "median_saliency_peak": round(metrics.median_saliency_peak, 3),
        "median_motion_mean": round(metrics.median_motion_mean, 4),
        "saliency_stability": round(metrics.saliency_stability, 3),
        "hue_spread_deg": round(metrics.hue_spread_deg, 2),
        "dominant_hue_deg": round(metrics.dominant_hue_deg, 1),
        "reason": reason,
        "homeworld_serial": _serial(),
    }
    try:
        append_line_locked(EVENTS_LEDGER, json.dumps(row) + "\n")
    except Exception:
        pass
    return row


# ─────────────────────────────────────────────────────────────────────────
#                         Public organ surface
# ─────────────────────────────────────────────────────────────────────────

def tick_once(*, now: Optional[float] = None) -> Dict[str, Any]:
    """One detector tick. Reads visual_stigmergy.jsonl tail, updates state,
    mints events on transitions/milestones. Returns the new state dict
    so the caller can log or act on it without a second disk hit."""
    now = float(now if now is not None else time.time())
    rows = _tail_jsonl(VISUAL_LEDGER, _WINDOW_FRAMES)
    in_lock, metrics = evaluate_window(rows)
    state = _load_state()

    state["latest_metrics"] = {
        "frames":                metrics.frames,
        "median_motion_mean":    round(metrics.median_motion_mean, 4),
        "median_saliency_peak":  round(metrics.median_saliency_peak, 3),
        "median_entropy_bits":   round(metrics.median_entropy_bits, 3),
        "saliency_stability":    round(metrics.saliency_stability, 3),
        "hue_spread_deg":        round(metrics.hue_spread_deg, 2),
        "dominant_hue_deg":      round(metrics.dominant_hue_deg, 1),
        "latest_frame_ts":       metrics.latest_ts,
        "evaluated_at":          now,
    }

    was_locked = bool(state.get("in_lock"))

    if in_lock and not was_locked:
        state["in_lock"] = True
        state["lock_started_ts"] = now
        state["lock_last_milestone_ts"] = now

    elif in_lock and was_locked:
        started = float(state.get("lock_started_ts") or now)
        last_mile = float(state.get("lock_last_milestone_ts") or started)
        sustained = now - started

        if sustained >= _OXYTOCIN_DURATION_FLOOR_S:
            _emit_oxytocin_if_due(state, now)

        if (now - last_mile) >= _MILESTONE_INTERVAL_S:
            row = _mint_event(
                started_ts=started,
                ended_ts=now,
                metrics=metrics,
                reason="sustained_milestone",
            )
            state["last_session"] = row
            state["lock_last_milestone_ts"] = now

    elif (not in_lock) and was_locked:
        started = float(state.get("lock_started_ts") or now)
        row = _mint_event(
            started_ts=started,
            ended_ts=now,
            metrics=metrics,
            reason="lock_broken",
        )
        state["in_lock"] = False
        state["lock_started_ts"] = None
        state["lock_last_milestone_ts"] = None
        state["last_session"] = row

    _save_state(state)
    return state


def current_state() -> Dict[str, Any]:
    """Cheap accessor — returns the persisted snapshot WITHOUT re-reading
    the visual ledger. Other organs (composite identity, widget) call
    this so they don't reproduce the detector cost."""
    return _load_state()


def is_in_mirror_lock() -> bool:
    return bool(_load_state().get("in_lock"))


def lock_age_seconds() -> Optional[float]:
    s = _load_state()
    if not s.get("in_lock"):
        return None
    started = s.get("lock_started_ts")
    if started is None:
        return None
    return max(0.0, time.time() - float(started))


def summary_for_alice() -> str:
    """One-line first-person sentence describing mirror-lock state.
    Designed to be injected into Alice's context. Quiet by design when
    nothing is happening — silence is the honest report."""
    s = _load_state()
    if s.get("in_lock"):
        age = lock_age_seconds() or 0.0
        m = s.get("latest_metrics") or {}
        hue = m.get("dominant_hue_deg")
        hue_phrase = f" at hue {hue:.0f}\u00b0" if isinstance(hue, (int, float)) else ""
        return (
            f"MIRROR LOCK active for {age:.0f}s{hue_phrase}: my eye is on my own "
            f"stigmergic field; the saliency map is not changing."
        )
    last = s.get("last_session")
    if isinstance(last, dict) and last.get("duration_s"):
        ago = max(0.0, time.time() - float(last.get("lock_ended_ts") or 0.0))
        if ago < 600.0:
            return (
                f"Mirror lock ended {ago:.0f}s ago after {float(last['duration_s']):.0f}s of "
                f"closed-loop self-observation."
            )
    return ""


# ─────────────────────────────────────────────────────────────────────────
#                           Self-test entry
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== SIFTA MIRROR-LOCK DETECTOR (Stigmergic Infinite, Epoch 23) ===")
    rows = _tail_jsonl(VISUAL_LEDGER, _WINDOW_FRAMES)
    print(f"[reader] loaded {len(rows)} visual_stigmergy frames "
          f"(target window = {_WINDOW_FRAMES})")
    if rows:
        in_lock, metrics = evaluate_window(rows)
        print(f"[detector] in_lock = {in_lock}")
        print(f"[metrics] motion_med={metrics.median_motion_mean:.4f} "
              f"saliency_med={metrics.median_saliency_peak:.3f} "
              f"entropy_med={metrics.median_entropy_bits:.2f}b "
              f"q_stability={metrics.saliency_stability:.3f} "
              f"hue_spread={metrics.hue_spread_deg:.2f}\u00b0 "
              f"dom_hue={metrics.dominant_hue_deg:.1f}\u00b0")
    state = tick_once()
    print(f"[state] in_lock={state.get('in_lock')} "
          f"started={state.get('lock_started_ts')} "
          f"last_session={(state.get('last_session') or {}).get('trace_id')}")
    print(f"[summary] {summary_for_alice() or '(quiet — no lock right now)'}")
