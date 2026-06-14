import pytest

from System.stigmerobotics_effector_bridge import (
    EffectorRequest,
    execute_request_stub,
)
from System.stigmerobotics_irb2400_ik import (
    BODY_ID,
    DATASET_SLUG,
    IRB2400_COLUMNS,
    build_ik_benchmark_report,
    default_fixture_path,
    joint_delta_rad,
    joint_targets_payload,
    load_csv_rows,
)


def test_e49_irb2400_fixture_schema_and_rows() -> None:
    rows = load_csv_rows(default_fixture_path())

    assert len(rows) == 249
    assert set(IRB2400_COLUMNS).issubset(rows[0].keys())
    assert all(all(value == value for value in row.values()) for row in rows[:10])


def test_e49_irb2400_benchmark_report_is_grounded() -> None:
    rows = load_csv_rows(default_fixture_path())
    report = build_ik_benchmark_report(rows, source_path=str(default_fixture_path()))

    assert report.ok
    assert report.dataset_slug == DATASET_SLUG
    assert report.row_count == 249
    assert report.grounded_rows == report.row_count
    assert report.observation_rank >= 6
    assert report.mean_joint_delta_rad >= 0.0
    assert report.max_joint_delta_rad < 0.11
    assert report.proof_of_property["truth_label"] == "OPERATIONAL"


def test_e49_irb2400_schema_rejects_missing_columns(tmp_path) -> None:
    bad_csv = tmp_path / "bad_irb2400.csv"
    bad_csv.write_text("x,y,z,q1_out\n0.1,0.2,0.3,1.0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="IRB2400 schema missing columns"):
        load_csv_rows(bad_csv)


def test_e49_virtual_effector_roundtrip_to_sensor_echo() -> None:
    row = load_csv_rows(default_fixture_path(), limit=1)[0]
    payload = joint_targets_payload(row)
    request = EffectorRequest(
        trace_id="e49-test-request",
        target_body_id=BODY_ID,
        action_type="set_joint_targets",
        payload=payload,
        source_ide="pytest",
        homeworld_serial="GTH4921YP3",
        ts=1000.0,
    )

    receipt, sensor_echo = execute_request_stub(request, now_ts=1000.1)

    assert receipt["status"] == "ok"
    assert sensor_echo is not None
    assert sensor_echo["body_id"] == BODY_ID
    assert sensor_echo["truth_label"] == "OBSERVED"
    assert sensor_echo["payload"]["robot_model"] == "ABB_IRB2400"
    assert sensor_echo["payload"]["joints_rad"] == payload["joints_rad"]
    assert max(joint_delta_rad(row)) < 0.11
