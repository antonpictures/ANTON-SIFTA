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
