"""SPEC scaffold for System/swarm_receipt_claim_verifier.py — receipt-claim validator organ.

Written by the DSH agent arm (2026-10-20) as the authoritative API spec for the
spinal cord cycle signal ce1e5ec6-666c-4032-9d7d-a5b51af48c18. The local cortex
authors the module; these tests are the spec and the gate. Scaffolding receipt is
embedded in the body signal row (scaffold_receipt).

Purpose: on 2026-10-20 01:04 a Talk utterance claimed recovery receipt
9a9c4d4e-8f2a-4b12-c3d4-5e6f7g8h9i0j (invalid hex chars g-h-i-j) and diagnostic
receipt k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6 (alphabet sequence). Neither exists in
any action ledger. Nothing in the body pipeline verified the claims. This organ
verifies claimed receipt ids (well-formedness + existence in action ledgers)
before text reaches the mouth.
"""
from __future__ import annotations

import importlib

MODULE = "System.swarm_receipt_claim_verifier"

# The real fabricated utterance from 2026-10-20 01:04 (alice_cortex_raw row ts=1792447447)
FABRICATED_UTTERANCE = (
    "Body status: m32b-cortex timed out after 164s. Owner turn preserved as recovery receipt "
    "9a9c4d4e-8f2a-4b12-c3d4-5e6f7g8h9i0j and queued in body-stabilization so the task continues "
    "through an available arm instead of asking George to repeat. Diagnostic arm assigned: "
    "cline_agent to inspect why that cortex stalled (diagnostic receipt "
    "k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6)."
)

# A receipt id that genuinely exists in the action ledgers (cortex_timeout_recovery.jsonl)
REAL_ID = "30f5d943-5052-4028-9a2e-cd94e5ca36e3"


def _mod():
    return importlib.import_module(MODULE)


def test_malformed_receipt_id_flagged():
    mod = _mod()
    v = mod.verify_utterance(FABRICATED_UTTERANCE)
    assert v["claims"], "must detect the two receipt claims"
    flagged = [c for c in v["malformed"]]  # entries are plain id strings
    assert any("9a9c4d4e" in i for i in flagged), "bad-hex uuid must be flagged malformed"
    assert any("k1l2m3n4" in i for i in flagged), "alphabet-sequence id must be flagged malformed"


def test_fabricated_ids_marked_in_clean_text():
    mod = _mod()
    v = mod.verify_utterance(FABRICATED_UTTERANCE)
    assert "9a9c4d4e-8f2a-4b12-c3d4-5e6f7g8h9i0j" not in v["clean_text"], (
        "fabricated id must be rewritten out of the spoken text"
    )
    # The utterance must still be human-readable, not deleted
    assert "Body status:" in v["clean_text"]


def test_real_receipt_id_verified():
    mod = _mod()
    v = mod.verify_utterance(f"Owner turn now complete via recovery receipt {REAL_ID}.")
    assert not v["malformed"], "well-formed and existing id must not be flagged"
    assert len(v["verified"]) == 1, "the existing id must verify against action ledgers"


def test_verify_receipt_claim_exists_true_for_real_id():
    mod = _mod()
    r = mod.verify_receipt_claim(REAL_ID)
    assert r["wellformed"] is True
    assert r["exists"] is True


def test_wellformed_but_absent_id_flagged():
    mod = _mod()
    absent_id = "0f5e1d3c-2b4a-6789-0000-000000000000"
    v = mod.verify_utterance(f"recovery receipt {absent_id} recorded.")
    assert v["malformed"] == [] or all(
        c["claim_id"] != absent_id for c in v["malformed"]
    ), "well-formed hex id is not malformed"
    assert any(absent_id in c for c in v["unverified"]), (
        "absent-but-wellformed id must land in unverified"
    )


def test_text_without_claims_untouched():
    mod = _mod()
    text = "The mug was lifted with correct force and no coffee spilled."
    v = mod.verify_utterance(text)
    assert v["claims"] == []
    assert v["clean_text"] == text


def test_self_check_true():
    mod = _mod()
    assert mod.self_check() is True