#!/usr/bin/env python3
"""Tests for lagrangian_constraint_manifold - final organ of tranche 1.

Upgraded contract: zero delta on core 4 ledgers + the organ's own
state files (lagrangian_multipliers.json and constraint_residues.jsonl).

Focus: manifold construction, dual ascent, projection, and residue logging
under full isolation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from System import lagrangian_constraint_manifold as lcm


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _fingerprint(path: Path) -> tuple[int, str]:
    if not path.exists():
        return 0, ""
    data = path.read_bytes()
    return len(data.splitlines()), hashlib.sha256(data).hexdigest()


def test_get_manifold_returns_instance():
    """Real behavior 1: entry point works."""
    manifold = lcm.get_manifold()
    assert isinstance(manifold, lcm.LagrangianManifold)
    assert hasattr(manifold, "compute_dual_ascent")


def test_compute_dual_ascent_under_isolation(tmp_path, monkeypatch):
    """Core math + logging under full state isolation."""
    original_dual = lcm._DUAL_STATE_PATH
    original_residue = lcm._RESIDUE_LOG_PATH
    lcm._DUAL_STATE_PATH = tmp_path / "lagrangian_multipliers.json"
    lcm._RESIDUE_LOG_PATH = tmp_path / "constraint_residues.jsonl"

    try:
        manifold = lcm.get_manifold()

        # Mock telemetry so we control the inputs
        with patch.object(manifold, "_read_telemetry") as mock_tele:
            mock_tele.return_value = {"rho": 0.9, "lambda2": 0.2, "e_total": 0.4}

            result = manifold.compute_dual_ascent()

            assert isinstance(result, dict)
            assert result["measurements"] == {"rho": 0.9, "lambda2": 0.2, "e_total": 0.4}
            assert result["violations"] == {"congestion": 0.05, "safety": 0.1, "energy": 0.1}
            assert result["multipliers"] == {
                "lambda_congestion": 0.0025,
                "lambda_safety": 0.005,
                "lambda_energy": 0.005,
            }
            assert result["total_lambda_penalty"] == 0.0125
            assert result["projection_masks"] == {
                "mask_fission": False,
                "mask_mutation": False,
                "mask_exploration": False,
            }
            assert lcm._DUAL_STATE_PATH.exists()
            assert lcm._RESIDUE_LOG_PATH.exists()
    finally:
        lcm._DUAL_STATE_PATH = original_dual
        lcm._RESIDUE_LOG_PATH = original_residue


def test_real_ledgers_untouched_including_organ_own_state(tmp_path, monkeypatch):
    """Explicit isolation gate (core 4 + organ's two state files)."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "lagrangian_multipliers.json",
        state / "constraint_residues.jsonl",
    ]
    before = {str(p): _fingerprint(p) for p in watch}

    original_dual = lcm._DUAL_STATE_PATH
    original_residue = lcm._RESIDUE_LOG_PATH
    lcm._DUAL_STATE_PATH = tmp_path / "lagrangian_multipliers.json"
    lcm._RESIDUE_LOG_PATH = tmp_path / "constraint_residues.jsonl"

    try:
        manifold = lcm.get_manifold()

        with patch.object(manifold, "_read_telemetry") as mock_tele, \
             patch("System.swarm_physics_gate.request_clearance") as mock_clear, \
             patch("System.swarm_physics_gate.stamp_receipt"):
            mock_clear.return_value = {"ok": True, "clearance_hash": "mock", "decision": "grant"}
            mock_tele.return_value = {"rho": 0.7, "lambda2": 0.5, "e_total": 0.6}
            _ = manifold.compute_dual_ascent()
    finally:
        lcm._DUAL_STATE_PATH = original_dual
        lcm._RESIDUE_LOG_PATH = original_residue

    after = {str(p): _fingerprint(p) for p in watch}
    delta = {k: {"before": before[k], "after": after[k]} for k in before if after[k] != before[k]}

    assert not delta, f"Real ledgers (incl. organ own state) contaminated: {delta}"
