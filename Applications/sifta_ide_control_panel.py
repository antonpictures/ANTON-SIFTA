#!/usr/bin/env python3
"""
Applications/sifta_ide_control_panel.py

GUI lane for the sealed Somatosensory Homunculus.

This panel does not compute repo proprioception itself. It consumes the live
System.swarm_somatosensory_homunculus.read_homeostasis() entry point sealed by
C47H and renders the state as an operator surface for Alice, AG31, C47H, Codex,
and the Architect.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_somatosensory_homunculus import read_homeostasis  # noqa: E402


class IdeControlPanelWidget(QWidget):
    """Activity Monitor style panel for repo/IDE proprioception."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SIFTA IDE Control Panel")
        self.resize(1040, 700)
        self.setStyleSheet(_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title = QLabel("SIFTA IDE CONTROL PANEL")
        self.title.setFont(QFont("Menlo", 18, QFont.Weight.Bold))
        self.subtitle = QLabel("Repo proprioception from the sealed Somatosensory Homunculus")
        self.subtitle.setObjectName("dim")
        title_box.addWidget(self.title)
        title_box.addWidget(self.subtitle)
        header.addLayout(title_box)
        header.addStretch(1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)
        root.addLayout(header)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(12)
        self.dirty_card = self._metric_card("Dirty Files", "0")
        self.energy_card = self._metric_card("Free Energy", "0.00")
        self.active_card = self._metric_card("Active IDEs", "0")
        self.blocked_card = self._metric_card("Blocked IDEs", "0")
        metrics.addWidget(self.dirty_card["frame"], 0, 0)
        metrics.addWidget(self.energy_card["frame"], 0, 1)
        metrics.addWidget(self.active_card["frame"], 0, 2)
        metrics.addWidget(self.blocked_card["frame"], 0, 3)
        root.addLayout(metrics)

        self.energy_bar = QProgressBar()
        self.energy_bar.setRange(0, 100)
        self.energy_bar.setTextVisible(True)
        root.addWidget(self.energy_bar)

        self.directive = QTextEdit()
        self.directive.setReadOnly(True)
        self.directive.setFixedHeight(84)
        self.directive.setObjectName("directive")
        root.addWidget(self.directive)

        tables = QHBoxLayout()

        marker_box = QVBoxLayout()
        marker_label = QLabel("Recent STIGTIME Markers")
        marker_label.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        marker_box.addWidget(marker_label)
        self.markers = QTableWidget(0, 4)
        self.markers.setHorizontalHeaderLabels(["Agent", "State", "Context", "Time"])
        self.markers.verticalHeader().setVisible(False)
        self.markers.setAlternatingRowColors(True)
        marker_box.addWidget(self.markers)
        tables.addLayout(marker_box, 2)

        dirty_box = QVBoxLayout()
        dirty_label = QLabel("Repo Surface")
        dirty_label.setFont(QFont("Menlo", 12, QFont.Weight.Bold))
        dirty_box.addWidget(dirty_label)
        self.dirty_files = QTextEdit()
        self.dirty_files.setReadOnly(True)
        dirty_box.addWidget(self.dirty_files)
        tables.addLayout(dirty_box, 3)

        root.addLayout(tables, 1)

        footer = QHBoxLayout()
        self.version = QLabel("Source: System.swarm_somatosensory_homunculus.read_homeostasis()")
        self.version.setObjectName("dim")
        footer.addWidget(self.version)
        footer.addStretch(1)
        self.stigtime = QLabel("STIGTIME: standby")
        self.stigtime.setObjectName("pill")
        footer.addWidget(self.stigtime)
        root.addLayout(footer)

        # AG31 Action Bar Expansion
        action_bar = QHBoxLayout()
        action_bar.setSpacing(12)
        self.btn_wellbeing = QPushButton("👁️ Launch Wellbeing Cortex")
        self.btn_wellbeing.setObjectName("action")
        self.btn_wellbeing.setToolTip("Open Alice's operational feelings panel")
        self.btn_wellbeing.clicked.connect(self._launch_wellbeing)
        
        self.btn_scrub = QPushButton("🧹 Run Distro Scrubber")
        self.btn_scrub.setObjectName("action_danger")
        self.btn_scrub.setToolTip("Compile sanitized public snapshot to .distro_build/")
        self.btn_scrub.clicked.connect(self._launch_scrubber)
        
        action_bar.addWidget(self.btn_wellbeing)
        action_bar.addWidget(self.btn_scrub)
        root.addLayout(action_bar)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)
        self.refresh()

    def _launch_wellbeing(self) -> None:
        subprocess.Popen([sys.executable, str(_REPO / "Applications" / "sifta_alice_wellbeing_panel.py")])

    def _launch_scrubber(self) -> None:
        subprocess.Popen([sys.executable, str(_REPO / "Scripts" / "distro_scrubber.py"), "--output", str(_REPO / ".distro_build")])

    def _metric_card(self, title: str, value: str) -> dict:
        frame = QFrame()
        frame.setObjectName("metric")
        layout = QVBoxLayout(frame)
        label = QLabel(title)
        label.setObjectName("dim")
        number = QLabel(value)
        number.setFont(QFont("Menlo", 24, QFont.Weight.Bold))
        layout.addWidget(label)
        layout.addWidget(number)
        return {"frame": frame, "number": number}

    def refresh(self) -> None:
        try:
            reading = read_homeostasis()
            data = reading.to_json()
            self._render_reading(data)
            self._render_dirty_files(_git_status_lines())
        except Exception as exc:
            self.directive.setPlainText(f"Panel read failed: {type(exc).__name__}: {exc}")
            self.energy_bar.setValue(0)

    def _render_reading(self, data: dict) -> None:
        dirty = int(data.get("git_dirty_count") or 0)
        energy = float(data.get("free_energy") or 0.0)
        active = int(data.get("active_agents") or 0)
        blocked = int(data.get("blocked_agents") or 0)

        self.dirty_card["number"].setText(str(dirty))
        self.energy_card["number"].setText(f"{energy:.2f}")
        self.active_card["number"].setText(str(active))
        self.blocked_card["number"].setText(str(blocked))

        severity = min(100, int(energy if energy <= 100 else 100))
        self.energy_bar.setValue(severity)
        if blocked:
            self.energy_bar.setFormat("blocked intervention needed")
            self.energy_bar.setProperty("tone", "blocked")
        elif energy > 10:
            self.energy_bar.setFormat("high surprise")
            self.energy_bar.setProperty("tone", "hot")
        elif energy > 0:
            self.energy_bar.setFormat("managed metabolism")
            self.energy_bar.setProperty("tone", "warm")
        else:
            self.energy_bar.setFormat("homeostasis")
            self.energy_bar.setProperty("tone", "calm")
        self.energy_bar.style().unpolish(self.energy_bar)
        self.energy_bar.style().polish(self.energy_bar)

        directive = data.get("directive") or "No directive."
        self.directive.setPlainText(json.dumps({
            "directive": directive,
            "git_dirty_count": dirty,
            "free_energy": round(energy, 4),
            "active_agents": active,
            "blocked_agents": blocked,
        }, indent=2))

        markers = data.get("markers") or []
        self.markers.setRowCount(len(markers))
        for row, marker in enumerate(markers):
            self._set_cell(row, 0, marker.get("agent"))
            self._set_cell(row, 1, marker.get("state"))
            self._set_cell(row, 2, marker.get("context") or "")
            self._set_cell(row, 3, marker.get("iso_ts"))
        self.markers.resizeColumnsToContents()

        self.stigtime.setText(_panel_state(active, blocked, energy))

    def _render_dirty_files(self, lines: Iterable[str]) -> None:
        rows = list(lines)
        if not rows:
            self.dirty_files.setPlainText("Clean working tree.")
            return
        shown = rows[:80]
        suffix = "" if len(rows) <= len(shown) else f"\n... {len(rows) - len(shown)} more"
        self.dirty_files.setPlainText("\n".join(shown) + suffix)

    def _set_cell(self, row: int, col: int, value: object) -> None:
        item = QTableWidgetItem("" if value is None else str(value))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if col == 1:
            state = item.text().lower()
            if state == "active":
                item.setForeground(QColor("#8fda9b"))
            elif state == "blocked":
                item.setForeground(QColor("#ff6b7a"))
            elif state == "verify-only":
                item.setForeground(QColor("#ffd166"))
        self.markers.setItem(row, col, item)


def _panel_state(active: int, blocked: int, energy: float) -> str:
    if blocked:
        return "STIGTIME: blocked(needs-architect)"
    if active:
        return "STIGTIME: active(orchestrating-ide-lane)"
    if energy > 10:
        return "STIGTIME: active(scrub-and-commit-needed)"
    return "STIGTIME: standby"


def _git_status_lines() -> List[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(_REPO),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ["git status unavailable"]
    if result.returncode != 0:
        return ["git status unavailable"]
    return [line for line in result.stdout.splitlines() if line.strip()]


_STYLE = """
QWidget {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0b0f19, stop:1 #131a28);
    color: #e2e8f0;
    font-family: 'Inter', 'Menlo', sans-serif;
}
QLabel#dim {
    color: #94a3b8;
}
QLabel {
    font-weight: 500;
}
QLabel#pill {
    color: #0b0f19;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #34d399);
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 800;
}
QFrame#metric {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
}
QFrame#metric:hover {
    background: rgba(30, 41, 59, 0.9);
    border: 1px solid rgba(56, 189, 248, 0.5);
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 700;
    font-size: 13px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #60a5fa, stop:1 #3b82f6);
    border: 1px solid rgba(255, 255, 255, 0.3);
}
QPushButton:pressed {
    background: #1d4ed8;
}
QPushButton#action {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #6d28d9);
}
QPushButton#action_danger {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #b91c1c);
}
QPushButton#action_danger:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f87171, stop:1 #ef4444);
}
QProgressBar {
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    height: 22px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}
QProgressBar::chunk {
    border-radius: 7px;
    background: #94a3b8;
}
QProgressBar[tone="calm"]::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #34d399);
}
QProgressBar[tone="warm"]::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #fbbf24);
}
QProgressBar[tone="hot"]::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #f87171);
}
QProgressBar[tone="blocked"]::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #be123c, stop:1 #e11d48);
}
QTextEdit, QTableWidget {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    color: #cbd5e1;
    selection-background-color: #38bdf8;
    padding: 6px;
}
QTextEdit#directive {
    background: rgba(2, 6, 23, 0.8);
    color: #38bdf8;
}
QHeaderView::section {
    background: rgba(30, 41, 59, 0.9);
    color: #e2e8f0;
    border: none;
    border-bottom: 2px solid rgba(255, 255, 255, 0.1);
    padding: 8px;
    font-weight: bold;
}
QTableWidget::item {
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    padding: 4px;
}
"""


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = IdeControlPanelWidget()
    widget.show()
    sys.exit(app.exec())
