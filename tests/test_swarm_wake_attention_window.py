#!/usr/bin/env python3
"""Tests for the wake attention window (stigmergic hold after Alice hears her name).

Covers the decay math, open/expire behaviour, and the media-ingress-gate
follow-up routing: a nearfield short turn during the warm window routes
direct; far-field replay and an expired window stay ambient/observed.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_wake_attention_window as win


# ── decay math ───────────────────────────────────────────────────────────
def test_strength_is_one_at_deposit():
    s = win.window_strength(100.0, last_wake_ts=100.0)
    assert abs(s - 1.0) < 1e-9


def test_strength_decays_exponentially():
    t0 = 100.0
    s = win.window_strength(t0 + win.TAU_SECONDS, last_wake_ts=t0)
    assert abs(s - math.exp(-1.0)) < 1e-9


def test_strength_zero_past_hard_ceiling():
    t0 = 100.0
    s = win.window_strength(t0 + win.MAX_WINDOW_SECONDS + 1.0, last_wake_ts=t0)
    assert s == 0.0


def test_no_deposit_means_no_strength():
    assert win.window_strength(100.0, last_wake_ts=None) == 0.0


# ── window active / expire ─────────────────────────────────────────────────
def test_window_active_right_after_wake():
    out = win.wake_window_active(100.05, last_wake_ts=100.0)
    assert out["active"] is True
    assert out["strength"] > 0.9


def test_window_expires_after_decay():
    t0 = 100.0
    # Far enough out that strength drops below the floor.
    out = win.wake_window_active(t0 + win.MAX_WINDOW_SECONDS + 0.5, last_wake_ts=t0)
    assert out["active"] is False


def test_window_inactive_with_no_wake():
    out = win.wake_window_active(100.0, last_wake_ts=None)
    assert out["active"] is False
    assert out["age_s"] is None


# ── file-backed deposit round-trip (tmp root, deterministic) ───────────────
def test_mark_and_read_roundtrip(tmp_path):
    win.mark_wake(500.0, source="wake_ear", root=tmp_path)
    out = win.wake_window_active(500.1, root=tmp_path)
    assert out["active"] is True
    win.clear_window(root=tmp_path)
    assert win.wake_window_active(500.1, root=tmp_path)["active"] is False


# ── integration with the media ingress gate ───────────────────────────────
NEARFIELD = {
    "nearfield_voice_likelihood": 0.85,
    "farfield_replay_likelihood": 0.05,
    "channel_cue": "nearfield_voice_likely",
}
FARFIELD = {
    "nearfield_voice_likelihood": 0.10,
    "farfield_replay_likelihood": 0.90,
    "channel_cue": "farfield_replay_likely",
}


def _gate():
    from System import swarm_media_ingress_gate as gate
    return gate


def test_followup_routes_direct_while_window_warm(tmp_path, monkeypatch):
    gate = _gate()
    # Pretend the window is warm by patching the gate's lookup.
    import System.swarm_wake_attention_window as w
    monkeypatch.setattr(
        w, "wake_window_active",
        lambda *a, **k: {"active": True, "strength": 0.8, "age_s": 1.0},
    )
    out = gate.classify_spoken_ingress(
        "what time is it",
        stt_conf=0.7,
        focus_context="youtube video watching",
        acoustic_fingerprint=NEARFIELD,
    )
    assert out["route"] == "direct"
    assert out["reason"] == "wake_window_followup"


def test_followup_does_not_ride_window_when_farfield(tmp_path, monkeypatch):
    gate = _gate()
    import System.swarm_wake_attention_window as w
    monkeypatch.setattr(
        w, "wake_window_active",
        lambda *a, **k: {"active": True, "strength": 0.8, "age_s": 1.0},
    )
    out = gate.classify_spoken_ingress(
        "and the universe expanded therefore the galaxies",
        stt_conf=0.7,
        focus_context="youtube video watching",
        acoustic_fingerprint=FARFIELD,
    )
    assert out["route"] != "direct" or out["reason"] != "wake_window_followup"


def test_followup_dropped_when_window_cold(monkeypatch):
    gate = _gate()
    import System.swarm_wake_attention_window as w
    monkeypatch.setattr(
        w, "wake_window_active",
        lambda *a, **k: {"active": False, "strength": 0.0, "age_s": 99.0},
    )
    out = gate.classify_spoken_ingress(
        "what time is it",
        stt_conf=0.7,
        focus_context="youtube video watching",
        acoustic_fingerprint=NEARFIELD,
    )
    assert out["reason"] != "wake_window_followup"


def test_named_wake_opens_window(tmp_path, monkeypatch):
    """A direct 'Alice ...' turn must deposit the pheromone."""
    gate = _gate()
    import System.swarm_wake_attention_window as w
    marked = {}
    monkeypatch.setattr(w, "mark_wake", lambda *a, **k: marked.setdefault("hit", True))
    out = gate.classify_spoken_ingress(
        "Alice what time is it",
        stt_conf=0.7,
        focus_context="youtube video watching",
        acoustic_fingerprint=NEARFIELD,
    )
    assert out["route"] == "direct"
    assert marked.get("hit") is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
