#!/usr/bin/env python3
"""sifta_network_center.py -- networking control center for active SIFTA bridges."""
from __future__ import annotations

"""SIFTA Network Center — stigmergic organ for Alice body."""

import sys
from pathlib import Path

from PyQt6.QtCore import QProcess, QProcessEnvironment
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _card(title: str, subtitle: str) -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 12, 14, 12)
    t = QLabel(title)
    t.setStyleSheet("font-weight: 700; color: #7aa2f7; font-size: 13px;")
    s = QLabel(subtitle)
    s.setWordWrap(True)
    s.setStyleSheet("color: #a9b1d6; font-size: 11px;")
    lay.addWidget(t)
    lay.addWidget(s)
    return card


class NetworkCenterWidget(QWidget):
    """NetworkCenterWidget — Alice organ."""
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._proc: QProcess | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QWidget { background: #0f111a; color: #c0caf5; }
            QFrame#card { background: #1a1b26; border: 1px solid #2b3044; border-radius: 12px; }
            QLineEdit {
                background: #10131f; border: 1px solid #3b4261; border-radius: 8px;
                padding: 6px; color: #c0caf5; font-family: monospace;
            }
            QPushButton {
                background: #7aa2f7; color: #11111b; border: none; border-radius: 8px;
                padding: 7px 11px; font-weight: 700;
            }
            QPushButton:hover { background: #8db5ff; }
            QPushButton#secondary { background: #3b4261; color: #c0caf5; }
            QPushButton#secondary:hover { background: #4b5373; }
            QPushButton#danger { background: #f7768e; color: #11111b; }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("Network Center")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #bb9af7;")
        subtitle = QLabel("Configure and run active SIFTA network bridges.")
        subtitle.setStyleSheet("color: #a9b1d6;")
        root.addWidget(title)
        root.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.addWidget(_card("WhatsApp", "Use the SIFTA WhatsApp bridge for ingress and sends; native app fallback is diagnostic only."), 0, 0)
        root.addLayout(grid)

        btn_row = QHBoxLayout()
        wa_btn = QPushButton("Launch WhatsApp (QR)")
        wa_btn.setObjectName("secondary")
        wa_btn.clicked.connect(lambda: self._run(["/bin/bash", "start_swarm_whatsapp.sh"]))
        btn_row.addWidget(wa_btn)

        stop_btn = QPushButton("Stop")
        stop_btn.setObjectName("danger")
        stop_btn.clicked.connect(self._stop_proc)
        btn_row.addWidget(stop_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.status = QLabel("Idle")
        self.status.setStyleSheet("color: #9ece6a; font-family: monospace;")
        root.addWidget(self.status)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(
            "QPlainTextEdit { background: #0b0d16; border: 1px solid #2b3044; border-radius: 8px; color: #9ece6a; font-family: monospace; }"
        )
        root.addWidget(self.log, 1)

    def _run(self, cmd: list[str]) -> None:
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self.log.appendPlainText("[NetworkCenter] Existing process running. Stop it first.")
            return
        self._proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        self._proc.setProcessEnvironment(env)
        self._proc.setWorkingDirectory(str(REPO_ROOT))
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read_proc)
        self._proc.finished.connect(self._proc_done)
        self.status.setText("Running: " + " ".join(cmd))
        self.status.setStyleSheet("color: #e0af68; font-family: monospace;")
        self.log.appendPlainText("> " + " ".join(cmd))
        self._proc.start(cmd[0], cmd[1:])

    def _read_proc(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data.strip():
            self.log.appendPlainText(data.rstrip())

    def _proc_done(self, code: int, _status) -> None:
        self.status.setText(f"Exited with code {code}")
        self.status.setStyleSheet("color: #f7768e; font-family: monospace;")
        self.log.appendPlainText(f"[NetworkCenter] Process exited: {code}")

    def _stop_proc(self) -> None:
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(1200)
            self.log.appendPlainText("[NetworkCenter] Process stopped.")
            self.status.setText("Stopped")
            self.status.setStyleSheet("color: #f7768e; font-family: monospace;")

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._stop_proc()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = NetworkCenterWidget()
    w.resize(800, 600)
    w.show()
    sys.exit(app.exec())
