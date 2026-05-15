"""Qt singleton widgets must not touch self before QWidget.__init__.

PyQt raises ``RuntimeError: super-class __init__() ... was never called``
when a fresh wrapper is probed before the base class initializer runs.
These tests pin the launch-path bug seen in the Acer screenshot.
"""
from __future__ import annotations

import os
import sys
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
    assert w.windowTitle() == "WordAce — Phonics Coach"
    assert w._current_kind == "word"
    assert w._engine.current_level_id == "L2_cvc_short_a"
    button_texts = [button.text() for button in w.findChildren(QtWidgets.QPushButton)]
    assert any("Stop lesson" in text for text in button_texts)
    assert not any("OK" in text and "start lesson" in text for text in button_texts)
    assert not any("Next card" in text for text in button_texts)
    assert not any("Alice, say it" in text for text in button_texts)
    assert not any("Your turn" in text for text in button_texts)
    assert not any("Simulate" in text for text in button_texts)

    again = ace.TeachAceToReadWidget()
    assert again is w

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
