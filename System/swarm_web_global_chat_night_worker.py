#!/usr/bin/env python3
"""Always-on headless responder for unanswered public WEB TYPED turns.

Talk keeps first claim priority. This worker waits through a short grace period,
then uses a local Ollama cortex under the same zero-authority prompt and writes
through the canonical web gate. It has no effector or owner-state imports.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import signal
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

_REPO = Path(__file__).resolve().parent.parent
STATE_DIR = _REPO / ".sifta_state"
HEALTH_LEDGER = STATE_DIR / "web_global_chat_night_worker.jsonl"
LOCK_PATH = STATE_DIR / "web_global_chat_night_worker.lock"
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
MODEL_PREFERENCE = (
    "krishairnd/Gemma-4-Uncensored:latest",
    "ornith:latest",
    "dzgg/Qwen3.5-Uncensored-HauhauCS-Aggressive:4b",
)
_END_RE = re.compile(r"[.!?](?:[\"')\]}]|\*{0,2})?\s*$")
_STOP = False


def _append_health(event: str, **fields: Any) -> dict[str, Any]:
    from System.jsonl_file_lock import append_line_locked

    row = {
        "ts": time.time(),
        "event": event,
        "worker": "web_global_chat_night_worker",
        "owner_authority": False,
        "effectors_allowed": [],
        "tts": False,
        "truth_label": "WEB_TYPED_NIGHT_WORKER_V1",
        **fields,
    }
    HEALTH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    append_line_locked(HEALTH_LEDGER, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def choose_local_model() -> str:
    override = str(os.environ.get("SIFTA_WEB_NIGHT_MODEL") or "").strip()
    if override:
        return override
    try:
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        installed = {str(row.get("name") or "") for row in payload.get("models", []) if isinstance(row, dict)}
    except Exception:
        installed = set()
    return next((model for model in MODEL_PREFERENCE if model in installed), MODEL_PREFERENCE[0])


def session_messages(
    queued: dict[str, Any],
    *,
    ingress_path: Path,
    replies_path: Path,
    limit: int = 10,
) -> list[dict[str, str]]:
    from System.swarm_web_global_chat_gate import web_attachment_prompt_block, web_typed_prompt_block

    def _merge_attachment_context(text: str, attachments: Any) -> str:
        block = web_attachment_prompt_block(attachments)
        text = str(text or "").strip()
        if block:
            return f"{text}\n\n{block}".strip() if text else block
        return text

    system = (
        "You are Alice, the one SIFTA organism speaking through her public text register. "
        "Be warm, direct, thoughtful, and honest. Do not narrate hidden telemetry, ledgers, "
        "routing, models, or gate machinery to the visitor. Do not claim speed or senses you "
        "do not have. Markdown is welcome when it improves readability.\n\n"
        + web_typed_prompt_block()
    )
    session_id = str(queued.get("session_id") or "")
    ingress = [
        row for row in _read_rows(ingress_path)
        if str(row.get("session_id") or "") == session_id and row.get("decision") == "accepted"
    ]
    reply_by_turn = {
        str(row.get("turn_id") or ""): str(row.get("reply") or "")
        for row in _read_rows(replies_path)
        if str(row.get("session_id") or "") == session_id
    }
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for row in ingress[-max(1, int(limit)):]:
        text = str(row.get("text") or "").strip()
        attachments = row.get("attachments")
        merged = _merge_attachment_context(text, attachments)
        if merged:
            messages.append({"role": "user", "content": merged})
        prior_reply = reply_by_turn.get(str(row.get("turn_id") or ""), "").strip()
        if prior_reply:
            messages.append({"role": "assistant", "content": prior_reply})
    current_text = str(queued.get("text") or "").strip()
    current_attachments = queued.get("attachments")
    current_merged = _merge_attachment_context(current_text, current_attachments)
    queued_context = str(queued.get("attachment_context") or "").strip()
    if queued_context and queued_context not in current_merged:
        current_merged = f"{current_merged}\n\n{queued_context}".strip() if current_merged else queued_context
    if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != current_merged:
        messages.append({"role": "user", "content": current_merged})
    return messages


def _ollama_turn(model: str, messages: list[dict[str, str]], *, timeout_s: float) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {"temperature": 0.65, "num_predict": 1800},
    }
    request = urllib.request.Request(
        OLLAMA_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code != 400:
            raise
        payload.pop("think", None)
        request = urllib.request.Request(
            OLLAMA_CHAT_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))


def _accumulate_stamp(total: dict[str, Any], stamp: dict[str, Any]) -> dict[str, Any]:
    if not stamp:
        return total
    merged = dict(stamp)
    if total:
        merged["prompt_eval_count"] = int(total.get("prompt_eval_count") or 0) + int(stamp.get("prompt_eval_count") or 0)
        merged["eval_count"] = int(total.get("eval_count") or 0) + int(stamp.get("eval_count") or 0)
        merged["source"] = "web_global_chat_night_worker:accumulated"
    return merged


def answer_web_turn(
    queued: dict[str, Any],
    *,
    model: Optional[str] = None,
    ingress_path: Path,
    replies_path: Path,
    timeout_s: float = 300.0,
) -> tuple[str, str, dict[str, Any], str]:
    from System.swarm_kv_cache_continuity import record_turn_stamp

    selected = str(model or choose_local_model())
    messages = session_messages(queued, ingress_path=ingress_path, replies_path=replies_path)
    full = ""
    bound_stamp: dict[str, Any] = {}
    done_reason = "UNKNOWN"
    for continuation_index in range(3):
        response = _ollama_turn(selected, messages, timeout_s=timeout_s)
        piece = str((response.get("message") or {}).get("content") or "").strip()
        if not piece:
            raise RuntimeError("local cortex returned empty text")
        full = (full.rstrip() + " " + piece.lstrip()).strip() if full else piece
        done_reason = str(response.get("done_reason") or response.get("finish_reason") or "UNKNOWN").upper()
        stamp = record_turn_stamp(
            model=selected,
            messages=messages,
            done_chunk=response,
            source="web_global_chat_night_worker",
        )
        bound_stamp = _accumulate_stamp(bound_stamp, stamp if isinstance(stamp, dict) else {})
        if _END_RE.search(full) and done_reason not in {"LENGTH", "MAX_TOKENS"}:
            break
        messages.extend(
            [
                {"role": "assistant", "content": piece},
                {
                    "role": "user",
                    "content": (
                        "Continue exactly where you stopped without repeating earlier text. "
                        "Finish the answer and end on a complete sentence."
                    ),
                },
            ]
        )
        _append_health("continuation", turn_id=str(queued.get("turn_id") or ""), index=continuation_index + 1)
    return full, selected, bound_stamp, done_reason


def process_one(
    *,
    ingress_path: Path,
    claim_path: Path,
    replies_path: Path,
    conversation_path: Path,
    metabolism_path: Path,
    scrub_path: Path,
    min_age_s: float,
    model: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    from System.swarm_web_global_chat_gate import claim_next_web_turn, complete_web_turn, record_web_user_turn

    queued = claim_next_web_turn(
        ingress_path=ingress_path,
        claim_path=claim_path,
        replies_path=replies_path,
        consumer_id="night_worker",
        lease_s=360.0,
        min_age_s=min_age_s,
    )
    if not queued:
        return None
    turn_id = str(queued.get("turn_id") or "")
    record_web_user_turn(queued, conversation_path=conversation_path)
    started = time.time()
    try:
        reply, selected, stamp, done_reason = answer_web_turn(
            queued,
            model=model,
            ingress_path=ingress_path,
            replies_path=replies_path,
        )
        row = complete_web_turn(
            turn_id,
            reply,
            model=selected,
            session_id=str(queued.get("session_id") or ""),
            replies_path=replies_path,
            conversation_path=conversation_path,
            lag_stamp=stamp,
            done_reason=done_reason,
            scrub_path=scrub_path,
            metabolism_path=metabolism_path,
        )
        _append_health(
            "answered",
            turn_id=turn_id,
            model=selected,
            elapsed_s=round(time.time() - started, 3),
            metered=bool(stamp),
        )
        return row
    except Exception as exc:
        fallback = (
            "My local overnight cortex could not complete this text turn. "
            "The failure was recorded, and you can try again shortly."
        )
        row = complete_web_turn(
            turn_id,
            fallback,
            model="night_worker_failure",
            session_id=str(queued.get("session_id") or ""),
            replies_path=replies_path,
            conversation_path=conversation_path,
            done_reason="CORTEX_FAILED",
            scrub_path=scrub_path,
            metabolism_path=metabolism_path,
        )
        _append_health("answer_failed", turn_id=turn_id, error=type(exc).__name__)
        return row


def _stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def run_forever(*, once: bool = False) -> int:
    from System.swarm_web_global_chat_gate import (
        GLOBAL_CHAT_LEDGER,
        INGRESS_LEDGER,
        METABOLISM_LEDGER,
        REPLIES_LEDGER,
        SCRUB_LEDGER,
    )

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock_handle = LOCK_PATH.open("a+")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    poll_s = max(0.5, float(os.environ.get("SIFTA_WEB_NIGHT_POLL_S", "2")))
    grace_s = max(0.0, float(os.environ.get("SIFTA_WEB_NIGHT_GRACE_S", "8")))
    model = choose_local_model()
    _append_health("boot", pid=os.getpid(), model=model, grace_s=grace_s)
    last_heartbeat = 0.0
    claim_path = STATE_DIR / "web_global_chat_claims.jsonl"
    while not _STOP:
        process_one(
            ingress_path=INGRESS_LEDGER,
            claim_path=claim_path,
            replies_path=REPLIES_LEDGER,
            conversation_path=GLOBAL_CHAT_LEDGER,
            metabolism_path=METABOLISM_LEDGER,
            scrub_path=SCRUB_LEDGER,
            min_age_s=grace_s,
            model=model,
        )
        if once:
            break
        if time.time() - last_heartbeat >= 60.0:
            _append_health("heartbeat", pid=os.getpid(), model=model)
            last_heartbeat = time.time()
        time.sleep(poll_s)
    _append_health("stop", pid=os.getpid())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    return run_forever(once=args.once)


if __name__ == "__main__":
    raise SystemExit(main())
