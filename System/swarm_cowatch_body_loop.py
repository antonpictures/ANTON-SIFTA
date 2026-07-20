#!/usr/bin/env python3
"""predict→observe wrapper for co-watch witness commentary (not browser search).

Truth label: COWATCH_BODY_LOOP_V1
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

TRUTH_LABEL = "COWATCH_BODY_LOOP_V1"


def run_cowatch_commentary_body_loop(
    *,
    context: str,
    reply: str,
    receipt_id: str,
    url: str,
    decision: Mapping[str, Any],
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """predict → speak commentary → observe for co-watch urge tick."""
    from System.swarm_body_loop_receipt import (
        begin_body_action_prediction,
        complete_body_action_prediction,
    )

    action = "cowatch_commentary_speak"
    expected = (
        f"Co-watch commentary spoken with video pause-if-playing; "
        f"receipt={receipt_id}; context={context[:80]!r}"
    )
    begin_body_action_prediction(action, expected, context=context[:200], state_dir=state_dir)
    clipped = " ".join(str(reply or "").split())[:400]
    actual = (
        f"cowatch_commentary ok receipt={receipt_id} url={url} "
        f"reason={decision.get('reason')} reply={clipped!r}"
    )
    outcome = complete_body_action_prediction(action, actual, state_dir=state_dir)
    return {"action": action, "actual": actual, "outcome": outcome}


def run_cowatch_video_pause_body_loop(
    *,
    url: str,
    receipt: Mapping[str, Any],
    context: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """predict → pause video → observe for co-watch / speech pause."""
    from System.swarm_body_loop_receipt import (
        begin_body_action_prediction,
        complete_body_action_prediction,
    )

    action = "cowatch_video_pause"
    expected = f"Alice Browser pauses playing video at {url} before speech"
    begin_body_action_prediction(action, expected, context=context[:200], state_dir=state_dir)
    ok = bool(receipt.get("ok")) and bool(receipt.get("paused"))
    actual = (
        f"cowatch_pause ok={ok} url={url} was_paused={receipt.get('was_paused')} "
        f"paused={receipt.get('paused')}"
    )
    outcome = complete_body_action_prediction(action, actual, state_dir=state_dir)
    return {"action": action, "actual": actual, "outcome": outcome}


def run_cowatch_video_resume_body_loop(
    *,
    url: str,
    context: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """predict → resume video → observe after speech ends."""
    from System.swarm_body_loop_receipt import (
        begin_body_action_prediction,
        complete_body_action_prediction,
    )

    action = "cowatch_video_resume"
    expected = f"Alice Browser resumes video at {url} after speech"
    begin_body_action_prediction(action, expected, context=context[:200], state_dir=state_dir)
    actual = f"cowatch_resume issued url={url}"
    outcome = complete_body_action_prediction(action, actual, state_dir=state_dir)
    return {"action": action, "actual": actual, "outcome": outcome}


__all__ = [
    "TRUTH_LABEL",
    "run_cowatch_commentary_body_loop",
    "run_cowatch_video_pause_body_loop",
    "run_cowatch_video_resume_body_loop",
]