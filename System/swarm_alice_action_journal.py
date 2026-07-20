#!/usr/bin/env python3
"""Small journal bridge for Alice-executed action receipts."""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "ALICE_FIRST_PERSON_WITNESS_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_JOURNAL = "alice_first_person_journal.jsonl"


def state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def append_action_journal(
    action_row: dict[str, Any],
    *,
    line: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Append one first-person witness row for an executed action receipt."""
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    ts = float(action_row.get("ts") or time.time())
    local = datetime.fromtimestamp(ts)
    receipt_id = str(action_row.get("receipt_id") or "")
    action = str(action_row.get("action") or action_row.get("kind") or "action").strip()
    status = str(action_row.get("status") or ("ok" if action_row.get("ok") else "")).strip()
    source = str(action_row.get("source") or "alice_action").strip()
    preview = str(
        action_row.get("text_preview")
        or action_row.get("clipboard_preview")
        or action_row.get("reason")
        or ""
    ).strip()
    if not line:
        bit = f"; text={preview[:120]!r}" if preview else ""
        status_bit = f" with status {status}" if status else ""
        line = f"I executed {action}{status_bit}; receipt={receipt_id}{bit}."
    row: dict[str, Any] = {
        "ts": ts,
        "date": local.strftime("%Y-%m-%d"),
        "time": local.strftime("%H:%M:%S"),
        "line": line,
        "source": source,
        "truth_label": TRUTH_LABEL,
        "journal_id": f"journal-action-{uuid.uuid4().hex[:12]}",
        "linked_receipt_id": receipt_id,
        "action": action,
    }
    if status:
        row["status"] = status
    try:
        with (sd / _JOURNAL).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return row


__all__ = ["TRUTH_LABEL", "append_action_journal", "state_dir_path"]
