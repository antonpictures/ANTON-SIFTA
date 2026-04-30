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
    QListWidgetItem, QMessageBox, QCheckBox,
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


def _contact_entries() -> list[dict[str, Any]]:
    """Return known WhatsApp targets with phone/LID aliases merged."""
    contacts = _load_contacts()
    try:
        from System.whatsapp_social_graph import canonical_contact_entries

        return canonical_contact_entries(contacts)
    except Exception:
        entries: list[dict[str, Any]] = []
        for _k, v in contacts.items():
            name = v.get("display_name", "").strip()
            jid = str(v.get("jid") or "").strip()
            if not name or not jid or jid == "status@broadcast":
                continue
            chat_type = str(v.get("chat_type") or ("group" if jid.endswith("@g.us") else "direct")).strip()
            is_group = chat_type == "group"
            label = f"📢 {name}" if is_group else name
            entries.append(
                {
                    "label": label,
                    "display_name": name,
                    "jid": jid,
                    "jid_aliases": [jid],
                    "chat_type": chat_type,
                    "send_target_allowed": v.get("send_target_allowed") is not False,
                    "relationship_to_owner": str(v.get("relationship_to_owner") or ""),
                    "merged_count": 1,
                }
            )
        entries.sort(key=lambda e: (e["display_name"].casefold(), e["chat_type"]))
        return entries


def _contact_names() -> list[str]:
    """Return sorted list of known WhatsApp contact display labels."""
    return [entry["label"] for entry in _contact_entries()]


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
        self._refreshing_contacts = False
        self._selected_jid: str = ""  # "" = All Chats, else filter by JID
        self._selected_aliases: set[str] = set()
        self._selected_name: str = "All Chats"
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
        self._contact_list.itemChanged.connect(self._on_contact_auto_changed)
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
        self._target_combo.currentIndexChanged.connect(self._sync_auto_checkbox)
        compose_lay.addWidget(self._target_combo)

        self._auto_reply_checkbox = QCheckBox("Auto")
        self._auto_reply_checkbox.setToolTip("Owner-delegated Alice auto-reply for this person/group")
        self._auto_reply_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {_TEXT};
                background: transparent;
                font-size: 12px;
                font-weight: bold;
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
            }}
            QCheckBox::indicator:unchecked {{
                border: 1px solid {_BORDER};
                border-radius: 4px;
                background: {_BG_INPUT};
            }}
            QCheckBox::indicator:checked {{
                border: 1px solid {_GREEN};
                border-radius: 4px;
                background: {_GREEN};
            }}
        """)
        self._auto_reply_checkbox.toggled.connect(self._on_compose_auto_toggled)
        compose_lay.addWidget(self._auto_reply_checkbox)

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
        prior_jid = ""
        try:
            prior_jid = str(self._current_target_entry().get("jid") or "")
        except Exception:
            prior_jid = ""
        self._refreshing_contacts = True
        self._contact_list.clear()
        entries = _contact_entries()
        try:
            from System.whatsapp_autonomy_settings import is_auto_enabled
        except Exception:
            is_auto_enabled = None

        # "All Chats" item at top
        all_item = QListWidgetItem("💬 All Chats")
        all_item.setData(Qt.ItemDataRole.UserRole, {"jid": "", "label": "All Chats", "display_name": "All Chats"})
        if not self._selected_jid:
            all_item.setSelected(True)
        self._contact_list.addItem(all_item)

        for entry in entries:
            item = QListWidgetItem(entry["label"])
            item.setData(Qt.ItemDataRole.UserRole, entry)
            aliases = list(entry.get("jid_aliases") or [entry.get("jid")])
            if self._selected_jid and self._selected_jid in set(aliases):
                item.setSelected(True)
            if len(aliases) > 1:
                item.setToolTip("Merged WhatsApp aliases: " + ", ".join(aliases))
            if entry.get("send_target_allowed"):
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                enabled = bool(
                    is_auto_enabled
                    and any(
                        is_auto_enabled(alias, chat_type=entry["chat_type"])
                        for alias in aliases
                    )
                )
                item.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
            else:
                item.setToolTip("Owner/control identity - auto-reply disabled")
            self._contact_list.addItem(item)

        # Also populate combo
        self._target_combo.clear()
        selected_idx = -1
        for entry in entries:
            if not entry.get("send_target_allowed"):
                continue
            self._target_combo.addItem(entry["label"], entry)
            if prior_jid and prior_jid in set(entry.get("jid_aliases") or [entry.get("jid")]):
                selected_idx = self._target_combo.count() - 1
        if selected_idx >= 0:
            self._target_combo.setCurrentIndex(selected_idx)
        self._refreshing_contacts = False
        self._sync_auto_checkbox()

    def _filter_contacts(self, text: str):
        text = text.strip().lower()
        for i in range(self._contact_list.count()):
            item = self._contact_list.item(i)
            if not text or text in (item.text() or "").lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def _on_contact_selected(self, item: QListWidgetItem):
        entry = item.data(Qt.ItemDataRole.UserRole) or {}
        jid = str(entry.get("jid") or "").strip()
        label = entry.get("label") or item.text()
        name = str(entry.get("display_name") or label).replace("📢 ", "")

        # Update selected filter
        self._selected_jid = jid
        self._selected_aliases = {str(alias).strip() for alias in (entry.get("jid_aliases") or [jid]) if str(alias).strip()}
        self._selected_name = name if jid else "All Chats"
        if not jid:
            self._selected_aliases = set()

        # Update compose bar target
        if jid:
            idx = self._target_combo.findText(label)
            if idx >= 0:
                self._target_combo.setCurrentIndex(idx)
            else:
                self._target_combo.setCurrentText(label.replace("📢 ", ""))

        self._msg_input.setFocus()
        self._publish_focus(f"Viewing: {self._selected_name}")
        self._render_conversation()

    def _current_target_entry(self) -> dict[str, Any]:
        data = self._target_combo.currentData()
        if isinstance(data, dict):
            return data
        label = self._target_combo.currentText().strip()
        clean = label.replace("📢 ", "")
        for entry in _contact_entries():
            if label == entry.get("label") or clean == entry.get("display_name"):
                return entry
        return {"label": label, "display_name": clean, "jid": clean, "jid_aliases": [clean], "chat_type": "direct"}

    def _set_auto_enabled_for_entry(self, entry: dict[str, Any], enabled: bool) -> bool:
        jid = str(entry.get("jid") or "").strip()
        if not jid:
            return False
        aliases = [str(alias).strip() for alias in (entry.get("jid_aliases") or [jid]) if str(alias).strip()]
        try:
            from System.whatsapp_autonomy_settings import set_auto_enabled

            for alias in aliases:
                set_auto_enabled(
                    alias,
                    display_name=str(entry.get("display_name") or entry.get("label") or ""),
                    chat_type=str(entry.get("chat_type") or ""),
                    enabled=bool(enabled),
                    actor="owner",
                    source="whatsapp_organ",
                )
            self._publish_focus(
                f"WhatsApp auto-reply {'ON' if enabled else 'OFF'}: "
                f"{entry.get('display_name') or jid}"
            )
            return True
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Auto Reply",
                f"Could not update auto-reply for {entry.get('display_name') or jid}:\n{exc}",
            )
            return False

    def _sync_auto_checkbox(self):
        entry = self._current_target_entry()
        jid = str(entry.get("jid") or "").strip()
        enabled = False
        allowed = bool(entry.get("send_target_allowed", True)) and bool(jid)
        if allowed:
            try:
                from System.whatsapp_autonomy_settings import is_auto_enabled

                aliases = [str(alias).strip() for alias in (entry.get("jid_aliases") or [jid]) if str(alias).strip()]
                enabled = any(
                    is_auto_enabled(alias, chat_type=str(entry.get("chat_type") or ""))
                    for alias in aliases
                )
            except Exception:
                enabled = False
        self._auto_reply_checkbox.blockSignals(True)
        self._auto_reply_checkbox.setEnabled(allowed)
        self._auto_reply_checkbox.setChecked(enabled)
        self._auto_reply_checkbox.blockSignals(False)

    def _on_compose_auto_toggled(self, checked: bool):
        if self._refreshing_contacts:
            return
        entry = self._current_target_entry()
        if self._set_auto_enabled_for_entry(entry, checked):
            self._refresh_contacts()

    def _on_contact_auto_changed(self, item: QListWidgetItem):
        if self._refreshing_contacts:
            return
        entry = item.data(Qt.ItemDataRole.UserRole) or {}
        if not entry.get("send_target_allowed"):
            return
        enabled = item.checkState() == Qt.CheckState.Checked
        if self._set_auto_enabled_for_entry(entry, enabled):
            self._sync_auto_checkbox()

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
        """Merge inbox + outbox into a time-sorted conversation view.

        When a contact is selected (self._selected_jid), only show messages
        involving that JID. When empty / All Chats, show everything.
        """
        inbox = _read_inbox(max_rows=200)
        outbox = _read_outbox(max_rows=100)
        filter_jid = self._selected_jid  # "" = show all
        filter_aliases = set(self._selected_aliases or ({filter_jid} if filter_jid else set()))
        filter_name_norm = " ".join((self._selected_name or "").casefold().split())

        # Build unified timeline
        events = []
        for row in inbox:
            from_jid = str(row.get("from_jid") or "").strip()
            ts = row.get("ts", 0)
            from_me = row.get("from_me", False)
            name = row.get("name", "Unknown")
            text = row.get("text", "")
            chat_type = row.get("chat_type", "direct")
            participant = row.get("participant", "")

            # Filter: skip messages not involving selected JID
            if filter_jid:
                name_norm = " ".join(str(name or "").casefold().split())
                status_name_match = from_jid == "status@broadcast" and name_norm == filter_name_norm
                if from_jid not in filter_aliases and participant not in filter_aliases and not status_name_match:
                    continue

            if from_me:
                sender = "George"
                color = _TEAL
            else:
                sender = name or "Unknown"
                color = _TEXT

            badge = ""
            if chat_type == "group":
                badge = f' <span style="color:{_TEXT_DIM};font-size:10px;">[{name}]</span>'

            events.append((ts, "in", sender, text, color, badge, chat_type))

        for row in outbox:
            resolved_jid = str(row.get("resolved_jid") or "").strip()
            target_name = str(row.get("target") or "?").strip()
            ts = row.get("ts", 0)
            ok = row.get("ok", False)
            text = row.get("text", "")
            status = row.get("status", "")
            source = row.get("source", "")

            # Filter: skip sends not to the selected JID
            if filter_jid:
                target_norm = " ".join(str(target_name or "").casefold().split())
                if resolved_jid not in filter_aliases and target_norm != filter_name_norm:
                    continue

            if "alice" in source.lower() or "autonomous" in source.lower() or "auto" in source.lower():
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

            events.append((ts, "out", f"{sender} → {target_name}", text, color, status_badge, "send"))

        # Sort by timestamp
        events.sort(key=lambda e: e[0])

        # Header
        view_label = self._selected_name or "All Chats"

        # Render HTML
        html_parts = [
            f'<div style="text-align:center;color:{_ACCENT};font-size:13px;'
            f'padding:8px 0;font-weight:bold;">'
            f'── {view_label} ──</div>'
        ]
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

        if not events and filter_jid:
            html_parts.append(
                f'<div style="text-align:center;color:{_TEXT_DIM};font-size:14px;'
                f'padding:40px 0;">No messages with {view_label} yet</div>'
            )

        self._chat_display.setHtml("".join(html_parts))
        # Scroll to bottom
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._chat_display.setTextCursor(cursor)

        count_label = f"{len(events)} messages" if filter_jid else f"Inbox: {len(inbox)} messages"
        self._inbox_count_label.setText(count_label)
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
        entry = self._current_target_entry()
        target = str(entry.get("jid") or self._target_combo.currentText()).strip().replace("📢 ", "")
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
                allow_group_send=str(entry.get("chat_type") or "") == "group",
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
