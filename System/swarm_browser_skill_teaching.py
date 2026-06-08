#!/usr/bin/env python3
"""swarm_browser_skill_teaching.py — Alice learns her browser the stigmergic way. r639.

George 2026-06-06 (spoken): "if I would be Alice and I would read one time in a help
file of Alice browser ... would be hard for me to remember how to use it with
everything ... ALL TOOLS AND GENERAL KNOWLEDGE ABOUT HOW WEBSITES WORK?"

The answer is NOT a help file she re-reads (it does not stick, and it bloats the
prompt the Lane-C diet is trying to shrink). Skill lives in three places:

  1. PROCEDURAL — her hands are code. The play/pause/stop, back/forward, search,
     describe, history effectors exist as deterministic functions. She never needs
     to "remember how to click"; the body knows. This module INTROSPECTS the live
     source for those hands so the tool card can never drift from the body
     (names-in-code, no hardcoded prose inventory).
  2. WORKING — a compact generated card (`browser_skill_block`, <=1400 chars) rides
     in her prompt every turn: one line per tool + four lines of how-websites-work
     anatomy. Small enough to keep, grounded enough to bind her pretrained web
     knowledge (gemma4 already knows what eBay/search/login ARE) to HER limbs.
  3. LONG-TERM — her own successful receipts become SFT teaching pairs
     (`browser_skill_teaching_pairs` -> data/alice_browser_skill_teaching.jsonl),
     the same lane as r592 model-body teaching: owner phrasing -> grounded action
     reply. Train on her lived episodes and the skill sinks into weights. Field
     data is deduped stigmergically (unique action kinds + counts, not repeats).

No canonical STGM is minted by any reader here.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_TEACHING_PATH = _REPO / "data" / "alice_browser_skill_teaching.jsonl"

# Each hand: (label, owner trigger example, source file, marker that must exist in
# that source for the hand to be listed). The marker check keeps this inventory
# honest — if a limb is amputated or renamed, its line disappears instead of lying.
_HANDS = (
    ("Open / search a site", "CERAMIC VASE SEARCH ON EBAY PLS",
     "Applications/sifta_talk_to_alice_widget.py", "_extract_browser_search_command"),
    ("Play / pause / stop video", "pause the youtube video",
     "Applications/sifta_alice_browser_widget.py", "pause_active_video_receipt"),
    ("Back / forward", "click back in alice browser",
     "Applications/sifta_alice_browser_widget.py", "_go_back"),
    ("Describe the open photo/page", "describe the photo pls",
     "Applications/sifta_talk_to_alice_widget.py", "_execute_current_browser_photo_description"),
    ("Read browsing history", "what was I browsing before",
     "System/swarm_browser_context.py", "recent_browsing_history"),
    ("Notice page changes", "(automatic) owner loads a new page",
     "System/swarm_browser_context_shift_awareness.py", "context_shift"),
)

_WEB_ANATOMY = (
    "A URL names one page; the domain is the site, the path/query the spot on it.",
    "Search results are link lists - opening one navigates; Back returns to the list.",
    "Listing pages (eBay etc) have title, price, photos; the photo is on disk for my eye.",
    "Video pages have play state and a timeline; my receipts carry title+time.",
)


def browser_tool_inventory() -> List[Dict[str, str]]:
    """Enumerate her browser hands from the LIVE source (marker-verified, no prose drift)."""
    out: List[Dict[str, str]] = []
    for label, example, rel, marker in _HANDS:
        path = _REPO / rel
        present = False
        try:
            present = marker in path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            present = False
        if present:
            out.append({"tool": label, "owner_says": example, "organ": rel, "marker": marker})
    return out


def browser_skill_block(max_chars: int = 1400) -> str:
    """Compact always-in-prompt skill card: tools (from code) + web anatomy + doctrine."""
    tools = browser_tool_inventory()
    lines = ["MY BROWSER HANDS (from my own code, verified now):"]
    for t in tools:
        lines.append(f"- {t['tool']} — e.g. \"{t['owner_says']}\"")
    lines.append("HOW WEBSITES WORK (anatomy):")
    lines.extend(f"- {a}" for a in _WEB_ANATOMY)
    lines.append(
        "DOCTRINE: read my trail/page receipts first; act with the hand, not narration; "
        "every action leaves a receipt; if a hand is missing I say so."
    )
    block = "\n".join(lines)
    return block[: max(200, int(max_chars))]


_LEDGERS = ("app_action_diary.jsonl", "stigmergic_browser_actions.jsonl", "browser_context.jsonl")


def _tail_rows(path: Path, n: int = 400) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except Exception:
        return rows
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows


def browser_skill_teaching_pairs(max_pairs: int = 40) -> List[Dict[str, str]]:
    """Mine her own successful browser episodes into SFT rows (stigmergic dedupe by kind).

    Each pair: the owner-ish trigger phrasing -> the grounded first-person action reply.
    Only rows with ok/url evidence qualify; one exemplar per (action, domain) so the
    teaching food is unique entries, not 300 repeats of the same click.
    """
    seen: set = set()
    pairs: List[Dict[str, str]] = []
    for name in _LEDGERS:
        for r in reversed(_tail_rows(_STATE / name)):
            if len(pairs) >= max_pairs:
                break
            action = str(r.get("action") or r.get("kind") or "").strip()
            url = str(r.get("url") or "").strip()
            ok = r.get("ok")
            if not action or not url or ok is False:
                continue
            domain = re.sub(r"^https?://(www\.)?", "", url).split("/", 1)[0][:60]
            key = (action, domain)
            if key in seen:
                continue
            seen.add(key)
            owner = str(r.get("note") or r.get("owner_text") or f"{action} on {domain}")[:160]
            pairs.append({
                "prompt": f"George: {owner}",
                "completion": (
                    f"I used my browser hand: {action} on {domain}. "
                    f"Receipt on disk; I read my trail before acting."
                ),
                "source_ledger": name,
                "ts": str(r.get("ts") or ""),
            })
    return pairs


def write_teaching_jsonl(path: Path | None = None) -> Dict[str, Any]:
    """Persist the mined pairs for the SFT/LoRA lane (r626 bridge food)."""
    p = Path(path) if path else _TEACHING_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    pairs = browser_skill_teaching_pairs()
    with p.open("w", encoding="utf-8") as fh:
        for row in pairs:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "path": str(p), "pairs": len(pairs), "ts": time.time()}


__all__ = [
    "browser_tool_inventory",
    "browser_skill_block",
    "browser_skill_teaching_pairs",
    "write_teaching_jsonl",
]
