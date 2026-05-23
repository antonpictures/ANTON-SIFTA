"""Tests: stigmergic audiogram — RMS rises with bounded reward (honest loudness)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from System import swarm_stigmergic_audiogram as aud
from System.swarm_visual_phenotype_gl import UniformFrame, clamp_uniforms


def test_uniforms_to_tone_params_monotonic_in_drive_and_reward() -> None:
    low = clamp_uniforms({"u_stigmergic_drive": 0.1, "u_reward": 0.1, "u_metabolic_scope": 0.2})
    high = clamp_uniforms({"u_stigmergic_drive": 0.9, "u_reward": 0.9, "u_metabolic_scope": 0.8})
    f_low, a_low = aud.uniforms_to_tone_params(low)
    f_high, a_high = aud.uniforms_to_tone_params(high)
    assert f_high >= f_low
    assert a_high > a_low


def test_high_reward_higher_rms_than_low() -> None:
    low_u = clamp_uniforms({"u_reward": 0.05, "u_stigmergic_drive": 0.1})
    high_u = clamp_uniforms({"u_reward": 0.95, "u_stigmergic_drive": 0.5})
    a = aud.synthesize_mono_pcm(low_u, duration_s=0.08, phase0=0.1)
    b = aud.synthesize_mono_pcm(high_u, duration_s=0.08, phase0=0.1)
    assert aud.pcm_rms(b) > aud.pcm_rms(a)


def test_phenotype_frame_to_pcm_matches_synth() -> None:
    u = clamp_uniforms({"u_reward": 0.4, "u_stigmergic_drive": 0.3})
    frame = UniformFrame(
        uniforms=u,
        source_path="/tmp",
        tick_id="t1",
        receipt_backed=True,
        row_ts=1.0,
        pulled_ts=2.0,
    )
    p1 = aud.phenotype_frame_to_pcm(frame, phase0=0.0)
    p2 = aud.synthesize_mono_pcm(u, phase0=0.0)
    np.testing.assert_array_almost_equal(p1, p2)


def test_audiogram_proof_row_keys(tmp_path: Path) -> None:
    row = aud.audiogram_proof_row({"u_reward": 0.7, "u_stigmergic_drive": 0.6})
    assert row["truth_label"] == aud.TRUTH_LABEL
    assert "rms" in row and row["rms"] > 0
    assert 55.0 <= row["freq_hz"] <= 880.0


def test_ledger_tail_pcm_reads_last_line(tmp_path: Path) -> None:
    ledger = tmp_path / "visual_phenotype_uniforms.jsonl"
    row = {
        "tick_id": "abc",
        "receipt_backed": True,
        "ts": 123.0,
        "u_reward": 0.85,
        "u_stigmergic_drive": 0.7,
    }
    ledger.write_text(json.dumps({"u_reward": 0.1}) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
    pcm, frame = aud.ledger_tail_pcm(ledger, duration_s=0.06, phase0=0.0)
    assert frame.tick_id == "abc"
    assert pcm.dtype == np.float32
    assert aud.pcm_rms(pcm) > 0.01


def test_write_wav_mono16_roundtrip_rms(tmp_path: Path) -> None:
    u = clamp_uniforms({"u_reward": 0.5, "u_stigmergic_drive": 0.4})
    pcm = aud.synthesize_mono_pcm(u, sample_rate=8000, duration_s=0.04)
    path = tmp_path / "proof.wav"
    aud.write_wav_mono16(path, pcm, 8000)
    assert path.stat().st_size > 44


def test_frequency_clamped() -> None:
    u = clamp_uniforms({"u_stigmergic_drive": 1.0, "u_metabolic_scope": 2.0, "u_reward": 0.0})
    f, _ = aud.uniforms_to_tone_params(u)
    assert 55.0 <= f <= 880.0
