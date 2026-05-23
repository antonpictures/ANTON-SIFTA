"""
tests/test_ledger_invariants.py
════════════════════════════════════════════════════════════════════════════
Pytest companion for System/ledger_auditor.py — Priority A.

Hypothesis (P): Every effector/ledger row in ide_stigmergic_trace.jsonl and
work_receipts.jsonl obeys machine-checkable invariants.
Conclusion (Q): all tests below pass with zero false-positives.
Contrapositive: if any test fails, at least one row violates the schema.

Fixtures used:
    tests/fixtures/sanitized_trace.jsonl   — good rows (must all pass)
    tests/fixtures/sanitized_receipts.jsonl — good rows (must all pass)
    tests/fixtures/bad_rows.jsonl          — intentionally bad (must fail)

§8.6 compliance: no live .sifta_state/ data is read or printed.  All
assertions run against hand-crafted sanitized fixtures.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from System.ledger_auditor import (
    AuditResult,
    AuditViolation,
    audit_ledger,
    audit_live,
    assert_row_valid,
    check_invariants,
    load_sanitized_fixture,
    REQUIRED_KEYS,
    EFFECTOR_KINDS,
    PAYLOAD_REQUIRED_KINDS,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── 1. Fixture loading ────────────────────────────────────────────────────

class TestLoadSanitizedFixture:
    def test_good_trace_loads(self) -> None:
        rows = load_sanitized_fixture(FIXTURES / "sanitized_trace.jsonl")
        assert len(rows) >= 5  # at least the rows we hand-crafted

    def test_payload_truncated_at_200(self, tmp_path: Path) -> None:
        import json
        long_payload = "x" * 300
        row = {
            "trace_id": "t1", "ts": 1.0, "source_ide": "test",
            "kind": "LLM_REGISTRATION", "homeworld_serial": "SER",
            "payload": long_payload,
        }
        f = tmp_path / "long.jsonl"
        f.write_text(json.dumps(row) + "\n")
        loaded = load_sanitized_fixture(f)
        assert len(loaded) == 1
        assert loaded[0]["payload"].endswith("...[sanitized]")
        assert len(loaded[0]["payload"]) < 230  # well under original 300

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_sanitized_fixture(FIXTURES / "does_not_exist.jsonl")

    def test_empty_lines_skipped(self, tmp_path: Path) -> None:
        import json
        row = {
            "trace_id": "t1", "ts": 1.0, "source_ide": "x",
            "kind": "LLM_SIGNOUT", "homeworld_serial": "SER",
            "payload": "{}",
        }
        f = tmp_path / "sparse.jsonl"
        f.write_text("\n\n" + json.dumps(row) + "\n\n")
        rows = load_sanitized_fixture(f)
        assert len(rows) == 1

    def test_malformed_json_produces_parse_error_sentinel(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.jsonl"
        f.write_text("{not valid json}\n")
        rows = load_sanitized_fixture(f)
        assert len(rows) == 1
        assert "_parse_error" in rows[0]


# ── 2. Invariant checker — positive (all valid rows) ─────────────────────

class TestCheckInvariantsPositive:
    def test_sanitized_trace_passes(self) -> None:
        rows = load_sanitized_fixture(FIXTURES / "sanitized_trace.jsonl")
        result = check_invariants(rows)
        result.path = str(FIXTURES / "sanitized_trace.jsonl")
        assert result.ok, result.summary()

    def test_sanitized_receipts_passes(self) -> None:
        rows = load_sanitized_fixture(FIXTURES / "sanitized_receipts.jsonl")
        result = check_invariants(rows)
        result.path = str(FIXTURES / "sanitized_receipts.jsonl")
        assert result.ok, result.summary()

    def test_legacy_rows_not_flagged_as_errors(self) -> None:
        """Pre-bridge rows (system/event/device shape) must be LEGACY, not violations."""
        rows = load_sanitized_fixture(FIXTURES / "sanitized_trace.jsonl")
        result = check_invariants(rows)
        assert result.legacy_rows >= 1, "Expected at least one legacy row in the fixture"
        # None of the violations should reference the legacy row
        kinds_violated = {v.row_kind for v in result.violations}
        assert "?" not in kinds_violated or result.ok

    def test_modern_row_with_event_field_is_not_misclassified_as_legacy(self) -> None:
        """A broken modern row cannot hide behind legacy vocabulary like event/system."""
        row = {
            "event": "LLM_REGISTRATION",
            "kind": "LLM_REGISTRATION",
            "source_ide": "antigravity_m5",
            "payload": '{"intent":"missing trace id"}',
            "ts": 1.0,
            "homeworld_serial": "GTH4921YP3",
        }
        result = check_invariants([row])
        assert result.legacy_rows == 0
        assert not result.ok
        assert "required_keys" in {v.rule for v in result.violations}

    def test_work_receipts_profile_tolerates_older_receipt_rows(self) -> None:
        """Old receipt_hash/node_serial rows are valid legacy work receipts."""
        row = {
            "agent_id": "auditor_test",
            "description": "sanitized receipt shape",
            "node_serial": "GTH4921YP3",
            "receipt_hash": "abc123",
            "receipt_id": "receipt_test",
            "timestamp": 1_778_000_000.0,
            "work_type": "test",
            "work_value": 1.0,
        }
        result = check_invariants([row], profile="work_receipts")
        assert result.ok, result.summary()
        assert result.legacy_rows == 1
        assert result.modern_rows == 0

    def test_work_receipt_shape_still_fails_under_trace_profile(self) -> None:
        """The looser work receipt profile must not weaken the trace ledger."""
        row = {
            "agent_id": "auditor_test",
            "node_serial": "GTH4921YP3",
            "receipt_hash": "abc123",
            "timestamp": 1_778_000_000.0,
        }
        result = check_invariants([row])
        assert not result.ok
        assert "required_keys" in {v.rule for v in result.violations}

    def test_unknown_profile_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown ledger audit profile"):
            check_invariants([], profile="unknown")

    def test_modern_row_count_positive(self) -> None:
        rows = load_sanitized_fixture(FIXTURES / "sanitized_trace.jsonl")
        result = check_invariants(rows)
        assert result.modern_rows >= 5

    def test_all_required_keys_present_in_fixture(self) -> None:
        rows = load_sanitized_fixture(FIXTURES / "sanitized_trace.jsonl")
        modern = [r for r in rows if "trace_id" in r]
        for r in modern:
            missing = REQUIRED_KEYS - r.keys()
            assert not missing, f"fixture row missing {missing}: {r}"


# ── 3. Invariant checker — negative (bad_rows fixture) ───────────────────

class TestCheckInvariantsNegative:
    def test_bad_rows_fixture_fails(self) -> None:
        rows = load_sanitized_fixture(FIXTURES / "bad_rows.jsonl")
        result = check_invariants(rows)
        assert not result.ok, "Expected violations in bad_rows.jsonl but got none"

    def test_missing_required_keys_detected(self) -> None:
        """Row with no trace_id or homeworld_serial → required_keys violation."""
        import json
        row = {
            "ts": 1_778_000_000.0,
            "source_ide": "bad_ide",
            "kind": "LLM_REGISTRATION",
            "payload": '{"intent":"no trace_id"}',
            # missing: trace_id, homeworld_serial
        }
        result = check_invariants([row])
        rules = [v.rule for v in result.violations]
        assert "required_keys" in rules

    def test_empty_scar_payload_detected(self) -> None:
        """SCAR_RECEIPT with empty payload → payload_required violation."""
        row = {
            "trace_id": "t1", "ts": 1.0, "source_ide": "test",
            "kind": "SCAR_RECEIPT", "payload": "",
            "homeworld_serial": "SER",
        }
        result = check_invariants([row])
        rules = [v.rule for v in result.violations]
        assert "payload_required" in rules

    def test_non_numeric_ts_detected(self) -> None:
        row = {
            "trace_id": "t1", "ts": "bad", "source_ide": "test",
            "kind": "immune_intervention", "payload": "{}",
            "homeworld_serial": "SER",
        }
        result = check_invariants([row])
        rules = [v.rule for v in result.violations]
        assert "ts_numeric" in rules

    def test_empty_homeworld_serial_detected(self) -> None:
        row = {
            "trace_id": "t1", "ts": 1.0, "source_ide": "test",
            "kind": "LLM_SIGNOUT", "payload": "{}",
            "homeworld_serial": "",
        }
        result = check_invariants([row])
        rules = [v.rule for v in result.violations]
        assert "homeworld_serial_nonempty" in rules

    def test_zero_ts_detected(self) -> None:
        row = {
            "trace_id": "t1", "ts": 0.0, "source_ide": "test",
            "kind": "LLM_SIGNOUT", "payload": "{}",
            "homeworld_serial": "SER",
        }
        result = check_invariants([row])
        rules = [v.rule for v in result.violations]
        assert "ts_positive" in rules

    def test_parse_error_row_flagged(self) -> None:
        """Malformed JSON row must produce a json_parseable violation."""
        row = {"_parse_error": "Expecting value: line 1 column 1", "_lineno": 1}
        result = check_invariants([row])
        assert not result.ok
        rules = [v.rule for v in result.violations]
        assert "json_parseable" in rules


# ── 4. AuditResult dataclass ─────────────────────────────────────────────

class TestAuditResult:
    def test_ok_when_no_violations(self) -> None:
        r = AuditResult(path="test")
        assert r.ok

    def test_not_ok_when_violations_present(self) -> None:
        r = AuditResult(path="test")
        r.violations.append(AuditViolation(0, "kind", "rule", "detail"))
        assert not r.ok

    def test_summary_contains_pass_marker(self) -> None:
        r = AuditResult(path="p")
        assert "PASS" in r.summary()

    def test_summary_contains_fail_marker(self) -> None:
        r = AuditResult(path="p")
        r.violations.append(AuditViolation(0, "k", "r", "d"))
        s = r.summary()
        assert "FAIL" in s
        assert "INVARIANT_FAIL" in s


# ── 5. audit_ledger() convenience wrapper ────────────────────────────────

class TestAuditLedger:
    def test_sanitized_trace_passes(self, capsys: pytest.CaptureFixture) -> None:
        ok = audit_ledger(FIXTURES / "sanitized_trace.jsonl")
        assert ok
        out = capsys.readouterr().out
        assert "PASS" in out

    def test_sanitized_receipts_passes(self, capsys: pytest.CaptureFixture) -> None:
        ok = audit_ledger(FIXTURES / "sanitized_receipts.jsonl")
        assert ok

    def test_audit_live_uses_work_receipts_profile(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        import json

        trace_path = tmp_path / "trace.jsonl"
        receipts_path = tmp_path / "work_receipts.jsonl"
        trace_row = {
            "trace_id": "t1",
            "ts": 1.0,
            "source_ide": "test",
            "kind": "LLM_SIGNOUT",
            "payload": "{}",
            "homeworld_serial": "SER",
        }
        receipt_row = {
            "agent_id": "auditor_test",
            "description": "old work receipt shape",
            "node_serial": "SER",
            "receipt_hash": "hash",
            "receipt_id": "receipt",
            "timestamp": 1.0,
            "work_type": "test",
            "work_value": 1.0,
        }
        trace_path.write_text(json.dumps(trace_row) + "\n", encoding="utf-8")
        receipts_path.write_text(json.dumps(receipt_row) + "\n", encoding="utf-8")

        ok, trace_result, receipt_result = audit_live(
            trace_path=trace_path,
            receipts_path=receipts_path,
            verbose=True,
        )

        assert ok
        assert trace_result.modern_rows == 1
        assert receipt_result.legacy_rows == 1
        out = capsys.readouterr().out
        assert "PASS" in out

    def test_bad_rows_fails(self, capsys: pytest.CaptureFixture) -> None:
        ok = audit_ledger(FIXTURES / "bad_rows.jsonl")
        assert not ok
        out = capsys.readouterr().out
        assert "FAIL" in out or "INVARIANT_FAIL" in out


# ── 6. assert_row_valid() hot-path hook ──────────────────────────────────

class TestAssertRowValid:
    def test_valid_row_does_not_raise(self) -> None:
        row = {
            "trace_id": "t1", "ts": 1.0, "source_ide": "test",
            "kind": "LLM_REGISTRATION",
            "payload": '{"intent":"test"}',
            "homeworld_serial": "SER",
        }
        assert_row_valid(row, strict=True)  # must not raise

    def test_legacy_row_tolerated(self) -> None:
        row = {
            "system": "swarm_x", "event": "tick", "device": "SER",
            "reason": "scheduled", "resolution": "ok", "ts": 1.0,
        }
        assert_row_valid(row, strict=True)  # legacy — must not raise

    def test_invalid_row_raises_in_strict_mode(self) -> None:
        row = {
            # missing trace_id and homeworld_serial
            "ts": 1.0, "source_ide": "test",
            "kind": "SCAR_RECEIPT", "payload": "",
        }
        with pytest.raises(ValueError, match="Ledger invariant violation"):
            assert_row_valid(row, strict=True)

    def test_invalid_row_prints_warning_in_soft_mode(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        row = {
            "ts": 1.0, "source_ide": "test",
            "kind": "SCAR_RECEIPT", "payload": "",
            # missing trace_id, homeworld_serial
        }
        assert_row_valid(row, strict=False)  # must not raise
        out = capsys.readouterr().out
        assert "WARNING" in out or "INVARIANT_FAIL" in out


# ── 7. Schema constants sanity ───────────────────────────────────────────

class TestSchemaConstants:
    def test_required_keys_set(self) -> None:
        assert "trace_id" in REQUIRED_KEYS
        assert "ts" in REQUIRED_KEYS
        assert "kind" in REQUIRED_KEYS
        assert "source_ide" in REQUIRED_KEYS
        assert "homeworld_serial" in REQUIRED_KEYS

    def test_scar_is_effector_kind(self) -> None:
        assert "SCAR_RECEIPT" in EFFECTOR_KINDS

    def test_llm_registration_is_effector_kind(self) -> None:
        assert "LLM_REGISTRATION" in EFFECTOR_KINDS

    def test_scar_requires_payload(self) -> None:
        assert "SCAR_RECEIPT" in PAYLOAD_REQUIRED_KINDS

    def test_llm_registration_requires_payload(self) -> None:
        assert "LLM_REGISTRATION" in PAYLOAD_REQUIRED_KINDS
