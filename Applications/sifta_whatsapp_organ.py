#!/usr/bin/env python3
"""
Applications/sifta_whatsapp_organ.py — Alice's WhatsApp Social Nerve
══════════════════════════════════════════════════════════════════════
AG46 2026-05-06 | Covenant §7.6 | GTH4921YP3

Simplified for Alice's use. This is HER organ dashboard — not a chat
app for George. George talks to Alice via voice; she sends via this nerve.

Architecture (native macOS — no Baileys, no bridge, no JID):
  - Sends via System/swarm_macos_messenger.py (WhatsApp Desktop + osascript)
  - Reads inbox from .sifta_state/whatsapp_inbox.jsonl (ingest when running)
  - Reads send log from .sifta_state/macos_messenger_sends.jsonl
  - Contact resolution via macOS Contacts.app (cached in macos_contacts_cache.json)
  - Publishes focus to swarm_app_focus so Alice's Predator Gaze sees it

Identity principle: Alice IS George on WhatsApp. Same number. Same device.
When she sends, Carlton receives from George's number. No pretending — extension.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QFrame, QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_INBOX = _STATE / "whatsapp_inbox.jsonl"
_SEND_LOG = _STATE / "macos_messenger_sends.jsonl"
_CONTACTS_CACHE = _STATE / "macos_contacts_cache.json"

# ── Color palette (Tokyo Night Dark — matches SIFTA OS) ───────────────
_BG_DEEP   = "#0a0b10"
_BG_PANEL  = "#13141d"
_BG_INPUT  = "#1a1b26"
_BORDER    = "#2a2d3d"
_TEXT      = "#c0caf5"
_TEXT_DIM  = "#565f89"
_ACCENT    = "#7aa2f7"
_GREEN     = "#9ece6a"
_RED       = "#f7768e"
_ORANGE    = "#ff9e64"
_PURPLE    = "#bb9af7"
_TEAL      = "#73daca"


# ── Data helpers ──────────────────────────────────────────────────────

def _read_inbox(max_rows: int = 150) -> list[dict]:
    if not _INBOX.exists():
        return []
    try:
        lines = _INBOX.read_text(encoding="utf-8").strip().split("\n")
        rows = []
        for line in lines[-max_rows:]:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows
    except Exception:
        return []


def _read_sends(max_rows: int = 60) -> list[dict]:
    if not _SEND_LOG.exists():
        return []
    try:
        lines = _SEND_LOG.read_text(encoding="utf-8").strip().split("\n")
        rows = []
        for line in lines[-max_rows:]:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows
    except Exception:
        return []


def _load_contacts_cache() -> dict[str, str]:
    try:
        if _CONTACTS_CACHE.exists():
            return json.loads(_CONTACTS_CACHE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _check_pending() -> dict | None:
    p = _STATE / "wa_pending_reply.json"
    try:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            age = time.time() - float(data.get("ts", 0))
            if age < 300:
                return data
    except Exception:
        pass
    return None


# ── Widget ────────────────────────────────────────────────────────────

class WhatsAppOrganWidget(QWidget):
    """Alice's WhatsApp social nerve — simplified native macOS organ."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._inbox_mtime: float = 0.0
        self._send_mtime: float = 0.0
        self._build_ui()
        self._refresh()

        # Poll every 3s for new messages / send results
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(3000)

        # Publish focus
        self._publish_focus("WhatsApp organ open")

    def _publish_focus(self, detail: str) -> None:
        try:
            from System.swarm_app_focus import publish_focus
            publish_focus("WhatsApp Organ", detail)
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background: {_BG_DEEP};
                color: {_TEXT};
                font-family: 'Inter', 'SF Pro Display', 'Helvetica Neue', sans-serif;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {_BG_PANEL}, stop:1 rgba(122,162,247,0.08));
            border-bottom: 1px solid {_BORDER};
        """)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)

        title = QLabel("📱  WhatsApp Nerve")
        title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_ACCENT}; background: transparent;")
        h_lay.addWidget(title)

        h_lay.addStretch()

        self._status_label = QLabel("● native macOS")
        self._status_label.setFont(QFont("Inter", 11))
        self._status_label.setStyleSheet(f"color: {_GREEN}; background: transparent;")
        h_lay.addWidget(self._status_label)

        root.addWidget(header)

        # ── Pending draft banner (hidden when no draft) ───────────────
        self._pending_banner = QLabel("")
        self._pending_banner.setWordWrap(True)
        self._pending_banner.setStyleSheet(f"""
            background: rgba(255,158,100,0.12);
            border: 1px solid {_ORANGE};
            border-radius: 6px;
            color: {_ORANGE};
            font-size: 12px;
            padding: 8px 14px;
            margin: 8px 12px 0 12px;
        """)
        self._pending_banner.hide()
        root.addWidget(self._pending_banner)

        # ── Conversation timeline ─────────────────────────────────────
        self._chat_display = QTextEdit()
        self._chat_display.setReadOnly(True)
        self._chat_display.setFont(QFont("Inter", 12))
        self._chat_display.setStyleSheet(f"""
            QTextEdit {{
                background: {_BG_DEEP};
                color: {_TEXT};
                border: none;
                padding: 12px;
                selection-background-color: rgba(122,162,247,0.3);
            }}
        """)
        root.addWidget(self._chat_display, 1)

        # ── Compose bar ───────────────────────────────────────────────
        compose = QWidget()
        compose.setFixedHeight(56)
        compose.setStyleSheet(f"""
            background: {_BG_PANEL};
            border-top: 1px solid {_BORDER};
        """)
        c_lay = QHBoxLayout(compose)
        c_lay.setContentsMargins(12, 8, 12, 8)
        c_lay.setSpacing(8)

        self._to_input = QLineEdit()
        self._to_input.setPlaceholderText("To (name)...")
        self._to_input.setFixedWidth(120)
        self._to_input.setStyleSheet(f"""
            QLineEdit {{
                background: {_BG_INPUT};
                color: {_TEXT};
                border: 1px solid {_BORDER};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{ border: 1px solid {_ORANGE}; }}
        """)
        c_lay.addWidget(self._to_input)

        self._msg_input = QLineEdit()
        self._msg_input.setPlaceholderText("Alice types here → sends via WhatsApp Desktop...")
        self._msg_input.setStyleSheet(f"""
            QLineEdit {{
                background: {_BG_INPUT};
                color: {_TEXT};
                border: 1px solid {_BORDER};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border: 1px solid {_ACCENT}; }}
        """)
        self._msg_input.returnPressed.connect(self._send)
        c_lay.addWidget(self._msg_input, 1)

        send_btn = QPushButton("Send ➤")
        send_btn.setFixedWidth(80)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {_ACCENT};
                color: #1a1b26;
                border: none;
                border-radius: 8px;
                padding: 6px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #89b4fa; }}
            QPushButton:pressed {{ background: #5d8acc; }}
        """)
        send_btn.clicked.connect(self._send)
        c_lay.addWidget(send_btn)

        root.addWidget(compose)

        # ── Status bar ────────────────────────────────────────────────
        status_bar = QWidget()
        status_bar.setFixedHeight(26)
        status_bar.setStyleSheet(f"""
            background: {_BG_PANEL};
            border-top: 1px solid {_BORDER};
        """)
        s_lay = QHBoxLayout(status_bar)
        s_lay.setContentsMargins(12, 0, 12, 0)

        self._count_label = QLabel("No messages")
        self._count_label.setFont(QFont("Inter", 10))
        self._count_label.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent;")
        s_lay.addWidget(self._count_label)

        s_lay.addStretch()

        self._contacts_label = QLabel("")
        self._contacts_label.setFont(QFont("Inter", 10))
        self._contacts_label.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent;")
        s_lay.addWidget(self._contacts_label)

        root.addWidget(status_bar)

    # ── Data refresh ─────────────────────────────────────────────────

    def _poll(self) -> None:
        changed = False
        try:
            if _INBOX.exists():
                mt = _INBOX.stat().st_mtime
                if mt != self._inbox_mtime:
                    self._inbox_mtime = mt
                    changed = True
        except Exception:
            pass
        try:
            if _SEND_LOG.exists():
                mt = _SEND_LOG.stat().st_mtime
                if mt != self._send_mtime:
                    self._send_mtime = mt
                    changed = True
        except Exception:
            pass
        if changed:
            self._refresh()
        else:
            # Check pending draft even if no new messages
            self._update_pending_banner()

    def _refresh(self) -> None:
        self._render()
        self._update_contacts_label()
        self._update_pending_banner()

    def _update_pending_banner(self) -> None:
        pending = _check_pending()
        if pending:
            target = pending.get("target", "?")
            msg = pending.get("message", "")
            age_s = int(time.time() - float(pending.get("ts", 0)))
            self._pending_banner.setText(
                f"📝 Draft for {target}: \"{msg[:80]}\" "
                f"({age_s}s ago) — say Execute to send or change it"
            )
            self._pending_banner.show()
        else:
            self._pending_banner.hide()

    def _update_contacts_label(self) -> None:
        cache = _load_contacts_cache()
        n = len(cache)
        self._contacts_label.setText(f"Contacts: {n} registered")

    def _render(self) -> None:
        inbox = _read_inbox()
        sends = _read_sends()

        # Merge into timeline
        events: list[tuple] = []
        for row in inbox:
            ts = float(row.get("ts", 0))
            name = row.get("name", "Unknown")
            text = row.get("text", "")
            from_me = row.get("from_me", False)
            sender = "George" if from_me else name
            color = _TEAL if from_me else _TEXT
            events.append((ts, "in", sender, text, color))

        for row in sends:
            ts = float(row.get("ts", 0))
            target = row.get("target", "?")
            msg_len = row.get("message_len", 0)
            ok = row.get("ok", False)
            status = row.get("status", "?")
            channel = row.get("channel", "whatsapp")
            # Reconstruct preview — actual text not stored in log for privacy
            text = f"[{channel}] → {target} | {status}"
            color = _GREEN if ok else _RED
            events.append((ts, "out", "Alice", text, color))

        events.sort(key=lambda e: e[0])

        html = [f'<div style="text-align:center;color:{_ACCENT};font-size:12px;'
                f'padding:8px;font-weight:bold;">── WhatsApp Timeline ──</div>']

        if not events:
            html.append(f'<div style="text-align:center;color:{_TEXT_DIM};'
                        f'font-size:14px;padding:40px;">No messages yet. '
                        f'George speaks → Alice sends.</div>')
        else:
            last_date = ""
            for ts, direction, sender, text, color in events:
                dt = datetime.fromtimestamp(ts)
                date_str = dt.strftime("%b %d")
                time_str = dt.strftime("%H:%M")
                if date_str != last_date:
                    last_date = date_str
                    html.append(f'<div style="text-align:center;color:{_TEXT_DIM};'
                                f'font-size:10px;padding:8px 0;">── {date_str} ──</div>')
                arrow = "◀" if direction == "in" else "▶"
                txt = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html.append(
                    f'<div style="margin:3px 0;padding:5px 8px;'
                    f'border-radius:6px;background:rgba(26,27,38,0.5);">'
                    f'<span style="color:{color};font-weight:bold;font-size:11px;">'
                    f'{arrow} {sender}</span>'
                    f'<span style="color:{_TEXT_DIM};font-size:10px;margin-left:6px;">{time_str}</span>'
                    f'<br/><span style="color:{_TEXT};font-size:12px;">{txt}</span>'
                    f'</div>'
                )

        self._chat_display.setHtml("".join(html))
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._chat_display.setTextCursor(cursor)

        in_count = len([e for e in events if e[1] == "in"])
        out_count = len([e for e in events if e[1] == "out"])
        self._count_label.setText(f"Inbox: {in_count} · Sent: {out_count}")

    # ── Send ─────────────────────────────────────────────────────────

    def _send(self) -> None:
        target = self._to_input.text().strip()
        msg = self._msg_input.text().strip()
        if not target or not msg:
            self._status_label.setText("● need: To + message")
            self._status_label.setStyleSheet(f"color: {_ORANGE}; background: transparent;")
            return

        try:
            from System.swarm_macos_messenger import send_message
            result = send_message(target, msg, via="whatsapp")
            ok = result.get("ok", False)
            status = result.get("status", "?")
            if ok:
                self._status_label.setText(f"● sent to {target} ✓")
                self._status_label.setStyleSheet(f"color: {_GREEN}; background: transparent;")
                self._msg_input.clear()
            else:
                note = result.get("note", "")
                self._status_label.setText(f"● {status}: {note[:40]}")
                self._status_label.setStyleSheet(f"color: {_RED}; background: transparent;")
            self._publish_focus(f"WhatsApp sent to {target}: {status}")
        except Exception as e:
            self._status_label.setText(f"● error: {str(e)[:40]}")
            self._status_label.setStyleSheet(f"color: {_RED}; background: transparent;")

        self._refresh()
