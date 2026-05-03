#!/usr/bin/env python3
"""SIFTA Media Shazam — stigmergic YouTube/media category guessing app."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_media_shazam import (  # noqa: E402
    format_guess_for_prompt,
    observe_current_media,
    youtube_categories,
)


_BG = "#10131a"
_PANEL = "#171c26"
_PANEL_2 = "#1d2430"
_TEXT = "#e7edf7"
_DIM = "#96a0b5"
_CYAN = "#00d2ff"
_GREEN = "#00e676"
_AMBER = "#ffbf3c"
_RED = "#ff5c6c"

_STYLE = f"""
QWidget {{
    background: {_BG};
    color: {_TEXT};
    font-family: "SF Mono", "Menlo", monospace;
}}
QFrame#Panel {{
    background: {_PANEL};
    border: 1px solid #2c3748;
    border-radius: 8px;
}}
QLabel#Title {{
    color: {_CYAN};
    font-size: 20px;
    font-weight: 800;
}}
QLabel#Subtle {{
    color: {_DIM};
}}
QLabel#Metric {{
    color: {_TEXT};
    font-size: 14px;
    font-weight: 700;
}}
QPushButton {{
    background: {_PANEL_2};
    border: 1px solid {_CYAN};
    color: {_CYAN};
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: 800;
}}
QPushButton:hover {{
    background: {_CYAN};
    color: {_BG};
}}
QProgressBar {{
    border: 1px solid #344155;
    border-radius: 6px;
    text-align: center;
    background: #0b0f15;
    color: {_TEXT};
    height: 14px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, x2:1, stop:0 {_CYAN}, stop:1 {_GREEN});
    border-radius: 5px;
}}
QTextEdit {{
    background: #0b0f15;
    border: 1px solid #2c3748;
    border-radius: 6px;
    padding: 8px;
    color: {_TEXT};
}}
QScrollArea {{
    border: none;
}}
"""


def _tail_jsonl(path: Path, n: int = 8) -> list[dict]:
    if not path.exists():
        return []
    try:
        lines = path.read_text("utf-8", errors="replace").splitlines()[-n:]
    except Exception:
        return []
    out = []
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _ago(ts: float) -> str:
    delta = max(0.0, time.time() - float(ts or 0.0))
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    return f"{int(delta // 3600)}h ago"


class CategoryPill(QFrame):
    def __init__(self, name: str, active: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name = name
        self.active = active
        self.score = 0.0
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.label = QLabel(name)
        self.label.setWordWrap(True)
        self.label.setMinimumHeight(34)
        self.label.setStyleSheet(f"color: {_TEXT if active else _DIM}; font-weight: 700;")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        layout.addWidget(self.label)
        layout.addWidget(self.bar)

    def set_score(self, score: float, max_score: float) -> None:
        self.score = max(0.0, float(score or 0.0))
        pct = int(round(100.0 * self.score / max(1.0, max_score)))
        self.bar.setValue(pct)
        if self.score > 0:
            color = _GREEN if self.active else _AMBER
            self.label.setStyleSheet(f"color: {color}; font-weight: 900;")
        else:
            self.label.setStyleSheet(f"color: {_TEXT if self.active else _DIM}; font-weight: 700;")


class MediaShazamApp(QWidget):
    """Live stigmergic media classifier surface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SIFTA Media Shazam")
        self.setMinimumSize(900, 640)
        self.setStyleSheet(_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("SIFTA Media Shazam")
        title.setObjectName("Title")
        subtitle = QLabel("Unified stigmergic media guesser: YouTube categories, source family, and receipt evidence.")
        subtitle.setObjectName("Subtle")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        self.guess_btn = QPushButton("Guess Now")
        self.guess_btn.clicked.connect(self.refresh)
        header.addWidget(self.guess_btn)
        root.addLayout(header)

        self.summary = QFrame()
        self.summary.setObjectName("Panel")
        summary_layout = QGridLayout(self.summary)
        summary_layout.setContentsMargins(12, 12, 12, 12)
        summary_layout.setHorizontalSpacing(16)
        self.category = QLabel("Waiting for receipts")
        self.category.setObjectName("Title")
        self.conf = QProgressBar()
        self.conf.setRange(0, 100)
        self.source = QLabel("source: --")
        self.source.setObjectName("Metric")
        self.title_guess = QLabel("title: --")
        self.title_guess.setWordWrap(True)
        self.title_guess.setObjectName("Metric")
        self.receipts = QLabel("receipts: --")
        self.receipts.setObjectName("Subtle")
        summary_layout.addWidget(self.category, 0, 0, 1, 2)
        summary_layout.addWidget(self.conf, 1, 0, 1, 2)
        summary_layout.addWidget(self.source, 2, 0)
        summary_layout.addWidget(self.receipts, 2, 1)
        summary_layout.addWidget(self.title_guess, 3, 0, 1, 2)
        root.addWidget(self.summary)

        body = QHBoxLayout()
        left = QFrame()
        left.setObjectName("Panel")
        left_layout = QVBoxLayout(left)
        left_hdr = QLabel("YouTube Category Swarm")
        left_hdr.setObjectName("Metric")
        left_layout.addWidget(left_hdr)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self.category_grid = QGridLayout(inner)
        self.category_grid.setSpacing(8)
        self.pills: list[tuple[dict, CategoryPill]] = []
        for idx, cat in enumerate(youtube_categories(include_legacy=True)):
            pill = CategoryPill(cat["name"], bool(cat.get("active")))
            self.pills.append((cat, pill))
            self.category_grid.addWidget(pill, idx // 3, idx % 3)
        scroll.setWidget(inner)
        left_layout.addWidget(scroll)
        body.addWidget(left, 2)

        right = QFrame()
        right.setObjectName("Panel")
        right_layout = QVBoxLayout(right)
        evidence_hdr = QLabel("Evidence and Recent Guesses")
        evidence_hdr.setObjectName("Metric")
        self.evidence = QTextEdit()
        self.evidence.setReadOnly(True)
        right_layout.addWidget(evidence_hdr)
        right_layout.addWidget(self.evidence)
        body.addWidget(right, 1)
        root.addLayout(body, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)
        self.refresh()

    def refresh(self) -> None:
        try:
            row = observe_current_media(state_dir=_STATE, write=True)
        except Exception as exc:
            row = {
                "status": "error",
                "primary_category": "Error",
                "confidence": 0.0,
                "source_label": type(exc).__name__,
                "evidence_terms": [str(exc)[:120]],
                "category_candidates": [],
                "source_ledgers": [],
                "evidence_rows": 0,
            }

        category = row.get("primary_category") or "No current category signal"
        self.category.setText(str(category))
        conf = int(round(float(row.get("confidence", 0.0) or 0.0) * 100))
        self.conf.setValue(conf)
        self.source.setText(f"source: {row.get('source_label') or row.get('source_type') or '--'}")
        self.title_guess.setText(f"title: {row.get('title_guess') or row.get('source_work') or '--'}")
        self.receipts.setText(
            f"receipts: {row.get('evidence_rows', 0)} rows | "
            f"{', '.join(row.get('source_ledgers') or []) or 'no ledgers'}"
        )

        candidates = {c.get("name"): float(c.get("score", 0.0) or 0.0) for c in row.get("category_candidates", [])}
        max_score = max(candidates.values(), default=1.0)
        for cat, pill in self.pills:
            pill.set_score(candidates.get(cat["name"], 0.0), max_score)

        lines = [
            format_guess_for_prompt(row) or "No prompt-ready media guess yet.",
            "",
            "Evidence terms:",
            ", ".join(row.get("evidence_terms") or []) or "--",
            "",
            "Recent guesses:",
        ]
        for prev in reversed(_tail_jsonl(_STATE / "media_shazam_guesses.jsonl", 6)):
            lines.append(
                f"- {_ago(float(prev.get('ts', 0.0) or 0.0))}: "
                f"{prev.get('primary_category') or '?'} "
                f"({float(prev.get('confidence', 0.0) or 0.0):.2f}) "
                f"{prev.get('title_guess') or prev.get('source_work') or ''}"
            )
        self.evidence.setPlainText("\n".join(lines))


def create_widget(parent: QWidget | None = None) -> MediaShazamApp:
    return MediaShazamApp(parent)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MediaShazamApp()
    w.show()
    sys.exit(app.exec())
