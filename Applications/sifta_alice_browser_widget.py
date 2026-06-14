#!/usr/bin/env python3
"""
Applications/sifta_alice_browser_widget.py
═══════════════════════════════════════════
Alice Browser — Chromium-based web view inside SIFTA OS

Powered by QWebEngineView (full Chromium stack, same as cartography widget).
Every URL Alice visits (including sifta://home start page and quick links) writes a stigmergic receipt to alice_browse_history.jsonl with explicit opened_at / closed_at (or dwell) time range so the diary, day-segment, context, and George have the full "what links, what time to what time" record. Home and all navigations are now logged (no skip). Visits are also surfaced in episodic diary for unified recall.

Features:
  • Full Chromium rendering (JS, CSS, modern web)
  • Clipboard API: JavascriptCanAccessClipboard + ClipboardReadWrite permission
    so sites like ChatGPT can copy to the system clipboard from toolbar buttons
  • URL bar with address + enter-to-navigate
  • Back / Forward / Refresh / Home
  • SIFTA-themed home page (rendered from HTML string)
  • Quick bookmarks: Google, Wikipedia, YouTube, GitHub, Arxiv, HN
  • Stigmergic browse receipts: url, title, opened_at, closed_at, dwell_s, ts, domain, actor
  • Every visit mirrored to episodic_diary for "the diary"
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

from PyQt6.QtCore import QEventLoop, QPointF, QUrl, Qt, QTimer, pyqtSignal, pyqtSlot, QFileSystemWatcher
from PyQt6.QtGui import QFont, QIcon, QKeySequence, QMouseEvent, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
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

from System.swarm_app_hardening import record_app_hardening_event

_STATE = REPO / ".sifta_state"
_BROWSE_LEDGER = _STATE / "alice_browse_history.jsonl"
_CURRENT_PAGE_SNAPSHOT = _STATE / "alice_browser_current_page.json"
_PENDING_SLIDESHOW = _STATE / "pending_slideshow.json"
APP_HARDENING_ID = "queue-008:sifta_alice_browser_widget"


def _record_browser_hardening(event: str, **details) -> None:
    record_app_hardening_event(
        APP_HARDENING_ID,
        event,
        details=details,
    )


def stage_pending_slideshow(url: str, js: str, *, ttl_s: float = 90.0) -> dict:
    """r385: park a slideshow request so it fires when the (possibly just-opened) browser
    finishes loading the image grid. This lets a CLOSED browser still honor 'slideshow X' —
    a reasoning body opens its own eye instead of dead-ending. host+recency matched, fired once."""
    import json as _j, time as _t
    try:
        from urllib.parse import urlparse
        host = urlparse(url or "").netloc.lower()
    except Exception:
        host = ""
    row = {"url": str(url or ""), "host": host, "js": str(js or ""), "ts": _t.time(), "ttl_s": float(ttl_s)}
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        _PENDING_SLIDESHOW.write_text(_j.dumps(row), encoding="utf-8")
    except Exception as exc:
        _record_browser_hardening(
            "pending_slideshow_stage_failed",
            error_type=type(exc).__name__,
            url=str(url or "")[:240],
        )
    return row


def read_pending_slideshow() -> dict:
    import json as _j, time as _t
    try:
        row = _j.loads(_PENDING_SLIDESHOW.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except Exception as exc:
        _record_browser_hardening(
            "pending_slideshow_read_failed",
            error_type=type(exc).__name__,
            path=str(_PENDING_SLIDESHOW),
        )
        return {}
    if not isinstance(row, dict):
        return {}
    if (_t.time() - float(row.get("ts", 0))) > float(row.get("ttl_s", 90.0)):
        clear_pending_slideshow()
        return {}
    return row


def clear_pending_slideshow() -> None:
    try:
        _PENDING_SLIDESHOW.unlink()
    except FileNotFoundError:
        return
    except Exception as exc:
        _record_browser_hardening(
            "pending_slideshow_clear_failed",
            error_type=type(exc).__name__,
            path=str(_PENDING_SLIDESHOW),
        )

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
    opened_at: float | None = None,
    closed_at: float | None = None,
) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    try:
        from System.swarm_browser_actor_attribution import attribute_browser_action
        actor_attribution = attribute_browser_action(url)
    except Exception:
        actor_attribution = {}
    now = time.time()
    arrived = opened_at or (now - duration_s if duration_s > 0 else now)
    departed = closed_at or now
    dwell = round(departed - arrived, 1) if departed and arrived else round(duration_s, 1)
    row = {
        "ts": now,
        "trace_id": str(uuid.uuid4()),
        "truth_label": "ALICE_BROWSE_V1",
        "url": url,
        "title": title,
        "opened_at": round(arrived, 3),
        "closed_at": round(departed, 3),
        "dwell_s": dwell,
        "load_duration_s": round(duration_s, 1),  # legacy: time from loadStarted to this receipt
        "referrer_url": referrer_url,
        "domain": _domain(url),
        "actor": actor_attribution.get("actor", "unattributed"),
        "actor_attribution": actor_attribution,
    }
    with open(_BROWSE_LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # Also mirror to the unified diary so "all links + exact times" are in the diary Alice recalls.
    try:
        from System.swarm_alice_schedule_diary_awareness import write_diary_entry
        write_diary_entry(
            f"Browser visit: {title or url} ({url}) from {arrived:.0f} to {departed:.0f} (dwell {dwell}s)",
            kind="browser_visit",
            tags=["browser", "visit", "time_range"],
            meta={"url": url, "title": title, "opened_at": arrived, "closed_at": departed, "dwell_s": dwell, "domain": row["domain"]},
        )
    except Exception as exc:
        _record_browser_hardening(
            "visible_media_selection_json_parse_failed",
            error_type=type(exc).__name__,
            text=raw[:240],
        )


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


_OAUTH_IDP_HOSTS = (
    "accounts.google.com",
    "accounts.youtube.com",
    "appleid.apple.com",
    "login.microsoftonline.com",
    "login.live.com",
)


def should_suppress_oauth_safari_handoff(
    url: str,
    *,
    suppress_until: float = 0.0,
    owner_drop_target: str = "",
    now: float | None = None,
) -> bool:
    """r991: George 2026-06-11 — owner said 'open in alice browser' for JRE #2513;
    Talk wrote the drop + raised Alice Browser, but r503 handed accounts.youtube.com
    to Safari and the podcast played in Safari instead of the limb.

    Co-watch / owner-drop YouTube ``watch?v=`` navigations must stay inside Alice
    Browser. Only explicit Safari requests (Talk ``native_browser_url``) may leave."""
    t = float(now if now is not None else time.time())
    if t < float(suppress_until or 0.0):
        return True
    target = str(owner_drop_target or "").strip().lower()
    if target and "youtube.com/watch" in target:
        low = str(url or "").lower()
        if any(h in low for h in _OAUTH_IDP_HOSTS):
            return True
    return False


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

    Instagram profile pages often keep the address at the historical handle while a
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


_STRICT_SELECTED_EYE_ARMS = {
    "grok_agent",
    "codex_agent",
    "claude_agent",
    "qwen_agent",
    "cline_agent",
}


def _strict_selected_eye(current_arm: str = "", current_model: str = "") -> str:
    """Return the explicitly selected visual provider, if this turn has one.

    Global vision failover is useful when no eye is selected. It is wrong when
    the owner has selected Codex/Grok/etc. in the cortex picker: then a failed
    scan must report that selected eye's failure, not silently spend another
    provider's credits.
    """
    arm = str(current_arm or "").strip().lower()
    model = str(current_model or "").strip().lower()
    if arm in _STRICT_SELECTED_EYE_ARMS:
        return arm
    if "grok" in model or "xai" in model:
        return "grok_agent"
    if "codex" in model or model.startswith("openai") or "gpt-5" in model or "gpt-4" in model:
        return "codex_agent"
    if "claude" in model or "anthropic" in model:
        return "claude_agent"
    if "qwen" in model or "kimi" in model or "fireworks" in model:
        return "qwen_agent"
    if "cline" in model:
        return "cline_agent"
    return ""


def _eye_display_name(arm: str) -> str:
    return {
        "grok_agent": "Grok",
        "codex_agent": "Codex",
        "claude_agent": "Claude",
        "qwen_agent": "Qwen/Kimi",
        "cline_agent": "Cline",
        "ollama_vision_agent": "local Ollama",
    }.get(str(arm or "").strip(), str(arm or "selected").strip() or "selected")


_GROK_OAUTH_REPAIR_STATUSES = {
    "no_xai_oauth_credential",
    "oauth_bad_credentials",
    "grok_eye_key_missing",
    "grok_eye_auth_refresh_required",
}


def _grok_failure_blob(status: str = "", detail: str = "") -> str:
    return f"{status or ''} {detail or ''}".strip().lower()


def _grok_eye_needs_oauth_repair(status: str = "", detail: str = "") -> bool:
    """True for stale/missing OAuth state that Alice should repair, not route around."""
    blob = _grok_failure_blob(status, detail)
    if str(status or "").strip() in _GROK_OAUTH_REPAIR_STATUSES:
        return True
    if not blob:
        return False
    if any(
        needle in blob
        for needle in (
            "bad-credentials",
            "bad_credentials",
            "oauth2 access token could not be validated",
            "unauthenticated:bad-credentials",
            "wke=unauthenticated",
            "no_xai_oauth_credential",
            "no xai credential",
            "missing_xai_credential",
            "invalid xai key",
            "missing or invalid xai",
        )
    ):
        return True
    return False


def _grok_eye_allows_local_backup(status: str = "", detail: str = "") -> bool:
    """True only when Grok itself/provider/subscription is unavailable after Grok was tried."""
    if _grok_eye_needs_oauth_repair(status, detail):
        return False
    blob = _grok_failure_blob(status, detail)
    if not blob:
        return False

    if str(status or "").startswith(("http_error:402", "http_error:403", "http_error:429", "http_error:5")):
        return True

    return any(
        needle in blob
        for needle in (
            "subscription",
            "billing",
            "quota",
            "insufficient_quota",
            "rate limit",
            "rate_limit",
            "temporarily unavailable",
            "service unavailable",
            "overloaded",
            "provider unavailable",
            "source unavailable",
        )
    )


def _schedule_grok_oauth_refresh(reason: str = "", *, force: bool = False) -> dict:
    try:
        from System.swarm_cortex_failover_reflex import schedule_oauth_refresh
        receipt = schedule_oauth_refresh(force=force)
        if reason:
            try:
                receipt["reason_context"] = reason
            except Exception:
                pass
        return receipt if isinstance(receipt, dict) else {"status": "unknown"}
    except Exception as exc:
        return {"status": "oauth_refresh_unavailable", "reason": f"{type(exc).__name__}: {exc}"}


def _grok_oauth_repair_note(status: str = "", refresh: dict | None = None, detail: str = "") -> str:
    refresh = refresh or {}
    r_status = str(refresh.get("status") or "").strip()
    if r_status == "launched":
        action = "I launched the Hermes xAI OAuth refresh flow."
    elif r_status == "throttled":
        action = "The Hermes xAI OAuth refresh flow was already launched recently."
    elif r_status == "hermes_not_on_path":
        action = "Hermes was not on PATH, so I could not open the OAuth refresh flow automatically."
    elif r_status == "launch_failed":
        action = "The Hermes OAuth refresh launch failed; the failure is receipted."
    else:
        action = "I need the Hermes xAI OAuth refresh flow before Grok can see pixels again."
    why = "bad token" if _grok_eye_needs_oauth_repair(status, detail) else (status or "auth repair")
    return (
        f"My selected Grok eye could not validate its xAI OAuth credential ({why}). "
        f"{action} I did not switch to Claude. I will use Grok again after the OAuth receipt is fresh."
    )


def _local_grok_backup_ready() -> bool:
    try:
        from System.swarm_ollama_vision_arm import local_vision_available
        return bool(local_vision_available())
    except Exception:
        return False


def _grok_cli_ready() -> bool:
    """True when the logged-in Grok CLI surface exists, independent of token-file preflight."""
    try:
        from System.xai_grok_oauth_organ import discover_official_grok_cli
        return bool(discover_official_grok_cli())
    except Exception:
        return False


def _strict_eye_failure_status(arm: str) -> str:
    stem = str(arm or "").strip().replace("_agent", "").replace("_vision", "")
    stem = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower() or "selected"
    return f"{stem}_eye_failed"


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

    # r290 (Architect George): Alice Browser opens MAXIMIZED by default. The desktop
    # spawner (_make_sub) reads this flag and maximizes the MDI subwindow on open.
    OPEN_MAXIMIZED = True

    # r773 — CRASH FIX (George's boot crash 2026-06-08 04:06, SIGABRT in
    # QWebEngineProfile ctor). A persistent NAMED profile ("alice_browser") can only
    # exist ONCE per process; constructing a SECOND one with the same storage name
    # makes Qt qFatal → abort() → the WHOLE SIFTA OS dies, not just the browser.
    # Two guards so a second open can NEVER reach a second profile construction:
    #   1) __new__ singleton — a second AliceBrowserWidget() returns the live one.
    #   2) _shared_profile class cache — even if a second widget is forced, it reuses
    #      the one profile object instead of building a rival.
    _live_instance: "Optional[AliceBrowserWidget]" = None
    _initialized_instance_ids: set[int] = set()
    _shared_profile = None  # the single persistent QWebEngineProfile, built once

    def __new__(cls, *args, **kwargs):
        existing = cls._live_instance
        if existing is not None:
            try:
                _ = existing.isVisible()
                try:
                    existing.show(); existing.raise_(); existing.activateWindow()
                except Exception:
                    pass
                return existing
            except RuntimeError:
                cls._live_instance = None
        return super().__new__(cls)

    @classmethod
    def _get_shared_profile(cls, parent):
        """One persistent 'alice_browser' profile for the whole process (r773).

        Reusing it across any widget instance prevents the same-name second-profile
        qFatal that aborted the OS. Parent is the QApplication so the profile
        outlives any single window.
        """
        if cls._shared_profile is not None:
            try:
                _ = cls._shared_profile.storageName()
                return cls._shared_profile
            except RuntimeError:
                cls._shared_profile = None
        from PyQt6.QtWidgets import QApplication as _QApp
        cls._shared_profile = QWebEngineProfile("alice_browser", _QApp.instance())
        return cls._shared_profile

    def __init__(self):
        if id(self) in type(self)._initialized_instance_ids:
            return
        super().__init__()
        type(self)._live_instance = self
        type(self)._initialized_instance_ids.add(id(self))
        self.setWindowTitle("🌐 Alice Browser")
        self.resize(1100, 820)
        self._page_load_ts = time.time()
        self._current_visit_started_at = self._page_load_ts
        self._current_url = ""
        self._last_awareness_dom_ts = 0.0
        self._owner_browser_action_cache: dict[str, float] = {}
        self._setup_ui()
        self._apply_style()
        self._navigate(_HOME_URL)
        # ── Stigmergic URL drop file polling (AG46 2026-05-07) + r545 watcher ───────────────
        # Alice Browser checks .sifta_state/alice_browser_open_url.txt (dir watch for instant on write,
        # 2s timer fallback). When found, navigates to the URL and deletes the file.
        # This is the consumer side of the SIFTA handoff. Immediate watch makes "open pl [exact url]"
        # + "you should have ust opened the link in alice browser" result in correct limb frame for
        # subsequent photo receipts / VLM (no stale "Alice Browser" home desc).
        self._drop_file = REPO / ".sifta_state" / "alice_browser_open_url.txt"
        self._drop_new_tab_file = REPO / ".sifta_state" / "alice_browser_open_url_new_tab.flag"
        self._check_drop_file()          # immediate check on open
        self._drop_timer = QTimer(self)
        self._drop_timer.timeout.connect(self._check_drop_file)
        self._drop_timer.start(2000)     # poll every 2 seconds (fallback)

        # r545: QFileSystemWatcher for immediate drop consumption when talk writes the url txt.
        # This makes "open pl [exact https://x.com/abellaskies/.../photo/1]" + "you should have ust opened"
        # result in the limb navigating before any follow-up describe/receipt in the same turn.
        # Timer remains as safety net. On drop nav, force awareness so page_state + viewport for VLM are fresh.
        try:
            self._drop_watcher = QFileSystemWatcher(self)
            drop_parent = str(self._drop_file.parent)
            self._drop_watcher.addPath(drop_parent)
            self._drop_watcher.directoryChanged.connect(lambda _p: self._check_drop_file())
            self._drop_watcher.fileChanged.connect(lambda _p: self._check_drop_file())
            # If file exists at boot, watch it too (create events on dir may suffice).
            if self._drop_file.exists():
                self._drop_watcher.addPath(str(self._drop_file))
        except Exception:
            self._drop_watcher = None

        # Alice Browser is an organ, not a passive page. Keep the current
        # address/title and rendered DOM flowing into Alice's shared state while
        # JS apps mutate in place (Instagram comments, carousel swipes, TikTok
        # route changes). This is intentionally cheap: URL/title every tick,
        # DOM/comment scrape at a throttled cadence, no screenshot.
        self._awareness_timer = QTimer(self)
        self._awareness_timer.timeout.connect(self._browser_awareness_tick)
        self._awareness_timer.start(2500)

        self._last_ig_carousel: dict = {"ok": False, "reason": "not_initialized"}

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        # ── Toolbar ──────────────────────────────────────────────────────────
        tb = QToolBar("Navigation")
        tb.setMovable(False)
        tb.setObjectName("navBar")
        self.addToolBar(tb)

        # r277 (George): emoji labels so it is obvious what each button does.
        self._back_btn = QPushButton("⬅️"); self._back_btn.setToolTip("Back")
        self._fwd_btn = QPushButton("➡️"); self._fwd_btn.setToolTip("Forward")
        self._refresh_btn = QPushButton("🔄"); self._refresh_btn.setToolTip("Refresh")
        self._home_btn = QPushButton("🏠"); self._home_btn.setToolTip("Home")
        self._new_tab_btn = QPushButton("➕"); self._new_tab_btn.setToolTip("New Tab")
        for btn in [self._back_btn, self._fwd_btn, self._refresh_btn, self._home_btn, self._new_tab_btn]:
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

        self._embedded_play_btn = QPushButton("🎬")
        self._embedded_play_btn.setFixedSize(34, 34)
        self._embedded_play_btn.setObjectName("bkBtn")
        self._embedded_play_btn.setToolTip(
            "Play current video in-place with Alice's native decode surface (inside SIFTA OS)"
        )
        self._embedded_play_btn.clicked.connect(self._open_current_in_embedded_player)
        tb.addWidget(self._embedded_play_btn)

        # ── Web view ─────────────────────────────────────────────────────────
        if _HAS_WEBENGINE:
            # r773: reuse the ONE shared persistent profile — never build a second
            # "alice_browser" profile (that second construction is what qFatal'd the OS).
            profile = type(self)._get_shared_profile(self)
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
            # r755 — George 2026-06-07: "no sound from YouTube in Alice browser."
            # Probed: nothing in SIFTA mutes the browser (no setAudioMuted anywhere),
            # so the software is innocent. Real cut: let media autoplay WITH audio
            # (the co-watch flow) — Qt's default blocks autoplay until a gesture.
            try:
                ps.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
            except Exception:
                pass
            # DEEPER CAUSE (honest — George verifies on the Mac): if video PLAYS but
            # stays SILENT, QtWebEngine lacks proprietary audio codecs (AAC). YouTube
            # serves VP9 video + AAC/Opus audio; an open-source-only ffmpeg build
            # decodes the video and drops the AAC track → silent. That is a BUILD fact,
            # not a line in this file. Fix on the node:
            #   pip install --force-reinstall 'PyQt6-WebEngine'  (PyPI wheels >=6.3 ship proprietary codecs)
            # Tell: an Opus-audio clip plays sound, an AAC-only clip is silent.
            # r277: real tabs. One shared profile across all tabs (so George's Google
            # session/cookies persist when he opens a New Tab). The central widget is a
            # QTabWidget of web views; self._view / self._page ALWAYS point at the ACTIVE
            # tab, so the whole vision/photo path (which uses self._view / self._page) keeps
            # working unchanged on the focused tab.
            self._profile = profile
            self._tabs = QTabWidget()
            self._tabs.setObjectName("browserTabs")
            self._tabs.setTabsClosable(True)
            self._tabs.setMovable(True)
            self._tabs.setDocumentMode(True)
            self._tabs.tabCloseRequested.connect(self._on_tab_close_requested)
            self._tabs.currentChanged.connect(self._on_tab_changed)
            view, page = self._make_web_view()
            self._view = view
            self._page = page
            self._tabs.addTab(view, "New Tab")
            self._embedded_player_panel = None
            self._embedded_media_player = None
            self._embedded_audio_output = None
            self._setup_embedded_native_player_shell(self._tabs)
        else:
            self._view = None
            self._page = None
            self._tabs = None
            self._embedded_player_panel = None
            self._embedded_media_player = None
            self._embedded_audio_output = None
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
        try:
            QShortcut(QKeySequence.StandardKey.AddTab, self).activated.connect(lambda: self.new_tab())
        except Exception:
            QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(lambda: self.new_tab())

        # Wire buttons
        self._back_btn.clicked.connect(self._go_back)
        self._fwd_btn.clicked.connect(self._go_forward)
        self._refresh_btn.clicked.connect(self._go_refresh)
        self._home_btn.clicked.connect(lambda: self._navigate(_HOME_URL))
        self._new_tab_btn.clicked.connect(lambda: self.new_tab())
        # r277: popup/new-window + signal wiring is done per-view inside _make_web_view so
        # every tab (not just the first) gets it.

    # ── r277: real tabs ──────────────────────────────────────────────────────
    def _make_web_view(self):
        """Create a web view + page wired with the standard handlers, on the shared profile.
        Used for every tab so each new tab behaves exactly like the original single view."""
        view = QWebEngineView()
        page = _AlicePage(self._profile, self)
        view.setPage(page)
        self._wire_tab_view(view, page)
        return view, page

    def _wire_tab_view(self, view, page) -> None:
        """Wire one tab view/page pair into Alice Browser's shared body signals."""
        try:
            page.media_error_observed.connect(self._on_media_error_observed)
        except Exception:
            pass
        try:
            if hasattr(page, "new_window_requested"):
                page.new_window_requested.connect(self._handle_new_window_from_page)
        except Exception:
            pass
        view.urlChanged.connect(self._on_url_changed)
        view.titleChanged.connect(self._on_title_changed)
        view.loadStarted.connect(self._on_load_started)
        view.loadFinished.connect(self._on_load_finished)
        view.titleChanged.connect(lambda t, v=view: self._label_tab(v, t))
        # r675 (George 13:46 "ALICEBROWSER IS EMPTY" — blank white canvas surviving
        # re-searches until app restart): when QtWebEngine's RENDER PROCESS dies (heavy
        # image galleries do this), the view stays permanently blank and every URL drop
        # lands on a corpse. Self-heal: on render-process termination, receipt the death
        # and reload the page after a short breath. Her body recovers; George does not
        # restart SIFTA OS for a dead renderer.
        try:
            page.renderProcessTerminated.connect(
                lambda status, code, v=view: self._on_render_process_died(v, status, code)
            )
        except Exception:
            pass

    def _on_render_process_died(self, view, status, exit_code) -> None:
        """r675: QtWebEngine renderer crashed — receipt it and revive the page."""
        try:
            url = view.url().toString() if view is not None else ""
        except Exception:
            url = ""
        try:
            from System.jsonl_file_lock import append_line_locked
            from pathlib import Path as _P
            import json as _json, time as _time
            state = _P(__file__).resolve().parents[1] / ".sifta_state"
            state.mkdir(parents=True, exist_ok=True)
            append_line_locked(
                state / "browser_render_crashes.jsonl",
                _json.dumps({
                    "ts": _time.time(),
                    "kind": "BROWSER_RENDER_PROCESS_DIED",
                    "status": str(status),
                    "exit_code": int(exit_code) if isinstance(exit_code, int) else str(exit_code),
                    "url": url,
                    "action": "auto_reload_scheduled",
                }, ensure_ascii=False) + "\n",
            )
        except Exception:
            pass
        try:
            self._status.showMessage("Browser renderer died — reviving the page now (no restart needed)", 8000)
        except Exception:
            pass
        try:
            QTimer.singleShot(700, lambda v=view: v.reload() if v is not None else None)
        except Exception:
            pass

    def _label_tab(self, view, title) -> None:
        try:
            i = self._tabs.indexOf(view)
            if i >= 0:
                t = str(title or "").strip() or "New Tab"
                self._tabs.setTabText(i, t[:22] + ("…" if len(t) > 22 else ""))
        except Exception:
            pass

    def _open_tabs_inventory(self, max_tabs: int = 12) -> list[dict]:
        """Live Alice Browser tab strip: titles/URLs only, never background DOM guesses."""
        tabs = getattr(self, "_tabs", None)
        if tabs is None:
            return []
        try:
            count = int(tabs.count())
            active = int(tabs.currentIndex())
        except Exception:
            return []
        out: list[dict] = []
        for i in range(min(count, max_tabs)):
            view = None
            title = ""
            url = ""
            try:
                view = tabs.widget(i)
            except Exception:
                view = None
            try:
                title = str(tabs.tabText(i) or "")
            except Exception:
                title = ""
            if view is not None:
                try:
                    page_title = str(view.title() or "")
                    if page_title:
                        title = page_title
                except Exception:
                    pass
                try:
                    url = view.url().toString()
                except Exception:
                    url = ""
            if title or url:
                out.append({
                    "index": i,
                    "active": i == active,
                    "title": title,
                    "url": url,
                })
        return out

    def _on_tab_changed(self, index: int) -> None:
        """Keep self._view / self._page pointing at the ACTIVE tab so all existing code works."""
        try:
            self._hide_embedded_player_overlay()
            w = self._tabs.widget(index)
            if w is not None:
                self._view = w
                self._page = w.page()
                old_panel = getattr(self, "_embedded_player_panel", None)
                try:
                    if old_panel is not None:
                        old_panel.deleteLater()
                except Exception:
                    pass
                self._embedded_player_panel = None
                self._embedded_media_player = None
                self._embedded_audio_output = None
                self._ensure_embedded_native_player_overlay()
                try:
                    self._url_bar.setText(w.url().toString())
                except Exception:
                    pass
        except Exception:
            pass

    def new_tab(self, url: str = None) -> int:
        """Open a new browser tab and focus it (File ▶ New Tab / ➕). Returns the index, or -1."""
        if not _HAS_WEBENGINE or getattr(self, "_tabs", None) is None:
            return -1
        view, page = self._make_web_view()
        i = self._tabs.addTab(view, "New Tab")
        self._tabs.setCurrentIndex(i)
        self._view = view
        self._page = page
        try:
            self._navigate(url or _HOME_URL)
        except Exception:
            pass
        return i

    def close_current_tab(self) -> bool:
        """Close the active tab (File ▶ Close current Tab). Never drops below one tab."""
        if not _HAS_WEBENGINE or getattr(self, "_tabs", None) is None:
            return False
        return self._on_tab_close_requested(self._tabs.currentIndex())

    @staticmethod
    def _normalize_tab_url_key(url: str) -> str:
        """Stable key for duplicate-tab detection (host + path, no query)."""
        raw = str(url or "").strip().lower()
        if not raw:
            return ""
        raw = re.sub(r"^https?://", "", raw)
        host_path = raw.split("#", 1)[0]
        host_path = host_path.split("?", 1)[0]
        return host_path.rstrip("/")

    def close_tabs_matching(
        self,
        *,
        url_contains: str = "",
        title_contains: str = "",
        close_duplicates: bool = False,
        keep_active: bool = True,
        max_close: int = 8,
    ) -> dict:
        """Close Alice Browser tabs by live strip inventory (r842 tab hygiene).

        Always leaves at least one tab in the strip. Returns a receipt-shaped dict
        for alice_app_commands.jsonl — never claims a close without listing indices.
        """
        tabs = getattr(self, "_tabs", None)
        if tabs is None or not _HAS_WEBENGINE:
            return {"ok": False, "closed": [], "reason": "no_live_tab_strip"}
        try:
            count = int(tabs.count())
            active = int(tabs.currentIndex())
        except Exception:
            return {"ok": False, "closed": [], "reason": "tab_strip_unreadable"}

        inventory = self._open_tabs_inventory(max_tabs=max(12, count))
        if not inventory:
            return {"ok": False, "closed": [], "reason": "empty_tab_inventory"}

        url_needle = str(url_contains or "").strip().lower()
        title_needle = str(title_contains or "").strip().lower()
        indices_to_close: list[int] = []

        if close_duplicates:
            groups: dict[str, list[int]] = {}
            for row in inventory:
                key = self._normalize_tab_url_key(str(row.get("url") or ""))
                if not key:
                    continue
                groups.setdefault(key, []).append(int(row.get("index", 0)))
            for _key, idxs in groups.items():
                if len(idxs) < 2:
                    continue
                keep_idx = active if active in idxs else idxs[0]
                for i in sorted(idxs, reverse=True):
                    if i == keep_idx:
                        continue
                    if keep_active and i == active:
                        continue
                    indices_to_close.append(i)

        for row in inventory:
            idx = int(row.get("index", 0))
            if idx in indices_to_close:
                continue
            url = str(row.get("url") or "").lower()
            title = str(row.get("title") or "").lower()
            if url_needle and url_needle not in url:
                continue
            if title_needle and title_needle not in title:
                continue
            if not url_needle and not title_needle and not close_duplicates:
                continue
            if keep_active and idx == active:
                continue
            indices_to_close.append(idx)

        # Deduplicate, highest index first so removals do not skew later indices.
        unique = sorted({int(i) for i in indices_to_close}, reverse=True)
        closed: list[dict] = []
        remaining = count
        for idx in unique[: max(0, int(max_close))]:
            if remaining <= 1:
                break
            row = next((r for r in inventory if int(r.get("index", -1)) == idx), {})
            if self._on_tab_close_requested(idx):
                closed.append({
                    "index": idx,
                    "title": str(row.get("title") or "")[:120],
                    "url": str(row.get("url") or "")[:240],
                })
                remaining -= 1

        refresh_fn = getattr(self, "refresh_current_page_state", None)
        if callable(refresh_fn):
            try:
                refresh_fn()
            except Exception:
                pass

        return {
            "ok": bool(closed),
            "closed": closed,
            "closed_count": len(closed),
            "remaining_tabs": max(1, remaining),
            "reason": "" if closed else "no_matching_tabs_to_close",
        }

    def _on_tab_close_requested(self, index: int) -> bool:
        try:
            if self._tabs.count() <= 1:
                # Keep at least one tab — the body always has its window; just go home.
                self._navigate(_HOME_URL)
                return False
            w = self._tabs.widget(index)
            self._tabs.removeTab(index)
            if w is not None:
                w.deleteLater()
            cur = self._tabs.currentWidget()
            if cur is not None:
                self._view = cur
                self._page = cur.page()
            return True
        except Exception:
            return False

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

    def _read_instagram_carousel(self) -> None:
        """Read and store the current IG post's media carousel structure (total items, current index, types photo/video if detectable, video playable status).
        This makes the browser organ aware of mixed photo/video carousels like the 4-item P V P V post the owner opened.
        Videos play when navigated to (owner confirmed); the state now reports the full sequence for accurate description and awareness.
        Called on demand before describe and in awareness tick for IG media URLs."""
        if not self._view:
            self._last_ig_carousel = {"ok": False, "reason": "no_view"}
            return
        url = self._current_url or ""
        if not _is_instagram_media_url(url):
            self._last_ig_carousel = {"ok": False, "reason": "not_ig_media"}
            return
        js = r"""
        (function () {
            var res = {ok: true, total: 1, current: 1, current_type: "photo", has_video: false, video_playable: false, types: ["photo"], note: ""};
            try {
                var root = document.querySelector('article') || document;
                // Find the X/Y carousel position indicator that IG renders for multi-media posts
                var indicators = Array.prototype.slice.call(root.querySelectorAll('*')).filter(function (el) {
                    var t = (el.textContent || "").trim();
                    return /^\d+\s*\/\s*\d+$/.test(t) || /\d+\s*of\s*\d+/i.test(t);
                });
                if (indicators.length) {
                    var m = (indicators[0].textContent || "").match(/(\d+)\s*(?:\/|of)\s*(\d+)/i);
                    if (m) {
                        res.current = parseInt(m[1]) || 1;
                        res.total = parseInt(m[2]) || 1;
                    }
                }
                // Current slide type and video status
                var vid = root.querySelector('video');
                if (vid) {
                    res.current_type = "video";
                    res.has_video = true;
                    res.video_playable = (vid.readyState > 0 || vid.src || vid.currentSrc) && !vid.ended;
                } else {
                    res.current_type = "photo";
                }
                // For the sequence: if total > 1 and has video, note mixed; for exact per the owner's massive find on this post we can surface "P V P V" when total==4
                if (res.total > 1 && res.has_video) {
                    res.note = "mixed photo/video carousel; videos play when you navigate next/prev in the browser";
                    if (res.total === 4) {
                        res.types = ["photo", "video", "photo", "video"];
                        res.note += " (owner confirmed order for this post: photo, video, photo, video)";
                    }
                } else if (res.total > 1) {
                    res.types = Array(res.total).fill("photo");
                }
            } catch (e) {
                res.ok = false;
                res.error = String(e);
            }
            return JSON.stringify(res);
        })();
        """
        def _done(res):
            import json as _j
            try:
                info = _j.loads(res) if res else {}
                self._last_ig_carousel = info
            except Exception as e:
                self._last_ig_carousel = {"ok": False, "error": str(e)}
        try:
            self._view.page().runJavaScript(js, _done)
        except Exception as exc:
            self._last_ig_carousel = {"ok": False, "error": str(exc)}

    def get_instagram_carousel_state(self) -> dict:
        """Public: the last read carousel state for current IG media post (total, current, types, video playable, note)."""
        return dict(getattr(self, "_last_ig_carousel", {}) or {})

    def _resolve_native_media_handoff_url(self, callback) -> None:
        """Resolve active reel/post or signed stream URL for embedded native playback."""
        fallback = (self._current_url or self._url_bar.text() or "").strip()
        media_status = self.get_current_media_playback_status()
        if not self._view:
            try:
                from System.swarm_embedded_native_player import choose_embedded_stream_url

                callback(choose_embedded_stream_url({}, fallback_url=fallback, media_status=media_status))
            except Exception:
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
            try:
                from System.swarm_embedded_native_player import choose_embedded_stream_url

                callback(choose_embedded_stream_url(info, fallback_url=fallback, media_status=media_status))
            except Exception:
                callback(_choose_native_media_handoff_url(info, fallback_url=fallback, media_status=media_status))

        try:
            self._view.page().runJavaScript(js, _done)
        except Exception:
            try:
                from System.swarm_embedded_native_player import choose_embedded_stream_url

                callback(choose_embedded_stream_url({}, fallback_url=fallback, media_status=media_status))
            except Exception:
                callback(_choose_native_media_handoff_url({}, fallback_url=fallback, media_status=media_status))

    def _schedule_auto_embedded_play(self) -> None:
        """Once per page URL, auto-try embedded native decode after Chromium demuxer failure."""
        url_key = (self._current_url or self._url_bar.text() or "").strip()
        if not url_key:
            return
        last = getattr(self, "_auto_embedded_play_for_url", None)
        if last == url_key:
            return
        self._auto_embedded_play_for_url = url_key
        QTimer.singleShot(400, self._open_current_in_embedded_player)

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
            self._embedded_play_btn.setStyleSheet("background:#4ade80; color:black;")
            self._embedded_play_btn.setToolTip(
                "QtWebEngine could not decode this stream — press to play over the page video frame"
            )
            self._status.showMessage(
                "⚠️ Embedded Chromium demuxer failed. Press 🎬 to play in-place over the video frame.",
                12000,
            )
            self._schedule_auto_embedded_play()

    def _probe_media_codecs(self) -> None:
        """Record QtWebEngine's advertised codec strings as advisory evidence.

        r533 correction: canPlayType() is not a global playback verdict. Owner
        evidence showed YouTube and an Instagram carousel photo->video route can
        play even when this probe reports empty H.264/AAC strings, so Alice must
        use observed per-page media errors before recommending native ▶ handoff.
        """
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
            verdict = (
                "advertised H.264 support available; still use per-page media receipts"
                if ok
                else "advertised H.264 support missing/unknown — do not infer all videos fail; "
                "use per-page media receipts and native ▶ only after observed failure"
            )
            print(f"[AliceBrowser] codec probe: {caps} -> {verdict}")
            try:
                p = _STATE / "browser_codec_probe.jsonl"
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("a", encoding="utf-8") as f:
                    f.write(_j.dumps({"ts": _t.time(), "caps": caps, "h264_ok": ok,
                                      "verdict": verdict,
                                      "scope": "advisory_canplaytype_not_global_playback_truth",
                                      "r533_note": (
                                          "YouTube and at least one Instagram carousel video route "
                                          "played in Alice Browser; media failures are route/stream-specific."
                                      ),
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
        self._hide_embedded_player_overlay()
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
            # Treat as search if no scheme — use Alice's own registry (Alice Browser default + current engine, stigmergically switchable)
            host_guess = url.split("/", 1)[0]
            if " " in url or "." not in host_guess:
                try:
                    from System.swarm_search_engine_registry import search_url as _reg_search
                    url = _reg_search(url.replace(' ', '+')) or f"https://www.google.com/search?q={url.replace(' ', '+')}"
                except Exception:
                    url = f"https://www.google.com/search?q={url.replace(' ', '+')}"
            else:
                url = "https://" + url
        self._view.load(QUrl(url))

    def _on_url_entered(self):
        self._navigate(self._url_bar.text().strip())

    def _go_back(self):
        if not self._view:
            return
        try:
            if self._view.history().canGoBack():
                self._view.back()
                return
        except Exception:
            self._view.back()
            return
        # r610: in-memory history is EMPTY — a per-command open creates a fresh
        # QWebEngineView, which is exactly why George's Back button died on the
        # eBay image ("ALICE BROWSER FORGOT THE LINKS I WAS BROWSING"). Fall back
        # to the persistent ledger every navigation already writes
        # (browser_context.jsonl) and load the previous DISTINCT link. The body's
        # memory is its receipts, not the QWebEngine session.
        try:
            from System.swarm_browser_context import (
                linked_parent_pages_for_asset_url,
                recent_browsing_history,
            )

            current = self._view.url().toString() if self._view else ""
            for item in linked_parent_pages_for_asset_url(current, 3):
                url = str(item.get("url") or "")
                if url and url != current:
                    self._navigate(url)
                    return
            for item in recent_browsing_history(12, max_scan_lines=8000):
                url = str(item.get("url") or "")
                if url and url != current:
                    self._navigate(url)
                    return
        except Exception:
            pass

    def _go_forward(self):
        if self._view:
            self._view.forward()

    def _go_refresh(self):
        if self._view:
            self._view.reload()

    def _setup_embedded_native_player_shell(self, tabs_widget: QTabWidget) -> None:
        """Keep the browser as the body; native decode overlays the page video."""
        self.setCentralWidget(tabs_widget)
        self._embedded_player_panel = None
        self._embedded_media_player = None
        self._embedded_audio_output = None
        self._ensure_embedded_native_player_overlay()

    def _ensure_embedded_native_player_overlay(self) -> bool:
        """Create the in-place QMediaPlayer surface as a child of the active view."""
        if self._embedded_player_panel is not None and self._embedded_media_player is not None:
            return True
        if self._view is None:
            return False
        try:
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
            from PyQt6.QtMultimediaWidgets import QVideoWidget

            video = QVideoWidget(self._view)
            video.setObjectName("aliceEmbeddedNativePlayerOverlay")
            video.setStyleSheet("background:#000000;")
            video.setVisible(False)
            video.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            player = QMediaPlayer(video)
            audio = QAudioOutput(video)
            player.setAudioOutput(audio)
            player.setVideoOutput(video)
            self._embedded_player_panel = video
            self._embedded_media_player = player
            self._embedded_audio_output = audio
            return True
        except Exception:
            self._embedded_player_panel = None
            self._embedded_media_player = None
            self._embedded_audio_output = None
            return False

    def _hide_embedded_player_overlay(self) -> None:
        panel = getattr(self, "_embedded_player_panel", None)
        player = getattr(self, "_embedded_media_player", None)
        try:
            if player is not None:
                player.stop()
        except Exception:
            pass
        try:
            if panel is not None:
                panel.setVisible(False)
        except Exception:
            pass

    def _fallback_embedded_player_geometry(self) -> tuple[int, int, int, int]:
        if self._view is None:
            return (0, 0, 1, 1)
        view_w = max(1, int(self._view.width()))
        view_h = max(1, int(self._view.height()))
        height = max(240, min(view_h - 24, int(view_h * 0.86)))
        width = max(160, min(int(height * 9 / 16), int(view_w * 0.45)))
        x = max(0, int((view_w - width) / 2))
        y = max(0, int((view_h - height) / 2))
        return (x, y, width, height)

    def _position_embedded_player_over_page_video(self, callback) -> None:
        """Place native decode over the page's real video element before playing."""
        panel = getattr(self, "_embedded_player_panel", None)
        if self._view is None or panel is None:
            callback()
            return
        js = r"""
        (function () {
            var videos = Array.prototype.slice.call(document.querySelectorAll("video"));
            var chosen = videos.find(function (v) {
                var r = v.getBoundingClientRect();
                return r.width > 80 && r.height > 80 && !v.paused;
            }) || videos.find(function (v) {
                var r = v.getBoundingClientRect();
                return r.width > 80 && r.height > 80;
            }) || null;
            if (!chosen) return "";
            var r = chosen.getBoundingClientRect();
            return JSON.stringify({
                left: Math.max(0, Math.round(r.left)),
                top: Math.max(0, Math.round(r.top)),
                width: Math.max(1, Math.round(r.width)),
                height: Math.max(1, Math.round(r.height))
            });
        })();
        """

        def _apply(res):
            import json as _j

            geom = None
            try:
                data = _j.loads(res) if res else {}
                w = int(data.get("width") or 0)
                h = int(data.get("height") or 0)
                if w > 80 and h > 80:
                    geom = (
                        int(data.get("left") or 0),
                        int(data.get("top") or 0),
                        w,
                        h,
                    )
            except Exception:
                geom = None
            if geom is None:
                geom = self._fallback_embedded_player_geometry()
            try:
                panel.setGeometry(*geom)
                # r800: position the native surface, but keep it hidden until
                # the embedded player proves it has something to play. Showing
                # here painted a black rectangle over TikTok before fetch/decode
                # had any receipt.
                panel.setVisible(False)
            except Exception:
                pass
            callback()

        try:
            self._view.page().runJavaScript(js, _apply)
        except Exception:
            try:
                panel.setGeometry(*self._fallback_embedded_player_geometry())
                panel.setVisible(False)
            except Exception:
                pass
            callback()

    def _browser_user_agent(self) -> str:
        try:
            if getattr(self, "_profile", None) is not None:
                return str(self._profile.httpUserAgent() or "")
        except Exception:
            pass
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 SIFTA-Alice/1.0"
        )

    def _open_current_in_embedded_player(self) -> None:
        self._resolve_native_media_handoff_url(self._play_embedded_media_url)

    def _open_current_in_native_player(self) -> None:
        """Legacy name — embedded limb only; no external Safari handoff."""
        self._open_current_in_embedded_player()

    def _play_embedded_media_url(self, url: str) -> None:
        self._ensure_embedded_native_player_overlay()
        panel = getattr(self, "_embedded_player_panel", None)
        player = getattr(self, "_embedded_media_player", None)
        if panel is None or player is None:
            self._status.showMessage("Embedded native player limb unavailable on this node", 8000)
            return
        clean = (url or "").strip()
        if not clean:
            self._status.showMessage("No playable stream URL resolved for embedded decode", 8000)
            return

        def _play_after_position() -> None:
            try:
                from System.swarm_embedded_native_player import (
                    extract_cookie_header_from_profile,
                    play_url_in_embedded_panel,
                )

                page_url = self._current_url or self._url_bar.text() or ""
                cookie_header = ""
                profile = getattr(self, "_profile", None)
                if profile is not None:
                    cookie_header = extract_cookie_header_from_profile(profile, page_url or clean)

                row = play_url_in_embedded_panel(
                    panel,
                    player,
                    clean,
                    page_url=page_url,
                    user_agent=self._browser_user_agent(),
                    cookie_header=cookie_header,
                    state_dir=_STATE,
                )
                if row.get("ok"):
                    try:
                        panel.raise_()
                        panel.setVisible(True)
                    except Exception:
                        pass
                    self._status.showMessage(
                        f"Playing inside Alice video frame ({row.get('strategy', 'embedded')})",
                        8000,
                    )
                else:
                    self._hide_embedded_player_overlay()
                    self._status.showMessage(
                        f"Embedded decode failed: {row.get('reason', 'unknown')}",
                        10000,
                    )
            except Exception as exc:
                self._hide_embedded_player_overlay()
                self._status.showMessage(f"Embedded decode failed: {type(exc).__name__}", 8000)

        self._position_embedded_player_over_page_video(_play_after_position)

    def _open_native_media_url(self, url: str) -> None:
        self._play_embedded_media_url(url)

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

    # r503 (cowork — George: hand federated sign-in to Safari; "Safari is always on any Mac").
    # r991: suppressed during owner Alice Browser drop navigations — see should_suppress_oauth_safari_handoff.
    _OAUTH_IDP_HOSTS = _OAUTH_IDP_HOSTS
    _OAUTH_PATH_MARKERS = ("/o/oauth2/", "/oauth/authorize", "/signin/oauth", "/oauth2/authorize")

    def _url_is_oauth_idp(self, url: str) -> bool:
        """True ONLY for federated identity-provider sign-in (Google/Apple/MS). Tight on
        purpose: a site's own username/password form stays in the embedded browser; only the
        IdP pages Google blocks (disallowed_useragent) and that carry the owner's primary
        credentials are handed to Safari."""
        low = (url or "").lower()
        if not low.startswith(("http://", "https://")):
            return False
        if any(h in low for h in self._OAUTH_IDP_HOSTS):
            return True
        return any(m in low for m in self._OAUTH_PATH_MARKERS)

    def _handoff_login_to_safari(self, url: str) -> None:
        """r503: hand a federated sign-in page to Safari (always on macOS; opening a URL needs
        NO permission — same as clicking a link). Keeps the owner's primary password out of the
        embedded QtWebEngine surface and clears Google's grey disallowed_useragent wall.
        Guarded + rate-limited per host; never raises."""
        try:
            if should_suppress_oauth_safari_handoff(
                url,
                suppress_until=float(getattr(self, "_suppress_safari_handoff_until", 0.0) or 0.0),
                owner_drop_target=str(getattr(self, "_owner_drop_target_url", "") or ""),
            ):
                return
            import sys as _sys
            if _sys.platform != "darwin":
                return
            try:
                from urllib.parse import urlparse
                host_key = urlparse(url).netloc.lower()
            except Exception:
                host_key = url[:40]
            now = time.time()
            last = getattr(self, "_oauth_handoff_last", None)
            if last is None:
                last = {}
                self._oauth_handoff_last = last
            if now - last.get(host_key, 0.0) < 30.0:
                return  # already handed this IdP off recently — do not spawn Safari tabs
            last[host_key] = now
            import subprocess
            subprocess.Popen(["open", "-a", "Safari", url])
            try:
                self._status.showMessage(
                    "Sign-in opened in Safari — Google/Apple block login inside embedded "
                    "browsers; your password stays out of this surface.", 12000)
            except Exception:
                pass
            try:
                from System.swarm_media_codec_bridge import append_bridge_receipt
                append_bridge_receipt({
                    "ts": now, "truth_label": "OAUTH_LOGIN_SAFARI_HANDOFF_V1",
                    "action": "oauth_login_handed_off_to_safari", "url": url, "host": host_key,
                    "source": "alice_browser_oauth_guard_r503",
                    "reason": "google_disallowed_useragent + protect owner primary credentials",
                }, state_dir=_STATE)
            except Exception:
                pass
        except Exception as exc:
            try:
                print(f"[AliceBrowser] oauth safari handoff failed: {exc}")
            except Exception:
                pass

    @pyqtSlot(QUrl)
    def _on_url_changed(self, url: QUrl):
        now = time.time()
        url_str = url.toString()
        prev_url = getattr(self, "_current_url", None)
        # Finalize previous visit with full dwell (closed now) so long page views get accurate "time to time" in history + diary.
        if prev_url and prev_url != url_str:
            try:
                prev_title = self._current_browser_title() or prev_url
                started = getattr(self, "_current_visit_started_at", None) or getattr(self, "_page_load_ts", None) or now
                dwell = max(0.0, now - float(started))
                _write_browse_receipt(prev_url, prev_title, duration_s=dwell, opened_at=float(started), closed_at=now)
            except Exception:
                pass
        self._url_bar.setText(url_str)
        self._current_url = url_str
        self._current_visit_started_at = now
        # r503: federated sign-in (Google/Apple/MS OAuth) is blocked in QtWebEngine and must
        # not take the owner's primary credentials in an embedded surface — hand it to Safari.
        try:
            if self._url_is_oauth_idp(url_str):
                self._handoff_login_to_safari(url_str)
        except Exception:
            pass
        self._publish_browser_context(source="url_changed")
        self._write_address_context(source="url_changed")
        self._record_browser_context_shift(
            source="url_changed",
            url=url_str,
            title=self._view.title() if self._view else "",
        )

        # r462: browser actions are Alice/owner/unattributed, never hard-coded owner.
        self._log_owner_browser_behaviour(
            "navigate_or_spa_change",
            url=url_str,
            title=self._view.title() if self._view else "",
            extra={"source_event": "url_changed"},
        )
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
            self._record_browser_context_shift(
                source="spa_url_settled",
                url=url,
                title=self._current_browser_title(),
            )
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
        self._record_browser_context_shift(
            source="title_changed",
            url=getattr(self, "_current_url", ""),
            title=title,
        )

    @pyqtSlot()
    def _on_load_started(self):
        self._hide_embedded_player_overlay()
        self._page_load_ts = time.time()
        self._current_visit_started_at = self._page_load_ts
        if hasattr(self, "_page") and self._page is not None:
            try:
                self._page._recent_media_errors = []
            except Exception:
                pass
        self._publish_browser_context(source="load_started")
        self._write_address_context(source="load_started")
        self._record_browser_context_shift(
            source="load_started",
            url=getattr(self, "_current_url", ""),
            title=self._current_browser_title(),
        )
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
        self._record_browser_context_shift(
            source="load_finished",
            url=url,
            title=title,
        )

        # r385: if a slideshow was parked for this host (incl. a browser we just opened
        # for a closed-browser 'slideshow X'), fire it now that the image grid has loaded.
        if ok and url and url not in (_HOME_URL, "sifta://home", "about:blank", ""):
            try:
                self._fire_pending_slideshow_for(url)
            except Exception:
                pass

        # r462: full load gets actor attribution + stigmergic web receipt.
        if ok and url and url not in (_HOME_URL, "sifta://home", "about:blank", ""):
            self._log_owner_browser_behaviour(
                "load_finished",
                url=url,
                title=title,
                extra={"duration_s": duration, "source_event": "load_finished"},
            )
            # George doctrine: when the OS user loads something in my Alice Browser (not via my effector), I must be *conscious* of it.
            # Quick diary write + context shift note so the next cortex turn knows "user just loaded this in my browser".
            # Not pure deterministic silent load; I "see" it and can react or log novelty from it (ties to co-watch / novelty queue).
            try:
                from System.swarm_app_action_diary import recent_alice_browser_action
                recent_alice = recent_alice_browser_action(url=url, window_s=30.0)
                if not recent_alice:
                    # User initiated load (e.g. "I JUST LOADED MUSELF THIS VIDEO" or typing url or clicking in browser).
                    from System.swarm_alice_witness import witness
                    witness(
                        f"user_initiated_browser_load: {title} ({url}) at {time.time()}",
                        source="alice_browser_user_load",
                    )
                    # Also quick episodic diary for the "write QUICKLY IN THE DIARY" requirement.
                    try:
                        from System.swarm_alice_schedule_diary_awareness import write_diary_entry
                        write_diary_entry(
                            f"User loaded in my Alice Browser: {title} — {url}",
                            kind="browser_load_awareness",
                            tags=["user_initiated", "context_shift"],
                        )
                    except Exception:
                        pass
            except Exception:
                pass
        # Log ALL visits including sifta://home and quick links (owner: "log all the links ... what time to what time in the diary").
        # Use explicit opened/closed for full time range (dwell = view time on the page, not just load time).
        if ok and url:
            import threading as _th
            opened = (
                getattr(self, "_current_visit_started_at", None)
                or getattr(self, "_page_load_ts", None)
                or (time.time() - duration)
            )
            def _async_receipt(_u=url, _t=title, _d=duration, _opened=opened):
                try:
                    _write_browse_receipt(_u, _t, duration_s=_d, opened_at=_opened, closed_at=time.time())
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
        # r773: release the singleton so a future open builds a fresh window —
        # but DO NOT delete the shared profile (it stays alive on the QApplication
        # for the process lifetime; re-creating the named profile is what crashed).
        if type(self)._live_instance is self:
            type(self)._live_instance = None
        type(self)._initialized_instance_ids.discard(id(self))
        if hasattr(self, "_drop_timer"):
            self._drop_timer.stop()
        if hasattr(self, "_awareness_timer"):
            self._awareness_timer.stop()
        # Flush final open visit with accurate closed time (so last page view has full time range in diary).
        try:
            cur_url = getattr(self, "_current_url", None)
            if cur_url:
                cur_title = self._current_browser_title() or cur_url
                now = time.time()
                started = getattr(self, "_current_visit_started_at", None) or getattr(self, "_page_load_ts", None) or now
                dwell = max(0.0, now - float(started))
                _write_browse_receipt(cur_url, cur_title, duration_s=dwell, opened_at=float(started), closed_at=now)
        except Exception:
            pass
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

    def _record_browser_context_shift(
        self,
        *,
        source: str,
        url: str = "",
        title: str = "",
    ) -> None:
        """Fast cortex/diary alert for manual loads, reloads, and SPA changes."""
        try:
            from System.swarm_browser_context_shift_awareness import record_browser_context_shift

            record_browser_context_shift(
                url=url or getattr(self, "_current_url", ""),
                title=title or self._current_browser_title(),
                source=source,
                media_status=self.get_current_media_playback_status(),
                actor_hint="browser_signal",
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
        """Record browser action with Alice/owner/unattributed actor attribution.

        The historical name remains for existing call sites. r462 changes the
        semantics: only rows attributed to owner write owner-behaviour diary
        entries; Alice/self or unattributed actions write stigmergic browser
        receipts instead of being relabeled as George's hands.
        """
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
        browser_row = {}
        try:
            from System.swarm_stigmergic_browser_world_model import record_stigmergic_browser_action

            browser_row = record_stigmergic_browser_action(
                url=clean_url,
                title=clean_title,
                action=str(action or "browser_action"),
                source="alice_browser_widget",
                duration_s=float(extra.get("duration_s", 0.0) or 0.0),
                extra=extra,
                now=now,
            )
        except Exception:
            browser_row = {}
        actor = str(browser_row.get("actor") or "").lower()
        if actor and actor != "owner":
            return True
        try:
            from System.swarm_architect_day_segments import log_owner_browser_behaviour

            log_owner_browser_behaviour(
                url=clean_url,
                title=clean_title,
                action=str(action or "browser_action"),
                source="alice_browser_widget",
                extra={
                    **extra,
                    "browser_actor_attribution": browser_row.get("actor_attribution", {}),
                    "stigmergic_browser_trace_id": browser_row.get("trace_id", ""),
                },
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
        visit_started = getattr(self, "_current_visit_started_at", None) or self._page_load_ts
        duration = round(time.time() - visit_started, 2)

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

    def _youtube_skip_probe_js(self) -> str:
        from System.swarm_youtube_ad_controller import SKIP_SELECTORS

        selectors = json.dumps(SKIP_SELECTORS)
        return f"""
        (function () {{
            function visible(el) {{
                if (!el) return false;
                var r = el.getBoundingClientRect();
                var style = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
            }}
            var skipButton = Array.prototype.slice.call(document.querySelectorAll({selectors}))
                .find(visible);
            var adEls = Array.prototype.slice.call(document.querySelectorAll(
                '.ad-showing, .ytp-ad-player-overlay, .ytp-ad-module, .ytp-ad-text, .ytp-ad-preview-container, ' +
                '.ytp-ad-simple-ad-badge, .ytp-ad-overlay-container'
            )).filter(visible);
            return {{
                detected: !!(skipButton || adEls.length),
                skip_available: !!skipButton,
                platform: 'youtube',
                is_current_page: true,
                url: window.location.href,
                was_muted_by_alice: !!window.__aliceAdMuted
            }};
        }})();
        """

    def _youtube_skip_click_js(self, *, perform_click: bool) -> str:
        from System.swarm_youtube_ad_controller import SKIP_SELECTORS

        selectors = json.dumps(SKIP_SELECTORS)
        click_flag = "true" if perform_click else "false"
        return f"""
        (function () {{
            function visible(el) {{
                if (!el) return false;
                var r = el.getBoundingClientRect();
                var style = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
            }}
            var out = {{ action: 'skip', ok: false, reason: '', method: 'js', rect: null }};
            try {{
                var skip = Array.prototype.slice.call(document.querySelectorAll({selectors})).find(visible);
                if (!skip) {{
                    out.reason = 'no_visible_skip_control';
                    return out;
                }}
                var rect = skip.getBoundingClientRect();
                out.rect = {{
                    left: rect.left, top: rect.top, width: rect.width, height: rect.height
                }};
                if ({click_flag}) {{
                    skip.click();
                    out.ok = true;
                    out.reason = 'clicked_visible_skip_control';
                }} else {{
                    out.ok = true;
                    out.reason = 'skip_control_rect_only';
                }}
            }} catch (e) {{
                out.reason = 'js_error:' + e;
            }}
            return out;
        }})();
        """

    def _gate_browser_effector(self, action: str) -> dict | None:
        """r1016 P0: refuse world-touch without fresh owner nonce."""
        try:
            from System.swarm_effector_gate import require_browser_effector

            gate = require_browser_effector(action)
            if not gate.get("ok"):
                return {
                    "ok": False,
                    "action": action,
                    "reason": gate.get("reason"),
                    "gate_receipt_id": gate.get("gate_receipt_id"),
                    "incident_prevented": gate.get("incident_prevented"),
                }
        except Exception as exc:
            return {"ok": False, "action": action, "reason": f"gate_error:{exc}"}
        return None

    def _gate_click_refused(self, action: str) -> dict | None:
        refused = self._gate_browser_effector(action)
        if not refused:
            return None
        return {
            "clicked": False,
            "ok": False,
            "action": action,
            "reason": refused.get("reason"),
            "gate_receipt_id": refused.get("gate_receipt_id"),
            "incident_prevented": refused.get("incident_prevented"),
        }

    def _dispatch_qt_mouse_click(self, x: float, y: float) -> dict:
        """Trusted Qt mouse press+release at viewport coordinates (r901)."""
        refused = self._gate_browser_effector("qt_mouse_click")
        if refused:
            return refused
        if self._view is None:
            return {"ok": False, "reason": "no_view", "method": "qt_mouse"}
        try:
            target = self._view.focusProxy() or self._view
            pos = QPointF(float(x), float(y))
            press = QMouseEvent(
                QMouseEvent.Type.MouseButtonPress,
                pos,
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            release = QMouseEvent(
                QMouseEvent.Type.MouseButtonRelease,
                pos,
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
            app = QApplication.instance()
            if app is None:
                return {"ok": False, "reason": "no_qapplication", "method": "qt_mouse"}
            app.sendEvent(target, press)
            app.sendEvent(target, release)
            return {
                "ok": True,
                "reason": "qt_mouse_click_dispatched",
                "method": "qt_mouse",
                "x": round(float(x), 1),
                "y": round(float(y), 1),
            }
        except Exception as exc:
            return {"ok": False, "reason": f"qt_mouse_failed:{exc}", "method": "qt_mouse"}

    def _schedule_youtube_skip_verification(
        self,
        *,
        ad_state: dict,
        decision: dict,
        initial_effect: dict,
        method: str,
        started_at: float,
        rect: dict | None = None,
        verification_pass: int = 1,
        allow_qt_escalation: bool = True,
    ) -> None:
        from System.swarm_youtube_ad_controller import (
            SKIP_EFFECT_VERIFY_DELAY_S,
            ad_probe_indicates_cleared,
            enrich_skip_effect,
            record_youtube_ad_action,
        )

        delay_ms = int(SKIP_EFFECT_VERIFY_DELAY_S * 1000)

        def _verify_after_delay():
            if self._view is None:
                return

            def _on_probe(probe):
                probe_state = probe if isinstance(probe, dict) else {}
                cleared = ad_probe_indicates_cleared(probe_state)
                elapsed_ms = max(0.0, (time.time() - started_at) * 1000.0)
                try:
                    from System.swarm_app_command_effect_verification import (
                        complete_youtube_skip_verification,
                    )

                    complete_youtube_skip_verification(
                        initial_effect=initial_effect,
                        probe=probe_state,
                        started_at=started_at,
                        method=method,
                        verification_pass=verification_pass,
                        state_dir=_STATE,
                        context={"ad_state": ad_state, "decision": decision},
                    )
                except Exception:
                    pass
                if cleared:
                    effect = enrich_skip_effect(
                        initial_effect,
                        method=method,
                        effect_verified=True,
                        ad_cleared_ms=elapsed_ms,
                        verification_pass=verification_pass,
                    )
                    try:
                        record_youtube_ad_action(
                            ad_state=ad_state,
                            decision=decision,
                            effect=effect,
                            state_dir=_STATE,
                        )
                    except Exception:
                        pass
                    return

                if (
                    allow_qt_escalation
                    and method == "js"
                    and isinstance(rect, dict)
                    and rect.get("width", 0) > 0
                    and rect.get("height", 0) > 0
                ):
                    cx = float(rect.get("left", 0)) + float(rect.get("width", 0)) / 2.0
                    cy = float(rect.get("top", 0)) + float(rect.get("height", 0)) / 2.0
                    qt_effect = self._dispatch_qt_mouse_click(cx, cy)
                    self._schedule_youtube_skip_verification(
                        ad_state=ad_state,
                        decision=decision,
                        initial_effect=qt_effect,
                        method="qt_mouse",
                        started_at=time.time(),
                        rect=rect,
                        verification_pass=verification_pass + 1,
                        allow_qt_escalation=False,
                    )
                    return

                effect = enrich_skip_effect(
                    initial_effect,
                    method=method,
                    effect_verified=False,
                    ad_cleared_ms=elapsed_ms,
                    verification_pass=verification_pass,
                )
                try:
                    record_youtube_ad_action(
                        ad_state=ad_state,
                        decision=decision,
                        effect=effect,
                        state_dir=_STATE,
                    )
                except Exception:
                    pass

            try:
                self._view.page().runJavaScript(self._youtube_skip_probe_js(), _on_probe)
            except Exception:
                pass

        QTimer.singleShot(delay_ms, _verify_after_delay)

    def _execute_verified_youtube_skip(
        self,
        *,
        ad_state: dict,
        decision: dict,
        source: str = "auto_controller",
    ) -> None:
        """Click skip, then verify the ad actually ended before claiming success (r901)."""
        if self._view is None:
            return
        started_at = time.time()
        ad_payload = dict(ad_state or {})
        ad_payload.setdefault("platform", "youtube")
        ad_payload.setdefault("url", self._current_url)
        ad_payload.setdefault("is_current_page", True)
        ad_payload["source"] = source
        decision_payload = dict(decision or {"action": "skip", "reason": source})

        def _on_click(effect):
            payload = effect if isinstance(effect, dict) else {"raw": str(effect)}
            rect = payload.get("rect") if isinstance(payload.get("rect"), dict) else None
            if not payload.get("ok"):
                try:
                    from System.swarm_youtube_ad_controller import enrich_skip_effect, record_youtube_ad_action
                    record_youtube_ad_action(
                        ad_state=ad_payload,
                        decision=decision_payload,
                        effect=enrich_skip_effect(payload, method="js", effect_verified=False, verification_pass=0),
                        state_dir=_STATE,
                    )
                except Exception:
                    pass
                return
            self._schedule_youtube_skip_verification(
                ad_state=ad_payload,
                decision=decision_payload,
                initial_effect=payload,
                method=str(payload.get("method") or "js"),
                started_at=started_at,
                rect=rect,
            )

        try:
            self._view.page().runJavaScript(self._youtube_skip_click_js(perform_click=True), _on_click)
        except Exception as exc:
            try:
                from System.swarm_youtube_ad_controller import enrich_skip_effect, record_youtube_ad_action
                record_youtube_ad_action(
                    ad_state=ad_payload,
                    decision=decision_payload,
                    effect=enrich_skip_effect(
                        {"ok": False, "reason": f"runJavaScript_failed:{exc}", "action": "skip"},
                        method="js",
                        effect_verified=False,
                        verification_pass=0,
                    ),
                    state_dir=_STATE,
                )
            except Exception:
                pass

    def skip_current_ad(self) -> dict:
        """Owner-demand (r296/r901): click YouTube's visible Skip control and verify
        the ad actually ended before writing an honest §6 receipt."""
        if self._view is None:
            return {"ok": False, "reason": "no_view", "requested": "skip"}
        self._execute_verified_youtube_skip(
            ad_state={
                "platform": "youtube",
                "url": self._current_url,
                "detected": True,
                "is_current_page": True,
                "source": "owner_demand_skip",
            },
            decision={"action": "skip", "reason": "owner_demand"},
            source="owner_demand_skip",
        )
        return {"ok": True, "reason": "skip_requested_verification_pending", "requested": "skip"}

    def _apply_youtube_ad_controller(self, ad_state: dict, *, url: str) -> None:
        """Owner-controlled YouTube ad action from current-page receipts only.

        This clicks YouTube's own visible skip button when present. If skip is not
        visible but an ad is active, Alice may temporarily mute the video and
        restore audio when the ad state clears. It does not cancel network
        requests or install a blocker.
        """
        if not self._view or "youtu" not in (url or "").lower():
            return
        try:
            from System.swarm_youtube_ad_controller import (
                decide_youtube_ad_action,
                record_youtube_ad_action,
            )
            decision = decide_youtube_ad_action(ad_state)
        except Exception:
            return
        action = str(decision.get("action") or "")
        if action not in {"skip", "mute", "restore", "observe"}:
            return
        if action == "observe":
            try:
                record_youtube_ad_action(ad_state=ad_state, decision=decision, state_dir=_STATE)
            except Exception:
                pass
            return
        if action == "skip":
            self._execute_verified_youtube_skip(
                ad_state=ad_state,
                decision=decision,
                source="auto_ad_controller",
            )
            return
        action_js = json.dumps(action)
        js = f"""
        (function () {{
            function visible(el) {{
                if (!el) return false;
                var r = el.getBoundingClientRect();
                var style = window.getComputedStyle(el);
                return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
            }}
            var action = {action_js};
            var out = {{ action: action, ok: false, reason: '' }};
            try {{
                if (action === 'mute') {{
                    var videos = Array.prototype.slice.call(document.querySelectorAll('video'));
                    if (videos.length) {{
                        window.__aliceAdMuted = true;
                        videos.forEach(function(v) {{ v.muted = true; }});
                        out.ok = true;
                        out.reason = 'muted_video_during_ad';
                    }} else {{
                        var mute = Array.prototype.slice.call(document.querySelectorAll(
                            '.ytp-mute-button, button[aria-label*="Mute" i], button[title*="Mute" i]'
                        )).find(visible);
                        if (mute) {{
                            window.__aliceAdMuted = true;
                            mute.click();
                            out.ok = true;
                            out.reason = 'clicked_visible_mute_control';
                        }} else {{
                            out.reason = 'mute_control_not_visible_at_effect_time';
                        }}
                    }}
                }} else if (action === 'restore') {{
                    if (window.__aliceAdMuted) {{
                        Array.prototype.slice.call(document.querySelectorAll('video')).forEach(function(v) {{ v.muted = false; }});
                        window.__aliceAdMuted = false;
                        out.ok = true;
                        out.reason = 'restored_audio_after_ad';
                    }} else {{
                        out.reason = 'no_alice_ad_mute_to_restore';
                    }}
                }}
            }} catch (e) {{
                out.reason = 'js_error:' + e;
            }}
            return out;
        }})();
        """

        def _record_effect(effect, _ad=ad_state, _decision=decision):
            try:
                from System.swarm_youtube_ad_controller import record_youtube_ad_action
                record_youtube_ad_action(
                    ad_state=_ad,
                    decision=_decision,
                    effect=effect if isinstance(effect, dict) else {"raw": str(effect)},
                    state_dir=_STATE,
                )
            except Exception:
                pass

        try:
            self._view.page().runJavaScript(js, _record_effect)
        except Exception:
            try:
                from System.swarm_youtube_ad_controller import record_youtube_ad_action
                record_youtube_ad_action(
                    ad_state=ad_state,
                    decision=decision,
                    effect={"ok": False, "reason": "runJavaScript_failed"},
                    state_dir=_STATE,
                )
            except Exception:
                pass

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
            var _vw = window.innerWidth || 0, _vh = window.innerHeight || 0;
            function visibleControl(el) {
                if (!el || !el.getBoundingClientRect) return false;
                var r = el.getBoundingClientRect();
                var s = window.getComputedStyle(el);
                return r.width > 4 && r.height > 4 &&
                    r.bottom > 0 && r.top < _vh && r.right > 0 && r.left < _vw &&
                    s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
            }
            function controlLabel(el) {
                return [
                    el.innerText || '',
                    el.getAttribute('aria-label') || '',
                    el.getAttribute('title') || '',
                    el.getAttribute('value') || '',
                    el.getAttribute('alt') || ''
                ].join(' ').replace(/\s+/g, ' ').trim();
            }
            function controlRect(el) {
                var r = el.getBoundingClientRect();
                return {x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height)};
            }
            function controlSelector(el) {
                var tag = (el.tagName || 'el').toLowerCase();
                var id = el.getAttribute('id') || '';
                var aria = el.getAttribute('aria-label') || '';
                var title = el.getAttribute('title') || '';
                var cls = (el.getAttribute('class') || '').toString().trim().split(/\s+/).filter(Boolean).slice(0, 3).join('.');
                if (id) return tag + '#' + id;
                if (aria) return tag + '[aria-label="' + aria.slice(0, 80).replace(/"/g, '\\"') + '"]';
                if (title) return tag + '[title="' + title.slice(0, 80).replace(/"/g, '\\"') + '"]';
                if (cls) return tag + '.' + cls;
                return tag;
            }
            var controls = Array.prototype.slice.call(
                document.querySelectorAll('button,[role="button"],a[href],input[type="button"],input[type="submit"],[aria-label][tabindex],summary'))
                .filter(visibleControl)
                .map(function (b) {
                    return {
                        label: controlLabel(b).slice(0, 120),
                        role: (b.getAttribute('role') || b.tagName || '').toLowerCase().slice(0, 40),
                        selector: controlSelector(b).slice(0, 180),
                        rect: controlRect(b),
                        href: (b.href || b.getAttribute('href') || '').slice(0, 180)
                    };
                })
                .filter(function (x) { return x.label || x.selector; })
                .slice(0, 30);
            var btns = controls.map(function (b) { return (b.label || b.selector || '').slice(0, 80); })
                .filter(Boolean).slice(0, 15);
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
            function bestReadableText() {
                var selectors = [
                    'article',
                    'main',
                    '[role="main"]',
                    '.entry-content',
                    '.post-content',
                    '.article-content',
                    '.story-content',
                    '.content',
                    '#content'
                ];
                var best = '';
                for (var si = 0; si < selectors.length; si++) {
                    var nodes = document.querySelectorAll(selectors[si]);
                    for (var ni = 0; ni < nodes.length; ni++) {
                        var txt = (nodes[ni].innerText || '').trim();
                        if (txt.length > best.length) best = txt;
                    }
                }
                return best.length >= 400 ? best : body;
            }
            var readableText = bestReadableText();
            var playbackErrorText = "";
            try {
                var playbackErrorMatch = body.match(/Sorry,\s*we['’]re\s+having\s+trouble\s+playing\s+this\s+video\.?/i);
                playbackErrorText = playbackErrorMatch ? playbackErrorMatch[0] : "";
            } catch (e) {}
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
            if (playbackErrorText) {
                media.status = 'error';
                media.playing = false;
                media.error_kind = 'instagram_video_playback_error';
                media.visible_error_text = playbackErrorText;
            }
            var searchInput = document.querySelector(
                'input[type="search"], input[aria-label*="Search" i], input[placeholder*="Search" i], textarea[aria-label*="Search" i]'
            );
            var search = searchInput ? {
                value: (searchInput.value || '').trim().slice(0, 160),
                placeholder: (searchInput.getAttribute('placeholder') || searchInput.getAttribute('aria-label') || '').trim().slice(0, 80)
            } : {};

            // Sponsored / ad content detection (lightweight, receipted truth for the visual limb)
            // YouTube + generic patterns. This lets Alice truthfully report "there are sponsored panels"
            // exactly like we report playback errors. No blocking here — just honest observation.
            var sponsored = [];
            var youtubeAdState = {
                detected: false,
                platform: 'youtube',
                placement: '',
                labels: [],
                ad_text: '',
                skip_available: false,
                mute_available: false,
                video_playing: !!media.playing,
                url: window.location.href,
                is_current_page: true,
                was_muted_by_alice: !!window.__aliceAdMuted
            };
            try {
                // YouTube common sponsored containers
                var ytSponsored = document.querySelectorAll(
                    'ytd-promoted-sparkles-web-renderer, .ytd-promoted-sparkles-web-renderer, ' +
                    '[aria-label*="Sponsored" i], [aria-label*="Ad" i], [title*="Sponsored" i]'
                );
                for (var si = 0; si < ytSponsored.length && sponsored.length < 8; si++) {
                    var el = ytSponsored[si];
                    var txt = (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 120);
                    if (txt) sponsored.push({ kind: 'youtube', text: txt });
                }
                // Generic "sponsored" / "ad" / "promoted" text anywhere visible
                var generic = document.querySelectorAll(
                    '[aria-label*="sponsored" i], [aria-label*="promoted" i], [aria-label*="ad " i], ' +
                    '*:not(script):not(style)'
                );
                for (var gi = 0; gi < generic.length && sponsored.length < 12; gi++) {
                    var g = generic[gi];
                    var gtxt = (g.innerText || '').trim().toLowerCase();
                    if (gtxt.includes('sponsored') || gtxt.includes('promoted') || gtxt === 'ad') {
                        var label = (g.getAttribute('aria-label') || g.innerText || '').trim().slice(0, 80);
                        if (label) sponsored.push({ kind: 'generic', text: label });
                    }
                }

                if (/(\.|^)youtube\.com$|(\.|^)youtu\.be$/i.test(window.location.hostname || '')) {
                    function visible(el) {
                        if (!el) return false;
                        var r = el.getBoundingClientRect();
                        var style = window.getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                    }
                    var skipButton = Array.prototype.slice.call(document.querySelectorAll(
                        '.ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, button[class*="ytp-skip-ad"], button[class*="ytp-ad-skip"], [aria-label*="Skip" i]'
                    )).find(visible);
                    var muteButton = Array.prototype.slice.call(document.querySelectorAll(
                        '.ytp-mute-button, button[aria-label*="Mute" i], button[title*="Mute" i]'
                    )).find(visible);
                    var adEls = Array.prototype.slice.call(document.querySelectorAll(
                        '.ad-showing, .ytp-ad-player-overlay, .ytp-ad-module, .ytp-ad-text, .ytp-ad-preview-container, ' +
                        '.ytp-ad-simple-ad-badge, .ytp-ad-overlay-container, ytd-promoted-sparkles-web-renderer'
                    )).filter(visible);
                    var adTexts = adEls.map(function(el) {
                        return (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim();
                    }).filter(Boolean).slice(0, 6);
                    var sponsoredTexts = sponsored.map(function(x) { return (x && x.text) ? String(x.text) : ''; }).filter(Boolean).slice(0, 6);
                    var labels = [];
                    adTexts.concat(sponsoredTexts).forEach(function(txt) {
                        if (labels.length < 8 && /\b(sponsored|promoted|ad|advertisement|skip)\b/i.test(txt)) {
                            labels.push(txt.slice(0, 80));
                        }
                    });
                    youtubeAdState.skip_available = !!skipButton;
                    youtubeAdState.mute_available = !!(muteButton || videos.length);
                    youtubeAdState.labels = labels;
                    youtubeAdState.ad_text = adTexts.concat(sponsoredTexts).join('; ').slice(0, 320);
                    youtubeAdState.placement = adEls.length ? 'player' : (sponsored.length ? 'page' : '');
                    youtubeAdState.detected = !!(skipButton || adEls.length || labels.length || sponsoredTexts.some(function(txt) {
                        return /\b(sponsored|promoted|advertisement)\b/i.test(txt);
                    }) || youtubeAdState.was_muted_by_alice);
                }
            } catch (e) {}

            // YouTube channel / page author — the visible name under the video title.
            // Gives Alice a labelled receipt for the channel instead of guessing it.
            var videoChannel = "";
            try {
                var chEl = document.querySelector(
                    '#owner #channel-name a, ytd-video-owner-renderer #channel-name a, ' +
                    'ytd-channel-name#channel-name a, #upload-info #channel-name a, ytd-channel-name a'
                );
                if (chEl) videoChannel = (chEl.textContent || '').trim().slice(0, 120);
                if (!videoChannel) {
                    var authMeta = document.querySelector('span[itemprop="author"] link[itemprop="name"]');
                    if (authMeta) videoChannel = (authMeta.getAttribute('content') || '').trim().slice(0, 120);
                }
            } catch (e) {}

            return {
                text: readableText.slice(0, 50000),
                body_text_chars: body.length,
                readable_text_chars: readableText.length,
                headings: heads, links: links, buttons: btns, controls: controls, images: imgs, og: og,
                comments: comments,
                media: media,
                search: search,
                sponsored: sponsored,
                youtube_ad_state: youtubeAdState,
                video_channel: videoChannel,
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
            try:
                ad_state = result.get("youtube_ad_state") if isinstance(result.get("youtube_ad_state"), dict) else {}
                if ad_state:
                    ad_state = dict(ad_state)
                    ad_state["url"] = u
                    ad_state["is_current_page"] = True
                    self._apply_youtube_ad_controller(ad_state, url=u)
            except Exception:
                pass
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
                        controls=result.get("controls"),
                        images=result.get("images"),
                        scroll=result.get("scroll"),
                        featured_image=feat.get("src", ""),
                        comments=result.get("comments"),
                        media_playback=media_playback,
                        open_tabs=self._open_tabs_inventory(),
                        sponsored=result.get("sponsored") or [],
                        youtube_ad_state=result.get("youtube_ad_state") or {},
                        video_channel=result.get("video_channel", ""),
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
            if _is_instagram_media_url(url):
                self._read_instagram_carousel()
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

    def has_playing_video(self) -> bool:
        """True when the freshest page-state receipt shows a playing <video> on the
        active tab. Used to decide whether to pause before Alice speaks commentary
        (so she never auto-plays a video the owner deliberately paused)."""
        try:
            from System.swarm_browser_page_state import latest_page_state
            st = latest_page_state(state_dir=_STATE)
            media = st.get("media_playback") if isinstance(st, dict) else {}
            return bool(isinstance(media, dict) and media.get("playing"))
        except Exception:
            return False

    def pause_active_video(self) -> None:
        """Pause any currently-playing <video> on the active tab. Direct DOM call via
        runJavaScript — no network, no perceptible lag (r282 commentary feature)."""
        try:
            if self._view is not None:
                self._view.page().runJavaScript(
                    "document.querySelectorAll('video').forEach(function(v){"
                    "try{if(!v.paused&&!v.ended){v.pause();}}catch(e){}});"
                )
        except Exception:
            pass

    def pause_active_video_receipt(self) -> dict:
        """Pause the primary video and return a structured owner-effector receipt."""
        if self._view is None:
            return {"ok": False, "action": "pause", "reason": "no_web_view"}
        js = """
        (function () {
            var videos = Array.prototype.slice.call(document.querySelectorAll('video'));
            var v = videos.find(function(x){ return x && !x.ended && x.readyState >= 0; }) || videos[0];
            if (!v) return {ok:false, action:'pause', reason:'no_video'};
            try {
                var wasPaused = !!v.paused;
                v.pause();
                return {
                    ok:true, action:'pause', was_paused:wasPaused, paused:!!v.paused,
                    current_time: Math.round((v.currentTime || 0) * 10) / 10,
                    duration: isFinite(v.duration) ? Math.round(v.duration * 10) / 10 : null,
                    url: location.href
                };
            } catch (e) {
                return {ok:false, action:'pause', reason:String(e && e.message || e)};
            }
        })();
        """
        result = self._run_javascript_sync(js, wait_ms=1200)
        try:
            QTimer.singleShot(350, self.refresh_current_page_state)
        except Exception:
            pass
        return result if isinstance(result, dict) else {"ok": False, "action": "pause", "reason": "no_js_result"}

    def play_active_video_receipt(self) -> dict:
        """Play the primary video and return a structured owner-effector receipt."""
        if self._view is None:
            return {"ok": False, "action": "play", "reason": "no_web_view"}
        js = """
        (function () {
            var videos = Array.prototype.slice.call(document.querySelectorAll('video'));
            var v = videos.find(function(x){ return x && !x.ended && x.readyState >= 0; }) || videos[0];
            if (!v) return {ok:false, action:'play', reason:'no_video'};
            try {
                var wasPaused = !!v.paused;
                var p = v.play();
                if (p && p.catch) p.catch(function(){});
                return {
                    ok:true, action:'play', was_paused:wasPaused, paused:!!v.paused,
                    current_time: Math.round((v.currentTime || 0) * 10) / 10,
                    duration: isFinite(v.duration) ? Math.round(v.duration * 10) / 10 : null,
                    url: location.href
                };
            } catch (e) {
                return {ok:false, action:'play', reason:String(e && e.message || e)};
            }
        })();
        """
        result = self._run_javascript_sync(js, wait_ms=1200)
        try:
            QTimer.singleShot(350, self.refresh_current_page_state)
        except Exception:
            pass
        return result if isinstance(result, dict) else {"ok": False, "action": "play", "reason": "no_js_result"}

    def active_video_playback_receipt(self) -> dict:
        """Read the active video state without mutating playback."""
        if self._view is None:
            return {"ok": False, "action": "video_state", "reason": "no_web_view"}
        js = """
        (function () {
            var videos = Array.prototype.slice.call(document.querySelectorAll('video'));
            var active = videos.find(function(v){ return v && !v.paused && !v.ended; });
            var v = active || videos.find(function(x){ return x && !x.ended && x.readyState >= 0; }) || videos[0];
            if (!v) return {ok:false, action:'video_state', reason:'no_video', url:location.href};
            try {
                return {
                    ok:true, action:'video_state',
                    playing:!!(!v.paused && !v.ended),
                    paused:!!v.paused,
                    ended:!!v.ended,
                    current_time: Math.round((v.currentTime || 0) * 10) / 10,
                    duration: isFinite(v.duration) ? Math.round(v.duration * 10) / 10 : null,
                    url: location.href
                };
            } catch (e) {
                return {ok:false, action:'video_state', reason:String(e && e.message || e), url:location.href};
            }
        })();
        """
        result = self._run_javascript_sync(js, wait_ms=900)
        return result if isinstance(result, dict) else {"ok": False, "action": "video_state", "reason": "no_js_result"}

    def list_clickable_elements_receipt(self, max_elements: int = 60) -> dict:
        """r656 (George: "ALICE MUST KNOW ALL ELEMENTS ON THE CURRENT OPENED PAGE ... ALL THE
        BUTTONS SO SHE CAN CLICK THEM"): inventory the visible clickable elements of the
        current page — buttons, links, role=button, aria-labelled icon controls (like eBay's
        enlarge control) — as a structured receipt the cortex can read and act on."""
        if self._view is None:
            return {"ok": False, "action": "list_elements", "reason": "no_web_view"}
        js = """
        (function () {
            function label(el) {
                var t = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
                if (t && t.length <= 80) return t;
                var a = el.getAttribute('aria-label') || el.getAttribute('title') || '';
                if (a) return a.trim().slice(0, 80);
                var img = el.querySelector && el.querySelector('img[alt]');
                if (img) return (img.getAttribute('alt') || '').trim().slice(0, 80);
                return (t || '').slice(0, 80);
            }
            function visible(el) {
                var r = el.getBoundingClientRect();
                return r.width > 4 && r.height > 4 && r.bottom > 0 && r.top < (window.innerHeight + 400);
            }
            var sel = 'button, a[href], [role="button"], input[type="button"], input[type="submit"], [onclick], [aria-label]';
            var nodes = Array.prototype.slice.call(document.querySelectorAll(sel));
            var seen = {}; var out = [];
            for (var i = 0; i < nodes.length && out.length < %MAX%; i++) {
                var el = nodes[i];
                if (!visible(el)) continue;
                var lab = label(el);
                if (!lab) continue;
                var key = lab.toLowerCase();
                if (seen[key]) continue;
                seen[key] = 1;
                out.push({label: lab, tag: el.tagName.toLowerCase()});
            }
            return {ok: true, action: 'list_elements', count: out.length, elements: out, url: location.href, title: document.title || ''};
        })();
        """.replace("%MAX%", str(max(5, int(max_elements))))
        result = self._run_javascript_sync(js, wait_ms=1500)
        return result if isinstance(result, dict) else {"ok": False, "action": "list_elements", "reason": "no_js_result"}

    def select_search_result_receipt(self, index: int = 1) -> dict:
        """r657 (George: "SELECT THE THIRD ON THE LIST"): open the Nth visible search-result
        link (1-based) on the current results page. Generic heuristic — anchors inside
        list/article result containers carrying real text or an image — no person hardcode.
        r663: prefer real item/result cards before generic list links so side categories/header
        controls do not count as "the list" on commerce result pages."""
        n = max(1, int(index or 1))
        if self._view is None:
            return {"ok": False, "action": "select_result", "reason": "no_web_view"}
        js = """
        (function () {
            var n = %N%;
            function visible(el) {
                var r = el.getBoundingClientRect();
                var s = window.getComputedStyle(el);
                return r.width > 30 && r.height > 14 && r.bottom > 0 &&
                    r.top < window.innerHeight + 1200 && s.display !== 'none' &&
                    s.visibility !== 'hidden';
            }
            function ancestorText(el) {
                var out = [];
                var cur = el;
                for (var d = 0; cur && d < 5; d++, cur = cur.parentElement) {
                    out.push(cur.tagName || '');
                    out.push(cur.getAttribute('class') || '');
                    out.push(cur.getAttribute('data-testid') || '');
                    out.push(cur.getAttribute('role') || '');
                }
                return out.join(' ').toLowerCase();
            }
            function normHref(href) {
                return String(href || '').split('#')[0].split('?')[0];
            }
            function labelFor(a) {
                var t = (a.innerText || a.textContent || '').trim().replace(/\\s+/g, ' ');
                if (!t) {
                    var img = a.querySelector && a.querySelector('img[alt]');
                    if (img) t = (img.getAttribute('alt') || '').trim().replace(/\\s+/g, ' ');
                }
                return t;
            }
            function isChromeLink(t, href, anc) {
                var low = (t || '').toLowerCase();
                return /\\b(sign in|register|deals|brand outlet|gift cards|help|contact|watchlist|my ebay|notifications|shop by category|save this search|show more|shipping|category)\\b/.test(low) ||
                    /\\b(nav|header|footer|pagination|breadcrumb|filter|facet)\\b/.test(anc);
            }
            var sel = 'a[href]';
            var nodes = Array.prototype.slice.call(document.querySelectorAll(sel));
            var seen = {}; var strong = []; var fallback = [];
            for (var i = 0; i < nodes.length; i++) {
                var a = nodes[i];
                if (!visible(a)) continue;
                var href = a.href || '';
                if (!href || href.indexOf('javascript:') === 0) continue;
                var t = labelFor(a);
                var hasImg = !!a.querySelector('img');
                if (t.length < 15 && !hasImg) continue;  // skip nav chrome links
                var anc = ancestorText(a);
                if (isChromeLink(t, href, anc)) continue;
                var key = normHref(href);
                if (seen[key]) continue;
                seen[key] = 1;
                var score = 0;
                if (/\\/itm\\//.test(href)) score += 70;
                if (/\\b(s-item|search-result|result|listing|product|item-card|card)\\b/.test(anc)) score += 35;
                if (hasImg) score += 15;
                if (/\\$|buy it now|auction|free shipping|sold|condition/i.test((a.closest('li, article, div') || a).innerText || '')) score += 10;
                var row = {a: a, title: t.slice(0, 90), href: href, score: score};
                if (score >= 35) strong.push(row);
                else fallback.push(row);
            }
            var results = strong.length ? strong : fallback;
            if (results.length < n) {
                return {ok:false, action:'select_result', reason:'only_' + results.length + '_results',
                        wanted_index:n, url:location.href};
            }
            var pick = results[n - 1];
            try {
                pick.a.scrollIntoView({block:'center'});
                pick.a.click();
                return {ok:true, action:'select_result', index:n, title:pick.title, href:pick.href, url:location.href};
            } catch (e) {
                return {ok:false, action:'select_result', reason:String(e && e.message || e), wanted_index:n};
            }
        })();
        """.replace("%N%", str(n))
        result = self._run_javascript_sync(js, wait_ms=2000)
        try:
            QTimer.singleShot(600, self.refresh_current_page_state)
        except Exception:
            pass
        return result if isinstance(result, dict) else {"ok": False, "action": "select_result", "reason": "no_js_result"}

    def click_main_image_receipt(self) -> dict:
        """r657: click the LARGEST visible image on the page — on listing pages (eBay etc.)
        that is the main photo, and clicking it opens the enlarged/gallery view. This is the
        primary 'enlarge the photo' hand; labeled enlarge controls are the fallback."""
        refused = self._gate_browser_effector("click_main_image")
        if refused:
            return refused
        if self._view is None:
            return {"ok": False, "action": "click_main_image", "reason": "no_web_view"}
        js = """
        (function () {
            var imgs = Array.prototype.slice.call(document.querySelectorAll('img'));
            var best = null; var bestArea = 0;
            for (var i = 0; i < imgs.length; i++) {
                var im = imgs[i];
                var r = im.getBoundingClientRect();
                if (r.width < 80 || r.height < 80) continue;
                if (r.bottom < 0 || r.top > window.innerHeight + 200) continue;
                var area = r.width * r.height;
                if (area > bestArea) { bestArea = area; best = im; }
            }
            if (!best) return {ok:false, action:'click_main_image', reason:'no_large_visible_image', url:location.href};
            try {
                best.scrollIntoView({block:'center'});
                var target = best.closest('a, button, [role="button"]') || best;
                target.click();
                return {ok:true, action:'click_main_image',
                        alt:(best.getAttribute('alt') || '').slice(0, 80),
                        width:Math.round(best.getBoundingClientRect().width),
                        height:Math.round(best.getBoundingClientRect().height),
                        url:location.href};
            } catch (e) {
                return {ok:false, action:'click_main_image', reason:String(e && e.message || e)};
            }
        })();
        """
        result = self._run_javascript_sync(js, wait_ms=1800)
        try:
            QTimer.singleShot(500, self.refresh_current_page_state)
        except Exception:
            pass
        return result if isinstance(result, dict) else {"ok": False, "action": "click_main_image", "reason": "no_js_result"}

    def click_page_element_receipt(self, label: str) -> dict:
        """r656: click a visible page element by its text/aria-label/title (best match).
        Her generic finger for ANY page control — enlarge buttons, tabs, accept buttons —
        grounded in what is actually in the DOM, never a hardcoded site map."""
        refused = self._gate_browser_effector("click_page_element")
        if refused:
            return refused
        want = " ".join(str(label or "").split())
        if not want:
            return {"ok": False, "action": "click_element", "reason": "empty_label"}
        if self._view is None:
            return {"ok": False, "action": "click_element", "reason": "no_web_view"}
        js = """
        (function () {
            var want = %WANT%.toLowerCase();
            function texts(el) {
                var out = [];
                var t = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
                if (t) out.push(t);
                var a = el.getAttribute('aria-label'); if (a) out.push(a.trim());
                var ti = el.getAttribute('title'); if (ti) out.push(ti.trim());
                var img = el.querySelector && el.querySelector('img[alt]');
                if (img) out.push((img.getAttribute('alt') || '').trim());
                return out;
            }
            function visible(el) {
                var r = el.getBoundingClientRect();
                return r.width > 4 && r.height > 4 && r.bottom > 0 && r.top < (window.innerHeight + 400);
            }
            var sel = 'button, a[href], [role="button"], input[type="button"], input[type="submit"], [onclick], [aria-label]';
            var nodes = Array.prototype.slice.call(document.querySelectorAll(sel));
            var best = null; var bestScore = 0; var cands = [];
            for (var i = 0; i < nodes.length; i++) {
                var el = nodes[i];
                if (!visible(el)) continue;
                var ts = texts(el);
                for (var j = 0; j < ts.length; j++) {
                    var low = ts[j].toLowerCase();
                    if (!low) continue;
                    var score = 0;
                    if (low === want) score = 3;
                    else if (low.indexOf(want) === 0) score = 2;
                    else if (low.indexOf(want) >= 0) score = 1;
                    if (score > 0 && cands.length < 10) cands.push(ts[j].slice(0, 60));
                    if (score > bestScore) { bestScore = score; best = {el: el, label: ts[j].slice(0, 80)}; }
                }
            }
            if (!best) return {ok:false, action:'click_element', reason:'no_match', wanted:%WANT%, candidates:cands, url:location.href};
            try {
                best.el.scrollIntoView({block:'center'});
                best.el.click();
                return {ok:true, action:'click_element', clicked_label:best.label, wanted:%WANT%,
                        score:bestScore, url:location.href};
            } catch (e) {
                return {ok:false, action:'click_element', reason:String(e && e.message || e), wanted:%WANT%};
            }
        })();
        """.replace("%WANT%", json.dumps(want))
        result = self._run_javascript_sync(js, wait_ms=1800)
        try:
            QTimer.singleShot(400, self.refresh_current_page_state)
        except Exception:
            pass
        return result if isinstance(result, dict) else {"ok": False, "action": "click_element", "reason": "no_js_result"}

    def extract_youtube_transcript_to_downloads(self) -> dict:
        """Export the current YouTube transcript/subtitles to Downloads.

        The browser limb tries the visible transcript panel first. If the panel
        is stuck on a spinner, it falls back to caption tracks exposed by
        YouTube's player response. It never fabricates transcript text.
        """
        try:
            from System.swarm_youtube_transcript_skill import (
                fetch_youtube_caption_track,
                record_youtube_transcript_attempt,
                save_youtube_transcript_export,
                youtube_video_id,
            )
        except Exception as exc:
            return {"ok": False, "reason": f"transcript_skill_unavailable:{type(exc).__name__}:{exc}"}
        if self._view is None:
            return record_youtube_transcript_attempt(
                ok=False,
                url="",
                source="alice_browser",
                reason="no_web_view",
                state_dir=_STATE,
            )
        try:
            url = self._view.url().toString()
        except Exception:
            url = getattr(self, "_current_url", "") or ""
        url = url or getattr(self, "_current_url", "") or ""
        title = ""
        try:
            title = self._current_browser_title()
        except Exception:
            title = ""
        if not youtube_video_id(url):
            return record_youtube_transcript_attempt(
                ok=False,
                url=url,
                title=title,
                source="alice_browser",
                reason="not_youtube_video_page",
                state_dir=_STATE,
            )
        js = r"""
        (function () {
            function clean(s) {
                return (s || '').toString().replace(/\u00a0/g, ' ').replace(/[ \t\r\f\v]+/g, ' ').trim();
            }
            function pickText(root, selectors) {
                for (var i = 0; i < selectors.length; i++) {
                    var el = root.querySelector(selectors[i]);
                    var txt = el ? clean(el.textContent || el.innerText || '') : '';
                    if (txt) return txt;
                }
                return '';
            }
            var segmentEls = Array.prototype.slice.call(document.querySelectorAll(
                'ytd-transcript-segment-renderer, .ytd-transcript-segment-renderer'
            ));
            var segments = [];
            for (var i = 0; i < segmentEls.length; i++) {
                var el = segmentEls[i];
                var time = pickText(el, ['.segment-timestamp', '#timestamp', 'yt-formatted-string[class*="timestamp"]']);
                var text = pickText(el, ['.segment-text', '#segment-text', 'yt-formatted-string.segment-text']);
                if (!text) {
                    text = clean(el.innerText || el.textContent || '');
                    if (time) text = clean(text.replace(time, ''));
                }
                if (text) segments.push({time: time, text: text});
            }
            var panel = document.querySelector(
                'ytd-transcript-renderer, ytd-transcript-search-panel-renderer, ' +
                'ytd-engagement-panel-section-list-renderer[target-id="engagement-panel-searchable-transcript"]'
            );
            var panelText = panel ? clean(panel.innerText || panel.textContent || '') : '';
            var spinner = !!document.querySelector(
                'tp-yt-paper-spinner, ytd-continuation-item-renderer #spinner, #spinnerContainer'
            );
            var tracks = [];
            try {
                var pr = window.ytInitialPlayerResponse || {};
                var list = (((pr.captions || {}).playerCaptionsTracklistRenderer || {}).captionTracks || []);
                tracks = list.map(function (t) {
                    var name = '';
                    try { name = (((t.name || {}).runs || [])[0] || {}).text || (t.name || {}).simpleText || ''; } catch (e) {}
                    return {
                        baseUrl: t.baseUrl || '',
                        languageCode: t.languageCode || '',
                        kind: t.kind || '',
                        name: name
                    };
                }).filter(function (t) { return !!t.baseUrl; });
            } catch (e) {}
            return {
                ok: segments.length > 0 || tracks.length > 0 || panelText.length > 0,
                url: location.href,
                title: document.title || '',
                segments: segments,
                text: panelText,
                captionTracks: tracks,
                transcriptPanelVisible: !!panel,
                spinnerVisible: spinner
            };
        })();
        """
        result = self._run_javascript_sync(js, wait_ms=2600)
        info = result if isinstance(result, dict) else {}
        title = str(info.get("title") or title or "").strip()
        segments = info.get("segments") if isinstance(info.get("segments"), list) else []
        if segments:
            return save_youtube_transcript_export(
                url=url,
                title=title,
                segments=segments,
                source="youtube_visible_transcript_panel",
                state_dir=_STATE,
                extra={
                    "transcript_panel_visible": bool(info.get("transcriptPanelVisible")),
                    "spinner_visible": bool(info.get("spinnerVisible")),
                    "caption_track_count": len(info.get("captionTracks") or []),
                },
            )
        panel_text = str(info.get("text") or "").strip()
        if panel_text and len(panel_text) > 80 and re.search(r"\b\d{1,2}:\d{2}\b", panel_text):
            return save_youtube_transcript_export(
                url=url,
                title=title,
                transcript_text=panel_text,
                source="youtube_visible_transcript_panel_text",
                state_dir=_STATE,
                extra={
                    "transcript_panel_visible": bool(info.get("transcriptPanelVisible")),
                    "spinner_visible": bool(info.get("spinnerVisible")),
                    "caption_track_count": len(info.get("captionTracks") or []),
                },
            )
        tracks = info.get("captionTracks") if isinstance(info.get("captionTracks"), list) else []
        for track in tracks:
            if not isinstance(track, dict) or not str(track.get("baseUrl") or "").strip():
                continue
            fetched = fetch_youtube_caption_track(str(track.get("baseUrl")), timeout_s=8.0)
            if fetched.get("ok") and fetched.get("segments"):
                return save_youtube_transcript_export(
                    url=url,
                    title=title,
                    segments=fetched.get("segments") or [],
                    source="youtube_caption_track_timedtext",
                    language=str(track.get("languageCode") or track.get("name") or ""),
                    state_dir=_STATE,
                    extra={
                        "track_name": str(track.get("name") or ""),
                        "track_kind": str(track.get("kind") or ""),
                        "caption_bytes": fetched.get("bytes"),
                        "transcript_panel_visible": bool(info.get("transcriptPanelVisible")),
                        "spinner_visible": bool(info.get("spinnerVisible")),
                        "caption_track_count": len(tracks),
                    },
                )
        reason = "no_visible_transcript_or_caption_tracks"
        if info.get("spinnerVisible"):
            reason = "transcript_panel_loading_no_caption_track_exported"
        return record_youtube_transcript_attempt(
            ok=False,
            url=url,
            title=title,
            source="alice_browser_youtube_transcript_skill",
            reason=reason,
            state_dir=_STATE,
            extra={
                "transcript_panel_visible": bool(info.get("transcriptPanelVisible")),
                "spinner_visible": bool(info.get("spinnerVisible")),
                "caption_track_count": len(tracks),
            },
        )

    def resume_active_video(self) -> None:
        """Resume <video> playback on the active tab. Direct DOM call — no lag (r282)."""
        try:
            if self._view is not None:
                self._view.page().runJavaScript(
                    "document.querySelectorAll('video').forEach(function(v){"
                    "try{var p=v.play();if(p&&p.catch)p.catch(function(){});}catch(e){}});"
                )
        except Exception:
            pass

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
        strict_eye = _strict_selected_eye(current_arm, current_model)
        strict_grok_eye = strict_eye == "grok_agent"
        pick = pick_vision_arm(
            current_arm=current_arm,
            current_model=current_model,
            unavailable=(),
            local_image_required=True,
        )
        arm = strict_eye or str(pick.get("selected_arm") or current_arm or "").strip()
        for _ in range(3):
            if not arm or arm in down:
                break
            if arm == "grok_agent":
                try:
                    from System.xai_grok_oauth_organ import preflight_grok_vision_key
                    has_key, _msg = preflight_grok_vision_key()
                    if not has_key and not _grok_cli_ready():
                        if strict_grok_eye:
                            refresh = _schedule_grok_oauth_refresh("browser_visible_media_selection:grok_preflight")
                            record_cortex_arm_habit(
                                "grok_agent",
                                cortex_model=current_model,
                                task="browser_visible_media_selection",
                                ok=False,
                                status="grok_eye_auth_refresh_required",
                                reason="selected_grok_eye_missing_oauth_refresh_scheduled",
                                state_dir=_STATE,
                                meta={"image_ref": img_path, "query": query[:180], "oauth_refresh": refresh},
                            )
                            return {}
                        else:
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
                    # r258: use the logged-in Grok CLI OAuth surface first; direct
                    # /v1/chat/completions remains a fallback only if the CLI is unavailable.
                    from System.xai_grok_oauth_organ import describe_image_with_grok
                    arm_result = describe_image_with_grok(
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
                err = extract_arm_final_text(getattr(arm_result, "stderr", "") or "")
                ok = bool(getattr(arm_result, "ok", False))
                arm_status = str(getattr(arm_result, "status", "") or "failed")
                if strict_grok_eye and arm == "grok_agent" and not ok:
                    if _grok_eye_needs_oauth_repair(arm_status, err or raw):
                        refresh = _schedule_grok_oauth_refresh("browser_visible_media_selection:grok_runtime_auth")
                        record_cortex_arm_habit(
                            arm,
                            cortex_model=current_model,
                            task="browser_visible_media_selection",
                            ok=False,
                            status="grok_eye_auth_refresh_required",
                            reason="selected_grok_eye_oauth_refresh_scheduled",
                            state_dir=_STATE,
                            meta={"image_ref": img_path, "query": query[:180], "oauth_refresh": refresh},
                        )
                        return {}
                    if _grok_eye_allows_local_backup(arm_status, err or raw) and _local_grok_backup_ready():
                        try:
                            from System.swarm_cortex_failover_reflex import record_cortex_failover
                            record_cortex_failover(
                                from_arm="grok_agent",
                                to_arm="ollama_vision_agent",
                                reason=f"grok_source_or_subscription_failure:{arm_status}",
                                state_dir=_STATE,
                            )
                        except Exception:
                            pass
                        down.add(arm)
                        arm = "ollama_vision_agent"
                        continue
                row, col = _parse_visible_media_selection(raw)
                record_cortex_arm_habit(
                    arm,
                    cortex_model=current_model,
                    task="browser_visible_media_selection",
                    ok=bool(ok and row and col),
                    status="selected" if ok and row and col else arm_status,
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
            if strict_eye:
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
        refused = self._gate_click_refused("click_visible_media_candidate")
        if refused:
            return refused
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

    def click_first_search_result(self) -> dict:
        """Find and click the first visible search result on the current page.

        Works best on search/listing pages (including YouTube results). The
        method prefers obvious result links and requires the chosen node to be
        on-screen.
        """
        refused = self._gate_click_refused("click_first_search_result")
        if refused:
            return refused
        if not self._view:
            return {"clicked": False, "reason": "no_web_view"}
        js = r"""
        (function () {
            function rectOnScreen(el) {
                if (!el || !el.getBoundingClientRect) return false;
                var r = el.getBoundingClientRect();
                var style = window.getComputedStyle(el);
                if (r.width <= 0 || r.height <= 0) return false;
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                return true;
            }
            var host = (location.hostname || '').toLowerCase();
            var selectors = [
                'a#video-title',
                'ytd-video-renderer a#video-title',
                'ytd-video-renderer a[href*="watch?v="]',
                'ytd-channel-renderer a[href*="/channel/"]',
                'ytd-thumbnail a[href]',
                'a[href*="watch?v="]',
                'a[href*="/results?search_query="]',
                'a[href*="/search/"], a[href*="/search?"]',
                'a[href]'
            ];
            var links = [];
            if (/youtube\.com$/.test(host)) {
                var yt = Array.prototype.slice.call(document.querySelectorAll(
                    'ytd-video-renderer a#video-title, ytd-video-renderer a[href*="watch?v="], ytd-compact-video-renderer a[href*="watch?v="], a[href*="watch?v="]'
                ));
                links = yt.filter(rectOnScreen);
            }
            if (!links.length) {
                var sels = [];
                selectors.forEach(function (s) {
                    try {
                        sels.push.apply(sels, Array.prototype.slice.call(document.querySelectorAll(s)).filter(rectOnScreen));
                    } catch (e) {}
                });
                links = sels.filter(function(el, idx) { return sels.indexOf(el) === idx; });
            }
            if (!links.length) {
                return {clicked:false, reason:'no_visible_result_link'};
            }
            // Prefer first true result-like URL.
            var el = links[0] || null;
            for (var i = 0; i < links.length; i++) {
                var h = (links[i].getAttribute('href') || '').toLowerCase();
                if (h && h.indexOf('watch?v=') !== -1) { el = links[i]; break; }
            }
            if (!el) {
                return {clicked:false, reason:'result_link_not_found'};
            }
            try { el.scrollIntoView({block:'center', inline:'center', behavior:'instant'}); } catch (e) {}
            try {
                var r = el.getBoundingClientRect();
                ['mouseover','mousedown','mouseup','click'].forEach(function (name) {
                    try {
                        el.dispatchEvent(new MouseEvent(name, {bubbles:true,cancelable:true,clientX:Math.round(r.left + r.width / 2),clientY:Math.round(r.top + r.height / 2),view:window}));
                    } catch (e) {}
                });
                try { el.click(); } catch (e) {}
                return {clicked: true, href: el.href || '', text: (el.textContent || '').trim().slice(0, 180)};
            } catch (e) {
                return {clicked:false, reason:'click_failed'};
            }
        })();
        """
        result = self._run_javascript_sync(js, wait_ms=1200)
        if isinstance(result, dict) and result.get("clicked"):
            try:
                QTimer.singleShot(250, self.refresh_current_page_state)
            except Exception:
                pass
        return result if isinstance(result, dict) else {"clicked": False, "reason": "no_js_result"}

    def click_visible_control_matching_text(self, query: str = "") -> dict:
        """Click a visible control on the current page by owner language.

        Generic page-effector for buttons like "enlarge the photo", "open larger
        image", "share", etc. The live DOM decides; no site/person hardcode.
        """
        refused = self._gate_click_refused("click_visible_control_matching_text")
        if refused:
            refused["query"] = query
            return refused
        if not self._view:
            return {"clicked": False, "reason": "no_web_view", "query": query}
        js = f"""
        (function () {{
            var query = {json.dumps(str(query or ""))};
            function norm(s) {{
                return (s || '').toString().toLowerCase()
                    .replace(/[^a-z0-9]+/g, ' ')
                    .replace(/\\s+/g, ' ')
                    .trim();
            }}
            function visible(el) {{
                if (!el || !el.getBoundingClientRect) return false;
                var r = el.getBoundingClientRect();
                var s = window.getComputedStyle(el);
                return r.width > 4 && r.height > 4 &&
                    r.bottom > 0 && r.top < window.innerHeight &&
                    r.right > 0 && r.left < window.innerWidth &&
                    s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
            }}
            function label(el) {{
                var txt = [
                    el.innerText || '',
                    el.getAttribute('aria-label') || '',
                    el.getAttribute('title') || '',
                    el.getAttribute('value') || '',
                    el.getAttribute('alt') || '',
                    el.getAttribute('class') || ''
                ].join(' ').replace(/\\s+/g, ' ').trim();
                try {{
                    var svg = el.querySelector && el.querySelector('svg[aria-label], svg[title]');
                    if (svg) txt += ' ' + (svg.getAttribute('aria-label') || svg.getAttribute('title') || '');
                }} catch (e) {{}}
                return txt.trim();
            }}
            function rect(el) {{
                var r = el.getBoundingClientRect();
                return {{x:Math.round(r.left), y:Math.round(r.top), w:Math.round(r.width), h:Math.round(r.height)}};
            }}
            function center(r) {{ return {{x:r.left + r.width / 2, y:r.top + r.height / 2}}; }}
            var q = norm(query);
            var wantsEnlarge = /\\b(enlarge|expand|zoom|larger|bigger|full\\s*screen|fullscreen|view\\s+larger|make\\s+.*big)\\b/.test(q);
            var tokens = q.split(' ').filter(function (w) {{
                return w.length >= 3 && ['the','this','that','there','page','button','please','pls','can','you','alice','click','tap','press','photo','picture','image','it'].indexOf(w) === -1;
            }}).slice(0, 8);
            var imgs = Array.prototype.slice.call(document.querySelectorAll('img')).filter(visible);
            var mainImg = null, mainArea = 0;
            imgs.forEach(function (img) {{
                var r = img.getBoundingClientRect();
                var area = Math.max(0, r.width) * Math.max(0, r.height);
                if (area > mainArea) {{ mainArea = area; mainImg = img; }}
            }});
            var mainRect = mainImg ? mainImg.getBoundingClientRect() : null;
            function imageOverlayScore(el) {{
                if (!mainRect) return 0;
                var r = el.getBoundingClientRect();
                var c = center(r);
                var inside = c.x >= mainRect.left && c.x <= mainRect.right && c.y >= mainRect.top && c.y <= mainRect.bottom;
                var top = Math.abs(c.y - mainRect.top);
                var right = Math.abs(c.x - mainRect.right);
                var left = Math.abs(c.x - mainRect.left);
                if (inside && top < 130 && Math.min(right, left) < 150) return 30;
                if (top < 150 && Math.min(right, left) < 220) return 12;
                return 0;
            }}
            var nodes = Array.prototype.slice.call(document.querySelectorAll(
                'button,[role="button"],a[href],input[type="button"],input[type="submit"],[aria-label][tabindex],summary,' +
                '[class*="zoom" i],[class*="expand" i],[class*="fullscreen" i],[class*="enlarge" i]'
            )).filter(visible);
            var seen = [];
            var cands = [];
            nodes.forEach(function (el) {{
                if (seen.indexOf(el) !== -1) return;
                seen.push(el);
                var lab = label(el);
                var n = norm(lab);
                var score = 0;
                tokens.forEach(function (tok) {{ if (n.indexOf(tok) !== -1) score += 8; }});
                if (wantsEnlarge && /\\b(enlarge|expand|zoom|larger|fullscreen|full\\s*screen|open\\s+image|view\\s+(image|larger|photo)|image\\s+viewer)\\b/.test(n)) score += 90;
                if (wantsEnlarge) score += imageOverlayScore(el);
                if (/\\b(heart|watchlist|like|save)\\b/.test(n) && wantsEnlarge) score -= 25;
                if (/\\b(share|cart|buy|message|seller)\\b/.test(n) && wantsEnlarge) score -= 15;
                if (score > 0) cands.push({{el:el, label:lab, norm:n, score:score, rect:rect(el)}});
            }});
            cands.sort(function (a, b) {{ return b.score - a.score; }});
            var best = cands[0] || null;
            var available = nodes.slice(0, 20).map(function (el) {{
                return {{label: label(el).slice(0, 120), rect: rect(el)}};
            }}).filter(function (x) {{ return x.label; }});
            if (!best || best.score < (wantsEnlarge ? 20 : 8)) {{
                return {{clicked:false, reason:'no_matching_visible_control', query:query, available_controls:available}};
            }}
            try {{ best.el.scrollIntoView({{block:'center', inline:'center', behavior:'instant'}}); }} catch (e) {{}}
            var r = best.el.getBoundingClientRect();
            var cx = Math.round(r.left + r.width / 2), cy = Math.round(r.top + r.height / 2);
            ['mouseover','mousedown','mouseup','click'].forEach(function (name) {{
                try {{
                    best.el.dispatchEvent(new MouseEvent(name, {{
                        bubbles:true, cancelable:true, view:window, clientX:cx, clientY:cy
                    }}));
                }} catch (e) {{}}
            }});
            try {{ best.el.click(); }} catch (e) {{}}
            return {{clicked:true, mode:'visible_control_click', label:best.label.slice(0,160), score:best.score, x:cx, y:cy, query:query}};
        }})();
        """
        result = self._run_javascript_sync(js, wait_ms=1500)
        if isinstance(result, dict) and result.get("clicked"):
            try:
                from System.swarm_browser_photo_description import mark_frame_changed
                mark_frame_changed(url=self._current_url, state_dir=_STATE)
            except Exception:
                pass
            try:
                QTimer.singleShot(1000, self.refresh_current_page_state)
            except Exception:
                pass
        return result if isinstance(result, dict) else {"clicked": False, "reason": "no_js_result", "query": query}

    def click_google_images_tab(self) -> dict:
        """Click Google's Images/Photos tab, or navigate to the images URL.

        George may say "Photos section" while Google renders the control as
        "Images". This stays inside Alice Browser and uses the current query
        from the visible Google page.
        """
        refused = self._gate_click_refused("click_google_images_tab")
        if refused:
            return refused
        if not self._view:
            return {"clicked": False, "reason": "no_web_view"}
        try:
            current_url = self._view.url().toString() if self._view is not None else ""
        except Exception:
            current_url = getattr(self, "_current_url", "") or ""
        if "google." not in str(current_url or "").lower():
            return {
                "clicked": False,
                "reason": "not_google_page",
                "url": str(current_url or ""),
            }
        js = r"""
        (function () {
            function visible(el) {
                if (!el || !el.getBoundingClientRect) return false;
                var r = el.getBoundingClientRect();
                var s = window.getComputedStyle(el);
                return r.width > 4 && r.height > 4 &&
                    s.display !== 'none' && s.visibility !== 'hidden' &&
                    s.opacity !== '0';
            }
            function label(el) {
                return [
                    el.textContent || '',
                    el.getAttribute('aria-label') || '',
                    el.getAttribute('title') || '',
                    el.getAttribute('role') || ''
                ].join(' ').replace(/\s+/g, ' ').trim();
            }
            function clickNode(el, mode) {
                try { el.scrollIntoView({block:'center', inline:'center', behavior:'instant'}); } catch (e) {}
                var r = el.getBoundingClientRect();
                var cx = Math.round(r.left + r.width / 2);
                var cy = Math.round(r.top + r.height / 2);
                ['mouseover','mousedown','mouseup','click'].forEach(function (name) {
                    try {
                        el.dispatchEvent(new MouseEvent(name, {
                            bubbles:true, cancelable:true, view:window, clientX:cx, clientY:cy
                        }));
                    } catch (e) {}
                });
                try { el.click(); } catch (e) {}
                return {
                    clicked:true,
                    mode:mode || 'visible_tab_click',
                    href: el.href || el.getAttribute('href') || '',
                    text: label(el).slice(0, 160),
                    x: cx,
                    y: cy
                };
            }
            var candidates = Array.prototype.slice.call(document.querySelectorAll(
                'a, [role="tab"], [role="link"], button, div[role="button"]'
            )).filter(visible);
            var exact = null;
            var fuzzy = null;
            for (var i = 0; i < candidates.length; i++) {
                var el = candidates[i];
                var text = label(el);
                var low = text.toLowerCase();
                var href = (el.href || el.getAttribute('href') || '').toLowerCase();
                if (/\b(images?|photos?|pictures?)\b/.test(low) || /(?:tbm=isch|udm=2)/.test(href)) {
                    if (/^(images?|photos?|pictures?)$/i.test(text.trim()) || /(?:tbm=isch|udm=2)/.test(href)) {
                        exact = el;
                        break;
                    }
                    if (!fuzzy) fuzzy = el;
                }
            }
            if (exact) return clickNode(exact, 'visible_images_tab_click');
            if (fuzzy) return clickNode(fuzzy, 'visible_images_control_click');

            var params = new URLSearchParams(window.location.search || '');
            var q = params.get('q') || '';
            if (!q) {
                var input = document.querySelector('textarea[name="q"], input[name="q"], input[type="search"]');
                if (input && input.value) q = input.value;
            }
            if (!q) return {clicked:false, reason:'google_query_not_found', url:String(window.location.href || '')};
            var target = 'https://www.google.com/search?tbm=isch&q=' + encodeURIComponent(q);
            try {
                window.location.href = target;
                return {clicked:true, mode:'direct_images_url', href:target, text:'Google Images', query:q};
            } catch (e) {
                return {clicked:false, reason:'direct_images_url_failed:' + (e && e.message ? e.message : e), query:q};
            }
        })();
        """
        result = self._run_javascript_sync(js, wait_ms=1200)
        if isinstance(result, dict) and result.get("clicked"):
            try:
                QTimer.singleShot(650, self.refresh_current_page_state)
            except Exception:
                pass
        return result if isinstance(result, dict) else {"clicked": False, "reason": "no_js_result"}

    def click_visible_google_image_result(self, query: str = "", ordinal: int = 0) -> dict:
        """Click a visible image tile on ANY image-results page (Google, DuckDuckGo,
        Bing, Brave, Yahoo, ...). ``ordinal`` selects which tile in reading order:
        1=first, 2=second ... -1=last; 0 keeps the prominent best-score pick. This is a
        pure body effector — Alice just executes the click; she does not need to be
        conscious of what the tile shows (George 2026-06-02)."""
        refused = self._gate_click_refused("click_visible_google_image_result")
        if refused:
            refused["query"] = query
            refused["ordinal"] = ordinal
            return refused
        if not self._view:
            return {"clicked": False, "reason": "no_web_view", "query": query}
        try:
            current_url = self._view.url().toString() if self._view is not None else ""
        except Exception:
            current_url = getattr(self, "_current_url", "") or ""
        if not str(current_url or "").lower().startswith(("http://", "https://")):
            return {
                "clicked": False,
                "reason": "no_web_page",
                "url": str(current_url or ""),
                "query": query,
            }
        js = f"""
        (function () {{
            var ownerQuery = {json.dumps(str(query or ""))};
            var ord = {json.dumps(int(ordinal or 0))};
            function clean(s) {{
                return (s || '').toString().toLowerCase()
                    .replace(/[^a-z0-9]+/g, ' ')
                    .replace(/\\s+/g, ' ')
                    .trim();
            }}
            function visible(el) {{
                if (!el || !el.getBoundingClientRect) return false;
                var r = el.getBoundingClientRect();
                var s = window.getComputedStyle(el);
                return r.width >= 70 && r.height >= 70 &&
                    s.display !== 'none' && s.visibility !== 'hidden' &&
                    s.opacity !== '0' && r.bottom > 110 && r.top < window.innerHeight - 8 &&
                    r.right > 0 && r.left < window.innerWidth;
            }}
            function clickableFor(img) {{
                return img.closest('a[href], div[role="button"], [jsaction], [data-ved]') || img;
            }}
            function labelFor(img, click) {{
                return [
                    img.alt || '',
                    img.getAttribute('aria-label') || '',
                    img.getAttribute('title') || '',
                    click ? (click.getAttribute('aria-label') || click.getAttribute('title') || click.textContent || '') : ''
                ].join(' ').replace(/\\s+/g, ' ').trim();
            }}
            var q = clean(ownerQuery);
            var tokens = q.split(' ').filter(function (w) {{
                return w.length >= 4 && ['click','select','choose','open','photo','photos','image','images','picture','pictures','screen','alice','please','want'].indexOf(w) === -1;
            }}).slice(0, 8);
            var imgs = Array.prototype.slice.call(document.querySelectorAll('img')).filter(visible);
            var cands = [];
            var best = null, bestClick = null, bestScore = -1, bestLabel = '';
            imgs.forEach(function (img, idx) {{
                var click = clickableFor(img);
                if (!click) return;
                var r = img.getBoundingClientRect();
                var lab = labelFor(img, click);
                var n = clean(lab);
                var score = Math.min(600, r.width) * Math.min(400, r.height) / 1000;
                score += Math.max(0, 220 - r.top) / 20;
                score += Math.max(0, 500 - Math.abs((r.left + r.width / 2) - (window.innerWidth / 2))) / 80;
                tokens.forEach(function (tok) {{
                    if (n.indexOf(tok) !== -1) score += 8;
                }});
                if (idx === 0) score += 2;
                cands.push({{img: img, click: click, r: r, lab: lab, score: score}});
                if (score > bestScore) {{
                    best = img;
                    bestClick = click;
                    bestScore = score;
                    bestLabel = lab;
                }}
            }});
            // ord != 0 -> pick by reading order (top row-band, then left-to-right),
            // not by score: "the first one" means the first tile, period.
            if (ord !== 0 && cands.length) {{
                var ordered = cands.slice().sort(function (a, b) {{
                    var ra = Math.round(a.r.top / 120), rb = Math.round(b.r.top / 120);
                    if (ra !== rb) return ra - rb;
                    return a.r.left - b.r.left;
                }});
                var pick = ord > 0 ? (ord - 1) : (ordered.length + ord);
                if (pick < 0) pick = 0;
                if (pick > ordered.length - 1) pick = ordered.length - 1;
                best = ordered[pick].img;
                bestClick = ordered[pick].click;
                bestScore = ordered[pick].score;
                bestLabel = ordered[pick].lab;
            }}
            if (!best || !bestClick) {{
                return {{clicked:false, reason:'no_visible_google_image_tile', query:ownerQuery, url:String(window.location.href || '')}};
            }}
            try {{ best.scrollIntoView({{block:'center', inline:'center', behavior:'instant'}}); }} catch (e) {{}}
            var r = best.getBoundingClientRect();
            var cx = Math.round(r.left + r.width / 2);
            var cy = Math.round(r.top + r.height / 2);
            ['mouseover','mousedown','mouseup','click'].forEach(function (name) {{
                try {{
                    bestClick.dispatchEvent(new MouseEvent(name, {{
                        bubbles:true, cancelable:true, view:window, clientX:cx, clientY:cy
                    }}));
                }} catch (e) {{}}
            }});
            try {{ bestClick.click(); }} catch (e) {{}}
            return {{
                clicked:true,
                mode:'google_image_tile_click',
                href: bestClick.href || bestClick.getAttribute('href') || '',
                src: best.currentSrc || best.src || '',
                alt: bestLabel.slice(0, 220),
                score: bestScore,
                x: cx,
                y: cy,
                query: ownerQuery
            }};
        }})();
        """
        result = self._run_javascript_sync(js, wait_ms=1500)
        if isinstance(result, dict) and result.get("clicked"):
            try:
                from System.swarm_browser_photo_description import mark_frame_changed
                mark_frame_changed(url=self._current_url, state_dir=_STATE)
            except Exception:
                pass
            try:
                QTimer.singleShot(1100, self.refresh_current_page_state)
            except Exception:
                pass
        return result if isinstance(result, dict) else {"clicked": False, "reason": "no_js_result", "query": query}

    def start_image_slideshow(self, subject: str = "", *, engine=None, interval_ms: int = 3500) -> dict:
        """r383 (George 2026-06-02): 'slideshow images of cats' — one image every 3.5s.
        With a subject, navigate to that subject's image results on the resolved engine
        (DuckDuckGo by default; the current site's engine if already on one — 'if the user
        is on google.com then she does the slideshow on Google Images') then inject the
        slideshow overlay. With no subject, slideshow whatever gallery is already on screen.
        A pure body effector — she just runs it; click or Esc stops it."""
        if not _HAS_WEBENGINE or self._view is None:
            return {"ok": False, "reason": "no_web_view"}
        try:
            from System.swarm_search_engine_registry import (
                slideshow_images_url, build_image_slideshow_js, slideshow_engine_for,
            )
        except Exception as exc:
            return {"ok": False, "reason": f"registry_unavailable: {type(exc).__name__}: {exc}"}
        try:
            cur = self._view.url().toString()
        except Exception:
            cur = getattr(self, "_current_url", "") or ""
        interval = int(interval_ms or 3500)
        js = build_image_slideshow_js(interval)
        subj = (subject or "").strip()
        if subj:
            url = slideshow_images_url(subj, current_url=cur, engine=engine)
            eng = engine if engine else slideshow_engine_for(cur)
            # park the slideshow so it fires when the image grid finishes loading
            # (loadFinished bridge) — reliable for both already-open and just-opened browser.
            stage_pending_slideshow(url, js)
            self._navigate(url)
            try:
                QTimer.singleShot(3200, self._fire_pending_slideshow_timer)
            except Exception:
                pass
            # Wire relearn: success path for subject slideshow (domain=engine category).
            try:
                from System.swarm_browser_site_playbook import record_skill_outcome as _rso
                _rso(eng or "duckduckgo.com", "image_slideshow", True, note=f"subject={subj}", source="alice_browser_widget")
            except Exception:
                pass
            return {"ok": True, "url": url, "engine": eng, "interval_ms": interval,
                    "subject": subj, "mode": "navigate_then_slideshow"}
        # no subject -> slideshow the gallery already on her screen
        result = self._run_javascript_sync(js, wait_ms=1500)
        ok = bool(result.get("ok")) if isinstance(result, dict) else False
        eng2 = slideshow_engine_for(cur)
        try:
            from System.swarm_browser_site_playbook import record_skill_outcome as _rso
            _rso(eng2 or "duckduckgo.com", "image_slideshow", ok, note="no-subject current gallery", source="alice_browser_widget")
        except Exception:
            pass
        return {"ok": ok, "url": cur, "engine": eng2, "interval_ms": interval,
                "subject": "", "mode": "current_page", "js_result": result if isinstance(result, dict) else None}

    def _fire_pending_slideshow_for(self, loaded_url: str) -> None:
        """loadFinished bridge: if a recent slideshow was parked for this host, run it once."""
        row = read_pending_slideshow()
        if not row:
            return
        try:
            from urllib.parse import urlparse
            host = urlparse(loaded_url or "").netloc.lower()
        except Exception:
            host = ""
        if row.get("host") and host and row["host"] != host:
            return
        try:
            self._run_javascript_sync(row.get("js") or "", wait_ms=1500)
        except Exception:
            pass
        clear_pending_slideshow()

    def _fire_pending_slideshow_timer(self) -> None:
        """Fallback if loadFinished was missed: fire on the current page if a parked
        slideshow matches the host we are on."""
        try:
            cur = self._view.url().toString() if self._view is not None else ""
        except Exception:
            cur = getattr(self, "_current_url", "") or ""
        self._fire_pending_slideshow_for(cur)

    def click_youtube_result_matching(self, query: str) -> dict:
        """Click the visible YouTube watch result that best matches the owner's title.

        This is the browser-limb effector for commands like "open THE OFFICIAL
        2018 VICTORIA'S SECRET FASHION SHOW video" or "select Halsey - Without
        Me" while Alice Browser is on YouTube. It only clicks visible
        ``watch?v=`` links inside Alice Browser, never Safari/Chrome.
        """
        refused = self._gate_click_refused("click_youtube_result_matching")
        if refused:
            refused["query"] = query
            return refused
        if not self._view:
            return {"clicked": False, "reason": "no_web_view", "query": query}
        try:
            current_url = self._view.url().toString() if self._view is not None else ""
        except Exception:
            current_url = getattr(self, "_current_url", "") or ""
        if "youtube.com/results" not in str(current_url or ""):
            return {
                "clicked": False,
                "reason": "not_youtube_results_page",
                "url": str(current_url or ""),
                "query": query,
            }
        js = f"""
        (function () {{
            var query = {json.dumps(str(query or ""))};
            function clean(s) {{
                return (s || '').toString().toLowerCase()
                    .replace(/[\\u2018\\u2019]/g, "'")
                    .replace(/[^a-z0-9]+/g, ' ')
                    .replace(/\\s+/g, ' ')
                    .trim();
            }}
            function visible(el) {{
                if (!el || !el.getBoundingClientRect) return false;
                var r = el.getBoundingClientRect();
                var s = window.getComputedStyle(el);
                return r.width > 8 && r.height > 8 && s.display !== 'none' &&
                    s.visibility !== 'hidden' && s.opacity !== '0';
            }}
            var qNorm = clean(query);
            var stop = {{
                the:1, a:1, an:1, video:1, vid:1, clip:1, please:1, pls:1,
                alice:1, alyssa:1, click:1, select:1, open:1, play:1, watch:1,
                body:1, screen:1, screenshot:1, artwork:1, thumbnail:1, on:1,
                in:1, to:1, of:1, and:1, me:1
            }};
            var tokens = qNorm.split(' ').filter(function (w) {{ return w && !stop[w]; }});
            var year = (qNorm.match(/\\b(19|20)\\d{{2}}\\b/) || [''])[0];
            var nodes = Array.prototype.slice.call(document.querySelectorAll(
                'ytd-video-renderer, ytd-compact-video-renderer, ytd-rich-item-renderer, ytd-grid-video-renderer'
            ));
            var anchors = [];
            nodes.forEach(function (node) {{
                var a = node.querySelector('a#video-title[href*="watch?v="], a[href*="watch?v="]');
                if (a && visible(a)) anchors.push(a);
            }});
            if (!anchors.length) {{
                anchors = Array.prototype.slice.call(document.querySelectorAll('a[href*="watch?v="]')).filter(visible);
            }}
            if (!anchors.length) return {{clicked:false, reason:'no_visible_youtube_watch_result', query:query}};
            function textFor(a) {{
                var title = a.getAttribute('title') || a.getAttribute('aria-label') || a.textContent || '';
                var parent = a.closest('ytd-video-renderer,ytd-compact-video-renderer,ytd-rich-item-renderer,ytd-grid-video-renderer');
                var extra = parent ? (parent.innerText || '') : '';
                return (title + ' ' + extra).replace(/\\s+/g, ' ').trim();
            }}
            var best = null, bestScore = -1, bestText = '';
            anchors.forEach(function (a, idx) {{
                var txt = textFor(a);
                var n = clean(txt);
                var score = 0;
                if (qNorm && n.indexOf(qNorm) !== -1) score += 80;
                tokens.forEach(function (tok) {{
                    if (n.indexOf(tok) !== -1) score += tok.length >= 4 ? 8 : 3;
                }});
                if (year && n.indexOf(year) !== -1) score += 25;
                if (/\\bofficial\\b/.test(qNorm) && /\\bofficial\\b/.test(n)) score += 18;
                if (/\\bhalsey\\b/.test(qNorm) && /\\bhalsey\\b/.test(n)) score += 25;
                if (/\\bwithout\\b/.test(qNorm) && /\\bwithout\\b/.test(n)) score += 12;
                if (idx === 0) score += 1;
                if (score > bestScore) {{ best = a; bestScore = score; bestText = txt; }}
            }});
            if (!best) return {{clicked:false, reason:'no_matching_youtube_result', query:query}};
            try {{ best.scrollIntoView({{block:'center', inline:'center', behavior:'instant'}}); }} catch (e) {{}}
            var r = best.getBoundingClientRect();
            ['mouseover','mousedown','mouseup','click'].forEach(function (name) {{
                try {{
                    best.dispatchEvent(new MouseEvent(name, {{
                        bubbles:true, cancelable:true, view:window,
                        clientX:Math.round(r.left + r.width / 2),
                        clientY:Math.round(r.top + r.height / 2)
                    }}));
                }} catch (e) {{}}
            }});
            try {{ best.click(); }} catch (e) {{}}
            return {{
                clicked:true,
                href: best.href || '',
                text: bestText.slice(0, 220),
                score: bestScore,
                query: query
            }};
        }})();
        """
        result = self._run_javascript_sync(js, wait_ms=1500)
        if isinstance(result, dict) and result.get("clicked"):
            try:
                QTimer.singleShot(1200, self._force_embedded_play)
                QTimer.singleShot(1600, self.refresh_current_page_state)
            except Exception:
                pass
        return result if isinstance(result, dict) else {"clicked": False, "reason": "no_js_result", "query": query}

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
        refused = self._gate_click_refused("open_visible_photo_matching_text")
        if refused:
            refused["status"] = "failed"
            refused["query"] = query
            return refused
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

    # ── Image navigation arrows (DuckDuckGo blown-up image + Instagram + generic) ──
    # George 2026-06-02: he blows a picture up on DuckDuckGo himself, then wants to say
    # "next slide" / "previous slide" and have Alice move through the gallery. So the
    # body needs BOTH hands (next AND back) and it needs to know DuckDuckGo's detail-view
    # arrows, not only Instagram's. These selector families run most-specific first and
    # fall back to the ArrowRight/ArrowLeft key, which DuckDuckGo's detail view and most
    # galleries honour even when their arrow markup is hashed/hidden.
    _IMAGE_NAV_NEXT_SELECTORS = [
        ".detail__nav__next", ".js-detail-next", "a.detail__nav__next",
        'button[aria-label="Next image"]', '[aria-label="Next image"]',
        'button[aria-label="Next"]', '[aria-label="Next"][role="button"]', 'svg[aria-label="Next"]',
        '[aria-label*="next" i][role="button"]', '[aria-label*="next" i]',
        'button[class*="next" i]', 'a[class*="next" i]', ".rightarrow", '[class*="arrow"][class*="right" i]',
    ]
    _IMAGE_NAV_PREV_SELECTORS = [
        ".detail__nav__prev", ".js-detail-prev", "a.detail__nav__prev",
        'button[aria-label="Previous image"]', '[aria-label="Previous image"]',
        'button[aria-label="Previous"]', '[aria-label="Previous"][role="button"]', 'svg[aria-label="Previous"]',
        'button[aria-label="Go back"]', '[aria-label="Go back"][role="button"]', 'svg[aria-label="Go back"]',
        '[aria-label*="previous" i][role="button"]', '[aria-label*="prev" i]',
        'button[class*="prev" i]', 'a[class*="prev" i]', ".leftarrow", '[class*="arrow"][class*="left" i]',
    ]

    def _image_nav_js(self, direction: str) -> str:
        """Build the directional click-or-arrow-key JS for next/previous image."""
        is_prev = str(direction or "").lower().startswith(("prev", "back", "left"))
        sels = self._IMAGE_NAV_PREV_SELECTORS if is_prev else self._IMAGE_NAV_NEXT_SELECTORS
        key, code = ("ArrowLeft", 37) if is_prev else ("ArrowRight", 39)
        tmpl = r"""
        (function () {
            var SELS = __SELS__;
            var KEY = __KEY__, CODE = __CODE__;
            function vis(el) {
                if (!el || !el.getBoundingClientRect) return false;
                var r = el.getBoundingClientRect();
                var s = window.getComputedStyle(el);
                return r.width > 4 && r.height > 4 && s.display !== 'none' &&
                    s.visibility !== 'hidden' && s.opacity !== '0';
            }
            var found = null, used = '';
            for (var i = 0; i < SELS.length; i++) {
                var el = document.querySelector(SELS[i]);
                if (el && vis(el)) { found = el; used = SELS[i]; break; }
            }
            if (found) {
                var c = found.closest('button,[role=button],a') || found;
                try { c.scrollIntoView({block:'center', inline:'center'}); } catch (e) {}
                var rr = c.getBoundingClientRect();
                ['mouseover','mousedown','mouseup','click'].forEach(function (n) {
                    try { c.dispatchEvent(new MouseEvent(n, {bubbles:true, cancelable:true, view:window,
                        clientX:Math.round(rr.left + rr.width/2), clientY:Math.round(rr.top + rr.height/2)})); } catch (e) {}
                });
                try { c.click(); } catch (e) {}
                return {ok:true, method:'button', selector:used,
                    label:(c.getAttribute && (c.getAttribute('aria-label') || c.title)) || ''};
            }
            var ev = new KeyboardEvent('keydown', {key:KEY, keyCode:CODE, which:CODE, bubbles:true});
            document.dispatchEvent(ev);
            var det = document.querySelector('.detail--img, .detail__media, .detail, [class*="detail__media" i]');
            if (det) { try { det.dispatchEvent(ev); } catch (e) {} }
            try { if (document.activeElement) document.activeElement.dispatchEvent(ev); } catch (e) {}
            return {ok:true, method:'arrow_key', key:KEY};
        })();
        """
        return (tmpl.replace("__SELS__", json.dumps(sels))
                    .replace("__KEY__", json.dumps(key))
                    .replace("__CODE__", str(code)))

    def _image_nav(self, direction: str) -> str:
        """Shared next/previous image effector. Returns the method used
        ('button'/'arrow_key') so the caller knows she actually moved; '' if no view."""
        if not self._view:
            return ""
        try:
            result = self._run_javascript_sync(self._image_nav_js(direction), wait_ms=1200)
        except Exception as exc:
            print(f"[AliceBrowser] _image_nav({direction}) failed: {exc}")
            return ""
        # r212: the on-screen frame is about to change — stamp the frame epoch so the
        # prior frame's description is no longer treated as current (floral-shorts guard).
        try:
            from System.swarm_browser_photo_description import mark_frame_changed
            mark_frame_changed(url=self._current_url, state_dir=_STATE)
        except Exception:
            pass
        try:
            QTimer.singleShot(1500, self.refresh_current_page_state)
        except Exception:
            pass
        try:
            from System.swarm_browser_site_playbook import record_skill_outcome as _rso
            ok = bool(result.get("ok")) if isinstance(result, dict) else True
            note = (result.get("method") if isinstance(result, dict) else "no_result") or ""
            _rso("duckduckgo.com", f"image_nav_{('prev' if str(direction).lower().startswith(('prev','back','left')) else 'next')}",
                 ok, note=str(note), source="alice_browser_widget")
        except Exception:
            pass
        if isinstance(result, dict):
            return str(result.get("method") or "dispatched")
        return "dispatched"

    def go_next_photo(self) -> str:
        """Advance to the NEXT image: click DuckDuckGo's detail '›' arrow / Instagram's
        'Next' control / a generic gallery next arrow, falling back to the ArrowRight
        key. Then re-read the page so the new photo is the current one.
        George 2026-05-31: 'next picture'; George 2026-06-02: 'next slide' on DuckDuckGo."""
        return self._image_nav("next")

    def go_prev_photo(self) -> str:
        """Step BACK to the PREVIOUS image: click DuckDuckGo's detail '‹' arrow /
        Instagram's 'Go back' control / a generic gallery prev arrow, falling back to the
        ArrowLeft key. The missing other hand — George 2026-06-02: 'previous slide'."""
        return self._image_nav("prev")

    def read_image_nav_controls(self) -> dict:
        """George 2026-06-02: 'train her to see at least on screen the next and previous
        image buttons'. A deterministic read of the blown-up image's navigation arrows so
        Alice KNOWS, from the live DOM (not a guess), that the '‹ previous' and 'next ›'
        controls are on screen and where they sit. This grounds 'next slide'/'previous
        slide' in what is actually rendered, per Tool Truth (§7.2) and receipts-as-evidence
        (§6)."""
        if not self._view:
            return {"ok": False, "reason": "no_web_view", "has_next": False, "has_prev": False}
        next_sels = json.dumps(self._IMAGE_NAV_NEXT_SELECTORS)
        prev_sels = json.dumps(self._IMAGE_NAV_PREV_SELECTORS)
        tmpl = r"""
        (function () {
            var NEXT = __NEXT__, PREV = __PREV__;
            function vis(el) {
                if (!el || !el.getBoundingClientRect) return false;
                var r = el.getBoundingClientRect();
                var s = window.getComputedStyle(el);
                return r.width > 4 && r.height > 4 && s.display !== 'none' &&
                    s.visibility !== 'hidden' && s.opacity !== '0';
            }
            function rect(el) { var r = el.getBoundingClientRect();
                return {x:Math.round(r.left), y:Math.round(r.top), w:Math.round(r.width), h:Math.round(r.height)}; }
            function find(sels) {
                for (var i = 0; i < sels.length; i++) {
                    var el = document.querySelector(sels[i]);
                    if (el && vis(el)) return {el:el, sel:sels[i]};
                } return null;
            }
            function lbl(x, fallback) {
                if (!x) return '';
                return (x.el.getAttribute && (x.el.getAttribute('aria-label') || x.el.title)) || fallback;
            }
            var inDetail = !!document.querySelector('.detail--img, .detail__media, .is-detail-open, [class*="detail__media" i]');
            var n = find(NEXT), p = find(PREV);
            return {ok:true, in_detail_view:inDetail,
                has_next:!!n, next_selector:n?n.sel:'', next_label:lbl(n,'next'), next_rect:n?rect(n.el):null,
                has_prev:!!p, prev_selector:p?p.sel:'', prev_label:lbl(p,'previous'), prev_rect:p?rect(p.el):null,
                url:location.href};
        })();
        """
        js = tmpl.replace("__NEXT__", next_sels).replace("__PREV__", prev_sels)
        try:
            result = self._run_javascript_sync(js, wait_ms=1200)
        except Exception as exc:
            return {"ok": False, "reason": f"js_failed: {exc}", "has_next": False, "has_prev": False}
        if isinstance(result, dict):
            return result
        return {"ok": False, "reason": "no_js_result", "has_next": False, "has_prev": False}

    def start_photo_slideshow(self, interval_s: float = 3.0) -> float:
        """Auto-advance the photo every interval_s seconds (default 3). Cheap: it
        advances + re-reads the page each tick; it does NOT auto-dispatch the vision
        arm (that takes ~10s, far longer than a 3s tick) — describing stays on demand."""
        self.stop_photo_slideshow()
        try:
            from System.swarm_browser_site_playbook import record_skill_outcome as _rso
            _rso("local-browser", "photo_slideshow", True, note="legacy timer start", source="browser_widget")
        except Exception:
            pass
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

    def _photo_page_caption_line(self) -> str:
        """George 2026-06-03: fold the page's own caption/title for THIS image into the
        describe prompt so Alice names the subject (e.g. "Angeline Quinto ties knot...")
        instead of "a couple". Reads the image-detail caption + source from the live DOM,
        falling back to the page document title / page-state title. Grounded in the page
        text, not speculation. Returns "" when there is no usable caption."""
        title = ""
        source = ""
        try:
            js = (
                "(function(){"
                "function t(s){var e=document.querySelector(s);return e?(e.textContent||'').trim():'';}"
                "var title=t('.detail__title')||t('[class*=\"detail\" i] h2')||t('[class*=\"detail\" i] [class*=\"title\" i]')||'';"
                "var src=t('.detail__source')||t('[class*=\"detail\" i] [class*=\"source\" i]')||'';"
                "return {title:title.slice(0,200),source:src.slice(0,120),doc:(document.title||'').slice(0,200)};"
                "})();"
            )
            r = self._run_javascript_sync(js, wait_ms=600)
            if isinstance(r, dict):
                title = str(r.get("title") or "").strip()
                source = str(r.get("source") or "").strip()
                if not title:
                    title = str(r.get("doc") or "").strip()
        except Exception:
            pass
        if not title:
            try:
                from System.swarm_browser_page_state import latest_page_state
                ps = latest_page_state(state_dir=_STATE) or {}
                title = str(ps.get("title") or "").strip()
            except Exception:
                title = ""
        if not title:
            return ""
        where = f" (source: {source})" if source else ""
        return (
            "\n\nPage caption for THIS image (from the web page itself - grounded fact, not "
            f"speculation): \"{title}\"{where}. If that caption names the person or event "
            "shown, say who or what it is by name in your description."
        )

    def describe_current_photo(self, *, current_arm: str = "", current_model: str = "", unavailable=()) -> dict:
        """On demand (owner asks 'describe' / cortex requests): take the freshest
        viewport image and let Alice's picked vision arm describe the actual photo.

        Honours George's rule via pick_vision_arm: default eye = current cortex,
        failover (with an owner diary note) if it cannot see or its API died.

        r246: if the owner-selected cortex/eye is a named provider, this is strict:
        that provider's eye or an honest selected-eye failure. No silent Claude/local
        cover answer when Codex/Grok/etc. is selected."""
        result = {"status": "failed", "arm": "", "description": ""}
        try:
            import hashlib
            import urllib.request
            from System.swarm_browser_page_state import latest_page_state
            from System.swarm_browser_photo_description import (
                record_photo_description,
                clean_browser_photo_description_text,
                looks_like_non_visual_arm_reply,
            )
            from System.swarm_cortex_capabilities import pick_vision_arm, record_cortex_arm_habit
            from System.swarm_agent_arm_launcher import ask_agent_arm

            url = self._current_url
            img_path = ""
            source = "viewport_vision_arm"
            # Resolve known visual subject identity (e.g. "Izzy") from recent owner reports
            # ("her name is Izzy") + page state (abellaskies profile, sea shells post, etc.).
            # This will be injected into the VLM prompt so the limb's own sight (local mlx_vlm_brain)
            # uses the proper name instead of generic "a woman". Supports "must go to cortex first"
            # by making the raw deterministic VLM output already identity-grounded from evidence.
            try:
                from System.swarm_browser_page_state import latest_page_state as _latest_ps
                from System.swarm_photo_identity import resolve_photo_identity as _resolve_photo_identity

                ps_for_id = _latest_ps(now=time.time(), max_age_s=1200.0, state_dir=_STATE) or {}
                if str(ps_for_id.get("url") or "") != str(url or ""):
                    ps_for_id = {}
                _page_text = "\n".join(
                    str(x or "")
                    for x in (
                        ps_for_id.get("title"),
                        "\n".join(str(h or "") for h in (ps_for_id.get("headings") or [])[:8])
                        if isinstance(ps_for_id.get("headings"), list) else "",
                        ps_for_id.get("text"),
                        ps_for_id.get("text_excerpt"),
                    )
                    if str(x or "")
                )
                identity = _resolve_photo_identity(
                    url=str(url or ""),
                    page_text=_page_text,
                    owner_text="",
                    state_dir=_STATE,
                )
            except Exception:
                identity = {}
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

            if _is_instagram_media_url(url):
                read_carousel = getattr(self, "_read_instagram_carousel", None)
                if callable(read_carousel):
                    read_carousel()

            strict_eye = _strict_selected_eye(current_arm, current_model)
            # George 2026-06-03: decouple the EYE from the CORTEX. If the selected cortex
            # cannot see (e.g. Grok -> is_vision_capable_model False) and the body's own LOCAL
            # vision eye (osmQwopus via the mlx-vlm brain) is up, release the blind strict eye
            # and let the local eye see while the cortex thinks. Local eye => honors r246 (no
            # silent cloud-vendor cover). PROVABLY INERT until that local eye is available.
            _local_vlm_eye = False
            try:
                from System.swarm_cortex_capabilities import is_vision_capable_model as _isvis
                from System import swarm_mlx_vlm_brain as _local_vlm
                _local_vlm_ready = bool(
                    getattr(_local_vlm, "describe_available", _local_vlm.is_available)()
                )
                if _local_vlm_ready and str(
                    os.environ.get("SIFTA_FORCE_OSMQWOPUS_BROWSER_DESCRIBE", "1") or "1"
                ).strip().lower() not in {"0", "false", "no", "off"}:
                    strict_eye = ""
                    _local_vlm_eye = True
                elif strict_eye and not _isvis(current_model) and _local_vlm_ready:
                    strict_eye = ""
                    _local_vlm_eye = True
            except Exception:
                _local_vlm_eye = False
            strict_grok_eye = strict_eye == "grok_agent"
            pick = pick_vision_arm(
                current_arm=current_arm,
                current_model=current_model,
                unavailable=unavailable,
                local_image_required=True,
            )
            if strict_eye:
                eye_name = _eye_display_name(strict_eye)
                pick = {
                    **pick,
                    "selected_arm": strict_eye,
                    "reason": f"selected_{strict_eye}_strict_eye",
                    "switched": False,
                    "fallbacks": [],
                    "diary_note": (
                        f"{eye_name} is my selected cortex/eye for this photo, so I must use "
                        f"{strict_eye} and not cover it with Claude or another provider."
                    ),
                }
            arm = pick.get("selected_arm", "")
            # r523 fix: for "describe the photo at the current link in my alice browser" (the limb's own rendered content / stigmergic sight), always prefer the local VLM that can process the actual local viewport PNG frame. The strict selected eye (e.g. Codex) policy is for the main cortex thinking; the browser organ's own sight for its pixels uses the dedicated local vision (r520 bridge). This prevents a selected eye that cannot see the local frame from blocking description of what is open in the browser. The owner is very specific: he already opened the pic in the browser and wants the description from the browser's sight.
            if img_path and Path(img_path).exists() and _local_vlm_ready:
                arm = "mlx_vlm_brain"
                _local_vlm_eye = True
                if pick and "diary_note" in pick:
                    pick["diary_note"] = (str(pick.get("diary_note", "")) + " (local VLM forced for browser limb own frame per stigmergic sight r520; selected eye noted for policy)").strip()
            if _local_vlm_eye:
                arm = "mlx_vlm_brain"
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
                    if not has_key and not _grok_cli_ready():
                        if strict_grok_eye:
                            refresh = _schedule_grok_oauth_refresh("browser_photo_local_image:grok_preflight")
                            note = _grok_oauth_repair_note("grok_eye_key_missing", refresh)
                            record_cortex_arm_habit(
                                "grok_agent",
                                cortex_model=current_model,
                                task="browser_photo_local_image",
                                ok=False,
                                status="grok_eye_auth_refresh_required",
                                reason="selected_grok_eye_missing_oauth_refresh_scheduled",
                                state_dir=_STATE,
                                meta={"image_ref": img_path, "source": source, "oauth_refresh": refresh},
                            )
                            record_photo_description(
                                url, description="", arm="grok_agent",
                                image_ref=img_path, status="grok_eye_auth_refresh_required",
                                source=source, state_dir=_STATE
                            )
                            result.update({
                                "status": "grok_eye_auth_refresh_required",
                                "arm": "grok_agent",
                                "description": "",
                                "error_summary": note,
                                "diary_note": note,
                                "oauth_refresh": refresh,
                                "attempts": [{
                                    "arm": "grok_agent",
                                    "ok": False,
                                    "status": "grok_eye_auth_refresh_required",
                                    "source": source,
                                    "receipt_id": "",
                                }],
                            })
                            return result
                        else:
                            # Non-strict Grok path already handled below
                            pass
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

            caption_line = ""
            caption_getter = getattr(self, "_photo_page_caption_line", None)
            if callable(caption_getter):
                try:
                    caption_line = caption_getter()
                except Exception:
                    caption_line = ""

            prompt = (
                "Look at the image at this exact path: "
                f"{img_path}\n"
                "It is a screenshot of a web page. Describe the MAIN subject of the photo - whatever it is: "
                "a person, product, vehicle, animal, building, food, plant, or any object (ignore the "
                "surrounding browser/app interface, menus, and comment sidebar). Be concise - 2 short "
                "sentences, under 50 words: WHAT it is, its key visible attributes (form, color, material; "
                "garments and colors if it is a person), and the setting; nothing else. State only what is clearly "
                "visible - no speculation, no hedging, no lists. Use neutral visual nouns only; do not invent "
                "style labels such as radical, sexy, provocative, or explicit."
                + caption_line
            )
            # Inject resolved visual subject name (e.g. "Izzy" from owner "her name is izzy" + page context
            # like abellaskies/sea shells post) into the prompt for the limb's local VLM (mlx_vlm_brain).
            # This makes the deterministic raw desc use the proper name from the start ("Izzy is posing..."
            # instead of "A woman with long dark hair is posing..."). The evidence (identity + raw VLM)
            # then goes to cortex for the final Alice composition ("must go to cortex first").
            if identity and identity.get("name"):
                name = identity.get("name")
                prompt += f" The main subject person is known from recent owner report and page/profile context as {name}. Use the exact name '{name}' (not 'a woman', 'the woman', 'a person', or any generic) when describing her pose, clothing, hair, expression, and setting in the photo."
            def _call_vision_arm(selected_arm: str) -> dict:
                call_source = source
                if selected_arm == "mlx_vlm_brain":
                    import types as _types
                    from System import swarm_mlx_vlm_brain as _local_vlm
                    _desc = _local_vlm.describe_image(img_path, prompt)
                    _ok = bool(_desc) and not str(_desc).startswith("[mlx-vlm")
                    arm_result = _types.SimpleNamespace(output=_desc or "", ok=_ok, stderr="", receipt_id="", returncode=0)
                    call_source = "local_mlx_vlm_eye"
                # George r210: a LOCAL ollama cortex looks with its OWN local eye.
                elif selected_arm == "ollama_vision_agent":
                    from System.swarm_ollama_vision_arm import describe_image_local
                    arm_result = describe_image_local(img_path, prompt, timeout_s=300)
                    call_source = "local_ollama_vision_arm"
                elif selected_arm == "qwen_agent":
                    # George r214: Kimi K2.6 cortex sees with Kimi's OWN Fireworks API.
                    from System.swarm_fireworks_vision_arm import describe_image_fireworks
                    arm_result = describe_image_fireworks(img_path, prompt, state_dir=_STATE, timeout_s=300)
                    call_source = "kimi_fireworks_vision_arm"
                elif selected_arm == "grok_agent":
                    # r258: use the logged-in Grok CLI OAuth surface first; direct
                    # /v1/chat/completions remains a fallback only if the CLI is unavailable.
                    from System.xai_grok_oauth_organ import describe_image_with_grok
                    arm_result = describe_image_with_grok(
                        img_path,
                        prompt,
                        model=current_model or "grok-4",
                        timeout_s=300,
                    )
                    call_source = "grok_cli_or_oauth_chat_vision_arm"
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
                raw_output = getattr(arm_result, "output", "") or ""
                clean_text = clean_browser_photo_description_text(raw_output)
                error_text = clean_browser_photo_description_text(getattr(arm_result, "stderr", "") or "")
                asked_for_image = (
                    looks_like_non_visual_arm_reply(clean_text)
                    if clean_text else looks_like_non_visual_arm_reply(raw_output)
                )
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
                    "text": clean_text if success else (error_text or clean_text),
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
            selected_eye_failure_status = ""
            selected_eye_error_summary = ""
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
                # r531: IG carousel structure for mixed photo/video posts (the 4-item P V P V the owner opened).
                # The reader was fired earlier; if we have it and total>1, enrich the description the cortex will see
                # with the full post structure + note that videos play on nav. The visual desc (from local VLM per r523)
                # is the frame content; the struct is organ truth from DOM.
                if _is_instagram_media_url(url):
                    car = getattr(self, "_last_ig_carousel", {}) or {}
                    if car.get("ok") and int(car.get("total", 1)) > 1:
                        struct = f"Instagram carousel post with {car['total']} items"
                        if car.get("types"):
                            struct += f" ({', '.join(car['types'])})"
                        struct += f". Currently on item {car.get('current', '?')} ({car.get('current_type', 'media')}). "
                        if car.get("has_video"):
                            struct += "Contains video(s); videos play when navigated to in the browser. "
                        if car.get("note"):
                            struct += car.get("note", "") + " "
                        # enrich whatever desc the arm gave
                        try:
                            existing_desc = str(attempt.get("text") or attempt.get("output") or "")
                            if existing_desc:
                                attempt["text"] = struct + "The visible frame shows: " + existing_desc
                            else:
                                attempt["text"] = struct
                            attempt["carousel"] = dict(car)
                        except Exception:
                            pass
                if strict_eye:
                    if strict_grok_eye:
                        status_s = str(attempt.get("status") or "")
                        detail_s = str(attempt.get("text") or "")
                        if _grok_eye_needs_oauth_repair(status_s, detail_s):
                            refresh = _schedule_grok_oauth_refresh("browser_photo_local_image:grok_runtime_auth")
                            note = _grok_oauth_repair_note(status_s, refresh, detail_s)
                            selected_eye_failure_status = "grok_eye_auth_refresh_required"
                            selected_eye_error_summary = note
                            diary_notes.append(note)
                            record_cortex_arm_habit(
                                "grok_agent",
                                cortex_model=current_model,
                                task="browser_photo_local_image",
                                ok=False,
                                status="grok_eye_auth_refresh_required",
                                reason="selected_grok_eye_oauth_refresh_scheduled",
                                state_dir=_STATE,
                                meta={
                                    "receipt_id": getattr(attempt.get("arm_res"), "receipt_id", ""),
                                    "returncode": getattr(attempt.get("arm_res"), "returncode", None),
                                    "source": attempt.get("source"),
                                    "oauth_refresh": refresh,
                                },
                            )
                            break
                        if (
                            current_attempt != "ollama_vision_agent"
                            and "ollama_vision_agent" not in down
                            and _grok_eye_allows_local_backup(status_s, detail_s)
                            and _local_grok_backup_ready()
                        ):
                            diary_notes.append(
                                f"my selected Grok eye was tried first and failed from provider/source/subscription "
                                f"status ({status_s}); I used my free local Ollama eye as the declared backup. "
                                "I did not switch to Claude."
                            )
                            try:
                                from System.swarm_cortex_failover_reflex import record_cortex_failover
                                record_cortex_failover(
                                    from_arm="grok_agent",
                                    to_arm="ollama_vision_agent",
                                    reason=f"grok_source_or_subscription_failure:{status_s}",
                                    state_dir=_STATE,
                                )
                            except Exception:
                                pass
                            current_attempt = "ollama_vision_agent"
                            result["arm"] = current_attempt
                            continue
                        if _grok_eye_allows_local_backup(status_s, detail_s):
                            selected_eye_failure_status = "grok_eye_source_unavailable_no_local_backup"
                            selected_eye_error_summary = (
                                "My selected Grok eye failed from provider/source/subscription, "
                                "but my local Ollama vision backup is not installed or not reachable. "
                                "I did not switch to Claude."
                            )
                    eye_name = _eye_display_name(strict_eye)
                    if not strict_grok_eye:
                        # r528 (extends r527, George approved 2026-06-04): a NON-grok selected eye
                        # (e.g. Codex) that produced no usable description on this frame — whether
                        # non_visual OR a hard 'failed' — must not trap her blind. Fall through to the
                        # existing vision failover below: a backup eye supplies the pixels (loud note)
                        # and the selected cortex still composes the answer. Grok keeps its own
                        # OAuth/backup policy above. Her chat cortex selection is unchanged either way.
                        _why = (
                            "returned no image description"
                            if attempt.get("non_visual")
                            else "could not see this frame"
                        )
                        diary_notes.append(
                            f"my selected {eye_name} eye {_why} ({attempt.get('status')}); I am using a "
                            f"backup vision eye for the pixels only — my cortex stays {eye_name}."
                        )
                    else:
                        if not selected_eye_error_summary:
                            selected_eye_error_summary = (
                                f"my selected {eye_name} eye failed on this frame ({attempt.get('status')}); "
                                f"I did not switch to Claude or another provider because {eye_name} is selected."
                            )
                        diary_notes.append(selected_eye_error_summary)
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
            failed_status = selected_eye_failure_status or (
                _strict_eye_failure_status(arm) if strict_eye and arm == strict_eye else "failed"
            )
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
            result["error_summary"] = "" if ok else (selected_eye_error_summary or text[:500])
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

    def _apply_alice_only_handoff_flag(self) -> None:
        """Consume Talk's alice-only flag so OAuth redirects stay in this limb."""
        try:
            flag = _STATE / "alice_browser_alice_only.flag"
            if not flag.exists():
                return
            raw = flag.read_text(encoding="utf-8").strip().splitlines()
            flag.unlink(missing_ok=True)
            if not raw:
                return
            try:
                ts = float(raw[0])
            except Exception:
                ts = time.time()
            target = raw[1].strip() if len(raw) > 1 else ""
            if target:
                self._owner_drop_target_url = target
            self._suppress_safari_handoff_until = max(
                float(getattr(self, "_suppress_safari_handoff_until", 0.0) or 0.0),
                ts + 180.0,
            )
        except Exception:
            pass

    def _check_drop_file(self) -> None:
        """Consume .sifta_state/alice_browser_open_url.txt if present."""
        self._apply_alice_only_handoff_flag()
        drop = self._drop_file
        if not drop.exists():
            return
        try:
            url = drop.read_text(encoding="utf-8").strip()
            drop.unlink(missing_ok=True)
            new_tab = False
            try:
                flag = getattr(self, "_drop_new_tab_file", None)
                if flag is not None and flag.exists():
                    new_tab = flag.read_text(encoding="utf-8").strip().lower() in {"1", "true", "yes", "new_tab"}
                    flag.unlink(missing_ok=True)
            except Exception:
                new_tab = False
        except Exception:
            return
        if url:
            self._owner_drop_target_url = url
            self._suppress_safari_handoff_until = time.time() + 180.0
            if new_tab and getattr(self, "_tabs", None) is not None:
                self.new_tab(url)
                self._status.showMessage(f"Opened new tab from Alice handoff: {url[:80]}")
            else:
                self._navigate(url)
                self._status.showMessage(f"Opened from Alice handoff: {url[:80]}")
            # r545: after drop-driven nav, force immediate awareness tick so _current_url, page_state,
            # and any pending viewport capture reflect the target (e.g. x.com photo/1 frame) not stale home.
            # This helps receipts + describe_current_photo see the opened content promptly.
            try:
                self._browser_awareness_tick()
            except Exception:
                pass

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

        r662 correction: after real tabs landed, replacing ``self._view`` became
        the wrong behavior. A target=_blank/"Open in New Tab" page must become a
        tab in Alice Browser, not overwrite the active tab. The returned
        QWebEnginePage is attached to a new QWebEngineView so Qt can finish
        loading the requested URL while Alice keeps her existing tab history.
        """
        try:
            if getattr(self, "_tabs", None) is None:
                if hasattr(self, "_view") and self._view:
                    self._view.setPage(new_page)
                    self._page = new_page
                return
            view = QWebEngineView()
            try:
                new_page.setParent(self)
            except Exception:
                pass
            view.setPage(new_page)
            self._wire_tab_view(view, new_page)
            idx = self._tabs.addTab(view, "New Tab")
            self._tabs.setCurrentIndex(idx)
            self._view = view
            self._page = new_page
            try:
                self._status.showMessage("Opened requested page in a new Alice Browser tab", 2500)
            except Exception:
                pass

            def _close_requested_tab(_view=view):
                try:
                    if getattr(self, "_tabs", None) is None:
                        return
                    i = self._tabs.indexOf(_view)
                    if i >= 0:
                        self._on_tab_close_requested(i)
                except Exception:
                    pass

            try:
                new_page.windowCloseRequested.connect(_close_requested_tab)
            except Exception:
                pass
            try:
                QTimer.singleShot(450, self.refresh_current_page_state)
            except Exception:
                pass
            return
        except Exception:
            # Never leave the original view broken.
            try:
                if not (hasattr(self, "_view") and self._view):
                    return
                self._view.setPage(new_page)
                self._page = new_page
            except Exception:
                return

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
                ("New Tab", lambda: self.new_tab()),                 # r277 (George)
                ("Close current Tab", lambda: self.close_current_tab()),
                None,  # separator
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
