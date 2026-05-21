#!/usr/bin/env python3
"""Tests for swarm_physics_gate — high in-degree load-bearing organ (14 dependents).

Contract per GROK_COVERAGE_CAMPAIGN_ORDER.md:
- Tests only (no source changes).
- Real-ledger delta must be 0.
- Headless-collectable.
- Deterministic, no network, no live metabolic calls where possible.
- Honest, failable assertions.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from System import swarm_physics_gate as gate


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def test_module_exports_public_api():
    """Real behavior 1: the documented public surface exists."""
    assert hasattr(gate, "request_clearance")
    assert hasattr(gate, "stamp_receipt")
    assert hasattr(gate, "request_processing_clearance")  # back-compat alias


def test_cost_policy_is_complete_and_reasonable():
    """Real behavior 2: policy table covers the three declared classes with sane caps."""
    policy = gate._COST_POLICY
    assert "feather" in policy
    assert "breath" in policy
    assert "swimmer" in policy

    for cls, p in policy.items():
        assert p["thermal_max"] in (1, 2)
        assert p["default_stgm"] > 0


def test_request_clearance_grants_under_nominal_conditions(monkeypatch):
    """Core happy path: with good thermal/energy/metabolic, feather/breath grant."""
    with patch.object(gate, "_read_thermal_warning_level", return_value=0), \
         patch.object(gate, "_read_low_power_mode", return_value=False), \
         patch.object(gate, "_read_live_stgm_balance", return_value=42.0), \
         patch.object(gate, "_read_owner_desire", return_value=0.8), \
         patch.object(gate, "_get_metabolic_throttle", return_value=None):

        receipt = gate.request_clearance(cost_class="breath", lane="test.nominal")

    assert receipt["ok"] is True
    assert receipt["decision"] == "grant"
    assert "clearance_hash" in receipt
    assert receipt["signals"]["cost_class"] == "breath"


def test_request_clearance_denies_on_thermal_critical(monkeypatch):
    """Thermal gate: even feather is denied at critical."""
    with patch.object(gate, "_append_denial"), \
         patch.object(gate, "_read_thermal_warning_level", return_value=3), \
         patch.object(gate, "_read_low_power_mode", return_value=False), \
         patch.object(gate, "_read_live_stgm_balance", return_value=100.0), \
         patch.object(gate, "_read_owner_desire", return_value=0.9):

        receipt = gate.request_clearance(cost_class="feather", lane="test.thermal")

    assert receipt["ok"] is False
    assert receipt["decision"] == "deny_thermal_critical"
    assert "clearance_hash" in receipt


def test_request_clearance_denies_low_power_when_boring(monkeypatch):
    """Low-power gate for non-feather classes."""
    with patch.object(gate, "_append_denial"), \
         patch.object(gate, "_read_thermal_warning_level", return_value=0), \
         patch.object(gate, "_read_low_power_mode", return_value=True), \
         patch.object(gate, "_read_live_stgm_balance", return_value=50.0), \
         patch.object(gate, "_read_owner_desire", return_value=0.1):

        receipt = gate.request_clearance(cost_class="swimmer", lane="test.boring")

    assert receipt["ok"] is False
    assert receipt["decision"] == "deny_low_power_conserve"


def test_hash_is_recomputable_and_cryptographic():
    """The clearance_hash must be a deterministic sha256 over (signals, decision)."""
    signals = {"thermal_level": 0, "cost_class": "breath"}
    decision = "grant"

    h1 = gate._hash_receipt(signals, decision=decision)
    h2 = gate._hash_receipt(signals, decision=decision)

    assert h1 == h2
    assert len(h1) == 64  # sha256 hex

    # Tamper with decision → different hash
    h3 = gate._hash_receipt(signals, decision="deny_thermal_critical")
    assert h1 != h3


def test_stamp_receipt_embeds_fields():
    """stamp_receipt mutates the caller's row with the required clearance fields."""
    row: dict = {"schema": "SOME_EVENT_V1", "text": "hello"}
    clearance = {
        "clearance_id": "clr-123",
        "clearance_hash": "abc123",
        "decision": "grant",
        "signals": {"thermal_level": 0},
        "ok": True,
    }

    stamped = gate.stamp_receipt(row, clearance)

    assert stamped is row  # mutates in place
    assert row["clearance_id"] == "clr-123"
    assert row["thermo_denied"] is False


def test_real_ledgers_untouched_by_physics_gate_tests(tmp_path, monkeypatch):
    """Explicit isolation gate per campaign contract."""
    state = Path(".sifta_state")
    watch = [
        state / "memory_ledger.jsonl",
        state / "stgm_memory_rewards.jsonl",
        state / "work_receipts.jsonl",
        state / "ide_stigmergic_trace.jsonl",
        state / "physics_gate_denials.jsonl",
    ]
    before = {str(p): _count_lines(p) for p in watch}

    # Patch the denial writer so we never touch the real denial ledger
    with patch.object(gate, "_append_denial"), \
         patch.object(gate, "_read_thermal_warning_level", return_value=0), \
         patch.object(gate, "_read_low_power_mode", return_value=False), \
         patch.object(gate, "_read_live_stgm_balance", return_value=100.0), \
         patch.object(gate, "_read_owner_desire", return_value=0.9), \
         patch.object(gate, "_get_metabolic_throttle", return_value=None):

        _ = gate.request_clearance(cost_class="feather")
        _ = gate.request_clearance(cost_class="swimmer")

    after = {str(p): _count_lines(p) for p in watch}
    delta = {k: after[k] - before[k] for k in before}

    assert all(v == 0 for v in delta.values()), f"Physics gate tests contaminated live ledgers: {delta}"


def test_request_clearance_hash_verifiable_by_auditor(monkeypatch):
    """End-to-end: an external auditor can recompute the hash from the returned receipt."""
    with patch.object(gate, "_read_thermal_warning_level", return_value=0), \
         patch.object(gate, "_read_low_power_mode", return_value=False), \
         patch.object(gate, "_read_live_stgm_balance", return_value=10.0), \
         patch.object(gate, "_read_owner_desire", return_value=0.5), \
         patch.object(gate, "_get_metabolic_throttle", return_value=None):

        receipt = gate.request_clearance(cost_class="breath", lane="audit.test")

    # Auditor recomputes
    recomputed = gate._hash_receipt(receipt["signals"], decision=receipt["decision"])
    assert recomputed == receipt["clearance_hash"]
