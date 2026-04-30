#!/usr/bin/env python3
"""
Applications/sifta_whatsapp_organ.py — Alice's WhatsApp Social Organ
═══════════════════════════════════════════════════════════════════════
A native SIFTA OS app that gives Alice a real WhatsApp body part.
George talks to friends. Alice observes the social stream as part of
her unified sensory field. She can see who said what, distinguish
owner messages from external humans, and participate when asked.

Architecture (§6 + §7.5 + §7.6 compliant):
  - Reads inbox from .sifta_state/whatsapp_inbox.jsonl
  - Sends via System/whatsapp_bridge_autopilot.py (the real effector)
  - Health-checks bridge.js on 127.0.0.1:3001
  - Health-checks ingest server on 127.0.0.1:7434
  - Publishes focus to swarm_app_focus so Alice's Predator Gaze sees it
  - Labels truth: George sent / External human sent / Alice sent / Failed
  - NOT a second chat — it's a social nerve with a send capability
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QFrame, QComboBox, QSplitter, QListWidget,
    QListWidgetItem, QMessageBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QColor

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_INBOX = _STATE / "whatsapp_inbox.jsonl"
_CONTACTS = _STATE / "whatsapp_contacts.json"
_BRIDGE_TRACE = _STATE / "whatsapp_bridge_trace.jsonl"

# Bridge endpoints
_BRIDGE_HEALTH = "http://127.0.0.1:3001/health"
_INGEST_HEALTH = "http://127.0.0.1:7434/health"

# ── Color palette (Tokyo Night Dark) ──────────────────────────────────
_BG_DEEP    = "#0a0b10"
_BG_PANEL   = "#13141d"
_BG_INPUT   = "#1a1b26"
_BORDER     = "#2a2d3d"
_TEXT        = "#c0caf5"
_TEXT_DIM    = "#565f89"
_ACCENT      = "#7aa2f7"
_GREEN       = "#9ece6a"
_RED         = "#f7768e"
_ORANGE      = "#ff9e64"
_PURPLE      = "#bb9af7"
_CYAN        = "#7dcfff"
_TEAL        = "#73daca"


def _load_contacts() -> dict[str, Any]:
    if not _CONTACTS.exists():
        return {}
    try:
        return json.loads(_CONTACTS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _contact_names() -> list[str]:
    """Return sorted list of known WhatsApp contact display names."""
    contacts = _load_contacts()
    names = []
    for _k, v in contacts.items():
        name = v.get("display_name", "").strip()
        if name and not v.get("is_group"):
            names.append(name)
    # Also add groups separately
    for _k, v in contacts.items():
        name = v.get("display_name", "").strip()
        if name and v.get("is_group"):
            names.append(f"📢 {name}")
    return sorted(set(names))


def _read_inbox(max_rows: int = 100) -> list[dict]:
    """Read the most recent inbox rows."""
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


def _read_outbox(max_rows: int = 50) -> list[dict]:
    """Read the most recent outbound trace rows."""
    if not _BRIDGE_TRACE.exists():
        return []
    try:
        lines = _BRIDGE_TRACE.read_text(encoding="utf-8").strip().split("\n")
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


def _check_health(url: str) -> tuple[bool, str]:
    """Quick health check against a local endpoint."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("ok", False), json.dumps(data)
    except Exception as e:
        return False, str(e)


class WhatsAppOrganWidget(QWidget):
    """Alice's WhatsApp social nerve — native SIFTA OS organ."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._last_inbox_count = 0
        self._last_outbox_count = 0
        self._inbox_mtime: float = 0.0
        self._outbox_mtime: float = 0.0
        self._build_ui()
        self._refresh_all()

        # Poll inbox every 2 seconds (stat check, not full read)
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_inbox)
        self._poll_timer.start(2000)

        # Health check every 10 seconds
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_bridge_health)
        self._health_timer.start(10000)
        self._check_bridge_health()

        # Publish focus
        self._publish_focus("WhatsApp Organ opened")

    def _publish_focus(self, detail: str) -> None:
        try:
            from System.swarm_app_focus import publish_focus
            publish_focus("WhatsApp Organ", detail)
        except Exception:
            pass

    def _build_ui(self):
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

        # ── Header bar ────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {_BG_PANEL}, stop:1 rgba(122,162,247,0.08));
            border-bottom: 1px solid {_BORDER};
        """)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(16, 0, 16, 0)

        title = QLabel("📱  WhatsApp Organ")
        title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {_ACCENT}; background: transparent;")
        h_lay.addWidget(title)

        h_lay.addStretch()

        self._bridge_status = QLabel("● Bridge: checking...")
        self._bridge_status.setFont(QFont("Inter", 11))
        self._bridge_status.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent;")
        h_lay.addWidget(self._bridge_status)

        self._ingest_status = QLabel("● Ingest: checking...")
        self._ingest_status.setFont(QFont("Inter", 11))
        self._ingest_status.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent; margin-left: 12px;")
        h_lay.addWidget(self._ingest_status)

        root.addWidget(header)

        # ── Main body: contact list (left) + conversation (right) ─────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{ background: {_BORDER}; }}
        """)

        # Left: Contact list
        left_panel = QWidget()
        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(280)
        left_panel.setStyleSheet(f"background: {_BG_PANEL};")
        left_lay = QVBoxLayout(left_panel)
        left_lay.setContentsMargins(8, 8, 8, 8)
        left_lay.setSpacing(6)

        contacts_label = QLabel("Contacts")
        contacts_label.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        contacts_label.setStyleSheet(f"color: {_PURPLE}; padding: 4px;")
        left_lay.addWidget(contacts_label)

        self._contact_search = QLineEdit()
        self._contact_search.setPlaceholderText("🔍 Search contacts...")
        self._contact_search.setStyleSheet(f"""
            QLineEdit {{
                background: {_BG_INPUT};
                color: {_TEXT};
                border: 1px solid {_BORDER};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {_ACCENT};
            }}
        """)
        self._contact_search.textChanged.connect(self._filter_contacts)
        left_lay.addWidget(self._contact_search)

        self._contact_list = QListWidget()
        self._contact_list.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: none;
                font-size: 13px;
            }}
            QListWidget::item {{
                padding: 8px 6px;
                border-bottom: 1px solid rgba(42, 45, 61, 0.5);
                border-radius: 6px;
                margin: 1px 0;
            }}
            QListWidget::item:selected {{
                background: rgba(122, 162, 247, 0.18);
                color: {_ACCENT};
            }}
            QListWidget::item:hover {{
                background: rgba(122, 162, 247, 0.08);
            }}
        """)
        self._contact_list.itemClicked.connect(self._on_contact_selected)
        left_lay.addWidget(self._contact_list, 1)

        # Refresh contacts button
        refresh_btn = QPushButton("⟳ Refresh Contacts")
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(122, 162, 247, 0.12);
                color: {_ACCENT};
                border: 1px solid {_BORDER};
                border-radius: 8px;
                padding: 6px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(122, 162, 247, 0.25);
            }}
        """)
        refresh_btn.clicked.connect(self._refresh_contacts)
        left_lay.addWidget(refresh_btn)

        splitter.addWidget(left_panel)

        # Right: Conversation view + compose
        right_panel = QWidget()
        right_panel.setStyleSheet(f"background: {_BG_DEEP};")
        right_lay = QVBoxLayout(right_panel)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        # Conversation display
        self._chat_display = QTextEdit()
        self._chat_display.setReadOnly(True)
        self._chat_display.setFont(QFont("Inter", 12))
        self._chat_display.setStyleSheet(f"""
            QTextEdit {{
                background: {_BG_DEEP};
                color: {_TEXT};
                border: none;
                padding: 12px;
                selection-background-color: rgba(122, 162, 247, 0.3);
            }}
        """)
        right_lay.addWidget(self._chat_display, 1)

        # Compose bar
        compose_frame = QWidget()
        compose_frame.setFixedHeight(56)
        compose_frame.setStyleSheet(f"""
            background: {_BG_PANEL};
            border-top: 1px solid {_BORDER};
        """)
        compose_lay = QHBoxLayout(compose_frame)
        compose_lay.setContentsMargins(12, 8, 12, 8)
        compose_lay.setSpacing(8)

        self._target_combo = QComboBox()
        self._target_combo.setFixedWidth(180)
        self._target_combo.setEditable(True)
        self._target_combo.setPlaceholderText("To: contact name")
        self._target_combo.setStyleSheet(f"""
            QComboBox {{
                background: {_BG_INPUT};
                color: {_TEXT};
                border: 1px solid {_BORDER};
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QComboBox:focus {{
                border: 1px solid {_ACCENT};
            }}
            QComboBox QAbstractItemView {{
                background: {_BG_PANEL};
                color: {_TEXT};
                border: 1px solid {_BORDER};
                selection-background-color: rgba(122, 162, 247, 0.3);
            }}
        """)
        compose_lay.addWidget(self._target_combo)

        self._msg_input = QLineEdit()
        self._msg_input.setPlaceholderText("Type a message...")
        self._msg_input.setStyleSheet(f"""
            QLineEdit {{
                background: {_BG_INPUT};
                color: {_TEXT};
                border: 1px solid {_BORDER};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {_ACCENT};
            }}
        """)
        self._msg_input.returnPressed.connect(self._send_message)
        compose_lay.addWidget(self._msg_input, 1)

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
            QPushButton:hover {{
                background: #89b4fa;
            }}
            QPushButton:pressed {{
                background: #5d8acc;
            }}
        """)
        send_btn.clicked.connect(self._send_message)
        compose_lay.addWidget(send_btn)

        right_lay.addWidget(compose_frame)

        splitter.addWidget(right_panel)
        splitter.setSizes([220, 700])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)

        # ── Status bar ────────────────────────────────────────────────
        status_bar = QWidget()
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet(f"""
            background: {_BG_PANEL};
            border-top: 1px solid {_BORDER};
        """)
        s_lay = QHBoxLayout(status_bar)
        s_lay.setContentsMargins(12, 0, 12, 0)

        self._inbox_count_label = QLabel("Inbox: 0 messages")
        self._inbox_count_label.setFont(QFont("Inter", 10))
        self._inbox_count_label.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent;")
        s_lay.addWidget(self._inbox_count_label)

        s_lay.addStretch()

        self._last_update_label = QLabel("")
        self._last_update_label.setFont(QFont("Inter", 10))
        self._last_update_label.setStyleSheet(f"color: {_TEXT_DIM}; background: transparent;")
        s_lay.addWidget(self._last_update_label)

        root.addWidget(status_bar)

    # ── Data methods ──────────────────────────────────────────────────

    def _refresh_contacts(self):
        self._contact_list.clear()
        names = _contact_names()
        for name in names:
            item = QListWidgetItem(name)
            self._contact_list.addItem(item)
        # Also populate combo
        self._target_combo.clear()
        self._target_combo.addItems([n for n in names if not n.startswith("📢")])
        # Add groups at bottom
        for n in names:
            if n.startswith("📢"):
                self._target_combo.addItem(n)

    def _filter_contacts(self, text: str):
        text = text.strip().lower()
        for i in range(self._contact_list.count()):
            item = self._contact_list.item(i)
            if not text or text in (item.text() or "").lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def _on_contact_selected(self, item: QListWidgetItem):
        name = item.text().replace("📢 ", "")
        self._target_combo.setCurrentText(name)
        self._msg_input.setFocus()
        self._publish_focus(f"Selected contact: {name}")

    def _refresh_all(self):
        self._refresh_contacts()
        self._render_conversation()

    def _poll_inbox(self):
        """Stat-check inbox/outbox for changes, re-render only if modified."""
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
            if _BRIDGE_TRACE.exists():
                mt = _BRIDGE_TRACE.stat().st_mtime
                if mt != self._outbox_mtime:
                    self._outbox_mtime = mt
                    changed = True
        except Exception:
            pass
        if changed:
            self._render_conversation()

    def _render_conversation(self):
        """Merge inbox + outbox into a time-sorted conversation view."""
        inbox = _read_inbox(max_rows=80)
        outbox = _read_outbox(max_rows=40)

        # Build unified timeline
        events = []
        for row in inbox:
            ts = row.get("ts", 0)
            from_me = row.get("from_me", False)
            name = row.get("name", "Unknown")
            text = row.get("text", "")
            chat_type = row.get("chat_type", "direct")
            participant = row.get("participant", "")

            if from_me:
                sender = "George"
                color = _TEAL
            else:
                sender = name or "Unknown"
                color = _TEXT

            badge = ""
            if chat_type == "group":
                group_name = name if not from_me else ""
                if participant:
                    badge = f' <span style="color:{_TEXT_DIM};font-size:10px;">[group]</span>'

            events.append((ts, "in", sender, text, color, badge, chat_type))

        for row in outbox:
            ts = row.get("ts", 0)
            ok = row.get("ok", False)
            text = row.get("text", "")
            target = row.get("target", "?")
            status = row.get("status", "")
            source = row.get("source", "")

            if "alice" in source.lower() or "autonomous" in source.lower():
                sender = "Alice"
                color = _PURPLE
            else:
                sender = "George"
                color = _TEAL

            status_badge = ""
            if ok:
                status_badge = f' <span style="color:{_GREEN};font-size:10px;">✓ sent</span>'
            elif "SILENCE" in status or "BLOCKED" in status:
                status_badge = f' <span style="color:{_ORANGE};font-size:10px;">⊘ {status.lower()}</span>'
            else:
                status_badge = f' <span style="color:{_RED};font-size:10px;">✗ {status.lower()}</span>'

            events.append((ts, "out", f"{sender} → {target}", text, color, status_badge, "send"))

        # Sort by timestamp
        events.sort(key=lambda e: e[0])

        # Render HTML
        html_parts = []
        last_date = ""
        for ts, direction, sender, text, color, badge, chat_type in events:
            dt = datetime.fromtimestamp(ts)
            date_str = dt.strftime("%b %d, %Y")
            time_str = dt.strftime("%H:%M")

            if date_str != last_date:
                last_date = date_str
                html_parts.append(
                    f'<div style="text-align:center;color:{_TEXT_DIM};font-size:11px;'
                    f'padding:12px 0 6px 0;font-weight:bold;">'
                    f'── {date_str} ──</div>'
                )

            arrow = "◀" if direction == "in" else "▶"
            text_escaped = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            html_parts.append(
                f'<div style="margin:3px 0;padding:6px 8px;'
                f'border-radius:8px;background:rgba(26,27,38,0.6);">'
                f'<span style="color:{color};font-weight:bold;font-size:12px;">'
                f'{arrow} {sender}</span>'
                f'<span style="color:{_TEXT_DIM};font-size:10px;margin-left:8px;">{time_str}</span>'
                f'{badge}'
                f'<br/>'
                f'<span style="color:{_TEXT};font-size:13px;">{text_escaped}</span>'
                f'</div>'
            )

        self._chat_display.setHtml("".join(html_parts))
        # Scroll to bottom
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._chat_display.setTextCursor(cursor)

        total = len(inbox)
        self._inbox_count_label.setText(f"Inbox: {total} messages")
        self._last_update_label.setText(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

    def _check_bridge_health(self):
        """Check both bridge.js and ingest server health."""
        bridge_ok, bridge_info = _check_health(_BRIDGE_HEALTH)
        if bridge_ok:
            self._bridge_status.setText("● Bridge: connected")
            self._bridge_status.setStyleSheet(f"color: {_GREEN}; background: transparent;")
        else:
            self._bridge_status.setText("● Bridge: offline")
            self._bridge_status.setStyleSheet(f"color: {_RED}; background: transparent;")

        ingest_ok, ingest_info = _check_health(_INGEST_HEALTH)
        if ingest_ok:
            self._ingest_status.setText("● Ingest: listening")
            self._ingest_status.setStyleSheet(f"color: {_GREEN}; background: transparent; margin-left: 12px;")
        else:
            self._ingest_status.setText("● Ingest: offline")
            self._ingest_status.setStyleSheet(f"color: {_RED}; background: transparent; margin-left: 12px;")

    def _send_message(self):
        """Send a WhatsApp message through the real effector."""
        target = self._target_combo.currentText().strip().replace("📢 ", "")
        text = self._msg_input.text().strip()

        if not target:
            return
        if not text:
            return

        self._msg_input.clear()

        try:
            sys.path.insert(0, str(_REPO))
            from System.whatsapp_bridge_autopilot import send_whatsapp
            result = send_whatsapp(
                target,
                text,
                source="owner_explicit_whatsapp_organ",
            )
            ok = result.get("ok", False)
            status = result.get("status", "UNKNOWN")

            if ok:
                self._publish_focus(f"Sent message to {target}")
            else:
                reason = result.get("result", status)
                QMessageBox.warning(
                    self,
                    "Send Failed",
                    f"Could not send to {target}:\n{reason}",
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Send Error",
                f"Effector error:\n{type(e).__name__}: {e}",
            )

        # Refresh to show the new outbound message
        QTimer.singleShot(500, self._render_conversation)

    def closeEvent(self, event):
        if hasattr(self, "_poll_timer"):
            self._poll_timer.stop()
        if hasattr(self, "_health_timer"):
            self._health_timer.stop()
        super().closeEvent(event)


# ── Standalone launch ──────────────────────────────────────────────────
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = WhatsAppOrganWidget()
    w.setWindowTitle("SIFTA WhatsApp Organ")
    w.resize(960, 640)
    w.show()
    sys.exit(app.exec())
