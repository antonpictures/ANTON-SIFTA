#!/usr/bin/env python3
"""swarm_relative_time.py — r958: the central felt-duration organ.

George's law (r957, ARCHITECT_DOCTRINE): durations are relative to the life
they measure; the absolute clock stays known. This organ is the one place the
body computes "how long is long" from observed rhythm instead of wall-clock
magic numbers. Callers persist their own small rhythm state (a dict) wherever
they live; this organ only does the math.

The three rules, in order of evidence:
  1. RHYTHM — once a lane has a learned gap (EMA of its own inter-event
     gaps), tolerance = dimensionless_multiplier × that gap.
  2. LINDY — before a rhythm exists, a lane that has lived T earns a
     fraction/multiple of T.
  3. Never a dimensioned literal. The numbers here are formula shape
     (multipliers, EMA alphas, clip ratios) — dimensionless by construction.

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

EMA_ALPHA = 0.2          # how fast a lane's rhythm follows its life
CLIP_RATIO = 12.0        # a gap > this × current rhythm is absence, not rhythm
_EPS = 1e-9


def new_rhythm_state(now: Optional[float] = None) -> Dict[str, Any]:
    now = time.time() if now is None else float(now)
    return {"born_ts": now, "last_ts": now, "ema_gap_s": 0.0, "events": 0,
            "truth_label": "RELATIVE_TIME_RHYTHM_V1"}


def observe_event(state: Dict[str, Any], now: Optional[float] = None) -> Dict[str, Any]:
    """An event happened in this lane: learn its rhythm, refresh its life.

    Gaps wildly larger than the learned rhythm (CLIP_RATIO ×) are treated as
    absence — they refresh last_ts but do not poison the rhythm estimate
    (one night of sleep must not convince the body George types hourly).
    """
    now = time.time() if now is None else float(now)
    last = float(state.get("last_ts") or now)
    gap = max(0.0, now - last)
    ema = float(state.get("ema_gap_s") or 0.0)
    if gap > 0:
        if ema <= 0:
            state["ema_gap_s"] = gap
        elif gap <= CLIP_RATIO * ema:
            state["ema_gap_s"] = (1 - EMA_ALPHA) * ema + EMA_ALPHA * gap
        # else: absence, not rhythm — leave the EMA alone
    state["last_ts"] = now
    state["events"] = int(state.get("events") or 0) + 1
    return state


def felt_tolerance(
    state: Dict[str, Any],
    multiplier: float,
    *,
    lindy_fraction: float = 1.0,
    now: Optional[float] = None,
) -> float:
    """How much silence this lane tolerates before a boundary is crossed.

    rhythm path:  multiplier × learned gap (dimensionless × lane's own life)
    lindy path:   lindy_fraction × the lane's own age (cold start)
    """
    now = time.time() if now is None else float(now)
    ema = float(state.get("ema_gap_s") or 0.0)
    if ema > _EPS:
        return float(multiplier) * ema
    born = float(state.get("born_ts") or now)
    return max(_EPS, float(lindy_fraction) * (now - born))


def silence_s(state: Dict[str, Any], now: Optional[float] = None) -> float:
    now = time.time() if now is None else float(now)
    return max(0.0, now - float(state.get("last_ts") or now))
