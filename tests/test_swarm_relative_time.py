"""r958 — the central felt-duration organ (Grok r960's named debt, landed)."""
from System.swarm_relative_time import (
    felt_tolerance,
    new_rhythm_state,
    observe_event,
    silence_s,
)


def test_rhythm_learning_and_tolerance():
    s = new_rhythm_state(now=1000.0)
    for i in range(1, 6):
        observe_event(s, now=1000.0 + i * 10.0)  # steady 10s rhythm
    assert 9.0 <= s["ema_gap_s"] <= 11.0
    # tolerance is a dimensionless multiple of the lane's own rhythm
    assert abs(felt_tolerance(s, 8.0, now=1050.0) - 8.0 * s["ema_gap_s"]) < 1e-6


def test_absence_does_not_poison_rhythm():
    s = new_rhythm_state(now=0.0)
    for i in range(1, 4):
        observe_event(s, now=i * 5.0)  # 5s rhythm
    ema_before = s["ema_gap_s"]
    observe_event(s, now=15.0 + 9999.0)  # one night of absence
    assert s["ema_gap_s"] == ema_before  # clipped: absence is not rhythm
    assert silence_s(s, now=15.0 + 9999.0 + 3.0) == 3.0


def test_lindy_cold_start():
    s = new_rhythm_state(now=100.0)
    # no rhythm yet: tolerance grows with the lane's own age
    assert abs(felt_tolerance(s, 8.0, lindy_fraction=0.5, now=300.0) - 100.0) < 1e-6
