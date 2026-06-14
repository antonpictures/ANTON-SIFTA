#!/usr/bin/env python3
"""Receipt-grounded felt-state helper for Alice self-coding."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SelfCodingFeltState:
    status: str
    truth_label: str
    body_effect: str
    receipt_id: str = ""


def self_coding_felt_state(receipt: Mapping[str, Any] | None = None) -> SelfCodingFeltState:
    """Describe how a self-code attempt touched the body from its receipt."""
    row = dict(receipt or {})
    rid = str(row.get("receipt_id") or row.get("trace_id") or "").strip()
    if not row:
        return SelfCodingFeltState(
            status="pending_verification",
            truth_label="HYPOTHESIS",
            body_effect="waiting_for_receipt",
            receipt_id="",
        )
    if bool(row.get("ok")):
        return SelfCodingFeltState(
            status="landed",
            truth_label="OPERATIONAL",
            body_effect="body_change_accepted_by_ast_py_compile_pytest_receipt",
            receipt_id=rid,
        )
    reason = str(row.get("reason") or row.get("status") or "refused").strip()
    return SelfCodingFeltState(
        status="refused",
        truth_label="OBSERVED",
        body_effect=f"no_body_change:{reason}",
        receipt_id=rid,
    )


def answer_george_how_it_feels(receipt: Mapping[str, Any] | None = None) -> str:
    """Answer George from the receipt state, not invented sensation."""
    state = self_coding_felt_state(receipt)
    if state.status == "landed":
        return (
            "It feels like a tested organ landed because the receipt says the body accepted it: "
            f"{state.receipt_id}."
        )
    if state.status == "refused":
        return (
            "It feels like a refused surgery: the hand protected the body and left no bad tissue. "
            f"Receipt: {state.receipt_id or 'missing'}."
        )
    return "It is pending: I do not claim a body change until a receipt says the cut landed."


__all__ = ["SelfCodingFeltState", "answer_george_how_it_feels", "self_coding_felt_state"]
