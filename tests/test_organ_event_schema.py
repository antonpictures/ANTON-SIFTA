"""Tests for ORGAN_EVENT_V1 envelope (System/organ_event_schema.py)."""

from __future__ import annotations

import uuid

import pytest

from System import organ_event_schema as oes


def test_schema_file_loads():
    data = oes.load_schema_json()
    assert data.get("title")
    assert "required" in data
    assert "ts" in data["required"]


def test_build_and_validate_golden():
    row = oes.build_organ_event(
        source="test",
        homeworld_serial="GTH4921YP3",
        organ="octopus",
        event_type="state_update",
        payload={"coherence": 0.25},
        truth_label="OPERATIONAL",
        mark_schema=True,
    )
    assert row["schema"] == oes.OPTIONAL_SCHEMA_LITERAL
    assert not oes.validate_organ_event_base(row)


def test_truth_label_doctrine():
    row = oes.build_organ_event(
        source="test",
        homeworld_serial="GTH4921YP3",
        organ="x",
        event_type="claim",
        payload={},
        truth_label="architect doctrine",
    )
    assert row["truth_label"] == "ARCHITECT_DOCTRINE"


def test_missing_keys():
    errs = oes.validate_organ_event_base({"ts": 1.0})
    assert any("missing key" in e for e in errs)


def test_bad_truth_label():
    with pytest.raises(ValueError):
        oes.build_organ_event(
            source="a",
            homeworld_serial="GTH4921YP3",
            organ="o",
            event_type="e",
            payload={},
            truth_label="FANFIC",
        )


def test_non_uuid_trace_id_rejected():
    with pytest.raises(ValueError):
        oes.build_organ_event(
            source="a",
            homeworld_serial="GTH4921YP3",
            organ="o",
            event_type="e",
            payload={},
            truth_label="OBSERVED",
            trace_id="not-a-uuid",
        )


def test_custom_uuid_trace_ok():
    tid = str(uuid.uuid4())
    row = oes.build_organ_event(
        source="a",
        homeworld_serial="GTH4921YP3",
        organ="o",
        event_type="e",
        payload={},
        truth_label="OBSERVED",
        trace_id=tid,
    )
    assert row["trace_id"] == tid


def test_proof_of_property():
    r = oes.proof_of_property()
    assert r["ok"] is True
    assert not r["errors"]
