#!/usr/bin/env python3
"""Alice Browser Grok paste-from-clipboard command organ.

After Alice copies her Global Chat post, she pastes clipboard into Grok composer
and optionally sends — her response turn inside Alice Browser.
"""
from __future__ import annotations

import json
import re
import hashlib
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "ALICE_BROWSER_GROK_PASTE_CLIPBOARD_COMMAND_V1"
RESULT_TRUTH_LABEL = "ALICE_BROWSER_GROK_PASTE_CLIPBOARD_RESULT_V1"

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_COMMAND_FILE = "alice_browser_grok_paste_clipboard_command.json"
_COMMAND_LEDGER = "alice_browser_grok_paste_clipboard_commands.jsonl"
_GROK_THREAD_RE = re.compile(r"https?://(?:www\.)?grok\.com/c/([^/?#]+)", re.IGNORECASE)
_BAD_NO_RECEIPT_FALLBACK_RE = re.compile(
    r"\bi\s+will\s+not\s+claim\b.{0,100}\b(?:effector|action)\s+receipt\b",
    re.IGNORECASE | re.DOTALL,
)


def state_dir_path(state_dir: Optional[Path | str] = None) -> Path:
    if state_dir is None:
        return _STATE
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else p / ".sifta_state"


def command_path(state_dir: Optional[Path | str] = None) -> Path:
    return state_dir_path(state_dir) / _COMMAND_FILE


def grok_thread_id(url: str) -> str:
    """Return the Grok conversation id embedded in a URL, if present."""
    m = _GROK_THREAD_RE.search(str(url or ""))
    return m.group(1) if m else ""


def needs_target_thread_navigation(current_url: str, target_url: str) -> bool:
    """Paste-back must stay in the intended Grok conversation, not the root composer."""
    target_thread = grok_thread_id(target_url)
    if not target_thread:
        return False
    return grok_thread_id(current_url) != target_thread


def read_system_clipboard_text() -> str:
    """Best-effort macOS clipboard read for freezing staged paste payloads."""
    try:
        out = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
        if out.returncode == 0:
            return str(out.stdout or "").strip()
    except Exception:
        pass
    return ""


def clean_text_sha256(text: str) -> str:
    return hashlib.sha256(" ".join((text or "").split()).encode("utf-8")).hexdigest()


def looks_like_bad_no_receipt_action_payload(text: str) -> bool:
    """Detect old fallback prose as a bad action payload, not as Alice's reply."""
    clean = " ".join(str(text or "").split())
    if not clean:
        return False
    return bool(_BAD_NO_RECEIPT_FALLBACK_RE.search(clean)) and len(clean) < 180


def stage_grok_paste_clipboard_command(
    *,
    owner_text: str = "",
    press_enter: bool = True,
    url: str = "https://grok.com/",
    source: str = "grok_5loop_orchestrator",
    from_talk_paste_receipt: str = "",
    loop: int = 0,
    clipboard_text: str = "",
    state_dir: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Stage Alice Browser hand: paste system clipboard into Grok composer."""
    sd = state_dir_path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    frozen_clipboard = str(clipboard_text or read_system_clipboard_text() or "").strip()
    bad_action_payload = looks_like_bad_no_receipt_action_payload(frozen_clipboard)
    if bad_action_payload:
        frozen_clipboard = ""
    row: dict[str, Any] = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": time.time(),
        "receipt_id": f"alice-browser-grok-paste-{uuid.uuid4().hex[:12]}",
        "action": "alice_browser_grok_paste_clipboard",
        "source": source,
        "url": url,
        "press_enter": bool(press_enter),
        "owner_text_preview": " ".join((owner_text or "").split())[:300],
        "from_talk_paste_receipt": str(from_talk_paste_receipt or ""),
        "loop": int(loop or 0),
        "status": "bad_action_receipt_no_paste_attempted" if bad_action_payload else "staged",
        "clipboard_text": frozen_clipboard,
        "clipboard_sha256": clean_text_sha256(frozen_clipboard) if frozen_clipboard else "",
        "clipboard_chars": len(frozen_clipboard),
        "payload_frozen_at_stage": True,
    }
    if bad_action_payload:
        row["bad_action_reason"] = "stale_no_receipt_fallback_payload"
    command_path(sd).write_text(
        json.dumps(row, ensure_ascii=False, sort_keys=True),
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


def append_grok_paste_result(row: dict[str, Any], *, state_dir: Optional[Path | str] = None) -> None:
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
    for name in ("alice_browser_grok_paste_clipboard_results.jsonl", "browser_action_diary.jsonl", "work_receipts.jsonl"):
        try:
            with (sd / name).open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            pass


__all__ = [
    "TRUTH_LABEL",
    "RESULT_TRUTH_LABEL",
    "append_grok_paste_result",
    "command_path",
    "clean_text_sha256",
    "grok_thread_id",
    "looks_like_bad_no_receipt_action_payload",
    "needs_target_thread_navigation",
    "read_system_clipboard_text",
    "stage_grok_paste_clipboard_command",
]
