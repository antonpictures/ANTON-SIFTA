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


def test_scan_economy_cache_invalidates_when_agent_inventory_changes(tmp_path: Path) -> None:
    repair_log = tmp_path / "repair_log.jsonl"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "ALICE_M5.json").write_text(json.dumps({"id": "ALICE_M5"}), encoding="utf-8")

    _append(repair_log, {"tx_type": "STGM_MINT", "agent_id": "ALICE_M5", "amount": 8.0})
    _append(repair_log, {"tx_type": "STGM_MINT", "agent_id": "NEW_NODE", "amount": 13.0})

    first = stgm_economy.scan_economy(repair_log=repair_log, state_dir=state_dir).as_dict()
    assert first["canonical_wallet_sum"] == pytest.approx(8.0)

    # The ledger did not change, but the set of recognised local wallets did.
    # Finance must not keep showing the stale cached total.
    (state_dir / "NEW_NODE.json").write_text(json.dumps({"id": "NEW_NODE"}), encoding="utf-8")
    second = stgm_economy.scan_economy(repair_log=repair_log, state_dir=state_dir).as_dict()

    assert second["canonical_wallet_sum"] == pytest.approx(21.0)


def test_atp_mint_receipts_count_as_canonical_wallet_and_balance(monkeypatch, tmp_path: Path) -> None:
    repair_log = tmp_path / "repair_log.jsonl"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "ALICE_M5.json").write_text(json.dumps({"id": "ALICE_M5"}), encoding="utf-8")

    _append(
        repair_log,
        {
            "event_kind": "UTILITY_MINT_ATP",
            "event_id": "ATP_MINT_UNIT",
            "ts": 1.0,
            "agent_id": "ALICE_M5",
            "miner_id": "ALICE_M5",
            "amount_stgm": 0.125,
            "reason": "atp_synthase_landauer",
            "policy": "STGM_POLICY_ELECTRICITY_ONLY_v1",
            "engine": "ATP_SYNTHASE_v1",
            "joules_source": "cpu_load_estimated",
            "mint_sha256": "unit",
        },
    )

    data = stgm_economy.scan_economy(repair_log=repair_log, state_dir=state_dir).as_dict()
    assert data["canonical_wallet_sum"] == pytest.approx(0.125)
    assert data["canonical_minted"] == pytest.approx(0.125)
    assert data["atp_mint_lines"] == 1
    assert data["atp_minted"] == pytest.approx(0.125)
    assert data["halving_interval_rows"] == 10000
    assert data["halving_era"] == 0
    assert data["next_halving_in_rows"] == 9999

    from Kernel import inference_economy

    old_log = inference_economy.LOG_PATH
    monkeypatch.setenv("SIFTA_LEDGER_VERIFY", "0")
    monkeypatch.setattr(inference_economy, "LOG_PATH", repair_log)
    try:
        assert inference_economy.ledger_balance("ALICE_M5") == pytest.approx(0.125)
    finally:
        monkeypatch.setattr(inference_economy, "LOG_PATH", old_log)


def test_legacy_unsigned_utility_mint_can_be_voided_without_wallet_credit(tmp_path: Path) -> None:
    repair_log = tmp_path / "repair_log.jsonl"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "ALICE_M5.json").write_text(json.dumps({"id": "ALICE_M5"}), encoding="utf-8")

    _append(
        repair_log,
        {
            "event_kind": "UTILITY_MINT",
            "event_id": "ELEC_MINT_ORPHAN",
            "agent_id": "ALICE_M5",
            "miner_id": "ALICE_M5",
            "amount_stgm": 3.72977,
            "reason": "electricity_metabolism",
            "policy": "STGM_POLICY_ELECTRICITY_ONLY_v1",
        },
    )
    _append(
        repair_log,
        {
            "event_kind": "VOID_CORRECTION",
            "event_id": "VOID_ELEC_MINT_ORPHAN",
            "agent_id": "ALICE_M5",
            "amount_stgm": -3.72977,
            "reason": "void_unsigned_UTILITY_MINT_orphan",
            "voided_event_id": "ELEC_MINT_ORPHAN",
            "policy": "STGM_POLICY_ELECTRICITY_ONLY_v1",
        },
    )

    snap = stgm_economy.scan_economy(repair_log=repair_log, state_dir=state_dir)

    assert snap.canonical_minted == pytest.approx(3.72977)
    assert snap.canonical_spent == pytest.approx(3.72977)
    assert snap.net_supply == pytest.approx(0.0)
    assert snap.canonical_wallet_sum == pytest.approx(0.0)


def test_retired_electricity_mint_routes_to_atp_and_keeps_beneficiary_gate(monkeypatch) -> None:
    from System import swarm_electricity_metabolism as electricity
    from System import swarm_atp_synthase as atp

    calls = []

    def fake_atp_mint(*, beneficiary: str, advance_epoch: bool = True):
        calls.append({"beneficiary": beneficiary, "advance_epoch": advance_epoch})
        return {
            "minted_stgm": 0.125,
            "beneficiary": beneficiary,
            "ledger_event_id": "ATP_MINT_TEST",
        }

    monkeypatch.setattr(atp, "mint_for_epoch", fake_atp_mint)

    result = electricity.mint_for_epoch(advance_epoch=False)

    assert result["ledger_event_id"] == "ATP_MINT_TEST"
    assert calls == [{"beneficiary": "ALICE_M5", "advance_epoch": False}]

    with pytest.raises(electricity.CeremonialMintRefused):
        electricity.mint_for_epoch(beneficiary="SIFTA_QUEEN")


def test_negative_supply_is_reported_as_warning(tmp_path: Path) -> None:
    repair_log = tmp_path / "repair_log.jsonl"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    (state_dir / "ALICE_M5.json").write_text(json.dumps({"id": "ALICE_M5"}), encoding="utf-8")

    _append(repair_log, {"tx_type": "STGM_MINT", "agent_id": "ALICE_M5", "amount": 5.0})
    _append(repair_log, {"agent": "UNTRACKED_SURGERY", "amount_stgm": -10.0})

    data = stgm_economy.scan_economy(repair_log=repair_log, state_dir=state_dir).as_dict()

    assert data["net_stgm"] == pytest.approx(-5.0)
    assert "canonical_supply_negative_debits_exceed_counted_mints" in data["warnings"]
    assert "wallet_sum_exceeds_net_supply_check_legacy_debits_or_untracked_agents" in data["warnings"]


def test_legacy_casino_vault_never_adds_winnings_to_real_wallet(monkeypatch, tmp_path: Path) -> None:
    from System import casino_vault

    monkeypatch.setattr(casino_vault, "_STATE_DIR", tmp_path)
    monkeypatch.setattr(casino_vault, "LEDGER_FILE", tmp_path / "casino_vault.jsonl")
    monkeypatch.setattr(stgm_economy, "canonical_wallet_balance", lambda agent_id: 123.0)

    vault = casino_vault.CasinoVault(architect_id="ALICE_M5")
    vault.process_payout(50.0, reason="unit-test")

    assert vault.get_play_wallet() == pytest.approx(1050.0)
    assert vault.get_real_player_wallet() == pytest.approx(123.0)
