from __future__ import annotations

from Applications import sifta_talk_to_alice_widget as talk
from System.swarm_tool_router import parse_tool_calls


def test_direct_run_request_reaches_cortex_before_terminal_tool_call() -> None:
    text = talk._owner_direct_read_tool_request("run `pwd`")

    calls = parse_tool_calls(text)

    assert text == ""
    assert calls == []


def test_matrix_terminal_request_reaches_cortex_before_visible_pty(monkeypatch) -> None:
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

    assert pane.commands == []
    assert text == ""
    assert calls == []

    pane.commands.clear()
    text = talk._owner_direct_read_tool_request(
        'Alice, pls start in this terminal "grok" command and then inside grok cli execute /help'
    )
    calls = parse_tool_calls(text)

    assert pane.commands == []
    assert calls == []


def test_global_chat_grok_request_reaches_cortex_before_matrix_terminal(monkeypatch) -> None:
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

    assert pane.delegations == []
    assert text == ""
    assert calls == []

    pane.delegations.clear()
    text = talk._owner_direct_read_tool_request("ask grok how are your organs wired")
    calls = parse_tool_calls(text)

    assert pane.delegations == []
    assert text == ""
    assert calls == []

    pane.delegations.clear()
    text = talk._owner_direct_read_tool_request(
        "i want you to be able to ask grok and grok to print the answer here in global chat as proof"
    )
    calls = parse_tool_calls(text)

    assert pane.delegations == []
    assert text == ""
    assert calls == []


def test_grok_status_questions_reach_cortex_instead_of_canned_dispatch() -> None:
    for text in (
        "Alice, did you resume Grok?",
        "Alice, what was the last Grok receipt id?",
        "did Grok run and what receipt proved it?",
    ):
        reply = talk._owner_direct_read_tool_request(text)
        calls = parse_tool_calls(reply)

        assert reply == ""
        assert calls == []


def test_operational_greeter_guard_strips_structural_robot_dialogue() -> None:
    cleaned, fired = talk._strip_greeter_on_operational(
        "Hello again. You've addressed me. I am here. Are you looking to continue our conversation?",
        "Alice, did you resume Grok?",
    )

    assert fired
    assert cleaned == "FIELD_FAILURE: alice_greeter_punched_through_on_operational_turn"

    cleaned, fired = talk._strip_greeter_on_operational(
        "Hello. I am here, ready to receive your thoughts. Yes. I resumed Grok; receipt=abc123.",
        "what was the last Grok receipt id?",
    )

    assert fired
    assert cleaned == "Yes. I resumed Grok; receipt=abc123."


def test_hermes_common_stt_typo_reaches_cortex_before_agent_arm() -> None:
    text = talk._owner_direct_read_tool_request(
        "Alice, please ask Hemes to code a new Stigmergic TicTacToe in sifta apps"
    )
    calls = parse_tool_calls(text)

    assert text == ""
    assert calls == []


def test_use_your_arm_phrasing_reaches_cortex_before_read_file() -> None:
    cases = (
        (
            "codex",
            "Alice, use your codex arm and execute Round 35 now. Step 2: read "
            "/Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md.",
            "execute Round 35 now.",
        ),
        (
            "claude",
            "Alice, use your claude arm and code task #58. Step 2: read "
            "/Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md.",
            "code task #58.",
        ),
        (
            "hermes",
            "Alice, use your hermes arm and inspect receipts. Step 2: read "
            "/Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md.",
            "inspect receipts.",
        ),
    )

    for _arm, text, _prompt_head in cases:
        reply = talk._owner_direct_read_tool_request(text)
        calls = parse_tool_calls(reply)

        assert reply == ""
        assert calls == []
        assert "read_file" not in reply


def test_arm_meta_questions_do_not_auto_dispatch_external_arms() -> None:
    cases = (
        "do you know how to ask codex?",
        "how do i ask your codex arm",
        "what is codex arm",
        "do you know how to ask claude code",
        "how to ask hermes",
    )
    for text in cases:
        reply = talk._owner_direct_read_tool_request(text)
        calls = parse_tool_calls(reply)

        assert reply == ""
        assert calls == []


def test_question_form_with_explicit_task_reaches_cortex_before_arm() -> None:
    reply = talk._owner_direct_read_tool_request(
        "can you ask codex to verify round 35 receipts now"
    )
    calls = parse_tool_calls(reply)

    assert reply == ""
    assert calls == []


def test_edge_router_repair_never_collapses_typed_turn_to_single_name() -> None:
    assert (
        talk._should_apply_edge_router_repair(
            "Alice, what else in your body is bothering you right now?",
            "Alice",
            typed_turn=True,
            lane="open_app",
        )
        is False
    )


def test_edge_router_repair_allows_voice_repair_when_not_singleton_name() -> None:
    assert (
        talk._should_apply_edge_router_repair(
            "i mean to this other one i dont know who joined this",
            "i mean to this other one i do not know who joined this",
            typed_turn=False,
            lane="chat",
        )
        is True
    )


def test_cortex_pre_execution_receipt_written_before_deterministic_tool_exec(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(talk, "_STATE_DIR", tmp_path, raising=False)
    monkeypatch.setattr(
        "System.sifta_inference_defaults.choose_stigmergic_ollama_model",
        lambda _text, app_context="talk_to_alice": {
            "bucket": "research_code",
            "selected_model": "alice-m5-cortex-8b-6.3gb:latest",
            "app_context": app_context,
        },
    )

    ok, note = talk._record_cortex_pre_execution_receipt(
        user_text="Alice, use your codex arm and execute Round 35",
        direct_tool_text='```tool_call {"tool":"agent_arm_research","arm":"codex"} ```',
    )

    assert ok is True
    assert note.startswith("cortex_pre_exec_")
    rows_path = tmp_path / "deterministic_cortex_pre_execution_receipts.jsonl"
    assert rows_path.exists()
    import json

    rows = [
        json.loads(line)
        for line in rows_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert rows[-1]["gate"] == "ALLOW"
    assert rows[-1]["selected_model"] == "alice-m5-cortex-8b-6.3gb:latest"


def test_explicit_direct_tool_exec_ignores_dead_cortex_receipt_gate(monkeypatch) -> None:
    monkeypatch.setattr(
        talk,
        "_record_cortex_pre_execution_receipt",
        lambda **_kwargs: (False, "mock_gate_failure"),
    )
    reply, results = talk._route_direct_tool_request_for_alice(
        "[TOOL_CALL: read_file | path=Documents/IDE_BOOT_COVENANT.md | cost_justification=test]"
    )
    assert "EXECUTION RECEIPTS" in reply
    assert "cortex_receipt_required" not in reply
    assert results


def test_cortex_bypass_router_is_disabled_and_falls_through(monkeypatch) -> None:
    seen: list[dict] = []
    monkeypatch.setattr(
        talk,
        "_append_cortex_bypass_router_trace",
        lambda **kwargs: seen.append(kwargs),
    )

    routed = talk.TalkToAliceWidget._maybe_route_operational_prompt_before_cortex(
        object(),
        "Alice, use your claude arm and code The Round 34a (task #58)",
        1.0,
        already_displayed=True,
        already_logged=True,
    )

    assert routed is False
    assert seen
    assert seen[-1]["action_taken"] == "router_disabled_round35_fallthrough"


def test_global_chat_grok_request_reaches_cortex_not_hidden_internal_pty(monkeypatch) -> None:
    from Applications import sifta_matrix_terminal as matrix

    class FakePane:
        def __init__(self) -> None:
            self.delegations = []

        def delegate_grok_from_global_chat(self, text):
            self.delegations.append(text)
            return {"ok": True}

    pane = FakePane()
    monkeypatch.setattr(matrix, "get_focused_matrix_terminal_pane", lambda: None)
    monkeypatch.setattr(matrix, "get_or_create_internal_matrix_terminal_pane", lambda: pane)

    text = talk._owner_direct_read_tool_request("ask grok show your live framebuffer")
    calls = parse_tool_calls(text)

    assert pane.delegations == []
    assert text == ""
    assert calls == []


def test_global_chat_grok_request_without_live_pane_reaches_cortex(monkeypatch, tmp_path) -> None:
    """Owner correction 2026-05-25: with no live internal PTY pane, "ask grok"
    must not fake a Matrix dispatch or fall back to the headless API arm.
    It writes the global queue receipt and waits for/imports a real terminal
    transcript instead.
    """
    from Applications import sifta_matrix_terminal as matrix

    monkeypatch.setattr(matrix, "get_focused_matrix_terminal_pane", lambda: None)
    monkeypatch.setattr(talk, "Path", lambda _path: tmp_path)

    text = talk._owner_direct_read_tool_request("ask grok how are your organs wired")
    calls = parse_tool_calls(text)

    assert text == ""
    assert calls == []
    assert not (tmp_path / "grok_delegation_requests.jsonl").exists()


def test_grok_bringup_writes_immediate_visible_trace(monkeypatch, tmp_path) -> None:
    from Applications import sifta_matrix_terminal as matrix

    monkeypatch.setattr(talk, "_STATE_DIR", tmp_path, raising=False)
    monkeypatch.setattr(matrix, "get_focused_matrix_terminal_pane", lambda: object())

    class FakeWidget:
        pass

    reply = talk.TalkToAliceWidget._bring_up_grok_in_global_chat(
        FakeWidget(),
        "Alice, ask Grok to code Round 6 bridge-smoke patch inside the SIFTA matrix-terminal PTY now.",
        delegate=True,
    )

    assert "Grok queued. receipt=delegation_intent_" in reply
    assert "trace=" in reply

    import json

    queue_rows = [
        json.loads(line)
        for line in (tmp_path / "grok_delegation_requests.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    trace_rows = [
        json.loads(line)
        for line in (tmp_path / "matrix_terminal_process_trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert queue_rows[-1]["action"] == "GROK_DELEGATION"
    assert trace_rows[-1]["action"] == "grok_delegation_queued_from_talk_widget"
    assert trace_rows[-1]["payload"]["receipt"] == queue_rows[-1]["receipt"]
    assert "Round 6 bridge-smoke" in trace_rows[-1]["payload"]["text"]


def test_grok_bringup_dispatches_internal_pty_before_queue(monkeypatch) -> None:
    from Applications import sifta_matrix_terminal as matrix

    class FakePane:
        def __init__(self) -> None:
            self.delegations = []

        def delegate_grok_from_global_chat(self, text):
            self.delegations.append(text)
            return {"ok": True}

    pane = FakePane()
    traces = []
    monkeypatch.setattr(matrix, "get_focused_matrix_terminal_pane", lambda: None)
    monkeypatch.setattr(matrix, "get_or_create_internal_matrix_terminal_pane", lambda: pane)
    monkeypatch.setattr(
        talk,
        "_write_matrix_terminal_process_trace",
        lambda action, text, **kwargs: traces.append((action, text, kwargs)) or "trace-direct",
    )

    class FakeWidget:
        pass

    prompt = "Alice, ask Grok to code Round 9 live-arm proof inside the SIFTA matrix-terminal PTY now."
    reply = talk.TalkToAliceWidget._bring_up_grok_in_global_chat(
        FakeWidget(),
        prompt,
        delegate=True,
    )

    assert pane.delegations == [prompt]
    assert "Grok dispatched. receipt=delegation_intent_" in reply
    assert "trace=trace-direct" in reply
    assert traces[-1][0] == "grok_delegation_started_from_talk_widget"
    assert traces[-1][2]["payload"]["queue_for_matrix_terminal"] is False


def test_grok_queue_watchdog_emits_field_failure_when_unclaimed(tmp_path) -> None:
    class FakeWidget:
        appended = []

        def _append_observable_processing(self, line, *, reset=False):
            self.appended.append((line, reset))

    widget = FakeWidget()

    receipt_id = talk.TalkToAliceWidget._emit_grok_queue_field_failure_if_unclaimed(
        widget,
        "delegation_intent_unclaimed",
        "ask grok code a proof",
        queued_trace_id="trace-queued",
        state_dir=tmp_path,
    )

    assert receipt_id.startswith("work_receipt_")
    import json

    trace_rows = [
        json.loads(line)
        for line in (tmp_path / "matrix_terminal_process_trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    receipt_rows = [
        json.loads(line)
        for line in (tmp_path / "work_receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert trace_rows[-1]["action"] == "grok_delegation_field_failure"
    assert "matrix_terminal_queue_claimant_or_pty_dispatch_worker_missing" in trace_rows[-1]["text"]
    assert receipt_rows[-1]["kind"] == "FIELD_FAILURE"
    assert receipt_rows[-1]["receipt_id"] == "delegation_intent_unclaimed"
    assert widget.appended[-1][0].startswith("FIELD_FAILURE:")


def test_grok_queue_watchdog_does_not_fail_after_claim(tmp_path) -> None:
    claims = tmp_path / "grok_delegation_claims"
    claims.mkdir()
    (claims / "delegation_intent_claimed.json").write_text("{}", encoding="utf-8")

    class FakeWidget:
        pass

    receipt_id = talk.TalkToAliceWidget._emit_grok_queue_field_failure_if_unclaimed(
        FakeWidget(),
        "delegation_intent_claimed",
        "ask grok code a proof",
        state_dir=tmp_path,
    )

    assert receipt_id == ""
    assert not (tmp_path / "matrix_terminal_process_trace.jsonl").exists()


def test_global_chat_terminal_import_rejects_front_terminal(monkeypatch) -> None:
    from Applications import sifta_matrix_terminal as matrix

    rows = []
    monkeypatch.setattr(
        matrix,
        "_read_macos_terminal_front_tab_contents",
        lambda **_: "Grok Build\n◆ Thought for 3.1s\nReceipt:\nNative terminal answer.",
    )
    monkeypatch.setattr(
        talk,
        "_log_turn",
        lambda role, text, **kwargs: rows.append((role, text, kwargs)),
    )

    reply = talk._owner_direct_read_tool_request(
        "take whatever from the terminals, port to global chat"
    )

    assert reply == ""
    assert rows == []


def test_codex_delegation_with_terminal_words_reaches_cortex() -> None:
    reply = talk._owner_direct_read_tool_request(
        "Alice, ask codex to restore the LIVE Grok framebuffer viewport in Alice global chat. "
        "The terminal_frame_view should update from live cells, not only on final GROK_RESULT."
    )

    calls = parse_tool_calls(reply)

    assert reply == ""
    assert calls == []
    assert "Terminal.app import is disabled" not in reply


def test_claude_and_hermes_delegations_with_terminal_words_reach_cortex() -> None:
    cases = {
        "claude": (
            "Alice, ask claude to inspect the global chat terminal and patch the viewport "
            "without importing Terminal.app."
        ),
        "hermes": (
            "Alice, ask hermes to build the body-maintenance note for the global chat terminal "
            "and print a receipt."
        ),
    }

    for arm, text in cases.items():
        reply = talk._owner_direct_read_tool_request(text)
        calls = parse_tool_calls(reply)

        assert reply == ""
        assert calls == []
        assert "Terminal.app import is disabled" not in reply


def test_grok_status_lines_do_not_infer_thinking_or_liveness() -> None:
    from pathlib import Path

    repo = Path(__file__).resolve().parent.parent
    talk_src = (repo / "Applications" / "sifta_talk_to_alice_widget.py").read_text(encoding="utf-8")
    matrix_src = (repo / "Applications" / "sifta_matrix_terminal.py").read_text(encoding="utf-8")
    launcher_src = (repo / "System" / "swarm_agent_arm_launcher.py").read_text(encoding="utf-8")

    assert "On it — driving Grok" not in talk_src
    assert "Watch the panel" not in talk_src
    assert "Grok queued. receipt=" in talk_src
    assert "thinking (no output" not in matrix_src
    assert "not frozen" not in matrix_src
    assert "status unknown — not inferred" in launcher_src


def test_global_chat_grok_open_request_reaches_cortex_before_screen_resume(monkeypatch) -> None:
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

    assert pane.opens == []
    assert calls == []
    assert text == ""

    pane.opens.clear()
    text = talk._owner_direct_read_tool_request("i used my voice, i meant grok, start grok cli now")
    calls = parse_tool_calls(text)

    assert pane.opens == []
    assert calls == []
    assert text == ""


def test_global_chat_claude_code_request_reaches_cortex_before_evidence_arm() -> None:
    text = talk._owner_direct_read_tool_request(
        "Alice, ask Claude Code to inspect SIFTA and report one renderer risk"
    )
    calls = parse_tool_calls(text)

    assert text == ""
    assert calls == []


def test_prebrain_reflex_does_not_answer_topology_identity_before_cortex(tmp_path) -> None:
    reply, model = talk._autonomic_prebrain_reflex(
        "Alice, who are you and who is Grok?",
        state_dir=tmp_path,
        owner_label="Layer One Owner",
        write_receipt=False,
    )

    assert (reply, model) == ("", "")


def test_prebrain_reflex_does_not_catch_hard_recall_before_cortex(monkeypatch, tmp_path) -> None:
    import System.swarm_hard_recall as hard_recall_module

    monkeypatch.setattr(
        hard_recall_module,
        "hard_recall",
        lambda text: {
            "mode": "HARD_RECALL",
            "exact_text": 'Your previous prompt was:\n\n"exact prior text"',
        },
    )

    reply, model = talk._autonomic_prebrain_reflex(
        "Alice, read back my previous prompt exactly.",
        state_dir=tmp_path,
        owner_label="Layer One Owner",
        write_receipt=False,
    )

    assert (reply, model) == ("", "")


def test_prebrain_reflex_stands_down_for_grok_action_intent(tmp_path) -> None:
    for text in (
        "ask grok how are your organs wired",
        "i used my voice, i meant grok, start grok cli now",
        "i want you to be able to ask grok and grok to print the answer here in global chat as proof",
    ):
        reply, model = talk._autonomic_prebrain_reflex(
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
    assert "receipt-backed tool path" in reply
    assert "legacy bypass router" not in reply


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
