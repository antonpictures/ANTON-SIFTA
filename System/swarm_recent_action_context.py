#!/usr/bin/env python3
"""Recent action working memory for Alice's live cortex prompt.

This is deliberately small and receipt-backed. It gives the LLM the same
short-term action memory a human uses when asked "did you execute?" seconds
after a tool run, without hardcoding a response branch.
"""

from __future__ import annotations

from collections import deque
import json
import re
import time
from pathlib import Path
from typing import Any


_MATRIX_ACTIONS = {
    "grok_delegation_queue_claimed",
    "matrix_command_receipt",
    "write_command",
    "grok_resume_screen_observed",
    "grok_resume_choice_nudge",
    "grok_resume_ctrl_s",
    "grok_resume_enter",
    "grok_resume_ready_for_prompt",
    "grok_result_capture_start",
    "grok_delegation",
    "grok_permission_autoapprove",
    "grok_result",
    "grok_result_capture_failed",
    "captured_framebuffer",
}

_DEFAULT_TAIL_BYTES = 8 * 1024 * 1024


def _tail_jsonl(
    path: Path,
    max_rows: int = 120,
    *,
    max_bytes: int = _DEFAULT_TAIL_BYTES,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: deque[dict[str, Any]] = deque(maxlen=max(1, int(max_rows)))
    try:
        size = path.stat().st_size
        start = max(0, size - max(1024, int(max_bytes)))
        with path.open("rb") as f:
            f.seek(start)
            if start:
                f.readline()
            for raw in f:
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except Exception:
        return []
    return list(rows)


def _clean_text(value: Any, limit: int = 180) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: max(0, limit - 1)].rstrip() + "..."
    return text


def _time_label(ts: Any, now: float) -> str:
    try:
        t = float(ts)
    except Exception:
        return "recent"
    age = max(0.0, now - t)
    if age < 90:
        return f"{int(age)}s ago"
    if age < 3600:
        return f"{int(age // 60)}m ago"
    return time.strftime("%H:%M:%S", time.localtime(t))


def _matrix_summary(row: dict[str, Any], *, now: float) -> str:
    action = str(row.get("action") or row.get("kind") or "").casefold()
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    text = _clean_text(row.get("text"), 220)
    when = _time_label(row.get("ts"), now)

    if action == "grok_delegation_queue_claimed":
        receipt = _clean_text(payload.get("receipt") or "", 64)
        return f"{when}: Grok delegation queued/claimed receipt={receipt}."
    if action == "matrix_command_receipt":
        receipt = _clean_text(payload.get("trace_id") or row.get("trace_id") or "", 64)
        commands = payload.get("commands")
        if isinstance(commands, list):
            cmd_text = ", ".join(str(c) for c in commands[:5])
        else:
            cmd_text = text
        return f"{when}: command receipt {receipt[:12]} for {cmd_text}."
    if action == "write_command":
        target = _clean_text(payload.get("target") or row.get("focused_cli") or "pty", 32)
        command = _clean_text(payload.get("command") or text, 80)
        return f"{when}: sent command to {target}: {command}."
    if action == "grok_resume_screen_observed":
        state = _clean_text(payload.get("state") or "", 40)
        return f"{when}: observed Grok screen state={state}; waiting for stable framebuffer."
    if action == "grok_resume_choice_nudge":
        state = _clean_text(payload.get("state") or "", 40)
        key = _clean_text(payload.get("key") or "", 30)
        decision = _clean_text(payload.get("decision") or text, 120)
        return f"{when}: decided on Grok {state}: {decision}; pressed {key}."
    if action == "grok_resume_ctrl_s":
        return f"{when}: pressed Ctrl-S on Grok main menu."
    if action == "grok_resume_enter":
        return f"{when}: pressed Enter on Grok session picker."
    if action == "grok_resume_ready_for_prompt":
        chars = payload.get("prompt_chars")
        suffix = f" ({chars} prompt chars)" if chars is not None else ""
        return f"{when}: Grok was past startup screens; queued prompt sent{suffix}."
    if action == "captured_framebuffer":
        # Round 20/21 memory doctrine: surface framebuffer captures as explicit
        # GROK_RESULT receipt lines the cortex can quote verbatim first.
        hash_text = _clean_text(
            payload.get("captured_output_hash")
            or payload.get("hash")
            or row.get("captured_output_hash")
            or "",
            48,
        )
        if not hash_text:
            m = re.search(r"hash=([a-f0-9]{8,64})", text, flags=re.IGNORECASE)
            if m:
                hash_text = m.group(1)
        chars_raw = (
            payload.get("captured_output_chars")
            or payload.get("captured_chars")
            or payload.get("chars")
            or 0
        )
        try:
            chars_i = int(chars_raw or 0)
        except Exception:
            chars_i = 0
        if chars_i <= 0:
            m = re.search(r"captured\s+(\d+)\s+chars", text, flags=re.IGNORECASE)
            if m:
                chars_i = int(m.group(1))
        span = payload.get("pty_transcript_span") or payload.get("span") or {}
        seq_s = seq_e = 0
        if isinstance(span, dict):
            try:
                seq_s = int(span.get("start_seq") or 0)
                seq_e = int(span.get("end_seq") or 0)
            except Exception:
                seq_s = seq_e = 0
        if not (seq_s or seq_e):
            m = re.search(r"seq\s+(\d+)-(\d+)", text, flags=re.IGNORECASE)
            if m:
                seq_s = int(m.group(1))
                seq_e = int(m.group(2))
        ts_label = ""
        try:
            ts_label = time.strftime("%H:%M:%S", time.localtime(float(row.get("ts") or 0.0)))
        except Exception:
            ts_label = when
        return (
            f"GROK_RESULT receipt={hash_text or 'UNKNOWN'} "
            f"captured={chars_i}chars seq={seq_s}-{seq_e} ts={ts_label}"
        )
    if action == "grok_result_capture_start":
        capture = _clean_text(payload.get("capture_id") or "", 64)
        return f"{when}: started GROK_RESULT capture {capture}."
    if action == "grok_delegation":
        chars = payload.get("chars")
        suffix = f" ({chars} chars)" if chars is not None else ""
        return f"{when}: pasted delegation into Grok{suffix}."
    if action == "grok_permission_autoapprove":
        return f"{when}: auto-approved Grok permission prompt per owner standing order."
    if action in {"grok_result", "grok_result_capture_failed"}:
        status = _clean_text(payload.get("capture_status") or ("failed" if "failed" in action else "captured"), 40)
        capture = _clean_text(payload.get("capture_id") or "", 64)
        output_hash = _clean_text(payload.get("captured_output_hash") or "", 24)
        source = _clean_text(payload.get("source") or row.get("source") or "", 48)
        answer = _clean_text(payload.get("answer") or payload.get("captured_text") or "", 160)
        return f"{when}: GROK_RESULT {status} capture_id={capture} hash={output_hash} source={source}; {answer}"
    if text:
        return f"{when}: {text}"
    return ""


def _agent_arm_summary(row: dict[str, Any], *, now: float) -> str:
    label = str(row.get("truth_label") or "")
    if label != "AGENT_ARM_LAUNCH_RESULT":
        return ""
    when = _time_label(row.get("ts"), now)
    arm = _clean_text(row.get("arm_id") or row.get("display_name") or "agent_arm", 48)
    status = _clean_text(row.get("status") or "", 48)
    receipt = _clean_text(row.get("receipt_id") or "", 64)
    ok = bool(row.get("ok"))
    duration = row.get("duration_s")
    dur = ""
    try:
        dur = f" duration={float(duration):.1f}s"
    except Exception:
        pass
    tail = _clean_text(row.get("output_tail") or row.get("stderr_tail") or "", 180)
    return f"{when}: agent arm {arm} result status={status} ok={ok} receipt={receipt}{dur}; {tail}"


def recent_action_events(state_dir: Path, *, now: float | None = None, max_rows: int = 140) -> list[str]:
    """Return compact, receipt-backed action lines ordered oldest to newest."""
    state = Path(state_dir)
    now_f = float(time.time() if now is None else now)
    events: list[tuple[float, str]] = []

    for row in _tail_jsonl(state / "matrix_terminal_process_trace.jsonl", max_rows=max_rows):
        action = str(row.get("action") or row.get("kind") or "").casefold()
        if action not in _MATRIX_ACTIONS:
            continue
        line = _matrix_summary(row, now=now_f)
        if line:
            try:
                ts = float(row.get("ts") or 0.0)
            except Exception:
                ts = 0.0
            events.append((ts, line))

    for row in _tail_jsonl(state / "agent_arm_receipts.jsonl", max_rows=80):
        line = _agent_arm_summary(row, now=now_f)
        if line:
            try:
                ts = float(row.get("ts") or 0.0)
            except Exception:
                ts = 0.0
            events.append((ts, line))

    events.sort(key=lambda item: item[0])
    seen: set[str] = set()
    out: list[str] = []
    for _ts, line in events:
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
    return out


def format_recent_action_working_memory(
    *,
    state_dir: Path,
    user_text: str = "",
    now: float | None = None,
    max_events: int = 10,
) -> str:
    events = recent_action_events(state_dir, now=now)
    if not events:
        return ""
    events = events[-max(1, int(max_events)):]
    grok_receipts = [line for line in events if line.startswith("GROK_RESULT receipt=")]
    bullets = "\n".join(f"- {line}" for line in events)
    first_sentence_rule = ""
    if grok_receipts and any(tok in _clean_text(user_text, 300).lower() for tok in ("dispatch", "code", "round", "receipt", "grok", "ask", "paste")):
        first_sentence_rule = (
            "If you answer this as an operational turn, your FIRST sentence MUST be the latest "
            "GROK_RESULT receipt line verbatim. No greeter. No mirror language.\n"
        )
    return (
        "RECENT ACTION WORKING MEMORY (receipt-backed, not generic chat):\n"
        "Use these rows as short-term memory for questions like 'did you execute?', "
        "'what just happened?', 'did Grok run?', or 'what was the receipt?'. "
        "Answer from these receipts first; if they do not prove an action, say what is missing. "
        "Do not answer those questions with a generic greeting.\n"
        f"{first_sentence_rule}"
        f"{bullets}"
    )
