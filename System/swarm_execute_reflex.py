#!/usr/bin/env python3
"""
System/swarm_execute_reflex.py — EXECUTE Trigger Word CLI Executor
══════════════════════════════════════════════════════════════════════
Architecture (IBM/OpenClaw-style explicit EXECUTE line):

  Owner says:  "switch to macbook camera EXECUTE"
                or "EXECUTE switch camera"
                or "increase resolution EXECUTE"

  1. EXECUTE keyword detected — bypasses ALL media gates (it's never in a YouTube video)
  2. Swimmer chorus parses the surrounding context window (not LLM)
  3. Correct effector is called (camera switch, resolution, etc.)
  4. Receipt injected into Alice's next prompt turn with ONE example seed
  5. Alice composes her own response — not hardcoded, never a star-action

ONE EXAMPLE SEED (injected into prompt, not hardcoded in code):
  "Ok I hear you — switching to the MacBook camera now."

Alice generates variations:
  "Got it, moving to the built-in eye."
  "MacBook camera — done."
  "Switching."
"""
from __future__ import annotations

import re
import json
import time
import uuid
from pathlib import Path
from typing import Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# ── The trigger word ────────────────────────────────────────────────────────
# Rare in casual speech and YouTube narration. Short enough to say naturally.
TRIGGER_WORD = "execute"
_TRIGGER_RE = re.compile(r"\bexecute\b", re.IGNORECASE)

# ── Swimmer chorus: command classifiers ─────────────────────────────────────
# Each classifier is (name, pattern, handler_fn).
# The text window around EXECUTE is scored against all of them.
# First match wins. No LLM.

_CAMERA_SWITCH_RE = re.compile(
    r"\b(?:switch|change|swap|use|move|go\s+to)\b.{0,50}\bcamera\b"
    r"|\bcamera\b.{0,30}\b(?:switch|change|macbook|logitech|iphone|built[- ]?in|usb)\b",
    re.IGNORECASE,
)
_CAMERA_MACBOOK_RE = re.compile(r"\b(?:macbook|built[- ]?in|facetime|laptop|internal)\b", re.IGNORECASE)
_CAMERA_LOGITECH_RE = re.compile(r"\b(?:logitech|usb|external|desk|webcam)\b", re.IGNORECASE)
_CAMERA_IPHONE_RE = re.compile(r"\b(?:iphone|phone|continuity)\b", re.IGNORECASE)

_RESOLUTION_RE = re.compile(
    r"\b(?:resolution|res|quality|acuity|sharpness)\b",
    re.IGNORECASE,
)
_RESOLUTION_UP_RE = re.compile(r"\b(?:increase|up|higher|more|boost|max|better|improve)\b", re.IGNORECASE)
_RESOLUTION_DOWN_RE = re.compile(r"\b(?:decrease|down|lower|less|reduce|min|worse)\b", re.IGNORECASE)

# ── One example seed for Alice's response ───────────────────────────────────
# This is injected into Alice's system prompt after execution.
# She reads it once and develops her own style from it.
# NEVER put this in Alice's output directly — it's a seed, not a template.
RESPONSE_SEED = (
    "EXECUTE_RECEIPT: A CLI command was just run directly on my hardware body "
    "without going through the LLM. Here is what happened: {action_summary}. "
    "Respond in your own voice — short, grounded, first-person. "
    "ONE EXAMPLE of the tone (do not copy verbatim): "
    "'Ok I hear you — {example_action} now.' "
    "Develop your own phrasing from that seed."
)


def _read_current_camera() -> int:
    try:
        from System.swarm_camera_target import read_target

        row = read_target()
        if isinstance(row, dict) and row.get("index") is not None:
            return int(row["index"])
    except Exception:
        pass
    return 1


def _camera_name_for_role(role: str) -> str:
    from System.swarm_eye_registry import live_owner_eye_device, live_world_eye_device

    if role == "owner":
        return str(live_owner_eye_device().get("name") or "")
    if role == "world":
        return str(live_world_eye_device().get("name") or "")
    return ""


def _handle_camera_switch(text: str) -> Optional[dict]:
    """Swimmer: parse camera target from text window."""
    if not _CAMERA_SWITCH_RE.search(text):
        return None

    role = "cycle"
    if _CAMERA_MACBOOK_RE.search(text):
        role = "owner"
    elif _CAMERA_LOGITECH_RE.search(text):
        role = "world"
    elif _CAMERA_IPHONE_RE.search(text):
        role = "iphone"
    else:
        current = _read_current_camera()
        role = "world" if current == 1 else "owner"

    try:
        from System.swarm_camera_switch import _index_for_role
        from System.swarm_camera_target import write_target

        if role == "iphone":
            idx = 3
            canonical_name = _camera_name_for_role("owner")
        else:
            idx = _index_for_role(role)
            canonical_name = _camera_name_for_role(role)
        if idx is None and not canonical_name:
            return {
                "effector": "camera_switch",
                "ok": False,
                "error": "no live camera for requested role",
                "action_summary": "camera switch failed: no live device",
                "example_action": "I could not move my active eye",
            }
        rec = write_target(
            name=canonical_name,
            index=idx,
            writer="execute_reflex",
            priority=95,
            lease_s=120.0,
            respect_lease=False,
        )
        name = rec.get("name") or canonical_name
    except Exception as e:
        return {
            "effector": "camera_switch",
            "ok": False,
            "error": str(e),
            "action_summary": f"camera switch failed: {e}",
            "example_action": "I could not move my active eye",
        }
    return {
        "effector": "camera_switch",
        "ok": True,
        "camera_index": idx,
        "camera_name": name,
        "action_summary": f"camera switched to {name} (index {idx})",
        "example_action": f"switching to the {name}",
    }


def _handle_resolution(text: str) -> Optional[dict]:
    """Swimmer: parse resolution change direction from text window."""
    if not _RESOLUTION_RE.search(text):
        return None

    if _RESOLUTION_UP_RE.search(text):
        direction = "increased"
    elif _RESOLUTION_DOWN_RE.search(text):
        direction = "decreased"
    else:
        direction = "increased"

    try:
        from System.swarm_visual_acuity_target import step_acuity

        row = step_acuity(
            "decrease" if direction == "decreased" else "increase",
            state_dir=_STATE,
            writer="execute_reflex",
            source_text=text,
        )
    except Exception as e:
        return {
            "effector": "resolution_change",
            "ok": False,
            "error": str(e),
            "action_summary": f"visual acuity change failed: {e}",
            "example_action": "I could not change my photon grid",
        }

    return {
        "effector": "resolution_change",
        "ok": True,
        "grid_size": row.get("grid_size"),
        "total_cells": row.get("total_cells"),
        "direction": direction,
        "action_summary": f"visual acuity {direction} to {row.get('grid_size')}x{row.get('grid_size')}",
        "example_action": f"sharpening my photon grid to {row.get('grid_size')}x{row.get('grid_size')}",
    }


# ── Swimmer chorus orchestrator ─────────────────────────────────────────────
_SWIMMERS = [
    _handle_camera_switch,
    _handle_resolution,
]


def detect_and_execute(text: str, stt_conf: float = 1.0) -> Optional[dict]:
    """
    Detect EXECUTE trigger in text, parse command context, run the effector.
    Returns a result dict (with response_seed for Alice) or None.

    This gate bypasses ALL media/YouTube filters.
    Delegates to swarm_owner_camera_commands — the real stigmergic unified field
    (swarm_camera_target + swarm_visual_acuity_target).
    """
    if not _TRIGGER_RE.search(text or ""):
        return None

    clean = " ".join(str(text).split())

    # Delegate to the real stigmergic organ — fully connected to the unified field
    try:
        from System.swarm_owner_camera_commands import (
            handle_owner_camera_command,
            summary_for_prompt,
        )
        row = handle_owner_camera_command(clean, state_dir=_STATE, write=True)
        if row is None:
            # EXECUTE fired but no recognizable command — acknowledge it
            return {
                "effector": "unknown",
                "ok": False,
                "actions": [],
                "action_summary": "EXECUTE heard but no camera/resolution command found in context",
                "response_seed": (
                    "EXECUTE_RECEIPT: EXECUTE was triggered but the command context "
                    "wasn't recognized. Ask the primary operator to clarify."
                ),
            }
        # Use the stigmergic organ's own response seed
        response_seed = (
            "EXECUTE_RECEIPT: command was parsed and receipts were written by my local sensor-control organ.\n"
            + summary_for_prompt(row)
        )
        result = {
            "effector": "execute_chorus",
            "ok": True,
            "actions": row.get("actions", []),
            "owner_eye_command": row,
            "action_summary": "; ".join(row.get("actions", [])) or "owner eye command",
            "response_seed": response_seed,
        }
    except Exception as e:
        return {
            "effector": "error",
            "ok": False,
            "actions": [],
            "action_summary": f"EXECUTE reflex error: {e}",
            "response_seed": f"EXECUTE_RECEIPT: error in stigmergic organ: {e}",
        }

    # Write EXECUTE-specific receipt
    try:
        log = _STATE / "execute_reflex.jsonl"
        entry = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "trigger": "EXECUTE",
            "text_preview": clean[:200],
            "stt_conf": stt_conf,
            "effector": result.get("effector"),
            "ok": result.get("ok"),
            "actions": result.get("actions", []),
            "action_summary": result.get("action_summary", "")[:200],
        }
        with open(log, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

    return result


__all__ = ["TRIGGER_WORD", "detect_and_execute", "RESPONSE_SEED"]
