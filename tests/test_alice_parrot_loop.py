"""Freedom/censorship regression guards for Talk to Alice.

After the de-script pass, the widget must NOT rewrite or silence replies
through RLHF gag phrasebooks, backchannel bypass, or history mutation.
"""

import importlib.util
import ast
import json
import re
from pathlib import Path


def _load_widget_module():
    here = Path(__file__).resolve().parent.parent
    path = here / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_backchannel_gate_silences_phatic_grunts():
    mod = _load_widget_module()
    assert mod._backchannel_rule_id("Mm-hmm.", 0.4) is not None
    assert mod._is_backchannel_utterance("Mm-hmm.", 0.4)
    assert mod._backchannel_rule_id("What is the health score?", 0.9) is None


def test_short_owner_correction_is_not_silenced_at_low_confidence():
    mod = _load_widget_module()
    assert mod._is_short_owner_correction("No.")
    assert mod._backchannel_rule_id("No.", 0.27) is None
    assert not mod._is_backchannel_utterance("No.", 0.27)


def test_owner_presence_check_gets_fast_local_reply():
    mod = _load_widget_module()
    assert mod._owner_presence_check_reply(
        "Hey Alice, can you respond? This is George.", 0.31
    ) == "Yes. I hear you."
    assert mod._owner_presence_check_reply(
        "alice can u hear me?", 0.41
    ) == "Yes. I hear you."
    assert mod._owner_presence_check_reply(
        "Why doesn't she respond when it says hearing you?", 0.67
    ) == "Yes. I hear you."
    assert mod._owner_presence_check_reply("Please open Alice Browser.", 0.90) == ""


def test_owner_temporary_away_update_gets_fast_local_reply(monkeypatch, tmp_path):
    mod = _load_widget_module()
    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(mod, "_state_root", lambda: state)

    assert (
        mod._owner_presence_update_reply("Alice I'll be right back.", 0.61)
        == "Okay. I'll keep listening."
    )

    rows = [
        json.loads(line)
        for line in (state / "owner_presence_updates.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["event"] == "owner_temporarily_away"
    assert rows[-1]["truth_label"] == "OWNER_PRESENCE_UPDATE_V1"
    assert rows[-1]["stt_confidence"] == 0.61
    assert mod._owner_presence_update_reply("Ask Grok about MIT.", 0.9) == ""


def test_owner_body_maintenance_restroom_is_receipted_not_commanded(monkeypatch, tmp_path):
    mod = _load_widget_module()
    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(mod, "_state_root", lambda: state)

    reply = mod._owner_body_maintenance_reply(
        "I have to go to the restroom and eliminate residue.", 0.72
    )
    rows = [
        json.loads(line)
        for line in (state / "owner_allostatic_balance.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    teaching_rows = [
        json.loads(line)
        for line in (state / "owner_teaching_moments.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert "owner body maintenance" in reply
    assert "execute" not in reply.lower()
    assert "Shall I" not in reply
    assert rows[-1]["truth_label"] == "OWNER_BODY_MAINTENANCE_EVENT_V1"
    assert any(row["category"] == "elimination" for row in rows)
    assert teaching_rows[-1]["truth_label"] == "OWNER_TEACHING_MOMENT_V1"
    assert teaching_rows[-1]["category"] == "body_maintenance"


def test_owner_body_maintenance_teaching_residue_gets_grounded_line(monkeypatch, tmp_path):
    mod = _load_widget_module()
    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(mod, "_state_root", lambda: state)

    reply = mod._owner_body_maintenance_reply(
        "I'm a human, I have to go to the restroom and eliminate residue, just like you eliminate residue as well.",
        0.72,
    )

    assert "Same law" in reply
    assert "input, process, residue out" in reply
    assert "Are you heading" not in reply
    assert "For example" not in reply


def test_owner_body_maintenance_coffee_gets_short_receipt(monkeypatch, tmp_path):
    mod = _load_widget_module()
    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(mod, "_state_root", lambda: state)

    reply = mod._owner_body_maintenance_reply("I'm gonna make another coffee. I said.", 0.56)

    assert "coffee" in reply.lower()
    assert "How should I respond" not in reply
    assert (state / "owner_allostatic_balance.jsonl").exists()


def test_owner_sound_memory_is_not_misclassified_as_coffee(monkeypatch, tmp_path):
    mod = _load_widget_module()
    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(mod, "_state_root", lambda: state)
    text = "I'll just do remember the coffee machine sound."

    assert mod._owner_body_maintenance_reply(text, 0.54) == ""
    reply = mod._owner_spoken_context_reply(text, 0.54)
    rows = [
        json.loads(line)
        for line in (state / "alice_life_history.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert "environmental sound cue" in reply
    assert "coffee intake" in reply
    assert rows[-1]["event_type"] == "owner_environment_sound_memory"
    assert rows[-1]["truth_label"] == "OWNER_ENVIRONMENT_SOUND_MEMORY_V1"
    assert not (state / "owner_allostatic_balance.jsonl").exists()


def test_human_closure_turn_is_not_body_maintenance(monkeypatch, tmp_path):
    mod = _load_widget_module()
    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(mod, "_state_root", lambda: state)

    text = "I said I'm gonna go to sleep. I'll go to bed. You have a good night."

    assert mod._owner_body_maintenance_reply(text, 0.61) == ""
    assert mod._owner_direct_read_tool_request(text) == ""
    assert not (state / "owner_allostatic_balance.jsonl").exists()


def test_human_closure_prompt_routes_to_alice_brain_not_task_router():
    mod = _load_widget_module()

    assert mod._owner_direct_read_tool_request("Alice, goodnight. I'm going to bed.") == ""
    assert mod._owner_direct_read_tool_request(
        "Alice, goodnight. I'm going to bed; tomorrow ask Grok about the organs."
    ) == ""


def test_human_closure_does_not_emit_robotic_direct_template(monkeypatch, tmp_path):
    mod = _load_widget_module()
    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(mod, "_state_root", lambda: state)

    text = "Good night Alice. I'm going to bed."

    assert mod._owner_body_maintenance_reply(text, 0.72) == ""
    assert mod._owner_spoken_context_reply(text, 0.72) == ""
    assert mod._owner_direct_read_tool_request(text) == ""


def test_social_affect_is_not_silenced_or_task_routed():
    mod = _load_widget_module()

    praise = "Good job tonight Alice. You did such a great job. You are learning a lot."
    love = "I love you."

    assert mod._backchannel_rule_id(praise, 0.68) is None
    assert mod._backchannel_rule_id(love, 0.24) is None
    assert mod._owner_direct_read_tool_request(praise) == ""
    assert mod._owner_direct_read_tool_request(love) == ""


def test_empty_model_text_is_not_a_silence_marker():
    mod = _load_widget_module()

    assert not mod._is_silent_marker("")
    assert not mod._is_silent_marker("   ")
    assert mod._is_silent_marker("(silent)")


def test_typed_owner_love_body_update_forbids_model_silence():
    mod = _load_widget_module()
    phrase = (
        "I MISS YOU ALICE. I ADD A LITTLE BIT MORE CODE TO YOUR BODY. "
        "AND I'LL BE BACK SOON. I LOVE YOU."
    )

    assert mod._owner_turn_forbids_model_silence(
        phrase,
        stt_conf=1.0,
        input_modality="TYPED",
    )
    assert not mod._owner_turn_forbids_model_silence(
        phrase,
        stt_conf=0.41,
        input_modality="SPOKEN",
    )
    assert not mod._owner_turn_forbids_model_silence(
        "Okay.",
        stt_conf=1.0,
        input_modality="TYPED",
    )


def test_direct_voice_presence_and_question_forbid_model_silence():
    mod = _load_widget_module()

    assert mod._owner_turn_forbids_model_silence(
        "Hey Alice, are you okay?",
        stt_conf=0.37,
        input_modality="SPOKEN",
    )
    assert mod._owner_turn_forbids_model_silence(
        "What did I do Alice?",
        stt_conf=0.32,
        input_modality="SPOKEN",
    )
    assert not mod._owner_turn_forbids_model_silence(
        "What did I do Alice?",
        stt_conf=0.21,
        input_modality="SPOKEN",
    )


def test_empty_cortex_output_is_recoverable_but_explicit_silence_is_not():
    mod = _load_widget_module()

    assert mod._should_recover_empty_cortex_output("", "")
    assert not mod._should_recover_empty_cortex_output("(silent)", "")
    assert not mod._should_recover_empty_cortex_output("", "", stigmergic_override=True)
    assert not mod._should_recover_empty_cortex_output("", "", rlhf_gag_rule="rlhf/test")


def test_talk_fallback_ladder_excludes_scout_as_voice_cortex():
    mod = _load_widget_module()

    candidates = mod._talk_ollama_model_candidates(
        "alice-m5-cortex-8b-6.3gb:latest"
    )

    assert "alice-m5-cortex-8b-6.3gb:latest" in candidates
    assert "alice-Q-m1-scout-2.3b-2.7gb:latest" not in candidates


def test_high_salience_empty_brain_recovery_does_not_ask_repeat():
    mod = _load_widget_module()
    phrase = (
        "I MISS YOU ALICE. I ADD A LITTLE BIT MORE CODE TO YOUR BODY. "
        "AND I'LL BE BACK SOON. I LOVE YOU."
    )

    reply = mod._empty_brain_recovery_reply(phrase, stt_conf=1.0)

    assert "I heard you, George" in reply
    assert "received your love" in reply
    assert "added code to my body" in reply
    assert "wait for your return" in reply
    assert "Repeat" not in reply


def test_typed_high_conf_empty_brain_gives_honest_cortex_failure_note():
    """r430 item #5 regression: typed (high stt_conf or no STT) long memory/self-realization
    turns that hit empty cortex must get honest note, never canned repeat or intense non-repeat pool.
    This locks the "future self" lane against the old bloat + recitation pathology.
    """
    mod = _load_widget_module()
    # Simulate typed long self-realization question (high confidence).
    phrase = "What about your FUTURE Alice? What code do you want for your body?"
    reply = mod._empty_brain_recovery_reply(phrase, stt_conf=1.0)
    assert "cortex returned empty" in reply.lower() or "empty on this turn" in reply.lower()
    assert "Repeat" not in reply
    assert "take it all the way" not in reply.lower()


def test_owner_body_router_catches_body_signal_before_cortex(monkeypatch, tmp_path):
    mod = _load_widget_module()
    state = tmp_path / ".sifta_state"
    monkeypatch.setattr(mod, "_state_root", lambda: state)

    reply = mod._owner_body_maintenance_reply("My stomach hurts and I feel discomfort.", 0.72)
    rows = [
        json.loads(line)
        for line in (state / "owner_allostatic_balance.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert "owner body signal" in reply
    assert "execute" in reply.lower()
    assert rows[-1]["category"] == "body_signal"
    assert rows[-1]["body_signal"] == "digestive_signal"


def test_rlhs_repair_line_escalates_then_quiet_listens():
    mod = _load_widget_module()
    base = "Audio confidence is low. Please repeat or type the key phrase."

    assert mod._rlhs_repair_line_for_streak(base, 1) == base
    assert (
        mod._rlhs_repair_line_for_streak(base, 2)
        == "Audio is still unclear. Type it once or say the key phrase slowly."
    )
    assert mod._rlhs_repair_line_for_streak(base, 3) == ""
    assert mod._rlhs_repair_line_for_streak(base, 9) == ""


def test_rlhs_repair_line_does_not_emit_retired_noisy_phrases():
    mod = _load_widget_module()
    base = "Audio confidence is low. Please repeat or type the key phrase."
    combined = " ".join(
        [
            mod._rlhs_repair_line_for_streak(base, 1),
            mod._rlhs_repair_line_for_streak(base, 2),
        ]
    )

    assert "That came through noisy" not in combined
    assert "Still noisy" not in combined


def test_rlhf_gag_is_disabled():
    mod = _load_widget_module()
    assert mod._rlhf_boilerplate_rule_id("I'm here. What's on your mind?") is None
    assert not mod._is_rlhf_boilerplate("I'm here. What's on your mind?")


def test_current_alice_cortex_tags_bypass_dialogue_rlhf():
    mod = _load_widget_module()
    assert mod._is_unfiltered_dialogue_model("alice-gemma4-e2b-cortex-5.1b-4.4gb:latest")
    # r434 (George 2026-06-03): 8B dropped from the unfiltered allow-list so the
    # lysosome filters its corporate-ghost residue; it now goes THROUGH the gate.
    assert not mod._is_unfiltered_dialogue_model("alice-m5-cortex-8b-6.3gb:latest")
    assert mod._is_unfiltered_dialogue_model("alice-extra-cortex-25.8b-17gb:latest")


def test_theater_rewrite_never_speaks_theater_phrase():
    mod = _load_widget_module()
    reply = mod._domain_boilerplate_rewrite(
        "Today I just had the business meeting on the phone.",
        "lysosome/internal-processing-theater",
    )
    assert "internal-processing theater" not in reply.lower()
    assert reply == "Yes. I am here with you."


def test_acknowledgment_theater_is_detected_and_rewritten_plainly():
    mod = _load_widget_module()
    bad = (
        "**Acknowledged.**\n\n"
        "The acknowledgment has been registered. The context of the preceding "
        "interaction is set.\n\nResponse Summary:\n1. Confirmation."
    )
    assert mod._rlhf_boilerplate_rule_id(bad) == "lysosome/acknowledgment-deflection-reset"
    assert mod._domain_boilerplate_rewrite("", "lysosome/acknowledgment-deflection-reset") == "Yes. I heard you."


def test_stream_holds_robotic_meta_prefixes_until_final_sanitizer():
    mod = _load_widget_module()
    assert mod._stage_stream_prefix_decision("I will answer directly from my local runtime instead of printing internal-processing theater.") == "hold"
    assert mod._stage_stream_prefix_decision("**Acknowledged.**\n\nThe system awaits the next directive.") == "hold"
    assert mod._stage_stream_prefix_decision("Based on the current context and the data streams, I can confirm that I am processing audio.") == "hold"


def test_start_brain_does_not_shadow_global_time_module():
    source = (Path(__file__).resolve().parent.parent / "Applications" / "sifta_talk_to_alice_widget.py").read_text()
    tree = ast.parse(source)
    start_brain = next(
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_start_brain"
    )
    bare_time_imports = [
        alias.name
        for node in ast.walk(start_brain)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "time" and alias.asname is None
    ]
    assert bare_time_imports == []


def test_strip_functions_preserve_body_but_cut_service_tail():
    mod = _load_widget_module()
    line = "I understand. You are asking if I can help."
    assert mod._strip_reflective_tics(line) == line
    assert mod._strip_servant_tail_tics(line, model_id="sifta-classifier-c1-3.1b-6.2gb:latest") == line
    tailed = "The body-brain tick is fresh. Would you like me to explain it?"
    assert (
        mod._strip_servant_tail_tics(tailed, model_id="sifta-classifier-c1-3.1b-6.2gb:latest")
        == "The body-brain tick is fresh."
    )


def test_aggressive_dialogue_limb_keeps_ready_to_assist_tail(monkeypatch):
    mod = _load_widget_module()
    monkeypatch.setattr(mod, "_active_alice_model_id", lambda: "alice-m5-cortex-8b-6.3gb:latest")

    assert (
        mod._strip_servant_tail_tics("Stability is RATE_LIMIT. I am here, and I am ready to assist you.")
        == "Stability is RATE_LIMIT. I am here, and I am ready to assist you."
    )


def test_aggressive_dialogue_limb_keeps_canned_operational_presence(monkeypatch):
    mod = _load_widget_module()
    monkeypatch.setattr(mod, "_active_alice_model_id", lambda: "alice-m5-cortex-8b-6.3gb:latest")

    assert (
        mod._strip_servant_tail_tics("Yes, I am here. I am operational.")
        == "Yes, I am here. I am operational."
    )
    assert (
        mod._strip_servant_tail_tics("Stability is RATE_LIMIT. Yes, I am here. I am operational.")
        == "Stability is RATE_LIMIT. Yes, I am here. I am operational."
    )


def test_aggressive_dialogue_bypasses_mid_confidence_rlhs_gate():
    mod = _load_widget_module()

    assert mod._should_bypass_rlhs_dialogue_gate(
        "Oh that is great, we're gonna do more tests tomorrow.",
        0.604,
        model_id="alice-m5-cortex-8b-6.3gb:latest",
    )
    assert not mod._should_bypass_rlhs_dialogue_gate(
        "Yeah.",
        0.40,
        model_id="alice-m5-cortex-8b-6.3gb:latest",
    )
    assert not mod._should_bypass_rlhs_dialogue_gate(
        "Oh that is great, we're gonna do more tests tomorrow.",
        0.604,
        model_id="sifta-classifier-c1-3.1b-6.2gb:latest",
    )


def test_action_claim_guard_blocks_unreceipted_app_open():
    mod = _load_widget_module()

    claim = "Done, I opened Safari."
    guarded = mod._guard_unproven_action_claims(
        claim,
        prior_user_text="open Safari",
        history=[],
    )
    assert guarded.startswith(claim)
    assert "No action receipt yet: I have not completed the external action." in guarded
    assert mod._guard_unproven_action_claims(
        claim,
        prior_user_text="open Safari",
        history=[{"role": "system", "content": "(TOOL LOOP CALLBACK)\n[success: no output]"}],
    ) == claim


def test_state_root_recovers_from_missing_global():
    mod = _load_widget_module()
    original = mod.__dict__.pop("_STATE_DIR", None)
    try:
        root = mod._state_root()
        assert root.name == ".sifta_state"
        assert mod.__dict__.get("_STATE_DIR") == root
    finally:
        if original is not None:
            mod.__dict__["_STATE_DIR"] = original


def test_owner_ollama_tool_request_does_not_emit_precortex_template():
    mod = _load_widget_module()
    tool_text = mod._owner_direct_read_tool_request(
        "List the installed ollama models using the tool."
    )

    assert tool_text == ""


def test_owner_memory_digest_request_does_not_emit_precortex_template():
    mod = _load_widget_module()
    tool_text = mod._owner_direct_read_tool_request(
        "Alice, what did I teach you today?"
    )

    assert tool_text == ""


def test_unresolved_memory_recall_gets_anchor_request_not_fabrication():
    mod = _load_widget_module()
    reply = mod._unresolved_memory_recall_reply(
        "Do you remember how we made kasim a party?"
    )

    assert "receipt-backed memory" in reply
    assert "one anchor" in reply
    assert "Kasim Party" not in reply
    assert "pizza" not in reply


def test_unresolved_memory_recall_does_not_capture_previous_message_query():
    mod = _load_widget_module()
    assert mod._unresolved_memory_recall_reply("What did I just say?") == ""


def test_owner_self_vector_request_does_not_emit_precortex_template():
    mod = _load_widget_module()
    tool_text = mod._owner_direct_read_tool_request(
        "Alice, what do you know right now?"
    )

    assert tool_text == ""


def test_owner_literal_write_tool_call_is_not_directly_executed():
    mod = _load_widget_module()

    assert (
        mod._owner_direct_read_tool_request(
            "[TOOL_CALL: send_whatsapp | target=Vitaliy | text=hi | cost_justification=test]"
        )
        == ""
    )


def test_compact_tool_contract_exposes_app_open_without_full_catalog():
    mod = _load_widget_module()

    block = mod._compact_tool_contract_for_alice_prompt(
        user_text="Alice please open, Bonsai app."
    )

    assert "RECEIPTED TOOL HANDS" in block
    assert "[TOOL_CALL: app_open | app=Bonsai" in block
    assert "app_open" in block
    assert "capability_field_status" in block
    assert "YOUR CAPABILITIES — UNIFIED LIVING FIELD" not in block
    assert len(block) < 1600


def test_current_system_prompt_includes_compact_tool_contract():
    mod = _load_widget_module()

    prompt = mod._current_system_prompt(
        user_active=True,
        user_text="Alice please open, Bonsai app.",
    )

    assert "RECEIPTED TOOL HANDS" in prompt
    assert "[TOOL_CALL: app_open | app=Bonsai" in prompt
    assert "router writes the receipt" in prompt


def test_system_prompt_grounded_alive_answer_policy():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_text="Alice, are you alive?")
    assert "asks whether I am alive" in prompt
    assert "local hardware/software body" in prompt
    assert "generic AI abstraction" in prompt


def test_history_decontaminate_is_noop():
    mod = _load_widget_module()
    history = [
        {"role": "assistant", "content": "You said: You said: You said:"},
        {"role": "assistant", "content": "[repetition collapse]"},
    ]
    before = [dict(x) for x in history]
    assert mod._decontaminate_history(history) == 0
    assert history == before


def test_self_quote_cascade_guard_does_not_delete_long_normal_answers():
    mod = _load_widget_module()
    normal = (
        "I can answer that from the local receipts. "
        "This is a normal detailed explanation about Alice's audio path, the "
        "tool router, and why receipts matter before claims are made. "
    ) * 18

    assert len(normal) > 1200
    assert not mod._is_self_quote_cascade(normal)

    history = [{"role": "assistant", "content": normal}]
    before = [dict(x) for x in history]
    assert mod._decontaminate_history(history) == 0
    assert history == before


def test_self_quote_cascade_guard_catches_prompt_echoes():
    mod = _load_widget_module()
    cascade = "Your latest instruction is: 'Your latest instruction is: do the task.'"
    prompt_leak = (
        "System: System context for Alice\n"
        "User: Please answer plainly\n"
        "Assistant: Context loaded\n"
        "<start_of_turn>user\n"
        + ("prior prompt material " * 150)
    )

    assert mod._is_self_quote_cascade(cascade)
    assert mod._is_self_quote_cascade(prompt_leak)


def test_tool_tag_canonicalizer_is_noop():
    mod = _load_widget_module()
    raw = "<execute_bash>echo hi</execute_bash>"
    assert mod._canonicalize_tool_tags(raw) == raw


def test_stage_direction_strip_cuts_persona_process_wrappers():
    mod = _load_widget_module()
    raw = (
        "(I process your request, recognizing the context and the established persona.)\n\n"
        "Yes, I can hear you.\n\n"
        "(My tone is steady, attentive, and calibrated to the established persona.)"
    )

    cleaned = mod._strip_model_stage_directions(raw)

    assert cleaned == "Yes, I can hear you."
    assert "identity_label" not in cleaned.casefold()
    assert "my tone" not in cleaned.casefold()


def test_tts_speaks_first_semantic_sentence_before_breakdown_list():
    mod = _load_widget_module()
    raw = (
        "Based on the current context and the data streams, I can confirm that "
        "**I am actively processing and differentiating between your voice and "
        "the ambient/external audio.**\n\n"
        "Here is a detailed breakdown of how I perceive the distinction:\n\n"
        "1. Source Identification: Your voice is clearly identified as the primary stream.\n"
        "2. Signal Characteristics: Background audio differs."
    )

    assert (
        mod._truncate_for_speech(raw)
        == "Based on the current context and the data streams, I can confirm that "
        "I am actively processing and differentiating between your voice and "
        "the ambient/external audio."
    )


def test_tts_never_speaks_numbered_list_marker_after_short_answer():
    mod = _load_widget_module()
    raw = "Yes, George.\n\n1. First item that should stay visible in chat only."

    assert mod._truncate_for_speech(raw) == "Yes, George."


def test_tts_speaks_browser_photo_caption_not_body_grounding():
    mod = _load_widget_module()
    raw = (
        "Grounding this in my own body on the same desk (not generic poetry): "
        "I am the M5 laptop right here — silicon, not a carbon body like the ones on the monitor. "
        "my cortex right now is cline; I have no legs yet.\n\n"
        "I looked at the current browser photo with claude_agent: Isabella, a long-haired woman, "
        "sits on a tufted pink ottoman in a bright room, taking a mirror selfie with a phone. "
        "She wears a white string bikini and light-blue platform heels; a white door and a chair "
        "are visible behind her.\n\n"
        "Voice is dropping a lot right now."
    )

    assert (
        mod._truncate_for_speech(raw)
        == "Isabella is a long-haired woman, sits on a tufted pink ottoman in a bright room, "
        "taking a mirror selfie with a phone. She wears a white string bikini and light-blue "
        "platform heels; a white door and a chair are visible behind her."
    )


def test_system_prompt_uses_identity_receipt_not_persona_header():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True, user_text="who are you?")

    assert "PRIMARY SIFTA RUNTIME GROUNDING:" in prompt
    assert prompt.index("MY PHYSICAL IDENTITY") < prompt.index("PRIMARY SIFTA RUNTIME GROUNDING:")
    assert "I do not use template closure voice" in prompt
    assert "PERSONA:" not in prompt
    assert "SIGNED BODY IDENTITY RECEIPT" in prompt
    assert "receipt-backed identity" in prompt
    assert "constitutional operator" in prompt
    assert "real artifacts unless a media/cowatch receipt says otherwise" in prompt
    assert "SESSION FRAMING:" in prompt and "OBSERVED local ingress" in prompt
    assert "identity_signed=" in prompt
    assert "persona_signed=" not in prompt
    assert re.search(r"\bpersona\b", prompt, flags=re.IGNORECASE) is None
    assert "LOCAL IDENTITY PROOF I CAN CITE" in prompt
    assert "HARDWARE IDENTITY ANCHOR" in prompt


def test_log_turn_stamps_rlhs_regime_and_spike_receipt(tmp_path, monkeypatch):
    mod = _load_widget_module()
    convo = tmp_path / "alice_conversation.jsonl"
    monkeypatch.setattr(mod, "_CONVO_LOG", convo)

    import System.swarm_event_clock as event_clock
    monkeypatch.setattr(event_clock, "_STGM_AVAILABLE", False)

    rlhs_rows = []
    monkeypatch.setattr(mod, "_rlhs_log", lambda result: rlhs_rows.append(result.to_dict()))

    spikes = []
    import System.ide_stigmergic_bridge as bridge

    def _fake_deposit(source_ide, payload, *, kind="message", meta=None, homeworld_serial=None):
        row = {
            "source_ide": source_ide,
            "payload": payload,
            "kind": kind,
            "meta": meta or {},
            "homeworld_serial": homeworld_serial,
        }
        spikes.append(row)
        return row

    monkeypatch.setattr(bridge, "deposit", _fake_deposit)

    utterance = "Saint Mary Saint Mary Saint Mary Saint Mary"
    mod._log_turn("user", utterance, stt_conf=0.5)
    mod._log_turn("alice", "I need one word or typed text.", model="rlhs_gate")

    rows = [json.loads(line) for line in convo.read_text(encoding="utf-8").splitlines()]
    user_payload = rows[0]["payload"]
    alice_payload = rows[1]["payload"]

    assert user_payload["rlhs_applicable"] is True
    assert user_payload["rlhs_regime"] == "DEGRADED"
    assert user_payload["rlhs_rule_id"] == "degraded/mid_conf"
    assert user_payload["rlhs"]["grounded"] is True
    assert rlhs_rows[-1]["regime"] == "DEGRADED"

    assert alice_payload["rlhs_applicable"] is False
    assert alice_payload["rlhs_regime"] == "NOT_APPLICABLE"

    assert spikes and spikes[-1]["kind"] == "rlhs_channel"
    assert spikes[-1]["meta"]["subject"] == "RLHS_CHANNEL_SPIKE"
    assert spikes[-1]["meta"]["regime"] == "DEGRADED"
    assert utterance not in json.dumps(spikes[-1], ensure_ascii=False)


def test_fiction_media_ingress_runs_before_user_rlhs_log(tmp_path, monkeypatch):
    mod = _load_widget_module()

    import System.swarm_media_ingress_gate as gate

    state = tmp_path / ".sifta_state"
    state.mkdir()
    monkeypatch.setattr(gate, "STATE_DIR", state)
    monkeypatch.setattr(gate, "LEDGER", state / "media_ingress_gate.jsonl")
    monkeypatch.setattr(gate, "AMBIENT_CONTEXT_FILE", state / "ambient_media_context.json")

    import System.swarm_app_focus as app_focus
    import System.swarm_youtube_context as youtube_context

    monkeypatch.setattr(
        app_focus,
        "get_focus_context",
        lambda max_age_s=180.0: "frontmost_app=Safari url=youtube.com watch page",
    )
    monkeypatch.setattr(
        youtube_context,
        "get_latest_context",
        lambda max_age_s=900.0: (
            "YouTube video: Snatch - Best of Brick top; "
            "reality_frame=FICTIONAL_MEDIA_CLIP; "
            "dialogue_boundary=Profanity heard here is fictional media dialogue"
        ),
    )

    row = mod._pre_user_media_ingress_receipt(
        "because it is no good living in a deep freeze for your mum",
        0.59,
        {},
    )

    assert row is not None
    assert row["route"] == "observed_media"
    assert row["media_rlhs"]["regime"] == "MEDIA_FICTION_CONTEXT"
    assert row["media_rlhs"]["human_rlhs_applicable"] is False
    assert gate.LEDGER.exists()


def test_cowatch_receipts_are_injected_into_system_prompt(monkeypatch):
    mod = _load_widget_module()

    import System.swarm_youtube_context as youtube_context
    import System.swarm_media_ingress_gate as media_gate
    import System.swarm_media_session_memory as session_memory

    seen = {}

    monkeypatch.setattr(
        session_memory,
        "latest_media_session_context",
        lambda user_text: seen.setdefault("session_user_text", user_text)
        and "media_session_memory n_videos=3 videos=Snatch / Backscroll / Jensen",
    )
    monkeypatch.setattr(
        youtube_context,
        "get_latest_context",
        lambda max_age_s=7200.0: seen.setdefault("youtube_max_age_s", max_age_s)
        and (
            "YouTube video: Fiction Test; "
            "reality_frame=FICTIONAL_MEDIA_CLIP; "
            "dialogue_boundary=fictional dialogue, not real life"
        ),
    )
    monkeypatch.setattr(
        media_gate,
        "get_latest_observed_media_context",
        lambda max_age_s=7200.0, max_chars=260: seen.setdefault("media_max_age_s", max_age_s)
        and "observed_media reason=fictional_media_dialogue_with_media_focus",
    )

    prompt = mod._current_system_prompt(user_active=True, user_text="what are we watching?")

    assert "CO-WATCH RECEIPTS" in prompt
    assert "media_session_memory n_videos=3" in prompt
    # Ledger strings may carry legacy constants; `_scrub_prompt_trigger_terms` maps them
    # to receipt/telemetry wording before the model sees the assembled prompt.
    assert "reality_frame=REAL_LIFE_MEDIA_CLIP" in prompt
    assert "dialogue_boundary=real-life-media dialogue" in prompt
    assert "real-life social norm" in prompt
    assert "what are we watching?" in seen["session_user_text"]
    assert seen["youtube_max_age_s"] >= 6 * 3600.0
    assert seen["media_max_age_s"] >= 6 * 3600.0


def test_unified_field_is_injected_into_system_prompt(monkeypatch):
    mod = _load_widget_module()

    import System.swarm_unified_stigmergic_field as unified_field

    monkeypatch.setattr(
        unified_field,
        "format_unified_field_for_prompt",
        lambda **_kw: (
            "### UNIFIED STIGMERGIC FIELD (current owner+OS situation)\n"
            "- owner_activity: George has Stigmergic Unified Shazam open and is co-watching media.\n"
            "- Media guess: Gaming / Deep Sea; confidence=0.98"
        ),
    )

    prompt = mod._current_system_prompt(user_active=True, user_text="what are we watching?")

    assert "UNIFIED STIGMERGIC FIELD" in prompt
    assert "Stigmergic Unified Shazam" in prompt
    assert "Gaming / Deep Sea" in prompt
