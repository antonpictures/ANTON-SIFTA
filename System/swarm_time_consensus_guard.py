#!/usr/bin/env python3
"""
System/swarm_time_consensus_guard.py
══════════════════════════════════════════════════════════════════════
Boundary layer (not a new organ): hard gate around swarm_time_consensus.

Purpose:
  - Normalize accepted field names (`logical_seq` alias → `seq` for ordering).
  - Reject ambiguous *submissions* before they are silently “healed” by the
    pure sort (duplicate seq claims; unsequenced rows interleaved with sequenced).
  - Emit deterministic ordering fingerprint + append-only audit ledger row.

Explicit non-claims (by design):
  - No vector clocks, no federation transport, no seq authority assignment,
    no distributed conflict merge. Only: given a batch, ordering is
    deterministic and policy-violating batches are flagged.

Optional next hop (Warp9 / federation only):
  - Causal readiness for live payloads: System/swarm_causal_vector_clock.py
    (SwarmVectorClock). Do not fold that into this guard without lifting the
    claim-boundary scope and adding operational evidence.

Fingerprint:
  - Default: SHA256 over concatenated per-row canonical hashes (no repo secret).
  - Optional: set env SIFTA_TIME_CONSENSUS_HMAC_KEY (UTF-8 string) to use
    HMAC-SHA256 for the same concat (host-supplied key material, not hardcoded).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked
from System.swarm_time_consensus import order_events

MODULE_VERSION = "2026-04-24.time-consensus-guard.v1"

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_LEDGER = _REPO / ".sifta_state" / "time_consensus_enforced.jsonl"


def _effective_seq(event: Dict[str, Any]) -> Optional[int]:
    raw = event.get("seq")
    if raw is None:
        raw = event.get("logical_seq")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _normalize_for_resolver(event: Dict[str, Any]) -> Dict[str, Any]:
    n = dict(event)
    if n.get("seq") is None and n.get("logical_seq") is not None:
        n["seq"] = n["logical_seq"]
    return n


def _hash_canonical_row(event: Dict[str, Any]) -> str:
    payload = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _ordering_fingerprint(ordered: List[Dict[str, Any]]) -> str:
    concat = "".join(_hash_canonical_row(e) for e in ordered).encode("utf-8")
    key_raw = os.environ.get("SIFTA_TIME_CONSENSUS_HMAC_KEY", "").strip()
    if key_raw:
        key = key_raw.encode("utf-8")
        return hmac.new(key, concat, hashlib.sha256).hexdigest()
    return hashlib.sha256(concat).hexdigest()


def _violations_conflicting_fields(events: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for i, e in enumerate(events):
        if e.get("seq") is None or e.get("logical_seq") is None:
            continue
        try:
            a, b = int(e["seq"]), int(e["logical_seq"])
        except (TypeError, ValueError):
            continue
        if a != b:
            out.append(f"conflicting_seq_logical_seq@{i}")
    return out


def _violations_duplicate_seq_claims(events: List[Dict[str, Any]]) -> List[str]:
    """Multiple rows claim the same integer seq before resolver collapse."""
    counts: Dict[int, int] = {}
    for e in events:
        s = _effective_seq(e)
        if s is None:
            continue
        counts[s] = counts.get(s, 0) + 1
    return [f"duplicate_seq@{s}" for s, c in counts.items() if c > 1]


def _violations_unsequenced_interleaved(events: List[Dict[str, Any]]) -> List[str]:
    """Sequenced row must not appear after an unsequenced row in the submission."""
    seen_unsequenced = False
    for i, e in enumerate(events):
        if _effective_seq(e) is None:
            seen_unsequenced = True
        elif seen_unsequenced:
            return [f"unsequenced_interleaved@{i}"]
    return []


def _violations_post_order(ordered: List[Dict[str, Any]]) -> List[str]:
    """
    Regression detector: output of order_events must be a sequenced
    prefix (strictly increasing seq) followed by an unsequenced suffix only.
    """
    violations: List[str] = []
    seen_hashes: List[str] = []
    in_suffix = False
    last_seq: Optional[int] = None

    for i, e in enumerate(ordered):
        h = _hash_canonical_row(e)
        if h in seen_hashes:
            violations.append(f"duplicate_row_hash@{i}")
        seen_hashes.append(h)

        s = _effective_seq(e)
        if s is None:
            in_suffix = True
            continue
        if in_suffix:
            violations.append(f"sequenced_after_unsequenced_suffix@{i}")
            continue
        if last_seq is not None and s <= last_seq:
            violations.append(f"seq_non_monotone@{i}")
        last_seq = s

    return violations


@dataclass
class GuardResult:
    ordered_events: List[Dict[str, Any]]
    ordering_hash: str
    invariant_passed: bool
    violations: List[str]


def enforce_time_consensus(
    events: List[Dict[str, Any]],
    *,
    write_ledger: bool = True,
    ledger_path: Optional[Path] = None,
) -> GuardResult:
    """
    Hard gate:
      1) structural violations on the raw batch (duplicate seq, interleaved)
      2) normalize logical_seq → seq for ordering
      3) order_events (pure invariant)
      4) post-order sanity checks
      5) deterministic ordering fingerprint
      6) mandatory audit append (unless write_ledger=False, e.g. unit tests)
    """
    raw_violations: List[str] = []
    raw_violations.extend(_violations_conflicting_fields(events))
    raw_violations.extend(_violations_duplicate_seq_claims(events))
    raw_violations.extend(_violations_unsequenced_interleaved(events))

    normalized = [_normalize_for_resolver(e) for e in events]
    ordered = order_events(normalized)

    post_violations = _violations_post_order(ordered)
    violations = raw_violations + post_violations
    invariant_passed = len(violations) == 0

    fingerprint = _ordering_fingerprint(ordered)

    if write_ledger:
        path = ledger_path if ledger_path is not None else _DEFAULT_LEDGER
        row = {
            "event": "time_consensus_enforced",
            "ordering_hash": fingerprint,
            "invariant_passed": invariant_passed,
            "violations": violations,
            "event_count": len(ordered),
            "ts": time.time(),
        }
        append_line_locked(path, json.dumps(row, sort_keys=True) + "\n")

    return GuardResult(
        ordered_events=ordered,
        ordering_hash=fingerprint,
        invariant_passed=invariant_passed,
        violations=violations,
    )
