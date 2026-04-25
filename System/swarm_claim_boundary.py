#!/usr/bin/env python3
"""
System/swarm_claim_boundary.py
══════════════════════════════════════════════════════════════════════
Concept: Claim Boundary Gate
Author:  C55M adaptation of external claim-boundary patch (Event 52)
Status:  Active library

Purpose:
  Before a proof, bolus, doc line, or public claim is promoted, force its
  language to match the evidence attached to it. This prevents a proof
  invariant from being inflated into operational claims such as Warp9
  time-sync, vector clocks, or federation causal audit.

Boundary:
  This module gates claims when callers invoke it. It does not by itself
  scan every README line or intercept every Castle bolus path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from System.jsonl_file_lock import append_line_locked


MODULE_VERSION = "2026-04-24.claim-boundary.v1"

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_LEDGER = _REPO / ".sifta_state" / "claim_boundary_decisions.jsonl"

DEFAULT_FORBIDDEN_CLAIMS: Tuple[Tuple[str, str], ...] = (
    ("warp9_time_sync", r"\bwarp\s*9\b|\bwarp9\b|\btime[-\s]?sync(?:hronization)?\b"),
    ("vector_clocks", r"\bvector\s+clocks?\b|\bvector[-_ ]clock(?:s)?\b"),
    (
        "federation_causal_audit",
        r"\bfederat(?:ed|ion)\b.*\bcausal\b|\bcausal\b.*\bfederat(?:ed|ion)\b",
    ),
    (
        "distributed_seq_authority",
        r"\bper[-\s]?node\b.*\bseq(?:uence)?\b|"
        r"\bdistributed\b.*\bseq(?:uence)?\b.*\bauthority\b",
    ),
)

DEFAULT_REQUIRED_EVIDENCE: Mapping[str, Tuple[str, ...]] = {
    "proof_invariant": ("module", "tests", "verified_cases"),
    "operational_sync": ("signed_source_identity", "replay_policy", "clock_model", "seq_authority"),
    "federation_causal_audit": (
        "signed_source_identity",
        "vector_clock_model",
        "replay_policy",
        "node_membership",
    ),
}


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _decision_fingerprint(payload: Mapping[str, Any]) -> str:
    """
    Deterministic decision fingerprint.

    Default is SHA-256 because a public hardcoded HMAC key provides no security.
    Hosts that want an authenticated local decision MAC can set
    SIFTA_CLAIM_BOUNDARY_HMAC_KEY.
    """
    key_raw = os.environ.get("SIFTA_CLAIM_BOUNDARY_HMAC_KEY", "").strip()
    if key_raw:
        return hmac.new(key_raw.encode("utf-8"), _canonical_json(payload), hashlib.sha256).hexdigest()
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def normalize_claim_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip()).lower()


def detect_forbidden_claims(
    claim_text: str,
    forbidden_patterns: Sequence[Tuple[str, str]] = DEFAULT_FORBIDDEN_CLAIMS,
) -> Tuple[str, ...]:
    normalized = normalize_claim_text(claim_text)
    hits: List[str] = []
    for label, pattern in forbidden_patterns:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            hits.append(label)
    return tuple(hits)


def required_evidence_for_scope(
    scope: str,
    required: Mapping[str, Tuple[str, ...]] = DEFAULT_REQUIRED_EVIDENCE,
) -> Tuple[str, ...]:
    return tuple(required.get(scope, ()))


def missing_evidence(scope: str, evidence: Mapping[str, Any]) -> Tuple[str, ...]:
    missing: List[str] = []
    for key in required_evidence_for_scope(scope):
        value = evidence.get(key)
        if value is None or value == "" or value == [] or value == {}:
            missing.append(key)
    return tuple(missing)


@dataclass(frozen=True)
class BoundaryDecision:
    accepted: bool
    status: str
    normalized_claim: str
    requested_scope: str
    allowed_scope: str
    violations: Tuple[str, ...] = field(default_factory=tuple)
    missing_evidence: Tuple[str, ...] = field(default_factory=tuple)
    evidence_hash: str = ""
    decision_hash: str = ""

    def to_ledger_event(self, *, ts: Optional[float] = None) -> Dict[str, Any]:
        data = asdict(self)
        data["event"] = "claim_boundary_decision"
        data["schema"] = "SIFTA_CLAIM_BOUNDARY_DECISION_V1"
        data["module_version"] = MODULE_VERSION
        data["ts"] = float(time.time() if ts is None else ts)
        data["violations"] = list(self.violations)
        data["missing_evidence"] = list(self.missing_evidence)
        return data


def boundary_gate(
    *,
    claim_text: str,
    evidence: Mapping[str, Any],
    requested_scope: str = "proof_invariant",
    allowed_scope: str = "proof_invariant",
) -> BoundaryDecision:
    normalized = normalize_claim_text(claim_text)
    forbidden = detect_forbidden_claims(normalized)
    missing = missing_evidence(requested_scope, evidence)
    violations: List[str] = []

    if requested_scope != allowed_scope:
        violations.append(f"scope_escalation:{requested_scope}>{allowed_scope}")

    if forbidden and requested_scope == "proof_invariant":
        violations.extend(f"forbidden_operational_claim:{label}" for label in forbidden)

    if missing:
        violations.extend(f"missing_evidence:{key}" for key in missing)

    accepted = not violations
    status = "ACCEPT_PROMOTE" if accepted else "REJECT_QUARANTINE"
    evidence_hash = _sha256(dict(evidence))

    unsigned = {
        "accepted": accepted,
        "status": status,
        "normalized_claim": normalized,
        "requested_scope": requested_scope,
        "allowed_scope": allowed_scope,
        "violations": tuple(violations),
        "missing_evidence": tuple(missing),
        "evidence_hash": evidence_hash,
    }
    decision_hash = _decision_fingerprint(unsigned)

    return BoundaryDecision(
        accepted=accepted,
        status=status,
        normalized_claim=normalized,
        requested_scope=requested_scope,
        allowed_scope=allowed_scope,
        violations=tuple(violations),
        missing_evidence=tuple(missing),
        evidence_hash=evidence_hash,
        decision_hash=decision_hash,
    )


def write_claim_boundary_decision(
    decision: BoundaryDecision,
    *,
    ledger_path: Path = _DEFAULT_LEDGER,
    ts: Optional[float] = None,
) -> Dict[str, Any]:
    row = decision.to_ledger_event(ts=ts)
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def time_consensus_event52_claim(evidence: Mapping[str, Any]) -> BoundaryDecision:
    safe_claim = (
        "SIFTA now has a tested pure invariant: logical sequence dominates "
        "wall-clock timestamp under synthetic skew. Status: PROOF INVARIANT, "
        "not operational federation sync."
    )
    return boundary_gate(
        claim_text=safe_claim,
        evidence=evidence,
        requested_scope="proof_invariant",
        allowed_scope="proof_invariant",
    )


if __name__ == "__main__":
    sample = {
        "module": "System/swarm_time_consensus.py",
        "tests": ["tests/test_swarm_quorum_time_ordering.py"],
        "verified_cases": ["logical sequence dominates wall-clock timestamp under synthetic skew"],
    }
    print(time_consensus_event52_claim(sample).to_ledger_event())
