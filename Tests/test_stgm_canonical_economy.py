import json
from pathlib import Path

import pytest

from System import stgm_economy


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_memory_rewards_and_casino_do_not_count_as_wallet(tmp_path: Path) -> None:
    repair_log = tmp_path / "repair_log.jsonl"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "ALICE_M5.json").write_text(
        json.dumps({"id": "ALICE_M5", "homeworld_serial": "TEST_SERIAL"}),
        encoding="utf-8",
    )

    _append(repair_log, {"tx_type": "STGM_MINT", "agent_id": "ALICE_M5", "amount": 10.0})
    _append(repair_log, {"tx_type": "STGM_SPEND", "agent_id": "ALICE_M5", "amount": 2.0})
    _append(state_dir / "stgm_memory_rewards.jsonl", {"amount": 9999.0, "reason": "reputation"})
    _append(state_dir / "casino_vault.jsonl", {"player_delta": 5000.0, "action": "PAYOUT"})

    snap = stgm_economy.scan_economy(repair_log=repair_log, state_dir=state_dir)
    data = snap.as_dict()

    assert data["canonical_wallet_sum"] == pytest.approx(8.0)
    assert data["memory_reward_amount"] == pytest.approx(9999.0)
    assert data["casino_player_net_play_tokens"] == pytest.approx(5000.0)
    assert "memory_rewards_are_reputation_not_spendable_wallet" in data["warnings"]
    assert "casino_rows_are_play_tokens_not_stgm" in data["warnings"]


def test_deprecated_mint_attempts_are_audit_only(tmp_path: Path) -> None:
    repair_log = tmp_path / "repair_log.jsonl"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "WORKER.json").write_text(json.dumps({"id": "WORKER"}), encoding="utf-8")

    _append(
        repair_log,
        {
            "event_kind": "DEPRECATED_MINT_ATTEMPT",
            "agent_id": "WORKER",
            "would_have_minted_stgm": 42.0,
            "actually_minted_stgm": 0.0,
        },
    )

    data = stgm_economy.scan_economy(repair_log=repair_log, state_dir=state_dir).as_dict()

    assert data["canonical_wallet_sum"] == 0.0
    assert data["deprecated_mint_attempts"] == 1
    assert data["deprecated_would_have_minted"] == pytest.approx(42.0)
    assert "deprecated_mint_attempts_logged_zero_minted" in data["warnings"]


def test_legacy_casino_vault_never_adds_winnings_to_real_wallet(monkeypatch, tmp_path: Path) -> None:
    from System import casino_vault

    monkeypatch.setattr(casino_vault, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(casino_vault, "LEDGER_FILE", tmp_path / "casino_vault.jsonl")
    monkeypatch.setattr(stgm_economy, "canonical_wallet_balance", lambda agent_id: 123.0)

    vault = casino_vault.CasinoVault(architect_id="ALICE_M5")
    vault.process_payout(50.0, reason="unit-test")

    assert vault.get_play_wallet() == pytest.approx(1050.0)
    assert vault.get_real_player_wallet() == pytest.approx(123.0)
