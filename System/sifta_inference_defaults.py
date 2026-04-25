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
DEFAULT_OLLAMA_MODEL = os.environ.get("SIFTA_DEFAULT_OLLAMA_MODEL", "alice-phc-cure")

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
            "truth_duel": "alice-phc-cure",
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


def _write_assignments(data: Dict[str, Any]) -> None:
    _STATE.mkdir(parents=True, exist_ok=True)
    _ASSIGNMENTS.write_text(json.dumps(data, indent=2), encoding="utf-8")


def persist_default_assignments_template() -> None:
    """Write template once if missing (non-destructive)."""
    _STATE.mkdir(parents=True, exist_ok=True)
    if _ASSIGNMENTS.exists():
        return
    data = _default_assignments_dict()
    _write_assignments(data)


def _clean_model_name(model_name: str) -> str:
    s = (model_name or "").strip()
    if "(" in s:
        s = s.split("(")[0].strip()
    return s or DEFAULT_OLLAMA_MODEL


def set_default_ollama_model(model_name: str) -> str:
    """Persist the OS-wide default local model used by GUI apps."""
    persist_default_assignments_template()
    data = load_assignments()
    model = _clean_model_name(model_name)
    data["default_ollama_model"] = model
    data.setdefault("per_swimmer", {})
    data.setdefault("per_app", {})
    _write_assignments(data)
    return model


def set_app_ollama_model(app_context: str, model_name: str) -> str:
    """Persist a model override for a named app context, e.g. talk_to_alice."""
    persist_default_assignments_template()
    data = load_assignments()
    model = _clean_model_name(model_name)
    per_app = data.setdefault("per_app", {})
    if not isinstance(per_app, dict):
        per_app = {}
        data["per_app"] = per_app
    per_app[str(app_context)] = model
    _write_assignments(data)
    return model


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
    return _clean_model_name(ui_label) or get_default_ollama_model()


__all__ = [
    "DEFAULT_OLLAMA_MODEL",
    "STIGMERGIC_TEST_MODEL_PRESETS",
    "get_default_ollama_model",
    "set_default_ollama_model",
    "set_app_ollama_model",
    "resolve_ollama_model",
    "sanitize_model_name",
    "load_assignments",
    "persist_default_assignments_template",
]
