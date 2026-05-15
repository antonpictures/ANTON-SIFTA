#!/usr/bin/env python3
"""
SIFTA Tournament Briefing
========================

Visible OS surface for external benchmark maps: IBM agents, Agent Skills,
NVIDIA contrast, Chamath/JRE narrative, and Codex harness lessons.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtWidgets import QLabel, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout, QWidget

from System.sifta_base_widget import SiftaBaseWidget


DOCS: tuple[tuple[str, str], ...] = (
    ("Territory Map", "Documents/SIFTA_TERRITORY_BENCHMARK_MAP.md"),
    ("IBM Agents", "Documents/IBM_AGENTS_HUB_MAPPING.md"),
    ("Chamath Pack", "Documents/CHAMATH_NARRATIVE_PACK_V1.md"),
    ("NVIDIA Contrast", "Documents/NVIDIA_DIFFERENTIATOR_NOTES.md"),
)


class TournamentBriefingWidget(SiftaBaseWidget):
    APP_NAME = "SIFTA Tournament Briefing"

    def build_ui(self, layout: QVBoxLayout) -> None:
        header = QLabel("SIFTA Tournament Briefing - external narratives mapped to code territory")
        header.setStyleSheet("color: rgb(0,255,200); font-size: 13px; font-weight: bold;")
        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.viewers: dict[str, QTextBrowser] = {}
        for title, _path in DOCS:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            viewer = QTextBrowser()
            viewer.setOpenExternalLinks(True)
            viewer.setStyleSheet(
                "QTextBrowser { background: rgb(10,8,16); color: rgb(220,225,245); "
                "border: 1px solid rgb(45,42,65); font-size: 11px; padding: 8px; }"
            )
            page_layout.addWidget(viewer, 1)
            self.viewers[title] = viewer
            self.tabs.addTab(page, title)
        layout.addWidget(self.tabs, 1)

        refresh = QPushButton("Refresh briefing docs")
        refresh.clicked.connect(self.refresh_docs)
        layout.addWidget(refresh)

        self.refresh_docs()

    def refresh_docs(self) -> None:
        for title, rel in DOCS:
            path = _REPO / rel
            viewer = self.viewers[title]
            if not path.exists():
                viewer.setPlainText(f"Missing briefing document: {rel}")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            viewer.setMarkdown(text)


if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    win = TournamentBriefingWidget()
    win.resize(1180, 760)
    win.show()
    sys.exit(app.exec())
