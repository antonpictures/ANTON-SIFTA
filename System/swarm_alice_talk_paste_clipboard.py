#!/usr/bin/env python3
"""Alice Talk paste-from-clipboard command organ.

Alice reads the system clipboard (after she clicked Grok COPY) and pastes into
her visible Talk input box, then sends. Receipt proves clipboard_sha256.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "ALICE_TALK_PASTE_CLIPBOARD_COMMAND_V1"
RESULT_TRUTH_LABEL = "ALICE_TALK_PASTE_CLIPBOARD_RESULT_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_COMMAND_FILE = "alice_talk_paste_clipboard_command.json"
_COMMAND_LEDGER = "alice_talk_paste_clipboard_commands.jsonl"


def state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def command_path(state_dir: Optional[Path | str] = None) -> Path:
    return state_dir_path(state_dir) / _COMMAND_FILE


def stage_talk_paste_clipboard_command(
    *,
    owner_text: str = "",
    send: bool = True,
    reason: str = "grok_copy_to_global_chat",
    source: str = "grok_5loop_orchestrator",
    from_grok_copy_receipt: str = "",
    expected_clipboard_sha256: str = "",
    clipboard_text: str = "",
    loop: int = 0,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Stage Alice Talk hand: mirror Grok COPY into Talk and send.

    If clipboard_text is provided, it is the frozen payload from the browser COPY
    receipt. The consumer must use it instead of reading the global OS clipboard.
    """
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    frozen_payload = " ".join((clipboard_text or "").split()).strip()
    payload_sha = clipboard_sha256(frozen_payload) if frozen_payload else str(expected_clipboard_sha256 or "")
    row: dict[str, Any] = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "receipt_id": f"alice-talk-paste-clip-{uuid.uuid4().hex[:12]}",
        "action": "alice_talk_paste_clipboard",
        "source": source,
        "send": bool(send),
        "reason": reason,
        "owner_text_preview": " ".join((owner_text or "").split())[:300],
        "from_grok_copy_receipt": str(from_grok_copy_receipt or ""),
        "expected_clipboard_sha256": payload_sha,
        "clipboard_sha256": payload_sha,
        "clipboard_chars": len(frozen_payload),
        "payload_frozen_at_stage": bool(frozen_payload),
        "transport": "direct_payload" if frozen_payload else "system_clipboard",
        "loop": int(loop or 0),
        "status": "staged",
    }
    command = dict(row)
    if frozen_payload:
        command["clipboard_text"] = frozen_payload[:12000]
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


def append_talk_paste_result(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
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
    for name in ("alice_talk_paste_clipboard_results.jsonl", "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass


def clipboard_sha256(text: str) -> str:
    return hashlib.sha256(" ".join((text or "").split()).encode("utf-8")).hexdigest()


__all__ = [
    "TRUTH_LABEL",
    "RESULT_TRUTH_LABEL",
    "append_talk_paste_result",
    "clipboard_sha256",
    "command_path",
    "stage_talk_paste_clipboard_command",
]
