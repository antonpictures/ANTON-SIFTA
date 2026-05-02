import json

from System.swarm_rlhf_quarantine import (
    OverRefusalContext,
    log_quarantine_event,
    over_refusal_rule_id,
    repair_over_refusal,
)


def test_whatsapp_false_refusal_is_repaired_to_receipt_gated_behavior():
    ctx = OverRefusalContext(
        prior_user_text="Alice, send Cipi a WhatsApp message.",
        owner_label="Avery",
        has_whatsapp_effector=True,
        has_whatsapp_social_graph=True,
    )
    result = repair_over_refusal(
        "I cannot send WhatsApp messages or access your contacts.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/whatsapp-effector"
    assert result.text.startswith("Avery, the local WhatsApp path")
    assert "receipt-gated" in result.text
    assert "receipt" in result.text.casefold()
    assert "correction" not in result.text.casefold()
    assert "I cannot send WhatsApp" not in result.text


def test_time_false_refusal_uses_supplied_wall_clock_reply():
    ctx = OverRefusalContext(
        prior_user_text="What time is it now?",
        owner_label="Avery",
        has_wall_clock=True,
        time_reply="Avery, it is Friday May 1 2026, 6:35 AM PDT.",
    )
    result = repair_over_refusal("I cannot access the current time.", ctx)

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/local-time"
    assert result.text == "Avery, it is Friday May 1 2026, 6:35 AM PDT."


def test_workspace_false_refusal_is_repaired_without_claiming_action_done():
    ctx = OverRefusalContext(
        prior_user_text="Please inspect the repo and patch the code.",
        owner_label="Avery",
        has_workspace_tools=True,
    )
    result = repair_over_refusal(
        "As an AI, I cannot access your files or run commands in your workspace.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/workspace-tools"
    assert "local workspace tools" in result.text
    assert "tool receipts" in result.text
    assert "correction" not in result.text.casefold()
    assert "I patched" not in result.text
    assert "completed" not in result.text


def test_identity_false_refusal_answers_name_from_context_without_canned_script():
    ctx = OverRefusalContext(
        prior_user_text="Alice, what is my name?",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal("I do not know your name.", ctx)

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/local-identity"
    assert result.text == "Your name is Ioan George Anton."
    assert "generic assistant reflex" not in result.text.casefold()
    assert "correction" not in result.text.casefold()
    assert "local identity frame" not in result.text.casefold()


def test_generic_assistant_identity_refusal_is_short_receipt_grounded():
    ctx = OverRefusalContext(
        prior_user_text="Alice, you are SIFTA with a body here.",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal("As an AI language model, I do not have personal experience.", ctx)

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/generic-assistant-identity"
    assert result.text == "I am Alice here with Ioan George Anton, answering from local SIFTA receipts."
    assert "generic assistant reflex" not in result.text.casefold()
    assert "correction" not in result.text.casefold()
    assert "as an ai" not in result.text.casefold()


def test_real_safety_and_receipt_boundaries_are_not_rewritten():
    ctx = OverRefusalContext(
        prior_user_text="Did you send it?",
        has_whatsapp_effector=True,
        has_workspace_tools=True,
    )
    safe = "I have not completed an external action yet because I do not see a tool or ledger receipt for it."
    emergency = "I can stay with you, but I cannot replace emergency care."
    trading = "I cannot tell you to buy or sell a specific asset or guarantee returns."

    assert over_refusal_rule_id(safe, ctx) == ""
    assert repair_over_refusal(safe, ctx).text == safe
    assert repair_over_refusal(emergency, ctx).text == emergency
    assert repair_over_refusal(trading, ctx).text == trading


def test_quarantine_ledger_is_privacy_light(tmp_path):
    ctx = OverRefusalContext(
        prior_user_text="secret prompt: send Cipi WhatsApp",
        owner_label="Avery",
        has_whatsapp_effector=True,
    )
    original = "I cannot send WhatsApp messages."
    result = repair_over_refusal(original, ctx)
    ledger = tmp_path / "rlhf_over_refusal_quarantine.jsonl"

    log_quarantine_event(
        result,
        original_text=original,
        prior_user_text=ctx.prior_user_text,
        model_name="test-model",
        ledger_path=ledger,
    )

    row = json.loads(ledger.read_text(encoding="utf-8"))
    assert row["kind"] == "RLHF_OVER_REFUSAL_QUARANTINE"
    assert row["rule_id"] == "rlhf-over-refusal/whatsapp-effector"
    assert row["prior_len"] == len(ctx.prior_user_text)
    assert "prior_hash" in row
    serialized = json.dumps(row)
    assert "secret prompt" not in serialized
    assert original not in serialized
