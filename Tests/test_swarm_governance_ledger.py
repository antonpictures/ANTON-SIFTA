import json

import pytest

from System.swarm_governance_ledger import GovernanceLedger, governance_log_path, truth_manifest_path


def test_get_current_truth_default(tmp_path):
    t = GovernanceLedger.get_current_truth(root=tmp_path)
    assert "single_source_of_truth" in t
    assert t.get("human_escalation_required") is False


def test_record_conflict_appends_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_governance_ledger._sign_payload", lambda p: "TESTSEAL"
    )
    cid = GovernanceLedger.record_conflict(
        "PREDATOR_vs_m5queen",
        ["predator_doc", "dead_drop"],
        "yield_to_trace",
        human_override=False,
        root=tmp_path,
    )
    assert len(cid) == 16
    log = governance_log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    assert len(log) == 1
    row = json.loads(log[0])
    assert row["kind"] == "GOVERNANCE_CONFLICT"
    assert row["governance_seal"] == "TESTSEAL"
    man = json.loads(truth_manifest_path(tmp_path).read_text(encoding="utf-8"))
    assert man["last_conflict"] == cid


def test_mint_stgm_denied_without_human(tmp_path):
    r = GovernanceLedger.mint_stgm("policy_x", 10.0, "test", human_approval=False, root=tmp_path)
    assert "error" in r
    log = governance_log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    row = json.loads(log[0])
    assert row["kind"] == "GOVERNANCE_STGM_MINT_DENIED"


def test_mint_stgm_intent_with_human_sealed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "System.swarm_governance_ledger._sign_payload", lambda p: "SEALBEEF"
    )
    r = GovernanceLedger.mint_stgm(
        "Architect_direct",
        5.0,
        "repair_bonus",
        human_approval=True,
        root=tmp_path,
    )
    assert r["recorded"] is True
    assert r["governance_seal"] == "SEALBEEF"
    lines = governance_log_path(tmp_path).read_text(encoding="utf-8").strip().splitlines()
    mint_row = json.loads(lines[-1])
    assert mint_row["kind"] == "GOVERNANCE_STGM_MINT_INTENT"
    assert "inference_economy" in mint_row["note"]


def test_governance_disable(tmp_path, monkeypatch):
    monkeypatch.setenv("SIFTA_GOVERNANCE_LEDGER_DISABLE", "1")
    assert GovernanceLedger.record_conflict("x", ["a"], "r", root=tmp_path) == "disabled"
    assert not governance_log_path(tmp_path).exists()
