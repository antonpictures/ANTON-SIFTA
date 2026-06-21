#!/usr/bin/env python3
"""sifta_alice_journal_viewer.py — Alice's Explorer Journal

Daily files: .sifta_state/alice_journal/YYYY-MM-DD.jsonl

Run from anywhere:
  python3 Applications/sifta_alice_journal_viewer.py          # last 24h
  python3 Applications/sifta_alice_journal_viewer.py --hours 12
  python3 Applications/sifta_alice_journal_viewer.py --all     # all days
  python3 Applications/sifta_alice_journal_viewer.py --tail 20
  python3 Applications/sifta_alice_journal_viewer.py --days    # list available days
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

_STATE       = Path(__file__).resolve().parent.parent / ".sifta_state"
_JOURNAL_DIR = _STATE / "alice_journal"
_LEGACY      = _STATE / "alice_narrative_diary.jsonl"
_PHONE       = _STATE / "owner_body_events.jsonl"

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
MAGENTA= "\033[35m"
BLUE   = "\033[34m"


class AliceJournalViewer:
    """Manifest-compatible Qt wrapper for the journal viewer surface.

    This module started as a CLI reader, but `apps_manifest.json` also exposes
    it as an in-OS widget. Keep the CLI path below intact and delegate the GUI
    surface to the canonical Alice Journal widget so there is still one journal
    organ and one owner-rhythm surface.
    """

    APP_NAME = "Alice Journal Viewer"

    def __new__(cls, *args, **kwargs):
        from Applications.sifta_alice_journal_widget import AliceJournalWidget

        class _AliceJournalViewer(AliceJournalWidget):
            APP_NAME = "Alice Journal Viewer"

        return _AliceJournalViewer(*args, **kwargs)


def _journal_label_from_ts(ts: float) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%m-%d-%y_%H:%M")


def _journal_label(row: dict) -> str:
    label = str(row.get("local_journal_label") or "").strip()
    if label:
        return label
    try:
        return _journal_label_from_ts(float(row.get("ts") or 0.0))
    except Exception:
        return "unknown_time"


def show_days() -> None:
    """List all available journal days."""
    _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(_JOURNAL_DIR.glob("*.jsonl"))
    if not files:
        print(f"{YELLOW}No journal days yet.{RESET}")
        return
    print(f"\n{BOLD}{CYAN}Available journal days:{RESET}")
    for f in files:
        try:
            lines = [l for l in f.read_text().strip().splitlines() if l.strip()]
            print(f"  {BOLD}{f.stem}{RESET}  ({len(lines)} entries)  [{f}]")
        except Exception:
            print(f"  {f.stem}")
    print()


def _load_rows(hours: float, show_all: bool, tail: int) -> list[dict]:
    cutoff = 0.0 if show_all else time.time() - hours * 3600
    rows = []

    # Legacy monolithic file
    if _LEGACY.exists():
        for line in _LEGACY.read_text().strip().splitlines():
            try:
                r = json.loads(line)
                if float(r.get("ts", 0)) >= cutoff:
                    rows.append(r)
            except Exception:
                pass

    # Daily files
    _JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    for f in sorted(_JOURNAL_DIR.glob("*.jsonl")):
        for line in f.read_text().strip().splitlines():
            try:
                r = json.loads(line)
                if float(r.get("ts", 0)) >= cutoff:
                    rows.append(r)
            except Exception:
                pass

    # Sort and deduplicate
    seen: set = set()
    unique = []
    for r in sorted(rows, key=lambda x: x.get("ts", 0)):
        key = (r.get("ts", 0), r.get("entry", "")[:40])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[-tail:] if tail > 0 else unique


def show_journal(hours: float = 24.0, tail: int = 0, show_all: bool = False) -> None:
    rows = _load_rows(hours, show_all, tail)

    if not rows:
        print(f"\n{DIM}No journal entries found. Run SIFTA OS and talk to Alice — entries appear after each turn.{RESET}\n")
        print(f"{DIM}Journal dir: {_JOURNAL_DIR}{RESET}\n")
        return

    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║   Alice's Explorer Journal  ·  alice_journal/          ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════════╝{RESET}\n")

    for r in rows:
        entry = r.get("entry", "").strip()
        etype = r.get("event_type", "turn")
        ts    = r.get("ts", 0.0)
        conf  = r.get("stt_conf", 0.0)
        label = _journal_label(r)

        if etype == "boot":
            color, icon = GREEN, "🔄"
        elif etype.startswith("phone"):
            color, icon = YELLOW, "📞"
        else:
            color, icon = RESET, "📓"

        print(f"  {icon}  {color}{entry}{RESET}")
        if conf > 0:
            print(f"     {DIM}[{label} | {etype} | stt={conf:.2f}]{RESET}")
        else:
            print(f"     {DIM}[{label} | {etype}]{RESET}")
        print()

    # Recent phone calls
    phone_rows = []
    if _PHONE.exists():
        cutoff_p = 0.0 if show_all else time.time() - hours * 3600
        for line in _PHONE.read_text().strip().splitlines():
            try:
                r = json.loads(line)
                if r.get("event_type", "").startswith("phone_call"):
                    if float(r.get("ts", 0)) >= cutoff_p:
                        phone_rows.append(r)
            except Exception:
                pass

    if phone_rows:
        print(f"{BOLD}{YELLOW}📞  Phone Call Log:{RESET}")
        for r in phone_rows:
            note = r.get("note", "")[:120]
            print(f"   {DIM}{note}{RESET}")
        print()

    print(f"{DIM}  Journal dir: {_JOURNAL_DIR}{RESET}")
    print(f"{DIM}  Entries shown: {len(rows)}{RESET}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alice's narrative journal viewer")
    parser.add_argument("--hours",  type=float, default=24.0,
                        help="Show entries from the last N hours (default 24)")
    parser.add_argument("--tail",   type=int,   default=0,
                        help="Show only the last N entries")
    parser.add_argument("--all",    dest="show_all", action="store_true",
                        help="Show all journal entries ever")
    parser.add_argument("--days",   action="store_true",
                        help="List available journal days")
    args = parser.parse_args()

    if args.days:
        show_days()
    else:
        show_journal(hours=args.hours, tail=args.tail, show_all=args.show_all)
