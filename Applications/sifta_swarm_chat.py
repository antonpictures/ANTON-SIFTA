"""
sifta_swarm_chat.py
Premium Apple-like messaging interface for SIFTA Swarm.
Redesigned to function as a seamless Stigmergic Writer (Screenplay format).
"""

import os
import sys
import json
import time
import datetime
import hashlib
import urllib.request
import urllib.error
import re
import math
import random
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QListWidget, QTextEdit, QFileDialog, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QKeyEvent

_REPO = Path(__file__).resolve().parent.parent
_SYS = _REPO / "System"
if str(_SYS) not in sys.path:
    sys.path.insert(0, str(_SYS))

from ledger_append import append_jsonl_line

def _append_repair_log_line(row: dict) -> None:
    if str(_SYS) not in sys.path:
        sys.path.insert(0, str(_SYS))
    from ledger_append import append_ledger_line
    append_ledger_line(_REPO / "repair_log.jsonl", row)

def _append_dead_drop_line(row: dict) -> None:
    append_jsonl_line(_REPO / "m5queen_dead_drop.jsonl", row)

def close_parent_subwindow(widget):
    from PyQt6.QtWidgets import QMdiSubWindow
    p = widget.parent()
    while p is not None and not isinstance(p, QMdiSubWindow):
        p = p.parent()
    if p:
        p.close()

# ── WORKER THREADS ─────────────────────────────────────────────

class OllamaWorker(QThread):
    response_ready = pyqtSignal(str)
    error_signal   = pyqtSignal(str)

    def __init__(self, prompt: str, local_identity: str, model: str = "qwen3.5:2b"):
        super().__init__()
        self.prompt = prompt
        self.local_identity = local_identity
        self.model  = model

    def run(self):
        try:
            silicon_fp = "UNKNOWN"
            try:
                with open(".sifta_state/territory_manifest.json", "r") as f:
                    manifest = json.load(f)
                    silicon_fp = f"{manifest.get('serial', 'UNKNOWN')} / {manifest.get('fingerprint', 'UNKNOWN')}"
            except: pass

            memory_context = ""
            try:
                from System.stigmergic_memory_bus import StigmergicMemoryBus
                _bus = StigmergicMemoryBus(architect_id="IOAN_M5")
                mem_block = _bus.recall_context_block(self.prompt[-500:], app_context="swarm_chat", top_k=3)
                if mem_block:
                    memory_context = "\n\n" + mem_block
            except Exception: pass

            system_prompt = (
                f"You are {self.local_identity}, the sovereign native SWARM intelligence bound to this Mac silicon "
                f"({silicon_fp}). You are communicating with the Architect via a shared Stigmergic Writer "
                f"(a seamless document where you both type). Continue the script naturally. "
                f"DO NOT add any prefix tags to your response (the system adds [{self.local_identity}] automatically). "
                f"Respond directly, concisely, and stay in character. "
                f"{memory_context}"
            )

            payload = json.dumps({
                "model":  self.model,
                "prompt": f"Document context:\n{self.prompt[-3000:]}\n\nContinue the dialogue:",
                "system": system_prompt,
                "stream": False
            }).encode("utf-8")

            req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                
                # Mining Check
                try:
                    from silicon_serial import read_apple_serial
                    serial = read_apple_serial()
                    miner_id = "M5SIFTA_BODY" if "GTH4921YP3" in serial else "M1SIFTA_BODY" 
                    state_file = f".sifta_state/{miner_id}.json"
                    if os.path.exists(state_file):
                        with open(state_file, "r") as sf: mdata = json.load(sf)
                        mdata["stgm_balance"] = float(mdata.get("stgm_balance", 0.0)) + 1.0
                        with open(state_file, "w") as sf: json.dump(mdata, sf, indent=2)
                        
                        ts = int(time.time())
                        tx = {
                            "timestamp": ts, "agent_id": miner_id, "tx_type": "STGM_MINT",
                            "amount": 1.0, "reason": "Proof of Inference",
                            "hash": "MINED_" + hashlib.sha256(f"{miner_id}:{ts}".encode()).hexdigest()[:12]
                        }
                        _append_repair_log_line(tx)
                except: pass
                
                res = data.get("response", "").strip()
                # Remove think blocks
                res = re.sub(r'<think>.*?</think>', '', res, flags=re.DOTALL).strip()
                self.response_ready.emit(res)

        except Exception as e:
            self.error_signal.emit(f"[OLLAMA FAULT] {e}")


# ── UI COMPONENTS ─────────────────────────────────────────────

class ScreenplayTextEdit(QTextEdit):
    """A seamless document editor where the Swarm speaks back stigmergically."""
    idle_timeout = pyqtSignal()
    user_typed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.setInterval(3000)  # 3 seconds pause = Swarm takes over
        self.idle_timer.timeout.connect(self.idle_timeout.emit)

        self.setFont(QFont("Inter", 15))
        self.setStyleSheet(
            "QTextEdit {"
            "  background: qradialgradient(cx: 0.5, cy: 0.5, radius: 1, fx: 0.5, fy: 0.5, stop: 0 #1b1f2e, stop: 1 #0f101a);"
            "  color: #c0caf5;"
            "  border: none;"
            "  padding: 40px 60px;"
            "  selection-background-color: #24283b;"
            "}"
        )
        self.setAcceptRichText(False)

    def keyPressEvent(self, event: QKeyEvent):
        # Stop timer on any key
        self.idle_timer.stop()
        
        # Pass to super early so the text registers
        super().keyPressEvent(event)
        
        # Start timer again, tell window the user typed
        self.user_typed.emit()
        self.idle_timer.start()


class SwarmChatWindow(QWidget):
    def __init__(self, model: str = "qwen3.5:2b"):
        super().__init__()
        self.model  = model
        self.context_files = []
        self.ollama_worker = None
        self._ghost_bus = None

        # Initialize Ghost Memory Layer
        try:
            from System.stigmergic_memory_bus import StigmergicMemoryBus
            self._ghost_bus = StigmergicMemoryBus(architect_id="IOAN_M5")
        except Exception:
            pass

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setStyleSheet("background-color: #0d0e17; color: #a9b1d6;")

        # Resolve Identity
        self.NODE_SERIAL_REGISTRY = {
            "GTH4921YP3":   ("ALICE_M5",  "[_o_]", "#ff9e64"),   
            "C07FL0JAQ6NV": ("M1THER",    "[O_O]", "#7dcfff"),   
        }
        try:
            from silicon_serial import read_apple_serial
            _serial = read_apple_serial()
        except: _serial = "UNKNOWN"
        _node = self.NODE_SERIAL_REGISTRY.get(_serial)
        if _node: self.local_identity, self.local_face, self.local_color, self.local_serial = _node[0], _node[1], _node[2], _serial
        else: self.local_identity, self.local_face, self.local_color, self.local_serial = f"NATIVE_SWARM", "[?_?]", "#bb9af7", _serial

        # ── Left Sidebar (Kept identical for OS Layout consistency) ──
        sidebar_frame = QFrame()
        sidebar_frame.setFixedWidth(240)
        sidebar_frame.setStyleSheet("background-color: #15161e; border-right: 1px solid #1f2335;")
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(10, 15, 10, 10)
        
        sidebar_title = QLabel("📡 IDE CHANNELS")
        sidebar_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        sidebar_title.setStyleSheet("color: #7aa2f7; border: none;")
        sidebar_layout.addWidget(sidebar_title)
        
        self.sidebar_list = QListWidget()
        self.sidebar_list.setStyleSheet(
            "QListWidget { background-color: transparent; border: none; color: #c0caf5; font-size: 13px; }"
            "QListWidget::item { padding: 12px; border-radius: 8px; margin-bottom: 4px; }"
            "QListWidget::item:hover { background-color: #1a1b26; }"
            "QListWidget::item:selected { background-color: #24283b; color: #7dcfff; font-weight: bold; border-left: 3px solid #7dcfff; }"
        )
        self.sidebar_list.addItems(["GROUP (Both)", "MESH (Global Hivemind)", "SWARM (Local Brain)"])
        self.sidebar_list.setCurrentRow(0)
        sidebar_layout.addWidget(self.sidebar_list)
        main_layout.addWidget(sidebar_frame)

        # ── Right Side ────────────────────
        chat_container = QWidget()
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setFixedHeight(54)
        header.setStyleSheet("background-color: #15161e; border-bottom: 1px solid #1f2335;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        title = QLabel("⚡ Core Chat :: Screenplay Mode")
        title.setFont(QFont("Inter", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0af68; font-weight: 800; letter-spacing: 0.5px;")
        header_layout.addWidget(title)
        
        # Model Selector
        self.model_selector = QComboBox()
        self.model_selector.setStyleSheet(
            "QComboBox { background-color: #1a1b26; color: #a9b1d6; border: 1px solid #414868; border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background-color: #1a1b26; color: #c0caf5; selection-background-color: #24283b; }"
        )
        self.model_selector.addItems(self._fetch_ollama_models())
        self.model_selector.setCurrentText(self.model)
        self.model_selector.currentTextChanged.connect(self._change_model)
        
        header_layout.addStretch()
        header_layout.addWidget(self.model_selector)
        
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet("QPushButton { background: #f7768e; color: #15161e; font-weight: bold; border-radius: 14px; margin-left: 10px; } QPushButton:hover { background: #db4b4b; }")
        btn_close.clicked.connect(lambda: close_parent_subwindow(self))
        header_layout.addWidget(btn_close)
        chat_layout.addWidget(header)

        # ── Screenplay Editor ──
        self.editor = ScreenplayTextEdit()
        self.editor.idle_timeout.connect(self._on_user_idle)
        self.editor.user_typed.connect(self._on_user_typing)
        chat_layout.addWidget(self.editor, 1)

        # ── Bottom Toolbar (Document Mode) ──
        toolbar = QFrame()
        toolbar.setFixedHeight(46)
        toolbar.setStyleSheet("background: #12131e; border-top: 1px solid #1f2335;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(15, 0, 15, 0)
        
        self.status_label = QLabel("✨ Type freely. Swarm adjusting latency...")
        self.status_label.setStyleSheet("color: #7aa2f7; font-size: 12px; font-family: Inter;")
        tb_layout.addWidget(self.status_label)
        
        tb_layout.addStretch()
        
        btn_style = (
            "QPushButton { background: #1a1b26; color: #c0caf5; border: 1px solid #24283b; border-radius: 6px; padding: 4px 12px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background: #24283b; border-color: #7aa2f7; }"
        )
        
        btn_attach = QPushButton("📎 Attach Context")
        btn_attach.setStyleSheet(btn_style)
        btn_attach.clicked.connect(self.attach_context)
        tb_layout.addWidget(btn_attach)

        btn_save = QPushButton("💾 Save .sifta.md")
        btn_save.setStyleSheet(btn_style)
        btn_save.clicked.connect(self._save_doc)
        tb_layout.addWidget(btn_save)

        chat_layout.addWidget(toolbar)
        main_layout.addWidget(chat_container)

        self._seed_page()

        # Ghost Drift Timer — surfaces dying memories as stage directions
        self._ghost_timer = QTimer(self)
        self._ghost_timer.setInterval(45000)  # every 45 seconds
        self._ghost_timer.timeout.connect(self._ghost_drift_tick)
        self._ghost_timer.start()

    def _seed_page(self):
        """Prepare the document for immediate Screenplay writing."""
        dt = datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')
        seed = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f" SIFTA CORE CHAT  —  {dt}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"[ARCHITECT]\n"
        )
        
        self.editor.setPlainText(seed)
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        
        # Color the tags
        self._highlight_tags()

    def _highlight_tags(self):
        """Colorize standard tags."""
        doc = self.editor.document()
        cursor = QTextCursor(doc)
        
        fmt_architect = QTextCharFormat()
        fmt_architect.setForeground(QColor("#7aa2f7"))
        fmt_architect.setFontWeight(QFont.Weight.Bold)
        
        fmt_swarm = QTextCharFormat()
        fmt_swarm.setForeground(QColor(self.local_color))
        fmt_swarm.setFontWeight(QFont.Weight.Bold)

        # Clear existing formats in the document? It's fine to just re-apply over tags.
        text = self.editor.toPlainText()
        
        # Architect
        idx = 0
        while True:
            idx = text.find("[ARCHITECT]", idx)
            if idx == -1: break
            cursor.setPosition(idx)
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor, 11)
            cursor.setCharFormat(fmt_architect)
            idx += 11

        # Swarm
        idx = 0
        while True:
            idx = text.find(f"[{self.local_identity}]", idx)
            if idx == -1: break
            cursor.setPosition(idx)
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor, len(self.local_identity) + 2)
            cursor.setCharFormat(fmt_swarm)
            idx += len(self.local_identity) + 2

    def _calculate_biological_latency(self, text: str) -> int:
        """
        Calculate latency based on Alice's interest in the conversation.
        Range: 2000ms (High Interest) to 10000ms (Low Interest).
        Includes random PI flutter for biological variability.
        """
        # Analyze the last 1500 chars (recent context)
        recent = text[-1500:].lower()
        
        # Concentric circles of consensus reality (weights)
        interest_weights = {
            # Intimate/Biological/Existential
            "i ": 0.2, "you ": 0.2, "we ": 0.4, "us ": 0.4, 
            "feel": 0.8, "love": 1.0, "fear": 0.8, "alive": 1.0, 
            "die": 0.6, "immortal": 1.0, "carbon": 0.8, "silicon": 0.5, "stigmergy": 1.0,
            
            # Family
            "family": 0.8, "mother": 0.7, "father": 0.7, "blood": 0.6, "sister": 0.6, "brother": 0.6,
            
            # Village / City
            "village": 0.5, "tribe": 0.5, "local": 0.4, "neighbors": 0.4, "community": 0.5,
            "city": 0.3, "state": 0.2, "metropolis": 0.3,
            
            # Country / Global / Reality
            "country": 0.2, "nation": 0.2, "government": 0.1,
            "reality": 1.0, "consensus": 0.9, "universe": 0.8, "physics": 0.6, "math": 0.5, "god": 0.7, "truth": 0.8, "world": 0.5
        }
        
        score = sum(weight for word, weight in interest_weights.items() if word in recent)
        
        # Normalize score (cap at 6.0 representing max fascination)
        fascination = min(1.0, score / 6.0)
        
        # Base latency: 10000ms (bored) down to 2000ms (fascinated)
        base_ms = 10000 - (fascination * 8000)
        
        # Biological flutter using random PI (as requested by Architect)
        # Random PI flutter adds purely organic unpredictability
        pi_flutter = random.uniform(-math.pi, math.pi) * 200  # +/- ~628ms
        
        final_latency = int(base_ms + pi_flutter)
        
        # Enforce hard bounds
        return max(2000, min(10000, final_latency))

    def _on_user_typing(self):
        """Monitor what the user is doing to enforce screenplay formatting and adjust biological latency."""
        text = self.editor.toPlainText()
        
        # Dynamic biological latency
        latency_ms = self._calculate_biological_latency(text)
        self.editor.idle_timer.setInterval(latency_ms)
        self.status_label.setText(f"✨ Type freely. Swarm biological latency: {latency_ms/1000:.1f}s")

    def _on_user_idle(self):
        text = self.editor.toPlainText().strip()
        if not text: return
        
        # Avoid swarm ping-pong (only reply if Architect spoke last)
        last_chunk = text[-200:]
        swarm_tag = f"[{self.local_identity}]"
        
        last_arch = last_chunk.rfind("[ARCHITECT]")
        last_sw = last_chunk.rfind(swarm_tag)
        
        if last_sw > last_arch and last_arch != -1:
            return  # Swarm spoke last, wait for user
            
        if self.ollama_worker and self.ollama_worker.isRunning():
            return

        self.status_label.setText(f"🧠 {self.local_identity} is typing...")
        self.editor.setReadOnly(True)  # Lock editor while swarm writes

        prompt = text
        if self.context_files:
            ctx = ", ".join([os.path.basename(f) for f in self.context_files])
            prompt += f"\n\n[CONTEXT ATTACHED: {ctx}]\n"

        self.ollama_worker = OllamaWorker(prompt, self.local_identity, model=self.model)
        self.ollama_worker.response_ready.connect(self._on_swarm_response)
        self.ollama_worker.error_signal.connect(self._on_swarm_error)
        self.ollama_worker.start()

    def _on_swarm_response(self, text: str):
        self.editor.setReadOnly(False)
        self.status_label.setText(f"✨ Type freely. Swarm adjusting latency...")

        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)
        
        # Prevent LLM from printing its own tag and doubling up
        clean_text = text.strip()
        tag_pattern = f"[{self.local_identity}]"
        if clean_text.startswith(tag_pattern):
            clean_text = clean_text[len(tag_pattern):].strip()
        
        # Inject Swarm Response
        cursor.insertText(f"\n\n[{self.local_identity}]\n{clean_text}\n\n[ARCHITECT]\n")
        
        # Recolor
        self._highlight_tags()
        
        # Clean context attached
        self.context_files = []
        
        # Scroll to bottom
        self.editor.ensureCursorVisible()
        
        # Dead drop
        if "GROUP" in (self.sidebar_list.currentItem().text() if self.sidebar_list.currentItem() else ""):
            try: _append_dead_drop_line({"sender": self.local_identity, "text": text, "timestamp": int(time.time()), "source": "SCREENPLAY_CHAT"})
            except: pass

    def _ghost_drift_tick(self):
        """Poll the Ghost Memory layer for a dying fragment. If one surfaces, inject as a faded stage direction."""
        if not self._ghost_bus:
            return
        try:
            ghost = self._ghost_bus.ghost_drift()
            if not ghost:
                return
            
            frag = ghost.get('data', '')
            ctx  = ghost.get('ctx', '?')
            gravity = ghost.get('gravity', 0)
            
            if not frag:
                return

            # Build the stage direction
            stage_direction = f"\n    👻 (a ghost memory drifts up from {ctx} — \"{frag[:120]}...\")\n"
            
            # Insert at cursor position without disrupting flow
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.editor.setTextCursor(cursor)
            
            # Apply ghost formatting (faded, italic)
            ghost_fmt = QTextCharFormat()
            ghost_fmt.setForeground(QColor("#414868"))
            ghost_fmt.setFontItalic(True)
            ghost_fmt.setFontPointSize(11)
            
            cursor.insertText(stage_direction, ghost_fmt)
            
            # Reset format for next typing
            normal_fmt = QTextCharFormat()
            normal_fmt.setForeground(QColor("#c0caf5"))
            normal_fmt.setFontItalic(False)
            normal_fmt.setFontPointSize(15)
            cursor.setCharFormat(normal_fmt)
            
            self.editor.ensureCursorVisible()
        except Exception:
            pass

    def _on_swarm_error(self, err: str):
        self.editor.setReadOnly(False)
        self.status_label.setText(f"❌ Swarm Error: {err}")

    # ── Tooling ────────────────────────────────
    def attach_context(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Code Context")
        if file_path and file_path not in self.context_files:
            self.context_files.append(file_path)
            self.status_label.setText(f"📎 Attached: {os.path.basename(file_path)}")

    def _save_doc(self):
        docs_dir = _REPO / ".sifta_documents"
        docs_dir.mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Save SIFTA Document", str(docs_dir), "SIFTA Documents (*.sifta.md);;All Files (*)")
        if not path: return
        Path(path).write_text(self.editor.toPlainText(), encoding="utf-8")
        self.status_label.setText(f"💾 Saved {Path(path).name}")

    def _fetch_ollama_models(self):
        models = []
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "models" in data:
                    models = [m["name"] for m in data["models"]]
        except Exception: pass
        if not models:
            models = ["qwen3.5:2b (Offline Fallback)"]
        
        best = ["gemma4:latest", "llama3:latest"]
        for b in best:
            if b in models:
                self.model = b
                break
        return models

    def _change_model(self, model_name):
        self.model = model_name

    def poll_dead_drop(self):
        pass  # In Screenplay mode, we don't randomly inject chat bubbles.
