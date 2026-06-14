#!/usr/bin/env python3
"""whats_left.py — consolidate the tournament's scattered "WHAT IS LEFT" lanes (r253).

The Architect keeps asking, every pass, to "show list what is left". Those open-lane
notes are scattered across many rounds in the consciousness tournament doc, in three
header shapes (### WHAT IS LEFT TO CODE / ### WHAT IS LEFT / **What is left:**). Re-deriving
the list by hand every turn is exactly the kind of work the swarm should do stigmergically.

This tool scans the latest CONSCIOUSNESS_TOURNAMENT_*.md, extracts every "what is left"
section with the round it belongs to, treats the MOST RECENT section as the live open list
(each round's "updated after rN" supersedes the prior), and:
  * prints a readable list, and
  * writes a machine-readable snapshot to .sifta_state/whats_left.json

so any IDE doctor (or the Architect) gets one source of truth for open lanes on demand.

IDE-doctor coordination tool. Read-only over the doc; the JSON snapshot is a forgeable
operational trace (covenant 4.2), not an Alice swimmer receipt.

Usage:
  python3 tools/whats_left.py                 # latest tournament -> list + snapshot
  python3 tools/whats_left.py --json          # print the JSON snapshot
  python3 tools/whats_left.py --all           # every section, not just the most recent
  python3 tools/whats_left.py --doc <path>    # explicit doc
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_DOCS = _REPO / "Documents"
_STATE = _REPO / ".sifta_state"
_SNAPSHOT = _STATE / "whats_left.json"

_ROUND_RE = re.compile(r"^##\s+(r\d+.*)$", re.IGNORECASE)
_ANCHOR_RE = re.compile(r"\[r[0-9a-z][\w-]*-[a-f0-9]{8}\]", re.IGNORECASE)
_WIL_RE = re.compile(r"what\s*is\s*left|what'?s\s*left|whats\s*left", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*([-*•]|\d+[.)])\s+(.*\S)")
_CATEGORY_RE = re.compile(r"^\s*\*\*(.+?)\*\*\s*:?\s*$")
_END_RE = re.compile(r"^(##\s|###\s|Receipt:|For the Swarm)", re.IGNORECASE)
_DATED_TOURNAMENT_RE = re.compile(r"^CONSCIOUSNESS_TOURNAMENT_(\d{4}-\d{2}-\d{2})\.md$")


def _tournament_sort_key(path: Path) -> tuple[int, str, float]:
    """Prefer the newest date-stamped carrier over mtime.

    Multiple IDEs can append to yesterday's carrier after today's file exists.
    That should not make the live list jump backward in time.
    """
    m = _DATED_TOURNAMENT_RE.match(path.name)
    if m:
        return (1, m.group(1), path.stat().st_mtime)
    return (0, "", path.stat().st_mtime)


def find_latest_tournament(docs_dir: Path = _DOCS) -> Path | None:
    cands = sorted(
        docs_dir.glob("CONSCIOUSNESS_TOURNAMENT_*.md"),
        key=_tournament_sort_key,
        reverse=True,
    )
    return cands[0] if cands else None


def _is_wil_header(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    # A "what is left" header is a markdown header (#/##/###) or a bold lead line.
    if s.startswith("#") and _WIL_RE.search(s):
        return True
    if s.startswith("**") and _WIL_RE.search(s):
        return True
    return False


def parse_whats_left(text: str) -> list[dict]:
    """Return sections [{round, header, items, line}] in document order."""
    lines = text.splitlines()
    sections: list[dict] = []
    current_round = ""
    current_anchor = ""
    pending_anchor = ""
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        line_anchor = _ANCHOR_RE.search(line)
        m = _ROUND_RE.match(line.strip())
        if m and not _WIL_RE.search(line):
            hdr = m.group(1).strip()
            anchor_m = _ANCHOR_RE.search(hdr)
            current_round = hdr
            current_anchor = anchor_m.group(0) if anchor_m else pending_anchor
            pending_anchor = ""
            i += 1
            continue
        if line_anchor and not _is_wil_header(line):
            # C1: doctors may put the unique round anchor on a separate line
            # before a section; carry it into the next "what is left" block.
            pending_anchor = line_anchor.group(0)
            if current_round:
                current_anchor = pending_anchor
            i += 1
            continue
        if _is_wil_header(line):
            header = line.strip().lstrip("#").strip().strip("*").strip(": ").strip()
            items: list[str] = []
            category = ""
            j = i + 1
            while j < n:
                ln = lines[j]
                if _END_RE.match(ln.strip()) and not _is_wil_header(ln):
                    break
                if _is_wil_header(ln):
                    break
                cat = _CATEGORY_RE.match(ln)
                bull = _BULLET_RE.match(ln)
                if cat and not bull:
                    category = cat.group(1).strip().rstrip(":").strip()
                elif bull:
                    text_item = re.sub(r"\s+", " ", bull.group(2)).strip()
                    items.append(f"[{category}] {text_item}" if category else text_item)
                j += 1
            if items:
                sections.append({
                    "round": current_round,
                    "anchor": current_anchor,
                    "header": header,
                    "items": items,
                    "line": i + 1,
                })
            i = j
            continue
        i += 1
    return sections


def build_snapshot(doc: Path) -> dict:
    text = doc.read_text(encoding="utf-8", errors="replace")
    sections = parse_whats_left(text)
    live = sections[-1] if sections else {"round": "", "header": "", "items": [], "line": 0}
    return {
        "ts": time.time(),
        "generated": time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime()),
        "source_doc": str(doc.relative_to(_REPO)) if str(doc).startswith(str(_REPO)) else str(doc),
        "section_count": len(sections),
        "live_round": live["round"],
        "live_anchor": live.get("anchor", ""),
        "live_header": live["header"],
        "open_items": live["items"],
        "open_item_count": len(live["items"]),
        "all_sections": sections,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc", default=None, help="explicit tournament doc path")
    ap.add_argument("--json", action="store_true", help="print the JSON snapshot")
    ap.add_argument("--all", action="store_true", help="print every section, not just the latest")
    ap.add_argument("--no-write", action="store_true", help="do not write the .sifta_state snapshot")
    args = ap.parse_args()

    doc = Path(args.doc) if args.doc else find_latest_tournament()
    if not doc or not doc.exists():
        print("No CONSCIOUSNESS_TOURNAMENT_*.md found.")
        return 1

    snap = build_snapshot(doc)

    if not args.no_write:
        try:
            _STATE.mkdir(parents=True, exist_ok=True)
            _SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            print(f"(snapshot write failed: {exc})")

    if args.json:
        print(json.dumps(snap, ensure_ascii=False, indent=2))
        return 0

    print(f"WHAT IS LEFT — {snap['source_doc']}")
    print(f"({snap['section_count']} 'what is left' sections; live = {snap['live_round'] or 'n/a'})\n")
    sections = snap["all_sections"] if args.all else (snap["all_sections"][-1:] if snap["all_sections"] else [])
    for sec in sections:
        print(f"## {sec['round']}  —  {sec['header']}  (line {sec['line']})")
        for it in sec["items"]:
            print(f"  - {it}")
        print()
    print(f"snapshot -> {_SNAPSHOT.relative_to(_REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
