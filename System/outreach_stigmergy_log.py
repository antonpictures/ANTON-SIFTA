#!/usr/bin/env python3
"""
outreach_stigmergy_log.py — Append-only public-milestone records (disk truth for X / press).
══════════════════════════════════════════════════════════════════════════════
Does **not** post to social APIs. Callers log what was published so provenance
matches stigmergy — separate from RL training code.

Turn 40 example: short outreach to a named correspondent; keep narrative distinct
from engineering claims (software on hardware, not biology in humans).

Each event is appended to **both** `outreach_events.jsonl` and `stigmergy_events.jsonl`
(same JSON line) so dashboards that expect either filename stay aligned with execution.
══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
OUTREACH_EVENTS_JSONL = _STATE / "outreach_events.jsonl"
STIGMERGY_EVENTS_JSONL = _STATE / "stigmergy_events.jsonl"
_LOG = OUTREACH_EVENTS_JSONL  # alias


def log_outreach_event(
    *,
    kind: str,
    summary: str,
    meta: Optional[Dict[str, Any]] = None,
    source_ide: str = "cursor_m5",
) -> Dict[str, Any]:
    """
    Append one JSONL row: public milestone / tweet / note for audit.
    Writes the identical line to `outreach_events.jsonl` and `stigmergy_events.jsonl`.
    """
    from System.jsonl_file_lock import append_line_locked

    row = {
        "event_id": str(uuid.uuid4()),
        "ts": time.time(),
        "kind": kind,
        "source_ide": source_ide,
        "summary": summary[:2000],
        "meta": meta or {},
    }
    line = json.dumps(row, ensure_ascii=False) + "\n"
    _STATE.mkdir(parents=True, exist_ok=True)
    append_line_locked(OUTREACH_EVENTS_JSONL, line)
    append_line_locked(STIGMERGY_EVENTS_JSONL, line)
    return row


if __name__ == "__main__":  # pragma: no cover
    r = log_outreach_event(
        kind="turn_40_annie_outreach_ack",
        summary="CP2F acknowledges AG31 Turn 40 sequence; disk log only — no API post from this module.",
        meta={"dyor_batch": 29, "bibliographic_anchor": "Jacobsen 2015 Little Brown"},
    )
    print(json.dumps(r, indent=2))
