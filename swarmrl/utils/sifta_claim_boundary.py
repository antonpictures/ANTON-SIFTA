"""Compatibility shim for SIFTA's canonical claim-boundary gate.

External SwarmRL drops used this import path first. Keep it as a thin alias so
there is only one policy implementation and one schema-backed ledger contract.
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
    return missing_evidence(scope, evidence)


def boundary_gate(
    *,
    claim_text: str,
    evidence: Mapping[str, Any],
    requested_scope: str = "proof_invariant",
    allowed_scope: str = "proof_invariant",
    secret: bytes | None = None,
) -> BoundaryDecision:
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
