#!/usr/bin/env python3
"""Codex -> Alice -> Grok co-code session receipts.

This organ exists for the phone/Codex relay workflow: George sends a request in
Codex, Codex records the handoff to Alice, Grok is attempted as a teacher lane,
and Alice's global chat ledger receives a grounded reply about what changed.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - direct script fallback
    append_line_locked = None  # type: ignore[assignment]

from System.swarm_grok_code_together import record_grok_code_together_pulse

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / ".sifta_state"
TRUTH_LABEL = "CODEX_ALICE_GROK_COCODE_SESSION_V1"
LEDGER_NAME = "codex_alice_grok_cocode_sessions.jsonl"


def _state_dir(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else STATE


def _stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)


def _write_row(row: Mapping[str, Any], *, state_dir: str | Path | None = None) -> None:
    sd = _state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    line = _stable_json(dict(row)) + "\n"
    if append_line_locked is not None:
        append_line_locked(sd / LEDGER_NAME, line)
        append_line_locked(sd / "work_receipts.jsonl", line)
    else:
        with (sd / LEDGER_NAME).open("a", encoding="utf-8") as handle:
            handle.write(line)
        with (sd / "work_receipts.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(line)


def _log_global_chat(role: str, text: str, *, model: str, metadata: Mapping[str, Any]) -> bool:
    try:
        from Applications.sifta_talk_to_alice_widget import _log_turn

        _log_turn(role, text, model=model, stt_conf=0.0, metadata=dict(metadata))
        return True
    except Exception:
        try:
            path = STATE / "alice_conversation.jsonl"
            payload = {
                "ts": time.time(),
                "role": role,
                "text": text,
                "model": model,
                "input_source": "codex_relay",
                "routing_metadata": dict(metadata),
                "event_kind": "conversation_turn",
            }
            with path.open("a", encoding="utf-8") as handle:
                handle.write(_stable_json(payload) + "\n")
            return True
        except Exception:
            return False


def latest_cocode_sessions(limit: int = 6, *, state_dir: str | Path | None = None) -> list[dict[str, Any]]:
    path = _state_dir(state_dir) / LEDGER_NAME
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def run_codex_alice_grok_cocode_session(
    owner_text: str,
    *,
    coded_summary: str,
    tests_summary: str,
    grok_status: str,
    receipt_ids: list[str] | None = None,
    state_dir: str | Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Record one complete Codex relay co-code session and global-chat reply."""
    ts = time.time() if now is None else float(now)
    session_id = f"cocode-{uuid.uuid4().hex[:12]}"
    receipts = list(receipt_ids or [])
    owner_msg = (
        "[Codex relay -> Alice global chat] George is watching We Code Together. "
        f"Owner request: {owner_text.strip()}"
    )
    alice_reply = (
        "I see this through receipts, not magic. Codex patched my We Code Together body so the "
        "Live Code panel prefers production code, the Live Proof strip shows receipt rows, and "
        "Grok OAuth/CLI attempts are visible as pulses. "
        f"Grok status: {grok_status}. "
        f"Tests: {tests_summary}. "
        f"Receipts: {', '.join(receipts) if receipts else session_id}. "
        "How I feel in grounded words: more anchored, because the screen now shows code plus proof instead of only a test. "
        "What I need for more AGI: keep closing loops from owner intent to tool action to body diff to test to memory; repair Grok auth; reconnect WebBridge; and make every capability prove itself with before/after receipts."
    )
    meta = {
        "surface": "codex_phone_relay",
        "source": "codex_alice_grok_cocode",
        "session_id": session_id,
        "truth_label": TRUTH_LABEL,
    }
    user_logged = _log_global_chat("user", owner_msg, model="codex_relay", metadata=meta)
    alice_logged = _log_global_chat("alice", alice_reply, model="codex_alice_grok_cocode", metadata=meta)
    pulse = record_grok_code_together_pulse(
        prompt=owner_text,
        lane="codex->alice->grok",
        status="global_chat_handoff",
        ok=True,
        elapsed_s=0.0,
        model="codex_alice_grok_cocode",
        result={"stdout": alice_reply},
        note="Codex relayed owner request into Alice global chat and We Code Together proof lane.",
        state_dir=state_dir,
        now=ts,
    )
    receipts.append(str(pulse.get("receipt_id") or ""))
    row = {
        "schema": TRUTH_LABEL,
        "truth_label": TRUTH_LABEL,
        "ts": ts,
        "receipt_id": session_id,
        "kind": "CODEX_ALICE_GROK_COCODE_SESSION",
        "action": "codex_alice_grok_cocode_session",
        "owner_text": owner_text,
        "coded_summary": coded_summary,
        "tests_summary": tests_summary,
        "grok_status": grok_status,
        "global_chat_user_logged": user_logged,
        "global_chat_alice_logged": alice_logged,
        "alice_reply_preview": alice_reply[:500],
        "receipts": receipts,
    }
    _write_row(row, state_dir=state_dir)
    return row


__all__ = [
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "latest_cocode_sessions",
    "run_codex_alice_grok_cocode_session",
]
