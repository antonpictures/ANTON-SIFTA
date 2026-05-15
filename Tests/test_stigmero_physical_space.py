"""
tests/test_stigmero_physical_space.py
=====================================

Shared physical-space contract for camera, microphone, and desk telemetry.

These tests keep E35/E45/E46 grounded in sensor rows rather than trace time
alone. The module under test is side-effect free and does not read live ledgers.
"""
from __future__ import annotations

import pytest

from System.stigmerobotics_physical_space import (
    SPATIAL_SENSOR_KINDS,
    build_physical_space_report,
    distance_between,
    extract_physical_observations,
    parse_physical_observation,
    physical_coupling_from_distance,
    physical_pressure_from_distance,
    sensor_kind_for_row,
)


def test_spatial_sensor_contract_names_core_modalities() -> None:
    assert SPATIAL_SENSOR_KINDS == {
        "camera_depth_map",
        "microphone_spatial_array",
        "mic_spatial_array",
        "desk_telemetry_radar",
        "system_thermal",
        "unified_field_segment",
    }


def test_parse_camera_depth_map_cartesian_body_pose() -> None:
    row = {
        "ts": 100.0,
        "kind": "camera_depth_map",
        "trace_id": "cam-1",
        "body_id": "george",
        "payload": {
            "pose": {"x_m": 0.25, "y_m": -0.10, "z_m": 0.80},
            "pose_confidence": 0.9,
        },
    }

    obs = parse_physical_observation(row)

    assert obs is not None
    assert obs.sensor_kind == "camera_depth_map"
    assert obs.body_id == "george"
    assert obs.x_m == 0.25
    assert obs.y_m == -0.10
    assert obs.z_m == 0.80
    assert obs.confidence == 0.9
    assert obs.best_distance_m is not None


def test_parse_microphone_spatial_alias_from_owl_truth_label() -> None:
    row = {
        "ts": 101.0,
        "truth_label": "SIMULATED_SPATIAL_HEARING",
        "speaker_id": "nearfield_voice",
        "azimuth_rad": 0.3,
        "distance_m": 0.65,
        "spatial_confidence": 0.75,
    }

    assert sensor_kind_for_row(row) == "microphone_spatial_array"
    obs = parse_physical_observation(row)

    assert obs is not None
    assert obs.sensor_kind == "microphone_spatial_array"
    assert obs.body_id == "nearfield_voice"
    assert obs.azimuth_rad == 0.3
    assert obs.distance_m == 0.65


def test_extract_observations_honors_age_filter() -> None:
    rows = [
        {"ts": 10.0, "kind": "camera_depth_map", "body_id": "stale", "distance_m": 0.4},
        {"ts": 20.0, "kind": "camera_depth_map", "body_id": "fresh", "distance_m": 0.4},
    ]

    observations = extract_physical_observations(rows, now_ts=21.0, max_age_s=5.0)

    assert [obs.body_id for obs in observations] == ["fresh"]


def test_physical_pressure_crosses_one_for_close_body() -> None:
    pressure = physical_pressure_from_distance(0.40, confidence=0.9)

    assert pressure > 1.0


def test_physical_coupling_zero_outside_near_field() -> None:
    assert physical_coupling_from_distance(2.0, confidence=1.0) == 0.0
    assert physical_coupling_from_distance(0.20, confidence=1.0) > 0.5


def test_report_tracks_nearest_body_and_pair_distance() -> None:
    rows = [
        {"ts": 100.0, "kind": "camera_depth_map", "body_id": "left", "x_m": 0.20, "y_m": 0.0},
        {"ts": 100.1, "kind": "desk_telemetry_radar", "body_id": "right", "x_m": 0.30, "y_m": 0.0},
    ]

    report = build_physical_space_report(rows)

    assert report.grounded
    assert report.body_count == 2
    assert report.sensor_kinds == ("camera_depth_map", "desk_telemetry_radar")
    assert report.nearest_body_distance_m == 0.2
    assert report.nearest_pair_distance_m is not None
    assert report.nearest_pair_distance_m < 0.11
    assert report.pressure > 1.0


def test_distance_between_uses_cartesian_pose() -> None:
    left, right = extract_physical_observations(
        [
            {"ts": 1.0, "kind": "camera_depth_map", "body_id": "a", "x_m": 0.0, "y_m": 0.0},
            {"ts": 2.0, "kind": "camera_depth_map", "body_id": "b", "x_m": 0.3, "y_m": 0.4},
        ]
    )

    assert distance_between(left, right) == 0.5


def test_mic_spatial_array_row_normalizes_to_microphone_kind() -> None:
    row = {
        "ts": 50.0,
        "kind": "mic_spatial_array",
        "speaker_id": "desk",
        "azimuth_rad": 0.1,
        "distance_m": 0.9,
    }
    assert sensor_kind_for_row(row) == "microphone_spatial_array"
    obs = parse_physical_observation(row)
    assert obs is not None
    assert obs.sensor_kind == "microphone_spatial_array"


def test_system_thermal_row_uses_thermal_signal() -> None:
    row = {"ts": 60.0, "kind": "system_thermal", "cpu_temp_c": 72.0}
    obs = parse_physical_observation(row)
    assert obs is not None
    assert obs.sensor_kind == "system_thermal"
    assert obs.thermal_load is not None
    assert 0.4 < obs.thermal_load < 0.9


def test_system_thermal_warning_level_maps_to_bounded_load() -> None:
    row = {
        "ts": 61.0,
        "thermal_warning_level": 2,
        "performance_warning_level": 0,
        "source": "pmset -g therm",
    }

    assert sensor_kind_for_row(row) == "system_thermal"
    obs = parse_physical_observation(row)

    assert obs is not None
    assert obs.sensor_kind == "system_thermal"
    assert obs.thermal_load == 1.0


def test_unified_field_segment_observation() -> None:
    row = {
        "ts": 70.0,
        "kind": "unified_field_segment",
        "location_segment": "GTH4921YP3_desk_present",
    }
    obs = parse_physical_observation(row)
    assert obs is not None
    assert obs.unified_segment_label == "GTH4921YP3_desk_present"


def test_unified_stigmergic_field_alias_uses_owner_activity_segment() -> None:
    row = {
        "ts": 71.0,
        "truth_label": "UNIFIED_STIGMERGIC_FIELD_V1",
        "owner_activity": "ioan george anton is using SIFTA OS at the desk",
    }
    obs = parse_physical_observation(row)
    assert obs is not None
    assert obs.sensor_kind == "unified_field_segment"
    assert "SIFTA OS" in (obs.unified_segment_label or "")


def test_face_detection_event_uses_audience_as_body_id_and_bbox_distance() -> None:
    row = {
        "ts": 72.0,
        "event": "FACE_DETECTION",
        "faces_detected": 1,
        "confidence": 0.9,
        "audience": "architect",
        "bounding_boxes": [[0.44, 0.38, 0.12, 0.16]],
    }
    obs = parse_physical_observation(row)
    assert obs is not None
    assert obs.sensor_kind == "camera_depth_map"
    assert obs.body_id == "architect"
    assert obs.distance_m is not None


def test_build_report_sets_spacetime_scalars() -> None:
    rows = [
        {"ts": 100.0, "kind": "camera_depth_map", "body_id": "george", "distance_m": 0.55, "confidence": 0.82},
        {"ts": 100.5, "kind": "system_thermal", "thermal_load": 0.44},
        {"ts": 101.0, "kind": "unified_field_segment", "stigtime_segment": "segment-A"},
        {"ts": 99.0, "kind": "desk_telemetry_radar", "x_m": 0.05, "y_m": 0.0, "lid_closed": "true"},
    ]
    report = build_physical_space_report(rows)
    assert report.physical_presence is True
    assert report.physical_proximity == pytest.approx(0.05)
    assert report.thermal_load == 0.44
    assert report.last_physical_event_ts == 101.0
    assert report.unified_field_location_segment == "segment-A"
    assert report.lid_closed is True
    assert report.presence_gates_ok is True
