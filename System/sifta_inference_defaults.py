#!/usr/bin/env python3
"""
sifta_inference_defaults.py — Single source of truth for Ollama model selection.

Architect policy (2026-04-18):
  - **Default production model:** `gemma4:latest` (best local quality for swimmers / OS).
  - **Other models:** use for stigmergic testing, probes, or per-app tuning — never pretend
    one node's API is another node's fingerprint; routing goes through `inference_router`.

Optional overrides: `.sifta_state/swimmer_ollama_assignments.json`
Environment: `SIFTA_DEFAULT_OLLAMA_MODEL`, `SIFTA_ACTIVE_SWIMMER_ID` (optional hint for resolve).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ASSIGNMENTS = _STATE / "swimmer_ollama_assignments.json"

# Primary default — swimmers + OS helpers unless overridden.
DEFAULT_OLLAMA_MODEL = os.environ.get("SIFTA_DEFAULT_OLLAMA_MODEL", "gemma4:latest")

# Models commonly used for SLLI / lightweight probes (not production default).
STIGMERGIC_TEST_MODEL_PRESETS: tuple[str, ...] = (
    "llama3:latest",
    "phi4-mini-reasoning:latest",
    "rnj-1:latest",
)


def _default_assignments_dict() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "default_ollama_model": DEFAULT_OLLAMA_MODEL,
        "per_swimmer": {},
        "per_app": {
            "stigmergic_probe": "llama3:latest",
        },
        "notes": (
            "default_ollama_model is production. per_swimmer / per_app override for testing "
            "or app-specific UX. Use inference_router for node selection — do not hardcode M1 URL on M5."
        ),
    }


def load_assignments() -> Dict[str, Any]:
    if not _ASSIGNMENTS.exists():
        return _default_assignments_dict()
    try:
        raw = json.loads(_ASSIGNMENTS.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except (OSError, json.JSONDecodeError):
        pass
    return _default_assignments_dict()


def persist_default_assignments_template() -> None:
    """Write template once if missing (non-destructive)."""
    _STATE.mkdir(parents=True, exist_ok=True)
    if _ASSIGNMENTS.exists():
        return
    data = _default_assignments_dict()
    _ASSIGNMENTS.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_default_ollama_model() -> str:
    data = load_assignments()
    return str(data.get("default_ollama_model") or DEFAULT_OLLAMA_MODEL)


def resolve_ollama_model(
    *,
    swimmer_id: Optional[str] = None,
    app_context: Optional[str] = None,
) -> str:
    """
    Resolve model name for Ollama /api/generate.

    Precedence: explicit swimmer_id → per_app[app_context] → file default → env default.
    If env `SIFTA_ACTIVE_SWIMMER_ID` is set and swimmer_id is None, it is used.
    """
    persist_default_assignments_template()
    data = load_assignments()
    sid = swimmer_id or os.environ.get("SIFTA_ACTIVE_SWIMMER_ID")
    if sid:
        per = data.get("per_swimmer") or {}
        if isinstance(per, dict) and sid in per and per[sid]:
            return str(per[sid])
    if app_context:
        per_app = data.get("per_app") or {}
        if isinstance(per_app, dict) and app_context in per_app and per_app[app_context]:
            return str(per_app[app_context])
    return str(data.get("default_ollama_model") or DEFAULT_OLLAMA_MODEL)


def sanitize_model_name(ui_label: str) -> str:
    """Strip UI suffixes like ' (Offline Fallback)'."""
    s = (ui_label or "").strip()
    if "(" in s:
        s = s.split("(")[0].strip()
    return s or get_default_ollama_model()


__all__ = [
    "DEFAULT_OLLAMA_MODEL",
    "STIGMERGIC_TEST_MODEL_PRESETS",
    "get_default_ollama_model",
    "resolve_ollama_model",
    "sanitize_model_name",
    "load_assignments",
    "persist_default_assignments_template",
]
