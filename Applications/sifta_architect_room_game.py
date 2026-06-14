#!/usr/bin/env python3
"""
sifta_architect_room_game.py — The Architect Room (Science App / Game)
======================================================================
Predator v7 celebration science app.
Narrative: terminals, graphs, choice widgets.
Stigmergic hooks: publish_focus / append JSONL receipts.
"""
from __future__ import annotations

"""SIFTA Architect Room Game — stigmergic organ for Alice body."""
import sys
from pathlib import Path

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_app_focus import publish_focus

class ArchitectRoomGame(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("The Architect Room")
        self.setStyleSheet("background-color: #0b1020; color: #c0caf5;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("The Architect Room")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #00ffc8;")
        layout.addWidget(title)
        
        desc = QLabel("Problem is choice. Sum of a remainder of an unbalanced equation.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("font-size: 14px; color: #7aa2f7;")
        layout.addWidget(desc)
        
        self.btn_choice = QPushButton("Make a Choice")
        self.btn_choice.setStyleSheet(
            "background: #1a1b26; border: 1px solid #414868; padding: 10px; border-radius: 6px;"
        )
        self.btn_choice.clicked.connect(self._on_choice)
        layout.addWidget(self.btn_choice, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()
        
    def _on_choice(self):
        publish_focus("The Architect Room", "User made a choice in the Architect Room", tab="Choice")


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        w = ArchitectRoomGame()
        w.resize(800, 600)
        w.show()
        sys.exit(app.exec())
    except Exception as _err:
        import traceback
        traceback.print_exc()
        sys.exit(1)
