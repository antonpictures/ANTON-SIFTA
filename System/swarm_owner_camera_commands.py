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
_USB_ACCESSORY_RE = re.compile(
    r"\busb\s+(?:cord|cable|wire|charger|adapter|hub|drive|stick|dongle|plug)\b"
    r"|"
    r"\b(?:cord|cable|wire|charger|adapter|hub|drive|stick|dongle|plug)\s+(?:for\s+)?usb\b",
    re.IGNORECASE,
)
_CAMERA_WORD_RE = re.compile(
    r"\b(?:camera|eye|webcam|logitech|external\s+camera|side\s+camera|macbook\s+camera|iphone\s+camera|obs\s+camera)\b",
    re.IGNORECASE,
)

_SELF_ACTION_RE = re.compile(
    r"^\s*(?:"
    r"i\s*(?:['’]ll|will|am\s+going\s+to)|"
    r"i\s+(?:can|would|should)|"
    r"we\s*(?:['’]ll|will|are\s+going\s+to)"
    r")\s+(?:switch|change|move|route|turn|look|focus|use|select|activate|open|increase|decrease|raise|lower)\b",
    re.IGNORECASE,
)
_EMBODIMENT_CAMERA_TEACHING_RE = re.compile(
    r"\bpointed\s+at\b"
    r"|\bpointing\s+at\b"
    r"|\bsee\s+for\s+yourself\b"
    r"|\bso\s+you\s+can\s+see\b"
    r"|\byour\s+screen\s+body\b"
    r"|\bscreen\s+body\b",
    re.IGNORECASE,
)
_DIRECT_CAMERA_COMMAND_RE = re.compile(
    r"^\s*(?:switch|change|use|select|activate|move|route|turn|focus)\s+(?:to\s+)?(?:the\s+)?"
    r"(?:usb|logitech|side|external|macbook|front|iphone|obs|camera|eye)\b",
    re.IGNORECASE,
)


def is_embodiment_camera_teaching_turn(text: str) -> bool:
    """Owner is teaching embodiment/vision — not issuing a short camera switch command."""
    clean = " ".join(str(text or "").replace("’", "'").split())
    if not clean:
        return False
    if _DIRECT_CAMERA_COMMAND_RE.search(clean):
        return False
    if _EMBODIMENT_CAMERA_TEACHING_RE.search(clean):
        return True
    if len(clean.split()) >= 14 and re.search(
        r"\b(?:beautiful|good\s+job|deterministic|unacceptable|see\s+for\s+yourself)\b",
        clean,
        re.IGNORECASE,
    ):
        return bool(_CAMERA_WORD_RE.search(clean))
    return False


def _owner_eye_target() -> dict[str, Any]:
    from System.swarm_eye_registry import live_owner_eye_device

    eye = live_owner_eye_device()
    return {
        "name": str(eye.get("name") or ""),
        "index": eye.get("index"),
        "unique_id": eye.get("unique_id"),
        "role": "front_camera",
    }


def _world_eye_target() -> dict[str, Any] | None:
    from System.swarm_eye_registry import live_world_eye_device

    eye = live_world_eye_device()
    if not eye.get("name"):
        return None
    return {
        "name": str(eye.get("name")),
        "index": eye.get("index"),
        "unique_id": eye.get("unique_id"),
        "role": "side_camera",
    }


def _is_owner_eye_name(name: str) -> bool:
    try:
        from System.swarm_camera_target import is_builtin_owner_camera

        return bool(is_builtin_owner_camera(name))
    except Exception:
        return "macbook" in str(name or "").casefold() or "facetime" in str(name or "").casefold()


def _target_from_text(text: str, *, current: dict[str, Any] | None = None) -> dict[str, Any] | None:
    clean = " ".join(str(text or "").replace("’", "'").split()).casefold()
    if is_embodiment_camera_teaching_turn(text):
        return None
    if _SELF_ACTION_RE.search(clean):
        return None
    # r522: "I'm going to use a USB cord" is owner self-narration about a cable,
    # not an order to switch Alice's eye to the USB camera. USB by itself is too
    # ambiguous when accessory words are present; require an actual camera/eye word.
    if _USB_ACCESSORY_RE.search(clean) and not _CAMERA_WORD_RE.search(clean):
        return None
    if not _SWITCH_RE.search(clean):
        return None
    if re.search(r"\b(?:front|macbook|built[- ]?in|close)\b", clean):
        return _owner_eye_target()
    if re.search(r"\b(?:side|usb|logitech|room|external)\b", clean):
        return _world_eye_target()
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
        current_name = str(current.get("name") or "")
        if _is_owner_eye_name(current_name):
            world = _world_eye_target()
            if world is None:
                return None
            world["toggle_from"] = current.get("name") or current.get("index")
            return world
        owner = _owner_eye_target()
        owner["toggle_from"] = current.get("name") or current.get("index")
        return owner
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
            index=target.get("index"),
            unique_id=target.get("unique_id"),
            writer="owner_camera_command",
            priority=_OWNER_CAMERA_LOCK_PRIORITY,
            lease_s=_OWNER_CAMERA_LOCK_LEASE_S,
            respect_lease=True,
        )
        if written:
            target = dict(target)
            for key in ("name", "index", "unique_id"):
                if written.get(key) is not None:
                    target[key] = written.get(key)

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
