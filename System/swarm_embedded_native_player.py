#!/usr/bin/env python3
"""Embedded native media player limb for Alice Browser.

QtWebEngine's Chromium demuxer cannot digest some site streams (TikTok signed
MP4 is the live case). This organ keeps playback INSIDE SIFTA OS using macOS
VideoToolbox via PyQt6 QMediaPlayer — not Safari handoff, not a yellow escape
button to another app.

Strategy:
  1. Read the signed stream URL the browser limb already captured in media errors.
  2. Try direct QMediaPlayer playback (works when CDN allows bare URL).
  3. If that fails, fetch to a temp file with Referer/User-Agent (and optional
     cookies) then play locally — still inside Alice.

Truth boundary (§7.2): every attempt appends to media_codec_bridge.jsonl.
"""
from __future__ import annotations

import json
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = REPO / ".sifta_state"
TRUTH_LABEL = "SIFTA_EMBEDDED_NATIVE_PLAYER_V1"

_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36 SIFTA-Alice/1.0"
)

_H264_FIRST_HOSTS = ("tiktok.com", "instagram.com", "facebook.com")


def _state_dir(state_dir: str | Path | None = None) -> Path:
    if state_dir is None:
        return DEFAULT_STATE_DIR
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def _is_instagram_media_url(url: str) -> bool:
    text = str(url or "")
    return "instagram.com" in text and any(part in text for part in ("/reel/", "/p/", "/tv/"))


def _is_direct_stream_url(url: str) -> bool:
    low = str(url or "").lower()
    if not low.startswith(("http://", "https://")):
        return False
    if any(x in low for x in (".mp4", ".m3u8", "mime_type=video", "/video/tos/", "/aweme/v1/play")):
        return True
    host = urlparse(low).netloc
    return any(h in host for h in ("tiktok.com", "cdninstagram", "fbcdn"))


def choose_embedded_stream_url(
    dom_info: Mapping[str, Any] | None,
    *,
    fallback_url: str = "",
    media_status: Mapping[str, Any] | None = None,
) -> str:
    """Pick the best stream/page URL for embedded native playback."""
    info = dict(dom_info) if isinstance(dom_info, Mapping) else {}
    media = dict(media_status) if isinstance(media_status, Mapping) else {}
    loc = str(info.get("location") or fallback_url or "").strip()
    host = urlparse(loc or fallback_url).netloc.lower()
    tiktok_mode = "tiktok.com" in host

    stream_urls: list[str] = []
    page_urls: list[str] = []
    for err in media.get("recent_errors", []) or []:
        if isinstance(err, Mapping):
            src = str(err.get("src") or "").strip()
            if src and _is_direct_stream_url(src):
                stream_urls.append(src)

    for key in ("last_clicked", "dialog_href", "active_href", "first_reel_href", "first_media_href"):
        value = str(info.get(key) or "").strip()
        if value:
            page_urls.append(value)
    if _is_instagram_media_url(loc):
        page_urls.insert(0, loc)
    video_src = str(info.get("video_src") or "").strip()
    if video_src:
        stream_urls.append(video_src)
    if loc and loc not in page_urls:
        page_urls.append(loc)
    if fallback_url:
        page_urls.append(str(fallback_url).strip())

    ordered = (stream_urls + page_urls) if tiktok_mode else (page_urls + stream_urls)
    seen: set[str] = set()
    for candidate in ordered:
        if not candidate or candidate in {"sifta://home", "about:blank"} or candidate in seen:
            continue
        seen.add(candidate)
        if candidate.startswith(("http://", "https://")):
            return candidate
    return ""


def build_cdn_fetch_headers(
    stream_url: str,
    *,
    page_url: str = "",
    user_agent: str = _DEFAULT_UA,
    cookie_header: str = "",
) -> dict[str, str]:
    """Minimum strict headers for TikTok/social CDN fetches (Gemini research r776)."""
    clean = (stream_url or "").strip()
    headers = {
        "User-Agent": user_agent or _DEFAULT_UA,
        "Referer": referer_for_url(page_url or clean),
        "Accept": "*/*",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    return headers


def cookie_header_from_qnetwork_cookies(cookies: list[Any]) -> str:
    """Format QNetworkCookie list into a Cookie header string."""
    pairs: list[str] = []
    for cookie in cookies or []:
        try:
            name = bytes(cookie.name()).decode("utf-8", errors="replace").strip()
            value = bytes(cookie.value()).decode("utf-8", errors="replace").strip()
            if name:
                pairs.append(f"{name}={value}")
        except Exception:
            continue
    return "; ".join(pairs)


def extract_cookie_header_from_profile(profile: Any, target_url: str) -> str:
    """Export cookies from QWebEngineProfile for urllib/CDN fetch (async store bridge)."""
    if profile is None:
        return ""
    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtWidgets import QApplication
    except Exception:
        return ""

    try:
        store = profile.cookieStore()
    except Exception:
        return ""

    target = QUrl(str(target_url or "https://www.tiktok.com/"))
    host = target.host().lower()
    collected: list[Any] = []

    def _accept(cookie: Any) -> None:
        try:
            domain = str(cookie.domain() or "").lstrip(".").lower()
            if host and domain and host not in domain and not domain.endswith(host):
                return
            collected.append(cookie)
        except Exception:
            pass

    try:
        store.cookieAdded.connect(_accept)
        store.loadAllCookies()
        app = QApplication.instance()
        if app is not None:
            deadline = time.time() + 0.6
            while time.time() < deadline:
                app.processEvents()
                time.sleep(0.02)
        store.cookieAdded.disconnect(_accept)
    except Exception:
        try:
            store.cookieAdded.disconnect(_accept)
        except Exception:
            pass

    return cookie_header_from_qnetwork_cookies(collected)


def referer_for_url(url: str) -> str:
    """Best-effort Referer for CDN fetches."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if "tiktok" in host:
            return "https://www.tiktok.com/"
        if "instagram" in host or "cdninstagram" in host:
            return "https://www.instagram.com/"
        if host:
            return f"{parsed.scheme}://{host}/"
    except Exception:
        pass
    return "https://www.tiktok.com/"


def fetch_stream_to_temp(
    url: str,
    *,
    referer: str = "",
    user_agent: str = _DEFAULT_UA,
    cookie_header: str = "",
    opener: Callable[..., Any] | None = None,
    max_bytes: int = 64 * 1024 * 1024,
) -> dict[str, Any]:
    """Download stream bytes to a temp file for local QMediaPlayer playback."""
    clean = (url or "").strip()
    if not clean.startswith(("http://", "https://")):
        return {"ok": False, "reason": "invalid_url", "url": clean}

    headers = build_cdn_fetch_headers(
        clean,
        page_url=referer or clean,
        user_agent=user_agent,
        cookie_header=cookie_header,
    )

    req = Request(clean, headers=headers)
    try:
        resp = (opener or urlopen)(req, timeout=30)
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            return {"ok": False, "reason": "stream_too_large", "url": clean}
        suffix = ".mp4" if "mp4" in clean.lower() else ".bin"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="alice_embed_")
        tmp.write(data)
        tmp.close()
        return {
            "ok": True,
            "url": clean,
            "local_path": tmp.name,
            "bytes": len(data),
            "strategy": "fetch_then_play",
        }
    except Exception as exc:
        return {
            "ok": False,
            "reason": "fetch_failed",
            "url": clean,
            "error": f"{type(exc).__name__}: {exc}",
        }


def append_player_receipt(row: Mapping[str, Any], *, state_dir: str | Path | None = None) -> Path:
    from System.swarm_media_codec_bridge import append_bridge_receipt

    payload = dict(row)
    payload.setdefault("truth_label", TRUTH_LABEL)
    payload.setdefault("ts", time.time())
    payload.setdefault("trace_id", str(uuid.uuid4()))
    return append_bridge_receipt(payload, state_dir=state_dir)


def build_embedded_player_panel(parent=None):
    """Return (panel_widget, player, video_widget, audio_output) or Nones if unavailable."""
    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
        from PyQt6.QtMultimediaWidgets import QVideoWidget
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
    except Exception:
        return None, None, None, None

    panel = QWidget(parent)
    panel.setObjectName("aliceEmbeddedNativePlayer")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(4, 4, 4, 4)

    header = QHBoxLayout()
    title = QLabel("Alice native decode surface")
    title.setObjectName("embeddedPlayerTitle")
    close_btn = QPushButton("✕")
    close_btn.setFixedSize(28, 28)
    close_btn.setToolTip("Hide embedded player")
    header.addWidget(title)
    header.addStretch(1)
    header.addWidget(close_btn)
    layout.addLayout(header)

    video = QVideoWidget(panel)
    video.setMinimumHeight(180)
    layout.addWidget(video, stretch=1)

    status = QLabel("Idle")
    status.setObjectName("embeddedPlayerStatus")
    layout.addWidget(status)

    player = QMediaPlayer(panel)
    audio = QAudioOutput(panel)
    player.setAudioOutput(audio)
    player.setVideoOutput(video)

    def _on_close():
        try:
            player.stop()
        except Exception:
            pass
        panel.setVisible(False)
        status.setText("Hidden")

    close_btn.clicked.connect(_on_close)

    panel._alice_player = player  # type: ignore[attr-defined]
    panel._alice_video = video  # type: ignore[attr-defined]
    panel._alice_status = status  # type: ignore[attr-defined]
    panel._alice_close = close_btn  # type: ignore[attr-defined]
    return panel, player, video, audio


def play_url_in_embedded_panel(
    panel,
    player,
    url: str,
    *,
    page_url: str = "",
    user_agent: str = _DEFAULT_UA,
    cookie_header: str = "",
    fetch_opener: Callable[..., Any] | None = None,
    state_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Play URL inside the embedded QMediaPlayer panel; fetch fallback on failure."""
    from PyQt6.QtCore import QUrl

    clean = (url or "").strip()
    row: dict[str, Any] = {
        "action": "embedded_native_play_attempt",
        "source": "alice_browser_embedded_limb",
        "requested_url": clean,
        "page_url": page_url,
        "lane": "EMBEDDED_NATIVE_PLAYER",
    }

    def _hide_panel() -> None:
        try:
            panel.setVisible(False)
        except Exception:
            pass

    if not clean.startswith(("http://", "https://")):
        row.update({"ok": False, "reason": "no_playable_url"})
        _hide_panel()
        append_player_receipt(row, state_dir=state_dir)
        return row

    status_lbl = getattr(panel, "_alice_status", None)

    def _set_status(text: str) -> None:
        if status_lbl is not None:
            try:
                status_lbl.setText(text)
            except Exception:
                pass

    host = urlparse(clean).netloc.lower()
    tiktok_cdn = "tiktok.com" in host
    # Gemini r776: QMediaPlayer cannot inject Referer; TikTok CDN needs fetch-first.
    skip_direct = tiktok_cdn or "mime_type=video" in clean.lower()

    if not skip_direct:
        try:
            player.stop()
            player.setSource(QUrl(clean))
            player.play()
            panel.setVisible(True)
            _set_status(f"Playing (direct): {clean[:72]}…")
            row.update({"ok": True, "strategy": "direct_qmediaplayer", "playing_url": clean})
            append_player_receipt(row, state_dir=state_dir)
            return row
        except Exception as exc:
            row["direct_error"] = f"{type(exc).__name__}: {exc}"

    row["headers"] = build_cdn_fetch_headers(
        clean,
        page_url=page_url or clean,
        user_agent=user_agent,
        cookie_header=cookie_header,
    )
    fetched = fetch_stream_to_temp(
        clean,
        referer=referer_for_url(page_url or clean),
        user_agent=user_agent,
        cookie_header=cookie_header,
        opener=fetch_opener,
    )
    row["fetch"] = fetched
    if not fetched.get("ok"):
        row.update({"ok": False, "reason": fetched.get("reason", "fetch_failed")})
        _set_status(f"Decode failed: {row.get('reason')}")
        _hide_panel()
        append_player_receipt(row, state_dir=state_dir)
        return row

    local_path = str(fetched.get("local_path") or "")
    try:
        player.stop()
        player.setSource(QUrl.fromLocalFile(local_path))
        player.play()
        panel.setVisible(True)
        _set_status(f"Playing (fetched {fetched.get('bytes', 0)} B)")
        row.update({
            "ok": True,
            "strategy": "fetch_then_qmediaplayer",
            "playing_url": local_path,
            "remote_url": clean,
        })
        append_player_receipt(row, state_dir=state_dir)
        return row
    except Exception as exc:
        row.update({
            "ok": False,
            "reason": "local_play_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "local_path": local_path,
        })
        _set_status(f"Local play failed: {type(exc).__name__}")
        _hide_panel()
        append_player_receipt(row, state_dir=state_dir)
        return row


__all__ = [
    "TRUTH_LABEL",
    "append_player_receipt",
    "build_cdn_fetch_headers",
    "build_embedded_player_panel",
    "choose_embedded_stream_url",
    "cookie_header_from_qnetwork_cookies",
    "extract_cookie_header_from_profile",
    "fetch_stream_to_temp",
    "play_url_in_embedded_panel",
    "referer_for_url",
]
