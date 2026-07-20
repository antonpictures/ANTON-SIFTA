#!/usr/bin/env python3
"""Mirror a known Alice browser line into Global Chat (no brain, no Ioan label).

Orchestrator stages the exact text Alice typed in browser — it does NOT read
Grok page snapshots. Separate from GROK MIRROR (clipboard after COPY click).
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "ALICE_TALK_MIRROR_LINE_COMMAND_V1"
RESULT_TRUTH_LABEL = "ALICE_TALK_MIRROR_LINE_RESULT_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_COMMAND_FILE = "alice_talk_mirror_line_command.json"
_COMMAND_LEDGER = "alice_talk_mirror_line_commands.jsonl"


def state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def command_path(state_dir: Optional[Path | str] = None) -> Path:
    return state_dir_path(state_dir) / _COMMAND_FILE


def stage_talk_mirror_line_command(
    text: str,
    *,
    turn: int = 0,
    owner_text: str = "",
    from_browser_receipt: str = "",
    source: str = "visible_grok_dialogue",
    speaker: str = "alice",
    site: str = "",
    browser_url: str = "",
    schedule_reply: bool = False,
    target_rounds: int = 0,
    final: bool = False,
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    payload = " ".join((text or "").split())
    if not payload:
        raise ValueError("stage_talk_mirror_line_command requires non-empty text")
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "receipt_id": f"alice-talk-mirror-line-{uuid.uuid4().hex[:12]}",
        "action": "alice_talk_mirror_line",
        "source": source,
        "turn": int(turn or 0),
        "text_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "text_preview": payload[:240],
        "owner_text_preview": " ".join((owner_text or "").split())[:300],
        "from_browser_receipt": str(from_browser_receipt or ""),
        "speaker": str(speaker or "alice"),
        "site": str(site or ""),
        "browser_url": str(browser_url or ""),
        "schedule_reply": bool(schedule_reply),
        "target_rounds": int(target_rounds or 0),
        "final": bool(final),
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


def append_talk_mirror_line_result(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    out = dict(row)
    out.setdefault("schema", RESULT_TRUTH_LABEL)
    out.setdefault("truth_label", RESULT_TRUTH_LABEL)
    out.setdefault("ts", time.time())
    line = json.dumps(out, ensure_ascii=False, sort_keys=True) + "\n"
    for name in ("alice_talk_mirror_line_results.jsonl", "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass


__all__ = [
    "TRUTH_LABEL",
    "RESULT_TRUTH_LABEL",
    "append_talk_mirror_line_result",
    "command_path",
    "stage_talk_mirror_line_command",
]
