"""
tests/test_stigmero_e45_chaos_escape.py
=======================================

E45 - Variable chaos / bounded wiggle escape.

Claim:
    When the E33 pheromone field is overloaded by collision risk or total
    intensity, SIFTA can inject a deterministic bounded wiggle vector. The
    wiggle is a recommendation only: it never writes a row and never actuates.

Falsifier:
    Any wiggle exceeds max_amplitude, a calm field receives nonzero wiggle,
    or a malformed field is treated as safe.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from System.stigmerobotics_chaos_escape import (
    DEFAULT_MAX_AMPLITUDE,
    ChaosEscapeDecision,
    chaos_escape_decision,
    chaos_escape_from_rows,
    deterministic_wiggle,
    fixture_chaos_escape,
)
from System.stigmerobotics_pheromone_field import field_report, load_jsonl

FIXTURES = Path(__file__).parent / "fixtures"
HIGH_COLLISION = FIXTURES / "stigmero_e45_chaos_high_collision.jsonl"
CALM = FIXTURES / "stigmero_e45_chaos_calm.jsonl"
BAD_TAU = FIXTURES / "stigmero_e45_bad_tau.jsonl"


class TestE45HighCollision:
    def test_high_collision_triggers_chaos_escape(self) -> None:
        decision = fixture_chaos_escape(HIGH_COLLISION, now_ts=1020.0)
        assert decision.mode == "CHAOS_ESCAPE"
        assert decision.action == "YIELD_OR_REROUTE_COLLIDING_WRITERS"
        assert decision.collision_risk > 0.45

    def test_high_collision_has_positive_bounded_amplitude(self) -> None:
        decision = fixture_chaos_escape(HIGH_COLLISION, now_ts=1020.0)
        assert 0.0 < decision.amplitude <= DEFAULT_MAX_AMPLITUDE

    def test_every_wiggle_is_within_bound(self) -> None:
        decision = fixture_chaos_escape(HIGH_COLLISION, now_ts=1020.0)
        assert decision.wiggles
        for item in decision.wiggles:
            assert abs(item.wiggle) <= decision.amplitude + 1e-12

    def test_same_seed_is_deterministic(self) -> None:
        rows = load_jsonl(HIGH_COLLISION)
        a = chaos_escape_from_rows(rows, now_ts=1020.0, seed="fixed")
        b = chaos_escape_from_rows(rows, now_ts=1020.0, seed="fixed")
        assert a.wiggles == b.wiggles

    def test_different_seed_changes_at_least_one_wiggle(self) -> None:
        rows = load_jsonl(HIGH_COLLISION)
        a = chaos_escape_from_rows(rows, now_ts=1020.0, seed="fixed-a")
        b = chaos_escape_from_rows(rows, now_ts=1020.0, seed="fixed-b")
        assert [w.wiggle for w in a.wiggles] != [w.wiggle for w in b.wiggles]


class TestE45CalmAndIntensity:
    def test_calm_field_keeps_gradient(self) -> None:
        decision = chaos_escape_from_rows(
            load_jsonl(CALM),
            now_ts=1001.0,
            collision_threshold=100.0,
            intensity_threshold=100.0,
        )
        assert decision.mode == "CALM"
        assert decision.action == "KEEP_GRADIENT"
        assert decision.amplitude == 0.0
        assert all(w.wiggle == 0.0 for w in decision.wiggles)

    def test_intensity_threshold_triggers_wiggle_without_collision(self) -> None:
        decision = chaos_escape_from_rows(
            load_jsonl(CALM),
            now_ts=1001.0,
            collision_threshold=100.0,
            intensity_threshold=0.1,
            seed="intensity",
        )
        assert decision.mode == "WIGGLE"
        assert decision.action == "INJECT_BOUNDED_WIGGLE"
        assert decision.collision_risk == 0.0
        assert decision.amplitude > 0.0

    def test_pressure_controls_amplitude_monotonically(self) -> None:
        rows = load_jsonl(HIGH_COLLISION)
        low = chaos_escape_from_rows(rows, now_ts=1020.0, collision_threshold=2.0, seed="x")
        high = chaos_escape_from_rows(rows, now_ts=1020.0, collision_threshold=0.2, seed="x")
        assert low.pressure < high.pressure
        assert low.amplitude <= high.amplitude


class TestE45PhysicalSpace:
    def test_near_camera_body_triggers_physical_space_escape(self) -> None:
        rows = [
            {
                "ts": 1000.0,
                "kind": "LLM_REGISTRATION",
                "homeworld_serial": "GTH4921YP3",
                "source_ide": "ag_m5",
                "trace_id": "reg",
            },
            {
                "ts": 1000.1,
                "kind": "camera_depth_map",
                "body_id": "george",
                "distance_m": 0.40,
                "pose_confidence": 1.0,
                "trace_id": "cam",
            },
        ]

        decision = chaos_escape_from_rows(
            rows,
            now_ts=1001.0,
            collision_threshold=100.0,
            intensity_threshold=100.0,
            seed="physical",
        )

        assert decision.mode == "PHYSICAL_SPACE_ESCAPE"
        assert decision.action == "YIELD_OR_REROUTE_AROUND_MOVING_BODY"
        assert decision.physical_pressure > 1.0
        assert decision.physical_observation_count == 1
        assert decision.physical_sensor_kinds == ("camera_depth_map",)
        assert decision.nearest_body_distance_m == 0.4
        assert decision.amplitude > 0.0

    def test_far_physical_body_does_not_add_pressure(self) -> None:
        rows = [
            {
                "ts": 1000.0,
                "kind": "desk_telemetry_radar",
                "body_id": "far_body",
                "distance_m": 3.0,
                "sensor_confidence": 1.0,
            }
        ]

        decision = chaos_escape_from_rows(
            rows,
            now_ts=1001.0,
            collision_threshold=100.0,
            intensity_threshold=100.0,
        )

        assert decision.mode == "CALM"
        assert decision.physical_pressure == 0.0
        assert decision.physical_observation_count == 1


class TestE45MalformedField:
    def test_bad_tau_freezes_instead_of_wiggling(self) -> None:
        decision = fixture_chaos_escape(BAD_TAU, now_ts=1001.0)
        assert decision.mode == "FROZEN"
        assert decision.action == "FREEZE_AND_REPAIR_FIELD"
        assert decision.amplitude == 0.0
        assert decision.violations

    def test_invalid_threshold_is_a_violation(self) -> None:
        report = field_report(load_jsonl(CALM), now_ts=1001.0)
        decision = chaos_escape_decision(report, collision_threshold=0.0)
        assert not decision.ok
        assert "collision_threshold_must_be_positive" in decision.violations

    def test_negative_max_amplitude_is_a_violation(self) -> None:
        report = field_report(load_jsonl(CALM), now_ts=1001.0)
        decision = chaos_escape_decision(report, max_amplitude=-1.0)
        assert not decision.ok
        assert "max_amplitude_must_be_nonnegative" in decision.violations


class TestE45ProofContract:
    def test_proof_dict_has_required_shape(self) -> None:
        proof = fixture_chaos_escape(HIGH_COLLISION, now_ts=1020.0).proof_of_property
        assert {
            "E45",
            "trigger",
            "mode",
            "action",
            "pressure",
            "physical_pressure",
            "physical_observation_count",
            "physical_sensor_kinds",
            "nearest_body_distance_m",
            "amplitude",
            "max_amplitude",
            "bounded",
            "deterministic_seed",
            "truth_label",
        } <= proof.keys()

    def test_proof_dict_reports_bounded_true(self) -> None:
        proof = fixture_chaos_escape(HIGH_COLLISION, now_ts=1020.0).proof_of_property
        assert proof["bounded"] is True
        assert proof["truth_label"] == "OPERATIONAL"

    def test_summary_names_mode_and_action(self) -> None:
        decision = fixture_chaos_escape(HIGH_COLLISION, now_ts=1020.0)
        text = "\n".join(decision.summary_lines())
        assert "CHAOS_ESCAPE" in text
        assert "YIELD_OR_REROUTE_COLLIDING_WRITERS" in text


class TestE45Primitive:
    @pytest.mark.parametrize("amplitude", [0.0, 0.01, 0.25, 1.0])
    def test_deterministic_wiggle_never_exceeds_requested_amplitude(self, amplitude: float) -> None:
        value = deterministic_wiggle("file:System/test.py", "seed", amplitude)
        assert abs(value) <= amplitude + 1e-12

    def test_decision_is_dataclass_contract(self) -> None:
        decision = fixture_chaos_escape(HIGH_COLLISION, now_ts=1020.0)
        assert isinstance(decision, ChaosEscapeDecision)
        assert decision.ok
