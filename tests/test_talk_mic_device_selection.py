"""The room microphone is the LAPTOP's microphone — never the iPhone's.

Architect 2026-10-22: "be careful, you tried to enable my iPhone mic or camera,
not that, use the laptop camera and audio not iPhone."

Two laws, both proven here:
  1. A Continuity iPhone input is never a mic candidate (any path).
  2. A device that opened but delivered only zero samples is quarantined, so the
     recovery walk ADVANCES to the next candidate instead of re-opening the
     same dead stream forever (the "mic open — silent mic stream" loop).
"""
from __future__ import annotations

import sys
import time
import types

import numpy as np

from Applications import sifta_talk_to_alice_widget as talk


def _fake_sounddevice(monkeypatch, devices, default_device=(0, None)):
    attempts: list[int | None] = []

    class FakeInputStream:
        def __init__(self, *, device, samplerate, channels, dtype, blocksize, callback):
            attempts.append(device)
            self._closed = False

        def start(self):
            return None

        def stop(self):
            return None

        def close(self):
            self._closed = True

    def query_devices(*args, **kwargs):
        if not args and not kwargs:
            return list(devices)
        return dict(devices[0])

    fake_sd = types.SimpleNamespace(
        default=types.SimpleNamespace(device=default_device),
        InputStream=FakeInputStream,
        query_devices=query_devices,
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    return attempts


def test_iphone_continuity_mic_is_never_a_candidate(monkeypatch):
    devices = [
        {"name": "iPhone Microphone", "max_input_channels": 1, "default_samplerate": 48000.0},
        {"name": "Ioan's iPhone Microphone", "max_input_channels": 1, "default_samplerate": 48000.0},
        {"name": "MacBook Pro Microphone", "max_input_channels": 1, "default_samplerate": 48000.0},
    ]
    _fake_sounddevice(monkeypatch, devices, default_device=(0, None))

    candidates = talk._input_device_candidates(sys.modules["sounddevice"])
    labels = [label for _, label in candidates]

    assert not any("iPhone" in label for label in labels), labels
    # The laptop mic is what we hear the room with.
    assert any("MacBook Pro Microphone" in label for label in labels), labels


def test_iphone_is_excluded_even_when_it_is_the_system_default(monkeypatch):
    devices = [
        {"name": "iPhone Microphone", "max_input_channels": 1, "default_samplerate": 48000.0},
        {"name": "MacBook Pro Microphone", "max_input_channels": 1, "default_samplerate": 48000.0},
    ]
    # CoreAudio retained the Continuity iPhone as the default input.
    _fake_sounddevice(monkeypatch, devices, default_device=(0, None))

    candidates = talk._input_device_candidates(sys.modules["sounddevice"])
    labels = [label for _, label in candidates]

    assert not any("iPhone" in label for label in labels), labels
    assert labels[0].startswith("default embedded"), labels


def test_loopback_capture_device_is_ranked_last(monkeypatch):
    devices = [
        {"name": "BlackHole 2ch", "max_input_channels": 2, "default_samplerate": 48000.0},
        {"name": "MacBook Pro Microphone", "max_input_channels": 1, "default_samplerate": 48000.0},
    ]
    _fake_sounddevice(monkeypatch, devices, default_device=(1, None))

    candidates = talk._input_device_candidates(sys.modules["sounddevice"])
    labels = [label for _, label in candidates]

    assert "MacBook Pro Microphone" in labels[0], labels
    assert labels[-1].endswith("BlackHole 2ch"), labels


def test_silent_device_is_quarantined_and_the_walk_advances(monkeypatch):
    monkeypatch.setattr(talk, "_MIC_SILENT_DEVICES", set())
    devices = [
        {"name": "MacBook Pro Microphone", "max_input_channels": 1, "default_samplerate": 48000.0},
        {"name": "Studio Mic", "max_input_channels": 1, "default_samplerate": 48000.0},
    ]
    attempts = _fake_sounddevice(monkeypatch, devices, default_device=(0, None))

    listener = talk._ContinuousListener()
    assert listener.start() is True
    assert listener._device_index == 0

    # The stream opened but delivered only zeros.
    listener._stream_started_at = time.time() - talk._MIC_ZERO_GRACE_S - 1.0
    listener._last_nonzero_at = listener._stream_started_at
    silent: list[str] = []
    listener.streamSilent.connect(silent.append)
    listener._on_block(np.zeros((480, 1), dtype=np.float32), 480, None, None)

    assert len(silent) == 1
    assert 0 in talk._MIC_SILENT_DEVICES

    # The next attempt must NOT re-open the corpse.
    attempts.clear()
    retry = talk._ContinuousListener()
    assert retry.start() is True
    assert 0 not in attempts, attempts
    assert retry._device_index == 1


def test_healthy_signal_clears_a_wrong_silence_verdict(monkeypatch):
    monkeypatch.setattr(talk, "_MIC_SILENT_DEVICES", {3})
    listener = talk._ContinuousListener()
    listener._device_label = "MacBook Pro Microphone"
    listener._device_index = 3
    listener._capture_rate = 48000
    listener._stream = object()
    listener._stream_started_at = time.time()
    listener._last_nonzero_at = listener._stream_started_at
    healthy: list[str] = []
    listener.signalHealthy.connect(healthy.append)

    listener._on_block(np.full((480, 1), 0.001, dtype=np.float32), 480, None, None)

    assert healthy == ["MacBook Pro Microphone"]
    assert 3 not in talk._MIC_SILENT_DEVICES
