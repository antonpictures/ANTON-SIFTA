#!/usr/bin/env python3
"""Alice Talk self-type command organ.

Orchestrator (Grok terminal) stages text for Alice to type into her visible
Talk input box. Talk widget consumes the command file and calls
``alice_type_in_own_box`` — same path as owner-quoted self-type requests.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "ALICE_SELF_TYPE_TO_TALK_COMMAND_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_COMMAND_FILE = "alice_self_type_to_talk_command.json"
_COMMAND_LEDGER = "alice_self_type_to_talk_commands.jsonl"


def state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def command_path(state_dir: Optional[Path | str] = None) -> Path:
    return state_dir_path(state_dir) / _COMMAND_FILE


def stage_alice_self_type_to_talk_command(
    text: str,
    *,
    owner_text: str = "",
    send: bool = True,
    reason: str = "orchestrator_staged_transfer",
    source: str = "grok_5loop_orchestrator",
    from_grok_receipt: str = "",
    loop: int = 0,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Write the Talk self-type command file and append command ledgers."""
    payload = " ".join((text or "").split())
    if not payload:
        raise ValueError("stage_alice_self_type_to_talk_command requires non-empty text")
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "receipt_id": f"alice-talk-self-type-cmd-{uuid.uuid4().hex[:12]}",
        "action": "alice_self_type_to_talk_command",
        "source": source,
        "send": bool(send),
        "reason": reason,
        "text_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "text_preview": payload[:240],
        "owner_text_preview": " ".join((owner_text or "").split())[:300],
        "from_grok_receipt": str(from_grok_receipt or ""),
        "loop": int(loop or 0),
        "status": "staged",
    }
    command = dict(row)
    command["text"] = payload
    command_path(sd).write_text(
        json.dumps(command, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    line = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    for name in (_COMMAND_LEDGER, "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass
    return row


__all__ = [
    "TRUTH_LABEL",
    "command_path",
    "stage_alice_self_type_to_talk_command",
]