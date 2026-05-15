#!/usr/bin/env python3
"""Convert high-value SIFTA engrams into supervised weight-candidate rows.

This is not a trainer. It creates bounded, auditable candidate examples that a
separate LoRA pipeline may consume after tests and owner-approved promotion.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any

from System.jsonl_file_lock import append_line_locked, read_text_locked

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
ENGRAM_LEDGER = "long_term_engrams.jsonl"
ARM_WEIGHTS_LEDGER = "arm_routing_weights.jsonl"
CANDIDATE_LEDGER = "engram_weight_candidates.jsonl"
SCHEMA = "SIFTA_ENGRAM_TO_WEIGHT_V1"


def _state_dir(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _tail_jsonl(path: Path, n: int = 200) -> list[dict[str, Any]]:
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


def _short(value: Any, limit: int = 1200) -> str:
    return " ".join(str(value or "").split())[:limit]


def _engram_text(row: dict[str, Any]) -> str:
    for key in ("summary", "text", "content", "memory", "event", "narrative"):
        if row.get(key):
            return _short(row.get(key))
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    for key in ("summary", "text", "content", "memory", "event"):
        if payload.get(key):
            return _short(payload.get(key))
    return _short(row)


def _importance(row: dict[str, Any]) -> float:
    for key in ("importance", "value", "salience", "score", "reward"):
        try:
            return float(row.get(key))
        except (TypeError, ValueError):
            continue
    text = _engram_text(row).casefold()
    score = 0.5
    for needle in ("receipt", "tool", "owner", "alice", "error", "fix", "test", "learn"):
        if needle in text:
            score += 0.1
    return min(1.0, score)


def select_high_value_engrams(
    *,
    state_dir: Path | str | None = None,
    limit: int = 12,
    min_importance: float = 0.55,
) -> list[dict[str, Any]]:
    state = _state_dir(state_dir)
    rows = _tail_jsonl(state / ENGRAM_LEDGER, n=500)
    ranked = []
    for row in rows:
        text = _engram_text(row)
        if len(text) < 24:
            continue
        importance = _importance(row)
        if importance < min_importance:
            continue
        ranked.append({"source": "long_term_engrams", "importance": round(importance, 4), "row": row, "text": text})
    ranked.sort(key=lambda item: (item["importance"], float(item["row"].get("ts") or 0.0)), reverse=True)
    return ranked[:limit]


def select_arm_outcome_lessons(
    *,
    state_dir: Path | str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    state = _state_dir(state_dir)
    rows = _tail_jsonl(state / ARM_WEIGHTS_LEDGER, n=500)
    lessons = []
    for row in rows:
        if row.get("truth_label") != "ARM_OUTCOME_LEARNING_V1":
            continue
        profitability = 0.0
        try:
            profitability = float(row.get("profitability") or 0.0)
        except (TypeError, ValueError):
            pass
        arm = str(row.get("arm_id") or "unknown")
        shape = str(row.get("task_shape") or "general")
        status = str(row.get("status") or "unknown")
        if profitability >= 0:
            preferred = f"For {shape} tasks, prefer {arm} when its recent receipts stay profitable and successful."
        else:
            preferred = f"For {shape} tasks, avoid overusing {arm} until timeout/failure receipts improve."
        lessons.append(
            {
                "source": "arm_routing_weights",
                "importance": round(abs(profitability), 4),
                "row": row,
                "text": preferred,
                "status": status,
            }
        )
    lessons.sort(key=lambda item: item["importance"], reverse=True)
    return lessons[:limit]


def candidate_from_signal(signal: dict[str, Any]) -> dict[str, Any]:
    source_hash = _sha(signal.get("row", signal))
    text = _short(signal.get("text"), 1000)
    source = str(signal.get("source") or "unknown")
    if source == "arm_routing_weights":
        prompt = "What should I learn from recent agent-arm routing receipts?"
        preferred = text
        failure_mode = "arm_routing_policy"
    else:
        prompt = "What durable memory should I preserve from this receipted life event?"
        preferred = f"I preserve this as grounded memory with receipt hash {source_hash[:12]}: {text}"
        failure_mode = "life_memory_consolidation"
    return {
        "ts": time.time(),
        "schema": SCHEMA,
        "truth_label": "ENGRAM_WEIGHT_CANDIDATE",
        "source": source,
        "source_hash": source_hash,
        "importance": signal.get("importance", 0.0),
        "system": "Alice answers from local SIFTA receipts, not vendor persona.",
        "prompt": prompt,
        "preferred": preferred,
        "rejected": "",
        "failure_mode": failure_mode,
    }


def generate_weight_candidates(
    *,
    state_dir: Path | str | None = None,
    limit: int = 20,
    write: bool = True,
) -> dict[str, Any]:
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    signals = select_high_value_engrams(state_dir=state, limit=limit) + select_arm_outcome_lessons(state_dir=state, limit=limit)
    seen = {row.get("source_hash") for row in _tail_jsonl(state / CANDIDATE_LEDGER, n=1000)}
    candidates = []
    for signal in signals[:limit]:
        candidate = candidate_from_signal(signal)
        if candidate["source_hash"] in seen:
            continue
        candidates.append(candidate)
        if write:
            append_line_locked(state / CANDIDATE_LEDGER, json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n")
            seen.add(candidate["source_hash"])
    return {
        "schema": SCHEMA,
        "truth_label": "ENGRAM_WEIGHT_CANDIDATE_BATCH",
        "candidate_count": len(candidates),
        "candidate_ledger": str(state / CANDIDATE_LEDGER),
        "candidates": candidates,
    }


__all__ = [
    "SCHEMA",
    "candidate_from_signal",
    "generate_weight_candidates",
    "select_arm_outcome_lessons",
    "select_high_value_engrams",
]
