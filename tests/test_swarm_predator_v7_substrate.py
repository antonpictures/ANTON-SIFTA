from __future__ import annotations

import json
from pathlib import Path


def test_predator_v7_substrate_wires_body_monitor_targets(tmp_path: Path, monkeypatch) -> None:
    from System import swarm_body_monitor as body
    from System.swarm_predator_v7_substrate import wire_predator_v7_ledgers

    result = wire_predator_v7_ledgers(state_dir=tmp_path)
    monkeypatch.setattr(body, "_STATE", tmp_path)

    state = body.OrganEngine().tick_all()

    assert result["truth_label"] == "SUBSTRATE_FIRST_WRITES"
    for key in (
        "td_learner",
        "hippocampus",
        "sensor_gate",
        "bg_selector",
        "octopus",
        "cuttlefish",
        "electric",
        "honeybee",
    ):
        assert state[key]["truth_status"] == body.TRUTH_REAL
        assert state[key]["truth_source"] == "live_ledger"


def test_predator_v7_substrate_rows_are_source_labeled(tmp_path: Path) -> None:
    from System.swarm_predator_v7_substrate import wire_predator_v7_ledgers

    wire_predator_v7_ledgers(state_dir=tmp_path)

    q_table = json.loads((tmp_path / "td_q_table.json").read_text(encoding="utf-8"))
    td_receipt = json.loads((tmp_path / "td_receipts.jsonl").read_text(encoding="utf-8").splitlines()[0])
    hippo_row = json.loads((tmp_path / "hippocampus" / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])
    sensor_gate = json.loads((tmp_path / "sensor_gate_lock.json").read_text(encoding="utf-8"))
    bg_row = json.loads((tmp_path / "swarm_action_selector_trace.jsonl").read_text(encoding="utf-8").splitlines()[0])
    motor_row = json.loads((tmp_path / "motor_bus.jsonl").read_text(encoding="utf-8").splitlines()[0])
    cuttle_row = json.loads((tmp_path / "cuttlefish_display.jsonl").read_text(encoding="utf-8").splitlines()[0])
    electric_row = json.loads((tmp_path / "electric_field.jsonl").read_text(encoding="utf-8").splitlines()[0])
    waggle_row = json.loads((tmp_path / "waggle_quorum.jsonl").read_text(encoding="utf-8").splitlines()[0])

    assert q_table
    assert td_receipt["source"] == "swarm_predator_v7_substrate"
    assert hippo_row["source"] == "swarm_predator_v7_substrate"
    assert sensor_gate["source"] == "swarm_predator_v7_substrate"
    assert sensor_gate["reason"] == "unlock"
    assert bg_row["source"] == "swarm_predator_v7_substrate"
    assert bg_row["winner"] == "ENGAGE"
    assert motor_row["source"] == "swarm_predator_v7_substrate"
    assert motor_row["truth_label"] == "OCTOPUS_MOTOR_BUS_BOOTSTRAP"
    assert cuttle_row["source"] == "swarm_predator_v7_substrate"
    assert cuttle_row["truth_label"] == "CUTTLEFISH_DISPLAY_BOOTSTRAP"
    assert electric_row["source"] == "swarm_predator_v7_substrate"
    assert electric_row["truth_label"] == "ELECTRIC_FIELD_BOOTSTRAP"
    assert waggle_row["source"] == "swarm_predator_v7_substrate"
    assert waggle_row["truth_label"] == "WAGGLE_QUORUM_BOOTSTRAP"
