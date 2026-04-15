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


class CyborgPanelWidget(_StreamPanel):
    """Cyborg organ demo — CLI stream inside OS."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "Cyborg organ simulator (stdout). Add --visual when running from CLI for charts.",
            [str(_REPO / "Applications" / "sifta_cyborg_sim.py"), "--ticks", "80"],
            parent,
        )


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
