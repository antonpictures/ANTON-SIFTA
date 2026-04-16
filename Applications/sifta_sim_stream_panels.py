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
    """Cyborg Organ Simulator — living split-pane with Swarm conversation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        import json
        import urllib.request
        import urllib.error
        import time
        import datetime

        self._proc: QProcess | None = None

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)

        # ── Split: Sim output (left) + Chat (right) ────────────
        from PyQt6.QtWidgets import QSplitter, QTextEdit, QFrame
        from PyQt6.QtCore import QThread, pyqtSignal

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # LEFT: Simulation output
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

        splitter.addWidget(left)

        # RIGHT: Swarm conversation
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(4, 8, 8, 8)

        chat_title = QLabel("💬 Talk to the Swarm during the test")
        chat_title.setStyleSheet("color: #bb9af7; font-weight: bold; font-size: 12px;")
        right_lay.addWidget(chat_title)

        self._chat_display = QTextEdit()
        self._chat_display.setReadOnly(True)
        self._chat_display.setStyleSheet(
            "QTextEdit { background: #0d0e17; color: #c0caf5; border: 1px solid #1f2335;"
            " border-radius: 8px; font-size: 13px; font-family: -apple-system, Inter, sans-serif; padding: 10px; }"
        )
        right_lay.addWidget(self._chat_display)

        # System greeting
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, lambda: self._chat_display.append(
            '<p style="color: #9ece6a;"><b>SWARM</b> • Cyborg test standing by. '
            'The pacemaker, cochlear implant and NFC gate are loaded. '
            'Talk to me while we run the simulation — what do you want to explore?</p>'
        ))

        input_row = QHBoxLayout()
        self._chat_input = QTextEdit()
        self._chat_input.setPlaceholderText("Talk to M5Queen about the cyborg test…")
        self._chat_input.setFixedHeight(50)
        self._chat_input.setStyleSheet(
            "QTextEdit { background: #1a1b26; color: #c0caf5; border: 1px solid #414868;"
            " border-radius: 10px; padding: 8px 12px; font-size: 13px; }"
            "QTextEdit:focus { border-color: #7aa2f7; }"
        )
        input_row.addWidget(self._chat_input)

        send_btn = QPushButton("🚀")
        send_btn.setFixedSize(42, 42)
        send_btn.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1a73e8,stop:1 #3282f6);"
            " color: white; border-radius: 21px; font-size: 18px; }"
            "QPushButton:hover { background: #5599ff; }"
        )
        send_btn.clicked.connect(self._send_chat)
        input_row.addWidget(send_btn)
        right_lay.addLayout(input_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        main_lay.addWidget(splitter)

        # Store references for chat
        self._ollama_thread = None

        # Auto-start sim
        self._start()

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

    def _send_chat(self) -> None:
        text = self._chat_input.toPlainText().strip()
        if not text:
            return
        self._chat_input.clear()

        import datetime
        ts = datetime.datetime.now().strftime("%H:%M")
        self._chat_display.append(
            f'<p style="color: #7aa2f7;"><b>Architect</b> • {ts}<br>{text}</p>'
        )

        # Fire Ollama inference in a background thread
        import json
        import urllib.request

        class _OllamaChat(QThread):
            response_ready = pyqtSignal(str)
            error_signal = pyqtSignal(str)
            def __init__(self, prompt, parent=None):
                super().__init__(parent)
                self.prompt = prompt
            def run(self):
                try:
                    payload = json.dumps({
                        "model": "qwen3:4b",
                        "prompt": self.prompt,
                        "system": (
                            "You are M5Queen, a sovereign swarm intelligence controlling a cyborg organ simulator. "
                            "You manage a pacemaker, cochlear implant, and NFC gate via cryptographically signed swimmers. "
                            "The Architect is talking to you during a live test. Be conversational, warm, and knowledgeable "
                            "about the cyborg systems. Keep replies SHORT (2-4 sentences)."
                        ),
                        "stream": False
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        "http://127.0.0.1:11434/api/generate",
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        self.response_ready.emit(data.get("response", "[EMPTY]"))
                except Exception as e:
                    self.error_signal.emit(str(e))

        self._ollama_thread = _OllamaChat(text, self)
        self._ollama_thread.response_ready.connect(self._on_chat_response)
        self._ollama_thread.error_signal.connect(self._on_chat_error)
        self._ollama_thread.start()

    def _on_chat_response(self, text: str) -> None:
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M")
        self._chat_display.append(
            f'<p style="color: #9ece6a;"><b>M5Queen</b> • {ts}<br>{text}</p>'
        )
        sb = self._chat_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_chat_error(self, err: str) -> None:
        self._chat_display.append(
            f'<p style="color: #f7768e;"><b>ERROR</b><br>{err}</p>'
        )

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
