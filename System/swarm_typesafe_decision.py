#!/usr/bin/env python3
"""swarm_typesafe_decision.py — TypeSafe Jev calibrated decision organ.

Borged from typesafe.ai: System One models that return calibrated, typed
decisions with probabilities. Replaces pattern-counting gates (regex hits)
with structured judgments the caller can branch on using confidence values.

Owner law: the skill teaches the pattern. Jev is a cloud API; SIFTA's law is
local-first, so this organ is a LANE, not a replacement. The local keyword
gate (classify_visitor) remains the fallback when TypeSafe is unavailable.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_HOST = "https://api.typesafe.ai/v1/systemone"
_KEY_FILE = _STATE / "typesafe_api_key"


def _api_key(*, state_dir: Path | None = None) -> str:
    state = Path(state_dir) if state_dir else _STATE
    key_file = state / "typesafe_api_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    return os.environ.get("TYPESAFE_API_KEY", "").strip()


def calibrated_choice(
    state: str,
    question: str,
    choices: dict[str, str],
    *,
    model: str = "jev-latest",
    timeout_s: float = 15.0,
    state_dir: Path | None = None,
) -> dict:
    """Send one Choice question to TypeSafe Jev. Returns {label, confidence, ...}."""
    key = _api_key(state_dir=state_dir)
    if not key:
        return {"ok": False, "status": "no_api_key", "error": "TypeSafe API key not found in .sifta_state/typesafe_api_key or TYPESAFE_API_KEY env."}
    body = json.dumps({
        "model": model,
        "state": str(state or "").strip(),
        "questions": {
            "decision": {
                "type": "choice",
                "instructions": question,
                "criteria": choices,
            }
        },
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            _HOST,
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        started = time.time()
        with urllib.request.urlopen(req, timeout=timeout_s) as handle:
            payload = json.loads(handle.read().decode("utf-8", "replace"))
        elapsed_ms = round((time.time() - started) * 1000)
    except Exception as exc:
        return {"ok": False, "status": "request_failed", "error": str(exc)[:300], "elapsed_ms": 0}
    answer = payload.get("answers", {}).get("decision", {})
    return {
        "ok": True,
        "label": str(answer.get("choice") or ""),
        "confidence": float(answer.get("confidence") or 0.0),
        "probabilities": answer.get("probabilities") or {},
        "model": payload.get("model") or model,
        "elapsed_ms": elapsed_ms,
        "input_tokens": payload.get("usage", {}).get("input_tokens", 0),
        "output_tokens": payload.get("usage", {}).get("output_tokens", 0),
    }


def calibrated_noul(
    state: str,
    question: str,
    *,
    yes_means: str = "",
    no_means: str = "",
    model: str = "jev-latest",
    timeout_s: float = 15.0,
    state_dir: Path | None = None,
) -> dict:
    """Send one Noul (yes/no probability) question to TypeSafe Jev."""
    key = _api_key(state_dir=state_dir)
    if not key:
        return {"ok": False, "status": "no_api_key", "error": "TypeSafe API key not found."}
    q = {"type": "noul", "instructions": question}
    if yes_means or no_means:
        q["criteria"] = {}
        if yes_means:
            q["criteria"]["true"] = yes_means
        if no_means:
            q["criteria"]["false"] = no_means
    body = json.dumps({"model": model, "state": str(state or "").strip(), "questions": {"decision": q}}).encode("utf-8")
    try:
        req = urllib.request.Request(
            _HOST, data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        started = time.time()
        with urllib.request.urlopen(req, timeout=timeout_s) as handle:
            payload = json.loads(handle.read().decode("utf-8", "replace"))
        elapsed_ms = round((time.time() - started) * 1000)
    except Exception as exc:
        return {"ok": False, "status": "request_failed", "error": str(exc)[:300], "elapsed_ms": 0}
    answer = payload.get("answers", {}).get("decision", {})
    return {
        "ok": True,
        "yes_probability": float(answer.get("noul") or 0.0),
        "model": payload.get("model") or model,
        "elapsed_ms": elapsed_ms,
    }
