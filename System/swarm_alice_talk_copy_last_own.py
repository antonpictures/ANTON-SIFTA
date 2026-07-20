#!/usr/bin/env python3
"""Alice Talk copy-last-own-message command organ.

Alice copies her most recent Global Chat post (the Grok transfer she just sent)
to the system clipboard for paste-back into Grok browser composer.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "ALICE_TALK_COPY_LAST_OWN_MESSAGE_COMMAND_V1"
RESULT_TRUTH_LABEL = "ALICE_TALK_COPY_LAST_OWN_MESSAGE_RESULT_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_COMMAND_FILE = "alice_talk_copy_last_own_command.json"
_COMMAND_LEDGER = "alice_talk_copy_last_own_commands.jsonl"


def state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def command_path(state_dir: Optional[Path | str] = None) -> Path:
    return state_dir_path(state_dir) / _COMMAND_FILE


def stage_talk_copy_last_own_command(
    *,
    owner_text: str = "",
    source: str = "grok_5loop_orchestrator",
    from_talk_paste_receipt: str = "",
    from_grok_mirror_receipt: str = "",
    copy_role: str = "",
    copy_text: str = "",
    paste_to_browser_after_copy: bool = False,
    browser_url: str = "",
    loop: int = 0,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Stage Alice Talk hand: copy her last own chat message to clipboard."""
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "receipt_id": f"alice-talk-copy-own-{uuid.uuid4().hex[:12]}",
        "action": "alice_talk_copy_last_own_message",
        "source": source,
        "owner_text_preview": " ".join((owner_text or "").split())[:300],
        "from_talk_paste_receipt": str(from_talk_paste_receipt or ""),
        "from_grok_mirror_receipt": str(from_grok_mirror_receipt or ""),
        "copy_role": str(copy_role or ""),
        "copy_text_preview": " ".join((copy_text or "").split())[:240],
        "copy_text_sha256": hashlib.sha256(" ".join((copy_text or "").split()).encode("utf-8")).hexdigest()
        if (copy_text or "").strip()
        else "",
        "paste_to_browser_after_copy": bool(paste_to_browser_after_copy),
        "browser_url": str(browser_url or ""),
        "loop": int(loop or 0),
        "status": "staged",
    }
    command = dict(row)
    payload = " ".join((copy_text or "").split())
    if payload:
        command["copy_text"] = payload[:8000]
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


def append_talk_copy_last_own_result(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    out = dict(row)
    out.setdefault("schema", RESULT_TRUTH_LABEL)
    out.setdefault("truth_label", RESULT_TRUTH_LABEL)
    out.setdefault("ts", time.time())
    try:
        from System.swarm_alice_action_journal import append_action_journal

        journal = append_action_journal(out, state_dir=sd)
        out.setdefault("journal_ref", journal.get("journal_id") or journal.get("linked_receipt_id"))
    except Exception:
        pass
    line = json.dumps(out, ensure_ascii=False, sort_keys=True) + "\n"
    for name in ("alice_talk_copy_last_own_results.jsonl", "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass


__all__ = [
    "TRUTH_LABEL",
    "RESULT_TRUTH_LABEL",
    "append_talk_copy_last_own_result",
    "command_path",
    "stage_talk_copy_last_own_command",
]
