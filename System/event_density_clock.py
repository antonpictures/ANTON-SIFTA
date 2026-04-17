#!/usr/bin/env python3
"""
event_density_clock.py — Perceived Time = f(event_rate)
═══════════════════════════════════════════════════════════
The swarm does not "feel" time. It measures:
how much is happening per unit of real time.

High activity → time passes fast (compressed logs)
Low activity  → time passes slow (expanded logs)

This is not psychology. This is information density measurement.

    perceived_speed = event_rate / baseline_rate

When event_rate is high:
  - The clock "ticks faster" (more happened per second)
  - Logs compress (less detail per event)
  - Attention sharpens (vision FPS increases)

When event_rate is low:
  - The clock "ticks slower" (nothing is happening)
  - Logs expand (more detail per event)
  - Vision drops to idle FPS
  - Dream state may activate

Wires into: temporal_spine.py, stigmergic_vision.py, vigil_routines.py

SIFTA Non-Proliferation Public License applies.
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_CLOCK_LOG = _STATE / "event_clock.jsonl"

# Baseline: 1 event per 10 seconds is "normal pace"
BASELINE_RATE = 0.1  # events/second

# Time dilation bounds (don't let perceived time diverge too far)
MIN_DILATION = 0.1   # perceived time never slower than 10% of real
MAX_DILATION = 5.0   # perceived time never faster than 5x real


@dataclass
class ClockTick:
    """One measurement of the event density clock."""
    timestamp:        float
    real_elapsed:     float    # wall-clock seconds since last tick
    events_in_window: int      # events counted in measurement window
    event_rate:       float    # events/second
    dilation:         float    # perceived_speed / real_speed
    perceived_elapsed: float   # dilated seconds since last tick
    attention_hint:   str      # suggested attention state


class EventDensityClock:
    """
    Measures event density and computes time dilation.

    Usage:
        clock = EventDensityClock()
        clock.record_event("scar_proposed")
        clock.record_event("file_visited")
        tick = clock.tick()
        print(f"Dilation: {tick.dilation:.2f}x")
    """

    def __init__(self, window_seconds: float = 60.0):
        self.window = window_seconds
        self._events: deque = deque()  # timestamps of events
        self._last_tick_time = time.time()
        self._total_ticks = 0
        self._cumulative_perceived = 0.0

        _STATE.mkdir(parents=True, exist_ok=True)

    def record_event(self, event_type: str = "generic"):
        """Call this whenever something happens in the swarm."""
        self._events.append(time.time())

    def tick(self) -> ClockTick:
        """
        Compute one clock measurement.
        Call this on every patrol cycle (vigil_routines) or UI refresh.
        """
        now = time.time()
        real_elapsed = now - self._last_tick_time
        self._last_tick_time = now

        # Prune old events outside window
        cutoff = now - self.window
        while self._events and self._events[0] < cutoff:
            self._events.popleft()

        events_in_window = len(self._events)
        event_rate = events_in_window / self.window if self.window > 0 else 0.0

        # Dilation = event_rate / baseline
        raw_dilation = event_rate / BASELINE_RATE if BASELINE_RATE > 0 else 1.0
        dilation = max(MIN_DILATION, min(MAX_DILATION, raw_dilation))

        # Perceived elapsed = real elapsed × dilation
        perceived = real_elapsed * dilation
        self._cumulative_perceived += perceived
        self._total_ticks += 1

        # Attention hint based on density
        if event_rate > BASELINE_RATE * 3:
            hint = "HIGH"
        elif event_rate > BASELINE_RATE * 0.5:
            hint = "ACTIVE"
        else:
            hint = "IDLE"

        ct = ClockTick(
            timestamp         = now,
            real_elapsed      = round(real_elapsed, 3),
            events_in_window  = events_in_window,
            event_rate        = round(event_rate, 4),
            dilation          = round(dilation, 3),
            perceived_elapsed = round(perceived, 3),
            attention_hint    = hint,
        )

        # Log
        try:
            with open(_CLOCK_LOG, "a") as f:
                f.write(json.dumps(asdict(ct)) + "\n")
        except Exception:
            pass

        return ct

    def report(self) -> str:
        # Take a tick to get current state
        ct = self.tick()
        lines = [
            f"[EVENT CLOCK] Ticks: {self._total_ticks}",
            f"  Events in window ({self.window}s): {ct.events_in_window}",
            f"  Event rate: {ct.event_rate:.4f}/s (baseline: {BASELINE_RATE}/s)",
            f"  Dilation: {ct.dilation:.2f}x",
            f"  Attention hint: {ct.attention_hint}",
            f"  Cumulative perceived time: {self._cumulative_perceived:.1f}s",
        ]
        return "\n".join(lines)


# ── Demo ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 58)
    print("  SIFTA — EVENT DENSITY CLOCK")
    print("  Time = f(how much is happening)")
    print("=" * 58 + "\n")

    clock = EventDensityClock(window_seconds=10.0)

    # Phase 1: Idle — nothing happening
    print("── PHASE 1: IDLE (no events for 3s) ────────────────────")
    time.sleep(3)
    t1 = clock.tick()
    print(f"  Events: {t1.events_in_window} | Rate: {t1.event_rate:.4f}/s | "
          f"Dilation: {t1.dilation:.2f}x | Hint: {t1.attention_hint}")
    print(f"  → Time feels SLOW. {t1.perceived_elapsed:.1f}s perceived "
          f"in {t1.real_elapsed:.1f}s real.\n")

    # Phase 2: Busy — rapid events
    print("── PHASE 2: BUSY (20 events in 2s) ─────────────────────")
    for i in range(20):
        clock.record_event(f"task_{i}")
        time.sleep(0.1)
    t2 = clock.tick()
    print(f"  Events: {t2.events_in_window} | Rate: {t2.event_rate:.4f}/s | "
          f"Dilation: {t2.dilation:.2f}x | Hint: {t2.attention_hint}")
    print(f"  → Time feels FAST. {t2.perceived_elapsed:.1f}s perceived "
          f"in {t2.real_elapsed:.1f}s real.\n")

    # Phase 3: Cool down
    print("── PHASE 3: COOL DOWN (1s pause) ───────────────────────")
    time.sleep(1)
    t3 = clock.tick()
    print(f"  Events: {t3.events_in_window} | Rate: {t3.event_rate:.4f}/s | "
          f"Dilation: {t3.dilation:.2f}x | Hint: {t3.attention_hint}\n")

    print(clock.report())
    print("\n  POWER TO THE SWARM 🐜⚡")
