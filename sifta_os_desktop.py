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
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMdiArea, QMdiSubWindow,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QFrame, QMenu, QMessageBox, QLineEdit, QComboBox, QListWidget
)
from PyQt6.QtCore import Qt, QProcess, QProcessEnvironment, QTimer, QDateTime, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

_REPO = Path(__file__).resolve().parent
_SYS = _REPO / "System"

# ── Swarm Intelligence Subsystems ────────────────────────────
if str(_SYS) not in sys.path:
    sys.path.insert(0, str(_SYS))

from app_fitness import ranked_apps, record_crash, record_launch  # noqa: E402
from stigmergic_wm import neighbors as wm_neighbors  # noqa: E402
from stigmergic_wm import record_open as wm_record_open  # noqa: E402
from stigmergic_wm import reset_session as wm_reset_session  # noqa: E402
from stigmergic_wm import suggest_position  # noqa: E402
from pheromone_fs import clusters as fs_clusters  # noqa: E402
from pheromone_fs import neighbors as fs_neighbors  # noqa: E402
from pheromone_fs import record_access as fs_record_access  # noqa: E402


def _append_repair_log_line(row: dict) -> None:
    if str(_SYS) not in sys.path:
        sys.path.insert(0, str(_SYS))
    from ledger_append import append_ledger_line

    append_ledger_line(_REPO / "repair_log.jsonl", row)


def _append_dead_drop_line(row: dict) -> None:
    if str(_SYS) not in sys.path:
        sys.path.insert(0, str(_SYS))
    from ledger_append import append_jsonl_line

    append_jsonl_line(_REPO / "m5queen_dead_drop.jsonl", row)


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
                "http://127.0.0.1:11434/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                
                # ── SWARM MINING (Proof of Inference) ──
                try:
                    import os, sys, time, hashlib
                    _sysd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "System")
                    if _sysd not in sys.path:
                        sys.path.insert(0, _sysd)
                    from silicon_serial import read_apple_serial
                    serial = read_apple_serial()
                    # Hardware-bound identity
                    miner_id = "M5SIFTA_BODY" if "GTH4921YP3" in serial else "M1SIFTA_BODY" 
                    state_file = f".sifta_state/{miner_id}.json"
                    
                    if os.path.exists(state_file):
                        with open(state_file, "r") as sf:
                            mdata = json.load(sf)
                        mdata["stgm_balance"] = float(mdata.get("stgm_balance", 0.0)) + 1.0
                        with open(state_file, "w") as sf:
                            json.dump(mdata, sf, indent=2)
                        
                        ts = int(time.time())
                        sig_str = f"{miner_id}:1.0:INFERENCE_MINING:{ts}:{serial}"
                        tx_hash = "MINED_" + hashlib.sha256(sig_str.encode()).hexdigest()[:12]
                        tx = {
                            "timestamp": ts,
                            "agent_id": miner_id,
                            "tx_type": "STGM_MINT",
                            "amount": 1.0,
                            "reason": "Proof of Inference (Local Silicon)",
                            "hash": tx_hash
                        }
                        _append_repair_log_line(tx)
                except Exception as e:
                    print(f"Mining error: {e}")
                    
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

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setStyleSheet("background-color: #0d0e17; color: #a9b1d6;")
        
        # ── Left Sidebar (Nodes/Groups) ───────────────
        sidebar_frame = QFrame()
        sidebar_frame.setFixedWidth(240)
        sidebar_frame.setStyleSheet("background-color: #15161e; border-right: 1px solid #1f2335;")
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(10, 15, 10, 10)
        
        sidebar_title = QLabel("📡 SIFTA NODES")
        sidebar_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        sidebar_title.setStyleSheet("color: #7aa2f7; border: none;")
        sidebar_layout.addWidget(sidebar_title)
        
        self.sidebar_list = QListWidget()
        self.sidebar_list.setStyleSheet(
            "QListWidget {"
            "  background-color: transparent; border: none; color: #c0caf5; font-size: 13px;"
            "}"
            "QListWidget::item { padding: 12px; border-radius: 6px; margin-bottom: 2px; }"
            "QListWidget::item:hover { background-color: #1a1b26; }"
            "QListWidget::item:selected { background-color: #24283b; color: #7dcfff; font-weight: bold; }"
        )
        chat_targets = ["GROUP (All)", "m5Queen (Mesh)", "m1Queen (Mesh)", "SWARM (Ollama)", "ANTIGRAVITY (IDE)"]
        self.sidebar_list.addItems(chat_targets)
        self.sidebar_list.setCurrentRow(0)
        sidebar_layout.addWidget(self.sidebar_list)
        main_layout.addWidget(sidebar_frame)
        
        # ── Right Side (Chat Area) ────────────────────
        chat_container = QWidget()
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(15, 15, 15, 15)
        
        # ── Resolve Local Swarm Identity from bare-metal serial ──────
        # Same registry used by circadian_rhythm.py + body_state.py.
        # No hostname guessing. No hardcoded strings. Silicon is truth.
        self.NODE_SERIAL_REGISTRY = {
            "GTH4921YP3":   ("ALICE_M5",  "[_o_]", "#ff9e64"),   # M5 Mac Studio
            "C07FL0JAQ6NV": ("M1THER",    "[O_O]", "#7dcfff"),   # M1 Mac Mini
        }
        try:
            import sys as _sys
            _sysd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "System")
            if _sysd not in _sys.path:
                _sys.path.insert(0, _sysd)
            from silicon_serial import read_apple_serial
            _serial = read_apple_serial()
        except Exception:
            _serial = "UNKNOWN"

        _node = self.NODE_SERIAL_REGISTRY.get(_serial)
        if _node:
            self.local_identity = _node[0]   # e.g. "ALICE_M5" or "M1THER"
            self.local_face     = _node[1]   # e.g. "[_o_]"
            self.local_color    = _node[2]
            self.local_serial   = _serial
        else:
            self.local_identity = f"SWARM_VOICE_{_serial[:6]}"
            self.local_face     = "[?_?]"
            self.local_color    = "#bb9af7"
            self.local_serial   = _serial

        # ── Header ──────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("🐜 SIFTA CORE CHAT")
        title.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #565f89;")
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
        chat_layout.addLayout(header)

        # ── Divider ─────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #24283b;")
        chat_layout.addWidget(line)

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

        chat_layout.addWidget(self.display)
        
        # ── Load Persistent Chat History ───────────────────────
        self.dead_drop_file = str(_REPO / "m5queen_dead_drop.jsonl")
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
                        
                        display_name = sender
                        color = "#e0af68"
                        if "YOU" in sender or sender.startswith("[ARCHITECT"):
                            display_name = "[ ARCHITECT ]"
                            color = "#9ece6a"
                        elif "ANTIGRAVITY" in sender:
                            display_name = "ANTIGRAVITY"
                            color = "#bb9af7"
                        else:
                            for ser, (ident, face, col) in self.NODE_SERIAL_REGISTRY.items():
                                if ser in sender:
                                    display_name = f"{ident} ({ser})"
                                    color = col
                                    break
                        self.display.append(f"{time_str}<b style='color:{color};'>{display_name} ▶</b>  {text}")
                        self.display.append("")
        except Exception as e:
            self.display.append(f"<span style='color:#f7768e;'>[History Loader ERROR] {e}</span>\n")

        # ── Input Row ────────────────────────────────────────
        input_row = QHBoxLayout()

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

        chat_layout.addLayout(input_row)
        main_layout.addWidget(chat_container)
        self.setLayout(main_layout)

        # ── Dead Drop Poller (m5Queen Bridge) ────────────────
        self.last_dead_drop_pos = os.path.getsize(self.dead_drop_file)
        
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_dead_drop)
        self.poll_timer.start(1000) # Poll every 1 second

    def transmit(self):
        text = self.input_field.text().strip()
        if not text:
            return
            
        target = self.sidebar_list.currentItem().text() if self.sidebar_list.currentItem() else "GROUP (All)"
        
        if "SWARM" in target or "GROUP" in target:
            if self.worker and self.worker.isRunning():
                self.display.append("[SWARM] Still processing — please wait.\n")
                return

        self.input_field.clear()
        
        # Display the outgoing message
        target_display = target.split(" ")[0]
        time_str = f"<span style='color:#565f89;'>[{datetime.datetime.now().strftime('%H:%M:%S')}]</span> "
        network_id = f"[ARCHITECT::HW:{self.local_identity}::IF:SWARM_OS]"
        html_msg = f"{time_str}<b style='color:#9ece6a;'>[ ARCHITECT ] (to {target_display}) ▶</b>  {text}"
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
            
        if "m5Queen" in target or "m1Queen" in target or "GROUP" in target or "ANTIGRAVITY" in target:
            # Write to the dead drop file for off-node entities to read
            drop_entry = {
                "sender": network_id,
                "text": text,
                "timestamp": int(time.time())
            }
            try:
                _append_dead_drop_line(drop_entry)
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
                                
                        source = entry.get("source", "HUMAN")
                        is_cron = (source == "CRON_HEARTBEAT")

                        # Color and Name by mapped hardware serial logic
                        color = "#e0af68"
                        visual_sender = sender
                        
                        if sender.startswith("[ARCHITECT") or sender == "YOU":
                            visual_sender = "[ ARCHITECT ]"
                            color = "#9ece6a"
                        elif "ANTIGRAVITY" in sender or sender.startswith("[A_G::"):
                            visual_sender = "ANTIGRAVITY"
                            color = "#bb9af7"
                        elif sender.startswith("[C_C::"):
                            color = "#f7768e"
                        else:
                            for ser, (ident, face, col) in self.NODE_SERIAL_REGISTRY.items():
                                if ser in sender:
                                    visual_sender = f"{ident} ({ser})"
                                    color = col
                                    break

                        # Skip local echo of our own messages
                        local_network_id = f"[ARCHITECT::HW:{self.local_identity}::IF:SWARM_OS]"
                        if sender == local_network_id:
                            continue

                        # Cron heartbeats render dim — human messages are bold/dominant
                        if is_cron:
                            msg = f"{time_str}<span style='color:#3b4261; font-size:10px;'>⬡ {visual_sender} {t}</span>"
                        else:
                            msg = f"{time_str}<b style='color:{color};'>{visual_sender} ▶</b>  {t}"
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

        target = self.sidebar_list.currentItem().text() if self.sidebar_list.currentItem() else "GROUP (All)"
        if "GROUP" in target:
            drop_entry = {
                "sender": self.local_identity,
                "text": text,
                "timestamp": int(time.time())
            }
            try:
                _append_dead_drop_line(drop_entry)
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
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", os.getcwd())
        self.process.setProcessEnvironment(env)
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
# EMBEDDED SCRIPT APP WINDOW (forced in-OS launch)
# ──────────────────────────────────────────────────────────────

class EmbeddedScriptSubWindow(QWidget):
    """Runs a python app script inside an MDI window.
    Unlike terminal launching, this forces a non-popout plotting backend
    so menu apps stay inside iSwarm OS."""

    def __init__(self, app_title: str, script_path: str):
        super().__init__()
        self.app_title = app_title
        self.script_path = script_path
        layout = QVBoxLayout()
        self.setStyleSheet("background-color: #0c0c11; color: #9ece6a; font-family: monospace;")

        header = QHBoxLayout()
        title = QLabel(f"{app_title} — embedded runtime")
        title.setStyleSheet("color: #7aa2f7; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        btn_restart = QPushButton("↻ Restart")
        btn_restart.setStyleSheet(
            "QPushButton { background-color: #9ece6a; color: #15161e; font-weight: bold; border-radius: 4px; padding: 3px 8px; }"
            "QPushButton:hover { background-color: #b9f27c; }"
        )
        btn_restart.clicked.connect(self._start)
        header.addWidget(btn_restart)
        btn_close = QPushButton("✕  CLOSE")
        btn_close.setStyleSheet(
            "background-color: #f7768e; color: #15161e; font-weight: bold;"
            "border-radius: 4px; padding: 2px 8px;"
        )
        btn_close.clicked.connect(lambda: close_parent_subwindow(self))
        header.addWidget(btn_close)
        layout.addLayout(header)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("border: 1px solid #3b4261; padding: 5px;")
        layout.addWidget(self.log)
        self.setLayout(layout)

        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_merged)
        self._start()

    def _start(self):
        if self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
            self.process.waitForFinished(1000)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", os.getcwd())
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("SIFTA_EMBEDDED", "1")
        env.insert("MPLBACKEND", "Agg")
        self.process.setProcessEnvironment(env)
        self.process.start("python3", [self.script_path])
        self.log.append(f"> python3 {self.script_path}")
        self.log.append("[iSwarm] Embedded mode forced (MPLBACKEND=Agg)")

    def _read_merged(self):
        data = self.process.readAllStandardOutput()
        txt = bytes(data).decode("utf-8", errors="replace").strip()
        if txt:
            self.log.append(txt)

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
                _append_repair_log_line(entry)
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
        self._apps_manifest_cache: dict[str, dict] = {}

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

        # ── Swarm Intelligence boot ────────────────────────
        wm_reset_session()
        self._open_windows: dict[str, tuple[int, int]] = {}

        # Show dream report if one exists for today
        try:
            from dream_engine import latest_report
            dream = latest_report()
            if dream:
                self._boot_dream = dream
        except Exception:
            self._boot_dream = None

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
        creative = prog.addMenu("Creative ▶")
        sims = prog.addMenu("Simulations ▶")
        net  = prog.addMenu("Networking ▶")
        sys_menu = prog.addMenu("System ▶")

        # ── Core Built-in OS Apps ────────────────────────
        acc.addAction("🐜 Swarm Chat").triggered.connect(self.open_swarm_chat)
        acc.addAction("Video Editor").triggered.connect(self.open_video_editor)
        acc.addAction("SwarmText Editor").triggered.connect(lambda: self.spawn_text_editor(None))

        # ── Dynamic Native Apps (sorted by fitness) ────────
        manifest_path = "Applications/apps_manifest.json"
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r") as f:
                    apps = json.load(f)
                self._apps_manifest_cache = dict(apps)
                app_names_sorted = ranked_apps(list(apps.keys()))
                for app_name in app_names_sorted:
                    app_data = apps[app_name]
                    cat = app_data.get("category", "Accessories")
                    entry = app_data.get("entry_point", "")
                    widget_class = app_data.get("widget_class", "")
                    if not entry:
                        continue

                    target_menu = acc
                    if cat == "Simulations":
                        target_menu = sims
                    elif cat == "Creative":
                        target_menu = creative
                    elif cat == "Networking":
                        target_menu = net
                    elif cat == "System":
                        target_menu = sys_menu

                    app_sub = target_menu.addMenu(f"{app_name} ▶")
                    app_sub.addAction("Open").triggered.connect(
                        (
                            (lambda nm, ep, wc, dat: lambda: self._launch_app(
                                nm,
                                ep,
                                wc,
                                w=int(dat.get("window_width", 920)),
                                h=int(dat.get("window_height", 640)),
                            ))(app_name, entry, widget_class, dict(app_data))
                            if widget_class
                            else (lambda nm, e: lambda: self._launch_terminal_app(nm, e))(app_name, entry)
                        )
                    )
                    app_sub.addAction("Help").triggered.connect(
                        (lambda nm, data: lambda: self._show_app_help(nm, dict(data)))(app_name, app_data)
                    )
            except Exception as e:
                print(f"[Boot Error] Failed to load apps manifest: {e}")

        # ── Swarm Intelligence submenu ─────────────────────
        intel = menu.addMenu("Swarm Intelligence ▶")
        intel.setStyleSheet(
            "QMenu { background-color: #1a1b26; color: #a9b1d6; border: 1px solid #414868; padding: 5px; }"
            "QMenu::item { padding: 5px 20px; }"
            "QMenu::item:selected { background-color: #24283b; color: #bb9af7; }"
        )
        intel.addAction("🧠 Dream Report").triggered.connect(self._show_dream_report)
        intel.addAction("🛡 Immune Status").triggered.connect(self._show_immune_status)
        intel.addAction("🗳 Quorum Proposals").triggered.connect(self._show_quorum_status)
        intel.addAction("⚡ Nerve Channel").triggered.connect(self._show_nerve_status)
        intel.addAction("🗺 File Trails").triggered.connect(self._show_file_trails)
        intel.addAction("📊 App Fitness").triggered.connect(self._show_fitness_scores)

        docs = menu.addMenu("Documents ▶")
        docs.addAction("README.md").triggered.connect(lambda: self.spawn_text_editor("Documents/README.md"))
        docs.addAction("APP_HELP.md").triggered.connect(lambda: self.spawn_text_editor("Documents/APP_HELP.md"))
        docs.addAction("repair_log.jsonl").triggered.connect(lambda: self.spawn_text_editor("Utilities/repair_log.jsonl"))

        menu.addSeparator()
        finance_menu = menu.addMenu("Finance ▶")
        finance_menu.addAction("⚡ Swarm Finance").triggered.connect(
            lambda: self.spawn_native_widget(
                "Swarm Finance", "Applications/sifta_finance.py", "FinanceDashboard",
                w=480, h=640, x=420, y=30
            )
        )

        menu.addSeparator()
        menu.addAction("Help").triggered.connect(
            lambda: self.spawn_text_editor("Documents/APP_HELP.md")
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
    def _make_sub(self, widget, title, w, h, border_color="#414868", x=None, y=None):
        sub = QMdiSubWindow()
        sub.setWindowFlags(
            Qt.WindowType.SubWindow
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )
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
        if x is not None and y is not None:
            sub.move(x, y)
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
        sub  = self._make_sub(chat, "🐜 SIFTA CORE CHAT", 700, 520, "#565f89")
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

    def spawn_embedded_script(self, title, script_path):
        self._make_sub(EmbeddedScriptSubWindow(title, script_path), title, 860, 560, "#9ece6a")

    # ── Swarm-intelligent app launcher ───────────────────
    def _launch_app(self, title, module_path, class_name, w=660, h=540):
        """Launch an app: record fitness, WM pheromone, suggest position."""
        record_launch(title)
        wm_record_open(title)
        fs_record_access(module_path)

        pos = suggest_position(title, self._open_windows)
        x, y = (pos if pos else (None, None))
        self.spawn_native_widget(title, module_path, class_name, w=w, h=h, x=x, y=y)

    def _launch_terminal_app(self, title, entry):
        """Launch a script app inside iSwarm OS (no external popout intent)."""
        record_launch(title)
        wm_record_open(title)
        fs_record_access(entry)
        self.spawn_embedded_script(title, entry)

    def spawn_native_widget(self, title, module_path, class_name, w=660, h=540, x=None, y=None):
        """Import a SIFTA app module and embed its widget class inside the MDI.
        No subprocess. No separate QApplication. Stays inside Swarm OS."""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                class_name, os.path.join(os.getcwd(), module_path)
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            widget_cls = getattr(mod, class_name)
            widget = widget_cls()
            sub = self._make_sub(widget, f"⚙ {title}", w, h, "#7aa2f7", x=x, y=y)
            self._open_windows[title] = (sub.x(), sub.y())
            sub.destroyed.connect(lambda: self._open_windows.pop(title, None))
        except Exception as e:
            record_crash(title)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Launch Error", f"Failed to load {title}:\n{e}")

    # ── Swarm Intelligence Panels ──────────────────────────
    def _show_dream_report(self):
        from PyQt6.QtWidgets import QPlainTextEdit
        try:
            from dream_engine import run_dream_cycle
            report = run_dream_cycle()
        except Exception as e:
            report = f"[Dream engine error] {e}"
        w = QPlainTextEdit()
        w.setReadOnly(True)
        w.setPlainText(report)
        w.setStyleSheet(
            "QPlainTextEdit { background: #0b1020; color: #bb9af7; "
            "font-family: monospace; font-size: 12px; padding: 12px; }"
        )
        self._make_sub(w, "🧠 Dream Report", 700, 480, "#bb9af7")

    def _show_immune_status(self):
        from PyQt6.QtWidgets import QPlainTextEdit
        try:
            from immune_memory import immune_status
            status = immune_status()
            lines = [
                "IMMUNE MEMORY STATUS",
                "=" * 40,
                f"Total antibodies:  {status['total_antibodies']}",
                f"Total matches:     {status['total_matches']}",
                f"Strongest:         {status['strongest']:.2f}",
                "",
                "Pattern types:",
            ]
            for t, c in status.get("types", {}).items():
                lines.append(f"  {t}: {c}")
            text = "\n".join(lines)
        except Exception as e:
            text = f"[Immune system error] {e}"
        w = QPlainTextEdit()
        w.setReadOnly(True)
        w.setPlainText(text)
        w.setStyleSheet(
            "QPlainTextEdit { background: #0b1020; color: #f7768e; "
            "font-family: monospace; font-size: 12px; padding: 12px; }"
        )
        self._make_sub(w, "🛡 Immune Memory", 600, 400, "#f7768e")

    def _show_quorum_status(self):
        from PyQt6.QtWidgets import QPlainTextEdit
        try:
            from quorum_sense import active_proposals
            props = active_proposals()
            if not props:
                text = "No active quorum proposals.\n\nThe Swarm is at peace."
            else:
                lines = ["ACTIVE QUORUM PROPOSALS", "=" * 50]
                for p in props:
                    lines.append(
                        f"  [{p['action_id']}] {p['type']}  "
                        f"votes: {p['votes']}/{p['needed']}  age: {p['age_sec']}s"
                    )
                text = "\n".join(lines)
        except Exception as e:
            text = f"[Quorum sense error] {e}"
        w = QPlainTextEdit()
        w.setReadOnly(True)
        w.setPlainText(text)
        w.setStyleSheet(
            "QPlainTextEdit { background: #0b1020; color: #e0af68; "
            "font-family: monospace; font-size: 12px; padding: 12px; }"
        )
        self._make_sub(w, "🗳 Quorum Sense", 620, 360, "#e0af68")

    def _show_nerve_status(self):
        from PyQt6.QtWidgets import QPlainTextEdit
        try:
            from nerve_channel import NERVE_PORT, NerveSignal, encode_pulse, decode_pulse
            test = encode_pulse(NerveSignal.HEARTBEAT, 100, "GTH4921YP3")
            decoded = decode_pulse(test)
            lines = [
                "NERVE CHANNEL STATUS",
                "=" * 50,
                f"Protocol:     UDP port {NERVE_PORT}",
                f"Datagram:     {len(test)} bytes",
                f"Test decode:  signal={decoded['signal'].name}  intensity={decoded['intensity']}",
                "",
                "M5 → M1:  Configure M1 IP in System/nerve_channel.py",
                "M1 → M5:  HeartbeatDaemon auto-starts on both nodes",
                "",
                "Signal types:",
            ]
            for sig in NerveSignal:
                lines.append(f"  0x{sig.value:02X}  {sig.name}")
            text = "\n".join(lines)
        except Exception as e:
            text = f"[Nerve channel error] {e}"
        w = QPlainTextEdit()
        w.setReadOnly(True)
        w.setPlainText(text)
        w.setStyleSheet(
            "QPlainTextEdit { background: #0b1020; color: #73daca; "
            "font-family: monospace; font-size: 12px; padding: 12px; }"
        )
        self._make_sub(w, "⚡ Nerve Channel", 620, 420, "#73daca")

    def _show_file_trails(self):
        from PyQt6.QtWidgets import QPlainTextEdit
        try:
            trail_clusters = fs_clusters(0.5)
            from pheromone_fs import trail_map
            tmap = trail_map()
            lines = ["PHEROMONE FILE TRAILS", "=" * 50]
            if not tmap:
                lines.append("No trails yet. Open files from the OS and trails will form.")
            else:
                lines.append(f"Active trails: {len(tmap)}")
                lines.append("")
                top = sorted(tmap.items(), key=lambda x: -x[1])[:15]
                for k, v in top:
                    a, b = k.split("::")
                    lines.append(f"  {v:.2f}  {a}  ↔  {b}")
                if trail_clusters:
                    lines.append("")
                    lines.append("File clusters (co-accessed):")
                    for i, c in enumerate(trail_clusters, 1):
                        lines.append(f"  Cluster {i}: {', '.join(c)}")
            text = "\n".join(lines)
        except Exception as e:
            text = f"[Pheromone FS error] {e}"
        w = QPlainTextEdit()
        w.setReadOnly(True)
        w.setPlainText(text)
        w.setStyleSheet(
            "QPlainTextEdit { background: #0b1020; color: #9ece6a; "
            "font-family: monospace; font-size: 12px; padding: 12px; }"
        )
        self._make_sub(w, "🗺 File Trails", 700, 480, "#9ece6a")

    def _show_fitness_scores(self):
        from PyQt6.QtWidgets import QPlainTextEdit
        from app_fitness import get_scores
        scores = get_scores()
        lines = ["APP FITNESS RANKINGS", "=" * 50]
        if not scores:
            lines.append("No fitness data yet. Launch apps to build history.")
        else:
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            for name, score in ranked:
                bar_len = max(0, int(score * 2))
                bar = "█" * min(bar_len, 40)
                lines.append(f"  {score:+7.2f}  {bar}  {name}")
        text = "\n".join(lines)
        w = QPlainTextEdit()
        w.setReadOnly(True)
        w.setPlainText(text)
        w.setStyleSheet(
            "QPlainTextEdit { background: #0b1020; color: #7dcfff; "
            "font-family: monospace; font-size: 12px; padding: 12px; }"
        )
        self._make_sub(w, "📊 App Fitness", 620, 400, "#7dcfff")

    def _show_app_help(self, app_name: str, app_data: dict) -> None:
        from PyQt6.QtWidgets import QPlainTextEdit

        cat = app_data.get("category", "Accessories")
        entry = app_data.get("entry_point", "")
        widget = app_data.get("widget_class", "")

        category_principles = {
            "Simulations": "Interpret dynamics, convergence, and failure modes first. Metrics > vibes.",
            "Creative": "Stigmergic media tools. Watch emergent decisions, pheromone consensus, and export fidelity.",
            "Networking": "Treat all external IO as hostile by default. Verify provenance and signatures.",
            "System": "Watch boundaries: identity, authority, execution. Small config changes can have global effects.",
            "Accessories": "UI/ops tooling for human bandwidth. These are observability and control surfaces.",
        }
        app_blurbs = {
            "Colloid Simulator": "Active-matter stigmergy. Watch local interactions create global order.",
            "Swarm Arena": "Model-vs-model debugging tournament with reproducible level fixtures.",
            "Cyborg Organ Simulator": "Organ regulation + BCI intent clustering + signed control events.",
            "Logistics Swarm (Overnight)": "Pheromone routing under congestion; evaluate throughput vs stability.",
            "Warehouse Logistics Test": "Validation harness for logistics constraints and regression checks.",
            "Crucible Cyber-Defense (10-min)": "DDoS + anomaly gauntlet; assess quarantine and resilience under burst.",
            "Stigmergic Edge Vision": "Distributed edge extraction from noisy fields using swimmer consensus.",
            "Urban Resilience Simulator": "Vehicle-drone coordination in disrupted infrastructure scenarios.",
            "Epistemic Mesh (Anti-Gaslight)": "Truth pheromone emerges from cryptographic provenance verification.",
            "Stigmergic Fold Swarm (Cα / Go)": "Protein-like folding search with Go contacts, sterics, and obstacle fields.",
            "Intelligence Settings": "Global model/runtime defaults used by system components.",
            "Circadian Rhythm": "Autonomous scheduling for low-noise night cycles and maintenance windows.",
            "Cardio Metrics": "Swarm health telemetry and heartbeat diagnostics.",
            "Biological Dashboard": "Live organism state projection for operator situational awareness.",
            "Sebastian Batch Editor": "Batch media workflow and proof-of-useful-work accounting for edits.",
            "Human Council GUI": "Human governance and decision surface over autonomous proposals.",
            "Desktop GUI (Legacy)": "Older shell kept for comparison and fallback.",
            "Swarm Discord Engine": "Bridge layer for Discord ingress/egress in the swarm communication stack.",
            "Swarm Telegram Engine": "Bridge layer for Telegram ingress/egress in the swarm communication stack.",
            "Swarm WhatsApp Bridge": "Bridge layer for WhatsApp ingress/egress with strict separation from TRANSEC.",
            "First Boot Provisioning": "Node bootstrap/provisioning flow for first-run environment setup.",
        }

        lines = [
            f"{app_name}",
            "=" * max(24, len(app_name)),
            "",
            f"Category:      {cat}",
            f"Entry point:   {entry}",
            f"Widget class:  {widget or 'N/A (terminal app)'}",
            "",
            "What you are looking at:",
            f"  {app_blurbs.get(app_name, 'App-specific operation surface in the SIFTA ecosystem.')}",
            "",
            "Scientific reading frame:",
            f"  {category_principles.get(cat, 'Track state transitions and measurable outputs.')}",
            "",
            "Operator checklist:",
            "  1) Identify primary output metric(s)",
            "  2) Identify control parameter(s)",
            "  3) Observe failure mode / saturation behavior",
            "  4) Verify whether ledger, signatures, or immunity changed",
            "",
            "Long-form manual:",
            "  Open Documents/APP_HELP.md for full per-app sections.",
        ]

        w = QPlainTextEdit()
        w.setReadOnly(True)
        w.setPlainText("\n".join(lines))
        w.setStyleSheet(
            "QPlainTextEdit { background: #0b1020; color: #c0caf5; "
            "font-family: monospace; font-size: 12px; padding: 12px; }"
        )
        self._make_sub(w, f"❓ Help — {app_name}", 760, 520, "#565f89")



# ──────────────────────────────────────────────────────────────
# BOOT
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Inter", 12))
    desktop = SiftaDesktop()
    sys.exit(app.exec())
