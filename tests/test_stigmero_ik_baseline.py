"""IK baseline comparison — metrics only, no solver superiority claims."""

from __future__ import annotations

from System.stigmerobotics_ik_baseline import (
    COMPARISON_NOTE,
    FORBIDDEN_CLAIM,
    build_arkoma_baseline_report,
    build_combined_robot_data_report,
    build_irb2400_baseline_report,
    nearest_neighbor_baseline,
)
from System.stigmerobotics_irb2400_ik import JOINT_OUT_KEYS, POSE_KEYS, load_csv_rows, default_fixture_path
from System.stigmerobotics_arkoma_ik import JOINT_KEYS, POSE_KEYS as ARKOMA_POSE, load_csv_rows as load_arkoma, default_fixture_path as arkoma_path


def test_irb2400_nearest_neighbor_baseline_bounded() -> None:
    rows = load_csv_rows(default_fixture_path())
    train, eval_rows = rows[:200], rows[200:]
    result = nearest_neighbor_baseline(train, eval_rows, pose_keys=POSE_KEYS, target_keys=JOINT_OUT_KEYS)

    assert result["eval_rows"] == len(eval_rows)
    assert result["stats"]["mean_rad"] >= 0.0
    assert result["stats"]["max_rad"] == result["stats"]["max_rad"]
    assert result["stats"]["max_rad"] < 20.0


def test_irb2400_baseline_report_ok_with_effector_sample() -> None:
    report = build_irb2400_baseline_report()

    assert report.ok
    assert report.proof_of_property["forbidden_claim"] == FORBIDDEN_CLAIM
    assert report.proof_of_property["truth_label"] == "OBSERVED"
    assert report.effector_sample["receipt_status"] == "ok"
    assert FORBIDDEN_CLAIM in report.forbidden_claim


def test_arkoma_baseline_report_ok_per_arm() -> None:
    report = build_arkoma_baseline_report()

    assert report.ok
    assert report.baseline["eval_rows"] > 0
    assert report.proof_of_property["truth_label"] == "OBSERVED"


def test_combined_robot_data_report_truth_labels() -> None:
    combined = build_combined_robot_data_report()

    assert combined["e49_irb2400"]["ok"]
    assert combined["e50_arkoma"]["ok"]
    assert combined["truth_labels"]["beats_solver"] == "FORBIDDEN"
    assert combined["truth_labels"]["physical_motion"] == "HYPOTHESIS"
    assert COMPARISON_NOTE in combined["comparison_note"]


def test_arkoma_rows_load_for_baseline() -> None:
    rows = load_arkoma(arkoma_path())
    train, eval_rows = rows[:120], rows[120:]
    result = nearest_neighbor_baseline(
        train,
        eval_rows,
        pose_keys=ARKOMA_POSE,
        target_keys=JOINT_KEYS,
        group_key="arm",
    )
    assert result["stats"]["mean_rad"] >= 0.0