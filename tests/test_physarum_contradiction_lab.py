# History
# -------
# 2026-04-26 — Codex (C55M) authored this test alongside the lab. The
# original assertions captured the OLD body-only PoUW gate, where:
#   - `audit["forged_pouw"]["ok"] is True`
#   - `audit["physarum_work_value_present"] is False`
#   - `audit["verdict"] == "CONTRADICTS_MEMO"`
# That was a real, demonstrated gap.
#
# 2026-04-26 (later same day) — Cursor (Claude Opus 4.7) closed the gap
# in `System/proof_of_useful_work.py` by adding a canonical
# `PHYSARUM_SOLVE` work type, a deterministic-replay verifier
# `prove_physarum_solve`, a result-hash spend ledger, and a peer
# countersignature scaffold. Codex's lab now exercises the new gate via
# checks 5/6/7 and the verdict flips to `MEMO_CONFIRMED`.
#
# These tests are the regression net for that fix. Codex's body-gate
# observations (checks 2 and 3) are intentionally preserved unchanged
# because the body gate is body-level only and is *not* the gate the
# Slime-Mold Bank now relies on for Physarum semantics.
from Applications.sifta_physarum_contradiction_lab import (
    make_claude_report,
    run_claim_audit,
)


def test_claim_audit_documents_body_gate_and_semantic_gate_are_now_distinct():
    audit = run_claim_audit(max_iters=120)

    assert audit["graph"] == "tokyo_stub"

    # Codex's original body-gate observations — preserved verbatim.
    # The body gate is body-level only by design, and the audit response
    # explicitly does not "fix" it because it has the right behaviour
    # for what it actually checks (bytes changed + system alive).
    assert audit["honest_pouw"]["ok"] is True
    assert audit["forged_pouw"]["ok"] is True

    # Post-audit: PHYSARUM_SOLVE is now a canonical 0.65-valued PoUW
    # work type. The marketing memo's claim is true on `main`.
    assert audit["physarum_work_value_present"] is True
    assert audit["physarum_work_value_actual"] == 0.65
    assert audit["physarum_work_value_canonical"] is True

    # Post-audit: the new semantic gate accepts the honest deterministic
    # replay and rejects forged hashes by HASH_MISMATCH.
    assert audit["semantic_gate_available"] is True
    assert audit["semantic_honest"]["ok"] is True
    assert audit["semantic_honest"]["hash_match"] is True
    assert audit["semantic_forged"]["ok"] is False
    assert audit["semantic_forged"]["reason"] == "HASH_MISMATCH"

    # Result-hash spend ledger: re-claiming the same converged solve
    # is rejected with DOUBLE_SPEND.
    assert audit["semantic_double_spend"]["ok"] is False
    assert audit["semantic_double_spend"]["reason"] == "DOUBLE_SPEND"

    assert audit["verdict"] == "MEMO_CONFIRMED"


def test_claude_report_documents_audit_resolution():
    report = make_claude_report(run_claim_audit(max_iters=120))

    # Codex's original truth statement is still in the report, because
    # it was correct then and still is — the solver IS real.
    assert "The Physarum solver is real" in report

    # Both the original audit checks AND the post-audit semantic gate
    # checks must appear, so a public reader can see the full arc.
    assert "Original Codex (C55M) audit checks:" in report
    assert "Post-audit semantic gate checks" in report
    assert "PHYSARUM_SOLVE_VERIFIED" in report
    assert "HASH_MISMATCH" in report
    assert "DOUBLE_SPEND" in report
    assert "MEMO_CONFIRMED" in report
