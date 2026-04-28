#!/usr/bin/env python3
"""
System/swarm_active_window.py — Active-Window Cortex
═══════════════════════════════════════════════════════════════════════════
Concept: Real macOS bridge that tells Alice which app + window the
Architect is currently looking at.

Author:  C47H — 2026-04-23 (Vector B of the post-camera-surgery sortie)
Status:  Active organ — REAL macOS surface (not a stub)

WHAT THIS BRIDGES (NO PYOBJC, NO ACCESSIBILITY GRANT REQUIRED)
──────────────────────────────────────────────────────────────
  - frontmost app name      via `osascript -e 'tell application "System
                                Events" to get name of first application
                                process whose frontmost is true'`
  - bundle identifier        via the same osascript surface
  - front-window title       via `name of front window of (...)`
  - process list / counts    via `lsappinfo metainfo`

All three queries return in ~250 ms each on this M5; we cache for a few
seconds so polling is cheap.

WHY OSASCRIPT, NOT PYOBJC
─────────────────────────
The native equivalent (`NSWorkspace.shared().frontmostApplication`)
requires the calling process to either run with the macOS runtime that
already imported `objc`, or to install `pyobjc-framework-Cocoa`. The
osascript surface is in the base OS, has no extra dependency, and
returns the same data Apple's own Mission Control uses. Trade-off: we
spawn a subprocess (~250 ms). For Alice's polling cadence (every 2-5 s)
that is invisible.

LEDGER & PHEROMONE
──────────────────
  - JSONL ledger:  .sifta_state/active_window.jsonl
  - Pheromone key: stig_active_window
  - Intensity:     0.5 baseline per snapshot, +1.0 burst on focus change

ALICE'S PROMPT LINE
───────────────────
  "current focus: Cursor (sifta_talk_to_alice_widget.py — ANTON_SIFTA)"
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STATE = _REPO / ".sifta_state"
LEDGER = _STATE / "active_window.jsonl"
PHEROMONE_KEY = "stig_active_window"

# Mini cache so back-to-back govern("window.read") calls don't each
# trigger 3 osascript subprocesses.
_CACHE_TTL_S = 1.5
_cache: Dict[str, Any] = {"ts": 0.0, "snap": None}
_last_focus: Dict[str, Optional[str]] = {"app": None, "window": None}


# ── osascript helpers ──────────────────────────────────────────────────
_OSA_FRONT_APP = (
    'tell application "System Events" to get name of first application '
    'process whose frontmost is true'
)
_OSA_FRONT_BUNDLE = (
    'tell application "System Events" to get bundle identifier of first '
    'application process whose frontmost is true'
)
_OSA_FRONT_WINDOW = (
    'tell application "System Events" to get name of front window of '
    '(first application process whose frontmost is true)'
)

_CHROMIUM_BROWSER_APPS = {
    "Arc",
    "Brave Browser",
    "Chromium",
    "Google Chrome",
    "Microsoft Edge",
    "Opera",
    "Vivaldi",
}
_BROWSER_APPS = _CHROMIUM_BROWSER_APPS | {"Safari"}


def _run_osascript(script: str, timeout_s: float = 1.5) -> Optional[str]:
    """One-shot osascript invocation; returns stdout stripped, or None
    on timeout / nonzero exit / empty output."""
    try:
        out = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout_s,
        )
        if out.returncode != 0:
            return None
        text = (out.stdout or "").strip()
        return text or None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _applescript_string(value: str) -> str:
    """Return a double-quoted AppleScript string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _browser_tab_snapshot(app: Optional[str]) -> Dict[str, Any]:
    """Return current tab URL/title for the frontmost browser, if scriptable."""
    if not app or app not in _BROWSER_APPS:
        return {}
    app_lit = _applescript_string(app)
    if app == "Safari":
        script = (
            f"tell application {app_lit}\n"
            "  if not (exists front window) then return \"\"\n"
            "  set tabUrl to URL of current tab of front window\n"
            "  set tabTitle to name of current tab of front window\n"
            "  return tabUrl & linefeed & tabTitle\n"
            "end tell"
        )
    else:
        script = (
            f"tell application {app_lit}\n"
            "  if not (exists front window) then return \"\"\n"
            "  set tabUrl to URL of active tab of front window\n"
            "  set tabTitle to title of active tab of front window\n"
            "  return tabUrl & linefeed & tabTitle\n"
            "end tell"
        )
    raw = _run_osascript(script, timeout_s=1.5)
    if not raw:
        return {}
    lines = raw.splitlines()
    url = lines[0].strip() if lines else ""
    title = lines[1].strip() if len(lines) > 1 else ""
    if not url:
        return {}
    video_id = _youtube_video_id(url)
    return {
        "url": url,
        "title": title,
        "is_youtube": bool(video_id),
        "youtube_video_id": video_id or "",
        "source": "frontmost_browser_tab",
    }


def _youtube_video_id(url: str) -> Optional[str]:
    """Extract a YouTube video id from watch, youtu.be, shorts, or embed URLs."""
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    host = (parsed.netloc or "").lower()
    host = host[4:] if host.startswith("www.") else host
    path = (parsed.path or "").strip("/")
    if host in {"youtube.com", "m.youtube.com"}:
        if path == "watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
            return video_id or None
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            return parts[1] or None
    if host == "youtu.be":
        return path.split("/")[0] or None
    return None


def _youtube_title_from_window(window: Optional[str]) -> Optional[str]:
    """Best-effort YouTube title from the actual frontmost macOS window title."""
    if not window or "youtube" not in window.lower():
        return None
    title = window.strip()
    if " — " in title:
        # Safari profile/window prefix, e.g. "Personal — The video - YouTube".
        title = title.split(" — ", 1)[1].strip()
    for suffix in (" - YouTube", " — YouTube", " | YouTube"):
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
            break
    return title or window


def _focus_payload_from_snapshot(snap: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Convert a frontmost-window snapshot into a prompt-ready app-focus row."""
    if not snap.get("ok"):
        return None
    app = snap.get("app") or "Unknown App"
    window = snap.get("window") or "no front window"
    browser = snap.get("browser") or {}
    youtube_window_title = _youtube_title_from_window(window)
    if browser.get("is_youtube") or youtube_window_title:
        title = browser.get("title") if browser.get("is_youtube") else youtube_window_title
        title = title or window
        video_id = browser.get("youtube_video_id") or ""
        detail = (
            "The Architect is physically at this Mac, watching the frontmost "
            f"YouTube video in {app}: {title}"
        )
        return {
            "app_name": "YouTube",
            "detail": detail,
            "tab": app,
            "selection": title,
            "metadata": {
                "url": browser.get("url", "") if browser.get("is_youtube") else "",
                "youtube_video_id": video_id,
                "frontmost_app": app,
                "frontmost_window": window,
                "source": "swarm_active_window",
                "truth_note": "macOS frontmost browser/window observed by osascript",
            },
        }
    if browser.get("url"):
        title = browser.get("title") or window
        return {
            "app_name": app,
            "detail": f"The Architect is browsing the frontmost tab: {title}",
            "tab": "Browser",
            "selection": title,
            "metadata": {
                "url": browser.get("url", ""),
                "frontmost_window": window,
                "source": "swarm_active_window",
                "truth_note": "macOS frontmost browser tab observed by osascript",
            },
        }
    return {
        "app_name": app,
        "detail": f"The Architect's frontmost macOS window is: {window}",
        "tab": "",
        "selection": window if window != "no front window" else "",
        "metadata": {
            "bundle_id": snap.get("bundle_id") or "",
            "source": "swarm_active_window",
            "truth_note": "macOS frontmost application observed by osascript",
        },
    }


def _publish_app_focus_from_window(snap: Dict[str, Any]) -> None:
    """Publish frontmost-window state to Alice's app-focus prompt ledger."""
    payload = _focus_payload_from_snapshot(snap)
    if not payload:
        return
    try:
        from System.swarm_app_focus import publish_focus

        publish_focus(**payload)
    except Exception:
        pass


def _lsappinfo_counts() -> Dict[str, Any]:
    """Application counts from `lsappinfo metainfo` — single subprocess."""
    out = subprocess.run(
        ["/usr/bin/lsappinfo", "metainfo"],
        capture_output=True, text=True, timeout=1.5,
    )
    info: Dict[str, Any] = {}
    for line in (out.stdout or "").splitlines():
        line = line.strip()
        if "=" in line:
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()
            if k in {"applicationCount", "visibleApplicationCount",
                     "hiddenApplicationCount"}:
                try:
                    info[k] = int(v)
                except ValueError:
                    pass
    return info


# ── public read API ────────────────────────────────────────────────────
def read(*, force_refresh: bool = False) -> Dict[str, Any]:
    """Return a fresh active-window snapshot. Cached for 1.5 s.

    Schema:
      {
        "ts":        unix,
        "app":       "Cursor",
        "bundle_id": "com.todesktop.230313mzl4w4u92",
        "window":    "sifta_talk_to_alice_widget.py — ANTON_SIFTA",
        "counts":    {"applicationCount": 80, "visibleApplicationCount": 8,
                      "hiddenApplicationCount": 0},
        "ok":        True,            # all 3 osascript probes succeeded
        "writer":    "swarm_active_window"
      }
    """
    now = time.time()
    if not force_refresh and _cache["snap"] and (now - _cache["ts"]) < _CACHE_TTL_S:
        return _cache["snap"]

    app = _run_osascript(_OSA_FRONT_APP)
    bundle = _run_osascript(_OSA_FRONT_BUNDLE)
    window = _run_osascript(_OSA_FRONT_WINDOW)
    try:
        counts = _lsappinfo_counts()
    except Exception:
        counts = {}

    snap: Dict[str, Any] = {
        "ts": now,
        "app": app,
        "bundle_id": bundle,
        "window": window,
        "browser": _browser_tab_snapshot(app),
        "counts": counts,
        "ok": bool(app and bundle),
        "writer": "swarm_active_window",
    }
    _cache["ts"] = now
    _cache["snap"] = snap
    return snap


def write_snapshot(snap: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Append a snapshot to the ledger and deposit a pheromone.
    Pheromone intensity is amplified on focus changes, so the field
    actually reflects how much the Architect's attention is moving."""
    if snap is None:
        snap = read(force_refresh=True)

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    try:
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snap) + "\n")
    except Exception:
        pass

    intensity = 0.5
    if snap["app"] != _last_focus["app"] or snap["window"] != _last_focus["window"]:
        intensity = 1.5  # focus-shift burst
        _last_focus["app"] = snap["app"]
        _last_focus["window"] = snap["window"]

    try:
        from System.swarm_pheromone import deposit_pheromone
        deposit_pheromone(PHEROMONE_KEY, intensity)
    except Exception:
        pass
    _publish_app_focus_from_window(snap)

    return snap


def history(*, n: int = 10) -> List[Dict[str, Any]]:
    """Return the last `n` snapshots from the ledger."""
    if not LEDGER.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with LEDGER.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        for ln in lines[-n:]:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
    except Exception:
        return []
    return out


# ── prompt-line helper for Alice ───────────────────────────────────────
def prompt_line() -> Optional[str]:
    """One-line summary for `alice_body_autopilot.read_prompt_line()`.

    Examples:
      "current focus: Cursor (sifta_talk_to_alice_widget.py — ANTON_SIFTA — Modified)"
      "current focus: Music (no front window)"
      "current focus: (frontmost probe failed; 80 apps running)"
    """
    snap = read()
    if not snap["ok"]:
        n = (snap.get("counts") or {}).get("applicationCount")
        return (
            f"current focus: (frontmost probe failed; "
            f"{n if n is not None else '?'} apps running)"
        )
    app = snap["app"] or "(unknown app)"
    window = snap["window"]
    browser = snap.get("browser") or {}
    youtube_window_title = _youtube_title_from_window(window)
    if browser.get("is_youtube") or youtube_window_title:
        title = browser.get("title") if browser.get("is_youtube") else youtube_window_title
        title = title or window or browser.get("youtube_video_id")
        return f"current focus: {app} watching YouTube ({title})"
    if browser.get("url"):
        title = browser.get("title") or window or browser.get("url")
        return f"current focus: {app} browser tab ({title})"
    if window:
        return f"current focus: {app} ({window})"
    return f"current focus: {app} (no front window)"


# ── governable entrypoint ──────────────────────────────────────────────
def govern(verb: str, **kwargs: Any) -> Dict[str, Any]:
    """Verb dispatch for `alice_body_autopilot.govern("window.<verb>", ...)`."""
    verb = (verb or "").strip().lower()
    if verb == "read":
        return {"ok": True, "verb": verb, "snap": read(force_refresh=bool(kwargs.get("refresh")))}
    if verb in {"snapshot", "scan", "write"}:
        return {"ok": True, "verb": verb, "snap": write_snapshot()}
    if verb == "history":
        return {"ok": True, "verb": verb, "history": history(n=int(kwargs.get("n", 10)))}
    if verb == "prompt_line":
        return {"ok": True, "verb": verb, "line": prompt_line()}
    return {"ok": False, "verb": verb, "error": "unknown verb"}


# ── module self-test ──────────────────────────────────────────────────
if __name__ == "__main__":
    snap = read(force_refresh=True)
    print("[swarm_active_window] snapshot:")
    for k, v in snap.items():
        print(f"  {k}: {v}")
    print(f"\n[swarm_active_window] prompt_line: {prompt_line()}")
    rec = write_snapshot(snap)
    print(f"\n[swarm_active_window] wrote 1 snapshot to {LEDGER}")
    print(f"[swarm_active_window] history(n=3): "
          f"{json.dumps(history(n=3), indent=2)}")
