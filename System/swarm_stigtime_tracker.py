"""
Event 122 — Stigtime organ (action continuity / human-aware lane changes).

Append-only JSONL: who was doing what, when the lane changed, witnessed from
which surface. Complements message logs: the unit is an **action interval**
boundary, not a chat line.

Covenant: locked writes, no secrets in `context` — short hints only.
Kill-switch: `SIFTA_STIGTIME_DISABLE=1`.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_kernel_identity import owner_display_name, owner_silicon
from System.swarm_persistent_owner_history import state_dir

LOG_NAME = "stigtime_log.jsonl"
MAX_PROMPT_CONTEXT_CHARS = 90


def stigtime_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def log_action_boundary(
    *,
    actor: str,
    previous: str,
    new: str,
    witness: str = "sifta_talk_widget",
    context: str = "",
    root: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    One receipt when `new` materially differs from `previous`.
    Models STIGTIMEOUT(previous) + STIGTIMEIN(new) as a single locked row.
    """
    if os.environ.get("SIFTA_STIGTIME_DISABLE", "").strip() == "1":
        return None
    prev = (previous or "idle").strip() or "idle"
    nxt = (new or "").strip()
    if not nxt or prev == nxt:
        return None
    row: Dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "kind": "STIGTIME_BOUNDARY",
        "actor": actor[:120],
        "witness": witness[:120],
        "owner_label": owner_display_name(),
        "node_serial": owner_silicon(),
        "stigtime_out": prev,
        "stigtime_in": nxt,
        "context": (context or "")[:240],
    }
    append_line_locked(
        stigtime_log_path(root),
        json.dumps(row, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return row


def tail_stigtime_rows(
    max_lines: int = 24,
    *,
    root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Last N parsed rows (newest last), capped for prompt/dashboard use."""
    path = stigtime_log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    out: List[Dict[str, Any]] = []
    for ln in lines[-max(1, min(max_lines, 200)) :]:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _age_human(ts: Any, *, now: Optional[float] = None) -> str:
    try:
        age_s = max(0.0, float(now if now is not None else time.time()) - float(ts))
    except (TypeError, ValueError):
        return "unknown age"
    if age_s < 60:
        return f"{int(age_s)}s ago"
    if age_s < 3600:
        return f"{int(age_s // 60)}m ago"
    if age_s < 86400:
        return f"{int(age_s // 3600)}h ago"
    return f"{int(age_s // 86400)}d ago"


def _compact_context(text: Any, *, max_chars: int = MAX_PROMPT_CONTEXT_CHARS) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max(0, max_chars - 1)].rstrip() + "…"


def summary_for_alice(
    max_rows: int = 8,
    *,
    root: Optional[Path] = None,
    now: Optional[float] = None,
) -> str:
    """
    Compact prompt block for Alice's cortex.

    The rows are action-boundary receipts, not chat lines. They let Alice answer
    from recent body-time instead of claiming generic cloud amnesia.
    """
    rows = tail_stigtime_rows(max_rows, root=root)
    if not rows:
        return ""

    latest = rows[-1]
    owner = str(latest.get("owner_label") or owner_display_name()).strip() or "owner"
    serial = str(latest.get("node_serial") or owner_silicon()).strip() or "UNKNOWN"
    lines = [
        "STIGTIME ACTION CONTINUITY (append-only body-time receipts):",
        f"- owner={owner} node={serial} recent_boundaries={len(rows)}",
        "- Use this silently to remember recent action rhythm; do not say you lack past-24h memory when these receipts exist.",
    ]
    for row in rows:
        actor = _compact_context(row.get("actor"), max_chars=42) or "unknown"
        previous = _compact_context(row.get("stigtime_out"), max_chars=34) or "unknown"
        new = _compact_context(row.get("stigtime_in"), max_chars=34) or "unknown"
        context = _compact_context(row.get("context"), max_chars=MAX_PROMPT_CONTEXT_CHARS)
        age = _age_human(row.get("ts"), now=now)
        suffix = f" context={context}" if context else ""
        lines.append(f"- {age}: {actor} shifted {previous} -> {new}.{suffix}")
    return "\n".join(lines)


__all__ = [
    "log_action_boundary",
    "stigtime_log_path",
    "summary_for_alice",
    "tail_stigtime_rows",
]
