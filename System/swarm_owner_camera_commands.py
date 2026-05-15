#!/usr/bin/env python3
"""Owner-spoken camera control commands.

This organ is intentionally small: it only recognizes direct owner commands
that choose between the known physical eyes and writes the canonical
active_saccade_target.json receipt. It does not claim frames are flowing; the
sensor truth context still decides that from visual/camera receipts.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = "owner_camera_commands.jsonl"


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


_OWNER_CAMERA_LOCK_LEASE_S = max(300.0, _float_env("SIFTA_OWNER_CAMERA_LOCK_LEASE_S", 1800.0))
_OWNER_CAMERA_LOCK_PRIORITY = _int_env("SIFTA_OWNER_CAMERA_LOCK_PRIORITY", 95)

_SWITCH_RE = re.compile(
    r"\b(?:switch|change|move|route|turn|look|focus|use|select|activate|open)\b"
    r"[\w\s,.'’:-]{0,80}\b(?:camera|eye|front|side|macbook|usb|logitech|iphone|obs)\b",
    re.IGNORECASE,
)
_ACUITY_RE = re.compile(r"\b(?:camera\s+)?(?:resolution|acuity|quality|sharpness|photon\s+density)\b", re.IGNORECASE)
_ACUITY_UP_RE = re.compile(r"\b(?:increase|up|higher|more|boost|improve|raise|sharpen|one\s+step)\b", re.IGNORECASE)
_ACUITY_DOWN_RE = re.compile(r"\b(?:decrease|down|lower|less|reduce|drop|coarser)\b", re.IGNORECASE)

_SELF_ACTION_RE = re.compile(
    r"^\s*(?:"
    r"i\s*(?:['’]ll|will|am\s+going\s+to)|"
    r"i\s+(?:can|would|should)|"
    r"we\s*(?:['’]ll|will|are\s+going\s+to)"
    r")\s+(?:switch|change|move|route|turn|look|focus|use|select|activate|open|increase|decrease|raise|lower)\b",
    re.IGNORECASE,
)


def _target_from_text(text: str, *, current: dict[str, Any] | None = None) -> dict[str, Any] | None:
    clean = " ".join(str(text or "").replace("’", "'").split()).casefold()
    if _SELF_ACTION_RE.search(clean):
        return None
    if not _SWITCH_RE.search(clean):
        return None
    if re.search(r"\b(?:front|macbook|built[- ]?in|close)\b", clean):
        return {
            "name": "MacBook Pro Camera",
            "index": 1,
            "role": "front_camera",
        }
    if re.search(r"\b(?:side|usb|logitech|room|external)\b", clean):
        return {
            "name": "USB Camera VID:1133 PID:2081",
            "index": 0,
            "role": "side_camera",
        }
    if re.search(r"\biphone\b", clean):
        return {
            "name": "iPhone Camera",
            "index": 3,
            "role": "iphone_camera",
        }
    if re.search(r"\bobs\b", clean):
        return {
            "name": "OBS Virtual Camera",
            "index": 2,
            "role": "obs_virtual_camera",
        }
    # Generic owner command: "switch the camera" must still write a real
    # target receipt. Toggle the two physical eyes the owner is testing now.
    if re.search(r"\b(?:switch|change|toggle|cycle)\b", clean) and re.search(r"\b(?:camera|eye)\b", clean):
        current = current or {}
        current_name = " ".join(str(current.get("name") or "").casefold().split())
        current_index = current.get("index")
        if current_index == 1 or "macbook" in current_name:
            return {
                "name": "USB Camera VID:1133 PID:2081",
                "index": 0,
                "role": "side_camera",
                "toggle_from": current.get("name") or current_index,
            }
        return {
            "name": "MacBook Pro Camera",
            "index": 1,
            "role": "front_camera",
            "toggle_from": current.get("name") or current_index,
        }
    return None


def _acuity_direction_from_text(text: str) -> str | None:
    clean = " ".join(str(text or "").replace("’", "'").split()).casefold()
    if _SELF_ACTION_RE.search(clean):
        return None
    if not _ACUITY_RE.search(clean):
        return None
    if _ACUITY_DOWN_RE.search(clean):
        return "decrease"
    if _ACUITY_UP_RE.search(clean) or re.search(r"\b(?:resolution|acuity|quality|sharpness)\b", clean):
        return "increase"
    return None


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def handle_owner_camera_command(
    text: str,
    *,
    state_dir: Path | str = _STATE,
    write: bool = True,
) -> dict[str, Any] | None:
    current: dict[str, Any] | None = None
    try:
        from System.swarm_camera_target import read_target

        current = read_target()
    except Exception:
        current = None

    target = _target_from_text(text, current=current)
    acuity_direction = _acuity_direction_from_text(text)
    if not target and not acuity_direction:
        return None

    written: dict[str, Any] | None = None
    if target and write:
        from System.swarm_camera_target import write_target

        written = write_target(
            name=target["name"],
            index=target["index"],
            writer="owner_camera_command",
            priority=_OWNER_CAMERA_LOCK_PRIORITY,
            lease_s=_OWNER_CAMERA_LOCK_LEASE_S,
            respect_lease=True,
        )

    acuity_written: dict[str, Any] | None = None
    if acuity_direction:
        try:
            from System.swarm_visual_acuity_target import step_acuity

            acuity_written = step_acuity(
                acuity_direction,
                state_dir=state_dir,
                writer="owner_camera_command",
                source_text=text,
                write_ledger=write,
            )
        except Exception as e:
            acuity_written = {
                "ok": False,
                "error": str(e),
                "direction": acuity_direction,
            }

    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "OWNER_CAMERA_COMMAND_V1",
        "source": "owner_voice_or_text",
        "text_preview": str(text or "")[:220],
        "target": target,
        "camera_target": written,
        "acuity_target": acuity_written,
        "actions": [
            action
            for action in (
                "camera_target" if target else "",
                "visual_acuity" if acuity_direction else "",
            )
            if action
        ],
        "note": (
            "Owner eye command wrote receipt-backed camera and/or visual acuity targets; "
            "sensor truth still decides whether frames are flowing."
        ),
    }
    if write:
        _append_jsonl(Path(state_dir) / _LEDGER, row)
    return row


def summary_for_prompt(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    written = row.get("camera_target") if isinstance(row.get("camera_target"), dict) else {}
    name = target.get("name") or written.get("name") or "unknown"
    role = target.get("role") or "unknown"
    index = target.get("index", written.get("index"))
    acuity = row.get("acuity_target") if isinstance(row.get("acuity_target"), dict) else {}
    lines = ["OWNER EYE COMMAND RECEIPT:"]
    if target or written:
        lines.append(f"- requested_eye={role} target={name} index={index}")
    if acuity:
        lines.append(
            f"- visual_acuity={acuity.get('grid_size')}x{acuity.get('grid_size')} "
            f"cells={acuity.get('total_cells')} source_thumb={acuity.get('source_thumb_px')}px"
        )
    lines.append(
        "- receipts written before speech; sensor truth confirms live frames from visual_stigmergy."
    )
    lines.append(
        "RESPONSE SEED (one example only; do not copy verbatim): "
        "I hear you — eye command is in the ledger; I'll answer from that receipt, not from prompt-stage directions."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    print(json.dumps(handle_owner_camera_command(" ".join(sys.argv[1:]), write=False), indent=2))
