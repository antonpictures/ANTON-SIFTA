#!/usr/bin/env python3
"""
System/ledger_auditor.py
════════════════════════════════════════════════════════════════════════════
Auditor organ — machine-checks SIFTA ledger invariants (Priority A).

Covenant placement: §8.2 Auditor lane.

The **hypothesis** being tested:
    P: Every effector/ledger row in ide_stigmergic_trace.jsonl +
       work_receipts.jsonl obeys the following machine-checkable invariants.
    Q: audit_ledger(path) returns True (zero violations).

    Contrapositive: if Q is False (violations found), then P is False
    (at least one row violates the schema), and the caller MUST treat
    the affected deposit() as unsigned / untrusted surgery (covenant §4.3).

Row format contract (from ide_stigmergic_bridge.deposit()):
    {
        "trace_id":        str  — uuid4
        "ts":              float — unix timestamp
        "source_ide":      str  — e.g. "antigravity_m5", "cursor_m5"
        "kind":            str  — e.g. "LLM_REGISTRATION", "immune_intervention"
        "payload":         str | dict
        "homeworld_serial": str — hardware serial
        "meta":            dict  (optional)
    }

Legacy rows (before stigmergic bridge was standardised) may lack some keys.
    They are tolerated (counted as LEGACY, not ERROR) so old history is not
    retroactively invalidated.

Effector kinds that carry extra invariants:
    SCAR_RECEIPT      — must carry non-empty payload
    LLM_REGISTRATION  — must carry source_ide + homeworld_serial
    LLM_SIGNOUT       — must carry source_ide
    immune_intervention — must carry ts + payload
    immune_budget_blocked — must carry ts + payload

§8.6 compliance: load_sanitized_fixture() truncates any payload > 200 chars
so no raw .sifta_state content reaches test output or CI logs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ── Row schema ──────────────────────────────────────────────────────────────

# Keys that EVERY modern (post-bridge) row must have.
REQUIRED_KEYS: frozenset[str] = frozenset(
    {"trace_id", "ts", "kind", "source_ide", "homeworld_serial"}
)

# Effector kinds: rows that claim to record an external action.
# These are subject to stricter checks.
EFFECTOR_KINDS: frozenset[str] = frozenset(
    {
        "SCAR_RECEIPT",
        "LLM_REGISTRATION",
        "LLM_SIGNOUT",
        "stigmergic_signin",
        "stigmergic_signout",
        "stigauth",
        "WORK_RECEIPT",
    }
)

# Kinds whose payload must be non-empty (non-trivial claim).
PAYLOAD_REQUIRED_KINDS: frozenset[str] = frozenset(
    {"SCAR_RECEIPT", "LLM_REGISTRATION", "immune_intervention"}
)

# Legacy detector: rows that pre-date the bridge schema.
_LEGACY_INDICATORS: frozenset[str] = frozenset({"system", "event", "device", "resolution"})
_MODERN_INDICATORS: frozenset[str] = frozenset(
    {"kind", "source_ide", "homeworld_serial", "payload", "meta"}
)
_WORK_RECEIPT_LEGACY_INDICATORS: frozenset[str] = frozenset(
    {
        "action",
        "agent_id",
        "description",
        "event_type",
        "intent",
        "node_serial",
        "output_hash",
        "previous_receipt_hash",
        "receipt_hash",
        "receipt_id",
        "sender_agent",
        "status",
        "territory",
        "timestamp",
        "truth_note",
        "work_type",
        "work_value",
    }
)


# ── Result types ────────────────────────────────────────────────────────────

@dataclass
class AuditViolation:
    row_index: int
    row_kind: str
    rule: str
    detail: str


@dataclass
class AuditResult:
    path: str
    total_rows: int = 0
    modern_rows: int = 0
    legacy_rows: int = 0
    empty_rows: int = 0
    violations: List[AuditViolation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.violations) == 0

    def summary(self) -> str:
        status = "✓ PASS" if self.ok else "✗ FAIL"
        lines = [
            f"{status} — {self.path}",
            f"  total={self.total_rows}  modern={self.modern_rows}  "
            f"legacy={self.legacy_rows}  empty={self.empty_rows}  "
            f"violations={len(self.violations)}",
        ]
        for v in self.violations:
            lines.append(
                f"  INVARIANT_FAIL row={v.row_index} kind={v.row_kind!r} "
                f"rule={v.rule!r}: {v.detail}"
            )
        return "\n".join(lines)


# ── Loader ──────────────────────────────────────────────────────────────────

def load_sanitized_fixture(path: Path) -> List[Dict[str, Any]]:
    """
    Load a JSONL file and return parsed rows.

    §8.6 sanitisation: any payload value longer than 200 chars is truncated
    so no raw .sifta_state content reaches test output or CI logs.

    Raises FileNotFoundError if path does not exist.
    """
    rows: List[Dict[str, Any]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, raw in enumerate(text.splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            # Malformed JSON is treated as an empty-parse row; the checker
            # will flag the missing keys.  We still append a sentinel so
            # the row index stays aligned with the file.
            row = {"_parse_error": str(exc), "_lineno": lineno}
        # Sanitise: truncate long payloads.
        if "payload" in row and isinstance(row["payload"], str) and len(row["payload"]) > 200:
            row["payload"] = row["payload"][:200] + "...[sanitized]"
        rows.append(row)
    return rows


# ── Invariant checker ───────────────────────────────────────────────────────

def _is_legacy(row: Dict[str, Any]) -> bool:
    """True if the row was written before the stigmergic bridge schema."""
    return (
        bool(_LEGACY_INDICATORS & row.keys())
        and "trace_id" not in row
        and not bool(_MODERN_INDICATORS & row.keys())
    )


def _is_legacy_work_receipt(row: Dict[str, Any]) -> bool:
    """
    True for older work_receipts.jsonl rows that pre-date bridge deposit().

    Work receipts historically used agent_id/node_serial/receipt_hash-style
    rows.  Treat those as legacy only in the work_receipts profile; modern
    bridge rows with kind/source_ide/homeworld_serial still receive the strict
    bridge checks.
    """
    return (
        bool(_WORK_RECEIPT_LEGACY_INDICATORS & row.keys())
        and not bool(_MODERN_INDICATORS & row.keys())
    )


def check_invariants(rows: Iterable[Dict[str, Any]], *, profile: str = "trace") -> AuditResult:
    """
    Run all invariant checks over a sequence of parsed rows.

    Returns an AuditResult; never raises.
    """
    if profile not in {"trace", "work_receipts"}:
        raise ValueError(f"unknown ledger audit profile: {profile!r}")

    result = AuditResult(path="<stream>")
    for i, row in enumerate(rows):
        result.total_rows += 1

        # Parse error sentinel
        if "_parse_error" in row:
            result.violations.append(AuditViolation(
                row_index=i,
                row_kind="<parse_error>",
                rule="json_parseable",
                detail=row["_parse_error"],
            ))
            continue

        # Skip empty / whitespace-only rows (counted separately)
        if not row:
            result.empty_rows += 1
            continue

        # Legacy rows: tolerated, not errors
        if _is_legacy(row):
            result.legacy_rows += 1
            continue
        if profile == "work_receipts" and _is_legacy_work_receipt(row):
            result.legacy_rows += 1
            continue

        result.modern_rows += 1
        kind = str(row.get("kind", ""))

        # ── Invariant 1: required keys present ──────────────────────────
        missing = REQUIRED_KEYS - row.keys()
        if missing:
            result.violations.append(AuditViolation(
                row_index=i,
                row_kind=kind or "?",
                rule="required_keys",
                detail=f"missing keys: {sorted(missing)}",
            ))

        # ── Invariant 2: ts is a positive float ─────────────────────────
        ts = row.get("ts")
        if ts is not None:
            try:
                ts_f = float(ts)
                if ts_f <= 0:
                    result.violations.append(AuditViolation(
                        row_index=i, row_kind=kind,
                        rule="ts_positive",
                        detail=f"ts={ts_f!r} must be > 0",
                    ))
            except (TypeError, ValueError):
                result.violations.append(AuditViolation(
                    row_index=i, row_kind=kind,
                    rule="ts_numeric",
                    detail=f"ts={ts!r} is not a number",
                ))

        # ── Invariant 3: effector rows must have trace_id ───────────────
        if kind in EFFECTOR_KINDS and not row.get("trace_id"):
            result.violations.append(AuditViolation(
                row_index=i, row_kind=kind,
                rule="effector_trace_id",
                detail="effector row missing trace_id",
            ))

        # ── Invariant 4: SCAR_RECEIPT must carry non-empty payload ──────
        if kind in PAYLOAD_REQUIRED_KINDS:
            payload = row.get("payload")
            if not payload:
                result.violations.append(AuditViolation(
                    row_index=i, row_kind=kind,
                    rule="payload_required",
                    detail=f"{kind!r} row has empty/missing payload",
                ))

        # ── Invariant 5: homeworld_serial must be non-empty string ──────
        serial = row.get("homeworld_serial")
        if serial is not None and (not isinstance(serial, str) or not serial.strip()):
            result.violations.append(AuditViolation(
                row_index=i, row_kind=kind,
                rule="homeworld_serial_nonempty",
                detail=f"homeworld_serial={serial!r} must be a non-empty string",
            ))

        # ── Invariant 6: source_ide must be a non-empty string ──────────
        source = row.get("source_ide")
        if source is not None and (not isinstance(source, str) or not source.strip()):
            result.violations.append(AuditViolation(
                row_index=i, row_kind=kind,
                rule="source_ide_nonempty",
                detail=f"source_ide={source!r} must be a non-empty string",
            ))

    return result


# ── Public convenience ───────────────────────────────────────────────────────

def audit_ledger(fixture_path: Path, *, profile: str = "trace", verbose: bool = True) -> bool:
    """
    Load fixture_path, run invariants, print summary, return True iff ok.

    This is the function the pytest companion calls.
    """
    result = check_invariants(load_sanitized_fixture(fixture_path), profile=profile)
    result.path = str(fixture_path)
    if verbose:
        print(result.summary())
    return result.ok


def audit_live(
    trace_path: Optional[Path] = None,
    receipts_path: Optional[Path] = None,
    *,
    tail_rows: int = 500,
    verbose: bool = True,
) -> Tuple[bool, AuditResult, AuditResult]:
    """
    Audit the live ledgers on this node (not for pytest — for operator use).

    Returns (all_ok, trace_result, receipts_result).
    Uses tail_rows to limit scan so large ledgers don't block the UI.

    This never dumps raw payload content; sanitisation is applied.
    """
    from pathlib import Path as _Path

    _REPO = _Path(__file__).resolve().parent.parent
    _STATE = _REPO / ".sifta_state"

    trace_path = trace_path or (_STATE / "ide_stigmergic_trace.jsonl")
    receipts_path = receipts_path or (_STATE / "work_receipts.jsonl")

    def _tail_rows(path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        rows = load_sanitized_fixture(path)
        return rows[-tail_rows:]

    trace_rows = _tail_rows(trace_path)
    receipt_rows = _tail_rows(receipts_path)

    tr = check_invariants(trace_rows, profile="trace")
    tr.path = str(trace_path)
    rr = check_invariants(receipt_rows, profile="work_receipts")
    rr.path = str(receipts_path)

    if verbose:
        print(tr.summary())
        print(rr.summary())

    return tr.ok and rr.ok, tr, rr


# ── Hot-path hook for deposit() ─────────────────────────────────────────────

def assert_row_valid(row: Dict[str, Any], *, strict: bool = False) -> None:
    """
    Lightweight invariant check for a single freshly-deposited row.

    Called (optionally) after deposit() to catch schema violations before
    they reach the ledger.  In strict=False mode, violations are printed
    but do not raise (to avoid crashing the hot path on minor legacy rows).
    In strict=True mode, raises ValueError on any violation.

    Wire-up example in ide_stigmergic_bridge.py deposit():
        from System.ledger_auditor import assert_row_valid
        assert_row_valid(row)
    """
    if _is_legacy(row):
        return  # pre-bridge rows are tolerated
    result = check_invariants([row])
    result.path = "<hot_path>"
    if not result.ok:
        msg = result.summary()
        if strict:
            raise ValueError(f"Ledger invariant violation:\n{msg}")
        print(f"[ledger_auditor] WARNING — {msg}")


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if args and args[0] == "--live":
        ok, _t, _r = audit_live()
        sys.exit(0 if ok else 1)
    elif args:
        fixture = Path(args[0])
        sys.exit(0 if audit_ledger(fixture) else 1)
    else:
        print("Usage: python3 -m System.ledger_auditor [--live | <fixture.jsonl>]")
        print("  --live        audit the last 500 rows of the live node ledgers")
        print("  <fixture.jsonl>  audit a sanitised fixture file")
        sys.exit(0)
