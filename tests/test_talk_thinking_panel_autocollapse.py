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
    assert "Global chat received GROK_RESULT" in src


def test_long_external_tools_have_observable_worker_lane():
    src = _src()
    assert "class _DirectToolWorker(QThread)" in src
    assert "_maybe_start_observable_direct_tool_request" in src
    assert "still waiting for tool receipt" in src
    assert "Tool worker:" in src


def test_external_cortex_requests_are_observable_direct_tool_requests():
    from Applications.sifta_talk_to_alice_widget import (
        _direct_tool_request_needs_observable_worker,
        _observable_direct_tool_label,
        _observable_tool_result_line,
    )

    assert _direct_tool_request_needs_observable_worker("Alice, ask Hermes how your organs are wired")
    assert _direct_tool_request_needs_observable_worker("Alice, ask Claude Code to inspect the repo")
    assert not _direct_tool_request_needs_observable_worker("Alice, show Hermes skills app")
    assert _observable_direct_tool_label("ask claude code to inspect the repo") == "Claude Code agent arm"
    assert _observable_direct_tool_label("ask hermes how your organs are wired") == "Hermes agent arm"

    class FakeResult:
        tool_name = "agent_arm_research"
        status = "TIMEOUT"
        executed = False
        result = {"arm_id": "claude_agent", "receipt_id": "r-123"}
        feedback_for_alice = "agent_arm_research returned no usable evidence"

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
