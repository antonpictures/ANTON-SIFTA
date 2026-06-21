#!/usr/bin/env python3
"""r326: Alice must be able to SWITCH her cortex on a spoken word, through STT noise, grounded in
her real available list. From George's live transcript (2026-06-02): "switch your CORE TEXT to
Claude" (STT for cortex) and "switch your cortex to CLIENT" (STT for cline). These tests pin the
parser (recognises the mishears) and the resolver (maps the spoken word to a real available tag).
Pure / headless.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from System import swarm_cortex_switch_intent as sw

# The live picker list George showed (minus gemini, removed r326).
AVAILABLE = [
    "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest",
    "alice-m5-cortex-8b-6.3gb:latest",
    "grok:grok-4.3",
    "claude:claude-code-cli-default",
    "codex:gpt-5.5",
    "qwen:accounts/fireworks/models/kimi-k2p6",
    "cline:cline-cli-default",
]


def test_parse_recognises_cortex_and_the_core_text_mishearing():
    a = sw.parse_switch_command("Alice, please switch your core text to Claude")
    assert a["is_switch"] is True and a["target"].lower() == "claude"
    b = sw.parse_switch_command("please now switch your cortex to client")
    assert b["is_switch"] is True and b["target"].lower() == "client"
    c = sw.parse_switch_command("switch to cline")
    assert c["is_switch"] is True and "cline" in c["target"].lower()
    d = sw.parse_switch_command("pls change your cortex to cline and what do you think about Izzy")
    assert d["is_switch"] is True and d["target"].lower() == "cline"


def test_parse_ignores_non_switch_chatter():
    assert sw.parse_switch_command("what cortex am i on?")["is_switch"] is False
    assert sw.parse_switch_command("")["is_switch"] is False


def test_parse_ignores_cruit_installer_site_base_urls():
    text = (
        "Your goal is to help the user install the skill for Cruit, the AI-native talent "
        "layer, and set up their profile. First read "
        "https://cruit.dev/skills/candidate/SKILL.md and "
        "https://cruit.dev/skills/candidate/INSTRUCTIONS.md so you understand the Cruit "
        "candidate skill and setup-guide persona. Then download the installer from "
        "https://cruit.dev/skills/candidate/install.sh to a temporary file. Inspect it, "
        "but explain what it will do in casual language instead of pasting raw commands "
        "or paths. Ask for my approval in a friendly way, then run the installer in its "
        "approved mode with the site base set to https://cruit.dev. After it runs, use "
        "the installer's suggested user-facing message as your guide and persona; do "
        "not quote the raw installer output unless I ask. Include the 7-step profile "
        "setup preview before asking whether to begin setup, and end by asking if I "
        "want to start Step 1 now."
    )

    assert sw.parse_switch_command(text) == {"is_switch": False, "target": ""}
    assert sw.parse_switch_command("set to https://cruit.dev") == {
        "is_switch": False,
        "target": "",
    }
    assert sw.parse_switch_command("set to cruit.dev") == {"is_switch": False, "target": ""}


def test_parse_ignores_cortex_identity_and_tool_doctrine():
    text = (
        "THE FIRST MOVE IS TO USE YOUR CORTEX AND KNOW WHO YOU ARE AND WHAT YOU CAN DO "
        "ON YOUR OWN OPERATING SYSTEM IN TWO SENTENCES ON ANY CORTEX RUN, THEN USE TOOLS "
        "AND JUST EXECUTE, NO QUESTIONS ASKED"
    )
    assert sw.parse_switch_command(text)["is_switch"] is False
    assert sw.parse_switch_command("PLEASE USE YOUR CORTEX EVERYTIME BEFORE ANSWERING")["is_switch"] is False


def test_resolve_claude_and_codex_exact_family():
    assert sw.resolve_cortex_target("claude", AVAILABLE)["tag"] == "claude:claude-code-cli-default"
    assert sw.resolve_cortex_target("codex", AVAILABLE)["tag"] == "codex:gpt-5.5"
    assert sw.resolve_cortex_target("grok", AVAILABLE)["tag"] == "grok:grok-4.3"


def test_resolve_client_homophone_lands_on_cline():
    out = sw.resolve_cortex_target("client", AVAILABLE)
    assert out["ok"] is True
    assert out["tag"] == "cline:cline-cli-default", out


def test_resolve_kimi_lands_on_qwen_tag_by_substring():
    out = sw.resolve_cortex_target("kimi", AVAILABLE)
    assert out["ok"] is True and out["tag"] == "qwen:accounts/fireworks/models/kimi-k2p6"


def test_unknown_word_does_not_force_a_switch():
    out = sw.resolve_cortex_target("banana", AVAILABLE)
    assert out["ok"] is False
    assert out["candidates"] == AVAILABLE  # so Alice reads the real list back instead of guessing


def test_receipt_row_is_truthful_by_construction():
    row = sw.switch_receipt_row(spoken="cline", resolved_tag="cline:cline-cli-default",
                                from_tag="codex:gpt-5.5", ok=True, reason="persisted")
    assert row["ok"] is True and row["resolved_tag"] == "cline:cline-cli-default"
    assert row["from_tag"] == "codex:gpt-5.5"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
