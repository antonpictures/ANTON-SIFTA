#!/usr/bin/env python3
"""
sifta_control_center.py
════════════════════════════════════════════════
A beautiful, glassmorphic Control Center overlay perfectly mimicking macOS.
Bridges directly into macOS hardware (Volume via osascript, Wi-Fi status).
"""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QPoint, QRect, QSize, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QFont, QIcon, QBrush
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QSlider, QPushButton, QGridLayout, QGraphicsDropShadowEffect
)

_REPO = Path(__file__).resolve().parent.parent

# ── Hardware Bridging ────────────────────────────────────────────────────────

def get_macos_volume() -> int:
    try:
        out = subprocess.check_output(
            ["osascript", "-e", "output volume of (get volume settings)"], 
            text=True
        ).strip()
        return int(out)
    except Exception:
        return 50

def set_macos_volume(vol: int):
    try:
        subprocess.run(["osascript", "-e", f"set volume output volume {vol}"])
    except Exception:
        pass

def get_wifi_ssid() -> str:
    try:
        out = subprocess.check_output(
            ["networksetup", "-getairportnetwork", "en0"],
            text=True
        ).strip()
        if "Current Wi-Fi Network" in out:
            return out.split(": ")[1]
        return "Not Connected"
    except Exception:
        return "Unknown"


# ── Styling ──────────────────────────────────────────────────────────────────

GLASS_FRAME_STYLE = """
    QFrame {
        background-color: rgba(30, 30, 40, 180);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 30);
    }
"""

MODULE_CARD_STYLE = """
    QFrame {
        background-color: rgba(60, 60, 75, 120);
        border-radius: 12px;
    }
"""
MODULE_CARD_HOVER = """
    QFrame:hover { background-color: rgba(80, 80, 100, 140); }
"""

BLUE_CIRCLE_STYLE = """
    QLabel {
        background-color: #3275e6;
        border-radius: 14px;
        color: white;
        font-weight: bold;
    }
"""

GRAY_CIRCLE_STYLE = """
    QLabel {
        background-color: rgba(255, 255, 255, 40);
        border-radius: 14px;
        color: white;
        font-weight: bold;
    }
"""


# ── Components ───────────────────────────────────────────────────────────────

class CommRow(QFrame):
    """Row inside the Comms card (Wi-Fi, Bluetooth)."""
    def __init__(self, icon_char: str, title: str, subtitle: str, active: bool = True):
        super().__init__()
        self.setFixedHeight(44)
        self.setStyleSheet("background: transparent; border: none;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(12)
        
        icon_lbl = QLabel(icon_char)
        icon_lbl.setFixedSize(28, 28)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if active:
            icon_lbl.setStyleSheet(BLUE_CIRCLE_STYLE)
        else:
            icon_lbl.setStyleSheet(GRAY_CIRCLE_STYLE)
            
        layout.addWidget(icon_lbl)
        
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 8, 0, 8)
        text_layout.setSpacing(0)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: white; font-weight: 600; font-size: 13px; font-family: -apple-system;")
        
        self.subtitle_lbl = QLabel(subtitle)
        self.subtitle_lbl.setStyleSheet("color: rgba(255,255,255,160); font-size: 11px; font-family: -apple-system;")
        
        text_layout.addWidget(title_lbl)
        text_layout.addWidget(self.subtitle_lbl)
        
        layout.addLayout(text_layout)
        layout.addStretch()


class CustomSlider(QSlider):
    def __init__(self):
        super().__init__(Qt.Orientation.Horizontal)
        self.setStyleSheet("""
            QSlider { background: transparent; height: 26px; }
            QSlider::groove:horizontal {
                background: rgba(255, 255, 255, 40);
                height: 24px;
                border-radius: 12px;
            }
            QSlider::sub-page:horizontal {
                background: rgba(255, 255, 255, 200);
                border-radius: 12px;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 24px;
                height: 24px;
                border-radius: 12px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }
        """)


class GlassWidget(QWidget):
    """The main frameless window floating over the OS."""
    
    def __init__(self, x: int, y: int):
        super().__init__()
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Popup
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setFixedSize(320, 360)
        self.move(x - 320, y)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        base_frame = QFrame()
        base_frame.setStyleSheet(GLASS_FRAME_STYLE)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 4)
        base_frame.setGraphicsEffect(shadow)
        
        frame_layout = QVBoxLayout(base_frame)
        frame_layout.setContentsMargins(12, 12, 12, 12)
        frame_layout.setSpacing(10)
        
        # ── Top Grid (Comms & Media)
        top_grid = QGridLayout()
        top_grid.setContentsMargins(0, 0, 0, 0)
        top_grid.setSpacing(10)
        
        # Comms Card
        comms_card = QFrame()
        comms_card.setStyleSheet(MODULE_CARD_STYLE)
        comms_layout = QVBoxLayout(comms_card)
        comms_layout.setContentsMargins(0, 4, 0, 4)
        comms_layout.setSpacing(0)
        
        ssid = get_wifi_ssid()
        self.wifi_row = CommRow("📶", "Wi-Fi", ssid, active=(ssid != "Not Connected"))
        bluetooth_row = CommRow("B", "Bluetooth", "On", active=True)
        airdrop_row = CommRow("A", "AirDrop", "Contacts Only", active=True)
        
        comms_layout.addWidget(self.wifi_row)
        comms_layout.addWidget(bluetooth_row)
        comms_layout.addWidget(airdrop_row)
        
        top_grid.addWidget(comms_card, 0, 0, 2, 1)
        
        # Media Card
        media_card = QFrame()
        media_card.setStyleSheet(MODULE_CARD_STYLE)
        media_card.setMinimumSize(120, 120)
        
        media_layout = QVBoxLayout(media_card)
        
        m_lbl = QLabel("Not Playing")
        m_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        m_lbl.setStyleSheet("color: rgba(255,255,255,160); font-weight: 500; font-size: 13px; font-family: -apple-system;")
        
        controls = QLabel("◀   ▶   ▶|")
        controls.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        
        media_layout.addStretch()
        media_layout.addWidget(m_lbl)
        media_layout.addWidget(controls)
        media_layout.addStretch()
        
        top_grid.addWidget(media_card, 0, 1, 1, 1)
        
        # Focus Row
        focus_card = QFrame()
        focus_card.setStyleSheet(MODULE_CARD_STYLE)
        focus_layout = QHBoxLayout(focus_card)
        
        f_icon = QLabel("🌙")
        f_icon.setFixedSize(24, 24)
        f_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f_icon.setStyleSheet(GRAY_CIRCLE_STYLE)
        
        f_lbl = QLabel("Focus")
        f_lbl.setStyleSheet("color: white; font-weight: 500; font-size: 13px; font-family: -apple-system;")
        
        focus_layout.addWidget(f_icon)
        focus_layout.addWidget(f_lbl)
        focus_layout.addStretch()
        
        top_grid.addWidget(focus_card, 1, 1, 1, 1)
        
        frame_layout.addLayout(top_grid)
        
        # ── Sliders
        sliders_layout = QVBoxLayout()
        sliders_layout.setSpacing(10)
        
        # Display Slider
        display_card = QFrame()
        display_card.setStyleSheet(MODULE_CARD_STYLE)
        display_layout = QVBoxLayout(display_card)
        display_layout.setContentsMargins(12, 12, 12, 12)
        
        lbl_disp = QLabel("Display")
        lbl_disp.setStyleSheet("color: white; font-weight: bold; font-size: 12px; font-family: -apple-system;")
        self.slider_disp = CustomSlider()
        self.slider_disp.setValue(80) # Mock brightness
        
        display_layout.addWidget(lbl_disp)
        display_layout.addWidget(self.slider_disp)
        
        # Sound Slider
        sound_card = QFrame()
        sound_card.setStyleSheet(MODULE_CARD_STYLE)
        sound_layout = QVBoxLayout(sound_card)
        sound_layout.setContentsMargins(12, 12, 12, 12)
        
        lbl_sound = QLabel("Sound")
        lbl_sound.setStyleSheet("color: white; font-weight: bold; font-size: 12px; font-family: -apple-system;")
        self.slider_sound = CustomSlider()
        self.slider_sound.setRange(0, 100)
        self.slider_sound.setValue(get_macos_volume())
        self.slider_sound.valueChanged.connect(self._on_volume_changed)
        
        sound_layout.addWidget(lbl_sound)
        sound_layout.addWidget(self.slider_sound)
        
        sliders_layout.addWidget(display_card)
        sliders_layout.addWidget(sound_card)
        
        frame_layout.addLayout(sliders_layout)
        
        main_layout.addWidget(base_frame)

    def _on_volume_changed(self, val: int):
        set_macos_volume(val)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Parse position if provided: python script.py <x> <y>
    x, y = 1000, 40
    if len(sys.argv) == 3:
        try:
            x = int(sys.argv[1])
            y = int(sys.argv[2])
        except ValueError:
            pass

    w = GlassWidget(x, y)
    w.show()
    sys.exit(app.exec())
