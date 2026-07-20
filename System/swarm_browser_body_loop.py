#!/usr/bin/env python3
"""Unified predict→execute→observe wrapper for Talk browser/app effectors.

George r1338: provider reality + action_prediction on browser_url, close-tab,
photo-select, and generic browser paths — not only explicit SEARCH ON GOOGLE PLS.

Truth label: BROWSER_BODY_LOOP_V1
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

TRUTH_LABEL = "BROWSER_BODY_LOOP_V1"


def _state_dir(state_dir: Optional[Path | str] = None) -> Path:
    repo = Path(__file__).resolve().parents[1]
    default = repo / ".sifta_state"
    if state_dir is None:
        return default
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


_BRIDGE_SOURCE_ACTIONS: dict[str, tuple[str, str]] = {
    "post_cortex_web_bridge": (
        "hallucination_bridge_web_search",
        "Hallucination bridge routes owner verbatim web search through Alice Browser",
    ),
    "post_cortex_youtube_bridge": (
        "hallucination_bridge_youtube",
        "Hallucination bridge routes owner YouTube search through Alice Browser",
    ),
    "post_cortex_photo_select_bridge": (
        "hallucination_bridge_photo_select",
        "Hallucination bridge clicks the requested browser image tile",
    ),
}


def plan_body_loop_from_command(command: dict[str, Any]) -> Optional[tuple[str, str]]:
    """Map a sifta app command to (action_id, expected_outcome)."""
    if command.get("_body_loop_inner"):
        return None
    bridge_source = str(command.get("contextual_search_source") or "").strip()
    if bridge_source in _BRIDGE_SOURCE_ACTIONS:
        action, expected = _BRIDGE_SOURCE_ACTIONS[bridge_source]
        query = str(command.get("query") or "").strip()
        if query:
            expected = f"{expected} for {query!r}"
        return action, expected
    kind = str(command.get("kind") or "").strip()
    if kind == "browser_url":
        url = str(command.get("url") or "").strip()
        query = str(command.get("query") or "").strip()
        if query:
            return (
                "browser_search",
                f"Alice Browser opens web search results for {query!r} at {url}",
            )
        return ("browser_navigate_url", f"Alice Browser loads {url}")
    if kind == "browser_action":
        action = str(command.get("action") or "").strip()
        if action == "close_browser_tabs":
            match = str(command.get("url_match") or command.get("title_match") or "").strip()
            if command.get("close_duplicates"):
                return ("browser_close_tab", "Alice Browser closes duplicate tab(s)")
            if command.get("index") is not None:
                return ("browser_close_tab", f"Alice Browser closes tab index {command.get('index')}")
            return ("browser_close_tab", f"Alice Browser closes tab(s) matching {match or 'owner request'}")
        if action == "click_element":
            labels = command.get("labels") or []
            label = str(labels[0] if labels else command.get("label") or "element").strip()
            return ("browser_click", f"Alice Browser clicks {label!r}")
    return None


def observe_text_for_command(
    command: dict[str, Any],
    reply: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Build actual-outcome string for predict→observe."""
    kind = str(command.get("kind") or "").strip()
    url = str(command.get("url") or "").strip()
    query = str(command.get("query") or "").strip()
    owner_text = str(command.get("owner_text") or command.get("raw_text") or "").strip()
    if kind == "browser_url" and query and url:
        try:
            from System.swarm_search_provider_reality import (
                append_provider_reality_row,
                build_provider_reality_row,
                observe_text_for_prediction,
            )

            row = build_provider_reality_row(
                owner_text=owner_text,
                query=query,
                execution_url=url,
            )
            append_provider_reality_row(row, state_dir=state_dir)
            return observe_text_for_prediction(
                owner_text=owner_text,
                query=query,
                execution_url=url,
            )
        except Exception:
            pass
    clipped = " ".join(str(reply or "").split())
    return clipped[:500] if clipped else "no_reply"


def maybe_honest_search_reply(
    command: dict[str, Any],
    reply: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Replace generic search narration with provider-reality reply when applicable."""
    kind = str(command.get("kind") or "").strip()
    url = str(command.get("url") or "").strip()
    query = str(command.get("query") or "").strip()
    owner_text = str(command.get("owner_text") or command.get("raw_text") or "").strip()
    if kind != "browser_url" or not query or not url:
        return str(reply or "")
    try:
        from System.swarm_search_provider_reality import honest_search_reply

        honest = honest_search_reply(
            owner_text=owner_text,
            query=query,
            execution_url=url,
            state_dir=state_dir,
            persist=True,
        )
        if honest:
            return honest
    except Exception:
        pass
    return str(reply or "")


def run_sifta_app_body_loop(
    command: dict[str, Any],
    execute: Callable[[dict[str, Any]], str],
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """predict → execute → observe for eligible app/browser commands."""
    plan = plan_body_loop_from_command(command)
    if plan is None:
        return execute(command)
    action, expected = plan
    from System.swarm_body_loop_receipt import (
        begin_body_action_prediction,
        complete_body_action_prediction,
    )

    owner_text = str(command.get("owner_text") or command.get("raw_text") or "").strip()
    begin_body_action_prediction(
        action,
        expected,
        context=owner_text[:200],
        state_dir=state_dir,
    )
    inner = dict(command)
    inner["_body_loop_inner"] = True
    try:
        reply = str(execute(inner) or "").strip()
    except Exception as exc:
        actual = f"error:{type(exc).__name__}:{exc}"
        complete_body_action_prediction(action, actual, state_dir=state_dir)
        raise
    reply = maybe_honest_search_reply(command, reply, state_dir=state_dir)
    actual = observe_text_for_command(command, reply, state_dir=state_dir)
    complete_body_action_prediction(action, actual, state_dir=state_dir)
    return reply


def run_self_screenshot_body_loop(
    *,
    owner_text: str,
    capture_runner: Callable[[], dict[str, Any]],
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """predict → capture → observe for /SC proprioception turns."""
    from System.swarm_body_loop_receipt import (
        begin_body_action_prediction,
        complete_body_action_prediction,
    )

    action = "self_screenshot_capture"
    expected = "SIFTA OS self-screenshot saved with receipt_id and image_path"
    begin_body_action_prediction(action, expected, context=owner_text[:200], state_dir=state_dir)
    cap = capture_runner()
    if cap.get("ok") and cap.get("image_path"):
        actual = (
            f"self_screenshot ok receipt_id={cap.get('receipt_id')} "
            f"path={cap.get('image_path')}"
        )
    else:
        actual = f"self_screenshot failed error={cap.get('error') or cap.get('status') or 'unknown'}"
    complete_body_action_prediction(action, actual, state_dir=state_dir)
    return cap


def sc_describe_clothing_reply(
    owner_text: str,
    *,
    state_dir: Optional[Path | str] = None,
) -> str:
    """Fast /SC + describe clothing path — VLM receipt or honest gap."""
    from System.swarm_body_loop_receipt import (
        begin_body_action_prediction,
        complete_body_action_prediction,
    )

    action = "sc_describe_clothing"
    expected = "owner-frame VLM receipt with clothing/colors or honest unavailable gap"
    begin_body_action_prediction(action, expected, context=owner_text[:200], state_dir=state_dir)
    try:
        from System.swarm_saccadic_blink_vision import describe_owner_frame_on_demand

        row = describe_owner_frame_on_demand(
            reason="sc_describe_clothing",
            owner_text=owner_text,
            write=True,
            state_dir=state_dir,
        )
        desc = row.get("semantic_description") if isinstance(row.get("semantic_description"), dict) else {}
        status = str(desc.get("status") or "unknown")
        text = str(desc.get("description") or "").strip()
        frame_age = row.get("frame_age_s")
        age_note = f"frame {int(frame_age)}s ago" if frame_age is not None else "frame age unknown"
        if status == "ok" and text:
            # Force grounding: the VLM text must be treated as the pixel source.
            # If it contains invented prior-turn details, the cortex will still see the image.
            reply = (
                f"From my owner-eye camera ({age_note}), pixel-grounded description: {text} "
                f"(VLM receipt blink_id={row.get('blink_id')}). I will not invent or continue prior guesses."
            )
            actual = f"vlm_ok blink_id={row.get('blink_id')} status=ok"
        else:
            reply = (
                f"I tried to describe your clothing from my camera, but I do not have a fresh "
                f"owner-frame VLM receipt yet ({status}, {age_note}). "
                "I will not invent colors or garments. Open What Alice Sees or enable the camera and ask again."
            )
            actual = f"vlm_gap status={status}"
    except Exception as exc:
        reply = (
            f"I could not run the owner-frame clothing describe this turn: "
            f"{type(exc).__name__}: {exc}. I will not invent colors."
        )
        actual = f"vlm_error:{type(exc).__name__}"
    complete_body_action_prediction(action, actual, state_dir=state_dir)
    return reply


__all__ = [
    "TRUTH_LABEL",
    "plan_body_loop_from_command",
    "observe_text_for_command",
    "maybe_honest_search_reply",
    "run_sifta_app_body_loop",
    "run_self_screenshot_body_loop",
    "sc_describe_clothing_reply",
]
