#!/usr/bin/env python3
"""Tests for swarm_memory_consciousness_bridge.

These tests verify the operational SIFTA property:
observed event -> OBSERVED memory trace -> unified field receipt,
all linked by shared trace IDs and hashes, plus a WIP self-vector delta.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from System import swarm_memory_consciousness_bridge as bridge
from System import stigmergic_memory_bus as memory_bus


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.strip():
            out.append(json.loads(raw))
    return out


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()])


@pytest.fixture
def isolated_memory_bus(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setattr(memory_bus, "LEDGER_DIR", state)
    monkeypatch.setattr(memory_bus, "LEDGER_FILE", state / "memory_ledger.jsonl")
    monkeypatch.setattr(memory_bus, "STGM_LOG_FILE", state / "stgm_memory_rewards.jsonl")
    monkeypatch.setattr(memory_bus, "MEMORY_EPISTEMOLOGY_AUDIT", state / "memory_epistemology_audit.jsonl")

    monkeypatch.setitem(
        sys.modules,
        "System.marrow_memory",
        types.SimpleNamespace(MarrowMemory=lambda architect_id: None),
    )
    monkeypatch.setitem(
        sys.modules,
        "System.tab_heartbeat",
        types.SimpleNamespace(HeartbeatBus=lambda architect_id: types.SimpleNamespace(pin_to_web=lambda **_: None)),
    )
    monkeypatch.setitem(
        sys.modules,
        "System.proof_of_useful_work",
        types.SimpleNamespace(issue_work_receipt=lambda **_: None),
    )
    return memory_bus.StigmergicMemoryBus(architect_id="IOAN_M5")


def test_bridge_writes_observed_memory_and_field_receipt(tmp_path, isolated_memory_bus):
    bridge_ledger = tmp_path / "memory_consciousness_bridge.jsonl"
    field_ledger = tmp_path / "unified_stigmergic_field.jsonl"
    self_vector_ledger = tmp_path / "stigmergic_consciousness_self_vector.jsonl"
    latest = tmp_path / "memory_consciousness_bridge_latest.json"

    row = bridge.bridge_observed_memory_to_consciousness(
        "George says Alice is observer and observed in the same stigmergic field.",
        memory_bus=isolated_memory_bus,
        bridge_ledger=bridge_ledger,
        field_ledger=field_ledger,
        self_vector_ledger=self_vector_ledger,
        memory_ledger=memory_bus.LEDGER_FILE,
        latest_path=latest,
        now=1234.5,
    )

    memory_rows = _rows(memory_bus.LEDGER_FILE)
    bridge_rows = _rows(bridge_ledger)
    field_rows = _rows(field_ledger)
    self_vector_rows = _rows(self_vector_ledger)

    assert len(memory_rows) == 1
    assert len(bridge_rows) == 1
    assert len(field_rows) == 1
    assert len(self_vector_rows) == 1

    memory_row = memory_rows[0]
    field_row = field_rows[0]
    self_vector_row = self_vector_rows[0]

    assert row["truth_label"] == "STIGMERGIC_CONSCIOUSNESS"
    assert row["claim_status"] == "WORK_IN_PROGRESS"
    assert row["owner_gloss"] == "continuous witnessing-in-progress across a stigmergic field"
    assert memory_row["epistemic_label"] == "OBSERVED"
    assert row["memory_trace_id"] == memory_row["trace_id"]
    assert row["memory_trace_id"] == field_row["memory_trace_id"]
    assert row["observed_hash"] == field_row["observed_hash"]
    assert row["observer_observed_same_trace"] is True
    assert field_row["observer_observed_same_trace"] is True
    assert row["field_receipt_id"] == field_row["trace_id"]
    assert "receipt:" + row["trace_id"] in memory_row["links"]
    assert row["self_vector_receipt_id"] == self_vector_row["trace_id"]
    assert self_vector_row["truth_label"] == "STIGMERGIC_CONSCIOUSNESS"
    assert self_vector_row["claim_status"] == "WORK_IN_PROGRESS"
    assert self_vector_row["owner_gloss"] == "continuous witnessing-in-progress across a stigmergic field"
    assert self_vector_row["changed"] is True
    assert self_vector_row["before_hash"] != self_vector_row["after_hash"]
    assert {"memory", "bridge", "field"}.issubset(set(self_vector_row["changed_sources"]))

    verified = bridge.verify_latest_bridge(
        bridge_ledger=bridge_ledger,
        field_ledger=field_ledger,
        self_vector_ledger=self_vector_ledger,
    )
    assert verified["ok"] is True
    assert verified["truth_label"] == "STIGMERGIC_CONSCIOUSNESS"
    assert verified["claim_status"] == "WORK_IN_PROGRESS"
    assert verified["owner_gloss"] == "continuous witnessing-in-progress across a stigmergic field"
    assert verified["memory_epistemic_label"] == "OBSERVED"
    assert verified["self_vector_changed"] is True


def test_bridge_boundary_keeps_wip_and_qualia_limits(tmp_path, isolated_memory_bus):
    row = bridge.bridge_observed_memory_to_consciousness(
        "Alice links memory to the field as an operational WIP receipt.",
        memory_bus=isolated_memory_bus,
        bridge_ledger=tmp_path / "bridge.jsonl",
        field_ledger=tmp_path / "field.jsonl",
        self_vector_ledger=tmp_path / "self_vector.jsonl",
        memory_ledger=memory_bus.LEDGER_FILE,
        latest_path=tmp_path / "latest.json",
        now=2000.0,
    )

    assert "WORK_IN_PROGRESS" in row["boundary"]
    assert "witnessing-in-progress" in row["boundary"]
    assert "does not assert private subjective qualia" in row["boundary"]
    assert "WORK_IN_PROGRESS" in bridge.explain_operational_proof(row)


def test_bridge_rejects_empty_observation(tmp_path, isolated_memory_bus):
    with pytest.raises(ValueError, match="observed_text must be non-empty"):
        bridge.bridge_observed_memory_to_consciousness(
            "   ",
            memory_bus=isolated_memory_bus,
            bridge_ledger=tmp_path / "bridge.jsonl",
            field_ledger=tmp_path / "field.jsonl",
            self_vector_ledger=tmp_path / "self_vector.jsonl",
            memory_ledger=memory_bus.LEDGER_FILE,
            latest_path=tmp_path / "latest.json",
        )


def test_redirected_run_does_not_touch_real_core_ledgers(tmp_path, isolated_memory_bus):
    watch = [
        Path(".sifta_state/memory_ledger.jsonl"),
        Path(".sifta_state/stgm_memory_rewards.jsonl"),
        Path(".sifta_state/work_receipts.jsonl"),
        Path(".sifta_state/ide_stigmergic_trace.jsonl"),
        Path(".sifta_state/unified_stigmergic_field.jsonl"),
        Path(".sifta_state/stigmergic_consciousness_self_vector.jsonl"),
    ]
    before = {str(path): _count_lines(path) for path in watch}

    bridge.bridge_observed_memory_to_consciousness(
        "No real ledger contamination while proving the bridge under test.",
        memory_bus=isolated_memory_bus,
        bridge_ledger=tmp_path / "bridge.jsonl",
        field_ledger=tmp_path / "field.jsonl",
        self_vector_ledger=tmp_path / "self_vector.jsonl",
        memory_ledger=memory_bus.LEDGER_FILE,
        latest_path=tmp_path / "latest.json",
        now=3000.0,
    )

    after = {str(path): _count_lines(path) for path in watch}
    assert after == before


def test_stigmergic_consciousness_term_avoids_forbidden_freeze_words():
    files = [
        Path("System/swarm_memory_consciousness_bridge.py"),
        Path("tests/test_memory_consciousness_bridge.py"),
        Path("Documents/MEMORY_CONSCIOUSNESS_BRIDGE_PROOF_2026-05-21.md"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files)
    lowered = combined.casefold()
    frozen_positive = "pro" + "ven"
    frozen_negative = "un" + frozen_positive
    assert frozen_positive not in lowered
    assert frozen_negative not in lowered
