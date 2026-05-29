import json

from System.swarm_stability_audit import (
    compute_stability_snapshot,
    stability_audit_log_path,
    summary_for_prompt,
    tail_stability_rows,
)


def test_stability_audit_low_energy_is_stable(tmp_path):
    row = compute_stability_snapshot(
        root=tmp_path,
        multi_gate_norm=0.2,
        critic_norm=0.1,
        arbiter_norm=0.1,
        world_error_norm=0.1,
        astrocyte_heat_norm=0.1,
    )

    assert row["truth_label"] == "STABILITY_AUDIT"
    assert row["stable"] is True
    assert stability_audit_log_path(tmp_path).exists()


def test_stability_audit_high_energy_is_unstable(tmp_path):
    row = compute_stability_snapshot(
        root=tmp_path,
        multi_gate_norm=3.0,
        critic_norm=2.0,
        arbiter_norm=2.0,
        world_error_norm=3.0,
        astrocyte_heat_norm=1.0,
    )

    assert row["stable"] is False
    assert row["status"] == "UNSTABLE"


def test_stability_audit_delta_can_mark_unstable(tmp_path, monkeypatch):
    monkeypatch.setenv("STABILITY_AUDIT_MAX_ENERGY", "10")
    monkeypatch.setenv("STABILITY_AUDIT_MAX_DELTA", "0.01")
    monkeypatch.setenv("STABILITY_ENERGY_DECAY", "0")
    first = compute_stability_snapshot(root=tmp_path, multi_gate_norm=0.1)
    second = compute_stability_snapshot(root=tmp_path, multi_gate_norm=1.0)

    assert first["stable"] is True
    assert second["delta_lyapunov_energy"] > 0.01
    assert second["stable"] is False


def test_stability_audit_disable_writes_no_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_STABILITY_AUDIT_DISABLE", "1")
    row = compute_stability_snapshot(root=tmp_path, multi_gate_norm=5.0)

    assert row["disabled"] is True
    assert not stability_audit_log_path(tmp_path).exists()


def test_stability_audit_tail_and_summary(tmp_path):
    compute_stability_snapshot(root=tmp_path, multi_gate_norm=0.2)

    rows = tail_stability_rows(root=tmp_path)
    assert len(rows) == 1
    assert json.loads(stability_audit_log_path(tmp_path).read_text().splitlines()[0])["kind"] == "STABILITY_AUDIT"
    assert "STABILITY_AUDIT" in summary_for_prompt(root=tmp_path)
