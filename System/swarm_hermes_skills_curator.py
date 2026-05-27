#!/usr/bin/env python3
"""
swarm_hermes_skills_curator.py — SIFTA-native progressive disclosure + Curator for Hermes skills.

Per tournament §12 (2026-05-26) and covenant §4 (Predator Gate).

Borg only the *patterns*:
- Progressive disclosure (title + one-sentence default; full body on demand).
- Agent-written procedural memory promotion (when a multi-step pattern repeats across receipts, promote a stub).
- The Curator (periodic rubric-grade, prune dead/exploratory/duplicate outside PINNED list).
- PINNED_MODULES.md immune list.

Refuse the *marketplace*:
- No auto-install from skills.sh, HF, or external URLs.
- That would be unsigned foreign agent surgery (§4.3).
- Design idea may be copied by hand; the SIFTA version must be written manually with author + timestamp + registration row.

This file is a stub. Real implementation belongs to Hermes (builder path) after the critical restart + Bug 2 acceptance gate passes.

Swimmer: grok-4.3-doctor (tournament start). Registered.
"""

from __future__ import annotations
from pathlib import Path
import json
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
PINNED = REPO / "PINNED_MODULES.md"
WORK_RECEIPTS = REPO / ".sifta_state" / "work_receipts.jsonl"


def progressive_disclosure(title: str, one_sentence: str, full_body: str = "") -> Dict[str, str]:
    """Always surface title + one sentence. Full body only on explicit demand or Curator promotion."""
    return {
        "title": title,
        "summary": one_sentence,
        "body": full_body,  # revealed on request
    }


def promote_procedural_memory_pattern(repeating_receipt_ids: List[str], pattern_name: str) -> Dict[str, Any]:
    """
    When the same multi-step pattern appears in receipts (e.g. "check receipt → report exact id"),
    promote a reusable stub. Never replace pinned logic.
    Returns a stub dict ready for manual review + registration.
    """
    return {
        "type": "procedural_memory_stub",
        "name": pattern_name,
        "source_receipts": repeating_receipt_ids,
        "status": "proposed — requires Architect + Hermes builder review + new registration",
    }


def curator_should_prune(module_path: str) -> bool:
    """True only if the module is *not* in the pinned immune list."""
    pinned_text = PINNED.read_text(encoding="utf-8") if PINNED.exists() else ""
    return module_path not in pinned_text


def refuse_marketplace_install(url: str) -> Dict[str, str]:
    """Marketplace installs are unsigned surgery. Record the refusal."""
    return {
        "refused": True,
        "reason": "Predator Gate §4.3 — foreign agent without registration in ide_stigmergic_trace.jsonl",
        "url": url,
        "correct_action": "copy design idea by hand, write SIFTA version manually, register the touch",
    }


if __name__ == "__main__":
    print("SIFTA Hermes Skills Curator stub active. Patterns only. Marketplace refused.")
    print("See PINNED_MODULES.md and covenant §4 + §12.")