from __future__ import annotations

import pytest


def test_mature_terminal_renderer_is_drop_in_for_early_screen_api():
    pytest.importorskip("pyte")

    from System.swarm_terminal_mature_renderer import MatureTerminalRenderer

    renderer = MatureTerminalRenderer(rows=4, cols=24)
    renderer.feed("shell prompt")

    assert "shell prompt" in renderer.render()
    assert renderer.text() == renderer.render()
    assert renderer.use_alternate is False

    renderer.feed_bytes(b"\r\nNew worktree ctrl-w\r\nResume session ctrl-s\r\n")
    text = renderer.render()

    assert "New worktree" in text
    assert "Resume session" in text

    renderer.clear()
    assert "New worktree" not in renderer.render()


def test_mature_terminal_renderer_resize_and_cells_do_not_crash():
    pytest.importorskip("pyte")

    from System.swarm_terminal_mature_renderer import MatureTerminalRenderer

    renderer = MatureTerminalRenderer(rows=2, cols=10)
    renderer.resize(3, 12)
    renderer.feed(b"ok")

    assert renderer.rows == 3
    assert renderer.cols == 12
    assert renderer.cells()[0][0]["char"] == "o"
    assert renderer.cursor()[2] in (True, False)
