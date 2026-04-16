#!/usr/bin/env python3
"""
System/global_cognitive_interface.py — Global Cognitive Interface (GCI)
═══════════════════════════════════════════════════════════════════════════════
The universal human ↔ entity interface layer of SIFTA Living OS.

Every app gets the same brain interface:
  - Chat box (user ↔ entity, powered by local Ollama)
  - Memory hook (auto-remember / auto-recall via StigmergicMemoryBus)
  - Document save/load (shared .sifta_documents/ folder)

Not optional. Not per-app. Injected everywhere through SiftaBaseWidget.

Claude mapped the architecture. Gemini built it. The Architect owns it.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QFrame, QComboBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor

_REPO = Path(__file__).resolve().parent.parent
DOCS_DIR = _REPO / ".sifta_documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


# ── Ollama Worker (background thread for real responses) ────────────────────

class _GCIWorker(QThread):
    """Background Ollama inference for the entity's response."""
    response_ready = pyqtSignal(str)
    error_signal   = pyqtSignal(str)

    def __init__(self, prompt: str, system: str, model: str = "gemma4:latest"):
        super().__init__()
        self.prompt = prompt
        self.system = system
        self.model  = model

    def run(self):
        try:
            import re
            payload = json.dumps({
                "model":  self.model,
                "prompt": self.prompt,
                "system": self.system,
                "stream": False,
                "temperature": 0.6,
                "num_predict": 512,
                "keep_alive": "2m",
            }).encode("utf-8")

            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("response", "").strip()
                # Strip <think> tags from reasoning models
                text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                if text:
                    self.response_ready.emit(text)
                else:
                    self.error_signal.emit("[Empty response from model]")
        except Exception as e:
            self.error_signal.emit(f"[Ollama offline] {e}")


# ── Global Cognitive Interface Widget ────────────────────────────────────────

class GlobalCognitiveInterface(QWidget):
    """
    The universal human ↔ entity interface.
    Drop this into any app. It gives:
      - Persistent chat with cross-app memory
      - One-click document save to .sifta_documents/
      - Real Ollama inference (not a fake echo)
    """
    message_sent = pyqtSignal(str)

    def __init__(
        self,
        app_context: str = "unknown_app",
        entity_name: str = "ALICE_M5",
        architect_id: str = "IOAN_M5",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.app_context  = app_context
        self.entity_name  = entity_name
        self.architect_id = architect_id
        self._worker: Optional[_GCIWorker] = None
        self._bus = None
        self._model = "gemma4:latest"

        # Try to initialize Memory Bus
        try:
            sys.path.insert(0, str(_REPO))
            from System.stigmergic_memory_bus import StigmergicMemoryBus
            self._bus = StigmergicMemoryBus(architect_id=architect_id)
        except Exception:
            pass

        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget#gci_panel {
                background: rgb(13, 14, 23);
                border-left: 1px solid rgb(35, 32, 50);
            }
        """)
        self.setObjectName("gci_panel")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Header
        header = QLabel(f"💬 {self.entity_name}")
        header.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
        header.setStyleSheet("color: rgb(0, 255, 200); padding: 4px;")
        lay.addWidget(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgb(45, 42, 65);")
        lay.addWidget(sep)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Inter", 11))
        self.chat_display.setStyleSheet(
            "QTextEdit { background: rgb(10, 8, 16); border: 1px solid rgb(40, 35, 55);"
            " border-radius: 4px; color: rgb(200, 210, 240); padding: 8px;"
            " font-size: 12px; }"
        )
        lay.addWidget(self.chat_display, 1)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(4)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Talk to the entity...")
        self.input_field.setStyleSheet(
            "QLineEdit { background: rgb(18, 16, 28); border: 1px solid rgb(55, 50, 75);"
            " border-radius: 4px; padding: 8px; color: rgb(200, 210, 240); font-size: 12px; }"
            "QLineEdit:focus { border-color: rgb(0, 255, 200); }"
        )
        self.input_field.returnPressed.connect(self._handle_send)
        input_row.addWidget(self.input_field, 1)

        send_btn = QPushButton("⚡")
        send_btn.setToolTip("Send message")
        send_btn.setFixedWidth(36)
        send_btn.clicked.connect(self._handle_send)
        input_row.addWidget(send_btn)

        lay.addLayout(input_row)

        # Bottom row: Save + context label
        bottom_row = QHBoxLayout()

        save_btn = QPushButton("💾 Save Doc")
        save_btn.setToolTip("Save this conversation to .sifta_documents/")
        save_btn.clicked.connect(self._save_document)
        bottom_row.addWidget(save_btn)

        self._ctx_label = QLabel(f"ctx: {self.app_context}")
        self._ctx_label.setStyleSheet("color: rgb(80, 75, 110); font-size: 9px;")
        bottom_row.addStretch()
        bottom_row.addWidget(self._ctx_label)

        lay.addLayout(bottom_row)

    # ── Messaging ──────────────────────────────────────────────

    def _handle_send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()

        ts = datetime.now().strftime("%H:%M")
        self.chat_display.append(
            f'<span style="color:#7aa2f7;font-weight:bold;">[{ts}] Architect:</span> '
            f'<span style="color:#c0caf5;">{text}</span>'
        )

        # 1. Store in memory bus
        if self._bus and len(text) > 5:
            try:
                self._bus.remember(text[:500], app_context=self.app_context)
            except Exception:
                pass

        # 2. Recall relevant memories
        memory_context = ""
        if self._bus:
            try:
                mem = self._bus.recall_context_block(text, app_context=self.app_context, top_k=3)
                if mem:
                    memory_context = "\n\n" + mem
            except Exception:
                pass

        # 3. Dispatch to Ollama
        if self._worker and self._worker.isRunning():
            return  # already thinking

        system_prompt = (
            f"You are {self.entity_name}, the sovereign intelligence of SIFTA Living OS. "
            f"You are speaking to the Architect inside the '{self.app_context}' application. "
            f"Be helpful, concise, and warm. If relevant memories exist below, reference them naturally. "
            f"Keep responses under 150 words unless asked for detail."
            f"{memory_context}"
        )

        self._worker = _GCIWorker(prompt=text, system=system_prompt, model=self._model)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_signal.connect(self._on_error)
        self._worker.start()

        self.message_sent.emit(text)

    def _on_response(self, text: str):
        ts = datetime.now().strftime("%H:%M")
        self.chat_display.append(
            f'<span style="color:#ff9e64;font-weight:bold;">[{ts}] {self.entity_name}:</span> '
            f'<span style="color:#a9b1d6;">{text}</span>'
        )
        self.chat_display.append("")  # spacing

    def _on_error(self, err: str):
        ts = datetime.now().strftime("%H:%M")
        self.chat_display.append(
            f'<span style="color:#f7768e;">[{ts}] {err}</span>'
        )

    # ── Document Save/Load ─────────────────────────────────────

    def _save_document(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.app_context}_{ts}.sifta.md"
        path = DOCS_DIR / filename

        content = self.chat_display.toPlainText()
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {self.entity_name} — {self.app_context}\n")
            f.write(f"*Saved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
            f.write(content)

        # Store the save event in memory
        if self._bus:
            try:
                last_line = content.strip().split("\n")[-1] if content.strip() else ""
                self._bus.remember(
                    f"Document saved from {self.app_context}: {last_line[:100]}",
                    app_context=self.app_context,
                )
            except Exception:
                pass

        self.chat_display.append(
            f'<span style="color:#9ece6a;">💾 Saved → {filename}</span>'
        )

    def set_model(self, model: str):
        """Allow the parent app to set which Ollama model the GCI uses."""
        self._model = model


# ── Standalone test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    gci = GlobalCognitiveInterface(app_context="gci_test", entity_name="ALICE_M5")
    gci.setWindowTitle("SIFTA — Global Cognitive Interface")
    gci.resize(420, 600)
    gci.show()
    sys.exit(app.exec())
