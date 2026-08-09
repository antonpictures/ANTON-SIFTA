#!/usr/bin/env python3
"""Headless local mouth for explicit public WEB TYPED ``/speak`` requests."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from System.swarm_web_global_chat_gate import (
    claim_next_web_speech_request,
    complete_web_speech_request,
)

_REPO = Path(__file__).resolve().parent.parent
_STATE_DIR = _REPO / ".sifta_state"
_HEALTH_LEDGER = _STATE_DIR / "web_global_chat_speech_worker.jsonl"
_POLL_S = 0.7
_HEARTBEAT_S = 60.0


def _append(row: dict) -> None:
    try:
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        with _HEALTH_LEDGER.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"ts": time.time(), **row}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _speak(request: dict) -> None:
    request_id = str(request.get("request_id") or request.get("turn_id") or "").strip()
    text = str(request.get("text") or "").strip()
    if not request_id or not text:
        complete_web_speech_request(request_id, ok=False, error="empty_speech_request")
        return

    ok = False
    error = ""
    backend_name = "unknown"
    try:
        from System.swarm_vocal_cords import VoiceParams, get_default_backend

        backend = get_default_backend()
        backend_name = str(getattr(backend, "name", "unknown") or "unknown")
        ok = bool(backend.speak(text, VoiceParams()))
        if not ok and hasattr(backend, "last_failure_reason"):
            error = str(backend.last_failure_reason() or "speech_backend_returned_false")
        elif not ok:
            error = "speech_backend_returned_false"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    complete_web_speech_request(request_id, ok=ok, error=error)
    _append({
        "event": "WEB_TYPED_SPEECH_RUNTIME",
        "request_id": request_id,
        "backend": backend_name,
        "ok": ok,
        "error": error,
        "truth_label": "WEB_TYPED_SPEECH_RUNTIME_V1",
    })


def main() -> int:
    _append({
        "event": "worker_started",
        "pid": os.getpid(),
        "truth_label": "WEB_TYPED_SPEECH_WORKER_V1",
    })
    last_heartbeat = 0.0
    while True:
        try:
            request = claim_next_web_speech_request(consumer_id="headless_tts")
            if request:
                _speak(request)
                continue
            now = time.time()
            if now - last_heartbeat >= _HEARTBEAT_S:
                _append({
                    "event": "heartbeat",
                    "pid": os.getpid(),
                    "truth_label": "WEB_TYPED_SPEECH_WORKER_V1",
                })
                last_heartbeat = now
            time.sleep(_POLL_S)
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            _append({
                "event": "worker_error",
                "error": f"{type(exc).__name__}: {exc}",
                "truth_label": "WEB_TYPED_SPEECH_WORKER_V1",
            })
            time.sleep(2.0)


if __name__ == "__main__":
    raise SystemExit(main())
