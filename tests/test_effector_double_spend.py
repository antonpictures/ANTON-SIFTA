"""C4 — double-spend property on intent nonce ledger."""
from __future__ import annotations

import json

from System.swarm_effector_gate import bind_owner_ingress, require_browser_effector
from System.swarm_intent_nonce_gate import mint_intent_nonce, validate_effector_spend


def test_double_spend_blocked(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    mint = mint_intent_nonce(owner_text="close tab", state_dir=sd)
    nonce = mint["nonce"]
    first = validate_effector_spend(nonce, state_dir=sd, effector="browser")
    second = validate_effector_spend(nonce, state_dir=sd, effector="browser")
    assert first["ok"] is True
    assert second["ok"] is False
    assert second.get("reason") == "double_spend_blocked"


def test_restart_survival_spend_ledger(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()
    mint = mint_intent_nonce(owner_text="open browser", state_dir=sd)
    validate_effector_spend(mint["nonce"], state_dir=sd, effector="browser")
    ledger = sd / "intent_nonce_gate.jsonl"
    assert ledger.exists()
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert any("spend" in ln for ln in lines)


def test_purchase_intent_row_lands_on_effector_gate(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()

    ctx = bind_owner_ingress(
        owner_text="buy the first one on ebay under 40 dollars",
        state_dir=sd,
    )
    assert ctx["purchase_intent_detected"] is True
    assert ctx["purchase_intent"]["mana_is_crypto"] is False
    assert ctx["purchase_intent"]["stgm_is_crypto"] is True

    allowed = require_browser_effector("click_checkout_button", state_dir=sd)
    assert allowed["ok"] is True
    assert allowed["purchase_intent_detected"] is True

    rows = [
        json.loads(line)
        for line in (sd / "effector_gate.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    purchase_rows = [row for row in rows if row.get("action") == "purchase_intent"]
    assert len(purchase_rows) == 1
    purchase = purchase_rows[0]
    assert purchase["schema"] == "PURCHASE_INTENT_GATE_V1"
    assert purchase["nonce"] == ctx["nonce"]
    assert purchase["economy_lane"] == "STGM_SPEND_PROOF_REQUIRED"
    assert purchase["mana_is_crypto"] is False
    assert purchase["stgm_is_crypto"] is True
    allowed_rows = [row for row in rows if row.get("action") == "allowed"]
    assert allowed_rows[-1]["purchase_intent_detected"] is True


def test_non_purchase_owner_turn_does_not_write_purchase_intent(tmp_path):
    sd = tmp_path / ".sifta_state"
    sd.mkdir()

    ctx = bind_owner_ingress(owner_text="close the extra browser tab", state_dir=sd)
    assert ctx["purchase_intent_detected"] is False

    rows = [
        json.loads(line)
        for line in (sd / "effector_gate.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] if (sd / "effector_gate.jsonl").exists() else []
    assert [row for row in rows if row.get("action") == "purchase_intent"] == []


def test_commerce_demo_one_utterance_one_nonce_one_effector_second_refused(tmp_path):
    """Product demo path: purchase intent → one browser spend → second spend refused."""
    sd = tmp_path / ".sifta_state"
    sd.mkdir()

    ctx = bind_owner_ingress(
        owner_text="buy the first one on ebay under 40 dollars",
        state_dir=sd,
    )
    nonce = ctx["nonce"]
    assert ctx["purchase_intent_detected"] is True

    first = require_browser_effector("click_checkout_button", state_dir=sd)
    second = require_browser_effector("confirm_payment", state_dir=sd)

    assert first["ok"] is True
    assert second["ok"] is False
    assert second.get("reason") == "double_spend_blocked"

    rows = [
        json.loads(line)
        for line in (sd / "effector_gate.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    purchase_rows = [r for r in rows if r.get("action") == "purchase_intent"]
    allowed_rows = [r for r in rows if r.get("action") == "allowed"]
    refused_rows = [r for r in rows if r.get("action") == "refused"]

    assert len(purchase_rows) == 1
    assert purchase_rows[0]["nonce"] == nonce
    assert len(allowed_rows) == 1
    assert allowed_rows[0]["nonce"] == nonce
    assert any(r.get("reason") == "double_spend_blocked" for r in refused_rows)
