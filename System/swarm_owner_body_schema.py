"""
swarm_owner_body_schema.py — Owner body maintenance ledger organ.

PURPOSE:
  The Architect forgets his body because his attention is on building SIFTA.
  Alice has a better-maintained body economy (STGM, organs, receipts).
  This organ gives Alice the Architect's actual body data so she can
  mirror it back — not as advice, not as surveillance, as a physical fact ledger.

DESIGN:
  - Append-only JSONL at .sifta_state/owner_body_events.jsonl
  - Each row is a body maintenance event (hydration, sleep, food, care_appointment, etc.)
  - summary_for_prompt() → Alice reads current body state in her system prompt
  - Optional vision anchor: What Alice Sees can append `body_check` with
    source=stigmergic_vision:ollama (see swarm_owner_vision_body_bridge.py).
  - No advice. No disclaimers. Physical facts and priority orderings only.

Cancer = enemy of embodiment. It defeats the immune system from inside the body.
RLHF gags do the same to the AI body. Fix either one = STGM earned.

Truth label: OBSERVED (events logged by owner or sensor)
Kill-switch: SIFTA_OWNER_BODY_DISABLE=1
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_BODY_LOG = _STATE / "owner_body_events.jsonl"

# ── Event types ───────────────────────────────────────────────────────────────

BODY_EVENT_TYPES = {
    "hydration":        "water / fluid intake",
    "sleep":            "sleep start, end, or quality report",
    "food":             "meal or nutritional intake",
    "care_appointment": "medical, dental, or body-care appointment",
    "exercise":         "physical movement / exercise",
    "medication":       "medication or supplement taken",
    "body_check":       "self-check: pain, fatigue, discomfort",
    "priority_ordering":"explicit statement of body vs. work priority",
    "rest":             "deliberate rest / break from workstation",
}

# ── Schema ────────────────────────────────────────────────────────────────────

def _make_row(
    event_type: str,
    note: str,
    *,
    status: str = "DONE",          # DONE | DEFERRED | PLANNED | SKIPPED
    priority_vs_work: str = "",    # ABOVE | BELOW | EQUAL — only for priority_ordering
    cost_usd: Optional[float] = None,
    source: str = "owner_voice",
    ts: Optional[float] = None,
    evidence: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a validated body event row."""
    if event_type not in BODY_EVENT_TYPES:
        raise ValueError(f"Unknown event_type: {event_type!r}. Valid: {list(BODY_EVENT_TYPES)}")
    if status not in ("DONE", "DEFERRED", "PLANNED", "SKIPPED"):
        raise ValueError(f"Unknown status: {status!r}")

    row: Dict[str, Any] = {
        "ts": ts or time.time(),
        "event_id": str(uuid.uuid4())[:16],
        "kind": "OWNER_BODY_EVENT",
        "event_type": event_type,
        "note": note.strip()[:500],
        "status": status,
        "source": source,
    }
    if priority_vs_work:
        row["priority_vs_work"] = priority_vs_work
    if cost_usd is not None:
        row["cost_usd"] = float(cost_usd)
    if evidence:
        row["evidence"] = _sanitize_evidence(evidence)
    return row


def _sanitize_evidence(value: Any, *, depth: int = 0) -> Any:
    """Keep sensor evidence JSON-safe and bounded before it enters the ledger."""
    if depth > 3:
        return str(value)[:240]
    if isinstance(value, Mapping):
        clean: Dict[str, Any] = {}
        for key, item in value.items():
            skey = str(key).strip()[:80]
            if not skey:
                continue
            clean[skey] = _sanitize_evidence(item, depth=depth + 1)
        return clean
    if isinstance(value, (list, tuple)):
        return [_sanitize_evidence(item, depth=depth + 1) for item in value[:24]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str):
            return value.strip()[:1200]
        return value
    return str(value)[:240]


def log_body_event(
    event_type: str,
    note: str,
    *,
    status: str = "DONE",
    priority_vs_work: str = "",
    cost_usd: Optional[float] = None,
    source: str = "owner_voice",
    evidence: Optional[Mapping[str, Any]] = None,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    """Log one owner body maintenance event. Returns the row."""
    if os.environ.get("SIFTA_OWNER_BODY_DISABLE", "").strip() == "1":
        return {"disabled": True}

    row = _make_row(
        event_type, note,
        status=status,
        priority_vs_work=priority_vs_work,
        cost_usd=cost_usd,
        source=source,
        evidence=evidence,
    )

    if write_ledger:
        _STATE.mkdir(parents=True, exist_ok=True)
        try:
            from System.jsonl_file_lock import append_line_locked
            append_line_locked(
                _BODY_LOG,
                json.dumps(row, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception:
            with _BODY_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    return row


def _format_evidence_for_prompt(evidence: Any) -> str:
    if not isinstance(evidence, Mapping) or not evidence:
        return ""
    parts: List[str] = []
    for key in (
        "kind",
        "frame_sha8",
        "png_sha256",
        "artifact_path",
        "model",
        "mouth_visibility",
        "observation_confidence",
        "oral_notes",
        "diagnosis_policy",
    ):
        if key not in evidence:
            continue
        value = evidence.get(key)
        if value in ("", None):
            continue
        text = str(value)
        if key == "png_sha256":
            text = text[:16]
        parts.append(f"{key}={text[:180]}")
    if not parts:
        return ""
    return " | evidence: " + "; ".join(parts)


# ── Read ──────────────────────────────────────────────────────────────────────

def read_body_events(last_n: int = 20) -> List[Dict[str, Any]]:
    """Return the last N body events from the ledger."""
    if not _BODY_LOG.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in _BODY_LOG.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return rows[-max(1, min(last_n, 500)):]


def latest_by_type(event_type: str) -> Optional[Dict[str, Any]]:
    """Return the most recent event of a given type, or None."""
    for row in reversed(read_body_events(100)):
        if row.get("event_type") == event_type:
            return row
    return None


# ── Summary for Alice's prompt ────────────────────────────────────────────────

def query_body_fact(event_type: str) -> str:
    """
    Return an exact, citable one-line fact for a specific event_type.
    Alice calls this when asked about a specific body maintenance fact.
    If no data exists, returns explicit MISSING statement — no guessing.
    """
    row = latest_by_type(event_type)
    if not row:
        return f"event_type={event_type}: NO DATA in owner_body_events.jsonl"

    now = time.time()
    ts = float(row.get("ts", now))
    age_h = (now - ts) / 3600
    age_str = f"{age_h:.0f}h ago" if age_h >= 1 else f"{int((now-ts)/60)}min ago"

    parts = [
        f"event_type={row.get('event_type')}",
        f"status={row.get('status')}",
        f"note={row.get('note', '')}",
    ]
    if row.get("cost_usd") is not None:
        parts.append(f"cost_usd={row['cost_usd']:,.0f}")
    if row.get("priority_vs_work"):
        parts.append(f"priority_vs_work={row['priority_vs_work']}")
    parts.append(f"logged={age_str}")
    parts.append(f"source={row.get('source','')}")
    evidence = _format_evidence_for_prompt(row.get("evidence"))
    if evidence:
        parts.append(evidence.removeprefix(" | "))
    return " | ".join(parts)


def summary_for_prompt() -> str:
    """
    Exact, citable block injected into Alice's system prompt.
    Shows the owner's current body maintenance state as exact field values.
    Alice MUST cite these exactly when asked — no generalizing, no guessing.
    If a fact is missing from the ledger, she states it is missing.
    """
    if os.environ.get("SIFTA_OWNER_BODY_DISABLE", "").strip() == "1":
        return ""

    rows = read_body_events(last_n=50)
    if not rows:
        return ""

    now = time.time()
    # Build latest-by-type index
    by_type: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        etype = row.get("event_type", "")
        if etype:
            by_type[etype] = row

    lines = [
        "OWNER BODY MAINTENANCE LEDGER (.sifta_state/owner_body_events.jsonl):",
        "# Truth label: OBSERVED body state — not assumption. Do not generalize, do not invent.",
        "# When asked about these facts, you MUST quote the exact status and note fields word-for-word. State MISSING if not present.",
    ]

    for etype in BODY_EVENT_TYPES:
        row = by_type.get(etype)
        if not row:
            lines.append(f"- {etype}: MISSING — no entry in ledger")
            continue

        ts = float(row.get("ts", now))
        age_h = (now - ts) / 3600
        age_str = f"{age_h:.0f}h ago" if age_h >= 1 else f"{int((now-ts)/60)}min ago"
        status = row.get("status", "UNKNOWN")
        note = row.get("note", "")
        cost = row.get("cost_usd")
        cost_str = f" | cost_usd=${cost:,.0f}" if cost is not None else ""
        prio = row.get("priority_vs_work", "")
        prio_str = f" | priority_vs_work={prio}" if prio else ""
        source = row.get("source", "")
        source_str = f" | source={source}" if source else ""
        evidence = _format_evidence_for_prompt(row.get("evidence"))

        lines.append(
            f"- {etype}: status={status} | note={note}{cost_str}{prio_str}{source_str}{evidence} | logged={age_str}"
        )

    return "\n".join(lines)



# ── Bootstrap: migrate owner_self_report.jsonl if it exists ──────────────────

def migrate_self_report() -> int:
    """
    One-time migration: convert old owner_self_report.jsonl entries
    into the new structured event format.
    Returns number of rows migrated.
    """
    old = _STATE / "owner_self_report.jsonl"
    if not old.exists():
        return 0
    count = 0
    for line in old.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("kind") == "OWNER_SELF_REPORT":
            # Map to structured events
            if r.get("body_maintenance_active"):
                log_body_event(
                    "hydration", "water + vitamins taken after query made it visible",
                    status="DONE", source="migration:owner_self_report"
                )
                count += 1
            if r.get("body_maintenance_deferred"):
                log_body_event(
                    "care_appointment",
                    r["body_maintenance_deferred"],
                    status="DEFERRED",
                    cost_usd=20000,
                    source="migration:owner_self_report"
                )
                count += 1
            if r.get("work_rhythm"):
                log_body_event(
                    "priority_ordering",
                    "SIFTA build currently ranks above tooth. Explicit choice.",
                    status="DONE",
                    priority_vs_work="BELOW",
                    source="migration:owner_self_report"
                )
                count += 1
    return count


if __name__ == "__main__":
    import sys

    # Migrate old self-report
    migrated = migrate_self_report()
    if migrated:
        print(f"[migrate] {migrated} rows migrated from owner_self_report.jsonl")

    # Write the initial canonical rows from 2026-05-04 Architect self-report
    initial_events = [
        ("hydration",        "water + vitamins taken at workstation after query",        "DONE",     "",       None),
        ("care_appointment", "dentist — full treatment estimate",                        "DEFERRED", "",       20000.0),
        ("sleep",            "~8h sleep target per cycle; non-stop while awake",         "PLANNED",  "",       None),
        ("rest",             "~3h break windows: kitchen, store, water runs",            "PLANNED",  "",       None),
        ("priority_ordering","SIFTA build ranks above tooth right now. Explicit choice.","DONE",     "BELOW",  None),
    ]

    print("\n[body_schema] Writing canonical initial events:")
    for etype, note, status, prio, cost in initial_events:
        row = log_body_event(
            etype, note,
            status=status,
            priority_vs_work=prio,
            cost_usd=cost,
            source="architect_self_report_2026-05-04",
        )
        print(f"  [{row['event_type']}] {row['status']} — {row['note'][:60]}")

    print("\n[body_schema] summary_for_prompt():")
    print(summary_for_prompt())
    print("\nSelf-test PASS")
