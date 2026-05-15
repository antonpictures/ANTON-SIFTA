from __future__ import annotations

import json
from pathlib import Path

from System.swarm_unified_organ_ecology import (
    SCHEMA,
    append_organ_ecology_from_field,
    build_organ_ecology_mesh,
    format_organ_ecology_for_prompt,
)


def _field_row() -> dict:
    organs = [
        {"organ": "field", "health": 0.92, "swimmer_count": 3, "source": "organ_field_vector.jsonl", "resolution": "current_tick_field_vector"},
        {"organ": "honeybee", "health": 0.88, "swimmer_count": 2, "source": "waggle_quorum.jsonl", "resolution": "heartbeat_tensor"},
        {"organ": "octopus", "health": 0.50, "swimmer_count": 2, "source": "motor_bus.jsonl", "resolution": "heartbeat_tensor"},
        {"organ": "sensor_gate", "health": 0.20, "swimmer_count": 1, "source": "sensor_gate_lock.json", "resolution": "json_state"},
    ]
    swimmers = []
    for node in organs:
        for idx in range(node["swimmer_count"]):
            swimmers.append(
                {
                    "swimmer_id": f"{node['organ']}:{idx}",
                    "organ": node["organ"],
                    "index": idx,
                }
            )
    return {
        "schema": "ORGAN_EVENT_V1",
        "organ": "unified_field",
        "payload": {
            "tick_id": "tick-test",
            "field_completeness": 1.0,
            "cost_pressure": 0.25,
            "organ_nodes": organs,
            "swimmer_registry": swimmers,
            "coupling_edges": [
                {"source": "honeybee", "target": "octopus", "variables": ["dance_vector"]},
                {"source": "octopus", "target": "field", "variables": ["coherence"]},
                {"source": "sensor_gate", "target": "field", "variables": ["locked"]},
                {"source": "motor_bus.jsonl", "target": "honeybee", "variables": ["prev_octopus_coherence"]},
            ],
        },
    }


def test_ecology_assigns_every_swimmer_to_home_organ() -> None:
    row = build_organ_ecology_mesh(_field_row(), now=123.0)

    assert row["schema"] == SCHEMA
    assert row["kind"] == "UNIFIED_ORGAN_ECOLOGY_MESH"
    assert row["organ_count"] == 4
    assert row["swimmer_count"] == 8
    assert all(s["knows_organ"] is True for s in row["swimmer_assignments"])
    assert {s["home_organ"] for s in row["swimmer_assignments"]} == {
        "field",
        "honeybee",
        "octopus",
        "sensor_gate",
    }


def test_ecology_records_communication_and_health_actions() -> None:
    row = build_organ_ecology_mesh(_field_row(), now=123.0)
    nodes = {n["organ"]: n for n in row["organ_nodes"]}

    assert nodes["honeybee"]["communication_targets"] == ["octopus"]
    assert nodes["octopus"]["communication_sources"] == ["honeybee"]
    assert nodes["field"]["incoming_degree"] >= 2
    assert nodes["sensor_gate"]["health_action"] == "repair"
    assert nodes["honeybee"]["health_action"] in {"grow", "maintain"}
    assert nodes["honeybee"]["stgm_profitability"]["profitable"] is True
    assert row["total_surplus_stgm"] > 0.0


def test_ecology_append_writes_jsonl_and_latest(tmp_path: Path) -> None:
    row = append_organ_ecology_from_field(_field_row(), state_dir=tmp_path, now=123.0)

    ledger = tmp_path / "organ_ecology_mesh.jsonl"
    latest = tmp_path / "organ_ecology_mesh_latest.json"
    assert ledger.exists()
    assert latest.exists()
    written = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert written["schema"] == SCHEMA
    assert written["field_tick_id"] == "tick-test"
    assert json.loads(latest.read_text(encoding="utf-8"))["swimmer_count"] == row["swimmer_count"]


def test_ecology_prompt_summary_surfaces_profitability(tmp_path: Path) -> None:
    append_organ_ecology_from_field(_field_row(), state_dir=tmp_path, now=123.0)

    summary = format_organ_ecology_for_prompt(state_dir=tmp_path)

    assert "UNIFIED ORGAN ECOLOGY" in summary
    assert "swimmers=8" in summary
    assert "total_surplus_stgm" in summary
    assert "weak_organs=sensor_gate" in summary
