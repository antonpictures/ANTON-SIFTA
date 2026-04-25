"""
Applications/sifta_conversation_browser.py
═══════════════════════════════════════════
Full GUI browser for alice_conversation.jsonl — the live transcript of every
spoken turn between the Architect and Alice, with STT confidence badges,
silent-failure highlights, and a search bar.
"""

import json
import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QScrollArea, QFrame, QPushButton,
    QSizePolicy, QSplitter, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

_REPO = Path(__file__).resolve().parent.parent
_CONVO = _REPO / ".sifta_state" / "alice_conversation.jsonl"


def _load_turns(limit: int = 500) -> list[dict]:
    if not _CONVO.exists():
        return []
    turns = []
    try:
        with _CONVO.open("r") as f:
            for line in f:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    row = json.loads(line)
                    payload = row.get("payload", row)
                    role = payload.get("role", "")
                    text = payload.get("text", "").strip()
                    ts_raw = payload.get("ts") or (row.get("ts", {}).get("physical_pt") if isinstance(row.get("ts"), dict) else row.get("ts", 0))
                    try:
                        ts = float(ts_raw or 0)
                    except (TypeError, ValueError):
                        ts = 0.0
                    confidence = payload.get("stt_confidence")
                    model = payload.get("model", "")
                    if role and text:
                        turns.append({
                            "role": role,
                            "text": text,
                            "ts": ts,
                            "confidence": confidence,
                            "model": model,
                        })
                except (json.JSONDecodeError, AttributeError):
                    continue
    except OSError:
        return []
    return turns[-limit:]


class TurnBubble(QFrame):
    def __init__(self, turn: dict, parent=None):
        super().__init__(parent)
        role = turn["role"]
        text = turn["text"]
        ts = turn["ts"]
        confidence = turn.get("confidence")
        is_silent = "(silent" in text.lower()
        is_alice = role == "alice"

        self.setStyleSheet(
            "QFrame { background: transparent; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        # Role + time header
        ts_str = time.strftime("%H:%M", time.localtime(ts)) if ts else ""
        conf_str = f"  •  STT {confidence:.0%}" if confidence is not None else ""
        role_label = "🧜‍♀️ Alice" if is_alice else "🏛️ Architect"
        header = QLabel(f"<b>{role_label}</b>  <span style='color:#565f89; font-size:11px'>{ts_str}{conf_str}</span>")
        header.setStyleSheet("color: #a9b1d6; font-size: 12px;")
        layout.addWidget(header)

        # Bubble
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setFont(QFont("Inter", 14))
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if is_silent:
            bubble.setStyleSheet(
                "background-color: rgba(255, 90, 90, 0.15); color: #f7768e; "
                "border-left: 3px solid #f7768e; padding: 10px 14px; border-radius: 6px;"
            )
        elif is_alice:
            bubble.setStyleSheet(
                "background-color: rgba(122, 162, 247, 0.12); color: #c0caf5; "
                "border-left: 3px solid #7aa2f7; padding: 10px 14px; border-radius: 6px;"
            )
        else:
            bubble.setStyleSheet(
                "background-color: rgba(187, 154, 247, 0.12); color: #c0caf5; "
                "border-left: 3px solid #bb9af7; padding: 10px 14px; border-radius: 6px;"
            )

        layout.addWidget(bubble)
        self.text_content = text.lower()
        self._is_visible = True

    def matches(self, query: str) -> bool:
        return not query or query in self.text_content


class ConversationBrowserApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Conversation History")
        self.setStyleSheet("background-color: rgba(26, 27, 38, 0.97); border-radius: 12px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top Bar ──────────────────────────────────────────────────────────
        top_bar = QFrame()
        top_bar.setFixedHeight(54)
        top_bar.setStyleSheet("background: rgba(36, 40, 59, 0.8); border-bottom: 1px solid #414868;")
        top_h = QHBoxLayout(top_bar)
        top_h.setContentsMargins(20, 0, 20, 0)

        title_lbl = QLabel("💬 Conversation History")
        title_lbl.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #bb9af7;")
        top_h.addWidget(title_lbl)
        top_h.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search turns…")
        self.search_box.setFixedWidth(260)
        self.search_box.setStyleSheet(
            "background: rgba(26, 27, 38, 0.8); color: #c0caf5; "
            "border: 1px solid #414868; border-radius: 8px; padding: 6px 12px; font-size: 14px;"
        )
        self.search_box.textChanged.connect(self._filter)
        top_h.addWidget(self.search_box)

        self.count_lbl = QLabel()
        self.count_lbl.setStyleSheet("color: #565f89; font-size: 13px; margin-left: 12px;")
        top_h.addWidget(self.count_lbl)

        layout.addWidget(top_bar)

        # ── Scroll Area ───────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._feed = QVBoxLayout(self._container)
        self._feed.setContentsMargins(20, 16, 20, 16)
        self._feed.setSpacing(10)
        self._feed.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll)
        self._scroll = scroll

        # ── Load ──────────────────────────────────────────────────────────────
        self._bubbles: list[TurnBubble] = []
        self._load_turns()

        # Live-reload every 8 s
        self._reload_timer = QTimer(self)
        self._reload_timer.timeout.connect(self._load_turns)
        self._reload_timer.start(8000)

    def _load_turns(self):
        turns = _load_turns(limit=300)

        # Only rebuild if count changed (cheap guard)
        if len(turns) == len(self._bubbles):
            return

        # Clear existing
        while self._feed.count() > 1:
            item = self._feed.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._bubbles.clear()

        for t in turns:
            bubble = TurnBubble(t)
            self._feed.insertWidget(self._feed.count() - 1, bubble)
            self._bubbles.append(bubble)

        self.count_lbl.setText(f"{len(turns)} turns")

        # Scroll to bottom
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _filter(self, query: str):
        q = query.strip().lower()
        visible = 0
        for b in self._bubbles:
            show = b.matches(q)
            b.setVisible(show)
            if show:
                visible += 1
        self.count_lbl.setText(f"{visible} / {len(self._bubbles)} turns")
