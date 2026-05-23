from __future__ import annotations

import time
from types import SimpleNamespace

import numpy as np

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
