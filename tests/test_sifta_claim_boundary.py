#!/usr/bin/env python3
"""Tests for System/swarm_claim_boundary.py — claim promotion / quarantine gate."""

import json
from pathlib import Path

from System.canonical_schemas import LEDGER_SCHEMAS
from System.swarm_claim_boundary import (
    boundary_gate,
    detect_forbidden_claims,
    time_consensus_event52_claim,
    write_claim_boundary_decision,
)

EVIDENCE = {
    "module": "System/swarm_time_consensus.py",
    "tests": [
        "tests/test_swarm_quorum_time_ordering.py",
        "tests/test_swarm_time_consensus_guard.py",
    ],
    "verified_cases": [
        "skewed POSIX timestamps cannot override logical seq",
        "duplicate seq collapses deterministically",
        "unsequenced events sort after sequenced events",
        "time consensus guard: raw duplicate-seq and interleaved batches quarantined",
    ],
}


def test_event52_safe_claim_promotes():
    decision = time_consensus_event52_claim(EVIDENCE)
    assert decision.accepted
    assert decision.status == "ACCEPT_PROMOTE"
    assert decision.violations == ()
    assert decision.to_ledger_event()["event"] == "claim_boundary_decision"
    assert decision.to_ledger_event()["requested_scope"] == "proof_invariant"


def test_warp9_overclaim_is_quarantined_under_proof_scope():
    decision = boundary_gate(
        claim_text="Warp9 time-sync is implemented by this invariant.",
        evidence=EVIDENCE,
        requested_scope="proof_invariant",
        allowed_scope="proof_invariant",
    )
    assert not decision.accepted
    assert "forbidden_operational_claim:warp9_time_sync" in decision.violations


def test_vector_clock_and_federation_claims_are_detected():
    hits = detect_forbidden_claims(
        "Vector clocks and federation causal audit are live now."
    )
    assert "vector_clocks" in hits
    assert "federation_causal_audit" in hits


def test_scope_escalation_without_operational_evidence_rejected():
    decision = boundary_gate(
        claim_text="Operational federation causal audit is live.",
        evidence=EVIDENCE,
        requested_scope="federation_causal_audit",
        allowed_scope="proof_invariant",
    )
    assert not decision.accepted
    assert "scope_escalation:federation_causal_audit>proof_invariant" in decision.violations
    assert "missing_evidence:signed_source_identity" in decision.violations
    assert "missing_evidence:vector_clock_model" in decision.violations


def test_decision_hash_is_deterministic_and_changes_with_evidence():
    a = time_consensus_event52_claim(EVIDENCE)
    b = time_consensus_event52_claim(dict(reversed(list(EVIDENCE.items()))))
    assert a.decision_hash == b.decision_hash

    changed = dict(EVIDENCE)
    changed["verified_cases"] = EVIDENCE["verified_cases"] + ["extra"]
    c = time_consensus_event52_claim(changed)
    assert a.decision_hash != c.decision_hash


def test_claim_boundary_ledger_row_matches_schema(tmp_path: Path):
    decision = time_consensus_event52_claim(EVIDENCE)
    ledger = tmp_path / "claim_boundary_decisions.jsonl"

    row = write_claim_boundary_decision(decision, ledger_path=ledger, ts=123.0)

    assert set(row.keys()) == LEDGER_SCHEMAS["claim_boundary_decisions.jsonl"]
    assert row["event"] == "claim_boundary_decision"
    assert row["schema"] == "SIFTA_CLAIM_BOUNDARY_DECISION_V1"
    assert row["accepted"] is True
    assert row["ts"] == 123.0
    assert json.loads(ledger.read_text(encoding="utf-8").strip()) == row


def test_claim_boundary_registered_for_oncology():
    from System.swarm_oncology import SwarmOncology

    assert "claim_boundary_decisions.jsonl" in LEDGER_SCHEMAS
    assert "claim_boundary_decisions.jsonl" in SwarmOncology().healthy_schemas
