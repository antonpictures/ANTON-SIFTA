"""hippocampus.py – simple episodic memory replay module for SIFTA.

It stores event logs (timestamp, payload) in a JSONL ledger under `.sifta_state/hippocampus/`.
A background consolidation (cron) can be triggered via `consolidate()` which writes a summary
to `hippocampus_summary.json` and optionally prunes old entries.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LOG_DIR = _STATE / "hippocampus"
_LOG_FILE = _LOG_DIR / "events.jsonl"
_SUMMARY_FILE = _LOG_DIR / "hippocampus_summary.json"

_LOG_DIR.mkdir(parents=True, exist_ok=True)

def log_event(event: Dict[str, Any]) -> str:
    """Append a single event dict to the ledger and return its UUID.
    The caller should include a minimal payload (e.g. ``{"type": "sensors", "data": {...}}``).
    """
    event.setdefault("ts", time.time())
    event.setdefault("event_id", str(uuid.uuid4()))
    with open(_LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")
    return event["event_id"]

def load_events(since: float = 0.0) -> List[Dict[str, Any]]:
    """Return all events with timestamp >= ``since``.
    """
    events = []
    if not _LOG_FILE.exists():
        return events
    with open(_LOG_FILE) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                if d.get("ts", 0) >= since:
                    events.append(d)
            except json.JSONDecodeError:
                continue
    return events

def consolidate(retention_hours: float = 168.0) -> Dict[str, Any]:
    """Create a simple statistical summary of recent events.

    The summary is written to ``hippocampus_summary.json`` and also returned.
    Older events beyond ``retention_hours`` are pruned to keep the ledger size manageable.
    """
    cutoff = time.time() - retention_hours * 3600
    recent = load_events(since=cutoff)
    summary = {
        "generated_ts": time.time(),
        "event_count": len(recent),
        "types": {},
    }
    for ev in recent:
        t = ev.get("type", "unknown")
        summary["types"][t] = summary["types"].get(t, 0) + 1
    # write summary
    with open(_SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2)
    # prune old entries
    if _LOG_FILE.exists():
        kept = [json.dumps(ev) for ev in recent]
        with open(_LOG_FILE, "w") as f:
            f.write("\n".join(kept) + ("\n" if kept else ""))
    return summary
