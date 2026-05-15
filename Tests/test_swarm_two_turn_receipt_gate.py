"""Fixture-only tests for the two-turn receipt gate.

No API keys. No network. The Voss vibes-problem failure mode is
proven by these tests: **Turn 2 cannot run without Turn 1 on disk.**

Pins:
  - Turn 1 record + Turn 2 require returns the prior receipt.
  - Turn 2 require without Turn 1 record raises PriorReceiptMissingError.
  - Different pipeline_ids do not satisfy each other's gates.
  - The demo_two_turn_pipeline assembles a real report when Turn 1
    is present, and refuses cleanly when Turn 1 is skipped.
  - Receipts carry a sha256 stamp and an append-only history.
  - Idempotent re-record of the same payload still produces a fresh
    trace_id (append-only, never overwrite).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_two_turn_receipt_gate import (  # noqa: E402
    LEDGER_NAME,
    TRUTH_LABEL,
    PriorReceiptMissingError,
    TwoTurnReceiptGate,
    demo_two_turn_pipeline,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "two_turn"


def _load_research_fixture() -> dict:
    return json.loads((FIXTURES / "research_q4_2026.json").read_text(encoding="utf-8"))


# ── gate primitive ────────────────────────────────────────────────────────


def test_gate_record_writes_receipt_with_sha256(tmp_path):
    gate = TwoTurnReceiptGate(pipeline_id="p1", state_dir=tmp_path)
    receipt = gate.record("RESEARCH", {"hello": "world"})
    assert receipt.truth_label == TRUTH_LABEL
    assert len(receipt.sha256) == 64
    assert (tmp_path / LEDGER_NAME).exists()


def test_gate_require_returns_prior_when_present(tmp_path):
    gate = TwoTurnReceiptGate(pipeline_id="p1", state_dir=tmp_path)
    gate.record("RESEARCH", {"x": 1})
    found = gate.require("RESEARCH")
    assert found["turn_id"] == "RESEARCH"
    assert found["pipeline_id"] == "p1"


def test_gate_require_raises_without_prior(tmp_path):
    gate = TwoTurnReceiptGate(pipeline_id="p1", state_dir=tmp_path)
    with pytest.raises(PriorReceiptMissingError) as excinfo:
        gate.require("RESEARCH")
    assert "Turn 2 cannot run without Turn 1" in str(excinfo.value)
    assert excinfo.value.pipeline_id == "p1"


def test_gate_does_not_share_pipelines(tmp_path):
    """A receipt for pipeline A must NOT satisfy a gate for pipeline B."""
    a = TwoTurnReceiptGate(pipeline_id="A", state_dir=tmp_path)
    b = TwoTurnReceiptGate(pipeline_id="B", state_dir=tmp_path)
    a.record("RESEARCH", {"k": "v"})
    with pytest.raises(PriorReceiptMissingError):
        b.require("RESEARCH")


def test_gate_does_not_share_turn_ids(tmp_path):
    gate = TwoTurnReceiptGate(pipeline_id="P", state_dir=tmp_path)
    gate.record("RESEARCH", {"k": "v"})
    with pytest.raises(PriorReceiptMissingError):
        gate.require("WRITE")


def test_gate_record_is_append_only_with_fresh_trace_id(tmp_path):
    gate = TwoTurnReceiptGate(pipeline_id="P", state_dir=tmp_path)
    r1 = gate.record("RESEARCH", {"a": 1})
    r2 = gate.record("RESEARCH", {"a": 1})  # same payload!
    assert r1.trace_id != r2.trace_id  # fresh trace each time
    lines = (tmp_path / LEDGER_NAME).read_text().splitlines()
    assert len(lines) == 2  # both rows present, append-only


def test_gate_payload_sha_is_stable_on_repeat(tmp_path):
    gate = TwoTurnReceiptGate(pipeline_id="P", state_dir=tmp_path)
    r1 = gate.record("RESEARCH", {"a": 1, "b": 2})
    r2 = gate.record("RESEARCH", {"b": 2, "a": 1})  # reordered keys
    assert r1.payload_sha == r2.payload_sha


def test_gate_all_receipts_returns_only_this_pipeline(tmp_path):
    a = TwoTurnReceiptGate(pipeline_id="A", state_dir=tmp_path)
    b = TwoTurnReceiptGate(pipeline_id="B", state_dir=tmp_path)
    a.record("R", {"x": 1})
    b.record("R", {"y": 2})
    assert len(a.all_receipts()) == 1
    assert all(r["pipeline_id"] == "A" for r in a.all_receipts())


def test_gate_turn_id_must_be_non_empty_string(tmp_path):
    gate = TwoTurnReceiptGate(pipeline_id="P", state_dir=tmp_path)
    with pytest.raises(ValueError):
        gate.record("", {"x": 1})


# ── demo pipeline (fixture-only) ──────────────────────────────────────────


def test_demo_pipeline_succeeds_with_fixture(tmp_path):
    fixture = _load_research_fixture()
    out = demo_two_turn_pipeline(
        pipeline_id="financial_q4_2026",
        research_fixture=fixture,
        state_dir=tmp_path,
    )
    assert out["report"]["title"] == "Q4 2026 Mock Financial Report"
    assert out["report"]["evidence_count"] == 3
    assert "research_trace_id" in out["report"]
    # Ledger has two rows: RESEARCH + WRITE
    rows = [
        json.loads(ln)
        for ln in (tmp_path / LEDGER_NAME).read_text().splitlines()
        if ln.strip()
    ]
    assert len(rows) == 2
    assert {r["turn_id"] for r in rows} == {"RESEARCH", "WRITE"}


def test_demo_pipeline_refuses_when_turn_1_skipped(tmp_path):
    """The headline test. Turn 2 MUST refuse when Turn 1 receipt is absent."""
    fixture = _load_research_fixture()
    with pytest.raises(PriorReceiptMissingError) as excinfo:
        demo_two_turn_pipeline(
            pipeline_id="financial_q4_2026",
            research_fixture=fixture,
            skip_turn_1_record=True,
            state_dir=tmp_path,
        )
    assert "Turn 2 cannot run without Turn 1" in str(excinfo.value)
    # No receipts on disk at all (the test passed through the gate, not around it)
    ledger = tmp_path / LEDGER_NAME
    assert not ledger.exists() or ledger.read_text().strip() == ""


def test_demo_pipeline_report_body_references_research_trace_id(tmp_path):
    """Report body must cite the research receipt's trace_id —
    audit trail, not vibes."""
    fixture = _load_research_fixture()
    out = demo_two_turn_pipeline(
        pipeline_id="P",
        research_fixture=fixture,
        state_dir=tmp_path,
    )
    research_trace = out["research_receipt"]["trace_id"]
    assert research_trace in out["report"]["body"]


def test_fixture_payload_is_not_an_api_call():
    """Sanity: the fixture is literal JSON on disk, never fetched."""
    fixture = _load_research_fixture()
    assert fixture["truth_label"] == "FIXTURE_RESEARCH_DATA_V1"
    assert "NOT actual revenue" in fixture["truth_boundary"]
