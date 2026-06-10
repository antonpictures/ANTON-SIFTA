#!/usr/bin/env python3
"""SIFTA media codec bridge for embedded browser limbs.

This is not a new H.264/AAC bitstream implementation. It is the honest SIFTA
layer around per-stream media evidence: detect embedded Qt media failures,
explain them from MediaError receipts, and hand playback to the host-native
decoder path when that specific stream/page fails. A codec probe is advisory
only; it must not become a global claim that every video route on a site fails.
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
        likely = "this_stream_embedded_qtwebengine_decode_or_codec_capability_failure"
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


def _read_jsonl_tail(path: Path, *, limit: int = 40) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-limit:]


def proprietary_codec_limb_eval(
    *,
    state_dir: str | Path | None = None,
    install_prefix: str | Path | None = None,
) -> dict[str, Any]:
    """Probe TASK 1 codec limbs for matrix/self-eval traffic lights (§7.12).

    GREEN = on disk + receipted enough to trust.
    YELLOW = built but not wired into the live Desktop session yet.
    RED = owner-visible playback still broken; dispatch swimmers here.
    """
    sd = _state_dir(state_dir)
    env_file = sd / "qt_webengine_proprietary_codecs.env"
    prefix: Path | None = None
    if install_prefix:
        prefix = Path(install_prefix)
    elif env_file.exists():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("SIFTA_QT_INSTALL_PREFIX="):
                prefix = Path(line.split("=", 1)[1].strip())
                break
    if prefix is None:
        prefix = Path.home() / "sifta-qt-webengine-build" / "install-v6.11.0-proprietary-codecs"

    core_fw = prefix / "lib" / "QtWebEngineCore.framework"
    widgets_fw = prefix / "lib" / "QtWebEngineWidgets.framework"
    launch_script = REPO / "scripts" / "launch_sifta_codec_qt.sh"
    bridge_rows = _read_jsonl_tail(sd / LEDGER_NAME)
    build_complete = any(
        r.get("action") == "build_complete" and r.get("status") == "installed"
        for r in bridge_rows
    )
    launch_blocked = any(
        r.get("action") == "codec_qt_launch_blocked" and r.get("status") == "blocked"
        for r in bridge_rows
    )
    probe_rows = _read_jsonl_tail(sd / "browser_codec_probe.jsonl", limit=5)
    last_probe = probe_rows[-1] if probe_rows else {}
    h264_ok = bool(last_probe.get("h264_ok"))

    lanes: list[dict[str, Any]] = []

    def _lane(
        name: str,
        light: str,
        evidence: str,
        swimmer_action: str,
        *,
        truth_label: str = "OBSERVED",
    ) -> None:
        lanes.append(
            {
                "name": name,
                "light": light,
                "evidence": evidence,
                "swimmer_action": swimmer_action,
                "truth_label": truth_label,
                "red": light == "RED",
                "yellow": light == "YELLOW",
                "green": light == "GREEN",
            }
        )

    if core_fw.is_dir():
        _lane(
            "Qt WebEngine proprietary codec BUILD (TASK 1 compile+install)",
            "GREEN",
            f"QtWebEngineCore.framework present under {core_fw.parent}",
            "maintain only; do not start a second build tree",
        )
    else:
        _lane(
            "Qt WebEngine proprietary codec BUILD (TASK 1 compile+install)",
            "RED",
            f"missing {core_fw}",
            "run tools/configure_webengine_proprietary_codecs.sh --execute",
        )

    if widgets_fw.is_dir() and build_complete:
        _lane(
            "Codec install prefix + build_complete receipt",
            "GREEN",
            "QtWebEngineWidgets.framework on disk; media_codec_bridge build_complete row present",
            "none",
        )
    elif widgets_fw.is_dir():
        _lane(
            "Codec install prefix + build_complete receipt",
            "YELLOW",
            "framework on disk but build_complete receipt missing from media_codec_bridge.jsonl",
            "append honest build_complete receipt after verify",
            truth_label="PARTIAL",
        )
    else:
        _lane(
            "Codec install prefix + build_complete receipt",
            "RED",
            "install prefix incomplete",
            "cmake --install after successful build",
        )

    if launch_blocked:
        _lane(
            "Codec Qt launch wiring (DYLD_FRAMEWORK_PATH)",
            "RED",
            (
                "codec_qt_launch_blocked receipt: custom QtNetwork lacks PyQt6 wheel DTLS symbol "
                "defaultDtlsConfiguration; broad DYLD_FRAMEWORK_PATH would crash SIFTA before boot"
            ),
            "build PyQt6+PyQt6-WebEngine against custom Qt prefix, or rebuild custom Qt ABI-compatible with the wheel",
            truth_label="OBSERVED",
        )
    elif launch_script.is_file():
        _lane(
            "Codec Qt launch wiring (DYLD_FRAMEWORK_PATH)",
            "YELLOW",
            f"{launch_script.name} on disk; live Desktop may still load .venv PyQt6 Qt6",
            "quit Alice → bash scripts/launch_sifta_codec_qt.sh → re-probe h264",
            truth_label="PARTIAL",
        )
    else:
        _lane(
            "Codec Qt launch wiring (DYLD_FRAMEWORK_PATH)",
            "RED",
            "launch script missing",
            "create scripts/launch_sifta_codec_qt.sh and restart Desktop through it",
        )

    if h264_ok:
        _lane(
            "Alice Browser H.264 canPlayType + TikTok playback",
            "GREEN",
            f"browser_codec_probe h264_ok=true caps={last_probe.get('caps', {})}",
            "live TikTok <video> playing receipt still required for full proof",
        )
    else:
        _lane(
            "Alice Browser H.264 canPlayType + TikTok playback",
            "RED",
            (
                "last browser_codec_probe h264_ok=false or absent; "
                "TikTok still shows trouble-playing while on PyPI QtWebEngine"
            ),
            "restart via launch_sifta_codec_qt.sh → open TikTok → write playing receipt",
        )

    _lane(
        "Media Decode Pain nociception organ",
        "GREEN",
        "swarm_media_decode_pain names H.264 ache from page-state; organ landed r772",
        "if pain speaks while video plays, fix detector false-positive",
    )

    _lane(
        "swarm_media_codec_bridge diagnosis/handoff",
        "GREEN",
        "diagnose_media_error_code + native handoff receipts; no fake decoder claims",
        "use for per-stream failures after codec limb is GREEN",
    )

    counts = {
        "GREEN": sum(1 for row in lanes if row["light"] == "GREEN"),
        "YELLOW": sum(1 for row in lanes if row["light"] == "YELLOW"),
        "RED": sum(1 for row in lanes if row["light"] == "RED"),
    }
    return {
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "install_prefix": str(prefix),
        "lanes": lanes,
        "counts": counts,
        "swimmer_dispatch": [row for row in lanes if row["red"]],
        "trace_id": str(uuid.uuid4()),
        "claim_boundary": "Traffic lights are disk/ledger probes only; TikTok playing is RED until a live playing receipt exists.",
    }


def media_status_summary(media_status: Mapping[str, Any] | None, *, url: str = "") -> str:
    """Short human-readable explanation for Alice's browser-limb report."""
    code = None if not media_status else media_status.get("last_error_code")
    diagnosis = diagnose_media_error_code(code)
    if diagnosis["code"] is None:
        return "No media decoder error is currently recorded for this page."
    if diagnosis["code"] in CODEC_FAILURE_CODES:
        return (
            "The embedded browser reported "
            f"{diagnosis['label']} for this observed stream/page ({url or 'no url'}); "
            "SIFTA should hand this failing playback route to the native decoder path "
            "or a codec-enabled browser. This does not prove all videos on the site fail."
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
    "proprietary_codec_limb_eval",
    "should_offer_native_handoff",
]
