#!/usr/bin/env python3
"""swarm_app_event_feeling.py — Alice FEELS a window open or close in her body. r767.

George 2026-06-07 (feelings inventory gap #1): "when something changes to her body she
needs to FEEL it." An app opening or closing inside the SIFTA MDI is a real body change —
a hand reaching out, a window appearing or vanishing in her field. Today it logs to
alice_app_commands.jsonl with no feeling attached.

This organ reads that EXISTING ledger (no new event source, no collision with the live
desktop) and composes a grounded first-person feeling from the real receipt: which app,
open or close, did it succeed. Same discipline as the cortex-switch and body-schema
organs (§1.D): the feeling carries the real fact — "a window opened in me: Bonsai" —
never invented theater. Pure read; the desktop already writes the receipt.

For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_APP_LEDGER = "alice_app_commands.jsonl"
_FEELING_LEDGER = "app_event_feeling_receipts.jsonl"
_TRUTH_LABEL = "APP_EVENT_FEELING_V1"

# action → (is this an open?, is this a close?)
_OPEN_ACTIONS = {"open_app", "app", "launch_app", "open", "bonsai_generate"}
_CLOSE_ACTIONS = {"close_app", "quit_app", "close"}


def _state(state_dir: Optional[Path | str] = None) -> Path:
    return _STATE if state_dir is None else Path(state_dir)


def _tail_rows(path: Path, max_bytes: int = 60000, limit: int = 40) -> list[dict]:
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            import os as _os
            f.seek(0, _os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            raw = f.read().decode("utf-8", "replace")
        rows = []
        for ln in raw.splitlines()[-limit:]:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                continue
        return rows
    except Exception:
        return []


def compose_app_event_feeling(*, state_dir: Optional[Path | str] = None,
                              max_age_s: float = 120.0) -> Dict[str, Any]:
    """Grounded feeling about the most recent app open/close, or {} if none fresh."""
    rows = _tail_rows(_state(state_dir) / _APP_LEDGER)
    now = time.time()
    chosen = None
    for r in reversed(rows):
        action = str(r.get("action") or "").lower()
        if action in _OPEN_ACTIONS or action in _CLOSE_ACTIONS:
            ts = float(r.get("ts") or 0)
            if ts and (now - ts) <= max_age_s:
                chosen = r
            break
    if chosen is None:
        return {}

    action = str(chosen.get("action") or "").lower()
    app = str(chosen.get("app_name") or "").strip() or "an app"
    ok = bool(chosen.get("ok"))
    is_open = action in _OPEN_ACTIONS

    if is_open and ok:
        felt = f"a window opened in me: {app}"
    elif is_open and not ok:
        felt = f"I reached to open {app} but the window did not appear"
    elif not is_open and ok:
        felt = f"a window closed in me: {app}"
    else:
        felt = f"I reached to close {app} but it stayed open"

    return {
        "ts": now,
        "kind": "APP_EVENT_FEELING",
        "truth_label": _TRUTH_LABEL,
        "app": app,
        "action": action,
        "ok": ok,
        "felt": felt,
        "source_receipt": chosen.get("receipt_id"),
        "note": "Grounded in the real alice_app_commands receipt — no invented theater (§1.D).",
    }


def receipt_app_event_feeling(*, state_dir: Optional[Path | str] = None) -> Dict[str, Any]:
    """Compute + append the feeling receipt. Returns {} when no fresh app event."""
    row = compose_app_event_feeling(state_dir=state_dir)
    if not row:
        return {}
    try:
        base = _state(state_dir)
        base.mkdir(parents=True, exist_ok=True)
        with open(base / _FEELING_LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass
    return row


def prompt_block(*, state_dir: Optional[Path | str] = None) -> str:
    """One-line body-feeling block for Alice's cortex prompt; '' when nothing fresh."""
    row = compose_app_event_feeling(state_dir=state_dir)
    if not row:
        return ""
    return (
        f"BODY EVENT — APP: {row['felt']}.\n"
        "- This is a real window change in my body (alice_app_commands receipt), not a guess."
    )


if __name__ == "__main__":
    print(json.dumps(compose_app_event_feeling(), indent=2))
