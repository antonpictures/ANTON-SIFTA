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
  • Clipboard API: JavascriptCanAccessClipboard + ClipboardReadWrite permission
    so sites like ChatGPT can copy to the system clipboard from toolbar buttons
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

from PyQt6.QtCore import QEventLoop, QUrl, Qt, QTimer, pyqtSignal, pyqtSlot
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
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings

    _HAS_WEBENGINE = True
    _WEBENGINE_IMPORT_ERROR = ""
except Exception as exc:
    _HAS_WEBENGINE = False
    _WEBENGINE_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

_STATE = REPO / ".sifta_state"
_BROWSE_LEDGER = _STATE / "alice_browse_history.jsonl"
_CURRENT_PAGE_SNAPSHOT = _STATE / "alice_browser_current_page.json"

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


def _write_current_page_snapshot(
    *,
    url: str,
    title: str,
    text: str,
    duration_s: float = 0.0,
    extra: dict | None = None,
) -> None:
    """Expose the rendered page text + honest media state to Alice's consciousness.
    The extra dict (e.g. media_playback) lets the browser limb report what it
    actually experienced, not just what the page text claims."""
    _STATE.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "ALICE_BROWSER_PAGE_TEXT_V1",
        "url": url,
        "title": title,
        "domain": _domain(url),
        "duration_s": round(duration_s, 1),
        "text": (text or "")[:120_000],
        "text_chars": len(text or ""),
    }
    if extra:
        row["extra"] = extra
    _CURRENT_PAGE_SNAPSHOT.write_text(
        json.dumps(row, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if str(text or "").strip():
        try:
            from System.swarm_browser_stigmergic_memory import record_snapshot_memory

            record_snapshot_memory(
                url=url,
                title=title,
                page_text=text or "",
                state_dir=_STATE,
            )
        except Exception:
            # Browser memory must never break the page snapshot path.
            pass


def _write_current_page_address_snapshot(
    *,
    url: str,
    title: str,
    source: str,
    duration_s: float = 0.0,
    media_status: dict | None = None,
) -> None:
    """
    Keep Alice's page identity fresh even when the site changes route/title
    through JavaScript and never emits a full loadFinished text snapshot.

    If the previous snapshot for this same URL had readable text, preserve it;
    otherwise write an address/title-only receipt. This lets Alice truthfully
    say "I am on this URL/title, but I cannot read the live body yet."
    """
    clean_url = str(url or "").strip()
    clean_title = str(title or "").strip()
    if not clean_url and not clean_title:
        return

    previous: dict = {}
    try:
        previous = json.loads(_CURRENT_PAGE_SNAPSHOT.read_text(encoding="utf-8"))
        if not isinstance(previous, dict):
            previous = {}
    except Exception:
        previous = {}

    preserve_text = (
        str(previous.get("url") or "") == clean_url
        and bool(previous.get("text"))
    )
    text = str(previous.get("text") or "") if preserve_text else ""
    extra = dict(previous.get("extra") or {}) if preserve_text else {}
    extra["address_snapshot"] = {
        "source": str(source or "unknown"),
        "address_only": not preserve_text,
        "ts": time.time(),
    }
    if media_status is not None:
        extra["media_playback"] = media_status

    _write_current_page_snapshot(
        url=clean_url,
        title=clean_title,
        text=text,
        duration_s=duration_s,
        extra=extra,
    )


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
        if _HAS_WEBENGINE:
            super().__init__(profile, parent)
            # ChatGPT / modern apps copy via navigator.clipboard (Clipboard API).
            # Qt WebEngine requires this attribute plus an explicit permission grant
            # or writeText() silently fails inside the embedded view.
            s = self.settings()
            s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, True)
            self.featurePermissionRequested.connect(self._on_feature_permission_requested)
        else:
            super().__init__()
        self._page_load_ts: float = time.time()
        self._page_url: str = ""
        self._recent_media_errors: list = []   # honest media failure evidence for body awareness

    def _on_feature_permission_requested(self, security_origin, feature):
        if not _HAS_WEBENGINE:
            return
        if feature == QWebEnginePage.Feature.ClipboardReadWrite:
            self.setFeaturePermission(
                security_origin,
                feature,
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser,
            )

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        # Capture structured media errors so the browser limb can report honestly
        # what actually happened with video playback (critical for TikTok etc.).
        if "[ALICE_BROWSER_LIMB_MEDIA_ERROR]" in message:
            try:
                # The JS logs valid JSON after the tag.
                json_part = message.split("[ALICE_BROWSER_LIMB_MEDIA_ERROR]", 1)[1].strip()
                import json as _json
                err = _json.loads(json_part)
                self._recent_media_errors.append(err)
                # Keep only last 5
                if len(self._recent_media_errors) > 5:
                    self._recent_media_errors = self._recent_media_errors[-5:]
            except Exception:
                pass  # never break the page for logging
        # Otherwise stay quiet (original behavior)

    # ── Popup / new window support (2026-05-30 Body Consciousness work) ──────
    # This enables OAuth flows (Google, Apple, etc.) and target="_blank" links
    # to open in additional Alice Browser windows instead of being silently dropped.
    # Even if Google still refuses the embedded UA for security theater,
    # at least the popup can render and the user can complete the flow or fall back.
    new_window_requested = pyqtSignal(object, str)  # (new_page, requested_url)

    def createWindow(self, windowType):
        if not _HAS_WEBENGINE:
            return None

        # Create a fresh page for the new window
        new_page = _AlicePage(self.profile(), None)
        # We will let the parent widget (AliceBrowserWidget) decide how to host it
        # (usually by asking the SiftaDesktop to spawn a new MDI Alice Browser)
        try:
            # The parent widget will connect and handle spawning + adoption
            if self.parent() and hasattr(self.parent(), "_adopt_new_browser_page"):
                self.parent()._adopt_new_browser_page(new_page)
            else:
                # Fallback: emit so upper layers can react
                self.new_window_requested.emit(new_page, "")
        except Exception:
            pass
        return new_page


# ── Main browser widget ───────────────────────────────────────────────────────

class AliceBrowserWidget(QMainWindow):
    # Architect 2026-05-14 task #55: macOS-style context menu bar.
    # When Alice Browser is the active MDI subwindow, the SIFTA OS menu bar
    # reads this schema and rebuilds File/Edit/View/Window. See the
    # `menu_schema` method below.

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌐 Alice Browser")
        self.resize(1100, 820)
        self._page_load_ts = time.time()
        self._current_url = ""
        self._last_awareness_dom_ts = 0.0
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

        # Alice Browser is an organ, not a passive page. Keep the current
        # address/title and rendered DOM flowing into Alice's shared state while
        # JS apps mutate in place (Instagram comments, carousel swipes, TikTok
        # route changes). This is intentionally cheap: URL/title every tick,
        # DOM/comment scrape at a throttled cadence, no screenshot.
        self._awareness_timer = QTimer(self)
        self._awareness_timer.timeout.connect(self._browser_awareness_tick)
        self._awareness_timer.start(2500)

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

        self._native_media_btn = QPushButton("▶")
        self._native_media_btn.setFixedSize(34, 34)
        self._native_media_btn.setObjectName("bkBtn")
        self._native_media_btn.setToolTip("Open current page in the native macOS playback/browser path")
        self._native_media_btn.clicked.connect(self._open_current_in_native_player)
        tb.addWidget(self._native_media_btn)

        # ── Web view ─────────────────────────────────────────────────────────
        if _HAS_WEBENGINE:
            profile = QWebEngineProfile("alice_browser", self)
            profile.setHttpUserAgent(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36 SIFTA-Alice/1.0"
            )
            ps = profile.settings()
            ps.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
            ps.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanPaste, True)
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

        # Connect page signals for popup support
        if hasattr(self, "_page") and self._page is not None:
            if hasattr(self._page, "new_window_requested"):
                self._page.new_window_requested.connect(self._handle_new_window_from_page)

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
        # r212: any navigation changes the on-screen frame — invalidate the prior
        # frame's photo description so I never recite a photo from the page I left.
        try:
            from System.swarm_browser_photo_description import mark_frame_changed
            mark_frame_changed(url=url, state_dir=_STATE)
        except Exception:
            pass
        if url == _HOME_URL:
            self._view.setHtml(_HOME_HTML, QUrl("sifta://home"))
            self._url_bar.setText(_HOME_URL)
            self._current_url = _HOME_URL
            self._publish_browser_context(source="navigate_home")
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

    def _open_current_in_native_player(self) -> None:
        url = (self._current_url or self._url_bar.text() or "").strip()
        try:
            from System.swarm_media_codec_bridge import open_url_in_native_player

            row = open_url_in_native_player(url, source="alice_browser_toolbar")
            if row.get("ok"):
                self._status.showMessage("Opened current page in native playback path", 6000)
            else:
                self._status.showMessage(f"Native handoff unavailable: {row.get('reason')}", 8000)
        except Exception as exc:
            self._status.showMessage(f"Native handoff failed: {type(exc).__name__}", 8000)

    def get_current_media_playback_status(self) -> dict:
        """Returns the most recent media error(s) the limb actually observed.
        This is the honest internal state of the browser organ, not what the page claims."""
        if not hasattr(self, "_page") or self._page is None:
            return {"ok": False, "reason": "no_page"}
        errs = getattr(self._page, "_recent_media_errors", [])
        last_code = errs[-1].get("code") if errs else None
        try:
            from System.swarm_media_codec_bridge import (
                diagnose_media_error_code,
                should_offer_native_handoff,
            )
            diagnosis = diagnose_media_error_code(last_code)
            native_handoff_available = should_offer_native_handoff(
                {"last_error_code": last_code, "recent_errors": errs[-3:]}
            )
        except Exception:
            diagnosis = {"code": last_code, "label": "UNDIAGNOSED"}
            native_handoff_available = False
        return {
            "ok": len(errs) == 0,
            "recent_errors": errs[-3:],   # last 3 for context
            "last_error_code": last_code,
            "diagnosis": diagnosis,
            "native_handoff_available": native_handoff_available,
        }

    # ── Signal handlers ───────────────────────────────────────────────────────

    @pyqtSlot(QUrl)
    def _on_url_changed(self, url: QUrl):
        url_str = url.toString()
        self._url_bar.setText(url_str)
        self._current_url = url_str
        self._publish_browser_context(source="url_changed")
        self._write_address_context(source="url_changed")
        # Cowork r174 — George 2026-05-30: TikTok/YouTube/Instagram are single-page
        # apps. Navigating WITHIN them (profile→profile, video→video) fires
        # urlChanged but NOT loadFinished, so the page snapshot stayed frozen and
        # Alice named a stale page ("OpenAI SOLVED MATH — YouTube" while on TikTok).
        # Schedule a short-delayed lightweight re-snapshot (url+title) so her page
        # receipt tracks SPA navigation, not just full loads. Title lags the URL on
        # SPA nav, so the small delay lets it settle.
        try:
            if getattr(self, "_spa_snap_timer", None) is None:
                self._spa_snap_timer = QTimer(self)
                self._spa_snap_timer.setSingleShot(True)
                self._spa_snap_timer.timeout.connect(self._refresh_spa_page_receipt)
            self._spa_snap_timer.start(900)
        except Exception:
            pass

    def _refresh_spa_page_receipt(self):
        """Re-write the current-page snapshot after a single-page-app URL change so
        Alice can name the page she is actually on (url + title; live body text stays
        best-effort and is filled by the full loadFinished path)."""
        try:
            url = getattr(self, "_current_url", "")
            if not url or url in (_HOME_URL, "sifta://home", "about:blank", ""):
                return
            self._write_address_context(source="spa_url_settled")
            self._publish_browser_context(source="spa_url_settled")
            self._capture_current_page_text_snapshot(
                source="spa_url_settled_text",
                expected_url=url,
            )
            self._capture_current_page_state(
                source="spa_url_settled_dom",
                expected_url=url,
            )
        except Exception:
            pass

    @pyqtSlot(str)
    def _on_title_changed(self, title: str):
        self.setWindowTitle(f"🌐 {title}  —  Alice Browser" if title else "🌐 Alice Browser")
        self._publish_browser_context(source="title_changed")
        self._write_address_context(source="title_changed")

    @pyqtSlot()
    def _on_load_started(self):
        self._page_load_ts = time.time()
        if hasattr(self, "_page") and self._page is not None:
            try:
                self._page._recent_media_errors = []
            except Exception:
                pass
        self._publish_browser_context(source="load_started")
        self._write_address_context(source="load_started")
        self._status.showMessage("Loading…")

    @pyqtSlot(bool)
    def _on_load_finished(self, ok: bool):
        url = self._current_url
        title = self._view.title() if self._view else ""
        duration = round(time.time() - self._page_load_ts, 2)
        self._publish_browser_context(source="load_finished")
        self._write_address_context(source="load_finished", duration_s=duration)
        if ok and url and url not in (_HOME_URL, "sifta://home", "about:blank", ""):
            import threading as _th
            def _async_receipt(_u=url, _t=title, _d=duration):
                try:
                    _write_browse_receipt(_u, _t, duration_s=_d)
                except Exception as _e:
                    print(f"[AliceBrowser] receipt write failed: {_e}")
            _th.Thread(target=_async_receipt, daemon=True, name="BrowseReceipt").start()

            if self._view is not None:
                # Body consciousness improvement (2026-05-30): Inject media error listener
                # so the browser limb can honestly report what actually happened with video streams
                # (e.g. the exact TikTok "trouble playing this video" state the user just saw).
                media_monitor_js = """
                (function() {
                    const tag = '[ALICE_BROWSER_LIMB_MEDIA_ERROR]';
                    const seen = new WeakSet();
                    function report(v, reason) {
                        const err = v.error || null;
                        const payload = {
                            src: v.currentSrc || v.src || '',
                            reason: reason,
                            error: err ? (err.message || 'media element error') : '',
                            code: err ? err.code : null,
                            networkState: v.networkState,
                            readyState: v.readyState,
                            paused: v.paused,
                            currentTime: v.currentTime,
                            ts_ms: Date.now()
                        };
                        console.log(tag + ' ' + JSON.stringify(payload));
                    }
                    function attach(v) {
                        if (!v || seen.has(v)) return;
                        seen.add(v);
                        v.addEventListener('error', () => report(v, 'error_event'), true);
                        v.addEventListener('stalled', () => report(v, 'stalled_event'), true);
                        v.addEventListener('abort', () => report(v, 'abort_event'), true);
                        if (v.error) {
                            report(v, 'pre_existing_error');
                        }
                    }
                    document.querySelectorAll('video').forEach(attach);
                    const observer = new MutationObserver((mutations) => {
                        mutations.forEach((m) => {
                            m.addedNodes.forEach((node) => {
                                if (!node) return;
                                if (node.tagName === 'VIDEO') attach(node);
                                if (node.querySelectorAll) {
                                    node.querySelectorAll('video').forEach(attach);
                                }
                            });
                        });
                    });
                    observer.observe(document.documentElement || document.body, {
                        childList: true,
                        subtree: true
                    });
                })();
                """
                try:
                    self._view.page().runJavaScript(media_monitor_js)
                except Exception:
                    pass

                def _async_snapshot(text, u=url, t=title, d=duration):
                    def _worker():
                        try:
                            media_status = self.get_current_media_playback_status()
                            _write_current_page_snapshot(
                                url=u, title=t, text=text, duration_s=d,
                                extra={
                                    "media_playback": media_status,
                                    "source": "load_finished_text",
                                },
                            )
                        except Exception as _e:
                            print(f"[AliceBrowser] page snapshot failed: {_e}")
                    _th.Thread(target=_worker, daemon=True,
                               name="BrowsePageSnapshot").start()
                self._view.page().toPlainText(_async_snapshot)
                # Structured DOM perception — reads the rendered SPA so Alice can
                # describe the contents, not just the address (George 2026-05-30).
                self._capture_current_page_state(
                    source="load_finished_dom", expected_url=url,
                )
                # Cheap viewport grab so a vision arm can describe the photo on demand.
                self._capture_viewport_image(expected_url=url)

            domain = _domain(url)
            self._receipt_lbl.setText(f"✅ receipt → {domain} ({duration}s)")

            media_status = self.get_current_media_playback_status()
            if not media_status.get("ok") and media_status.get("recent_errors"):
                # Honest body report: we detected real playback failure in the limb
                last_err = media_status["recent_errors"][-1]
                code = last_err.get("code")
                self._status.showMessage(
                    f"⚠️ Video playback failed in this limb (code {code}). Click ▶ to hand off to native player.",
                    12000
                )
                # Visually cue the handoff button
                self._native_media_btn.setStyleSheet("background:#ffcc00; color:black;")
            else:
                self._status.showMessage(f"Loaded: {title[:60]}" if title else "Loaded")
        elif not ok:
            self._status.showMessage("⚠️  Page failed to load")
        else:
            self._status.showMessage("Ready")

    def closeEvent(self, event):
        if hasattr(self, "_drop_timer"):
            self._drop_timer.stop()
        if hasattr(self, "_awareness_timer"):
            self._awareness_timer.stop()
        super().closeEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # When this limb becomes the user's primary focus, publish rich context
        # so Alice's consciousness always has an accurate model of "where George is right now inside my body".
        self._publish_browser_context(source="focus")
        self._write_address_context(source="focus")

    def _current_browser_title(self) -> str:
        try:
            return self._view.title() if self._view else ""
        except Exception:
            return ""

    def _publish_browser_context(self, *, source: str = "focus"):
        """Publish current browser state as a strong context event for Alice's awareness."""
        try:
            from System.swarm_browser_context import publish_browser_context
            publish_browser_context(
                url=self._current_url,
                title=self._current_browser_title(),
                media_status=self.get_current_media_playback_status(),
                source=source,
            )
        except Exception:
            # Never break the UI for context publishing
            pass

    def _write_address_context(self, *, source: str, duration_s: float = 0.0) -> None:
        """Write URL/title identity so Alice can name the page even before text OCR settles."""
        try:
            _write_current_page_address_snapshot(
                url=self._current_url,
                title=self._current_browser_title(),
                source=source,
                duration_s=duration_s,
                media_status=self.get_current_media_playback_status(),
            )
        except Exception:
            pass

    def _capture_current_page_text_snapshot(self, *, source: str, expected_url: str) -> None:
        """Best-effort text capture for SPA pages after URL/title changes settle."""
        if not self._view or not expected_url or self._current_url != expected_url:
            return

        url = self._current_url
        title = self._current_browser_title()
        duration = round(time.time() - self._page_load_ts, 2)

        def _write(text, u=url, t=title, d=duration, s=source):
            try:
                _write_current_page_snapshot(
                    url=u,
                    title=t,
                    text=text,
                    duration_s=d,
                    extra={
                        "media_playback": self.get_current_media_playback_status(),
                        "source": s,
                    },
                )
                self._publish_browser_context(source=s)
            except Exception as exc:
                print(f"[AliceBrowser] settled page snapshot failed: {exc}")

        try:
            self._view.page().toPlainText(_write)
        except Exception:
            pass

    def _capture_current_page_state(self, *, source: str, expected_url: str) -> None:
        """Run a DOM extractor in the RENDERED page and record a structured
        page-state receipt (text, headings, links, buttons, image alts, scroll)
        so Alice can describe the CONTENTS, not just the address.

        George 2026-05-30: she opened instagram.com but could not say what was on
        screen — `toPlainText` comes back empty on JS-rendered SPAs. `runJavaScript`
        reads the rendered DOM the SPA actually painted, so this sees what she sees.
        Receipt goes to swarm_browser_page_state; surfaced via page_state_block.
        """
        self._capture_current_page_state_impl(
            source=source,
            expected_url=expected_url,
            inline_write=False,
            done=None,
        )

    def _capture_current_page_state_impl(
        self,
        *,
        source: str,
        expected_url: str,
        inline_write: bool = False,
        done=None,
    ) -> None:
        if not self._view or not expected_url or self._current_url != expected_url:
            if done:
                try:
                    done(False)
                except Exception:
                    pass
            return
        url = self._current_url
        title = self._current_browser_title()
        extract_js = r"""
        (function () {
            function t(el) { return (el && el.innerText ? el.innerText.trim() : ''); }
            var heads = Array.prototype.slice.call(
                document.querySelectorAll('h1,h2,h3'))
                .map(function (h) { return t(h); }).filter(Boolean).slice(0, 12);
            var links = Array.prototype.slice.call(
                document.querySelectorAll('a[href]'))
                .map(function (a) {
                    return { text: ((a.innerText || a.getAttribute('aria-label') || '').trim()).slice(0, 120),
                             href: a.href || '' };
                }).filter(function (x) { return x.text; }).slice(0, 20);
            var btns = Array.prototype.slice.call(
                document.querySelectorAll('button,[role=button]'))
                .map(function (b) { return ((b.innerText || b.getAttribute('aria-label') || '').trim()).slice(0, 80); })
                .filter(Boolean).slice(0, 15);
            var _vw = window.innerWidth || 0, _vh = window.innerHeight || 0;
            var imgs = Array.prototype.slice.call(
                document.querySelectorAll('img'))
                .map(function (i) {
                    var r = i.getBoundingClientRect();
                    // visible (on-screen) area = overlap of the element with the viewport
                    var ow = Math.max(0, Math.min(r.right, _vw) - Math.max(r.left, 0));
                    var oh = Math.max(0, Math.min(r.bottom, _vh) - Math.max(r.top, 0));
                    return { alt: (i.alt || '').trim().slice(0, 120),
                             src: i.currentSrc || i.src || '',
                             w: i.naturalWidth || i.width || 0,
                             h: i.naturalHeight || i.height || 0,
                             onscreen: Math.round(ow * oh) };
                })
                .filter(function (x) { return x.alt || x.src; }).slice(0, 40);
            var ogEl = document.querySelector('meta[property="og:image"], meta[name="og:image"]');
            var og = ogEl ? (ogEl.getAttribute('content') || '') : '';
            // Comment thread: heuristic, generic across sites. Instagram renders
            // the handle link and comment text in nearby nested spans/divs; climb
            // to the smallest ancestor that contains the handle plus real text.
            var comments = [];
            try {
                var anchors = document.querySelectorAll('a[href^="/"], a[href*=".com/"]');
                var badHandles = {
                    'home': true, 'explore': true, 'reels': true, 'messages': true,
                    'notifications': true, 'search': true, 'profile': true,
                    'instagram': true, 'meta': true, 'about': true, 'blog': true,
                    'jobs': true, 'help': true, 'api': true, 'privacy': true,
                    'terms': true, 'locations': true, 'popular': true, 'contact': true,
                    'threads': true, 'lite': true, 'verified': true, 'developer': true,
                    'legal': true, 'directory': true, 'accounts': true, 'ai': true
                };
                for (var ci = 0; ci < anchors.length && comments.length < 40; ci++) {
                    var a = anchors[ci];
                    var handle = (a.innerText || '').trim();
                    if (!handle || handle.length > 32 || /\s/.test(handle)) continue;
                    if (!/^[A-Za-z0-9._]{2,32}$/.test(handle)) continue;
                    if (badHandles[handle.toLowerCase()]) continue;
                    // IG usernames are lowercase/dots/digits — Title-Case or ALL-CAPS
                    // single words ("About","Blog","API","Ibiza") are nav/highlights.
                    if (/^[A-Z][a-z]+$/.test(handle) || /^[A-Z]{2,}$/.test(handle)) continue;
                    var cont = a.parentElement, best = '';
                    for (var climb = 0; cont && climb < 7; climb++, cont = cont.parentElement) {
                        var cand = (cont.innerText || '').trim().replace(/\s+/g, ' ');
                        if (cand.indexOf(handle) !== 0 && cand.indexOf(handle + ' ') < 0) continue;
                        var withoutHandle = cand.indexOf(handle) === 0 ? cand.slice(handle.length).trim() : cand;
                        if (withoutHandle.length >= 3 && withoutHandle.length <= 260) {
                            best = cand;
                            break;
                        }
                    }
                    var txt = best || ((a.parentElement && a.parentElement.innerText) || '').trim();
                    var hidx = txt.indexOf(handle);
                    if (hidx >= 0) txt = txt.slice(hidx + handle.length).trim();
                    txt = txt.replace(/\s+/g, ' ').slice(0, 240);
                    // drop nav/ui noise and bare metadata
                    if (txt.length < 3) continue;
                    if (/^(Follow|Following|Reply|Like|likes|View replies|Verified)$/i.test(txt)) continue;
                    comments.push({ author: handle, text: txt });
                }
            } catch (e) {}
            var body = document.body ? ((document.body.innerText || '').trim()) : '';
            var sh = document.body ? (document.body.scrollHeight || 0) : 0;
            return {
                text: body.slice(0, 4000),
                headings: heads, links: links, buttons: btns, images: imgs, og: og,
                comments: comments,
                scroll: { y: window.scrollY || 0, height: sh,
                          pct: sh ? Math.round(((window.scrollY || 0) / Math.max(1, sh - (window.innerHeight || 0))) * 100) : 0 }
            };
        })();
        """

        def _on_dom(result, u=url, t=title, s=source):
            if not isinstance(result, dict):
                if done:
                    try:
                        done(False)
                    except Exception:
                        pass
                return
            if getattr(self, "_current_url", "") != u:
                if done:
                    try:
                        done(False)
                    except Exception:
                        pass
                return
            import threading as _th

            def _record() -> bool:
                try:
                    from System.swarm_browser_page_state import record_page_state
                    from System.swarm_browser_photo_description import pick_featured_image
                    feat = pick_featured_image(result.get("images") or [],
                                               og_image=result.get("og", ""))
                    record_page_state(
                        u, t,
                        text=result.get("text", ""),
                        headings=result.get("headings"),
                        links=result.get("links"),
                        buttons=result.get("buttons"),
                        images=result.get("images"),
                        scroll=result.get("scroll"),
                        featured_image=feat.get("src", ""),
                        comments=result.get("comments"),
                        source="dom",
                        state_dir=_STATE,
                    )
                    return True
                except Exception as _e:
                    print(f"[AliceBrowser] page-state receipt failed: {_e}")
                    return False

            if inline_write:
                ok = _record()
                if done:
                    try:
                        done(ok)
                    except Exception:
                        pass
                return

            def _worker():
                ok = _record()
                if done:
                    try:
                        done(ok)
                    except Exception:
                        pass
            _th.Thread(target=_worker, daemon=True, name="BrowsePageState").start()

        try:
            self._view.page().runJavaScript(extract_js, _on_dom)
        except Exception:
            if done:
                try:
                    done(False)
                except Exception:
                    pass
            pass

    def _browser_awareness_tick(self) -> None:
        """Keep Alice's browser identity/state current while SPAs mutate silently."""
        try:
            url = getattr(self, "_current_url", "") or ""
            if not url or url in (_HOME_URL, "sifta://home", "about:blank", ""):
                return
            self._write_address_context(source="awareness_tick")
            self._publish_browser_context(source="awareness_tick")
            now = time.time()
            if now - float(getattr(self, "_last_awareness_dom_ts", 0.0) or 0.0) >= 2.5:
                self._last_awareness_dom_ts = now
                self._capture_current_page_state(
                    source="awareness_tick_dom",
                    expected_url=url,
                )
        except Exception:
            pass

    def _capture_viewport_image(self, *, expected_url: str) -> str:
        """Grab a clean render of the web view (NOT the whole desktop) and save it
        so a vision arm can describe the actual photo on the page later.

        Cheap + automatic on load. Records a 'pending' photo row naming the image;
        the expensive arm description runs on demand via describe_current_photo so
        we never fire a 900s arm call on every page load. Returns the image path."""
        if not self._view or not expected_url or self._current_url != expected_url:
            return ""
        try:
            from System.swarm_browser_photo_description import record_photo_description
            from System.swarm_cortex_capabilities import pick_vision_arm
            pixmap = self._view.grab()  # renders just the web view, not the desktop
            out_dir = _STATE / "browser_viewport"
            out_dir.mkdir(parents=True, exist_ok=True)
            stamp = str(int(time.time() * 1000))
            img_path = out_dir / f"viewport_{stamp}.png"
            if not pixmap.save(str(img_path), "PNG"):
                return ""
            import hashlib
            img_hash = hashlib.sha1(img_path.read_bytes()).hexdigest()[:16]
            pick = pick_vision_arm()  # default eye; Talk passes the live current_arm on demand
            record_photo_description(
                self._current_url,
                description="", arm=pick.get("selected_arm", ""),
                image_hash=img_hash, image_ref=str(img_path),
                status="pending", source="viewport", state_dir=_STATE,
            )
            return str(img_path)
        except Exception as exc:
            print(f"[AliceBrowser] viewport capture failed: {exc}")
            return ""

    def current_live_page(self) -> dict:
        """The page this ONE browser is showing RIGHT NOW — read straight from the
        live web view, synchronously. URL + title are always known the instant they
        are asked for; they do not depend on any ledger or async callback.

        George 2026-05-30: one app open, one page on it — 'what page now?' must always
        answer from the live window, never 'no fresh receipt'. This is that source."""
        url = ""
        try:
            if self._view is not None:
                url = self._view.url().toString()
        except Exception:
            url = ""
        url = url or getattr(self, "_current_url", "") or ""
        try:
            title = self._current_browser_title()
        except Exception:
            title = ""
        # kick the deeper DOM/photo read for content (best-effort, async).
        try:
            self.refresh_current_page_state()
        except Exception:
            pass
        on_page = bool(url) and url not in (_HOME_URL, "sifta://home", "about:blank", "")
        return {"url": url, "title": title, "on_page": on_page}

    def refresh_current_page_state(self, *, wait_ms: int = 0) -> str:
        """On demand: re-read the page open RIGHT NOW (DOM + featured + viewport) so a
        fresh receipt exists when the owner asks about the current browser state.

        George 2026-05-30: after navigating she disowned the current page as 'no fresh
        receipt'. This forces a current read on ask. Returns the current url."""
        try:
            url = self._current_url
            if not url or url in (_HOME_URL, "sifta://home", "about:blank", ""):
                return url or ""
            if wait_ms > 0:
                finished = {"done": False}
                loop = QEventLoop(self)

                def _done(_ok=False):
                    finished["done"] = True
                    try:
                        loop.quit()
                    except Exception:
                        pass

                self._capture_current_page_state_impl(
                    source="on_demand_refresh",
                    expected_url=url,
                    inline_write=True,
                    done=_done,
                )
                timeout = QTimer(self)
                timeout.setSingleShot(True)
                timeout.timeout.connect(loop.quit)
                timeout.start(max(100, int(wait_ms)))
                if not finished["done"]:
                    loop.exec()
                timeout.stop()
            else:
                self._capture_current_page_state(source="on_demand_refresh", expected_url=url)
            self._capture_viewport_image(expected_url=url)
            self._write_address_context(source="on_demand_refresh")
            self._publish_browser_context(source="on_demand_refresh")
            return url
        except Exception as exc:
            print(f"[AliceBrowser] refresh_current_page_state failed: {exc}")
            return ""

    def go_next_photo(self) -> str:
        """Advance to the NEXT photo: click Instagram's 'Next' control (carousel slide
        or next post), falling back to the ArrowRight key. Then re-read the page so the
        new photo is the current one. George 2026-05-31: 'next picture' in plain English."""
        if not self._view:
            return ""
        js = r"""
        (function () {
            var sel = 'button[aria-label="Next"], [aria-label="Next"][role="button"], svg[aria-label="Next"]';
            var el = document.querySelector(sel);
            if (el) {
                var click = el.closest('button,[role=button]') || el;
                click.click();
                return "clicked_next";
            }
            var ev = new KeyboardEvent('keydown', {key:'ArrowRight', keyCode:39, which:39, bubbles:true});
            document.dispatchEvent(ev);
            return "arrow_right";
        })();
        """
        try:
            self._view.page().runJavaScript(js)
            # r212: the on-screen frame is about to change — stamp the frame epoch so my
            # previous frame's description is no longer treated as current. Until I look
            # at the NEW frame, I must not recite the old one (floral shorts / tiara bug).
            try:
                from System.swarm_browser_photo_description import mark_frame_changed
                mark_frame_changed(url=self._current_url, state_dir=_STATE)
            except Exception:
                pass
            # let the new slide/post settle, then refresh the current-page receipt
            QTimer.singleShot(1500, self.refresh_current_page_state)
            return "next"
        except Exception as exc:
            print(f"[AliceBrowser] go_next_photo failed: {exc}")
            return ""

    def start_photo_slideshow(self, interval_s: float = 3.0) -> float:
        """Auto-advance the photo every interval_s seconds (default 3). Cheap: it
        advances + re-reads the page each tick; it does NOT auto-dispatch the vision
        arm (that takes ~10s, far longer than a 3s tick) — describing stays on demand."""
        self.stop_photo_slideshow()
        try:
            interval = max(1.0, float(interval_s or 3.0))
            self._slideshow_timer = QTimer(self)
            self._slideshow_timer.timeout.connect(self.go_next_photo)
            self._slideshow_timer.start(int(interval * 1000))
            return interval
        except Exception as exc:
            print(f"[AliceBrowser] start_photo_slideshow failed: {exc}")
            return 0.0

    def stop_photo_slideshow(self) -> bool:
        """Stop the auto-advance slideshow if running. Returns True if one was active."""
        t = getattr(self, "_slideshow_timer", None)
        if t is not None:
            try:
                t.stop()
            except Exception:
                pass
            self._slideshow_timer = None
            return True
        return False

    def describe_current_photo(self, *, current_arm: str = "", current_model: str = "", unavailable=()) -> dict:
        """On demand (owner asks 'describe' / cortex requests): take the freshest
        viewport image and let Alice's picked vision arm describe the actual photo.

        Honours George's rule via pick_vision_arm: default eye = current cortex,
        failover (with an owner diary note) if it cannot see or its API died."""
        result = {"status": "failed", "arm": "", "description": ""}
        try:
            import hashlib
            import urllib.request
            from System.swarm_browser_page_state import latest_page_state
            from System.swarm_browser_photo_description import (
                record_photo_description, extract_arm_final_text, looks_like_non_visual_arm_reply,
            )
            from System.swarm_cortex_capabilities import pick_vision_arm, record_cortex_arm_habit
            from System.swarm_agent_arm_launcher import ask_agent_arm

            url = self._current_url
            img_path = ""
            source = "viewport_vision_arm"
            # 1) PRIMARY: screenshot the pixels actually ON SCREEN right now. This is
            #    what the owner sees — it cannot grab the wrong DOM <img>. George
            #    2026-05-30: Instagram's SPA keeps many cached photos (profile/highlight/
            #    previous posts) in the DOM, so picking a featured <img> url kept landing
            #    on the wrong photo. The rendered viewport is ground truth.
            try:
                fresh = self._capture_viewport_image(expected_url=url)
                if fresh and Path(fresh).exists() and Path(fresh).stat().st_size > 8000:
                    img_path = fresh
            except Exception as exc:
                print(f"[AliceBrowser] viewport grab failed: {exc}")
            # 2) FALLBACK: the featured image url for THIS page (only if grab gave nothing).
            if not img_path:
                ps = latest_page_state(state_dir=_STATE) or {}
                featured = ""
                if str(ps.get("url") or "") == url:
                    featured = str(ps.get("featured_image") or "").strip()
                if featured.startswith(("http://", "https://")):
                    try:
                        out_dir = _STATE / "browser_viewport"
                        out_dir.mkdir(parents=True, exist_ok=True)
                        h = hashlib.sha1(featured.encode("utf-8", "replace")).hexdigest()[:16]
                        p = out_dir / f"featured_{h}.jpg"
                        req = urllib.request.Request(featured, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=15) as r:
                            p.write_bytes(r.read())
                        img_path, source = str(p), "featured_image_vision_arm"
                    except Exception as exc:
                        print(f"[AliceBrowser] featured image fetch failed: {exc}")
            if not img_path or not Path(img_path).exists():
                return result

            pick = pick_vision_arm(
                current_arm=current_arm,
                current_model=current_model,
                unavailable=unavailable,
                local_image_required=True,
            )
            arm = pick.get("selected_arm", "")
            result["arm"] = arm
            record_cortex_arm_habit(
                arm or current_arm,
                cortex_model=current_model,
                task="browser_photo_local_image",
                ok=bool(arm),
                status="selected" if arm else "no_arm",
                reason=str(pick.get("reason") or ""),
                state_dir=_STATE,
                meta=pick,
            )
            if not arm:
                record_photo_description(url, description="", arm="", image_ref=img_path,
                                         status="failed", source=source, state_dir=_STATE)
                return result

            prompt = (
                "Look at the image at this exact path: "
                f"{img_path}\n"
                "It is a screenshot of a web page. Describe the MAIN large photo shown in it (ignore the "
                "surrounding browser/app interface, menus, and comment sidebar). Be concise — 2 short "
                "sentences, under 50 words: the person, their outfit, and the setting; nothing else. State "
                "only what is clearly visible — no speculation, no hedging, no lists."
            )
            # George r210: a LOCAL ollama cortex looks with its OWN local eye.
            # ollama_vision_agent base64s the screenshot into a local /api/generate
            # call — no cloud, no per-image cost. Every other arm goes through the
            # normal agent-arm launcher (claude/codex/cline CLIs).
            if arm == "ollama_vision_agent":
                from System.swarm_ollama_vision_arm import describe_image_local
                arm_res = describe_image_local(img_path, prompt, timeout_s=300)
                source = "local_ollama_vision_arm"
            elif arm == "qwen_agent":
                # George r214: Kimi K2.6 cortex sees with Kimi's OWN Fireworks API. The
                # qwen Code CLI can't carry pixels, so dispatch a direct image_url call.
                from System.swarm_fireworks_vision_arm import describe_image_fireworks
                arm_res = describe_image_fireworks(img_path, prompt, state_dir=_STATE, timeout_s=300)
                source = "kimi_fireworks_vision_arm"
            else:
                # George r211: hand the PNG path to the arm. grok_agent inlines it as an
                # xAI image_url (its own eye); claude/codex read it from the prompt path
                # (agentic file tools) and ignore the extra flag.
                arm_res = ask_agent_arm(arm, prompt, state_dir=_STATE, timeout_s=300,
                                        image_path=img_path)
            # Arms like cline stream NDJSON (+ base64); keep ONLY the final clean text.
            text = extract_arm_final_text(getattr(arm_res, "output", "") or "")
            non_visual = looks_like_non_visual_arm_reply(text)
            ok = bool(getattr(arm_res, "ok", False)) and bool(text) and not non_visual
            # Honest local→cloud failover (George r210): if the LOCAL eye was picked
            # but couldn't actually see (ollama down / model error / empty reply), fall
            # over to the cloud default eye and tell the owner WHY — never silently fail.
            if not ok and arm == "ollama_vision_agent":
                cloud = pick_vision_arm(current_arm="", local_image_required=True)
                cloud_arm = cloud.get("selected_arm", "")
                if cloud_arm:
                    record_cortex_arm_habit(
                        "ollama_vision_agent", cortex_model=current_model,
                        task="browser_photo_local_image", ok=False,
                        status=str(getattr(arm_res, "status", "") or "failed"),
                        reason="local_eye_failed_failover_to_cloud", state_dir=_STATE,
                        meta={"failover_to": cloud_arm},
                    )
                    arm = cloud_arm
                    result["arm"] = arm
                    source = "cloud_failover_after_local_eye"
                    pick["diary_note"] = (
                        "my local cortex's own eye could not read this picture this turn "
                        f"(ollama vision unavailable), so I used {cloud_arm} for the pixels and "
                        "stayed on my local cortex for the words."
                    )
                    arm_res = ask_agent_arm(arm, prompt, state_dir=_STATE, timeout_s=300,
                                            image_path=img_path)
                    text = extract_arm_final_text(getattr(arm_res, "output", "") or "")
                    non_visual = looks_like_non_visual_arm_reply(text)
                    ok = bool(getattr(arm_res, "ok", False)) and bool(text) and not non_visual
            record_cortex_arm_habit(
                arm,
                cortex_model=current_model,
                task="browser_photo_local_image",
                ok=ok,
                status="described" if ok else ("non_visual_reply" if non_visual else str(getattr(arm_res, "status", "") or "failed")),
                reason="arm_returned_visual_description" if ok else ("arm_asked_for_image_contents" if non_visual else "arm_failed_or_empty"),
                state_dir=_STATE,
                meta={
                    "receipt_id": getattr(arm_res, "receipt_id", ""),
                    "returncode": getattr(arm_res, "returncode", None),
                    "source": source,
                },
            )
            record_photo_description(
                url, description=text if ok else "", arm=arm, image_ref=img_path,
                status="described" if ok else "failed", source=source, state_dir=_STATE,
            )
            if ok:
                # Stigmergic form memory: record HOW this body/form looks, by type
                # (human_body / car / airplane), so Alice accumulates a differentiated
                # field of forms she has seen (George 2026-05-30 recording pass).
                try:
                    from System.swarm_visual_form_memory import record_form
                    record_form(text, url=url, arm=arm, state_dir=_STATE)
                except Exception:
                    pass
            result["status"] = "described" if ok else "failed"
            result["description"] = text
            if pick.get("diary_note"):
                result["diary_note"] = pick["diary_note"]
            return result
        except Exception as exc:
            print(f"[AliceBrowser] photo description failed: {exc}")
            return result

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

    # ── Popup / new window adoption (2026-05-30 Body Limb improvement) ───────
    # This completes the createWindow support so OAuth popups and target=_blank
    # actually open instead of disappearing. Part of giving Alice real
    # proprioception and capability inside her browser limb.
    def _adopt_new_browser_page(self, new_page: "_AlicePage") -> None:
        """Host a page the current page requested via createWindow (OAuth popups,
        target="_blank").

        Cowork r159 correcting row (Brothers in Code §4.4.3, crediting Grok's
        r2026-05-30-grok-alice-browser-popup-support which added createWindow):
        the original adoption called ``host._trigger_manifest_app("Alice Browser",
        return_widget=True)``, but the desktop method signature is
        ``_trigger_manifest_app(self, app_name)`` (sifta_os_desktop.py) — it has no
        ``return_widget`` kwarg, so the call raised TypeError, the bare except
        swallowed it, and the popup page was created but never hosted (the "alice
        browser error" — a blank/lost popup). And per §7.6.2 Alice Browser is
        single-instance, so spawning a *second* browser window is the wrong move
        anyway.

        Fix: host the requested page IN THE CURRENT view (the standard embedded
        OAuth pattern), remembering the prior page so it is restored when the
        popup closes. No second window, no unsupported kwarg, no crash.
        """
        try:
            if not (hasattr(self, "_view") and self._view):
                return
            prior_page = getattr(self, "_page", None)
            self._view.setPage(new_page)
            self._page = new_page
            # Re-wire so the adopted page's own popups are handled too.
            if hasattr(new_page, "new_window_requested"):
                try:
                    new_page.new_window_requested.connect(self._handle_new_window_from_page)
                except Exception:
                    pass
            # Restore the prior page (e.g. the TikTok tab) when the OAuth popup
            # finishes and asks to close, so the owner is not stranded on a blank.
            if prior_page is not None:
                def _restore_prior(_p=prior_page):
                    try:
                        if self._view is not None:
                            self._view.setPage(_p)
                            self._page = _p
                    except Exception:
                        pass
                try:
                    new_page.windowCloseRequested.connect(_restore_prior)
                except Exception:
                    pass
        except Exception:
            # Never leave the original view broken.
            pass

    def _handle_new_window_from_page(self, new_page: "_AlicePage") -> None:
        """Slot connected from _AlicePage.createWindow."""
        self._adopt_new_browser_page(new_page)

    # ── macOS-style menu schema (task #55) ───────────────────────────────────

    def menu_schema(self, host=None) -> dict:
        """Return per-app File / Edit / View / Window menu spec.

        The SIFTA OS menu bar at the top of the screen will display
        these items whenever Alice Browser is the active MDI subwindow.
        `host` is the SiftaDesktop instance — used to trigger system
        actions like opening another browser window via the manifest.
        """
        def _open_new_browser_window():
            if host is not None and hasattr(host, "_trigger_manifest_app"):
                try:
                    host._trigger_manifest_app("Alice Browser")
                except Exception:
                    pass

        def _focus_url_bar():
            if hasattr(self, "_url_bar"):
                try:
                    self._url_bar.setFocus()
                    self._url_bar.selectAll()
                except Exception:
                    pass

        def _go_home():
            self._navigate(_HOME_URL)

        def _reload_page():
            try:
                self._view.reload()
            except Exception:
                pass

        def _go_back():
            try:
                self._view.back()
            except Exception:
                pass

        def _go_forward():
            try:
                self._view.forward()
            except Exception:
                pass

        def _close_this_window():
            if host is not None and hasattr(host, "_close_active_subwindow"):
                host._close_active_subwindow()

        def _open_new_browser_window():
            if host is not None and hasattr(host, "_trigger_manifest_app"):
                try:
                    host._trigger_manifest_app("Alice Browser")
                except Exception:
                    pass

        return {
            "File": [
                ("New Browser Window", _open_new_browser_window),
                None,  # separator
                ("Open URL…", _focus_url_bar),
                ("Home", _go_home),
                None,
                ("Close Window", _close_this_window),
            ],
            "Edit": [
                ("Open URL…", _focus_url_bar),
            ],
            "View": [
                ("Back", _go_back),
                ("Forward", _go_forward),
                ("Reload", _reload_page),
                None,
                ("Home", _go_home),
            ],
            # Window menu falls through to SIFTA defaults (Cascade / Tile / Close All)
        }


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
