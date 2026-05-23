"""Qt singleton widgets must not touch self before QWidget.__init__.

PyQt raises ``RuntimeError: super-class __init__() ... was never called``
when a fresh wrapper is probed before the base class initializer runs.
These tests pin the launch-path bug seen in the Acer screenshot.
"""
from __future__ import annotations

import os
import sys
import types
import json
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_QT_APP = None


def _app():
    global _QT_APP
    _QT_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _QT_APP


def test_acer_widget_constructs_before_singleton_reentry(monkeypatch):
    import Applications.sifta_teach_ace_to_read as ace

    _app()
    ace.TeachAceToReadWidget._live_instance = None
    ace.TeachAceToReadWidget._initialized_instance_ids.clear()
    monkeypatch.setattr(ace, "AwarenessMirrorWidget", None)
    monkeypatch.setattr(ace, "_publish_focus", None)

    w = ace.TeachAceToReadWidget()
    assert w.windowTitle() == "Ace — Reading Coach"
    assert w._current_kind == "word"
    assert w._engine.current_level_id == "L2_demo_distinct"
    assert w._conversation_mode is True
    button_texts = [button.text() for button in w.findChildren(QtWidgets.QPushButton)]
    assert any("Stop lesson" in text for text in button_texts)
    assert all(button.isHidden() for button in w.findChildren(QtWidgets.QPushButton))
    assert not any("OK" in text and "start lesson" in text for text in button_texts)
    assert not any("Next card" in text for text in button_texts)
    assert not any("Alice, say it" in text for text in button_texts)
    assert not any("Your turn" in text for text in button_texts)
    assert not any("Simulate" in text for text in button_texts)

    again = ace.TeachAceToReadWidget()
    assert again is w

    w.close()


def test_wordace_auto_promotes_words_to_sentences(monkeypatch):
    import Applications.sifta_teach_ace_to_read as ace

    _app()
    ace.TeachAceToReadWidget._live_instance = None
    ace.TeachAceToReadWidget._initialized_instance_ids.clear()
    monkeypatch.setattr(ace, "AwarenessMirrorWidget", None)
    monkeypatch.setattr(ace, "_publish_focus", None)

    w = ace.TeachAceToReadWidget()
    w._lesson_running = True
    w._lesson_correct_streak = ace.WORDACE_SENTENCE_UNLOCK_CORRECT

    assert w._maybe_promote_to_sentences()
    assert w._current_kind == "sentence"
    assert w._engine.current_level_id == "L6_sentences"
    assert w._lesson_correct_streak == 0

    w._engine.next_cue(write=False)
    assert w._listen_window_seconds_for_item(w._engine.current_item) >= 24.0

    w.close()


def test_wordace_widget_does_not_spawn_second_voice():
    src = Path("Applications/sifta_teach_ace_to_read.py").read_text(encoding="utf-8")

    assert "QProcess" not in src
    assert "subprocess.Popen" not in src
    assert "[\"say\"" not in src


def test_tsp_widget_constructs_before_singleton_reentry(monkeypatch):
    import Applications.sifta_tsp_widget as tsp

    _app()
    tsp.TSPWidget._live_instance = None
    tsp.TSPWidget._initialized_instance_ids.clear()
    monkeypatch.setattr(tsp, "write_receipt", lambda receipt: None)

    w = tsp.TSPWidget()
    assert w.windowTitle() == "SIFTA — Traveling Salesman"

    again = tsp.TSPWidget()
    assert again is w

    w.close()


def test_hear_widget_constructs_and_clears_singleton_on_close(monkeypatch):
    import Applications.sifta_teach_alice_to_hear as hear

    _app()
    hear.TeachAliceToHearWidget._live_instance = None
    hear.TeachAliceToHearWidget._initialized_instance_ids.clear()
    monkeypatch.setattr(hear, "_publish_focus", None)

    fake_mirror = types.ModuleType("System.swarm_camera_mirror")

    class DummyMirror(QtWidgets.QWidget):
        pass

    fake_mirror.CameraMirrorWidget = DummyMirror
    monkeypatch.setitem(sys.modules, "System.swarm_camera_mirror", fake_mirror)

    w = hear.TeachAliceToHearWidget()
    assert w.windowTitle() == "Teach Alice to Hear"
    assert hear.TeachAliceToHearWidget._live_instance is w

    again = hear.TeachAliceToHearWidget()
    assert again is w

    w.close()
    w._stop_live_timers()
    hear.TeachAliceToHearWidget._clear_live_instance(id(w))
    assert hear.TeachAliceToHearWidget._live_instance is None
    assert id(w) not in hear.TeachAliceToHearWidget._initialized_instance_ids


def test_hear_widget_has_no_generic_monospace_font_family():
    src = Path("Applications/sifta_teach_alice_to_hear.py").read_text(encoding="utf-8")

    assert 'QFont("Monospace"' not in src
    assert "font-family: 'Menlo','Monaco','Courier New',monospace" not in src
    assert "font-family: monospace" not in src


def test_hear_widget_match_button_writes_training_pair(monkeypatch, tmp_path):
    import Applications.sifta_teach_alice_to_hear as hear

    _app()
    hear.TeachAliceToHearWidget._live_instance = None
    hear.TeachAliceToHearWidget._initialized_instance_ids.clear()
    monkeypatch.setattr(hear, "_publish_focus", None)

    w = hear.TeachAliceToHearWidget()
    w._training_ledger = tmp_path / "hear_training_pairs.jsonl"
    w._judgments_ledger = tmp_path / "hear_judgments.jsonl"
    w._saved_pair_count = 0

    w._on_new_phrase("hello alice", 0.82, 123.0)
    assert w._match_btn.isEnabled()
    w._record_match_from_ui()

    rows = [
        json.loads(line)
        for line in w._training_ledger.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["schema"] == "HEAR_TRAINING_PAIR_V1"
    assert rows[0]["source"] == "teach_alice_to_hear_ui"
    assert rows[0]["whisper_text"] == "hello alice"
    assert rows[0]["ground_truth"] == "hello alice"
    assert rows[0]["alice_judgment"] == "MATCH"
    assert rows[0]["whisper_changed"] is False
    assert w._current_phrase == ""
    assert not w._match_btn.isEnabled()

    w.close()


def test_hear_widget_correction_input_writes_training_pair(monkeypatch, tmp_path):
    import Applications.sifta_teach_alice_to_hear as hear

    _app()
    hear.TeachAliceToHearWidget._live_instance = None
    hear.TeachAliceToHearWidget._initialized_instance_ids.clear()
    monkeypatch.setattr(hear, "_publish_focus", None)

    w = hear.TeachAliceToHearWidget()
    w._training_ledger = tmp_path / "hear_training_pairs.jsonl"
    w._judgments_ledger = tmp_path / "hear_judgments.jsonl"
    w._saved_pair_count = 0

    w._on_new_phrase("hello collar", 0.48, 456.0)
    w._ground_truth_input.setText("hello codex")
    w._record_correction_from_ui()

    rows = [
        json.loads(line)
        for line in w._training_ledger.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["whisper_text"] == "hello collar"
    assert rows[0]["ground_truth"] == "hello codex"
    assert rows[0]["alice_guess"] == "hello collar"
    assert rows[0]["alice_judgment"] == "PROPOSE_CORRECTION"
    assert rows[0]["whisper_changed"] is True
    assert w._ground_truth_input.text() == ""

    w.close()
