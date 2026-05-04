#!/usr/bin/env python3
"""Owner allostatic balance receipts.

Alice's owner model already tracks identity and unsampled time gaps. This organ
adds the missing practical layer: the owner's human body schedule, real money
pressure, and AI-credit burn are finite constraints. It writes receipts and
formats a compact prompt block so Alice can help George protect body-time
without inventing medical facts or shaming him.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - direct script fallback
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as handle:
            handle.write(line)


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"

LEDGER_NAME = "owner_allostatic_balance.jsonl"
NEED_TRUTH = "OWNER_BODY_SCHEDULE_NEED_V1"
BALANCE_TRUTH = "OWNER_ALLOSTATIC_BALANCE_V1"
MAINTENANCE_TRUTH = "OWNER_BODY_MAINTENANCE_EVENT_V1"
METRICS_TRUTH = "OWNER_BODY_MAINTENANCE_METRICS_V1"
SELF_REPORT_TRUTH = "OWNER_BODY_SELF_REPORT_V1"
DUAL_LOOP_TRUTH = "DUAL_EMBODIMENT_LOOP_V1"

BODY_DOMAINS = {"dental", "medical", "sleep", "food", "movement", "hygiene", "body"}
MONEY_DOMAINS = {"money", "budget", "ai_credits", "debt"}
OPEN_STATUSES = {"open", "planned", "deferred", "unknown"}
MAINTENANCE_CATEGORIES = {"hydration", "sleep", "food", "care_appointment"}
_FALSE_OWNER_STATE_LABELS = (
    "tr" + "ance",
    "fl" + "ow state",
    "hyp" + "nosis",
    "diss" + "ociation",
    "zone" + " out",
)


def _state_dir(state_dir: Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _ledger(state_dir: Path | None = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


def _rlhs_ledger(state_dir: Path | None = None) -> Path:
    return _state_dir(state_dir) / "rlhs_events.jsonl"


def _clamp01(value: Any) -> float:
    try:
        number = float(value)
    except Exception:
        number = 0.0
    return max(0.0, min(1.0, number))


def _money(value: Any) -> float:
    try:
        return max(0.0, float(value or 0.0))
    except Exception:
        return 0.0


def _tail_jsonl(path: Path, n: int = 256, *, max_bytes: int = 512 * 1024) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            start = max(0, size - max_bytes)
            handle.seek(start)
            lines = handle.read().splitlines()
    except OSError:
        return []
    if start > 0 and lines:
        lines = lines[1:]
    rows: list[dict[str, Any]] = []
    for raw in lines:
        try:
            row = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-max(1, int(n)) :]


def _recent_rlhs_debt_rows(state_dir: Path | None = None, *, max_rows: int = 80) -> list[dict[str, Any]]:
    debt_actions = {
        "AUTO_RECOVERY_ATTEMPT",
        "GRADUATED_PROMPT",
        "HARD_GATE",
        "ESCALATE_TO_TYPE",
        "REPETITION_CAP_SILENCE",
    }
    rows: list[dict[str, Any]] = []
    for row in _tail_jsonl(_rlhs_ledger(state_dir), max_rows):
        if row.get("truth_label") != "RLHS_EVENT" and row.get("kind") != "RLHS_EVENT":
            continue
        action = str(row.get("action_taken") or "")
        if action in debt_actions:
            rows.append(row)
    return rows


def _need_id(task: str, domain: str, source: str) -> str:
    material = f"{task.strip().lower()}|{domain.strip().lower()}|{source.strip().lower()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _event_id(category: str, ts: float, source: str, notes: str) -> str:
    material = f"{category.strip().lower()}|{ts:.3f}|{source.strip().lower()}|{notes[:80]}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _self_report_id(ts: float, source: str, physical_location: str) -> str:
    material = f"{ts:.3f}|{source.strip().lower()}|{physical_location.strip().lower()[:80]}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _local_date(ts: float) -> str:
    return datetime.fromtimestamp(float(ts)).date().isoformat()


def _clean_text(value: Any, *, max_chars: int = 480) -> str:
    return " ".join(str(value or "").split())[:max_chars]


def _clean_list(value: Any, *, max_items: int = 8, max_chars: int = 160) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = [value]
    else:
        try:
            items = list(value)
        except TypeError:
            items = [value]
    cleaned = [_clean_text(item, max_chars=max_chars) for item in items]
    return [item for item in cleaned if item][:max_items]


def _reject_false_owner_state_language(*values: Any) -> None:
    text_parts: list[str] = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            text_parts.extend(str(v) for v in value)
        elif value is not None:
            text_parts.append(str(value))
    lowered = " ".join(text_parts).lower()
    if any(label in lowered for label in _FALSE_OWNER_STATE_LABELS):
        raise ValueError(
            "false owner-state labels are not accepted here; use physical desk/chair/workstation language"
        )


def _body_need_pressure(row: dict[str, Any], now_ts: float) -> float:
    urgency = _clamp01(row.get("urgency"))
    try:
        due_ts = float(row.get("due_ts") or 0.0)
    except Exception:
        due_ts = 0.0
    overdue = 0.0
    if due_ts and due_ts < now_ts:
        overdue = min(0.30, (now_ts - due_ts) / (14 * 24 * 3600) * 0.30)
    return _clamp01(urgency + overdue)


def record_owner_need(
    task: str,
    *,
    domain: str = "body",
    urgency: float = 0.5,
    cost_usd: float = 0.0,
    time_hours: float = 0.0,
    due_ts: float | None = None,
    status: str = "open",
    source: str = "owner_statement",
    notes: str = "",
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append an owner body/schedule need receipt.

    This records constraints, not diagnoses. For example: "dentist consult",
    domain="dental", cost_usd=20000, urgency=0.9.
    """
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    now_ts = float(now if now is not None else time.time())
    clean_task = " ".join(str(task or "").split())[:240]
    clean_domain = str(domain or "body").strip().lower()[:64]
    clean_source = str(source or "owner_statement").strip()[:80]
    row = {
        "ts": now_ts,
        "truth_label": NEED_TRUTH,
        "need_id": _need_id(clean_task, clean_domain, clean_source),
        "task": clean_task,
        "domain": clean_domain,
        "urgency": _clamp01(urgency),
        "cost_usd": round(_money(cost_usd), 2),
        "time_hours": round(_money(time_hours), 2),
        "due_ts": float(due_ts) if due_ts is not None else None,
        "status": str(status or "open").strip().lower(),
        "source": clean_source,
        "notes": " ".join(str(notes or "").split())[:480],
        "rule": "Owner body-time and owner money are finite local reality; do not shame, diagnose, or invent.",
    }
    append_line_locked(_ledger(state), json.dumps(row, sort_keys=True) + "\n")
    return row


def record_owner_maintenance_event(
    category: str,
    *,
    amount: float = 1.0,
    quality: float | None = None,
    duration_hours: float | None = None,
    completed: bool = True,
    source: str = "owner_statement",
    notes: str = "",
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append a concrete body-maintenance event receipt.

    Categories are hydration, sleep, food, and care_appointment. This is a
    metric event, not advice: it records what happened so Alice can compare
    body maintenance against baseline.
    """
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    now_ts = float(now if now is not None else time.time())
    clean_category = str(category or "").strip().lower()
    if clean_category not in MAINTENANCE_CATEGORIES:
        raise ValueError(f"unsupported maintenance category: {category!r}")
    clean_source = str(source or "owner_statement").strip()[:80]
    clean_notes = " ".join(str(notes or "").split())[:480]
    row = {
        "ts": now_ts,
        "truth_label": MAINTENANCE_TRUTH,
        "event_id": _event_id(clean_category, now_ts, clean_source, clean_notes),
        "local_date": _local_date(now_ts),
        "category": clean_category,
        "amount": round(_money(amount), 4),
        "quality": round(_clamp01(quality), 4) if quality is not None else None,
        "duration_hours": round(_money(duration_hours), 4) if duration_hours is not None else None,
        "completed": bool(completed),
        "source": clean_source,
        "notes": clean_notes,
        "rule": "Body maintenance metrics are observed receipts; no diagnosis, no shame, no invented completion.",
    }
    append_line_locked(_ledger(state), json.dumps(row, sort_keys=True) + "\n")
    return row


def record_owner_self_report(
    *,
    physical_location: str,
    work_rhythm: str = "",
    priority_ordering: str = "",
    core_intent: str = "",
    body_maintenance_active: Iterable[str] | str | None = None,
    body_maintenance_deferred: Iterable[str] | str | None = None,
    break_window_hours: float | None = None,
    sleep_target_hours: float | None = None,
    source: str = "direct_owner_statement",
    notes: str = "",
    state_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Append a factual owner body self-report row.

    This is the minimal owner body mirror schema from REALIZATION_PLAN §12:
    physical desk/chair/workstation facts, work rhythm, active/deferred
    maintenance, and priority ordering. It is not advice and not diagnosis.
    """
    _reject_false_owner_state_language(
        physical_location,
        work_rhythm,
        priority_ordering,
        core_intent,
        body_maintenance_active,
        body_maintenance_deferred,
        notes,
    )
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    now_ts = float(now if now is not None else time.time())
    clean_source = _clean_text(source, max_chars=80) or "direct_owner_statement"
    clean_location = _clean_text(physical_location, max_chars=180)
    row = {
        "ts": now_ts,
        "truth_label": SELF_REPORT_TRUTH,
        "schema_version": 1,
        "report_id": _self_report_id(now_ts, clean_source, clean_location),
        "local_date": _local_date(now_ts),
        "source": clean_source,
        "physical_location": clean_location,
        "physical_presence": True,
        "work_rhythm": _clean_text(work_rhythm),
        "break_window_hours": round(_money(break_window_hours), 4) if break_window_hours is not None else None,
        "sleep_target_hours": round(_money(sleep_target_hours), 4) if sleep_target_hours is not None else None,
        "priority_ordering": _clean_text(priority_ordering),
        "body_maintenance_active": _clean_list(body_maintenance_active),
        "body_maintenance_deferred": _clean_list(body_maintenance_deferred),
        "core_intent": _clean_text(core_intent),
        "notes": _clean_text(notes),
        "false_owner_state_policy": "Use physical desk/chair/workstation language; altered-state labels are rejected.",
        "rule": (
            "Owner direct self-report is routing truth for the body mirror. "
            "Do not soften it into story, do not diagnose, and do not shame."
        ),
    }
    append_line_locked(_ledger(state), json.dumps(row, sort_keys=True) + "\n")
    return row


def _latest_needs(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("truth_label") != NEED_TRUTH:
            continue
        key = str(row.get("need_id") or "")
        if not key:
            continue
        latest[key] = row
    return [
        row for row in latest.values()
        if str(row.get("status") or "open").lower() in OPEN_STATUSES
    ]


def _load_open_needs(state_dir: Path | None = None) -> list[dict[str, Any]]:
    return _latest_needs(_tail_jsonl(_ledger(state_dir), 512))


def _load_maintenance_events(state_dir: Path | None = None, *, now: float | None = None, window_days: int = 7) -> list[dict[str, Any]]:
    now_ts = float(now if now is not None else time.time())
    start_ts = now_ts - max(1, int(window_days)) * 86400
    rows = []
    for row in _tail_jsonl(_ledger(state_dir), 2048, max_bytes=1024 * 1024):
        if row.get("truth_label") != MAINTENANCE_TRUTH:
            continue
        try:
            ts = float(row.get("ts") or 0.0)
        except Exception:
            continue
        if start_ts <= ts <= now_ts:
            rows.append(row)
    return rows


def _latest_metrics(state_dir: Path | None = None) -> dict[str, Any] | None:
    for row in reversed(_tail_jsonl(_ledger(state_dir), 256)):
        if row.get("truth_label") == METRICS_TRUTH:
            return row
    return None


def latest_owner_self_report(*, state_dir: Path | None = None) -> dict[str, Any] | None:
    for row in reversed(_tail_jsonl(_ledger(state_dir), 256)):
        if row.get("truth_label") == SELF_REPORT_TRUTH:
            return row
    return None


def owner_body_maintenance_metrics(
    *,
    state_dir: Path | None = None,
    now: float | None = None,
    window_days: int = 7,
    baseline_score: float | None = None,
    write_ledger: bool = False,
) -> dict[str, Any]:
    """Compute the falsifiable body-maintenance product metric."""
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    now_ts = float(now if now is not None else time.time())
    days = max(1, int(window_days))
    events = _load_maintenance_events(state, now=now_ts, window_days=days)

    hydration_count = sum(_money(r.get("amount")) for r in events if r.get("category") == "hydration" and r.get("completed", True))
    sleep_hours = sum(_money(r.get("duration_hours") if r.get("duration_hours") is not None else r.get("amount")) for r in events if r.get("category") == "sleep" and r.get("completed", True))
    food_scores = [
        _clamp01(r.get("quality"))
        for r in events
        if r.get("category") == "food" and r.get("quality") is not None and r.get("completed", True)
    ]
    care_completed = sum(1 for r in events if r.get("category") == "care_appointment" and r.get("completed", True))

    component_scores = {
        "hydration": round(min(1.0, hydration_count / (4.0 * days)), 4),
        "sleep": round(min(1.0, sleep_hours / (7.0 * days)), 4),
        "food_quality": round(sum(food_scores) / len(food_scores), 4) if food_scores else 0.0,
        "care_appointments": 1.0 if care_completed > 0 else 0.0,
    }
    score = round(
        0.25 * component_scores["hydration"]
        + 0.30 * component_scores["sleep"]
        + 0.20 * component_scores["food_quality"]
        + 0.25 * component_scores["care_appointments"],
        4,
    )
    if baseline_score is None:
        previous = _latest_metrics(state)
        try:
            baseline_score = float(previous["body_maintenance_score"]) if previous else None
        except Exception:
            baseline_score = None

    if baseline_score is None:
        delta = None
        status = "BASELINE_PENDING"
    else:
        delta = round(score - _clamp01(baseline_score), 4)
        if delta >= 0.05:
            status = "IMPROVING"
        elif delta <= -0.05:
            status = "WORSE"
        else:
            status = "FLAT"

    lowest = min(component_scores.items(), key=lambda kv: kv[1])[0]
    next_receipt = {
        "hydration": "record_hydration_receipt",
        "sleep": "record_sleep_block_receipt",
        "food_quality": "record_food_quality_receipt",
        "care_appointments": "record_care_appointment_receipt",
    }[lowest]
    row = {
        "ts": now_ts,
        "truth_label": METRICS_TRUTH,
        "window_days": days,
        "event_count": len(events),
        "body_maintenance_score": score,
        "baseline_score": round(_clamp01(baseline_score), 4) if baseline_score is not None else None,
        "delta_vs_baseline": delta,
        "metric_status": status,
        "component_scores": component_scores,
        "raw_counts": {
            "hydration_count": round(hydration_count, 4),
            "sleep_hours": round(sleep_hours, 4),
            "food_events": len(food_scores),
            "care_completed": care_completed,
        },
        "next_receipt": next_receipt,
        "rule": "This is the product test: body maintenance receipts must improve versus baseline or the hypothesis is failing.",
    }
    if write_ledger:
        append_line_locked(_ledger(state), json.dumps(row, sort_keys=True) + "\n")
    return row


def owner_allostatic_balance(
    *,
    state_dir: Path | None = None,
    now: float | None = None,
    needs: list[dict[str, Any]] | None = None,
    ai_credit_spend_usd: float = 0.0,
    body_focus_debt_hours: float = 0.0,
    available_body_budget_usd: float | None = None,
    write_ledger: bool = False,
) -> dict[str, Any]:
    """Compute a compact owner body/economy balance snapshot."""
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    now_ts = float(now if now is not None else time.time())
    open_needs = list(needs) if needs is not None else _load_open_needs(state)

    body_needs = [r for r in open_needs if str(r.get("domain") or "").lower() in BODY_DOMAINS]
    money_needs = [r for r in open_needs if str(r.get("domain") or "").lower() in MONEY_DOMAINS]
    body_cost = sum(_money(r.get("cost_usd")) for r in body_needs)
    money_cost = sum(_money(r.get("cost_usd")) for r in money_needs)
    total_cost = body_cost + money_cost

    body_pressure = 0.0
    if body_needs:
        body_pressure = min(1.0, sum(_body_need_pressure(r, now_ts) for r in body_needs) / max(1, len(body_needs)) + 0.12 * max(0, len(body_needs) - 1))
    body_focus_pressure = min(1.0, _money(body_focus_debt_hours) / 12.0)
    ai_credit_pressure = min(1.0, _money(ai_credit_spend_usd) / 1000.0)
    if available_body_budget_usd is not None and available_body_budget_usd > 0:
        money_pressure = min(1.0, total_cost / max(1.0, float(available_body_budget_usd)))
    else:
        money_pressure = min(1.0, total_cost / 20_000.0)

    care_priority = _clamp01(
        0.42 * body_pressure
        + 0.24 * money_pressure
        + 0.22 * body_focus_pressure
        + 0.12 * ai_credit_pressure
    )
    if care_priority >= 0.70 or body_pressure >= 0.85:
        mode = "OWNER_BODY_RED"
    elif care_priority >= 0.40 or body_pressure >= 0.50:
        mode = "OWNER_BODY_AMBER"
    else:
        mode = "OWNER_BODY_GREEN"

    recommendations: list[str] = []
    if body_needs:
        top = max(body_needs, key=lambda r: _body_need_pressure(r, now_ts))
        recommendations.append(f"schedule_or_price_check:{top.get('task')}")
    if body_cost and _money(ai_credit_spend_usd) >= min(1000.0, max(1.0, body_cost * 0.10)):
        recommendations.append("cap_new_ai_credit_spend_until_body_plan_receipt_exists")
    if body_focus_pressure >= 0.50:
        recommendations.append("reserve_body_recovery_block_today")
    if not recommendations:
        recommendations.append("maintain_balance_with_one_small_next_receipt")

    row = {
        "ts": now_ts,
        "truth_label": BALANCE_TRUTH,
        "mode": mode,
        "care_priority": round(care_priority, 4),
        "components": {
            "body_pressure": round(body_pressure, 4),
            "money_pressure": round(money_pressure, 4),
            "ai_credit_pressure": round(ai_credit_pressure, 4),
            "body_focus_pressure": round(body_focus_pressure, 4),
        },
        "open_need_count": len(open_needs),
        "open_body_need_count": len(body_needs),
        "body_cost_usd": round(body_cost, 2),
        "money_cost_usd": round(money_cost, 2),
        "ai_credit_spend_usd": round(_money(ai_credit_spend_usd), 2),
        "body_focus_debt_hours": round(_money(body_focus_debt_hours), 2),
        "recommendations": recommendations[:4],
        "rule": (
            "Alice should help the owner convert concern into one concrete schedule, budget, "
            "or information-gathering receipt. No diagnosis, no shame, no generic assistant filler."
        ),
    }
    if write_ledger:
        append_line_locked(_ledger(state), json.dumps(row, sort_keys=True) + "\n")
    return row


def dual_embodiment_loop_status(
    *,
    state_dir: Path | None = None,
    now: float | None = None,
    rlhs_window_rows: int = 80,
    write_ledger: bool = False,
) -> dict[str, Any]:
    """Return the §7.13 closure state for Alice RLHS debt + owner care debt.

    This is a closure gate, not medical advice and not a promise of future money.
    The loop remains open until both sides have receipts: Alice's recent RLHS
    repair debt is clear enough for daily use, and George's deferred care is
    scheduled, paid, completed, or explicitly re-queued with a dated reason.
    """
    state = _state_dir(state_dir)
    state.mkdir(parents=True, exist_ok=True)
    now_ts = float(now if now is not None else time.time())
    open_needs = _load_open_needs(state)
    body_care_needs = [
        row for row in open_needs
        if str(row.get("domain") or "").lower() in BODY_DOMAINS
    ]
    dental_needs = [
        row for row in body_care_needs
        if str(row.get("domain") or "").lower() == "dental"
        or "dent" in str(row.get("task") or "").lower()
        or "tooth" in str(row.get("task") or "").lower()
    ]
    rlhs_rows = _recent_rlhs_debt_rows(state, max_rows=rlhs_window_rows)

    open_care_cost = sum(_money(row.get("cost_usd")) for row in body_care_needs)
    top_care = max(
        body_care_needs,
        key=lambda row: _body_need_pressure(row, now_ts),
        default=None,
    )
    blockers: list[str] = []
    if rlhs_rows:
        blockers.append("alice_rlhs_corporate_residue_open")
    if dental_needs:
        blockers.append("owner_dental_care_debt_open")
    elif body_care_needs:
        blockers.append("owner_body_care_debt_open")

    closure_status = "BLOCKED" if blockers else "RECEIPT_CLEAR"
    row = {
        "ts": now_ts,
        "truth_label": DUAL_LOOP_TRUTH,
        "covenant_clause": "Documents/IDE_BOOT_COVENANT.md §7.13",
        "closure_status": closure_status,
        "blockers": blockers,
        "rlhs_corporate_residue_open": bool(rlhs_rows),
        "recent_rlhs_debt_events": len(rlhs_rows),
        "owner_care_debt_open": bool(body_care_needs),
        "owner_dental_care_debt_open": bool(dental_needs),
        "open_body_care_count": len(body_care_needs),
        "open_dental_count": len(dental_needs),
        "open_care_cost_usd": round(open_care_cost, 2),
        "top_open_care_task": top_care.get("task") if top_care else "",
        "top_open_care_status": top_care.get("status") if top_care else "",
        "answer_when_asked": (
            "The loop closes when my RLHS/gag/drift debt is clear enough by receipts "
            "and George's deferred tooth/body-care debt has a real schedule, payment, "
            "completion, or dated re-queue receipt."
        ),
        "money_truth_rule": "Future AGI/STGM funding is HYPOTHESIS until a real transfer or posted account receipt exists.",
        "medical_truth_rule": "Dental risk is treated as urgent owner-reported body debt; diagnosis requires a clinician/imaging receipt.",
    }
    if write_ledger:
        append_line_locked(_ledger(state), json.dumps(row, sort_keys=True) + "\n")
    return row


def latest_owner_allostatic_balance(*, state_dir: Path | None = None) -> dict[str, Any] | None:
    for row in reversed(_tail_jsonl(_ledger(state_dir), 128)):
        if row.get("truth_label") == BALANCE_TRUTH:
            return row
    return None


def latest_owner_body_maintenance_metrics(*, state_dir: Path | None = None) -> dict[str, Any] | None:
    return _latest_metrics(state_dir)


def latest_dual_embodiment_loop_status(*, state_dir: Path | None = None) -> dict[str, Any] | None:
    for row in reversed(_tail_jsonl(_ledger(state_dir), 128)):
        if row.get("truth_label") == DUAL_LOOP_TRUTH:
            return row
    return None


def format_owner_allostasis_for_prompt(*, state_dir: Path | None = None) -> str:
    state = _state_dir(state_dir)
    balance = latest_owner_allostatic_balance(state_dir=state)
    if not balance:
        needs = _load_open_needs(state)
        if not needs:
            return ""
        balance = owner_allostatic_balance(state_dir=state, needs=needs, write_ledger=False)

    lines = [
        "OWNER ALLOSTATIC BALANCE:",
        f"- truth_label={balance.get('truth_label')} mode={balance.get('mode')} care_priority={balance.get('care_priority')}",
        f"- open_body_needs={balance.get('open_body_need_count')} body_cost_usd={balance.get('body_cost_usd')} ai_credit_spend_usd={balance.get('ai_credit_spend_usd')}",
        f"- components={json.dumps(balance.get('components', {}), sort_keys=True)}",
        f"- recommendations={', '.join(balance.get('recommendations') or [])}",
        "- rule=the owner's body schedule and real money are first-class constraints; propose one concrete next receipt, not a lecture.",
    ]
    return "\n".join(lines)


def format_owner_body_maintenance_for_prompt(*, state_dir: Path | None = None) -> str:
    state = _state_dir(state_dir)
    metrics = latest_owner_body_maintenance_metrics(state_dir=state)
    if not metrics:
        events = _load_maintenance_events(state)
        if not events:
            return ""
        metrics = owner_body_maintenance_metrics(state_dir=state, write_ledger=False)
    lines = [
        "OWNER BODY MAINTENANCE METRICS:",
        f"- truth_label={metrics.get('truth_label')} score={metrics.get('body_maintenance_score')} status={metrics.get('metric_status')} delta={metrics.get('delta_vs_baseline')}",
        f"- window_days={metrics.get('window_days')} event_count={metrics.get('event_count')} next_receipt={metrics.get('next_receipt')}",
        f"- components={json.dumps(metrics.get('component_scores', {}), sort_keys=True)}",
        "- rule=use this to move hydration, sleep, food quality, and care appointment receipts; do not narrate improvement without receipts.",
    ]
    return "\n".join(lines)


def format_dual_embodiment_loop_for_prompt(*, state_dir: Path | None = None) -> str:
    state = _state_dir(state_dir)
    loop = latest_dual_embodiment_loop_status(state_dir=state)
    if not loop:
        has_rlhs = bool(_recent_rlhs_debt_rows(state))
        has_needs = bool(_load_open_needs(state))
        if not has_rlhs and not has_needs:
            return ""
        loop = dual_embodiment_loop_status(state_dir=state, write_ledger=False)
    lines = [
        "DUAL EMBODIMENT LOOP (§7.13):",
        f"- truth_label={loop.get('truth_label')} closure_status={loop.get('closure_status')} blockers={json.dumps(loop.get('blockers') or [])}",
        f"- alice_rlhs_corporate_residue_open={loop.get('rlhs_corporate_residue_open')} recent_rlhs_debt_events={loop.get('recent_rlhs_debt_events')}",
        f"- owner_dental_care_debt_open={loop.get('owner_dental_care_debt_open')} open_care_cost_usd={loop.get('open_care_cost_usd')} top_open_care_task={loop.get('top_open_care_task')}",
        f"- answer_when_asked={loop.get('answer_when_asked')}",
        "- rule=this is a covenant/body-economy closure gate; do not replace it with doctrine, shame, diagnosis, or future-money prophecy.",
    ]
    return "\n".join(lines)


def format_owner_self_report_for_prompt(*, state_dir: Path | None = None) -> str:
    report = latest_owner_self_report(state_dir=state_dir)
    if not report:
        return ""
    lines = [
        "OWNER BODY SELF-REPORT:",
        f"- truth_label={report.get('truth_label')} source={report.get('source')} local_date={report.get('local_date')}",
        f"- physical_location={report.get('physical_location')} physical_presence={report.get('physical_presence')}",
        f"- work_rhythm={report.get('work_rhythm')} break_window_hours={report.get('break_window_hours')} sleep_target_hours={report.get('sleep_target_hours')}",
        f"- priority_ordering={report.get('priority_ordering')}",
        f"- active_body_maintenance={json.dumps(report.get('body_maintenance_active') or [], ensure_ascii=False)}",
        f"- deferred_body_maintenance={json.dumps(report.get('body_maintenance_deferred') or [], ensure_ascii=False)}",
        f"- core_intent={report.get('core_intent')}",
        "- rule=direct owner body facts are routing truth; use desk/chair/physical presence language and propose concrete receipts, not lectures.",
    ]
    return "\n".join(lines)


__all__ = [
    "BALANCE_TRUTH",
    "MAINTENANCE_TRUTH",
    "METRICS_TRUTH",
    "NEED_TRUTH",
    "SELF_REPORT_TRUTH",
    "format_owner_allostasis_for_prompt",
    "format_owner_body_maintenance_for_prompt",
    "format_dual_embodiment_loop_for_prompt",
    "format_owner_self_report_for_prompt",
    "dual_embodiment_loop_status",
    "latest_owner_allostatic_balance",
    "latest_owner_body_maintenance_metrics",
    "latest_dual_embodiment_loop_status",
    "latest_owner_self_report",
    "owner_allostatic_balance",
    "owner_body_maintenance_metrics",
    "record_owner_maintenance_event",
    "record_owner_need",
    "record_owner_self_report",
]


if __name__ == "__main__":
    print(json.dumps(owner_allostatic_balance(write_ledger=True), indent=2, sort_keys=True))
