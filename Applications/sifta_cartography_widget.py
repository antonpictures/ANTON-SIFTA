#!/usr/bin/env python3
"""
sifta_cartography_widget.py — The Subconscious Dashboard (Blackboard 2.0)
═════════════════════════════════════════════════════════════════════════
Visual telemetry for SIFTA's stigmergic biology.
Renders the Mycelial Genome pressure field, heatwave thresholds,
and Mutation Governor blockages continuously without locking the main thread.

SIFTA Non-Proliferation Public License applies.
"""

import sys
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QListWidgetItem, QProgressBar, QFrame, QSplitter
)
from PyQt6.QtCore import Qt, QTimer

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_GENOME_STATE = _STATE_DIR / "mycelial_genome.json"
_GOVERNOR_STATE = _STATE_DIR / "mutation_governor.json"


class CartographyWidget(QWidget):
    """Visualizes the invisible stigmergic structures of SIFTA."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CARTOGRAPHY — Blackboard 2.0")
        self.setStyleSheet("background-color: #0c0c11; color: #a9b1d6; font-family: monospace;")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # ─── HEADER: Heatwave & Density ───
        self.header_frame = QFrame()
        self.header_layout = QVBoxLayout(self.header_frame)
        self.header_frame.setStyleSheet("border: 1px solid #3b4261; border-radius: 4px; padding: 5px;")
        
        self.lbl_status = QLabel("STATUS: [ ❄️ NORMAL ]")
        self.lbl_status.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 16px;")
        
        self.lbl_stats = QLabel("Active Fields: 0 / 500  |  Total Resonance: 0.00")
        self.lbl_stats.setStyleSheet("color: #9ece6a;")
        
        self.progress_density = QProgressBar()
        self.progress_density.setRange(0, 100)
        self.progress_density.setValue(0)
        self.progress_density.setTextVisible(True)
        self.progress_density.setFormat("Density: %p%")
        self.progress_density.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3b4261;
                border-radius: 4px;
                text-align: center;
                color: #c0caf5;
            }
            QProgressBar::chunk {
                background-color: #2ac3de;
            }
        """)

        self.header_layout.addWidget(self.lbl_status)
        self.header_layout.addWidget(self.progress_density)
        self.header_layout.addWidget(self.lbl_stats)
        self.layout.addWidget(self.header_frame)
        
        # ─── BODY: Splitter (Resonance Field | Governor Blocks) ───
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Genome Resonance 
        self.panel_genome = QWidget()
        self.layout_genome = QVBoxLayout(self.panel_genome)
        self.lbl_genome_title = QLabel("MYCELIAL GENOME 🧬")
        self.lbl_genome_title.setStyleSheet("color: #bb9af7; font-weight: bold;")
        self.list_resonance = QListWidget()
        self.list_resonance.setStyleSheet("background: #1a1b26; border: 1px solid #3b4261;")
        self.layout_genome.addWidget(self.lbl_genome_title)
        self.layout_genome.addWidget(self.list_resonance)
        
        # Right: Mutation Governor 
        self.panel_gov = QWidget()
        self.layout_gov = QVBoxLayout(self.panel_gov)
        self.lbl_gov_title = QLabel("MUTATION GOVERNOR 🛑")
        self.lbl_gov_title.setStyleSheet("color: #f7768e; font-weight: bold;")
        self.list_blocks = QListWidget()
        self.list_blocks.setStyleSheet("background: #1a1b26; border: 1px solid #3b4261;")
        self.layout_gov.addWidget(self.lbl_gov_title)
        self.layout_gov.addWidget(self.list_blocks)

        self.splitter.addWidget(self.panel_genome)
        self.splitter.addWidget(self.panel_gov)
        self.layout.addWidget(self.splitter)
        
        # ─── POLLER TICK ───
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_telemetry)
        self.timer.start(2000)  # Sweep every 2 seconds
        
        self._poll_telemetry()
        
    def _poll_telemetry(self):
        self._poll_genome()
        self._poll_governor()
        
    def _poll_genome(self):
        if not _GENOME_STATE.exists():
            return
            
        try:
            raw = _GENOME_STATE.read_text()
            data = json.loads(raw)
        except Exception:
            return
            
        resonance_map = data.get("resonance", {})
        heatwave = data.get("heatwave_active", False)
        capacity = data.get("capacity", 500)
        density = data.get("density", 0.0)
        
        # Update Header Stats
        pct = min(100, int(density * 100))
        self.progress_density.setValue(pct)
        
        # Toggle Heatwave Visuals
        if heatwave:
            self.lbl_status.setText(f"STATUS: [ 🔥 HEATWAVE #{data.get('heatwave_count', 0)} ]")
            self.lbl_status.setStyleSheet("color: #f7768e; font-weight: bold; font-size: 16px;")
            self.progress_density.setStyleSheet("""
                QProgressBar { border: 1px solid #f7768e; border-radius: 4px; text-align: center; color: white; }
                QProgressBar::chunk { background-color: #f7768e; }
            """)
        else:
            self.lbl_status.setText("STATUS: [ ❄️ NORMAL ]")
            self.lbl_status.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 16px;")
            self.progress_density.setStyleSheet("""
                QProgressBar { border: 1px solid #3b4261; border-radius: 4px; text-align: center; color: #c0caf5; }
                QProgressBar::chunk { background-color: #2ac3de; }
            """)
            
        total_res = sum(resonance_map.values())
        self.lbl_stats.setText(f"Active Fields: {len(resonance_map)} / {capacity}  |  Total Resonance: {total_res:.2f}")

        # Update List
        self.list_resonance.clear()
        # Sort by highest resonance
        sorted_files = sorted(resonance_map.items(), key=lambda x: -x[1])
        for path, res in sorted_files[:40]: # Top 40
            item = QListWidgetItem(f"[{res:06.2f}] {Path(path).name}")
            
            # Glow logic (high resonance is bright cyan, dying is dim blue)
            if res > 10.0:
                item.setForeground(Qt.GlobalColor.cyan)
            elif res < 0.5:
                item.setForeground(Qt.GlobalColor.darkGray)
            else:
                item.setForeground(Qt.GlobalColor.white)
                
            item.setToolTip(path)
            self.list_resonance.addItem(item)
            
    def _poll_governor(self):
        if not _GOVERNOR_STATE.exists():
            return
            
        try:
            raw = _GOVERNOR_STATE.read_text()
            data = json.loads(raw)
        except Exception:
            return
            
        # Draw the block state
        self.list_blocks.clear()
        
        # Mutations blocked recently or budget constraints
        budgets = data.get("file_budgets", {})
        blocks = 0
        
        for path, budget in budgets.items():
            if budget <= 1:
                item = QListWidgetItem(f"🔒 BUDGET LOW: {Path(path).name}")
                item.setForeground(Qt.GlobalColor.yellow)
                self.list_blocks.addItem(item)
                blocks += 1
                
        # Mock global stats
        global_cap = data.get("global_mutations_quota", 10)
        item = QListWidgetItem(f"🌍 GLOBAL QUOTA REMAINING: {global_cap}/10")
        item.setForeground(Qt.GlobalColor.green if global_cap > 3 else Qt.GlobalColor.red)
        self.list_blocks.insertItem(0, item)

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = CartographyWidget()
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec())
