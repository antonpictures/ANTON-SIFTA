#!/usr/bin/env python3
"""sifta_alice_journal_viewer.py — Alice's Explorer Journal

Run from anywhere:
  python3 Applications/sifta_alice_journal_viewer.py
  python3 Applications/sifta_alice_journal_viewer.py --hours 12
  python3 Applications/sifta_alice_journal_viewer.py --all
  python3 Applications/sifta_alice_journal_viewer.py --tail 20
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
_LEDGER = _STATE / "alice_narrative_diary.jsonl"
_PHONE  = _STATE / "owner_body_events.jsonl"
_SCHED  = _STATE / "stigmergic_schedule.jsonl"

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
MAGENTA= "\033[35m"
BLUE   = "\033[34m"


def _hhmm(ts: float) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def show_journal(hours: float = 24.0, tail: int = 0, show_all: bool = False) -> None:
    if not _LEDGER.exists():
        print(f"{YELLOW}No journal yet — start a conversation with Alice.{RESET}")
        return

    cutoff = 0.0 if show_all else time.time() - hours * 3600
    rows = []
    for line in _LEDGER.read_text().strip().splitlines():
        try:
            r = json.loads(line)
            if float(r.get("ts", 0)) >= cutoff:
                rows.append(r)
        except Exception:
            pass

    if tail > 0:
        rows = rows[-tail:]

    if not rows:
        print(f"{DIM}No journal entries in the last {hours:.0f}h.{RESET}")
        return

    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║  Alice's Explorer Journal  —  alice_narrative_diary  ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════╝{RESET}\n")

    for r in rows:
        entry = r.get("entry", "").strip()
        etype = r.get("event_type", "turn")
        ts    = r.get("ts", 0.0)
        conf  = r.get("stt_conf", 0.0)

        # Color by event type
        if etype == "boot":
            color = GREEN
            icon  = "🔄"
        elif etype.startswith("phone"):
            color = YELLOW
            icon  = "📞"
        else:
            color = RESET
            icon  = "📓"

        print(f"  {icon}  {color}{entry}{RESET}")
        print(f"     {DIM}[{_hhmm(ts)} | {etype} | stt={conf:.2f}]{RESET}")
        print()

    # ── Recent phone calls ─────────────────────────────────────────────────
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

    print(f"{DIM}  Ledger: {_LEDGER}{RESET}")
    print(f"{DIM}  Entries shown: {len(rows)}{RESET}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alice's narrative journal viewer")
    parser.add_argument("--hours", type=float, default=24.0,
                        help="Show entries from the last N hours (default 24)")
    parser.add_argument("--tail", type=int, default=0,
                        help="Show only the last N entries")
    parser.add_argument("--all", dest="show_all", action="store_true",
                        help="Show all journal entries ever")
    args = parser.parse_args()
    show_journal(hours=args.hours, tail=args.tail, show_all=args.show_all)
