from System.swarm_stale_speech_guard import (
    is_stale,
    stale_phrase,
    wrap_value_if_stale,
)


def test_is_stale_boundaries_and_threshold_override():
    assert is_stale(None) is False
    assert is_stale(0) is False
    assert is_stale(86401) is True
    assert is_stale(11, threshold_s=10) is True
    assert is_stale(10, threshold_s=10) is False


def test_stale_phrase_uses_hour_floor():
    assert stale_phrase(0) == ""
    assert "24 hours ago" in stale_phrase(86401)


def test_wrap_value_if_stale_preserves_label_and_original_value():
    wrapped = wrap_value_if_stale("x", 0.467, 86401 * 5)

    assert "last snapshot" in wrapped
    assert "hours ago" in wrapped
    assert "0.467" in wrapped
    assert wrapped.startswith("x=<")


def test_wrap_value_if_fresh_keeps_plain_assignment():
    assert wrap_value_if_stale("x", 0.467, 10) == "x=0.467"
