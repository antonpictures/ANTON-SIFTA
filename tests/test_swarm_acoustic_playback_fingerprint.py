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
    assert d.get("formula_revision") == "109b"
    assert "hnr_proxy" in d and "am_depth" in d
    assert len(apf.BIOACOUSTIC_STIGMERGY_ANCHORS) >= 2
    assert len(apf.LITERATURE_CITES) >= 2


def test_recent_tail_media_context(tmp_path) -> None:
    from System.swarm_acoustic_playback_fingerprint import append_acoustic_fingerprint_ledger

    for _ in range(10):
        append_acoustic_fingerprint_ledger(
            {
                "tick_id": "t",
                "sample_rate": 16000,
                "truth_label": "SYNTHETIC_BUFFER",
                "playback_fingerprint": {
                    "truth_label": apf.TRUTH_LABEL,
                    "formula_revision": "109b",
                    "channel_cue": "farfield_replay_likely",
                    "farfield_replay_likelihood": 0.9,
                    "nearfield_voice_likelihood": 0.1,
                    "crest_factor": 2.0,
                    "spectral_flatness": 0.8,
                    "mfcc_coeff_std": 0.01,
                    "hnr_proxy": 0.1,
                    "am_depth": 0.05,
                },
            },
            state_dir=tmp_path,
        )
    assert apf.recent_tail_is_media_playback_context(state_dir=tmp_path, n=12, media_fraction=0.55)
