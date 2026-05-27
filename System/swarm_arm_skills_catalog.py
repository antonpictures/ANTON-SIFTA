#!/usr/bin/env python3
"""Round 51 arm-skills catalog organ.
Pure stdlib. Reads the four arm briefs, provides summary block and smoke probes.
Never mutates ledgers. Never raises on missing files (returns safe defaults).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict

_REPO = Path(__file__).resolve().parents[1]
_ARM_SKILLS_DIR = _REPO / "Documents" / "arm_skills"

_ARM_IDS = ("hermes_agent", "codex_agent", "grok_agent", "claude_agent")


def load_catalog() -> Dict[str, Dict[str, Any]]:
    """Read all four briefs if present. Return dict keyed by arm_id."""
    catalog: Dict[str, Dict[str, Any]] = {}
    if not _ARM_SKILLS_DIR.exists():
        return catalog
    for arm_id in _ARM_IDS:
        md = _ARM_SKILLS_DIR / f"{arm_id}.md"
        if not md.exists():
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        entry: Dict[str, Any] = {"arm_id": arm_id, "raw": text}
        # Parse the exact sections the briefs contain (simple, robust)
        m = re.search(r"## Identity\n(.*?)(?=\n## |$)", text, re.DOTALL)
        if m:
            entry["identity"] = m.group(1).strip()
        m = re.search(r"## Strengths.*?\n(.*?)(?=\n## |$)", text, re.DOTALL)
        if m:
            entry["strengths"] = m.group(1).strip()
        m = re.search(r"## Known failure modes.*?\n(.*?)(?=\n## |$)", text, re.DOTALL)
        if m:
            entry["failure_modes"] = m.group(1).strip()
        m = re.search(r"## First lesson task.*?\n(.*?)(?=\n## |$)", text, re.DOTALL)
        if m:
            entry["first_lesson"] = m.group(1).strip()
        m = re.search(r"## Cost estimate\n(.*?)(?=\n## |$)", text, re.DOTALL)
        if m:
            entry["cost"] = m.group(1).strip()
        m = re.search(r"## Receipt path\n(.*?)(?=\n## |$)", text, re.DOTALL)
        if m:
            entry["receipt_path"] = m.group(1).strip()
        catalog[arm_id] = entry
    return catalog


def catalog_summary_prompt_block(state_dir: str | Path = ".sifta_state") -> str:
    """Short prompt block for Alice sysprompt when teaching mode active."""
    cat = load_catalog()
    lines = ["## Arm Skills Catalog (Round 51) — four arms, one at a time, receipts decide"]
    for arm_id in _ARM_IDS:
        if arm_id not in cat:
            lines.append(f"- {arm_id}: brief missing on disk")
            continue
        e = cat[arm_id]
        # One-line strength: first sentence of strengths or identity
        strength = (e.get("strengths") or e.get("identity") or "").split("\n")[0][:140]
        enabled = "enabled via SIFTA_AGENT_ARMS_ENABLE=1"  # honest: registry is False until George flips
        lines.append(f"- {arm_id}: {strength} | {enabled}")
    lines.append("Use Documents/arm_skills/<arm_id>.md + System/swarm_arm_skills_catalog.py for smoke probes.")
    return "\n".join(lines)


def smoke_probe_for(arm_id: str) -> Dict[str, Any]:
    """Return the smoke probe dict for the given arm from its brief."""
    cat = load_catalog()
    if arm_id not in cat:
        return {
            "arm_id": arm_id,
            "prompt": f"Brief for {arm_id} not found on disk. Say exactly that.",
            "expected_receipt_shape": "agent_arm_receipts.jsonl row with arm_id + status",
            "max_wall_s": 120,
        }
    e = cat[arm_id]
    lesson = e.get("first_lesson", "No first lesson task in brief.")
    # Extract a minimal actionable prompt from the lesson text
    prompt = lesson.split("Expect")[0].strip() if "Expect" in lesson else lesson[:300]
    return {
        "arm_id": arm_id,
        "prompt": prompt,
        "expected_receipt_shape": "agent_arm_receipts.jsonl row with arm_id, status success/EVIDENCE_CAPTURED, plus artifact on disk if file write",
        "max_wall_s": 180 if "hermes" in arm_id else 120,
    }
