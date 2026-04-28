#!/usr/bin/env python3
"""
swarm_notification_ingress.py — macOS notification / background-activity sense

Alice cannot read a private Notification Center database by wish. She can,
however, observe the same surfaces the local OS exposes to this user process:

  * visible Notification Center UI text through Accessibility, when permitted;
  * Background Task Management state through `sfltool dumpbtm`;
  * LaunchAgent plists that cause macOS "can run in the background" banners.

Every scan is written to `.sifta_state/notification_ingress.jsonl` so the
prompt can stay truthful: what Alice saw, what was blocked, and what launchd
background items are actually registered.
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "notification_ingress.jsonl"
_LATEST = _STATE / "notification_ingress_latest.json"

_INTERESTING_BACKGROUND_RE = re.compile(
    r"sifta|stig|warp9|auto[_-]?sync|codex|cursor|antigravity|ollama|python|bash",
    re.IGNORECASE,
)


def _run(cmd: List[str], timeout: float = 4.0) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "stdout": "", "stderr": ""}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "stdout": "", "stderr": ""}


def _compact_text(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _parse_sfltool_dump(raw: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if re.match(r"^#\d+:", stripped):
            if current:
                items.append(current)
            current = {}
            continue
        if ":" not in stripped or not current and not re.match(
            r"^(Name|Developer Name|Type|Flags|Disposition|Identifier|URL|Executable Path):",
            stripped,
        ):
            continue
        key, value = stripped.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        current[key] = _compact_text(value)
    if current:
        items.append(current)

    interesting: List[Dict[str, Any]] = []
    for item in items:
        hay = " ".join(str(v) for v in item.values())
        if _INTERESTING_BACKGROUND_RE.search(hay):
            interesting.append(item)
    return interesting[:40]


def scan_background_task_management() -> Dict[str, Any]:
    out = _run(["/usr/bin/sfltool", "dumpbtm"], timeout=5.0)
    if not out.get("ok"):
        return {
            "ok": False,
            "source": "sfltool dumpbtm",
            "error": out.get("error") or _compact_text(out.get("stderr")),
            "items": [],
        }
    return {
        "ok": True,
        "source": "sfltool dumpbtm",
        "items": _parse_sfltool_dump(out.get("stdout", "")),
    }


def _read_plist(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("rb") as f:
            data = plistlib.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def scan_launch_agents() -> Dict[str, Any]:
    roots = [
        Path.home() / "Library" / "LaunchAgents",
        Path("/Library/LaunchAgents"),
        Path("/Library/LaunchDaemons"),
    ]
    found: List[Dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        try:
            paths = sorted(root.glob("*.plist"))
        except OSError:
            continue
        for path in paths:
            hay = str(path)
            data = _read_plist(path) or {}
            hay += " " + json.dumps(data, default=str)
            if not _INTERESTING_BACKGROUND_RE.search(hay):
                continue
            args = data.get("ProgramArguments") or []
            if isinstance(args, list):
                args = " ".join(str(a) for a in args[:8])
            found.append({
                "label": _compact_text(data.get("Label") or path.stem),
                "path": str(path),
                "program": _compact_text(data.get("Program") or args),
                "run_at_load": bool(data.get("RunAtLoad", False)),
                "start_interval": data.get("StartInterval"),
                "keep_alive": data.get("KeepAlive", False),
            })
    return {"ok": True, "source": "LaunchAgents", "items": found[:60]}


def scan_visible_notification_center() -> Dict[str, Any]:
    script = r'''
tell application "System Events"
    if not (exists process "Notification Center") then
        return "__NO_PROCESS__"
    end if
    tell process "Notification Center"
        set out to {}
        try
            repeat with w in windows
                try
                    set end of out to (name of w as text)
                end try
                try
                    repeat with s in static texts of w
                        try
                            set end of out to (value of s as text)
                        end try
                        try
                            set end of out to (name of s as text)
                        end try
                    end repeat
                end try
                try
                    repeat with g in groups of w
                        try
                            repeat with s in static texts of g
                                try
                                    set end of out to (value of s as text)
                                end try
                                try
                                    set end of out to (name of s as text)
                                end try
                            end repeat
                        end try
                    end repeat
                end try
            end repeat
            return out as text
        on error errText number errNum
            return "__ERROR__" & errNum & ": " & errText
        end try
    end tell
end tell
'''
    out = _run(["/usr/bin/osascript", "-e", script], timeout=4.0)
    raw = (out.get("stdout") or "").strip()
    if not out.get("ok"):
        return {
            "ok": False,
            "source": "Accessibility UI",
            "error": out.get("error") or _compact_text(out.get("stderr")),
            "items": [],
        }
    if raw == "__NO_PROCESS__":
        return {"ok": True, "source": "Accessibility UI", "visible": False, "items": []}
    if raw.startswith("__ERROR__"):
        return {"ok": False, "source": "Accessibility UI", "error": raw, "items": []}

    parts = []
    for piece in re.split(r",|\n|\r", raw):
        text = _compact_text(piece, 180)
        if text and text not in parts:
            parts.append(text)
    return {
        "ok": True,
        "source": "Accessibility UI",
        "visible": bool(parts),
        "items": parts[:25],
    }


def scan_now(*, write: bool = True) -> Dict[str, Any]:
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "event": "notification_ingress_scan",
        "background_task_management": scan_background_task_management(),
        "launch_agents": scan_launch_agents(),
        "visible_notification_center": scan_visible_notification_center(),
    }
    if write:
        _STATE.mkdir(parents=True, exist_ok=True)
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        _LATEST.write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8")
    return row


def _load_latest(max_age_s: float = 90.0) -> Optional[Dict[str, Any]]:
    try:
        row = json.loads(_LATEST.read_text(encoding="utf-8"))
    except Exception:
        return None
    if time.time() - float(row.get("ts", 0) or 0) <= max_age_s:
        return row
    return None


def _priority_background_item(item: Dict[str, Any]) -> int:
    hay = json.dumps(item, default=str).lower()
    if "auto_sync" in hay or "warp9" in hay:
        return 0
    if "sifta" in hay or "stig" in hay:
        return 1
    return 2


def summary_for_alice(max_age_s: float = 90.0) -> str:
    row = _load_latest(max_age_s=max_age_s) or scan_now(write=True)
    age = int(time.time() - float(row.get("ts", 0) or 0))

    lines: List[str] = []
    visible = row.get("visible_notification_center") or {}
    if visible.get("ok") and visible.get("items"):
        joined = " | ".join(str(x)[:90] for x in visible.get("items", [])[:5])
        lines.append(f"visible Notification Center text: {joined}")
    elif visible.get("ok"):
        lines.append("visible Notification Center text: none captured")
    else:
        lines.append(f"Notification Center UI blocked: {visible.get('error', 'unknown')}")

    launch_items = (row.get("launch_agents") or {}).get("items") or []
    launch = sorted(launch_items, key=_priority_background_item)[:5]
    if launch:
        desc = []
        for item in launch:
            interval = item.get("start_interval")
            interval_text = f", every {interval}s" if interval else ""
            desc.append(f"{item.get('label')} ({Path(str(item.get('path'))).name}{interval_text})")
        lines.append("background launch agents: " + " | ".join(desc))

    btm = ((row.get("background_task_management") or {}).get("items") or [])[:5]
    if btm:
        desc = []
        for item in btm:
            ident = item.get("identifier") or item.get("name") or "unknown"
            disp = item.get("disposition") or ""
            desc.append(f"{ident} {disp}".strip())
        lines.append("macOS background-task registry: " + " | ".join(desc))

    if not lines:
        return ""
    return "MACOS NOTIFICATION / BACKGROUND ACTIVITY SENSE " f"({age}s old):\n  " + "\n  ".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", action="store_true", help="scan now and append the notification ingress ledger")
    parser.add_argument("--summary", action="store_true", help="print Alice's prompt summary")
    args = parser.parse_args()
    if args.summary:
        print(summary_for_alice())
        return 0
    row = scan_now(write=True)
    print(json.dumps(row, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
