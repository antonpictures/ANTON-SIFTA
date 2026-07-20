#!/usr/bin/env python3
"""Uniform predict -> execute -> observe receipt helper for Talk effectors.

Truth label: BODY_LOOP_ACTION_RECEIPT_V1
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

TRUTH_LABEL = "BODY_LOOP_ACTION_RECEIPT_V1"


def _state_dir(state_dir: Optional[Path | str]) -> Path:
    if state_dir is None:
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def begin_body_action_prediction(
    action: str,
    expected: str,
    *,
    context: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    from System.swarm_action_prediction import predict

    return predict(action, expected, context=context, state_dir=state_dir)


def complete_body_action_prediction(
    action: str,
    actual: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    from System.swarm_action_prediction import observe

    return observe(action, actual, state_dir=state_dir)


def run_body_action_with_receipt(
    action: str,
    expected: str,
    runner: Callable[[], str],
    *,
    context: str = "",
    state_dir: Optional[Path | str] = None,
) -> tuple[str, dict[str, Any]]:
    begin_body_action_prediction(action, expected, context=context, state_dir=state_dir)
    try:
        actual = str(runner() or "").strip()
    except Exception as exc:
        actual = f"error:{type(exc).__name__}:{exc}"
        outcome = complete_body_action_prediction(action, actual, state_dir=state_dir)
        raise
    outcome = complete_body_action_prediction(action, actual, state_dir=state_dir)
    return actual, outcome


__all__ = [
    "TRUTH_LABEL",
    "begin_body_action_prediction",
    "complete_body_action_prediction",
    "run_body_action_with_receipt",
]