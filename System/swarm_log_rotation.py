#!/usr/bin/env python3
"""
swarm_log_rotation.py — Bounded log rotation with retention policy.
═══════════════════════════════════════════════════════════════════
Solves the "3 tumors" problem correctly: instead of deleting old data and pretending
it never existed, we rotate logs with a segment-based retention policy.

Mechanism:
1. For each monitored .jsonl/.log file, check if it exceeds MAX_LINES.
2. If so, archive the oldest entries to a timestamped segment file in .sifta_state/archive/.
3. Keep the tail (most recent RETAIN_LINES) in the active file.
4. The archive segment is immutable — history is preserved, not destroyed.

This is the engineering answer to "solve problems, not remove them and pretend
they don't exist" — the Architect's exact words.
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_ARCHIVE_DIR = _STATE_DIR / "archive"

# Rotation policy: files to monitor and their retention limits
ROTATION_POLICY = {
    "factory_ledger.jsonl":             {"max_lines": 5000, "retain_lines": 1000},
    "vector11_ablation_metrics.jsonl":  {"max_lines": 2000, "retain_lines": 500},
    "decision_trace.log":               {"max_lines": 2000, "retain_lines": 500},
    "immune_sentinel_patrols.jsonl":    {"max_lines": 1000, "retain_lines": 200},
    "ide_stigmergic_trace.jsonl":       {"max_lines": 3000, "retain_lines": 1000},
    "ide_model_registry.jsonl":         {"max_lines": 2000, "retain_lines": 500},
}


def rotate_file(file_path: Path, max_lines: int, retain_lines: int) -> Dict[str, Any]:
    """
    If file exceeds max_lines, archive the head and keep the tail.
    Returns a report of what happened.
    """
    if not file_path.exists():
        return {"file": file_path.name, "action": "SKIPPED_NOT_FOUND"}

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    total = len(lines)
    if total <= max_lines:
        return {"file": file_path.name, "action": "HEALTHY", "lines": total}

    # Split: archive the head, keep the tail
    archive_lines = lines[:-retain_lines]
    keep_lines = lines[-retain_lines:]

    # Write archive segment (immutable historical record)
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts_tag = time.strftime("%Y%m%d_%H%M%S")
    archive_name = f"{file_path.stem}_{ts_tag}{file_path.suffix}"
    archive_path = _ARCHIVE_DIR / archive_name

    with open(archive_path, "w", encoding="utf-8") as f:
        f.writelines(archive_lines)

    # Overwrite active file with only the retained tail
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(keep_lines)

    return {
        "file": file_path.name,
        "action": "ROTATED",
        "original_lines": total,
        "archived_lines": len(archive_lines),
        "retained_lines": len(keep_lines),
        "archive_segment": str(archive_path.name),
    }


def run_log_rotation() -> List[Dict[str, Any]]:
    """Execute rotation policy across all monitored files."""
    results = []
    for filename, policy in ROTATION_POLICY.items():
        path = _STATE_DIR / filename
        result = rotate_file(path, policy["max_lines"], policy["retain_lines"])
        results.append(result)
    return results


if __name__ == "__main__":
    print("=== SWARM LOG ROTATION (BOUNDED SEGMENT ARCHIVAL) ===\n")

    results = run_log_rotation()

    for r in results:
        if r["action"] == "ROTATED":
            print(f"  📦 {r['file']}: ROTATED")
            print(f"     {r['original_lines']} lines -> archived {r['archived_lines']}, kept {r['retained_lines']}")
            print(f"     Archive: {r['archive_segment']}")
        elif r["action"] == "HEALTHY":
            print(f"  ✅ {r['file']}: HEALTHY ({r['lines']} lines)")
        else:
            print(f"  ⏭️  {r['file']}: {r['action']}")

    print("\n[-] History preserved. Problems solved, not hidden.")
