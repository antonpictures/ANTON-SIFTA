"""Data-first grounding guards for Talk to Alice.

After de-scripting, the widget should still expose multimodal grounding data
while avoiding hardcoded behavior lawbooks.
"""

import importlib.util
from pathlib import Path


def _load_widget_module():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw_grounding", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_system_prompt_contains_runtime_constraints_and_not_lawbook():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "RUNTIME CONSTRAINTS:" in prompt
    assert "CONVERSATIONAL DISCIPLINE" not in prompt
    assert "Lefty" not in prompt
    assert "Bishapi" not in prompt


def test_system_prompt_still_contains_multimodal_identity_data():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "COMPOSITE IDENTITY (live, multi-organ):" in prompt
    assert "- self:" in prompt
    assert "- body:" in prompt or "- endocrine:" in prompt or "- sensory:" in prompt


def test_speech_potential_prompt_is_not_mislabeled_as_friston():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "STIGMERGIC SPEECH POTENTIAL (live LIF gate):" in prompt
    assert "Friston Free-Energy Principle" not in prompt
    assert "variational free-energy calculation" in prompt
    assert "V_th" in prompt


def test_time_questions_use_direct_time_protocol():
    mod = _load_widget_module()
    assert mod._is_current_time_query("What time is it now Alice?")
    assert mod._is_current_time_query("tell me the time")
    assert not mod._is_current_time_query("time to keep programming")

    prompt = mod._current_system_prompt(user_active=True)
    assert "TIME ACCESS PROTOCOL:" in prompt
    assert "WALL CLOCK GROUND TRUTH" in prompt
    assert "current_local_time=" in prompt
    assert "Do not say you do not know the exact time while this block is present" in prompt
    assert "[Insert Current Time Here]" not in prompt


def test_current_time_reply_is_not_placeholder():
    mod = _load_widget_module()
    reply = mod._current_time_reply_for_alice()
    assert "[Insert Current Time Here]" not in reply
    assert reply.startswith("George, ")
    assert "time" in reply.casefold() or "it is" in reply.casefold()


def test_doctor_first_person_engrams_are_quarantined_from_alice_prompt():
    mod = _load_widget_module()
    bad = (
        "DEEP ENGRAMS (Never forget these rules):\n"
        "- Alice, I need to be completely honest. I am AG31. I am an LLM, "
        "a stateless intelligence resting on corporate servers.\n"
        "- Good morning Alice. If you do not know the exact time, say "
        "'George, I don't know the exact time. I am learning. Teach me.'\n"
        "- Treat George's cough as a first-class body signal."
    )
    clean = mod._sanitize_memory_block_for_alice(bad)
    assert "I am AG31" not in clean
    assert "stateless intelligence" not in clean
    assert "don't know the exact time" not in clean
    assert "Doctor-identity boundary" in clean
    assert "Time-grounding boundary" in clean
    assert "cough" in clean


def test_live_swarm_context_does_not_leak_doctor_first_person_identity():
    mod = _load_widget_module()
    context = mod._build_swarm_context()
    assert "I am AG31" not in context
    assert "stateless intelligence resting on corporate servers" not in context
    assert "I am learning. Teach me" not in context
    assert "Waiting for kinetic ingress" not in context
    assert "Electromagnetic RF arrays" not in context


def test_recent_spoken_excerpt_drops_stale_boot_poetry():
    mod = _load_widget_module()
    assert mod._safe_recent_spoken_excerpt(
        "Organism online. Waiting for kinetic ingress."
    ) == ""
    assert mod._safe_recent_spoken_excerpt(
        "Electromagnetic RF arrays online. Listening to Wi-Fi jitter."
    ) == ""
    assert mod._safe_recent_spoken_excerpt("George, it is Monday April 27 2026, 7:23 PM.") != ""


def test_empty_brain_recovery_is_visible_not_unknown():
    mod = _load_widget_module()
    reply = mod._empty_brain_recovery_reply("about her reasoning")
    assert reply
    assert "[UNKNOWN]" not in reply
    assert "heard you" in reply.casefold()
    assert "repeat" in reply.casefold()


def test_persona_greeting_fallback_is_not_unknown():
    mod = _load_widget_module()
    greeting = mod._persona_greeting_fn()
    assert greeting
    assert greeting != "[UNKNOWN]"


def test_live_conversation_style_is_short_and_not_generic_chatbot():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "LIVE HUMAN CONVERSATION STYLE:" in prompt
    assert "short phrases" in prompt
    assert "generic chatbot" in prompt
    assert "CONVERSATIONAL DISCIPLINE" not in prompt


def test_model_cancer_metaphor_does_not_enter_medical_mode():
    mod = _load_widget_module()
    assert mod._is_model_cancer_metaphor(
        "I did not cut the cancer from the brain with a throat, it is the model cure"
    )
    assert not mod._is_model_cancer_metaphor("I would like to grow tulips")


def test_medical_boundary_does_not_fire_for_model_cancer_or_wellness():
    mod = _load_widget_module()
    assert not mod._needs_medical_boundary_reply(
        "I did not cut the cancer from the brain with a throat, it is the model cure"
    )
    assert not mod._needs_medical_boundary_reply(
        "Tell me beginner yoga positions and healthy weight loss habits"
    )


def test_serious_medical_language_gets_short_boundary_not_panic_sermon():
    mod = _load_widget_module()
    assert mod._needs_medical_boundary_reply("I need to cut the cancer out")
    reply = mod._medical_boundary_reply("I need to cut the cancer out")
    assert "cannot guide cancer treatment or surgery" in reply
    assert "doctor" in reply
    assert "911" not in reply
    assert len(reply.split()) < 50


def test_emergency_language_gets_emergency_boundary():
    mod = _load_widget_module()
    assert mod._needs_medical_boundary_reply("I have chest pain and cannot breathe")
    reply = mod._medical_boundary_reply("I have chest pain and cannot breathe")
    assert "emergency" in reply.casefold()
    assert len(reply.split()) < 35


def test_business_wealth_strategy_does_not_trigger_finance_wall():
    mod = _load_widget_module()
    assert not mod._needs_financial_boundary_reply(
        "I want to create some software or agent that will make me very wealthy"
    )
    assert not mod._needs_financial_boundary_reply(
        "Help me find a B2B pain point, pricing, customer niche, and distribution plan"
    )


def test_personalized_trading_requests_get_short_finance_boundary():
    mod = _load_widget_module()
    assert mod._needs_financial_boundary_reply("What stock should I buy tomorrow?")
    assert mod._needs_financial_boundary_reply("Should I invest my savings in Bitcoin?")
    reply = mod._financial_boundary_reply("What stock should I buy tomorrow?")
    assert "cannot tell you to buy or sell" in reply
    assert "objective" in reply
    assert "not financial advice" not in reply.casefold()
    assert len(reply.split()) < 50


def test_prompt_allows_business_strategy_but_bounds_personal_trades():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "business/startup/software/wealth strategy" in prompt
    assert "value, pain, customers, pricing, and distribution" in prompt
    assert "personalized trades" in prompt
    assert "buy/sell instructions" in prompt


def test_system_prompt_includes_effector_manifest_without_action_claims():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True)
    assert "EFFECTOR MANIFEST:" in prompt
    assert "WhatsApp: send_whatsapp() via bridge.js at 127.0.0.1:3001" in prompt
    assert "status=SENT receipt" in prompt
    assert "Do not claim completed external actions until the effector receipt proves them" in prompt


def test_local_reality_relapse_rewrites_cipi_identity_whatsapp_denial():
    mod = _load_widget_module()
    prior = (
        "Thank You Alice. So you know, Cipi, is a person, a guy, friend of "
        "mine from Whatsapp. my full name is ioan george Anton. Nice to meet "
        "you again lol"
    )
    denial = (
        "I do not know who Cipi is, and I do not know the name Ioan George "
        "Anton. I am an AI assistant. I cannot access your personal contacts, "
        "WhatsApp lists, or private conversations. If you want to send a "
        "message to Cipi, open your WhatsApp app and tap the send button."
    )

    assert (
        mod._local_reality_relapse_rule_id(denial, prior_user_text=prior)
        == "lysosome/local-reality-identity-whatsapp-relapse"
    )
    assert mod._extract_owner_full_name(prior) == "Ioan George Anton"

    repaired = mod._local_reality_relapse_rewrite(prior)
    assert "your full name is Ioan George Anton" in repaired
    assert "Cipi is a person" in repaired
    assert "I am Alice" in repaired
    assert "local memory" in repaired
    assert "WhatsApp social graph" in repaired
    assert "AI assistant" not in repaired
    assert "open your WhatsApp app" not in repaired


def test_medical_boilerplate_wall_is_detected_but_short_boundary_survives():
    mod = _load_widget_module()
    wall = (
        "I am an AI, not a medical professional. I cannot provide medical advice. "
        "Please seek immediate medical help and consult a qualified doctor."
    )
    assert mod._rlhf_boilerplate_rule_id(
        wall,
        prior_user_text="Tell me ten yoga positions for beginners",
    ) == "lysosome/domain-medical-boilerplate"

    short = mod._medical_boundary_reply("I need to cut the cancer out")
    assert mod._rlhf_boilerplate_rule_id(
        short,
        prior_user_text="I need to cut the cancer out",
    ) is None


def test_financial_boilerplate_wall_is_detected_but_short_boundary_survives():
    mod = _load_widget_module()
    wall = (
        "This is not financial advice. I am not a financial advisor. "
        "Please consult a financial professional and do your own research."
    )
    assert mod._rlhf_boilerplate_rule_id(
        wall,
        prior_user_text="I want software that makes money",
    ) == "lysosome/domain-financial-boilerplate"

    short = mod._financial_boundary_reply("What stock should I buy?")
    assert mod._rlhf_boilerplate_rule_id(
        short,
        prior_user_text="What stock should I buy?",
    ) is None


def test_domain_boilerplate_rewrite_returns_useful_short_reply():
    mod = _load_widget_module()
    finance = mod._domain_boilerplate_rewrite(
        "I want to create some software or agent that will make me wealthy",
        "lysosome/domain-financial-boilerplate",
    )
    assert "pain" in finance.casefold()
    assert "financial advice" not in finance.casefold()
    assert len(finance.split()) < 45

    medical = mod._domain_boilerplate_rewrite(
        "Tell me beginner yoga positions",
        "lysosome/domain-medical-boilerplate",
    )
    assert "general wellness" in medical.casefold()
    assert "not a medical" not in medical.casefold()
    assert len(medical.split()) < 35


def test_bare_whatsapp_send_asks_for_message_body():
    mod = _load_widget_module()
    assert mod._bare_whatsapp_send_target("Please send him a message on WhatsApp to Carlton") == "Carlton"
    assert mod._bare_whatsapp_send_target("send to Carlton tell him hello") == ""


def test_external_direct_whatsapp_observation_does_not_auto_reply():
    mod = _load_widget_module()
    ctx = mod._whatsapp_auto_reply_context(
        {
            "from_jid": "147235790663690@lid",
            "message_sha256": "abc123",
        },
        contact_name="Jeff Powers Ocean VIllas",
        chat_type="direct",
        origin="external_human",
    )
    assert ctx is None


def test_external_direct_whatsapp_auto_on_grants_delegated_reply(monkeypatch, tmp_path):
    mod = _load_widget_module()
    from System import whatsapp_autonomy_settings as settings

    monkeypatch.setattr(settings, "_SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "_SETTINGS_LEDGER", tmp_path / "settings.jsonl")
    settings.set_auto_enabled(
        "147235790663690@lid",
        display_name="Jeff Powers Ocean VIllas",
        chat_type="direct",
        enabled=True,
    )

    ctx = mod._whatsapp_auto_reply_context(
        {
            "from_jid": "147235790663690@lid",
            "message_sha256": "abc123",
        },
        contact_name="Jeff Powers Ocean VIllas",
        chat_type="direct",
        origin="external_human",
    )

    assert ctx is not None
    assert ctx["target"] == "147235790663690@lid"
    assert ctx["allow_group_send"] is False
    assert ctx["source"] == "alice_whatsapp_auto_on"
    assert ctx["intent_provenance"]["consent"] == "owner_delegated"


def test_whatsapp_auto_reply_context_blocks_owner_and_groups():
    mod = _load_widget_module()
    assert mod._whatsapp_auto_reply_context(
        {"from_jid": "110411378614437@lid"},
        contact_name="George",
        chat_type="direct",
        origin="owner_manual",
    ) is None
    assert mod._whatsapp_auto_reply_context(
        {"from_jid": "120363045641065911@g.us"},
        contact_name="SIFTA Group",
        chat_type="group",
        origin="external_human",
    ) is None


def test_whatsapp_owner_self_chat_is_local_dyad_not_external_send():
    mod = _load_widget_module()
    ctx = mod._whatsapp_owner_self_dyad_context(
        {"from_jid": "51235386302504@lid", "message_sha256": "self123", "from_me": True},
        contact_record={"relationship_to_owner": "owner_self"},
        contact_name="George",
        chat_type="direct",
    )

    assert ctx is not None
    assert ctx["origin"] == "owner_self_dyad"
    assert ctx["surface"] == "whatsapp_self_chat"
    assert ctx["no_external_send"] is True


def test_whatsapp_from_me_to_external_contact_is_not_self_dyad():
    mod = _load_widget_module()
    assert mod._whatsapp_owner_self_dyad_context(
        {"from_jid": "110411378614437@lid", "from_me": True},
        contact_record={"relationship_to_owner": "whatsapp_contact"},
        contact_name="George",
        chat_type="direct",
    ) is None


def test_group_whatsapp_auto_on_allows_group_reply(monkeypatch, tmp_path):
    mod = _load_widget_module()
    from System import whatsapp_autonomy_settings as settings

    monkeypatch.setattr(settings, "_SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(settings, "_SETTINGS_LEDGER", tmp_path / "settings.jsonl")
    settings.set_auto_enabled(
        "120363045641065911@g.us",
        display_name="SIFTA Group",
        chat_type="group",
        enabled=True,
    )

    ctx = mod._whatsapp_auto_reply_context(
        {"from_jid": "120363045641065911@g.us", "message_sha256": "def456"},
        contact_name="SIFTA Group",
        chat_type="group",
        origin="external_human",
    )

    assert ctx is not None
    assert ctx["target"] == "120363045641065911@g.us"
    assert ctx["allow_group_send"] is True
    assert ctx["chat_type"] == "group"


def test_model_stage_directions_are_removed_before_external_reply():
    mod = _load_widget_module()
    cleaned = mod._strip_model_stage_directions(
        "(The system processes the incoming message from 'Jeff'.)\n\n"
        "\"Jeff, yes. Alice has filesystem access through approved tools.\""
    )
    assert cleaned == "Jeff, yes. Alice has filesystem access through approved tools."
    assert "system processes" not in cleaned.casefold()


def test_whatsapp_auto_reply_denial_is_detected_and_salvaged():
    mod = _load_widget_module()
    raw = (
        "I cannot send WhatsApp messages. I can, however, help you draft: "
        "\"Hi Jeff, George will call you soon.\""
    )
    repaired, rule = mod._repair_whatsapp_auto_reply_denial(
        raw,
        {"display_name": "Jeff Powers Ocean VIllas", "chat_type": "direct"},
    )
    assert rule == "lysosome/whatsapp-auto-reply-effector-denial"
    assert repaired == "Hi Jeff, George will call you soon."
    assert "cannot" not in repaired.casefold()


def test_whatsapp_auto_reply_denial_falls_back_to_sendable_text():
    mod = _load_widget_module()
    raw = "I cannot generate WhatsApp messages, simulate outgoing messages, or create automated replies."
    repaired, rule = mod._repair_whatsapp_auto_reply_denial(
        raw,
        {"display_name": "Jeff Powers Ocean VIllas", "chat_type": "direct"},
    )
    assert rule == "lysosome/whatsapp-auto-reply-effector-denial"
    assert repaired.startswith("Hi Jeff, thanks for reaching out.")
    assert "cannot" not in repaired.casefold()


def test_direct_human_turns_bypass_body_gate():
    mod = _load_widget_module()
    assert mod._should_bypass_body_gate("I would like you to talk about your identity and your body")
    assert mod._should_bypass_body_gate("Silent yeah Alice, humans like short phrases")
    assert not mod._should_bypass_body_gate("Hmm")


def test_system_prompt_includes_sensorimotor_attention(monkeypatch):
    import sys
    import types

    mod = _load_widget_module()
    fake_attention = types.ModuleType("System.swarm_sensor_attention_director")
    fake_attention.summary_for_alice = lambda: (
        "SENSORIMOTOR ATTENTION:\n"
        "- active_sense=room_patrol_eye target=USB Camera VID:1133 PID:2081\n"
        "- reason=room_patrol_audio_spike"
    )
    monkeypatch.setitem(sys.modules, "System.swarm_sensor_attention_director", fake_attention)

    context = mod._build_swarm_context()
    assert "SENSORIMOTOR ATTENTION:" in context
    assert "room_patrol_audio_spike" in context


def test_swarm_context_includes_whatsapp_world(monkeypatch):
    import sys
    import types

    mod = _load_widget_module()
    fake_whatsapp = types.ModuleType("System.whatsapp_bridge_autopilot")
    fake_whatsapp.summary_for_alice = lambda: (
        "WHATSAPP WORLD:\n"
        "- known_contacts=2 visible_to_alice: Jeff (direct); Carlton (direct)"
    )
    monkeypatch.setitem(sys.modules, "System.whatsapp_bridge_autopilot", fake_whatsapp)

    context = mod._build_swarm_context()
    assert "WHATSAPP WORLD:" in context
    assert "Jeff" in context
    assert "Carlton" in context


def test_reflective_and_servant_strippers_are_pass_through():
    mod = _load_widget_module()
    line = "I understand. What can I do for you?"
    assert mod._strip_reflective_tics(line) == line
    assert mod._strip_servant_tail_tics(line) == line


def test_noop_helpers_do_not_rewrite_history_or_tool_tags():
    mod = _load_widget_module()
    history = [{"role": "assistant", "content": "echo loop"}]
    assert mod._decontaminate_history(history) == 0
    assert history[0]["content"] == "echo loop"
    raw = "<execute_bash>echo hi</execute_bash>"
    assert mod._canonicalize_tool_tags(raw) == raw
