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
    assert "[Insert Current Time Here]" not in prompt


def test_current_time_reply_is_not_placeholder():
    mod = _load_widget_module()
    reply = mod._current_time_reply_for_alice()
    assert "[Insert Current Time Here]" not in reply
    assert reply.startswith("George, ")
    assert "time" in reply.casefold() or "it is" in reply.casefold()


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
