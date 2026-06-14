"""CUR-F7.5 — stigmergic diffusion policy unit tests."""
from __future__ import annotations

import os
from unittest import mock

import pytest

from System.swarm_diffusion_stigmergic_policy import (
    ALG_CONFIDENCE,
    ALG_ENTROPY,
    StigmergicDiffusionState,
    active_policy,
    coherence_score,
    is_stigmergic_enabled,
)


def test_confidence_policy_default():
    with mock.patch.dict(os.environ, {}, clear=True):
        os.environ.pop("SIFTA_DIFFUSION_POLICY", None)
        assert active_policy() == "confidence"
        assert not is_stigmergic_enabled()


def test_stigmergic_policy_env():
    with mock.patch.dict(os.environ, {"SIFTA_DIFFUSION_POLICY": "stigmergic"}):
        assert is_stigmergic_enabled()


def test_tune_confidence_uses_algorithm_4():
    st = StigmergicDiffusionState()
    with mock.patch.dict(os.environ, {"SIFTA_DIFFUSION_POLICY": "confidence"}):
        t = st.tune(base_steps=64, block_length=32, canvas_ub=128, prompt_id="p0")
    assert t.algorithm == ALG_CONFIDENCE
    assert t.steps == 64


def test_tune_stigmergic_can_diverge(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_DIFFUSION_POLICY", "stigmergic")
    st = StigmergicDiffusionState()
    for _ in range(5):
        st.stig_field.deposit(3, 0, amount=5.0)
    t = st.tune(base_steps=64, block_length=32, canvas_ub=128, prompt_id="p0")
    assert t.policy == "stigmergic"
    assert t.algorithm in (ALG_CONFIDENCE, ALG_ENTROPY, 2)


def test_no_double_spend_detects_anchor_flip():
    st = StigmergicDiffusionState()
    st.locks["confidence:p0"] = "abc"
    rec = st.record_generation(
        prompt_id="confidence:p0",
        repeat_idx=1,
        output="Totally different opening that breaks the anchor completely.",
        previous_output="Alice is the protagonist of the M5.",
    )
    assert rec["no_double_spend_ok"] is False


def test_coherence_score_nonempty():
    assert coherence_score("Alice is alive on the M5.") > 0.5
    assert coherence_score("") == 0.0


def test_build_cli_includes_algorithm_flag():
    from pathlib import Path
    from System import swarm_diffusion_cortex as sdc

    cmd = sdc.build_cli_command(
        Path("/tmp/x.gguf"),
        "hello",
        {"schedule": "block", "block_length": 32},
    )
    assert "--diffusion-algorithm" in cmd