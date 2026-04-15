#!/usr/bin/env python3
"""
sifta_broadcaster_widget.py — The Swarm Broadcaster
═══════════════════════════════════════════════════
A dedicated marketing studio that uses local Swarm intelligence
to generate highly-converting, 60-second TikTok/Reels promo scripts.
Because nobody installs an OS for the architecture—they install for the demo.
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QPlainTextEdit, QWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor

from System.sifta_base_widget import SiftaBaseWidget


# ── Structured Prompts ────────────────────────────────────────────────────────

TOPICS = {
    "The Ghost IDE (Passive Code Healing)": (
        "Focus on 'sifta_watcher.py'. It silently watches your directory. "
        "The second you hit save with a Python syntax error, it immediately dispatches an autonomous Drone "
        "to surgically fix the file in the background before you even notice. "
        "It acts like a Guardian Angel for your unhandled exceptions."
    ),
    "The Factory (Chat-to-App Generation)": (
        "Focus on the 'Swimmer App Factory'. "
        "Show a user typing 'build: a pomodoro timer' into the OS chat. "
        "The OS doesn't just reply with code. It generates the app, validates the Abstract Syntax Tree, "
        "checks for security imports, tests it for runtime crashes, and then automatically registers it "
        "in your Start Menu. Zero friction. 'It's done. Restart your OS.'"
    ),
    "Warren Buffett Mode (Compute Economy)": (
        "Focus on the local Swarm Economy and Proof-of-Useful-Compute. "
        "Whenever a Swimmer (like ALICE_M5) successfully fixes your code or builds an app, "
        "they earn 'STGM' crypto tokens. The OS natively displays your wallet on the top HUD. "
        "It feels like the machine is actually paying you for running local compute. "
        "Show the number ticking up."
    )
}

BROADCAST_PROMPT = """You are a highly viral, energetic TikTok/YouTube Shorts scriptwriter.
Write a 60-second video script clearly promoting the SIFTA Swarm OS.

Subject to focus on:
{topic_description}

FORMAT REQUIREMENTS:
- **Hook (0-3s):** The visual/verbal attention grabber (e.g., "Stop manually writing code...")
- **Visual Directions:** Write clear brackets `[Show the terminal fixing the file]` telling the Architect exactly what to record.
- **Body (3-45s):** Fast, punchy explanation of what is happening on screen and why it's insane.
- **CTA (45-60s):** Call to Action. "Fork the SIFTA OS right now."

Keep it highly engaging, modern, and perfectly suited for short-form developers. Do not use generic corporate language. Make it punchy.
"""

# ── Worker Thread ────────────────────────────────────────────────────────────

class ScriptGeneratorWorker(QThread):
    chunk_ready = pyqtSignal(str)
    completed = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, topic_key: str, model: str = "gemma4:latest"):
        super().__init__()
        self.topic_key = topic_key
        self.model = model

    def run(self):
        desc = TOPICS.get(self.topic_key, "")
        prompt = BROADCAST_PROMPT.format(topic_description=desc)

        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "temperature": 0.7,
        }
        
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            
            with urllib.request.urlopen(req, timeout=60) as resp:
                for raw_line in resp:
                    raw_line = raw_line.strip()
                    if not raw_line: continue
                    try:
                        chunk = json.loads(raw_line)
                    except json.JSONDecodeError: continue

                    token = chunk.get("response", "")
                    
                    if "<think>" in token: continue
                    if "</think>" in token: continue
                    
                    self.chunk_ready.emit(token)
                    
                    if chunk.get("done"):
                        break
                        
            # Mint STGM for marketing generation
            try:
                from inference_economy import mint_reward
                mint_reward(
                    agent_id="M5SIFTA_BODY",
                    action=f"MARKETING_STUDIO::{self.topic_key[:15]}",
                    file_repaired="Applications/sifta_broadcaster_widget.py",
                    model=self.model,
                )
            except Exception as e:
                print(f"[BROADCASTER] Mint failed: {e}")
                
            self.completed.emit()
            
        except Exception as e:
            self.error_signal.emit(f"Swarm Generation Failed: {e}")

# ── The Application ──────────────────────────────────────────────────────────

class BroadcasterWidget(SiftaBaseWidget):
    APP_NAME = "Swarm Broadcaster"

    def build_ui(self, layout: QVBoxLayout) -> None:
        self.set_status("Broadcaster Studio Online. Awaiting Topic Selection.")
        
        # Headers
        desc_lbl = QLabel("Select a viral primitive. The Swarm will generate a highly optimized 60-second video script for you to record and publish.")
        desc_lbl.setStyleSheet("color: #a9b1d6; font-size: 13px;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)
        
        # Controls Row
        btn_row = QHBoxLayout()
        
        topic_lbl = QLabel("Focus Hook:")
        topic_lbl.setStyleSheet("color: #c0caf5; font-weight: bold;")
        btn_row.addWidget(topic_lbl)
        
        self.topic_selector = QComboBox()
        self.topic_selector.addItems(list(TOPICS.keys()))
        self.topic_selector.setStyleSheet(
            "QComboBox { background-color: #1a1b26; color: #a9b1d6; border: 1px solid #414868; border-radius: 4px; padding: 5px; }"
        )
        btn_row.addWidget(self.topic_selector, 1)
        
        self.generate_btn = QPushButton("🎬 Generate Viral Script")
        self.generate_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #10b981, stop:1 #059669); color: white; border: none; }"
            "QPushButton:hover { background: #34d399; }"
            "QPushButton:disabled { background: #374151; color: #9ca3af; }"
        )
        self.generate_btn.setMinimumHeight(32)
        self.generate_btn.clicked.connect(self._start_generation)
        btn_row.addWidget(self.generate_btn)
        
        layout.addLayout(btn_row)
        
        # Script Editor Area
        self.script_editor = QPlainTextEdit()
        self.script_editor.setReadOnly(True)
        self.script_editor.setPlaceholderText("Your 60-second generated broadcast script will appear here...\n\nHit Generate.")
        self.script_editor.setStyleSheet(
            "QPlainTextEdit { background-color: #0b1020; border: 1px solid #24283b; color: #7dcfff; font-size: 14px; font-family: 'Inter', sans-serif; padding: 15px; }"
        )
        layout.addWidget(self.script_editor, 1)
        
        self.worker = None

    def _start_generation(self):
        topic = self.topic_selector.currentText()
        self.generate_btn.setEnabled(False)
        self.topic_selector.setEnabled(False)
        self.script_editor.clear()
        self.set_status(f"Generative sequence started for: {topic}")
        
        self.worker = ScriptGeneratorWorker(topic_key=topic)
        self.worker.chunk_ready.connect(self._on_chunk)
        self.worker.completed.connect(self._on_complete)
        self.worker.error_signal.connect(self._on_error)
        self.worker.start()

    def _on_chunk(self, token: str):
        cursor = self.script_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.script_editor.setTextCursor(cursor)
        self.script_editor.insertPlainText(token)
        # Auto-scroll
        sb = self.script_editor.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_complete(self):
        self.generate_btn.setEnabled(True)
        self.topic_selector.setEnabled(True)
        self.set_status("Generation Complete. Broadcaster Script successfully minted STGM.")
        
    def _on_error(self, msg: str):
        self.generate_btn.setEnabled(True)
        self.topic_selector.setEnabled(True)
        self.set_status(msg)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = BroadcasterWidget()
    w.resize(1100, 800)
    w.show()
    sys.exit(app.exec())
