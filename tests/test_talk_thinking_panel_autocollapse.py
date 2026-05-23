"""Source-level guard for Alice's live thinking panel lifecycle.

The Talk widget is a large PyQt surface, so these tests pin the wiring
without constructing the full desktop:

* thinking starts -> panel may auto-open
* thinking finishes -> panel auto-collapses after 900 ms
* owner manually toggles -> timer is stopped and auto-collapse is skipped
"""
from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
TALK_WIDGET = REPO / "Applications" / "sifta_talk_to_alice_widget.py"


def _src() -> str:
    return TALK_WIDGET.read_text(encoding="utf-8")


def test_thinking_panel_has_single_shot_auto_collapse_timer():
    src = _src()
    assert "self._thinking_auto_collapse_ms = 900" in src
    assert "self._thinking_auto_collapse_timer = QTimer(self)" in src
    assert "self._thinking_auto_collapse_timer.setSingleShot(True)" in src
    assert "self._thinking_auto_collapse_timer.timeout.connect(" in src
    assert "self._auto_collapse_thinking_panel" in src


def test_manual_toggle_stops_timer_and_marks_user_interaction():
    src = _src()
    toggle_start = src.index("def _toggle_thinking_panel")
    toggle_end = src.index("def _auto_collapse_thinking_panel")
    toggle_block = src[toggle_start:toggle_end]
    assert "self._thinking_user_interacted = True" in toggle_block
    assert "timer.stop()" in toggle_block


def test_new_thinking_resets_interaction_and_stops_old_timer():
    src = _src()
    thinking_start = src.index("def _on_thinking")
    thinking_end = src.index("def _on_token")
    thinking_block = src[thinking_start:thinking_end]
    assert "self._thinking_stream_active = True" in thinking_block
    assert "self._thinking_user_interacted = False" in thinking_block
    assert "timer.stop()" in thinking_block
    assert "and not getattr(self, \"_thinking_user_interacted\", False)" in thinking_block


def test_done_schedules_auto_collapse_after_final_char_count():
    src = _src()
    done_start = src.index("def _on_brain_done")
    done_block = src[done_start:done_start + 1800]
    assert "n_chars = len(panel.toPlainText() or \"\")" in done_block
    assert "self._schedule_thinking_auto_collapse()" in done_block

