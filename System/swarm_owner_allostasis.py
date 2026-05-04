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

BODY_DOMAINS = {"dental", "medical", "sleep", "food", "movement", "hygiene", "body"}
MONEY_DOMAINS = {"money", "budget", "ai_credits", "debt"}
OPEN_STATUSES = {"open", "planned", "deferred", "unknown"}


def _state_dir(state_dir: Path | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _ledger(state_dir: Path | None = None) -> Path:
    return _state_dir(state_dir) / LEDGER_NAME


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


def _need_id(task: str, domain: str, source: str) -> str:
    material = f"{task.strip().lower()}|{domain.strip().lower()}|{source.strip().lower()}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


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


def latest_owner_allostatic_balance(*, state_dir: Path | None = None) -> dict[str, Any] | None:
    for row in reversed(_tail_jsonl(_ledger(state_dir), 128)):
        if row.get("truth_label") == BALANCE_TRUTH:
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


__all__ = [
    "BALANCE_TRUTH",
    "NEED_TRUTH",
    "format_owner_allostasis_for_prompt",
    "latest_owner_allostatic_balance",
    "owner_allostatic_balance",
    "record_owner_need",
]


if __name__ == "__main__":
    print(json.dumps(owner_allostatic_balance(write_ledger=True), indent=2, sort_keys=True))
