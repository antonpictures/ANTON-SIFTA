from __future__ import annotations

import json
from pathlib import Path

from System.stigmerobotics_life_loop_simulator import (
    EXPERIMENT_LEDGER_FILENAME,
    LEDGER_FILENAME,
    SIMULATION_TRUTH_LABEL,
    StigmeroboticsLifeLoopSimulator,
    _all_receipts_paired,
    life_loop_evidence_lines,
    run_life_loop_experiment,
)


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_life_loop_survives_restart_and_recovers_from_disturbance(tmp_path: Path) -> None:
    result = run_life_loop_experiment(tmp_path)

    assert result.passed
    assert result.truth_label == SIMULATION_TRUTH_LABEL
    assert result.process_boundary_verified
    assert result.initial_process_pid != result.resumed_process_pid
    assert result.body_identity_persisted
    assert result.physical_state_persisted
    assert result.trace_loaded_after_restart
    assert result.cold_activation.reached_target
    assert result.resumed_activation.reached_target
    assert result.resumed_activation.disturbed
    assert result.recovery_advantage_steps > 0
    assert result.receipt_chain_ok
    assert result.pheromone_evaporation_ok


def test_each_simulated_motor_request_has_receipt_and_sensor_echo(tmp_path: Path) -> None:
    result = run_life_loop_experiment(tmp_path)
    rows = _rows(Path(result.run_dir) / LEDGER_FILENAME)

    requests = [row for row in rows if row.get("kind") == "effector_request"]
    receipts = [row for row in rows if row.get("kind") == "effector_receipt"]
    echoes = [row for row in rows if row.get("kind") == "desk_telemetry_radar"]

    assert requests
    assert len(requests) == len(receipts) == len(echoes)
    assert {row["trace_id"] for row in requests} == {
        row["request_trace_id"] for row in receipts
    }
    assert all(row["truth_label"] == SIMULATION_TRUTH_LABEL for row in receipts)
    assert all(row["truth_label"] == SIMULATION_TRUTH_LABEL for row in echoes)
    assert all(row["body_instance_id"] == result.body_instance_id for row in echoes)

    experiment_rows = _rows(tmp_path / EXPERIMENT_LEDGER_FILENAME)
    assert len(experiment_rows) == 1
    assert experiment_rows[0]["status"] == "pass"
    assert experiment_rows[0]["payload"]["run_dir"] == result.run_dir


def test_controller_skill_is_recovered_from_field_not_body_snapshot(tmp_path: Path) -> None:
    state_dir = tmp_path / "one-body"
    first = StigmeroboticsLifeLoopSimulator(state_dir)
    cold = first.run_activation()
    assert cold.reached_target

    snapshot = json.loads(first.state_path.read_text(encoding="utf-8"))
    assert "controller_gains" not in snapshot

    restarted = StigmeroboticsLifeLoopSimulator(state_dir)
    assert restarted.trace_loaded
    assert restarted.gains.ki > cold.controller_gains.ki
    assert restarted.body_instance_id == first.body_instance_id


def test_duplicate_motor_ids_fail_receipt_pairing() -> None:
    rows = [
        {"kind": "effector_request", "trace_id": "same"},
        {"kind": "effector_request", "trace_id": "same"},
        {"kind": "effector_receipt", "request_trace_id": "same"},
        {"kind": "effector_receipt", "request_trace_id": "same"},
    ]

    assert not _all_receipts_paired(rows)


def test_evidence_surface_shows_missing_and_latest_failed_result(tmp_path: Path) -> None:
    assert "NOT RUN" in "\n".join(life_loop_evidence_lines(tmp_path))
    root = tmp_path / "stigmerobotics_life_loop_runs"
    run_life_loop_experiment(root)
    assert "Recorded result: PASS" in "\n".join(life_loop_evidence_lines(tmp_path))
    index = root / EXPERIMENT_LEDGER_FILENAME
    row = _rows(index)[-1]
    row["payload"]["passed"] = False
    with index.open("a") as stream:
        stream.write(json.dumps(row) + "\n")
    summary = "\n".join(life_loop_evidence_lines(tmp_path))
    assert "FAIL / UNVERIFIED" in summary
    assert "Recorded result: PASS" not in summary


def test_evidence_surface_does_not_promote_legacy_or_corrupt_record(tmp_path: Path) -> None:
    root = tmp_path / "stigmerobotics_life_loop_runs"
    run_life_loop_experiment(root)
    index = root / EXPERIMENT_LEDGER_FILENAME
    row = _rows(index)[-1]
    del row["payload"]["process_boundary_verified"]
    with index.open("a") as stream:
        stream.write(json.dumps(row) + "\n")
    assert "FAIL / UNVERIFIED" in "\n".join(life_loop_evidence_lines(tmp_path))
    with index.open("a") as stream:
        stream.write("{broken\n")
    assert "UNAVAILABLE" in "\n".join(life_loop_evidence_lines(tmp_path))
