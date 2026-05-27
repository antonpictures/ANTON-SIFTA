"""Tests for swarm_pty_visibility_stream — task #63."""

from __future__ import annotations

import json

import pytest

from System.swarm_pty_visibility_stream import (
    PTYVisibilityConfig,
    PTYLine,
    DirectTypeDispatch,
    FIELD_FAILURE_RESUME,
    check_resume_guard,
    create_direct_type_dispatch,
    format_pty_line,
    should_display,
    format_milestone_summary,
    format_final_summary,
    VISIBILITY_LEDGER,
)


@pytest.fixture(autouse=True)
def _patch_ledger(tmp_path, monkeypatch):
    ledger = tmp_path / "pty_visibility_stream.jsonl"
    monkeypatch.setattr(
        "System.swarm_pty_visibility_stream.VISIBILITY_LEDGER", ledger
    )
    return ledger


class TestResumeGuard:
    def test_resume_navigation_triggers_failure(self):
        assert check_resume_guard("resume_navigation:await_picker") == FIELD_FAILURE_RESUME

    def test_grok_resume_choice_triggers_failure(self):
        assert check_resume_guard("grok_resume_choice_nudge") == FIELD_FAILURE_RESUME

    def test_grok_resume_enter_triggers_failure(self):
        assert check_resume_guard("grok_resume_enter") == FIELD_FAILURE_RESUME

    def test_session_picker_triggers_failure(self):
        assert check_resume_guard("session_picker") == FIELD_FAILURE_RESUME

    def test_ctrl_s_main_menu_triggers_failure(self):
        assert check_resume_guard("ctrl_s_main_menu") == FIELD_FAILURE_RESUME

    def test_normal_action_passes(self):
        assert check_resume_guard("code_tournament_tasks") is None

    def test_direct_type_passes(self):
        assert check_resume_guard("direct_type_grok_payload") is None

    def test_empty_action_passes(self):
        assert check_resume_guard("") is None


class TestDirectTypeDispatch:
    def test_normal_dispatch_is_ready(self):
        dispatch = create_direct_type_dispatch("code the tournament")
        assert dispatch.status == "DIRECT_TYPE_READY"
        assert dispatch.dispatch_id
        assert dispatch.field_failure == ""

    def test_resume_payload_is_field_failure(self):
        dispatch = create_direct_type_dispatch("resume_navigation:await_picker")
        assert dispatch.status == "FIELD_FAILURE"
        assert "full_tournament_resume_flow_triggered_unexpectedly" in dispatch.field_failure

    def test_dispatch_recorded_to_ledger(self, _patch_ledger):
        create_direct_type_dispatch("test payload")
        lines = _patch_ledger.read_text().strip().split("\n")
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["status"] == "DIRECT_TYPE_READY"


class TestFormatPTYLine:
    def test_receipt_line_flagged(self):
        line = format_pty_line("receipt=abc123 files_written=3")
        assert line.is_receipt is True

    def test_heartbeat_line_flagged(self):
        line = format_pty_line("heartbeat: alive")
        assert line.is_heartbeat is True

    def test_normal_line(self):
        line = format_pty_line("def hello_world():")
        assert line.is_receipt is False
        assert line.is_heartbeat is False

    def test_long_line_truncated(self):
        config = PTYVisibilityConfig(max_line_length=50)
        line = format_pty_line("x" * 200, config=config)
        assert len(line.text) < 200
        assert "[truncated]" in line.text


class TestShouldDisplay:
    def test_receipts_always_shown(self):
        line = PTYLine(text="receipt=abc123", is_receipt=True)
        assert should_display(line) is True

    def test_heartbeats_suppressed(self):
        config = PTYVisibilityConfig(suppress_heartbeat=True)
        line = PTYLine(text="heartbeat", is_heartbeat=True)
        assert should_display(line, config=config) is False

    def test_empty_line_hidden(self):
        line = PTYLine(text="   ")
        assert should_display(line) is False

    def test_duplicate_suppressed(self):
        line = PTYLine(text="same line")
        assert should_display(line, recent_lines=["same line"]) is False

    def test_normal_line_shown(self):
        line = PTYLine(text="def function():")
        assert should_display(line) is True


class TestMilestoneSummary:
    def test_format_milestone(self):
        summary = format_milestone_summary(
            files_written=["System/foo.py", "tests/test_foo.py"],
            tests_run=5,
            receipt_id="abc-123",
        )
        assert "files_written=" in summary
        assert "tests_run=5" in summary
        assert "receipt_id=abc-123" in summary

    def test_format_final(self):
        summary = format_final_summary(
            total_files_touched=16,
            total_tests_run=85,
            final_receipt_id="final-xyz",
        )
        assert "total_files_touched=16" in summary
        assert "total_tests_run=85" in summary
        assert "final_receipt_id=final-xyz" in summary
