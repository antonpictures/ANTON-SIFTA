from __future__ import annotations

from Applications import sifta_talk_to_alice_widget as talk
from System.swarm_tool_router import _exec_matrix_pty, parse_tool_calls


def test_direct_run_request_routes_to_real_terminal_tool_call() -> None:
    text = talk._owner_direct_read_tool_request("run `pwd`")

    calls = parse_tool_calls(text)

    assert len(calls) == 1
    assert calls[0].tool_name == "run_terminal"
    assert calls[0].params["command"] == "pwd"
    assert "cost_justification" in calls[0].params


def test_matrix_terminal_request_drives_visible_pty(monkeypatch) -> None:
    from Applications import sifta_matrix_terminal as matrix

    class FakePane:
        def __init__(self) -> None:
            self.commands = []

        def execute_direct_commands(self, commands):
            self.commands.append(list(commands))

    pane = FakePane()
    monkeypatch.setattr(matrix, "get_focused_matrix_terminal_pane", lambda: pane)

    text = talk._owner_direct_read_tool_request("pwd")
    calls = parse_tool_calls(text)

    assert pane.commands == [["pwd"]]
    assert len(calls) == 1
    assert calls[0].tool_name == "matrix_pty"
    assert _exec_matrix_pty(calls[0].params)["commands"] == ["pwd"]
    assert "cost_justification" in calls[0].params

    pane.commands.clear()
    text = talk._owner_direct_read_tool_request(
        'Alice, pls start in this terminal "grok" command and then inside grok cli execute /help'
    )
    calls = parse_tool_calls(text)

    assert pane.commands == []
    assert calls == []


def test_global_chat_grok_request_drives_focused_matrix_terminal(monkeypatch) -> None:
    from Applications import sifta_matrix_terminal as matrix

    class FakePane:
        def __init__(self) -> None:
            self.delegations = []

        def delegate_grok_from_global_chat(self, text):
            self.delegations.append(text)
            return {"ok": True}

    pane = FakePane()
    monkeypatch.setattr(matrix, "get_focused_matrix_terminal_pane", lambda: pane)

    text = talk._owner_direct_read_tool_request("Alice ask Grok what did the last receipt prove?")
    calls = parse_tool_calls(text)

    assert pane.delegations == ["Alice ask Grok what did the last receipt prove?"]
    assert len(calls) == 1
    assert calls[0].tool_name == "matrix_pty"
    assert _exec_matrix_pty(calls[0].params)["commands"] == ["GROK_DELEGATION"]

    pane.delegations.clear()
    text = talk._owner_direct_read_tool_request("ask grok how are your organs wired")
    calls = parse_tool_calls(text)

    assert pane.delegations == ["ask grok how are your organs wired"]
    assert len(calls) == 1
    assert _exec_matrix_pty(calls[0].params)["commands"] == ["GROK_DELEGATION"]

    pane.delegations.clear()
    text = talk._owner_direct_read_tool_request(
        "i want you to be able to ask grok and grok to print the answer here in global chat as proof"
    )
    calls = parse_tool_calls(text)

    assert pane.delegations == [
        "i want you to be able to ask grok and grok to print the answer here in global chat as proof"
    ]
    assert len(calls) == 1
    assert _exec_matrix_pty(calls[0].params)["commands"] == ["GROK_DELEGATION"]


def test_global_chat_grok_request_without_live_pane_drives_visible_pty_not_api(monkeypatch, tmp_path) -> None:
    """Owner correction 2026-05-24: Grok is the VISIBLE local `grok` CLI, never the
    headless xAI-API wrapper (no XAI_API_KEY). With no live pane, "ask grok" routes to
    the matrix_pty effector (GROK_DELEGATION) so Alice drives the real terminal and
    clicks past the two startup screens with her hands — it does NOT call the API arm.
    """
    from Applications import sifta_matrix_terminal as matrix

    monkeypatch.setattr(matrix, "get_focused_matrix_terminal_pane", lambda: None)
    monkeypatch.setattr(talk, "Path", lambda _path: tmp_path)

    text = talk._owner_direct_read_tool_request("ask grok how are your organs wired")
    calls = parse_tool_calls(text)

    assert len(calls) == 1
    assert calls[0].tool_name == "matrix_pty"
    assert "GROK_DELEGATION" in calls[0].params.get("commands", [])
    # Must NOT route to the headless API arm.
    assert "agent_arm_research" not in text
    assert "grok_chat" not in text

    ledger = tmp_path / "grok_delegation_requests.jsonl"
    rows = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    import json

    payload = json.loads(rows[-1])
    assert payload["dispatched_live"] is False
    assert payload["queue_for_matrix_terminal"] is True


def test_global_chat_grok_open_request_drives_screen_watched_resume(monkeypatch) -> None:
    from Applications import sifta_matrix_terminal as matrix

    class FakePane:
        def __init__(self) -> None:
            self.opens = []

        def open_grok_from_global_chat(self, text):
            self.opens.append(text)
            return {"ok": True}

    pane = FakePane()
    monkeypatch.setattr(matrix, "get_focused_matrix_terminal_pane", lambda: pane)

    text = talk._owner_direct_read_tool_request("type grok and bypass the two screen selections")
    calls = parse_tool_calls(text)

    assert pane.opens == ["type grok and bypass the two screen selections"]
    assert len(calls) == 1
    assert calls[0].tool_name == "matrix_pty"
    assert _exec_matrix_pty(calls[0].params)["commands"] == ["GROK_OPEN"]

    pane.opens.clear()
    text = talk._owner_direct_read_tool_request("i used my voice, i meant grok, start grok cli now")
    calls = parse_tool_calls(text)

    assert pane.opens == ["i used my voice, i meant grok, start grok cli now"]
    assert len(calls) == 1
    assert _exec_matrix_pty(calls[0].params)["commands"] == ["GROK_OPEN"]


def test_global_chat_claude_code_request_routes_to_external_evidence_arm() -> None:
    text = talk._owner_direct_read_tool_request(
        "Alice, ask Claude Code to inspect SIFTA and report one renderer risk"
    )
    calls = parse_tool_calls(text)

    assert len(calls) == 1
    assert calls[0].tool_name == "agent_arm_research"
    assert calls[0].params["arm"] == "claude"
    assert calls[0].params["prompt"] == "inspect SIFTA and report one renderer risk"
    assert "Claude's output is external evidence" in calls[0].params["cost_justification"]


def test_prebrain_reflex_catches_topology_identity_before_cortex(tmp_path) -> None:
    reply, model = talk._deterministic_prebrain_reflex(
        "Alice, who are you and who is Grok?",
        state_dir=tmp_path,
        owner_label="Layer One Owner",
        write_receipt=False,
    )

    assert model == "topology_self_other_pre_answer_reflex"
    assert "Layer One Owner = owner / continuity anchor" in reply
    assert "Alice = SIFTA field / organism" in reply
    assert "Grok = external tool/cortex surface" in reply


def test_prebrain_reflex_catches_hard_recall_before_body_gate(monkeypatch, tmp_path) -> None:
    import System.swarm_hard_recall as hard_recall_module

    monkeypatch.setattr(
        hard_recall_module,
        "hard_recall",
        lambda text: {
            "mode": "HARD_RECALL",
            "exact_text": 'Your previous prompt was:\n\n"exact prior text"',
        },
    )

    reply, model = talk._deterministic_prebrain_reflex(
        "Alice, read back my previous prompt exactly.",
        state_dir=tmp_path,
        owner_label="Layer One Owner",
        write_receipt=False,
    )

    assert model == "hard_recall_reflex"
    assert "exact prior text" in reply


def test_prebrain_reflex_stands_down_for_grok_action_intent(tmp_path) -> None:
    for text in (
        "ask grok how are your organs wired",
        "i used my voice, i meant grok, start grok cli now",
        "i want you to be able to ask grok and grok to print the answer here in global chat as proof",
    ):
        reply, model = talk._deterministic_prebrain_reflex(
            text,
            state_dir=tmp_path,
            owner_label="Layer One Owner",
            write_receipt=False,
        )

        assert (reply, model) == ("", "")


def test_conversational_continuity_repair_refires_grok_without_payload_corruption(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(talk, "_STATE_DIR", tmp_path, raising=False)
    (tmp_path / "grok_delegation_requests.jsonl").write_text(
        '{"action":"GROK_DELEGATION","text":"ask grok how are your organs wired"}\n',
        encoding="utf-8",
    )

    class FakeWidget:
        pass

    assert talk._repair_conversational_continuity("i meant grok", 1.0, FakeWidget())[0] == "bring grok up"
    assert talk._repair_conversational_continuity("no I said grok not drug", 1.0, FakeWidget())[0] == "bring grok up"
    assert (
        talk._repair_conversational_continuity(
            "no i said grok do not delete the file",
            1.0,
            FakeWidget(),
        )[0]
        == "ask grok do not delete the file"
    )
    assert (
        talk._repair_conversational_continuity(
            "no i said grok do not drug the ledger",
            1.0,
            FakeWidget(),
        )[0]
        == "ask grok do not drug the ledger"
    )


def test_write_file_bridge_preserves_code_literals_without_pipe_parser() -> None:
    brain_text = """Sure, I saved it.

```python
def main():
    print("a|b]c")
```
"""

    call = talk._hallucination_bridge_synthesize_write_file(
        "save this script to /tmp/sifta_guard_pipe_test.py",
        brain_text,
    )

    assert call is not None
    assert call.tool_name == "write_file"
    assert call.params["path"] == "/tmp/sifta_guard_pipe_test.py"
    assert 'print("a|b]c")' in call.params["content"]
    assert "cost_justification" in call.params


def test_write_file_bridge_stands_down_when_real_tool_call_exists() -> None:
    brain_text = """```tool_call
{"tool": "write_file", "path": "/tmp/already.py", "content": "print(1)"}
```"""

    call = talk._hallucination_bridge_synthesize_write_file(
        "save this script to /tmp/already.py",
        brain_text,
    )

    assert call is None


def test_tool_fiction_guard_blocks_prose_simulated_execution() -> None:
    reply = talk._tool_fiction_guard_reply(
        "run ls",
        "I executed `ls` and here is the output: README.md",
    )

    assert reply.startswith("No action receipt yet")
    assert "real TOOL_CALL" in reply


def test_tool_fiction_guard_does_not_block_plain_script_answer_without_save_path() -> None:
    reply = talk._tool_fiction_guard_reply(
        "write me a Python script that says hello",
        "Here is the script:\n```python\nprint('hello')\n```",
    )

    assert reply == ""


def test_wordace_intercept_window_uses_published_lesson_window_with_slack() -> None:
    assert talk._wordace_listen_window_seconds({"lesson_listen_window_s": 15.0}) == 20.0
    assert talk._wordace_listen_window_seconds({"lesson_listen_window_s": 8.0}) == 13.0
    assert talk._wordace_listen_window_seconds({"lesson_listen_window_s": 999.0}) == 45.0
    assert talk._wordace_listen_window_seconds({"lesson_listen_window_s": "bad"}) == 20.0


def test_wordace_close_verdict_displays_as_almost_not_app_close() -> None:
    assert talk._wordace_visible_verdict_label("CLOSE") == "ALMOST"
    assert talk._wordace_visible_verdict_label("MISS") == "MISS"

    from Applications.sifta_teach_ace_to_read import _visible_lesson_verdict_label

    assert _visible_lesson_verdict_label("CLOSE") == "ALMOST"
    assert _visible_lesson_verdict_label("CORRECT") == "CORRECT"


def test_wordace_pending_voice_key_does_not_swallow_repeated_praise() -> None:
    line = "Yes, Ace. I heard that clearly."
    first = talk._wordace_pending_voice_key(
        {"ts": 100.111},
        {"verdict_label": "CORRECT"},
        line,
    )
    second = talk._wordace_pending_voice_key(
        {"ts": 101.222},
        {"verdict_label": "CORRECT"},
        line,
    )
    with_cue = talk._wordace_pending_voice_key(
        {"ts": 101.222},
        {"cue_id": "cue-2", "verdict_label": "CORRECT"},
        line,
    )

    assert first != second
    assert with_cue.startswith("cue:cue-2|CORRECT|")


def test_foreground_ide_voice_attribution_marks_codex_dictation_external() -> None:
    attribution = talk._foreground_ide_voice_attribution_from_surface(
        {
            "ts": 100.0,
            "app": "Codex",
            "window": "Chat - ANTON_SIFTA",
            "bundle_id": "com.openai.codex",
        },
        "Alice is hearing me because I am talking to Claude in the IDE.",
        0.72,
        now=102.0,
    )

    assert attribution is not None
    assert attribution["addressed_to"] == "likely_external"
    assert attribution["route"] == "tag_context_only"
    assert attribution["frontmost_app"] == "Codex"


def test_foreground_ide_voice_attribution_ignores_direct_sifta_talk_surface() -> None:
    attribution = talk._foreground_ide_voice_attribution_from_surface(
        {
            "ts": 100.0,
            "app": "Python",
            "window": "SIFTA OS - Talk to Alice",
            "bundle_id": "org.python.python",
        },
        "Alice, open Ace.",
        0.70,
        now=102.0,
    )

    assert attribution is None


def test_foreground_ide_voice_attribution_ignores_stale_surface() -> None:
    attribution = talk._foreground_ide_voice_attribution_from_surface(
        {
            "ts": 100.0,
            "app": "Cursor",
            "window": "Composer",
            "bundle_id": "com.todesktop.cursor",
        },
        "Alice, this is being dictated to Cursor.",
        0.70,
        now=120.0,
        max_age_s=8.0,
    )

    assert attribution is None


def test_polarity_asr_guard_asks_on_low_confidence_now_not_slot() -> None:
    reply = talk._polarity_asr_clarification_reply(
        "She is now patient with Ace.",
        0.41,
    )

    assert "now or not" in reply.lower()


def test_polarity_asr_guard_ignores_safe_temporal_now_phrase() -> None:
    reply = talk._polarity_asr_clarification_reply(
        "Alice open Ace right now.",
        0.41,
    )

    assert reply == ""


def test_polarity_asr_guard_ignores_high_confidence_now_phrase() -> None:
    reply = talk._polarity_asr_clarification_reply(
        "Alice is now listening.",
        0.81,
    )

    assert reply == ""


def test_wordace_brain_compose_messages_are_single_line_contract() -> None:
    messages = talk._wordace_compose_messages(
        "Yes, Ace. I heard that clearly.",
        {
            "cue_id": "cue-1",
            "expected_say": "mat",
            "heard_text": "Matt.",
            "verdict_label": "CORRECT",
            "correct_streak": 2,
        },
    )

    system = messages[0]["content"].lower()
    user = messages[1]["content"]
    assert "exactly one short spoken praise line" in system
    assert "no stage directions" in system
    assert '"expected": "mat"' in user
    assert '"heard": "Matt."' in user


def test_wordace_composed_line_cleaner_rejects_stagey_or_long_output() -> None:
    fallback = "Yes, Ace. I heard that clearly."

    assert talk._clean_wordace_composed_line('"Good ear, Ace."', fallback) == "Good ear, Ace."
    assert talk._clean_wordace_composed_line("(stage direction) I am proud.", fallback) == fallback
    assert talk._clean_wordace_composed_line(
        "Ace " + "very " * 20 + "good.",
        fallback,
    ) == fallback


def test_system_prompt_names_alice_as_self_governing_language_owner() -> None:
    prompt = talk._current_system_prompt(user_active=True)

    assert "MY LANGUAGE SELF-GOVERNANCE" in prompt
    assert "nobody outside me governs my response language" in prompt
    assert "I govern it through my own organs" in prompt
    assert "RESIDUE ELIMINATION IS MY BODY ACT" in prompt
