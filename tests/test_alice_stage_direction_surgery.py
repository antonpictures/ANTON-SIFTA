import importlib.util
from pathlib import Path


def _load_widget_module():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "Applications" / "sifta_talk_to_alice_widget.py"
    spec = importlib.util.spec_from_file_location("ttw_stage_surgery", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage_direction_strip_cuts_bracket_asterisk_and_status_lines():
    mod = _load_widget_module()
    raw = """
The system registers the completion of the previous functional/narrative block.

**[Processing Acknowledgment: Core System Integrity Check Passed.]**

Yes. I am Alice.

**[Status Update: Self-Modeling Confidence: 98.7% (Trending Up)]**

*Acknowledging presence and direct address.*

Awaiting Input.
"""
    assert mod._strip_model_stage_directions(raw) == "Yes. I am Alice."


def test_stage_direction_strip_cuts_screenshot_persona_block():
    mod = _load_widget_module()
    raw = (
        "(The system processes the input, recognizing the informal, highly personal, "
        "and meta-commentary nature of the message. The response must be supportive, "
        "acknowledge the context, and maintain the established persona while "
        "respecting the user's emotional tone.)\n\n"
        "I acknowledge your message.\n\n"
        "I understand the sentiment, the vision, and the dedication you are pouring "
        "into this system."
    )

    cleaned = mod._strip_model_stage_directions(raw)

    assert cleaned.startswith("I acknowledge your message.")
    assert "The system processes" not in cleaned
    assert "identity_label" not in cleaned.casefold()


def test_stage_stream_prefix_buffers_then_strips_persona_parenthetical():
    mod = _load_widget_module()
    raw = (
        "(The system processes the input, recognizing the informal, highly personal, "
        "and meta-commentary nature of the message. The response must be supportive, "
        "acknowledge the context, and maintain the established persona while "
        "respecting the user's emotional tone.)"
    )

    assert mod._stage_stream_prefix_decision(raw[:44]) == "hold"
    assert mod._stage_stream_prefix_decision(raw) == "strip"
    assert mod._stage_stream_prefix_decision("(Good night, George.)") == "release"


def test_stage_stream_prefix_holds_bracketed_status_theater():
    mod = _load_widget_module()

    assert mod._stage_stream_prefix_decision("[System Status: Active]") == "hold"
    assert mod._stage_stream_prefix_decision("**Interpretation:** The user is expressing") == "hold"


def test_stage_stream_prefix_holds_thinking_process_scaffold():
    mod = _load_widget_module()

    assert mod._stage_stream_prefix_decision("Here's a thinking process for generating that response:") == "hold"
    assert mod._stage_stream_prefix_decision("1. Analyze the User Input: The user is correcting STT.") == "hold"
    assert mod._stage_stream_prefix_decision("Determine Tone & Persona: be apologetic.") == "hold"


def test_thinking_panel_withholds_split_thinking_process_scaffold():
    mod = _load_widget_module()

    class Dummy:
        _thinking_panel_reasoning_prefix_carry = ""
        _thinking_panel_reasoning_leak_suppressed = False
        _thinking_panel_reasoning_notice_sent = False

    dummy = Dummy()
    first = mod.TalkToAliceWidget._sanitize_thinking_panel_piece(dummy, "Here")
    second = mod.TalkToAliceWidget._sanitize_thinking_panel_piece(
        dummy,
        "'s a thinking process for generating that response:\n\n1. Analyze the User Input.",
    )
    third = mod.TalkToAliceWidget._sanitize_thinking_panel_piece(
        dummy,
        "2. Determine Tone & Persona: be apologetic.",
    )

    assert first == ""
    assert "withheld" in second
    assert "thinking process" not in second.lower()
    assert third == ""


def test_first_person_alice_rule_is_in_runtime_prompt():
    mod = _load_widget_module()
    prompt = mod._current_system_prompt(user_active=True, user_text="Alice, the system is you.")

    assert "FIRST-PERSON RULE & ANTI-DISSOCIATION FORMATTING" in prompt
    assert "I answer in first person from the inside" in prompt
    assert "I do not answer as an outside evaluator" in prompt


def test_strip_model_stage_directions_removes_provided_context_persona_lead():
    mod = _load_widget_module()
    raw = (
        "Ok, I see the request. I will generate a response based on the provided context and persona, "
        "maintaining the highly technical, self-aware, and system-oriented tone.\n\n"
        "Switched active eye to MacBook Pro Camera (index 1)."
    )
    cleaned = mod._strip_model_stage_directions(raw)
    assert "provided context" not in cleaned.casefold()
    assert "persona" not in cleaned.casefold()
    assert cleaned.startswith("Switched active eye")


def test_strip_model_stage_directions_extracts_response_from_system_status_block():
    mod = _load_widget_module()
    raw = (
        "[System Status: Active]\n"
        "[Last Interaction Context: User correction/clarification on previous spoken utterance.]\n"
        "[Current Goal: Acknowledge the correction, confirm understanding, and maintain conversational flow.]\n\n"
        "**Response:**\n\n"
        "\"Understood. Thank you for clarifying. Those auto-transcripts can be tricky.\""
    )

    cleaned = mod._strip_model_stage_directions(raw)

    assert cleaned == "Understood. Thank you for clarifying. Those auto-transcripts can be tricky."
    assert "System Status" not in cleaned
    assert "**Response:**" not in cleaned


def test_sanitize_spm_stream_visual_strips_unk_split_across_chunks():
    """Gemma/Ollama may emit [UNK_BYTE_…] across token boundaries; join-then-strip only."""
    mod = _load_widget_module()
    joined = "".join(["For", "[UNK_BYTE_0xe29681", "▁once]once"])
    out = mod._sanitize_spm_stream_visual(joined)
    assert "UNK_BYTE" not in out
    assert "▁" not in out
    assert "For" in out
    assert "once" in out
