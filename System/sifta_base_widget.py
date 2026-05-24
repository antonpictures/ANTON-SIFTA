#!/usr/bin/env python3
"""
sifta_base_widget.py — Universal Base Widget for all iSwarm OS Applications
═══════════════════════════════════════════════════════════════════════════════
Every app inherits from SiftaBaseWidget. You write the window chrome ONCE:
  • SIFTA dark palette (automatic)
  • Help button (?) → contextual help from APP_HELP.md
  • Status bar with STGM telemetry
  • Consistent font, colors, controls
  • Clean timer/process shutdown on close

New apps:
    class MyApp(SiftaBaseWidget):
        APP_NAME = "My Cool App"
        def build_ui(self, layout: QVBoxLayout) -> None:
            layout.addWidget(QLabel("hello swarm"))
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QVBoxLayout, QWidget, QFrame, QSplitter,
)
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

# ── Global SIFTA Palette (reusable constants) ────────────────────

SIFTA_STYLESHEET = """
QWidget {
    background: rgb(8, 10, 18);
    color: rgb(200, 210, 240);
    font-family: 'Menlo', 'Courier New', monospace;
}
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgb(50,42,65), stop:1 rgb(30,25,42));
    border: 1px solid rgb(80,70,100);
    border-radius: 6px; padding: 6px 14px;
    color: rgb(200,210,240);
    font-size: 11px; font-weight: bold;
}
QPushButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgb(70,60,90), stop:1 rgb(45,38,62));
    border-color: rgb(0,255,200);
}
QPushButton:pressed { background: rgb(40,35,55); }
QPushButton#btnHelp {
    background: rgb(30,25,42);
    border: 1px solid rgb(80,70,100);
    padding: 4px 10px; font-size: 13px; font-weight: bold;
    color: rgb(0,255,200); min-width: 28px; max-width: 28px;
}
QSlider::groove:horizontal { height: 4px; background: rgb(40,35,55); border-radius: 2px; }
QSlider::handle:horizontal {
    background: rgb(0,255,200); width: 12px; height: 12px;
    margin: -4px 0; border-radius: 6px;
}
QTextEdit, QPlainTextEdit {
    background: rgb(10,8,16); border: 1px solid rgb(40,35,55);
    border-radius: 4px; font-size: 9px; color: rgb(0,255,200); padding: 4px;
}
QTableWidget {
    background: rgb(12,10,20); border: 1px solid rgb(40,35,55);
    font-size: 9px; color: rgb(200,210,240); gridline-color: rgb(35,32,50);
}
QHeaderView::section {
    background: rgb(25,22,38); color: rgb(0,255,200);
    border: 1px solid rgb(40,35,55); font-size: 9px;
    font-weight: bold; padding: 4px;
}
QTabWidget::pane { border: 1px solid rgb(45,42,65); background: rgb(12,10,20); }
QTabBar::tab {
    background: rgb(25,22,38); color: rgb(150,155,180);
    border: 1px solid rgb(45,42,65); padding: 6px 16px; font-size: 10px;
}
QTabBar::tab:selected {
    background: rgb(40,35,55); color: rgb(0,255,200);
    border-bottom-color: rgb(0,255,200);
}
QLineEdit, QComboBox {
    background: rgb(18,16,28); border: 1px solid rgb(55,50,75);
    border-radius: 4px; padding: 6px 10px; color: rgb(200,210,240);
    font-size: 11px; selection-background-color: rgb(0,120,80);
}
QLineEdit:focus, QComboBox:focus { border-color: rgb(0,255,200); }
QCheckBox { spacing: 6px; font-size: 11px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QScrollBar:vertical {
    background: rgb(12,10,20); width: 8px; border: none;
}
QScrollBar::handle:vertical {
    background: rgb(60,55,80); min-height: 30px; border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


# MDI chrome (`sifta_os_desktop._make_sub`) prepends glyphs like "⚙ " to the
# manifest title for the window label; Help passes that full string here.
# APP_HELP.md headings use the bare `apps_manifest.json` key — strip the same
# prefix set used when journaling app closes (witness strip). Include U+FE0F
# so "⚙️" (gear + VS16) normalizes like plain "⚙".
_MDI_HELP_TITLE_PREFIX_CHARS = "⚙🐜🚀💬👁🌐🧠🛡🗳📊🗺⚡ \t\ufe0f"


def help_manifest_key_from_mdi_title(title: str) -> str:
    """Map an MDI title label (may include leading tool glyphs) to manifest / APP_HELP key."""
    return (title or "").strip().lstrip(_MDI_HELP_TITLE_PREFIX_CHARS).strip()


def _load_help_text(app_name: str) -> str:
    """Load help text for a specific app from APP_HELP.md."""
    help_file = _REPO / "Documents" / "APP_HELP.md"
    if not help_file.exists():
        return f"No help file found for {app_name}.\nExpected: Documents/APP_HELP.md"

    text = help_file.read_text(encoding="utf-8", errors="replace")
    stripped = help_manifest_key_from_mdi_title(app_name)
    headings: list[str] = []
    seen: set[str] = set()

    def _push(h: str) -> None:
        n = (h or "").strip()
        if n and n not in seen:
            seen.add(n)
            headings.append(n)

    _push(app_name)
    _push(stripped)
    if app_name.startswith("SIFTA "):
        _push(app_name[6:].strip())
    idx = -1
    for h in headings:
        marker = f"### {h}"
        idx = text.find(marker)
        if idx >= 0:
            break
    if idx < 0:
        needles = [h.lower() for h in headings if h]
        for line in text.split("\n"):
            if line.startswith("### "):
                ll = line.lower()
                if any(n in ll for n in needles):
                    idx = text.find(line)
                    break
    if idx < 0:
        return f"No help entry found for '{app_name}' in APP_HELP.md."

    block = text[idx:]
    next_h3 = block.find("\n### ", 4)
    next_h2 = block.find("\n## ", 4)
    ends = [e for e in [next_h3, next_h2] if e > 0]
    if ends:
        block = block[: min(ends)]
    return block.strip()


# App-local Alice chat is opt-in only. Desktop Alice is the canonical chat
# surface; apps that need collaboration should keep it in their own canvas.
_APP_LOCAL_CHAT_ALLOWLIST: set[str] = set()


class _NoOpChatDisplay:
    """Compatibility object for apps that previously wrote into `_gci.chat_display`."""

    def append(self, *_args, **_kwargs) -> None:
        return

    def toPlainText(self) -> str:
        return ""

    def setPlainText(self, *_args, **_kwargs) -> None:
        return


class _DisabledAppChatBridge(QObject):
    """
    Non-visual bridge preserving the old `_gci` API without app-local chat UI.

    A few legacy apps still emit context/status through `_gci`. Keeping this
    small bridge prevents crashes while ensuring normal apps do not spawn a
    second Alice conversation panel.
    """

    message_sent = pyqtSignal(str)
    response_received = pyqtSignal(str)

    def __init__(self, app_context: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.app_context = app_context
        self._app_context_injection = ""
        self._bus = None
        self.chat_display = _NoOpChatDisplay()

    def set_app_context(self, context: str) -> None:
        self._app_context_injection = context

    def set_model(self, _model: str) -> None:
        return

    def close(self) -> None:
        return


class SiftaBaseWidget(QWidget):
    """
    Universal base for all iSwarm OS apps.

    Subclass, set APP_NAME, override build_ui().
    Everything else (chrome, help, status, styling) is automatic.

    macOS-style context menu bar (Architect 2026-05-14 task #55):
    Subclasses MAY override `menu_schema(host)` to declare their own
    File / Edit / View / Window items. The active app's schema replaces
    SIFTA defaults when the user clicks its MDI subwindow — same way
    macOS swaps the menu bar when you bring an app forward.

    Returning None or an empty dict means "use SIFTA defaults".
    """

    APP_NAME: str = "SIFTA App"
    APP_LOCAL_CHAT_DISABLED: bool = False

    @classmethod
    def menu_schema(cls, host: "object | None" = None) -> dict | None:
        """Return {menu_name: [(label, callable) | None, ...]} or None.

        `host` is the SiftaDesktop instance (passed in by the OS) — used
        by subclass implementations that want to trigger system actions
        like opening another manifest app or closing the active window.

        Default: None → fall back to SIFTA OS defaults.
        Subclasses override this to surface app-specific items.
        """
        return None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(SIFTA_STYLESHEET)
        self._timers: List[QTimer] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # ── Title + Help row ──────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel(self.APP_NAME)
        title.setFont(QFont("Menlo", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: rgb(0,255,200); padding: 2px;")
        title_row.addWidget(title)
        title_row.addStretch()

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: rgb(100,108,140); font-size: 10px;")
        title_row.addWidget(self._status)

        btn_help = QPushButton("?")
        btn_help.setObjectName("btnHelp")
        btn_help.setToolTip(f"Help — {self.APP_NAME}")
        btn_help.clicked.connect(self._show_help)
        title_row.addWidget(btn_help)

        root.addLayout(title_row)

        # ── Content area (filled by subclass) ─────────────────────
        # We use a splitter: app content on the left, GCI chat on the right.
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setSpacing(4)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._splitter.addWidget(self._content_widget)

        # ── App-local cognitive interface ────────────────────────
        # Desktop Alice is now the canonical OS chat. Normal apps receive a
        # compatibility bridge only; app collaboration belongs in-app, not in
        # a second right-side chat panel.
        self._gci = None
        self._gci_visible = self._should_enable_app_local_chat()
        app_context = self.APP_NAME.lower().replace(" ", "_")
        if self._gci_visible:
            try:
                from System.global_cognitive_interface import GlobalCognitiveInterface
                self._gci = GlobalCognitiveInterface(
                    app_context=app_context,
                    entity_name="ALICE_M5",
                    architect_id="IOAN_M5",
                )
                self._gci.setMinimumWidth(280)
                self._gci.setMaximumWidth(420)
                self._splitter.addWidget(self._gci)
                QTimer.singleShot(0, self._balance_gci_splitter)
            except Exception:
                self._gci = _DisabledAppChatBridge(app_context, self)
                self._gci_visible = False
        else:
            self._gci = _DisabledAppChatBridge(app_context, self)

        root.addWidget(self._splitter, 1)

        # ── Toggle chat button in the title bar ───────────────────
        if self._gci_visible:
            btn_chat = QPushButton("💬")
            btn_chat.setObjectName("btnHelp")  # reuse the same compact style
            btn_chat.setToolTip("Toggle Entity Chat")
            btn_chat.clicked.connect(self._toggle_gci)
            title_row.insertWidget(title_row.count() - 1, btn_chat)  # before the ? button

        self.build_ui(self._content_layout)

    # ── Override this ─────────────────────────────────────────────

    def build_ui(self, layout: QVBoxLayout) -> None:
        """Override in subclass to build the app's UI into `layout`."""
        layout.addWidget(QLabel(f"{self.APP_NAME} — no UI defined yet."))

    # ── Convenience API ───────────────────────────────────────────

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def make_timer(self, interval_ms: int, callback) -> QTimer:
        """Create a QTimer that auto-stops on close.

        Wraps every callback in a try/except guard so an unhandled Python
        exception never propagates into PyQt6's C++ slot dispatcher.
        Without this guard, any exception escaping a timer slot reaches
        pyqt6_err_print() → QMessageLogger::fatal() → abort() → SIGABRT.
        (Confirmed by IPS crash reports Python-2026-05-02-074518/074603.)
        """
        import traceback as _tb

        def _safe_callback() -> None:
            try:
                callback()
            except Exception:
                _tb.print_exc()  # stderr only — never reaches Qt fatal handler

        t = QTimer(self)
        t.timeout.connect(_safe_callback)
        t.start(interval_ms)
        self._timers.append(t)
        return t

    def _should_enable_app_local_chat(self) -> bool:
        if self.APP_NAME == "Stigmergic Writer":
            return False
        if bool(getattr(self, "APP_LOCAL_CHAT_DISABLED", False)):
            return False
        if self.APP_NAME in _APP_LOCAL_CHAT_ALLOWLIST:
            return True
        import os

        return os.environ.get("SIFTA_ENABLE_APP_LOCAL_CHAT", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @staticmethod
    def separator() -> QFrame:
        s = QFrame()
        s.setFrameShape(QFrame.Shape.VLine)
        s.setStyleSheet("color: rgb(45,42,65);")
        return s

    def _balance_gci_splitter(self) -> None:
        """Give GCI a usable initial width (Qt often leaves the right pane at 0)."""
        if not self._gci or not self._gci_visible:
            return
        from System.splitter_utils import balance_horizontal_splitter

        balance_horizontal_splitter(
            self._splitter,
            self,
            left_ratio=0.68,
            min_right=280,
            min_left=360,
            max_right=420,
        )

    def _toggle_gci(self) -> None:
        """Show/hide the Global Cognitive Interface chat panel."""
        if not self._gci or not self._gci_visible:
            return
        sizes = self._splitter.sizes()
        if sizes[1] < 10:  # collapsed—open it
            total = sum(sizes)
            self._splitter.setSizes([total - 360, 360])
        else:  # visible—collapse it
            total = sum(sizes)
            self._splitter.setSizes([total, 0])

    # ── Help system ───────────────────────────────────────────────

    def _show_help(self) -> None:
        text = _load_help_text(self.APP_NAME)
        w = QPlainTextEdit()
        w.setReadOnly(True)
        w.setPlainText(text)
        w.setWindowTitle(f"Help — {self.APP_NAME}")
        w.setStyleSheet(
            "QPlainTextEdit { background: #0b1020; color: #c0caf5; "
            "font-family: 'Menlo'; font-size: 12px; padding: 12px; }"
        )
        w.resize(700, 500)
        w.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        w.show()
        self._help_window = w  # prevent GC

    # ── Lifecycle ─────────────────────────────────────────────────

    def _stop_child_qthreads_before_delete(self) -> None:
        """Drain parented QThreads before QWidget child destruction.

        Qt aborts the whole process if a QThread C++ object is destroyed while
        its native thread is still running. Several SIFTA apps create short
        lived worker threads as children of the widget; the latest worker is
        often tracked by an attribute, but older still-running children can be
        invisible to the app-specific closeEvent. The base widget is the last
        common membrane before QWidget teardown, so it performs a final sweep.
        """
        try:
            workers = list(self.findChildren(QThread))
        except RuntimeError:
            return
        current = QThread.currentThread()
        for worker in workers:
            if worker is None or worker is current:
                continue
            try:
                running = bool(worker.isRunning())
            except RuntimeError:
                continue
            if not running:
                continue

            # Give custom workers first chance to stop cooperatively.
            for method_name in ("halt", "stop"):
                try:
                    method = getattr(worker, method_name, None)
                except RuntimeError:
                    method = None
                if callable(method):
                    try:
                        method()
                    except Exception:
                        pass
                    try:
                        if not worker.isRunning():
                            break
                    except RuntimeError:
                        break

            try:
                if not worker.isRunning():
                    continue
            except RuntimeError:
                continue

            try:
                worker.requestInterruption()
            except RuntimeError:
                pass
            try:
                worker.quit()
            except RuntimeError:
                pass
            try:
                if worker.wait(2000):
                    continue
            except RuntimeError:
                continue

            # Last resort during app shutdown. Better an interrupted worker
            # than Qt deleting a live QThread and aborting Python.
            try:
                worker.terminate()
                worker.wait(1000)
            except RuntimeError:
                pass

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        for t in self._timers:
            t.stop()
        # Stop the GCI's background WebSocket/QThread so it doesn't SIGABRT on teardown.
        if self._gci is not None:
            try:
                self._gci.close()
            except Exception:
                pass
        self._stop_child_qthreads_before_delete()
        super().closeEvent(event)
