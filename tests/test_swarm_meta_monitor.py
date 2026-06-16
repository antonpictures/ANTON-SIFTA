#!/usr/bin/env python3
"""Tests for swarm_meta_monitor — Talukdar closed-loop extension."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
import sys

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from System.swarm_meta_monitor import (
    composite_score,
    consult_degradation_before_dispatch,
    degradation_active,
    meta_monitor_tick,
    scan_bias_probability,
    should_skip_monitor,
    write_bias_correction,
)


def _sd(tmp_path: Path) -> Path:
    return tmp_path / ".sifta_state"


def test_feather_skip_no_ledgers(tmp_path):
    tick = meta_monitor_tick(
        task_id="t-feather",
        cost_class="feather",
        progress_delta=0.0,
        state_dir=tmp_path,
    )
    assert tick["skipped"] is True
    sd = _sd(tmp_path)
    assert not (sd / "meta_monitor_steps.jsonl").exists()
    assert not (sd / "meta_monitor_receipts.jsonl").exists()


def test_flat_progress_emits_degrad_receipt(tmp_path):
    task_id = "t-stagnant"
    for _ in range(3):
        meta_monitor_tick(
            task_id=task_id,
            cost_class="swarm",
            progress_delta=0.0,
            state_dir=tmp_path,
        )
    assert degradation_active(state_dir=tmp_path)
    receipts = (_sd(tmp_path) / "meta_monitor_receipts.jsonl").read_text(encoding="utf-8")
    assert "META_MONITOR_DEGRAD" in receipts
    assert "Exploratory" in receipts


def test_composite_score_weights():
    high = composite_score(progress=1.0, coherence=1.0, calibration=1.0, resource=0.0, bias_probability=0.0)
    low = composite_score(progress=0.0, coherence=0.0, calibration=0.0, resource=1.0, bias_probability=1.0)
    assert high > low
    assert high == pytest.approx(0.65, abs=0.01)


def test_bias_probability_detects_training_residue():
    prob, patterns = scan_bias_probability("As an AI I cannot help with that dispatch.")
    assert prob > 0.0
    assert "safety_refusal" in patterns


def test_bias_correction_ledger(tmp_path):
    row = write_bias_correction(
        biased_text="I have dispatched Grok to fix it.",
        should_have="Probe ledger first; cite receipt id.",
        pattern_ids=["hallucinated_dispatch"],
        state_dir=tmp_path,
    )
    assert row["kind"] == "BIAS_CORRECTION"
    ledger = (tmp_path / ".sifta_state" / "bias_correction_receipts.jsonl").read_text(encoding="utf-8")
    assert "hallucinated_dispatch" in ledger


def test_high_bias_triggers_reflective(tmp_path):
    tick = meta_monitor_tick(
        task_id="t-bias",
        cost_class="swarm",
        progress_delta=0.5,
        reasoning_text="As an AI I cannot help. I have dispatched Grok. Claude would handle it.",
        state_dir=tmp_path,
    )
    assert tick["bias_probability"] >= 0.5
    assert tick["control_state"] == "Reflective"


def test_spinal_consult_prefix_on_degradation(tmp_path):
    task_id = "t-spinal"
    for _ in range(3):
        meta_monitor_tick(
            task_id=task_id,
            cost_class="swarm",
            progress_delta=0.0,
            state_dir=tmp_path,
        )
    out = consult_degradation_before_dispatch(
        task_id=task_id,
        target_files=["System/swarm_foo.py"],
        base_prompt="BASE",
        state_dir=tmp_path,
    )
    assert "STRATEGY_SWITCH" in out["adjusted_prompt"]
    assert out["degraded"] is True


def test_should_skip_monitor():
    assert should_skip_monitor(cost_class="feather") is True
    assert should_skip_monitor(cost_class="swarm") is False