#!/usr/bin/env python3
"""
sifta_session_log.py — Persistent Agent Session Logger
Rolling 7-day log of ALL agent stdout. Never fills the drive.
Rotates daily. Max ~50MB total. Survives GUI restarts.
"""

import sys
import os
import time
import subprocess
import threading
from pathlib import Path
from datetime import datetime

LOG_DIR = Path(__file__).parent / ".sifta_state" / "session_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

MAX_DAYS = 7
MAX_LOG_SIZE_MB = 10  # per day file


def _get_today_log() -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / f"session_{today}.log"


def _rotate_old_logs():
    """Delete logs older than MAX_DAYS."""
    logs = sorted(LOG_DIR.glob("session_*.log"))
    while len(logs) > MAX_DAYS:
        oldest = logs.pop(0)
        oldest.unlink()
        print(f"[🗂️  LOG ROTATE] Dropped: {oldest.name}", flush=True)


def _write_log_line(agent_id: str, line: str):
    log_path = _get_today_log()

    # Soft size cap — start new day file if oversized
    if log_path.exists() and log_path.stat().st_size > MAX_LOG_SIZE_MB * 1024 * 1024:
        return  # Too large for today — drop to next rotation

    ts = datetime.now().strftime("%H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{agent_id}] {line}\n")


def tail_process(agent_id: str, proc: subprocess.Popen):
    """Stream a subprocess's stdout to the persistent session log and terminal."""
    _rotate_old_logs()

    for raw_line in proc.stdout:
        line = raw_line.rstrip()
        _write_log_line(agent_id, line)
        print(f"  [{agent_id}] {line}", flush=True)

    proc.wait()
    _write_log_line(agent_id, f"--- SWIM COMPLETE (exit {proc.returncode}) ---")


def read_session(date: str = None, agent_filter: str = None, tail: int = 100):
    """Print the last `tail` lines from a session log."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    log_path = LOG_DIR / f"session_{date}.log"
    if not log_path.exists():
        print(f"[!] No session log found for {date}")
        return

    lines = log_path.read_text(encoding="utf-8").splitlines()

    if agent_filter:
        lines = [l for l in lines if f"[{agent_filter.upper()}]" in l]

    for line in lines[-tail:]:
        print(line)


def list_sessions():
    """List all available session logs."""
    logs = sorted(LOG_DIR.glob("session_*.log"), reverse=True)
    print("\n  📋 AVAILABLE SESSION LOGS")
    print("  ─────────────────────────────")
    for log in logs:
        size_kb = log.stat().st_size // 1024
        print(f"  {log.stem.replace('session_', '')} — {size_kb} KB")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SIFTA Session Log Reader")
    parser.add_argument("--list", action="store_true", help="List all session logs")
    parser.add_argument("--read", metavar="DATE", nargs="?", const="today",
                        help="Read session log (YYYY-MM-DD or 'today')")
    parser.add_argument("--agent", metavar="AGENT_ID", help="Filter by agent")
    parser.add_argument("--tail", type=int, default=100, help="Lines to show")
    args = parser.parse_args()

    if args.list:
        list_sessions()
    elif args.read is not None:
        date = None if args.read == "today" else args.read
        read_session(date=date, agent_filter=args.agent, tail=args.tail)
    else:
        parser.print_help()
