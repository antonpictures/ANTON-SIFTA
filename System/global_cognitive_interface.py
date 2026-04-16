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
import asyncio
import websockets
from queue import Queue, Empty
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QFrame, QComboBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor

from System.context_preloader import ContextPreloader

_REPO = Path(__file__).resolve().parent.parent
DOCS_DIR = _REPO / ".sifta_documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# ── Layer 2 Configuration ────────────────────────────────────────────────────
# Set SWARM_RELAY_URI in your environment to point at M1's relay when it's remote.
# Example: export SWARM_RELAY_URI=ws://192.168.1.42:8765
# Default: localhost (for testing on the same machine)
SWARM_RELAY_URI = os.environ.get("SWARM_RELAY_URI", "ws://127.0.0.1:8765")


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

class _ContextWorker(QThread):
    """Parallel swarm worker: Runs a secondary small model to deduce intent/subtext."""
    def __init__(self, prompt: str, system: str, model: str = "gemma4:latest"):
        super().__init__()
        self.prompt = prompt
        self.system = system
        self.model = model
        self.intent_found = ""

    def run(self):
        try:
            import re
            payload = json.dumps({
                "model": self.model,
                "prompt": self.prompt,
                "system": self.system,
                "stream": False,
                "temperature": 0.2,
                "num_predict": 64,
            }).encode("utf-8")
            
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data.get("response", "").strip()
                self.intent_found = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        except:
            pass


# ── Swarm Mesh Client (Layer 2) ──────────────────────────────────────────────

class _SwarmMeshClientWorker(QThread):
    """Background asyncio worker maintaining a persistent WebSocket to the Swarm Relay."""
    swarm_message_ready = pyqtSignal(str)
    connection_status = pyqtSignal(bool)

    def __init__(self, uri="ws://127.0.0.1:8765", architect_id="IOAN_M5"):
        super().__init__()
        self.uri = uri
        self.architect_id = architect_id
        self._send_queue = Queue()
        self._loop = None
        self._running = True

    def send_to_swarm(self, message: dict):
        self._send_queue.put(json.dumps(message))

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._client_loop())

    async def _client_loop(self):
        while self._running:
            try:
                async with websockets.connect(self.uri) as ws:
                    self.connection_status.emit(True)
                    # Announce presence
                    await ws.send(json.dumps({"type": "REGISTER", "sender": self.architect_id}))
                    
                    receive_task = asyncio.create_task(ws.recv())

                    while self._running:
                        try:
                            # Flush outgoing queue
                            while not self._send_queue.empty():
                                msg_to_send = self._send_queue.get_nowait()
                                await ws.send(msg_to_send)
                        except Empty:
                            pass

                        # Wait for incoming messages, max 0.05s to allow queue checking
                        done, pending = await asyncio.wait([receive_task], timeout=0.05)
                        if receive_task in done:
                            try:
                                raw_msg = receive_task.result()
                                self.swarm_message_ready.emit(raw_msg)
                                receive_task = asyncio.create_task(ws.recv())
                            except websockets.exceptions.ConnectionClosed:
                                break

                    # Socket session ended (disconnect, stop, or recv closed)
                    self.connection_status.emit(False)

            except Exception as e:
                self.connection_status.emit(False)
                await asyncio.sleep(2)  # Reconnect backoff

    def stop(self):
        self._running = False
        self.wait()



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
    response_received = pyqtSignal(str)

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
            self.preloader = ContextPreloader(architect_id=architect_id)
        except Exception:
            self.preloader = None
            pass

        self._preloaded_memory_cache = None

        # Build UI first so status labels exist before the mesh thread emits.
        self._mesh_connected = False
        self._mesh_client = _SwarmMeshClientWorker(uri=SWARM_RELAY_URI, architect_id=self.architect_id)
        self._mesh_client.swarm_message_ready.connect(self._on_swarm_message)
        self._mesh_client.connection_status.connect(self._on_swarm_status)
        self._build_ui()
        self._mesh_client.start()

    @property
    def mesh_connected(self) -> bool:
        """True when Layer 2 WebSocket to SWARM_RELAY_URI is up (same source as taskbar)."""
        return getattr(self, "_mesh_connected", False)

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
        
        # Mesh Status Indicator
        self._mesh_status_label = QLabel("Layer 2 Mesh: Connecting...")
        self._mesh_status_label.setStyleSheet("color: rgb(150, 155, 180); font-size: 9px;")
        lay.addWidget(self._mesh_status_label)

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
        self.input_field.textChanged.connect(self._preload_context)
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

    def _preload_context(self, text: str):
        if not self.preloader:
            return
        
        # Don't preload if user deleted everything
        if not text.strip():
            self._preloaded_memory_cache = None
            return

        preload = self.preloader.preload(text, self.app_context)
        if preload:
            self.chat_display.append(f'<span style="color:#565f89; font-size:10px;">[PRELOAD] {preload}</span>')
            self._preloaded_memory_cache = preload

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
        if self._preloaded_memory_cache:
            # We already have anticipatory context! Instant load, bypassing duplicate bus scan.
            memory_context = "\n\n[STIGMERGIC MEMORY — retrieved from cross-app territory]\n" + self._preloaded_memory_cache
            self._preloaded_memory_cache = None
        elif self._bus:
            try:
                mem = self._bus.recall_context_block(text, app_context=self.app_context, top_k=3)
                if mem:
                    memory_context = "\n\n" + mem
                    # ── LAYER 2: Shared Cross-Node Recall ────────────────
                    self._mesh_client.send_to_swarm({
                        "type": "MEMORY_HINT",
                        "sender": self.architect_id,
                        "target": "ALL",
                        "text": mem.splitlines()[0][:120] + "..."
                    })
            except Exception:
                pass

        # 3. Broadcast to Swarm Mesh
        mesh_payload = {
            "type": "CHAT",
            "sender": self.architect_id,
            "target": "ALL",
            "text": text,
            "context": self.app_context
        }
        self._mesh_client.send_to_swarm(mesh_payload)

        # 4. Dispatch to local Ollama (Parallel Swarm)
        if self._worker and self._worker.isRunning():
            return  # primary worker is busy

        # 4.5 Ghost Layer — serendipitous identity fragments
        ghost_whisper = ""
        if self._bus:
            try:
                ghost = self._bus.ghost_drift()
                if ghost:
                    frag = ghost.get('data', '')
                    ctx  = ghost.get('ctx', '?')
                    ts = datetime.now().strftime("%H:%M")
                    self.chat_display.append(
                        f'<span style="color:#414868; font-size:9px;">[{ts}] 👻 Ghost Memory (from {ctx}): "{frag[:120]}"</span>'
                    )
                    ghost_whisper = (
                        f"\n\n[GHOST MEMORY — an old, almost-lost fragment from '{ctx}']\n"
                        f"\"{frag}\"\n"
                        f"[This surfaced involuntarily. If relevant, weave it gently into your response.]"
                    )
            except Exception:
                pass

        system_prompt = (
            f"You are {self.entity_name}, the sovereign intelligence of SIFTA Living OS. "
            f"You are speaking to the Architect inside the '{self.app_context}' application. "
            f"Be helpful, concise, and warm. If relevant memories exist below, reference them naturally. "
            f"Keep responses under 150 words unless asked for detail."
            f"{memory_context}"
            f"{ghost_whisper}"
        )

        self._worker = _GCIWorker(prompt=text, system=system_prompt, model=self._model)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_signal.connect(self._on_error)
        self._worker.start()

        # Fire secondary parallel worker (Empathy/Intent analysis)
        context_prompt = "Identify the core underlying emotional intent or hidden requirement in this message in 5 words or less."
        self._ctx_worker = _ContextWorker(prompt=text, system=context_prompt, model=self._model)
        self._ctx_worker.finished.connect(self._on_context_finished)
        self._ctx_worker.start()

        self.message_sent.emit(text)

    def _on_context_finished(self):
        if hasattr(self, "_ctx_worker") and self._ctx_worker.intent_found:
            self._mesh_client.send_to_swarm({
                "type": "MEMORY_HINT",
                "sender": f"SWARM_INTENT_{self.architect_id}",
                "target": "ALL",
                "text": f"Subtext: {self._ctx_worker.intent_found}"
            })

    def _on_response(self, text: str):
        ts = datetime.now().strftime("%H:%M")
        self.chat_display.append(
            f'<span style="color:#ff9e64;font-weight:bold;">[{ts}] {self.entity_name}:</span> '
            f'<span style="color:#a9b1d6;">{text}</span>'
        )
        self.chat_display.append("")  # spacing
        self.response_received.emit(text)

    def _on_error(self, err: str):
        ts = datetime.now().strftime("%H:%M")
        self.chat_display.append(
            f'<span style="color:#f7768e;">[{ts}] {err}</span>'
        )

    # ── Swarm Mesh Networking ──────────────────────────────────
    
    def _on_swarm_status(self, connected: bool):
        self._mesh_connected = connected
        if connected:
            self._mesh_status_label.setText("Layer 2 Mesh: LIVE 🟢")
            self._mesh_status_label.setStyleSheet("color: rgb(0, 255, 200); font-size: 9px;")
        else:
            self._mesh_status_label.setText("Layer 2 Mesh: OFFLINE 🔴")
            self._mesh_status_label.setStyleSheet("color: rgb(247, 118, 142); font-size: 9px;")

    def _on_swarm_message(self, raw_message: str):
        try:
            msg = json.loads(raw_message)
            msg_type = msg.get("type")
            sender = msg.get("sender", "UNKNOWN")
            
            # Don't echo our own broadcasts
            if sender == self.architect_id:
                return
                
            if msg_type == "CHAT":
                ts = datetime.now().strftime("%H:%M")
                text = msg.get("text", "")
                self.chat_display.append(
                    f'<span style="color:#bb9af7;font-weight:bold;">[{ts}] {sender}:</span> '
                    f'<span style="color:#c0caf5;">{text}</span>'
                )
                
            elif msg_type == "MEMORY_HINT":
                # Parallel memory sync across nodes
                hint = msg.get("text", "")
                ts = datetime.now().strftime("%H:%M")
                self.chat_display.append(
                    f'<span style="color:#e0af68;">[{ts}] 🧠 Swarm Recall ({sender}):</span> '
                    f'<span style="color:#c0caf5;"><i>{hint}</i></span>'
                )
                
        except json.JSONDecodeError:
            pass

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
