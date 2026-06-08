"""Round 81 Slice C tests — predator gate writer §4.1 fan-out.

Verifies that one call to ``write_ide_surgery_receipt`` lands a row in
ALL four canonical ledgers (work_receipts, agent_arm_receipts,
ide_stigmergic_trace, episodic_diary) with consistent receipt_id and
round_id, and that partial failures surface in the return status.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from System import swarm_predator_gate_writer as gate


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


# ─── Happy path ────────────────────────────────────────────────────────────


def test_writes_to_all_four_canonical_ledgers(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    status = gate.write_ide_surgery_receipt(
        round_id="r81-test",
        doctor="claude-opus-cowork",
        model="claude-opus-4-7",
        files_touched=["System/foo.py", "tests/test_foo.py"],
        tests_green="3/3 green",
        summary="round 81 dogfood test fanout",
        receipt_id="r81-test-fanout-001",
        state_dir=state,
    )

    assert set(status.keys()) == set(gate.CANONICAL_LEDGERS)
    for ledger in gate.CANONICAL_LEDGERS:
        assert status[ledger] == "ok", f"{ledger} status was {status[ledger]!r}"
        path = state / ledger
        assert path.exists(), f"{ledger} not created"
        rows = _load_jsonl(path)
        assert len(rows) == 1, f"{ledger} should have exactly one row"
        row = rows[0]
        assert row["receipt_id"] == "r81-test-fanout-001"
        assert row["round_id"] == "r81-test"
        assert row["doctor"] == "claude-opus-cowork"
        assert row["model"] == "claude-opus-4-7"
        assert row["files_touched"] == ["System/foo.py", "tests/test_foo.py"]
        assert row["tests_green"] == "3/3 green"
        assert "round 81 dogfood test fanout" in row["summary"]
        assert "signing_serial" not in row
        assert row["receipt_class"] == gate.IDE_RECEIPT_CLASS
        assert row["cryptographic_integrity"] == gate.IDE_CRYPTOGRAPHIC_INTEGRITY
        assert row["lane"] == gate.IDE_DOCTOR_LANE
        assert row["currency"] == gate.IDE_DOCTOR_CURRENCY
        assert row["runtime"] == gate.IDE_DOCTOR_RUNTIME
        assert row["forgeable"] is True
        assert row["alice_swimmer_receipt"] is False
        assert row["forgeable_by_local_file_writer"] is True
        assert "not an Alice" in row["receipt_boundary_note"]
        assert row["ide_mana_namespace"] == gate.IDE_MANA_NAMESPACE
        assert row["ide_mana_settlement"] == gate.IDE_MANA_SETTLEMENT
        assert "sandbox-only coordination namespace" in row["ide_mana_note"]
        assert row["organism_economy_receipt"] is False
        assert row["organism_economy_access"] is False
        assert row["organism_mint_or_spend"] is False
        assert row["truth_label"] == "OPERATIONAL"
        assert row["ledger_name"] == ledger


def test_ide_receipts_marked_as_forgeable_not_swimmer_proofs(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    status = gate.write_ide_surgery_receipt(
        round_id="r-taxonomy",
        doctor="codex",
        model="gpt-5-codex",
        files_touched=["System/foo.py"],
        tests_green="ok",
        summary="taxonomy boundary",
        receipt_id="rid-taxonomy",
        state_dir=state,
    )

    assert gate.all_ok(status) is True
    row = _load_jsonl(state / "work_receipts.jsonl")[0]
    assert row["receipt_class"] == "IDE_DOCTOR_OPERATIONAL_TRACE"
    assert row["cryptographic_integrity"] == "NONE_FORGEABLE_LOCAL_JSONL"
    assert row["lane"] == "IDE_DOCTOR_CLAIM"
    assert row["currency"] == "MANA"
    assert row["runtime"] == "ide_doctor_sandbox_or_external_server"
    assert row["forgeable"] is True
    assert row["alice_swimmer_receipt"] is False
    assert row["forgeable_by_local_file_writer"] is True
    assert "local JSONL coordination trace only" in row["receipt_boundary_note"]
    assert "not an Alice hardware-bound cryptographic swimmer receipt" in row[
        "receipt_boundary_note"
    ]


def test_ide_receipts_carry_hardware_time_oracle_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from System import swarm_hardware_time_oracle

    def fake_current_time_for_alice() -> dict:
        return {
            "ok": True,
            "source": "hardware_time_oracle",
            "confidence": 1.0,
            "local_human": "Sunday June 07 2026, 06:35 AM",
            "timezone": "PDT",
            "local_iso": "2026-06-07T06:35:00-07:00",
            "epoch": 1780839300.0,
            "signature": "abc123def456",
        }

    monkeypatch.setattr(
        swarm_hardware_time_oracle,
        "current_time_for_alice",
        fake_current_time_for_alice,
    )

    state = tmp_path / ".sifta_state"
    status = gate.write_ide_surgery_receipt(
        round_id="r-time-provenance",
        doctor="codex",
        model="gpt-5-codex",
        files_touched=["System/swarm_predator_gate_writer.py"],
        tests_green="ok",
        summary="clock provenance check",
        receipt_id="rid-time-provenance",
        state_dir=state,
    )

    assert gate.all_ok(status) is True
    row = _load_jsonl(state / "work_receipts.jsonl")[0]
    assert row["action_oracle_ts"] == "2026-06-07T06:35:00-07:00"
    assert row["action_oracle_epoch"] == 1780839300.0
    assert row["action_oracle_source"] == "hardware_time_oracle"
    assert row["action_oracle_timezone"] == "PDT"
    assert row["action_oracle_signature"] == "abc123def456"


def test_ide_receipts_use_mana_namespace_not_organism_economy(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    status = gate.write_ide_surgery_receipt(
        round_id="r-mana-boundary",
        doctor="codex",
        model="gpt-5-codex",
        files_touched=["System/foo.py"],
        tests_green="ok",
        summary="mana boundary",
        receipt_id="rid-mana-boundary",
        state_dir=state,
    )

    assert gate.all_ok(status) is True
    row = _load_jsonl(state / "work_receipts.jsonl")[0]
    assert "stgm_receipt" not in row
    assert "stgm_economy_access" not in row
    assert "stgm_mint_or_spend" not in row
    assert "stgm_boundary_note" not in row
    assert row["ide_mana_namespace"] == "IDE_MANA_COORDINATION_ONLY"
    assert row["ide_mana_settlement"] == "USD_EXTERNAL_OWNER_PAID"
    assert "cannot mint, spend, earn, settle, or claim the organism token" in row[
        "ide_mana_note"
    ]
    assert row["organism_economy_receipt"] is False
    assert row["organism_economy_access"] is False
    assert row["organism_mint_or_spend"] is False


def test_all_ok_helper(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    status = gate.write_ide_surgery_receipt(
        round_id="r-helper",
        doctor="claude",
        model="claude-opus-4-7",
        files_touched=[],
        tests_green="ok",
        summary="helper smoke",
        receipt_id="rid-helper",
        state_dir=state,
    )
    assert gate.all_ok(status) is True


def test_all_ok_returns_false_when_any_ledger_failed() -> None:
    status = {name: "ok" for name in gate.CANONICAL_LEDGERS}
    # First sanity-check all_ok agrees the clean state is ok
    assert gate.all_ok(status) is True
    # Then flip one entry to a failure string
    status["ide_stigmergic_trace.jsonl"] = "PermissionError: denied"
    assert gate.all_ok(status) is False


def test_all_ok_false_for_empty_status() -> None:
    assert gate.all_ok({}) is False


# ─── Per-ledger key shape ─────────────────────────────────────────────────


def test_legacy_filter_keys_present_per_ledger(tmp_path: Path) -> None:
    """Each ledger has historical consumers that filter on different keys.
    The fan-out must mirror the base action under the keys those filters
    look at so the new row is visible to legacy code."""
    state = tmp_path / ".sifta_state"
    gate.write_ide_surgery_receipt(
        round_id="r-legacy",
        doctor="claude",
        model="claude-opus-4-7",
        files_touched=["x.py"],
        tests_green="ok",
        summary="legacy filter keys",
        receipt_id="rid-legacy",
        state_dir=state,
    )
    trace = _load_jsonl(state / "ide_stigmergic_trace.jsonl")[0]
    arm = _load_jsonl(state / "agent_arm_receipts.jsonl")[0]
    diary = _load_jsonl(state / "episodic_diary.jsonl")[0]
    work = _load_jsonl(state / "work_receipts.jsonl")[0]

    assert "event" in trace
    assert "event" in arm
    assert "kind" in diary
    assert "action" in work


# ─── Files-touched coercion ───────────────────────────────────────────────


def test_files_touched_accepts_string(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    gate.write_ide_surgery_receipt(
        round_id="r-str-files",
        doctor="claude",
        model="claude-opus-4-7",
        files_touched="System/single.py",
        tests_green="ok",
        summary="single file as str",
        receipt_id="rid-str",
        state_dir=state,
    )
    row = _load_jsonl(state / "work_receipts.jsonl")[0]
    assert row["files_touched"] == ["System/single.py"]


def test_files_touched_accepts_none(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    gate.write_ide_surgery_receipt(
        round_id="r-none",
        doctor="claude",
        model="claude-opus-4-7",
        files_touched=None,
        tests_green="ok",
        summary="no files",
        receipt_id="rid-none",
        state_dir=state,
    )
    row = _load_jsonl(state / "work_receipts.jsonl")[0]
    assert row["files_touched"] == []


# ─── Extra payload merge ──────────────────────────────────────────────────


def test_extra_payload_merged(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    gate.write_ide_surgery_receipt(
        round_id="r-extra",
        doctor="claude",
        model="claude-opus-4-7",
        files_touched=["a.py"],
        tests_green="ok",
        summary="extra payload merge",
        receipt_id="rid-extra",
        state_dir=state,
        extra={"covenant": "§4.1 §6 §7.5", "slice": "C"},
    )
    row = _load_jsonl(state / "work_receipts.jsonl")[0]
    assert row["covenant"] == "§4.1 §6 §7.5"
    assert row["slice"] == "C"


def test_extra_cannot_overwrite_required_fields(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    gate.write_ide_surgery_receipt(
        round_id="r-protect",
        doctor="claude",
        model="claude-opus-4-7",
        files_touched=["a.py"],
        tests_green="ok",
        summary="extra cannot overwrite base",
        receipt_id="rid-protect",
        state_dir=state,
        extra={"receipt_id": "HACKED", "round_id": "HACKED"},
    )
    row = _load_jsonl(state / "work_receipts.jsonl")[0]
    assert row["receipt_id"] == "rid-protect"
    assert row["round_id"] == "r-protect"


def test_extra_cannot_inject_hardware_or_stgm_fields(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    gate.write_ide_surgery_receipt(
        round_id="r-protect-lanes",
        doctor="claude",
        model="claude-opus-4-7",
        files_touched=["a.py"],
        tests_green="ok",
        summary="extra cannot inject forbidden lanes",
        receipt_id="rid-protect-lanes",
        state_dir=state,
        extra={
            "signing_serial": "GTH4921YP3",
            "stgm_receipt": True,
            "stgm_credit": 100,
            "safe_extra": "kept",
        },
    )
    row = _load_jsonl(state / "work_receipts.jsonl")[0]
    assert "signing_serial" not in row
    assert "stgm_receipt" not in row
    assert "stgm_credit" not in row
    assert row["safe_extra"] == "kept"


# ─── Atomicity-ish: one call writes exactly one row per ledger ────────────


def test_two_calls_produce_two_rows_per_ledger(tmp_path: Path) -> None:
    state = tmp_path / ".sifta_state"
    for i in range(2):
        gate.write_ide_surgery_receipt(
            round_id=f"r-twice-{i}",
            doctor="claude",
            model="claude-opus-4-7",
            files_touched=[f"f{i}.py"],
            tests_green="ok",
            summary=f"call {i}",
            receipt_id=f"rid-twice-{i}",
            state_dir=state,
        )
    for ledger in gate.CANONICAL_LEDGERS:
        rows = _load_jsonl(state / ledger)
        assert len(rows) == 2


# ─── Real .sifta_state isolation (test uses tmp_path only) ────────────────


def test_real_ledger_isolation(tmp_path: Path) -> None:
    real = Path(".sifta_state")
    watched = [real / name for name in gate.CANONICAL_LEDGERS]
    before = {str(p): (p.stat().st_size if p.exists() else 0) for p in watched}

    state = tmp_path / ".sifta_state"
    gate.write_ide_surgery_receipt(
        round_id="r-isolation",
        doctor="claude",
        model="claude-opus-4-7",
        files_touched=["only/tmp.py"],
        tests_green="ok",
        summary="isolation check",
        receipt_id="rid-isolation",
        state_dir=state,
    )

    after = {str(p): (p.stat().st_size if p.exists() else 0) for p in watched}
    for k in before:
        assert before[k] == after[k], f"predator gate writer mutated {k}"
