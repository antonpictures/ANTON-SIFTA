from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np

from Applications import sifta_talk_to_alice_widget as talk_module
from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget


def test_busy_utterance_is_queued_instead_of_dropped():
    audio = np.ones(16000, dtype=np.float32) * 0.05
    statuses: list[str] = []
    fake = SimpleNamespace(
        _busy=True,
        _deferred_utterance_audio=None,
        _deferred_utterance_ts=0.0,
        set_status=lambda msg: statuses.append(msg),
    )

    TalkToAliceWidget._on_utterance(fake, audio)

    assert fake._deferred_utterance_audio is not None
    assert np.allclose(fake._deferred_utterance_audio, audio)
    assert fake._deferred_utterance_ts > 0.0
    assert statuses[-1] == "Voice captured while busy; queued next."


def test_return_to_listening_drains_recent_queued_utterance():
    audio = np.ones(16000, dtype=np.float32) * 0.05
    captured: list[np.ndarray] = []
    notes: list[str] = []
    fake = SimpleNamespace(
        _busy=False,
        _deferred_utterance_audio=audio,
        _deferred_utterance_ts=time.time(),
        set_status=lambda _msg: None,
        _append_system_line=lambda msg, error=False: notes.append(msg),
        _on_utterance=lambda queued: captured.append(queued),
    )

    assert TalkToAliceWidget._process_deferred_utterance_if_any(fake) is True

    assert fake._deferred_utterance_audio is None
    assert fake._deferred_utterance_ts == 0.0
    assert len(captured) == 1
    assert np.allclose(captured[0], audio)
    assert "queued voice clip" in notes[-1]


def test_stale_queued_utterance_is_not_transcribed():
    audio = np.ones(16000, dtype=np.float32) * 0.05
    statuses: list[str] = []
    fake = SimpleNamespace(
        _busy=False,
        _deferred_utterance_audio=audio,
        _deferred_utterance_ts=time.time() - 999.0,
        set_status=lambda msg: statuses.append(msg),
        _append_system_line=lambda _msg, error=False: None,
        _on_utterance=lambda _queued: (_ for _ in ()).throw(AssertionError("stale audio processed")),
    )

    assert TalkToAliceWidget._process_deferred_utterance_if_any(fake) is False

    assert fake._deferred_utterance_audio is None
    assert statuses[-1] == "Dropped stale queued voice clip."


def test_utterance_is_discarded_during_timeout_cooldown():
    audio = np.ones(16000, dtype=np.float32) * 0.05
    statuses: list[str] = []
    fake = SimpleNamespace(
        _busy=False,
        _stt_cooldown_until=time.time() + 60.0,
        _pending_wake_audio=audio.copy(),
        _pending_wake_ts=time.time(),
        _deferred_utterance_audio=audio.copy(),
        _deferred_utterance_ts=time.time(),
        set_status=lambda msg: statuses.append(msg),
    )
    fake._stt_cooldown_remaining = lambda: TalkToAliceWidget._stt_cooldown_remaining(fake)
    fake._clear_pending_voice_audio = lambda: TalkToAliceWidget._clear_pending_voice_audio(fake)

    TalkToAliceWidget._on_utterance(fake, audio)

    assert fake._pending_wake_audio is None
    assert fake._deferred_utterance_audio is None
    assert "typed input is available" in statuses[-1]


def test_deferred_utterance_is_dropped_during_timeout_cooldown():
    audio = np.ones(16000, dtype=np.float32) * 0.05
    statuses: list[str] = []
    fake = SimpleNamespace(
        _busy=False,
        _stt_cooldown_until=time.time() + 60.0,
        _pending_wake_audio=None,
        _pending_wake_ts=0.0,
        _deferred_utterance_audio=audio,
        _deferred_utterance_ts=time.time(),
        set_status=lambda msg: statuses.append(msg),
        _append_system_line=lambda _msg, error=False: (_ for _ in ()).throw(
            AssertionError("cooldown should not add another chat error")
        ),
        _on_utterance=lambda _queued: (_ for _ in ()).throw(
            AssertionError("cooldown audio was transcribed")
        ),
    )
    fake._stt_cooldown_remaining = lambda: TalkToAliceWidget._stt_cooldown_remaining(fake)
    fake._clear_pending_voice_audio = lambda: TalkToAliceWidget._clear_pending_voice_audio(fake)

    assert TalkToAliceWidget._process_deferred_utterance_if_any(fake) is False

    assert fake._deferred_utterance_audio is None
    assert "Dropped queued voice during STT cooldown" in statuses[-1]


def test_stt_watchdog_clears_voice_backlog_and_starts_cooldown(monkeypatch):
    class Worker:
        terminated = False

        def isRunning(self):
            return True

        def requestInterruption(self):
            pass

        def quit(self):
            pass

        def wait(self, _timeout_ms):
            return True

        def terminate(self):
            self.terminated = True

    worker = Worker()
    lines: list[tuple[str, bool]] = []
    statuses: list[str] = []
    scheduled: list[tuple[int, object]] = []
    returns: list[bool] = []
    audio = np.ones(16000, dtype=np.float32) * 0.05
    fake = SimpleNamespace(
        _stt=worker,
        _busy=True,
        _pending_acoustic_fingerprint={"sha": "queued"},
        _stt_consecutive_timeouts=0,
        _stt_cooldown_until=0.0,
        _pending_wake_audio=audio.copy(),
        _pending_wake_ts=time.time(),
        _deferred_utterance_audio=audio.copy(),
        _deferred_utterance_ts=time.time(),
        _append_system_line=lambda msg, error=False: lines.append((msg, error)),
        set_status=lambda msg: statuses.append(msg),
        _return_to_listening=lambda: returns.append(True),
    )
    monkeypatch.setattr(talk_module, "_STT_TIMEOUT_COOLDOWN_S", 30.0)
    monkeypatch.setattr(
        talk_module,
        "QTimer",
        SimpleNamespace(singleShot=lambda delay, callback: scheduled.append((delay, callback))),
    )

    TalkToAliceWidget._on_stt_watchdog(fake, worker)

    assert fake._stt is None
    assert fake._busy is False
    assert fake._pending_wake_audio is None
    assert fake._deferred_utterance_audio is None
    assert fake._stt_consecutive_timeouts == 1
    assert fake._stt_cooldown_until > time.time() + 29.0
    assert lines == [
        (
            "STT timed out after 45s. I discarded queued room audio and paused "
            "voice transcription for 30s; typed input still works.",
            True,
        )
    ]
    assert statuses[-1] == "STT timed out; voice transcription is cooling down."
    assert returns == [True]
    assert scheduled[0][0] == 30050
