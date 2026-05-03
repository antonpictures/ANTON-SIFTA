"""
Tests for Event 134 — enforce_stability_clamps().
Validates clamp level escalation, receipt schema, EMERGENCY gate,
and disable env-var kill-switch.
"""
import os
import json
import pytest
from pathlib import Path
from System.swarm_stability_audit import (
    compute_stability_snapshot,
    enforce_stability_clamps,
    tail_stability_rows,
)


def _snap(energy=0.1, delta=0.0, astro=0.0, stable=True):
    """Build a minimal snapshot dict for clamp testing."""
    return {
        "lyapunov_energy": energy,
        "delta_lyapunov_energy": delta,
        "terms": {"astrocyte_heat_norm": astro},
        "stable": stable,
    }


# ── Clamp levels ───────────────────────────────────────────────────────────────

def test_no_clamp_when_healthy():
    receipt = enforce_stability_clamps(_snap(energy=0.1, delta=0.05), write_ledger=False)
    assert receipt["clamp_level"] == "NONE"
    assert receipt["stability_ok"] is True
    assert receipt["active_clamps"] == []


def test_rate_limit_on_rising_delta():
    receipt = enforce_stability_clamps(_snap(delta=0.25), write_ledger=False)
    assert receipt["clamp_level"] == "RATE_LIMIT"
    assert receipt["max_prunes_override"] == 3
    assert receipt["exploration_bias_cap"] == pytest.approx(0.3)


def test_block_new_gates_at_warn_energy():
    receipt = enforce_stability_clamps(_snap(energy=0.55), write_ledger=False)
    assert receipt["clamp_level"] == "BLOCK_NEW"
    assert receipt["block_new_gates"] is True
    assert receipt["lr_ceiling"] == pytest.approx(0.05)
    assert receipt["max_prunes_override"] == 1


def test_emergency_at_hard_energy():
    receipt = enforce_stability_clamps(_snap(energy=0.85), write_ledger=False)
    assert receipt["clamp_level"] == "EMERGENCY"
    assert receipt["stability_ok"] is False
    assert receipt["max_prunes_override"] == 0
    assert receipt["lr_ceiling"] == pytest.approx(0.01)
    assert receipt["exploration_bias_cap"] == pytest.approx(0.0)


def test_emergency_on_unstable_and_hard_delta():
    receipt = enforce_stability_clamps(
        _snap(energy=0.3, delta=0.45, stable=False), write_ledger=False
    )
    assert receipt["clamp_level"] == "EMERGENCY"


def test_receipt_has_provenance():
    receipt = enforce_stability_clamps(_snap(), write_ledger=False)
    assert "Khalil" in receipt["provenance"]
    assert "Liberzon" in receipt["provenance"]


# ── Ledger write ───────────────────────────────────────────────────────────────

def test_clamp_writes_to_ledger_when_active(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_SHARED_STATE_DIR", str(tmp_path))
    receipt = enforce_stability_clamps(_snap(energy=0.9), root=tmp_path)
    log = tmp_path / "stability_audit.jsonl"
    assert log.exists()
    row = json.loads(log.read_text().strip().splitlines()[-1])
    assert row["kind"] == "STABILITY_CLAMP"
    assert row["clamp_level"] == "EMERGENCY"


def test_no_write_when_clamp_is_none(tmp_path):
    enforce_stability_clamps(_snap(energy=0.1, delta=0.01), root=tmp_path, write_ledger=True)
    log = tmp_path / "stability_audit.jsonl"
    # file should not exist (NONE clamp skips write)
    assert not log.exists()


# ── Kill-switch ────────────────────────────────────────────────────────────────

def test_disable_env_returns_none_clamp(monkeypatch):
    monkeypatch.setenv("SIFTA_STABILITY_AUDIT_DISABLE", "1")
    receipt = enforce_stability_clamps(_snap(energy=0.99), write_ledger=False)
    assert receipt["clamp_level"] == "NONE"
    assert receipt["disabled"] is True


# ── Integration: compute_stability_snapshot feeds enforce_stability_clamps ─────

def test_snapshot_to_clamps_pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_SHARED_STATE_DIR", str(tmp_path))
    snap = compute_stability_snapshot(
        multi_gate_norm=0.0, critic_norm=0.0, arbiter_norm=0.0,
        world_error_norm=0.0, astrocyte_heat_norm=0.0,
        root=tmp_path, write_ledger=False,
    )
    receipt = enforce_stability_clamps(snap, write_ledger=False)
    assert "clamp_level" in receipt
    assert "stability_ok" in receipt
