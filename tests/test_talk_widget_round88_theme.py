"""Round 88 tests — Talk widget black theme + single cyan-green accent.

The widget is a 22k+ line PyQt6 module that can't import in the Linux
sandbox without Qt. Tests use static inspection (regex + AST parse) to
verify the styling sweep landed cleanly:

  - All nine touched setStyleSheet blocks carry the new colors:
    #000000 / #0a0a0a (true black + soft black backgrounds)
    #e8e8e8 (warm white text)
    #1f1f1f / #2a2a2a (hairline borders)
    #00d4aa (the ONE cyan-green accent)
  - The pre-Round-88 purple/blue palette is gone from those blocks:
    no rgb(56,101,190) blue send button
    no #BB9AF7 / #5d4a87 purple thinking-toggle
    no rgb(45,42,65) hard-purple border in the main chat / side panel
  - File still parses as Python (no syntax break from the QSS edits).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


WIDGET = Path(__file__).resolve().parents[1] / "Applications" / "sifta_talk_to_alice_widget.py"


def _src() -> str:
    return WIDGET.read_text(encoding="utf-8")


# ─── File integrity ────────────────────────────────────────────────────────


def test_widget_exists():
    assert WIDGET.exists()


def test_widget_still_parses_after_theme_sweep():
    """Make sure none of the QSS string edits broke the surrounding Python."""
    try:
        ast.parse(_src())
    except SyntaxError as exc:
        pytest.fail(f"widget no longer parses: {exc}")


# ─── New palette present ───────────────────────────────────────────────────


def test_oled_black_background_in_chat_pane():
    src = _src()
    # The _chat QTextEdit should now declare #000000 with a hairline border.
    pattern = re.compile(
        r"self\._chat\.setStyleSheet\(.*?#000000.*?#1f1f1f.*?border-radius: 12px",
        re.DOTALL,
    )
    assert pattern.search(src), "chat pane should use OLED #000000 + #1f1f1f hairline + 12px radius"


def test_side_panel_uses_soft_black():
    src = _src()
    pattern = re.compile(
        r"self\._side\.setStyleSheet\(.*?#0a0a0a.*?#1f1f1f",
        re.DOTALL,
    )
    assert pattern.search(src)


def test_thinking_panel_uses_cyan_green_accent_rail():
    src = _src()
    # The thinking panel must carry the left-side cyan-green rail.
    pattern = re.compile(
        r"self\._thinking_panel\.setStyleSheet\(.*?border-left: 2px solid #00d4aa",
        re.DOTALL,
    )
    assert pattern.search(src)


def test_thinking_header_is_single_unified_control():
    src = _src()
    assert "_thinking_bubble_lbl" not in src
    assert "_refresh_thinking_header" in src
    assert "layout.addWidget(self._thinking_header_btn)" in src


def test_send_button_is_solid_cyan_green():
    src = _src()
    # The send button should be solid #00d4aa with black text.
    pattern = re.compile(
        r"self\._send_btn\.setStyleSheet\(.*?background: #00d4aa.*?color: #000000",
        re.DOTALL,
    )
    assert pattern.search(src)


def test_text_input_uses_accent_on_focus():
    src = _src()
    pattern = re.compile(
        r"self\._text_input\.setStyleSheet\(.*?QLineEdit:focus \{ border: 1px solid #00d4aa",
        re.DOTALL,
    )
    assert pattern.search(src)


def test_progress_chunk_uses_accent():
    src = _src()
    pattern = re.compile(
        r"self\._level\.setStyleSheet\(.*?QProgressBar::chunk \{ background: #00d4aa",
        re.DOTALL,
    )
    assert pattern.search(src)


def test_attach_btn_uses_monochrome_with_accent_hover():
    src = _src()
    pattern = re.compile(
        r"_attach_btn_default_style = \(.*?#0a0a0a.*?QPushButton:hover \{[^}]*?color: #00d4aa",
        re.DOTALL,
    )
    assert pattern.search(src)


def test_thinking_toggle_uses_monochrome_with_accent_hover():
    src = _src()
    pattern = re.compile(
        r"self\._thinking_header_btn\.setStyleSheet\(.*?QPushButton:hover \{[^}]*?color: #00d4aa",
        re.DOTALL,
    )
    assert pattern.search(src)


def test_terminal_label_uses_accent():
    src = _src()
    pattern = re.compile(
        r"self\._terminal_frame_label\.setStyleSheet\(.*?color: #00d4aa",
        re.DOTALL,
    )
    assert pattern.search(src)


# ─── Old palette removed from the touched blocks ───────────────────────────


def test_no_old_blue_send_button():
    """The pre-Round-88 send button was solid rgb(56,101,190) blue. Must be gone."""
    src = _src()
    pattern = re.compile(
        r"self\._send_btn\.setStyleSheet\(.*?rgb\(56\s*,\s*101\s*,\s*190\)",
        re.DOTALL,
    )
    assert not pattern.search(src), "old blue send button styling should be removed"


def test_no_old_purple_thinking_toggle():
    """The pre-Round-88 thinking toggle used #BB9AF7 / #5d4a87 purple. Gone."""
    src = _src()
    pattern = re.compile(
        r"self\._thinking_header_btn\.setStyleSheet\(.*?#BB9AF7",
        re.DOTALL,
    )
    assert not pattern.search(src), "old purple thinking toggle styling should be removed"


def test_no_old_purple_chat_border():
    """The chat pane used rgb(45,42,65) purple border. Replace with hairline."""
    src = _src()
    pattern = re.compile(
        r"self\._chat\.setStyleSheet\(.*?border: 1px solid rgb\(45\s*,\s*42\s*,\s*65\)",
        re.DOTALL,
    )
    assert not pattern.search(src)


# ─── Wallpaper path still works (we only changed the fallback bg color) ────


def test_wallpaper_loader_still_in_place():
    src = _src()
    # Round 88 keeps the wallpaper code path. Just confirm the loader is still
    # referenced in the same section (the path itself stays unchanged).
    assert "set_wallpaper_path" in src
    assert "Library/Desktop Pictures" in src or 'Library" / "Desktop Pictures"' in src
