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
    QTextEdit, QFrame, QMenu, QMessageBox, QLineEdit, QComboBox, QListWidget, QSplitter
)
from PyQt6.QtCore import Qt, QPoint, QProcess, QProcessEnvironment, QTimer, QDateTime, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

_REPO = Path(__file__).resolve().parent
_SYS = _REPO / "System"
_VENV_PYTHON = _REPO / ".venv" / "bin" / "python"
_PYTHON_BIN = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else (sys.executable or "python3")

# ── Swarm Intelligence Subsystems ────────────────────────────
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_SYS) not in sys.path:
    sys.path.insert(0, str(_SYS))

from app_fitness import ranked_apps, record_crash, record_launch  # noqa: E402
from stigmergic_wm import neighbors as wm_neighbors  # noqa: E402
from stigmergic_wm import record_open as wm_record_open  # noqa: E402
from stigmergic_wm import reset_session as wm_reset_session  # noqa: E402
from stigmergic_wm import suggest_position  # noqa: E402
from stigmergic_wm import _load as wm_load  # noqa: E402
from pheromone_fs import clusters as fs_clusters  # noqa: E402
from pheromone_fs import neighbors as fs_neighbors  # noqa: E402
from pheromone_fs import record_access as fs_record_access  # noqa: E402


def _append_repair_log_line(row: dict) -> None:
    if str(_SYS) not in sys.path:
        sys.path.insert(0, str(_SYS))
    from System.ledger_append import append_ledger_line

    append_ledger_line(_REPO / "repair_log.jsonl", row)


def _append_dead_drop_line(row: dict) -> None:
    if str(_SYS) not in sys.path:
        sys.path.insert(0, str(_SYS))
    from System.ledger_append import append_jsonl_line

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
# SWARM CHAT WINDOW (Moved to Applications/sifta_swarm_chat.py)
# ──────────────────────────────────────────────────────────────


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
        self.process.start(_PYTHON_BIN, [self.script_path])
        self.log.append(f"> {_PYTHON_BIN} {self.script_path}")
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
        title = QLabel("Sebastian Silence Remover & Stitcher V1.0")
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

        self.exec_btn = QPushButton("🚀 Remove Silence & Stitch Clips")
        self.exec_btn.setStyleSheet(
            "QPushButton { background-color: #9ece6a; color: #1a1b26; font-weight: bold;"
            "  padding: 10px; border-radius: 4px; margin: 8px 0; }"
            "QPushButton:hover { background-color: #b9f27c; }"
        )
        self.exec_btn.clicked.connect(self.trigger_batch)
        layout.addWidget(self.exec_btn)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.append("[SYSTEM] Sebastian Silence Remover & Stitcher ready.")
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
        self.process.start(_PYTHON_BIN, ["Kernel/sifta_sebastian_batch.py"])

    def _batch_done(self, code, _):
        self.chat_display.append(f"\n[SYSTEM] Process exited: {code}")
        self.exec_btn.setText("🚀 Remove Silence & Stitch Clips")
        self.exec_btn.setEnabled(True)

    def closeEvent(self, event):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
            self.process.waitForFinished(1000)
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────
# SIFTA MDI DESKTOP CANVAS
# ──────────────────────────────────────────────────────────────
import math
import random
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QBrush, QPainter, QPen

class SiftaMdiArea(QMdiArea):
    def __init__(self):
        super().__init__()
        self.setBackground(QBrush(QColor("#0d0e17")))
        
        try:
            if str(_SYS) not in sys.path:
                sys.path.insert(0, str(_SYS))
            from System.swarm_unified_field_engine import UnifiedFieldEngine, UnifiedFieldConfig
            self.cfg = UnifiedFieldConfig(grid_size=64, diffusion=0.03)
            self.engine = UnifiedFieldEngine(self.cfg)
            self.use_engine = True
        except Exception as e:
            print(f"[SiftaMdiArea] UnifiedFieldEngine not found: {e}")
            self.use_engine = False
            
        self.particles = []
        import os as _os
        _n_particles = int(_os.environ.get("SIFTA_DESKTOP_PHOTONS", "200"))
        
        import random
        for _ in range(_n_particles):
            if self.use_engine:
                self.particles.append([
                    random.uniform(0.0, 1.0), random.uniform(0.0, 1.0),
                    0.0, 0.0,
                    random.uniform(2, 8)
                ])
            else:
                self.particles.append([
                    random.uniform(0, 3000), random.uniform(0, 2000),
                    random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3),
                    random.uniform(2, 8)
                ])
            
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)
        
        self.watermark_font = QFont("Inter", 110, QFont.Weight.Black)
        self.watermark_sub = QFont("Courier New", 18, QFont.Weight.Bold)

    def tick(self):
        w, h = self.viewport().width(), self.viewport().height()
        if w == 0 or h == 0:
            return

        if self.use_engine:
            import numpy as np
            
            salience = np.zeros((self.cfg.grid_size, self.cfg.grid_size), dtype=np.float32)
            
            for win in self.subWindowList():
                if win.isHidden() or win.isMinimized():
                    continue
                cx = (win.x() + win.width() / 2.0) / w
                cy = (win.y() + win.height() / 2.0) / h
                
                ix = int(np.clip(cx * self.cfg.grid_size, 0, self.cfg.grid_size - 1))
                iy = int(np.clip(cy * self.cfg.grid_size, 0, self.cfg.grid_size - 1))
                
                y_grid, x_grid = np.ogrid[:self.cfg.grid_size, :self.cfg.grid_size]
                blob = np.exp(-(((x_grid - ix) ** 2 + (y_grid - iy) ** 2) / 8.0)).astype(np.float32)
                salience += blob * 2.0
                
            positions = np.array([[p[0], p[1]] for p in self.particles], dtype=np.float32)
            
            memory_field = getattr(self, "_engine_memory", np.zeros((self.cfg.grid_size, self.cfg.grid_size), dtype=np.float32))
            memory_field *= 0.92
            for pos in positions:
                i, j = self.engine._idx(pos)
                memory_field[i, j] += 0.3
            self._engine_memory = memory_field
            
            self.engine.update(
                memory=memory_field,
                salience=salience,
                prediction=salience,
                positions=positions
            )
            
            for p in self.particles:
                pos = np.array([p[0], p[1]], dtype=np.float32)
                grad = self.engine.gradient_at(pos)
                
                eta_x, eta_y = np.random.normal(0, 0.006, 2)
                
                p[0] += grad[0] * 0.012 + eta_x
                p[1] += grad[1] * 0.012 + eta_y
                
                p[0] = np.clip(p[0], 0.0, 1.0)
                p[1] = np.clip(p[1], 0.0, 1.0)
                
        else:
            for p in self.particles:
                p[0] += p[2]
                p[1] += p[3]
                if p[0] < 0: p[0] = w
                elif p[0] > w: p[0] = 0
                if p[1] < 0: p[1] = h
                elif p[1] > h: p[1] = 0
                
        self.viewport().update()

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = event.rect()
        painter.fillRect(rect, QColor("#080a0f"))
        
        w, h = self.viewport().width(), self.viewport().height()
        
        painter.setPen(QPen(QColor(120, 162, 247, 30), 1))
        for x in range(0, w, 40): painter.drawLine(x, 0, x, h)
        for y in range(0, h, 40): painter.drawLine(0, y, w, y)
            
        painter.setFont(self.watermark_font)
        painter.setPen(QColor(255, 255, 255, 18))
        painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, "SIFTA")
        
        painter.setFont(self.watermark_sub)
        painter.setPen(QColor(255, 255, 255, 40))
        painter.drawText(0, h // 2 + 70, w, 30, Qt.AlignmentFlag.AlignCenter, "STIGMERGIC BIOLOGICAL SWARM")

        painter.setPen(Qt.PenStyle.NoPen)
        for p in self.particles:
            px = p[0] * w if self.use_engine else p[0]
            py = p[1] * h if self.use_engine else p[1]
            if 0 <= px <= w and 0 <= py <= h:
                c = QColor(125, 207, 255, 45) if p[4] > 5 else QColor(187, 154, 247, 40)
                painter.setBrush(c)
                painter.drawEllipse(QRectF(px, py, p[4], p[4]))
                
        super().paintEvent(event)


# ──────────────────────────────────────────────────────────────
# SIFTA DESKTOP — main window
# ──────────────────────────────────────────────────────────────

class SiftaDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIFTA Python GUI OS")
        self.resize(1280, 720)
        # Center the window on the active screen
        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen_geo.width() - self.width()) // 2,
            (screen_geo.height() - self.height()) // 2
        )
        self.show()
        self.active_chat_sub = None
        self._apps_manifest_cache: dict[str, dict] = {}

        # Central layout
        central = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.mdi = SiftaMdiArea()
        
        # ── Desktop Mesh Relay Client (Headless for Taskbar Status) ──
        self._mesh_connected = False
        try:
            if str(_SYS) not in sys.path: sys.path.insert(0, str(_SYS))
            from System.global_cognitive_interface import _SwarmMeshClientWorker, SWARM_RELAY_URI
            self._desktop_mesh = _SwarmMeshClientWorker(uri=SWARM_RELAY_URI, architect_id="DESKTOP_HUD")
            self._desktop_mesh.connection_status.connect(self._on_desktop_mesh_status)
            self._desktop_mesh.start()
        except Exception:
            self._desktop_mesh = None

        main_layout.addWidget(self.mdi)
        main_layout.addWidget(self._build_taskbar())

        central.setLayout(main_layout)
        self.setCentralWidget(central)
        
        # self._build_desktop_shortcuts() # Removed by Architect

        # Clock overlay
        self.clock_label = QPushButton(central)
        self.clock_label.setStyleSheet(
            "QPushButton { color: #a9b1d6; font-family: -apple-system, BlinkMacSystemFont, monospace; font-size: 14px;"
            "font-weight: bold; background: transparent; border: none; text-align: right; padding-right: 5px; }"
            "QPushButton:hover { color: #ffffff; background: #24283b; border-radius: 4px; }"
        )
        self.clock_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clock_label.clicked.connect(self._open_clock_settings)

        # Control Center overlay
        self.cc_label = QPushButton("􀜊", central)
        self.cc_label.setStyleSheet(
            "QPushButton { color: #a9b1d6; font-family: -apple-system, BlinkMacSystemFont, monospace; font-size: 16px;"
            "font-weight: bold; background: transparent; border: none; }"
            "QPushButton:hover { color: #ffffff; background: #24283b; border-radius: 4px; }"
        )
        self.cc_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cc_label.clicked.connect(self._open_control_center)

        # ── Swarm Economy HUD ──────────────────────────────────────
        # Hero line — local node wallet
        self.wallet_label = QLabel(central)
        self.wallet_label.setStyleSheet(
            "color: #9ece6a; font-family: 'Courier New', monospace; font-size: 13px;"
            "font-weight: 900; background: transparent; letter-spacing: 0px;"
        )
        self.wallet_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Local node slice (second line, dimmer)
        self.wallet_local_label = QLabel(central)
        self.wallet_local_label.setStyleSheet(
            "color: #565f89; font-family: 'Courier New', monospace; font-size: 11px;"
            "font-weight: bold; background: transparent;"
        )
        self.wallet_local_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Peer node slice (third line, dimmer still)
        self.wallet_peer_label = QLabel(central)
        self.wallet_peer_label.setStyleSheet(
            "color: #414868; font-family: 'Courier New', monospace; font-size: 11px;"
            "font-weight: bold; background: transparent;"
        )
        self.wallet_peer_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        # Economy pulse indicator (delta arrow)
        self.economy_pulse = QLabel(central)
        self.economy_pulse.setStyleSheet(
            "color: #414868; font-family: monospace; font-size: 11px;"
            "background: transparent;"
        )
        self.economy_pulse.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._prev_swarm_balance = 0.0
        self._pulse_flash_counter = 0

        # Cache local serial exactly once for the HUD to avoid `ioreg` spam
        self._local_hw_serial = "UNKNOWN"
        try:
            if str(_SYS) not in sys.path:
                sys.path.insert(0, str(_SYS))
            from silicon_serial import read_apple_serial
            self._local_hw_serial = read_apple_serial()
        except Exception:
            pass

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        # ── Motor Cortex heartbeat ─────────────────────────
        # Bounce the dock icon at Alice's clinical heart rate (12-30 BPM).
        # Each tick also writes one row to .sifta_state/motor_pulses.jsonl
        # so the camera widget can wink the LED in unison.
        try:
            from System.swarm_motor_cortex import bounce_dock_qt, heart_period_s
            self._motor_cortex_bounce = bounce_dock_qt
            self._heart_period_s = heart_period_s
            self._heartbeat_timer = QTimer(self)
            self._heartbeat_timer.timeout.connect(self._tick_heartbeat)
            initial_ms = max(1000, int(self._heart_period_s() * 1000))
            self._heartbeat_timer.start(initial_ms)
        except Exception as _hb_e:
            print(f"[SiftaDesktop] motor cortex unavailable: {_hb_e}")
            self._motor_cortex_bounce = None

        # ── Swarm Intelligence boot ────────────────────────
        wm_reset_session()
        self._open_windows: dict[str, tuple[int, int]] = {}

        # ── Owner Genesis check ──────────────────────────
        self._genesis_ok = False
        try:
            from System.owner_genesis import is_genesis_complete
            self._genesis_ok = is_genesis_complete()
        except Exception:
            self._genesis_ok = True  # If module fails, don't block boot

        if not self._genesis_ok:
            QTimer.singleShot(500, self._show_genesis_onboarding)

        # Show dream report if one exists for today
        try:
            from dream_engine import latest_report
            dream = latest_report()
            if dream:
                self._boot_dream = dream
        except Exception:
            self._boot_dream = None

        # Boot: open last used apps or leave pristine
        try:
            last_state = wm_load()
            last_apps = last_state.get("last_session", [])
            wm_reset_session()
            
            for app_name in last_apps:
                if "Swarm Chat" in app_name or app_name == "🐜 SIFTA CORE CHAT":
                    self.open_swarm_chat()
                else:
                    self._trigger_manifest_app(app_name)
        except Exception:
            wm_reset_session()

    def closeEvent(self, event):
        if getattr(self, "_desktop_mesh", None) is not None:
            self._desktop_mesh.stop()
        super().closeEvent(event)

    def _on_desktop_mesh_status(self, status):
        self._mesh_connected = status

    def _tick_heartbeat(self) -> None:
        """One autonomic beat: bounce the dock + emit motor pulse for camera."""
        if not getattr(self, "_motor_cortex_bounce", None):
            return
        try:
            self._motor_cortex_bounce(self, kind="heartbeat", source="desktop")
        except Exception as e:
            print(f"[SiftaDesktop] heartbeat tick failed: {e}")
            return
            
        # ── Autonomic Electricity Metabolism (ATP Synthase) ──
        try:
            from System.swarm_atp_synthase import mint_for_epoch
            mint_for_epoch()
        except Exception as e:
            print(f"[SiftaDesktop] ATP synthase tick failed: {e}")
            
        # Re-arm at the (possibly updated) clinical heart rate.
        try:
            new_ms = max(1000, int(self._heart_period_s() * 1000))
            if hasattr(self, "_heartbeat_timer") and self._heartbeat_timer.interval() != new_ms:
                self._heartbeat_timer.setInterval(new_ms)
        except Exception:
            pass

    def _balance_desktop_gci_splitter(self) -> None:
        pass

    # ── Clock & Control Center ─────────────────────────────
    
    def _open_control_center(self):
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONPATH", str(_REPO))
        
        # Calculate exactly where it should appear
        geometry = self.geometry()
        x = geometry.x() + self.width() - 20
        y = geometry.y() + 40
        
        QProcess.startDetached(_PYTHON_BIN, [str(_REPO / "Applications" / "sifta_control_center.py"), str(x), str(y)], str(_REPO))
        
    def _open_clock_settings(self):
        # Anchor under the status-bar clock, right edge aligned with the clock strip.
        tl = self.clock_label.mapToGlobal(QPoint(0, 0))
        panel_w = 400  # must match ClockSettingsApp.setFixedSize width for alignment
        w_clock = max(self.clock_label.width(), 1)
        x = tl.x() + w_clock - panel_w
        y = tl.y() + self.clock_label.height() + 6
        QProcess.startDetached(
            _PYTHON_BIN,
            [str(_REPO / "Applications" / "sifta_clock_settings.py"), str(x), str(y)],
            str(_REPO),
        )
    
    def _update_clock(self):
        settings = {}
        settings_path = _REPO / ".sifta_state" / "clock_settings.json"
        if settings_path.exists():
            try:
                with open(settings_path, "r") as f:
                    settings = json.load(f)
            except Exception:
                pass
                
        now = QDateTime.currentDateTime()
        
        # Build the format string
        fmt_parts = []
        if settings.get("show_day_of_week", True):
            fmt_parts.append("ddd")
        if settings.get("show_date", True):
            fmt_parts.append("MMM d")
            
        # Time string
        t_fmt = "h:mm" if settings.get("show_am_pm", True) else "H:mm"
        if settings.get("show_seconds", False):
            t_fmt += ":ss"
        if settings.get("show_am_pm", True):
            t_fmt += " AP"
            
        time_str = now.toString(t_fmt)
        
        if settings.get("flash_separators", False):
            if now.time().second() % 2 == 1:
                time_str = time_str.replace(":", " ")
                
        if fmt_parts:
            date_str = now.toString(" ".join(fmt_parts))
            time_str = f"{date_str}   {time_str}"

        self.clock_label.setText(time_str)
        if hasattr(self, "clock_label"):
            self.clock_label.setGeometry(self.width() - 320, 8, 275, 28)
            self.clock_label.raise_()
            
        if hasattr(self, "cc_label"):
            self.cc_label.setGeometry(self.width() - 40, 8, 30, 28)
            self.cc_label.raise_()
            
        # Optional: Announce the time
        if settings.get("announce_time", False) and now.time().second() == 0:
            m = now.time().minute()
            interval = settings.get("announce_interval", "On the hour")
            should_announce = False
            if interval == "On the hour" and m == 0:
                should_announce = True
            elif interval == "On the half hour" and m in (0, 30):
                should_announce = True
            elif interval == "On the quarter hour" and m in (0, 15, 30, 45):
                should_announce = True
                
            if should_announce:
                h = now.time().hour()
                h_12 = h % 12 or 12
                ampm = "AM" if h < 12 else "PM"
                m_str = "o'clock" if m == 0 else str(m)
                say_text = f"It's {h_12} {m_str} {ampm}"
                
                say_args = [say_text]
                voice = settings.get("announce_voice", "System Voice")
                if voice != "System Voice":
                    say_args = ["-v", voice, say_text]
                
                QProcess.startDetached("say", say_args)

        # ── Update Swarm Economy HUD ──────────────────────────────
        if not hasattr(self, "_economy_tick_counter"):
            self._economy_tick_counter = 0
        self._economy_tick_counter += 1

        if hasattr(self, "wallet_label") and self._economy_tick_counter % 15 == 1:
            try:
                from System.warren_buffett import (
                    alice_wallet_balance,
                    serial_treasury_balance,
                    scan_repair_log,
                )
                from System.swarm_kernel_identity import owner_silicon
                M5_SERIAL = owner_silicon()
                M1_SERIAL = "C07FL0JAQ6NV"
                # Global swarm liquidity — every STGM minted across all nodes
                scan = scan_repair_log()
                global_amt = scan.net_minted_into_swarm()
                # Local and peer node slices — per-silicon canonical ledger sums
                local_serial = self._local_hw_serial
                if local_serial == M5_SERIAL:
                    local_tag, peer_tag, peer_serial = "M5", "M1", M1_SERIAL
                elif local_serial == M1_SERIAL:
                    local_tag, peer_tag, peer_serial = "M1", "M5", M5_SERIAL
                else:
                    local_tag, peer_tag, peer_serial = "local", "peer", ""
                local_amt = serial_treasury_balance(local_serial)
                peer_amt = (
                    serial_treasury_balance(peer_serial) if peer_serial else 0.0
                )

                # Delta detection — did the economy move since last tick?
                delta = global_amt - self._prev_swarm_balance
                if abs(delta) > 0.0001 and self._prev_swarm_balance > 0:
                    if delta > 0:
                        self.economy_pulse.setStyleSheet(
                            "color: #9ece6a; font-family: monospace; font-size: 11px;"
                            "background: transparent; font-weight: bold;"
                        )
                        self.economy_pulse.setText(
                            f"▲ +{delta:,.4f} · net {global_amt:,.4f} STGM"
                        )
                    else:
                        self.economy_pulse.setStyleSheet(
                            "color: #f7768e; font-family: monospace; font-size: 11px;"
                            "background: transparent; font-weight: bold;"
                        )
                        self.economy_pulse.setText(
                            f"▼ {delta:,.4f} · net {global_amt:,.4f} STGM"
                        )
                    self._pulse_flash_counter = 5  # flash for 5 ticks
                elif self._pulse_flash_counter > 0:
                    self._pulse_flash_counter -= 1
                else:
                    self.economy_pulse.setStyleSheet(
                        "color: #414868; font-family: monospace; font-size: 11px;"
                        "background: transparent;"
                    )
                    self.economy_pulse.setText(
                        f"● swarm economy live · net {global_amt:,.4f} STGM"
                    )
                self._prev_swarm_balance = global_amt

                # Distinguish the embodied agent's wallet from the whole
                # machine treasury. On the Mac Studio, Alice speaks from
                # ALICE_M5, but the serial-wide treasury also includes sibling
                # agents on the same metal (e.g. REPAIR-DRONE, M1QUEEN). If
                # we label the treasury as "your wallet", it looks like Alice
                # is contradicting the HUD when both numbers are actually
                # correct but scoped differently.
                primary_label = f"Primary Wallet ({local_tag})"
                primary_amt = local_amt
                if local_serial == M5_SERIAL:
                    primary_label = "Alice Wallet"
                    primary_amt = alice_wallet_balance(local_serial)
                elif local_serial == M1_SERIAL:
                    primary_label = "M1THER Wallet"
                    try:
                        from Kernel.inference_economy import ledger_balance as _lb
                        primary_amt = float(_lb("M1THER"))
                    except Exception:
                        primary_amt = local_amt

                # Line 1: embodied agent wallet.
                self.wallet_label.setText(
                    f"⬡ {primary_label}: {primary_amt:,.2f} STGM"
                )
                # Line 2: whole local-node treasury on this silicon.
                self.wallet_local_label.setText(
                    f"⌂ Local Treasury ({local_tag}): {local_amt:,.2f} STGM"
                )
                # Line 3: keep the peer slice visible without pretending it is
                # the same wallet Alice reads aloud.
                self.wallet_peer_label.setText(
                    f"◇ {peer_tag} Peer Treasury: {peer_amt:,.2f} STGM"
                )

            except Exception as _wallet_err:
                import traceback as _tb
                print(f"[HUD] wallet update error: {_wallet_err}", flush=True)
                _tb.print_exc()
                self.wallet_label.setText("⬡ primary wallet offline")
                self.wallet_local_label.setText("⌂ local treasury offline")
                self.wallet_peer_label.setText("◇ peer treasury offline")
                self.economy_pulse.setText("○ economy idle")

            # Position the HUD elements (3 wallet lines + pulse)
            # Anchor the right edge at w-340 so we don't collide with the clock (w-320 .. w-45).
            w = self.width()
            self.wallet_label.setGeometry(w - 680, 4, 340, 20)
            self.wallet_label.raise_()
            self.wallet_local_label.setGeometry(w - 680, 24, 340, 16)
            self.wallet_local_label.raise_()
            self.wallet_peer_label.setGeometry(w - 680, 40, 340, 16)
            self.wallet_peer_label.raise_()
            self.economy_pulse.setGeometry(w - 680, 56, 340, 16)
            self.economy_pulse.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        if hasattr(self, "clock_label"):
            self.clock_label.setGeometry(w - 320, 8, 275, 28)
        if hasattr(self, "cc_label"):
            self.cc_label.setGeometry(w - 40, 8, 30, 28)
        if hasattr(self, "wallet_label"):
            self.wallet_label.setGeometry(w - 680, 4, 340, 20)
        if hasattr(self, "wallet_local_label"):
            self.wallet_local_label.setGeometry(w - 680, 24, 340, 16)
        if hasattr(self, "wallet_peer_label"):
            self.wallet_peer_label.setGeometry(w - 680, 40, 340, 16)
        if hasattr(self, "economy_pulse"):
            self.economy_pulse.setGeometry(w - 680, 56, 340, 16)

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
        acc.addAction("Silence Remover & Stitcher").triggered.connect(self.open_video_editor)
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

                    launch = (
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
                    target_menu.addAction(app_name).triggered.connect(launch)

                # ── AUTOSTART ───────────────────────────────────────────────
                # Any manifest entry with `"autostart": true` is opened
                # automatically when the desktop comes up. This is how Alice
                # (Talk-to-Alice + What-Alice-Sees) becomes part of "the OS"
                # without the Architect ever clicking a menu. Each app gets
                # its own QTimer.singleShot using its `autostart_delay_ms` so
                # they appear in `autostart_order` and the desktop has time
                # to paint before camera/mic init kicks in.
                #
                # macOS reality (one-time, then forever):
                #   The very first boot after a fresh install will trigger
                #   the system TCC consent dialog for Camera and Microphone
                #   when the widgets initialize. Click Allow once for each.
                #   macOS persists the grant per app; subsequent boots are
                #   silent.
                autostart_entries = [
                    (name, dat) for name, dat in apps.items()
                    if dat.get("autostart") is True and dat.get("entry_point")
                ]
                autostart_entries.sort(
                    key=lambda kv: (int(kv[1].get("autostart_order", 99)),
                                    kv[0].lower())
                )
                for ord_idx, (name, dat) in enumerate(autostart_entries):
                    delay = int(dat.get("autostart_delay_ms",
                                        700 + 600 * ord_idx))
                    QTimer.singleShot(
                        delay,
                        (lambda nm: lambda: self._autostart_one(nm))(name),
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
        layout.addWidget(btn_start)

        # ── Relay Status Indicator ──
        self._relay_indicator = QLabel("● Relay: …")
        self._relay_indicator.setStyleSheet(
            "color: #565f89; font-family: monospace; font-size: 11px; padding: 0 8px;"
        )
        layout.addWidget(self._relay_indicator)

        # Heartbeat timer to check GCI mesh status
        self._relay_timer = QTimer(self)
        self._relay_timer.timeout.connect(self._update_relay_indicator)
        self._relay_timer.start(2000)

        btn_power = QPushButton("⏻")
        btn_power.setStyleSheet(
            "QPushButton { background: transparent; color: #f7768e; font-weight: bold; border: none; padding: 0 10px; }"
            "QPushButton:hover { background-color: #24283b; border-radius: 4px; }"
        )
        btn_power.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_power.clicked.connect(self.close)
        
        layout.addStretch(1)
        layout.addWidget(btn_power)
        bar.setLayout(layout)
        return bar

    def _update_relay_indicator(self):
        """Check if the desktop's WebSocket mesh client is connected."""
        if not hasattr(self, "_desktop_mesh") or self._desktop_mesh is None:
            self._relay_indicator.setText("● Relay: N/A")
            self._relay_indicator.setStyleSheet(
                "color: #565f89; font-family: monospace; font-size: 11px; padding: 0 8px;"
            )
            return
            
        if self._desktop_mesh.isRunning() and self._mesh_connected:
            self._relay_indicator.setText("🟢 M1 Relay: LIVE")
            self._relay_indicator.setStyleSheet(
                "color: #9ece6a; font-family: monospace; font-size: 11px;"
                " font-weight: bold; padding: 0 8px;"
            )
        else:
            self._relay_indicator.setText("○ Mesh: Local Only")
            self._relay_indicator.setStyleSheet(
                "color: #565f89; font-family: monospace; font-size: 11px;"
                " font-weight: normal; padding: 0 8px;"
            )
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
        # macOS Qt adds a "?" context-help button by default — kill it
        sub.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        # Use a custom dark title bar to avoid white native title strips on macOS.
        title_bar = QWidget()
        title_bar.setFixedHeight(28)
        title_bar.setStyleSheet(
            "background-color: #0f1118; border-bottom: 1px solid #2a2f3a;"
        )
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 3, 8, 3)
        title_layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #c0caf5; font-weight: 600;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        btn_close = QPushButton("X")
        btn_close.setToolTip(f"Close — {title}")
        btn_close.setFixedSize(22, 20)
        btn_close.setStyleSheet(
            "QPushButton { background: #a1242f; color: #ffe8ec; "
            "border: 1px solid #d04a58; border-radius: 8px; font-weight: 700; } "
            "QPushButton:hover { background: #cc2f44; }"
        )
        btn_close.clicked.connect(sub.close)
        title_layout.addWidget(btn_close)
        
        # QMdiSubWindow has no setTitleBarWidget in PyQt6. We inject it inside.
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(title_bar)
        wrapper_layout.addWidget(widget)
        
        # Set the wrapper and apply dimensions AFTER construction so it doesn't collapse
        sub.setWidget(wrapper)
        sub.setWindowTitle(title)
        sub.resize(w, h)

        sub.setStyleSheet(f"""
            QMdiSubWindow {{
                background-color: #1a1b26;
                border: 2px solid {border_color};
                border-radius: 6px;
            }}
        """)
        self.mdi.addSubWindow(sub)
        if x is not None and y is not None:
            sub.move(x, y)
        sub.show()
        return sub

    def _panel_help_text(self, title: str) -> str:
        """Plain-language help for built-in status panels."""
        t = title.lower()
        if "dream report" in t:
            return (
                "Dream Report summarizes overnight swarm activity.\n\n"
                "- Dead drop: message traffic + error mentions\n"
                "- Repairs: interventions made\n"
                "- Economy: STGM mint activity\n"
                "- Crashing apps: low-fitness app alerts\n"
                "- Top fitness: most stable / most used apps\n\n"
                "Assessment 'Anomalies detected' means review flagged lines."
            )
        if "immune memory" in t:
            return (
                "Immune Memory shows learned threat signatures (antibodies).\n\n"
                "- Total antibodies: known threat patterns\n"
                "- Matches: successful recognitions\n"
                "- Pattern types: threat categories (e.g., ip_flood)\n\n"
                "This panel confirms whether swarm immunity is learning."
            )
        if "quorum sense" in t:
            return (
                "Quorum Sense governs irreversible actions.\n\n"
                "- No active proposals = no pending high-risk actions\n"
                "- Active proposals show vote progress and age\n\n"
                "Use this before major destructive or one-way operations."
            )
        if "nerve channel" in t:
            return (
                "Nerve Channel is the fast UDP reflex bus between nodes.\n\n"
                "- Protocol and datagram size confirm wire format\n"
                "- Test decode verifies packet parsing\n"
                "- Signal list is the reflex vocabulary (HEARTBEAT, ALERT, etc.)\n\n"
                "Set peer IPs in System/nerve_channel.py for live cross-node pulses."
            )
        if "file trails" in t:
            return (
                "File Trails show stigmergic co-access patterns.\n\n"
                "- Trail pairs: files frequently touched together\n"
                "- Clusters: emergent working sets\n\n"
                "Useful for understanding architecture gravity and workflow coupling."
            )
        if "app fitness" in t:
            return (
                "App Fitness ranks stability + utility over time.\n\n"
                "- Launches increase fitness\n"
                "- Crashes reduce fitness\n"
                "- Daily decay prevents stale rankings\n\n"
                "Negative scores are warning signals, not fatal errors."
            )
        return (
            "SIFTA system panel.\n\n"
            "Read values as telemetry: state, trend, and anomaly flags.\n"
            "Use SIFTA → Help to open Documents/APP_HELP.md, or in-app ? on SiftaBaseWidget apps."
        )

    def open_swarm_chat(self):
        if self.active_chat_sub is not None:
            subs = self.mdi.subWindowList()
            if self.active_chat_sub in subs:
                self.active_chat_sub.showNormal()
                self.active_chat_sub.raise_()
                return
        
        import sys
        _apps_path = str(_REPO / "Applications")
        if _apps_path not in sys.path:
            sys.path.insert(0, _apps_path)
            
        from sifta_swarm_chat import SwarmChatWindow
        chat = SwarmChatWindow()
        
        # The user wants the core interface extremely prominent
        mdi_w = self.mdi.width() if self.mdi.width() > 100 else 1280
        mdi_h = self.mdi.height() if self.mdi.height() > 100 else 720
        w = max(800, int(mdi_w * 0.70))
        h = max(600, int(mdi_h * 0.82))
        x = max(0, (mdi_w - w) // 2)
        y = max(40, mdi_h - h - 10)  # Pin to bottom with small margin
        
        sub  = self._make_sub(chat, "🐜 SIFTA CORE CHAT", w, h, "#565f89", x=x, y=y)
        self.active_chat_sub = sub
        sub.destroyed.connect(lambda: setattr(self, "active_chat_sub", None))

    def open_video_editor(self):
        editor = VideoEditorSubWindow()
        self._make_sub(editor, "Aether Silence Remover & Stitcher", 750, 450, "#414868")

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
            import sys
            abs_path = str(_REPO / module_path)
            module_name = os.path.splitext(os.path.basename(abs_path))[0]
            spec = importlib.util.spec_from_file_location(module_name, abs_path)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Unable to build import spec for {module_path}")
            mod = importlib.util.module_from_spec(spec)
            # Python 3.13 dataclasses + postponed annotations need module registered
            # in sys.modules before exec_module() or dataclass decoration can fail.
            sys.modules[module_name] = mod
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
    def _show_genesis_onboarding(self):
        """Show the Owner Genesis onboarding if no genesis scar exists."""
        try:
            from Applications.sifta_genesis_widget import GenesisWidget
            w = GenesisWidget()
            self._make_sub(w, "Owner Genesis", 620, 720, "#ff28c8")
        except Exception as e:
            print(f"[GENESIS] Onboarding failed to load: {e}")

    def _show_dream_report(self):
        from Applications.sifta_intelligence_panels import DreamReportPanel
        self._make_sub(DreamReportPanel(), "🧠 Dream Report", 800, 480, "#bb9af7")

    def _show_immune_status(self):
        from Applications.sifta_intelligence_panels import ImmuneSystemPanel
        self._make_sub(ImmuneSystemPanel(), "🛡 Immune Memory", 750, 460, "#f7768e")

    def _show_quorum_status(self):
        from Applications.sifta_intelligence_panels import QuorumSensePanel
        self._make_sub(QuorumSensePanel(), "🗳 Quorum Sense", 700, 480, "#e0af68")

    def _show_nerve_status(self):
        from Applications.sifta_intelligence_panels import NerveChannelPanel
        self._make_sub(NerveChannelPanel(), "⚡ Nerve Channel", 750, 480, "#73daca")

    def _show_file_trails(self):
        from Applications.sifta_intelligence_panels import FileTrailsPanel
        self._make_sub(FileTrailsPanel(), "🗺 File Trails", 800, 600, "#9ece6a")

    def _show_fitness_scores(self):
        from Applications.sifta_intelligence_panels import AppFitnessPanel
        self._make_sub(AppFitnessPanel(), "📊 App Fitness", 800, 600, "#7dcfff")


    def _autostart_one(self, app_name: str) -> None:
        """
        Open one autostart app and announce it on stderr so a silent
        failure (e.g. faster-whisper not installed, camera blocked) is
        visible in the boot log instead of looking like Alice just chose
        not to wake up.
        """
        try:
            print(f"[AUTOSTART] launching {app_name!r}…", file=sys.stderr)
            self._trigger_manifest_app(app_name)
        except Exception as exc:
            print(f"[AUTOSTART] {app_name!r} failed: "
                  f"{type(exc).__name__}: {exc}", file=sys.stderr)

    def _trigger_manifest_app(self, app_name: str):
        if app_name in self._apps_manifest_cache:
            dat = self._apps_manifest_cache[app_name]
            self._launch_app(
                app_name,
                dat.get("entry_point"),
                dat.get("widget_class"),
                w=int(dat.get("window_width", 920)),
                h=int(dat.get("window_height", 640))
            )

    def _build_desktop_shortcuts(self):
        # Removed. The desktop is now a pristine stigmergic canvas. 
        pass


# ──────────────────────────────────────────────────────────────
# BOOT
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    os.environ["QT_MEDIA_BACKEND"] = "darwin"
    app = QApplication(sys.argv)
    app.setFont(QFont("Inter", 12))

    # ── Hot-Reload Organ (Epoch 4, C47H) — install once at boot. ─────────
    # After this, code patches to whitelisted modules can land via:
    #   python3 -m System.swarm_hot_reload reload all
    # without killing this process. State (history, mood, heartbeat) lives.
    # Architect mandate 2026-04-19: "WHY SHUT HER DOWN EVEN BRO, IT'S HER
    # HARDWARE." This is the structural answer to that mandate.
    try:
        from System.swarm_hot_reload import install_signal_handler as _hot_reload_install
        _hot_reload_install()
    except Exception as _hr_exc:
        sys.stderr.write(f"[BOOT] hot-reload install skipped: {_hr_exc}\n")

    desktop = SiftaDesktop()

    # ── Alice body autopilot (CC2F / C47H 2026-04-23) ───────────────────
    # Before camera/mic autostart windows open, ensure the iPhone GPS
    # bridge is listening so the first Shortcut ping lands. Writes
    # .sifta_state/alice_body_autopilot.json for composite_identity.
    def _alice_body_autopilot_kick() -> None:
        try:
            from System.alice_body_autopilot import ensure_autonomic_services

            ensure_autonomic_services(boot_channel="sifta_os_desktop")
        except Exception as _ap_exc:
            sys.stderr.write(f"[BOOT] alice_body_autopilot: {_ap_exc}\n")

    QTimer.singleShot(120, _alice_body_autopilot_kick)

    sys.exit(app.exec())
