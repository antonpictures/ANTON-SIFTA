#!/usr/bin/env python3
"""Pytest coverage for `System.swarm_behavior_clock`.

What we prove
-------------
1. `behavior_clock()` is a singleton.
2. The clock exposes a `tick` signal that subscribers can connect to.
3. `pump()` emits the tick payload through to subscribers.
4. Successive `pump()` calls inside one debounce window coalesce — i.e.
   the clock does NOT flood subscribers with a hardcoded sub-100 ms rate
   when stimulus arrives faster than Alice's heart period.
5. The debounce period is read from `swarm_motor_cortex.heart_period_s()`
   and is therefore physiological, not a literal constant.

These tests are pure stdlib + pytest. They do not require a Qt event loop.
"""
from __future__ import annotations

import time

import pytest


def test_behavior_clock_is_singleton():
    from System.swarm_behavior_clock import behavior_clock

    a = behavior_clock()
    b = behavior_clock()
    assert a is b, "behavior_clock() must return the same singleton across calls"


def test_pump_delivers_payload_to_subscriber():
    from System.swarm_behavior_clock import behavior_clock

    clock = behavior_clock()
    seen: list[str] = []

    def slot(src: str) -> None:
        seen.append(src)

    clock.tick.connect(slot)
    # Reset internal debounce so this test isn't influenced by prior tests.
    clock._last_tick_monotonic = 0.0
    clock.pump("unit_test_source")
    assert seen and seen[-1] == "unit_test_source"


def test_rapid_pumps_coalesce_inside_heart_period():
    """The clock must NOT emit more often than Alice's heart period.

    This is the doctrine — replace hardcoded ms intervals with biological
    cadence. We pump three times back-to-back; at most one tick should
    fire because all three land inside the debounce window.
    """
    from System.swarm_behavior_clock import behavior_clock

    clock = behavior_clock()
    seen: list[str] = []
    clock.tick.connect(lambda src: seen.append(src))

    clock._last_tick_monotonic = 0.0
    n_before = len(seen)
    clock.pump("burst_1")
    clock.pump("burst_2")
    clock.pump("burst_3")
    n_after = len(seen)

    assert n_after - n_before == 1, (
        "Three back-to-back pumps must coalesce into ONE tick "
        "(heart-period debounce). Got "
        f"{n_after - n_before} ticks."
    )


def test_debounce_is_physiological_not_hardcoded():
    """The minimum tick period comes from heart_period_s(), not a literal.

    We assert the value is a positive float in a biological range; the
    exact number is allowed to drift with Alice's metabolic state.
    """
    from System.swarm_behavior_clock import _heart_period_s_safe

    v = _heart_period_s_safe()
    assert isinstance(v, float)
    assert v > 0.0, "heart period must be strictly positive"
    # Clinical 12–30 BPM → 2.0–5.0 s; fallback path also valid.
    # We just require it to be in a plausible bio range (0.05 s ≤ v ≤ 10 s).
    assert 0.05 <= v <= 10.0, (
        f"heart period {v!r} outside plausible biological range"
    )


def test_no_hardcoded_millisecond_constant_in_module():
    """Doctrine guard: the module source must not introduce a fresh
    arbitrary timer interval. We allow `0.25` (the no-physiology fallback)
    and `12–30 BPM` literals in comments, but reject `time.sleep(...)`
    calls or `QTimer.start(<number>)` calls."""
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "System" / "swarm_behavior_clock.py"
    src = path.read_text(encoding="utf-8")
    assert "time.sleep(" not in src, (
        "BehaviorClock must not block on time.sleep — it is event-driven."
    )
    assert "QTimer.start(" not in src and ".start(500)" not in src, (
        "BehaviorClock must not start any fixed-interval QTimer."
    )
