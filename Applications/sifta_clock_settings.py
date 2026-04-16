#!/usr/bin/env python3
"""
sifta_clock_settings.py

Renders a macOS-style Date & Time settings panel.
Saves preferences to .sifta_state/clock_settings.json.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QRect, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QFont, QBrush, QPen
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QComboBox, QPushButton,
)

_REPO = Path(__file__).resolve().parent.parent
SETTINGS_PATH = _REPO / ".sifta_state" / "clock_settings.json"

DEFAULT_SETTINGS = {
    "show_date": True,
    "show_day_of_week": True,
    "show_am_pm": True,
    "flash_separators": False,
    "show_seconds": False,
    "announce_time": False,
    "announce_interval": "On the hour",
    "announce_voice": "System Voice"
}


def load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r") as f:
                data = json.load(f)
                out = DEFAULT_SETTINGS.copy()
                out.update(data)
                out.pop("style", None)  # legacy Analog/Digital — digital only now
                return out
        except Exception:
            return DEFAULT_SETTINGS.copy()
    return DEFAULT_SETTINGS.copy()


def save_settings(data: dict):
    os.makedirs(SETTINGS_PATH.parent, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)


class SwitchControl(QWidget):
    """A macOS-style toggle switch."""

    def __init__(self, key: str, config: dict, parent=None):
        super().__init__(parent)
        self.key = key
        self.config = config
        self._checked = self.config.get(self.key, False)
        
        self.setFixedSize(36, 20)
        self._thumb_pos = 18 if self._checked else 2
        
        self.animation = QPropertyAnimation(self, b"thumb_pos", self)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.animation.setDuration(150)

    @pyqtProperty(float)
    def thumb_pos(self):
        return self._thumb_pos

    @thumb_pos.setter
    def thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.config[self.key] = self._checked
            save_settings(self.config)
            
            end_pos = 18 if self._checked else 2
            self.animation.setEndValue(end_pos)
            self.animation.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        bg_color = QColor(10, 132, 255) if self._checked else QColor(60, 60, 64)
        p.setBrush(QBrush(bg_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, self.width(), self.height(), 10, 10)
        
        p.setBrush(QBrush(QColor(255, 255, 255)))
        p.drawEllipse(QRect(int(self._thumb_pos), 2, 16, 16))
        p.end()


class SettingsGroup(QFrame):
    """A rounded grouping frame for settings."""
    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            "SettingsGroup { background: #1c1c1f; border-radius: 8px; }"
        )
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 10, 15, 10)
        self.layout.setSpacing(10)

    def add_row(self, label_text: str, widget: QWidget, is_last: bool = False):
        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 0, 4)
        
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: white; font-size: 13px; font-weight: 500;")
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(widget)
        
        self.layout.addLayout(row)
        
        if not is_last:
            div = QFrame()
            div.setFixedHeight(1)
            div.setStyleSheet("background: #333336;")
            self.layout.addWidget(div)


class ClockSettingsApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clock")
        self.setStyleSheet("background: #121214; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;")
        self.setFixedSize(400, 460)
        
        self.config = load_settings()
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        p_font = QFont()
        p_font.setPointSizeF(13)
        self.setFont(p_font)

        # ── Date ────────────────────────
        lbl_date = QLabel("Date")
        lbl_date.setStyleSheet("color: #a1a1a6; font-size: 12px; font-weight: bold;")
        main_layout.addWidget(lbl_date)
        
        g_date = SettingsGroup()
        g_date.add_row("Show date", SwitchControl("show_date", self.config), False)
        g_date.add_row("Show the day of the week", SwitchControl("show_day_of_week", self.config), True)
        main_layout.addWidget(g_date)
        
        main_layout.addSpacing(15)
        
        # ── Time ────────────────────────
        lbl_time = QLabel("Time")
        lbl_time.setStyleSheet("color: #a1a1a6; font-size: 12px; font-weight: bold;")
        main_layout.addWidget(lbl_time)
        
        g_time = SettingsGroup()

        g_time.add_row("Show AM/PM", SwitchControl("show_am_pm", self.config), False)
        g_time.add_row("Flash the time separators", SwitchControl("flash_separators", self.config), False)
        g_time.add_row("Display the time with seconds", SwitchControl("show_seconds", self.config), True)
        main_layout.addWidget(g_time)
        
        main_layout.addSpacing(15)
        
        # ── Announce ────────────────────
        g_ann = SettingsGroup()
        g_ann.add_row("Announce the time", SwitchControl("announce_time", self.config), False)
        
        cb_interval = QComboBox()
        cb_interval.addItems(["On the hour", "On the half hour", "On the quarter hour"])
        cb_interval.setCurrentText(self.config.get("announce_interval", "On the hour"))
        cb_interval.currentTextChanged.connect(self._on_interval_changed)
        cb_interval.setStyleSheet("""
            QComboBox { background: transparent; color: #a1a1a6; border: none; font-size: 13px; }
            QComboBox::drop-down { border: none; }
        """)
        g_ann.add_row("Interval", cb_interval, False)
        
        cb_voice = QComboBox()
        cb_voice.addItems(["System Voice", "Alex", "Samantha"])
        cb_voice.setCurrentText(self.config.get("announce_voice", "System Voice"))
        cb_voice.currentTextChanged.connect(self._on_voice_changed)
        cb_voice.setStyleSheet("""
            QComboBox { background: transparent; color: #a1a1a6; border: none; font-size: 13px; }
            QComboBox::drop-down { border: none; }
        """)
        g_ann.add_row("Voice", cb_voice, True)
        main_layout.addWidget(g_ann)

        main_layout.addStretch()

    def _on_interval_changed(self, text):
        self.config["announce_interval"] = text
        save_settings(self.config)
        
    def _on_voice_changed(self, text):
        self.config["announce_voice"] = text
        save_settings(self.config)

def run():
    app = QApplication(sys.argv)
    w = ClockSettingsApp()
    # Optional argv from SIFTA desktop: x y — anchor under status-bar clock.
    if len(sys.argv) >= 3:
        try:
            x = int(float(sys.argv[1]))
            y = int(float(sys.argv[2]))
            nx, ny = x, y
            scr = app.screenAt(QPoint(nx + w.width() // 2, ny)) or app.primaryScreen()
            if scr is not None:
                ag = scr.availableGeometry()
                if nx + w.width() > ag.right():
                    nx = ag.right() - w.width()
                if ny + w.height() > ag.bottom():
                    ny = ag.bottom() - w.height()
                nx = max(ag.left(), nx)
                ny = max(ag.top(), ny)
            w.move(nx, ny)
        except ValueError:
            pass
    else:
        # Standalone launch: center on primary screen
        screen = app.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            fr = w.frameGeometry()
            fr.moveCenter(geo.center())
            w.move(fr.topLeft())
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run()
