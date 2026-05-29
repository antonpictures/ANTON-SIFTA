"""Alice stigmergic planning mode.

Pure ledger and prompt helpers for planning before major work. This module
does not speak for Alice and does not execute tools. Alice's cortex composes
the plan; this organ validates simple JSON plans and appends receipt-backed
planning rows to .sifta_state/alice_plans.jsonl.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ALLOWED_ACTORS = {
    "alice_cortex",
    "codex_agent",
    "claude_agent",
    "grok_agent",
    "hermes_agent",
    "local_tool",
    "human_owner",
}

LEDGER_NAME = "alice_plans.jsonl"
TRUTH_LABEL = "ALICE_STIGMERGIC_PLAN_V1"
ACTIVE_STATUSES = {"active", "planned", "pending", "in_progress", "paused"}
DONE_STATUSES = {"done", "completed", "ok", "failed", "cancelled", "skipped"}


@dataclass
class PlanStep:
    step_id: str
    title: str
    actor: str
    action: str
    expected_receipt: str
    status: str = "pending"


@dataclass
class Plan:
    goal: str
    steps: List[PlanStep]
    success_criteria: Any = ""
    risks: List[str] = field(default_factory=list)
    next_receipt_expected: str = ""
    mode: str = "stigmergic_planning"
    status: str = "active"
    metabolic_mode: str = "UNKNOWN"
    receipt_refs: List[str] = field(default_factory=list)
    plan_id: str = ""
    ts: float = 0.0


def parse_plan(text: str) -> Optional[Plan]:
    """Parse a cortex-composed JSON plan from text.

    Returns None for malformed plans. This function is intentionally read-only:
    rejection never mutates the planning ledger and never writes Alice's words.
    """

    if not isinstance(text, str) or not text.strip():
        return None
    raw = _extract_json_object(text)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return _coerce_plan(data)


def write_plan(plan: Plan, state_dir: str | Path = ".sifta_state") -> Dict[str, Any]:
    """Append a full plan row to alice_plans.jsonl and return the row."""

    if isinstance(plan, dict):
        coerced = _coerce_plan(plan)
        if coerced is None:
            return {}
        plan = coerced
    if not isinstance(plan, Plan):
        return {}

    row = _plan_to_row(plan)
    row["event"] = "plan_write"
    row["truth_label"] = TRUTH_LABEL
    _append_row(_ledger_path(state_dir), row)
    return row


def update_plan_step(
    plan_id: str,
    step_id: str,
    status: str,
    receipt_ref: str | None = None,
    note: str = "",
    state_dir: str | Path = ".sifta_state",
) -> Dict[str, Any]:
    """Append a step update row; never rewrite prior plan history."""

    plan_id = str(plan_id or "").strip()
    step_id = str(step_id or "").strip()
    status = str(status or "").strip()
    if not plan_id or not step_id or not status:
        return {}

    ledger = _ledger_path(state_dir)
    latest = _latest_row_for_plan(ledger, plan_id) or {
        "plan_id": plan_id,
        "goal": "",
        "mode": "stigmergic_planning",
        "status": "active",
        "steps": [],
        "metabolic_mode": "UNKNOWN",
        "receipt_refs": [],
    }
    row = dict(latest)
    row["ts"] = time.time()
    row["event"] = "step_update"
    row["truth_label"] = TRUTH_LABEL
    row["plan_id"] = plan_id
    row["step_id"] = step_id
    row["step_status"] = status
    row["note"] = str(note or "")

    steps = [dict(s) for s in row.get("steps", []) if isinstance(s, dict)]
    updated = False
    for step in steps:
        if str(step.get("step_id", "")) == step_id:
            step["status"] = status
            updated = True
            break
    if not updated:
        steps.append(
            {
                "step_id": step_id,
                "title": step_id,
                "actor": "alice_cortex",
                "action": str(note or "step update recorded"),
                "expected_receipt": str(receipt_ref or ""),
                "status": status,
            }
        )
    row["steps"] = steps

    refs = _as_string_list(row.get("receipt_refs"))
    if receipt_ref:
        ref = str(receipt_ref).strip()
        if ref and ref not in refs:
            refs.append(ref)
    row["receipt_refs"] = refs
    row["status"] = _derive_plan_status(steps, fallback=str(row.get("status", "active")))

    _append_row(ledger, row)
    return row


def read_active_plan_for_resume(state_dir: str | Path = ".sifta_state") -> Optional[Dict[str, Any]]:
    """Round 110 (§2.H) — return the latest active plan dict, read-only.

    Used by the cortex failover path so the new cortex can resume from the
    first pending step instead of waking amnesic. Pure read; never mutates
    the planning ledger.
    """
    return _latest_active_plan(_ledger_path(state_dir))


def mark_plan_resumed(
    plan_id: str,
    *,
    source: str,
    switched_from: str = "",
    switched_to: str = "",
    note: str = "",
    state_dir: str | Path = ".sifta_state",
) -> Dict[str, Any]:
    """Round 110 (§2.H) — write an audit row for cortex-failover plan resume.

    Append-only per §4.4.3. Records that a plan continued across a cortex
    body change so future doctors can audit the chain. Returns the row.
    """
    plan_id = str(plan_id or "").strip()
    if not plan_id:
        return {}

    ledger = _ledger_path(state_dir)
    latest = _latest_row_for_plan(ledger, plan_id)
    if not latest:
        return {}

    pending_step = ""
    for step in latest.get("steps", []) or []:
        if not isinstance(step, dict):
            continue
        if str(step.get("status", "")).strip().lower() in {"pending", "in_progress", "paused"}:
            pending_step = str(step.get("step_id", "")) or ""
            break

    row = {
        "ts": time.time(),
        "event": "plan_resumed_on_cortex_switch",
        "truth_label": TRUTH_LABEL,
        "plan_id": plan_id,
        "goal": str(latest.get("goal", "")),
        "status": str(latest.get("status", "active")),
        "resume_source": str(source or "").strip() or "unknown",
        "switched_from": str(switched_from or "").strip(),
        "switched_to": str(switched_to or "").strip(),
        "first_pending_step_id": pending_step,
        "note": str(note or "").strip(),
    }
    _append_row(ledger, row)
    return row


def active_plan_block(state_dir: str | Path = ".sifta_state") -> str:
    """Round 110 (§2.H) — compact prompt block for the active plan.

    Designed to be included in the memory card composer so every cortex turn
    sees the live plan, including the first turn after a failover switch.
    Pure read; returns empty string when no plan is active.
    """
    plan = read_active_plan_for_resume(state_dir)
    if not plan:
        return ""
    lines = [
        "ACTIVE PLAN (resume from first pending step — do not restart from scratch):",
        f"- plan_id: {plan.get('plan_id', '?')}",
        f"- goal: {str(plan.get('goal', '')).strip()[:200]}",
        f"- status: {plan.get('status', 'active')}",
    ]
    steps = plan.get("steps") or []
    pending_lines: List[str] = []
    done_lines: List[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_id = step.get("step_id", "?")
        title = str(step.get("title", "")).strip()[:120]
        status = str(step.get("status", "")).strip().lower()
        line = f"  [{status or 'pending'}] {step_id}: {title}"
        if status in DONE_STATUSES:
            done_lines.append(line)
        else:
            pending_lines.append(line)
    if done_lines:
        lines.append("Completed steps (for context, not for redoing):")
        lines.extend(done_lines[-6:])
    if pending_lines:
        lines.append("Pending steps (resume here):")
        lines.extend(pending_lines[:6])
    return "\n".join(lines)


def planning_prompt_block(state_dir: str | Path = ".sifta_state") -> str:
    """Return the prompt block injected when Alice's Planning Mode is enabled."""

    latest = _latest_active_plan(_ledger_path(state_dir))
    actors = ", ".join(sorted(ALLOWED_ACTORS))
    lines = [
        "ALICE STIGMERGIC PLANNING MODE",
        "Planning Mode is Alice's visible executive function, not an owner approval gate.",
        "For major coding, organism repair, arm endurance, or multi-step tool work, I first compose a plan from cortex before dispatching arms or tools.",
        "After the plan exists, explicit [TOOL_CALL] syntax and arm dispatch may execute normally; receipts update the plan ledger.",
        "No deterministic chat template may speak for me. Schema validation can reject malformed plan JSON, but it must not write my words.",
        "MetabolicHomeostat RED_CONSERVE may shorten or pause planning; that is the body budget, not a human click gate.",
        f"Allowed actors: {actors}.",
        "Plan JSON format:",
        '```json\n{"goal":"...","success_criteria":"...","steps":[{"step_id":"s1","title":"...","actor":"alice_cortex","action":"...","expected_receipt":"work_receipts.jsonl","status":"pending"}],"risks":["..."],"next_receipt_expected":"..."}\n```',
    ]
    try:
        from System.swarm_owner_somatic_state import latest_somatic_block

        somatic = (latest_somatic_block(state_dir=state_dir) or "").strip()
        low = somatic.lower()
        if somatic and "no recent data" not in low and "no fresh data" not in low and "ledger read error" not in low:
            lines.extend(
                [
                    "Owner somatic planning input:",
                    f"- {somatic}",
                ]
            )
    except Exception:
        lines.append("Owner somatic planning input: FIELD_FAILURE")
    if latest:
        step_bits = []
        for step in latest.get("steps", [])[:6]:
            if isinstance(step, dict):
                step_bits.append(
                    f"{step.get('step_id', '?')}:{step.get('status', '?')}:{step.get('actor', '?')}"
                )
        refs = ", ".join(_as_string_list(latest.get("receipt_refs"))[-6:]) or "none yet"
        lines.extend(
            [
                "Latest active plan from alice_plans.jsonl:",
                f"- plan_id={latest.get('plan_id', '')}",
                f"- goal={latest.get('goal', '')}",
                f"- status={latest.get('status', '')}; metabolic_mode={latest.get('metabolic_mode', '')}",
                f"- steps={'; '.join(step_bits) if step_bits else 'none'}",
                f"- receipt_refs={refs}",
            ]
        )
    else:
        lines.append("No active plan ledger row yet.")
    return "\n".join(lines)


def _extract_json_object(text: str) -> Optional[str]:
    fenced = re.search(r"```(?:json|plan)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.I)
    if fenced:
        return fenced.group(1).strip()
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return None


def _coerce_plan(data: Any) -> Optional[Plan]:
    if not isinstance(data, dict):
        return None
    goal = str(data.get("goal", "")).strip()
    raw_steps = data.get("steps")
    if not goal or not isinstance(raw_steps, list) or not raw_steps:
        return None

    steps: List[PlanStep] = []
    for idx, raw in enumerate(raw_steps, start=1):
        if not isinstance(raw, dict):
            return None
        actor = str(raw.get("actor", "")).strip()
        if actor not in ALLOWED_ACTORS:
            return None
        step = PlanStep(
            step_id=str(raw.get("step_id") or f"s{idx}").strip(),
            title=str(raw.get("title", "")).strip(),
            actor=actor,
            action=str(raw.get("action", "")).strip(),
            expected_receipt=str(raw.get("expected_receipt", "")).strip(),
            status=str(raw.get("status", "pending")).strip() or "pending",
        )
        if not step.step_id or not step.title or not step.action:
            return None
        steps.append(step)

    return Plan(
        plan_id=str(data.get("plan_id", "")).strip(),
        ts=_float_or_zero(data.get("ts")),
        goal=goal,
        success_criteria=data.get("success_criteria", ""),
        steps=steps,
        risks=_as_string_list(data.get("risks")),
        next_receipt_expected=str(data.get("next_receipt_expected", "")).strip(),
        mode=str(data.get("mode", "stigmergic_planning")).strip() or "stigmergic_planning",
        status=str(data.get("status", "active")).strip() or "active",
        metabolic_mode=str(data.get("metabolic_mode", "UNKNOWN")).strip() or "UNKNOWN",
        receipt_refs=_as_string_list(data.get("receipt_refs")),
    )


def _plan_to_row(plan: Plan) -> Dict[str, Any]:
    row = asdict(plan)
    row["plan_id"] = plan.plan_id or f"plan_{uuid.uuid4().hex[:16]}"
    row["ts"] = plan.ts or time.time()
    row["receipt_refs"] = _as_string_list(plan.receipt_refs)
    row["risks"] = _as_string_list(plan.risks)
    row["steps"] = [asdict(step) for step in plan.steps]
    row["metabolic_mode"] = plan.metabolic_mode or "UNKNOWN"
    row["mode"] = plan.mode or "stigmergic_planning"
    row["status"] = plan.status or "active"
    return row


def _derive_plan_status(steps: Iterable[Dict[str, Any]], fallback: str = "active") -> str:
    statuses = {str(step.get("status", "")).strip().lower() for step in steps}
    statuses.discard("")
    if not statuses:
        return fallback or "active"
    if statuses <= {"done", "completed", "ok", "skipped"}:
        return "completed"
    if statuses & {"failed", "lied"}:
        return "active"
    if statuses & {"in_progress", "dispatched"}:
        return "in_progress"
    return fallback or "active"


def _latest_active_plan(ledger: Path) -> Optional[Dict[str, Any]]:
    for row in reversed(list(_iter_rows(ledger))):
        status = str(row.get("status", "")).strip().lower()
        if status in ACTIVE_STATUSES or status not in DONE_STATUSES:
            return row
    return None


def _latest_row_for_plan(ledger: Path, plan_id: str) -> Optional[Dict[str, Any]]:
    for row in reversed(list(_iter_rows(ledger))):
        if str(row.get("plan_id", "")) == plan_id:
            return row
    return None


def _iter_rows(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    return rows


def _append_row(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _ledger_path(state_dir: str | Path) -> Path:
    return Path(state_dir).expanduser() / LEDGER_NAME


def _as_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0
