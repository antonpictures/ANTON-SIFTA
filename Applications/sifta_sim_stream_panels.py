#!/usr/bin/env python3
"""
Stream-based simulation panels for iSwarm OS (QProcess + log view).
Used when a sim is CLI/stream-oriented (arena, headless logistics, warehouse).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import QProcess, QProcessEnvironment, Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class _StreamPanel(QWidget):
    def __init__(self, title: str, argv: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._argv = argv
        self._proc: QProcess | None = None

        lay = QVBoxLayout(self)
        hint = QLabel(title)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #565f89; font-size: 11px;")
        lay.addWidget(hint)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            "QPlainTextEdit { background: #0b1020; color: #9ece6a; font-family: monospace; font-size: 11px; }"
        )
        lay.addWidget(self._log)

        row = QHBoxLayout()
        self._btn = QPushButton("Run / Restart")
        self._btn.clicked.connect(self._start)
        row.addWidget(self._btn)
        row.addStretch()
        lay.addLayout(row)

        self._start()

    def _start(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(2000)
        self._log.clear()
        self._proc = QProcess(self)
        self._proc.setProgram(sys.executable)
        self._proc.setArguments(self._argv)
        self._proc.setWorkingDirectory(str(_REPO))
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        self._proc.setProcessEnvironment(env)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.finished.connect(self._done)
        self._proc.start()

    def _read(self) -> None:
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._log.moveCursor(self._log.textCursor().MoveOperation.End)
        self._log.insertPlainText(data)
        self._log.moveCursor(self._log.textCursor().MoveOperation.End)

    def _done(self) -> None:
        pass

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.terminate()
        super().closeEvent(event)


class ArenaPanelWidget(_StreamPanel):
    """Swarm Arena — JSONL tournament stream (needs Ollama for full run)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Arena match: two teams vs one level. Requires Ollama models. Uses defaults if env unset.",
            [
                str(_REPO / "Applications" / "sifta_arena.py"),
                "--red",
                os.environ.get("SIFTA_ARENA_RED", "llama3.2"),
                "--blue",
                os.environ.get("SIFTA_ARENA_BLUE", "llama3.2"),
                "--level",
                os.environ.get("SIFTA_ARENA_LEVEL", "1"),
            ],
            parent,
        )


class LogisticsStreamWidget(_StreamPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Logistics swarm (headless metrics). For full heatmap, run: python3 Applications/sifta_logistics_swarm_sim.py --visual",
            [
                str(_REPO / "Applications" / "sifta_logistics_swarm_sim.py"),
                "--headless",
                "--ticks",
                "12000",
                "--grid",
                "128",
                "--agents",
                "80",
                "--metrics-every",
                "2000",
            ],
            parent,
        )


class WarehouseStreamWidget(_StreamPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Warehouse validation (headless). Add --visual on CLI for live map.",
            [
                str(_REPO / "Applications" / "sifta_warehouse_test.py"),
                "--headless",
                "--ticks",
                "8000",
            ],
            parent,
        )


class CyborgPanelWidget(QWidget):
    """Cyborg Organ Simulator — split-pane with Stigmergic Writer co-authoring."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        import json
        import re
        import urllib.request

        self._proc: QProcess | None = None
        self._ghost_worker = None

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)

        from PyQt6.QtWidgets import QSplitter, QTextEdit, QFrame
        from PyQt6.QtCore import QTimer, QThread, pyqtSignal
        from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QKeyEvent

        self._pane_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT: Simulation output ────────────────────────────────
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(8, 8, 4, 8)

        hint = QLabel("🧬 Cyborg Organ Simulator — Living Stream")
        hint.setStyleSheet("color: #e0af68; font-weight: bold; font-size: 12px;")
        left_lay.addWidget(hint)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            "QPlainTextEdit { background: #0b1020; color: #9ece6a; font-family: monospace; font-size: 12px; }"
        )
        left_lay.addWidget(self._log)

        btn_row = QHBoxLayout()
        self._btn = QPushButton("▶ Run / Restart")
        self._btn.setStyleSheet(
            "QPushButton { background: #9ece6a; color: #15161e; font-weight: bold; border-radius: 4px; padding: 5px 12px; }"
            "QPushButton:hover { background: #b9f27c; }"
        )
        self._btn.clicked.connect(self._start)
        btn_row.addWidget(self._btn)
        btn_row.addStretch()
        left_lay.addLayout(btn_row)

        self._pane_splitter.addWidget(left)

        # ── RIGHT: Stigmergic Writer (ghost-text, no send button) ──
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(4, 8, 8, 8)

        writer_title = QLabel("📝 Write with the Swarm — just type, pause, Tab to accept")
        writer_title.setStyleSheet("color: #bb9af7; font-weight: bold; font-size: 11px;")
        right_lay.addWidget(writer_title)

        # Ghost-text enabled editor (inline class to avoid import issues)
        _parent_ref = self

        class _CyborgEditor(QTextEdit):
            def __init__(self):
                super().__init__()
                self.ghost_text = ""
                self.ghost_start_pos = -1
                self.has_ghost = False
                self.idle_timer = QTimer(self)
                self.idle_timer.setSingleShot(True)
                self.idle_timer.setInterval(3000)
                self.setFont(QFont("Inter", 14))
                self.setStyleSheet(
                    "QTextEdit {"
                    "  background-color: #0a0b14; color: #c8d0f0;"
                    "  border: 1px solid #1f2335; border-radius: 8px;"
                    "  padding: 20px 24px; selection-background-color: #1e3a5f;"
                    "}"
                )
                self.setAcceptRichText(True)

            def keyPressEvent(self, event):
                if event.key() == Qt.Key.Key_Tab and self.has_ghost:
                    self._accept_ghost()
                    return
                if self.has_ghost:
                    self._dismiss_ghost()
                self.idle_timer.stop()
                self.idle_timer.start()
                super().keyPressEvent(event)

            def inject_ghost(self, text):
                self._dismiss_ghost()
                cursor = self.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.ghost_start_pos = cursor.position()
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(100, 110, 140, 120))
                fmt.setFontItalic(True)
                cursor.insertText(text, fmt)
                self.ghost_text = text
                self.has_ghost = True

            def _accept_ghost(self):
                if not self.has_ghost:
                    return
                cursor = self.textCursor()
                cursor.setPosition(self.ghost_start_pos)
                cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(200, 210, 240))
                fmt.setFontItalic(False)
                cursor.insertText(self.ghost_text, fmt)
                self.has_ghost = False
                self.ghost_text = ""
                self.ghost_start_pos = -1

            def _dismiss_ghost(self):
                if not self.has_ghost:
                    return
                cursor = self.textCursor()
                cursor.setPosition(self.ghost_start_pos)
                cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                self.has_ghost = False
                self.ghost_text = ""
                self.ghost_start_pos = -1

        self._editor = _CyborgEditor()
        self._editor.idle_timer.timeout.connect(self._on_idle)
        right_lay.addWidget(self._editor)

        self._pane_splitter.addWidget(right)
        self._pane_splitter.setStretchFactor(0, 1)
        self._pane_splitter.setStretchFactor(1, 1)

        main_lay.addWidget(self._pane_splitter)
        QTimer.singleShot(0, self._balance_pane_splitter)

        # Seed the page with a contextual greeting
        from datetime import datetime
        seed = (
            f"# Cyborg Test Log — {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n\n"
            "The pacemaker, cochlear implant and NFC gate are loaded. "
            "Swimmers are deploying with Ed25519-signed commands.\n\n"
            "---\n\n"
        )
        self._editor.setPlainText(seed)
        cursor = self._editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._editor.setTextCursor(cursor)

        # Auto-start sim
        self._start()

    def _balance_pane_splitter(self) -> None:
        from System.splitter_utils import balance_horizontal_splitter

        balance_horizontal_splitter(
            self._pane_splitter,
            self,
            left_ratio=0.55,
            min_right=280,
            min_left=280,
        )

    def _start(self) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(2000)
        self._log.clear()
        self._proc = QProcess(self)
        self._proc.setProgram(sys.executable)
        self._proc.setArguments([
            str(_REPO / "Applications" / "sifta_cyborg_sim.py"), "--ticks", "200"
        ])
        self._proc.setWorkingDirectory(str(_REPO))
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        self._proc.setProcessEnvironment(env)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read)
        self._proc.start()

    def _read(self) -> None:
        if self._proc is None:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._log.moveCursor(self._log.textCursor().MoveOperation.End)
        self._log.insertPlainText(data)
        self._log.moveCursor(self._log.textCursor().MoveOperation.End)

    def _on_idle(self):
        """Fired 3 seconds after last keystroke — generate ghost text."""
        if self._editor.has_ghost:
            return
        text = self._editor.toPlainText().strip()
        if len(text) < 20:
            return

        if self._ghost_worker and self._ghost_worker.isRunning():
            return

        import json
        import urllib.request
        import re
        from PyQt6.QtCore import QThread, pyqtSignal

        class _GhostWorker(QThread):
            ghost_ready = pyqtSignal(str)
            def __init__(self, context, parent=None):
                super().__init__(parent)
                self.context = context
            def run(self):
                try:
                    prompt = (
                        "You are a co-author inside a cyborg organ test log. "
                        "The human is writing notes during a live pacemaker/cochlear/NFC simulation. "
                        "Continue their text naturally. Write 1-2 sentences MAX. "
                        "Match their tone. DO NOT repeat what they wrote. "
                        "DO NOT use quotes or explain yourself. Just continue.\n\n"
                        f"Text so far:\n{self.context[-1500:]}\n\nContinue:"
                    )
                    data = json.dumps({
                        "model": "gemma4:latest",
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0.5,
                        "num_predict": 80,
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        "http://127.0.0.1:11434/api/generate",
                        data=data,
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        result = json.loads(resp.read().decode("utf-8"))
                        text = result.get("response", "").strip()
                        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
                        if text:
                            self.ghost_ready.emit(text)
                except Exception:
                    pass

        self._ghost_worker = _GhostWorker(text, self)
        self._ghost_worker.ghost_ready.connect(self._on_ghost_ready)
        self._ghost_worker.start()

    def _on_ghost_ready(self, suggestion: str):
        if not suggestion:
            return
        if not self._editor.idle_timer.isActive():
            self._editor.inject_ghost(" " + suggestion)

    def closeEvent(self, event) -> None:
        if self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.terminate()
        super().closeEvent(event)


class CrucibleStreamWidget(_StreamPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Crucible cyber-defense (headless summary). CLI without --headless for full matplotlib lab.",
            [
                str(_REPO / "Applications" / "sifta_crucible_swarm_sim.py"),
                "--headless",
                "--ticks",
                "8000",
            ],
            parent,
        )


class UrbanStreamWidget(_StreamPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Urban resilience (headless; may take a minute). CLI without --headless for live map.",
            [
                str(_REPO / "Applications" / "sifta_urban_resilience_sim.py"),
                "--headless",
                "--ticks",
                "4000",
                "--metrics-every",
                "500",
            ],
            parent,
        )
