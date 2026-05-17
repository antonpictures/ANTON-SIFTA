from __future__ import annotations

import json
import time
from types import SimpleNamespace

from Applications import sifta_teach_ace_to_read as ace_app


class _FakeTimer:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def _poll_fake(now: float):
    timer = _FakeTimer()
    handled = []
    visuals = []
    mic_visuals = []
    fake = SimpleNamespace(
        _lesson_running=True,
        _conversation_mode=False,
        _lesson_state="LISTEN",
        _lesson_poll_timer=timer,
        _lesson_read_new_verdicts=lambda: [],
        _lesson_cue_id="cue-mat",
        _lesson_listen_started_ts=100.0,
        _lesson_listen_window_s=8.0,
        _lesson_bridge_wait_announced_cue_id="",
        _lesson_late_verdict_deadlines={},
        _lesson_handle_verdict=lambda row: handled.append(row),
        _set_processing_visual=lambda text, active: visuals.append((text, active)),
        _set_mic_visual=lambda text, active: mic_visuals.append((text, active)),
    )
    return fake, timer, handled, visuals, mic_visuals


def test_ace_waits_for_talk_stt_bridge_before_timeout(monkeypatch):
    fake, timer, handled, visuals, mic_visuals = _poll_fake(now=110.0)
    monkeypatch.setattr(ace_app.time, "time", lambda: 110.0)

    ace_app.TeachAceToReadWidget._lesson_poll_verdict(fake)

    assert not timer.stopped
    assert handled == []
    assert mic_visuals == [("Alice ear heard the turn window; waiting for STT bridge.", True)]
    assert visuals == [("I am waiting for the microphone verdict before retrying this card.", True)]


def test_ace_times_out_only_after_bridge_deadline(monkeypatch):
    fake, timer, handled, _visuals, _mic_visuals = _poll_fake(now=114.0)
    monkeypatch.setattr(ace_app.time, "time", lambda: 114.0)

    ace_app.TeachAceToReadWidget._lesson_poll_verdict(fake)

    assert timer.stopped
    assert handled
    assert handled[0]["verdict_label"] == "TIMEOUT"
    assert "no microphone verdict after 13s" in handled[0]["explanation"]
    assert fake._lesson_late_verdict_deadlines["cue-mat"] == 144.0


def test_ace_recovers_late_verdict_from_prior_timeout(monkeypatch):
    fake, timer, handled, _visuals, _mic_visuals = _poll_fake(now=116.0)
    fake._lesson_cue_id = "cue-retry"
    fake._lesson_read_new_verdicts = lambda: [
        {"cue_id": "cue-mat", "heard_text": "Matt.", "verdict_label": "CORRECT"}
    ]
    fake._lesson_late_verdict_deadlines = {"cue-mat": 140.0}
    monkeypatch.setattr(ace_app.time, "time", lambda: 116.0)

    ace_app.TeachAceToReadWidget._lesson_poll_verdict(fake)

    assert timer.stopped
    assert handled[0]["late_timeout_recovery"] is True
    assert handled[0]["heard_text"] == "Matt."
    assert fake._lesson_late_verdict_deadlines == {}


def test_ace_fresh_open_ignores_stale_app_control_rows(tmp_path, monkeypatch):
    """Old close/hold rows must not replay into a newly opened Ace window."""
    from PyQt6.QtWidgets import QApplication

    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    for name, signal_kind in (
        ("wordace_close.jsonl", "close"),
        ("wordace_hold.jsonl", "hold"),
    ):
        (state_dir / name).write_text(
            json.dumps({
                "ts": 1.0,
                "signal_kind": signal_kind,
                "heard_text": "old session command",
                "schema": "WORDACE_SIGNAL_V1",
            })
            + "\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(ace_app, "_REPO", tmp_path)
    monkeypatch.setattr(ace_app, "_publish_focus", None)
    ace_app.TeachAceToReadWidget._live_instance = None
    ace_app.TeachAceToReadWidget._initialized_instance_ids.clear()

    app = QApplication.instance() or QApplication([])
    widget = ace_app.TeachAceToReadWidget()
    try:
        widget.show()
        deadline = time.time() + 1.2
        while time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)

        assert widget.isVisible()
        assert not widget.isHidden()
        assert widget._conversation_mode is True
        assert widget._lesson_running is False
        assert widget._current_word
        assert widget._lesson_state != "CLOSE_SIGNAL"
    finally:
        widget.close()
        app.processEvents()
        ace_app.TeachAceToReadWidget._live_instance = None
        ace_app.TeachAceToReadWidget._initialized_instance_ids.clear()
