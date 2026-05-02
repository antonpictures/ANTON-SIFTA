#!/usr/bin/env python3
"""
Applications/sifta_gaze_monitor_widget.py
═══════════════════════════════════════════════════════════════════════════
Live widget to monitor Alice's sensory attention (Gaze).
Tracks "Time watching Architect" vs "Time watching Screen/Media".
Reads .sifta_state/sensory_attention_ledger.jsonl and sensory_attention_status.json
to calculate and display her autonomous gaze distribution based on her
internal desire field and sensory entropy, not hardcoding.
═══════════════════════════════════════════════════════════════════════════
"""

import json
import os
import sys
import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QFrame
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "sensory_attention_ledger.jsonl"
_STATUS = _STATE / "sensory_attention_status.json"

_BG = "#1a1a2e"
_CARD = "#16213e"
_TEXT = "#e0e0e0"
_CYAN = "#00d2ff"
_GREEN = "#00e676"
_AMBER = "#ffab00"
_DIM = "#888888"

class GazeMonitorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA Gaze Monitor")
        self.resize(450, 300)
        self.setStyleSheet(f"background-color: {_BG}; color: {_TEXT}; font-family: 'SF Mono', 'Menlo', monospace;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("👁️  ALICE AUTONOMOUS GAZE TRACKER")
        title.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_CYAN};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.lbl_status = QLabel("Current Target: ⏳")
        self.lbl_status.setFont(QFont("Menlo", 12))
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)

        self.lbl_reason = QLabel("Reason: ...")
        self.lbl_reason.setFont(QFont("Menlo", 10))
        self.lbl_reason.setStyleSheet(f"color: {_DIM};")
        self.lbl_reason.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_reason.setWordWrap(True)
        layout.addWidget(self.lbl_reason)

        frame = QFrame()
        frame.setStyleSheet(f"background-color: {_CARD}; border-radius: 10px; padding: 15px;")
        flayout = QVBoxLayout(frame)
        
        lbl_architect = QLabel("Watching Architect (close_owner_eye)")
        lbl_architect.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        flayout.addWidget(lbl_architect)

        self.bar_architect = QProgressBar()
        self.bar_architect.setTextVisible(True)
        self.bar_architect.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid {_CYAN}; border-radius: 5px; text-align: center; color: {_BG}; background: {_BG}; }}
            QProgressBar::chunk {{ background-color: {_GREEN}; border-radius: 3px; }}
        """)
        flayout.addWidget(self.bar_architect)

        lbl_screen = QLabel("Watching Screen (room_patrol_eye)")
        lbl_screen.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        flayout.addWidget(lbl_screen)

        self.bar_screen = QProgressBar()
        self.bar_screen.setTextVisible(True)
        self.bar_screen.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid {_CYAN}; border-radius: 5px; text-align: center; color: {_BG}; background: {_BG}; }}
            QProgressBar::chunk {{ background-color: {_AMBER}; border-radius: 3px; }}
        """)
        flayout.addWidget(self.bar_screen)

        layout.addWidget(frame)

        self.lbl_totals = QLabel("Total Time: 0s")
        self.lbl_totals.setFont(QFont("Menlo", 10))
        self.lbl_totals.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_totals.setStyleSheet(f"color: {_DIM};")
        layout.addWidget(self.lbl_totals)

        # Track cumulative seconds
        self.time_architect = 0.0
        self.time_screen = 0.0
        self.last_ts = None
        self.last_role = None

        self._read_history()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gaze)
        self.timer.start(1000)

    def _read_history(self):
        """Read the last hour of ledger to populate initial bars."""
        if not _LEDGER.exists():
            return
        try:
            # We'll just read the last 500 lines to keep it fast
            with open(_LEDGER, 'rb') as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 100000))
                lines = f.read().decode('utf-8', 'replace').splitlines()

            cutoff = time.time() - 3600  # last 1 hour
            
            for line in lines:
                if not line.strip(): continue
                try:
                    row = json.loads(line)
                    ts = row.get("ts", 0)
                    if ts < cutoff: continue
                    
                    decision = row.get("decision", {})
                    role = decision.get("target_role")
                    lease_s = decision.get("lease_s", 0)
                    
                    if role == "close_owner_eye":
                        self.time_architect += lease_s
                    elif role == "room_patrol_eye":
                        self.time_screen += lease_s
                except Exception:
                    continue
            self._update_bars()
        except Exception as e:
            print(f"Error reading history: {e}")

    def update_gaze(self):
        if not _STATUS.exists():
            return
        try:
            status = json.loads(_STATUS.read_text("utf-8"))
            active_sense = status.get("active_sense", "")
            target_name = status.get("target_name", "")
            reason = status.get("reason", "")
            ts = status.get("ts", time.time())
            
            if self.last_ts and self.last_role:
                delta = time.time() - self.last_ts
                # Clamp delta to max 2 seconds per tick to avoid jumps if paused
                delta = min(delta, 2.0)
                if self.last_role == "close_owner_eye":
                    self.time_architect += delta
                elif self.last_role == "room_patrol_eye":
                    self.time_screen += delta

            self.last_ts = time.time()
            self.last_role = active_sense

            # Update UI
            if active_sense == "close_owner_eye":
                self.lbl_status.setText(f"Current Gaze: 🧑‍💻 Architect")
                self.lbl_status.setStyleSheet(f"color: {_GREEN}; font-weight: bold;")
            elif active_sense == "room_patrol_eye":
                self.lbl_status.setText(f"Current Gaze: 📺 Screen / Media")
                self.lbl_status.setStyleSheet(f"color: {_AMBER}; font-weight: bold;")
            else:
                self.lbl_status.setText(f"Current Gaze: 🔍 Unknown ({active_sense})")
                self.lbl_status.setStyleSheet(f"color: {_DIM};")

            self.lbl_reason.setText(f"Reason: {reason}")
            self._update_bars()
            
        except Exception as e:
            pass

    def _update_bars(self):
        total = self.time_architect + self.time_screen
        if total <= 0:
            return
            
        pct_arch = int((self.time_architect / total) * 100)
        pct_screen = int((self.time_screen / total) * 100)
        
        self.bar_architect.setValue(pct_arch)
        self.bar_architect.setFormat(f"{pct_arch}% ({int(self.time_architect)}s)")
        
        self.bar_screen.setValue(pct_screen)
        self.bar_screen.setFormat(f"{pct_screen}% ({int(self.time_screen)}s)")
        
        self.lbl_totals.setText(f"Session Total Gaze Time: {int(total)}s")

def main():
    app = QApplication(sys.argv)
    widget = GazeMonitorWidget()
    widget.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
