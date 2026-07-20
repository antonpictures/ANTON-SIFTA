from __future__ import annotations

import importlib
import time


def _fresh_guard(monkeypatch):
    mod = importlib.import_module("System.swarm_keyboard_mic_guard")
    mod = importlib.reload(mod)
    mod._LAST_KEYBOARD_TS = 0.0
    return mod


def test_keyboard_source_activity_detection():
    guard = importlib.import_module("System.swarm_keyboard_mic_guard")
    assert guard.is_keyboard_source_activity("behavior_clock:key")
    assert guard.is_keyboard_source_activity("keyboard")
    assert not guard.is_keyboard_source_activity("behavior_clock:mouse_click")


def test_thank_you_silenced_during_recent_keyboard(monkeypatch):
    guard = _fresh_guard(monkeypatch)
    guard.note_owner_keyboard_activity(1000.0)
    rule = guard.classify_keyboard_click_stt("thank you", 0.55, keyboard_recent=True)
    assert rule == "keyboard_click/stt_hallucination"


def test_named_thank_you_passes_through(monkeypatch):
    guard = _fresh_guard(monkeypatch)
    guard.note_owner_keyboard_activity(2000.0)
    rule = guard.classify_keyboard_click_stt("thank you Alice", 0.55, keyboard_recent=True)
    assert rule is None


def test_stale_keyboard_does_not_silence(monkeypatch):
    guard = _fresh_guard(monkeypatch)
    guard.note_owner_keyboard_activity(3000.0)
    rule = guard.classify_keyboard_click_stt("thank you", 0.55, keyboard_recent=False)
    assert rule is None


def test_low_conf_unaddressed_phatic_stt_silenced_without_keyboard(monkeypatch):
    guard = _fresh_guard(monkeypatch)
    rule = guard.classify_uncertain_phatic_stt("Thank you.", 0.42)
    assert rule == "stt_uncertain/phatic_no_address"


def test_low_conf_addressed_phatic_stt_passes_without_keyboard(monkeypatch):
    guard = _fresh_guard(monkeypatch)
    rule = guard.classify_uncertain_phatic_stt("Thank you Alice.", 0.42)
    assert rule is None


def test_owner_heartbeat_stamps_keyboard_guard(monkeypatch, tmp_path):
    hb = importlib.import_module("System.owner_heartbeat")
    hb = importlib.reload(hb)
    guard = importlib.import_module("System.swarm_keyboard_mic_guard")
    guard = importlib.reload(guard)
    guard._LAST_KEYBOARD_TS = 0.0
    monkeypatch.setattr(hb, "_LEDGER", tmp_path / "owner_heartbeat.jsonl")
    hb._current_last_activity_ts = 0.0
    hb._current_mode = "ACTIVE"

    now = 4000.0
    monkeypatch.setattr(hb, "_now", lambda: now)
    hb.mark_owner_activity("behavior_clock:key")

    assert guard.seconds_since_keyboard_activity(now + 0.1) < 1.0
