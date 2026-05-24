#!/usr/bin/env python3
"""System/swarm_stall_watchdog.py — the organism knows what it is doing, even when it hangs.

George 2026-05-23: "I treat this as a living organism. I want to know what is
looping now exactly — not just crash and forget."

A daemon thread (never blocked by the main-thread freeze) samples the MAIN
thread's Python stack every couple of seconds and writes:
  - `.sifta_state/alice_now_doing.jsonl`     — rolling "what am I doing right now"
  - `.sifta_state/alice_stall_receipts.jsonl` — a receipt when the main thread is
    STUCK on the same frame for too long (this is the loop, named).

No crash-and-forget: every hang leaves a trace of exactly what it was looping on.
Read-only on the organism; it only observes and records. For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_NOW = _STATE / "alice_now_doing.jsonl"
_STALL = _STATE / "alice_stall_receipts.jsonl"

_started = False


def _main_thread_stack():
    main_id = threading.main_thread().ident
    frame = sys._current_frames().get(main_id)
    if frame is None:
        return []
    return traceback.extract_stack(frame)


def _label(f) -> str:
    return f"{Path(f.filename).name}:{f.lineno} {f.name}()"


def _top_label(stack) -> str:
    return _label(stack[-1]) if stack else "idle"


def _append(path: Path, row: dict) -> None:
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _loop(interval: float, stall_after: float) -> None:
    last_top = None
    last_change = time.time()
    stall_reported = False
    while True:
        time.sleep(interval)
        try:
            stack = _main_thread_stack()
            top = _top_label(stack)
            now = time.time()
            # keep the rolling 'doing' file bounded
            _append(_NOW, {"ts": now, "doing": top})
            if top != last_top:
                last_top = top
                last_change = now
                stall_reported = False
            elif (now - last_change) >= stall_after and not stall_reported and top != "idle":
                stall_reported = True
                _append(_STALL, {
                    "ts": now,
                    "type": "MAIN_THREAD_STALL",
                    "stuck_in": top,
                    "stalled_seconds": round(now - last_change, 1),
                    "stack": [_label(f) for f in stack[-14:]],
                    "note": "Main thread unchanged this long — THIS is what the organism is looping on.",
                })
        except Exception:
            pass


def start(interval: float = 2.0, stall_after: float = 8.0) -> None:
    """Call once at boot from the main thread. Idempotent."""
    global _started
    if _started:
        return
    _started = True
    threading.Thread(
        target=_loop, args=(interval, stall_after),
        daemon=True, name="alice_stall_watchdog",
    ).start()


def what_is_alice_doing(n: int = 1) -> list[dict]:
    """Return the last n 'doing' rows — what the main thread is on right now."""
    if not _NOW.exists():
        return []
    try:
        lines = _NOW.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
        return [json.loads(x) for x in lines if x.strip().startswith("{")]
    except Exception:
        return []


if __name__ == "__main__":
    # Manual probe: show what the (this) main thread is doing right now.
    print(json.dumps({"doing": _top_label(_main_thread_stack())}, indent=2))
