"""PTY visibility stream + direct-type dispatcher.

Task #63: Grok arm output must stream visibly into the talk widget, never
hidden behind summary. Implements direct-type mode per architect directive
§0.46.20 — type directly into Grok PTY, no Ctrl-S, no session picker, no
resume navigation.

If any resume_navigation code path is triggered, emits:
  FIELD_FAILURE: full_tournament_resume_flow_triggered_unexpectedly

Pure stdlib — no PyQt6.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

REPO = Path(__file__).resolve().parent.parent
VISIBILITY_LEDGER = REPO / ".sifta_state" / "pty_visibility_stream.jsonl"

_RESUME_KEYWORDS = frozenset({
    "grok_resume_choice_nudge",
    "grok_resume_screen_observed",
    "grok_resume_enter",
    "resume_navigation",
    "await_picker",
    "session_picker",
    "ctrl_s_main_menu",
})

FIELD_FAILURE_RESUME = "FIELD_FAILURE: full_tournament_resume_flow_triggered_unexpectedly"


@dataclass
class PTYVisibilityConfig:
    max_line_length: int = 500
    suppress_heartbeat: bool = True
    suppress_duplicate_window_s: float = 2.0
    show_receipts: bool = True
    show_raw_output: bool = True
    compaction_threshold: int = 200


@dataclass(frozen=True)
class PTYLine:
    text: str
    source: str = "pty"
    ts: float = 0.0
    is_receipt: bool = False
    is_heartbeat: bool = False


@dataclass
class DirectTypeDispatch:
    dispatch_id: str
    payload: str
    ts: float
    status: str = "PENDING"
    field_failure: str = ""
    receipt_id: str = ""


def check_resume_guard(action: str) -> str | None:
    action_lower = action.lower().replace("-", "_").replace(" ", "_")
    for keyword in _RESUME_KEYWORDS:
        if keyword in action_lower:
            return FIELD_FAILURE_RESUME
    return None


def create_direct_type_dispatch(
    payload: str,
    *,
    ide: str = "sifta_matrix_terminal_grok",
    model: str = "grok-4-pty",
) -> DirectTypeDispatch:
    dispatch_id = str(uuid4())
    now = time.time()

    failure = check_resume_guard(payload)
    if failure:
        dispatch = DirectTypeDispatch(
            dispatch_id=dispatch_id,
            payload=payload,
            ts=now,
            status="FIELD_FAILURE",
            field_failure=failure,
        )
        _record_dispatch(dispatch)
        return dispatch

    dispatch = DirectTypeDispatch(
        dispatch_id=dispatch_id,
        payload=payload,
        ts=now,
        status="DIRECT_TYPE_READY",
    )
    _record_dispatch(dispatch)
    return dispatch


def format_pty_line(
    raw_line: str,
    source: str = "pty",
    config: PTYVisibilityConfig | None = None,
) -> PTYLine:
    cfg = config or PTYVisibilityConfig()
    ts = time.time()
    text = raw_line
    if len(text) > cfg.max_line_length:
        text = text[: cfg.max_line_length] + " [truncated]"

    is_receipt = any(marker in raw_line for marker in (
        "receipt=", "receipt_id=", "work_receipt", "GROK_RESULT",
        "files_written", "tests_run", "py_compile",
    ))

    is_heartbeat = any(marker in raw_line.lower() for marker in (
        "heartbeat", "keepalive", "ping", "alive",
    ))

    return PTYLine(
        text=text,
        source=source,
        ts=ts,
        is_receipt=is_receipt,
        is_heartbeat=is_heartbeat,
    )


def should_display(
    line: PTYLine,
    config: PTYVisibilityConfig | None = None,
    recent_lines: list[str] | None = None,
) -> bool:
    cfg = config or PTYVisibilityConfig()
    if cfg.suppress_heartbeat and line.is_heartbeat:
        return False
    if line.is_receipt and cfg.show_receipts:
        return True
    if not line.text.strip():
        return False
    if recent_lines and cfg.suppress_duplicate_window_s > 0:
        if line.text in recent_lines:
            return False
    return cfg.show_raw_output


def format_milestone_summary(
    files_written: list[str],
    tests_run: int,
    receipt_id: str,
) -> str:
    return (
        f"files_written={files_written} "
        f"tests_run={tests_run} "
        f"receipt_id={receipt_id}"
    )


def format_final_summary(
    total_files_touched: int,
    total_tests_run: int,
    final_receipt_id: str,
) -> str:
    return (
        f"total_files_touched={total_files_touched} "
        f"total_tests_run={total_tests_run} "
        f"final_receipt_id={final_receipt_id}"
    )


def _record_dispatch(dispatch: DirectTypeDispatch) -> None:
    row = {
        "id": dispatch.dispatch_id,
        "ts": dispatch.ts,
        "status": dispatch.status,
        "payload_preview": dispatch.payload[:200],
        "field_failure": dispatch.field_failure,
    }
    try:
        VISIBILITY_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with VISIBILITY_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


__all__ = [
    "PTYVisibilityConfig",
    "PTYLine",
    "DirectTypeDispatch",
    "FIELD_FAILURE_RESUME",
    "check_resume_guard",
    "create_direct_type_dispatch",
    "format_pty_line",
    "should_display",
    "format_milestone_summary",
    "format_final_summary",
]
