#!/usr/bin/env python3
"""Guarded local self-improvement consolidation loop.

This organ closes the missing path from lived receipts to weight-candidate
training rows. It deliberately stops before training or promotion unless future
receipts prove a candidate cortex exists and passes gates.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_engram_to_weight import generate_weight_candidates

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
CONSOLIDATION_LEDGER = "weight_consolidation_receipt.jsonl"
PROMOTION_LEDGER = "weight_promotion_decisions.jsonl"
SCHEMA = "SIFTA_WEIGHT_CONSOLIDATOR_V1"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tail_jsonl(path: Path, n: int = 100) -> list[dict[str, Any]]:
    try:
        text = read_text_locked(path, encoding="utf-8", errors="replace")
    except Exception:
        return []
    rows = []
    for line in text.splitlines()[-n:]:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _promotion_gate(
    *,
    state: Path,
    candidate_model_path: Path | str | None,
    min_candidates: int,
    candidate_count: int,
) -> dict[str, Any]:
    blockers = []
    model_hash = ""
    model_path = Path(candidate_model_path) if candidate_model_path else None
    if candidate_count < min_candidates:
        blockers.append(f"not_enough_weight_candidates:{candidate_count}/{min_candidates}")
    if model_path is None:
        blockers.append("no_candidate_cortex_path")
    elif not model_path.exists():
        blockers.append("candidate_cortex_missing")
    else:
        model_hash = _sha_file(model_path)

    # Reuse the runtime receipt gate if available; it may add stricter blockers.
    runtime_summary: dict[str, Any] = {}
    try:
        from System.swarm_lora_runtime_receipt import promotion_decision

        runtime_summary = promotion_decision()
        if not runtime_summary.get("promote"):
            blockers.append("lora_runtime_gate_not_green")
    except Exception as exc:
        runtime_summary = {"error": f"{type(exc).__name__}: {exc}"}
        blockers.append("lora_runtime_gate_unavailable")

    return {
        "promote": not blockers,
        "blockers": blockers,
        "candidate_model_path": str(model_path) if model_path else "",
        "candidate_model_sha256": model_hash,
        "runtime_gate": runtime_summary,
        "state_dir": str(state),
    }


def run_consolidation_cycle(
    *,
    state_dir: Path | str | None = None,
    candidate_model_path: Path | str | None = None,
    min_candidates_for_promotion: int = 20,
    limit: int = 32,
    now: float | None = None,
) -> dict[str, Any]:
    """Generate candidate rows and append consolidation + promotion receipts."""

    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    ts = time.time() if now is None else float(now)
    batch = generate_weight_candidates(state_dir=state, limit=limit, write=True)
    candidate_count = int(batch.get("candidate_count") or 0)
    gate = _promotion_gate(
        state=state,
        candidate_model_path=candidate_model_path,
        min_candidates=min_candidates_for_promotion,
        candidate_count=candidate_count,
    )
    receipt = {
        "ts": ts,
        "schema": SCHEMA,
        "truth_label": "WEIGHT_CONSOLIDATION_RECEIPT",
        "candidate_count": candidate_count,
        "candidate_ledger": batch.get("candidate_ledger"),
        "promotion_allowed": bool(gate["promote"]),
        "promotion_blockers": gate["blockers"],
    }
    append_line_locked(state / CONSOLIDATION_LEDGER, json.dumps(receipt, ensure_ascii=False, sort_keys=True) + "\n")

    decision = {
        "ts": ts,
        "schema": SCHEMA,
        "truth_label": "WEIGHT_PROMOTION_DECISION",
        "decision": "PROMOTE" if gate["promote"] else "DO_NOT_PROMOTE",
        **gate,
    }
    append_line_locked(state / PROMOTION_LEDGER, json.dumps(decision, ensure_ascii=False, sort_keys=True) + "\n")
    return {"receipt": receipt, "promotion": decision, "batch": batch}


def latest_consolidation_summary(*, state_dir: Path | str | None = None) -> dict[str, Any]:
    state = _state_dir(state_dir)
    rows = _tail_jsonl(state / CONSOLIDATION_LEDGER, n=1)
    decisions = _tail_jsonl(state / PROMOTION_LEDGER, n=1)
    return {
        "latest_receipt": rows[-1] if rows else {},
        "latest_promotion": decisions[-1] if decisions else {},
    }


def summary_for_prompt(*, state_dir: Path | str | None = None) -> str:
    summary = latest_consolidation_summary(state_dir=state_dir)
    receipt = summary["latest_receipt"]
    decision = summary["latest_promotion"]
    if not receipt:
        return ""
    return (
        "WEIGHT CONSOLIDATION:\n"
        f"- candidates={receipt.get('candidate_count')} ledger={receipt.get('candidate_ledger')}\n"
        f"- promotion_decision={decision.get('decision')} blockers={', '.join(decision.get('blockers') or []) or 'none'}"
    )


__all__ = ["SCHEMA", "latest_consolidation_summary", "run_consolidation_cycle", "summary_for_prompt"]
