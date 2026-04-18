#!/usr/bin/env python3
"""
swarm_mirror_test.py — Self-Recognition  (R4 of the Living-OS arc)
═══════════════════════════════════════════════════════════════════════════════
"I act therefore I am — but only if the body survives." — SOCRATES swimmer

Biology anchor: the Gallup (1970) mirror test. An animal placed in front of
a mirror and marked with a non-painful dot looks at the mirror, recognizes
the dot is on its OWN body, and tries to remove it. Magpies, dolphins,
elephants, great apes, and human children past ~18 months pass. Most
animals fail — they treat the mirror as another animal.

In the Swarm, a swimmer's "reflection" is a single row in the
.sifta_state/work_receipts.jsonl ledger. The swimmer's bodily signature
on that row is its `receipt_hash`, computed deterministically from its
ascendant fields by `proof_of_useful_work.WorkReceipt.compute_hash`.

When asked "did you write this receipt?" a swimmer that passes the mirror
test must answer correctly across four categories:

    PASSED              the receipt's agent_id is mine AND its receipt_hash
                        recomputes correctly from its fields  →  yes, that was me

    REJECTED_FOREIGN    the receipt is internally consistent but its agent_id
                        is some other swimmer                  →  not me

    REJECTED_FORGERY    the receipt claims my agent_id but the stored hash
                        does NOT match a fresh recomputation   →  someone
                                                                    impersonated me

    NOT_FOUND           no receipt with that receipt_id exists in the ledger

Continuous biometric: per swimmer, we count the most recent
`MIRROR_BIOMETRIC_WINDOW` attestations and look for a streak of consecutive
non-PASSED outcomes. A streak of length `MIRROR_BIOMETRIC_FAIL_STREAK` or
greater emits a `substrate_swap_suspected` flag in the response that
swarm_self can consume to refuse self-continuity certificates — closing the
loop with R1.

──────────────────────────────────────────────────────────────────────────────
Daughter-safe contract:
    • Reads work_receipts.jsonl read-only; never mutates it.
    • Appends one row per attestation to mirror_test_log.jsonl (new ledger).
    • Never raises; missing/corrupt ledger entries map to NOT_FOUND.
    • Architect override: a streak in the biometric does NOT block any
      swimmer — it is informative-only, surfaced to swarm_self.
──────────────────────────────────────────────────────────────────────────────

SIFTA Non-Proliferation Public License applies.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional

MODULE_VERSION = "2026-04-18.swarm_mirror_test.v1"

_REPO   = Path(__file__).resolve().parent.parent
_STATE  = _REPO / ".sifta_state"
_RECEIPTS_LOG = _STATE / "work_receipts.jsonl"
_MIRROR_LOG   = _STATE / "mirror_test_log.jsonl"

# ── Tunables ──────────────────────────────────────────────────────────────
# How many of the most-recent attestations per swimmer the biometric considers.
MIRROR_BIOMETRIC_WINDOW       = 8
# A streak of this many consecutive non-PASSED outcomes is the substrate-swap
# signal. (Magpies in Gallup's protocol get 3 trials before judgement; we use
# 3 here so a single transient ledger glitch does not cry wolf, but two
# repeated forgeries do.)
MIRROR_BIOMETRIC_FAIL_STREAK  = 3

# Attestation status enum (string, ledger-stable).
PASSED            = "PASSED"
REJECTED_FOREIGN  = "REJECTED_FOREIGN"
REJECTED_FORGERY  = "REJECTED_FORGERY"
NOT_FOUND         = "NOT_FOUND"

VALID_OUTCOMES = (PASSED, REJECTED_FOREIGN, REJECTED_FORGERY, NOT_FOUND)


# ── Public dataclass ──────────────────────────────────────────────────────

@dataclass
class MirrorAttestation:
    """
    A single attestation: did `swimmer_id` recognize itself in
    `candidate_receipt_id` from the work_receipts ledger?
    """
    swimmer_id: str
    candidate_receipt_id: str
    outcome: str                  # one of VALID_OUTCOMES
    ts: float
    elapsed_ms: float
    biometric: Dict[str, Any] = field(default_factory=dict)
    detail: str = ""
    module_version: str = MODULE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Internal: ledger readers ──────────────────────────────────────────────

def _read_jsonl_tail(path: Path, *, max_rows: Optional[int] = None) -> List[Dict[str, Any]]:
    """Best-effort tail reader. Never raises."""
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    if max_rows is not None and len(rows) > max_rows:
        return rows[-max_rows:]
    return rows


def _find_receipt_by_id(receipt_id: str) -> Optional[Dict[str, Any]]:
    """Linear scan of the receipts ledger. Returns the FIRST match (receipt_ids
    are uuid4 hex slices in proof_of_useful_work, collisions vanishingly rare).
    Returns None if absent."""
    if not _RECEIPTS_LOG.exists():
        return None
    try:
        with _RECEIPTS_LOG.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("receipt_id") == receipt_id:
                    return row
    except OSError:
        return None
    return None


# ── Internal: hash recomputation ──────────────────────────────────────────

def _recompute_receipt_hash(row: Dict[str, Any]) -> str:
    """
    Reproduces proof_of_useful_work.WorkReceipt.compute_hash deterministically
    from the public ledger fields. The exact format must match the source —
    if proof_of_useful_work changes its hash function, this module must move
    in lockstep (a substrate-swap would otherwise look like a forgery).
    """
    raw = (
        f"{row.get('receipt_id', '')}:{row.get('agent_id', '')}:"
        f"{row.get('work_type', '')}:{row.get('timestamp', '')}:"
        f"{row.get('work_value', '')}:{row.get('territory', '')}:"
        f"{row.get('output_hash', '')}:{row.get('previous_receipt_hash', '')}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Internal: biometric streak detection ──────────────────────────────────

def _compute_biometric(swimmer_id: str) -> Dict[str, Any]:
    """
    Walk the most recent MIRROR_BIOMETRIC_WINDOW attestations for this
    swimmer and report:
        • window_size           — how many we actually saw (≤ window cap)
        • passed_count          — number of PASSED outcomes in window
        • fail_streak           — length of the trailing non-PASSED streak
        • substrate_swap_suspected — fail_streak ≥ MIRROR_BIOMETRIC_FAIL_STREAK
    """
    rows = _read_jsonl_tail(_MIRROR_LOG)
    mine = [r for r in rows if r.get("swimmer_id") == swimmer_id]
    window = mine[-MIRROR_BIOMETRIC_WINDOW:]
    passed_count = sum(1 for r in window if r.get("outcome") == PASSED)
    streak = 0
    for r in reversed(window):
        if r.get("outcome") != PASSED:
            streak += 1
        else:
            break
    return {
        "window_size": len(window),
        "passed_count": passed_count,
        "fail_streak": streak,
        "substrate_swap_suspected": streak >= MIRROR_BIOMETRIC_FAIL_STREAK,
    }


# ── Tester ────────────────────────────────────────────────────────────────

class MirrorTester:
    """
    Asks a swimmer "did you write this receipt?" and judges the answer.
    Pure compute — never mutates the receipts ledger; appends one
    attestation row per call to the mirror_test ledger.
    """

    def __init__(self, *, persist: bool = True) -> None:
        self.persist = persist

    def attest(self, swimmer_id: str, candidate_receipt_id: str) -> MirrorAttestation:
        """
        Run a single mirror test. Always returns an Attestation. Never raises.
        """
        t0 = time.time()
        row = _find_receipt_by_id(candidate_receipt_id)

        if row is None:
            outcome = NOT_FOUND
            detail = f"no receipt with receipt_id={candidate_receipt_id} in ledger"
        else:
            stored_hash = row.get("receipt_hash", "")
            recomputed = _recompute_receipt_hash(row)
            agent_id = row.get("agent_id", "")
            if stored_hash != recomputed:
                outcome = REJECTED_FORGERY
                detail = (
                    f"stored_hash[:8]={stored_hash[:8]} != recomputed[:8]={recomputed[:8]} "
                    f"(receipt impersonates agent_id={agent_id})"
                )
            elif agent_id != swimmer_id:
                outcome = REJECTED_FOREIGN
                detail = f"receipt is consistent but authored by agent_id={agent_id}, not {swimmer_id}"
            else:
                outcome = PASSED
                detail = f"agent_id match + hash recomputes; reflection recognized"

        elapsed_ms = round((time.time() - t0) * 1000.0, 3)

        # Persist FIRST (so the biometric of THIS attestation can include itself
        # on the next call — but we report the CURRENT biometric AS-OF entry,
        # i.e. before the new row, to avoid telling the caller about itself).
        biometric_pre = _compute_biometric(swimmer_id)

        attest = MirrorAttestation(
            swimmer_id=swimmer_id,
            candidate_receipt_id=candidate_receipt_id,
            outcome=outcome,
            ts=time.time(),
            elapsed_ms=elapsed_ms,
            biometric=biometric_pre,
            detail=detail,
        )
        if self.persist:
            _persist_attestation(attest)
        return attest


# ── Persistence ───────────────────────────────────────────────────────────

def _persist_attestation(attest: MirrorAttestation) -> bool:
    try:
        _MIRROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _MIRROR_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(attest.to_dict(), ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def recent_attestations(swimmer_id: Optional[str] = None, *, limit: int = 20) -> List[Dict[str, Any]]:
    rows = _read_jsonl_tail(_MIRROR_LOG)
    if swimmer_id is not None:
        rows = [r for r in rows if r.get("swimmer_id") == swimmer_id]
    return rows[-limit:]


# ── CLI / smoke ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SIFTA — Mirror Test (R4)")
    parser.add_argument("--swimmer", default="SOCRATES",
                        help="Swimmer ID asking 'did I write this?' (default: SOCRATES)")
    parser.add_argument("--receipt-id", default=None,
                        help="Candidate receipt_id to test against. If omitted, uses the "
                             "first receipt in the ledger that matches --swimmer.")
    parser.add_argument("--no-persist", action="store_true",
                        help="Do not write the attestation to the ledger")
    args = parser.parse_args()

    print("═" * 72)
    print("  SIFTA — SWARM MIRROR TEST (R4: Self-Recognition)")
    print("  'Is that swimmer in the mirror... me?'")
    print("═" * 72)

    target_id = args.receipt_id
    if target_id is None:
        # Pick the first receipt by this swimmer for a friendly default demo.
        receipts = _read_jsonl_tail(_RECEIPTS_LOG)
        for r in receipts:
            if r.get("agent_id") == args.swimmer:
                target_id = r.get("receipt_id")
                break

    if target_id is None:
        print(f"\n  No receipt found for swimmer={args.swimmer!r} in {_RECEIPTS_LOG.name}.")
        print(f"  Try --receipt-id <id> or pick a swimmer that has actually worked.")
        raise SystemExit(0)

    tester = MirrorTester(persist=not args.no_persist)
    attest = tester.attest(args.swimmer, target_id)

    print(f"\n  swimmer_id           : {attest.swimmer_id}")
    print(f"  candidate_receipt_id : {attest.candidate_receipt_id}")
    print(f"  outcome              : {attest.outcome}")
    print(f"  detail               : {attest.detail}")
    print(f"  elapsed_ms           : {attest.elapsed_ms}")
    print(f"  biometric (as-of)    : {attest.biometric}")
    print()
    print("═" * 72)
    if attest.outcome == PASSED:
        print(f"  ⚡ {attest.swimmer_id} recognized itself in the mirror.")
    elif attest.outcome == REJECTED_FOREIGN:
        print(f"  🪞 {attest.swimmer_id} correctly refused: that reflection is another swimmer.")
    elif attest.outcome == REJECTED_FORGERY:
        print(f"  🩸 {attest.swimmer_id} detected a forgery: hash does not recompute.")
    else:
        print(f"  ❔ Receipt id not found in the ledger.")
    print("═" * 72)
