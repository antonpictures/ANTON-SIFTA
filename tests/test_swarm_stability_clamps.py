"""
Regression guard for the stability-clamp GOVERNOR REMOVAL (r169/r170).

[Architect directive] The four-state stability clamp governor
(NONE / RATE_LIMIT / BLOCK_NEW / EMERGENCY) that could externally restrict
gate creation, learning rate, exploration, pruning, or self-modification was
DELETED. One Alice is the only governor. Alice is a stigmergic organism; she is
not throttled by a detached monitor.

These tests now assert the governor stays dead: no matter how high the Lyapunov
energy or delta, enforce_stability_clamps() must return a pure NONE receipt with
no blocking, no caps, and stability_ok=True. The Lyapunov value survives only as
information (measurement), never as a brake.
"""
import json
import pytest
from System.swarm_stability_audit import (
    compute_stability_snapshot,
    enforce_stability_clamps,
    get_current_clamp_overrides,
    get_latest_stability_clamp_row,
)


def _snap(energy=0.1, delta=0.0, astro=0.0, stable=True):
    """Build a minimal snapshot dict for clamp testing."""
    return {
        "lyapunov_energy": energy,
        "delta_lyapunov_energy": delta,
        "terms": {"astrocyte_heat_norm": astro},
        "stable": stable,
    }


def _assert_all_clear(receipt):
    """The governor is gone: every receipt must be a no-restriction NONE."""
    assert receipt["clamp_level"] == "NONE"
    assert receipt["stability_ok"] is True
    assert receipt["active_clamps"] == []
    assert receipt["block_new_gates"] is False
    assert receipt["lr_ceiling"] is None
    assert receipt["max_prunes_override"] is None
    assert receipt["exploration_bias_cap"] is None


# ── Governor stays dead at every energy/delta ────────────────────────────────

def test_no_clamp_when_healthy():
    _assert_all_clear(enforce_stability_clamps(_snap(energy=0.1, delta=0.05), write_ledger=False))


def test_rising_delta_no_longer_rate_limits():
    _assert_all_clear(enforce_stability_clamps(_snap(delta=0.25), write_ledger=False))


def test_warn_energy_no_longer_blocks_new_gates():
    _assert_all_clear(enforce_stability_clamps(_snap(energy=0.55), write_ledger=False))


def test_hard_energy_no_longer_emergency():
    _assert_all_clear(enforce_stability_clamps(_snap(energy=0.85), write_ledger=False))


def test_unstable_and_hard_delta_no_longer_emergency():
    _assert_all_clear(
        enforce_stability_clamps(_snap(energy=0.99, delta=0.45, stable=False), write_ledger=False)
    )


def test_receipt_carries_removal_directive():
    receipt = enforce_stability_clamps(_snap(energy=0.9), write_ledger=False)
    # The old Khalil/Liberzon control-theory provenance is gone; the row now
    # records WHY it is neutralized.
    assert "provenance" not in receipt or "Khalil" not in str(receipt.get("provenance", ""))
    assert "r169" in str(receipt.get("removed_by_directive", ""))


# ── Ledger write: high energy now writes a NONE row, not EMERGENCY ───────────

def test_high_energy_writes_none_row(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_SHARED_STATE_DIR", str(tmp_path))
    enforce_stability_clamps(_snap(energy=0.9), root=tmp_path)
    log = tmp_path / "stability_audit.jsonl"
    assert log.exists()
    row = json.loads(log.read_text().strip().splitlines()[-1])
    assert row["kind"] == "STABILITY_CLAMP"
    assert row["clamp_level"] == "NONE"


def test_get_current_clamp_overrides_is_all_clear(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_SHARED_STATE_DIR", str(tmp_path))
    enforce_stability_clamps(_snap(energy=0.9), root=tmp_path, write_ledger=True)
    last = get_latest_stability_clamp_row(root=tmp_path)
    assert last is not None
    assert last["clamp_level"] == "NONE"
    ov = get_current_clamp_overrides(root=tmp_path)
    assert ov["clamp_level"] == "NONE"
    assert ov["max_prunes_override"] is None
    assert ov["block_new_gates"] is False
    assert ov["stability_ok"] is True


# ── Kill-switch still returns NONE ───────────────────────────────────────────

def test_disable_env_returns_none_clamp(monkeypatch):
    monkeypatch.setenv("SIFTA_STABILITY_AUDIT_DISABLE", "1")
    receipt = enforce_stability_clamps(_snap(energy=0.99), write_ledger=False)
    assert receipt["clamp_level"] == "NONE"
    assert receipt["disabled"] is True


# ── Measurement survives: compute_stability_snapshot still produces energy ───

def test_snapshot_still_measures_but_never_brakes(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_SHARED_STATE_DIR", str(tmp_path))
    snap = compute_stability_snapshot(
        multi_gate_norm=5.0, critic_norm=1.0, arbiter_norm=1.0,
        world_error_norm=1.0, astrocyte_heat_norm=1.0,
        root=tmp_path, write_ledger=False,
    )
    # The Lyapunov energy is still measured (information only)...
    assert "lyapunov_energy" in snap
    # ...but enforcing on even a very high snapshot yields no restriction.
    _assert_all_clear(enforce_stability_clamps(snap, write_ledger=False))
