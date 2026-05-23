#!/usr/bin/env python3
"""Tests for swarm_adaptive_compute_gate."""

from __future__ import annotations

from pathlib import Path

from System import swarm_adaptive_compute_gate as gate


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()])


def test_entropy_and_conflict_metrics_are_normalized():
    assert gate.normalized_entropy([0.5, 0.5]) == 1.0
    assert gate.normalized_entropy([1.0, 0.0]) == 0.0
    assert gate.probability_conflict([0.51, 0.49]) > 0.95
    assert gate.probability_conflict([0.95, 0.05]) < 0.20


def test_high_uncertainty_deepens_budget():
    decision = gate.decide_compute_budget(
        {
            "token_entropy": 0.9,
            "probability_conflict": 0.85,
            "task_risk": 0.5,
            "owner_direct": 1.0,
        }
    )
    assert decision.truth_label == "ADAPTIVE_COMPUTE_GATE_HYPOTHESIS_V1"
    assert decision.claim_status == "HYPOTHESIS_LOCAL_MECHANIC"
    assert decision.action == "DEEPEN"
    assert decision.budget_multiplier > 1.0
    assert "high_entropy" in decision.reasons
    assert "probability_conflict" in decision.reasons
    assert "Gemini" in decision.boundary


def test_low_uncertainty_fast_passes():
    decision = gate.decide_compute_budget(
        {"token_entropy": 0.05, "probability_conflict": 0.1, "task_risk": 0.0}
    )
    assert decision.action == "FAST_PASS"
    assert decision.budget_multiplier < 1.0


def test_body_pressure_overrides_uncertainty():
    decision = gate.decide_compute_budget(
        {
            "token_entropy": 0.95,
            "probability_conflict": 0.95,
            "task_risk": 0.8,
            "thermal_pressure": 1.0,
            "stgm_pressure": 0.9,
            "latency_pressure": 0.9,
        }
    )
    assert decision.action == "DEFER"
    assert decision.budget_multiplier < 1.0
    assert "body_pressure_high" in decision.reasons


def test_gate_does_not_touch_real_ledgers():
    watch = [
        Path(".sifta_state/work_receipts.jsonl"),
        Path(".sifta_state/stgm_memory_rewards.jsonl"),
        Path(".sifta_state/memory_ledger.jsonl"),
        Path(".sifta_state/unified_stigmergic_field.jsonl"),
    ]
    before = {str(path): _count_lines(path) for path in watch}
    _ = gate.decide_compute_budget({"token_entropy": 0.7, "probability_conflict": 0.7})
    _ = gate.normalized_entropy([0.2, 0.3, 0.5])
    after = {str(path): _count_lines(path) for path in watch}
    assert after == before
