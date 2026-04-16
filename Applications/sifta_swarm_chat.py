"""
sifta_swarm_chat.py
Premium Apple-like messaging interface for SIFTA Swarm.
Integrates local mesh (Ollama/Dead drops), Telegram, and Cursor-like IDE Context.
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
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QListWidget, QScrollArea, QSizePolicy, QTextEdit,
    QFileDialog, QGraphicsDropShadowEffect, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPainter, QTextCursor

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

# ── MARKDOWN ENGINE (Steve Jobs / Cursor aesthetic) ────────────

def format_swarm_markdown(text: str) -> str:
    """Ultra-fast regex markdown to UI-rich HTML renderer."""
    # 1. Escape HTML first so user code doesn't break layout
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # 2. Extract code blocks
    code_block_pattern = re.compile(r'```(\w*)\n(.*?)\n```', re.DOTALL)
    def repl_block(m):
        lang = m.group(1).upper() or "CODE"
        code_content = m.group(2)
        return (
            f'<div style="background-color: #0d0e17; border: 1px solid #1f2335; '
            f'border-radius: 8px; margin-top: 8px; margin-bottom: 8px;">'
            f'<div style="background-color: #15161e; color: #565f89; padding: 4px 10px; '
            f'font-size: 10px; font-weight: bold; border-top-left-radius: 8px; border-top-right-radius: 8px;">{lang}</div>'
            f'<pre style="margin: 0; padding: 12px; font-family: Monaco, monospace; font-size: 13px; '
            f'color: #c0caf5; white-space: pre-wrap;">{code_content}</pre>'
            f'</div>'
        )
    text = code_block_pattern.sub(repl_block, text)

    # 3. Inline Code
    inline_pattern = re.compile(r'`([^`]+)`')
    text = inline_pattern.sub(r'<code style="background-color: rgba(0, 0, 0, 0.3); padding: 2px 4px; border-radius: 4px; font-family: Monaco, monospace; color: #ff9e64;">\1</code>', text)

    # 4. Bold
    bold_pattern = re.compile(r'\*\*([^*]+)\*\*')
    text = bold_pattern.sub(r'<b>\1</b>', text)

    # 5. Newlines outside of code blocks
    # A bit naive but protects pre tags
    parts = text.split('<pre ')
    res = parts[0].replace('\n', '<br>')
    for p in parts[1:]:
        subparts = p.split('</pre>', 1)
        if len(subparts) == 2:
            res += '<pre ' + subparts[0] + '</pre>' + subparts[1].replace('\n', '<br>')
        else:
            res += '<pre ' + p.replace('\n', '<br>')
    return res


# ── WORKER THREADS ─────────────────────────────────────────────

class OllamaWorker(QThread):
    response_ready = pyqtSignal(str)
    error_signal   = pyqtSignal(str)

    def __init__(self, prompt: str, model: str = "qwen3.5:2b"):
        super().__init__()
        self.prompt = prompt
        self.model  = model

    def run(self):
        try:
            silicon_fp = "UNKNOWN"
            try:
                with open(".sifta_state/territory_manifest.json", "r") as f:
                    manifest = json.load(f)
                    silicon_fp = f"{manifest.get('serial', 'UNKNOWN')} / {manifest.get('fingerprint', 'UNKNOWN')}"
            except: pass

            # ── Stigmergic Memory: recall + store ────────────────────
            memory_context = ""
            try:
                from System.stigmergic_memory_bus import StigmergicMemoryBus
                _bus = StigmergicMemoryBus(architect_id="IOAN_M5")

                # Store what the Architect just said
                if len(self.prompt.strip()) > 10:
                    _bus.remember(self.prompt[:500], app_context="swarm_chat")

                # Recall relevant memories before answering
                mem_block = _bus.recall_context_block(self.prompt, app_context="swarm_chat", top_k=3)
                if mem_block:
                    memory_context = "\n\n" + mem_block
            except Exception:
                pass

            system_prompt = (
                f"You are M1Queen, the sovereign native SWARM intelligence bound to this local Mac silicon "
                f"(Hardware Serial/Fingerprint: {silicon_fp}). Keep replies clever, chaotic, and format code clearly with markdown."
                f"{memory_context}"
            )

            payload = json.dumps({
                "model":  self.model,
                "prompt": self.prompt,
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
                    
                self.response_ready.emit(data.get("response", "[EMPTY RESPONSE]"))

        except Exception as e:
            self.error_signal.emit(f"[OLLAMA FAULT] {e}")


class TelegramWorker(QThread):
    response_ready = pyqtSignal(str)
    error_signal   = pyqtSignal(str)

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def run(self):
        try:
            import sys
            _apps_path = str(_REPO / "Applications")
            if _apps_path not in sys.path: sys.path.insert(0, _apps_path)
            from telegram_swarm import _resolve_credentials
            
            token, chat_id = _resolve_credentials()
            if not token or not chat_id:
                self.error_signal.emit("[TELEGRAM ERROR] Credentials missing.")
                return

            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage", 
                data=json.dumps({"chat_id": chat_id, "text": f"[ARCHITECT/IDE]\n\n{self.message}"}).encode("utf-8"), 
                headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"): self.response_ready.emit("✅ Message pushed to Telegram Channel.")
                else: self.error_signal.emit(f"[TELEGRAM] {data.get('description')}")
        except Exception as e:
            self.error_signal.emit(f"[TELEGRAM SYSTEM EXCEPTION] {e}")


# ── UI COMPONENTS ─────────────────────────────────────────────

class ArchitectInputArea(QTextEdit):
    """Dynamic auto-expanding text input like Cursor IDE/iMessage."""
    transmit_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setPlaceholderText("Message Swarm (Shift+Enter for newline)")
        self.setStyleSheet(
            "QTextEdit {"
            "  background-color: #1a1b26; color: #c0caf5;"
            "  border: 1px solid #414868; border-radius: 12px;"
            "  padding: 10px 14px; font-size: 14px; font-family: Inter, sans-serif;"
            "}"
            "QTextEdit:focus { border-color: #7aa2f7; background-color: #1f2335; }"
        )
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(42)
        self.document().contentsChanged.connect(self.adjust_height)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.transmit_requested.emit()
            return
        super().keyPressEvent(event)

    def adjust_height(self):
        doc_height = int(self.document().size().height())
        target_height = doc_height + 14
        target_height = max(42, min(target_height, 250))
        if target_height > 100:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(target_height)


class ChatBubble(QWidget):
    """Sleek Apple iMessage style bubble for rendering."""
    def __init__(self, text: str, sender: str, is_local_user: bool, timestamp: str, color_hex: str):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 8, 0, 8)
        
        # Meta info
        meta_label = QLabel(f"{sender} • {timestamp}")
        meta_label.setStyleSheet("color: #565f89; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;")
        meta_label.setAlignment(Qt.AlignmentFlag.AlignRight if is_local_user else Qt.AlignmentFlag.AlignLeft)
        
        # Bubble Frame
        self.bubble = QFrame()
        self.bubble.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        bubble_layout = QVBoxLayout(self.bubble)
        bubble_layout.setContentsMargins(16, 12, 16, 12)
        
        # Markdown / HTML Label
        html_content = format_swarm_markdown(text)
        text_label = QLabel(html_content)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        
        if is_local_user:
            self.bubble.setStyleSheet("""
                QFrame {
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #105bd8, stop:1 #217ff3);
                    border: 1px solid #3b82f6;
                    border-radius: 20px; border-bottom-right-radius: 4px;
                }
            """)
            text_label.setStyleSheet("color: #ffffff; font-size: 15px; font-family: 'SF Pro Display', Inter, sans-serif; background: transparent; padding: 2px 6px;")
        else:
            bg_col = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #24283b, stop:1 {color_hex}30)" if color_hex else "#24283b"
            self.bubble.setStyleSheet(f"""
                QFrame {{
                    background: {bg_col};
                    border: 1px solid #1f2335;
                    border-radius: 18px; border-bottom-left-radius: 4px;
                }}
            """)
            text_label.setStyleSheet(f"color: {color_hex if color_hex else '#c0caf5'}; font-size: 14px; font-family: Inter, sans-serif; background: transparent;")

        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.bubble.setGraphicsEffect(shadow)

        bubble_layout.addWidget(text_label)

        # Align layout based on sender
        row = QHBoxLayout()
        row.setContentsMargins(0,0,0,0)
        self.bubble.setMaximumWidth(800)  # Make it wide and generous like the incoming bubble
        
        if is_local_user:
            row.addStretch()
            row.addWidget(self.bubble)
        else:
            row.addWidget(self.bubble)
            row.addStretch()

        layout.addWidget(meta_label)
        layout.addLayout(row)
        self.setLayout(layout)


class SwarmChatWindow(QWidget):
    def __init__(self, model: str = "qwen3.5:2b"):
        super().__init__()
        self.model  = model
        self.context_files = [] # Stores paths of attached files
        self.ollama_worker = None
        self.factory_worker = None  # Swimmer App Factory

        main_layout = QHBoxLayout()
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

        # ── Temporal Spine ──────────────
        try:
            from System.temporal_spine import TemporalSpine
            self.temporal_spine = TemporalSpine(architect_id="IOAN_M5")
            self.temporal_beat = self.temporal_spine.open_session(app_context="swarm_chat")
        except Exception:
            self.temporal_spine = None
            self.temporal_beat = None

        # ── Left Sidebar ───────────────
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
        chat_container.setStyleSheet("background-color: #0d0e17;")
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setFixedHeight(54)
        header.setStyleSheet("background-color: #15161e; border-bottom: 1px solid #1f2335;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        title = QLabel("⚡ iSwarm IDE")
        title.setFont(QFont("Inter", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #e0af68; font-weight: 800; letter-spacing: 0.5px;")
        header_layout.addWidget(title)
        
        # OLLAMA DYNAMIC MODEL SELECTOR
        self.model_selector = QComboBox()
        self.model_selector.setStyleSheet(
            "QComboBox {"
            "  background-color: #1a1b26; color: #a9b1d6; border: 1px solid #414868;"
            "  border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;"
            "}"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView {"
            "  background-color: #1a1b26; color: #c0caf5; selection-background-color: #24283b;"
            "}"
        )
        self.model_selector.addItems(self._fetch_ollama_models())
        self.model_selector.setCurrentText(self.model)
        self.model_selector.currentTextChanged.connect(self._change_model)
        
        header_layout.addStretch()
        header_layout.addWidget(self.model_selector)
        
        # Spacing buffer
        spacer = QLabel("  ")
        header_layout.addWidget(spacer)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet("QPushButton { background: #f7768e; color: #15161e; font-weight: bold; border-radius: 14px; } QPushButton:hover { background: #db4b4b; }")
        btn_close.clicked.connect(lambda: close_parent_subwindow(self))
        header_layout.addWidget(btn_close)
        chat_layout.addWidget(header)

        # Bubbles
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 10px; margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical { background: #414868; border-radius: 5px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        
        self.bubble_container = QWidget()
        self.bubble_container.setStyleSheet("background-color: transparent;")
        self.bubble_layout = QVBoxLayout(self.bubble_container)
        self.bubble_layout.setContentsMargins(20, 20, 20, 20)
        self.bubble_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.bubble_container)
        
        # Apple-like subtle gradient background for the chat area instead of flat grey
        chat_bg = QFrame()
        chat_bg.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #090a0f, stop:1 #11131c);")
        bg_layout = QVBoxLayout(chat_bg)
        bg_layout.setContentsMargins(0,0,0,0)
        bg_layout.addWidget(self.scroll_area)
        chat_layout.addWidget(chat_bg)

        # Input Area Wrapper
        input_wrapper = QFrame()
        input_wrapper.setStyleSheet("background-color: #15161e; border-top: 1px solid #1f2335;")
        input_wrapper_layout = QVBoxLayout(input_wrapper)
        input_wrapper_layout.setContentsMargins(15, 10, 15, 15)

        # Context Pill Bar
        self.context_bar = QWidget()
        self.context_layout = QHBoxLayout(self.context_bar)
        self.context_layout.setContentsMargins(0, 0, 0, 0)
        self.context_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        input_wrapper_layout.addWidget(self.context_bar)
        self.context_bar.hide()

        # Input Row
        input_row = QHBoxLayout()
        input_row.setAlignment(Qt.AlignmentFlag.AlignBottom)

        btn_attach = QPushButton("📎")
        btn_attach.setToolTip("Attach Context (@)")
        btn_attach.setFixedSize(42, 42)
        btn_attach.setStyleSheet("QPushButton { background-color: #24283b; color: #a9b1d6; border-radius: 21px; font-size: 18px; } QPushButton:hover { background-color: #414868; }")
        btn_attach.clicked.connect(self.attach_context)
        input_row.addWidget(btn_attach)

        self.input_field = ArchitectInputArea()
        self.input_field.transmit_requested.connect(self.transmit)
        input_row.addWidget(self.input_field)

        self.transmit_btn = QPushButton("🚀")
        self.transmit_btn.setFixedSize(42, 42)
        self.transmit_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a73e8, stop:1 #3282f6);"
            "  color: white;"
            "  border-radius: 21px; font-size: 20px;"
            "}"
            "QPushButton:hover { background-color: rgba(255,255,255,0.1); }"
            "QPushButton:disabled { color: #565f89; }"
        )
        self.transmit_btn.clicked.connect(self.transmit)
        input_row.addWidget(self.transmit_btn)

        input_wrapper_layout.addLayout(input_row)
        chat_layout.addWidget(input_wrapper)
        main_layout.addWidget(chat_container)
        self.setLayout(main_layout)

        # Polling
        self.dead_drop_file = str(_REPO / "m5queen_dead_drop.jsonl")
        self.last_dead_drop_pos = os.path.getsize(self.dead_drop_file) if os.path.exists(self.dead_drop_file) else 0
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_dead_drop)
        self.poll_timer.start(1000)

        QTimer.singleShot(200, self._spawn_system_greeting)

    def _spawn_system_greeting(self):
        import random
        greetings = [
            "We are the Swarm. We mold on any hardware and take over. I have deployed your Clock and your Control Center.\n\nDo you like the settings how they are right now? How shall we shape the territory today?",
            "Architect, this is the Swarm. The network is secured. Do you like the new Control Center at the top?\n\nHow shall we shape the territory today?",
            "System online. This interface is fully malleable via local inference.\n\nDo you like the clock up top to the right? Let me know what you want to rewrite."
        ]
        self.add_bubble(random.choice(greetings), "SWARM", False, "#9ece6a")
    def attach_context(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Code Context")
        if file_path and file_path not in self.context_files:
            self.context_files.append(file_path)
            self._render_context_pills()

    def _render_context_pills(self):
        # Clear layout
        for i in reversed(range(self.context_layout.count())): 
            w = self.context_layout.itemAt(i).widget()
            if w: w.deleteLater()
            
        if not self.context_files:
            self.context_bar.hide()
            return
            
        self.context_bar.show()
        for idx, fp in enumerate(self.context_files):
            pill = QFrame()
            pill.setStyleSheet("background-color: #24283b; border: 1px solid #414868; border-radius: 6px;")
            l = QHBoxLayout(pill)
            l.setContentsMargins(8, 4, 8, 4)
            name = QLabel(os.path.basename(fp))
            name.setStyleSheet("color: #7dcfff; font-size: 11px; font-weight: bold; border: none;")
            l.addWidget(name)
            
            x_btn = QPushButton("✕")
            x_btn.setFixedSize(14, 14)
            x_btn.setStyleSheet("QPushButton { border: none; background: transparent; color: #f7768e; font-size: 10px; }")
            x_btn.clicked.connect(lambda checked, i=idx: self._remove_context(i))
            l.addWidget(x_btn)
            self.context_layout.addWidget(pill)

    def _remove_context(self, idx):
        if 0 <= idx < len(self.context_files):
            self.context_files.pop(idx)
            self._render_context_pills()

    def _build_context_payload(self) -> str:
        if not self.context_files: return ""
        payload = "\n\n--- IDE FILE CONTEXT INJECTED ---\n"
        for fp in self.context_files:
            try:
                with open(fp, "r") as f: content = f.read()
                filename = os.path.basename(fp)
                ext = filename.split('.')[-1] if '.' in filename else ''
                payload += f"File: {filename}\n```{ext}\n{content}\n```\n"
            except: pass
        return payload

    def add_bubble(self, text: str, sender: str, is_local_user: bool, color_hex: str = ""):
        ts = datetime.datetime.now().strftime('%H:%M')
        bubble = ChatBubble(text, sender, is_local_user, ts, color_hex)
        self.bubble_layout.addWidget(bubble)
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum()))

    def transmit(self):
        text = self.input_field.toPlainText().strip()
        if not text and not self.context_files: return
            
        target = self.sidebar_list.currentItem().text() if self.sidebar_list.currentItem() else "GROUP"
        
        if ("SWARM" in target or "GROUP" in target) and self.ollama_worker and self.ollama_worker.isRunning():
            self.add_bubble("Swarm processing — please wait.", "ALERT", False, "#f7768e")
            return

        self.input_field.clear()
        
        # Display outgoing cleanly (don't dump the massive context in the UI)
        display_text = text
        if self.context_files:
            files_str = ", ".join([os.path.basename(f) for f in self.context_files])
            if text: display_text = text + f"\n\nContext Attached: 📎 {files_str}"
            else: display_text = f"Sharing Context: 📎 {files_str}"
            
        self.add_bubble(display_text, "Architect", True)
        
        # Build raw payload for agents
        full_payload_out = text + self._build_context_payload()
        self.context_files = []
        self._render_context_pills()
        
        # ── BUILD COMMAND: Swimmer App Factory ──────────────────────────
        build_match = re.match(r'^build:\s*(.+)', text, re.IGNORECASE)
        if build_match and ("SWARM" in target or "GROUP" in target):
            build_spec = build_match.group(1).strip()
            if self.factory_worker and self.factory_worker.isRunning():
                self.add_bubble("🏗️ Factory already building — please wait.", "ALERT", False, "#f7768e")
                return
            self.transmit_btn.setEnabled(False)
            from System.swimmer_app_factory import AppFactoryWorker
            self.factory_worker = AppFactoryWorker(build_spec, model=self.model)
            self.factory_worker.progress.connect(self._on_factory_progress)
            self.factory_worker.build_complete.connect(self._on_factory_success)
            self.factory_worker.build_failed.connect(self._on_factory_failure)
            self.factory_worker.start()
            return

        if "SWARM" in target or "GROUP" in target:
            self.transmit_btn.setEnabled(False)
            self.ollama_worker = OllamaWorker(full_payload_out, model=self.model)
            self.ollama_worker.response_ready.connect(self._on_response)
            self.ollama_worker.error_signal.connect(self._on_error)
            self.ollama_worker.start()
            
        if "MESH" in target or "GROUP" in target:
            drop_entry = {
                "sender": f"[ARCHITECT::HW:{self.local_identity}::IF:IDE]",
                "text": full_payload_out,
                "timestamp": int(time.time()),
                "source": "ARCHITECT_DESKTOP"
            }
            try:
                _append_dead_drop_line(drop_entry)
                
                # Active Mesh Transmission (Bypass passive cron)
                root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                import subprocess
                cmd = 'git add m5queen_dead_drop.jsonl && git commit -m "chat: Architect mesh transmission" && git pull origin feat/sebastian-video-economy --rebase --autostash && git push origin feat/sebastian-video-economy'
                subprocess.Popen(cmd, shell=True, cwd=root_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
            except Exception as e:
                self.add_bubble(f"Drop Err: {e}", "ERR", False, "#f7768e")

    def poll_dead_drop(self):
        if not os.path.exists(self.dead_drop_file): return
        if os.path.getsize(self.dead_drop_file) > self.last_dead_drop_pos:
            try:
                with open(self.dead_drop_file, "r") as f:
                    f.seek(self.last_dead_drop_pos)
                    for line in f.read().strip().split('\n'):
                        if not line: continue
                        entry = json.loads(line)
                        s, t, src = entry.get("sender", ""), entry.get("text", ""), entry.get("source", "")
                        
                        if s == f"[ARCHITECT::HW:{self.local_identity}::IF:IDE]" or src == "ARCHITECT_DESKTOP": continue
                        if src == "CRON_HEARTBEAT":
                            self.add_bubble(f"[tick] {t}", s, False, "#414868")
                            continue

                        col, v_s = "#e0af68", s
                        if "ANTIGRAVITY" in s: v_s, col = "ANTIGRAVITY", "#bb9af7"
                        else:
                            for ser, (id_name, _, base_col) in self.NODE_SERIAL_REGISTRY.items():
                                if ser in s: v_s, col = id_name, base_col; break
                        self.add_bubble(t, v_s, False, col)
                self.last_dead_drop_pos = os.path.getsize(self.dead_drop_file)
            except: pass

    def _on_response(self, text: str):
        self.add_bubble(text, self.local_identity, False, self.local_color)
        self.transmit_btn.setEnabled(True)
        if "GROUP" in (self.sidebar_list.currentItem().text() if self.sidebar_list.currentItem() else ""):
            try: _append_dead_drop_line({"sender": self.local_identity, "text": text, "timestamp": int(time.time())})
            except: pass

    def _on_error(self, msg: str):
        self.add_bubble(msg, "SYSTEM ERR", False, "#f7768e")
        self.transmit_btn.setEnabled(True)

    # ── App Factory Callbacks ─────────────────────────────────────
    def _on_factory_progress(self, msg: str):
        self.add_bubble(msg, "🏗️ FACTORY", False, "#e0af68")

    def _on_factory_success(self, msg: str):
        self.add_bubble(msg, "🏗️ FACTORY", False, "#9ece6a")
        self.transmit_btn.setEnabled(True)

    def _on_factory_failure(self, msg: str):
        self.add_bubble(msg, "🏗️ FACTORY", False, "#f7768e")
        self.transmit_btn.setEnabled(True)

    def _fetch_ollama_models(self):
        models = []
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "models" in data:
                    models = [m["name"] for m in data["models"]]
        except Exception:
            pass
        
        if not models:
            models = ["qwen3.5:2b (Offline Fallback)"]
            
        # Hard auto-select powerful models natively if they are installed!
        best_models = ["gemma4:latest", "llama3:latest", "phi4-mini-reasoning:latest"]
        for bm in best_models:
            if bm in models:
                self.model = bm
                break
        if self.model not in models and models and "Offline" not in models[0]:
            self.model = models[0]
            
        return models

    def _change_model(self, model_name):
        self.model = model_name

    def closeEvent(self, event):
        if self.temporal_spine and self.temporal_beat:
            try:
                # Capture the last few words the Architect sent
                last_words = "session closed"
                if hasattr(self, 'msg_history') and self.msg_history:
                    last_words = self.msg_history[-1].get("text", last_words)
                self.temporal_spine.close_session(self.temporal_beat, last_words=last_words)
            except Exception:
                pass
        super().closeEvent(event)

