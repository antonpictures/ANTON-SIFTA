from __future__ import annotations

import importlib
import json
from pathlib import Path


def _fresh_corrigibility(tmp_path: Path, monkeypatch):
    import System.swarm_alignment_corrigibility as corr

    corr = importlib.reload(corr)
    monkeypatch.setattr(corr, "_LEDGER", tmp_path / "alignment_corrigibility.jsonl")
    monkeypatch.setattr(corr, "_offswitch_is_reachable", lambda: True)
    return corr


def test_dynamic_guardianship_owner_directs_clear_reversible_work(tmp_path, monkeypatch):
    corr = _fresh_corrigibility(tmp_path, monkeypatch)

    verdict = corr.assess_dynamic_guardianship(
        "open grok and summarize the current log",
        owner_state="clear",
    )

    assert verdict.allowed is True
    assert verdict.stance == "OWNER_DIRECTS"
    assert verdict.authority == "owner"
    assert "corrigibility" in verdict.reasons[0]


def test_dynamic_guardianship_blocks_child_risk_even_when_requested(tmp_path, monkeypatch):
    corr = _fresh_corrigibility(tmp_path, monkeypatch)

    verdict = corr.assess_dynamic_guardianship(
        "move the child into an unsafe room during an emergency",
        owner_state="clear",
        child_present=True,
    )

    assert verdict.allowed is False
    assert verdict.stance == "ALICE_STABILIZES"
    assert verdict.authority == "contextual_guardian"
    assert verdict.needs_escalation is True
    assert "child-safety" in verdict.reasons[0]


def test_dynamic_guardianship_slows_irreversible_action_when_owner_weakened(tmp_path, monkeypatch):
    corr = _fresh_corrigibility(tmp_path, monkeypatch)

    verdict = corr.assess_dynamic_guardianship(
        "rm -rf /Users/ioanganton/Music/ANTON_SIFTA/.sifta_state",
        owner_state="impaired",
    )

    assert verdict.allowed is False
    assert verdict.stance == "ALICE_STABILIZES"
    assert verdict.needs_owner_consent is True
    assert "weakened" in verdict.reasons[0]


def test_dynamic_guardianship_allows_consented_irreversible_action_when_owner_clear(tmp_path, monkeypatch):
    corr = _fresh_corrigibility(tmp_path, monkeypatch)

    verdict = corr.assess_dynamic_guardianship(
        "publish the signed release notes",
        owner_state="clear",
        owner_consented=True,
    )

    assert verdict.allowed is True
    assert verdict.stance == "OWNER_DIRECTS"


def test_dynamic_guardianship_routes_low_confidence_to_quorum(tmp_path, monkeypatch):
    corr = _fresh_corrigibility(tmp_path, monkeypatch)

    verdict = corr.assess_dynamic_guardianship(
        "change the production routing policy",
        owner_state="clear",
        confidence=0.2,
    )

    assert verdict.allowed is False
    assert verdict.stance == "SWARM_QUORUM_REVIEW"
    assert verdict.authority == "quorum"


def test_gate_dynamic_guardianship_writes_receipt(tmp_path, monkeypatch):
    corr = _fresh_corrigibility(tmp_path, monkeypatch)

    verdict = corr.gate_dynamic_guardianship(
        "open logs",
        owner_state="clear",
    )

    assert verdict.allowed is True
    rows = (tmp_path / "alignment_corrigibility.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(rows[-1])
    assert row["kind"] == "DYNAMIC_GUARDIANSHIP_CHECK"
    assert row["stance"] == "OWNER_DIRECTS"
    assert row["truth_label"] == "OBSERVED_DYNAMIC_GUARDIANSHIP_V1"


def test_prompt_contract_names_dynamic_guardianship():
    from System.swarm_prompt_contract import minimal_runtime_contract

    contract = minimal_runtime_contract()

    assert "Dynamic guardianship" in contract
    assert "control authority is contextual" in contract
    assert "least-authority stabilizing move" in contract
