"""
E01 — Quantifier gate (STIGMEROBOTICS / ROB 501 tournament).

∀ policy: a node has opened a registration session (LLM_REGISTRATION or
stigmergic_signin) before any gated effector row on the same homeworld_serial.

Schema: ide_stigmergic_bridge.deposit() rows (see System/ledger_auditor.py).

§8.6: fixtures only — never read live .sifta_state in this test.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from System.ledger_auditor import load_sanitized_fixture

FIXTURES = Path(__file__).parent / "fixtures"

# Kinds that establish ∀ "policy open" for this serial (Predator / sign-in).
_REGISTRATION_KINDS = frozenset({"LLM_REGISTRATION", "stigmergic_signin"})

# Kinds that require a prior registration on the same homeworld_serial (subset of EFFECTOR-ish).
_GATED_KINDS = frozenset(
    {
        "SCAR_RECEIPT",
        "immune_intervention",
        "immune_budget_blocked",
        "WORK_RECEIPT",
        "LLM_SIGNOUT",
        "stigmergic_signout",
        "stigauth",
    }
)


def _is_modern_row(row: dict) -> bool:
    if row.get("_parse_error"):
        return False
    if "trace_id" not in row:
        return False
    return True


def quantifier_gate_ok(rows: list[dict]) -> tuple[bool, str]:
    """Per (homeworld_serial, source_ide): gated rows only after a registration row from same body."""
    seen_reg: dict[tuple[str, str], bool] = {}
    for i, row in enumerate(rows):
        if not _is_modern_row(row):
            continue
        serial = row.get("homeworld_serial") or ""
        ide = row.get("source_ide") or ""
        key = (serial, ide)
        kind = row.get("kind") or ""
        if kind in _REGISTRATION_KINDS:
            seen_reg[key] = True
            continue
        if kind in _GATED_KINDS:
            if not seen_reg.get(key):
                return False, (
                    f"row {i} kind={kind!r} {key=} has no prior "
                    f"registration in {_REGISTRATION_KINDS!r}"
                )
    return True, ""


def test_e01_good_fixture_passes_quantifier_gate() -> None:
    path = FIXTURES / "stigmero_e01_quantifier_good.jsonl"
    rows = load_sanitized_fixture(path)
    ok, msg = quantifier_gate_ok(rows)
    assert ok, msg


def test_e01_bad_fixture_fails_quantifier_gate() -> None:
    path = FIXTURES / "stigmero_e01_quantifier_bad.jsonl"
    rows = load_sanitized_fixture(path)
    ok, msg = quantifier_gate_ok(rows)
    assert not ok
    assert "SCAR_RECEIPT" in msg or "registration" in msg


def test_e01_sanitized_trace_fixture_also_passes() -> None:
    """Regression: shared ledger fixture must satisfy E01 (or we fix the fixture)."""
    path = FIXTURES / "sanitized_trace.jsonl"
    rows = load_sanitized_fixture(path)
    ok, msg = quantifier_gate_ok(rows)
    assert ok, msg
