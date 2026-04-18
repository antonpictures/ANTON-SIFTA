#!/usr/bin/env python3
"""
sifta_network_center.py — Apple-like networking control center for iSwarm OS
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from PyQt6.QtCore import QProcess, QProcessEnvironment, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "sifta_channels.json"


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
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._proc: QProcess | None = None
        self._build_ui()
        self._load_config()

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
        subtitle = QLabel("Configure and run Telegram, WhatsApp, and Discord bridges from inside iSwarm OS.")
        subtitle.setStyleSheet("color: #a9b1d6;")
        root.addWidget(title)
        root.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.addWidget(_card("Telegram", "Bot token + optional target chat ID for startup ping."), 0, 0)
        grid.addWidget(_card("WhatsApp", "Launch Baileys QR bridge and SIFTA voice channel."), 0, 1)
        grid.addWidget(_card("Discord", "Optional token for users who run a Discord bot."), 0, 2)
        root.addLayout(grid)

        fields = QGridLayout()
        fields.setHorizontalSpacing(8)
        fields.setVerticalSpacing(8)
        fields.addWidget(QLabel("Telegram token"), 0, 0)
        self.telegram_token = QLineEdit()
        self.telegram_token.setEchoMode(QLineEdit.EchoMode.Password)
        fields.addWidget(self.telegram_token, 0, 1)

        fields.addWidget(QLabel("Telegram chat ID"), 1, 0)
        self.telegram_chat_id = QLineEdit()
        self.telegram_chat_id.setPlaceholderText("-100... or @channel_username")
        fields.addWidget(self.telegram_chat_id, 1, 1)

        fields.addWidget(QLabel("Discord token"), 2, 0)
        self.discord_token = QLineEdit()
        self.discord_token.setEchoMode(QLineEdit.EchoMode.Password)
        fields.addWidget(self.discord_token, 2, 1)
        root.addLayout(fields)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Channels")
        save_btn.clicked.connect(self._save_config)
        btn_row.addWidget(save_btn)

        tg_btn = QPushButton("Launch Telegram")
        tg_btn.setObjectName("secondary")
        tg_btn.clicked.connect(lambda: self._run(["python3", "Applications/telegram_swarm.py"]))
        btn_row.addWidget(tg_btn)

        wa_btn = QPushButton("Launch WhatsApp (QR)")
        wa_btn.setObjectName("secondary")
        wa_btn.clicked.connect(lambda: self._run(["/bin/bash", "start_swarm_whatsapp.sh"]))
        btn_row.addWidget(wa_btn)

        dc_btn = QPushButton("Launch Discord")
        dc_btn.setObjectName("secondary")
        dc_btn.clicked.connect(lambda: self._run(["python3", "Applications/discord_swarm.py"]))
        btn_row.addWidget(dc_btn)

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

    def _load_config(self) -> None:
        cfg = {}
        if CONFIG_PATH.exists():
            try:
                cfg = json.loads(CONFIG_PATH.read_text())
            except Exception:
                cfg = {}
        self.telegram_token.setText(str(cfg.get("TELEGRAM_BOT_TOKEN", "")))
        self.telegram_chat_id.setText(str(cfg.get("TELEGRAM_CHAT_ID", "")))
        self.discord_token.setText(str(cfg.get("DISCORD_BOT_TOKEN", "")))

    def _save_config(self) -> None:
        cfg = {}
        if CONFIG_PATH.exists():
            try:
                cfg = json.loads(CONFIG_PATH.read_text())
            except Exception:
                cfg = {}
        cfg["TELEGRAM_BOT_TOKEN"] = self.telegram_token.text().strip()
        cfg["TELEGRAM_CHAT_ID"] = self.telegram_chat_id.text().strip()
        cfg["DISCORD_BOT_TOKEN"] = self.discord_token.text().strip()
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")
        self.status.setText(f"Saved → {CONFIG_PATH.name}")
        self.status.setStyleSheet("color: #7dcfff; font-family: monospace;")
        self.log.appendPlainText("[NetworkCenter] Channel credentials saved.")

    def _run(self, cmd: list[str]) -> None:
        if self._proc and self._proc.state() != QProcess.ProcessState.NotRunning:
            self.log.appendPlainText("[NetworkCenter] Existing process running. Stop it first.")
            return
        self._save_config()
        self._proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        if self.telegram_token.text().strip():
            env.insert("TELEGRAM_BOT_TOKEN", self.telegram_token.text().strip())
        if self.telegram_chat_id.text().strip():
            env.insert("TELEGRAM_CHAT_ID", self.telegram_chat_id.text().strip())
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

