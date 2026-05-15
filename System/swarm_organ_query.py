#!/usr/bin/env python3
"""Deterministic organ query map.

Alice and agent arms can ask "what organs can help with this?" and receive a
receipt-backed answer from ``organ_map.json`` instead of hallucinating tool
availability.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any

from System.jsonl_file_lock import append_line_locked
from System.swarm_organ_registry import load_organ_map, refresh_organ_registry

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
QUERY_LEDGER = "organ_query_receipts.jsonl"
QUERY_SCHEMA = "SIFTA_ORGAN_QUERY_V1"

_STOP = {
    "what", "which", "organ", "organs", "help", "with", "this", "that",
    "right", "now", "alice", "can", "use", "need", "needs", "for",
}


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-z][a-z0-9_]{2,}", (text or "").casefold())
        if t not in _STOP
    }


def _sha_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _haystack(organ: dict[str, Any]) -> set[str]:
    text = " ".join(
        [
            str(organ.get("organ_id") or ""),
            str(organ.get("module") or ""),
            " ".join(str(x) for x in organ.get("owned_ledgers") or []),
            " ".join(str(x) for x in organ.get("input_lanes") or []),
            " ".join(str(x) for x in organ.get("effector_surface") or []),
            " ".join(str(x) for x in organ.get("capabilities") or []),
        ]
    )
    return _tokens(text)


def query_organs(
    query: str,
    *,
    state_dir: Path | str | None = None,
    top_k: int = 5,
    refresh_if_missing: bool = True,
    write_receipt: bool = True,
) -> dict[str, Any]:
    """Return ranked organs for a task query and optionally receipt the query."""

    state = _state_dir(state_dir)
    snapshot = load_organ_map(state_dir=state)
    if refresh_if_missing and not snapshot:
        snapshot = refresh_organ_registry(state_dir=state)
    q_tokens = _tokens(query)
    matches: list[dict[str, Any]] = []
    for organ in snapshot.get("organs") or []:
        if not isinstance(organ, dict):
            continue
        overlap = q_tokens & _haystack(organ)
        lanes = set(str(x) for x in organ.get("input_lanes") or [])
        lane_bonus = len(q_tokens & lanes) * 1.5
        health_score = float((organ.get("health") or {}).get("score") or 0.0)
        score = len(overlap) + lane_bonus + health_score
        if score <= 0:
            continue
        matches.append(
            {
                "organ_id": organ.get("organ_id"),
                "module": organ.get("module"),
                "module_path": organ.get("module_path"),
                "score": round(score, 4),
                "matched_terms": sorted(overlap)[:12],
                "input_lanes": organ.get("input_lanes") or [],
                "owned_ledgers": organ.get("owned_ledgers") or [],
                "health": organ.get("health") or {},
                "effector_surface": organ.get("effector_surface") or [],
            }
        )
    matches.sort(key=lambda m: (float(m["score"]), str(m["organ_id"])), reverse=True)
    row = {
        "ts": time.time(),
        "schema": QUERY_SCHEMA,
        "truth_label": "ORGAN_QUERY_RESULT",
        "query_sha256": _sha_text(query),
        "query_terms": sorted(q_tokens),
        "organ_count": snapshot.get("organ_count", 0),
        "match_count": len(matches),
        "matches": matches[:top_k],
    }
    if write_receipt:
        state.mkdir(parents=True, exist_ok=True)
        append_line_locked(state / QUERY_LEDGER, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def summary_for_query(query: str, *, state_dir: Path | str | None = None, top_k: int = 5) -> str:
    row = query_organs(query, state_dir=state_dir, top_k=top_k)
    if not row["matches"]:
        return "ORGAN QUERY: no matching organs found in current registry."
    lines = ["ORGAN QUERY:"]
    for match in row["matches"]:
        lines.append(
            f"- {match.get('organ_id')} score={match.get('score')} "
            f"lanes={','.join(match.get('input_lanes') or [])} "
            f"health={(match.get('health') or {}).get('status')}"
        )
    return "\n".join(lines)


__all__ = ["QUERY_SCHEMA", "query_organs", "summary_for_query"]
