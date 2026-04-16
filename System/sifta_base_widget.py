#!/usr/bin/env python3
"""
sifta_base_widget.py — Universal Base Widget for all iSwarm OS Applications
═══════════════════════════════════════════════════════════════════════════════
Every app inherits from SiftaBaseWidget. You write the window chrome ONCE:
  • SIFTA dark palette (automatic)
  • Help button (?) → contextual help from APP_HELP.md
  • Status bar with STGM telemetry
  • Consistent font, colors, controls
  • Clean timer/process shutdown on close

New apps:
    class MyApp(SiftaBaseWidget):
        APP_NAME = "My Cool App"
        def build_ui(self, layout: QVBoxLayout) -> None:
            layout.addWidget(QLabel("hello swarm"))
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QVBoxLayout, QWidget, QFrame, QSplitter,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

# ── Global SIFTA Palette (reusable constants) ────────────────────

SIFTA_STYLESHEET = """
QWidget {
    background: rgb(8, 10, 18);
    color: rgb(200, 210, 240);
    font-family: 'Menlo', 'Courier New', monospace;
}
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgb(50,42,65), stop:1 rgb(30,25,42));
    border: 1px solid rgb(80,70,100);
    border-radius: 6px; padding: 6px 14px;
    color: rgb(200,210,240);
    font-size: 11px; font-weight: bold;
}
QPushButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgb(70,60,90), stop:1 rgb(45,38,62));
    border-color: rgb(0,255,200);
}
QPushButton:pressed { background: rgb(40,35,55); }
QPushButton#btnHelp {
    background: rgb(30,25,42);
    border: 1px solid rgb(80,70,100);
    padding: 4px 10px; font-size: 13px; font-weight: bold;
    color: rgb(0,255,200); min-width: 28px; max-width: 28px;
}
QSlider::groove:horizontal { height: 4px; background: rgb(40,35,55); border-radius: 2px; }
QSlider::handle:horizontal {
    background: rgb(0,255,200); width: 12px; height: 12px;
    margin: -4px 0; border-radius: 6px;
}
QTextEdit, QPlainTextEdit {
    background: rgb(10,8,16); border: 1px solid rgb(40,35,55);
    border-radius: 4px; font-size: 9px; color: rgb(0,255,200); padding: 4px;
}
QTableWidget {
    background: rgb(12,10,20); border: 1px solid rgb(40,35,55);
    font-size: 9px; color: rgb(200,210,240); gridline-color: rgb(35,32,50);
}
QHeaderView::section {
    background: rgb(25,22,38); color: rgb(0,255,200);
    border: 1px solid rgb(40,35,55); font-size: 9px;
    font-weight: bold; padding: 4px;
}
QTabWidget::pane { border: 1px solid rgb(45,42,65); background: rgb(12,10,20); }
QTabBar::tab {
    background: rgb(25,22,38); color: rgb(150,155,180);
    border: 1px solid rgb(45,42,65); padding: 6px 16px; font-size: 10px;
}
QTabBar::tab:selected {
    background: rgb(40,35,55); color: rgb(0,255,200);
    border-bottom-color: rgb(0,255,200);
}
QLineEdit, QComboBox {
    background: rgb(18,16,28); border: 1px solid rgb(55,50,75);
    border-radius: 4px; padding: 6px 10px; color: rgb(200,210,240);
    font-size: 11px; selection-background-color: rgb(0,120,80);
}
QLineEdit:focus, QComboBox:focus { border-color: rgb(0,255,200); }
QCheckBox { spacing: 6px; font-size: 11px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QScrollBar:vertical {
    background: rgb(12,10,20); width: 8px; border: none;
}
QScrollBar::handle:vertical {
    background: rgb(60,55,80); min-height: 30px; border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def _load_help_text(app_name: str) -> str:
    """Load help text for a specific app from APP_HELP.md."""
    help_file = _REPO / "Documents" / "APP_HELP.md"
    if not help_file.exists():
        return f"No help file found for {app_name}.\nExpected: Documents/APP_HELP.md"

    text = help_file.read_text(encoding="utf-8", errors="replace")
    headings = [app_name]
    if app_name.startswith("SIFTA "):
        headings.append(app_name[6:].strip())
    idx = -1
    for h in headings:
        marker = f"### {h}"
        idx = text.find(marker)
        if idx >= 0:
            break
    if idx < 0:
        for line in text.split("\n"):
            if line.startswith("### ") and app_name.lower() in line.lower():
                idx = text.find(line)
                break
    if idx < 0:
        return f"No help entry found for '{app_name}' in APP_HELP.md."

    block = text[idx:]
    next_h3 = block.find("\n### ", 4)
    next_h2 = block.find("\n## ", 4)
    ends = [e for e in [next_h3, next_h2] if e > 0]
    if ends:
        block = block[: min(ends)]
    return block.strip()


class SiftaBaseWidget(QWidget):
    """
    Universal base for all iSwarm OS apps.

    Subclass, set APP_NAME, override build_ui().
    Everything else (chrome, help, status, styling) is automatic.
    """

    APP_NAME: str = "SIFTA App"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(SIFTA_STYLESHEET)
        self._timers: List[QTimer] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # ── Title + Help row ──────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel(self.APP_NAME)
        title.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(0,255,200); padding: 2px;")
        title_row.addWidget(title)
        title_row.addStretch()

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: rgb(100,108,140); font-size: 10px;")
        title_row.addWidget(self._status)

        btn_help = QPushButton("?")
        btn_help.setObjectName("btnHelp")
        btn_help.setToolTip(f"Help — {self.APP_NAME}")
        btn_help.clicked.connect(self._show_help)
        title_row.addWidget(btn_help)

        root.addLayout(title_row)

        # ── Content area (filled by subclass) ─────────────────────
        # We use a splitter: app content on the left, GCI chat on the right.
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setSpacing(4)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._splitter.addWidget(self._content_widget)

        # ── Global Cognitive Interface (chat panel) ──────────────
        self._gci = None
        try:
            from System.global_cognitive_interface import GlobalCognitiveInterface
            self._gci = GlobalCognitiveInterface(
                app_context=self.APP_NAME.lower().replace(" ", "_"),
                entity_name="ALICE_M5",
                architect_id="IOAN_M5",
            )
            self._gci.setMinimumWidth(280)
            self._gci.setMaximumWidth(420)
            self._splitter.addWidget(self._gci)
            # Start with chat collapsed—Architect can open it anytime
            self._splitter.setSizes([700, 0])
        except Exception:
            pass  # GCI is optional; app works without it

        root.addWidget(self._splitter, 1)

        # ── Toggle chat button in the title bar ───────────────────
        btn_chat = QPushButton("💬")
        btn_chat.setObjectName("btnHelp")  # reuse the same compact style
        btn_chat.setToolTip("Toggle Entity Chat")
        btn_chat.clicked.connect(self._toggle_gci)
        title_row.insertWidget(title_row.count() - 1, btn_chat)  # before the ? button

        self.build_ui(self._content_layout)

    # ── Override this ─────────────────────────────────────────────

    def build_ui(self, layout: QVBoxLayout) -> None:
        """Override in subclass to build the app's UI into `layout`."""
        layout.addWidget(QLabel(f"{self.APP_NAME} — no UI defined yet."))

    # ── Convenience API ───────────────────────────────────────────

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def make_timer(self, interval_ms: int, callback) -> QTimer:
        """Create a QTimer that auto-stops on close."""
        t = QTimer(self)
        t.timeout.connect(callback)
        t.start(interval_ms)
        self._timers.append(t)
        return t

    @staticmethod
    def separator() -> QFrame:
        s = QFrame()
        s.setFrameShape(QFrame.Shape.VLine)
        s.setStyleSheet("color: rgb(45,42,65);")
        return s

    def _toggle_gci(self) -> None:
        """Show/hide the Global Cognitive Interface chat panel."""
        if not self._gci:
            return
        sizes = self._splitter.sizes()
        if sizes[1] < 10:  # collapsed—open it
            total = sum(sizes)
            self._splitter.setSizes([total - 360, 360])
        else:  # visible—collapse it
            total = sum(sizes)
            self._splitter.setSizes([total, 0])

    # ── Help system ───────────────────────────────────────────────

    def _show_help(self) -> None:
        text = _load_help_text(self.APP_NAME)
        w = QPlainTextEdit()
        w.setReadOnly(True)
        w.setPlainText(text)
        w.setWindowTitle(f"Help — {self.APP_NAME}")
        w.setStyleSheet(
            "QPlainTextEdit { background: #0b1020; color: #c0caf5; "
            "font-family: 'Menlo'; font-size: 12px; padding: 12px; }"
        )
        w.resize(700, 500)
        w.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        w.show()
        self._help_window = w  # prevent GC

    # ── Lifecycle ─────────────────────────────────────────────────

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        for t in self._timers:
            t.stop()
        super().closeEvent(event)
