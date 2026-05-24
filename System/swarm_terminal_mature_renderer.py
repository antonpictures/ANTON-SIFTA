#!/usr/bin/env python3
"""System/swarm_terminal_mature_renderer.py — MATURE terminal renderer.

George 2026-05-23 — the final wall is real terminal emulation inside the
organism. The Matrix Terminal's hand-built `_TerminalScreenBuffer` (the
"early renderer") only approximates a terminal, so a full-screen TUI like
the Grok CLI renders as leaked escape codes. This is the "mature renderer":
a proper VT100/xterm state machine (pyte) that turns raw PTY bytes into a
clean screen grid + per-cell colors/attributes, which a Qt widget paints.

Design notes
------------
- Pure-Python + pyte. NO Qt import here, so it is testable headless and the
  Alice field overlay / process-trace / global-memory integration stay in the
  widget layer on top. (Don't replace the PTY; render it properly.)
- The Matrix Terminal is NOT edited by this module. When the mature renderer
  is proven, the widget swaps `_TerminalScreenBuffer` -> MatureTerminalRenderer.
- Degrades gracefully if pyte is missing (PYTE_AVAILABLE=False) so importing
  this never crashes the OS; the widget can keep the early renderer until
  `pip install pyte` is run on the node.

For the Swarm. 🐜⚡
"""
from __future__ import annotations

from typing import Any

try:
    import pyte  # pure-python VT100/xterm emulator
    PYTE_AVAILABLE = True
except Exception:  # pragma: no cover - optional dep until `pip install pyte`
    pyte = None  # type: ignore
    PYTE_AVAILABLE = False


class MatureTerminalRenderer:
    """A real VT screen. Feed PTY bytes; read back a clean grid + colors.

    Usage (widget side, later):
        r = MatureTerminalRenderer(rows=40, cols=120)
        r.feed(pty_bytes)            # on QSocketNotifier read
        for row in r.cells():        # paint each cell with its fg/bg/attrs
            ...
        x, y, visible = r.cursor()
    """

    def __init__(self, rows: int = 24, cols: int = 80) -> None:
        if not PYTE_AVAILABLE:
            raise RuntimeError(
                "pyte is not installed — run `pip install pyte`. "
                "The early renderer (_TerminalScreenBuffer) remains the fallback."
            )
        self.rows = max(1, int(rows))
        self.cols = max(1, int(cols))
        # HistoryScreen gives scrollback; it also handles the alternate screen
        # buffer (1049h/l) that full-screen TUIs like Grok use.
        self._screen = pyte.HistoryScreen(self.cols, self.rows, history=2000, ratio=0.5)
        self._stream = pyte.ByteStream(self._screen)

    # ── input ──────────────────────────────────────────────────────────
    def feed(self, data: bytes | str) -> None:
        if not data:
            return
        if isinstance(data, str):
            data = data.encode("utf-8", errors="replace")
        try:
            self._stream.feed(data)
        except Exception:
            # A malformed sequence must never crash the organism's terminal.
            pass

    def resize(self, rows: int, cols: int) -> None:
        rows = max(1, int(rows))
        cols = max(1, int(cols))
        if rows == self.rows and cols == self.cols:
            return
        self.rows, self.cols = rows, cols
        try:
            self._screen.resize(rows, cols)
        except Exception:
            pass

    def reset(self) -> None:
        try:
            self._screen.reset()
        except Exception:
            pass

    # ── early-renderer API compatibility (drop-in for _TerminalScreenBuffer) ──
    # The Matrix Terminal has call sites that use the early renderer's method
    # names (clear/render/feed_bytes). Alias them so the mature renderer is a
    # true drop-in and no call site can crash when pyte is active.
    def clear(self) -> None:
        self.reset()

    def render(self) -> str:
        return self.text()

    def feed_bytes(self, data: bytes | str) -> None:
        self.feed(data)

    @property
    def use_alternate(self) -> bool:
        # The widget reads this to decide history framing; pyte handles the
        # alternate screen internally, so report False (single unified surface).
        return False

    # ── output ─────────────────────────────────────────────────────────
    def lines(self) -> list[str]:
        """Plain-text grid — drop-in compatible with the early renderer's render()."""
        try:
            return list(self._screen.display)
        except Exception:
            return []

    def text(self) -> str:
        return "\n".join(self.lines())

    def cells(self) -> list[list[dict[str, Any]]]:
        """Rich grid: each cell carries char + colors/attrs for a Qt painter.

        cell = {"char", "fg", "bg", "bold", "italics", "underscore", "reverse"}
        fg/bg are pyte color names ("default","green",...) or "RRGGBB" truecolor.
        """
        out: list[list[dict[str, Any]]] = []
        try:
            buf = self._screen.buffer
            for y in range(self.rows):
                row_cells: list[dict[str, Any]] = []
                row = buf[y]
                for x in range(self.cols):
                    ch = row[x]
                    row_cells.append({
                        "char": ch.data or " ",
                        "fg": ch.fg,
                        "bg": ch.bg,
                        "bold": bool(ch.bold),
                        "italics": bool(ch.italics),
                        "underscore": bool(ch.underscore),
                        "reverse": bool(ch.reverse),
                    })
                out.append(row_cells)
        except Exception:
            return out
        return out

    def cursor(self) -> tuple[int, int, bool]:
        try:
            c = self._screen.cursor
            return int(c.x), int(c.y), not bool(getattr(c, "hidden", False))
        except Exception:
            return 0, 0, True


def render_smoke(data: bytes, rows: int = 6, cols: int = 40) -> list[str]:
    """Tiny helper for headless verification / tests without Qt."""
    r = MatureTerminalRenderer(rows=rows, cols=cols)
    r.feed(data)
    return r.lines()


if __name__ == "__main__":
    if not PYTE_AVAILABLE:
        print("pyte not installed — run: pip install pyte")
        raise SystemExit(1)
    demo = (
        b"\x1b[2J\x1b[H"
        b"\x1b[1;32mNew worktree\x1b[0m   ctrl-w\r\n"
        b"\x1b[7mResume session\x1b[0m  ctrl-s\r\n"
        b"Quit            ctrl-q\r\n"
        b"\x1b[38;2;200;200;200mtruecolor line\x1b[0m"
    )
    r = MatureTerminalRenderer(rows=6, cols=40)
    r.feed(demo)
    for ln in r.lines():
        print(repr(ln))
    print("cursor:", r.cursor())
