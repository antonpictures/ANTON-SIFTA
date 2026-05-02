#!/usr/bin/env python3
# System/swarm_concept_context_builder.py

from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any

STATE = Path(".sifta_state")

SOURCES = {
    "now": STATE / "situated_time.jsonl",
    "day_segments": STATE / "architect_day_segments.jsonl",
    "episodic_diary": STATE / "episodic_diary.jsonl",
    "health": STATE / "nightly_health.jsonl",
    "body": STATE / "body_brain_memory.jsonl",
    "regime": STATE / "regime_shifts.jsonl",
}

def read_tail(path: Path, n: int = 5) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(errors="ignore").splitlines()[-n:]:
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows

def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "ts", "timestamp", "local_date", "start_minute", "end_minute",
        "label", "location", "media_context", "summary", "phase",
        "regime", "danger_state", "selected_drive", "action",
        "composite_score", "truth_label", "start_time", "end_time", "context_tags"
    ]
    return {k: row[k] for k in keys if k in row}

def build_concept_context(max_rows_per_source: int = 5) -> str:
    packet = {
        "generated_ts": time.time(),
        "truth_label": "CONCEPT_CONTEXT_PACKET",
        "note": "Facts from ledgers. LLM should reason over concepts; no regex intent guessing.",
        "sources": {},
    }

    for name, path in SOURCES.items():
        rows = [compact_row(r) for r in read_tail(path, max_rows_per_source)]
        if rows:
            packet["sources"][name] = rows

    return (
        "### SIFTA CONCEPT CONTEXT\n"
        "Use these ledger facts as grounded memory. "
        "Do not invent facts not present here.\n"
        + json.dumps(packet, indent=2, sort_keys=True)
    )

if __name__ == "__main__":
    print(build_concept_context())
