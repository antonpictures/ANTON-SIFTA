from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _pump_until(app, predicate, timeout_s: float = 4.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.03)
    return False


def test_sifta_terminal_uses_pty_shell_and_executes_commands(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from PyQt6.QtWidgets import QApplication

    from Applications.sifta_terminal import SiftaTerminalApp

    app = QApplication.instance() or QApplication([])
    terminal = SiftaTerminalApp()
    terminal.show()
    try:
        assert _pump_until(app, terminal.terminal.is_running)
        terminal.write_command("printf SIFTA_TERMINAL_OK\\\\n")
        assert _pump_until(
            app,
            lambda: "SIFTA_TERMINAL_OK" in terminal.terminal.toPlainText(),
        )
        assert "default interactive shell is now zsh" not in terminal.terminal.toPlainText()
    finally:
        terminal.shutdown()
        _pump_until(app, lambda: not terminal.terminal.is_running(), timeout_s=2.0)
        terminal.close()
