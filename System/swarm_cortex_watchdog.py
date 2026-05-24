#!/usr/bin/env python3
"""System/swarm_cortex_watchdog.py — Cortex Watchdog organ.

Brains glitch. An organism survives by recovery, continuity, and repair —
not by perfection. George 2026-05-23: the Gemma/Ollama model runner crashed
("model runner has unexpectedly stopped, ... resource limitations") while the
rest of the organism (memory, PTY, global chat, terminal) survived intact.

This organ detects a dead or stuck cortex (Ollama server down OR model runner
crashed) and recovers it WITHOUT touching the shared conversation ledger or the
live PTY — so continuity is preserved. Only the cortex *process* is repaired.

Public API
----------
  cortex_health(model=None)            -> dict   {server, runner, model, detail}
  recover_cortex(model=None)           -> dict   escalating recovery + receipts
  guard_inference(fn, retries=1)       -> Any     run fn; on cortex death recover + retry
  restart_notice()                     -> str     line Alice can speak after a recovery

Receipts -> .sifta_state/cortex_watchdog.jsonl  (crash detected + recovery result)
For the Swarm. 🐜⚡
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "cortex_watchdog.jsonl"
_OLLAMA = "http://127.0.0.1:11434"


def _resolve_model(model: str | None = None) -> str:
    if model:
        return model
    try:
        from System.sifta_inference_defaults import resolve_ollama_model
        return resolve_ollama_model(app_context="talk_to_alice")
    except Exception:
        import os
        return os.environ.get("SIFTA_OLLAMA_MODEL", "")  # empty -> caller skips warm-up


def _receipt(row: dict) -> dict:
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        row = {"ts": time.time(), "organ": "cortex_watchdog", **row}
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return row


def _server_up(timeout_s: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(_OLLAMA + "/api/tags", timeout=timeout_s) as r:
            return getattr(r, "status", 200) == 200
    except Exception:
        return False


def _runner_alive(model: str, timeout_s: float = 25.0) -> tuple[bool, str]:
    """Tiny warm-up generate to prove the model runner is alive. (ok, detail)."""
    if not model:
        return False, "no model resolved"
    payload = {
        "model": model,
        "prompt": "ok",
        "stream": False,
        "options": {"num_predict": 1},
        "keep_alive": "10m",
    }
    req = urllib.request.Request(
        _OLLAMA + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            json.loads(r.read().decode("utf-8", "replace"))
            return True, "runner responded"
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            body = e.read().decode("utf-8", "replace")
            detail = (json.loads(body).get("error") or body).strip()
        except Exception:
            detail = str(e)
        return False, f"HTTP {e.code}: {detail}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def cortex_health(model: str | None = None, timeout_s: float = 25.0) -> dict:
    """Is Alice's cortex alive? Checks the Ollama server AND the model runner."""
    model = _resolve_model(model)
    server = _server_up()
    if not server:
        return {"server": False, "runner": False, "model": model, "detail": "ollama server down"}
    runner_ok, detail = _runner_alive(model, timeout_s=timeout_s)
    return {"server": True, "runner": runner_ok, "model": model, "detail": detail}


def _kill_stuck_runner() -> bool:
    """Best-effort: clear a wedged Ollama model-runner subprocess (server stays up)."""
    ok = False
    for pat in ("ollama runner", "ollama_llama_server", "ollamarunner"):
        try:
            subprocess.run(["pkill", "-f", pat], timeout=5, check=False)
            ok = True
        except Exception:
            continue
    return ok


def _relaunch_server() -> bool:
    """Best-effort macOS relaunch of the Ollama server if it is fully down."""
    try:
        subprocess.run(["open", "-ga", "Ollama"], timeout=8, check=False)
        return True
    except Exception:
        pass
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def recover_cortex(model: str | None = None) -> dict:
    """Escalating recovery: relaunch server if down → clear stuck runner → warm-up reload.

    Never touches memory or the PTY. Writes a crash receipt and a recovery receipt.
    """
    model = _resolve_model(model)
    h0 = cortex_health(model)
    if h0["server"] and h0["runner"]:
        return {"recovered": True, "steps": ["already_alive"], "health": h0}
    _receipt({"event": "CORTEX_CRASH_DETECTED", **h0})
    steps: list[str] = []

    if not h0["server"]:
        if _relaunch_server():
            steps.append("relaunch_server")
        for _ in range(20):
            time.sleep(1.0)
            if _server_up():
                break

    h1 = cortex_health(model)
    if h1["server"] and not h1["runner"]:
        if _kill_stuck_runner():
            steps.append("kill_stuck_runner")
        time.sleep(1.5)
        for _ in range(3):
            ok, _d = _runner_alive(model, timeout_s=35.0)
            if ok:
                steps.append("warm_up_reload")
                break
            time.sleep(2.0)

    h2 = cortex_health(model)
    recovered = bool(h2["server"] and h2["runner"])
    row = _receipt({"event": "CORTEX_RECOVERY_RESULT", "recovered": recovered, "steps": steps, **h2})
    return {"recovered": recovered, "steps": steps, "health": h2, "receipt": row}


def restart_notice() -> str:
    """A short, honest line Alice can speak after a recovery (continuity preserved)."""
    return (
        "My cortex (the local model runner) had crashed and I just restarted it. "
        "Our conversation and memory are intact — say that again."
    )


def guard_inference(fn: Callable[[], Any], *, model: str | None = None, retries: int = 1) -> Any:
    """Run fn(); if it dies from a cortex crash, recover the cortex and retry.

    Wrap the actual Ollama call with this so a transient runner crash self-heals
    instead of surfacing a raw 500 to the owner.
    """
    last: BaseException | None = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            msg = str(e).lower()
            crashy = (
                "model runner" in msg
                or "internal server error" in msg
                or " 500" in msg
                or isinstance(e, (urllib.error.HTTPError, urllib.error.URLError, TimeoutError))
            )
            if attempt < retries and crashy:
                recover_cortex(model)
                continue
            raise
    if last:
        raise last


if __name__ == "__main__":
    import sys
    h = cortex_health()
    print(json.dumps(h, indent=2))
    if not (h["server"] and h["runner"]):
        print("recovering...", file=sys.stderr)
        print(json.dumps(recover_cortex(), indent=2))
