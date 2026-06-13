"""E50 — NAO ARKOMA inverse kinematics on real robot data (STIGMEROBOTICS)."""

from __future__ import annotations

import pytest

from System.stigmerobotics_arkoma_ik import (
    ARKOMA_COLUMNS,
    BODY_ID,
    DATASET_DOI,
    build_arkoma_benchmark_report,
    default_fixture_path,
    joint_targets_payload,
    joints_within_limits,
    load_csv_rows,
)
from System.stigmerobotics_effector_bridge import EffectorRequest, execute_request_stub


def test_e50_arkoma_fixture_schema_and_rows() -> None:
    rows = load_csv_rows(default_fixture_path())

    assert len(rows) >= 100
    assert set(ARKOMA_COLUMNS).issubset(rows[0].keys())
    assert all(joints_within_limits(row) for row in rows[:20])


def test_e50_arkoma_benchmark_report_is_grounded() -> None:
    rows = load_csv_rows(default_fixture_path())
    report = build_arkoma_benchmark_report(rows, source_path=str(default_fixture_path()))

    assert report.ok
    assert report.dataset_doi == DATASET_DOI
    assert report.grounded_rows == report.row_count
    assert report.observation_rank >= 5
    assert report.joints_in_range == report.row_count
    assert report.proof_of_property["truth_label"] == "OPERATIONAL"


def test_e50_arkoma_schema_rejects_missing_columns(tmp_path) -> None:
    bad_csv = tmp_path / "bad_arkoma.csv"
    bad_csv.write_text("Px,Py,Pz,joint1\n0.1,0.2,0.3,1.0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="ARKOMA schema missing columns"):
        load_csv_rows(bad_csv)


def test_e50_virtual_effector_roundtrip_to_sensor_echo() -> None:
    row = load_csv_rows(default_fixture_path(), limit=1)[0]
    payload = joint_targets_payload(row)
    request = EffectorRequest(
        trace_id="e50-test-request",
        target_body_id=BODY_ID,
        action_type="set_joint_targets",
        payload=payload,
        source_ide="pytest",
        homeworld_serial="GTH4921YP3",
        ts=2000.0,
    )

    receipt, sensor_echo = execute_request_stub(request, now_ts=2000.1)

    assert receipt["status"] == "ok"
    assert sensor_echo is not None
    assert sensor_echo["body_id"] == BODY_ID
    assert sensor_echo["truth_label"] == "OBSERVED"
    assert sensor_echo["payload"]["robot_model"] == "NAO_H25_v3.3"
    assert sensor_echo["payload"]["joints_rad"] == payload["joints_rad"]