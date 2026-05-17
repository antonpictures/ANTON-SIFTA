#!/usr/bin/env python3
"""SIFTA Home — consumer surface over the existing organism.

This stays inside the Qt/Python desktop body.  It does not launch a browser
or create a second chat; it renders the headless consumer-surface snapshot
from :mod:`System.swarm_consumer_surface` and gives the operator a compact
dropdown navigator instead of another row of cramped tabs.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from System.swarm_consumer_surface import (  # noqa: E402
    PAGE_DISCOVERY,
    PAGE_OVERVIEW,
    PAGE_TITLES,
    render_page,
    write_surface_receipt,
)


_QSS = """
QWidget#SiftaHomeRoot {
    background: #0b0f14;
    color: #edf2f7;
}
QLabel#Title {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 750;
}
QLabel#Subtitle, QLabel#Status {
    color: #94a3b8;
    font-size: 12px;
}
QComboBox#PagePicker {
    min-height: 34px;
    padding: 4px 10px;
    border: 1px solid #334155;
    border-radius: 6px;
    background: #111827;
    color: #f8fafc;
    font-size: 13px;
}
QPushButton#SmallAction {
    min-height: 32px;
    min-width: 88px;
    padding: 4px 10px;
    border: 1px solid #334155;
    border-radius: 6px;
    background: #172033;
    color: #e2e8f0;
    font-size: 12px;
    font-weight: 650;
}
QPushButton#SmallAction:hover {
    border-color: #38bdf8;
    background: #1e293b;
}
QTextBrowser#PageBody {
    background: #0f172a;
    color: #e5edf5;
    border: 1px solid #233044;
    border-radius: 8px;
    padding: 16px;
    font-family: Menlo;
    font-size: 12px;
    line-height: 1.45;
}
"""


class SiftaHomeWidget(QWidget):
    """One-window consumer home for the deep SIFTA field."""

    _live_instance: "Optional[SiftaHomeWidget]" = None
    _initialized_instance_ids: set[int] = set()

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                try:
                    existing.show()
                    existing.raise_()
                    existing.activateWindow()
                except Exception:
                    pass
                return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__(parent)
        self.setObjectName("SiftaHomeRoot")
        self.setWindowTitle("SIFTA Home")
        self.resize(980, 700)
        self.setStyleSheet(_QSS)

        title = QLabel("SIFTA Home")
        title.setObjectName("Title")
        title.setFont(QFont("SF Pro Display", 22, QFont.Weight.DemiBold))

        subtitle = QLabel("Consumer surface: first boot, organs, skills, Talk tools, public distro.")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)

        header = QVBoxLayout()
        header.setSpacing(2)
        header.addWidget(title)
        header.addWidget(subtitle)

        self._page_picker = QComboBox()
        self._page_picker.setObjectName("PagePicker")
        self._page_keys: list[str] = list(PAGE_TITLES.keys())
        for key in self._page_keys:
            self._page_picker.addItem(PAGE_TITLES[key], key)
        self._page_picker.setCurrentIndex(self._page_keys.index(PAGE_OVERVIEW))
        self._page_picker.currentIndexChanged.connect(self._refresh)
        self._page_picker.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setObjectName("SmallAction")
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setToolTip("Copy a Talk tool call for the current page.")
        self._copy_btn.clicked.connect(self._copy_talk_call)

        self._scan_btn = QPushButton("Scan Field")
        self._scan_btn.setObjectName("SmallAction")
        self._scan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._scan_btn.setToolTip("Scan recent local traces and write skill/OOBE proposals.")
        self._scan_btn.clicked.connect(self._scan_field)

        self._receipt_btn = QPushButton("Receipt")
        self._receipt_btn.setObjectName("SmallAction")
        self._receipt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._receipt_btn.setToolTip("Write a consumer surface receipt for the current page.")
        self._receipt_btn.clicked.connect(self._write_receipt)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("SmallAction")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setToolTip("Re-read the live manifest, skills, tools, and distro markers.")
        self._refresh_btn.clicked.connect(self._refresh)

        nav = QHBoxLayout()
        nav.setSpacing(8)
        nav.addWidget(self._page_picker, 1)
        nav.addWidget(self._scan_btn)
        nav.addWidget(self._copy_btn)
        nav.addWidget(self._receipt_btn)
        nav.addWidget(self._refresh_btn)

        self._body = QTextBrowser()
        self._body.setObjectName("PageBody")
        self._body.setOpenExternalLinks(False)
        self._body.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)

        self._status = QLabel("Ready")
        self._status.setObjectName("Status")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        root.addLayout(header)
        root.addLayout(nav)
        root.addWidget(self._body, 1)
        root.addWidget(self._status)

        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))
        QTimer.singleShot(20, self._refresh)

    def _current_page(self) -> str:
        key = self._page_picker.currentData()
        return str(key or PAGE_OVERVIEW)

    def _refresh(self) -> None:
        page = self._current_page()
        try:
            text = render_page(page)
            self._body.setHtml(self._markdownish_to_html(text))
            self._status.setText(f"Rendered {PAGE_TITLES.get(page, page)} from live local files.")
        except Exception as exc:
            self._body.setPlainText(f"Surface read failed: {type(exc).__name__}: {exc}")
            self._status.setText("Read failed")

    def _write_receipt(self) -> None:
        page = self._current_page()
        receipt = write_surface_receipt(
            action="ui_page_receipt",
            page=page,
            payload={"page_title": PAGE_TITLES.get(page, page)},
        )
        self._status.setText(f"Receipt {receipt['trace_id'][:16]} hash {receipt['hash'][:16]}")

    def _scan_field(self) -> None:
        try:
            from System.swarm_skill_autoproposal import scan_field_for_skill_needs

            result = scan_field_for_skill_needs(allow_pull=False, min_repeat=3)
            if PAGE_DISCOVERY in self._page_keys:
                self._page_picker.setCurrentIndex(self._page_keys.index(PAGE_DISCOVERY))
            self._refresh()
            self._status.setText(
                f"Field scan: {result.get('proposal_count', 0)} proposals, "
                f"{result.get('action_count', 0)} actions; receipt {str(result.get('receipt_id', ''))[:16]}"
            )
        except Exception as exc:
            self._status.setText(f"Field scan failed: {type(exc).__name__}: {exc}")

    def _copy_talk_call(self) -> None:
        page = self._current_page()
        call = (
            "[TOOL_CALL: consumer_surface_status | "
            f"page={page} | "
            "cost_justification=George asked for a consumer surface status receipt]"
        )
        QApplication.clipboard().setText(call)
        receipt = write_surface_receipt(
            action="ui_copied_talk_call",
            page=page,
            payload={"tool": "consumer_surface_status", "chars": len(call)},
        )
        self._status.setText(f"Copied Talk call; receipt {receipt['trace_id'][:16]}")

    @staticmethod
    def _markdownish_to_html(text: str) -> str:
        out: list[str] = []
        for raw in text.splitlines():
            line = html.escape(raw)
            if raw.startswith("# "):
                out.append(f"<h2>{html.escape(raw[2:])}</h2>")
            elif raw.startswith("- "):
                out.append(f"<div style='margin:4px 0 4px 12px;'>- {html.escape(raw[2:])}</div>")
            elif raw.startswith("   "):
                out.append(f"<div style='margin-left:28px;color:#b6c2d1;'>{html.escape(raw.strip())}</div>")
            elif not raw.strip():
                out.append("<div style='height:8px;'></div>")
            else:
                out.append(f"<div>{line}</div>")
        return "<body style='font-family:Menlo;color:#e5edf5;'>" + "\n".join(out) + "</body>"

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        try:
            if type(self)._live_instance is self:
                type(self)._live_instance = None
            type(self)._initialized_instance_ids.discard(id(self))
        except Exception:
            pass
        super().closeEvent(event)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = SiftaHomeWidget()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
