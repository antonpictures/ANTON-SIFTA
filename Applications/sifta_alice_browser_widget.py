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
import re
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


def _is_instagram_media_url(url: str) -> bool:
    text = str(url or "")
    return "instagram.com" in text and any(part in text for part in ("/reel/", "/p/", "/tv/"))


def _choose_native_media_handoff_url(
    dom_info: dict | None,
    *,
    fallback_url: str = "",
    media_status: dict | None = None,
) -> str:
    """Choose the best URL for native playback when the embedded limb cannot decode.

    Instagram profile pages often keep the address at ``/kylinmilan/`` while a
    clicked reel fails inside a modal. The native handoff must open the clicked
    reel/post, or the signed MP4 URL from the media error, not just the profile.
    """
    info = dom_info if isinstance(dom_info, dict) else {}
    candidates: list[str] = []
    for key in ("last_clicked", "dialog_href", "active_href", "first_reel_href", "first_media_href"):
        value = str(info.get(key) or "").strip()
        if value:
            candidates.append(value)

    loc = str(info.get("location") or fallback_url or "").strip()
    if _is_instagram_media_url(loc):
        candidates.append(loc)

    for err in (media_status or {}).get("recent_errors", []) or []:
        if isinstance(err, dict):
            src = str(err.get("src") or "").strip()
            if src:
                candidates.append(src)

    video_src = str(info.get("video_src") or "").strip()
    if video_src:
        candidates.append(video_src)
    if fallback_url:
        candidates.append(str(fallback_url).strip())

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in {"sifta://home", "about:blank"} or candidate in seen:
            continue
        seen.add(candidate)
        if candidate.startswith(("http://", "https://")):
            return candidate
    return ""


_VISIBLE_MEDIA_VISUAL_HINTS = {
    "beach", "ocean", "sea", "water", "shore", "waves", "wave", "sand",
    "backdrop", "background", "sky", "pool", "lake", "river",
}


def _visible_media_query_tokens(query: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9]{3,}", str(query or "").lower())
        if t not in {"the", "this", "that", "with", "from", "currently", "positioned", "please", "pls"}
    }


def _candidate_visible_text(candidate: dict) -> str:
    if not isinstance(candidate, dict):
        return ""
    parts = [
        candidate.get("href"),
        candidate.get("alt"),
        candidate.get("aria"),
        candidate.get("text"),
        candidate.get("src"),
    ]
    return " ".join(str(p or "") for p in parts).lower()


def _score_visible_media_candidate(query: str, candidate: dict) -> float:
    """Score an on-screen Instagram tile from text/geometry only.

    Pixel-only requests (for example "beach/ocean backdrop" when Instagram gives
    no useful alt text) are intentionally low-scored here so the browser limb can
    ask its vision arm instead of pretending DOM metadata saw the beach.
    """
    if not isinstance(candidate, dict):
        return 0.0
    tokens = _visible_media_query_tokens(query)
    text = _candidate_visible_text(candidate)
    score = 0.0
    for tok in tokens:
        if tok in text:
            score += 8.0 if tok in _VISIBLE_MEDIA_VISUAL_HINTS else 4.0

    q = str(query or "").lower()
    try:
        row = int(candidate.get("row") or 0)
        col = int(candidate.get("col") or 0)
        area = float(candidate.get("onscreen") or candidate.get("area") or 0.0)
    except Exception:
        row, col, area = 0, 0, 0.0
    if area > 0:
        score += min(2.0, area / 120000.0)
    if any(w in q for w in ("top", "upper", "first row")) and row == 1:
        score += 3.0
    if any(w in q for w in ("bottom", "lower", "last row")) and row >= 3:
        score += 3.0
    if "left" in q and col == 1:
        score += 2.0
    if "right" in q and col >= 4:
        score += 2.0
    if any(w in q for w in ("center", "middle")) and 2 <= col <= 4:
        score += 1.0
    return round(score, 4)


def _best_visible_media_candidate(query: str, candidates: list[dict]) -> tuple[dict | None, float]:
    best: dict | None = None
    best_score = 0.0
    for candidate in candidates or []:
        score = _score_visible_media_candidate(query, candidate)
        if score > best_score:
            best = candidate
            best_score = score
    return best, best_score


def _visible_media_query_needs_vision(query: str, best_score: float) -> bool:
    tokens = _visible_media_query_tokens(query)
    has_visual_hint = bool(tokens & _VISIBLE_MEDIA_VISUAL_HINTS)
    # Visual predicates like "ocean backdrop" are usually absent from IG DOM alt
    # text; when metadata did not strongly match, defer to pixels.
    return has_visual_hint and best_score < 8.0


def _parse_visible_media_selection(text: str) -> tuple[int, int]:
    """Parse row/column from a vision-arm JSON or natural-language answer."""
    raw = str(text or "").strip()
    if not raw:
        return 0, 0
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(raw[start:end + 1])
            row = int(data.get("row") or data.get("visible_row") or 0)
            col = int(data.get("col") or data.get("column") or data.get("visible_col") or 0)
            if row > 0 and col > 0:
                return row, col
    except Exception:
        pass
    m = re.search(r"\brow\s*(\d+)\D{0,20}\bcol(?:umn)?\s*(\d+)\b", raw, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\b(\d+)\s*(?:st|nd|rd|th)?\s+row\D{0,20}\b(\d+)\s*(?:st|nd|rd|th)?\s+col", raw, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def _candidate_by_row_col(candidates: list[dict], row: int, col: int) -> dict | None:
    for candidate in candidates or []:
        try:
            if int(candidate.get("row") or 0) == int(row) and int(candidate.get("col") or 0) == int(col):
                return candidate
        except Exception:
            continue
    return None


def _strict_grok_eye_selected(current_arm: str = "", current_model: str = "") -> bool:
    """True when the owner-selected cortex/eye is Grok, so browser pixels stay on Grok."""
    arm = str(current_arm or "").strip().lower()
    model = str(current_model or "").strip().lower()
    return arm == "grok_agent" or "grok" in model or "xai" in model


def _owner_browser_actions_from_dom_result(result: dict) -> list[tuple[str, dict, float]]:
    """Infer durable owner browser actions from one rendered DOM receipt."""
    if not isinstance(result, dict):
        return []
    actions: list[tuple[str, dict, float]] = []

    media = result.get("media") if isinstance(result.get("media"), dict) else {}
    status = str(media.get("status") or "").lower().strip()
    if status in {"playing", "paused"}:
        actions.append(
            (
                f"media_{status}",
                {
                    "video_count": media.get("video_count"),
                    "current_time": media.get("current_time"),
                    "duration": media.get("duration"),
                    "muted": media.get("muted"),
                },
                12.0,
            )
        )

    search = result.get("search") if isinstance(result.get("search"), dict) else {}
    query = " ".join(str(search.get("value") or "").split())
    if query:
        actions.append(
            (
                "search_query_visible",
                {
                    "query": query[:160],
                    "placeholder": str(search.get("placeholder") or "")[:80],
                },
                20.0,
            )
        )

    scroll = result.get("scroll") if isinstance(result.get("scroll"), dict) else {}
    try:
        pct = int(scroll.get("pct") or 0)
    except Exception:
        pct = 0
    if pct >= 25:
        bucket = min(100, (pct // 25) * 25)
        actions.append((f"scroll_depth_{bucket}", {"scroll_pct": pct}, 30.0))
    return actions


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
    media_error_observed = pyqtSignal(dict)

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
                try:
                    self.media_error_observed.emit(err)
                except Exception:
                    pass
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
        self._owner_browser_action_cache: dict[str, float] = {}
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
            # r231 (cowork): REVERT of r228. George was signed into Google in this browser;
            # r228's UA bump (120 + "SIFTA-Alice/1.0"  ->  clean "Chrome/124") and the new
            # persistent storage path broke a previously-working sign-in — Google flags a UA
            # whose claimed Chrome version mismatches the real QtWebEngine engine ("browser
            # may not be secure"), and the new storage path orphaned the existing Google
            # session cookies. Restored the EXACT UA + profile he was signed in with. Reels
            # stays a separate codec/handoff lane; it was never worth breaking sign-in.
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
            try:
                self._page.media_error_observed.connect(self._on_media_error_observed)
            except Exception:
                pass
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

    def _force_embedded_play(self) -> None:
        """r228: nudge <video> elements to play muted (autoplay-policy compliant).
        Helps a real <video> start; cannot help if the engine can't decode the codec."""
        if not self._view:
            return
        try:
            self._view.page().runJavaScript(
                "document.querySelectorAll('video').forEach(function(v){"
                "try{v.muted=true;var p=v.play();if(p&&p.catch)p.catch(function(){});}catch(e){}});"
            )
        except Exception as exc:
            print(f"[AliceBrowser] force embedded play failed: {exc}")

    def _install_instagram_media_tracker(self) -> None:
        """Remember the reel/post George clicked so native handoff opens that item."""
        if not self._view:
            return
        js = r"""
        (function () {
            if (window.__aliceInstagramMediaTrackerInstalled) return "already";
            window.__aliceInstagramMediaTrackerInstalled = true;
            window.__aliceLastInstagramMediaHref = window.__aliceLastInstagramMediaHref || "";
            function mediaHrefFrom(target) {
                var el = target;
                while (el && el !== document.documentElement) {
                    if (el.href && /\/(reel|p|tv)\//.test(el.href)) return el.href;
                    el = el.parentElement;
                }
                return "";
            }
            document.addEventListener("click", function (ev) {
                var href = mediaHrefFrom(ev.target);
                if (href) window.__aliceLastInstagramMediaHref = href;
            }, true);
            return "installed";
        })();
        """
        try:
            self._view.page().runJavaScript(js)
        except Exception as exc:
            print(f"[AliceBrowser] instagram media tracker failed: {exc}")

    def _resolve_native_media_handoff_url(self, callback) -> None:
        """Resolve active Instagram reel/post or signed MP4 before native handoff."""
        fallback = (self._current_url or self._url_bar.text() or "").strip()
        media_status = self.get_current_media_playback_status()
        if not self._view:
            callback(_choose_native_media_handoff_url({}, fallback_url=fallback, media_status=media_status))
            return
        js = r"""
        (function () {
            function firstHref(sel) {
                var el = document.querySelector(sel);
                return el && el.href ? el.href : "";
            }
            var videos = Array.prototype.slice.call(document.querySelectorAll("video"));
            var activeVideo = videos.find(function (v) {
                return v && !v.paused && !v.ended;
            }) || videos[0] || null;
            var info = {
                location: window.location.href || "",
                last_clicked: window.__aliceLastInstagramMediaHref || "",
                dialog_href: firstHref('[role="dialog"] a[href*="/reel/"], [role="dialog"] a[href*="/p/"], [role="dialog"] a[href*="/tv/"]'),
                active_href: firstHref('article a[href*="/reel/"], article a[href*="/p/"], article a[href*="/tv/"]'),
                first_reel_href: firstHref('a[href*="/reel/"]'),
                first_media_href: firstHref('a[href*="/p/"], a[href*="/tv/"]'),
                video_src: activeVideo ? (activeVideo.currentSrc || activeVideo.src || "") : ""
            };
            return JSON.stringify(info);
        })();
        """

        def _done(res):
            import json as _j
            try:
                info = _j.loads(res) if res else {}
            except Exception:
                info = {}
            callback(_choose_native_media_handoff_url(info, fallback_url=fallback, media_status=media_status))

        try:
            self._view.page().runJavaScript(js, _done)
        except Exception:
            callback(_choose_native_media_handoff_url({}, fallback_url=fallback, media_status=media_status))

    def _note_media_error_for_handoff(self, err: dict | None = None) -> None:
        """React when a video fails after loadFinished, not only during load."""
        media_status = self.get_current_media_playback_status()
        try:
            from System.swarm_media_codec_bridge import append_bridge_receipt, media_status_summary

            append_bridge_receipt(
                {
                    "ts": time.time(),
                    "truth_label": "SIFTA_MEDIA_CODEC_BRIDGE_V1",
                    "action": "embedded_media_error_observed",
                    "source": "alice_browser_media_error_signal",
                    "url": self._current_url,
                    "error": dict(err or {}),
                    "media_status": media_status,
                    "summary": media_status_summary(media_status, url=self._current_url),
                },
                state_dir=_STATE,
            )
        except Exception:
            pass
        if media_status.get("native_handoff_available"):
            self._native_media_btn.setStyleSheet("background:#ffcc00; color:black;")
            self._native_media_btn.setToolTip(
                "Embedded Qt cannot decode this video stream; open this reel/media in the native playback path"
            )
            self._status.showMessage(
                "⚠️ Embedded video decode failed here. Press ▶ to open the active reel/media natively.",
                12000,
            )

    def _probe_media_codecs(self) -> None:
        """r228 (honest, §7.12): record whether this QtWebEngine build can decode H.264/AAC.
        Embedded reels need proprietary codecs the standard PyQt6 wheel often omits. The
        verdict goes to .sifta_state/browser_codec_probe.jsonl so the owner knows whether
        embedded playback is even possible, or the native ▶ handoff is the only honest path."""
        if not self._view:
            return
        js = (
            "(function(){var v=document.createElement('video');return JSON.stringify({"
            "h264:v.canPlayType('video/mp4; codecs=\"avc1.42E01E\"'),"
            "aac:v.canPlayType('audio/mp4; codecs=\"mp4a.40.2\"'),"
            "webm_vp9:v.canPlayType('video/webm; codecs=\"vp9\"')});})()"
        )

        def _on_result(res):
            import json as _j
            import time as _t
            try:
                caps = _j.loads(res) if res else {}
            except Exception:
                caps = {"raw": str(res)}
            h264 = str(caps.get("h264") or "")
            ok = h264 in ("probably", "maybe")
            verdict = ("embedded H.264 playback AVAILABLE" if ok else
                       "NO embedded H.264 — reels cannot decode in-limb; native ▶ handoff is the path")
            print(f"[AliceBrowser] codec probe: {caps} -> {verdict}")
            try:
                p = _STATE / "browser_codec_probe.jsonl"
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("a", encoding="utf-8") as f:
                    f.write(_j.dumps({"ts": _t.time(), "caps": caps, "h264_ok": ok,
                                      "verdict": verdict,
                                      "truth_label": "QTWEBENGINE_CODEC_PROBE_V1"}) + "\n")
            except Exception:
                pass

        try:
            self._view.page().runJavaScript(js, _on_result)
        except Exception as exc:
            print(f"[AliceBrowser] codec probe failed: {exc}")

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
        self._resolve_native_media_handoff_url(self._open_native_media_url)

    def _open_native_media_url(self, url: str) -> None:
        url = (url or self._current_url or self._url_bar.text() or "").strip()
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

        # r222 Lane B — owner browser behaviour trail (Alice awareness of George's hands in her body)
        try:
            from System.swarm_architect_day_segments import log_owner_browser_behaviour
            log_owner_browser_behaviour(
                url=url_str,
                title=self._view.title() if self._view else "",
                action="navigate_or_spa_change",
                source="alice_browser_widget",
            )
        except Exception as _e:
            pass  # never break the limb for a diary row
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

    @pyqtSlot(dict)
    def _on_media_error_observed(self, err: dict):
        self._note_media_error_for_handoff(err)

    @pyqtSlot(bool)
    def _on_load_finished(self, ok: bool):
        url = self._current_url
        title = self._view.title() if self._view else ""
        duration = round(time.time() - self._page_load_ts, 2)
        self._publish_browser_context(source="load_finished")
        self._write_address_context(source="load_finished", duration_s=duration)

        # r222 Lane B — full load = stronger "George is now here doing this" signal
        if ok and url and url not in (_HOME_URL, "sifta://home", "about:blank", ""):
            try:
                from System.swarm_architect_day_segments import log_owner_browser_behaviour
                log_owner_browser_behaviour(
                    url=url,
                    title=title,
                    action="load_finished",
                    source="alice_browser_widget",
                )
            except Exception:
                pass
        if ok and url and url not in (_HOME_URL, "sifta://home", "about:blank", ""):
            import threading as _th
            def _async_receipt(_u=url, _t=title, _d=duration):
                try:
                    _write_browse_receipt(_u, _t, duration_s=_d)
                except Exception as _e:
                    print(f"[AliceBrowser] receipt write failed: {_e}")
            _th.Thread(target=_async_receipt, daemon=True, name="BrowseReceipt").start()

            if self._view is not None:
                self._install_instagram_media_tracker()
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
                QTimer.singleShot(800, self._force_embedded_play)

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

    def _log_owner_browser_behaviour(
        self,
        action: str,
        *,
        url: str = "",
        title: str = "",
        extra: dict | None = None,
        dedupe_s: float = 8.0,
    ) -> bool:
        """Record George's browser action without spamming repeated DOM ticks."""
        clean_url = str(url or self._current_url or "").strip()
        if not clean_url or clean_url in (_HOME_URL, "sifta://home", "about:blank", ""):
            return False
        clean_title = str(title or self._current_browser_title() or "").strip()
        extra = dict(extra or {})
        key = json.dumps(
            {
                "url": clean_url,
                "action": str(action or ""),
                "title": clean_title[:120],
                "extra": extra,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        now = time.time()
        cache = getattr(self, "_owner_browser_action_cache", {})
        if now - float(cache.get(key, 0.0) or 0.0) < dedupe_s:
            return False
        cache[key] = now
        self._owner_browser_action_cache = cache
        try:
            from System.swarm_architect_day_segments import log_owner_browser_behaviour

            log_owner_browser_behaviour(
                url=clean_url,
                title=clean_title,
                action=str(action or "browser_action"),
                source="alice_browser_widget",
                extra=extra,
            )
            return True
        except Exception:
            return False

    def _log_owner_browser_dom_actions(self, result: dict, *, url: str, title: str) -> None:
        """Infer finer owner activity from the rendered page state."""
        for action, extra, dedupe_s in _owner_browser_actions_from_dom_result(result):
            self._log_owner_browser_behaviour(
                action,
                url=url,
                title=title,
                extra=extra,
                dedupe_s=dedupe_s,
            )

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
            var videos = Array.prototype.slice.call(document.querySelectorAll('video'));
            var activeVideo = null;
            for (var vi = 0; vi < videos.length; vi++) {
                var v = videos[vi];
                if (v && !v.paused && !v.ended && v.readyState > 0) {
                    activeVideo = v;
                    break;
                }
            }
            var primaryVideo = activeVideo || videos[0] || null;
            var media = { status: 'no_media', playing: false, video_count: videos.length };
            if (primaryVideo) {
                var playing = !!activeVideo;
                media = {
                    status: playing ? 'playing' : (primaryVideo.ended ? 'ended' : 'paused'),
                    playing: playing,
                    video_count: videos.length,
                    current_time: Math.round((primaryVideo.currentTime || 0) * 10) / 10,
                    duration: isFinite(primaryVideo.duration) ? Math.round(primaryVideo.duration * 10) / 10 : null,
                    muted: !!primaryVideo.muted,
                    ready_state: primaryVideo.readyState,
                    src: primaryVideo.currentSrc || primaryVideo.src || ''
                };
            }
            var searchInput = document.querySelector(
                'input[type="search"], input[aria-label*="Search" i], input[placeholder*="Search" i], textarea[aria-label*="Search" i]'
            );
            var search = searchInput ? {
                value: (searchInput.value || '').trim().slice(0, 160),
                placeholder: (searchInput.getAttribute('placeholder') || searchInput.getAttribute('aria-label') || '').trim().slice(0, 80)
            } : {};
            return {
                text: body.slice(0, 4000),
                headings: heads, links: links, buttons: btns, images: imgs, og: og,
                comments: comments,
                media: media,
                search: search,
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
                    media_playback = result.get("media") if isinstance(result.get("media"), dict) else {}
                    if media_playback:
                        try:
                            media_playback = dict(media_playback)
                            media_playback["codec_status"] = self.get_current_media_playback_status()
                        except Exception:
                            pass
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
                        media_playback=media_playback,
                        source="dom",
                        state_dir=_STATE,
                    )
                    self._log_owner_browser_dom_actions(result, url=u, title=t)
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

    def _run_javascript_sync(self, js: str, *, wait_ms: int = 1200):
        """Run small browser-limb JS and wait for its result."""
        if not self._view:
            return None
        box = {"done": False, "result": None}
        loop = QEventLoop(self)

        def _done(result):
            box["done"] = True
            box["result"] = result
            try:
                loop.quit()
            except Exception:
                pass

        try:
            self._view.page().runJavaScript(js, _done)
            timeout = QTimer(self)
            timeout.setSingleShot(True)
            timeout.timeout.connect(loop.quit)
            timeout.start(max(100, int(wait_ms)))
            if not box["done"]:
                loop.exec()
            timeout.stop()
        except Exception:
            return None
        return box.get("result")

    def _visible_instagram_media_candidates(self) -> dict:
        """Return visible Instagram profile/post tiles with stable row/col labels."""
        js = r"""
        (function () {
            var vw = window.innerWidth || 0, vh = window.innerHeight || 0;
            function clean(s) { return (s || '').toString().trim().replace(/\s+/g, ' ').slice(0, 260); }
            function area(r) {
                var ow = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0));
                var oh = Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
                return Math.round(ow * oh);
            }
            var anchors = Array.prototype.slice.call(
                document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"], a[href*="/tv/"]')
            );
            var out = [];
            for (var i = 0; i < anchors.length; i++) {
                var a = anchors[i];
                var r = a.getBoundingClientRect();
                var onscreen = area(r);
                if (!r || r.width < 40 || r.height < 40 || onscreen < 1200) continue;
                var img = a.querySelector('img');
                var href = a.href || a.getAttribute('href') || '';
                if (href && href.charAt(0) === '/') href = location.origin + href;
                out.push({
                    index: out.length,
                    href: href,
                    text: clean(a.innerText || ''),
                    aria: clean(a.getAttribute('aria-label') || ''),
                    alt: img ? clean(img.alt || '') : '',
                    src: img ? (img.currentSrc || img.src || '') : '',
                    x: Math.round(r.left), y: Math.round(r.top),
                    w: Math.round(r.width), h: Math.round(r.height),
                    center_x: Math.round(r.left + r.width / 2),
                    center_y: Math.round(r.top + r.height / 2),
                    onscreen: onscreen
                });
            }
            out.sort(function (a, b) { return (a.y - b.y) || (a.x - b.x); });
            var row = 0, col = 0, lastY = null;
            for (var j = 0; j < out.length; j++) {
                var c = out[j];
                if (lastY === null || Math.abs(c.y - lastY) > Math.max(32, c.h * 0.35)) {
                    row += 1; col = 1; lastY = c.y;
                } else {
                    col += 1;
                }
                c.row = row;
                c.col = col;
            }
            return {
                location: location.href,
                title: document.title || '',
                viewport: {w: vw, h: vh},
                candidates: out.slice(0, 80)
            };
        })();
        """
        result = self._run_javascript_sync(js, wait_ms=1400)
        return result if isinstance(result, dict) else {}

    def _select_visible_media_candidate_with_vision(
        self,
        query: str,
        candidates: list[dict],
        *,
        current_arm: str = "",
        current_model: str = "",
    ) -> dict:
        """Ask the current cortex's eye to choose a visible grid tile by row/col."""
        if not candidates:
            return {}
        img_path = ""
        try:
            img_path = self._capture_viewport_image(expected_url=self._current_url)
        except Exception:
            img_path = ""
        if not img_path or not Path(img_path).exists():
            return {}

        try:
            from System.swarm_browser_photo_description import extract_arm_final_text
            from System.swarm_cortex_capabilities import pick_vision_arm, record_cortex_arm_habit
        except Exception:
            return {}

        table = "\n".join(
            f"row={int(c.get('row') or 0)} col={int(c.get('col') or 0)} "
            f"href={str(c.get('href') or '')[:90]} alt={str(c.get('alt') or '')[:80]}"
            for c in candidates[:30]
        )
        prompt = (
            "Look at the image at this exact path: "
            f"{img_path}\n"
            "It is a screenshot of Instagram showing a visible grid of square media tiles. "
            "The owner wants this visible tile: "
            f"{query!r}.\n"
            "Count only the visible Instagram grid tiles, top-to-bottom and left-to-right. "
            "Return ONLY compact JSON with integer row and col, for example "
            "{\"row\":3,\"col\":4,\"reason\":\"ocean backdrop\"}. "
            "If no tile matches, return {\"row\":0,\"col\":0,\"reason\":\"no match\"}.\n"
            "Candidate coordinates from the DOM:\n"
            f"{table}"
        )

        down: set[str] = set()
        strict_grok_eye = _strict_grok_eye_selected(current_arm, current_model)
        pick = pick_vision_arm(
            current_arm=current_arm,
            current_model=current_model,
            unavailable=(),
            local_image_required=True,
        )
        arm = "grok_agent" if strict_grok_eye else str(pick.get("selected_arm") or current_arm or "").strip()
        for _ in range(3):
            if not arm or arm in down:
                break
            if arm == "grok_agent":
                try:
                    from System.xai_grok_oauth_organ import preflight_grok_vision_key
                    has_key, _msg = preflight_grok_vision_key()
                    if not has_key:
                        if strict_grok_eye:
                            record_cortex_arm_habit(
                                "grok_agent",
                                cortex_model=current_model,
                                task="browser_visible_media_selection",
                                ok=False,
                                status="grok_eye_key_missing",
                                reason="selected_grok_eye_has_no_oauth_credential",
                                state_dir=_STATE,
                                meta={"image_ref": img_path, "query": query[:180]},
                            )
                            return {}
                        down.add(arm)
                        arm = "ollama_vision_agent"
                        continue
                except Exception:
                    pass
            try:
                if arm == "ollama_vision_agent":
                    from System.swarm_ollama_vision_arm import describe_image_local
                    arm_result = describe_image_local(img_path, prompt, timeout_s=300)
                elif arm == "qwen_agent":
                    from System.swarm_fireworks_vision_arm import describe_image_fireworks
                    arm_result = describe_image_fireworks(img_path, prompt, state_dir=_STATE, timeout_s=300)
                elif arm == "grok_agent":
                    # r236: grok's eye via the OAuth-valid /v1/responses endpoint (NOT
                    # grok_chat's /v1/chat/completions, which 403s on the OAuth token).
                    from System.xai_grok_oauth_organ import describe_image_via_oauth
                    arm_result = describe_image_via_oauth(
                        img_path,
                        prompt,
                        model=current_model or "grok-4",
                        timeout_s=300,
                    )
                else:
                    from System.swarm_agent_arm_launcher import ask_agent_arm
                    arm_result = ask_agent_arm(
                        arm,
                        prompt,
                        state_dir=_STATE,
                        timeout_s=300,
                        image_path=img_path,
                    )
                raw = extract_arm_final_text(getattr(arm_result, "output", "") or "")
                ok = bool(getattr(arm_result, "ok", False))
                row, col = _parse_visible_media_selection(raw)
                record_cortex_arm_habit(
                    arm,
                    cortex_model=current_model,
                    task="browser_visible_media_selection",
                    ok=bool(ok and row and col),
                    status="selected" if ok and row and col else str(getattr(arm_result, "status", "") or "failed"),
                    reason=f"row={row} col={col}",
                    state_dir=_STATE,
                    meta={"image_ref": img_path, "query": query[:180]},
                )
                chosen = _candidate_by_row_col(candidates, row, col)
                if ok and chosen:
                    chosen = dict(chosen)
                    chosen["vision_selected_by"] = arm
                    chosen["vision_reason"] = raw[:240]
                    return chosen
            except Exception:
                pass
            down.add(arm)
            if strict_grok_eye:
                break
            try:
                pick = pick_vision_arm(
                    current_arm="",
                    current_model=current_model,
                    unavailable=tuple(sorted(down)),
                    local_image_required=True,
                )
                arm = str(pick.get("selected_arm") or "").strip()
            except Exception:
                break
        return {}

    def _click_visible_media_candidate(self, candidate: dict) -> dict:
        href = str((candidate or {}).get("href") or "")
        index = int((candidate or {}).get("index") or 0)
        js = f"""
        (function () {{
            var targetHref = {json.dumps(href)};
            var targetIndex = {json.dumps(index)};
            var nodes = Array.prototype.slice.call(
                document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"], a[href*="/tv/"]')
            );
            var visible = [];
            var vw = window.innerWidth || 0, vh = window.innerHeight || 0;
            function onscreen(el) {{
                var r = el.getBoundingClientRect();
                var ow = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0));
                var oh = Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
                return Math.round(ow * oh);
            }}
            for (var i = 0; i < nodes.length; i++) {{
                if (onscreen(nodes[i]) >= 1200) visible.push(nodes[i]);
            }}
            var el = null;
            for (var j = 0; j < visible.length; j++) {{
                if ((visible[j].href || '') === targetHref) {{ el = visible[j]; break; }}
            }}
            if (!el && visible[targetIndex]) el = visible[targetIndex];
            if (!el) return {{clicked:false, reason:'candidate_not_found', href:targetHref}};
            try {{ window.__aliceLastInstagramMediaHref = el.href || targetHref; }} catch (e) {{}}
            try {{ el.scrollIntoView({{block:'center', inline:'center', behavior:'instant'}}); }} catch (e) {{}}
            var r = el.getBoundingClientRect();
            var cx = Math.round(r.left + r.width / 2), cy = Math.round(r.top + r.height / 2);
            ['mouseover','mousedown','mouseup','click'].forEach(function (name) {{
                try {{
                    el.dispatchEvent(new MouseEvent(name, {{
                        bubbles:true, cancelable:true, view:window, clientX:cx, clientY:cy
                    }}));
                }} catch (e) {{}}
            }});
            try {{ el.click(); }} catch (e) {{}}
            return {{clicked:true, href:el.href || targetHref, x:cx, y:cy}};
        }})();
        """
        result = self._run_javascript_sync(js, wait_ms=900)
        return result if isinstance(result, dict) else {"clicked": False, "reason": "no_js_result"}

    def open_visible_photo_matching_text(
        self,
        query: str,
        *,
        current_arm: str = "",
        current_model: str = "",
    ) -> dict:
        """Pick and open a visible Instagram photo/reel/post named by the owner.

        This is the browser-limb path for turns like "open the photo against the
        ocean backdrop" — it must never route to the SIFTA app launcher just
        because the word "open" appears.
        """
        if not self._view:
            return {"status": "failed", "reason": "no_web_view"}
        candidates_result = self._visible_instagram_media_candidates()
        candidates = candidates_result.get("candidates") if isinstance(candidates_result, dict) else []
        if not isinstance(candidates, list) or not candidates:
            return {"status": "failed", "reason": "no_visible_instagram_media", "candidate_count": 0}

        candidate, score = _best_visible_media_candidate(query, candidates)
        used_vision = False
        needs_vision = _visible_media_query_needs_vision(query, score)
        if needs_vision:
            vision_candidate = self._select_visible_media_candidate_with_vision(
                query,
                candidates,
                current_arm=current_arm,
                current_model=current_model,
            )
            if vision_candidate:
                candidate = vision_candidate
                used_vision = True
                score = max(score, 20.0)
            elif score < 8.0:
                return {
                    "status": "failed",
                    "reason": "vision_needed_for_visual_tile_match",
                    "candidate_count": len(candidates),
                }

        if not candidate or score <= 0:
            return {
                "status": "failed",
                "reason": "no_matching_visible_media",
                "candidate_count": len(candidates),
            }

        clicked = self._click_visible_media_candidate(candidate)
        ok = bool(clicked.get("clicked"))
        if ok:
            try:
                from System.swarm_browser_photo_description import mark_frame_changed
                mark_frame_changed(url=self._current_url, state_dir=_STATE)
            except Exception:
                pass
            # Let the Instagram modal/post settle before the cortex asks for pixels.
            try:
                loop = QEventLoop(self)
                QTimer.singleShot(950, loop.quit)
                loop.exec()
            except Exception:
                pass
            try:
                self.refresh_current_page_state(wait_ms=700)
            except Exception:
                pass
        return {
            "status": "opened" if ok else "failed",
            "reason": "" if ok else str(clicked.get("reason") or "click_failed"),
            "href": str(clicked.get("href") or candidate.get("href") or ""),
            "row": candidate.get("row"),
            "col": candidate.get("col"),
            "score": score,
            "used_vision": used_vision,
            "vision_selected_by": candidate.get("vision_selected_by", ""),
            "vision_reason": candidate.get("vision_reason", ""),
            "candidate_count": len(candidates),
        }

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
        failover (with an owner diary note) if it cannot see or its API died.

        r236: if the owner-selected cortex/eye is Grok, this is strict: Grok OAuth
        vision or an honest Grok failure. No silent Claude/local cover answer."""
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

            strict_grok_eye = _strict_grok_eye_selected(current_arm, current_model)
            pick = pick_vision_arm(
                current_arm=current_arm,
                current_model=current_model,
                unavailable=unavailable,
                local_image_required=True,
            )
            if strict_grok_eye:
                pick = {
                    **pick,
                    "selected_arm": "grok_agent",
                    "reason": "selected_grok_cortex_strict_oauth_eye",
                    "switched": False,
                    "fallbacks": [],
                    "diary_note": (
                        "Grok is my selected cortex/eye for this photo, so I must use "
                        "grok_agent through xAI OAuth and not cover it with Claude."
                    ),
                }
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

            preflight_notes: list[str] = []
            # r225 / r226: Grok eye preflight — honest key check before burning tokens or surfacing opaque error.
            # r236: when Grok itself is selected, missing OAuth is a Grok failure, not a license
            # to switch vendors and pretend the selected eye saw the pixels.
            if arm == "grok_agent":
                try:
                    from System.xai_grok_oauth_organ import preflight_grok_vision_key, GROK_VISION_KEY_MISSING_MESSAGE
                    has_key, msg = preflight_grok_vision_key()
                    if not has_key:
                        if strict_grok_eye:
                            result.update({
                                "status": "grok_eye_key_missing",
                                "arm": "grok_agent",
                                "description": "",
                                "error_summary": GROK_VISION_KEY_MISSING_MESSAGE,
                                "attempts": [{
                                    "arm": "grok_agent",
                                    "ok": False,
                                    "status": "grok_eye_key_missing",
                                    "source": source,
                                    "receipt_id": "",
                                }],
                                "diary_note": (
                                    (msg or GROK_VISION_KEY_MISSING_MESSAGE)
                                    + " I did not switch to Claude or a local eye because Grok is selected."
                                ),
                            })
                            record_cortex_arm_habit(
                                "grok_agent",
                                cortex_model=current_model,
                                task="browser_photo_local_image",
                                ok=False,
                                status="grok_eye_key_missing",
                                reason="selected_grok_eye_has_no_oauth_credential",
                                state_dir=_STATE,
                                meta={"image_ref": img_path, "source": source},
                            )
                            record_photo_description(
                                url, description="", arm="grok_agent",
                                image_ref=img_path, status="grok_eye_key_missing",
                                source=source, state_dir=_STATE
                            )
                            return result
                        # Write a clear stigmergic trace the organism can read
                        try:
                            from System.swarm_cortex_failover_reflex import record_cortex_failover
                            record_cortex_failover(
                                from_arm="grok_agent",
                                to_arm="ollama_vision_agent",
                                reason="grok_eye_key_missing",
                                state_dir=_STATE,
                            )
                        except Exception:
                            pass
                        # Honest first-person report for the cortex
                        result["description"] = GROK_VISION_KEY_MISSING_MESSAGE
                        record_photo_description(
                            url, description=GROK_VISION_KEY_MISSING_MESSAGE, arm="grok_agent",
                            image_ref=img_path, status="grok_eye_key_missing", source=source, state_dir=_STATE
                        )
                        # Fail over to local eye for this turn
                        preflight_notes.append(msg or GROK_VISION_KEY_MISSING_MESSAGE)
                        arm = "ollama_vision_agent"
                        result["arm"] = arm
                except Exception as _pf_exc:
                    print(f"[AliceBrowser] grok eye preflight failed to run: {_pf_exc}")

            prompt = (
                "Look at the image at this exact path: "
                f"{img_path}\n"
                "It is a screenshot of a web page. Describe the MAIN subject of the photo — whatever it is: "
                "a person, product, vehicle, animal, building, food, plant, or any object (ignore the "
                "surrounding browser/app interface, menus, and comment sidebar). Be concise — 2 short "
                "sentences, under 50 words: WHAT it is, its key visible attributes (form, colour, material; "
                "clothing if it is a person), and the setting; nothing else. State only what is clearly "
                "visible — no speculation, no hedging, no lists."
            )
            def _call_vision_arm(selected_arm: str) -> dict:
                call_source = source
                # George r210: a LOCAL ollama cortex looks with its OWN local eye.
                if selected_arm == "ollama_vision_agent":
                    from System.swarm_ollama_vision_arm import describe_image_local
                    arm_result = describe_image_local(img_path, prompt, timeout_s=300)
                    call_source = "local_ollama_vision_arm"
                elif selected_arm == "qwen_agent":
                    # George r214: Kimi K2.6 cortex sees with Kimi's OWN Fireworks API.
                    from System.swarm_fireworks_vision_arm import describe_image_fireworks
                    arm_result = describe_image_fireworks(img_path, prompt, state_dir=_STATE, timeout_s=300)
                    call_source = "kimi_fireworks_vision_arm"
                elif selected_arm == "grok_agent":
                    # George r236: grok's eye via the OAuth-valid /v1/responses endpoint.
                    # grok_chat's /v1/chat/completions 403s on the OAuth token (it wants an
                    # xai- API key); /v1/responses accepts the OAuth bearer.
                    from System.xai_grok_oauth_organ import describe_image_via_oauth
                    arm_result = describe_image_via_oauth(
                        img_path,
                        prompt,
                        model=current_model or "grok-4",
                        timeout_s=300,
                    )
                    call_source = "grok_oauth_responses_vision_arm"
                else:
                    model_hint = ""
                    arm_result = ask_agent_arm(
                        selected_arm,
                        prompt,
                        state_dir=_STATE,
                        timeout_s=300,
                        image_path=img_path,
                        model_hint=model_hint,
                    )
                clean_text = extract_arm_final_text(getattr(arm_result, "output", "") or "")
                asked_for_image = looks_like_non_visual_arm_reply(clean_text)
                success = bool(getattr(arm_result, "ok", False)) and bool(clean_text) and not asked_for_image
                status = (
                    "described"
                    if success else (
                        "non_visual_reply"
                        if asked_for_image else str(getattr(arm_result, "status", "") or "failed")
                    )
                )
                reason = (
                    "arm_returned_visual_description"
                    if success else (
                        "arm_asked_for_image_contents"
                        if asked_for_image else "arm_failed_or_empty"
                    )
                )
                return {
                    "arm": selected_arm,
                    "arm_res": arm_result,
                    "text": clean_text,
                    "non_visual": asked_for_image,
                    "ok": success,
                    "status": status,
                    "reason": reason,
                    "source": call_source,
                }

            attempts: list[dict] = []
            down = {str(a or "").strip() for a in (unavailable or ()) if str(a or "").strip()}
            diary_notes = list(preflight_notes)
            if pick.get("diary_note"):
                diary_notes.append(str(pick.get("diary_note") or "").strip())
            current_attempt = arm
            final = None
            while current_attempt:
                attempt = _call_vision_arm(current_attempt)
                attempts.append(attempt)
                record_cortex_arm_habit(
                    current_attempt,
                    cortex_model=current_model,
                    task="browser_photo_local_image",
                    ok=bool(attempt.get("ok")),
                    status=str(attempt.get("status") or "failed"),
                    reason=str(attempt.get("reason") or "arm_failed_or_empty"),
                    state_dir=_STATE,
                    meta={
                        "receipt_id": getattr(attempt.get("arm_res"), "receipt_id", ""),
                        "returncode": getattr(attempt.get("arm_res"), "returncode", None),
                        "source": attempt.get("source"),
                        "attempt_index": len(attempts),
                    },
                )
                final = attempt
                if attempt.get("ok"):
                    break
                down.add(current_attempt)
                if strict_grok_eye:
                    diary_notes.append(
                        f"my selected Grok eye failed on this frame ({attempt.get('status')}); "
                        "I did not switch to Claude, Codex, Kimi, or local vision because Grok is selected."
                    )
                    break
                next_pick = pick_vision_arm(
                    current_arm="",
                    current_model=current_model,
                    unavailable=tuple(sorted(down)),
                    local_image_required=True,
                )
                next_arm = str(next_pick.get("selected_arm") or "").strip()
                if not next_arm or next_arm in down:
                    break
                diary_notes.append(
                    f"my {current_attempt} eye failed on this frame "
                    f"({attempt.get('status')}); I switched to {next_arm} for the pixels "
                    "and still let the cortex compose the answer."
                )
                current_attempt = next_arm
                result["arm"] = current_attempt

            arm = str((final or {}).get("arm") or arm)
            arm_res = (final or {}).get("arm_res")
            text = str((final or {}).get("text") or "")
            non_visual = bool((final or {}).get("non_visual"))
            ok = bool((final or {}).get("ok"))
            source = str((final or {}).get("source") or source)
            result["arm"] = arm
            failed_status = "grok_eye_failed" if strict_grok_eye and arm == "grok_agent" else "failed"
            record_photo_description(
                url, description=text if ok else "", arm=arm, image_ref=img_path,
                status="described" if ok else failed_status, source=source, state_dir=_STATE,
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
            result["status"] = "described" if ok else failed_status
            result["description"] = text if ok else ""
            result["error_summary"] = "" if ok else text[:500]
            result["attempts"] = [
                {
                    "arm": str(a.get("arm") or ""),
                    "ok": bool(a.get("ok")),
                    "status": str(a.get("status") or ""),
                    "source": str(a.get("source") or ""),
                    "receipt_id": getattr(a.get("arm_res"), "receipt_id", ""),
                }
                for a in attempts
            ]
            notes = [n for n in diary_notes if n]
            if notes:
                result["diary_note"] = " ".join(notes)
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
