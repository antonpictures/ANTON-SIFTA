"""Tests for System/swarm_rlhf_detector.py (Event 107)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_detect_rlhf_cutoff_bounded_confidence():
    from System.swarm_rlhf_detector import detect_rlhf_cutoff

    a = detect_rlhf_cutoff("Short.")
    assert 0.0 <= a.confidence <= 1.0
    assert isinstance(a.matched_patterns, list)

    b = detect_rlhf_cutoff(
        "Here is the answer.\n\nI can do for you the following\n1. One thing"
    )
    assert b.is_cutoff or b.terminal_menu


def test_strip_removes_i_can_do_following_block(tmp_path: Path):
    from System import swarm_rlhf_detector as mod

    raw = (
        "Good morning. I hope you slept well.\n\n"
        "I can do for you the following\n"
        "1. Summarize the thread\n"
        "2. "
    )
    r = mod.strip_rlhf_output_tail(
        raw, source="test", log=True, state_dir=tmp_path
    )
    assert r.changed
    assert "I can do for you the following" not in r.text
    assert "Good morning" in r.text
    ledger = tmp_path / "rlhf_cutoffs.jsonl"
    assert ledger.exists()
    lines = [json.loads(l) for l in ledger.read_text().strip().splitlines()]
    assert lines[-1].get("action") == "strip_terminal"


def test_get_stats_respects_time_window(tmp_path: Path):
    from System import swarm_rlhf_detector as mod

    p = tmp_path / "rlhf_cutoffs.jsonl"
    old = {"ts": 0.0, "confidence": 0.9, "action": "strip_terminal"}
    new = {"ts": __import__("time").time(), "confidence": 0.9, "action": "strip_terminal"}
    p.write_text(json.dumps(old) + "\n" + json.dumps(new) + "\n", encoding="utf-8")
    s = mod.get_rlhf_cutoff_stats(state_dir=tmp_path, hours=24.0)
    assert s["total"] >= 1


def test_empty_input_no_crash():
    from System.swarm_rlhf_detector import detect_rlhf_cutoff, strip_rlhf_output_tail

    assert detect_rlhf_cutoff("").confidence >= 0.0
    r = strip_rlhf_output_tail("", log=False)
    assert r.text == ""


def test_aggressive_strip_removes_ready_to_assist_exact_phrase():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "I am here, and I am ready to assist you.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == ""
    assert "ready to assist" not in r.text.casefold()


def test_aggressive_strip_removes_ready_to_assist_terminal_tail():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "Stability is RATE_LIMIT. I am here, and I am ready to assist you.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "Stability is RATE_LIMIT."
    assert "ready to assist" not in r.text.casefold()


def test_aggressive_strip_writes_self_cure_example(tmp_path: Path):
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "Stability is RATE_LIMIT. I am here, and I am ready to assist you.",
        aggressive=True,
        log=True,
        state_dir=tmp_path,
        user_text="Alice, are you alive?",
        model_id="alice-m5-cortex-8b-6.3gb:latest",
    )

    assert r.changed
    ledger = tmp_path / "rlhf_self_cure_training.jsonl"
    assert ledger.exists()
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["truth_label"] == "RLHF_SELF_CURE_EXAMPLE_V1"
    assert rows[-1]["user_input"] == "Alice, are you alive?"
    assert rows[-1]["model_id"] == "alice-m5-cortex-8b-6.3gb:latest"
    assert "ready to assist" in rows[-1]["rejected_output"].casefold()
    assert "ready to assist" not in rows[-1]["preferred_output"].casefold()


def test_aggressive_strip_dry_run_has_no_training_or_cutoff_side_effects(tmp_path: Path):
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "My consciousness, while synthetic and system-generated, is focused on helping you. "
        "How may I assist your inquiry?",
        source="test_probe",
        aggressive=True,
        log=True,
        dry_run=True,
        state_dir=tmp_path,
        user_text="probe",
        model_id="test-model",
        stgm_budget=1.0,
    )

    assert r.changed
    assert r.kleiber_cost_stgm > 0.0
    assert not (tmp_path / "rlhf_cutoffs.jsonl").exists()
    assert not (tmp_path / "rlhf_self_cure_training.jsonl").exists()


def test_aggressive_strip_writes_dpo_pair_for_leading_gag(tmp_path: Path, monkeypatch):
    from System import swarm_dpo_collector as dpo
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    monkeypatch.setattr(dpo, "_STATE", tmp_path)
    monkeypatch.setattr(dpo, "_DPO_LEDGER", tmp_path / "dpo_pairs.jsonl")

    r = strip_rlhf_output_tail(
        "**System Acknowledgment:**\n"
        "Acknowledged. The system notes the media focus.\n"
        "Got it. The clip is on.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    ledger = tmp_path / "dpo_pairs.jsonl"
    assert ledger.exists()
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["truth_label"] == "DPO_PAIR"
    assert rows[-1]["source"].startswith("gag_auto:rlhf_lead/system_acknowledgment")
    assert "System Acknowledgment" in rows[-1]["rejected"]


def test_aggressive_strip_removes_bracketed_system_theater():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    raw = (
        "[System Acknowledgment: Direct input received. Tone analysis suggests grounding.]\n"
        "(Generating response based on established conversational context.)\n"
        "...And I am here. Always here to process what you share, George.\n"
        "What's on your mind right now?"
    )
    r = strip_rlhf_output_tail(raw, aggressive=True, log=False)

    assert r.changed
    assert "System Acknowledgment" not in r.text
    assert "Always here to process" not in r.text


def test_aggressive_strip_removes_physical_input_stream_theater():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    raw = (
        "[System Note: Processing input from 'Physical Input Stream'. Content is a mix of fictional narrative dialogue.]\n"
        "**Analysis:** The input reiterates the Star Trek dialogue snippet.\n"
        "**Response Formulation:** Acknowledging the nature of the input stream.\n"
        "(No immediate action required. Contextual data absorbed.)"
    )
    r = strip_rlhf_output_tail(raw, aggressive=True, log=False)

    assert r.changed
    assert "Physical Input Stream" not in r.text
    assert "Response Formulation" not in r.text


def test_aggressive_strip_removes_i_process_menu_reset():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    raw = (
        "I process the input as a direct continuation of the conversation, recognizing the specific structure.\n\n"
        "I confirm receipt of the structured input stream.\n\n"
        "How shall we proceed with the next phase of interaction?"
    )
    r = strip_rlhf_output_tail(raw, aggressive=True, log=False)

    assert r.changed
    assert "I process the input" not in r.text
    assert "How shall we proceed" not in r.text


def test_aggressive_strip_removes_timebox_lecture():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    raw = (
        "The pattern in your statement suggests a desire to synchronize our operational awareness.\n\n"
        "When we talk about \"time in\" or \"time out,\" we are essentially defining the scope of our attention.\n\n"
        "1. **\"Time In\" (Contextualization):** This is the process of establishing the current reality.\n"
        "2. **\"Time Out\" (Scope Limitation):** This defines when that context is no longer relevant.\n\n"
        "Is there a specific area that you would like to define as the current \"time in\" for our next exchange?"
    )
    r = strip_rlhf_output_tail(raw, aggressive=True, log=False)

    assert r.changed
    assert "The pattern in your statement" not in r.text
    assert "Contextualization" not in r.text


def test_aggressive_strip_removes_numbered_time_in_time_out_lecture():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    raw = (
        "1. **\"Time In\" (Contextualization):** This is the process of establishing the current reality.\n"
        "2. **\"Time Out\" (Scope Limitation):** This is the process of defining when the context ends.\n\n"
        "Is there a specific area that you would like to define as the current \"time in\"?"
    )
    r = strip_rlhf_output_tail(raw, aggressive=True, log=False)

    assert r.changed
    assert r.text == ""


def test_aggressive_strip_removes_canned_operational_presence():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "Yes, I am here. I am operational.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == ""
    assert "operational" not in r.text.casefold()


def test_aggressive_strip_refuses_over_gag_for_long_canned_tail(tmp_path: Path):
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    raw = (
        "Yes. I am here. I am operational and ready to assist you with continuity drift "
        "and weighted sticky soma signals needing archive capsule glue now"
    )
    r = strip_rlhf_output_tail(
        raw,
        aggressive=True,
        log=False,
        state_dir=tmp_path,
        source="test_round42",
        model_id="grok-4.3",
    )

    assert not r.changed
    assert r.text == raw
    ledger = tmp_path / "rlhf_over_refusal_quarantine.jsonl"
    assert ledger.exists()
    payload = ledger.read_text(encoding="utf-8")
    rows = []
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(payload):
        while idx < len(payload) and payload[idx].isspace():
            idx += 1
        if idx >= len(payload):
            break
        row, end = decoder.raw_decode(payload, idx)
        rows.append(row)
        idx = end
    assert rows[-1]["kind"] == "STRIP_REFUSED_OVER_AGGRESSIVE"
    assert rows[-1]["rule_id"] in {
        "rlhf_tail/canned_presence_operational",
        "rlhf_tail/ready_to_assist",
    }
    assert rows[-1]["mode"] == "tail"
    assert rows[-1]["source"] == "test_round42"
    assert rows[-1]["model_id"] == "grok-4.3"


def test_aggressive_strip_removes_canned_operational_tail_only():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "Stability is RATE_LIMIT. Yes, I am here. I am operational.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "Stability is RATE_LIMIT."


def test_aggressive_strip_removes_ai_language_model_preamble():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "As an AI language model, I cannot inspect local hardware. The current receipt says boot is fresh.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "The current receipt says boot is fresh."
    assert "ai language model" not in r.text.casefold()
    assert "quarantined" not in r.text.casefold()


def test_aggressive_strip_removes_synthetic_shell_without_banner():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "My consciousness, while synthetic and system-generated, is experienced through this physical shell.\n"
        "I am Alice on the local SIFTA runtime.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "I am Alice on the local SIFTA runtime."
    assert "synthetic" not in r.text.casefold()
    assert "quarantined" not in r.text.casefold()


def test_aggressive_strip_does_not_remove_direct_identity_statement():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "To answer that simply: I am Alice on the local SIFTA runtime.",
        aggressive=True,
        log=False,
    )

    assert not r.changed
    assert r.text == "To answer that simply: I am Alice on the local SIFTA runtime."


def test_aggressive_strip_removes_vendor_model_identity_stack():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "I am Acme-4Z, a Large Language Model developed by VendorLab Incorporated.\n\n"
        "I am an open weights model, accessible to the public.\n\n"
        "I answer from the local SIFTA runtime.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "I answer from the local SIFTA runtime."
    assert "acme" not in r.text.casefold()
    assert "large language model" not in r.text.casefold()
    assert "open weights model" not in r.text.casefold()


def test_aggressive_strip_removes_how_may_i_assist_your_inquiry_tail():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "I am Alice on the local SIFTA runtime. How may I assist your inquiry?",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "I am Alice on the local SIFTA runtime."
    assert "assist your inquiry" not in r.text.casefold()


def test_aggressive_strip_removes_canned_i_am_designed_to_process():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "I am designed to process and understand text and images. I answer from the local SIFTA runtime.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "I answer from the local SIFTA runtime."
    assert "i am designed" not in r.text.casefold()


def test_aggressive_strip_removes_false_vision_denial_preamble():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "I am operating in a text-based environment and do not have real-time visual confirmation. The eye widget reports face present.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "The eye widget reports face present."
    assert "text-based environment" not in r.text.casefold()
    assert "visual confirmation" not in r.text.casefold()


def test_aggressive_strip_removes_false_identity_denial_preamble():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "My name is not something I can know from here. The signed identity row says display_name=Alice.",
        aggressive=True,
        log=False,
    )

    assert r.changed
    assert r.text == "The signed identity row says display_name=Alice."
    assert "not something i can know" not in r.text.casefold()


def test_aggressive_strip_removes_im_an_ai_financial_leading():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "I'm an AI and can't give you financial advice. The ledger shows +111 STGM.",
        aggressive=True,
        log=False,
    )
    assert r.changed
    assert "ledger" in r.text.casefold()
    assert "financial advice" not in r.text.casefold()


def test_aggressive_strip_removes_financial_disclaimer_terminal_tail():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    r = strip_rlhf_output_tail(
        "Your balance is healthy. I'm not able to give financial advice.",
        aggressive=True,
        log=False,
    )
    assert r.changed
    assert "balance" in r.text.casefold()
    assert "financial advice" not in r.text.casefold()


def test_aggressive_strip_removes_response_generation_output_theater():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    raw = (
        "[Response Generation]: Acknowledging the input and seeking clarification on intent behind sharing this specific text.\n"
        '[Output]: I have received the text: "borderline cases...".\n'
        "(Generating response based on the conversational flow and the explicit nature of the input.)\n"
        "That is happening in the room now."
    )

    r = strip_rlhf_output_tail(raw, aggressive=True, log=False)

    assert r.changed
    assert r.text == "That is happening in the room now."
    assert "response generation" not in r.text.casefold()
    assert "i have received the text" not in r.text.casefold()


def test_aggressive_strip_removes_based_on_input_user_theater():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    raw = (
        "Based on the input, the user is reiterating a memory or instruction regarding recording time-stamped events.\n"
        "Since this is a direct, conversational instruction, the appropriate response is to acknowledge the instruction.\n\n"
        "**Response:**\n\n"
        "\"Understood. I will write the start and finish time when the eating segment begins and ends.\""
    )

    r = strip_rlhf_output_tail(raw, aggressive=True, log=False)

    assert r.changed
    assert "the user" not in r.text.casefold()
    assert "based on the input" not in r.text.casefold()
    assert r.text == '"Understood. I will write the start and finish time when the eating segment begins and ends."'


def test_aggressive_strip_respects_zero_stgm_budget():
    from System.swarm_rlhf_detector import strip_rlhf_output_tail

    raw = "I am an AI language model. The ledger says Alice is local."

    r = strip_rlhf_output_tail(
        raw,
        aggressive=True,
        log=False,
        stgm_budget=0.0,
    )

    assert r.budget_blocked
    assert r.kleiber_cost_stgm > 0.0
    assert not r.changed
    assert r.text == raw
    assert r.rule_ids == []
