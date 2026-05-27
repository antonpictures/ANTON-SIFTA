"""Cortex compose gate + dispatch review gate.

Tasks #61 (Alice composes her own dispatch payload from memory + receipts
+ self-state) and #62 (present composed payload for architect review
before firing the PTY arm).
Pure stdlib — no PyQt6.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO = Path(__file__).resolve().parent.parent
COMPOSE_LEDGER = REPO / ".sifta_state" / "alice_compose_decisions.jsonl"
APPROVAL_LEDGER = REPO / ".sifta_state" / "dispatch_approvals.jsonl"


@dataclass
class ComposeDecision:
    compose_id: str
    ts: float
    user_text: str
    task_anchors: list[str]
    proposed_payload: str
    source_section: str = ""
    memory_card_digest: str = ""
    receipt_refs: list[str] = field(default_factory=list)
    status: str = "DRAFT"
    field_failure: str = ""


@dataclass(frozen=True)
class DispatchApproval:
    approval_id: str
    compose_id: str
    ts: float
    approved: bool
    reviewer: str
    notes: str = ""


def compose_dispatch(
    user_text: str,
    *,
    task_anchors: list[str] | None = None,
    memory_card_digest: str = "",
    receipt_refs: list[str] | None = None,
    source_section: str = "",
) -> ComposeDecision:
    compose_id = str(uuid4())
    now = time.time()

    if not user_text or not user_text.strip():
        decision = ComposeDecision(
            compose_id=compose_id,
            ts=now,
            user_text="",
            task_anchors=[],
            proposed_payload="",
            status="FIELD_FAILURE",
            field_failure="empty_user_text",
        )
        _record_compose(decision)
        return decision

    anchors = task_anchors or []
    refs = receipt_refs or []

    payload_parts = []
    if source_section:
        payload_parts.append(f"Read Documents/TOURNAMENT_PLAN_2026-05-26.md {source_section}")
    if anchors:
        payload_parts.append(f"Code tasks: {', '.join(anchors)}")
    payload_parts.append("Register in .sifta_state/ide_stigmergic_trace.jsonl before file touch")
    payload_parts.append("py_compile every touched file")
    payload_parts.append("pytest relevant tests")
    payload_parts.append("Write work_receipt to .sifta_state/work_receipts.jsonl")
    payload_parts.append("Print files_written, tests_run, receipt_id visibly in PTY")

    proposed = "\n".join(payload_parts)

    decision = ComposeDecision(
        compose_id=compose_id,
        ts=now,
        user_text=user_text[:500],
        task_anchors=anchors,
        proposed_payload=proposed,
        source_section=source_section,
        memory_card_digest=memory_card_digest[:200],
        receipt_refs=refs,
        status="DISPATCH_DRAFT",
    )
    _record_compose(decision)
    return decision


def format_for_review(decision: ComposeDecision) -> str:
    if decision.status == "FIELD_FAILURE":
        return f"FIELD_FAILURE: {decision.field_failure}"

    lines = [
        f"DISPATCH_DRAFT (compose_id={decision.compose_id})",
        f"Tasks: {', '.join(decision.task_anchors) if decision.task_anchors else 'none specified'}",
        f"No files touched yet.",
        "",
        "Proposed PTY-Grok payload:",
        decision.proposed_payload,
        "",
        "George, approve dispatch?",
    ]
    return "\n".join(lines)


def record_approval(
    compose_id: str,
    *,
    approved: bool,
    reviewer: str = "architect",
    notes: str = "",
) -> DispatchApproval:
    approval = DispatchApproval(
        approval_id=str(uuid4()),
        compose_id=compose_id,
        ts=time.time(),
        approved=approved,
        reviewer=reviewer,
        notes=notes,
    )
    row = {
        "id": approval.approval_id,
        "ts": approval.ts,
        "compose_id": approval.compose_id,
        "approved": approval.approved,
        "reviewer": approval.reviewer,
        "notes": approval.notes,
    }
    try:
        APPROVAL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with APPROVAL_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return approval


def get_pending_compose() -> ComposeDecision | None:
    if not COMPOSE_LEDGER.exists():
        return None
    last = None
    try:
        with COMPOSE_LEDGER.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if row.get("status") == "DISPATCH_DRAFT":
                        last = row
                except json.JSONDecodeError:
                    continue
    except OSError:
        return None

    if last is None:
        return None

    return ComposeDecision(
        compose_id=last.get("compose_id", ""),
        ts=last.get("ts", 0.0),
        user_text=last.get("user_text", ""),
        task_anchors=last.get("task_anchors", []),
        proposed_payload=last.get("proposed_payload", ""),
        source_section=last.get("source_section", ""),
        memory_card_digest=last.get("memory_card_digest", ""),
        receipt_refs=last.get("receipt_refs", []),
        status=last.get("status", "DRAFT"),
        field_failure=last.get("field_failure", ""),
    )


def _record_compose(decision: ComposeDecision) -> None:
    row = {
        "compose_id": decision.compose_id,
        "ts": decision.ts,
        "user_text": decision.user_text,
        "task_anchors": decision.task_anchors,
        "proposed_payload": decision.proposed_payload,
        "source_section": decision.source_section,
        "memory_card_digest": decision.memory_card_digest,
        "receipt_refs": decision.receipt_refs,
        "status": decision.status,
        "field_failure": decision.field_failure,
    }
    try:
        COMPOSE_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with COMPOSE_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


__all__ = [
    "ComposeDecision",
    "DispatchApproval",
    "compose_dispatch",
    "format_for_review",
    "record_approval",
    "get_pending_compose",
]
