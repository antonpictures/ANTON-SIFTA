from __future__ import annotations

import json
from pathlib import Path

from System.swarm_organ_health_mesh import (
    SCHEMA,
    OrganHealthReport,
    build_health_mesh,
    demo_reports,
    health_score,
    plan_repairs,
    run_organ_health_mesh_demo,
)


def test_health_score_decreases_with_error_latency_and_wounds() -> None:
    healthy = OrganHealthReport(
        organ_id="memory",
        energy=0.9,
        error_rate=0.02,
        latency_ms=120,
        stgm_delta=0.5,
        wounds=(),
        local_swimmers=8,
    )
    sick = OrganHealthReport(
        organ_id="talk",
        energy=0.25,
        error_rate=0.5,
        latency_ms=2500,
        stgm_delta=-0.5,
        wounds=("voice_backlog", "residue_leak"),
        local_swimmers=8,
    )

    assert health_score(healthy) > 0.75
    assert health_score(sick) < health_score(healthy)
    assert health_score(sick) < 0.55


def test_sick_talk_emits_distress_and_recruits_named_repair_organs() -> None:
    mesh = build_health_mesh(demo_reports(now=123.0), now=123.0)
    plan = plan_repairs(mesh, stgm_budget=0.5)

    talk = mesh["organs"]["talk"]
    assert mesh["schema"] == SCHEMA
    assert talk["status"] in {"sick", "critical"}
    assert talk["distress_pheromone"] >= 0.2

    interventions = plan["interventions"]
    assert [row["to_organ"] for row in interventions[:3]] == ["talk", "talk", "talk"]
    assert {row["from_organ"] for row in interventions[:3]} == {"memory", "residue", "economy"}
    assert {row["repair_kind"] for row in interventions[:3]} == {
        "context_swimmer",
        "cleanup_swimmer",
        "budget_swimmer",
    }
    assert 0 < plan["stgm_spent"] <= 0.5


def test_demo_recovers_talk_and_writes_receipt(tmp_path: Path) -> None:
    result = run_organ_health_mesh_demo(state_dir=tmp_path, write=True, now=123.0)
    receipt = result["receipt"]

    assert receipt["kind"] == "ORGAN_HEALTH_MESH_REPAIR"
    assert receipt["target_organ"] == "talk"
    assert receipt["after_score"] > receipt["before_score"]
    assert receipt["recovered"] is True
    assert receipt["before_status"] == "critical"
    assert receipt["after_status"] in {"watch", "healthy"}
    assert receipt["stgm_spent"] > 0
    assert receipt["distress_pheromone"] >= 0.2
    assert "simulation" in receipt["truth_boundary"].casefold()

    ledger = tmp_path / "organ_health_mesh_receipts.jsonl"
    latest = tmp_path / "organ_health_mesh_latest.json"
    assert ledger.exists()
    assert latest.exists()
    written = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert written["receipt"] == receipt["receipt"]
    assert json.loads(latest.read_text(encoding="utf-8"))["receipt"]["target_organ"] == "talk"


def test_budget_caps_repair_spend() -> None:
    mesh = build_health_mesh(demo_reports(now=123.0), now=123.0)
    plan = plan_repairs(mesh, stgm_budget=0.08)

    assert 0 < plan["stgm_spent"] <= 0.08
    assert plan["intervention_count"] >= 1


def test_no_distress_no_repairs() -> None:
    reports = {
        "talk": OrganHealthReport("talk", 0.92, 0.02, 130.0, 0.4, (), 8, 123.0),
        "memory": OrganHealthReport("memory", 0.90, 0.03, 140.0, 0.5, (), 8, 123.0),
        "economy": OrganHealthReport("economy", 0.93, 0.01, 100.0, 0.7, (), 8, 123.0),
    }
    mesh = build_health_mesh(reports, now=123.0)
    plan = plan_repairs(mesh, stgm_budget=0.5)

    assert mesh["distress_organs"] == []
    assert plan["intervention_count"] == 0
    assert plan["stgm_spent"] == 0.0
