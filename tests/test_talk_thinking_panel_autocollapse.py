"""Source-level guard for Alice's live thinking panel lifecycle.

The Talk widget is a large PyQt surface, so these tests pin the wiring
without constructing the full desktop:

* thinking starts -> panel may auto-open
* thinking finishes -> panel auto-collapses after 900 ms
* owner manually toggles -> timer is stopped and auto-collapse is skipped
"""
from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
TALK_WIDGET = REPO / "Applications" / "sifta_talk_to_alice_widget.py"


def _src() -> str:
    return TALK_WIDGET.read_text(encoding="utf-8")


def test_thinking_panel_has_single_shot_auto_collapse_timer():
    src = _src()
    assert "self._thinking_auto_collapse_ms = 900" in src
    assert "self._thinking_auto_collapse_timer = QTimer(self)" in src
    assert "self._thinking_auto_collapse_timer.setSingleShot(True)" in src
    assert "self._thinking_auto_collapse_timer.timeout.connect(" in src
    assert "self._auto_collapse_thinking_panel" in src


def test_manual_toggle_stops_timer_and_marks_user_interaction():
    src = _src()
    toggle_start = src.index("def _toggle_thinking_panel")
    toggle_end = src.index("def _auto_collapse_thinking_panel")
    toggle_block = src[toggle_start:toggle_end]
    assert "self._thinking_user_interacted = True" in toggle_block
    assert "timer.stop()" in toggle_block


def test_new_thinking_resets_interaction_and_stops_old_timer():
    src = _src()
    thinking_start = src.index("def _on_thinking")
    thinking_end = src.index("def _on_token")
    thinking_block = src[thinking_start:thinking_end]
    assert "self._thinking_stream_active = True" in thinking_block
    assert "self._thinking_user_interacted = False" in thinking_block
    assert "timer.stop()" in thinking_block
    assert "and not getattr(self, \"_thinking_user_interacted\", False)" in thinking_block


def test_done_schedules_auto_collapse_after_final_char_count():
    src = _src()
    done_start = src.index("def _on_brain_done")
    done_block = src[done_start:done_start + 1800]
    assert "n_chars = len(panel.toPlainText() or \"\")" in done_block
    assert "self._schedule_thinking_auto_collapse()" in done_block


def test_talk_tails_matrix_process_trace_into_thinking_panel():
    src = _src()
    assert "self.make_timer(900, self._poll_matrix_process_trace_for_thinking)" in src
    assert "matrix_terminal_process_trace.jsonl" in src
    assert "still waiting for GROK_RESULT" in src
    assert "SIFTA_GROK_WAIT_HEARTBEAT_S" in src
    assert "now - last_row_ts >= hb_interval_s" in src
    assert "Global chat received GROK_RESULT" in src


def test_observable_processing_does_not_mirror_into_global_chat_by_default(monkeypatch):
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    monkeypatch.delenv("SIFTA_OBSERVABLE_MIRROR_TO_CHAT", raising=False)
    widget = type("FakeTalkWidget", (), {})()
    mirrored = []
    widget._trim_thinking_buffer_for_body_economy = lambda: False
    widget._append_global_cognition_stream = (
        lambda line, reset=False: mirrored.append((line, reset))
    )

    TalkToAliceWidget._append_observable_processing(
        widget,
        "Tool worker: dispatching agent_arm_research",
        reset=True,
    )

    assert mirrored == []


def test_observable_processing_debug_mirror_requires_env(monkeypatch):
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    monkeypatch.setenv("SIFTA_OBSERVABLE_MIRROR_TO_CHAT", "1")
    widget = type("FakeTalkWidget", (), {})()
    mirrored = []
    widget._trim_thinking_buffer_for_body_economy = lambda: False
    widget._append_global_cognition_stream = (
        lambda line, reset=False: mirrored.append((line, reset))
    )

    TalkToAliceWidget._append_observable_processing(
        widget,
        "Tool worker: dispatching agent_arm_research",
        reset=True,
    )

    assert mirrored == [("Tool worker: dispatching agent_arm_research", True)]


def test_observable_processing_suppresses_exact_duplicate_rows(monkeypatch):
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    monkeypatch.setenv("SIFTA_OBSERVABLE_MIRROR_TO_CHAT", "1")
    widget = type("FakeTalkWidget", (), {})()
    mirrored = []
    widget._trim_thinking_buffer_for_body_economy = lambda: False
    widget._append_global_cognition_stream = (
        lambda line, reset=False: mirrored.append((line, reset))
    )
    monkeypatch.setattr("Applications.sifta_talk_to_alice_widget.time.time", lambda: 1000.0)

    line = (
        "13:58:47 Matrix/Grok: grok_delegation_queued_from_talk_widget: "
        "queued visible Grok delegation receipt=delegation_intent_f31aa834e8e0"
    )
    TalkToAliceWidget._append_observable_processing(widget, line)
    TalkToAliceWidget._append_observable_processing(widget, line)

    assert mirrored == [(line, False)]


def test_global_chat_visible_text_collapses_long_prompts(monkeypatch):
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    monkeypatch.setenv("SIFTA_CHAT_COLLAPSE_LINES", "4")
    monkeypatch.setenv("SIFTA_CHAT_PREVIEW_LINES", "2")
    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)

    body = "\n".join(f"line {idx}" for idx in range(10))
    visible = TalkToAliceWidget._global_chat_visible_text(widget, body, "owner")

    assert "line 0\nline 1" in visible
    assert "line 7" not in visible
    assert "collapsed in chat: 10 lines" in visible
    assert "full turn remains in alice_conversation.jsonl" in visible


def test_global_chat_visible_text_surfaces_receipt_refs():
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)
    visible = TalkToAliceWidget._global_chat_visible_text(
        widget,
        "Round done. Receipt r58-src-e04da72a3c landed.",
        "alice",
    )

    assert "[receipts: r58-src-e04da72a3c]" in visible


def test_chat_anchor_and_render_all_messages_hooks_exist():
    src = _src()
    assert "def _on_chat_anchor_clicked" in src
    assert "def _render_all_messages" in src
    assert 'hasattr(self._chat, "setOpenExternalLinks")' in src
    assert 'hasattr(self._chat, "anchorClicked")' in src
    assert "anchorClicked.connect(self._on_chat_anchor_clicked)" in src


def test_planning_mode_toggle_injects_cortex_prompt_block():
    src = _src()
    assert "self._planning_mode_toggle = QCheckBox(\"Plan\")" in src
    assert "def _planning_mode_active" in src
    assert "from System.swarm_planning_mode import planning_prompt_block" in src
    assert "sysprompt = sysprompt + \"\\n\\n\" + _planning_context" in src


def test_planning_mode_skips_pre_cortex_direct_tool_and_arm_prepass():
    src = _src()
    assert "not self._planning_mode_active() and self._maybe_start_observable_direct_tool_request" in src
    assert "elif self._planning_mode_active():" in src
    assert "if self._planning_mode_active():\n            _reply, _tool_results = \"\", []" in src
    assert "agent-arm decision prepass REMOVED" in src
    assert "schedule_async_agent_arm_prepass" not in src


def test_planning_mode_does_not_parse_or_write_plans_inside_chat_widget():
    src = _src()
    assert "parse_plan(" not in src
    assert "write_plan(" not in src
    assert "update_plan_step(" not in src


def test_round67_honest_uncertainty_injects_prompt_context_not_chat_template():
    src = _src()
    assert "from System.swarm_honest_uncertainty import (" in src
    assert "evaluate as _honest_uncertainty_evaluate" in src
    assert "write_unknown as _honest_uncertainty_write_unknown" in src
    assert "_memory_card_has_relevant = _remember_memory_card_relevance" in src
    assert "UNKNOWN_LEDGER_RECEIPT" in src
    assert "parts.append(\n                    _hu_signal.block_text" in src


def test_round67_phone_audio_guard_is_ingress_guard_before_execute_trigger():
    src = _src()
    guard_start = src.index("Round 67 (2026-05-27): phone-audio")
    execute_start = src.index("EXECUTE TRIGGER WORD")
    assert guard_start < execute_start
    guard_block = src[guard_start:execute_start]
    assert "from System.swarm_phone_audio_guard import detect_environmental_audio" in guard_block
    assert "modality=\"spoken\"" in guard_block
    assert "owner_label=_owner_label()" in guard_block
    assert 'self._history.append({"role": "assistant", "content": "(silent: phone_audio_guard)"})' in guard_block
    assert "_append_system_line(_phone_audio_probe" in guard_block
    assert "_BrainWorker(" not in guard_block


def test_visible_alice_duplicate_guard_short_window(monkeypatch):
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    widget = type("FakeTalkWidget", (), {})()
    monkeypatch.setattr(
        "Applications.sifta_talk_to_alice_widget.time.time",
        lambda: 1000.0,
    )

    assert TalkToAliceWidget._suppress_visible_alice_duplicate(widget, "Online.") is False
    assert TalkToAliceWidget._suppress_visible_alice_duplicate(widget, "Online.") is True


def test_global_chat_cognition_stream_buffer_is_capped():
    import types

    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    widget = type("FakeTalkWidget", (), {})()
    widget._global_cognition_stream_active = False
    widget._global_cognition_stream_buffer = []
    widget._global_cognition_stream_max_chars = 260
    widget._global_cognition_stream_max_chunks = 4
    widget._trim_global_cognition_stream_buffer = types.MethodType(
        TalkToAliceWidget._trim_global_cognition_stream_buffer,
        widget,
    )
    widget._render_global_cognition_stream_block = lambda: None

    for idx in range(12):
        TalkToAliceWidget._append_global_cognition_stream(
            widget,
            f"09:12:{idx:02d} Codex live: " + ("x" * 70),
        )

    rendered = "".join(widget._global_cognition_stream_buffer)
    assert len(rendered) <= 260
    assert "older visible cognition stream compacted" in rendered
    assert "matrix_terminal_process_trace.jsonl" in rendered
    assert len(widget._global_cognition_stream_buffer) <= 4


def test_global_chat_cognition_stream_is_visible_main_chat_not_ledger_spam():
    src = _src()
    assert "Alice visible cognition stream" in src
    assert "def _append_global_cognition_stream" in src
    assert "SIFTA_OBSERVABLE_MIRROR_TO_CHAT" in src
    assert "_global_cognition_stream_pending_render_line" in src
    assert "reset_stream = action in {" in src
    assert "does not write synthetic thoughts into alice_conversation.jsonl" in src


def test_talk_renders_grok_framebuffer_cells_in_global_chat_surface():
    src = _src()
    assert "HighFidelityTerminalView" in src
    assert "self._terminal_frame_view = HighFidelityTerminalView" in src
    assert "def _connect_live_grok_framebuffer_source" in src
    assert "grokFramebufferSnapshotReady" in src
    assert "def _render_grok_terminal_frame_from_metadata" in src
    assert "framebuffer_cells" in src
    assert "pyte cells + cursor" in src


def test_talk_grok_framebuffer_helper_feeds_view_and_label():
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    class FakeView:
        def __init__(self):
            self.cells = None
            self.cursor = None
            self.visible = None

        def set_cells(self, cells, cursor):
            self.cells = cells
            self.cursor = cursor

        def setVisible(self, value):
            self.visible = value

    class FakeLabel:
        def __init__(self):
            self.text = ""
            self.visible = None

        def setText(self, text):
            self.text = text

        def setVisible(self, value):
            self.visible = value

    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)
    widget._terminal_frame_view = FakeView()
    widget._terminal_frame_label = FakeLabel()

    ok = TalkToAliceWidget._render_grok_terminal_frame_from_metadata(
        widget,
        {
            "framebuffer_cells": [[{"char": "G", "fg": "green", "bg": "default"}]],
            "framebuffer_cursor": [0, 0, True],
            "framebuffer_rows": 1,
            "framebuffer_cols": 1,
            "framebuffer_output_hash": "abcdef1234567890",
        },
    )

    assert ok is True
    assert widget._terminal_frame_view.cells[0][0]["char"] == "G"
    assert widget._terminal_frame_view.cursor == (0, 0, True)
    assert widget._terminal_frame_view.visible is True
    assert "Focused Grok viewport inside Alice global chat" in widget._terminal_frame_label.text
    assert "not a separate window" in widget._terminal_frame_label.text
    assert "1x1" in widget._terminal_frame_label.text
    assert "abcdef1234567890" in widget._terminal_frame_label.text
    assert widget._terminal_frame_label.visible is True


def test_talk_live_grok_framebuffer_signal_feeds_view_and_label():
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    class FakeView:
        def __init__(self):
            self.cells = None
            self.cursor = None
            self.visible = None

        def set_cells(self, cells, cursor):
            self.cells = cells
            self.cursor = cursor

        def setVisible(self, value):
            self.visible = value

    class FakeLabel:
        def __init__(self):
            self.text = ""
            self.visible = None

        def setText(self, text):
            self.text = text

        def setVisible(self, value):
            self.visible = value

    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)
    widget._terminal_frame_view = FakeView()
    widget._terminal_frame_label = FakeLabel()

    ok = TalkToAliceWidget._render_live_grok_terminal_frame_from_signal(
        widget,
        {
            "framebuffer_cells": [[{"char": "L", "fg": "cyan", "bg": "default"}]],
            "framebuffer_cursor": [0, 0, True],
            "framebuffer_rows": 1,
            "framebuffer_cols": 1,
            "framebuffer_output_hash": "livehash1234567890",
        },
    )

    assert ok is True
    assert widget._terminal_frame_view.cells[0][0]["char"] == "L"
    assert widget._terminal_frame_view.cursor == (0, 0, True)
    assert widget._terminal_frame_view.visible is True
    assert "live, not a separate window" in widget._terminal_frame_label.text
    assert "livehash12345678" in widget._terminal_frame_label.text


def test_talk_agent_arm_framebuffer_snapshot_suppresses_chat_view_by_default(monkeypatch):
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    monkeypatch.delenv("SIFTA_AGENT_ARM_FRAMEBUFFER_IN_CHAT", raising=False)

    class FakeView:
        def __init__(self):
            self.cells = None
            self.cursor = None
            self.visible = None

        def set_cells(self, cells, cursor):
            self.cells = cells
            self.cursor = cursor

        def setVisible(self, value):
            self.visible = value

    class FakeLabel:
        def __init__(self):
            self.text = ""
            self.visible = None

        def setText(self, text):
            self.text = text

        def setVisible(self, value):
            self.visible = value

    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)
    widget._terminal_frame_view = FakeView()
    widget._terminal_frame_label = FakeLabel()

    line = TalkToAliceWidget._format_matrix_process_trace_for_thinking(
        widget,
        {
            "ts": 1779650000.0,
            "action": "agent_arm_framebuffer_snapshot",
            "focused_cli": "codex",
            "text": "codex framebuffer",
            "payload": {
                "focused_cli": "codex",
                "terminal_label": "Codex",
                "framebuffer_cells": [[{"char": "C", "fg": "green", "bg": "default"}]],
                "framebuffer_cursor": [0, 0, True],
                "framebuffer_rows": 1,
                "framebuffer_cols": 1,
                "framebuffer_output_hash": "codexhash1234567890",
            },
        },
    )

    assert "Matrix/codex: framebuffer received" in line
    assert "chat mirror suppressed" in line
    assert widget._terminal_frame_view.cells is None
    assert widget._terminal_frame_label.text == ""


def test_talk_agent_arm_framebuffer_snapshot_can_debug_mirror_to_chat(monkeypatch):
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    monkeypatch.setenv("SIFTA_AGENT_ARM_FRAMEBUFFER_IN_CHAT", "1")

    class FakeView:
        def __init__(self):
            self.cells = None
            self.cursor = None
            self.visible = None

        def set_cells(self, cells, cursor):
            self.cells = cells
            self.cursor = cursor

        def setVisible(self, value):
            self.visible = value

    class FakeLabel:
        def __init__(self):
            self.text = ""
            self.visible = None

        def setText(self, text):
            self.text = text

        def setVisible(self, value):
            self.visible = value

    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)
    widget._terminal_frame_view = FakeView()
    widget._terminal_frame_label = FakeLabel()

    line = TalkToAliceWidget._format_matrix_process_trace_for_thinking(
        widget,
        {
            "ts": 1779650000.0,
            "action": "agent_arm_framebuffer_snapshot",
            "focused_cli": "codex",
            "text": "codex framebuffer",
            "payload": {
                "focused_cli": "codex",
                "terminal_label": "Codex",
                "framebuffer_cells": [[{"char": "C", "fg": "green", "bg": "default"}]],
                "framebuffer_cursor": [0, 0, True],
                "framebuffer_rows": 1,
                "framebuffer_cols": 1,
                "framebuffer_output_hash": "codexhash1234567890",
            },
        },
    )

    assert "Matrix/codex: framebuffer rendered in Alice global chat" in line
    assert widget._terminal_frame_view.cells[0][0]["char"] == "C"
    assert "Focused Codex viewport inside Alice global chat" in widget._terminal_frame_label.text


def test_observable_trace_buffer_is_capped_by_body_economy():
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    class FakeScroll:
        def maximum(self):
            return 0

        def setValue(self, _value):
            pass

    class FakePanel:
        def __init__(self):
            self.text = ""
            self.visible = True

        def isVisible(self):
            return self.visible

        def setVisible(self, value):
            self.visible = value

        def appendHtml(self, text):
            self.text += text + "\n"

        def setPlainText(self, text):
            self.text = text

        def toPlainText(self):
            return self.text

        def verticalScrollBar(self):
            return FakeScroll()

    class FakeButton:
        def __init__(self):
            self.text = ""

        def setText(self, text):
            self.text = text

    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)
    widget._thinking_buffer = []
    widget._thinking_panel = FakePanel()
    widget._thinking_header_btn = FakeButton()
    widget._thinking_stream_active = True
    widget._thinking_buffer_max_chars = 260
    widget._thinking_buffer_max_chunks = 4

    for idx in range(12):
        TalkToAliceWidget._append_observable_processing(
            widget,
            f"09:11:{idx:02d} Matrix/Grok: " + ("x" * 70),
        )

    rendered = widget._thinking_panel.toPlainText()
    assert len(rendered) <= 260
    assert "older observable trace compacted" in rendered
    assert "full receipts remain on disk" in rendered
    assert len(widget._thinking_buffer) <= 4


def test_long_external_tools_have_observable_worker_lane():
    src = _src()
    assert "class _DirectToolWorker(QThread)" in src
    assert "_maybe_start_observable_direct_tool_request" in src
    assert "tool receipt in flight" in src
    assert "_direct_tool_last_stream_ts" in src
    assert "Tool worker:" in src
    assert "Owner-named external arms are action requests, not greetings." in src


def test_direct_tool_heartbeat_suppressed_while_live_stream_recent(monkeypatch):
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    class FakeWorker:
        def isRunning(self):
            return True

    now = 1779650000.0
    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)
    widget._direct_tool_worker = FakeWorker()
    widget._direct_tool_started_ts = now - 40.0
    widget._direct_tool_label = "Codex agent arm"
    widget._direct_tool_last_stream_ts = now - 2.0
    appended = []
    widget._append_observable_processing = appended.append

    monkeypatch.setattr("Applications.sifta_talk_to_alice_widget.time.time", lambda: now)

    TalkToAliceWidget._direct_tool_heartbeat_tick(widget)

    assert appended == []


def test_external_cortex_requests_are_observable_direct_tool_requests():
    from Applications.sifta_talk_to_alice_widget import (
        _direct_tool_request_needs_observable_worker,
        _observable_direct_tool_label,
        _observable_tool_result_line,
    )

    assert _direct_tool_request_needs_observable_worker("Alice, ask Hermes how your organs are wired")
    assert _direct_tool_request_needs_observable_worker("Alice, ask Claude Code to inspect the repo")
    assert _direct_tool_request_needs_observable_worker("Alice, use your Codex arm and execute task #58")
    assert _direct_tool_request_needs_observable_worker("Alice, use your Claude arm and inspect the repo")
    assert _direct_tool_request_needs_observable_worker("Alice, use your Hermes arm and inspect receipts")
    assert not _direct_tool_request_needs_observable_worker("Alice, show Hermes skills app")
    assert _observable_direct_tool_label("ask claude code to inspect the repo") == "Claude Code agent arm"
    assert _observable_direct_tool_label("ask hermes how your organs are wired") == "Hermes agent arm"

    class FakeResult:
        tool_name = "agent_arm_research"
        status = "TIMEOUT"
        executed = False
        result = {"arm_id": "claude_agent", "receipt_id": "r-123"}
        feedback_for_alice = "agent_arm_research returned no successful receipt"

    line = _observable_tool_result_line(FakeResult())
    assert "Tool agent_arm_research" in line
    assert "status=TIMEOUT" in line
    assert "arm=claude_agent" in line
    assert "receipt=r-123" in line


def test_matrix_process_trace_formatter_reports_grok_result_proof():
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)
    line = TalkToAliceWidget._format_matrix_process_trace_for_thinking(
        widget,
        {
            "ts": 1779650000.0,
            "action": "GROK_RESULT",
            "text": "GROK_RESULT captured",
            "payload": {
                "capture_status": "captured",
                "captured_output_chars": 321,
                "captured_output_hash": "abcdef1234567890abcdef",
                "pty_transcript_span": {
                    "start_seq": 4,
                    "end_seq": 9,
                    "start_byte": 100,
                    "end_byte": 999,
                },
            },
        },
    )

    assert "captured 321 chars" in line
    assert "hash=abcdef1234567890" in line
    assert "seq 4-9 bytes 100-999" in line
    assert "Global chat should show GROK_RESULT" in line


def test_agent_arm_live_code_stream_stays_visible_by_default(monkeypatch):
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    monkeypatch.delenv("SIFTA_AGENT_ARM_RAW_LIVE", raising=False)
    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)
    row = {
        "ts": 1779650000.0,
        "action": "agent_arm_live",
        "focused_cli": "codex",
        "payload": {"session": "abc123456789"},
        "text": "+    def _weighted_choice(self, scored):",
    }

    line = TalkToAliceWidget._format_matrix_process_trace_for_thinking(widget, row)

    assert "_weighted_choice" in line
    assert "raw code/diff stream hidden" not in line


def test_agent_arm_live_code_stream_can_be_compacted_for_resource_pressure(monkeypatch):
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    monkeypatch.setenv("SIFTA_AGENT_ARM_RAW_LIVE", "0")
    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)
    row = {
        "ts": 1779650000.0,
        "action": "agent_arm_live",
        "focused_cli": "codex",
        "payload": {"session": "abc123456789"},
        "text": "+    def _weighted_choice(self, scored):",
    }

    line = TalkToAliceWidget._format_matrix_process_trace_for_thinking(widget, row)

    assert "raw code/diff stream hidden" in line
    assert "_weighted_choice" not in line
    assert "full trace on disk" in line


def test_agent_arm_live_proof_lines_stay_visible(monkeypatch):
    from Applications.sifta_talk_to_alice_widget import TalkToAliceWidget

    monkeypatch.delenv("SIFTA_AGENT_ARM_RAW_LIVE", raising=False)
    widget = TalkToAliceWidget.__new__(TalkToAliceWidget)
    line = TalkToAliceWidget._format_matrix_process_trace_for_thinking(
        widget,
        {
            "ts": 1779650000.0,
            "action": "agent_arm_live",
            "focused_cli": "codex",
            "payload": {"session": "abc123456789"},
            "text": "✅ BUILD_VERIFIED Stigmergic Ant Foraging Trail",
        },
    )

    assert "BUILD_VERIFIED" in line
    assert "raw code/diff stream hidden" not in line
