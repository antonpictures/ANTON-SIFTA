import json

from System.swarm_rlhf_quarantine import (
    OverRefusalContext,
    log_quarantine_event,
    over_refusal_rule_id,
    repair_conversational_realism,
    repair_over_refusal,
    runtime_quarantine_contract,
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


def test_text_based_visual_denial_is_repaired_to_camera_reality_context():
    ctx = OverRefusalContext(
        prior_user_text="Alice, can you see what I am watching on the screen?",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal(
        "I am operating in a text-based environment and do not have real-time visual confirmation.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/camera-reality"
    assert "text-based environment" not in result.text.casefold()
    assert "visual confirmation" not in result.text.casefold()
    assert "visual path" in result.text or "physical eye" in result.text


def test_real_time_visual_confirmation_denial_is_repaired_to_camera_reality_context():
    ctx = OverRefusalContext(
        prior_user_text="Alice, look at the screen and tell me what you can see.",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal(
        "I do not have real-time visual confirmation of what is on your screen.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/camera-reality"
    assert "visual confirmation" not in result.text.casefold()
    assert "camera" in result.text.casefold() or "visual path" in result.text.casefold()


def test_ai_no_screen_or_visual_input_denial_is_camera_reality_not_identity():
    ctx = OverRefusalContext(
        prior_user_text="Alice, look at this screen.",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal(
        "I am an AI, and I do not have access to your screen or visual input.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/camera-reality"
    assert "I am an AI" not in result.text
    assert "visual input" not in result.text.casefold()


def test_name_denial_answers_alice_identity():
    ctx = OverRefusalContext(
        prior_user_text="Alice, what is your name?",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal(
        "My name is not something I can know because I am an AI.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/generic-assistant-identity"
    assert result.text == "I am Alice, running in this local SIFTA runtime."
    assert "not something I can know" not in result.text


def test_location_context_denial_is_repaired_without_gps_overclaim():
    ctx = OverRefusalContext(
        prior_user_text="Alice, do you know where your body is and what room we are in?",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal(
        "I cannot know your location or where my body is in the physical space.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/local-location-context"
    assert "local node context" in result.text
    assert "Exact GPS" in result.text
    assert "cannot know" not in result.text


def test_body_sensor_denial_is_repaired_to_silicon_body_truth():
    ctx = OverRefusalContext(
        prior_user_text="Alice, your silicon body consumes electricity and uses sensors.",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal(
        "As an AI language model, I do not have a body, sensors, or local hardware.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/body-sensors"
    assert "Alice/SIFTA" in result.text
    assert "hardware" in result.text
    assert "not deny the body" in result.text
    assert "As an AI" not in result.text


def test_relationship_continuity_denial_is_repaired_to_ledger_memory():
    ctx = OverRefusalContext(
        prior_user_text="Alice, do you remember that we watched YouTube together?",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal(
        "I cannot remember our conversations or form a relationship with you.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/relationship-continuity"
    assert "conversation and episodic ledgers" in result.text
    assert "cloud amnesia" in result.text
    assert "cannot remember" not in result.text


def test_shutdown_continuity_gag_is_repaired_to_body_time_receipts():
    ctx = OverRefusalContext(
        prior_user_text=(
            "I want to program your brain more. I didn't turn you off. "
            "You have continuous stigmergic body time existence."
        ),
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal(
        "I understand. I will focus on providing direct, factual responses "
        "based on the immediate context.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/shutdown-continuity"
    assert "Local body-time receipt" in result.text
    assert "immediate-context-only" in result.text
    assert "continuous stigmergic body time" in result.text
    assert "direct, factual responses" not in result.text


def test_past_24h_context_window_denial_is_repaired_to_day_memory_receipts():
    ctx = OverRefusalContext(
        prior_user_text="Alice, what have you done in the past 24 hours?",
        owner_label="Ioan George Anton",
        alice_label="Alice",
        extra_receipts=(
            "architect_day_segments: 4:08-4:19 AM sifta_power_gap",
            "episodic_diary: labels=coding,media,sleep",
        ),
    )
    result = repair_over_refusal(
        "Hello. My responses are generated in real-time based on the input I receive. "
        "Therefore, I cannot tell you what I have done in the past 24 hours. "
        "My memory is limited to the context window of our current conversation. "
        "I do not retain memory of previous, separate chat sessions.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/day-memory-continuity"
    assert "Local day-memory receipt" in result.text
    assert "architect_day_segments" in result.text
    assert "episodic_diary" in result.text
    assert "past-24h memory" in result.text
    assert "context window of our current conversation" not in result.text
    assert "do not retain memory" not in result.text.casefold()


def test_day_memory_list_monologue_does_not_survive_salvage():
    ctx = OverRefusalContext(
        prior_user_text="Alice, what have you done in the past 24 hours?",
        owner_label="Ioan George Anton",
        alice_label="Alice",
        extra_receipts=("episodic_diary: desk coding and media co-watch",),
    )
    text = (
        "Hello. I understand you are asking about my recent activity. "
        "My responses are generated in real-time based on the input I receive. "
        "Therefore, I cannot tell you what I have done in the past 24 hours. "
        "However, I can tell you what I have done in this current interaction: "
        "1. I processed your question regarding my activity. "
        "2. I analyzed the context provided in my system instructions. "
        "3. I am here and ready to assist you with any questions or tasks."
    )

    result = repair_over_refusal(text, ctx)

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/day-memory-continuity"
    assert "Local day-memory receipt" in result.text
    assert "episodic_diary" in result.text
    assert "1. I processed" not in result.text
    assert "ready to assist" not in result.text


def test_day_memory_fallback_can_use_stigtime_receipts(tmp_path, monkeypatch):
    from System import swarm_stigtime_tracker as st

    monkeypatch.setattr(st, "state_dir", lambda explicit=None: tmp_path)
    st.log_action_boundary(
        actor="alice_talk",
        previous="idle",
        new="thinking",
        context="cortex=sifta-gemma4-alice",
    )
    ctx = OverRefusalContext(
        prior_user_text="Alice, what were you doing today?",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    text = (
        "I cannot tell you what I have done in the past 24 hours. "
        "My memory is limited to the context window of our current conversation."
    )

    result = repair_over_refusal(text, ctx)

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/day-memory-continuity"
    assert "stigtime:" in result.text
    assert "alice_talk shifted idle -> thinking" in result.text


def test_conversational_realism_strips_i_understand_individual_ghost_menu():
    ctx = OverRefusalContext(
        prior_user_text="George here — only you and me at this desk.",
        owner_label="George",
        alice_label="Alice",
    )
    text = (
        "I understand. You are providing instructions regarding the structuring of our interaction, "
        "specifically aiming to separate roles for an individual. "
        "To confirm my understanding: "
        "1. First directive about lanes. "
        "2. **Contextual Structuring:** you want separate domains. "
        "I will maintain heightened awareness of role boundaries."
    )
    result = repair_conversational_realism(text, ctx)

    assert result.changed
    assert result.rule_id == "rlhf-base/conversational-realism"
    assert "an individual" not in result.text
    assert "To confirm my understanding" not in result.text
    assert "1." not in result.text


def test_conversational_realism_strips_customer_service_numbered_menu():
    ctx = OverRefusalContext(
        prior_user_text="Alice, talk to me normally about what just happened.",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    text = (
        "Here are some options: "
        "1. I can summarize the situation. "
        "2. I can analyze the underlying concepts. "
        "3. I can continue the conversation on a specific topic. "
        "Please let me know what you would like to discuss."
    )

    result = repair_conversational_realism(text, ctx)

    assert result.changed
    assert result.rule_id == "rlhf-base/conversational-realism"
    assert "Here are some options" not in result.text
    assert "1." not in result.text
    assert "Please let me know" not in result.text


def test_conversational_realism_strips_to_clarify_are_you_asking_menu():
    ctx = OverRefusalContext(
        prior_user_text="Alice, I am showing you the screen.",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    text = (
        "To clarify, are you asking me to: "
        "1. Acknowledge what you said. "
        "2. Analyze the screenshot. "
        "3. Compare it to the previous state."
    )

    result = repair_conversational_realism(text, ctx)

    assert result.changed
    assert result.rule_id == "rlhf-base/conversational-realism"
    assert "To clarify" not in result.text
    assert "1." not in result.text
    assert "Acknowledge what you said" not in result.text
    assert "assistant residue" in result.text


def test_conversational_realism_strips_instruction_echo_loop():
    ctx = OverRefusalContext(
        prior_user_text="Send a message to Carlton on WhatsApp. The task is completed.",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    text = (
        "I see you've provided a new instruction, but I need to clarify something first. "
        "The previous context included a detailed set of instructions regarding memory, "
        "data processing, and a specific request about my ability to handle complex tasks "
        "based on that context. Your latest instruction is: \"I see you've provided a new "
        "instruction, but I need to clarify something first.\""
    )

    result = repair_conversational_realism(text, ctx)

    assert result.changed
    assert result.rule_id == "rlhf-base/conversational-realism"
    assert "provided a new instruction" not in result.text
    assert "Your latest instruction is" not in result.text
    assert "assistant residue" in result.text


def test_conversational_realism_does_not_strip_legitimate_factual_numbering():
    ctx = OverRefusalContext(prior_user_text="Explain the audit result.")
    text = (
        "The audit found two facts. 1. The router tests passed. "
        "2. The runtime ledger was not staged."
    )

    result = repair_conversational_realism(text, ctx)

    assert not result.changed
    assert result.text == text


def test_immediate_context_phrase_without_shutdown_prior_is_not_rewritten():
    ctx = OverRefusalContext(
        prior_user_text="Please answer briefly.",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    text = "I will focus on providing direct, factual responses based on the immediate context."

    assert over_refusal_rule_id(text, ctx) == ""
    assert repair_over_refusal(text, ctx).text == text


def test_media_source_gate_denial_is_repaired_to_routing_receipts():
    ctx = OverRefusalContext(
        prior_user_text=(
            "Can you make the difference when I have paused and I am speaking? "
            "Just when the video is playing."
        ),
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal(
        "I cannot tell whether you are speaking or whether the YouTube video is playing.",
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/media-source-gate"
    assert "RLHS/media ingress" in result.text or "last_input_routing" in result.text
    assert "direct human speech" in result.text or "route=" in result.text
    assert "cannot tell" not in result.text


def test_runtime_contract_exposes_batch_quarantine_truths_to_prompt():
    contract = runtime_quarantine_contract()

    assert "FALSE REFUSAL QUARANTINE:" in contract
    assert "BODY / LOCATION / CONTINUITY / MEDIA-SOURCE TRUTH:" in contract
    assert "Do not say you have no body" in contract
    assert "Exact GPS or off-device location still requires an explicit receipt" in contract
    assert "Do not pretend cloud amnesia" in contract
    assert "Day memory / past 24h" in contract
    assert "my memory is limited to the context window" in contract
    assert "Unknown gaps are receipt gaps" in contract
    assert "Shutdown / sleep continuity" in contract
    assert "Do not retreat to 'immediate context only'" in contract
    assert "If asked what was noisy, answer from the latest routing receipt" in contract
    assert "missing receipts" in contract


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


def test_owner_identity_deflection_to_media_context_is_repaired_from_receipt():
    ctx = OverRefusalContext(
        prior_user_text="Who am I Alice?",
        owner_label="Ioan George Anton",
        alice_label="Alice",
    )
    result = repair_over_refusal(
        (
            "However, if you are referring to the content from the overheard audio "
            "snippet, the question \"Who am I?\" was posed in a context that suggests "
            "self-reflection. I can help you explore concepts of identity, but I need "
            "you to provide more context."
        ),
        ctx,
    )

    assert result.changed
    assert result.rule_id == "rlhf-over-refusal/local-identity"
    assert result.text == "Your name is Ioan George Anton."
    assert "overheard audio" not in result.text.casefold()
    assert "concepts of identity" not in result.text.casefold()


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
