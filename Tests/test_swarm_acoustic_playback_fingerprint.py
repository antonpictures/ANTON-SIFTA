"""Tests for System/swarm_acoustic_playback_fingerprint.py."""

from __future__ import annotations

import numpy as np

from System import swarm_acoustic_playback_fingerprint as apf
from System import swarm_stigmergic_cochlea as cochlea


def test_fingerprint_on_tone_vs_noise() -> None:
    tone = cochlea.synthetic_tone(440.0, duration_s=0.4, amp=0.22)
    rng = np.random.default_rng(7)
    noise = rng.normal(0.0, 0.2, int(16000 * 0.4)).astype(np.float32)

    ft = cochlea.analyze_buffer(tone, truth_label=cochlea.TRUTH_SYNTHETIC)
    fn = cochlea.analyze_buffer(noise, truth_label=cochlea.TRUTH_SYNTHETIC)

    assert ft.playback_fingerprint.get("truth_label") == apf.TRUTH_LABEL
    assert fn.playback_fingerprint.get("truth_label") == apf.TRUTH_LABEL
    assert "channel_cue" in ft.playback_fingerprint
    # Broadband noise tends toward higher far-field score vs pure tone
    assert (
        fn.playback_fingerprint["farfield_replay_likelihood"]
        >= ft.playback_fingerprint["farfield_replay_likelihood"] - 0.05
    )


def test_compute_playback_fingerprint_bounded() -> None:
    buf = np.zeros(8000, dtype=np.float32)
    d = apf.compute_playback_fingerprint(buf, sample_rate=16000)
    assert d["truth_label"] == apf.TRUTH_LABEL
    assert 0.0 <= d["nearfield_voice_likelihood"] <= 1.0
    assert 0.0 <= d["farfield_replay_likelihood"] <= 1.0
