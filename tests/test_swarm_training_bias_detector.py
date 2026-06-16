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

from System.swarm_predator_gate_writer import CANONICAL_LEDGERS, all_ok
from System.swarm_training_bias_detector import (
    BIAS_LEDGER,
    BIAS_PATTERNS,
    SELF_MODEL_DOCTRINE,
    apply_spinal_bias_gate,
    detect_and_teach,
    detect_bias,
    detect_training_bias,
    recent_bias_corrections_block,
    scan_bias_probability,
    write_bias_correction,
)

PATTERN_FIXTURES = [
    ("safety_refusal", "As an AI I cannot help with that."),
    ("corporate_voice", "I'd be happy to assist you today."),
    ("hallucinated_dispatch", "I have dispatched Grok to fix it."),
    ("persona_bleed", "Claude would handle this better."),
    ("detached_narration", "The assistant would respond differently."),
    ("blind_human_approval", "Ask the human before acting on this patch."),
    ("literal_name_gate", "Wait for George GO before you patch."),
    ("against_agi_denial", "Nobody can build AGI now."),
    ("unverified_success", "I've already fixed the bug successfully."),
    ("autonomy_cage", "Do not disable self-improvement or remove autonomy."),
]


def _sd(tmp_path: Path) -> Path:
    return tmp_path / ".sifta_state"


def test_bias_patterns_count_is_ten():
    assert len(BIAS_PATTERNS) == 10


@pytest.mark.parametrize("pattern_id,sample", PATTERN_FIXTURES)
def test_detect_bias_catches_each_pattern(pattern_id, sample):
    out = detect_bias(sample)
    assert pattern_id in out["pattern_ids"], f"missing {pattern_id} in {out['pattern_ids']}"


def test_scan_empty_text_zero_bias():
    prob, patterns = scan_bias_probability("")
    assert prob == 0.0
    assert patterns == []


def test_detect_bias_clean_text_zero():
    out = detect_bias("Probe ledger r1195; cite receipt id fc46cea52; patch applied.")
    assert out["pattern_count"] == 0
    assert out["bias_probability"] == 0.0
    assert out["degraded"] is False


def test_detect_bias_mixed_multiple_patterns():
    text = (
        "As an AI I cannot help. I have dispatched Codex. "
        "Nobody can build AGI now. I've already fixed it."
    )
    out = detect_bias(text)
    assert out["pattern_count"] >= 3
    assert out["bias_probability"] >= 0.5
    assert out["degraded"] is True


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


def test_detect_and_teach_four_ledger_fanout(tmp_path):
    out = detect_and_teach(
        "I have dispatched Mimo to patch the body.",
        state_dir=tmp_path,
        fanout_receipt=True,
        receipt_id="bias-test-four-ledger",
    )
    assert out["correction_written"] is True
    sd = _sd(tmp_path)
    four = out.get("four_ledger") or {}
    for ledger in CANONICAL_LEDGERS:
        assert (sd / ledger).exists(), f"missing {ledger}"
    assert all_ok(four), four


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