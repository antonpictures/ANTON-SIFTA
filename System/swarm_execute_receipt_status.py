#!/usr/bin/env python3
"""Classify execution receipt rows for router repair."""

from __future__ import annotations

from typing import Any, Mapping


TRUTH_LABEL = "EXECUTE_RECEIPT_STATUS_V1"


def classify_execute_outcome(row: Mapping[str, Any] | None, *, error: Exception | None = None) -> dict[str, Any]:
    if error is not None:
        return {
            "truth_label": TRUTH_LABEL,
            "ok": False,
            "status": "error",
            "reason": str(error),
        }
    if not isinstance(row, Mapping):
        return {
            "truth_label": TRUTH_LABEL,
            "ok": False,
            "status": "refused_unparsed",
            "reason": "no_parseable_execution_row",
        }
    actions = row.get("actions")
    if isinstance(actions, (list, tuple)) and len(actions) > 0:
        return {
            "truth_label": TRUTH_LABEL,
            "ok": True,
            "status": "executed",
            "reason": "execution_row_has_actions",
            "action_count": len(actions),
        }
    return {
        "truth_label": TRUTH_LABEL,
        "ok": False,
        "status": "needs_router_repair",
        "reason": "execution_row_without_actions",
        "action_count": 0,
    }


__all__ = ["TRUTH_LABEL", "classify_execute_outcome"]
