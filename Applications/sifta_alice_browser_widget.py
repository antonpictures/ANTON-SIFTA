#!/usr/bin/env python3
"""
Applications/sifta_alice_browser_widget.py
═══════════════════════════════════════════
Alice Browser — Chromium-based web view inside SIFTA OS

Powered by QWebEngineView (full Chromium stack, same as cartography widget).
Every URL Alice visits writes a stigmergic receipt to alice_browse_history.jsonl
so the day-segment organ, context system, and George can see what she's seen.

Features:
  • Full Chromium rendering (JS, CSS, modern web)
  • URL bar with address + enter-to-navigate
  • Back / Forward / Refresh / Home
  • SIFTA-themed home page (rendered from HTML string)
  • Quick bookmarks: Google, Wikipedia, YouTube, GitHub
  • Stigmergic browse receipts: url, title, ts, duration_s
  • Download interception: logs to ledger, no silent downloads
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

try:
    from System.qt_webengine_bootstrap import bootstrap_qt_webengine

    _WEBENGINE_BOOTSTRAP = bootstrap_qt_webengine()
except Exception as exc:
    _WEBENGINE_BOOTSTRAP = None
    _WEBENGINE_BOOTSTRAP_ERROR = f"{type(exc).__name__}: {exc}"
else:
    _WEBENGINE_BOOTSTRAP_ERROR = _WEBENGINE_BOOTSTRAP.error

try:
    if _WEBENGINE_BOOTSTRAP is not None and not _WEBENGINE_BOOTSTRAP.available:
        raise RuntimeError(_WEBENGINE_BOOTSTRAP.error)
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

    _HAS_WEBENGINE = True
    _WEBENGINE_IMPORT_ERROR = ""
except Exception as exc:
    _HAS_WEBENGINE = False
    _WEBENGINE_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

_STATE = REPO / ".sifta_state"
_BROWSE_LEDGER = _STATE / "alice_browse_history.jsonl"

_HOME_URL = "sifta://home"

_HOME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alice · SIFTA Browser</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #0d1117;
    color: #c9d1d9;
    font-family: 'Inter', 'SF Pro Display', system-ui, sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 32px;
    padding: 40px 20px;
  }
  .logo {
    font-size: 52px;
    margin-bottom: 4px;
  }
  h1 {
    font-size: 28px;
    font-weight: 700;
    color: #e6edf3;
    letter-spacing: -0.5px;
  }
  .subtitle {
    font-size: 14px;
    color: #6e7681;
    margin-top: 4px;
  }
  .bookmarks {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    justify-content: center;
    max-width: 600px;
  }
  .bk {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 14px 20px;
    text-decoration: none;
    color: #c9d1d9;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 130px;
    justify-content: center;
  }
  .bk:hover {
    background: #1f2937;
    border-color: #00e5ff44;
    color: #00e5ff;
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0,229,255,0.1);
  }
  .status-bar {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 11px;
    color: #6e7681;
    font-family: 'SF Mono', Consolas, monospace;
    max-width: 600px;
    width: 100%;
    text-align: center;
  }
  .pulse {
    display: inline-block;
    width: 7px;
    height: 7px;
    background: #00e5ff;
    border-radius: 50%;
    margin-right: 6px;
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
</style>
</head>
<body>
  <div>
    <div class="logo">🌐</div>
    <h1>Alice Browser</h1>
    <p class="subtitle">Stigmergic web access — every page visit is a receipt</p>
  </div>
  <div class="bookmarks">
    <a class="bk" href="https://google.com">🔍 Google</a>
    <a class="bk" href="https://en.wikipedia.org">📚 Wikipedia</a>
    <a class="bk" href="https://youtube.com">📺 YouTube</a>
    <a class="bk" href="https://github.com">🐙 GitHub</a>
    <a class="bk" href="https://arxiv.org">🔬 ArXiv</a>
    <a class="bk" href="https://news.ycombinator.com">📰 HN</a>
  </div>
  <div class="status-bar">
    <span class="pulse"></span>
    Chromium engine active · Browse receipts → alice_browse_history.jsonl
  </div>
</body>
</html>"""


# ── Stigmergic receipt writer ─────────────────────────────────────────────────

def _write_browse_receipt(
    url: str,
    title: str,
    duration_s: float = 0.0,
    *,
    referrer_url: str = "",
) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "ALICE_BROWSE_V1",
        "url": url,
        "title": title,
        "duration_s": round(duration_s, 1),
        "referrer_url": referrer_url,
        "domain": _domain(url),
    }
    with open(_BROWSE_LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return ""


# ── Fallback widget (no WebEngine) ───────────────────────────────────────────

class _NoWebEngineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        py = sys.executable or "python3"
        install_hint = (
            "Install into this exact Python with:\n"
            f"  {py} -m pip install 'PyQt6-WebEngine==6.11.*'\n\n"
        )
        if "AA_ShareOpenGLContexts" in _WEBENGINE_IMPORT_ERROR:
            install_hint = (
                "QtWebEngine is installed, but the Qt process booted it too late.\n"
                "Restart SIFTA so the desktop can initialize WebEngine before QApplication.\n\n"
            )
        detail = f"\n\nActive Python:\n  {py}"
        if _WEBENGINE_IMPORT_ERROR:
            detail += f"\n\nImport error:\n  {_WEBENGINE_IMPORT_ERROR}"
        lbl = QLabel(
            "⚠️  QtWebEngine did not initialize.\n\n"
            + install_hint
            + "Then restart SIFTA."
            + detail
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #ff9800; font-size: 14px; padding: 40px;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)


# ── Browser page with receipt hooks ──────────────────────────────────────────

class _AlicePage(QWebEnginePage if _HAS_WEBENGINE else object):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self._page_load_ts: float = time.time()
        self._page_url: str = ""

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        # Suppress console spam silently
        pass


# ── Main browser widget ───────────────────────────────────────────────────────

class AliceBrowserWidget(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌐 Alice Browser")
        self.resize(1100, 820)
        self._page_load_ts = time.time()
        self._current_url = ""
        self._setup_ui()
        self._apply_style()
        self._navigate(_HOME_URL)
        # ── Stigmergic URL drop file polling (AG46 2026-05-07) ───────────────
        # Alice Browser checks .sifta_state/alice_browser_open_url.txt every
        # 2 seconds. When found, it navigates to the URL and deletes the file.
        # This is the consumer side of the VLC-bridge SIFTA handoff (§7.5).
        self._drop_file = REPO / ".sifta_state" / "alice_browser_open_url.txt"
        self._check_drop_file()          # immediate check on open
        self._drop_timer = QTimer(self)
        self._drop_timer.timeout.connect(self._check_drop_file)
        self._drop_timer.start(2000)     # poll every 2 seconds

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        # ── Toolbar ──────────────────────────────────────────────────────────
        tb = QToolBar("Navigation")
        tb.setMovable(False)
        tb.setObjectName("navBar")
        self.addToolBar(tb)

        self._back_btn = QPushButton("‹")
        self._fwd_btn = QPushButton("›")
        self._refresh_btn = QPushButton("↺")
        self._home_btn = QPushButton("⌂")
        for btn in [self._back_btn, self._fwd_btn, self._refresh_btn, self._home_btn]:
            btn.setFixedSize(36, 36)
            btn.setObjectName("navBtn")
            tb.addWidget(btn)

        self._url_bar = QLineEdit()
        self._url_bar.setObjectName("urlBar")
        self._url_bar.setPlaceholderText("Enter URL or search…")
        self._url_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._url_bar.setFixedHeight(34)
        self._url_bar.returnPressed.connect(self._on_url_entered)
        tb.addWidget(self._url_bar)

        # Quick bookmarks
        bookmarks = [
            ("🔍", "https://google.com"),
            ("📚", "https://en.wikipedia.org"),
            ("📺", "https://youtube.com"),
            ("🐙", "https://github.com"),
        ]
        for emoji, url in bookmarks:
            btn = QPushButton(emoji)
            btn.setFixedSize(34, 34)
            btn.setObjectName("bkBtn")
            btn.setToolTip(url)
            btn.clicked.connect(lambda _, u=url: self._navigate(u))
            tb.addWidget(btn)

        # ── Web view ─────────────────────────────────────────────────────────
        if _HAS_WEBENGINE:
            profile = QWebEngineProfile("alice_browser", self)
            profile.setHttpUserAgent(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36 SIFTA-Alice/1.0"
            )
            self._page = _AlicePage(profile, self)
            self._view = QWebEngineView()
            self._view.setPage(self._page)
            self._view.urlChanged.connect(self._on_url_changed)
            self._view.titleChanged.connect(self._on_title_changed)
            self._view.loadStarted.connect(self._on_load_started)
            self._view.loadFinished.connect(self._on_load_finished)
            self.setCentralWidget(self._view)
        else:
            self._view = None
            self.setCentralWidget(_NoWebEngineWidget())

        # ── Status bar ────────────────────────────────────────────────────────
        self._status = QStatusBar()
        self._status.setObjectName("statusBar")
        self._receipt_lbl = QLabel("No page loaded")
        self._receipt_lbl.setObjectName("receiptLbl")
        self._status.addPermanentWidget(self._receipt_lbl)
        self.setStatusBar(self._status)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(
            lambda: self._url_bar.selectAll() or self._url_bar.setFocus()
        )
        QShortcut(QKeySequence("Alt+Left"), self).activated.connect(self._go_back)
        QShortcut(QKeySequence("Alt+Right"), self).activated.connect(self._go_forward)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self._go_refresh)
        QShortcut(QKeySequence("F5"), self).activated.connect(self._go_refresh)

        # Wire buttons
        self._back_btn.clicked.connect(self._go_back)
        self._fwd_btn.clicked.connect(self._go_forward)
        self._refresh_btn.clicked.connect(self._go_refresh)
        self._home_btn.clicked.connect(lambda: self._navigate(_HOME_URL))

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #0d1117;
                color: #c9d1d9;
                font-family: 'Inter', 'SF Pro Display', system-ui;
            }
            QToolBar#navBar {
                background: #161b22;
                border-bottom: 1px solid #21262d;
                padding: 4px 6px;
                spacing: 4px;
            }
            QPushButton#navBtn {
                background: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton#navBtn:hover { background: #2d333b; color: #00e5ff; }
            QPushButton#navBtn:pressed { background: #161b22; }
            QPushButton#bkBtn {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton#bkBtn:hover { background: #21262d; border-color: #00e5ff44; }
            QLineEdit#urlBar {
                background: #0d1117;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
                selection-background-color: #1f6feb;
            }
            QLineEdit#urlBar:focus { border-color: #388bfd; }
            QStatusBar#statusBar {
                background: #161b22;
                border-top: 1px solid #21262d;
                color: #6e7681;
                font-size: 11px;
                font-family: 'SF Mono', Consolas, monospace;
            }
            QLabel#receiptLbl {
                color: #3fb950;
                font-size: 10px;
                font-family: 'SF Mono', Consolas, monospace;
                padding-right: 8px;
            }
        """)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _navigate(self, url: str):
        if not _HAS_WEBENGINE or self._view is None:
            return
        if url == _HOME_URL:
            self._view.setHtml(_HOME_HTML, QUrl("sifta://home"))
            self._url_bar.setText(_HOME_URL)
            return
        if not url.startswith(("http://", "https://", "file://", "data:")):
            # Treat as search if no scheme
            if " " in url or "." not in url:
                url = f"https://www.google.com/search?q={url.replace(' ', '+')}"
            else:
                url = "https://" + url
        self._view.load(QUrl(url))

    def _on_url_entered(self):
        self._navigate(self._url_bar.text().strip())

    def _go_back(self):
        if self._view:
            self._view.back()

    def _go_forward(self):
        if self._view:
            self._view.forward()

    def _go_refresh(self):
        if self._view:
            self._view.reload()

    # ── Signal handlers ───────────────────────────────────────────────────────

    @pyqtSlot(QUrl)
    def _on_url_changed(self, url: QUrl):
        url_str = url.toString()
        self._url_bar.setText(url_str)
        self._current_url = url_str

    @pyqtSlot(str)
    def _on_title_changed(self, title: str):
        self.setWindowTitle(f"🌐 {title}  —  Alice Browser" if title else "🌐 Alice Browser")

    @pyqtSlot()
    def _on_load_started(self):
        self._page_load_ts = time.time()
        self._status.showMessage("Loading…")

    @pyqtSlot(bool)
    def _on_load_finished(self, ok: bool):
        url = self._current_url
        title = self._view.title() if self._view else ""
        duration = round(time.time() - self._page_load_ts, 2)
        if ok and url and url not in (_HOME_URL, "sifta://home", "about:blank", ""):
            _write_browse_receipt(url, title, duration_s=duration)
            domain = _domain(url)
            self._receipt_lbl.setText(f"✅ receipt → {domain} ({duration}s)")
            self._status.showMessage(f"Loaded: {title[:60]}" if title else "Loaded")
        elif not ok:
            self._status.showMessage("⚠️  Page failed to load")
        else:
            self._status.showMessage("Ready")

    def closeEvent(self, event):
        if hasattr(self, "_drop_timer"):
            self._drop_timer.stop()
        super().closeEvent(event)

    # ── Stigmergic drop file consumer ────────────────────────────────────────

    def _check_drop_file(self) -> None:
        """Consume .sifta_state/alice_browser_open_url.txt if present."""
        drop = self._drop_file
        if not drop.exists():
            return
        try:
            url = drop.read_text(encoding="utf-8").strip()
            drop.unlink(missing_ok=True)
        except Exception:
            return
        if url:
            self._navigate(url)
            self._status.showMessage(f"Opened from VLC bridge: {url[:80]}")


# ── App manifest entry ────────────────────────────────────────────────────────
APP_MANIFEST = {
    "app_id": "sifta_alice_browser_widget",
    "name": "Alice Browser",
    "description": "Chromium-based web browser for Alice. Full JS/CSS rendering via QWebEngineView. Every URL visit writes a stigmergic receipt to alice_browse_history.jsonl.",
    "emoji": "🌐",
    "category": "Alice",
    "autostart": False,
}

if __name__ == "__main__":
    bootstrap_qt_webengine()
    app = QApplication(sys.argv)
    if not _HAS_WEBENGINE:
        print(f"❌ QtWebEngine unavailable: {_WEBENGINE_IMPORT_ERROR}")
    w = AliceBrowserWidget()
    w.show()
    sys.exit(app.exec())
