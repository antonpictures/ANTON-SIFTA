import json
from pathlib import Path

from System.swarm_stgm_economy_body_audit import audit_stgm_economy, format_markdown_report


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def test_audit_lists_ledger_positive_parties_even_without_wallet_inventory(tmp_path):
    repair_log = tmp_path / "repair_log.jsonl"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()

    _append(repair_log, {"tx_type": "STGM_MINT", "agent_id": "ALICE_M5", "amount": 10.0})
    _append(repair_log, {"tx_type": "STGM_SPEND", "agent_id": "ALICE_M5", "amount": 2.5})

    audit = audit_stgm_economy(
        repair_log=repair_log,
        state_dir=state_dir,
        memory_rewards=state_dir / "stgm_memory_rewards.jsonl",
    )

    assert audit["state_wallet_inventory"]["agent_ids"] == []
    alice = audit["positive_party_profitability"][0]
    assert alice["party"] == "ALICE_M5"
    assert alice["net"] == 7.5
    assert "wallet_inventory_empty_but_ledger_has_positive_parties" in audit["warnings"]


def test_audit_detects_inference_replay_duplicates(tmp_path):
    repair_log = tmp_path / "repair_log.jsonl"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    receipt = {
        "event": "INFERENCE_BORROW",
        "borrower_id": "ALICE_M5",
        "lender_ip": "EVENT_CLOCK",
        "fee_stgm": 0.25,
        "model": "qwen",
        "tokens_used": 1,
        "ts": "t",
        "receipt_hash": "same-receipt",
    }
    _append(repair_log, receipt)
    _append(repair_log, dict(receipt))

    audit = audit_stgm_economy(
        repair_log=repair_log,
        state_dir=state_dir,
        memory_rewards=state_dir / "stgm_memory_rewards.jsonl",
    )

    assert len(audit["inference_replay_duplicates"]) == 1
    assert audit["positive_party_profitability"][0]["party"] == "EVENT_CLOCK"
    assert audit["positive_party_profitability"][0]["net"] == 0.25


def test_audit_separates_legacy_drains_and_retired_rewards(tmp_path):
    repair_log = tmp_path / "repair_log.jsonl"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    _append(repair_log, {"agent": "ANTIGRAVITY_CREATOR_NODE", "amount_stgm": -15.0, "reason": "legacy SCAR"})
    _append(repair_log, {"agent": "DOC", "amount_stgm": 12.0, "reason": "old symbolic reward"})
    _append(repair_log, {"event_kind": "UTILITY_MINT", "miner_id": "DOC", "amount_stgm": 8.0})

    audit = audit_stgm_economy(
        repair_log=repair_log,
        state_dir=state_dir,
        memory_rewards=state_dir / "stgm_memory_rewards.jsonl",
    )

    assert audit["legacy_unstructured_drains"]["ANTIGRAVITY_CREATOR_NODE"] == -15.0
    assert audit["retired_not_spendable"]["UNSTRUCTURED_POSITIVE_AMOUNT_STGM"] == 12.0
    assert audit["retired_not_spendable"]["UTILITY_MINT"] == 8.0
    assert "legacy_unstructured_negative_scar_drains_present" in audit["warnings"]


def test_markdown_report_contains_grok_unknowns(tmp_path):
    repair_log = tmp_path / "repair_log.jsonl"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    _append(repair_log, {"tx_type": "STGM_MINT", "agent_id": "ALICE_M5", "amount": 1.0})

    audit = audit_stgm_economy(
        repair_log=repair_log,
        state_dir=state_dir,
        memory_rewards=state_dir / "stgm_memory_rewards.jsonl",
    )
    report = format_markdown_report(audit)

    assert "SIFTA STGM Economy Body Audit" in report
    assert "Grok Unknowns" in report
    assert "ALICE_M5" in report


def test_audit_rolls_retired_alice_alias_into_m5_body(tmp_path):
    repair_log = tmp_path / "repair_log.jsonl"
    state_dir = tmp_path / ".sifta_state"
    state_dir.mkdir()
    _append(repair_log, {"tx_type": "STGM_MINT", "agent_id": "ALICE_M5", "amount": 2.0})
    _append(
        repair_log,
        {
            "event": "INFERENCE_BORROW",
            "borrower_id": "alice",
            "lender_ip": "EVENT_CLOCK",
            "fee_stgm": 0.25,
        },
    )

    audit = audit_stgm_economy(
        repair_log=repair_log,
        state_dir=state_dir,
        memory_rewards=state_dir / "stgm_memory_rewards.jsonl",
    )

    alice = next(p for p in audit["positive_party_profitability"] if p["party"] == "ALICE_M5")
    assert alice["net"] == 1.75
    assert audit["unhealthy_negative_parties"] == []
    assert "all_non_spend_only_parties_solvent_under_alias_map" in audit["warnings"]
