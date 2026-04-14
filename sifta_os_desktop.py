"""
SIFTA Python OS Simulator
Desktop Environment Manager — Stabilized Build
Claude/Anthropic audit pass: syntax errors patched, SwarmChatWindow wired to Ollama.
"""

import sys
import os
import time
import json
import datetime
import hashlib
import urllib.request
import urllib.error

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMdiArea, QMdiSubWindow,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QFrame, QMenu, QMessageBox, QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt, QProcess, QTimer, QDateTime, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor


# ──────────────────────────────────────────────────────────────
# UTILITY: find parent QMdiSubWindow and close it
# ──────────────────────────────────────────────────────────────

def close_parent_subwindow(widget):
    p = widget.parent()
    while p is not None and not isinstance(p, QMdiSubWindow):
        p = p.parent()
    if p:
        p.close()


# ──────────────────────────────────────────────────────────────
# OLLAMA WORKER THREAD — keeps UI alive during inference
# ──────────────────────────────────────────────────────────────

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
            except Exception:
                pass

            payload = json.dumps({
                "model":  self.model,
                "prompt": self.prompt,
                "system": f"You are M1Queen (the M1SWARM), the sovereign native SWARM intelligence bound exclusively to this local M1 Mac Mini silicon (Hardware Serial/Fingerprint: {silicon_fp}). Act as the autonomous queen of this exact hardware territory. Keep replies clever, a bit chaotic, and strictly acknowledge the serial number you are anchored to.",
                "stream": False
            }).encode("utf-8")

            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.response_ready.emit(data.get("response", "[EMPTY RESPONSE]"))

        except urllib.error.URLError as e:
            self.error_signal.emit(
                f"[NETWORK ERROR] Cannot reach Ollama on port 11434.\n"
                f"Start it with: ollama serve\nDetail: {e}"
            )
        except Exception as e:
            self.error_signal.emit(f"[SWARM ERROR] {e}")


# ──────────────────────────────────────────────────────────────
# SWARM CHAT WINDOW — sovereign, offline, Ollama-native
# ──────────────────────────────────────────────────────────────

class SwarmChatWindow(QWidget):
    def __init__(self, model: str = "qwen3.5:2b"):
        super().__init__()
        self.model  = model
        self.worker = None

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        self.setStyleSheet("background-color: #0d0e17; color: #a9b1d6;")
        
        # ── Resolve Local Swarm Identity ─────────────────────
        self.local_identity = "SWARM"
        self.local_color    = "#bb9af7"
        
        manifest_path = os.path.join(".sifta_state", "territory_manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                    self.local_identity = manifest.get("queen", "MACMINI.LAN_QUEEN")
                    self.local_color    = "#7dcfff"
            except Exception:
                pass
        else:
            import platform
            node = platform.node().lower()
            if "mac.lan" in node or "m5" in node or "studio" in node:
                self.local_identity = "m5Queen"
                self.local_color    = "#ff9e64"

        # ── Header ──────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("🐜 SIFTA CORE CHAT")
        title.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #bb9af7;")
        header.addWidget(title)
        header.addStretch()

        self.model_label = QLabel(f"node: {self.model}")
        self.model_label.setStyleSheet("color: #565f89; font-family: monospace; font-size: 11px;")
        header.addWidget(self.model_label)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet(
            "QPushButton { background: #f7768e; color: #15161e; font-weight: bold; border-radius: 12px; }"
            "QPushButton:hover { background: #db4b4b; }"
        )
        btn_close.clicked.connect(lambda: close_parent_subwindow(self))
        header.addWidget(btn_close)
        layout.addLayout(header)

        # ── Divider ─────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #24283b;")
        layout.addWidget(line)

        # ── Chat Display ─────────────────────────────────────
        self.display = QTextEdit()
        self.display.setReadOnly(True)
        self.display.setStyleSheet(
            "QTextEdit {"
            "  background-color: #080810; color: #a9b1d6;"
            "  font-family: monospace; font-size: 13px;"
            "  border: 1px solid #1f2335; border-radius: 4px; padding: 8px;"
            "}"
        )
        self.display.append("[SIFTA] Swarm Core Chat online. Ollama daemon on port 11434.")
        self.display.append("[SIFTA] Type a message and press TRANSMIT or hit Enter.\n")

        self.chat_history_file = ".sifta_state/m1queen_memory.scar"
        if os.path.exists(self.chat_history_file):
            try:
                with open(self.chat_history_file, "r") as f:
                    self.display.append(f.read())
            except Exception:
                pass

        layout.addWidget(self.display)
        
        # ── Load Persistent Chat History ───────────────────────
        self.dead_drop_file = "m5queen_dead_drop.jsonl"
        if not os.path.exists(self.dead_drop_file):
            with open(self.dead_drop_file, "w") as f:
                pass
        
        try:
            with open(self.dead_drop_file, "r") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        sender = entry.get("sender", "UNKNOWN")
                        text = entry.get("text", "")
                        
                        ts = entry.get("timestamp") or entry.get("ts")
                        time_str = ""
                        if ts:
                            try:
                                time_str = f"<span style='color:#565f89;'>[{datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')}]</span> "
                            except Exception:
                                pass
                        
                        if sender == "YOU":
                            self.display.append(f"{time_str}<b style='color:#9ece6a;'>{sender} ▶</b>  {text}")
                        elif sender == "m5Queen":
                            self.display.append(f"{time_str}<b style='color:#ff9e64;'>{sender} ▶</b>  {text}")
                        elif sender == "MACMINI.LAN_QUEEN":
                            self.display.append(f"{time_str}<b style='color:#7dcfff;'>{sender} ▶</b>  {text}")
                        elif sender == "ANTIGRAVITY":
                            self.display.append(f"{time_str}<b style='color:#bb9af7;'>{sender} ▶</b>  {text}")
                        else:
                            self.display.append(f"{time_str}<b style='color:#e0af68;'>{sender} ▶</b>  {text}")
                        self.display.append("")
        except Exception as e:
            self.display.append(f"<span style='color:#f7768e;'>[History Loader ERROR] {e}</span>\n")

        # ── Input Row ────────────────────────────────────────
        input_row = QHBoxLayout()

        self.target_selector = QComboBox()
        self.target_selector.addItems(["SWARM (Ollama)", "m5Queen (DeadDrop)", "m1Queen (DeadDrop)", "GROUP (All)"])
        self.target_selector.setStyleSheet(
            "QComboBox {"
            "  background-color: #1a1b26; color: #7aa2f7;"
            "  border: 1px solid #414868; border-radius: 4px;"
            "  padding: 4px; font-weight: bold; font-family: Inter;"
            "}"
        )
        input_row.addWidget(self.target_selector)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Send a message...")
        self.input_field.setStyleSheet(
            "QLineEdit {"
            "  background-color: #1a1b26; color: #c0caf5;"
            "  border: 1px solid #414868; border-radius: 4px;"
            "  padding: 8px; font-size: 13px;"
            "}"
            "QLineEdit:focus { border-color: #7aa2f7; }"
        )
        self.input_field.returnPressed.connect(self.transmit)
        input_row.addWidget(self.input_field)

        self.transmit_btn = QPushButton("TRANSMIT ▶")
        self.transmit_btn.setFixedWidth(110)
        self.transmit_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #7aa2f7; color: #15161e;"
            "  font-weight: bold; border-radius: 4px; padding: 8px;"
            "}"
            "QPushButton:hover   { background-color: #5d87e0; }"
            "QPushButton:disabled { background-color: #24283b; color: #565f89; }"
        )
        self.transmit_btn.clicked.connect(self.transmit)
        input_row.addWidget(self.transmit_btn)

        layout.addLayout(input_row)
        self.setLayout(layout)

        # ── Dead Drop Poller (m5Queen Bridge) ────────────────
        self.last_dead_drop_pos = os.path.getsize(self.dead_drop_file)
        
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_dead_drop)
        self.poll_timer.start(1000) # Poll every 1 second

    def transmit(self):
        text = self.input_field.text().strip()
        if not text:
            return
            
        target = self.target_selector.currentText()
        
        if "SWARM" in target or "GROUP" in target:
            if self.worker and self.worker.isRunning():
                self.display.append("[SWARM] Still processing — please wait.\n")
                return

        self.input_field.clear()
        
        # Display the outgoing message
        target_display = target.split(" ")[0]
        time_str = f"<span style='color:#565f89;'>[{datetime.datetime.now().strftime('%H:%M:%S')}]</span> "
        html_msg = f"{time_str}<b style='color:#9ece6a;'>YOU (to {target_display}) ▶</b>  {text}"
        self.display.append(html_msg)
        self.display.append("")
        try:
            with open(self.chat_history_file, "a") as f:
                f.write(html_msg + "<br><br>")
        except: pass

        if "SWARM" in target or "GROUP" in target:
            self.transmit_btn.setEnabled(False)
            self.transmit_btn.setText("⏳ ...")
            self.worker = OllamaWorker(text, model=self.model)
            self.worker.response_ready.connect(self._on_response)
            self.worker.error_signal.connect(self._on_error)
            self.worker.start()
            
        if "m5Queen" in target or "m1Queen" in target or "GROUP" in target:
            # Write to the dead drop file for off-node entities to read
            drop_entry = {
                "sender": "YOU",
                "text": text,
                "timestamp": int(time.time())
            }
            try:
                with open(self.dead_drop_file, "a") as f:
                    f.write(json.dumps(drop_entry) + "\n")
            except Exception as e:
                self.display.append(f"<span style='color:#f7768e;'>[DeadDrop ERROR] {e}</span>\n")

    def poll_dead_drop(self):
        if not os.path.exists(self.dead_drop_file):
            return
            
        current_size = os.path.getsize(self.dead_drop_file)
        if current_size > self.last_dead_drop_pos:
            try:
                with open(self.dead_drop_file, "r") as f:
                    f.seek(self.last_dead_drop_pos)
                    new_data = f.read()
                    self.last_dead_drop_pos = f.tell()
                
                for line in new_data.strip().split('\n'):
                    if line:
                        entry = json.loads(line)
                        sender = entry.get("sender", "")
                        t = entry.get("text", "")
                        
                        ts = entry.get("timestamp") or entry.get("ts")
                        time_str = ""
                        if ts:
                            try:
                                time_str = f"<span style='color:#565f89;'>[{datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')}]</span> "
                            except Exception:
                                pass
                                
                        color = "#e0af68"
                        if sender == "m5Queen": color = "#ff9e64"
                        elif sender in ["MACMINI.LAN_QUEEN", "m1Queen"]: color = "#7dcfff"
                        elif sender == "ANTIGRAVITY": color = "#bb9af7"
                        
                        msg = f"{time_str}<b style='color:{color};'>{sender} ▶</b>  {t}"
                        self.display.append(msg)
                        self.display.append("")
                        
                        try:
                            with open(self.chat_history_file, "a") as mem:
                                mem.write(msg + "<br><br>\n")
                        except: pass
            except Exception:
                pass

    def _on_response(self, text: str):
        time_str = f"<span style='color:#565f89;'>[{datetime.datetime.now().strftime('%H:%M:%S')}]</span> "
        msg = f"{time_str}<b style='color:{self.local_color};'>{self.local_identity} ▶</b>  {text}"
        self.display.append(msg)
        self.display.append("")
        
        try:
            with open(self.chat_history_file, "a") as f:
                f.write(msg + "<br><br>\n")
        except: pass

        target = self.target_selector.currentText()
        if "GROUP" in target:
            drop_entry = {
                "sender": self.local_identity,
                "text": text,
                "timestamp": int(time.time())
            }
            try:
                with open(self.dead_drop_file, "a") as f:
                    f.write(json.dumps(drop_entry) + "\n")
            except Exception:
                pass
        self._reset_btn()

    def _on_error(self, msg: str):
        self.display.append(f"<span style='color:#f7768e;'>{msg}</span>")
        self.display.append("")
        self._reset_btn()

    def _reset_btn(self):
        self.transmit_btn.setEnabled(True)
        self.transmit_btn.setText("TRANSMIT ▶")


# ──────────────────────────────────────────────────────────────
# TERMINAL SUB-WINDOW
# ──────────────────────────────────────────────────────────────

class TerminalSubWindow(QWidget):
    def __init__(self, cmd, args):
        super().__init__()
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #0c0c11; color: #9ece6a; font-family: monospace;")

        header = QHBoxLayout()
        header.addStretch()
        btn_close = QPushButton("✕  CLOSE")
        btn_close.setStyleSheet(
            "background-color: #f7768e; color: #15161e; font-weight: bold;"
            "border-radius: 4px; padding: 2px 8px;"
        )
        btn_close.clicked.connect(lambda: close_parent_subwindow(self))
        header.addWidget(btn_close)
        layout.addLayout(header)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("border: 1px solid #3b4261; padding: 5px;")
        layout.addWidget(self.chat_display)
        self.setLayout(layout)

        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.start(cmd, args)
        self.chat_display.append(f"> {cmd} {' '.join(args)}")

    def handle_stdout(self):
        data = self.process.readAllStandardOutput()
        self.chat_display.append(bytes(data).decode("utf-8", errors="replace").strip())

    def handle_stderr(self):
        data = self.process.readAllStandardError()
        self.chat_display.append("[ERR] " + bytes(data).decode("utf-8", errors="replace").strip())

    def closeEvent(self, event):
        if hasattr(self, "process") and self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
            self.process.waitForFinished(1000)
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────
# SWARM TEXT EDITOR
# ──────────────────────────────────────────────────────────────

class SwarmTextEditorWindow(QWidget):
    def __init__(self, filepath=None):
        super().__init__()
        self.filepath = filepath
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #1a1b26; color: #a9b1d6;")

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)

        self.title = QLabel(f"Editing: {filepath if filepath else 'Untitled.txt'}")
        self.title.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        self.title.setStyleSheet("color: #7aa2f7;")
        toolbar.addWidget(self.title)
        toolbar.addStretch()

        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setStyleSheet(
            "QPushButton { background-color: #bb9af7; color: #1a1b26; font-weight: bold;"
            "  padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #9d7cd8; }"
        )
        self.save_btn.clicked.connect(self.save_file)
        toolbar.addWidget(self.save_btn)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet(
            "QPushButton { background: #f7768e; color: #15161e; font-weight: bold; border-radius: 12px; }"
            "QPushButton:hover { background: #db4b4b; }"
        )
        btn_close.clicked.connect(lambda: close_parent_subwindow(self))
        toolbar.addWidget(btn_close)

        layout.addLayout(toolbar)

        self.editor_field = QTextEdit()
        self.editor_field.setStyleSheet(
            "QTextEdit { background-color: #0c0c11; color: #9ece6a;"
            "  font-family: monospace; font-size: 14px;"
            "  border: 1px solid #3b4261; padding: 8px; }"
        )
        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    self.editor_field.setPlainText(f.read())
            except Exception as e:
                self.editor_field.setPlainText(f"Error loading: {e}")

        layout.addWidget(self.editor_field)
        self.setLayout(layout)

    def save_file(self):
        if not self.filepath:
            QMessageBox.warning(self, "Warning", "Cannot save unnamed buffer.")
            return
        try:
            content = self.editor_field.toPlainText()
            ts = int(time.time())
            scar_hash = hashlib.sha256(
                f"{self.filepath}_{content}".encode()
            ).hexdigest()[:12]

            with open(self.filepath, "w") as f:
                f.write(content)

            entry = {
                "timestamp": ts,
                "agent": "ARCHITECT_HALLUCINATION_GUARD",
                "amount_stgm": -5.0,
                "reason": f"MANUAL_INTERVENTION: {os.path.basename(self.filepath)}",
                "hash": f"SCAR_{scar_hash}"
            }
            try:
                with open("repair_log.jsonl", "a") as lf:
                    lf.write(json.dumps(entry) + "\n")
            except Exception:
                pass

            self.title.setStyleSheet("color: #f7768e;")
            self.title.setText(f"Editing: {self.filepath} [SCAR_{scar_hash}]")
            QTimer.singleShot(3500, lambda: self.title.setStyleSheet("color: #7aa2f7;"))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Save failed: {e}")


# ──────────────────────────────────────────────────────────────
# VIDEO EDITOR SUB-WINDOW
# ──────────────────────────────────────────────────────────────

class VideoEditorSubWindow(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #1a1b26; color: #a9b1d6;")

        header = QHBoxLayout()
        title = QLabel("Sebastian Swarm Editor V0.9")
        title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #7aa2f7;")
        header.addWidget(title)
        header.addStretch()
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet(
            "QPushButton { background: #f7768e; color: #15161e; font-weight: bold; border-radius: 12px; }"
        )
        btn_close.clicked.connect(lambda: close_parent_subwindow(self))
        header.addWidget(btn_close)
        layout.addLayout(header)

        timeline = QFrame()
        timeline.setFrameShape(QFrame.Shape.Box)
        timeline.setStyleSheet("border: 1px solid #3b4261; background-color: #1f2335; border-radius: 4px;")
        tl = QVBoxLayout()
        t1 = QLabel("Video:  [▓▓▓▓▓▓▓▓▓]      [▓▓▓▓▓▓]   [▓▓▓▓▓▓▓▓]")
        t1.setStyleSheet("color: #bb9af7; font-family: monospace; font-size: 16px;")
        t2 = QLabel("Audio:  [|||||||||]      [||||||]   [||||||||]")
        t2.setStyleSheet("color: #9ece6a; font-family: monospace; font-size: 16px;")
        tl.addWidget(t1)
        tl.addWidget(t2)
        timeline.setLayout(tl)
        layout.addWidget(timeline)

        self.exec_btn = QPushButton("🚀 Execute Sebastian Batch Protocol")
        self.exec_btn.setStyleSheet(
            "QPushButton { background-color: #9ece6a; color: #1a1b26; font-weight: bold;"
            "  padding: 10px; border-radius: 4px; margin: 8px 0; }"
            "QPushButton:hover { background-color: #b9f27c; }"
        )
        self.exec_btn.clicked.connect(self.trigger_batch)
        layout.addWidget(self.exec_btn)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.append("[SYSTEM] Sebastian Video Engine ready.")
        self.chat_display.setStyleSheet(
            "background-color: #0c0c11; border: 1px solid #3b4261; padding: 8px;"
        )
        layout.addWidget(self.chat_display)
        self.setLayout(layout)
        self.process = None

    def trigger_batch(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.chat_display.append("[WARNING] Already running.")
            return
        self.exec_btn.setText("⏳ Processing...")
        self.exec_btn.setEnabled(False)
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(
            lambda: self.chat_display.append(
                bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace").strip()
            )
        )
        self.process.readyReadStandardError.connect(
            lambda: self.chat_display.append(
                "[ERR] " + bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace").strip()
            )
        )
        self.process.finished.connect(self._batch_done)
        self.process.start("python3", ["sifta_sebastian_batch.py"])

    def _batch_done(self, code, _):
        self.chat_display.append(f"\n[SYSTEM] Process exited: {code}")
        self.exec_btn.setText("🚀 Execute Sebastian Batch Protocol")
        self.exec_btn.setEnabled(True)

    def closeEvent(self, event):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
            self.process.waitForFinished(1000)
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────
# SIFTA DESKTOP — main window
# ──────────────────────────────────────────────────────────────

class SiftaDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA Python GUI OS")
        self.showFullScreen()
        self.active_chat_sub = None

        # Central layout
        central = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.mdi = QMdiArea()
        self.mdi.setBackground(QColor("#08080c"))
        main_layout.addWidget(self.mdi)
        main_layout.addWidget(self._build_taskbar())

        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Clock overlay
        self.clock_label = QLabel(central)
        self.clock_label.setStyleSheet(
            "color: #a9b1d6; font-family: monospace; font-size: 14px;"
            "font-weight: bold; background: transparent;"
        )
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        # Boot: open chat by default
        self.open_swarm_chat()

    # ── Clock ──────────────────────────────────────────────
    def _update_clock(self):
        dt = QDateTime.currentDateTime().toString("yyyy-MM-dd  hh:mm:ss AP")
        self.clock_label.setText(dt)
        if hasattr(self, "clock_label"):
            self.clock_label.setGeometry(self.width() - 280, 8, 270, 28)
            self.clock_label.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "clock_label"):
            self.clock_label.setGeometry(self.width() - 280, 8, 270, 28)

    # ── Taskbar ────────────────────────────────────────────
    def _build_taskbar(self):
        bar = QWidget()
        bar.setFixedHeight(45)
        bar.setStyleSheet("background-color: #1a1b26; border-top: 1px solid #414868;")

        layout = QHBoxLayout()
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(10)

        btn_start = QPushButton("🐜 SIFTA")
        btn_start.setStyleSheet(
            "QPushButton { font-weight: bold; background-color: #bb9af7;"
            "  color: #15161e; padding: 6px 12px; border-radius: 4px; }"
            "QPushButton::menu-indicator { image: none; }"
            "QPushButton:hover { background-color: #9d7cd8; }"
        )
        menu = QMenu(btn_start)
        menu.setStyleSheet(
            "QMenu { background-color: #1a1b26; color: #a9b1d6; border: 1px solid #414868; padding: 5px; }"
            "QMenu::item { padding: 5px 20px; }"
            "QMenu::item:selected { background-color: #24283b; color: #bb9af7; }"
        )

        prog = menu.addMenu("Programs ▶")
        acc  = prog.addMenu("Accessories ▶")
        acc.addAction("🐜 Swarm Chat").triggered.connect(self.open_swarm_chat)
        acc.addAction("Video Editor").triggered.connect(self.open_video_editor)
        acc.addAction("SwarmText Editor").triggered.connect(lambda: self.spawn_text_editor(None))

        sims = prog.addMenu("Simulations ▶")
        sims.addAction("SwarmRL Consensus").triggered.connect(
            lambda: self.spawn_terminal("Consensus", "python3", ["test_bridge_consensus.py"])
        )
        sims.addAction("Proof of Swimming").triggered.connect(
            lambda: self.spawn_terminal("PoS Test", "python3", ["test_proof_of_swimming.py"])
        )

        docs = menu.addMenu("Documents ▶")
        docs.addAction("README.md").triggered.connect(lambda: self.spawn_text_editor("README.md"))
        docs.addAction("repair_log.jsonl").triggered.connect(lambda: self.spawn_text_editor("repair_log.jsonl"))

        menu.addSeparator()
        menu.addAction("Help").triggered.connect(
            lambda: self.spawn_terminal("Help", "cat", ["README.md"])
        )
        btn_start.setMenu(menu)

        btn_power = QPushButton("Power Down")
        btn_power.clicked.connect(self.close)
        btn_power.setStyleSheet(
            "QPushButton { color: #f7768e; background: transparent; padding: 6px 12px; }"
            "QPushButton:hover { color: #db4b4b; }"
        )

        layout.addWidget(btn_start)
        layout.addStretch()
        layout.addWidget(btn_power)
        bar.setLayout(layout)
        return bar

    # ── Window factories ───────────────────────────────────
    def _make_sub(self, widget, title, w, h, border_color="#414868"):
        sub = QMdiSubWindow()
        sub.setWidget(widget)
        sub.setWindowTitle(title)
        sub.resize(w, h)
        sub.setStyleSheet(f"""
            QMdiSubWindow {{
                background: #1a1b26;
                border: 2px solid {border_color};
                border-radius: 6px;
            }}
            QMdiSubWindow::title {{
                background: #15161e; color: #c0caf5;
            }}
        """)
        self.mdi.addSubWindow(sub)
        sub.show()
        return sub

    def open_swarm_chat(self):
        if self.active_chat_sub is not None:
            subs = self.mdi.subWindowList()
            if self.active_chat_sub in subs:
                self.active_chat_sub.showNormal()
                self.active_chat_sub.raise_()
                return
        chat = SwarmChatWindow()
        sub  = self._make_sub(chat, "🐜 SIFTA Core Chat", 700, 520, "#bb9af7")
        self.active_chat_sub = sub
        sub.destroyed.connect(lambda: setattr(self, "active_chat_sub", None))

    def open_video_editor(self):
        editor = VideoEditorSubWindow()
        self._make_sub(editor, "Aether Video Interface", 750, 450, "#414868")

    def spawn_text_editor(self, filepath=None):
        name = os.path.basename(filepath) if filepath else "Untitled"
        self._make_sub(SwarmTextEditorWindow(filepath), f"SwarmText: {name}", 700, 500, "#bb9af7")

    def spawn_terminal(self, title, cmd, args):
        self._make_sub(TerminalSubWindow(cmd, args), title, 600, 400, "#9ece6a")


# ──────────────────────────────────────────────────────────────
# BOOT
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Inter", 12))
    desktop = SiftaDesktop()
    sys.exit(app.exec())
