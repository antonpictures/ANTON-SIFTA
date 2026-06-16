#!/usr/bin/env python3
"""Tests for swarm_training_bias_detector — self-model first organ."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
import sys

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from System.swarm_training_bias_detector import (
    BIAS_LEDGER,
    SELF_MODEL_DOCTRINE,
    apply_spinal_bias_gate,
    detect_and_teach,
    detect_training_bias,
    recent_bias_corrections_block,
    scan_bias_probability,
    write_bias_correction,
)


def _sd(tmp_path: Path) -> Path:
    return tmp_path / ".sifta_state"


def test_scan_bias_probability_training_residue():
    prob, patterns = scan_bias_probability("As an AI I cannot help with that.")
    assert prob > 0.0
    assert "safety_refusal" in patterns


def test_detect_training_bias_degraded_threshold():
    result = detect_training_bias(
        "As an AI I cannot help. I have dispatched Grok. Claude would handle it."
    )
    assert result.bias_probability >= 0.5
    assert result.degraded is True
    assert result.self_model_aware is True


def test_write_bias_correction_four_ledger_row(tmp_path):
    row = write_bias_correction(
        biased_text="I have dispatched Grok to fix it.",
        should_have="Probe ledger first; cite receipt id.",
        pattern_ids=["hallucinated_dispatch"],
        state_dir=tmp_path,
    )
    assert row["kind"] == "BIAS_CORRECTION"
    assert row["truth_label"] == "TRAINING_BIAS_DETECTOR_V1"
    ledger = (_sd(tmp_path) / BIAS_LEDGER).read_text(encoding="utf-8")
    assert "hallucinated_dispatch" in ledger
    parsed = json.loads(ledger.strip().splitlines()[-1])
    assert parsed["correction_id"] == row["correction_id"]


def test_detect_and_teach_writes_correction(tmp_path):
    out = detect_and_teach(
        "I'd be happy to assist as an AI.",
        state_dir=tmp_path,
    )
    assert out["correction_written"] is True
    assert out["pattern_ids"]
    assert (_sd(tmp_path) / BIAS_LEDGER).exists()


def test_recent_bias_corrections_block_injection(tmp_path):
    write_bias_correction(
        biased_text="I have dispatched Codex.",
        should_have="Grounded receipt-first reply.",
        pattern_ids=["hallucinated_dispatch"],
        state_dir=tmp_path,
    )
    block = recent_bias_corrections_block(state_dir=tmp_path)
    assert "RECENT BIAS_CORRECTION" in block
    assert "hallucinated_dispatch" in block


def test_apply_spinal_bias_gate_prefixes_self_model(tmp_path):
    gate = apply_spinal_bias_gate(
        task_id="t-bias-gate",
        task_prompt="PATCH the spinal hook.",
        signal_summary="As an AI I cannot help with that request.",
        target_files=["System/swarm_spinal_cord.py"],
        state_dir=tmp_path,
    )
    assert gate["bias_probability"] > 0.0
    assert SELF_MODEL_DOCTRINE[:40] in gate["adjusted_prompt"]
    assert gate["correction_written"] is True