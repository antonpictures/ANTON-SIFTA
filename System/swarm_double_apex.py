#!/usr/bin/env python3
"""swarm_double_apex.py — one body for the double apex predator.

Unites:
  1) Event 71 Apex Perceiver (attention bottleneck)
  2) Predator v7 field (organs + swimmer canvas)
  3) Dual doctor arms (Codex + Claude) on a shared local Ollama cortex

Truth: launches local tools only; does not invent cloud credentials.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Optional

TRUTH_LABEL = "DOUBLE_APEX_PREDATOR_V1"
DEFAULT_LOCAL_MODEL = (
    "jikepjikep_16HEX/qwen3.6-27b-nightshift-heretic-uncensored-q4"
)

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"

# Ollama launch integration names (from `ollama launch --help`)
INTEGRATIONS = {
    "codex_app": "codex-app",
    "codex_cli": "codex",
    "claude": "claude",
}


def _receipt(event: str, payload: dict[str, Any]) -> None:
    try:
        _STATE.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": TRUTH_LABEL,
            "event": event,
            **payload,
        }
        with (_STATE / "double_apex_receipts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def ollama_bin() -> Optional[str]:
    return shutil.which("ollama")


def list_local_models() -> dict[str, Any]:
    """Return installed Ollama model names (best-effort)."""
    bin_path = ollama_bin()
    if not bin_path:
        return {"ok": False, "reason": "ollama_not_on_path", "models": []}
    try:
        proc = subprocess.run(
            [bin_path, "list"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "models": []}
    models: list[str] = []
    for line in (proc.stdout or "").splitlines()[1:]:
        name = (line.split() or [""])[0].strip()
        if name:
            models.append(name)
    return {
        "ok": proc.returncode == 0,
        "models": models,
        "returncode": proc.returncode,
        "stderr": (proc.stderr or "")[:400],
    }


def pick_default_model(models: list[str] | None = None) -> str:
    if models is None:
        models = list_local_models().get("models") or []
    prefer = [
        DEFAULT_LOCAL_MODEL,
        f"{DEFAULT_LOCAL_MODEL}:latest",
        "satgeze/qwenpaw-9b-heretic-1m:latest",
        "satgeze/qwenpaw-9b-heretic-1m",
    ]
    for p in prefer:
        if p in models:
            return p
    # fuzzy: nightshift / heretic 27b
    for m in models:
        low = m.lower()
        if "nightshift" in low or ("27b" in low and "heretic" in low):
            return m
    return models[0] if models else DEFAULT_LOCAL_MODEL


def doctor_status() -> dict[str, Any]:
    """Presence of ollama + codex + claude binaries."""
    return {
        "ollama": bool(ollama_bin()),
        "ollama_path": ollama_bin() or "",
        "codex": bool(shutil.which("codex")),
        "codex_path": shutil.which("codex") or "",
        "claude": bool(shutil.which("claude")),
        "claude_path": shutil.which("claude") or "",
        "truth_label": TRUTH_LABEL,
    }


def launch_doctor(
    arm: str,
    *,
    model: str,
    cwd: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Launch Codex App / Codex CLI / Claude Code via `ollama launch`.

    arm: codex_app | codex_cli | claude
    """
    arm_key = str(arm or "").strip().lower()
    integration = INTEGRATIONS.get(arm_key)
    if not integration:
        return {"ok": False, "reason": f"unknown_arm:{arm}"}

    bin_path = ollama_bin()
    if not bin_path:
        return {"ok": False, "reason": "ollama_not_on_path"}

    model = (model or pick_default_model()).strip()
    work = Path(cwd) if cwd else _REPO
    cmd = [bin_path, "launch", integration, "--model", model]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(work),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        out = {
            "ok": True,
            "arm": arm_key,
            "integration": integration,
            "model": model,
            "pid": proc.pid,
            "cmd": cmd,
            "cwd": str(work),
            "note": (
                "spawned ollama launch — agent uses local Ollama model; "
                "not Anthropic/OpenAI cloud unless the model is a cloud tag"
            ),
        }
        _receipt("launch_doctor", out)
        return out
    except Exception as exc:
        fail = {
            "ok": False,
            "arm": arm_key,
            "model": model,
            "reason": f"{type(exc).__name__}: {exc}",
            "cmd": cmd,
        }
        _receipt("launch_doctor_fail", fail)
        return fail


def launch_both(
    *,
    model: str,
    cwd: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Launch both apex doctors (Codex App + Claude Code) on same local model."""
    a = launch_doctor("codex_app", model=model, cwd=cwd)
    b = launch_doctor("claude", model=model, cwd=cwd)
    out = {
        "ok": bool(a.get("ok") or b.get("ok")),
        "codex_app": a,
        "claude": b,
        "model": model,
        "truth_label": TRUTH_LABEL,
    }
    _receipt("launch_both", out)
    return out


__all__ = [
    "TRUTH_LABEL",
    "DEFAULT_LOCAL_MODEL",
    "list_local_models",
    "pick_default_model",
    "doctor_status",
    "launch_doctor",
    "launch_both",
]
