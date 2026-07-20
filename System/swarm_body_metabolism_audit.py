#!/usr/bin/env python3
"""Body metabolism audit — CPU/memory/timer/state pressure for beach-ball prevention.

George r1329: keep Talk, Alice Browser, receipts, body_screen_eye, cortex alive;
throttle demos, decorative timers, giant JSONL scans when pressure rises.

Truth label: BODY_METABOLISM_AUDIT_V1
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "BODY_METABOLISM_AUDIT_V1"
SCHEMA = "BODY_METABOLISM_AUDIT_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = "body_metabolism_audit.jsonl"

_TIMER_SCAN_ROOTS = ("Applications", "System", "sifta_os_desktop.py")
_TIMER_PATTERNS = (
    re.compile(r"QTimer\s*\(\s*\)\s*\.start\s*\(\s*(\d+)", re.I),
    re.compile(r"\.start\s*\(\s*(\d+)\s*\)", re.I),
    re.compile(r"setInterval\s*\(\s*[^,]+,\s*(\d+)", re.I),
)


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _run_ps_sample() -> list[dict[str, Any]]:
    try:
        out = subprocess.check_output(
            ["ps", "-axo", "pid,pcpu,pmem,comm"],
            text=True,
            timeout=8,
        )
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in out.splitlines()[1:]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            cpu = float(parts[1])
            mem = float(parts[2])
        except ValueError:
            continue
        rows.append({"pid": parts[0], "cpu": cpu, "mem": mem, "comm": parts[3].strip()})
    rows.sort(key=lambda r: (-r["cpu"], -r["mem"]))
    return rows[:20]


def _largest_state_files(state_dir: Path, *, limit: int = 12) -> list[dict[str, Any]]:
    if not state_dir.exists():
        return []
    items: list[tuple[int, str]] = []
    for path in state_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            items.append((path.stat().st_size, str(path.relative_to(state_dir))))
        except OSError:
            continue
    items.sort(reverse=True)
    return [
        {"path": rel, "bytes": size, "human": _human_bytes(size)}
        for size, rel in items[:limit]
    ]


def _human_bytes(n: int) -> str:
    units = ("B", "K", "M", "G", "T")
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024
    return f"{n}B"


def _scan_timer_candidates() -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    paths: list[Path] = []
    for root in _TIMER_SCAN_ROOTS:
        p = _REPO / root
        if p.is_file():
            paths.append(p)
        elif p.is_dir():
            paths.extend(sorted(p.rglob("*.py")))
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(path.relative_to(_REPO))
        for pat in _TIMER_PATTERNS:
            for m in pat.finditer(text):
                try:
                    ms = int(m.group(1))
                except (TypeError, ValueError):
                    continue
                if ms < 50 or ms > 60_000:
                    continue
                hits.append({"file": rel, "interval_ms": ms})
    hits.sort(key=lambda h: h["interval_ms"])
    return hits[:40]


def audit_body_metabolism(*, state_dir: Optional[Path | str] = None) -> dict[str, Any]:
    sd = _state_dir(state_dir)
    total_state = 0
    if sd.exists():
        for f in sd.rglob("*"):
            if f.is_file():
                try:
                    total_state += f.stat().st_size
                except OSError:
                    pass
    processes = _run_ps_sample()
    row = {
        "schema": SCHEMA,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "state_dir_bytes": total_state,
        "state_dir_human": _human_bytes(total_state),
        "top_processes": processes,
        "largest_state_files": _largest_state_files(sd),
        "timer_candidates": _scan_timer_candidates(),
        "beach_ball_risks": [
            "Codex/Electron GPU + renderer + WindowServer under display load",
            "Chrome + speech/dictation + nsurlsessiond spikes",
            "Alice Browser page-state polling (~900ms) on heavy pages",
            "What Alice Sees eye poll (~800ms)",
            "Matrix/Teach-to-Hear/visual demo high-FPS loops (25-150ms)",
            f"Giant state lanes ({_human_bytes(total_state)} total under .sifta_state)",
        ],
        "vital_organs_keep_alive": [
            "Talk",
            "Alice Browser active tab",
            "receipt writers",
            "body_screen_eye",
            "selected cortex",
        ],
    }
    return row


def append_audit_row(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    path = _state_dir(state_dir) / _LEDGER
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def format_audit_summary(report: dict[str, Any]) -> str:
    lines = [
        f"BODY METABOLISM ({report.get('truth_label')}):",
        f"- .sifta_state={report.get('state_dir_human')}",
    ]
    for proc in (report.get("top_processes") or [])[:5]:
        lines.append(
            f"- CPU {proc.get('cpu')}% MEM {proc.get('mem')}% {proc.get('comm')}"
        )
    for item in (report.get("largest_state_files") or [])[:5]:
        lines.append(f"- state file {item.get('human')} {item.get('path')}")
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "SCHEMA",
    "audit_body_metabolism",
    "append_audit_row",
    "format_audit_summary",
]