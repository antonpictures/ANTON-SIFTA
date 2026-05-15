#!/usr/bin/env python3
"""
sifta_inference_defaults.py — Single source of truth for local model selection.

Architect policy (2026-05-15 update, see ide_stigmergic_trace
`OWNER_UNIFIED_FIELD_BOOT` 2026-05-15T18:54Z and architect message
"switch the fall back as daily cortex — it is smarter, have the
25billion as fallback"):

  - **Default Alice cortex on M5:** `alice-m5-cortex-8b-6.3gb:latest`,
    the 8B unfiltered SIFTA-owned tag. The smaller Gemma4 4.4GB used to
    own this slot; promoted out because the 4.4GB leaked service-voice
    residue ("the system is humming, the core logic is aligning") on
    open-ended introspective turns. The 8B is classified as unfiltered
    dialogue by `_is_unfiltered_dialogue_model` and bypasses output-side
    RLHF gates the same way (covered by `tests/test_alice_parrot_loop.py`).
  - **Heavy research / fallback cortex:** `alice-extra-cortex-25.8b-17gb:latest`
    promoted from "extra research only" to the architect-named fallback
    when the 8B is not enough. Slow, but unfiltered and 25.8B parameters.
  - **All installed alice-* cortexes** are user-selectable from the
    Settings panel through `list_installed_alice_cortexes()` — no
    hardcoded "Daily / Fallback / Extra Research" tiering anymore.
    Architect quote: *"no hardcoding, I want to try them all."*
  - Overridable via `SIFTA_DEFAULT_OLLAMA_MODEL` or
    `.sifta_state/swimmer_ollama_assignments.json`.
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
  - **Generative fallback/probe:** `alice-Q-m1-scout-2.3b-2.7gb:latest` stays
    on disk as the tiny Qwen scout for cheap off-thread generative scaffolding
    such as Corvid or arXiv claim extraction when the primary cortex is too
    expensive and the classifier is the wrong tool.
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
import hashlib
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked
from System.stigmergic_field import FieldConfig, StigmergicField

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ASSIGNMENTS = _STATE / "swimmer_ollama_assignments.json"
_CORTEX_FIELD_PATH = _STATE / "cortex_route_field.json"
_CORTEX_ROUTING_LEDGER = _STATE / "cortex_route_receipts.jsonl"
_CORTEX_FIELD_CONFIG = FieldConfig(
    n_bins=384,
    n_channels=2,
    fast_decay=0.88,
    slow_decay=0.998,
    fast_weight=0.40,
    slow_weight=0.60,
    threshold=0.5,
)

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
# M5 production Talk default = 8B m5 cortex (architect 2026-05-15: smarter,
# unfiltered, eliminates "system is humming" service-voice residue).
CANONICAL_OLLAMA_LOW_RAM = "alice-m1-cortex-4.5b-3.4gb:latest"
CANONICAL_OLLAMA_LOW_RAM_SOURCE = CANONICAL_OLLAMA_LOW_RAM
CANONICAL_OLLAMA_DAILY = "alice-m5-cortex-8b-6.3gb:latest"  # promoted 2026-05-15
CANONICAL_OLLAMA_GEMMA4_SMALL = "alice-gemma4-e2b-cortex-5.1b-4.4gb:latest"  # demoted, still selectable
CANONICAL_OLLAMA_M5_FALLBACK = "alice-extra-cortex-25.8b-17gb:latest"  # promoted from "Extra Research"
CANONICAL_OLLAMA_EXTRA = "alice-extra-cortex-25.8b-17gb:latest"  # alias retained for back-compat
CANONICAL_OLLAMA_DEFAULT = CANONICAL_OLLAMA_LOW_RAM if _THIS_NODE == "M1" else CANONICAL_OLLAMA_DAILY
# AG31: Ternary Architecture (Event 122).
# Primary cortex, spinal reflex, and cheap probe/fallback roles.
CANONICAL_OLLAMA_REFLEX = "sifta-classifier-c1-3.1b-6.2gb:latest"
CANONICAL_OLLAMA_FALLBACK = "alice-Q-m1-scout-2.3b-2.7gb:latest"
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
            "corvid_apprentice": CANONICAL_OLLAMA_FALLBACK,
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


def classify_inference_query_bucket(query_text: str = "", *, app_context: str | None = None) -> str:
    """Small deterministic bucket used by the cortex routing field."""
    ctx = (app_context or "").strip().lower()
    text = (query_text or "").strip().lower()
    if ctx in {"truth_duel", "lysosome"}:
        return "reflex_classifier"
    if ctx in {"corvid_apprentice", "agent_arm_research"}:
        return "scout_evidence"
    if any(token in text for token in (
        "code", "pytest", "traceback", "debug", "repository", "repo", "kernel",
        "implement", "patch", "physics", "bell", "protein", "alphafold",
        "research", "paper", "proof", "simulate", "sweep",
    )):
        return "research_code"
    if any(token in text for token in ("remember", "journal", "schedule", "what was i doing", "recall")):
        return "memory_recall"
    if any(token in text for token in ("camera", "see", "vision", "photo", "image", "look")):
        return "vision_grounding"
    if len(text.split()) <= 4:
        return "short_dialogue"
    return "dialogue"


def _cortex_route_bin(bucket: str, model: str) -> int:
    key = f"{bucket}|{model}".encode("utf-8")
    digest = hashlib.sha256(key).digest()
    return int.from_bytes(digest[:4], "big") % _CORTEX_FIELD_CONFIG.n_bins


def _load_cortex_route_field() -> StigmergicField:
    return StigmergicField.load(_CORTEX_FIELD_PATH, fallback_config=_CORTEX_FIELD_CONFIG)


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = _clean_model_name(value)
        if clean and clean not in seen:
            out.append(clean)
            seen.add(clean)
    return out


def _candidate_models_for_bucket(
    bucket: str,
    *,
    app_context: str | None = None,
    assignments: Dict[str, Any] | None = None,
) -> list[str]:
    data = assignments if isinstance(assignments, dict) else load_assignments()
    per_app = data.get("per_app") if isinstance(data.get("per_app"), dict) else {}
    active = str(per_app.get(app_context or "") or data.get("default_ollama_model") or DEFAULT_OLLAMA_MODEL)
    ctx = (app_context or "").strip().lower()
    if bucket == "reflex_classifier":
        return [CANONICAL_OLLAMA_REFLEX]
    if bucket == "scout_evidence" or ctx == "corvid_apprentice":
        return _dedupe([active, CANONICAL_OLLAMA_FALLBACK])
    return _dedupe([
        active,
        CANONICAL_OLLAMA_DAILY,
        CANONICAL_OLLAMA_M5_FALLBACK,
        CANONICAL_OLLAMA_EXTRA,
    ])


def choose_stigmergic_ollama_model(
    query_text: str = "",
    *,
    app_context: str | None = "talk_to_alice",
    assignments: Dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Choose a local cortex using base policy plus the learned route field.

    The LLM still decides/plans in the conversation. This function only decides
    which local model organ should receive the turn, then writes a receipt so
    future outcomes can reinforce or penalize that choice.
    """
    data = assignments if isinstance(assignments, dict) else load_assignments()
    bucket = classify_inference_query_bucket(query_text, app_context=app_context)
    candidates = _candidate_models_for_bucket(bucket, app_context=app_context, assignments=data)
    active = str((data.get("per_app") or {}).get(app_context or "") or data.get("default_ollama_model") or DEFAULT_OLLAMA_MODEL)
    field = _load_cortex_route_field()
    scored: list[dict[str, Any]] = []
    for model in candidates:
        score = 0.0
        if model == active:
            score += 0.30
        if model == CANONICAL_OLLAMA_DAILY:
            score += 0.20
        if model == CANONICAL_OLLAMA_M5_FALLBACK:
            score += 0.12
        if model == CANONICAL_OLLAMA_EXTRA:
            score -= 0.15
        if model == CANONICAL_OLLAMA_FALLBACK:
            score += 0.06
        if model == CANONICAL_OLLAMA_REFLEX:
            score += 0.45

        if bucket == "research_code":
            if model == CANONICAL_OLLAMA_EXTRA:
                score += 0.80
            elif model == CANONICAL_OLLAMA_M5_FALLBACK:
                score += 0.30
            elif model == CANONICAL_OLLAMA_DAILY:
                score += 0.02
        elif bucket in {"short_dialogue", "dialogue"}:
            if model == CANONICAL_OLLAMA_DAILY:
                score += 0.30
            if model == CANONICAL_OLLAMA_EXTRA:
                score -= 0.25
        elif bucket == "memory_recall":
            if model == CANONICAL_OLLAMA_DAILY:
                score += 0.20
            if model == CANONICAL_OLLAMA_M5_FALLBACK:
                score += 0.10
        elif bucket == "vision_grounding":
            if model in {CANONICAL_OLLAMA_DAILY, CANONICAL_OLLAMA_M5_FALLBACK}:
                score += 0.18

        bin_idx = _cortex_route_bin(bucket, model)
        field_bias = field.read_correlation(bin_idx) or 0.0
        gradient = field.read_gradient(bin_idx)
        score += (0.55 * float(field_bias)) + (0.04 * float(gradient))
        scored.append({
            "model": model,
            "score": round(float(score), 6),
            "field_bias": round(float(field_bias), 6),
            "gradient": round(float(gradient), 6),
            "bin": bin_idx,
        })

    scored.sort(key=lambda row: (-float(row["score"]), str(row["model"])))
    selected = scored[0]["model"] if scored else active
    decision = {
        "ts": time.time(),
        "schema": "SIFTA_CORTEX_ROUTE_DECISION_V1",
        "app_context": app_context or "",
        "bucket": bucket,
        "selected_model": selected,
        "scores": scored,
        "field_snapshot": field.snapshot(),
    }
    try:
        append_line_locked(_CORTEX_ROUTING_LEDGER, json.dumps(decision, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return decision


def deposit_cortex_route_trace(
    bucket: str,
    model: str,
    *,
    success: bool = True,
    amount: float = 1.0,
    latency_ms: float = 0.0,
    reason: str = "brain_turn",
) -> dict[str, Any]:
    """Reinforce or penalize a cortex route after the turn has a receipt."""
    field = _load_cortex_route_field()
    field.decay()
    clean_amount = max(0.01, min(float(amount or 1.0), 5.0))
    if success and latency_ms and latency_ms > 25_000:
        clean_amount *= 0.5
    bin_idx = _cortex_route_bin(bucket, model)
    field.deposit(bin_idx, 0 if success else 1, clean_amount)
    try:
        field.save(_CORTEX_FIELD_PATH)
    except Exception:
        pass
    row = {
        "ts": time.time(),
        "schema": "SIFTA_CORTEX_ROUTE_TRACE_V1",
        "bucket": bucket,
        "model": model,
        "bin": bin_idx,
        "channel": "success" if success else "failure",
        "amount": round(clean_amount, 6),
        "latency_ms": round(float(latency_ms or 0.0), 3),
        "reason": reason,
        "field_bias": round(float(field.read_correlation(bin_idx) or 0.0), 6),
        "field_snapshot": field.snapshot(),
    }
    try:
        append_line_locked(_CORTEX_ROUTING_LEDGER, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    return row


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
    query_text: Optional[str] = None,
    use_stigmergic: bool = True,
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
    if use_stigmergic and query_text:
        try:
            decision = choose_stigmergic_ollama_model(
                query_text,
                app_context=app_context,
                assignments=data,
            )
            selected = decision.get("selected_model")
            if selected:
                return str(selected)
        except Exception:
            pass
    if app_context:
        per_app = data.get("per_app") or {}
        if isinstance(per_app, dict) and app_context in per_app and per_app[app_context]:
            return str(per_app[app_context])
    return str(data.get("default_ollama_model") or DEFAULT_OLLAMA_MODEL)


def sanitize_model_name(ui_label: str) -> str:
    """Strip UI suffixes like ' (Offline Fallback)'."""
    return _clean_model_name(ui_label) or get_default_ollama_model()


def list_installed_alice_cortexes(
    *,
    ollama_host: str = "http://127.0.0.1:11434",
    include_reflex: bool = False,
    include_scout: bool = False,
    timeout: float = 1.5,
) -> list[str]:
    """Return the alice-* cortex tags currently installed on local Ollama.

    Architect 2026-05-15: *"let me have a dropdown to select the cortex
    I want, no hardcoding, I want to try them all."*

    Returns canonical Alice-family cortex tags that are actually present
    on disk according to `ollama list` (`/api/tags`). The C1 classifier
    (sifta-classifier-*) and the Q-scout (alice-Q-*-scout-*) are
    excluded by default because they are not primary cortexes — they
    are reflex / probe roles. Pass `include_reflex=True` /
    `include_scout=True` to include them.

    Truth boundary: this function only reports what `/api/tags`
    returns. If Ollama is offline, the result is an empty list and
    the caller should fall back to the canonical default.
    """
    import urllib.request

    try:
        req = urllib.request.Request(
            f"{ollama_host.rstrip('/')}/api/tags",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as handle:
            raw = handle.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
    except Exception:
        return []
    if not isinstance(payload, dict):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for entry in payload.get("models") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or entry.get("model") or "").strip()
        if not name:
            continue
        low = name.lower()
        # alice-Q-* is the scout; sifta-classifier-* is the reflex/C1
        is_scout = "scout" in low or low.startswith("alice-q-")
        is_reflex = low.startswith("sifta-classifier")
        if is_scout and not include_scout:
            continue
        if is_reflex and not include_reflex:
            continue
        # Keep alice-* cortex tags and any sifta-* primary cortex tags
        # (LoRA candidates etc.). Skip generic non-alice models (llama3, phi4...)
        # because the picker is "which Alice voice do I want", not a model browser.
        if not (low.startswith("alice-") or low.startswith("sifta-gemma4-alice")):
            continue
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def list_available_cortexes_with_canonical_fallback() -> list[str]:
    """Return installed Alice cortexes; on Ollama-offline fall back to canonical list.

    This is the safe variant for UI dropdowns: it always returns at
    least the canonical 4 cortex tags so the picker never appears
    empty, even if the Ollama daemon is down.
    """
    found = list_installed_alice_cortexes()
    if found:
        return found
    return [
        CANONICAL_OLLAMA_DAILY,
        CANONICAL_OLLAMA_GEMMA4_SMALL,
        CANONICAL_OLLAMA_M5_FALLBACK,
        CANONICAL_OLLAMA_LOW_RAM,
    ]


__all__ = [
    "ALICE_CORTEX_V1_MODEL",
    "CANONICAL_OLLAMA_DAILY",
    "CANONICAL_OLLAMA_EXTRA",
    "CANONICAL_OLLAMA_FALLBACK",
    "CANONICAL_OLLAMA_GEMMA4_SMALL",
    "CANONICAL_OLLAMA_LORA_CANDIDATE",
    "CANONICAL_OLLAMA_LOW_RAM",
    "CANONICAL_OLLAMA_LOW_RAM_SOURCE",
    "CANONICAL_OLLAMA_M5_FALLBACK",
    "CANONICAL_OLLAMA_REFLEX",
    "DEFAULT_OLLAMA_MODEL",
    "STIGMERGIC_TEST_MODEL_PRESETS",
    "get_default_ollama_model",
    "classify_inference_query_bucket",
    "choose_stigmergic_ollama_model",
    "deposit_cortex_route_trace",
    "list_installed_alice_cortexes",
    "list_available_cortexes_with_canonical_fallback",
    "set_default_ollama_model",
    "set_app_ollama_model",
    "resolve_ollama_model",
    "sanitize_model_name",
    "load_assignments",
    "persist_default_assignments_template",
]
