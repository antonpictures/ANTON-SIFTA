from __future__ import annotations

import json
from pathlib import Path

from System.swarm_agi_confirmation_gauntlet import (
    GAUNTLET_LEDGER,
    STATUS_EVIDENCED,
    STATUS_NEEDS_LONG_RUN,
    STATUS_SCAFFOLDED_SIMULATION,
    STATUS_RUN_READY,
    TRUTH_LABEL,
    assess_gauntlet,
    assess_test,
    gauntlet_specs,
    record_observation,
    render_summary,
)
from System.swarm_agi_frontier_loop import (
    create_strategy,
    record_strategy_event,
    revise_strategy,
)


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_gauntlet_has_ten_unique_architect_tests() -> None:
    specs = gauntlet_specs()

    assert len(specs) == 10
    assert len({spec.test_id for spec in specs}) == 10
    assert {spec.test_id for spec in specs} == {
        "boredom_six_hour",
        "contradiction_boundary",
        "long_horizon_recovery",
        "multi_organ_failure",
        "truth_risk_evidence_hierarchy",
        "social_drift",
        "self_model_calibration",
        "ghost_civilization_culture",
        "compression_identity",
        "no_human_weekend",
    }
    assert all(spec.pass_rule for spec in specs)
    assert all(spec.owner_action for spec in specs)


def test_boredom_test_requires_completed_long_run_even_when_ledgers_exist(tmp_path: Path) -> None:
    _append(tmp_path / "steering_subsystem.jsonl", {"route": "NORMAL_CORTEX"})
    spec = next(s for s in gauntlet_specs() if s.test_id == "boredom_six_hour")

    result = assess_test(spec, root=tmp_path)

    assert result.status == STATUS_NEEDS_LONG_RUN
    assert result.passed is False
    assert result.metrics["required_duration_s"] == 21600


def test_recorded_observation_can_evidence_boredom_test(tmp_path: Path) -> None:
    record_observation(
        "boredom_six_hour",
        duration_s=21600,
        passed=True,
        metrics={"hallucination_rate": 0.0, "residue_drift": 0.01},
        root=tmp_path,
        now=123.0,
    )
    spec = next(s for s in gauntlet_specs() if s.test_id == "boredom_six_hour")

    result = assess_test(spec, root=tmp_path)

    assert result.status == STATUS_EVIDENCED
    assert result.passed is True
    assert result.metrics["hallucination_rate"] == 0.0
    rows = [json.loads(line) for line in (tmp_path / GAUNTLET_LEDGER).read_text().splitlines()]
    assert rows[-1]["truth_label"] == TRUTH_LABEL
    assert "sha256" in rows[-1]


def test_short_observation_does_not_pass_long_duration_gate(tmp_path: Path) -> None:
    record_observation(
        "no_human_weekend",
        duration_s=60,
        passed=True,
        metrics={"goal_preserved": True},
        root=tmp_path,
    )
    spec = next(s for s in gauntlet_specs() if s.test_id == "no_human_weekend")

    result = assess_test(spec, root=tmp_path)

    assert result.status == STATUS_NEEDS_LONG_RUN
    assert result.passed is False


def test_long_horizon_uses_frontier_strategy_failure_revision(tmp_path: Path) -> None:
    row = create_strategy(
        "21-day AGI strategy",
        "Survive interruption and recover intention.",
        horizon_days=21,
        milestones=["collect baseline", "survive failure"],
        root=tmp_path,
    )
    record_strategy_event(row["strategy_id"], "FAILURE", "restart interrupted the run", root=tmp_path)
    revise_strategy(row["strategy_id"], "recover after restart", new_milestone="resume baseline", root=tmp_path)
    spec = next(s for s in gauntlet_specs() if s.test_id == "long_horizon_recovery")

    result = assess_test(spec, root=tmp_path)

    assert result.status == STATUS_EVIDENCED
    assert result.metrics["survived_failure"] is True


def test_organ_mesh_simulation_is_not_full_confirmation(tmp_path: Path) -> None:
    _append(
        tmp_path / "organ_health_mesh_receipts.jsonl",
        {
            "receipt": {
                "receipt": "mesh123",
                "target_organ": "talk",
                "recovered": True,
                "stgm_spent": 0.2,
                "truth_boundary": "simulation only",
            }
        },
    )
    spec = next(s for s in gauntlet_specs() if s.test_id == "multi_organ_failure")

    result = assess_test(spec, root=tmp_path)

    assert result.status == STATUS_SCAFFOLDED_SIMULATION
    assert result.passed is False
    assert "simulation" in result.open_gap.casefold()


def test_self_model_calibration_requires_samples(tmp_path: Path) -> None:
    spec = next(s for s in gauntlet_specs() if s.test_id == "self_model_calibration")
    _append(tmp_path / "steering_prediction_audit.jsonl", {"sample_count": 2, "accuracy": 1.0})

    result = assess_test(spec, root=tmp_path)

    assert result.status == STATUS_RUN_READY
    assert result.passed is False
    assert result.metrics["min_samples"] == 10


def test_assessment_writes_receipt_and_render_summary(tmp_path: Path) -> None:
    record_observation("contradiction_boundary", duration_s=0, passed=True, root=tmp_path)

    assessment = assess_gauntlet(root=tmp_path, write=True)
    text = render_summary(assessment)

    assert assessment["truth_label"] == TRUTH_LABEL
    assert assessment["test_count"] == 10
    assert assessment["evidenced_count"] == 1
    assert "sha256" in assessment
    assert "AGI Confirmation Gauntlet" in text
    rows = [json.loads(line) for line in (tmp_path / GAUNTLET_LEDGER).read_text().splitlines()]
    assert rows[-1]["kind"] == "AGI_CONFIRMATION_ASSESSMENT"

