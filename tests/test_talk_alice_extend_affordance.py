#!/usr/bin/env python3
"""Static coverage for Talk's imported-Alice long answer affordance."""

from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "Applications" / "sifta_talk_to_alice_widget.py"


def test_talk_imported_alice_rows_use_four_paragraph_preview_helper():
    src = SOURCE.read_text(encoding="utf-8")

    assert "def _prepare_alice_visible_text(" in src
    assert "collapse_text_after_paragraphs(raw_text, max_paragraphs=4)" in src
    assert "sifta://alice-extend/" in src
    assert "hidden_paragraph_count" in src


def test_talk_chat_text_edit_emits_local_anchor_clicks_for_global_and_direct_rows():
    src = SOURCE.read_text(encoding="utf-8")

    assert "localAnchorClicked = pyqtSignal(str)" in src
    assert "self.localAnchorClicked.emit(anchor)" in src
    assert "self._append_alice_extension_for_key(key)" in src
    assert "self._insert_alice_extend_control(cur, extend_key, hidden_count)" in src
    assert src.count("_prepare_alice_visible_text(") >= 4


def test_talk_answers_are_full_by_default_and_extension_is_idempotent():
    import inspect

    from Applications import sifta_talk_to_alice_widget as talk

    default = inspect.signature(talk.TalkToAliceWidget._prepare_alice_visible_text).parameters[
        "collapse_long"
    ].default
    assert default is False

    class Dummy:
        def __init__(self):
            self._alice_extend_blocks = {
                "k": {"hidden_text": "the continuation", "surface_tag": " [extended]"}
            }
            self.calls = []

        def _append_global_alice_line(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    dummy = Dummy()
    method = talk.TalkToAliceWidget._append_alice_extension_for_key
    method(dummy, "k")
    method(dummy, "k")
    assert len(dummy.calls) == 1
    assert dummy.calls[0][0] == ("the continuation",)
    assert dummy.calls[0][1]["collapse_long"] is False


def test_talk_chat_preserves_manual_scrollback_during_live_append():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    from Applications.sifta_talk_to_alice_widget import _WallpaperTextEdit

    app = QApplication.instance() or QApplication([])
    chat = _WallpaperTextEdit()
    chat.resize(400, 120)
    chat.setPlainText("\n".join(f"row {i}" for i in range(100)))
    chat.show()
    app.processEvents()
    scrollbar = chat.verticalScrollBar()
    scrollbar.setValue(max(0, scrollbar.maximum() // 2))
    before = scrollbar.value()
    chat._sifta_follow_live_tail = False
    cursor = chat.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    chat.setTextCursor(cursor)
    chat.insertPlainText("\nnew live row")
    chat.ensureCursorVisible()
    app.processEvents()
    assert scrollbar.value() == before
    chat.close()
