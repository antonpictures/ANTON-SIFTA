from __future__ import annotations

import json
import subprocess
import sys

import pytest

from System.swarm_edge_receipts import cached_receipt_hash, chain_head_path, verify_chained_ledger
from System.swarm_fast_layer_cpg import run_cpg_steps, step_cpg
from System.swarm_edge_species_live_demo import run_demo
from System.swarm_edge_unified_verifier import verify_unified_chain
from System.swarm_field_to_cpg_modulator import (
    compute_cpg_modulation,
    load_latest_modulation,
    modulate_cpg,
    write_modulation_receipt,
)
from System.swarm_jetson_motor_binding import duty_cycle_for_value, send_joint_command, setup
from System.swarm_edge_receipts import append_chained_receipt


def _field_state(tmp_path, *, thermal=0.0, pressure=0.0, dfa="SAFE"):
    return append_chained_receipt(
        state_dir=tmp_path,
        ledger_name="organ_field_vector.jsonl",
        source="test",
        event_type="FIELD",
        payload={
            "thermal_load": thermal,
            "energy_pressure": pressure,
            "dfa_state": dfa,
            "motor_effector_policy": {"effector_gate": "VETO" if dfa == "VETO" else "LEDGER_ONLY"},
        },
    )


def test_field_to_cpg_modulation_uses_thermal_and_energy_pressure(tmp_path):
    _field_state(tmp_path, thermal=0.5, pressure=0.25, dfa="SAFE")

    modulation = load_latest_modulation(state_dir=tmp_path)
    result = compute_cpg_modulation([1.0, 2.0], 0.4, state_dir=tmp_path, modulation=modulation)
    omega, coupling, amplitude = modulate_cpg([1.0, 2.0], 0.4, state_dir=tmp_path)

    assert modulation.thermal_load == pytest.approx(0.5)
    assert modulation.energy_pressure == pytest.approx(0.25)
    assert result.thermal_factor == pytest.approx(0.7)
    assert result.energy_factor == pytest.approx(0.75)
    assert omega == pytest.approx([0.525, 1.05])
    assert coupling == pytest.approx(0.3)
    assert amplitude == pytest.approx(0.75)


def test_veto_modulation_freezes_fast_layer(tmp_path):
    _field_state(tmp_path, thermal=0.9, pressure=0.9, dfa="VETO")

    result = compute_cpg_modulation([1.0, 2.0], 0.4, state_dir=tmp_path)

    assert result.dfa_state == "VETO"
    assert result.modulated_omega == pytest.approx((0.05, 0.1))
    assert result.modulated_coupling == pytest.approx(0.02)
    assert result.modulated_amplitude == pytest.approx(0.1)


def test_motor_binding_simulates_by_default_and_hash_chains(tmp_path, monkeypatch):
    monkeypatch.delenv("SIFTA_JETSON_MOTOR_ENABLE", raising=False)
    _field_state(tmp_path, thermal=0.0, pressure=0.0, dfa="SAFE")

    setup_row = setup(state_dir=tmp_path)
    command_row = send_joint_command("j2_wrist", 0.5, state_dir=tmp_path)

    assert setup_row["ok"] is True
    assert command_row["payload"]["hardware_sent"] is False
    assert command_row["payload"]["simulated"] is True
    assert command_row["payload"]["duty"] == pytest.approx(10.0)
    verification = verify_chained_ledger(tmp_path / "fast_layer_cpg.jsonl")
    assert verification["ok"] is True
    assert verification["row_count"] == 3
    assert cached_receipt_hash(tmp_path / "fast_layer_cpg.jsonl") == command_row["receipt_hash"]
    assert chain_head_path(tmp_path / "fast_layer_cpg.jsonl").exists()


def test_edge_receipts_use_chain_head_sidecar(tmp_path):
    first = append_chained_receipt(
        state_dir=tmp_path,
        ledger_name="fast_layer_cpg.jsonl",
        source="test",
        event_type="FIRST",
        payload={"n": 1},
    )
    second = append_chained_receipt(
        state_dir=tmp_path,
        ledger_name="fast_layer_cpg.jsonl",
        source="test",
        event_type="SECOND",
        payload={"n": 2},
    )

    ledger = tmp_path / "fast_layer_cpg.jsonl"
    head = json.loads(chain_head_path(ledger).read_text(encoding="utf-8"))
    assert second["previous_hash"] == first["receipt_hash"]
    assert head["last_hash"] == second["receipt_hash"]
    assert head["row_count"] == 2
    assert cached_receipt_hash(ledger) == second["receipt_hash"]
    assert verify_chained_ledger(ledger)["ok"] is True


def test_motor_binding_veto_blocks_even_simulated_output(tmp_path):
    _field_state(tmp_path, thermal=0.9, pressure=0.9, dfa="VETO")

    command_row = send_joint_command("j2_wrist", 0.8, state_dir=tmp_path)

    assert command_row["status"] == "blocked_by_dfa_veto"
    assert command_row["payload"]["sent_value"] == 0.0
    assert command_row["payload"]["hardware_sent"] is False
    assert command_row["payload"]["duty"] == pytest.approx(7.5)


def test_unknown_joint_rejected_with_receipt(tmp_path):
    command_row = send_joint_command("j9_unknown", 0.2, state_dir=tmp_path)

    assert command_row["ok"] is False
    assert command_row["status"] == "unknown_joint"
    assert command_row["payload"]["hardware_sent"] is False


def test_modulation_receipt_and_unified_verifier(tmp_path):
    _field_state(tmp_path, thermal=0.2, pressure=0.1, dfa="SAFE")
    write_modulation_receipt([1.0, 1.1], 0.35, state_dir=tmp_path)
    send_joint_command("j2_wrist", 0.3, state_dir=tmp_path)

    report = verify_unified_chain(state_dir=tmp_path, write_receipt=True)

    assert report["ok"] is True
    assert (tmp_path / "edge_unified_verifier.jsonl").exists()


def test_fast_layer_cpg_steps_and_hash_chains(tmp_path):
    _field_state(tmp_path, thermal=0.0, pressure=0.0, dfa="SAFE")

    report = run_cpg_steps(steps=3, state_dir=tmp_path, drive_motors=False)

    assert report["ok"] is True
    assert report["steps_completed"] == 3
    assert report["real_time_claim"] is False
    assert report["final_state"]["tick_index"] == 3
    assert verify_chained_ledger(tmp_path / "fast_layer_cpg_ticks.jsonl")["ok"] is True
    assert verify_chained_ledger(tmp_path / "fast_cpg_modulation.jsonl")["ok"] is True


def test_fast_layer_cpg_veto_receipts_and_blocks_motors(tmp_path):
    _field_state(tmp_path, thermal=0.9, pressure=0.9, dfa="VETO")

    result = step_cpg(state_dir=tmp_path, drive_motors=True)

    assert result["tick"]["status"] == "veto"
    assert result["tick"]["payload"]["modulation"]["dfa_state"] == "VETO"
    assert len(result["motor_rows"]) == 4
    assert {row["status"] for row in result["motor_rows"]} == {"blocked_by_dfa_veto"}
    assert verify_chained_ledger(tmp_path / "fast_layer_cpg_ticks.jsonl")["ok"] is True
    assert verify_chained_ledger(tmp_path / "fast_layer_cpg.jsonl")["ok"] is True


def test_live_demo_runs_end_to_end_in_simulation(tmp_path):
    report = run_demo(state_dir=tmp_path)

    assert report["ok"] is True
    assert len(report["steps"]) == 5
    assert verify_chained_ledger(tmp_path / "fast_layer_cpg.jsonl")["ok"] is True
    assert verify_chained_ledger(tmp_path / "fast_layer_cpg_ticks.jsonl")["ok"] is True
    assert verify_chained_ledger(tmp_path / "fast_cpg_modulation.jsonl")["ok"] is True


def test_live_demo_cli_respects_state_dir(tmp_path):
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "System.swarm_edge_species_live_demo",
            "--state-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(proc.stdout)

    assert report["ok"] is True
    assert (tmp_path / "organ_field_vector.jsonl").exists()
    assert (tmp_path / "fast_layer_cpg.jsonl").exists()
    assert verify_chained_ledger(tmp_path / "organ_field_vector.jsonl")["row_count"] == 4


def test_duty_cycle_clamps():
    assert duty_cycle_for_value(-2.0) == pytest.approx(2.5)
    assert duty_cycle_for_value(0.0) == pytest.approx(7.5)
    assert duty_cycle_for_value(2.0) == pytest.approx(12.5)
