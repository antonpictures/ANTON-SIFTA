#!/usr/bin/env python3
"""
Applications/sifta_pdf_forge_widget.py — SIFTA PDF Forge (§7.2 deterministic render hand)

Offline flyer builder: drop images, edit copy, print to PDF. The cortex writes words;
this organ forges the page. HTML lives in Utilities/PDF_Forge/PDF_Forge.html.
"""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout

from System.sifta_base_widget import SiftaBaseWidget

_HTML = _REPO / "Utilities" / "PDF_Forge" / "PDF_Forge.html"

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    _HAS_WEBENGINE = True
except ImportError:
    _HAS_WEBENGINE = False


class PdfForgeWidget(SiftaBaseWidget):
    APP_NAME = "SIFTA PDF Forge"

    def build_ui(self, layout: QVBoxLayout) -> None:
        if not _HTML.is_file():
            layout.addWidget(QLabel(f"Missing forge HTML: {_HTML}"))
            self._status.setText("ERROR — PDF_Forge.html not on disk")
            return

        url = QUrl.fromLocalFile(str(_HTML.resolve()))

        if _HAS_WEBENGINE:
            view = QWebEngineView()
            view.load(url)
            layout.addWidget(view, 1)
            self._status.setText(
                "Deterministic render — drop images, edit copy, Forge PDF → Save as PDF"
            )
            return

        note = QLabel(
            "QtWebEngine not available in this runtime. "
            "Open the forge in your default browser (same offline HTML)."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        btn = QPushButton("Open PDF Forge in Browser")
        btn.clicked.connect(lambda: webbrowser.open(url.toString()))
        layout.addWidget(btn)
        self._status.setText("Browser fallback — double-click Open PDF Forge.command also works")


def main() -> None:
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    win = PdfForgeWidget()
    win.resize(1280, 900)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()