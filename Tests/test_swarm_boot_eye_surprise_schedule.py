"""P0 eye schedule law — pure math smoke (no webcam / no cv2).

Validates the exponential attention curve used in swarm_boot._heartbeat
when SIFTA_EYE_DELTA_ENABLE=1.
"""

from __future__ import annotations

import math


def schedule_period_s(
    attention: float,
    *,
    fast_ms: float = 80.0,
    slow_ms: float = 800.0,
    k: float = 8.0,
) -> float:
    min_p = fast_ms / 1000.0
    max_p = slow_ms / 1000.0
    attention = max(0.0, float(attention))
    period = min_p + (max_p - min_p) * math.exp(-k * attention)
    return float(max(min_p, min(max_p, period)))


def test_schedule_monotone_in_attention() -> None:
    a1 = schedule_period_s(0.0)
    a2 = schedule_period_s(0.5)
    assert a1 > a2


def test_schedule_clips_to_fast_cap() -> None:
    p = schedule_period_s(2.0)
    assert abs(p - 0.08) < 0.005  # 80 ms


def test_schedule_clips_to_slow_floor_at_zero_attention() -> None:
    p = schedule_period_s(0.0)
    assert abs(p - 0.8) < 0.005  # 800 ms
