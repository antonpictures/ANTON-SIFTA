import json
from pathlib import Path

from System.swarm_agi_frontier_loop import (
    BEST_LINE,
    TRUTH_BOUNDARY,
    create_strategy,
    frontier_prompt_block,
    frontier_status,
    latent_world_model_stats,
    learn_open_ended_concepts,
    record_strategy_event,
    revise_strategy,
    run_frontier_cycle,
    strategy_snapshot,
)


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_truth_boundary_keeps_doctrine_and_frontier_gap_labels() -> None:
    assert "ARCHITECT_DOCTRINE" in TRUTH_BOUNDARY
    assert "stigmergic AGI" in TRUTH_BOUNDARY
    assert "learned-frontier" in TRUTH_BOUNDARY
    assert "not hidden self-awareness" in TRUTH_BOUNDARY


def test_latent_world_model_stats_reports_missing_artifact(tmp_path: Path) -> None:
    stats = latent_world_model_stats(root=tmp_path)
    assert stats["status"] == "OPEN_NO_ARTIFACT"
    assert stats["ready"] is False
    assert "No latent_world_model.json" in stats["open_gap"]


def test_latent_world_model_ready_gate(tmp_path: Path) -> None:
    data = {
        "transitions": {f"s{i}::a": {"next_state": f"n{i}", "reward": 0.1, "count": 1} for i in range(10)},
        "values": {f"s{i}": float(i) for i in range(5)},
    }
    (tmp_path / "latent_world_model.json").write_text(json.dumps(data), encoding="utf-8")

    stats = latent_world_model_stats(root=tmp_path)

    assert stats["ready"] is True
    assert stats["status"] == "EVIDENCED"


def test_concept_model_learns_cross_domain_transfer_candidates(tmp_path: Path) -> None:
    _append(
        tmp_path / "steering_subsystem.jsonl",
        {"route": "VERIFY_BEFORE_ACTION", "detector": "novelty_pressure", "concept": "calibration"},
    )
    _append(
        tmp_path / "causal_intervention_log.jsonl",
        {"expected_effect_on": "calibration", "causal_effect_size": 0.3, "concept": "calibration"},
    )

    model = learn_open_ended_concepts(root=tmp_path, min_count=2, write=True)

    assert model["ready"] is True
    labels = {c["label"] for c in model["concepts"]}
    assert "calibration" in labels
    calibration = next(c for c in model["concepts"] if c["label"] == "calibration")
    assert calibration["status"] == "TRANSFER_CANDIDATE"
    assert sorted(calibration["domains"]) == ["causal", "steering"]
    assert (tmp_path / "agi_frontier_concept_model.json").exists()


def test_create_strategy_snapshot_tracks_multi_week_plan(tmp_path: Path) -> None:
    row = create_strategy(
        "Morning frontier plan",
        "Track learned-frontier gaps across weeks.",
        horizon_days=21,
        milestones=["collect data", "revise after failure"],
        root=tmp_path,
    )

    snap = strategy_snapshot(row["strategy_id"], root=tmp_path)

    assert snap["ready"] is True
    assert snap["status"] == "ACTIVE_TRACKED"
    assert snap["next_milestone"] == "collect data"


def test_failure_then_revision_marks_strategy_survived_failure(tmp_path: Path) -> None:
    row = create_strategy(
        "Failure survival",
        "Survive a failed frontier experiment.",
        horizon_days=14,
        milestones=["try", "recover"],
        root=tmp_path,
    )
    sid = row["strategy_id"]

    record_strategy_event(sid, "FAILURE", "first transfer probe failed", root=tmp_path)
    revise_strategy(sid, "narrow the probe and continue", new_milestone="collect smaller evidence", root=tmp_path)
    snap = strategy_snapshot(sid, root=tmp_path)

    assert snap["failure_count"] == 1
    assert snap["revision_count"] == 1
    assert snap["survived_failure"] is True


def test_frontier_status_exposes_open_gaps_when_underpowered(tmp_path: Path) -> None:
    status = frontier_status(root=tmp_path)

    assert status["truth_label"] == "SIFTA_AGI_FRONTIER_LOOP_V1"
    assert status["ready_count"] < status["frontier_count"]
    assert status["open_gaps"]
    assert status["best_line"] == BEST_LINE


def test_run_frontier_cycle_writes_receipt_and_default_strategy(tmp_path: Path) -> None:
    receipt = run_frontier_cycle(root=tmp_path, write=True)

    assert receipt["truth_label"] == "SIFTA_AGI_FRONTIER_LOOP_V1"
    assert receipt["kind"] == "AGI_FRONTIER_CYCLE"
    assert "sha256" in receipt
    assert (tmp_path / "agi_frontier_loop.jsonl").exists()
    snap = strategy_snapshot(root=tmp_path)
    assert snap["ready"] is True
    assert snap["horizon_days"] == 21


def test_prompt_block_names_best_line_and_open_gaps(tmp_path: Path) -> None:
    run_frontier_cycle(root=tmp_path, write=True)

    block = frontier_prompt_block(root=tmp_path)

    assert "AGI FRONTIER LOOP" in block
    assert BEST_LINE in block
    assert "Open gaps" in block
