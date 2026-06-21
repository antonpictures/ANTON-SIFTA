from __future__ import annotations

import sys
import types

import numpy as np

from Applications import sifta_talk_to_alice_widget as talk


def test_listener_prefers_native_rate_on_macos_to_avoid_noisy_16khz_probe(monkeypatch):
    attempts: list[tuple[int | None, int, int]] = []

    class FakeInputStream:
        def __init__(self, *, device, samplerate, channels, dtype, blocksize, callback):
            attempts.append((device, int(samplerate), int(blocksize)))
            self.closed = False

        def start(self):
            return None

        def stop(self):
            return None

        def close(self):
            self.closed = True

    def query_devices(*args, **kwargs):
        info = {
            "name": "MacBook Pro Microphone",
            "max_input_channels": 1,
            "default_samplerate": 48000.0,
        }
        if not args and not kwargs:
            return [info]
        return info

    fake_sd = types.SimpleNamespace(
        default=types.SimpleNamespace(device=(0, None)),
        InputStream=FakeInputStream,
        query_devices=query_devices,
    )
    monkeypatch.setattr(talk.sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    listener = talk._ContinuousListener()
    assert listener.start() is True
    try:
        attempted_rates = [rate for _, rate, _ in attempts]
        assert attempted_rates == [48000]
        assert listener._capture_rate == 48000
    finally:
        listener.stop()


def test_listener_can_force_16khz_probe_before_native_rate(monkeypatch):
    attempts: list[int] = []

    class FakeInputStream:
        def __init__(self, *, device, samplerate, channels, dtype, blocksize, callback):
            attempts.append(int(samplerate))
            if int(samplerate) == int(talk._AUDIO_RATE):
                raise RuntimeError("16k rejected by CoreAudio")

        def start(self):
            return None

        def stop(self):
            return None

        def close(self):
            return None

    def query_devices(*args, **kwargs):
        info = {
            "name": "MacBook Pro Microphone",
            "max_input_channels": 1,
            "default_samplerate": 48000.0,
        }
        if not args and not kwargs:
            return [info]
        return info

    fake_sd = types.SimpleNamespace(
        default=types.SimpleNamespace(device=(0, None)),
        InputStream=FakeInputStream,
        query_devices=query_devices,
    )
    monkeypatch.setattr(talk.sys, "platform", "darwin")
    monkeypatch.setenv("SIFTA_MIC_TRY_16K_FIRST", "1")
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    listener = talk._ContinuousListener()
    assert listener.start() is True
    try:
        assert attempts[0] == int(talk._AUDIO_RATE)
        assert 48000 in attempts
        assert listener._capture_rate == 48000
    finally:
        listener.stop()


def test_input_device_candidates_default_embedded_macbook_first(monkeypatch):
    class FakeSd:
        default = types.SimpleNamespace(device=(8, None))

        @staticmethod
        def query_devices():
            return [
                {"name": "iPhone Microphone", "max_input_channels": 1, "default_samplerate": 48000.0},
                {"name": "MacBook Pro Microphone", "max_input_channels": 1, "default_samplerate": 48000.0},
                {"name": "DELL PROFESSIONAL SOUND BAR AE515", "max_input_channels": 2, "default_samplerate": 48000.0},
                {"name": "Unknown USB Audio Device", "max_input_channels": 2, "default_samplerate": 16000.0},
            ]

    candidates = talk._input_device_candidates(FakeSd())
    labels = [label for _, label in candidates]

    assert labels[0].startswith("default embedded 1:MacBook Pro Microphone")
    assert any("iPhone Microphone" in label for label in labels)
    assert any("DELL" in label for label in labels)
    assert labels[-1] == "input 0:iPhone Microphone"
    assert "system default" not in labels


def test_native_rate_audio_blocks_downsample_to_alice_audio_rate():
    block = np.linspace(-0.5, 0.5, 480, dtype=np.float32)

    out = talk._resample_mono_to_audio_rate(block, 48000)

    assert out.dtype == np.float32
    assert out.shape == (160,)
    assert float(np.max(out)) <= 0.5
    assert float(np.min(out)) >= -0.5
