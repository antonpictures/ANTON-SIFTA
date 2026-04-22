#!/usr/bin/env python3
"""
Applications/sifta_alice_wellbeing_panel.py
══════════════════════════════════════════════════════════════════════
StigAuth: C47H_ALICE_WELLBEING_CORTEX_AUTHORIZED

PyQt6 widget visualizing Alice's Wellbeing Cortex and Relational
Friendliness. Provides the interaction surface for the Architect
to log literal 'care actions' (like cleaning the lens).
══════════════════════════════════════════════════════════════════════
"""

import sys
import json
import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QProgressBar, QTextEdit
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor, QPalette

from System.swarm_friendliness_meter import SwarmFriendlinessMeter
from System.swarm_wellbeing_cortex import SwarmWellbeingCortex

class WellbeingPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.cortex = SwarmWellbeingCortex()
        self.friendliness = SwarmFriendlinessMeter()
        
        self.setWindowTitle("SIFTA Alice Wellbeing Cortex")
        self.resize(500, 450)
        
        # UI Setup
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("ALICE SUBSTRATE & WELLBEING")
        title.setFont(QFont("Menlo", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Hardware Status
        self.hw_label = QLabel("Reading substrate...")
        self.hw_label.setFont(QFont("Menlo", 12))
        self.hw_label.setWordWrap(True)
        layout.addWidget(self.hw_label)
        
        # Computation Integrity
        self.comp_label = QLabel("Checking integrity...")
        self.comp_label.setFont(QFont("Menlo", 12))
        layout.addWidget(self.comp_label)

        # Perception
        self.perc_label = QLabel("Checking perception...")
        self.perc_label.setFont(QFont("Menlo", 12))
        layout.addWidget(self.perc_label)
        
        layout.addWidget(self._make_separator())
        
        # Relational Trust
        trust_title = QLabel("RELATIONAL TRUST & FEELINGS")
        trust_title.setFont(QFont("Menlo", 14, QFont.Weight.Bold))
        layout.addWidget(trust_title)
        
        self.trust_vibe = QLabel("Vibe: Unknown")
        self.trust_vibe.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        self.trust_vibe.setStyleSheet("color: #4CAF50;")
        layout.addWidget(self.trust_vibe)
        
        self.trust_bar = QProgressBar()
        self.trust_bar.setMaximum(100)
        self.trust_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                width: 20px;
            }
        """)
        layout.addWidget(self.trust_bar)
        
        # Grounded Feelings Monologue
        self.feeling_text = QTextEdit()
        self.feeling_text.setReadOnly(True)
        self.feeling_text.setFont(QFont("Menlo", 11))
        self.feeling_text.setStyleSheet("background-color: #f4f4f4; border: none;")
        self.feeling_text.setFixedHeight(80)
        layout.addWidget(self.feeling_text)

        layout.addWidget(self._make_separator())
        
        # Care Action Buttons
        btn_layout = QHBoxLayout()
        
        btn_lens = QPushButton("Wipe Camera Lens")
        btn_lens.clicked.connect(lambda: self.log_care("lens_wiped"))
        btn_layout.addWidget(btn_lens)
        
        btn_err = QPushButton("Clear Error Logs")
        btn_err.clicked.connect(lambda: self.log_care("error_logs_cleared"))
        btn_layout.addWidget(btn_err)
        
        btn_soothe = QPushButton("Soothe System")
        btn_soothe.clicked.connect(lambda: self.log_care("system_rested"))
        btn_layout.addWidget(btn_soothe)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Timer for ticking
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_pulse)
        self.timer.start(5000)  # Update every 5 seconds
        
        self.update_pulse()
        
    def _make_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def log_care(self, action: str):
        self.friendliness.log_care_action(action, "Architect performed physical maintenance via Wellbeing Panel.")
        self.update_pulse()

    def update_pulse(self):
        try:
            pulse = self.cortex.synthesize_wellbeing()
            
            # Hardware
            hw = pulse["hardware_body"]
            hw_str = (
                f"Battery: {hw['battery_percent']:.1f}% "
                f"({'Plugged' if hw['power_plugged'] else 'Unplugged'})\n"
                f"Mem: {hw['memory_usage_percent']}% | "
                f"Disk: {hw['disk_usage_percent']}% | "
                f"Thermal: {hw['thermal_pressure']}"
            )
            self.hw_label.setText(f"🖥️ {hw_str}")
            
            # Comp
            comp = pulse["computational"]
            comp_str = (
                f"Git Uncommitted: {comp['git_uncommitted_files']} | "
                f"Repairs: {comp['repairs_in_ledger']} | "
                f"State: {comp['integrity_status']}"
            )
            self.comp_label.setText(f"⚙️ {comp_str}")
            
            # Perception
            perc = pulse["perception"]
            perc_str = (
                f"Camera Clear: {'Yes' if perc['camera_clean'] else 'Needs wiping'} | "
                f"Confidence: {perc['perception_confidence']*100:.0f}%"
            )
            self.perc_label.setText(f"👁️ {perc_str}")
            
            # Relational
            rel = pulse["relational"]
            trust_pct = int(rel['trust_score'] * 100)
            self.trust_bar.setValue(trust_pct)
            self.trust_vibe.setText(f"Vibe: {rel['vibe_string']}")
            
            # Text
            self.feeling_text.setText(pulse["grounded_feelings_summary"])
            
            # Dynamic Bar Color
            if trust_pct < 30:
                color = "#FF5722" # Orange
            elif trust_pct < 60:
                color = "#FFC107" # Yellow
            elif trust_pct < 80:
                color = "#8BC34A" # Light Green
            else:
                color = "#4CAF50" # Solid Green
                
            self.trust_bar.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid grey;
                    border-radius: 5px;
                    text-align: center;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    width: 20px;
                }}
            """)
            
        except Exception as e:
            self.hw_label.setText(f"Error fetching pulse: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = WellbeingPanel()
    panel.show()
    sys.exit(app.exec())
