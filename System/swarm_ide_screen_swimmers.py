#!/usr/bin/env python3
"""IDE Screen Swimmers: map Cursor / Antigravity / Codex windows onto a field."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from System.canonical_schemas import assert_payload_keys
from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
_LEDGER = _REPO / ".sifta_state" / "ide_screen_swimmers.jsonl"
_SCHEMA = "SIFTA_IDE_SCREEN_SWIMMERS_V1"
_MODULE_VERSION = "swarm_ide_screen_swimmers.v2"


def _canonical_name(app_name: str, window_name: str = "") -> Optional[str]:
    if app_name in {"Cursor", "Codex", "Antigravity"}:
        return app_name
    label = f"{app_name} {window_name}".lower()
    if app_name == "Electron" or "antigravity" in label or "walkthrough" in label:
        return "Antigravity"
    return None


def parse_osascript_bounds(output: str) -> List[Dict[str, Any]]:
    windows: List[Dict[str, Any]] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(":")
        if len(parts) == 3:
            app_name, coord_text, active_text = parts
            window_name = ""
        elif len(parts) >= 4:
            app_name, window_name, coord_text, active_text = parts[0], parts[1], parts[2], parts[3]
        else:
            continue
        name = _canonical_name(app_name, window_name)
        if name is None:
            continue
        try:
            x, y, w, h = [int(float(value)) for value in coord_text.split(",")]
        except ValueError:
            continue
        windows.append({"name": name, "app_name": app_name, "window": window_name, "x": x, "y": y, "w": max(0, w), "h": max(0, h), "is_active": active_text.strip().lower() == "true"})
    windows.sort(key=lambda row: row["name"])
    return windows


def get_ide_bounds() -> List[Dict[str, Any]]:
    script = """
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
        set out to ""
        repeat with p in application processes
            try
                set appName to name of p
                if appName is "Cursor" or appName is "Codex" or appName is "Antigravity" or appName is "Electron" then
                    if (count of windows of p) > 0 then
                        set w to first window of p
                        set pos to position of w
                        set sz to size of w
                        set wname to name of w
                        set isActive to (appName is frontApp)
                        set out to out & appName & ":" & wname & ":" & item 1 of pos & "," & item 2 of pos & "," & item 1 of sz & "," & item 2 of sz & ":" & (isActive as string) & "\n"
                    end if
                end if
            end try
        end repeat
        return out
    end tell
    """
    try:
        proc = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=6.0)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return parse_osascript_bounds(proc.stdout)


def map_to_grid(windows: List[Dict[str, Any]], grid_size: int = 16, screen_w: int = 3840, screen_h: int = 2160) -> np.ndarray:
    if grid_size <= 0:
        raise ValueError("grid_size must be positive")
    field = np.zeros((grid_size, grid_size), dtype=np.float32)
    for win in windows:
        x0 = int(np.floor((win["x"] / max(screen_w, 1)) * grid_size))
        y0 = int(np.floor((win["y"] / max(screen_h, 1)) * grid_size))
        x1 = int(np.ceil(((win["x"] + win["w"]) / max(screen_w, 1)) * grid_size))
        y1 = int(np.ceil(((win["y"] + win["h"]) / max(screen_h, 1)) * grid_size))
        x0, x1 = max(0, x0), min(grid_size, max(x0 + 1, x1))
        y0, y1 = max(0, y0), min(grid_size, max(y0 + 1, y1))
        field[x0:x1, y0:y1] += 5.0 if win.get("is_active") else 1.0
    max_value = float(field.max())
    if max_value > 0.0:
        field /= max_value
    return field


def glyph_from_grid(field: np.ndarray) -> str:
    if field.size == 0 or float(field.max()) <= 0.0:
        return ""
    chars = np.array(list(" .:-=+*#%@"))
    norm = field / (float(field.max()) + 1e-8)
    idx = np.clip((norm * (len(chars) - 1)).astype(int), 0, len(chars) - 1)
    return "\n".join("".join(chars[idx[x, y]] for x in range(field.shape[0])) for y in range(field.shape[1]))


def clusters_from_grid(field: np.ndarray, threshold: float = 0.25) -> List[Dict[str, Any]]:
    clusters = [{"x": int(x), "y": int(y), "strength": round(float(field[x, y]), 6)} for x, y in np.argwhere(field >= threshold)]
    clusters.sort(key=lambda row: row["strength"], reverse=True)
    return clusters


def _inferred_dimensions(rows: List[Dict[str, Any]], screen_w: Optional[int], screen_h: Optional[int]) -> tuple[int, int]:
    inferred_w = screen_w if screen_w is not None else 2560
    inferred_h = screen_h if screen_h is not None else 1440
    if rows:
        inferred_w = max(inferred_w, *(row["x"] + row["w"] for row in rows))
        inferred_h = max(inferred_h, *(row["y"] + row["h"] for row in rows))
    return int(inferred_w), int(inferred_h)


def build_snapshot(*, windows: Optional[List[Dict[str, Any]]] = None, grid_size: int = 16, screen_w: Optional[int] = None, screen_h: Optional[int] = None, source: str = "macos_window_bounds", now: Optional[float] = None) -> Dict[str, Any]:
    rows = get_ide_bounds() if windows is None else windows
    inferred_w, inferred_h = _inferred_dimensions(rows, screen_w, screen_h)
    grid = map_to_grid(rows, grid_size=grid_size, screen_w=inferred_w, screen_h=inferred_h)
    payload = {"event": "ide_screen_swimmers", "schema": _SCHEMA, "module_version": _MODULE_VERSION, "grid_size": int(grid_size), "screen_w": inferred_w, "screen_h": inferred_h, "windows": rows, "grid": grid.round(6).tolist(), "glyph": glyph_from_grid(grid), "clusters": clusters_from_grid(grid), "active_ide": next((row["name"] for row in rows if row.get("is_active")), ""), "source": source, "ts": time.time() if now is None else float(now)}
    assert_payload_keys("ide_screen_swimmers.jsonl", payload, strict=True)
    return payload


def write_snapshot(*, windows: Optional[List[Dict[str, Any]]] = None, ledger_path: Optional[Path] = None, grid_size: int = 16, source: str = "macos_window_bounds") -> Dict[str, Any]:
    payload = build_snapshot(windows=windows, grid_size=grid_size, source=source)
    target = Path(ledger_path) if ledger_path is not None else _LEDGER
    target.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(target, json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


def main() -> None:
    row = write_snapshot()
    print(json.dumps({k: row[k] for k in ("active_ide", "screen_w", "screen_h", "windows")}, indent=2))
    print(row["glyph"])


if __name__ == "__main__":
    main()
