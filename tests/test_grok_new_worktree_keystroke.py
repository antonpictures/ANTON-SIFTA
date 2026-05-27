"""Tests for direct-type Grok launch sequencing (task #74 follow-up).

Authors:
- Patch + tests: codex-5.3 (Cursor) landed during Round 22, ~2026-05-27 00:40 UTC.
- Skip-guard hardening: claude-opus-4-6 (Cowork, HEAD) — covenant §4.4 / §6:
  the matrix terminal module imports PyQt6 at module load, which is unavailable
  in CI/sandbox environments. Without a skip-guard, pytest collection RED for
  an environment reason instead of a real failure — and worse, prior test
  files (test_structural_greeter_detector.py) almost shipped silent-pass
  lambdas that made assertions pass vacuously. We follow that file's pattern:
  honest skip, never vacuous green.
"""

from __future__ import annotations

import pytest

try:
    from Applications import sifta_matrix_terminal as matrix
except Exception as exc:  # noqa: BLE001 — any import failure means we cannot honestly test
    pytest.skip(
        f"Skipping Round 22 Ctrl-W keystroke tests: matrix_terminal import failed "
        f"({type(exc).__name__}: {exc}). "
        "These tests require PyQt6 + the live matrix terminal module to be importable. "
        "Silent-pass against stubs is forbidden per covenant §6 / §7.12.",
        allow_module_level=True,
    )


def test_send_ctrl_w_writes_key_and_emits_trace():
    pane = matrix.MatrixTerminalPane.__new__(matrix.MatrixTerminalPane)
    written: list[bytes] = []
    traces: list[tuple[str, str, str]] = []

    pane.write_bytes = lambda data: written.append(data)  # type: ignore[method-assign]
    pane._append_process_trace = (  # type: ignore[method-assign]
        lambda text, *, kind="", action="", payload=None: traces.append((text, kind, action))
    )

    matrix.MatrixTerminalPane._send_ctrl_w_for_new_worktree(pane)

    assert written == [b"\x17"]
    assert traces
    assert traces[-1][1] == "tool_delegation"
    assert traces[-1][2] == "grok_direct_type_new_worktree_keystroke"


def test_direct_type_sequence_spawn_then_ready_gate_without_selection_keys(monkeypatch):
    class FakePane:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.single_shots: list[int] = []

        def is_running(self) -> bool:
            return True

        def start_shell(self) -> None:
            self.calls.append("start_shell")

        def _append_plain(self, text: str) -> None:
            self.calls.append(f"plain:{text[:24]}")

        def _append_matrix_command_receipt(self, commands) -> None:
            self.calls.append(f"receipt:{commands[0] if commands else ''}")

        def _append_process_trace(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            self.calls.append("trace")

        def _log_global_terminal_turn(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            self.calls.append("log")

        def _current_cli_name(self) -> str:
            return ""

        def write_command(self, command: str) -> None:
            self.calls.append(f"write_command:{command}")

        def _schedule_grok_direct_type_paste(self, prompt: str, timeout_s: float = 0.0, poll_ms: int = 0) -> None:
            self.calls.append("ready_gate")

    pane = FakePane()

    def _immediate_single_shot(ms: int, cb) -> None:  # noqa: ANN001
        pane.single_shots.append(int(ms))
        cb()

    monkeypatch.setattr(matrix.QTimer, "singleShot", _immediate_single_shot)

    matrix.MatrixTerminalPane._execute_alice_cli_prompt_request(
        pane,
        "grok",
        "Alice, direct-type mode only, do NOT run resume_navigation, dispatch now.",
    )

    assert pane.single_shots[:2] == [250, 900]
    assert pane.calls.index("write_command:grok") < pane.calls.index("ready_gate")
    assert "ctrl_w" not in pane.calls
