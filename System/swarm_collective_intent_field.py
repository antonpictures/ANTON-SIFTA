#!/usr/bin/env python3
"""
Event 109 — Collective Intent Field

Read recent organ / IDE / drive traces and emit one bounded swarm intent vector:
``consensus_drive``, ``conflict_pressure``, ``alignment_score``,
``next_collective_action``.

Truth label: ``COLLECTIVE_INTENT_FIELD``. Append-only ledger:
``.sifta_state/collective_intent_field.jsonl``.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_DEFAULT_STATE = _REPO / ".sifta_state"
_FIELD_NAME = "collective_intent_field.jsonl"
_TRUTH_LABEL = "COLLECTIVE_INTENT_FIELD"

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]


def _read_jsonl_tail(path: Path, n: int, *, max_chunk_bytes: int = 256_000) -> List[Dict[str, Any]]:
    """Last ``n`` JSON objects without loading unbounded multi-GB files."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    size = path.stat().st_size
    out: List[Dict[str, Any]] = []
    try:
        with open(path, "rb") as f:
            if size <= max_chunk_bytes:
                f.seek(0)
                chunk = f.read().decode("utf-8", errors="replace")
            else:
                f.seek(max(0, size - max_chunk_bytes))
                f.readline()
                chunk = f.read().decode("utf-8", errors="replace")
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        for line in lines[-n:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


def extract_signal(row: Dict[str, Any]) -> Optional[str]:
    """Best-effort token from heterogeneous ledger rows."""
    for key in (
        "selected_drive",
        "regulated_drive",
        "input_drive",
        "intent",
        "selected_action",
        "action",
        "payload",
        "kind",
    ):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower().split()[0]
    meta = row.get("meta")
    if isinstance(meta, dict):
        subject = meta.get("subject")
        if isinstance(subject, str) and subject.strip():
            return subject.strip().lower().split("_")[0]
    return None


def compute_collective_intent(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    root = Path(state_dir) if state_dir is not None else _DEFAULT_STATE
    trace = root / "ide_stigmergic_trace.jsonl"
    drives = root / "intrinsic_drive_receipts.jsonl"
    homeo = root / "homeostasis_actions.jsonl"
    policy = root / "motor_policy.jsonl"

    rows: List[Dict[str, Any]] = []
    rows += _read_jsonl_tail(trace, 40)
    rows += _read_jsonl_tail(drives, 20)
    rows += _read_jsonl_tail(homeo, 20)
    rows += _read_jsonl_tail(policy, 20)

    signals = [s for r in rows if (s := extract_signal(r))]
    counts = Counter(signals)
    total = sum(counts.values()) or 1
    if counts:
        top, top_n = counts.most_common(1)[0]
    else:
        top, top_n = "observe", 0

    alignment = top_n / total
    conflict = 1.0 - alignment

    if conflict > 0.65:
        collective_action = "quorum_review"
    elif top in {"repair", "rest", "red", "critical", "collapse"}:
        collective_action = "stabilize"
    elif top in {"explore", "learn", "research", "bio", "forage"}:
        collective_action = "forage_research"
    elif top in {"test", "pytest", "verify", "prove"}:
        collective_action = "prove"
    else:
        collective_action = "continue"

    return {
        "ts": time.time(),
        "truth_label": _TRUTH_LABEL,
        "window_rows": len(rows),
        "signals": dict(counts.most_common(12)),
        "consensus_drive": top,
        "alignment_score": round(alignment, 4),
        "conflict_pressure": round(conflict, 4),
        "next_collective_action": collective_action,
    }


def write_collective_intent(*, state_dir: Optional[Path] = None) -> Dict[str, Any]:
    root = Path(state_dir) if state_dir is not None else _DEFAULT_STATE
    root.mkdir(parents=True, exist_ok=True)
    row = compute_collective_intent(state_dir=root)
    path = root / _FIELD_NAME
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    return row


__all__ = [
    "TRUTH_LABEL",
    "compute_collective_intent",
    "extract_signal",
    "write_collective_intent",
]
