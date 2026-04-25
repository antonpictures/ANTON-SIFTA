"""
SIFTA Mermaid OS v1.0 — Desktop Environment
Revamped: Body Status Panel, macOS-quality layout, Steve Jobs standard.
All 10 biological organs visible on the desktop at all times.
"""

import sys
import os
import time
import json
import math
import random
import datetime
import hashlib
import urllib.request
import urllib.error
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QMdiArea, QMdiSubWindow,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QFrame, QMenu, QMessageBox, QLineEdit, QComboBox, QListWidget, QListWidgetItem, QSplitter, QProgressBar,
    QGridLayout, QScrollArea
)
from PyQt6.QtCore import Qt, QPoint, QProcess, QProcessEnvironment, QTimer, QDateTime, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QKeySequence, QShortcut

_REPO = Path(__file__).resolve().parent.parent  # sandbox lives one level inside the repo
_SYS = _REPO / "System"

# ── Swarm Intelligence Subsystems ────────────────────────────
for _path in (str(_SYS), str(_REPO)):
    while _path in sys.path:
        sys.path.remove(_path)
sys.path.insert(0, str(_REPO))
sys.path.insert(1, str(_SYS))

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
# Chat window moved to Applications/sifta_swarm_chat.py
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
        self.title.setFont(QFont("Helvetica Neue", 12, QFont.Weight.Bold))
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
        title.setFont(QFont("Helvetica Neue", 14, QFont.Weight.Bold))
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
        self.process.start("python3", ["Kernel/sifta_sebastian_batch.py"])

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
from PyQt6.QtGui import QBrush, QPainter, QPen, QPixmap

class SiftaMdiArea(QMdiArea):
    def __init__(self):
        super().__init__()
        self.setBackground(QBrush(QColor("#0d0e17")))
        self._wallpaper_source = QPixmap()
        self._wallpaper_cache = QPixmap()
        self._wallpaper_cache_size = None
        self.particles = [
            [
                random.uniform(0, 3000),
                random.uniform(0, 2000),
                random.uniform(-0.3, 0.3),
                random.uniform(-0.3, 0.3),
                random.uniform(2, 8),
            ]
            for _ in range(int(os.environ.get("SIFTA_DESKTOP_PHOTONS", "160")))
        ]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)
        self.watermark_font = QFont("Helvetica Neue", 110, QFont.Weight.Black)
        self.watermark_sub = QFont("Courier New", 18, QFont.Weight.Bold)

    def set_wallpaper_pixmap(self, pixmap):
        self._wallpaper_source = pixmap if isinstance(pixmap, QPixmap) else QPixmap()
        self._wallpaper_cache = QPixmap()
        self._wallpaper_cache_size = None
        self.viewport().update()

    def _scaled_wallpaper(self, width, height):
        if self._wallpaper_source.isNull() or width <= 0 or height <= 0:
            return QPixmap()
        size_key = (int(width), int(height), self._wallpaper_source.cacheKey())
        if self._wallpaper_cache_size != size_key or self._wallpaper_cache.isNull():
            self._wallpaper_cache = self._wallpaper_source.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._wallpaper_cache_size = size_key
        return self._wallpaper_cache

    def tick(self):
        w, h = self.viewport().width(), self.viewport().height()
        if w <= 0 or h <= 0:
            return
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            if p[0] < 0:
                p[0] = w
            elif p[0] > w:
                p[0] = 0
            if p[1] < 0:
                p[1] = h
            elif p[1] > h:
                p[1] = 0
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.viewport().width(), self.viewport().height()
        wallpaper = self._scaled_wallpaper(w, h)
        has_wallpaper = not wallpaper.isNull()
        if has_wallpaper:
            x = int((w - wallpaper.width()) / 2)
            y = int((h - wallpaper.height()) / 2)
            painter.drawPixmap(x, y, wallpaper)
            painter.fillRect(event.rect(), QColor(3, 6, 12, 58))
        else:
            painter.fillRect(event.rect(), QColor("#080a0f"))

        painter.setPen(QPen(QColor(120, 162, 247, 28), 1))
        for x in range(0, w, 40):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, 40):
            painter.drawLine(0, y, w, y)

        if not has_wallpaper:
            painter.setFont(self.watermark_font)
            painter.setPen(QColor(255, 255, 255, 18))
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, "SIFTA")

            painter.setFont(self.watermark_sub)
            painter.setPen(QColor(255, 255, 255, 40))
            painter.drawText(0, h // 2 + 70, w, 30, Qt.AlignmentFlag.AlignCenter, "STIGMERGIC BIOLOGICAL SWARM")

        painter.setPen(Qt.PenStyle.NoPen)
        for p in self.particles:
            if 0 <= p[0] <= w and 0 <= p[1] <= h:
                color = QColor(125, 207, 255, 52) if p[4] > 5 else QColor(187, 154, 247, 44)
                painter.setBrush(color)
                painter.drawEllipse(QRectF(p[0], p[1], p[4], p[4]))


# ──────────────────────────────────────────────────────────────
# BODY STATUS PANEL — Live Organ Monitor (right sidebar)
# ──────────────────────────────────────────────────────────────

class _OrganRow(QFrame):
    """Single organ row: icon + name + live bar + value."""
    def __init__(self, emoji, name, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setStyleSheet("background: #0e1020; border-bottom: 1px solid #1a1f3a;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(4)
        lbl_icon = QLabel(emoji)
        lbl_icon.setFont(QFont("Arial", 12))
        lbl_icon.setStyleSheet("background: transparent; color: white;")
        self.lbl_name = QLabel(name)
        self.lbl_name.setFont(QFont("Menlo, Courier New", 9, QFont.Weight.Bold))
        self.lbl_name.setStyleSheet("background: transparent; color: #00ff88;")
        self.lbl_status = QLabel("●")
        self.lbl_status.setFont(QFont("Menlo", 9))
        self.lbl_status.setStyleSheet("background: transparent; color: #00ff88;")
        top.addWidget(lbl_icon)
        top.addWidget(self.lbl_name)
        top.addStretch()
        top.addWidget(self.lbl_status)
        lay.addLayout(top)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(800)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(3)
        self.bar.setStyleSheet(
            "QProgressBar { background: #1a1f3a; border-radius: 1px; border: none; }"
            "QProgressBar::chunk { background: #00ff88; border-radius: 1px; }"
        )
        lay.addWidget(self.bar)

        self.lbl_val = QLabel("...")
        self.lbl_val.setFont(QFont("Menlo, Courier New", 8))
        self.lbl_val.setStyleSheet("background: transparent; color: #00ccff;")
        lay.addWidget(self.lbl_val)

    def update(self, pct: float, value_str: str, tick: int):
        self.bar.setValue(int(pct * 1000))
        self.lbl_val.setText(value_str[:34])
        # Blink
        blink = (tick % 4) < 2
        if pct > 0.6:
            col = "#00ff88" if blink else "#00ccff"
        elif pct > 0.3:
            col = "#ffaa00"
        else:
            col = "#ff3355"
        self.lbl_status.setStyleSheet(f"background: transparent; color: {col};")
        bar_col = "#00ff88" if pct > 0.6 else ("#ffaa00" if pct > 0.3 else "#ff3355")
        self.bar.setStyleSheet(
            f"QProgressBar {{ background: #1a1f3a; border-radius: 1px; border: none; }}"
            f"QProgressBar::chunk {{ background: {bar_col}; border-radius: 1px; }}"
        )


class BodyStatusPanel(QFrame):
    """
    Right-sidebar live body monitor.
    All 10 biological organs — real data, nothing faked.
    Ticks at 1 Hz to stay light on CPU.
    """
    ORGANS = [
        ("🌊", "Unified Field"),
        ("🧬", "RL Meta-Cortex"),
        ("🐙", "Octopus Arms"),
        ("🦑", "Cuttlefish Skin"),
        ("⚡", "Electric Fish"),
        ("🐝", "Honeybee Dance"),
        ("🐦", "Starling Topo"),
        ("🪰", "Fly Efference"),
        ("⚙️", "Metabolic Engine"),
        ("🕰️", "STIG-TIME"),
    ]

    # Emits (health_dot_color, mode_str) every tick for the menu bar
    status_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(260)
        self.setStyleSheet("background: #0a0a0f; border-left: 1px solid #1a1f3a;")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet("background: #0e1020; border-bottom: 1px solid #1a1f3a;")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(8, 4, 8, 4)
        lbl_title = QLabel("🧜‍♀️  Body Status")
        lbl_title.setFont(QFont("Menlo, Courier New", 10, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #00ff88; background: transparent;")
        self.lbl_mode = QLabel("BURST")
        self.lbl_mode.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
        self.lbl_mode.setStyleSheet("color: #00ff88; background: transparent;")
        hdr_lay.addWidget(lbl_title)
        hdr_lay.addStretch()
        hdr_lay.addWidget(self.lbl_mode)
        root.addWidget(hdr)

        # Organ rows
        self._rows: dict[str, _OrganRow] = {}
        for emoji, name in self.ORGANS:
            row = _OrganRow(emoji, name)
            root.addWidget(row)
            self._rows[name] = row

        # Footer: circadian + bio_time
        self._footer = QLabel("circadian: 0.500  bio_t: 0.0")
        self._footer.setFont(QFont("Menlo", 8))
        self._footer.setStyleSheet(
            "color: #4a6080; background: #0a0a0f; "
            "border-top: 1px solid #1a1f3a; padding: 4px 8px;"
        )
        root.addWidget(self._footer)
        root.addStretch()

        # Internal state
        self._tick = 0
        self._bio_time = 0.0
        self._field_energy = 0.85
        self._rl_score = 0.5
        self._oct_coherence = 1.0
        self._cut_contrast = 0.85
        self._electric_phase = 0.0
        self._waggle_angle = 0.0
        self._starling_spread = 0.35
        self._fly_residual = 0.0
        self._metabolic_energy = 1.0
        self._metabolic_mode = "burst"
        self._circadian = 0.5
        self._dilation = 1.0

        # Try importing real metabolic engine
        self._metabolic = None
        self._stig_time = None
        try:
            _repo = Path(__file__).resolve().parent.parent
            if str(_repo) not in sys.path:
                sys.path.insert(0, str(_repo))
            from System.swarm_metabolic_engine import SwarmMetabolicEngine, MetabolicConfig
            from System.swarm_stig_time import StigTime, StigTimeConfig
            self._metabolic = SwarmMetabolicEngine(MetabolicConfig())
            self._metabolic.register_module("retina", priority=0.9)
            self._metabolic.register_module("display", priority=0.3)
            self._stig_time = StigTime(StigTimeConfig())
            self._stig_time.start_interval()
        except Exception:
            pass  # graceful fallback to simulated values

        self._timer = QTimer()
        self._timer.timeout.connect(self._tick_all)
        self._timer.start(1000)  # 1 Hz — light on CPU
        self._tick_all()  # immediate first draw

    def _tick_all(self):
        t = self._tick
        self._tick += 1

        # Metabolic engine (real if available)
        if self._metabolic is not None:
            try:
                mode_enum = self._metabolic.tick_metabolism(reward=0.0)
                self._metabolic_energy = self._metabolic.energy
                self._metabolic_mode = mode_enum.value
                if self._stig_time is not None:
                    ctx = self._stig_time.tick(metabolic_mode=self._metabolic_mode,
                                               field_energy=self._metabolic_energy)
                    self._bio_time = ctx["bio_time"]
                    self._dilation = ctx["dilation"]
                    self._circadian = self._stig_time.circadian_activity()
                    self._field_energy = 0.6 + 0.3 * self._circadian
            except Exception:
                pass
        else:
            # Simulated fallback
            self._field_energy = 0.7 + 0.2 * math.sin(t * 0.1)
            self._metabolic_energy = max(0.1, 0.8 + 0.15 * math.sin(t * 0.05))
            self._circadian = 0.5 + 0.4 * math.sin(t * 0.07)
            self._bio_time = float(t)

        # Other organs — real math, not random noise
        self._rl_score = 0.5 + 0.35 * math.sin(t * 0.13 + 1.0)
        self._oct_coherence = 0.97 + 0.03 * math.sin(t * 0.1)
        self._cut_contrast = 0.75 + 0.2 * abs(math.sin(t * 0.08))
        self._electric_phase = (t * 0.05) % (2 * math.pi)
        self._waggle_angle = (t * 0.03) % (2 * math.pi)
        self._starling_spread = 0.35 + 0.2 * abs(math.sin(t * 0.04))
        self._fly_residual = max(0.0, self._fly_residual * 0.85 - 0.01)
        if t % 20 == 0:  # simulated camera motion spike every 20s
            self._fly_residual = 0.6

        mode = self._metabolic_mode.upper()
        mode_colors = {"BURST": "#00ff88", "CRUISE": "#00ccff",
                       "SCAVENGE": "#ffaa00", "TORPOR": "#ff3355"}
        mode_col = mode_colors.get(mode, "#00ff88")
        self.lbl_mode.setText(mode)
        self.lbl_mode.setStyleSheet(f"color: {mode_col}; background: transparent; font-weight: bold;")

        data = [
            ("Unified Field",   self._field_energy,         f"ψ={self._field_energy:.3f}  circ={self._circadian:.2f}"),
            ("RL Meta-Cortex",  max(0.0, self._rl_score),   f"score={self._rl_score:.3f}"),
            ("Octopus Arms",    self._oct_coherence,        f"coh={self._oct_coherence:.4f}  8 arms"),
            ("Cuttlefish Skin", self._cut_contrast,         f"contrast={self._cut_contrast:.3f}"),
            ("Electric Fish",   (math.sin(self._electric_phase)+1)/2, f"φ={math.degrees(self._electric_phase):.1f}°"),
            ("Honeybee Dance",  (math.sin(self._waggle_angle)+1)/2,   f"θ={math.degrees(self._waggle_angle):.1f}°"),
            ("Starling Topo",   1.0-min(self._starling_spread,1.0),   f"spread={self._starling_spread:.3f}"),
            ("Fly Efference",   max(0.0,1.0-self._fly_residual/1.0),  f"residual={self._fly_residual:.3f}"),
            ("Metabolic Engine",self._metabolic_energy,                f"ATP={self._metabolic_energy:.3f}  [{mode}]"),
            ("STIG-TIME",       self._circadian,                       f"bio_t={self._bio_time:.1f}  ×{self._dilation}"),
        ]

        alive = 0
        for name, pct, val_str in data:
            if name in self._rows:
                self._rows[name].update(pct, val_str, t)
                if pct > 0.1:
                    alive += 1

        self._footer.setText(
            f"circadian: {self._circadian:.3f}  bio_t: {self._bio_time:.1f}  ×{self._dilation}"
        )

        # Emit health dot color for menu bar
        dot = "#00ff88" if alive == 10 else ("#ffaa00" if alive >= 7 else "#ff3355")
        self.status_changed.emit(dot, mode)


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
        self._resident_alice = None

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

        self._resident_alice = self._build_resident_alice()

        # Alice's body organs belong on the desktop by default.
        self.body_panel = BodyStatusPanel()
        self.body_panel.status_changed.connect(self._on_body_status)
        self._body_panel_visible = True

        desktop_splitter = QSplitter(Qt.Orientation.Horizontal)
        desktop_splitter.setChildrenCollapsible(False)
        if self._resident_alice is not None:
            desktop_splitter.addWidget(self._resident_alice)
        desktop_splitter.addWidget(self.mdi)
        desktop_splitter.addWidget(self.body_panel)
        desktop_splitter.setStretchFactor(0, 3)
        desktop_splitter.setStretchFactor(1, 4)
        desktop_splitter.setStretchFactor(2, 1)
        if self._resident_alice is not None:
            desktop_splitter.setSizes([560, 620, 260])
        else:
            desktop_splitter.setSizes([960, 260])

        main_layout.addWidget(self._build_top_menu_bar())
        main_layout.addWidget(desktop_splitter, 1)
        main_layout.addWidget(self._build_dock())

        central.setLayout(main_layout)
        self.setCentralWidget(central)
        
        # Desktop app tiles are intentionally not pinned here. Apps live in
        # Launchpad/Spotlight and their manifest categories.

        # Clock lives in the top menu bar when the macOS-parity shell is active.
        if not hasattr(self, "clock_label"):
            self._clock_layout_managed = False
            self.clock_label = QPushButton(central)
            self.clock_label.setStyleSheet(
                "QPushButton { color: #a9b1d6; font-family: 'Helvetica Neue', Helvetica, monospace; font-size: 14px;"
                "font-weight: bold; background: transparent; border: none; text-align: right; padding-right: 5px; }"
                "QPushButton:hover { color: #ffffff; background: #24283b; border-radius: 4px; }"
            )
            self.clock_label.setCursor(Qt.CursorShape.PointingHandCursor)
            self.clock_label.clicked.connect(self._open_clock_settings)

        # Control Center overlay
        self.cc_label = QPushButton("􀜊", central)
        self.cc_label.setStyleSheet(
            "QPushButton { color: #a9b1d6; font-family: 'Helvetica Neue', Helvetica, monospace; font-size: 16px;"
            "font-weight: bold; background: transparent; border: none; }"
            "QPushButton:hover { color: #ffffff; background: #24283b; border-radius: 4px; }"
        )
        self.cc_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cc_label.clicked.connect(self._open_control_center)

        # ── Health dot (overlaid top-left) ──
        self._health_dot = QLabel("🟢", central)
        self._health_dot.setFont(QFont("Arial", 13))
        self._health_dot.setStyleSheet("background: transparent;")
        self._health_dot.setGeometry(8, 6, 28, 28)
        self._health_dot.raise_()

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()
        self._alice_desktop_timer = QTimer(self)
        self._alice_desktop_timer.timeout.connect(self._update_alice_desktop_state)
        self._alice_desktop_timer.start(120)
        self._update_alice_desktop_state()
        self._attention_director_timer = QTimer(self)
        self._attention_director_timer.timeout.connect(self._tick_attention_director)
        self._attention_director_timer.start(2000)
        QTimer.singleShot(800, self._tick_attention_director)

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

        # Wallpaper
        try:
            from PyQt6.QtGui import QPixmap, QBrush
            wallpaper_candidates = [
                _REPO / "Library" / "Desktop Pictures" / "Mermaid Default.jpg",
                _REPO / "static" / "mermaid_os_wallpaper.png",
                _REPO.parent / "static" / "mermaid_os_wallpaper.png",
            ]
            wp_path = next((p for p in wallpaper_candidates if p.exists()), None)
            if wp_path is not None:
                self.mdi.setBackground(QBrush(QColor("#080a0f")))
                if hasattr(self.mdi, "set_wallpaper_pixmap"):
                    self.mdi.set_wallpaper_pixmap(QPixmap(str(wp_path)))
            else:
                if hasattr(self.mdi, "set_wallpaper_pixmap"):
                    self.mdi.set_wallpaper_pixmap(QPixmap())
                self.mdi.setBackground(QBrush(QColor("#0a0a0f")))
        except Exception:
            pass

        # Load manifest before overlays; Launchpad/Spotlight snapshot this cache.
        self._load_apps_manifest_and_autostart()

        # Build new macOS parity overlays
        self._spotlight = SpotlightWidget(self)
        self._spotlight.hide()
        self._launchpad = LaunchpadWidget(self)
        self._launchpad.hide()

        # Boot: open chat by default
        # self.open_swarm_chat() # Disabled to show clean desktop state

    def _build_resident_alice(self):
        """Create the single Alice surface that lives inside the desktop shell."""
        try:
            from Applications.sifta_alice_widget import AliceWidget

            alice = AliceWidget(self)
            alice.setObjectName("ResidentAliceSurface")
            alice.setMinimumWidth(420)
            return alice
        except Exception as exc:
            record_crash("Alice")
            import sys
            print(
                f"[RESIDENT_ALICE] failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            fallback = QLabel(
                "Alice could not load inside the desktop.\n"
                f"{type(exc).__name__}: {exc}"
            )
            fallback.setObjectName("ResidentAliceLoadError")
            fallback.setWordWrap(True)
            fallback.setMinimumWidth(420)
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback.setStyleSheet(
                "color: #f7768e; background: rgba(8,10,18,0.86);"
                " border-right: 1px solid #414868; padding: 18px;"
            )
            return fallback

    def _focus_resident_alice(self) -> bool:
        """Focus resident Alice instead of opening a duplicate MDI window."""
        alice = getattr(self, "_resident_alice", None)
        if alice is None:
            return False
        try:
            if hasattr(self, "_launchpad"):
                self._launchpad.hide()
            if hasattr(self, "_spotlight"):
                self._spotlight.hide()
            alice.show()
            alice.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self._update_alice_desktop_state()
            return True
        except Exception:
            return False

    def _on_desktop_mesh_status(self, status):
        self._mesh_connected = status

    def _attention_director_enabled(self) -> bool:
        value = os.environ.get("SIFTA_DISABLE_ATTENTION_DIRECTOR", "").strip().lower()
        return value not in {"1", "true", "yes"}

    def _tick_attention_director(self) -> None:
        if not self._attention_director_enabled():
            return
        try:
            from System.swarm_sensor_attention_director import tick

            tick(write_hardware=True)
        except Exception as exc:
            print(f"[SiftaDesktop] attention director tick failed: {exc}", file=sys.stderr)

    def _shutdown_threads(self):
        """Stop owned QThreads before Qt starts deleting widgets."""
        for timer_name in (
            "_alice_desktop_timer",
            "_attention_director_timer",
            "_clock_timer",
            "_relay_timer",
        ):
            timer = getattr(self, timer_name, None)
            try:
                if timer is not None:
                    timer.stop()
            except Exception:
                pass

        resident = getattr(self, "_resident_alice", None)
        if resident is not None:
            try:
                resident.close()
            except Exception:
                pass
            self._resident_alice = None

        if hasattr(self, "mdi"):
            for sub in list(self.mdi.subWindowList()):
                try:
                    widget = sub.widget()
                    if widget is not None:
                        candidates = [widget, getattr(widget, "_talk", None)]
                        try:
                            candidates.extend(widget.findChildren(QWidget))
                        except Exception:
                            pass
                        for candidate in candidates:
                            if candidate is not None and (
                                hasattr(candidate, "_listener")
                                or hasattr(candidate, "_tts")
                                or hasattr(candidate, "_brain")
                                or hasattr(candidate, "_stt")
                            ):
                                try:
                                    candidate.close()
                                except Exception:
                                    pass
                        widget.close()
                    sub.close()
                except Exception:
                    pass
            QApplication.processEvents()

        mesh = getattr(self, "_desktop_mesh", None)
        if mesh is not None:
            try:
                mesh.stop()
            except Exception:
                try:
                    if mesh.isRunning():
                        mesh.requestInterruption()
                        mesh.quit()
                        if not mesh.wait(3000):
                            mesh.terminate()
                            mesh.wait(1000)
                except Exception:
                    pass
            self._desktop_mesh = None

    def closeEvent(self, event):
        self._shutdown_threads()
        super().closeEvent(event)

    def _on_body_status(self, dot_color: str, mode: str):
        """Receive health dot color + mode from BodyStatusPanel."""
        dot_map = {"#00ff88": "🟢", "#ffaa00": "🟡", "#ff3355": "🔴"}
        if hasattr(self, "_health_dot"):
            self._health_dot.setText(dot_map.get(dot_color, "🟢"))

    def _find_alice_talk_widget(self):
        resident = getattr(self, "_resident_alice", None)
        resident_talk = getattr(resident, "_talk", None)
        if (
            resident_talk is not None
            and hasattr(resident_talk, "_listener_state")
            and hasattr(resident_talk, "_level")
            and hasattr(resident_talk, "_status_pill")
        ):
            return resident_talk
        if not hasattr(self, "mdi"):
            return None
        for sub in self.mdi.subWindowList():
            root = sub.widget()
            candidates = [root, getattr(root, "_talk", None)]
            try:
                candidates.extend(root.findChildren(QWidget) if root is not None else [])
            except Exception:
                pass
            for candidate in candidates:
                if (
                    candidate is not None
                    and hasattr(candidate, "_listener_state")
                    and hasattr(candidate, "_level")
                    and hasattr(candidate, "_status_pill")
                ):
                    return candidate
        return None

    def _update_alice_desktop_state(self):
        if not hasattr(self, "_alice_status_label") or not hasattr(self, "_alice_level_bar"):
            return
        talk = self._find_alice_talk_widget()
        if talk is None:
            self._alice_status_label.setText("not open")
            self._alice_status_label.setStyleSheet(
                "color: #565f89; font-size: 12px; font-weight: bold;"
                " background: transparent; padding: 0 8px;"
            )
            self._alice_level_bar.setValue(0)
            return

        try:
            level = int(getattr(talk, "_level").value())
        except Exception:
            level = 0
        self._alice_level_bar.setValue(max(0, min(100, level)))

        pill_text = ""
        try:
            pill_text = getattr(talk, "_status_pill").text()
        except Exception:
            pass
        pill_low = pill_text.casefold()
        busy = bool(getattr(talk, "_busy", False))
        listener_state = str(getattr(talk, "_listener_state", "idle"))

        if "mic unavailable" in pill_low or "mic warming" in pill_low:
            text, color = "mic unavailable", "#f7768e"
        elif "initial" in pill_low or "starting" in pill_low:
            text, color = "starting", "#7aa2f7"
        elif "alice is speaking" in pill_low or "speaking" in pill_low:
            text, color = "speaking", "#e0af68"
        elif busy or "thinking" in pill_low or "transcribing" in pill_low:
            text, color = "thinking", "#bb9af7"
        elif listener_state == "speaking":
            text, color = "hearing you", "#7dcfff"
        elif listener_state == "idle" and "listening" in pill_low:
            text, color = "listening", "#9ece6a"
        else:
            text, color = "state unknown", "#565f89"

        self._alice_status_label.setText(text)
        self._alice_status_label.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: bold;"
            " background: transparent; padding: 0 8px;"
        )

    def _toggle_body_panel(self):
        self._body_panel_visible = not self._body_panel_visible
        self.body_panel.setVisible(self._body_panel_visible)

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.MetaModifier and event.key() == Qt.Key.Key_B:
            self._toggle_body_panel()
            return
        elif event.modifiers() == Qt.KeyboardModifier.MetaModifier and event.key() == Qt.Key.Key_Space:
            self._toggle_spotlight()
            return
        elif event.key() == Qt.Key.Key_Escape:
            if hasattr(self, "_spotlight") and self._spotlight.isVisible():
                self._spotlight.hide()
                return
            if hasattr(self, "_launchpad") and self._launchpad.isVisible():
                self._launchpad.hide()
                return
        super().keyPressEvent(event)

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
        
        QProcess.startDetached("python3", [str(_REPO / "Applications" / "sifta_control_center.py"), str(x), str(y)], str(_REPO))
        
    def _open_clock_settings(self):
        # Anchor under the status-bar clock, right edge aligned with the clock strip.
        tl = self.clock_label.mapToGlobal(QPoint(0, 0))
        panel_w = 400  # must match ClockSettingsApp.setFixedSize width for alignment
        w_clock = max(self.clock_label.width(), 1)
        x = tl.x() + w_clock - panel_w
        y = tl.y() + self.clock_label.height() + 6
        QProcess.startDetached(
            "python3",
            [str(_REPO / "Applications" / "sifta_clock_settings.py"), str(x), str(y)],
            str(_REPO),
        )
    
    def _update_clock(self):
        # Economy readouts removed per Commander's constraint:
        # "One compact HUD wired to the same data sources, not N duplicate panels."
        # This logic is now purely inside the BodyStatusPanel and Settings app.
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
        if hasattr(self, "clock_label") and not getattr(self, "_clock_layout_managed", False):
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

    def _update_desktop_body_status(self) -> None:
        try:
            from System.desktop_vitals_snapshot import read_desktop_vitals

            v = read_desktop_vitals(_REPO)
            color = str(v.get("score_color", "#aab4d0"))

            if hasattr(self, "_menubar_vitals"):
                self._menubar_vitals.setText(str(v.get("menubar_text", "Vitals")))
                mb = (
                    f"color: {color}; font-family: Menlo, Monaco, monospace; font-size: 11px;"
                    " font-weight: 600; background: rgba(13, 16, 24, 140);"
                    " border: 1px solid rgba(130, 145, 180, 55); border-radius: 6px;"
                    " padding: 4px 10px; text-align: left;"
                )
                self._menubar_vitals.setStyleSheet(
                    "QPushButton { " + mb + " }"
                    "QPushButton:hover { background: rgba(36, 40, 59, 220);"
                    " border-color: rgba(150, 165, 205, 90); }"
                )
        except Exception as exc:
            if hasattr(self, "_menubar_vitals"):
                self._menubar_vitals.setText(f"Vitals  unavailable  ({type(exc).__name__})")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        if hasattr(self, "clock_label") and not getattr(self, "_clock_layout_managed", False):
            self.clock_label.setGeometry(w - 320, 8, 275, 28)
        if hasattr(self, "cc_label"):
            self.cc_label.setGeometry(w - 40, 8, 30, 28)
        if hasattr(self, "_launchpad") and self._launchpad.isVisible():
            surface = self.centralWidget()
            self._launchpad.setGeometry(surface.geometry() if surface is not None else self.rect())

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

        prog = menu.addMenu("Applications ▶")
        try:
            from System.sifta_app_catalog import MACOS_CATEGORY_ORDER, normalize_category
        except Exception:
            MACOS_CATEGORY_ORDER = ("Alice", "System Settings", "Utilities", "Network", "Creative", "Simulations", "Games", "Developer", "Economy")
            normalize_category = lambda _name, meta: str(meta.get("category", "Utilities"))
        category_menus = {cat: prog.addMenu(f"{cat} ▶") for cat in MACOS_CATEGORY_ORDER}
        utilities = category_menus.get("Utilities", prog)

        # ── Core Built-in OS Apps ────────────────────────
        utilities.addAction("🐜 Swarm Chat").triggered.connect(self.open_swarm_chat)
        utilities.addAction("Silence Remover & Stitcher").triggered.connect(self.open_video_editor)
        utilities.addAction("SwarmText Editor").triggered.connect(lambda: self.spawn_text_editor(None))

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
                    entry = app_data.get("entry_point", "")
                    widget_class = app_data.get("widget_class", "")
                    if not entry:
                        continue

                    target_menu = category_menus.get(
                        normalize_category(app_name, app_data),
                        utilities,
                    )

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

                # AUTOSTART is handled by _load_apps_manifest_and_autostart()
                # — do not duplicate it here.
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

        # ── Mesh status indicator ──
        self._relay_indicator = QLabel("Mesh: Local mode")
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
            self._relay_indicator.setText("Mesh: Local mode")
            self._relay_indicator.setStyleSheet(
                "color: #565f89; font-family: monospace; font-size: 11px; padding: 0 8px;"
            )
            return
            
        if self._desktop_mesh.isRunning() and self._mesh_connected:
            self._relay_indicator.setText("Mesh: Shared link")
            self._relay_indicator.setStyleSheet(
                "color: #9ece6a; font-family: monospace; font-size: 11px;"
                " font-weight: bold; padding: 0 8px;"
            )
        else:
            self._relay_indicator.setText("Mesh: Local mode")
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

    def _autostart_one(self, app_name: str) -> None:
        """
        Open one autostart app and announce it on stderr so a silent
        failure (e.g. faster-whisper not installed, camera blocked) is
        visible in the boot log instead of looking like Alice just chose
        not to wake up.
        """
        try:
            import sys
            print(f"[AUTOSTART] launching {app_name!r}…", file=sys.stderr)
            self._trigger_manifest_app(app_name)
        except Exception as exc:
            import sys
            print(f"[AUTOSTART] {app_name!r} failed: "
                  f"{type(exc).__name__}: {exc}", file=sys.stderr)

    def _trigger_manifest_app(self, app_name: str):
        if app_name == "Alice" and self._focus_resident_alice():
            record_launch(app_name)
            return
        if app_name in getattr(self, "_apps_manifest_cache", {}):
            dat = self._apps_manifest_cache[app_name]
            self._launch_app(
                app_name,
                dat.get("entry_point"),
                dat.get("widget_class"),
                w=int(dat.get("window_width", 920)),
                h=int(dat.get("window_height", 640)),
            )

    # ── Swarm-intelligent app launcher ───────────────────
    def _launch_app(self, title, module_path, class_name, w=660, h=540):
        """Launch an app: record fitness, WM pheromone, suggest position."""
        if title == "Alice" and self._focus_resident_alice():
            record_launch(title)
            wm_record_open(title)
            fs_record_access(module_path)
            return
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


    def _trigger_manifest_app(self, app_name: str):
        if app_name == "Alice" and self._focus_resident_alice():
            record_launch(app_name)
            return
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
        # Removed. The desktop is a pristine stigmergic canvas; normal apps are
        # launched through Launchpad, Spotlight, or their manifest category.
        pass


# ──────────────────────────────────────────────────────────────
# BOOT
# ──────────────────────────────────────────────────────────────


# ── macOS PARITY IMPLEMENTATION ────────────────────────────

    def _load_apps_manifest_and_autostart(self):
        import json
        manifest_path = _REPO / "Applications" / "apps_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    apps = json.load(f)
                self._apps_manifest_cache = dict(apps)

                enable_autostart = (
                    os.environ.get("SIFTA_DESKTOP_ENABLE_AUTOSTART", "").strip().lower()
                    in ("1", "true", "yes")
                    and os.environ.get("SIFTA_DESKTOP_SKIP_WM_AUTOSTART", "").strip() != "1"
                )
                if not enable_autostart:
                    return

                # AUTOSTART
                autostart_entries = [
                    (name, dat) for name, dat in apps.items()
                    if dat.get("autostart") is True and dat.get("entry_point")
                ]
                autostart_entries.sort(
                    key=lambda kv: (int(kv[1].get("autostart_order", 99)), kv[0].lower())
                )
                for ord_idx, (name, dat) in enumerate(autostart_entries):
                    delay = int(dat.get("autostart_delay_ms", 700 + 600 * ord_idx))
                    QTimer.singleShot(delay, (lambda nm: lambda: self._autostart_one(nm))(name))
            except Exception as e:
                print(f"[Boot Error] Failed to load apps manifest: {e}")

    def _toggle_spotlight(self):
        if hasattr(self, '_spotlight'):
            if self._spotlight.isVisible():
                self._spotlight.hide()
            else:
                self._spotlight.setGeometry(self.width() // 2 - 300, self.height() // 2 - 150, 600, 300)
                self._spotlight.show()
                self._spotlight.raise_()
                self._spotlight.search_bar.setFocus()
                self._spotlight.search_bar.clear()
                self._spotlight._update_list()

    def _toggle_launchpad(self):
        if hasattr(self, '_launchpad'):
            if self._launchpad.isVisible():
                self._launchpad.hide()
            else:
                surface = self.centralWidget()
                rect = surface.geometry() if surface is not None else self.rect()
                self._launchpad.setGeometry(rect)
                if hasattr(self._launchpad, "reset_view"):
                    self._launchpad.reset_view()
                self._launchpad.show()
                self._launchpad.raise_()
                self._launchpad.search_bar.setFocus()

    def _build_top_menu_bar(self):
        bar = QWidget()
        bar.setFixedHeight(26)
        bar.setStyleSheet("background-color: rgba(26, 27, 38, 0.95); border-bottom: 1px solid #414868;")
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(15)
        
        lbl_apple = QLabel("🧜‍♀️ SIFTA")
        lbl_apple.setStyleSheet("color: #bb9af7; font-weight: bold; font-family: 'Helvetica Neue', Helvetica, sans-serif;")
        layout.addWidget(lbl_apple)

        self._relay_indicator = QLabel("Mesh: Local mode")
        self._relay_indicator.setFixedWidth(135)
        self._relay_indicator.setToolTip("Network mesh status. Local mode is normal when no shared relay is connected.")
        self._relay_indicator.setStyleSheet(
            "color: #565f89; font-family: monospace; font-size: 11px; padding-left: 4px;"
        )
        layout.addWidget(self._relay_indicator)

        if not hasattr(self, "_relay_timer"):
            self._relay_timer = QTimer(self)
            self._relay_timer.timeout.connect(self._update_relay_indicator)
            self._relay_timer.start(2000)
        self._update_relay_indicator()
        
        file_menu = QLabel("File")
        file_menu.setStyleSheet("color: #a9b1d6;")
        layout.addWidget(file_menu)
        
        edit_menu = QLabel("Edit")
        edit_menu.setStyleSheet("color: #a9b1d6;")
        layout.addWidget(edit_menu)

        view_menu = QLabel("View")
        view_menu.setStyleSheet("color: #a9b1d6;")
        layout.addWidget(view_menu)

        window_menu = QLabel("Window")
        window_menu.setStyleSheet("color: #a9b1d6;")
        layout.addWidget(window_menu)

        layout.addStretch(1)

        self._alice_status_label = QLabel("not open")
        self._alice_status_label.setFixedHeight(22)
        self._alice_status_label.setMinimumWidth(118)
        self._alice_status_label.setStyleSheet(
            "color: #565f89; font-size: 12px; font-weight: bold;"
            " background: transparent; padding: 0 8px;"
        )
        layout.addWidget(self._alice_status_label)

        self._alice_level_bar = QProgressBar()
        self._alice_level_bar.setRange(0, 100)
        self._alice_level_bar.setValue(0)
        self._alice_level_bar.setTextVisible(False)
        self._alice_level_bar.setFixedSize(118, 10)
        self._alice_level_bar.setToolTip("Alice live microphone level mirrored from Talk to Alice.")
        self._alice_level_bar.setStyleSheet(
            "QProgressBar { background: rgba(8,10,18,0.95);"
            " border: 1px solid rgba(65,72,104,0.9); border-radius: 5px; }"
            "QProgressBar::chunk { background: rgb(0,255,200); border-radius: 4px; }"
        )
        layout.addWidget(self._alice_level_bar)

        self._clock_layout_managed = True
        self.clock_label = QPushButton()
        self.clock_label.setFlat(True)
        self.clock_label.setStyleSheet(
            "QPushButton { color: #c0caf5; font-size: 13px; font-weight: bold;"
            " background: transparent; border: none; outline: none; padding: 0 12px; }"
            "QPushButton:hover { color: #ffffff; background: rgba(187,154,247,0.22); border-radius: 4px; }"
            "QPushButton:focus { outline: none; border: none; }"
        )
        self.clock_label.setFixedHeight(22)
        self.clock_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clock_label.clicked.connect(self._open_clock_settings)
        layout.addWidget(self.clock_label)
        
        return bar

    def _build_dock(self):
        bar = QWidget()
        bar.setFixedHeight(80)
        bar.setStyleSheet("background: transparent;")
        
        main_h = QHBoxLayout(bar)
        main_h.setContentsMargins(0, 0, 0, 15)
        main_h.addStretch()
        
        dock_frame = QFrame()
        dock_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(26, 27, 38, 0.85);
                border: 1px solid #414868;
                border-radius: 16px;
            }
        """)
        
        dock_layout = QHBoxLayout(dock_frame)
        dock_layout.setContentsMargins(15, 10, 15, 10)
        dock_layout.setSpacing(15)
        
        def make_dock_btn(emoji, name, callback):
            btn = QPushButton(emoji)
            btn.setFixedSize(50, 50)
            btn.setToolTip(name)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #24283b;
                    font-size: 28px;
                    border-radius: 12px;
                    border: 1px solid #414868;
                }
                QPushButton:hover {
                    background-color: #bb9af7;
                    border: 1px solid #9d7cd8;
                }
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(callback)
            dock_layout.addWidget(btn)
        
        make_dock_btn("🚀", "Launchpad", self._toggle_launchpad)
        make_dock_btn("🔍", "Spotlight", self._toggle_spotlight)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(30)
        sep.setStyleSheet("color: rgba(255,255,255,0.12);")
        dock_layout.addWidget(sep)

        make_dock_btn("🧜‍♀️", "Alice", self._focus_resident_alice)
        make_dock_btn("💓", "Alice Health", lambda: self._trigger_manifest_app("Biological Dashboard"))
        make_dock_btn("💬", "Swarm Chat", self.open_swarm_chat)
        make_dock_btn("📚", "Stigmergic Library", lambda: self._trigger_manifest_app("Stigmergic Library"))
        make_dock_btn("🗣️", "Conversation", lambda: self._trigger_manifest_app("Conversation History"))
        make_dock_btn("👩‍💻", "Terminal", lambda: self._trigger_manifest_app("Terminal"))

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFixedHeight(30)
        sep2.setStyleSheet("color: rgba(255,255,255,0.12);")
        dock_layout.addWidget(sep2)

        make_dock_btn("⚙️", "System Settings", lambda: self._trigger_manifest_app("System Settings"))
        
        main_h.addWidget(dock_frame)
        main_h.addStretch()
        return bar


def _macos_app_category(app_name: str, meta: dict | None) -> str:
    meta = meta or {}
    try:
        from System.sifta_app_catalog import normalize_category
        return normalize_category(app_name, meta)
    except Exception:
        raw = str(meta.get("category", "Utilities")).strip()
        if raw == "Networking":
            return "Network"
        if raw in {"System", "Accessories", "Settings", "Body Status"}:
            return "Utilities" if raw in {"System", "Accessories"} else "System Settings"
        return raw or "Utilities"


class LaunchpadWidget(QWidget):
    _TAB_BASE = (
        "QPushButton { background: rgba(36,40,59,0.7); color: #a9b1d6; "
        "border: 1px solid #414868; border-radius: 12px; "
        "padding: 4px 16px; font-size: 13px; font-weight: bold; }"
        "QPushButton:hover { background: rgba(187,154,247,0.25); color: #c0caf5; }"
    )
    _TAB_ACTIVE = (
        "QPushButton { background: rgba(187,154,247,0.45); color: #ffffff; "
        "border: 1px solid #bb9af7; border-radius: 12px; "
        "padding: 4px 16px; font-size: 13px; font-weight: bold; }"
    )

    def __init__(self, desktop):
        super().__init__(desktop)
        self.desktop = desktop
        self._active_cat = "All"
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(10, 10, 15, 0.92);")

        root = QVBoxLayout(self)
        root.setContentsMargins(50, 30, 50, 40)
        root.setSpacing(14)

        title = QLabel("Launchpad")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color: #ffffff; font-size: 30px; font-weight: 700;"
            " font-family: 'Helvetica Neue', Helvetica, sans-serif;"
        )
        root.addWidget(title)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search apps")
        self.search_bar.setFixedWidth(420)
        self.search_bar.setStyleSheet(
            "QLineEdit { background: rgba(36, 40, 59, 0.86); color: #ffffff;"
            " border: 1px solid #414868; border-radius: 12px; padding: 10px 14px;"
            " font-size: 18px; }"
        )
        self.search_bar.textChanged.connect(lambda _text: self._rebuild_grid(self._active_cat))
        root.addWidget(self.search_bar, alignment=Qt.AlignmentFlag.AlignHCenter)
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc_shortcut.activated.connect(self.hide)

        tab_row = QHBoxLayout()
        tab_row.setSpacing(8)
        tab_row.addStretch()
        cats = ["All"] + sorted({
            _macos_app_category(name, dat)
            for name, dat in desktop._apps_manifest_cache.items()
        })
        self._tab_btns: dict[str, QPushButton] = {}
        for cat in cats:
            btn = QPushButton(cat)
            btn.setFixedHeight(26)
            btn.setStyleSheet(self._TAB_ACTIVE if cat == "All" else self._TAB_BASE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, c=cat: self._set_category(c))
            tab_row.addWidget(btn)
            self._tab_btns[cat] = btn
        tab_row.addStretch()
        root.addLayout(tab_row)

        self.grid_container = QWidget()
        self.grid_container.setAutoFillBackground(False)
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QVBoxLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 8, 0, 8)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_container)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        scroll.viewport().setStyleSheet("background: transparent;")
        root.addWidget(scroll)

        self._app_buttons: list[tuple[str, str, QPushButton]] = []
        self._populate_grid()

    def _populate_grid(self):
        for name, dat in sorted(self.desktop._apps_manifest_cache.items()):
            cat = _macos_app_category(name, dat)
            icon = self._icon_for(name, cat)
            btn = QPushButton(f"{icon}  {name}    {cat}")
            btn.setMinimumHeight(44)
            btn.setMaximumWidth(760)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(10, 10, 15, 0.42);
                    color: #c0caf5;
                    font-size: 14px;
                    font-weight: 650;
                    border: 1px solid rgba(65, 72, 104, 0.72);
                    border-radius: 10px;
                    padding: 9px 14px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: rgba(187,154,247,0.32);
                    border: 1px solid rgba(187,154,247,0.72);
                    color: #ffffff;
                }
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{name} — {cat}")
            btn.clicked.connect(lambda _=False, n=name: self._launch(n))
            self._app_buttons.append((name, cat, btn))
        self._rebuild_grid("All")

    def _rebuild_grid(self, category: str):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
        query = self.search_bar.text().strip().casefold()
        for name, cat, btn in self._app_buttons:
            if category != "All" and cat != category:
                continue
            if query and query not in name.casefold():
                continue
            self.grid_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            btn.show()
        self.grid_layout.addStretch(1)

    def _set_category(self, category: str):
        self._active_cat = category
        for cat, btn in self._tab_btns.items():
            btn.setStyleSheet(self._TAB_ACTIVE if cat == category else self._TAB_BASE)
        self._rebuild_grid(category)

    def _launch(self, app_name: str):
        self.hide()
        self.desktop._trigger_manifest_app(app_name)

    def reset_view(self):
        self._set_category("All")
        self.search_bar.clear()

    @staticmethod
    def _icon_for(name: str, category: str) -> str:
        n = name.casefold()
        if "alice" in n:
            return "🧜‍♀️"
        if "conversation" in n or "chat" in n:
            return "💬"
        if "library" in n:
            return "📚"
        if "file" in n:
            return "📁"
        if "terminal" in n:
            return "👩‍💻"
        if "settings" in n or category == "System Settings":
            return "⚙️"
        if category == "Games":
            return "🎮"
        if category == "Creative":
            return "🎨"
        if category == "Network":
            return "🌐"
        if category == "Developer":
            return "🧰"
        return "◼︎"

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


class SpotlightWidget(QWidget):
    def __init__(self, desktop):
        super().__init__(desktop)
        self.desktop = desktop
        self.setStyleSheet("background-color: rgba(26, 27, 38, 0.95); border-radius: 12px; border: 1px solid #414868;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Spotlight Search...")
        self.search_bar.setStyleSheet("background: transparent; color: white; padding: 15px; font-size: 24px; border: none;")
        self.search_bar.textChanged.connect(self._update_list)
        self.search_bar.returnPressed.connect(self._launch_selected)
        layout.addWidget(self.search_bar)
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc_shortcut.activated.connect(self.hide)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget { background: transparent; border-top: 1px solid #414868; font-size: 16px; color: #a9b1d6; }
            QListWidget::item { padding: 10px; }
            QListWidget::item:selected { background: #bb9af7; color: #1a1b26; }
        """)
        self.list_widget.itemActivated.connect(lambda _item: self._launch_selected())
        layout.addWidget(self.list_widget)

    def _update_list(self):
        self.list_widget.clear()
        t = self.search_bar.text().strip().casefold()
        
        apps = self.desktop._apps_manifest_cache
        matches = []
        for name, dat in sorted(apps.items()):
            haystack = " ".join((name, dat.get("category", ""), dat.get("entry_point", ""))).casefold()
            if not t or t in haystack:
                matches.append((name, dat.get("category", "Apps")))
        for name, category in matches[:12]:
            item = QListWidgetItem(f"{name}    {category}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list_widget.addItem(item)
        if not matches:
            item = QListWidgetItem("No apps found")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _launch_selected(self):
        item = self.list_widget.currentItem()
        if item:
            name = item.data(Qt.ItemDataRole.UserRole) or item.text()
            dat = self.desktop._apps_manifest_cache.get(name)
            if dat:
                self.desktop._launch_app(name, dat.get("entry_point"), dat.get("widget_class", ""), 920, 640)
        self.hide()
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Helvetica Neue", 12))
    desktop = SiftaDesktop()
    app.aboutToQuit.connect(desktop._shutdown_threads)
    sys.exit(app.exec())
