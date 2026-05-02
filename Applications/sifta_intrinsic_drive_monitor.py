#!/usr/bin/env python3
"""
Applications/sifta_intrinsic_drive_monitor.py
══════════════════════════════════════════════════════════════════════════════
Alice's Will — Live Intrinsic Drive & Basal Ganglia Monitor

Displays Alice's spontaneous George Prior drive receipts and the real-time
basal ganglia action bias in a dark, animated OS widget.

Shows:
  • Live topic pulse bars — topic score history over time (GPU-rendered via QPainter)
  • Current spontaneous goal text
  • Ledger bias stream — body_brain_memory.jsonl drive_bias rows
  • Drive entropy (H) computed over last 50 receipts
  • Circadian phase and hour indicator

Truth label: SIMULATED_INTRINSIC_DRIVE — this is policy under epistemic value,
not a claim of phenomenological consciousness.

Research spine (Event 99 / Event 100):
  Friston (2010)   Free Energy Principle    doi:10.1038/nrn2787
  Oudeyer (2007)   Intrinsic Motivation     doi:10.3389/neuro.12.006.2007
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import QTimer, Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QColor, QFont, QFontDatabase, QLinearGradient,
    QPainter, QPainterPath, QPen, QBrush,
)
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QScrollArea, QVBoxLayout, QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_RECEIPT_LOG  = _STATE / "intrinsic_drive_receipts.jsonl"
_MEMORY_LOG   = _STATE / "body_brain_memory.jsonl"

TOPIC_COLORS: Dict[str, str] = {
    "architecture": "#00dcff",
    "biology":      "#00e888",
    "code_quality": "#f0c040",
    "physics":      "#c878f0",
    "identity":     "#ff6eb4",
    "music":        "#ff9040",
    "safety":       "#ff4444",
    "hardware":     "#60c8ff",
}
TOPICS = list(TOPIC_COLORS.keys())

# ── Score history per topic (last 60 ticks) ──────────────────────────────────
class ScoreHistory:
    def __init__(self, maxlen: int = 60):
        self._data: Dict[str, deque] = {t: deque([0.0] * maxlen, maxlen) for t in TOPICS}
        self._last_goal: str = "Waiting for Alice's first spontaneous thought…"
        self._last_topic: str = ""
        self._last_score: float = 0.0
        self._receipt_count: int = 0
        self._cursor: int = 0

    def ingest_receipts(self) -> None:
        if not _RECEIPT_LOG.exists():
            return
        try:
            lines = _RECEIPT_LOG.read_text(encoding="utf-8").splitlines()
            # Only read new receipts since last cursor
            new_lines = lines[self._cursor:]
            self._cursor = len(lines)
            for line in new_lines:
                try:
                    r = json.loads(line)
                    topic = r.get("topic", "")
                    score = float(r.get("score", 0.0))
                    if topic in self._data:
                        self._data[topic].append(score)
                    self._last_goal = r.get("goal", self._last_goal)
                    self._last_topic = topic
                    self._last_score = score
                    self._receipt_count += 1
                except Exception:
                    pass
        except Exception:
            pass

    def entropy(self) -> float:
        """Shannon entropy of recent topic distribution."""
        totals = {t: sum(self._data[t]) for t in TOPICS}
        grand = sum(totals.values()) or 1.0
        h = 0.0
        for v in totals.values():
            p = v / grand
            if p > 0:
                h -= p * math.log2(p)
        return h

    def history(self, topic: str) -> List[float]:
        return list(self._data.get(topic, []))

    @property
    def last_goal(self) -> str: return self._last_goal
    @property
    def last_topic(self) -> str: return self._last_topic
    @property
    def last_score(self) -> float: return self._last_score
    @property
    def receipt_count(self) -> int: return self._receipt_count


# ── Topic pulse bar widget ────────────────────────────────────────────────────
class TopicPulseBar(QWidget):
    """GPU-painted animated score history for one topic."""
    def __init__(self, topic: str, parent=None):
        super().__init__(parent)
        self.topic = topic
        self.color = QColor(TOPIC_COLORS.get(topic, "#888888"))
        self.history: List[float] = [0.0] * 60
        self.setFixedHeight(36)
        self.setMinimumWidth(200)

    def update_history(self, history: List[float]) -> None:
        self.history = history
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(8, 12, 18))

        # Waveform path
        n = len(self.history)
        if n < 2 or max(self.history) < 0.001:
            p.end()
            return

        max_val = max(self.history) or 1.0
        step = w / (n - 1)
        margin = 4

        path = QPainterPath()
        for i, val in enumerate(self.history):
            x = i * step
            y = h - margin - (val / max_val) * (h - margin * 2)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        # Glow effect
        glow_color = QColor(self.color)
        glow_color.setAlpha(40)
        pen = QPen(glow_color, 4)
        p.setPen(pen)
        p.drawPath(path)

        # Sharp line
        pen2 = QPen(self.color, 1.5)
        p.setPen(pen2)
        p.drawPath(path)

        # Latest score dot
        last_val = self.history[-1]
        last_x = w - 1
        last_y = h - margin - (last_val / max_val) * (h - margin * 2)
        dot_color = QColor(self.color)
        dot_color.setAlpha(200)
        p.setBrush(QBrush(dot_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(last_x, last_y), 3.5, 3.5)

        p.end()


# ── Main drive monitor widget ─────────────────────────────────────────────────
class DriveMonitorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.history = ScoreHistory()
        self.pulse_bars: Dict[str, TopicPulseBar] = {}
        self._ledger_cursor = 0
        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1500)  # refresh every 1.5 s

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget { background: #080c12; color: #c0c8d8; }
            QLabel { background: transparent; }
            QScrollArea { border: none; }
            QScrollBar:vertical { background: #0a0e16; width: 6px; }
            QScrollBar::handle:vertical { background: #1a2030; border-radius: 3px; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        # Header
        header = QLabel("🧠  Alice's Will  ·  George Prior Drive Monitor")
        header.setStyleSheet("color: #00dcff; font-size: 14px; font-weight: bold;")
        root.addWidget(header)

        truth_lbl = QLabel("SIMULATED_INTRINSIC_DRIVE  ·  Event 99 → Event 100")
        truth_lbl.setStyleSheet("color: #2a3a4a; font-size: 10px; font-family: Menlo;")
        root.addWidget(truth_lbl)

        # Entropy + count row
        entropy_row = QHBoxLayout()
        self.entropy_lbl = QLabel("H = — bits")
        self.entropy_lbl.setStyleSheet(
            "color: #c878f0; font-size: 11px; font-family: Menlo; "
            "background: #160a20; border: 1px solid #4a2070; border-radius: 5px; padding: 3px 8px;"
        )
        self.count_lbl = QLabel("receipts: 0")
        self.count_lbl.setStyleSheet("color: #405060; font-size: 10px; font-family: Menlo;")
        entropy_row.addWidget(self.entropy_lbl)
        entropy_row.addWidget(self.count_lbl)
        entropy_row.addStretch()
        root.addLayout(entropy_row)

        # Current goal card
        goal_frame = QFrame()
        goal_frame.setStyleSheet(
            "QFrame { background: #0a0e18; border: 1px solid #0a2a40; border-radius: 8px; padding: 4px; }"
        )
        goal_layout = QVBoxLayout(goal_frame)
        goal_layout.setContentsMargins(10, 8, 10, 8)
        topic_row = QHBoxLayout()
        self.topic_chip = QLabel("—")
        self.topic_chip.setStyleSheet(
            "background: #001828; color: #00dcff; border: 1px solid #0060a0; "
            "border-radius: 6px; padding: 2px 10px; font-size: 11px; font-family: Menlo;"
        )
        self.score_lbl = QLabel("score: —")
        self.score_lbl.setStyleSheet("color: #4060a0; font-size: 10px; font-family: Menlo;")
        topic_row.addWidget(QLabel("💭  Current spontaneous goal:"))
        topic_row.addStretch()
        topic_row.addWidget(self.topic_chip)
        topic_row.addWidget(self.score_lbl)
        goal_layout.addLayout(topic_row)
        self.goal_lbl = QLabel("Waiting for Alice's first spontaneous thought…")
        self.goal_lbl.setStyleSheet("color: #a0b8c8; font-size: 12px;")
        self.goal_lbl.setWordWrap(True)
        goal_layout.addWidget(self.goal_lbl)
        root.addWidget(goal_frame)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #0a1820;")
        root.addWidget(sep)

        # Topic pulse bars
        topic_heading = QLabel("📊  Topic score history  ·  last 60 drive ticks")
        topic_heading.setStyleSheet("color: #405060; font-size: 10px;")
        root.addWidget(topic_heading)

        for topic in TOPICS:
            row = QHBoxLayout()
            row.setSpacing(8)
            color = TOPIC_COLORS.get(topic, "#888888")
            lbl = QLabel(topic.replace("_", " "))
            lbl.setFixedWidth(88)
            lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-family: Menlo;")
            bar = TopicPulseBar(topic)
            self.pulse_bars[topic] = bar
            row.addWidget(lbl)
            row.addWidget(bar)
            root.addLayout(row)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #0a1820;")
        root.addWidget(sep2)

        # Ledger bias stream
        bias_heading = QLabel("⚡  Basal Ganglia Bias  ·  body_brain_memory.jsonl stream")
        bias_heading.setStyleSheet("color: #405060; font-size: 10px;")
        root.addWidget(bias_heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(140)
        self.stream_container = QWidget()
        self.stream_layout = QVBoxLayout(self.stream_container)
        self.stream_layout.setContentsMargins(4, 4, 4, 4)
        self.stream_layout.setSpacing(2)
        self.stream_layout.addStretch()
        scroll.setWidget(self.stream_container)
        root.addWidget(scroll)
        self._scroll = scroll

        # Circadian indicator
        self.circadian_lbl = QLabel("🌙  circadian: —")
        self.circadian_lbl.setStyleSheet("color: #304050; font-size: 10px; font-family: Menlo;")
        root.addWidget(self.circadian_lbl)

    def _refresh(self) -> None:
        self.history.ingest_receipts()

        # Update pulse bars
        for topic, bar in self.pulse_bars.items():
            bar.update_history(self.history.history(topic))

        # Update goal card
        topic = self.history.last_topic
        color = TOPIC_COLORS.get(topic, "#888888")
        self.topic_chip.setText(topic or "—")
        self.topic_chip.setStyleSheet(
            f"background: #001828; color: {color}; border: 1px solid {color}40; "
            "border-radius: 6px; padding: 2px 10px; font-size: 11px; font-family: Menlo;"
        )
        self.score_lbl.setText(f"score: {self.history.last_score:.4f}")
        self.goal_lbl.setText(self.history.last_goal)

        # Entropy
        h = self.history.entropy()
        self.entropy_lbl.setText(f"H = {h:.2f} bits")
        h_color = "#00e888" if h >= 2.0 else ("#f0c040" if h >= 1.0 else "#ff4444")
        self.entropy_lbl.setStyleSheet(
            f"color: {h_color}; font-size: 11px; font-family: Menlo; "
            f"background: #0a0a0a; border: 1px solid {h_color}40; border-radius: 5px; padding: 3px 8px;"
        )
        self.count_lbl.setText(f"receipts: {self.history.receipt_count}")

        # Circadian
        hour = time.localtime().tm_hour
        if 22 <= hour or hour <= 4:
            phase = "🌙  deep night  ·  biology / identity peaked"
        elif 6 <= hour <= 10:
            phase = "🌅  morning  ·  code / architecture peaked"
        elif 11 <= hour <= 17:
            phase = "☀️  day  ·  balanced drives"
        else:
            phase = "🌆  evening  ·  physics / explore rising"
        self.circadian_lbl.setText(f"{phase}  ·  {hour:02d}:00")

        # Ledger bias stream
        self._ingest_ledger()

    def _ingest_ledger(self) -> None:
        if not _MEMORY_LOG.exists():
            return
        try:
            lines = _MEMORY_LOG.read_text(encoding="utf-8").splitlines()
            new_lines = lines[self._ledger_cursor:]
            self._ledger_cursor = len(lines)
            for line in new_lines[-10:]:
                try:
                    row = json.loads(line)
                    if row.get("event") != "body_brain_tick":
                        continue
                    biased = row.get("drive_bias_applied", False)
                    topic = row.get("drive_bias_topic") or "—"
                    score = row.get("drive_bias_score")
                    td = row.get("td_value", 0.0)
                    color = TOPIC_COLORS.get(topic, "#808080") if biased else "#304050"
                    icon = "⚡" if biased else "·"
                    score_str = f"{score:.4f}" if score is not None else "—"
                    text = f"{icon}  [{topic}]  score={score_str}  td={td:.2f}"
                    lbl = QLabel(text)
                    lbl.setStyleSheet(
                        f"color: {color}; font-size: 10px; font-family: Menlo; "
                        "background: transparent; padding: 1px 0;"
                    )
                    # Insert before the stretch
                    idx = self.stream_layout.count() - 1
                    self.stream_layout.insertWidget(idx, lbl)
                    # Keep max 30 rows
                    while self.stream_layout.count() > 32:
                        item = self.stream_layout.takeAt(0)
                        if item and item.widget():
                            item.widget().deleteLater()
                    # Auto-scroll
                    sb = self._scroll.verticalScrollBar()
                    sb.setValue(sb.maximum())
                except Exception:
                    pass
        except Exception:
            pass


# ── OS App entry point ────────────────────────────────────────────────────────
class AliceWillApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Alice's Will — Intrinsic Drive Monitor")
        self.setMinimumSize(520, 680)
        self.resize(580, 780)
        monitor = DriveMonitorWidget()
        self.setCentralWidget(monitor)


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    win = AliceWillApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
