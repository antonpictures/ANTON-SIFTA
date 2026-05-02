"""Event 99 — multi-prover *agreement* ledger (MIP-inspired, not MIP*).

Several agents append structured claims; ``verify_claims`` groups by
``claim_hash`` (SHA-256 fingerprint of the claim string — content addressing
only, **not** an STGM/finance seal; use ``System.crypto_keychain`` for those).

**Verdict:** quorum over *independent agents* agreeing on the same claim text.
This proves **agreement under deposited evidence**, not mathematical truth.

Truth labels on rows: ``MULTI_PROVER_CLAIM``, ``MULTI_PROVER_VERDICT``.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

BUNDLE_ID = "BISHOP_BUNDLE_QUANTUM_SACK_2026_05_01"
BUNDLE_VERSION = "2026-05-01"

DEFAULT_STATE = Path(".sifta_state")
CLAIMS_NAME = "multi_prover_claims.jsonl"
VERDICTS_NAME = "multi_prover_verdicts.jsonl"


@dataclass(frozen=True)
class MultiProverLedgerPaths:
    """Injectable paths for pytest (tmp dirs) or custom state roots."""

    claims: Path
    verdicts: Path

    @staticmethod
    def default(state_dir: Path | None = None) -> MultiProverLedgerPaths:
        root = state_dir if state_dir is not None else DEFAULT_STATE
        return MultiProverLedgerPaths(
            claims=root / CLAIMS_NAME,
            verdicts=root / VERDICTS_NAME,
        )


def bishop_bundle_quantum_sack_manifest() -> dict[str, Any]:
    """Static manifest pointing at Documents/BISHOP_BUNDLE_QUANTUM_SACK_2026_05_01.md."""
    return {
        "name": BUNDLE_ID,
        "version": BUNDLE_VERSION,
        "entries": 10,
        "truth_labels": ("OBSERVED", "INTERPRETATION", "CONJECTURE"),
        "doc": "Documents/BISHOP_BUNDLE_QUANTUM_SACK_2026_05_01.md",
        "usage": (
            "Quorum agreement on claim_hash across agents; "
            "pair with pytest + signed traces for tournament routing / RLHF quarantine."
        ),
    }


def hash_claim(claim: str) -> str:
    return hashlib.sha256(claim.encode("utf-8")).hexdigest()


def submit_claim(
    agent: str,
    claim: str,
    proof: Mapping[str, Any] | dict[str, Any],
    *,
    paths: MultiProverLedgerPaths | None = None,
) -> dict[str, Any]:
    """Append one prover row; ``proof`` must be JSON-serializable."""
    ledgers = paths or MultiProverLedgerPaths.default()
    row = {
        "ts": time.time(),
        "truth_label": "MULTI_PROVER_CLAIM",
        "agent": agent,
        "claim": claim,
        "claim_hash": hash_claim(claim),
        "proof": dict(proof),
    }
    ledgers.claims.parent.mkdir(parents=True, exist_ok=True)
    with ledgers.claims.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    return row


def read_recent_claims(
    n: int = 10,
    *,
    paths: MultiProverLedgerPaths | None = None,
) -> list[dict[str, Any]]:
    ledgers = paths or MultiProverLedgerPaths.default()
    if not ledgers.claims.is_file():
        return []
    lines = ledgers.claims.read_text(encoding="utf-8").splitlines()[-n:]
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def verify_claims(
    *,
    paths: MultiProverLedgerPaths | None = None,
    agreement_threshold: float = 0.66,
    min_supporters: int = 2,
    tail: int = 200,
) -> dict[str, Any]:
    """Pick the largest claim_hash group in the recent tail; emit verdict row."""
    ledgers = paths or MultiProverLedgerPaths.default()
    claims = read_recent_claims(tail, paths=ledgers)
    if not claims:
        return {"status": "no_claims", "truth_label": "MULTI_PROVER_VERDICT"}

    groups: dict[str, list[dict[str, Any]]] = {}
    for row in claims:
        groups.setdefault(row["claim_hash"], []).append(row)

    claim_hash, supporters = max(groups.items(), key=lambda kv: len(kv[1]))
    agreement = len(supporters) / max(1, len(claims))
    unique_agents = {s["agent"] for s in supporters}
    accept = (
        agreement >= agreement_threshold
        and len(supporters) >= min_supporters
        and len(unique_agents) >= min_supporters
    )
    verdict = {
        "ts": time.time(),
        "truth_label": "MULTI_PROVER_VERDICT",
        "claim_hash": claim_hash,
        "claim": supporters[0]["claim"],
        "supporters": [s["agent"] for s in supporters],
        "unique_agents": sorted(unique_agents),
        "agreement": agreement,
        "verdict": "ACCEPT" if accept else "REJECT",
        "params": {
            "agreement_threshold": agreement_threshold,
            "min_supporters": min_supporters,
        },
    }
    ledgers.verdicts.parent.mkdir(parents=True, exist_ok=True)
    with ledgers.verdicts.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(verdict, sort_keys=True) + "\n")
    return verdict


__all__ = [
    "BUNDLE_ID",
    "BUNDLE_VERSION",
    "MultiProverLedgerPaths",
    "bishop_bundle_quantum_sack_manifest",
    "hash_claim",
    "read_recent_claims",
    "submit_claim",
    "verify_claims",
]
