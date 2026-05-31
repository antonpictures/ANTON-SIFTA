#!/usr/bin/env python3
"""
swarm_sticky_global_chat_panel.py
═════════════════════════════════
Read-only sticky mirror of Alice's one global chat for SIFTA app surfaces.

This panel deliberately reads the canonical `.sifta_state/alice_conversation.jsonl`
through `swarm_global_chat_view_model`. It does not create a second chat,
worker, cortex call, or local GCI thread. Apps can dock it beside their own
surface so the owner can keep the same conversation in view while working
inside a limb.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Any

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from System.swarm_global_chat_view_model import ChatRow, load_recent_view


TRUTH_LABEL = "STICKY_GLOBAL_CHAT_MIRROR_V1"

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_STATE_DIR = _REPO_ROOT / ".sifta_state"


@dataclass(frozen=True)
class StickyChatEvent:
    ts: float
    event: str
    app_name: str
    truth_label: str = TRUTH_LABEL


def resolve_state_dir(state_dir: str | Path | None = None) -> Path:
    """Resolve either repo root or `.sifta_state` to the real state directory."""
    if state_dir is None:
        return _DEFAULT_STATE_DIR
    p = Path(state_dir)
    if p.name == ".sifta_state":
        return p
    if (p / "alice_conversation.jsonl").exists():
        return p
    return p / ".sifta_state"


def _short_time(ts: float) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S")
    except (OSError, OverflowError, TypeError, ValueError):
        return "--:--:--"


def _speaker_label(row: ChatRow) -> str:
    speaker = (row.speaker or "unknown").strip().lower()
    if speaker == "owner":
        modality = (row.modality or "").strip().lower()
        return "Owner" + (f" ({modality})" if modality in {"typed", "spoken"} else "")
    if speaker == "alice":
        return "Alice"
    if speaker == "system":
        return "System"
    if speaker.startswith("arm:"):
        return speaker
    return speaker.title() if speaker else "Unknown"


def format_sticky_chat_rows(
    rows: Iterable[ChatRow],
    *,
    app_name: str,
    max_rows: int = 12,
) -> str:
    """Render recent global-chat rows as compact plain text for the sticky panel."""
    safe_app = (app_name or "current app").strip()
    selected = list(rows)[-max(1, int(max_rows)) :]
    lines = [
        "ONE GLOBAL CHAT",
        f"Sticky mirror attached to: {safe_app}",
        "Reads alice_conversation.jsonl. This is not a second chat.",
        "",
    ]
    if not selected:
        lines.append("(No global chat rows found yet.)")
        return "\n".join(lines)

    for row in selected:
        body = (row.text_preview or row.full_text or "").strip()
        if not body:
            body = "(empty row)"
        refs = ""
        if row.receipt_refs:
            refs = " [" + ", ".join(row.receipt_refs[:3]) + "]"
        lines.append(f"{_short_time(row.ts)}  {_speaker_label(row)}: {body}{refs}")
    return "\n".join(lines)


def record_sticky_chat_event(
    event: str,
    *,
    app_name: str,
    state_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Write a light MANA trace for sticky-chat surface events."""
    sd = resolve_state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "event": str(event or "unknown"),
        "app_name": str(app_name or "unknown"),
        "truth_label": TRUTH_LABEL,
        "currency": "MANA",
        "note": "UI surface trace only; one global chat mirror, no STGM claim.",
    }
    path = sd / "sticky_global_chat_events.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


class StickyGlobalChatPanel(QWidget):
    """Dockable read-only mirror of the canonical global chat ledger."""

    def __init__(
        self,
        *,
        app_name: str,
        state_dir: str | Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._app_name = str(app_name or "SIFTA App")
        self._state_dir = resolve_state_dir(state_dir)
        self._last_text = ""

        self.setObjectName("stickyGlobalChatPanel")
        self.setMinimumWidth(280)
        self.setMaximumWidth(420)
        self.setStyleSheet(
            """
            QWidget#stickyGlobalChatPanel {
                background: rgb(10, 8, 16);
                border-left: 1px solid rgb(45, 42, 65);
            }
            QLabel#stickyTitle {
                color: rgb(0, 255, 200);
                font-weight: 700;
                font-size: 11px;
            }
            QLabel#stickySub {
                color: rgb(135, 145, 180);
                font-size: 9px;
            }
            QPlainTextEdit#stickyChatText {
                background: rgb(8, 7, 13);
                border: 1px solid rgb(45, 42, 65);
                border-radius: 4px;
                color: rgb(200, 210, 240);
                font-size: 10px;
                padding: 6px;
            }
            QPushButton#stickySmallButton {
                padding: 4px 8px;
                font-size: 10px;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        title = QLabel("One Global Chat")
        title.setObjectName("stickyTitle")
        title.setFont(QFont("Menlo", 11, QFont.Weight.Bold))
        root.addWidget(title)

        self._surface_label = QLabel(f"Sticky to: {self._app_name}")
        self._surface_label.setObjectName("stickySub")
        self._surface_label.setWordWrap(True)
        root.addWidget(self._surface_label)

        self._chat_text = QPlainTextEdit()
        self._chat_text.setObjectName("stickyChatText")
        self._chat_text.setReadOnly(True)
        self._chat_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        root.addWidget(self._chat_text, 1)

        btn_row = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("stickySmallButton")
        self._refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self._refresh_btn)

        self._main_chat_btn = QPushButton("Main Chat")
        self._main_chat_btn.setObjectName("stickySmallButton")
        self._main_chat_btn.setToolTip("Return focus to the resident Alice global chat.")
        self._main_chat_btn.clicked.connect(self._open_main_chat)
        btn_row.addWidget(self._main_chat_btn)
        root.addLayout(btn_row)

        footer = QLabel("Mirror only: same Alice ledger, no second conversation.")
        footer.setObjectName("stickySub")
        footer.setWordWrap(True)
        root.addWidget(footer)

        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

        try:
            record_sticky_chat_event("mounted", app_name=self._app_name, state_dir=self._state_dir)
        except Exception:
            pass
        self.refresh()

    def refresh(self) -> None:
        """Reload recent rows from the canonical global chat view-model."""
        try:
            rows = load_recent_view(self._state_dir, max_n=40)
            text = format_sticky_chat_rows(rows, app_name=self._app_name, max_rows=12)
        except Exception as exc:
            text = (
                "ONE GLOBAL CHAT\n"
                f"Sticky mirror attached to: {self._app_name}\n\n"
                f"(Unable to read global chat ledger: {type(exc).__name__}: {exc})"
            )
        if text == self._last_text:
            return
        self._last_text = text
        self._chat_text.setPlainText(text)
        cursor = self._chat_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._chat_text.setTextCursor(cursor)

    def _open_main_chat(self) -> None:
        """Ask the desktop host to return focus to the resident global chat."""
        try:
            record_sticky_chat_event(
                "main_chat_requested",
                app_name=self._app_name,
                state_dir=self._state_dir,
            )
        except Exception:
            pass

        widget: QWidget | None = self
        while widget is not None:
            host = getattr(widget, "_sifta_desktop_host", None)
            if host is not None and hasattr(host, "_switch_desktop_mode"):
                try:
                    host._switch_desktop_mode("chat", force=True)
                    return
                except TypeError:
                    try:
                        host._switch_desktop_mode("chat")
                        return
                    except Exception:
                        break
                except Exception:
                    break
            widget = widget.parentWidget()
