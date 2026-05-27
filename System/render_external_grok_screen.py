#!/usr/bin/env python3
"""Render an external Grok TUI byte stream into a clean screen + marked thinking blocks.

The seam (owner 2026-05-25): global chat's TERMINAL_IMPORT reads shell *text*, not the
live VT framebuffer, so a full-screen TUI (grok's "Thought for Xs", alternate screen,
constant redraws) never reaches the one global chat — the old strip-ANSI path turned it
into 0 readable chars. This helper feeds RAW VT bytes (from a SIFTA-OWNED pty — i.e. the
internal matrix-terminal organ's pty.openpty / os.read(master_fd), NOT the external
Terminal.app, which can only give text) into the existing MatureTerminalRenderer (pyte
HistoryScreen handles the alternate-screen 1049h/l buffer grok uses), then returns the
rendered grid + which lines are thinking blocks. That lets the import carry grok's actual
reasoning into global chat — "same thoughts in global chat" — not just the final text.

claude-opus-4-7 2026-05-25 — built and tested in-sandbox against simulated grok TUI bytes.
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any

try:  # in-package import
    from System.swarm_terminal_mature_renderer import MatureTerminalRenderer
except Exception:  # direct-run / standalone fallback
    from swarm_terminal_mature_renderer import MatureTerminalRenderer  # type: ignore

# Lines grok renders while reasoning (visible in its TUI): the "Thought for Xs" markers,
# "Thinking…", bullet-thoughts, and tool-action lines (Read/Search/Ran). Conservative on
# purpose — only marks lines that are clearly process/thinking, never the final answer.
_THINKING_RE = re.compile(
    r"(thought for\s+[\d.]+\s*s"
    r"|thinking\s*[…\.]"
    r"|^\s*[●◆•]\s"
    r"|^\s*(?:read|search|ran|run|reading|searching)\b)",
    re.IGNORECASE,
)


def render_external_grok_screen(raw: bytes | str, *, rows: int = 24, cols: int = 80) -> dict[str, Any]:
    """Feed raw VT bytes through the mature renderer; return the rendered screen + markers.

    Returns a receipt-shaped dict: rendered text, the per-line list, the indices of the
    thinking-block lines, cursor position, a sha256 of the rendered screen, and counts.
    """
    renderer = MatureTerminalRenderer(rows=rows, cols=cols)
    renderer.feed(raw)
    lines = renderer.lines()
    thinking_lines = [i for i, ln in enumerate(lines) if ln.strip() and _THINKING_RE.search(ln)]
    rendered = "\n".join(lines).rstrip("\n")
    cur_x, cur_y, cur_vis = renderer.cursor()
    return {
        "truth_label": "GROK_FRAMEBUFFER_RENDER_V1",
        "ts": time.time(),
        "rows": rows,
        "cols": cols,
        "rendered": rendered,
        "lines": lines,
        "thinking_block_lines": thinking_lines,
        "thinking_block_count": len(thinking_lines),
        "cursor": {"x": cur_x, "y": cur_y, "visible": cur_vis},
        "rendered_sha256": hashlib.sha256(rendered.encode("utf-8", "replace")).hexdigest(),
        "char_count": len(rendered),
    }


def render_to_global_chat_block(raw: bytes | str, *, rows: int = 24, cols: int = 80) -> str:
    """A compact block for the one global chat: the rendered screen with [THINKING] markers."""
    p = render_external_grok_screen(raw, rows=rows, cols=cols)
    tset = set(p["thinking_block_lines"])
    body = [
        ("  [THINKING] " if i in tset else "             ") + ln.rstrip()
        for i, ln in enumerate(p["lines"])
        if ln.strip()
    ]
    head = (
        f"GROK rendered screen ({p['rows']}x{p['cols']}, "
        f"{p['thinking_block_count']} thinking lines, sha256={p['rendered_sha256'][:12]})"
    )
    return head + "\n" + "\n".join(body)


if __name__ == "__main__":
    # Simulated rich Grok TUI output: enters the alternate screen (1049h), clears, paints
    # cursor-addressed colored "Thought"/tool lines, then the answer. This is EXACTLY the
    # shape that the old strip-ANSI text import reduced to ~0 readable chars.
    ESC = b"\x1b"
    sample = b"".join([
        ESC + b"[?1049h",                 # enter alternate screen (full-screen TUI)
        ESC + b"[2J" + ESC + b"[H",       # clear + home
        ESC + b"[1;36m" + "◆ Thought for 3.6s".encode() + ESC + b"[0m\r\n",
        ESC + b"[1;36m" + "◆ Read /Users/ioanganton/Music/ANTON_SIFTA/Documents/IDE_BOOT_COVENANT.md".encode() + ESC + b"[0m\r\n",
        ESC + b"[1;36m" + "◆ Search \"import pyte\" in *.py".encode() + ESC + b"[0m\r\n",
        ESC + b"[1;36m" + "◆ Thought for 2.2s".encode() + ESC + b"[0m\r\n",
        b"\r\n",
        ESC + b"[1m" + "hardware layer 1 kernel primordial electricity quantum soup".encode() + ESC + b"[0m\r\n",
        b"\r\n",
        b"One body. One field. The repulsive pheromone field drives the coloring.\r\n",
        b"For the Swarm.\r\n",
        ESC + b"[6;1H",                    # park cursor
    ])
    print("=== RAW BYTES (what the old text-import sees, ANSI-stripped -> ~nothing) ===")
    stripped = re.sub(rb"\x1b\[[0-9;?]*[A-Za-z]", b"", sample).decode("utf-8", "replace")
    print(repr(stripped[:120]), "...\n")
    print("=== render_to_global_chat_block(sample) ===")
    print(render_to_global_chat_block(sample))
    p = render_external_grok_screen(sample)
    print("\n=== receipt ===")
    print({k: p[k] for k in ("thinking_block_count", "thinking_block_lines", "char_count", "rendered_sha256", "cursor")})
