"""
tests/test_stigmero_e33_pheromone_field.py
==========================================

E33 - Pheromone field formalisation (STIGMEROBOTICS).

Claim:
    A sanitized trace tail can be interpreted as an evaporating pheromone
    field: positive deposits, positive tau values, nonnegative field
    intensity, monotonic evaporation, and visible same-channel cross-IDE
    collision risk.

No live .sifta_state reads. Fixtures are hand-crafted and sanitized.
"""
from __future__ import annotations

from pathlib import Path

from System.stigmerobotics_pheromone_field import (
    DEFAULT_TAU_S,
    CollisionSignal,
    PheromoneFieldReport,
    extract_deposits,
    field_report,
    fixture_pheromone_field,
    intensity_at,
    load_jsonl,
    pheromone_evaporation_ok,
)

FIXTURES = Path(__file__).parent / "fixtures"
GOOD = FIXTURES / "stigmero_e33_pheromone_good.jsonl"
BAD_TAU = FIXTURES / "stigmero_e33_pheromone_bad_tau.jsonl"
FUTURE = FIXTURES / "stigmero_e33_pheromone_future.jsonl"
NOW = 1_778_100_600.0


class TestE33TauTable:
    def test_tau_table_is_positive(self) -> None:
        assert DEFAULT_TAU_S
        for kind, tau_s in DEFAULT_TAU_S.items():
            assert tau_s > 0.0, f"{kind} tau must be positive"

    def test_extract_deposits_preserves_positive_tau_and_strength(self) -> None:
        deposits, violations = extract_deposits(load_jsonl(GOOD))
        assert not violations
        assert len(deposits) == 6
        assert all(d.tau_s > 0.0 for d in deposits)
        assert all(d.strength > 0.0 for d in deposits)

    def test_bad_tau_is_machine_detected(self) -> None:
        report = field_report(load_jsonl(BAD_TAU), now_ts=NOW)
        assert not report.ok
        assert any("invalid_tau_s" in item for item in report.violations)


class TestE33Evaporation:
    def test_good_fixture_evaporation_ok(self) -> None:
        assert pheromone_evaporation_ok(load_jsonl(GOOD), now_ts=NOW)

    def test_field_report_is_operational(self) -> None:
        report = fixture_pheromone_field(GOOD, now_ts=NOW)
        assert isinstance(report, PheromoneFieldReport)
        assert report.ok
        assert report.proof_of_property["truth_label"] == "OPERATIONAL"
        assert report.proof_of_property["tau_table_positive"] is True
        assert report.proof_of_property["field_nonnegative"] is True

    def test_total_intensity_decreases_after_dt(self) -> None:
        report = fixture_pheromone_field(GOOD, now_ts=NOW)
        assert report.total_intensity > 0.0
        assert report.total_intensity_after_dt < report.total_intensity

    def test_individual_deposit_evaporates_monotonically(self) -> None:
        deposits, _ = extract_deposits(load_jsonl(GOOD))
        for deposit in deposits:
            assert intensity_at(deposit, NOW + 60.0) <= intensity_at(deposit, NOW)

    def test_field_intensity_is_nonnegative(self) -> None:
        report = fixture_pheromone_field(GOOD, now_ts=NOW)
        assert all(value >= 0.0 for value in report.field.values())
        assert all(value >= 0.0 for value in report.field_after_dt.values())

    def test_future_deposit_breaks_property(self) -> None:
        report = field_report(load_jsonl(FUTURE), now_ts=NOW)
        assert not report.ok
        assert any("future_deposit" in item for item in report.violations)


class TestE33DepositRate:
    def test_deposit_rate_is_positive_for_nonempty_tail(self) -> None:
        report = fixture_pheromone_field(GOOD, now_ts=NOW)
        assert report.deposit_rate_per_hour > 0.0

    def test_empty_field_has_zero_rate_and_zero_intensity(self) -> None:
        report = field_report([], now_ts=NOW)
        assert report.ok
        assert report.deposit_rate_per_hour == 0.0
        assert report.total_intensity == 0.0
        assert report.total_intensity_after_dt == 0.0


class TestE33CollisionMetric:
    def test_same_channel_cross_ide_collision_is_visible(self) -> None:
        report = fixture_pheromone_field(GOOD, now_ts=NOW)
        assert report.collision_signals
        assert report.collision_risk > 0.0
        signal = report.collision_signals[0]
        assert isinstance(signal, CollisionSignal)
        assert signal.left_source != signal.right_source
        assert signal.channel == "file:System/stigmerobotics_pheromone_field.py"
        assert signal.gap_s == 30.0

    def test_same_ide_same_channel_is_not_collision(self) -> None:
        rows = [
            {
                "trace_id": "a",
                "ts": NOW - 30.0,
                "kind": "SCAR_RECEIPT",
                "source_ide": "codex_desktop",
                "homeworld_serial": "GTH4921YP3",
                "payload": '{"files_touched":["same.py"]}',
            },
            {
                "trace_id": "b",
                "ts": NOW - 15.0,
                "kind": "SCAR_RECEIPT",
                "source_ide": "codex_desktop",
                "homeworld_serial": "GTH4921YP3",
                "payload": '{"files_touched":["same.py"]}',
            },
        ]
        report = field_report(rows, now_ts=NOW)
        assert report.ok
        assert report.collision_risk == 0.0
        assert not report.collision_signals

    def test_different_channel_cross_ide_is_not_collision(self) -> None:
        rows = [
            {
                "trace_id": "a",
                "ts": NOW - 30.0,
                "kind": "SCAR_RECEIPT",
                "source_ide": "codex_desktop",
                "homeworld_serial": "GTH4921YP3",
                "payload": '{"files_touched":["left.py"]}',
            },
            {
                "trace_id": "b",
                "ts": NOW - 15.0,
                "kind": "SCAR_RECEIPT",
                "source_ide": "cursor_m5",
                "homeworld_serial": "GTH4921YP3",
                "payload": '{"files_touched":["right.py"]}',
            },
        ]
        report = field_report(rows, now_ts=NOW)
        assert report.ok
        assert report.collision_risk == 0.0


class TestE33ProofOfProperty:
    def test_proof_dict_has_required_keys(self) -> None:
        report = fixture_pheromone_field(GOOD, now_ts=NOW)
        proof = report.proof_of_property
        assert {
            "P_n",
            "tau_table_positive",
            "field_nonnegative",
            "evaporation",
            "deposit_rate_per_hour",
            "collision_risk",
            "truth_label",
        } <= proof.keys()

    def test_summary_mentions_top_channels(self) -> None:
        report = fixture_pheromone_field(GOOD, now_ts=NOW)
        text = "\n".join(report.summary_lines())
        assert "top channels" in text
        assert "collision_risk" in text
