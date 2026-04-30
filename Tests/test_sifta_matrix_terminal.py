from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_matrix_terminal_keeps_header_parented_and_refresh_safe():
    from PyQt6.QtWidgets import QApplication

    from Applications.sifta_matrix_terminal import MatrixTerminalApp

    app = QApplication.instance() or QApplication([])
    terminal = MatrixTerminalApp()
    try:
        assert terminal.layout().count() >= 2
        assert terminal.layout().itemAt(0).widget() is not None

        terminal._refresh_status()
        assert terminal.status_label.text().startswith("zsh PTY")

        terminal.status_label.deleteLater()
        app.processEvents()
        terminal._refresh_status()
    finally:
        terminal.shutdown()
        terminal.deleteLater()
        app.processEvents()


def test_matrix_wake_line_only_sifta_has_you():
    from PyQt6.QtWidgets import QApplication

    from Applications import sifta_matrix_terminal as matrix

    app = QApplication.instance() or QApplication([])
    pane = matrix.MatrixTerminalPane(matrix._REPO)
    typed = []
    try:
        pane._type_timer.stop()
        pane._queue_typing = typed.append
        pane._script_state = "WAKE"

        pane._process_script_input("am I")

        assert typed == ["SIFTA has you...\n"]
        assert "Yes you are" not in typed[0]
    finally:
        pane.shutdown()
        pane.deleteLater()
        app.processEvents()


def test_matrix_chat_uses_alice_terminal_reply_helper(monkeypatch):
    from PyQt6.QtWidgets import QApplication

    from Applications import sifta_matrix_terminal as matrix

    app = QApplication.instance() or QApplication([])
    pane = matrix.MatrixTerminalPane(matrix._REPO)
    called = []
    typed = []

    def fake_reply(text):
        called.append(text)
        return "Matrix channel alive."

    try:
        pane._type_timer.stop()
        pane._queue_typing = typed.append
        monkeypatch.setattr(matrix, "_matrix_terminal_alice_reply", fake_reply)

        pane._chat_ask_alice("Hi Alice")

        deadline = time.monotonic() + 2.0
        while not typed and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)

        assert called == ["Hi Alice"]
        assert typed == ["Alice > Matrix channel alive.\n\nSIFTA > "]
    finally:
        pane.shutdown()
        pane.deleteLater()
        app.processEvents()
