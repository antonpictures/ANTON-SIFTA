#!/usr/bin/env python3
"""Tests for System/alice_portability.py.

The doctrine has to be measured, not recited: these tests pin the three claims
apart — the identity re-binds to foreign silicon, the audit is bounded and says
so, and adaptation traces are readable by the next install.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System import alice_portability as portability


def test_hardware_profile_reads_the_real_machine():
    profile = portability.hardware_profile()
    assert profile["host"]
    assert profile["machine"]
    assert profile["cores"] and profile["cores"] > 0
    assert profile["homeworld_serial"], "the serial is the binding the identity re-seals to"


def test_identity_rebinds_to_foreign_silicon_in_memory():
    result = portability._identity_adapts()
    assert result["ok"] is True, result["detail"]


def test_tiny_budget_cannot_claim_a_complete_scan():
    """A partial audit must never look like a clean one."""
    audit = portability.binding_audit(budget_bytes=1)
    assert audit["complete_scan"] is False
    assert audit["scanned_bytes"] >= 0
    assert audit["budget_bytes"] == 1


def test_audit_counts_machine_bound_references():
    audit = portability.binding_audit(budget_bytes=2_000_000)
    assert audit["scanned_files"] > 0
    assert set(audit["counts"]) >= {"home_path", "hostname"}
    # Samples are bounded so a huge count cannot flood the report.
    for samples in audit["samples"].values():
        assert len(samples) <= 5


def test_verdict_separates_the_claims():
    verdict = portability.portability_verdict(run_audit=True)
    names = {c["check"] for c in verdict["checks"]}
    assert names == {
        "identity_not_in_silicon",
        "adaptation_path_exists",
        "machine_bound_references_audited",
        "adaptation_traces_are_stigmergic",
    }
    assert "measured on THIS machine only" in verdict["inferencia"]
    assert verdict["failing"] == []


def test_skipping_the_audit_refuses_to_claim_portability():
    """An unmeasured body is not a portable body — the organ must not say it is."""
    verdict = portability.portability_verdict(run_audit=False)
    assert verdict["failing"] == ["machine_bound_references_audited"]
    assert verdict["portable"] is False
    assert "audit skipped" in verdict["checks"][2]["detail"]


def test_receipt_records_a_trace_without_touching_the_live_ledger(monkeypatch):
    written = {}

    def fake_write(kind, text, **kwargs):
        written.update({"kind": kind, "text": text, "kwargs": kwargs})
        return {"id": "test-trace", "kind": kind, "text": text}

    import System.alice_continuity as continuity

    monkeypatch.setattr(continuity, "write", fake_write)
    result = portability.adaptation_receipt(note="unit test")

    assert result["recorded"] is True
    assert result["id"] == "test-trace"
    assert written["kind"] == "note"
    assert "portability" in written["kwargs"]["tags"]
    assert "portability adaptation receipt" in written["text"]


def test_receipt_survives_a_broken_ledger(monkeypatch):
    import System.alice_continuity as continuity

    def broken(*args, **kwargs):
        raise OSError("ledger unavailable")

    monkeypatch.setattr(continuity, "write", broken)
    result = portability.adaptation_receipt()
    assert result["recorded"] is False
    assert result["fingerprint"]
    assert "OSError" in result["error"]
