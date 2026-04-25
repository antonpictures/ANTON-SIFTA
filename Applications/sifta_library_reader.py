"""
Applications/sifta_library_reader.py
═══════════════════════════════════════════
GUI reader for .sifta_state/stigmergic_library.jsonl — the curated knowledge
nuggets Alice and the Architect built together.

Features:
  • Full-text search across all nuggets
  • Category filter (NATURE, AGI_THEORY, etc.)
  • Random Nugget button (surprise discovery)
  • Detail pane with full text + metadata
  • Add Nugget — the Architect can write new entries directly
"""

import json
import random
import time
import uuid
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QTextEdit,
    QFrame, QPushButton, QComboBox, QSplitter, QDialog,
    QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

_REPO = Path(__file__).resolve().parent.parent
_LIB = _REPO / ".sifta_state" / "stigmergic_library.jsonl"

_CATEGORY_ICONS = {
    "NATURE": "🌿",
    "AGI_THEORY": "🧠",
    "PHYSICS": "⚛️",
    "MATH": "∑",
    "HISTORY": "📜",
    "BIOLOGY": "🧬",
    "ARCHITECTURE": "🏛️",
    "SIFTA": "🧜‍♀️",
    "GENERAL": "💡",
}


def _load_nuggets() -> list[dict]:
    if not _LIB.exists():
        return []
    nuggets = []
    try:
        with _LIB.open("r") as f:
            for line in f:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    nuggets.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return nuggets


def _append_nugget(nugget: dict):
    with _LIB.open("a") as f:
        f.write(json.dumps(nugget) + "\n")


class AddNuggetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Nugget to Library")
        self.setMinimumWidth(500)
        self.setStyleSheet("background-color: #1a1b26; color: #c0caf5;")

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Category:"))
        self.cat_box = QComboBox()
        self.cat_box.addItems(list(_CATEGORY_ICONS.keys()))
        self.cat_box.setStyleSheet("background: #24283b; color: #c0caf5; border: 1px solid #414868; padding: 6px; border-radius: 6px;")
        layout.addWidget(self.cat_box)

        layout.addWidget(QLabel("Nugget text:"))
        self.text_edit = QTextEdit()
        self.text_edit.setMinimumHeight(120)
        self.text_edit.setStyleSheet("background: #24283b; color: #c0caf5; border: 1px solid #414868; border-radius: 6px; padding: 8px;")
        layout.addWidget(self.text_edit)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_nugget(self) -> dict | None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            return None
        return {
            "ts": time.time(),
            "category": self.cat_box.currentText(),
            "nugget_text": text,
            "source_api": "ARCHITECT_MANUAL",
            "curator_agent": "ARCHITECT",
        }


class LibraryReaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stigmergic Library")
        self.setStyleSheet("background-color: rgba(26, 27, 38, 0.97); border-radius: 12px;")

        self._all_nuggets: list[dict] = []
        self._filtered: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────────
        top = QFrame()
        top.setFixedHeight(60)
        top.setStyleSheet("background: rgba(36, 40, 59, 0.8); border-bottom: 1px solid #414868;")
        top_h = QHBoxLayout(top)
        top_h.setContentsMargins(20, 0, 20, 0)

        title = QLabel("📚 Stigmergic Library")
        title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #bb9af7;")
        top_h.addWidget(title)
        top_h.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search nuggets…")
        self.search_box.setFixedWidth(220)
        self.search_box.setStyleSheet(
            "background: rgba(26,27,38,0.8); color: #c0caf5; border: 1px solid #414868; "
            "border-radius: 8px; padding: 6px 12px; font-size: 14px;"
        )
        self.search_box.textChanged.connect(self._apply_filter)
        top_h.addWidget(self.search_box)

        self.cat_filter = QComboBox()
        self.cat_filter.addItem("All Categories")
        self.cat_filter.setStyleSheet(
            "background: #24283b; color: #a9b1d6; border: 1px solid #414868; "
            "border-radius: 8px; padding: 6px 10px; font-size: 13px;"
        )
        self.cat_filter.currentTextChanged.connect(self._apply_filter)
        top_h.addWidget(self.cat_filter)

        rand_btn = QPushButton("🎲 Random")
        rand_btn.setStyleSheet(
            "background: #7aa2f7; color: #1a1b26; border-radius: 8px; "
            "padding: 6px 14px; font-weight: bold; font-size: 13px;"
        )
        rand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rand_btn.clicked.connect(self._show_random)
        top_h.addWidget(rand_btn)

        add_btn = QPushButton("✏️ Add")
        add_btn.setStyleSheet(
            "background: #bb9af7; color: #1a1b26; border-radius: 8px; "
            "padding: 6px 14px; font-weight: bold; font-size: 13px;"
        )
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_nugget)
        top_h.addWidget(add_btn)

        self.count_lbl = QLabel()
        self.count_lbl.setStyleSheet("color: #565f89; font-size: 12px; margin-left: 12px;")
        top_h.addWidget(self.count_lbl)

        layout.addWidget(top)

        # ── Splitter ──────────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: rgba(36, 40, 59, 0.5);
                border: none;
                border-right: 1px solid #414868;
                font-size: 14px;
                color: #a9b1d6;
            }
            QListWidget::item { padding: 12px 16px; border-bottom: 1px solid #292e42; }
            QListWidget::item:selected { background: rgba(187, 154, 247, 0.25); color: #c0caf5; }
            QListWidget::item:hover { background: rgba(65, 72, 104, 0.4); }
        """)
        self.list_widget.currentRowChanged.connect(self._show_nugget)
        splitter.addWidget(self.list_widget)

        # Detail pane
        detail_frame = QFrame()
        detail_frame.setStyleSheet("background: transparent;")
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(24, 20, 24, 20)

        self.detail_category = QLabel()
        self.detail_category.setStyleSheet("color: #7aa2f7; font-size: 13px; font-weight: bold;")
        detail_layout.addWidget(self.detail_category)

        self.detail_date = QLabel()
        self.detail_date.setStyleSheet("color: #565f89; font-size: 12px;")
        detail_layout.addWidget(self.detail_date)

        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setStyleSheet("""
            QTextEdit {
                background: rgba(36, 40, 59, 0.4);
                border: 1px solid #414868;
                border-radius: 8px;
                color: #c0caf5;
                font-size: 16px;
                padding: 16px;
                line-height: 1.6;
            }
        """)
        self.detail_text.setFont(QFont("Inter", 15))
        detail_layout.addWidget(self.detail_text)

        self.detail_source = QLabel()
        self.detail_source.setStyleSheet("color: #414868; font-size: 11px;")
        detail_layout.addWidget(self.detail_source)

        splitter.addWidget(detail_frame)
        splitter.setSizes([300, 700])

        layout.addWidget(splitter)

        self._load()

        # Reload every 30 s
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._load)
        self._timer.start(30000)

    def _load(self):
        self._all_nuggets = _load_nuggets()

        # Populate category filter
        cats = sorted({n.get("category", n.get("domain", "GENERAL")) for n in self._all_nuggets})
        current_cat = self.cat_filter.currentText()
        self.cat_filter.blockSignals(True)
        self.cat_filter.clear()
        self.cat_filter.addItem("All Categories")
        for c in cats:
            self.cat_filter.addItem(c)
        idx = self.cat_filter.findText(current_cat)
        self.cat_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.cat_filter.blockSignals(False)

        self._apply_filter()

    def _apply_filter(self):
        query = self.search_box.text().strip().lower()
        cat = self.cat_filter.currentText()

        self._filtered = []
        for n in self._all_nuggets:
            n_cat = n.get("category", n.get("domain", "GENERAL"))
            if cat != "All Categories" and n_cat != cat:
                continue
            text = (n.get("nugget_text", "") + " " + n.get("question", "")).lower()
            if query and query not in text:
                continue
            self._filtered.append(n)

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for n in reversed(self._filtered):  # newest first
            n_cat = n.get("category", n.get("domain", "GENERAL"))
            icon = _CATEGORY_ICONS.get(n_cat, "💡")
            snippet = (n.get("nugget_text", "") or n.get("question", ""))[:60].strip()
            item = QListWidgetItem(f"{icon}  {snippet}…")
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

        self.count_lbl.setText(f"{len(self._filtered)} nuggets")
        if self._filtered:
            self.list_widget.setCurrentRow(0)
            self._show_nugget(0)

    def _show_nugget(self, row: int):
        if row < 0 or row >= len(self._filtered):
            return
        # list is displayed reversed
        n = list(reversed(self._filtered))[row]
        n_cat = n.get("category", n.get("domain", "GENERAL"))
        icon = _CATEGORY_ICONS.get(n_cat, "💡")
        self.detail_category.setText(f"{icon}  {n_cat}")

        ts = n.get("ts", 0)
        try:
            ts_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
        except Exception:
            ts_str = "unknown date"
        self.detail_date.setText(ts_str)

        text = n.get("nugget_text") or n.get("question", "")
        self.detail_text.setPlainText(text)

        curator = n.get("curator_agent", "")
        source = n.get("source_api", "")
        self.detail_source.setText(f"Source: {source}  •  Curator: {curator}")

    def _show_random(self):
        if not self._filtered:
            return
        n = random.choice(self._filtered)
        idx = list(reversed(self._filtered)).index(n)
        self.list_widget.setCurrentRow(idx)
        self._show_nugget(idx)

    def _add_nugget(self):
        dlg = AddNuggetDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nugget = dlg.get_nugget()
            if nugget:
                _append_nugget(nugget)
                self._load()
