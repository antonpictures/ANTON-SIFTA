#!/usr/bin/env python3
"""scripts/show_memory_digest.py

Hand the Architect's own teaching back to him.

Usage::

    cd /Users/ioanganton/Music/ANTON_SIFTA
    PYTHONPATH=. python3 scripts/show_memory_digest.py            # today
    PYTHONPATH=. python3 scripts/show_memory_digest.py 2026-05-15 # any UTC date
    PYTHONPATH=. python3 scripts/show_memory_digest.py --list     # all archived dates
    PYTHONPATH=. python3 scripts/show_memory_digest.py --force    # regenerate today

This is the memory-symbiosis read-out. When George's biological memory
is tired, he runs this and gets back a one-page receipt-anchored summary
of: what Alice reflected on, what the swarm built, what the Architect
authorized, and what care threads remain open per §7.13.

Writes ``Documents/architect_memory/architect_daily_digest_<DATE>.md``
and prints the same markdown to stdout.

StigAuth: SIFTA_ARCHITECT_MEMORY_ARCHIVE_V0 (Cowork CW47, surgery
cw47-0516-2041, complementary to Codex's on-demand builder 22d615a1).
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from System.swarm_architect_memory_archive import (
    list_archived_digests,
    recall_for_date,
    write_daily_digest,
)


def _print_index() -> int:
    items = list_archived_digests()
    if not items:
        print("No archived daily digests yet.")
        print("Run this script without --list to write today's digest.")
        return 0
    print(f"Archived daily memory digests ({len(items)} total):")
    for item in items:
        print(f"  {item['date']}  ·  {item['size']:>6} bytes  ·  {item['path']}")
    return 0


def main(argv: list[str]) -> int:
    args = list(argv)
    force = False
    if "--force" in args:
        force = True
        args = [a for a in args if a != "--force"]
    if "--list" in args:
        return _print_index()

    target = args[0] if args else None

    if target is not None:
        existing = recall_for_date(target)
        if existing is not None and not force:
            print(existing)
            return 0

    result = write_daily_digest(target=target, force=force)
    print("-" * 78)
    print(
        f"Digest written: {result['path']}  "
        f"({result['renderer']}, {result['bytes']} bytes, "
        f"new={result['wrote']})"
    )
    print("-" * 78)
    body = recall_for_date(result["date"])
    if body:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
