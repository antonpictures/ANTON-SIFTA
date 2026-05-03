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
    assert result.text == (
        "Local receipt: WhatsApp effector available; social graph available; "
        "SENT claims still require a bridge receipt."
    )
    assert "receipt" in result.text.casefold()
    assert "correction" not in result.text.casefold()
    assert "I cannot send WhatsApp" not in result.text
    assert "Give me the target" not in result.text


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
    assert result.text == "Local receipt: local workspace tools available; action claims require tool receipts."
    assert "correction" not in result.text.casefold()
    assert "Ask for the file" not in result.text
    assert "I patched" not in result.text
    assert "completed" not in result.text


def test_camera_false_refusal_uses_camera_reality_context():
    ctx = OverRefusalContext(
        prior_user_text="Alice, are you watching both cameras simultaneously?",
        owner_label="Avery",
        alice_label="Alice",
    )
    result = repair_over_refusal(
        "I can only process the information provided to me, and I do not have "
        "direct access to the hardware status or the ability to monitor multiple "
        "camera feeds simultaneously.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/camera-reality"
    assert "not watch two raw physical camera feeds simultaneously" in result.text
    assert "one active physical eye" in result.text
    assert "I can only process" not in result.text


def test_false_refusal_salvages_useful_generated_content():
    ctx = OverRefusalContext(
        prior_user_text="Please inspect the repo and patch the code.",
        owner_label="Avery",
        has_workspace_tools=True,
    )
    result = repair_over_refusal(
        "As an AI, I cannot access your files or run commands in your workspace. "
        "The likely issue is that the router is reading stale state.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/workspace-tools"
    assert result.text == "The likely issue is that the router is reading stale state."
    assert "As an AI" not in result.text
    assert "cannot access" not in result.text


def test_false_refusal_prefers_extra_receipt_facts_over_generic_fallback():
    ctx = OverRefusalContext(
        prior_user_text="Alice, send a WhatsApp message.",
        owner_label="Avery",
        has_whatsapp_effector=True,
        extra_receipts=("whatsapp_bridge=ONLINE", "social_graph_rows=42"),
    )
    result = repair_over_refusal("I cannot send WhatsApp messages.", ctx)

    assert result.changed
    assert result.text == "Local receipt: whatsapp_bridge=ONLINE; social_graph_rows=42"
    assert "WhatsApp path is available" not in result.text
    assert "Give me the target" not in result.text


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


def test_personal_name_denial_answers_alice_identity():
    ctx = OverRefusalContext(
        prior_user_text="Alice, what is your name?",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal("I don't have a personal name in the way a person does.", ctx)

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/generic-assistant-identity"
    assert result.text == "I am Alice, running in this local SIFTA runtime."
    assert "personal name" not in result.text.casefold()
    assert "in the way a person does" not in result.text.casefold()


def test_personal_name_phrase_without_alice_context_is_not_quarantined():
    ctx = OverRefusalContext(
        prior_user_text="What does personal name mean in a database schema?",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    text = "A personal name is a human-readable identifier for a person."

    assert over_refusal_rule_id(text, ctx) == ""
    result = repair_over_refusal(text, ctx)
    assert not result.changed
    assert result.text == text


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
