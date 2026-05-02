"""Tests for Event 95 stigmergic cochlea feature extraction."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from System import swarm_stigmergic_cochlea as cochlea


def test_tone_extracts_pitch_and_low_entropy() -> None:
    samples = cochlea.synthetic_tone(440.0, duration_s=0.35, amp=0.25)
    frame = cochlea.analyze_buffer(samples, truth_label=cochlea.TRUTH_SYNTHETIC)

    assert frame.vad is True
    assert 420.0 <= frame.f0_hz <= 460.0
    assert frame.spectral_entropy < 0.35
    assert len(frame.mfcc) == 13
    assert all(np.isfinite(frame.mfcc))


def test_noise_has_higher_entropy_than_tone() -> None:
    rng = np.random.default_rng(42)
    noise = rng.normal(0.0, 0.25, 16000).astype(np.float32)
    tone = cochlea.synthetic_tone(440.0, duration_s=1.0, amp=0.25)

    noise_frame = cochlea.analyze_buffer(noise)
    tone_frame = cochlea.analyze_buffer(tone)

    assert noise_frame.spectral_entropy > tone_frame.spectral_entropy
    assert 0.0 <= noise_frame.acoustic_stress <= 1.0
    assert noise_frame.vad is True


def test_silence_is_quiet_and_feature_bounded() -> None:
    frame = cochlea.analyze_buffer(np.zeros(4096, dtype=np.float32))

    assert frame.vad is False
    assert frame.rms == 0.0
    assert frame.f0_hz == 0.0
    assert frame.danger_hint == "ACOUSTIC_QUIET"
    assert 0.0 <= frame.acoustic_stress <= 1.0
    assert -0.2 <= frame.td_bias <= 0.2


def test_write_cochlea_frame_logs_features_only(tmp_path: Path) -> None:
    ledger = tmp_path / "stigmergic_cochlea.jsonl"
    row = cochlea.analyze_and_write(
        cochlea.synthetic_tone(330.0),
        tick_id="tick-1",
        truth_label=cochlea.TRUTH_SYNTHETIC,
        ledger_path=ledger,
    )

    assert ledger.exists()
    saved = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert saved["tick_id"] == "tick-1"
    assert saved["raw_audio_logged"] is False
    assert "buffer" not in saved
    assert "samples" not in saved
    assert saved["mfcc"] == row["mfcc"]
    assert "playback_fingerprint" in saved
    assert saved["playback_fingerprint"].get("truth_label") == "ACOUSTIC_PLAYBACK_FINGERPRINT_V1"


def test_capture_default_is_synthetic_and_ci_safe(tmp_path: Path) -> None:
    row = cochlea.capture_and_write(ledger_path=tmp_path / "cochlea.jsonl")

    assert row["truth_label"] == cochlea.TRUTH_SYNTHETIC
    assert row["source"] == "synthetic_440hz_tone"
    assert row["raw_audio_logged"] is False


def test_microphone_path_requires_prior_consent() -> None:
    from System import audio_ingress

    audio_ingress.disable_microphone()
    with pytest.raises(cochlea.MicrophoneOptInRequired):
        cochlea.capture_and_write(use_microphone=True)
