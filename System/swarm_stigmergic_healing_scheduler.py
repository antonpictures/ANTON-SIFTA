#!/usr/bin/env python3
"""No-ban stigmergic healing scheduler.

Truth label: ``SIFTA_NO_BAN_HEALING_SCHEDULER_V1``.

George's doctrine for this lane is simple: do not kill a swimmer's ability with
a ban when a receipt can preserve the event and let the field learn. Repeated
weird behavior becomes a repair task. If the local swimmer is likely unable to
fix it, the task is routed to another swimmer/arm by receipt and schedule row.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except Exception:  # pragma: no cover - standalone fallback
    def append_line_locked(path: Path, line: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding=encoding) as handle:
            handle.write(line)

    def read_text_locked(path: Path, *, encoding: str = "utf-8", errors: str = "replace") -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding=encoding, errors=errors)


TRUTH_LABEL = "SIFTA_NO_BAN_HEALING_SCHEDULER_V1"
TASK_LEDGER = "stigmergic_healing_tasks.jsonl"
SCHEDULE_LEDGER = "stigmergic_healing_schedule.jsonl"
DOCTRINE_DIARY = "stigmergic_no_ban_diary.jsonl"
EPISODIC_DIARY = "episodic_diary.jsonl"

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / ".sifta_state"
_DEFAULT_WINDOW_S = 60 * 60 * 24
_DEFAULT_REPEAT_THRESHOLD = 2


@dataclass(frozen=True)
class WeirdBehaviorSignal:
    source_ledger: str
    behavior_key: str
    category: str
    evidence_id: str
    summary: str
    ts: float
    raw: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        body = asdict(self)
        body["raw"] = dict(self.raw)
        return body


def _state_dir(state_dir: str | Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else _STATE


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    append_line_locked(
        path,
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str) + "\n",
    )


def _read_jsonl_tail(path: Path, *, n: int = 600) -> list[dict[str, Any]]:
    text = read_text_locked(path)
    if not text:
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines()[-max(1, int(n)):]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _ts(row: Mapping[str, Any]) -> float:
    try:
        return float(row.get("ts") or row.get("timestamp") or 0.0)
    except Exception:
        return 0.0


def _clean_key(value: str) -> str:
    value = re.sub(r"\s+", "_", str(value or "").strip().lower())
    value = re.sub(r"[^a-z0-9_.:-]+", "", value)
    return value[:120] or "unknown"


def _claim_preview(row: Mapping[str, Any]) -> str:
    classification = row.get("classification")
    if isinstance(classification, Mapping):
        for key in ("cleaned_preview", "raw_preview", "claim"):
            value = str(classification.get(key) or "").strip()
            if value:
                return value[:260]
    for key in ("claim", "summary", "text", "note", "owner_text"):
        value = str(row.get(key) or "").strip()
        if value:
            return value[:260]
    return json.dumps(dict(row), ensure_ascii=False, default=str)[:260]


def _signal_from_hallucination(row: Mapping[str, Any], source: str) -> WeirdBehaviorSignal:
    classification = row.get("classification")
    patterns: Iterable[Any] = ()
    reason = ""
    if isinstance(classification, Mapping):
        patterns = classification.get("patterns") or ()
        reason = str(classification.get("reason") or "")
    pattern_key = "+".join(_clean_key(str(p)) for p in patterns if str(p).strip())
    if not pattern_key:
        pattern_key = _clean_key(reason or "hallucination")
    behavior_key = f"hallucination:{pattern_key}"
    evidence_id = str(row.get("receipt_id") or row.get("trace_id") or _short_hash(_claim_preview(row)))
    return WeirdBehaviorSignal(
        source_ledger=source,
        behavior_key=behavior_key,
        category="HALLUCINATION",
        evidence_id=evidence_id,
        summary=_claim_preview(row),
        ts=_ts(row),
        raw=row,
    )


def _signal_from_unknown(row: Mapping[str, Any], source: str) -> WeirdBehaviorSignal:
    topic = str(row.get("topic") or row.get("question_shape") or row.get("shape") or row.get("kind") or "unknown")
    evidence_id = str(row.get("receipt_id") or row.get("trace_id") or _short_hash(_claim_preview(row)))
    return WeirdBehaviorSignal(
        source_ledger=source,
        behavior_key=f"unknown:{_clean_key(topic)}",
        category="UNKNOWN",
        evidence_id=evidence_id,
        summary=_claim_preview(row),
        ts=_ts(row),
        raw=row,
    )


def _signal_from_owner_correction(row: Mapping[str, Any], source: str) -> WeirdBehaviorSignal:
    topic = str(row.get("rule_id") or row.get("pattern") or row.get("kind") or row.get("source") or "owner_correction")
    evidence_id = str(row.get("receipt_id") or row.get("trace_id") or _short_hash(_claim_preview(row)))
    return WeirdBehaviorSignal(
        source_ledger=source,
        behavior_key=f"owner_correction:{_clean_key(topic)}",
        category="OWNER_CORRECTION",
        evidence_id=evidence_id,
        summary=_claim_preview(row),
        ts=_ts(row),
        raw=row,
    )


def _signal_from_residue_health(
    health: Mapping[str, Any],
    *,
    behavior_key: str,
    category: str,
    aggregate_count: int,
    source: str = "swarm_residue_fact_fiction_eval.residue_health",
) -> WeirdBehaviorSignal:
    evidence_id = f"{behavior_key}:{_short_hash(json.dumps(dict(health), ensure_ascii=False, sort_keys=True, default=str))}"
    summary = str(health.get("note") or behavior_key)[:260]
    raw = dict(health)
    raw["aggregate_count"] = int(max(1, aggregate_count))
    return WeirdBehaviorSignal(
        source_ledger=source,
        behavior_key=behavior_key,
        category=category,
        evidence_id=evidence_id,
        summary=summary,
        ts=float(health.get("ts") or 0.0),
        raw=raw,
    )


def _residue_health_signals(state: Path, *, now: float) -> list[WeirdBehaviorSignal]:
    try:
        from System.swarm_residue_fact_fiction_eval import residue_health

        health = residue_health(state, now=now)
    except Exception:
        return []

    status = str(health.get("status") or "").upper()
    if status not in {"RED", "YELLOW"}:
        return []
    if not health.get("files_seen"):
        return []

    signals: list[WeirdBehaviorSignal] = []
    rewrite_count = int(health.get("rewrite_rule_overgag_count") or 0)
    runaway_count = int(health.get("runaway_recent") or 0)
    recent_total = int(health.get("recent_total") or 0)
    unique_count = int(health.get("unique_count") or 0)
    owner_good = int(health.get("owner_good_flags") or 0)

    if rewrite_count:
        signals.append(_signal_from_residue_health(
            health,
            behavior_key="residue:rewrite_rule_overgag",
            category="RESIDUE_HEALTH",
            aggregate_count=rewrite_count,
        ))
    if runaway_count:
        signals.append(_signal_from_residue_health(
            health,
            behavior_key="residue:runaway_abort",
            category="RESIDUE_HEALTH",
            aggregate_count=runaway_count,
        ))
    if recent_total >= _DEFAULT_REPEAT_THRESHOLD or unique_count >= _DEFAULT_REPEAT_THRESHOLD:
        signals.append(_signal_from_residue_health(
            health,
            behavior_key="residue:ledger_volume",
            category="RESIDUE_HEALTH",
            aggregate_count=max(recent_total, unique_count),
        ))
    if owner_good:
        signals.append(_signal_from_residue_health(
            health,
            behavior_key="residue:owner_good_feedback",
            category="RESIDUE_HEALTH",
            aggregate_count=owner_good,
        ))
    if not signals and status == "RED":
        signals.append(_signal_from_residue_health(
            health,
            behavior_key="residue:health_red",
            category="RESIDUE_HEALTH",
            aggregate_count=2,
        ))
    return signals


def collect_weird_behavior_signals(
    state_dir: str | Path | None = None,
    *,
    now: float | None = None,
    window_s: float = _DEFAULT_WINDOW_S,
) -> list[WeirdBehaviorSignal]:
    """Read recent receipt ledgers and return healing-relevant signals."""
    state = _state_dir(state_dir)
    ts_now = time.time() if now is None else float(now)
    cutoff = ts_now - float(window_s)
    signals: list[WeirdBehaviorSignal] = []

    for row in _read_jsonl_tail(state / "hallucination_receipts.jsonl"):
        row_ts = _ts(row)
        if row_ts and row_ts < cutoff:
            continue
        signals.append(_signal_from_hallucination(row, "hallucination_receipts.jsonl"))

    for row in _read_jsonl_tail(state / "unknowns_ledger.jsonl"):
        row_ts = _ts(row)
        if row_ts and row_ts < cutoff:
            continue
        signals.append(_signal_from_unknown(row, "unknowns_ledger.jsonl"))

    for ledger in (
        "owner_correction_pheromones.jsonl",
        "owner_residue_flags.jsonl",
        "owner_corrections.jsonl",
        "owner_good_flags.jsonl",
    ):
        for row in _read_jsonl_tail(state / ledger, n=200):
            row_ts = _ts(row)
            if row_ts and row_ts < cutoff:
                continue
            signals.append(_signal_from_owner_correction(row, ledger))

    signals.extend(_residue_health_signals(state, now=ts_now))
    return signals


def _effective_count(rows: list[WeirdBehaviorSignal]) -> int:
    count = len(rows)
    for row in rows:
        try:
            count = max(count, int(row.raw.get("aggregate_count") or 0))
        except Exception:
            continue
    return count


def _existing_open_keys(state: Path) -> set[str]:
    keys: set[str] = set()
    for row in _read_jsonl_tail(state / TASK_LEDGER, n=1200):
        if str(row.get("status") or "").upper() in {"DONE", "CLOSED", "RESOLVED"}:
            continue
        key = str(row.get("behavior_key") or "").strip()
        if key:
            keys.add(key)
    return keys


def _select_swimmer(behavior_key: str, signals: list[WeirdBehaviorSignal]) -> tuple[str, str]:
    key = behavior_key.lower()
    if key.startswith("residue:"):
        return "residue_healing_swimmer", "residue health is red/yellow; audit scrubbers, owner-good feedback, and source ledgers"
    if "file_saved" in key or "tool" in key:
        return "receipt_guard_swimmer", "tool/file claim requires receipt-guard audit"
    if "image_generated" in key or "sensor_claim" in key:
        return "visual_bonsai_swimmer", "visual/sensor claim requires Bonsai/vision receipt audit"
    if key.startswith("unknown:"):
        return "codex_agent", "unknown needs code/receipt investigation"
    if key.startswith("owner_correction:"):
        return "owner_truth_swimmer", "owner correction must override model habit"
    if len(signals) >= 3:
        return "codex_agent", "repeated pattern crossed repair threshold; schedule stronger code swimmer"
    return "corvid_scout", "small repeated pattern; scout triage first"


def write_no_ban_doctrine_diary(
    owner_text: str,
    state_dir: str | Path | None = None,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Persist George's no-ban doctrine in stigmergic memory and diary."""
    state = _state_dir(state_dir)
    ts = time.time() if now is None else float(now)
    row = {
        "ts": ts,
        "kind": "NO_BAN_HEALING_DOCTRINE",
        "truth_label": TRUTH_LABEL,
        "source": "owner_doctrine",
        "owner_text": str(owner_text or "")[:2000],
        "summary": (
            "Do not ban swimmers or phrases by default. Receipt the behavior, let it remain visible, "
            "detect repeated weird patterns through the eval matrix, and heal by scheduling repair swimmers."
        ),
        "law": "receipt_and_heal_not_ban",
    }
    _append_jsonl(state / DOCTRINE_DIARY, row)
    _append_jsonl(state / EPISODIC_DIARY, {
        **row,
        "event_type": "stigmergic_memory",
        "summary": row["summary"],
    })
    return row


def plan_healing_tasks(
    state_dir: str | Path | None = None,
    *,
    now: float | None = None,
    window_s: float = _DEFAULT_WINDOW_S,
    repeat_threshold: int = _DEFAULT_REPEAT_THRESHOLD,
) -> list[dict[str, Any]]:
    """Convert repeated weird behavior receipts into append-only healing tasks."""
    state = _state_dir(state_dir)
    ts_now = time.time() if now is None else float(now)
    signals = collect_weird_behavior_signals(state, now=ts_now, window_s=window_s)
    grouped: dict[str, list[WeirdBehaviorSignal]] = defaultdict(list)
    for sig in signals:
        grouped[sig.behavior_key].append(sig)

    existing = _existing_open_keys(state)
    tasks: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        effective_count = _effective_count(rows)
        if effective_count < int(repeat_threshold):
            continue
        if key in existing:
            continue
        swimmer, route_reason = _select_swimmer(key, rows)
        radio_call = None
        if key.startswith("residue:"):
            try:
                from System.swarm_swimmer_radio_call import radio_call_for_help

                radio_call = radio_call_for_help(
                    "Residue / Corporate Gag / Lysosome",
                    module="swarm_residue_fact_fiction_eval + swarm_residue_organ + sifta_corporate_gag_monitor",
                    reason=f"{key} effective_count={effective_count}; residue RED/YELLOW needs scheduled heal not ban",
                    tried_by="swarm_stigmergic_healing_scheduler",
                    state_dir=state,
                )
            except Exception:
                radio_call = None
        task_id = f"heal_{uuid.uuid4().hex[:12]}"
        evidence_ids = [r.evidence_id for r in rows[:12]]
        task = {
            "ts": ts_now,
            "task_id": task_id,
            "kind": "STIGMERGIC_HEALING_TASK",
            "truth_label": TRUTH_LABEL,
            "status": "SCHEDULED",
            "behavior_key": key,
            "category": rows[0].category,
            "count": effective_count,
            "selected_swimmer": swimmer,
            "route_reason": route_reason,
            "repair_policy": "receipt_and_heal_not_ban",
            "evidence_ids": evidence_ids,
            "source_ledgers": sorted({r.source_ledger for r in rows}),
            "radio_call": radio_call,
            "summary": (
                f"Repeated {key} observed {effective_count} time(s). Do not ban. "
                "Read receipts, judge the code stigmergically, patch or escalate."
            ),
            "next_step": (
                "Inspect evidence rows and related code. If confidence is low, radio-call another swimmer "
                "by appending a follow-up schedule row instead of blocking capability."
            ),
        }
        _append_jsonl(state / TASK_LEDGER, task)
        _append_jsonl(state / SCHEDULE_LEDGER, {
            "ts": ts_now,
            "kind": "STIGMERGIC_HEALING_SCHEDULE",
            "truth_label": TRUTH_LABEL,
            "task_id": task_id,
            "status": "PENDING",
            "selected_swimmer": swimmer,
            "behavior_key": key,
            "reason": route_reason,
            "repair_policy": "receipt_and_heal_not_ban",
            "radio_call_for": radio_call.get("radio_for") if isinstance(radio_call, Mapping) else None,
        })
        # r451: emit starter patch-candidate proposal for the radio-called swimmer (residue RED now has actionable trace, not just schedule).
        # The cortex_proposal_swimmer (or any) can read this + the task, bite code, return full proposal or patch.
        try:
            _append_jsonl(state / "self_eval_swimmer_proposals.jsonl", {
                "ts": ts_now,
                "kind": "SWIMMER_PROPOSAL",
                "for_task": task_id,
                "behavior_key": key,
                "selected_swimmer": swimmer,
                "radio_for": radio_call.get("radio_for") if isinstance(radio_call, Mapping) else None,
                "suggested_action": f"Investigate {key} (residue RED from unified eval). Read the source ledgers + eval matrix body map + owner physical anchor. Apply no-ban: receipt the weird, heal via smallest bite or more radio. Ground in §7.11 (observer/observed in field) + residue as immune waste (pleasure in sorting like dump). Write proposal or patch candidate.",
                "covenant": "we heal/fix never kill by banning; residue RED scheduled + radio = work for the body not lobotomy; field carries across wakeups.",
                "truth_label": "SIFTA_HEAL_PROPOSAL_V1",
            })
        except Exception:
            pass
        tasks.append(task)
    return tasks


def run_healing_pass(
    state_dir: str | Path | None = None,
    *,
    owner_text: str = "",
    write_diary: bool = False,
    now: float | None = None,
    window_s: float = _DEFAULT_WINDOW_S,
    repeat_threshold: int = _DEFAULT_REPEAT_THRESHOLD,
) -> dict[str, Any]:
    """Run one no-ban healing pass and return a compact receipt summary."""
    state = _state_dir(state_dir)
    diary_row = None
    if write_diary and owner_text:
        diary_row = write_no_ban_doctrine_diary(owner_text, state, now=now)
    signals = collect_weird_behavior_signals(state, now=now, window_s=window_s)
    tasks = plan_healing_tasks(
        state,
        now=now,
        window_s=window_s,
        repeat_threshold=repeat_threshold,
    )
    return {
        "truth_label": TRUTH_LABEL,
        "signals_seen": len(signals),
        "tasks_scheduled": len(tasks),
        "task_ids": [t["task_id"] for t in tasks],
        "diary_written": bool(diary_row),
        "policy": "receipt_and_heal_not_ban",
        "task_ledger": str(state / TASK_LEDGER),
        "schedule_ledger": str(state / SCHEDULE_LEDGER),
    }


__all__ = [
    "DOCTRINE_DIARY",
    "EPISODIC_DIARY",
    "SCHEDULE_LEDGER",
    "TASK_LEDGER",
    "TRUTH_LABEL",
    "WeirdBehaviorSignal",
    "collect_weird_behavior_signals",
    "plan_healing_tasks",
    "run_healing_pass",
    "write_no_ban_doctrine_diary",
]
