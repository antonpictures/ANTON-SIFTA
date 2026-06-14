from __future__ import annotations


def test_circadian_detect_state_uses_relative_owner_horizons(monkeypatch):
    import Applications.circadian_rhythm as circadian

    monkeypatch.setattr(
        circadian,
        "_relative_presence_horizons",
        lambda: {"active_s": 4.0, "sleep_s": 12.0},
    )

    assert circadian.detect_state(3.0) == "ACTIVE"
    assert circadian.detect_state(8.0) == "AFK"
    assert circadian.detect_state(13.0) == "SLEEPING"


def test_circadian_refuses_false_sleep_without_relative_clock(monkeypatch):
    import Applications.circadian_rhythm as circadian

    monkeypatch.setattr(circadian, "_relative_presence_horizons", lambda: None)

    assert circadian.detect_state(0.0) == "ACTIVE"
    assert circadian.detect_state(999999.0) == "AFK"
