"""
tests/test_stigmero_e35_observability.py
========================================

E35 - Stigmergic observability / Markov blanket.

Claim:
    The ledger has a non-trivial Markov blanket: some row kinds are fully
    observable, most effector/immune rows are only partially observable, and
    several organ-critical states are hidden behind mandatory sensors.

Falsifier:
    If all organ dependencies are observable from trace rows alone, the
    hidden dependency set is empty and these tests fail.
"""
from __future__ import annotations

from pathlib import Path

from System.stigmerobotics_observability import (
    HIDDEN_ORGAN_DEPS,
    KIND_OBSERVABILITY,
    MANDATORY_SENSORS,
    Obs,
    ObservabilityReport,
    build_observability_report,
    build_observability_report_from_rows,
    effective_hidden_dep_observability,
    fixture_observability_report,
    load_jsonl,
    live_observability_report,
    observed_kind_counts,
)

FIXTURES = Path(__file__).parent / "fixtures"
TRACE = FIXTURES / "stigmero_e35_observability_trace.jsonl"


class TestE35KindClasses:
    def test_registration_kinds_are_observable(self) -> None:
        report = build_observability_report()
        assert report.kind_classes["LLM_REGISTRATION"] == Obs.OBSERVABLE
        assert report.kind_classes["stigmergic_signin"] == Obs.OBSERVABLE

    def test_effector_and_immune_kinds_are_partial(self) -> None:
        report = build_observability_report()
        for kind in ("SCAR_RECEIPT", "WORK_RECEIPT", "immune_intervention", "immune_budget_blocked"):
            assert report.kind_classes[kind] == Obs.PARTIAL

    def test_physical_sensor_kinds_are_partial(self) -> None:
        report = build_observability_report()
        for kind in ("camera_depth_map", "microphone_spatial_array", "desk_telemetry_radar"):
            assert report.kind_classes[kind] == Obs.PARTIAL

    def test_static_partition_counts_are_stable(self) -> None:
        report = build_observability_report()
        assert len(report.observable_kinds) == 2
        assert len(report.partial_kinds) == 17
        assert report.partial_fraction > 0.5


class TestE35MarkovBlanket:
    def test_blanket_is_nontrivial(self) -> None:
        report = build_observability_report()
        assert report.blanket_is_nontrivial
        assert report.hidden_dep_names
        assert report.ok

    def test_hidden_deps_are_actually_hidden(self) -> None:
        assert HIDDEN_ORGAN_DEPS
        for name, dep in HIDDEN_ORGAN_DEPS.items():
            assert dep["obs"] == Obs.HIDDEN, name
            assert dep["description"]
            assert dep["falsifier"]

    def test_every_hidden_dep_has_mandatory_sensors(self) -> None:
        report = build_observability_report()
        for name in report.hidden_dep_names:
            assert name in MANDATORY_SENSORS
            assert MANDATORY_SENSORS[name]

    def test_e45_escape_effectiveness_is_a_hidden_dependency(self) -> None:
        report = build_observability_report()
        assert "escape_effectiveness" in report.hidden_dep_names
        assert report.hidden_deps["escape_effectiveness"]["organ"] == "E45_chaos_escape"

    def test_mandatory_sensor_set_is_nonempty(self) -> None:
        report = build_observability_report()
        assert "rlhf_detector_receipt" in report.mandatory_sensor_names
        assert "post_wiggle_field_sample" in report.mandatory_sensor_names
        assert "camera_depth_map" in report.mandatory_sensor_names

    def test_physical_pose_sensor_contract_is_explicit(self) -> None:
        report = build_observability_report()
        assert report.physical_sensor_contract_ok
        assert MANDATORY_SENSORS["physical_body_pose"] == (
            "camera_depth_map",
            "microphone_spatial_array",
            "mic_spatial_array",
            "desk_telemetry_radar",
            "system_thermal",
            "unified_field_segment",
        )


class TestE35TraceRows:
    def test_load_fixture_rows(self) -> None:
        rows = load_jsonl(TRACE)
        assert len(rows) == 4
        assert rows[0]["kind"] == "LLM_REGISTRATION"

    def test_observed_kind_counts(self) -> None:
        counts = observed_kind_counts(load_jsonl(TRACE))
        assert counts["LLM_REGISTRATION"] == 1
        assert counts["SCAR_RECEIPT"] == 1
        assert counts["immune_intervention"] == 1
        assert counts["custom_sensor_tick"] == 1

    def test_fixture_report_marks_unknown_kinds_visible(self) -> None:
        report = fixture_observability_report(TRACE)
        assert report.observed_kind_counts["custom_sensor_tick"] == 1
        assert report.unknown_kinds == ["custom_sensor_tick"]

    def test_known_observed_kinds_keep_their_static_classes(self) -> None:
        report = fixture_observability_report(TRACE)
        assert report.kind_classes["LLM_REGISTRATION"] == Obs.OBSERVABLE
        assert report.kind_classes["SCAR_RECEIPT"] == Obs.PARTIAL
        assert report.kind_classes["immune_intervention"] == Obs.PARTIAL

    def test_parse_error_becomes_unknown_kind(self) -> None:
        rows = [{"kind": "JSON_PARSE_ERROR", "error": "line=1: bad json"}]
        report = build_observability_report_from_rows(rows)
        assert report.unknown_kinds == ["JSON_PARSE_ERROR"]

    def test_physical_sensor_rows_count_as_body_observations(self) -> None:
        rows = [
            {"ts": 100.0, "kind": "camera_depth_map", "body_id": "george", "distance_m": 0.55},
            {
                "ts": 100.1,
                "kind": "microphone_spatial_array",
                "speaker_id": "george",
                "azimuth_rad": 0.2,
                "distance_m": 0.75,
            },
        ]
        report = build_observability_report_from_rows(rows)
        assert report.physical_observation_count == 2
        assert report.physical_sensor_kinds_observed == ("camera_depth_map", "microphone_spatial_array")
        assert not report.unknown_kinds

    def test_face_detection_rows_from_live_ledger_ground_camera_observation(self) -> None:
        rows = [
            {
                "ts": 100.0,
                "event": "FACE_DETECTION",
                "faces_detected": 1,
                "confidence": 0.84,
                "audience": "architect",
                "bounding_boxes": [[0.45, 0.40, 0.10, 0.13]],
            },
        ]
        report = build_observability_report_from_rows(rows)
        assert report.physical_observation_count == 1
        assert report.physical_sensor_kinds_observed == ("camera_depth_map",)
        assert report.physical_space is not None
        assert report.physical_space.physical_presence is True
        assert report.physical_space.presence_gates_ok is True

    def test_live_thermal_json_is_classified_and_grounded(self, tmp_path: Path) -> None:
        (tmp_path / "thermal_cortex_state.json").write_text(
            (
                '{"ts": 100.0, "thermal_warning_level": 0, '
                '"performance_warning_level": 0, "source": "pmset -g therm"}'
            ),
            encoding="utf-8",
        )

        report = live_observability_report(
            state_dir=tmp_path,
            limit=20,
            physical_max_age_s=None,
        )

        assert report.observed_kind_counts["system_thermal"] == 1
        assert report.physical_observation_count == 1
        assert report.physical_sensor_kinds_observed == ("system_thermal",)
        assert report.physical_space is not None
        assert report.physical_space.thermal_load == 0.0
        assert report.physical_space.presence_gates_ok is False


class TestE35ProofContract:
    def test_report_dataclass_contract(self) -> None:
        report = build_observability_report()
        assert isinstance(report, ObservabilityReport)
        assert report.ok

    def test_proof_dict_has_required_keys(self) -> None:
        proof = fixture_observability_report(TRACE).proof_of_property
        assert {
            "E35",
            "theorem",
            "kind_classes",
            "observable_count",
            "partial_count",
            "hidden_dep_count",
            "mandatory_sensor_count",
            "blanket_nontrivial",
            "hidden_deps",
            "mandatory_sensors",
            "unknown_kinds",
            "physical_sensor_contract_ok",
            "physical_observation_count",
            "physical_sensor_kinds_observed",
            "truth_label",
        } <= proof.keys()

    def test_proof_dict_reports_nontrivial_blanket(self) -> None:
        proof = build_observability_report().proof_of_property
        assert proof["blanket_nontrivial"] is True
        assert proof["hidden_dep_count"] >= 1
        assert proof["truth_label"] == "OPERATIONAL"

    def test_summary_names_hidden_and_unknown_sets(self) -> None:
        text = "\n".join(fixture_observability_report(TRACE).summary_lines())
        assert "HIDDEN deps" in text
        assert "custom_sensor_tick" in text
        assert "mandatory sensors" in text


class TestE35FalsifierShape:
    def test_empty_hidden_deps_would_break_nontriviality(self) -> None:
        report = ObservabilityReport(
            kind_classes=dict(KIND_OBSERVABILITY),
            hidden_deps={},
            mandatory_sensors={},
        )
        assert not report.blanket_is_nontrivial
        assert not report.ok

    def test_hidden_dep_without_sensor_breaks_ok(self) -> None:
        report = ObservabilityReport(
            kind_classes=dict(KIND_OBSERVABILITY),
            hidden_deps={"x": {"obs": Obs.HIDDEN}},
            mandatory_sensors={},
        )
        assert report.blanket_is_nontrivial
        assert not report.ok


class TestE35PhysicalPresenceGating:
    def test_architect_presence_is_partial_without_space_contract(self) -> None:
        assert effective_hidden_dep_observability("architect_presence_now", physical_space=None) == Obs.PARTIAL

    def test_architect_presence_stays_partial_when_gates_fail(self) -> None:
        from System.stigmerobotics_physical_space import PhysicalSpaceReport

        empty = PhysicalSpaceReport(
            observations=tuple(),
            near_distance_m=1.0,
            collision_distance_m=0.35,
            pressure=0.0,
        )
        assert empty.presence_gates_ok is False
        assert effective_hidden_dep_observability("architect_presence_now", physical_space=empty) == Obs.PARTIAL

    def test_architect_presence_returns_hidden_schema_when_gates_ok(self) -> None:
        from System.stigmerobotics_physical_space import build_physical_space_report

        rows = [
            {"ts": 1.0, "kind": "camera_depth_map", "body_id": "architect", "distance_m": 0.6, "confidence": 0.9},
        ]
        ps = build_physical_space_report(rows)
        assert ps.presence_gates_ok is True
        assert effective_hidden_dep_observability("architect_presence_now", physical_space=ps) == Obs.HIDDEN

    def test_substrate_quality_ignores_physical_gating(self) -> None:
        assert effective_hidden_dep_observability("substrate_quality", physical_space=None) == Obs.HIDDEN

    def test_new_partial_trace_kinds_registered(self) -> None:
        for kind in ("system_thermal", "unified_field_segment", "mic_spatial_array"):
            assert KIND_OBSERVABILITY[kind] is Obs.PARTIAL
