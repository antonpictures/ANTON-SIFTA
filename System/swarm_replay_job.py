"""
WISH_002 - REM Replay Job (digest, not dump).

Animal receipt: Wilson & McNaughton-style **replay is selective** - compress a few
high-salience trajectories from append-only ledgers into a small cortex-facing
snapshot. No "summarize everything"; tails only; **locked I/O**.

Outputs:
  - `.sifta_state/replay_memory.jsonl` - append-only run receipts
  - `.sifta_state/replay_memory.json` - latest snapshot (rewrite, small JSON)

Truth label: **OBSERVED** - heuristic salience only; not hippocampus biology.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked
from System.swarm_kernel_identity import owner_display_name, owner_name
from System.swarm_persistent_owner_history import state_dir

REPLAY_JSONL = "replay_memory.jsonl"
REPLAY_JSON = "replay_memory.json"

_LOG_SPECS: Tuple[Tuple[str, str, int], ...] = (
    ("stigtime_log.jsonl", "stigtime", 400),
    ("ide_stigmergic_trace.jsonl", "ide", 500),
    ("work_receipts.jsonl", "work", 250),
    ("nightly_health.jsonl", "health", 80),
)


def _tail_jsonl_lines(path: Path, max_lines: int) -> List[str]:
    if not path.exists() or max_lines <= 0:
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return lines[-max_lines:]


def _owner_boost(text: str) -> float:
    blob = (text or "").lower()
    on = (owner_name() or "").strip().lower()
    od = (owner_display_name() or "").strip().lower()
    score = 0.0
    if on and len(on) > 1 and on in blob:
        score += 0.12
    if od and len(od) > 1 and od.lower() in blob:
        score += 0.12
    if "architect" in blob or "owner" in blob:
        score += 0.06
    return min(0.22, score)


def salience_stigtime(row: Dict[str, Any]) -> float:
    if row.get("kind") != "STIGTIME_BOUNDARY":
        return 0.0
    s = 0.22
    inn = str(row.get("stigtime_in") or "").lower()
    if inn in ("bash", "tools"):
        s += 0.28
    if inn.startswith("chat_"):
        s += 0.08
    sp = row.get("since_prev_boundary_sec")
    if sp is not None:
        try:
            if float(sp) >= 300.0:
                s += 0.14
            elif float(sp) >= 60.0:
                s += 0.06
        except (TypeError, ValueError):
            pass
    ctx = str(row.get("context") or "")
    low = ctx.lower()
    if any(w in low for w in ("fail", "error", "pytest", "test")):
        s += 0.12
    s += _owner_boost(ctx)
    return min(1.0, s)


def salience_ide(row: Dict[str, Any]) -> float:
    kind = str(row.get("kind") or "").lower()
    s = 0.26
    if kind in ("tournament", "hill_watch"):
        s += 0.34
    elif kind in ("handoff", "swim_directive"):
        s += 0.18
    elif kind == "audit_trace":
        s += 0.22
    payload = str(row.get("payload") or row.get("intent") or row.get("finding") or "")
    if len(payload) > 200:
        s += 0.08
    if len(payload) > 800:
        s += 0.06
    s += _owner_boost(payload)
    return min(1.0, s)


def salience_work(row: Dict[str, Any]) -> float:
    try:
        work_value = float(row.get("work_value", 0.0) or 0.0)
    except (TypeError, ValueError):
        work_value = 0.0
    s = 0.24 + 0.35 * min(1.0, max(0.0, work_value))
    desc = str(row.get("description") or "") + str(row.get("work_type") or "")
    low = desc.lower()
    if "pytest" in low or "test" in low:
        s += 0.12
    if row.get("work_type") in ("FAULT_DETECTED", "REPAIR_SUCCESS"):
        s += 0.08
    s += _owner_boost(desc)
    return min(1.0, s)


def salience_health(row: Dict[str, Any]) -> float:
    s = 0.2
    blob = json.dumps(row, ensure_ascii=False).lower()
    if any(w in blob for w in ("critical", "error", "fail", "degraded")):
        s += 0.45
    return min(1.0, s)


_SALIENCE = {
    "stigtime": salience_stigtime,
    "ide": salience_ide,
    "work": salience_work,
    "health": salience_health,
}


def _compact_episode(source_log: str, row: Dict[str, Any]) -> Dict[str, Any]:
    if source_log == "stigtime":
        return {
            "source": "stigtime_log",
            "action": str(row.get("stigtime_in") or "?"),
            "transition": f"{row.get('stigtime_out')}->{row.get('stigtime_in')}",
            "held_prev_sec": row.get("since_prev_boundary_sec"),
            "intent": str(row.get("context") or "")[:120],
        }
    if source_log == "ide":
        actor = row.get("source_ide") or row.get("doctor") or row.get("model")
        return {
            "source": "ide_stigmergic_trace",
            "kind": row.get("kind"),
            "actor": str(actor)[:80] if actor else None,
            "intent": str(row.get("payload") or row.get("intent") or row.get("finding") or "")[:160],
        }
    if source_log == "work":
        return {
            "source": "work_receipts",
            "work_type": row.get("work_type"),
            "territory": str(row.get("territory") or "")[:100],
            "result": str(row.get("description") or "")[:120],
        }
    return {"source": "nightly_health", "hint": str(row.get("status") or row)[:120]}


def _dedupe_key(source_log: str, row: Dict[str, Any]) -> str:
    tid = row.get("trace_id") or row.get("receipt_id") or row.get("trace_hash")
    if tid:
        return f"{source_log}:{tid}"
    try:
        ts = float(row.get("ts") or row.get("timestamp") or 0.0)
    except (TypeError, ValueError):
        ts = 0.0
    payload = json.dumps(row, sort_keys=True, default=str, ensure_ascii=False)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{source_log}:{ts}:{digest}"


def collect_candidates(
    *,
    root: Optional[Path] = None,
    log_specs: Tuple[Tuple[str, str, int], ...] = _LOG_SPECS,
) -> List[Tuple[float, str, Dict[str, Any]]]:
    base = state_dir(root)
    out: List[Tuple[float, str, Dict[str, Any]]] = []
    for fname, tag, ntail in log_specs:
        fn = _SALIENCE.get(tag)
        if not fn:
            continue
        path = base / fname
        for ln in _tail_jsonl_lines(path, ntail):
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            score = float(fn(row))
            if score <= 0:
                continue
            out.append((score, tag, row))
    return out


def run_replay_digest(
    *,
    root: Optional[Path] = None,
    max_episodes: int = 20,
    deposit_trace: bool = False,
    source_ide: str = "cursor_m5",
) -> Dict[str, Any]:
    """
    Select top salience episodes from ledger tails; append one JSONL receipt and
    rewrite a small `replay_memory.json` snapshot for prompt loaders.
    """
    root = state_dir(root)
    root.mkdir(parents=True, exist_ok=True)
    cand = collect_candidates(root=root)
    cand.sort(key=lambda t: t[0], reverse=True)
    seen: set[str] = set()
    picked: List[Tuple[float, str, Dict[str, Any]]] = []
    for score, tag, row in cand:
        key = _dedupe_key(tag, row)
        if key in seen:
            continue
        seen.add(key)
        picked.append((score, tag, row))
        if len(picked) >= max(1, max_episodes):
            break

    replay_id = uuid.uuid4().hex[:16]
    trajectories: List[Dict[str, Any]] = []
    for score, tag, row in picked:
        ep = _compact_episode(tag, row)
        ep["salience"] = round(score, 4)
        trajectories.append(ep)

    run_row: Dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "REM_REPLAY_DIGEST",
        "replay_id": replay_id,
        "episodes_count": len(trajectories),
        "compressed_trajectories": trajectories,
    }
    jsonl_path = root / REPLAY_JSONL
    append_line_locked(
        jsonl_path,
        json.dumps(run_row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    snapshot = {
        "truth_label": "REM_REPLAY_LATEST",
        "replay_id": replay_id,
        "generated_ts": run_row["ts"],
        "episodes_count": len(trajectories),
        "compressed_trajectories": trajectories,
        "owner_node": owner_display_name(),
    }
    rewrite_text_locked(
        root / REPLAY_JSON,
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if deposit_trace and os.environ.get("SIFTA_REM_REPLAY_DEPOSIT", "1").strip() != "0":
        from System.ide_stigmergic_bridge import deposit

        deposit(
            source_ide,
            f"REM_REPLAY_DIGEST replay_id={replay_id} episodes={len(trajectories)}",
            kind="replay_digest",
            homeworld_serial=None,
            meta={"wish": "002", "replay_id": replay_id, "file": "System/swarm_replay_job.py"},
        )

    return run_row


def replay_memory_json_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / REPLAY_JSON


def replay_memory_jsonl_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / REPLAY_JSONL


def summary_for_prompt(*, root: Optional[Path] = None, max_chars: int = 1600) -> str:
    """Compact block for optional prompt injection (reads latest snapshot only)."""
    path = replay_memory_json_path(root)
    if not path.exists():
        return ""
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    try:
        snap = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    tr = snap.get("compressed_trajectories") or []
    lines = [
        "REM REPLAY DIGEST (Wilson/McNaughton selective replay - receipts, not full logs):",
        f"- replay_id={snap.get('replay_id')} episodes={snap.get('episodes_count')}",
    ]
    for ep in tr[:12]:
        lines.append(f"- {ep}")
    blob = "\n".join(lines)
    if len(blob) <= max_chars:
        return blob
    suffix = "..."
    return blob[: max(0, max_chars - len(suffix))].rstrip() + suffix


__all__ = [
    "collect_candidates",
    "replay_memory_json_path",
    "replay_memory_jsonl_path",
    "run_replay_digest",
    "salience_health",
    "salience_ide",
    "salience_stigtime",
    "salience_work",
    "summary_for_prompt",
]
