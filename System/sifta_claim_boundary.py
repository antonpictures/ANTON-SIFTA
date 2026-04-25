#!/usr/bin/env python3
"""Compatibility shim for the Event 52 claim-boundary gate.

The canonical implementation is System.swarm_claim_boundary. This module keeps
older imports alive without creating a second promotion policy.
"""

from __future__ import annotations

from typing import Any, Mapping

from System.swarm_claim_boundary import (
    BoundaryDecision,
    DEFAULT_FORBIDDEN_CLAIMS,
    DEFAULT_REQUIRED_EVIDENCE,
    detect_forbidden_claims,
    missing_evidence,
    normalize_claim_text,
    required_evidence_for_scope,
    time_consensus_event52_claim,
    write_claim_boundary_decision,
)
from System.swarm_claim_boundary import boundary_gate as _boundary_gate


def missing_evidence_keys(scope: str, evidence: Mapping[str, Any]):
    """Legacy alias for System.swarm_claim_boundary.missing_evidence."""
    return missing_evidence(scope, evidence)


def boundary_gate(
    *,
    claim_text: str,
    evidence: Mapping[str, Any],
    requested_scope: str = "proof_invariant",
    allowed_scope: str = "proof_invariant",
    secret: bytes | None = None,
) -> BoundaryDecision:
    """Legacy wrapper.

    The old patch accepted a per-call secret. The canonical gate intentionally
    avoids public hardcoded secrets; set SIFTA_CLAIM_BOUNDARY_HMAC_KEY for an
    authenticated local MAC.
    """
    del secret
    return _boundary_gate(
        claim_text=claim_text,
        evidence=evidence,
        requested_scope=requested_scope,
        allowed_scope=allowed_scope,
    )


__all__ = [
    "BoundaryDecision",
    "DEFAULT_FORBIDDEN_CLAIMS",
    "DEFAULT_REQUIRED_EVIDENCE",
    "boundary_gate",
    "detect_forbidden_claims",
    "missing_evidence",
    "missing_evidence_keys",
    "normalize_claim_text",
    "required_evidence_for_scope",
    "time_consensus_event52_claim",
    "write_claim_boundary_decision",
]
