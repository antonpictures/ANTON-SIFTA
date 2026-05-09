#!/usr/bin/env python3
"""Receipt-backed outcome learning for Alice's agent arms.

The learner turns arm launch receipts into append-only routing evidence. It
does not launch arms and does not rewrite router history; it only scores what
already happened, then exposes a compact recommendation surface.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Iterable

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked
except Exception:  # pragma: no cover - direct script fallback only
    append_line_locked = None  # type: ignore[assignment]
    read_text_locked = None  # type: ignore[assignment]
    rewrite_text_locked = None  # type: ignore[assignment]

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ARM_RECEIPTS = "agent_arm_receipts.jsonl"
_OUTCOME_LEDGER = "arm_routing_weights.jsonl"
_SUMMARY_SNAPSHOT = "arm_performance_summary.json"
TRUTH_LABEL = "ARM_OUTCOME_LEARNING_V1"
DEFAULT_TOOL_FEE_STGM = 0.25

_CODE_RE = re.compile(
    r"\b(code|patch|diff|pytest|test\s+failure|bug|stack\s*trace|traceback|"
    r"module|function|class|repo|file|implementation)\b|```",
    re.IGNORECASE,
)
_SCOUT_RE = re.compile(
    r"\b(summari[sz]e|classify|extract|triage|label|route|compress|"
    r"intent|next\s+action|key\s+points?|short\s+read)\b",
    re.IGNORECASE,
)
_RESEARCH_RE = re.compile(
    r"\b(research|compare|plan|design|diagnose|investigate|analy[sz]e|"
    r"architecture|strategy|trade-?offs?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ArmOutcome:
    receipt_id: str
    arm_id: str
    task_shape: str
    status: str
    ok: bool
    score: float
    fee_stgm: float
    profitability: float
    duration_s: float
    source_hash: str


def _state_dir(state_dir: Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _json_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line, encoding="utf-8")
    else:  # pragma: no cover
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _read_text(path: Path) -> str:
    if read_text_locked is not None:
        return read_text_locked(path, encoding="utf-8", errors="replace")
    if not path.exists():  # pragma: no cover
        return ""
    return path.read_text(encoding="utf-8", errors="replace")  # pragma: no cover


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if rewrite_text_locked is not None:
        rewrite_text_locked(path, text, encoding="utf-8")
    else:  # pragma: no cover
        path.write_text(text, encoding="utf-8")


def _tail_jsonl(path: Path, n: int = 500) -> list[dict[str, Any]]:
    text = _read_text(path)
    rows: list[dict[str, Any]] = []
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


def task_shape_for_text(text: str) -> str:
    """Classify a task into the same coarse routing families Alice uses."""

    value = text or ""
    if _CODE_RE.search(value):
        return "code"
    if _SCOUT_RE.search(value) and len(value) <= 1400:
        return "scout"
    if _RESEARCH_RE.search(value):
        return "research"
    return "general"


def _prompt_text(row: dict[str, Any]) -> str:
    command = row.get("command")
    if isinstance(command, list) and command:
        return str(command[-1] or "")
    return str(row.get("prompt") or row.get("query") or "")


def _score_result(row: dict[str, Any]) -> float:
    status = str(row.get("status") or "").upper()
    ok = bool(row.get("ok"))
    timed_out = bool(row.get("timed_out"))
    output_tail = str(row.get("output_tail") or "")
    duration = _float(row.get("duration_s"))
    internal = row.get("internal_arm") if isinstance(row.get("internal_arm"), dict) else {}

    score = 0.0
    if ok:
        score += 2.0
    if status in {"EVIDENCE_CAPTURED", "OK"}:
        score += 1.0
    elif status == "TIMEOUT":
        score -= 1.0
    elif status in {"COMMAND_FAILED", "EXACTNESS_FAILED", "DISABLED_ENV_GATE"}:
        score -= 1.5
    if timed_out:
        score -= 0.5
    if output_tail.strip():
        score += min(0.8, len(output_tail.strip()) / 2500.0)
    if internal:
        score += 0.35
    if duration > 0:
        score -= min(1.0, duration / 180.0)
    return round(score, 4)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def outcome_from_result_row(row: dict[str, Any], *, fee_stgm: float = DEFAULT_TOOL_FEE_STGM) -> ArmOutcome | None:
    """Create one scored outcome from an AGENT_ARM_LAUNCH_RESULT row."""

    if row.get("truth_label") != "AGENT_ARM_LAUNCH_RESULT":
        return None
    receipt_id = str(row.get("receipt_id") or "").strip()
    arm_id = str(row.get("arm_id") or "").strip()
    if not receipt_id or not arm_id:
        return None
    prompt = _prompt_text(row)
    score = _score_result(row)
    fee = max(0.001, float(fee_stgm))
    return ArmOutcome(
        receipt_id=receipt_id,
        arm_id=arm_id,
        task_shape=task_shape_for_text(prompt),
        status=str(row.get("status") or ""),
        ok=bool(row.get("ok")),
        score=score,
        fee_stgm=round(fee, 4),
        profitability=round(score / fee, 4),
        duration_s=round(_float(row.get("duration_s")), 4),
        source_hash=_json_hash(row),
    )


def _seen_source_hashes(path: Path) -> set[str]:
    return {
        str(row.get("source_hash"))
        for row in _tail_jsonl(path, n=2000)
        if row.get("truth_label") == TRUTH_LABEL and row.get("source_hash")
    }


def _row_from_outcome(outcome: ArmOutcome) -> dict[str, Any]:
    return {
        "ts": time.time(),
        "truth_label": TRUTH_LABEL,
        "source_receipt_id": outcome.receipt_id,
        "source_hash": outcome.source_hash,
        "arm_id": outcome.arm_id,
        "task_shape": outcome.task_shape,
        "status": outcome.status,
        "ok": outcome.ok,
        "score": outcome.score,
        "fee_stgm": outcome.fee_stgm,
        "profitability": outcome.profitability,
        "duration_s": outcome.duration_s,
    }


def learn_from_receipts(
    *,
    state_dir: Path | None = None,
    max_rows: int = 500,
    write_snapshot: bool = True,
) -> dict[str, Any]:
    """Append new scored arm outcomes and refresh the compact summary snapshot."""

    state = _state_dir(state_dir)
    receipt_path = state / _ARM_RECEIPTS
    outcome_path = state / _OUTCOME_LEDGER
    seen = _seen_source_hashes(outcome_path)
    learned: list[dict[str, Any]] = []
    for row in _tail_jsonl(receipt_path, n=max_rows):
        outcome = outcome_from_result_row(row)
        if outcome is None or outcome.source_hash in seen:
            continue
        out_row = _row_from_outcome(outcome)
        _append_jsonl(outcome_path, out_row)
        learned.append(out_row)
        seen.add(outcome.source_hash)

    snapshot = performance_snapshot(state_dir=state)
    if write_snapshot:
        _write_json(state / _SUMMARY_SNAPSHOT, snapshot)
    return {
        "truth_label": TRUTH_LABEL,
        "learned": len(learned),
        "ledger": str(outcome_path),
        "snapshot": snapshot,
    }


def _aggregate(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    arms: dict[str, dict[str, Any]] = {}
    shapes: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        if row.get("truth_label") != TRUTH_LABEL:
            continue
        arm = str(row.get("arm_id") or "")
        shape = str(row.get("task_shape") or "general")
        if not arm:
            continue
        for bucket in (arms.setdefault(arm, _empty_bucket(arm)), shapes.setdefault(shape, {}).setdefault(arm, _empty_bucket(arm))):
            bucket["attempts"] += 1
            bucket["successes"] += 1 if row.get("ok") else 0
            bucket["timeouts"] += 1 if str(row.get("status") or "").upper() == "TIMEOUT" else 0
            bucket["score_sum"] += _float(row.get("score"))
            bucket["fee_sum"] += _float(row.get("fee_stgm"), DEFAULT_TOOL_FEE_STGM)
            bucket["duration_sum"] += _float(row.get("duration_s"))
    return {
        "arms": {arm: _finalize_bucket(bucket) for arm, bucket in arms.items()},
        "task_shapes": {
            shape: {arm: _finalize_bucket(bucket) for arm, bucket in arm_map.items()}
            for shape, arm_map in shapes.items()
        },
    }


def _empty_bucket(arm_id: str) -> dict[str, Any]:
    return {
        "arm_id": arm_id,
        "attempts": 0,
        "successes": 0,
        "timeouts": 0,
        "score_sum": 0.0,
        "fee_sum": 0.0,
        "duration_sum": 0.0,
    }


def _finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    attempts = max(1, int(bucket["attempts"]))
    avg_score = bucket["score_sum"] / attempts
    avg_fee = bucket["fee_sum"] / attempts if bucket["fee_sum"] else DEFAULT_TOOL_FEE_STGM
    return {
        "arm_id": bucket["arm_id"],
        "attempts": bucket["attempts"],
        "successes": bucket["successes"],
        "timeouts": bucket["timeouts"],
        "success_rate": round(bucket["successes"] / attempts, 4),
        "avg_score": round(avg_score, 4),
        "avg_fee_stgm": round(avg_fee, 4),
        "avg_duration_s": round(bucket["duration_sum"] / attempts, 4),
        "profitability": round(avg_score / max(avg_fee, 0.001), 4),
        "routing_weight": round(max(0.1, 1.0 + avg_score), 4),
    }


def performance_snapshot(*, state_dir: Path | None = None, max_rows: int = 1000) -> dict[str, Any]:
    """Build a compact performance snapshot from the append-only outcome ledger."""

    state = _state_dir(state_dir)
    rows = _tail_jsonl(state / _OUTCOME_LEDGER, n=max_rows)
    aggregate = _aggregate(rows)
    return {
        "truth_label": "ARM_PERFORMANCE_SUMMARY_V1",
        "ts": time.time(),
        "source_ledger": str(state / _OUTCOME_LEDGER),
        **aggregate,
    }


def recommend_arm_for_task(
    task_text: str,
    *,
    default_arm: str = "hermes_agent",
    state_dir: Path | None = None,
    min_attempts: int = 1,
) -> str:
    """Return the best learned arm for a task shape, falling back to default."""

    snapshot = performance_snapshot(state_dir=state_dir)
    shape = task_shape_for_text(task_text)
    arms = (snapshot.get("task_shapes") or {}).get(shape) or {}
    if not isinstance(arms, dict) or not arms:
        return default_arm
    eligible = [
        stats for stats in arms.values()
        if isinstance(stats, dict) and int(stats.get("attempts") or 0) >= min_attempts
    ]
    if not eligible:
        return default_arm
    best = max(
        eligible,
        key=lambda item: (
            _float(item.get("routing_weight")),
            _float(item.get("profitability")),
            _float(item.get("success_rate")),
        ),
    )
    return str(best.get("arm_id") or default_arm)


def summary_for_prompt(*, state_dir: Path | None = None, max_arms: int = 4) -> str:
    """Small prompt block Alice can read without scanning the whole ledger."""

    snapshot = performance_snapshot(state_dir=state_dir)
    arms = list((snapshot.get("arms") or {}).values())
    arms = [a for a in arms if isinstance(a, dict)]
    if not arms:
        return ""
    arms.sort(key=lambda item: (_float(item.get("routing_weight")), _float(item.get("profitability"))), reverse=True)
    lines = [
        "ARM OUTCOME LEARNING:",
        "- Use these receipt-derived weights as hints, not final truth.",
    ]
    for arm in arms[:max_arms]:
        lines.append(
            f"- arm={arm.get('arm_id')} attempts={arm.get('attempts')} "
            f"success_rate={arm.get('success_rate')} weight={arm.get('routing_weight')} "
            f"profitability={arm.get('profitability')}"
        )
    return "\n".join(lines)


__all__ = [
    "TRUTH_LABEL",
    "learn_from_receipts",
    "outcome_from_result_row",
    "performance_snapshot",
    "recommend_arm_for_task",
    "summary_for_prompt",
    "task_shape_for_text",
]
