#!/usr/bin/env python3
"""
tests/test_sifta_architect_room_game.py
Smoke test for The Architect Room widget.
"""
import sys
from pathlib import Path
import pytest
from PyQt6.QtWidgets import QApplication

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from Applications.sifta_architect_room_game import ArchitectRoomGame

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

def test_architect_room_import_and_instantiate(qapp):
    widget = ArchitectRoomGame()
    assert widget.windowTitle() == "The Architect Room"
    assert widget.btn_choice.text() == "Make a Choice"
