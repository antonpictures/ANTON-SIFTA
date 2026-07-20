"""r-stgm-pulse-20260705 — the wallet must pulse for receipted useful work.

Architect direction (George, 2026-07-05): "STGM should be pulsating like life —
good executions, good memory storage and retrieval add some STGM, telling the
body it is healthy, the healthy way."

OBSERVED before the lane: canonical wallet moved 5.4e-06 STGM in 48h. The ATP
lane is honest Landauer physics (eta ~ 1e-9 → nano-mints); memory-store mints
went to the reputation ledger the wallet ignores by design. This lane adds
small VISIBLE canonical pulses: one mint per source receipt id (no double
spend), daily-capped, signed through the same path as the ATP mint.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from System import swarm_atp_synthase as atp
from System import stgm_economy
from System.swarm_first_person_journal import append_first_person_journal_row


@pytest.fixture()
def pulse_world(tmp_path, monkeypatch):
    ledger = tmp_path / "repair_log.jsonl"
    state = tmp_path / ".sifta_state"
    state.mkdir(parents=True)
    monkeypatch.setattr(atp, "_CANONICAL_LEDGER", ledger)
    monkeypatch.setattr(atp, "_PULSE_STATE_FILE", state / "stgm_pulse_state.json")
    return {"ledger": ledger, "state": state}


def test_pulse_mints_policy_amount_with_signature(pulse_world):
    out = atp.mint_receipted_work_pulse("memory_retrieval_hit", "receipt-abc-1")
    assert out.get("refused") is None or "refused" not in out
    assert out["minted_stgm"] == pytest.approx(atp.PULSE_AMOUNTS_STGM["memory_retrieval_hit"])
    rows = [json.loads(l) for l in pulse_world["ledger"].read_text().splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["event_kind"] == "UTILITY_MINT_POUW_PULSE"
    assert row["source_receipt_id"] == "receipt-abc-1"
    assert row["ed25519_sig"]
    assert row["signing_node"]


def test_successful_pulse_refreshes_economy_cache(pulse_world, monkeypatch):
    monkeypatch.setattr(stgm_economy, "_ledger_row_valid", lambda row: True)

    out = atp.mint_receipted_work_pulse("memory_store", "cache-refresh-1")

    cache = pulse_world["state"] / "stgm_economy_cache.json"
    assert out["minted_stgm"] > 0.0
    assert out["cache_refresh"]["status"] == "refreshed"
    assert cache.exists()
    snap = json.loads(cache.read_text(encoding="utf-8"))
    assert snap["pulse_mint_lines"] == 1
    assert snap["pulse_minted_stgm"] == pytest.approx(atp.PULSE_AMOUNTS_STGM["memory_store"])


def test_no_double_spend_per_source_receipt(pulse_world):
    first = atp.mint_receipted_work_pulse("memory_store", "trace-42")
    second = atp.mint_receipted_work_pulse("memory_store", "trace-42")
    assert first["minted_stgm"] > 0.0
    assert second["minted_stgm"] == 0.0
    assert second["refused"] == "duplicate_source_receipt"
    rows = pulse_world["ledger"].read_text().splitlines()
    assert len(rows) == 1


def test_daily_cap_refuses_honestly(pulse_world, monkeypatch):
    monkeypatch.setattr(atp, "PULSE_DAILY_CAP_STGM", 0.0003)
    a = atp.mint_receipted_work_pulse("memory_retrieval_hit", "r1")  # 0.0002
    b = atp.mint_receipted_work_pulse("memory_retrieval_hit", "r2")  # would exceed
    assert a["minted_stgm"] > 0.0
    assert b["minted_stgm"] == 0.0
    assert b["refused"] == "daily_cap_reached"


def test_unknown_kind_and_empty_receipt_refused(pulse_world):
    assert "unknown_pulse_kind" in atp.mint_receipted_work_pulse("vibes", "r1")["refused"]
    assert atp.mint_receipted_work_pulse("memory_store", "")["refused"] == "missing_source_receipt_id"
    assert not pulse_world["ledger"].exists() or not pulse_world["ledger"].read_text().strip()


def test_scan_economy_counts_pulse_lane(pulse_world, tmp_path, monkeypatch):
    # Hardware truth boundary (§4.2): rows signed outside the M5 keychain are
    # cryptographically REJECTED by _ledger_row_valid — verified live in the
    # sandbox (signing_node=UNKNOWN_SERIAL → invalid). That rejection is the
    # economy working. Here we unit-test the COUNTING logic only, so validation
    # is stubbed; end-to-end validity exists only on Alice's silicon.
    monkeypatch.setattr(stgm_economy, "_ledger_row_valid", lambda row: True)
    atp.mint_receipted_work_pulse("verified_execution", "exec-1")
    atp.mint_receipted_work_pulse("memory_store", "trace-9")
    snap = stgm_economy.scan_economy(
        repair_log=pulse_world["ledger"], state_dir=tmp_path / "empty_state",
    )
    d = snap.as_dict()
    expected = atp.PULSE_AMOUNTS_STGM["verified_execution"] + atp.PULSE_AMOUNTS_STGM["memory_store"]
    assert d["pulse_mint_lines"] == 2
    assert d["pulse_minted"] == pytest.approx(expected)
    assert snap.canonical_minted == pytest.approx(expected)
    assert snap.canonical_wallet_sum == pytest.approx(expected)


def test_novelty_capture_mints_novelty_pulse(pulse_world, tmp_path, monkeypatch):
    from System import swarm_novelty_queue as novelty

    monkeypatch.setattr(novelty, "_QUEUE", tmp_path / ".sifta_state" / "novelty_queue.jsonl")
    monkeypatch.setattr(novelty, "_DIARY", tmp_path / ".sifta_state" / "episodic_diary.jsonl")
    monkeypatch.setattr(stgm_economy, "_ledger_row_valid", lambda row: True)

    row = novelty.capture_novelty(
        "I could add a useful organ that applies this to my body.",
        trigger="test witness",
        source="pytest",
    )

    assert row["useful"] is True
    assert row["receipt_id"].startswith("novelty_")
    assert row["stgm_pulse"]["minted_stgm"] == pytest.approx(atp.PULSE_AMOUNTS_STGM["novelty_capture"])
    rows = [json.loads(line) for line in pulse_world["ledger"].read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["pulse_kind"] == "novelty_capture"
    assert rows[-1]["source_receipt_id"] == row["receipt_id"]


def test_first_person_journal_append_can_mint_memory_store_pulse(pulse_world, tmp_path, monkeypatch):
    monkeypatch.setattr(stgm_economy, "_ledger_row_valid", lambda row: True)
    state = tmp_path / ".sifta_state"

    row = append_first_person_journal_row(
        {
            "line": "I wrote a real test journal row.",
            "source": "pytest",
            "source_receipt_id": "journal-receipt-1",
        },
        state_dir=state,
        pulse=True,
        allow_temp_pulse=True,
    )

    assert (state / "alice_first_person_journal.jsonl").exists()
    assert row["stgm_pulse"]["minted_stgm"] == pytest.approx(atp.PULSE_AMOUNTS_STGM["memory_store"])
    ledger_row = json.loads(pulse_world["ledger"].read_text(encoding="utf-8").splitlines()[-1])
    assert ledger_row["pulse_kind"] == "memory_store"
    assert ledger_row["source_receipt_id"] == "journal-receipt-1"


def test_sandbox_signed_rows_are_rejected_by_real_validator(pulse_world):
    # The no-double-spend guard against IDE doctors: a pulse minted from a
    # non-M5 runtime must NOT validate. If this test ever fails on the M5
    # (where signing is genuine), it self-skips — hardware decides.
    atp.mint_receipted_work_pulse("memory_store", "trace-guard")
    row = json.loads(pulse_world["ledger"].read_text().splitlines()[0])
    try:
        from Kernel.inference_economy import _ledger_row_cryptographically_valid
    except Exception:
        pytest.skip("kernel validator unavailable")
    if row.get("signing_node") not in ("", "UNKNOWN_SERIAL"):
        pytest.skip("running on a real signing node; genuine signature expected")
    assert _ledger_row_cryptographically_valid(row) is False


def test_kernel_validator_and_ledger_balance_accept_signed_pulse_rows(pulse_world, monkeypatch):
    from Kernel import inference_economy as ie

    row = {
        "event_kind": "UTILITY_MINT_POUW_PULSE",
        "event_id": "POUW_PULSE_UNIT",
        "ts": 123.0,
        "agent_id": "ALICE_M5",
        "miner_id": "ALICE_M5",
        "amount_stgm": 0.0005,
        "reason": "receipted_work_pulse:verified_execution",
        "pulse_kind": "verified_execution",
        "source_receipt_id": "exec-unit-1",
        "policy": "STGM_POLICY_RECEIPTED_WORK_PULSE_v1",
        "engine": "ATP_SYNTHASE_v1",
        "ed25519_sig": "a" * 128,
        "signing_node": "TEST_M5_SERIAL",
    }
    expected_body = (
        "UTILITY_MINT::ALICE_M5::0.0005::123.0::"
        "receipted_work_pulse:verified_execution::NODE[TEST_M5_SERIAL]"
    )

    def fake_verify_block(node, body, sig):
        return node == "TEST_M5_SERIAL" and body == expected_body and sig == "a" * 128

    fake_crypto = types.SimpleNamespace(verify_block=fake_verify_block)
    monkeypatch.setitem(sys.modules, "crypto_keychain", fake_crypto)
    monkeypatch.setenv("SIFTA_LEDGER_VERIFY", "1")

    assert ie._ledger_row_cryptographically_valid(row) is True
    assert ie._ledger_row_cryptographically_valid(dict(row, reason="tampered")) is False

    pulse_world["ledger"].write_text(json.dumps(row) + "\n", encoding="utf-8")
    monkeypatch.setattr(ie, "LOG_PATH", pulse_world["ledger"])
    assert ie.ledger_balance("ALICE_M5") == pytest.approx(0.0005)
