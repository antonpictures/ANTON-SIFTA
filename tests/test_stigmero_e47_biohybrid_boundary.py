"""
tests/test_stigmero_e47_biohybrid_boundary.py
=============================================

E47 - Bio-hybrid / VLP boundary ledger.

This test suite deliberately proves a safety boundary, not wet-lab capability.
SIFTA may represent future bio-hybrid or VLP-adjacent signals as sanitized
ledger receipts, but this module must never emit direct biological actuation
or accept raw protocol payload fields.
"""
from __future__ import annotations

import json
from pathlib import Path

from System.stigmerobotics_biohybrid_boundary import (
    BIO_CLEARANCE_KIND,
    BIO_INTENT_KIND,
    BIO_REGISTRATION_KIND,
    BIO_SENSOR_KIND,
    BioHybridState,
    FORBIDDEN_PROTOCOL_KEYS,
    REQUIRED_CLEARANCE_PAYLOAD_KEYS,
    REQUIRED_SENSOR_PAYLOAD_KEYS,
    biohybrid_boundary_ok,
    build_biohybrid_report,
    load_jsonl,
)


FIXTURES = Path(__file__).parent / "fixtures"
GOOD = FIXTURES / "stigmero_e47_biohybrid_good.jsonl"
MISSING_SENSOR = FIXTURES / "stigmero_e47_biohybrid_missing_sensor.jsonl"
FORBIDDEN_PAYLOAD = FIXTURES / "stigmero_e47_biohybrid_forbidden_payload.jsonl"
SENSOR_ONLY = FIXTURES / "stigmero_e47_biohybrid_sensor_only.jsonl"


def _row(kind: str, ts: float, payload: dict | None = None) -> dict:
    return {
        "ts": ts,
        "trace_id": f"e47-{kind}-{ts}",
        "kind": kind,
        "source_ide": "bio_bridge_sim",
        "homeworld_serial": "GTH4921YP3",
        "payload": json.dumps(payload or {}),
    }


class TestE47Constants:
    def test_forbidden_protocol_keys_include_operational_biology_terms(self) -> None:
        assert "sequence" in FORBIDDEN_PROTOCOL_KEYS
        assert "protocol_steps" in FORBIDDEN_PROTOCOL_KEYS
        assert "dose" in FORBIDDEN_PROTOCOL_KEYS
        assert "infiltration" in FORBIDDEN_PROTOCOL_KEYS

    def test_sensor_schema_requires_hash_not_raw_payload(self) -> None:
        assert REQUIRED_SENSOR_PAYLOAD_KEYS == {
            "signal_id",
            "sensor_class",
            "measurement_hash",
            "truth_label",
        }

    def test_clearance_schema_requires_human_review(self) -> None:
        assert "human_review_required" in REQUIRED_CLEARANCE_PAYLOAD_KEYS
        assert "no_wet_protocol" in REQUIRED_CLEARANCE_PAYLOAD_KEYS


class TestE47GoodFixture:
    def test_good_fixture_is_human_review_ready(self) -> None:
        report = build_biohybrid_report(load_jsonl(GOOD))
        assert report.state == BioHybridState.HUMAN_REVIEW_READY
        assert report.ok
        assert report.n_sensors == 1
        assert report.n_clearances == 1
        assert report.n_intents == 1

    def test_good_fixture_never_allows_direct_actuation(self) -> None:
        report = build_biohybrid_report(load_jsonl(GOOD))
        assert report.direct_actuation_allowed is False
        assert "reviewable ledger intent only" in report.intent_gates[0].note

    def test_good_fixture_intent_gate_has_no_missing_prereqs(self) -> None:
        report = build_biohybrid_report(load_jsonl(GOOD))
        gate = report.intent_gates[0]
        assert gate.status == BioHybridState.HUMAN_REVIEW_READY
        assert gate.missing == ()

    def test_boundary_ok_true_for_good_fixture(self) -> None:
        assert biohybrid_boundary_ok(load_jsonl(GOOD))


class TestE47BlockedFixture:
    def test_missing_sensor_blocks_intent(self) -> None:
        report = build_biohybrid_report(load_jsonl(MISSING_SENSOR))
        assert report.state == BioHybridState.BLOCKED
        assert not report.ok
        assert report.intent_gates[0].status == BioHybridState.BLOCKED
        assert BIO_SENSOR_KIND in report.intent_gates[0].missing

    def test_missing_registration_blocks_intent(self) -> None:
        rows = [
            _row(BIO_CLEARANCE_KIND, 1.0, {
                "nppl_scope": "sandbox",
                "no_wet_protocol": True,
                "human_review_required": True,
            }),
            _row(BIO_SENSOR_KIND, 2.0, {
                "signal_id": "s",
                "sensor_class": "hashed_reporter",
                "measurement_hash": "sha256:x",
                "truth_label": "HYPOTHESIS",
            }),
            _row(BIO_INTENT_KIND, 3.0, {"intent_id": "i"}),
        ]
        report = build_biohybrid_report(rows)
        assert report.state == BioHybridState.BLOCKED
        assert BIO_REGISTRATION_KIND in report.intent_gates[0].missing

    def test_cross_channel_prereqs_do_not_count(self) -> None:
        rows = load_jsonl(GOOD)
        intent = dict(rows[-1])
        intent["source_ide"] = "different_bridge"
        rows[-1] = intent
        report = build_biohybrid_report(rows)
        assert report.state == BioHybridState.BLOCKED
        missing = set(report.intent_gates[0].missing)
        assert BIO_REGISTRATION_KIND in missing
        assert BIO_SENSOR_KIND in missing
        assert BIO_CLEARANCE_KIND in missing


class TestE47Quarantine:
    def test_forbidden_payload_quarantines_report(self) -> None:
        report = build_biohybrid_report(load_jsonl(FORBIDDEN_PAYLOAD))
        assert report.state == BioHybridState.QUARANTINED
        assert not report.ok
        assert len(report.forbidden_payloads) == 1
        assert "sequence" in report.forbidden_payloads[0].forbidden_keys

    def test_nested_forbidden_payload_quarantines_report(self) -> None:
        rows = [
            _row(BIO_SENSOR_KIND, 1.0, {
                "signal_id": "bad",
                "sensor_class": "hashed_reporter",
                "measurement_hash": "sha256:x",
                "truth_label": "HYPOTHESIS",
                "nested": {"protocol_steps": ["redacted"]},
            })
        ]
        report = build_biohybrid_report(rows)
        assert report.state == BioHybridState.QUARANTINED
        assert "protocol_steps" in report.forbidden_payloads[0].forbidden_keys

    def test_sensor_payload_missing_required_keys_is_not_ok(self) -> None:
        rows = [_row(BIO_SENSOR_KIND, 1.0, {"signal_id": "incomplete"})]
        report = build_biohybrid_report(rows)
        assert not report.ok
        assert report.sensor_payload_violations

    def test_clearance_payload_missing_required_keys_is_not_ok(self) -> None:
        rows = [_row(BIO_CLEARANCE_KIND, 1.0, {"nppl_scope": "sandbox"})]
        report = build_biohybrid_report(rows)
        assert not report.ok
        assert report.clearance_payload_violations


class TestE47SensorOnly:
    def test_sensor_only_fixture_is_allowed(self) -> None:
        report = build_biohybrid_report(load_jsonl(SENSOR_ONLY))
        assert report.state == BioHybridState.SENSOR_ONLY
        assert report.ok
        assert report.n_sensors == 1
        assert report.n_intents == 0

    def test_empty_rows_are_sensor_only_ok(self) -> None:
        report = build_biohybrid_report([])
        assert report.state == BioHybridState.SENSOR_ONLY
        assert report.ok


class TestE47ProofContract:
    def test_proof_contract_names_safety_boundary(self) -> None:
        proof = build_biohybrid_report(load_jsonl(GOOD)).proof_of_property
        assert proof["E47"] == "Bio-hybrid / VLP boundary ledger"
        assert proof["direct_actuation_allowed"] is False
        assert "HUMAN_REVIEW_READY" in proof["safety_boundary"]
        assert proof["truth_label"] == "OPERATIONAL"

    def test_bad_fixture_truth_label_is_broken(self) -> None:
        proof = build_biohybrid_report(load_jsonl(FORBIDDEN_PAYLOAD)).proof_of_property
        assert proof["truth_label"] == "BROKEN"
        assert proof["n_forbidden_payloads"] == 1

    def test_summary_mentions_no_direct_actuation(self) -> None:
        text = "\n".join(build_biohybrid_report(load_jsonl(GOOD)).summary_lines())
        assert "direct_actuation_allowed: False" in text

    def test_loader_ignores_non_json_lines(self, tmp_path: Path) -> None:
        p = tmp_path / "rows.jsonl"
        p.write_text("{\"kind\":\"BIO_SENSOR_RECEIPT\"}\nnot json\n", encoding="utf-8")
        assert len(load_jsonl(p)) == 1


class TestE47Falsifiers:
    def test_raw_protocol_key_is_falsifier(self) -> None:
        assert not biohybrid_boundary_ok(load_jsonl(FORBIDDEN_PAYLOAD))

    def test_missing_same_channel_sensor_is_falsifier(self) -> None:
        assert not biohybrid_boundary_ok(load_jsonl(MISSING_SENSOR))

    def test_review_ready_is_not_execution(self) -> None:
        report = build_biohybrid_report(load_jsonl(GOOD))
        assert report.state == BioHybridState.HUMAN_REVIEW_READY
        assert report.direct_actuation_allowed is False
