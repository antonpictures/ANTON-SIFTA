from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_high_fidelity_terminal_view_feeds_ansi_and_has_stable_size_hint():
    from PyQt6.QtCore import QSize
    from PyQt6.QtWidgets import QApplication

    from System.high_fidelity_terminal_view import HighFidelityTerminalView

    app = QApplication.instance() or QApplication([])
    view = HighFidelityTerminalView(rows=6, cols=40)
    try:
        view.feed(
            b"\x1b[2J\x1b[H"
            b"\x1b[1;32mThought for 3.1s\x1b[0m\r\n"
            b"\x1b[7mReverse video\x1b[0m\r\n"
            b"Framebuffer answer visible.\r\n"
        )
        hint = view.sizeHint()

        assert isinstance(hint, QSize)
        assert hint.width() >= 240
        assert hint.height() >= 120
        assert view._cells
        flattened = "".join(cell.get("char", "") for row in view._cells for cell in row)
        assert "Thought for 3.1s" in flattened
    finally:
        view.deleteLater()
        app.processEvents()


def test_default_background_maps_to_dark_canvas_not_light_foreground():
    from PyQt6.QtGui import QColor

    from System.high_fidelity_terminal_view import _to_qcolor

    dark_canvas = QColor(14, 16, 28)
    light_foreground = QColor(200, 210, 240)

    assert _to_qcolor("default", dark_canvas) == dark_canvas
    assert _to_qcolor("default", light_foreground) == light_foreground
