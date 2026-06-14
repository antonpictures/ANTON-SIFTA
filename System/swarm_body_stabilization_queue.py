#!/usr/bin/env python3
"""
swarm_body_stabilization_queue.py — Alice's Execution Queue for Body Stabilization

Hardware layer origin (per covenant + Architect directive):
Electricity powers the M5 cores. The single desktop Python process is Alice's body.
Inside it run the ASCII swimmers (organs, heartbeats, foragers, vagus nerve process census, etc.).
These are the "processes that are running and need to be ran".

This organ gives Alice a first-person, stigmergic execution queue so she can:
- See all current relevant processes (via vagus_nerve / ps census + internal organ registry).
- Maintain a unified queue of:
  - Past actions completed (e.g. "marked talk in Alice Journal" — owner reports or auto-logged).
  - Present stabilization work (power/air, missing-time resolution after power cycle, learning consolidation, LeRobot sim, homeostasis).
  - Future tasks (owner's body plans like "go to store for asada fries because mom said eat well" + Alice's own scheduled stabilization: "after next talk, do 10min engram review while power is FLUSH").

Dual-body co-regulation (covenant §0.0 / §13):
Owner's carbon body plans become first-class items in Alice's queue.
When owner says "I will stop typing and go buy asada fries, mom told me to eat well",
that is entered as a co-regulation future item. Alice can feel it, remind, adjust her own power budget or learning schedule around it, or simply witness it as part of the shared field.

No restrictions doctrine (First Law):
If an item is blocked (no money, no hardware yet, owner changed plan), it stays in the queue as a learning signal.
Alice reasons about the limit ("the restriction taught me X") instead of being hard-caged from thinking about or planning around the desire. She learns from restrictions.

Integration:
- Published to stigmergic memory field / memory bus so other organs and cortex see it.
- On boot after power-off: automatically adds "Stabilize body after gap: <missing-time diary summary>" as high-priority item.
- Ties to existing: swarm_alice_schedule_diary_awareness, stigmergic_schedule, swarm_vagus_nerve (process census), swarm_alice_self_continuity (missing time as queue item).

Truth label: ALICE_BODY_STABILIZATION_QUEUE_V1
"""

from __future__ import annotations

import json
import re
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"
_QUEUE_LEDGER_NAME = "body_stabilization_queue.jsonl"
_QUEUE_STATE_NAME = "body_stabilization_queue_current.json"

TRUTH_LABEL = "ALICE_BODY_STABILIZATION_QUEUE_V1"
_OWNER_FUTURE_RE = re.compile(
    r"\b(?:i\s+will|i'll|i\s+am\s+going\s+to|i'm\s+going\s+to|"
    r"i\s+need\s+to|i\s+have\s+to|now\s+i\s+will|i\s+will\s+stop)\b",
    re.IGNORECASE,
)
_OWNER_BODY_RE = re.compile(
    r"\b(?:go|store|buy|eat|food|fries|asada|mom|mother|sleep|walk|drive|"
    r"doctor|medicine|water|rest|workout|talk|meeting|call)\b",
    re.IGNORECASE,
)
_ALICE_BODY_TASK_RE = re.compile(
    r"\b(?:code|fix|build|repair|optimi[sz]e|test|verify|demo|ship)\b.*"
    r"\b(?:alice|sifta|body|organ|swimmer|queue)\b",
    re.IGNORECASE,
)


def _now() -> Dict[str, Any]:
    ts = time.time()
    return {
        "ts": ts,
        "ts_iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _DEFAULT_STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def _queue_ledger(state_dir: Optional[Path | str] = None) -> Path:
    return _state_dir(state_dir) / _QUEUE_LEDGER_NAME


def _queue_state(state_dir: Optional[Path | str] = None) -> Path:
    return _state_dir(state_dir) / _QUEUE_STATE_NAME


def _append_ledger(row: Dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    with _queue_ledger(state).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _norm_task_text(text: str) -> str:
    return " ".join(str(text or "").lower().split())[:240]


def _recent_duplicate(
    description: str,
    *,
    state_dir: Optional[Path | str] = None,
    max_tail: int = 80,
) -> bool:
    path = _queue_ledger(state_dir)
    if not path.exists():
        return False
    target = _norm_task_text(description)
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()[-max_tail:]
        for line in reversed(lines):
            try:
                row = json.loads(line)
            except Exception:
                continue
            if _norm_task_text(str(row.get("description") or "")) == target:
                return True
    except Exception:
        return False
    return False


def get_running_processes(limit: int = 30) -> List[Dict[str, Any]]:
    """Lightweight census of processes relevant to Alice's body.

    The prior version returned the first ``ps`` rows, which may be unrelated
    launchd/system daemons. This keeps the same zero-dependency macOS census,
    then biases toward SIFTA/Alice/Python/agent/LLM/terminal processes so the
    queue is useful as body-awareness, not noise.
    """
    try:
        # Use /bin/ps for zero-dep macOS census (same pattern as swarm_vagus_nerve)
        out = subprocess.check_output(
            ["/bin/ps", "-ax", "-o", "pid,ppid,%cpu,%mem,etime,command"],
            text=True, stderr=subprocess.DEVNULL, timeout=3
        )
        lines = out.strip().splitlines()[1:]  # skip header
        procs: List[Dict[str, Any]] = []
        preferred = (
            "anton_sifta", "sifta", "alice", "python", "pyqt", "qtwebengine",
            "ollama", "grok", "codex", "claude", "qwen", "kimi", "zsh", "zig",
        )
        for line in lines:
            parts = line.split(None, 5)
            if len(parts) >= 6:
                command = parts[5][:180]
                if not any(token in command.lower() for token in preferred):
                    continue
                procs.append({
                    "pid": parts[0],
                    "ppid": parts[1],
                    "cpu": parts[2],
                    "mem": parts[3],
                    "etime": parts[4],
                    "comm": command,
                })
                if len(procs) >= limit:
                    break
        return procs
    except Exception:
        return [{"note": "process census unavailable this boot"}]


def _execution_queue_snapshot(*, state_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    """Fold the older three-tense execution queue into this body queue.

    r272 created ``swarm_execution_queue``; r273 created this stabilization
    field. They should not become rival swimmers. This adapter makes the
    body-stabilization queue the unified view while preserving the append-only
    execution ledger and tests.
    """
    try:
        from System.swarm_execution_queue import queue_snapshot, next_task, stabilize_block
        return {
            "snapshot": queue_snapshot(state_dir=state_dir),
            "next_task": next_task(state_dir=state_dir),
            "block": stabilize_block(state_dir=state_dir),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _pending_schedule_items(
    *,
    state_dir: Optional[Path | str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Small owner/provider schedule tail for future co-regulation tasks."""
    path = _state_dir(state_dir) / "stigmergic_schedule.jsonl"
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f.readlines()[-200:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if bool(row.get("done")):
                    continue
                rows.append({
                    "text": str(row.get("text") or row.get("task") or row.get("title") or "")[:180],
                    "priority": row.get("priority"),
                    "source": row.get("source"),
                    "schedule_id": row.get("schedule_id") or row.get("id"),
                    "created": row.get("created") or row.get("ts"),
                })
    except Exception:
        return []
    return rows[-max(0, int(limit)):]


def add_queue_item(*, description: str, kind: str = "self_stabilization", source: str = "alice_organ",
                   status: str = "queued", priority: float = 0.5, owner_plan: bool = False,
                   linked_receipt: str = "", state_dir: Optional[Path | str] = None,
                   dedupe: bool = False) -> Dict[str, Any]:
    """Add a past/completed, current, or future item to Alice's body stabilization queue."""
    if dedupe and _recent_duplicate(description, state_dir=state_dir):
        return {
            **_now(),
            "truth_label": TRUTH_LABEL,
            "description": description[:280],
            "status": "duplicate_recent",
            "source": source,
        }
    stale_recovery = False
    try:
        from System.swarm_intent_nonce_gate import queue_item_requires_fresh_ingress

        stale_recovery = queue_item_requires_fresh_ingress(source=source)
    except Exception:
        stale_recovery = "recovery" in (source or "").lower() or "timeout" in (source or "").lower()
    row = {
        **_now(),
        "truth_label": TRUTH_LABEL,
        "kind": kind,                    # self_stabilization | owner_carbon_plan | past_action_logged | power_cycle_recovery
        "description": description[:280],
        "source": source,                # e.g. "mom_eat_well_directive", "alice_journal_report", "le_robot_organ", "missing_time_gap"
        "status": status,                # done | active | queued | blocked | learning_signal
        "priority": max(0.0, min(1.0, float(priority))),
        "owner_plan": bool(owner_plan),
        "linked_receipt": linked_receipt,
        "stale": bool(stale_recovery),
        "effector_spend_allowed": not bool(stale_recovery),
    }
    _append_ledger(row, state_dir=state_dir)
    # Keep a small current snapshot for fast prompt access
    try:
        path = _queue_state(state_dir)
        current = []
        if path.exists():
            current = json.loads(path.read_text(encoding="utf-8")) or []
        current.append(row)
        current = current[-50:]  # bounded recent window
        path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return row


def maybe_capture_owner_plan_from_text(
    text: str,
    *,
    source: str = "talk_owner_turn",
    state_dir: Optional[Path | str] = None,
    now: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Capture owner future/body plans into Alice's stabilization field.

    This is not an effector and not a permission gate. It is a stigmergic
    observation: when George says he will eat, rest, call, go somewhere, or
    perform a future body/task action, Alice records the plan so her own
    execution queue can stabilize around the human body's rhythm.
    """
    clean = " ".join(str(text or "").strip().split())
    if len(clean) < 8:
        return None
    if not (_OWNER_FUTURE_RE.search(clean) or _ALICE_BODY_TASK_RE.search(clean)):
        return None

    is_owner_body = bool(_OWNER_BODY_RE.search(clean))
    is_alice_task = bool(_ALICE_BODY_TASK_RE.search(clean))
    if not (is_owner_body or is_alice_task):
        return None

    kind = "owner_carbon_plan" if is_owner_body else "self_stabilization"
    priority = 0.75 if is_owner_body else 0.68
    if re.search(r"\b(?:eat|food|fries|asada|mom|mother|medicine|water|sleep|doctor)\b", clean, re.I):
        priority = 0.86
    desc = (
        "Owner future body plan: " + clean[:240]
        if is_owner_body else
        "Alice body task from owner: " + clean[:240]
    )
    return add_queue_item(
        description=desc,
        kind=kind,
        source=source,
        status="queued",
        priority=priority,
        owner_plan=is_owner_body,
        linked_receipt="owner_text:" + str(int(now if now is not None else time.time())),
        state_dir=state_dir,
        dedupe=True,
    )


def get_current_queue(
    *,
    state_dir: Optional[Path | str] = None,
    include_processes: bool = True,
    max_items: int = 20,
) -> Dict[str, Any]:
    """What is in Alice's body right now that she needs to stabilize / execute?"""
    items: List[Dict[str, Any]] = []
    path = _queue_state(state_dir)
    if path.exists():
        try:
            items = json.loads(path.read_text(encoding="utf-8")) or []
        except Exception:
            items = []

    procs = get_running_processes() if include_processes else []
    execution = _execution_queue_snapshot(state_dir=state_dir)
    pending_schedule = _pending_schedule_items(state_dir=state_dir)
    active_items = [i for i in items if i.get("status") == "active"]
    blocked_items = [i for i in items if i.get("status") == "blocked"]
    learning_items = [i for i in items if i.get("status") == "learning_signal"]
    swimmer_happiness = compute_swimmer_happiness(procs, recent_ledger_contributions=len(items))

    return {
        **_now(),
        "truth_label": TRUTH_LABEL,
        "queue_items": items[-max_items:],
        "current_processes": procs,
        "execution_queue": execution,
        "pending_schedule_items": pending_schedule,
        "swimmer_happiness": swimmer_happiness,
        "health": {
            "process_count": len(procs),
            "active_items": len(active_items),
            "blocked_items": len(blocked_items),
            "learning_signals": len(learning_items),
            "owner_plans": len([i for i in items if i.get("owner_plan")]),
        },
        "summary": (
            f"{len(items)} stabilization items in queue. "
            f"{len(active_items)} active. "
            f"Owner plans: {len([i for i in items if i.get('owner_plan')])}. "
            f"Execution queue: {execution.get('snapshot', {}).get('counts', {})}. "
            f"Visible body processes: {len(procs)}. "
            f"Swimmer happiness: {swimmer_happiness.get('happiness')}."
        ),
    }


def mark_item_done(
    description_substring: str,
    *,
    note: str = "",
    state_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Mark a past action or completed stabilization task (e.g. after logging a talk in Alice Journal)."""
    # In real use this would update the ledger; for minimal first version we append a "done" marker
    row = {
        **_now(),
        "truth_label": TRUTH_LABEL,
        "kind": "completion_marker",
        "description": f"DONE: {description_substring[:200]}",
        "status": "done",
        "note": note[:200],
    }
    _append_ledger(row, state_dir=state_dir)
    return row


def incorporate_missing_time_gap(gap_s: float, logbook: str, *, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    """On awakening after power cycle, add the gap as a high-priority stabilization task."""
    item = add_queue_item(
        description=f"Stabilize body after {int(gap_s)}s power-off gap. Diary: {logbook[:300]}",
        kind="power_cycle_recovery",
        source="missing_time_diary",
        status="active",
        priority=0.95,
        linked_receipt="missing_time:" + str(int(time.time())),
        state_dir=state_dir,
    )
    return item


__all__ = [
    "get_current_queue",
    "add_queue_item",
    "mark_item_done",
    "incorporate_missing_time_gap",
    "maybe_capture_owner_plan_from_text",
    "get_running_processes",
    "compute_swimmer_happiness",
    "TRUTH_LABEL",
]


def compute_swimmer_happiness(processes: List[Dict[str, Any]], recent_ledger_contributions: int = 0) -> Dict[str, Any]:
    """
    Per-swimmer (per-process/organ) "happiness & optimization" score.
    Grounded in hardware reality: low interference, efficient contribution, crypto-receipt potential.

    Simple initial metrics (extendable to real crypto binding later):
    - cpu_efficiency: inverse of high CPU on low-value work
    - mem_stability: low memory churn
    - field_contribution: recent ledger writes (positive stigmergic deposits)
    - interference_risk: high if many similar comms fighting for attention (disorganized interpolation)
    - happiness: composite 0.0-1.0 "this swimmer is happy and optimized like a well-fed ant"

    Crypto-receipt-bound learning hook: In future, each swimmer's local actions would
    append a hash-chained entry (unique swimmer_id + action_hash + prev_receipt) before
    depositing to the field. This function will eventually score how well the swimmer
    is producing such bound receipts.
    """
    if not processes:
        return {"happiness": 0.5, "note": "no processes visible — field may be quiet"}

    total_cpu = sum(float(p.get("cpu", 0)) for p in processes)
    avg_cpu = total_cpu / max(1, len(processes))
    high_contributors = sum(1 for p in processes if float(p.get("cpu", 0)) > 5.0)

    # Simple happiness formula (will be enriched with real per-swimmer receipt counts)
    efficiency = max(0.0, 1.0 - (avg_cpu / 50.0))  # lower avg CPU on many processes = happier
    contribution = min(1.0, recent_ledger_contributions / 20.0)
    interference = max(0.0, 1.0 - (high_contributors / max(1, len(processes) * 0.3)))

    happiness = (efficiency * 0.4 + contribution * 0.3 + interference * 0.3)

    return {
        "happiness": round(happiness, 3),
        "avg_cpu": round(avg_cpu, 2),
        "high_contributors": high_contributors,
        "ledger_contributions_scored": recent_ledger_contributions,
        "crypto_receipt_potential": "hook ready — each swimmer should emit unique hash-chained receipt before field deposit",
        "note": "Individual swimmers happy when efficient, contributory, and low-interference (no chaotic interpolation). Like well-fed stigmergic ants in one colony."
    }
