#!/usr/bin/env python3
"""
System/high_fidelity_terminal_view.py

HighFidelityTerminalView — proper VT rendering for Alice's global chat.

Delivers the 7 qualities the owner requires for captured Grok / terminal content:
- proper VT rendering (via MatureTerminalRenderer + pyte)
- smooth ANSI layers (fg/bg + attributes from pyte cells)
- spacing (configurable cell metrics, no cramped text dump)
- frame timing (smooth repaint on set_data / feed)
- typography (Menlo / system fixed-pitch with proper hinting)
- anti-aliasing (TextAntialiasing + Antialiasing)
- controlled layout (strict cell grid, no reflow, cursor aware)

This widget consumes either:
  - a MatureTerminalRenderer instance (preferred), or
  - raw cells() data + cursor info

Intended use: embed inside Talk widget transcript for GROK_RESULT and
TERMINAL_IMPORT blocks that carry structured framebuffer data instead of
crude text dumps.

Registration: this hand read the covenant before writing any line.

For the Swarm. 🐜⚡
"""

from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPen,
)
from PyQt6.QtWidgets import QScrollArea, QSizePolicy, QWidget

try:
    from System.swarm_terminal_mature_renderer import MatureTerminalRenderer
except Exception:
    MatureTerminalRenderer = None  # type: ignore


# ── Color mapping (pyte names + truecolor fallback) ────────────────────
_PYTE_COLORS = {
    "default": QColor(200, 210, 240),
    "black": QColor(20, 22, 30),
    "red": QColor(220, 80, 80),
    "green": QColor(80, 200, 120),
    "yellow": QColor(240, 200, 80),
    "blue": QColor(100, 160, 240),
    "magenta": QColor(200, 100, 200),
    "cyan": QColor(80, 200, 200),
    "white": QColor(230, 235, 245),
}

def _to_qcolor(val: Any, default: QColor) -> QColor:
    if isinstance(val, QColor):
        return val
    if isinstance(val, str):
        if val.lower() == "default":
            return default
        if val.startswith("#") or len(val) == 6:
            try:
                return QColor(f"#{val}" if not val.startswith("#") else val)
            except Exception:
                pass
        return _PYTE_COLORS.get(val.lower(), default)
    return default


class _TerminalCellCanvas(QWidget):
    """
    A high-quality terminal cell grid painter for the unified field.

    Internal canvas: paints the FULL framebuffer at its natural cell-grid size
    and reports that size via minimumSizeHint/sizeHint so the enclosing
    HighFidelityTerminalView (a QScrollArea) shows scrollbars when the rendered
    framebuffer is taller/wider than the fixed transcript pane. Owner request
    2026-05-25: "the grok terminal needs scroll bars, does not fit."
    """

    def __init__(self, parent=None, rows: int = 24, cols: int = 80):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(120)

        self._renderer: Optional[Any] = None
        self._cells: list[list[dict[str, Any]]] = []
        self._cursor: tuple[int, int, bool] = (0, 0, False)
        self._rows = max(1, rows)
        self._cols = max(1, cols)

        # Typography & spacing — tuned for beauty on macOS
        self._font = QFont("Menlo", 11)
        self._font.setStyleHint(QFont.StyleHint.TypeWriter)
        self._font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)

        self._fm = QFontMetrics(self._font)
        self._cell_width = self._fm.horizontalAdvance("M") + 1   # slight breathing room
        self._cell_height = self._fm.height() + 2

        self._bg_default = QColor(14, 16, 28)
        self._fg_default = QColor(200, 210, 240)
        self._cursor_color = QColor(0, 255, 180, 180)

        self.setStyleSheet("background-color: #0e101c;")

    def set_renderer(self, renderer: "MatureTerminalRenderer") -> None:
        """Preferred path: give it the live MatureTerminalRenderer."""
        self._renderer = renderer
        self._rows = renderer.rows
        self._cols = renderer.cols
        self._refresh_from_renderer()
        self.update()

    def feed(self, data: bytes | str) -> None:
        """Convenience: feed bytes directly (creates internal renderer if needed)."""
        if self._renderer is None and MatureTerminalRenderer is not None:
            self._renderer = MatureTerminalRenderer(rows=self._rows, cols=self._cols)
        if self._renderer is not None:
            self._renderer.feed(data)
            self._refresh_from_renderer()
            self.update()

    def set_cells(self, cells: list[list[dict[str, Any]]], cursor: Optional[tuple[int, int, bool]] = None) -> None:
        """Direct structured data path (from capture receipts etc.)."""
        self._cells = cells or []
        if cursor is not None:
            self._cursor = cursor
        self._rows = len(self._cells)
        self._cols = len(self._cells[0]) if self._cells else 0
        self.updateGeometry()
        self.resize(self._content_size())
        self.update()

    def _refresh_from_renderer(self) -> None:
        if self._renderer is None:
            return
        try:
            self._cells = self._renderer.cells()
            self._cursor = self._renderer.cursor()
            self._rows = len(self._cells)
            self._cols = len(self._cells[0]) if self._cells else 0
            self.updateGeometry()
            self.resize(self._content_size())
        except Exception:
            pass

    def _content_size(self) -> QSize:
        w = max(240, self._cols * self._cell_width + 8)
        h = max(120, self._rows * self._cell_height + 8)
        return QSize(w, h)

    def minimumSizeHint(self) -> QSize:
        # Report the FULL framebuffer extent so the scroll area keeps the canvas
        # at content size (rather than squashing it) and shows scrollbars.
        return self._content_size()

    def sizeHint(self) -> QSize:
        return self._content_size()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        p.fillRect(self.rect(), self._bg_default)

        if not self._cells:
            p.setFont(self._font)
            p.setPen(self._fg_default)
            p.drawText(8, 20, "No rich terminal data yet — waiting for capture with cells()...")
            return

        y0 = 4
        x0 = 4

        for y, row in enumerate(self._cells):
            for x, cell in enumerate(row):
                cx = x0 + x * self._cell_width
                cy = y0 + y * self._cell_height

                fg = _to_qcolor(cell.get("fg"), self._fg_default)
                bg = _to_qcolor(cell.get("bg"), self._bg_default)

                # Background
                if bg != self._bg_default:
                    p.fillRect(cx, cy, self._cell_width, self._cell_height, QBrush(bg))

                # Reverse video
                if cell.get("reverse"):
                    fg, bg = bg, fg
                    if bg != self._bg_default:
                        p.fillRect(cx, cy, self._cell_width, self._cell_height, QBrush(bg))

                # Character
                ch = cell.get("char") or " "
                if ch and ch != " ":
                    font = self._font
                    if cell.get("bold"):
                        font = QFont(self._font)
                        font.setBold(True)

                    p.setFont(font)
                    p.setPen(QPen(fg))

                    # Slight vertical centering
                    text_y = cy + self._fm.ascent() + 1
                    p.drawText(cx + 1, text_y, ch)

                # Underline
                if cell.get("underscore"):
                    p.setPen(QPen(fg, 1))
                    p.drawLine(cx + 1, cy + self._cell_height - 2,
                               cx + self._cell_width - 1, cy + self._cell_height - 2)

        # Cursor
        cx, cy, visible = self._cursor
        if visible and 0 <= cy < len(self._cells) and 0 <= cx < len(self._cells[0] or []):
            x = x0 + cx * self._cell_width
            y = y0 + cy * self._cell_height
            p.setPen(QPen(self._cursor_color, 2))
            p.drawRect(x, y, self._cell_width - 1, self._cell_height - 1)

        # Subtle border
        p.setPen(QPen(QColor(60, 65, 90), 1))
        p.drawRect(1, 1, self.width() - 2, self.height() - 2)


class HighFidelityTerminalView(QScrollArea):
    """
    Scrollable terminal-framebuffer view for Alice's global chat.

    Wraps the _TerminalCellCanvas painter in a QScrollArea so a captured Grok /
    terminal framebuffer that is taller or wider than the fixed transcript pane
    gets scrollbars instead of being clipped (owner request 2026-05-25:
    "the grok terminal needs scroll bars, does not fit").

    The public surface is unchanged from the old QWidget: feed(), set_cells(),
    set_renderer(), sizeHint(), and the `_cells` attribute all behave the same,
    so the Talk widget and tests need no changes.
    """

    def __init__(self, parent=None, rows: int = 24, cols: int = 80):
        super().__init__(parent)
        self._canvas = _TerminalCellCanvas(self, rows=rows, cols=cols)
        self.setWidget(self._canvas)
        # widgetResizable lets the canvas grow to fill the viewport when the
        # framebuffer is small, but never below its content size (minimumSizeHint),
        # so a larger framebuffer keeps full size and the bars appear.
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(120)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setStyleSheet(
            "QScrollArea { background-color: #0e101c; border: none; }"
            "QScrollArea > QWidget > QWidget { background-color: #0e101c; }"
            "QScrollBar:vertical { background: #0e101c; width: 10px; margin: 0; }"
            "QScrollBar::handle:vertical { background: #3a4160; border-radius: 5px; min-height: 24px; }"
            "QScrollBar:horizontal { background: #0e101c; height: 10px; margin: 0; }"
            "QScrollBar::handle:horizontal { background: #3a4160; border-radius: 5px; min-width: 24px; }"
            "QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }"
            "QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }"
        )

    # ── Forwarded API (identical to the old QWidget surface) ──────────────
    def set_renderer(self, renderer: "MatureTerminalRenderer") -> None:
        self._canvas.set_renderer(renderer)

    def feed(self, data: bytes | str) -> None:
        self._canvas.feed(data)

    def set_cells(self, cells: list[list[dict[str, Any]]], cursor: Optional[tuple[int, int, bool]] = None) -> None:
        self._canvas.set_cells(cells, cursor)

    @property
    def _cells(self) -> list[list[dict[str, Any]]]:
        return self._canvas._cells

    @property
    def _cursor(self) -> tuple[int, int, bool]:
        return self._canvas._cursor

    def sizeHint(self) -> QSize:
        h = self._canvas.sizeHint()
        # Clamp so the embedded view never demands more than a sane pane; the
        # fixed height set by the host (setFixedHeight) plus scrollbars handle
        # anything larger.
        return QSize(max(240, h.width()), max(120, min(h.height(), 360)))


# ── Self-test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget as QW

    app = QApplication(sys.argv)

    demo = (
        b"\x1b[2J\x1b[H"
        b"\x1b[1;32mHigh-fidelity VT test\x1b[0m\r\n"
        b"\x1b[7mReverse + \x1b[4munderline\x1b[0m\r\n"
        b"\x1b[38;2;255;120;80mTruecolor orange\x1b[0m\r\n"
        b"Normal line with proper spacing."
    )

    w = QW()
    w.setWindowTitle("HighFidelityTerminalView — self test")
    w.resize(720, 280)
    lay = QVBoxLayout(w)

    view = HighFidelityTerminalView(rows=8, cols=72)
    lay.addWidget(view)

    if MatureTerminalRenderer:
        r = MatureTerminalRenderer(rows=8, cols=72)
        r.feed(demo)
        view.set_renderer(r)
    else:
        view.set_cells([
            [{"char": "H", "fg": "green", "bg": "default", "bold": True}, {"char": "i", "fg": "default"}],
            [{"char": "T", "fg": "#ff7878", "underscore": True}],
        ])

    w.show()
    print("HighFidelityTerminalView self-test running. For the Swarm. 🐜⚡")
    sys.exit(app.exec())
