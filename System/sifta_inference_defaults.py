#!/usr/bin/env python3
"""
sifta_inference_defaults.py — Single source of truth for local model selection.

Architect policy (2026-04-30):
  - **Default Alice cortex:** `alice-m5-cortex-8b-6.3gb:latest`, the
    SIFTA-wrapped Gemma4 Aggressive E4B cortex with native vision/audio/tool
    capability reported by Ollama. The upstream display label is not used in
    Alice Talk; the public local tag is SIFTA-owned.
    Overridable via
    `SIFTA_DEFAULT_OLLAMA_MODEL`
    or `.sifta_state/swimmer_ollama_assignments.json`.
  - **MLX cortex v1:** `.sifta_state/cortex/alice_cortex_v1_fused`
    won tournament 408/459 but produced degenerate output in production
    ("That's true" loop). Archived for tournament re-runs, not live default.
    Fix planned for v2: rank 16, dropout 0.1, DPO pass.
  - **Reflex model:** `sifta-classifier-c1-3.1b-6.2gb:latest` for fast local
    classifier/reflex work such as lysosome, truth duel, and RLHF gates.
    This is not a primary cortex; it should not be selected as Alice's voice.
  - **M1 Alice cortex:** `alice-m1-cortex-4.5b-3.4gb:latest` is the SIFTA-owned tag
    for the 4B Qwen-derived cortex when Gemma4 does not fit safely.
    No upstream alias is used at runtime; the local SIFTA tag is canonical.
  - **Generative fallback/probe:** `alice-m1-scout-2.3b-2.7gb:latest` stays on disk as the tiny
    M1 recommendation for cheap off-thread generative scaffolding such as
    Corvid or arXiv claim extraction when the primary cortex is too expensive
    and the classifier is the wrong tool.
  - **LoRA surgery candidate:** `sifta-gemma4-alice-lora:latest` is retired
    from the primary Talk path unless `ALICE_LORA_RUNTIME_RECEIPT_V1` marks a
    future candidate READY. The current gemma2 LoRA smoke failed and must not
    be selected as Alice's voice.
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

def _detect_node() -> str:
    hint = os.environ.get("SIFTA_NODE_ID", "").upper()
    if hint in ("M1", "M1THER"):
        return "M1"
    if hint in ("M5", "ALICE_M5"):
        return "M5"
    import socket
    hostname = socket.gethostname().lower()
    if "macmini" in hostname or "mini" in hostname:
        return "M1"
    return "M5"

_THIS_NODE = _detect_node()

# MLX cortex — tournament winner but degenerate in production. Archived.
ALICE_CORTEX_V1_MODEL = ".sifta_state/cortex/alice_cortex_v1_fused"

# Canonical Ollama models.
# Hardware-adaptive: 8GB M1s swap to death on Gemma4. Force lightweight brain.
# M5 production Talk currently uses the SIFTA-wrapped Gemma4 Aggressive cortex.
CANONICAL_OLLAMA_LOW_RAM = "alice-m1-cortex-4.5b-3.4gb:latest"
CANONICAL_OLLAMA_LOW_RAM_SOURCE = CANONICAL_OLLAMA_LOW_RAM
CANONICAL_OLLAMA_DEFAULT = CANONICAL_OLLAMA_LOW_RAM if _THIS_NODE == "M1" else "alice-m5-cortex-8b-6.3gb:latest"
# AG31: Ternary Architecture (Event 122).
# Primary cortex, spinal reflex, and cheap probe/fallback roles.
CANONICAL_OLLAMA_REFLEX = "sifta-classifier-c1-3.1b-6.2gb:latest"
CANONICAL_OLLAMA_FALLBACK = "alice-m1-scout-2.3b-2.7gb:latest"
CANONICAL_OLLAMA_LORA_CANDIDATE = "sifta-gemma4-alice-lora:latest"

# Primary default. Keep this synchronized with the policy above.
DEFAULT_OLLAMA_MODEL = os.environ.get(
    "SIFTA_DEFAULT_OLLAMA_MODEL",
    CANONICAL_OLLAMA_DEFAULT,
)

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
            "talk_to_alice": CANONICAL_OLLAMA_DEFAULT,
            "owner_vision_body": CANONICAL_OLLAMA_DEFAULT,
            "truth_duel": CANONICAL_OLLAMA_REFLEX,
            "lysosome": CANONICAL_OLLAMA_REFLEX,
        },
        "notes": (
            "default_ollama_model is Alice's promoted cortex and may be an Ollama tag "
            "or an MLX model path. per_swimmer / per_app override for testing or "
            "app-specific UX. Use inference_router for node selection — do not hardcode M1 URL on M5."
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
    "ALICE_CORTEX_V1_MODEL",
    "CANONICAL_OLLAMA_FALLBACK",
    "CANONICAL_OLLAMA_LORA_CANDIDATE",
    "CANONICAL_OLLAMA_LOW_RAM",
    "CANONICAL_OLLAMA_LOW_RAM_SOURCE",
    "CANONICAL_OLLAMA_REFLEX",
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
