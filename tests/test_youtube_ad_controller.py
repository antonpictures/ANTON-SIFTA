#!/usr/bin/env python3
"""Tests for owner-controlled YouTube ad skip/mute policy."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System.swarm_youtube_ad_controller import (
    REQUEST_BLOCKING_DEFAULT_ENABLED,
    decide_youtube_ad_action,
    record_youtube_ad_action,
)


def _state(**extra):
    base = {
        "detected": True,
        "platform": "youtube",
        "placement": "player",
        "labels": ["Sponsored"],
        "ad_text": "Sponsored",
        "skip_available": False,
        "mute_available": False,
        "video_playing": True,
        "url": "https://www.youtube.com/watch?v=abc",
        "is_current_page": True,
    }
    base.update(extra)
    return base


def test_skip_button_available_selects_skip_action():
    decision = decide_youtube_ad_action(_state(skip_available=True, mute_available=True))
    assert decision["action"] == "skip"
    assert decision["reason"] == "visible_youtube_skip_control"


def test_no_skip_but_mute_available_selects_mute_action(tmp_path):
    state = _state(skip_available=False, mute_available=True)
    decision = decide_youtube_ad_action(state)
    assert decision["action"] == "mute"
    row = record_youtube_ad_action(
        ad_state=state,
        decision=decision,
        effect={"ok": True, "reason": "muted_video_during_ad"},
        state_dir=tmp_path,
        now=1000.0,
    )
    assert row["decision"]["action"] == "mute"
    assert row["request_blocking_enabled"] is False
    assert (tmp_path / ".sifta_state" / "youtube_ad_controller.jsonl").exists()


def test_no_controls_observes_only():
    decision = decide_youtube_ad_action(_state(skip_available=False, mute_available=False))
    assert decision["action"] == "observe"
    assert decision["reason"] == "ad_detected_no_safe_control_visible"


def test_non_current_receipt_does_nothing():
    decision = decide_youtube_ad_action(_state(is_current_page=False, skip_available=True))
    assert decision["action"] == "none"
    assert decision["reason"] == "not_current_page"


def test_alice_muted_ad_restores_after_ad_clears():
    decision = decide_youtube_ad_action(_state(detected=False, was_muted_by_alice=True))
    assert decision["action"] == "restore"
    assert decision["reason"] == "normal_video_resumed_after_alice_ad_mute"


def test_request_blocking_is_dormant_by_default():
    assert REQUEST_BLOCKING_DEFAULT_ENABLED is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
