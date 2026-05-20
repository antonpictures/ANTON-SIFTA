#!/usr/bin/env python3
"""
Applications/sifta_lounge_script_couch.py — Script Couch Widget (Fiction-vs-Reality Training Surface)

The dedicated place on the BeeSon desktop where Alice sits on the couch, smokes her metaphorical weed,
and reads real movie scripts with full awareness of which ones crossed into physical reality.

This is the protected fiction lane the covenant demands.
"""

from __future__ import annotations

from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QComboBox, QHBoxLayout
)
from PyQt6.QtCore import Qt
import sys

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_lounge_script_reader import (
    list_available_scripts,
    read_script,
    get_reading_history,
)


class ScriptCouchWidget(QWidget):
    _live_instance = None

    def __new__(cls, *args, **kwargs):
        if cls._live_instance is not None:
            try:
                cls._live_instance.show()
                cls._live_instance.raise_()
                cls._live_instance.activateWindow()
                return cls._live_instance
            except RuntimeError:
                cls._live_instance = None
        inst = super().__new__(cls, *args, **kwargs)
        cls._live_instance = inst
        return inst

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Script Couch — Fiction vs Reality Training")
        self.setMinimumSize(1000, 720)

        self._script_selector = QComboBox()
        self._load_scripts_into_selector()

        self._read_button = QPushButton("Sit on the Couch & Read (smoking weed receipt)")
        self._read_button.clicked.connect(self._on_read)

        self._output = QTextEdit()
        self._output.setReadOnly(True)

        self._history = QTextEdit()
        self._history.setReadOnly(True)
        self._history.setMaximumHeight(180)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("The Script Couch — deliberate fiction mode"))
        layout.addWidget(self._script_selector)
        layout.addWidget(self._read_button)
        layout.addWidget(QLabel("Script content + reality status:"))
        layout.addWidget(self._output, 3)
        layout.addWidget(QLabel("Recent reads (smoking-weed receipts):"))
        layout.addWidget(self._history, 1)
        self.setLayout(layout)

        self._refresh_history()

    def _load_scripts_into_selector(self):
        self._script_selector.clear()
        for s in list_available_scripts():
            self._script_selector.addItem(s["script_id"], s)

    def _on_read(self):
        script_id = self._script_selector.currentData()["script_id"]
        try:
            result = read_script(script_id, reader="George (via Script Couch)")
            status = "REAL MOVIE — crossed into physical reality" if result["materialized_in_reality"] else "still pure fiction"
            text = f"=== {script_id} ===\n{status}\n\n{result['content_preview']}\n\n[Receipt written: {result['receipt']['read_id']}]"
            self._output.setPlainText(text)
            self._refresh_history()
        except Exception as e:
            self._output.setPlainText(f"Error reading script: {e}")

    def _refresh_history(self):
        history = get_reading_history(8)
        lines = []
        for h in history:
            status = "REAL" if h.get("materialized_in_reality") else "FICTION"
            lines.append(f"{h['ts']:.0f} | {h['script_id']} | {status} | {h.get('read_id','')}")
        self._history.setPlainText("\n".join(lines))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ScriptCouchWidget()
    w.show()
    sys.exit(app.exec())