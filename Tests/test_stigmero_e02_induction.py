"""
tests/test_stigmero_e02_induction.py
════════════════════════════════════════════════════════════════════════════
E02 — Induction live (STIGMEROBOTICS / ROB 501 tournament)

ROB 501 topic: Mathematical induction, fundamental theorem, contradiction.

Hypothesis (P(n)):
    The first n modern rows of a SIFTA JSONL ledger satisfy:
      (a) ts_monotonic:   ts_i <= ts_{i+1}  for all i < n   (append-only time)
      (b) schema_closed:  every modern row passes REQUIRED_KEYS check

Proof structure (two-part, following §7.12 Probe-Before-Claim):

  Base case P(0):
    The empty modern prefix vacuously satisfies both predicates.
    Proved by: test_e02_base_case_empty_modern_prefix_ok
    Fixture:   tests/fixtures/stigmero_e02_base.jsonl
               (contains only legacy rows → modern_rows == 0, vacuous truth)

  Inductive step P(n) → P(n+1):
    If the first n rows satisfy (a) and (b), appending a valid row
    (ts_{n+1} >= ts_n, all required keys present) preserves both predicates.
    Proved by: test_e02_step_valid_append_preserves_invariants
    Fixture:   tests/fixtures/stigmero_e02_step_good.jsonl
               (5 rows with ts non-decreasing, all required keys present)

  Contrapositive (proof by contradiction):
    If ts_{n+1} < ts_n (history rewrite / rollback), then P(n+1) is false.
    Proved by: test_e02_step_ts_rollback_breaks_induction
    Fixture:   tests/fixtures/stigmero_e02_step_bad_ts.jsonl
               (row 3 has ts < row 2 → violation detected)

  Contrapositive (history shrink / past-insert):
    If an out-of-order row is inserted at any point in the sequence,
    monotonicity is violated, which means the ledger is NOT append-only.
    Proved by: test_e02_shrink_bad_detects_past_insert
    Fixture:   tests/fixtures/stigmero_e02_shrink_bad.jsonl

  Regression on real-shaped sanitized fixtures:
    Proved by: test_e02_sanitized_trace_is_monotonic
               test_e02_sanitized_receipts_are_monotonic

§8.6 compliance: all assertions run on sanitized hand-crafted fixtures.
No live .sifta_state/ data is read.

proof_of_property = {
    "P_n": "first n modern rows satisfy ts_monotonic ∧ schema_closed",
    "base": "n=0 → vacuous (empty modern prefix)",
    "step": "P(n) ∧ valid_append → P(n+1)",
    "contrapositive": "¬P(n+1) → ¬valid_append (ts rollback OR missing key)",
    "falsifier": "insert any row with ts < max_ts_seen → induction_ok() returns False",
}
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import pytest

from System.ledger_auditor import (
    REQUIRED_KEYS,
    check_invariants,
    load_sanitized_fixture,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── Core predicate functions (pure — no I/O) ────────────────────────────


def _is_modern_row(row: dict) -> bool:
    """True if the row was written by ide_stigmergic_bridge.deposit()."""
    return (
        not row.get("_parse_error")
        and "trace_id" in row
    )


def _schema_closed(row: dict) -> Tuple[bool, str]:
    """
    P(n) predicate (b): row has all REQUIRED_KEYS.
    Returns (True, '') or (False, <detail>).
    """
    missing = REQUIRED_KEYS - row.keys()
    if missing:
        return False, f"missing required keys: {sorted(missing)}"
    return True, ""


def induction_ok(rows: List[dict]) -> Tuple[bool, str]:
    """
    Check P(n) for all modern rows in sequence:
      (a) ts_monotonic: ts[i] <= ts[i+1]
      (b) schema_closed: REQUIRED_KEYS present in every modern row

    Base: empty modern prefix → returns (True, '').
    Step: each valid append preserves both predicates.

    Returns (True, '') if invariants hold, (False, <detail>) on first violation.
    """
    prev_ts: float | None = None
    for i, row in enumerate(rows):
        if not _is_modern_row(row):
            continue  # legacy row — tolerated, skip from induction

        # (b) schema_closed
        ok, msg = _schema_closed(row)
        if not ok:
            return False, f"row {i} schema_closed violation: {msg}"

        # (a) ts_monotonic
        ts_raw = row.get("ts")
        try:
            ts = float(ts_raw)
        except (TypeError, ValueError):
            return False, f"row {i} ts={ts_raw!r} is not numeric (not monotonic)"

        if prev_ts is not None and ts < prev_ts:
            return False, (
                f"row {i} ts rollback: {ts} < prev_ts {prev_ts} "
                f"(kind={row.get('kind')!r}, source_ide={row.get('source_ide')!r})"
            )
        prev_ts = ts

    return True, ""  # vacuously true for empty modern prefix


def _append_one(rows: List[dict], new_row: dict) -> List[dict]:
    """Return a new list with new_row appended — never mutates in place."""
    return rows + [new_row]


def _max_modern_ts(rows: List[dict]) -> float | None:
    """Return the largest ts seen in modern rows, or None if no modern rows."""
    ts_vals = []
    for r in rows:
        if _is_modern_row(r) and "ts" in r:
            try:
                ts_vals.append(float(r["ts"]))
            except (TypeError, ValueError):
                pass
    return max(ts_vals) if ts_vals else None


# ── Test 1 — Base case ──────────────────────────────────────────────────


class TestE02BaseCase:
    def test_e02_base_case_empty_modern_prefix_ok(self) -> None:
        """
        P(0): empty modern prefix → vacuous truth.
        Fixture contains only legacy rows → modern_rows == 0.
        """
        rows = load_sanitized_fixture(FIXTURES / "stigmero_e02_base.jsonl")
        modern = [r for r in rows if _is_modern_row(r)]
        assert len(modern) == 0, f"Expected 0 modern rows, got {len(modern)}"
        ok, msg = induction_ok(rows)
        assert ok, f"Base case failed: {msg}"

    def test_e02_base_case_truly_empty_file_ok(self, tmp_path: Path) -> None:
        """P(0): a literally empty file also satisfies the base case."""
        f = tmp_path / "empty.jsonl"
        f.write_text("", encoding="utf-8")
        rows = load_sanitized_fixture(f)
        ok, msg = induction_ok(rows)
        assert ok, msg

    def test_e02_single_valid_row_satisfies_p1(self) -> None:
        """P(1): a single valid modern row trivially satisfies monotonicity."""
        row = {
            "trace_id": "t1", "ts": 1_778_100_000.0, "source_ide": "test",
            "kind": "LLM_REGISTRATION", "payload": "{}", "homeworld_serial": "SER",
        }
        ok, msg = induction_ok([row])
        assert ok, msg


# ── Test 2 — Inductive step (positive) ─────────────────────────────────


class TestE02InductiveStepPositive:
    def test_e02_step_valid_append_preserves_invariants(self) -> None:
        """
        P(n) → P(n+1): good fixture has 5 rows with ts non-decreasing.
        Every appended row is valid → induction holds for the full sequence.
        """
        rows = load_sanitized_fixture(FIXTURES / "stigmero_e02_step_good.jsonl")
        ok, msg = induction_ok(rows)
        assert ok, msg

    def test_e02_step_equal_ts_is_allowed(self) -> None:
        """
        Append-only time: ts_{n+1} >= ts_n (not strictly greater).
        Two rows with the same ts are valid — simultaneous deposits are real.
        """
        import time

        now = time.time()
        rows = [
            {"trace_id": "t1", "ts": now, "source_ide": "x",
             "kind": "LLM_REGISTRATION", "payload": "{}", "homeworld_serial": "S"},
            {"trace_id": "t2", "ts": now, "source_ide": "x",  # same ts
             "kind": "immune_intervention", "payload": "{}", "homeworld_serial": "S"},
        ]
        ok, msg = induction_ok(rows)
        assert ok, msg

    def test_e02_step_append_one_valid_row_preserves_induction(self) -> None:
        """
        Simulate the inductive step explicitly:
        Start with n=2 rows (P(2) holds), append a valid row → P(3) holds.
        """
        prefix = [
            {"trace_id": "t1", "ts": 1.0, "source_ide": "x",
             "kind": "LLM_REGISTRATION", "payload": "{}", "homeworld_serial": "S"},
            {"trace_id": "t2", "ts": 2.0, "source_ide": "x",
             "kind": "immune_intervention", "payload": "{}", "homeworld_serial": "S"},
        ]
        # Verify P(2)
        ok, msg = induction_ok(prefix)
        assert ok, f"Prefix P(2) failed unexpectedly: {msg}"

        # Append valid row → P(3)
        new_row = {"trace_id": "t3", "ts": 3.0, "source_ide": "x",
                   "kind": "SCAR_RECEIPT", "payload": '{"scar_id":"S1"}', "homeworld_serial": "S"}
        extended = _append_one(prefix, new_row)
        ok, msg = induction_ok(extended)
        assert ok, f"P(3) after valid append failed: {msg}"

    def test_e02_step_legacy_rows_skipped_in_monotonicity(self) -> None:
        """
        Legacy rows (pre-bridge) must not break monotonicity even if their
        ts appears to be 'between' modern rows — they are simply skipped.
        """
        rows = [
            {"trace_id": "t1", "ts": 100.0, "source_ide": "x",
             "kind": "LLM_REGISTRATION", "payload": "{}", "homeworld_serial": "S"},
            # legacy row with ts = 50 (looks like a rollback but is legacy)
            {"system": "boot", "event": "tick", "device": "S",
             "reason": "cold", "resolution": "ok", "ts": 50.0},
            {"trace_id": "t2", "ts": 200.0, "source_ide": "x",
             "kind": "LLM_SIGNOUT", "payload": "{}", "homeworld_serial": "S"},
        ]
        ok, msg = induction_ok(rows)
        assert ok, f"Legacy rows should be skipped, not break induction: {msg}"

    def test_e02_step_all_required_keys_preserved_after_append(self) -> None:
        """
        schema_closed check: REQUIRED_KEYS must be present in every modern row
        even after arbitrary number of appends.
        """
        import uuid

        base = [{"trace_id": "t0", "ts": 0.0, "source_ide": "x",
                 "kind": "LLM_REGISTRATION", "payload": "{}", "homeworld_serial": "S"}]
        rows = list(base)
        for i in range(1, 11):
            new = {"trace_id": str(uuid.uuid4()), "ts": float(i),
                   "source_ide": "x", "kind": "immune_intervention",
                   "payload": "{}", "homeworld_serial": "S"}
            rows = _append_one(rows, new)
            ok, msg = induction_ok(rows)
            assert ok, f"P({i+1}) broken after append #{i}: {msg}"

    def test_e02_sanitized_trace_is_monotonic(self) -> None:
        """
        Regression: the sanitized_trace fixture used across other tests
        must itself satisfy the induction predicate.
        """
        rows = load_sanitized_fixture(FIXTURES / "sanitized_trace.jsonl")
        ok, msg = induction_ok(rows)
        assert ok, msg

    def test_e02_sanitized_receipts_are_monotonic(self) -> None:
        """Regression: sanitized_receipts must also satisfy the predicate."""
        rows = load_sanitized_fixture(FIXTURES / "sanitized_receipts.jsonl")
        ok, msg = induction_ok(rows)
        assert ok, msg


# ── Test 3 — Contrapositive / proof by contradiction ───────────────────


class TestE02Contrapositive:
    def test_e02_step_ts_rollback_breaks_induction(self) -> None:
        """
        Contrapositive: if ts_{n+1} < ts_n → P(n+1) is False.
        This is the contradiction: the step does NOT preserve monotonicity
        when a row with a past ts is appended (history rewrite / rollback attack).
        """
        rows = load_sanitized_fixture(FIXTURES / "stigmero_e02_step_bad_ts.jsonl")
        ok, msg = induction_ok(rows)
        assert not ok, "Expected induction failure for ts rollback, but got ok"
        assert "rollback" in msg or "< prev_ts" in msg, f"Wrong violation detail: {msg!r}"

    def test_e02_shrink_bad_detects_past_insert(self) -> None:
        """
        Contrapositive: a row inserted in the past (ts goes backward in the middle
        of the sequence) is equivalent to a history shrink — violates append-only law.
        """
        rows = load_sanitized_fixture(FIXTURES / "stigmero_e02_shrink_bad.jsonl")
        ok, msg = induction_ok(rows)
        assert not ok, "Expected induction failure for past-insert, but got ok"

    def test_e02_append_rollback_explicitly(self) -> None:
        """
        Explicit contrapositive: P(n) holds; appending a row with ts < max_ts
        breaks P(n+1).  This is the minimal proof-by-contradiction slice.
        """
        prefix = [
            {"trace_id": "t1", "ts": 1_000.0, "source_ide": "x",
             "kind": "LLM_REGISTRATION", "payload": "{}", "homeworld_serial": "S"},
            {"trace_id": "t2", "ts": 2_000.0, "source_ide": "x",
             "kind": "immune_intervention", "payload": "{}", "homeworld_serial": "S"},
        ]
        # P(2) holds
        ok, _ = induction_ok(prefix)
        assert ok, "Precondition: P(2) must hold for this test"

        # Append a past-ts row — direct contradiction of step hypothesis
        bad_row = {"trace_id": "t3", "ts": 999.0, "source_ide": "x",
                   "kind": "SCAR_RECEIPT", "payload": '{"scar_id":"bad"}', "homeworld_serial": "S"}
        extended = _append_one(prefix, bad_row)
        ok, msg = induction_ok(extended)
        assert not ok, "P(3) must be False when ts rolls back"
        assert "999" in msg or "rollback" in msg, f"Detail should cite bad ts: {msg!r}"

    def test_e02_missing_required_key_breaks_schema_closed(self) -> None:
        """
        Contrapositive on schema_closed: a row missing 'homeworld_serial'
        breaks P(n+1) even if ts is monotonic.
        """
        prefix = [
            {"trace_id": "t1", "ts": 1.0, "source_ide": "x",
             "kind": "LLM_REGISTRATION", "payload": "{}", "homeworld_serial": "S"},
        ]
        bad_row = {
            "trace_id": "t2", "ts": 2.0, "source_ide": "x",
            "kind": "immune_intervention", "payload": "{}",
            # homeworld_serial intentionally missing
        }
        extended = _append_one(prefix, bad_row)
        ok, msg = induction_ok(extended)
        assert not ok, "Missing required key must break schema_closed"
        assert "homeworld_serial" in msg, f"Should cite the missing key: {msg!r}"

    def test_e02_non_numeric_ts_breaks_induction(self) -> None:
        """
        Contrapositive: if ts is not a float, the monotonicity predicate
        cannot be evaluated → induction is broken at that row.
        """
        rows = [
            {"trace_id": "t1", "ts": 1.0, "source_ide": "x",
             "kind": "LLM_REGISTRATION", "payload": "{}", "homeworld_serial": "S"},
            {"trace_id": "t2", "ts": "NOT_A_FLOAT", "source_ide": "x",
             "kind": "immune_intervention", "payload": "{}", "homeworld_serial": "S"},
        ]
        ok, msg = induction_ok(rows)
        assert not ok, "Non-numeric ts should break induction"
        assert "NOT_A_FLOAT" in msg or "numeric" in msg.lower(), f"Detail: {msg!r}"

    def test_e02_bad_fixture_not_vacuously_passing(self) -> None:
        """
        Sanity: bad fixtures must contain at least one modern row,
        otherwise the test would pass vacuously and be meaningless.
        """
        for fname in ("stigmero_e02_step_bad_ts.jsonl", "stigmero_e02_shrink_bad.jsonl"):
            rows = load_sanitized_fixture(FIXTURES / fname)
            modern = [r for r in rows if _is_modern_row(r)]
            assert len(modern) >= 2, (
                f"{fname}: need >= 2 modern rows for a non-vacuous induction test, "
                f"got {len(modern)}"
            )


# ── Test 4 — Helper utilities ───────────────────────────────────────────


class TestE02Helpers:
    def test_max_modern_ts_empty(self) -> None:
        assert _max_modern_ts([]) is None

    def test_max_modern_ts_legacy_only(self) -> None:
        rows = [{"system": "boot", "event": "x", "device": "S",
                 "reason": "r", "resolution": "ok", "ts": 999.0}]
        assert _max_modern_ts(rows) is None  # legacy — not counted

    def test_max_modern_ts_mixed(self) -> None:
        rows = [
            {"system": "boot", "event": "x", "device": "S",
             "reason": "r", "resolution": "ok", "ts": 999.0},
            {"trace_id": "t1", "ts": 100.0, "source_ide": "x",
             "kind": "LLM_REGISTRATION", "payload": "{}", "homeworld_serial": "S"},
            {"trace_id": "t2", "ts": 200.0, "source_ide": "x",
             "kind": "LLM_SIGNOUT", "payload": "{}", "homeworld_serial": "S"},
        ]
        assert _max_modern_ts(rows) == 200.0

    def test_append_one_does_not_mutate_original(self) -> None:
        original = [{"trace_id": "t1", "ts": 1.0, "source_ide": "x",
                     "kind": "LLM_REGISTRATION", "payload": "{}", "homeworld_serial": "S"}]
        extended = _append_one(original, {"ts": 2.0})
        assert len(original) == 1, "_append_one must not mutate the prefix"
        assert len(extended) == 2

    def test_schema_closed_all_keys(self) -> None:
        row = {"trace_id": "t", "ts": 1.0, "kind": "x", "source_ide": "y",
               "homeworld_serial": "S"}
        ok, msg = _schema_closed(row)
        assert ok, msg

    def test_schema_closed_missing_key(self) -> None:
        row = {"trace_id": "t", "ts": 1.0, "kind": "x", "source_ide": "y"}
        # missing homeworld_serial
        ok, msg = _schema_closed(row)
        assert not ok
        assert "homeworld_serial" in msg


# ── Test 5 — proof_of_property dict (machine-readable claim) ────────────


class TestE02ProofOfProperty:
    """
    Smoke-test that the proof_of_property dict embedded in the module
    docstring is consistent with what the tests actually prove.
    These tests are intentionally tautological — they validate the
    documentation, not the logic (the logic is in classes above).
    """

    proof_of_property = {
        "P_n": "first n modern rows satisfy ts_monotonic ∧ schema_closed",
        "base": "n=0 → vacuous (empty modern prefix)",
        "step": "P(n) ∧ valid_append → P(n+1)",
        "contrapositive": "¬P(n+1) → ¬valid_append (ts rollback OR missing key)",
        "falsifier": (
            "insert any row with ts < max_ts_seen → induction_ok() returns False"
        ),
    }

    def test_proof_has_required_keys(self) -> None:
        required = {"P_n", "base", "step", "contrapositive", "falsifier"}
        assert required <= self.proof_of_property.keys()

    def test_falsifier_is_machine_checkable(self) -> None:
        """Falsifier must reference the function that is actually tested."""
        assert "induction_ok()" in self.proof_of_property["falsifier"]

    def test_base_references_vacuous_truth(self) -> None:
        assert "vacuous" in self.proof_of_property["base"].lower()
