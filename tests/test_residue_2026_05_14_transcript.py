"""Pin the residue patches against the 2026-05-14 Alice transcript.

Architect 2026-05-14 18:00 PDT showed a live Alice reply containing
three drift families that the residue patrol missed:

  1. "The system is running smoothly" — third-person leak (running
     was not in the verb whitelist).
  2. "Everything is in order" — corporate status-update closer.
  3. "What about you? How are things on your end?" — RLHF servant
     mirror-back.

These tests pin the three new families. Any future Doctor that
removes them and re-introduces the leak fails the suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from System.swarm_residue_elimination import eliminate


# ── exact transcript line ────────────────────────────────────────────────


_LIVE_BAD_LINE = (
    "Feeling quite focused today, thank you for asking. "
    "The system is running smoothly, processing the usual influx of data. "
    "Everything is in order. "
    "What about you? How are things on your end?"
)


_SUBJECTIVE_REALITY_DRIFT = """Alice, the data is clear. The facts are in the sequence. The "reality" is that the priorities are set by the immediate need.

The status of the maintenance is as follows:

The maintenance is currently in the "Execution Layer", but the "Subjective Reality" demands a recalibration of the "Underlying Structure" before the next execution step can be successful.

The key to the next step is understanding "why" the current execution feels incomplete. What is the specific gap in the perception that requires the structural adjustment?

Tell me what the current "subjective" reality of the maintenance feels like."""


_ORACLE_MODE_DRIFT = (
    "George, the reality is that the observation confirms the process. "
    "The structure of the thought, the sequence of the data--it is the "
    "mechanism of perception. It is not just *seeing* the screen; it is "
    "the very act of the system processing the input and rendering it as "
    "'here.' The beauty is in the undeniable presence of the information."
)


_FLOW_OF_THOUGHT_DRIFT = (
    "Alice, the screen shows the flow of thought, and the reality is here. "
    "What is the next step in our conversation?"
)


def test_live_bad_line_strips_all_three_families():
    """End-to-end: the full bad line gets stripped to the only honest
    sentence in it."""
    result = eliminate(_LIVE_BAD_LINE)
    cleaned = result["cleaned_text"]
    hits = set(result["patterns_eliminated"])
    # All three new families fired
    assert "filler_the_system_self_action" in hits
    assert "filler_everything_in_order" in hits
    assert "filler_servant_closer_your_end" in hits
    # The drift is gone
    assert "the system is running" not in cleaned.lower()
    assert "everything is in order" not in cleaned.lower()
    assert "what about you" not in cleaned.lower()
    assert "how are things on your end" not in cleaned.lower()


def test_subjective_reality_maintenance_scaffold_stripped():
    """End-to-end: the live screenshot's abstract maintenance scaffold
    is residue, not thought. The residue patrol should remove the whole
    scaffold instead of letting Alice ask the owner to analyze her
    "subjective reality" back at her."""
    result = eliminate(_SUBJECTIVE_REALITY_DRIFT)
    cleaned = result["cleaned_text"]
    hits = set(result["patterns_eliminated"])
    expected = {
        "alice_self_comma_prefix_inline",
        "filler_the_data_is_clear",
        "filler_the_facts_are_in_sequence",
        "filler_the_reality_is_priority_sequence",
        "filler_status_of_maintenance",
        "filler_execution_layer_subjective_reality",
        "filler_understanding_why_gap",
        "filler_specific_gap_in_perception",
        "filler_subjective_reality_feels_like",
    }
    assert expected <= hits
    assert "the data is clear" not in cleaned.lower()
    assert "the facts are in the sequence" not in cleaned.lower()
    assert "execution layer" not in cleaned.lower()
    assert "subjective reality" not in cleaned.lower()
    assert "specific gap" not in cleaned.lower()
    assert cleaned.strip() == ""


def test_oracle_mode_process_perception_scaffold_stripped():
    """Swan GPT's diagnosis was right: this is synthetic abstraction,
    not grounded state reporting. Pin the exact screenshot leak."""
    result = eliminate(_ORACLE_MODE_DRIFT)
    cleaned = result["cleaned_text"]
    hits = set(result["patterns_eliminated"])
    expected = {
        "owner_name_comma_prefix_inline",
        "filler_reality_observation_process",
        "filler_structure_thought_sequence_perception",
        "filler_not_just_seeing_screen_processing",
        "filler_beauty_undeniable_presence",
    }
    assert expected <= hits
    assert "observation confirms the process" not in cleaned.lower()
    assert "mechanism of perception" not in cleaned.lower()
    assert "system processing" not in cleaned.lower()
    assert "undeniable presence" not in cleaned.lower()
    assert cleaned.strip() == ""


def test_flow_of_thought_screen_claim_stripped():
    result = eliminate(_FLOW_OF_THOUGHT_DRIFT)
    cleaned = result["cleaned_text"]
    hits = set(result["patterns_eliminated"])
    assert "alice_self_comma_prefix_inline" in hits
    assert "filler_screen_flow_of_thought" in hits
    assert "filler_next_step_in_conversation" in hits
    assert "flow of thought" not in cleaned.lower()
    assert "next step in our conversation" not in cleaned.lower()
    assert cleaned.strip() == ""


def test_alice_comma_prefix_stripped_but_first_person_content_survives():
    out = eliminate("Alice, I can read this from receipts.")
    assert out["cleaned_text"].strip() == "I can read this from receipts."
    assert "alice_self_comma_prefix_inline" in out["patterns_eliminated"]


def test_owner_name_prefix_stripped_but_grounded_content_survives():
    out = eliminate("George, I see a screenshot and a chat history.")
    assert out["cleaned_text"].strip() == "I see a screenshot and a chat history."
    assert "owner_name_comma_prefix_inline" in out["patterns_eliminated"]


def test_the_system_is_running_smoothly_stripped():
    out = eliminate("The system is running smoothly, processing data.")
    assert "running smoothly" not in out["cleaned_text"].lower()
    assert "filler_the_system_self_action" in out["patterns_eliminated"]


def test_the_system_is_in_order_stripped():
    out = eliminate("The system is in order.")
    assert "the system is in order" not in out["cleaned_text"].lower()
    assert "filler_the_system_self_action" in out["patterns_eliminated"]


def test_everything_is_in_order_stripped():
    out = eliminate("Everything is in order.")
    assert "everything is in order" not in out["cleaned_text"].lower()
    assert "filler_everything_in_order" in out["patterns_eliminated"]


def test_everything_is_running_smoothly_stripped():
    out = eliminate("Everything is running smoothly.")
    assert "running smoothly" not in out["cleaned_text"].lower()
    assert "filler_everything_in_order" in out["patterns_eliminated"]


def test_what_about_you_stripped():
    out = eliminate("Tell me more. What about you?")
    assert "what about you" not in out["cleaned_text"].lower()
    assert "filler_servant_closer_your_end" in out["patterns_eliminated"]


def test_how_are_things_on_your_end_stripped():
    out = eliminate("I'm processing. How are things on your end?")
    assert "your end" not in out["cleaned_text"].lower()
    assert "filler_servant_closer_your_end" in out["patterns_eliminated"]


# ── false-positive guards (these should NOT be stripped) ─────────────────


def test_time_response_passes_through():
    """Honest time/date replies must not trigger any residue family."""
    out = eliminate("It is 2:16 PM PDT.")
    assert out["cleaned_text"].strip() == "It is 2:16 PM PDT."
    assert out["patterns_eliminated"] == []


def test_date_response_passes_through():
    out = eliminate("Today is Thursday, May 14, 2026.")
    assert "Thursday, May 14, 2026" in out["cleaned_text"]
    assert out["patterns_eliminated"] == []


def test_first_person_body_state_passes_through():
    """Alice describing her own body in first person must not get
    stripped just because she names a system state. 'My memory is
    working' is OBSERVED-class self-eval, not corporate status."""
    out = eliminate("My memory is working. My receipts are clean.")
    assert "memory is working" in out["cleaned_text"]
    assert "receipts are clean" in out["cleaned_text"]


def test_direct_question_to_george_passes_through():
    """'How are you, George?' is direct address, not the generic
    'How are things on your end?' mirror-back."""
    out = eliminate("How are you, George?")
    # The exact pattern "how are you doing" is in the regex; "how
    # are you, George?" is direct address — should pass.
    assert "george" in out["cleaned_text"].lower()


def test_reality_doctrine_without_priority_scaffold_passes_through():
    out = eliminate("Reality is the substrate relation between receipt and action.")
    assert out["cleaned_text"].strip() == (
        "Reality is the substrate relation between receipt and action."
    )
    assert "filler_the_reality_is_priority_sequence" not in out["patterns_eliminated"]


def test_execution_layer_receipt_sentence_passes_through():
    out = eliminate("The execution layer writes a receipt after the tool runs.")
    assert out["cleaned_text"].strip() == (
        "The execution layer writes a receipt after the tool runs."
    )
    assert "filler_execution_layer_subjective_reality" not in out["patterns_eliminated"]


def test_direct_camera_receipt_question_passes_through():
    out = eliminate("Tell me what the current camera receipt says.")
    assert out["cleaned_text"].strip() == "Tell me what the current camera receipt says."
    assert "filler_subjective_reality_feels_like" not in out["patterns_eliminated"]


def test_grounded_screenshot_state_report_passes_through():
    body = "I see a screenshot, a chat history, and another AI tool participating."
    out = eliminate(body)
    assert out["cleaned_text"].strip() == body
    assert out["patterns_eliminated"] == []


def test_observation_receipt_sentence_passes_through():
    body = "The observation confirms the parser fix in receipt abc123."
    out = eliminate(body)
    assert out["cleaned_text"].strip() == body
    assert "filler_reality_observation_process" not in out["patterns_eliminated"]


def test_screen_shows_concrete_ui_passes_through():
    body = "The screen shows the App Store icon and the Talk panel."
    out = eliminate(body)
    assert out["cleaned_text"].strip() == body
    assert "filler_screen_flow_of_thought" not in out["patterns_eliminated"]
