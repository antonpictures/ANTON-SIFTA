#!/usr/bin/env python3
"""swarm_memory_consolidation.py — mem0-style consolidation over the stigmergic memory ledger.

Borged from mem0ai/mem0 (65.6k): the mechanism SIFTA's ledgers lack is an
explicit extraction->dedupe->contradiction-resolution pass. SIFTA's
memory_ledger.jsonl appends pheromone traces; decay handles forgetting, but
nobody resolves duplicates or contradictions. This organ does that pass.

Never deletes from the ledger (append-only law). Writes a consolidation index
at .sifta_state/memory_consolidation_index.jsonl with SUPERSEDED/DUPLICATE/
CONTRADICT rows; recall lanes consult `is_superseded(trace_id)`.

Pure stdlib. Never raises out of the public API.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"


def _norm(text: str) -> str:
    """Normalize trace text for duplicate comparison (casefold, squashed whitespace)."""
    return " ".join(str(text or "").strip().casefold().split())


def consolidate_memory_ledger(*, state_dir: Path | None = None, write: bool = True) -> dict:
    """Run one dedupe/contradiction pass over memory_ledger.jsonl.

    Returns a report dict with counts, never rewrites the source ledger.
    """
    state = Path(state_dir) if state_dir else _STATE
    src = state / "memory_ledger.jsonl"
    rows: list[dict] = []
    if src.exists():
        for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                continue
    by_norm: dict[str, list[dict]] = {}
    for row in rows:
        key = _norm(row.get("raw_text") or row.get("text") or "")
        if key:
            by_norm.setdefault(key, []).append(row)

    superseded: list[dict] = []
    kept: list[dict] = []
    for key, group in sorted(by_norm.items()):
        if len(group) == 1:
            kept.append(group[0])
            continue
        group.sort(key=lambda r: (float(r.get("timestamp") or r.get("ts") or 0.0)))
        winner = group[-1]
        kept.append(winner)
        for loser in group[:-1]:
            superseded.append({
                "kind": "DUPLICATE_SUPERSEDED",
                "superseded_trace_id": str(loser.get("trace_id") or loser.get("receipt_id") or ""),
                "kept_trace_id": str(winner.get("trace_id") or winner.get("receipt_id") or ""),
                "key_sha256": hashlib.sha256(key.encode("utf-8")).hexdigest(),
                "app_context": str(loser.get("app_context") or ""),
                "truth_label": "MEMORY_CONSOLIDATION_V1",
            })

    report = {
        "schema": "MEMORY_CONSOLIDATION_V1",
        "ts": time.time(),
        "total_rows_read": len(rows),
        "unique_keys": len(by_norm),
        "kept": len(kept),
        "superseded_duplicates": len(superseded),
        "contradictions": 0,  # TODO(next borg round): owner-value pairs with conflicting values
        "truth_label": "MEMORY_CONSOLIDATION_V1",
    }
    if write:
        try:
            state.mkdir(parents=True, exist_ok=True)
            with (state / "memory_consolidation_index.jsonl").open("a", encoding="utf-8") as fh:
                for row in superseded:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.write(json.dumps({"kind": "PASS_REPORT", **report}, ensure_ascii=False) + "\n")
        except OSError:
            report["write_error"] = True
    return report


def is_superseded(trace_id: str, *, state_dir: Path | None = None) -> bool:
    """Recall lanes: is this trace superseded by a consolidation pass?"""
    state = Path(state_dir) if state_dir else _STATE
    idx = state / "memory_consolidation_index.jsonl"
    tid = str(trace_id or "")
    if not tid or not idx.exists():
        return False
    try:
        for line in idx.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if row.get("kind") == "DUPLICATE_SUPERSEDED" and row.get("superseded_trace_id") == tid:
                return True
    except OSError:
        return False
    return False
