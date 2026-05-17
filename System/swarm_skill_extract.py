#!/usr/bin/env python3
"""
System/swarm_skill_extract.py
=============================
Trace-to-skill extraction (Lane 3).

Thin wrapper around the extraction logic in swarm_skill_library.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import swarm_skill_library as lib

_STATE = Path(__file__).resolve().parent.parent / ".sifta_state"
_RECEIPTS = _STATE / "skill_extract.jsonl"


def _log_receipt(row: Dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    row["ts"] = time.time()
    with _RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def extract_skill_from_trace(trace: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Turn a successful trace into a SKILL.md with full provenance."""
    result = lib.extract_skill_from_successful_trace(trace, **kwargs)
    _log_receipt({
        "action": "extract_skill_from_trace",
        "trace_id": trace.get("trace_id"),
        "result": result,
    })
    return result


def find_trace_by_hash(hash_prefix: str) -> Optional[Dict[str, Any]]:
    """Scan all ledgers for a trace matching the hash."""
    for ledger in ["tool_router_trace.jsonl", "work_receipts.jsonl", "repair_log.jsonl"]:
        path = _STATE / ledger
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if hash_prefix in line:
                return json.loads(line)
    return None
