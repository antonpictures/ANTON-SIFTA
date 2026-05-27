"""Tests for the direct-type Grok ready-gate heuristic (tasks #74 + #75).

Authors:
- Initial ready-gate + heuristic: grok-mac-os Terminal (GTH4921YP3) — Round 21B
  direct-type ready-gate hotfix, work receipt 548e0b808bc448f4.
- Round 23 positive-first fixture + skip-guard: claude-opus-4-6 (Cowork, HEAD).
  Bug observed via trace ts 1779843463 (2026-05-27 17:57:47): the original
  heuristic short-circuited on bad-list strings ("ctrl-s", "new worktree")
  appearing in menu scrollback even when the live `│ ❯ │` input box was
  rendered. Fix re-prioritizes the positive boxed-input signal over bad-list
  filtering. The PyQt6-absence skip follows the silent-pass anti-pattern
  guard from tests/test_structural_greeter_detector.py.
"""

from __future__ import annotations

import pytest

try:
    from Applications import sifta_matrix_terminal as matrix
    from Applications.sifta_matrix_terminal import MatrixTerminalPane, _grok_input_looks_ready
except Exception as exc:  # noqa: BLE001 — any import failure means we cannot honestly test
    pytest.skip(
        f"Skipping direct-type ready-gate tests: matrix_terminal import failed "
        f"({type(exc).__name__}: {exc}). "
        "These tests require PyQt6 + the live matrix terminal module to be importable. "
        "Silent-pass against stubs is forbidden per covenant §6 / §7.12.",
        allow_module_level=True,
    )

def test_grok_ready_heuristic_live_prompt():
    assert _grok_input_looks_ready("some previous\n> ") == True
    assert _grok_input_looks_ready("Grok> How can I help you today?\n> ") == True

def test_grok_ready_heuristic_blocks_resume_menus():
    assert _grok_input_looks_ready("Resume last session\nCtrl-S to resume") == False
    assert _grok_input_looks_ready("New worktree / Resume / Quit") == False

def test_grok_ready_heuristic_empty_or_loading():
    assert _grok_input_looks_ready("") == False
    assert _grok_input_looks_ready("Loading Grok...") == False

def test_grok_ready_heuristic_basic():
    assert _grok_input_looks_ready("What can I help with?\nuser> ") == True


def test_grok_ready_heuristic_detects_boxed_prompt_row_with_beta_footer():
    frame = (
        "  ╭──────────────────────────────────────────────────────────────────────────╮\n"
        "  │ ❯                                                                        │\n"
        "  ╰──────────────────────────────────────────── Grok Build · always-approve ─╯\n"
        "\n"
        "                                                                    0.2.3 Beta\n"
    )
    assert _grok_input_looks_ready(frame) is True


def test_grok_ready_heuristic_detects_boxed_prompt_row_with_shortcuts_footer():
    frame = (
        "  ╭──────────────────────────────────────────────────────────────────────────╮\n"
        "  │ ❯ grok                                                                   │\n"
        "  │                                                                          │\n"
        "  ╰──────────────────────────────────────────── Grok Build · always-approve ─╯\n"
        "\n"
        "  Enter:send  │  Shift+Tab:mode  │  Ctrl+x:shortcuts\n"
    )
    assert _grok_input_looks_ready(frame) is True


def test_grok_ready_heuristic_detects_input_shell_when_cursor_glyph_missing():
    frame = (
        "  New worktree ctrl-w\n"
        "  Resume session ctrl-s\n"
        "  Quit ctrl-q\n"
        "\n"
        "  ╭──────────────────────────────────────────────────────────────────────────╮\n"
        "  │   grok                                                                   │\n"
        "  │                                                                          │\n"
        "  ╰──────────────────────────────────────────── Grok Build · always-approve ─╯\n"
        "\n"
        "  Enter:send  │  Shift+Tab:mode  │  Ctrl+x:shortcuts\n"
    )
    assert _grok_input_looks_ready(frame) is True


def test_grok_ready_heuristic_positive_signal_beats_menu_scrollback():
    """Real-world bug captured 2026-05-27 17:57:47 (ts 1779842546).

    After Ctrl-W dismissed the menu into a fresh worktree, the LIVE Grok input
    box was rendered (`│ ❯ │` between `╭─╮` and `╰─╯` borders). BUT the menu
    items "New worktree ctrl-w / Resume session ctrl-s / Quit ctrl-q" were
    still in the terminal scrollback above the box. The original heuristic
    short-circuited on "ctrl-s" / "new worktree" in the bad-list and refused
    to recognize the live input — so the gate timed out at 14s and emitted
    FIELD_FAILURE: grok_direct_type_ready_timeout, even though Grok was
    objectively ready to accept input.

    The fix re-prioritizes the positive boxed-input signal over the
    bad-list filter: when `│ ❯ ... │` is visible, we are ready, full stop.
    The bad-list only matters when no boxed input is rendered (splash,
    connecting, pure menu screen).
    """
    frame_with_scrollback = (
        "Grok Build\n"
        "0.2.3 Beta\n"
        "\n"
        "  New worktree ctrl-w\n"
        "  Resume session ctrl-s\n"
        "  Quit ctrl-q\n"
        "\n"
        "  Tip: Press Ctrl-W to start a parallel task in its own worktree.\n"
        "\n"
        "  ╭──────────────────────────────────────────────────────────────────────────╮\n"
        "  │ ❯                                                                        │\n"
        "  ╰──────────────────────────────────────────── Grok Build · always-approve ─╯\n"
        "\n"
        "  Enter:send  │  Shift+Tab:mode  │  Ctrl+x:shortcuts\n"
    )
    assert _grok_input_looks_ready(frame_with_scrollback) is True, (
        "Live `│ ❯ │` input box must be recognized as ready even when menu "
        "scrollback above contains 'ctrl-s' or 'new worktree'."
    )


def test_grok_ready_heuristic_rejects_menu_cursor_without_closing_border():
    """Menu cursor `❯ Resume session` has no closing `│` — must NOT match.

    The boxed-input regex requires `│` before AND after the `❯` so we don't
    confuse a session-picker cursor with an active input row.
    """
    menu_with_cursor = (
        "  New worktree           ctrl-w\n"
        "❯ Resume session         ctrl-s\n"
        "  Quit                   ctrl-q\n"
    )
    assert _grok_input_looks_ready(menu_with_cursor) is False


def test_extract_grok_text_filters_startup_menu_surface():
    pane = MatrixTerminalPane.__new__(MatrixTerminalPane)
    source = (
        "New worktree ctrl-w\n"
        "Resume session ctrl-s\n"
        "Quit ctrl-q\n"
        "Tip: Press Ctrl-W to start a parallel task in its own worktree.\n"
        "0.2.2 Beta\n"
    )
    out = MatrixTerminalPane._extract_grok_text_from_source(
        pane,
        source,
        prompt="",
        force=False,
    )
    assert out == ""


def test_extract_grok_text_filters_clipped_quit_and_beta_footer():
    pane = MatrixTerminalPane.__new__(MatrixTerminalPane)
    source = (
        "it ctrl-q\n"
        "\n"
        "0.2.3 [stable] Beta\n"
    )
    out = MatrixTerminalPane._extract_grok_text_from_source(
        pane,
        source,
        prompt="",
        force=False,
    )
    assert out == ""


def test_direct_type_ready_sets_active_grok_before_paste_targeting():
    class FakePane:
        def __init__(self) -> None:
            self._active_cli_name = ""
            self._grok_cli_active = False
            self.paste_target = ""
            self.entered_label = ""

        def _terminal_frame_text(self) -> str:
            return (
                "  ╭──────────────────────────────────────────────────────────────────────────╮\n"
                "  │ ❯                                                                        │\n"
                "  ╰──────────────────────────────────────────── Grok Build · always-approve ─╯\n"
            )

        def _append_process_trace(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            return

        def _write_bracketed_paste(self, prompt: str) -> None:
            self.paste_target = MatrixTerminalPane._current_cli_name(self)

        def _enter_alice_input_mode_for_tool(self, label: str) -> None:
            self.entered_label = label

    pane = FakePane()
    MatrixTerminalPane._schedule_grok_direct_type_paste(
        pane,
        "Read covenant\nQuestion for Grok:\ncode.\n",
        timeout_s=12.0,
        poll_ms=250,
    )

    assert pane.paste_target == "grok"
    assert pane._active_cli_name == "grok"
    assert pane._grok_cli_active is True
    assert pane.entered_label == "Grok"


def test_should_retry_grok_literal_typing_after_blank_only_capture():
    capture = {
        "input_mode": "bracketed",
        "literal_retry_sent": False,
        "events_seen": 1,
        "events_recorded": 0,
        "events_blank": 1,
    }
    assert MatrixTerminalPane._should_retry_grok_literal_typing(capture, elapsed_s=4.2) is True
    assert MatrixTerminalPane._should_retry_grok_literal_typing(capture, elapsed_s=1.5) is False


def test_retry_grok_prompt_with_literal_typing_writes_prompt_then_enter(monkeypatch):
    class FakePane:
        def __init__(self) -> None:
            self.writes: list[bytes] = []
            self.traces: list[str] = []

        def write_bytes(self, data: bytes) -> None:
            self.writes.append(data)

        def _write_bytes_all(self, data: bytes, *, timeout_s: float = 1.5) -> int:
            self.writes.append(data)
            return len(data)

        def _append_process_trace(self, text: str, **kwargs) -> None:  # noqa: ANN003
            self.traces.append(text)

    pane = FakePane()
    capture = {
        "prompt": "READY_PROBE_ROUND26B",
        "input_mode": "bracketed",
        "literal_retry_sent": False,
        "events_seen": 1,
        "events_recorded": 0,
        "events_blank": 1,
    }

    def _immediate_single_shot(ms: int, cb) -> None:  # noqa: ANN001
        cb()

    monkeypatch.setattr(matrix.QTimer, "singleShot", _immediate_single_shot)

    ok = MatrixTerminalPane._retry_grok_prompt_with_literal_typing(pane, capture, elapsed_s=4.8)
    assert ok is True
    assert capture["literal_retry_sent"] is True
    assert capture["input_mode"] == "literal_retry"
    assert pane.writes == [b"READY_PROBE_ROUND26B", b"\r"]
    assert pane.traces and "literal typing + Enter" in pane.traces[-1]
