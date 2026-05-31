#!/usr/bin/env python3
"""SIFTA media codec bridge for embedded browser limbs.

This is not a new H.264/AAC bitstream implementation. It is the honest SIFTA
layer around codec capability: detect embedded Qt media failures, explain them
from MediaError evidence, and hand playback to the host-native decoder path when
that is the correct repair.
"""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping


REPO = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = REPO / ".sifta_state"
LEDGER_NAME = "media_codec_bridge.jsonl"
TRUTH_LABEL = "SIFTA_MEDIA_CODEC_BRIDGE_V1"

MEDIA_ERROR_LABELS = {
    1: "MEDIA_ERR_ABORTED",
    2: "MEDIA_ERR_NETWORK",
    3: "MEDIA_ERR_DECODE",
    4: "MEDIA_ERR_SRC_NOT_SUPPORTED",
}
NATIVE_HANDOFF_CODES = {2, 3, 4}
CODEC_FAILURE_CODES = {3, 4}


def _state_dir(state_dir: str | Path | None = None) -> Path:
    if state_dir is None:
        return DEFAULT_STATE_DIR
    p = Path(state_dir)
    if p.name == ".sifta_state":
        return p
    return p / ".sifta_state"


def normalize_media_error_code(code: Any) -> int | None:
    """Return a valid HTMLMediaElement.error.code integer, or None."""
    if code is None or code == "":
        return None
    try:
        value = int(code)
    except (TypeError, ValueError):
        return None
    if value in MEDIA_ERROR_LABELS:
        return value
    return None


def diagnose_media_error_code(code: Any) -> dict[str, Any]:
    """Translate an HTML5 media error code into an Alice-safe diagnosis."""
    value = normalize_media_error_code(code)
    if value is None:
        return {
            "code": None,
            "label": "NO_MEDIA_ERROR",
            "likely_cause": "no_browser_media_error_observed",
            "native_handoff_recommended": False,
            "action": "continue_embedded_playback_or_wait_for_more_evidence",
        }

    if value in CODEC_FAILURE_CODES:
        likely = "embedded_qtwebengine_decode_or_codec_capability_failure"
        action = "open_url_in_native_macos_browser_or_codec_enabled_engine"
    elif value == 2:
        likely = "network_login_bot_wall_or_fetch_failure"
        action = "retry_after_login_or_open_in_native_browser"
    else:
        likely = "playback_aborted_by_page_or_user"
        action = "retry_embedded_playback_before_native_handoff"

    return {
        "code": value,
        "label": MEDIA_ERROR_LABELS[value],
        "likely_cause": likely,
        "native_handoff_recommended": value in NATIVE_HANDOFF_CODES,
        "action": action,
    }


def codec_bridge_status() -> dict[str, Any]:
    """Report the available host-side playback bridge without overstating codecs."""
    system = platform.system()
    open_tool = shutil.which("open") if system == "Darwin" else None
    xdg_open = shutil.which("xdg-open") if system != "Darwin" else None
    ffmpeg = shutil.which("ffmpeg")
    return {
        "truth_label": TRUTH_LABEL,
        "platform": system,
        "native_handoff_available": bool(open_tool or xdg_open),
        "native_opener": open_tool or xdg_open or "",
        "ffmpeg_available": bool(ffmpeg),
        "ffmpeg_path": ffmpeg or "",
        "strategy": (
            "native_macos_decoder_handoff"
            if open_tool
            else "desktop_native_opener_handoff"
            if xdg_open
            else "diagnosis_only"
        ),
        "claim_boundary": (
            "SIFTA diagnoses and routes playback; it does not ship a new "
            "proprietary H.264/AAC decoder in Python."
        ),
    }


def should_offer_native_handoff(media_status: Mapping[str, Any] | None) -> bool:
    """Return True when the embedded browser should offer host playback."""
    if not media_status:
        return False
    code = normalize_media_error_code(media_status.get("last_error_code"))
    if code in NATIVE_HANDOFF_CODES:
        return True
    for err in media_status.get("recent_errors", []) or []:
        if normalize_media_error_code(err.get("code")) in NATIVE_HANDOFF_CODES:
            return True
    return False


def append_bridge_receipt(row: Mapping[str, Any], *, state_dir: str | Path | None = None) -> Path:
    """Append a forgeable local bridge receipt for coordination/debugging."""
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    ledger = sd / LEDGER_NAME
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
    return ledger


def open_url_in_native_player(
    url: str,
    *,
    source: str = "alice_browser",
    state_dir: str | Path | None = None,
    launcher: Callable[[list[str]], Any] | None = None,
    opener_path: str | None = None,
) -> dict[str, Any]:
    """Open a page/video URL in the OS-native playback/browser path and receipt it."""
    clean_url = (url or "").strip()
    status = codec_bridge_status()
    row: dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "source": source,
        "action": "native_media_handoff",
        "url": clean_url,
        "bridge_status": status,
        "lane": "LOCAL_BROWSER_LIMB_DIAGNOSTIC",
    }

    if not clean_url or clean_url in {"sifta://home", "about:blank"}:
        row.update({"ok": False, "reason": "no_external_url"})
        append_bridge_receipt(row, state_dir=state_dir)
        return row

    opener = opener_path or status.get("native_opener") or ""
    if not opener:
        row.update({"ok": False, "reason": "no_native_opener_available"})
        append_bridge_receipt(row, state_dir=state_dir)
        return row

    cmd = [opener, clean_url]
    try:
        proc = (launcher or subprocess.Popen)(cmd)
        row.update({
            "ok": True,
            "command": cmd,
            "pid": getattr(proc, "pid", None),
            "reason": "opened_native_decoder_path",
        })
    except Exception as exc:
        row.update({
            "ok": False,
            "command": cmd,
            "reason": "native_handoff_failed",
            "error": f"{type(exc).__name__}: {exc}",
        })

    append_bridge_receipt(row, state_dir=state_dir)
    return row


def media_status_summary(media_status: Mapping[str, Any] | None, *, url: str = "") -> str:
    """Short human-readable explanation for Alice's browser-limb report."""
    code = None if not media_status else media_status.get("last_error_code")
    diagnosis = diagnose_media_error_code(code)
    if diagnosis["code"] is None:
        return "No media decoder error is currently recorded for this page."
    if diagnosis["code"] in CODEC_FAILURE_CODES:
        return (
            "The embedded browser reported "
            f"{diagnosis['label']} for {url or 'this page'}; SIFTA should hand "
            "playback to the native decoder path or a codec-enabled browser."
        )
    return (
        "The embedded browser reported "
        f"{diagnosis['label']} for {url or 'this page'}; first suspect network, "
        "login, bot-wall, or page-level fetch failure."
    )


__all__ = [
    "TRUTH_LABEL",
    "append_bridge_receipt",
    "codec_bridge_status",
    "diagnose_media_error_code",
    "media_status_summary",
    "normalize_media_error_code",
    "open_url_in_native_player",
    "should_offer_native_handoff",
]
