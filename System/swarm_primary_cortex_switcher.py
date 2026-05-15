#!/usr/bin/env python3
"""
swarm_primary_cortex_switcher.py

Small, receipt-backed organ for selecting Alice's primary cortex.

Truth boundary:
  - The switch changes the Ollama model tag used by the Talk-to-Alice app.
  - It does not invent model capabilities. A model is selectable only when it
    is present in the local Ollama model list, or when tests inject a model
    inventory explicitly.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from System.sifta_inference_defaults import (
    CANONICAL_OLLAMA_DEFAULT,
    CANONICAL_OLLAMA_FALLBACK,
    CANONICAL_OLLAMA_LORA_CANDIDATE,
    CANONICAL_OLLAMA_LOW_RAM,
    resolve_ollama_model,
    set_app_ollama_model,
)

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover - fallback only for damaged boot paths
    append_line_locked = None  # type: ignore[assignment]


_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_LEDGER = _STATE / "primary_cortex_switches.jsonl"
APP_CONTEXT = "talk_to_alice"

# Stable defaults plus local experimental slots. The actual dropdown filters to
# installed models, so these names are hints, not claims that a model exists.
PREFERRED_PRIMARY_CORTICES: tuple[str, ...] = (
    CANONICAL_OLLAMA_DEFAULT,
    CANONICAL_OLLAMA_LOW_RAM,
    CANONICAL_OLLAMA_FALLBACK,
)


def _canonical_model_name(name: str) -> str:
    value = (name or "").strip()
    if not value:
        return ""
    # Ollama treats missing tag as latest. Preserve explicit non-latest tags.
    if ":" not in value and not value.startswith("."):
        return value
    return value


def _same_model(a: str, b: str) -> bool:
    """Compare Ollama tags while treating missing ':latest' as equivalent."""
    a = _canonical_model_name(a)
    b = _canonical_model_name(b)
    if a == b:
        return True
    if ":" not in a and b == f"{a}:latest":
        return True
    if ":" not in b and a == f"{b}:latest":
        return True
    return False


def installed_ollama_models(*, timeout: float = 10.0) -> List[Dict[str, Any]]:
    """Return installed Ollama models from `ollama list`.

    The function is intentionally tolerant. If Ollama is offline or absent, it
    returns an empty list instead of blocking the UI boot.
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []

    rows: List[Dict[str, Any]] = []
    for line in (result.stdout or "").splitlines()[1:]:
        parts = line.split()
        if not parts:
            continue
        name = parts[0].strip()
        if not name or name.upper() == "NAME":
            continue
        rows.append(
            {
                "name": name,
                "id": parts[1] if len(parts) > 1 else "",
                "size": " ".join(parts[2:4]) if len(parts) >= 4 else "",
                "modified": " ".join(parts[4:]) if len(parts) > 4 else "",
            }
        )
    return rows


def _env_candidates() -> List[str]:
    raw = os.environ.get("SIFTA_PRIMARY_CORTEX_CANDIDATES", "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def primary_cortex_options(
    *,
    installed: Optional[Iterable[str]] = None,
    current: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Build honest dropdown options for the primary cortex.

    Installed models are selectable. Preferred but missing models are returned
    as non-selectable context rows so the UI can tell the Architect why a
    bigger cortex is not available yet.
    """
    installed_names = list(installed) if installed is not None else [
        row["name"] for row in installed_ollama_models()
    ]
    active = current or resolve_ollama_model(app_context=APP_CONTEXT)
    hints: List[str] = []
    # Do not dump every installed Ollama tag into the cortex selector. Some
    # installed tags are classifiers or specialist organs, not primary brains.
    for name in [active, *_env_candidates(), *PREFERRED_PRIMARY_CORTICES]:
        if name and not any(_same_model(name, seen) for seen in hints):
            hints.append(name)

    out: List[Dict[str, Any]] = []
    lora_status: Dict[str, Any] = {}
    try:
        from System.swarm_lora_runtime_receipt import (
            LORA_CANDIDATE_MODEL,
            lora_candidate_status,
        )

        lora_status = lora_candidate_status()
        lora_candidate = str(lora_status.get("candidate_model") or LORA_CANDIDATE_MODEL)
    except Exception:
        lora_candidate = CANONICAL_OLLAMA_LORA_CANDIDATE
        lora_status = {
            "promotion_status": "UNKNOWN",
            "promotion_ready": False,
            "promotion_blockers": ["lora_status_unavailable"],
        }

    for name in hints:
        installed_match = next((x for x in installed_names if _same_model(name, x)), "")
        selectable = bool(installed_match)
        model_name = installed_match or name
        label = model_name
        quarantined = _same_model(model_name, lora_candidate) and not bool(
            lora_status.get("promotion_ready")
        )
        if not selectable:
            label = f"{model_name} (not installed)"
        elif _same_model(model_name, active):
            label = f"{model_name} (active)"
        elif quarantined:
            label = f"{model_name} (quarantined: {lora_status.get('promotion_status', 'UNKNOWN')})"
        out.append(
            {
                "model": model_name,
                "label": label,
                "installed": selectable,
                "active": _same_model(model_name, active),
                "quarantined": quarantined,
                "promotion_status": (
                    lora_status.get("promotion_status") if _same_model(model_name, lora_candidate) else None
                ),
                "promotion_blockers": (
                    lora_status.get("promotion_blockers", [])
                    if _same_model(model_name, lora_candidate)
                    else []
                ),
            }
        )
    return out


def set_primary_cortex(
    model_name: str,
    *,
    installed: Optional[Iterable[str]] = None,
    source: str = "talk_to_alice_dropdown",
    verification_results: Optional[Dict[str, Any]] = None,
    require_verification: bool = False,
) -> Dict[str, Any]:
    """Persist Alice's Talk-to-Alice cortex and append a switch receipt."""
    model = _canonical_model_name(model_name)
    installed_names = list(installed) if installed is not None else [
        row["name"] for row in installed_ollama_models()
    ]
    installed_match = next((x for x in installed_names if _same_model(model, x)), "")
    if not installed_match:
        raise ValueError(f"primary cortex is not installed in Ollama: {model}")
    try:
        from System.swarm_lora_runtime_receipt import (
            LORA_CANDIDATE_MODEL,
            lora_candidate_status,
        )

        lora_status = lora_candidate_status()
        lora_candidate = str(lora_status.get("candidate_model") or LORA_CANDIDATE_MODEL)
        if _same_model(installed_match, lora_candidate) and not bool(
            lora_status.get("promotion_ready")
        ):
            blockers = ", ".join(map(str, lora_status.get("promotion_blockers", [])))
            raise ValueError(
                "primary cortex candidate is quarantined: "
                f"{installed_match} ({lora_status.get('promotion_status', 'UNKNOWN')}; {blockers})"
            )
    except ValueError:
        raise
    except Exception as exc:
        if _same_model(installed_match, CANONICAL_OLLAMA_LORA_CANDIDATE):
            raise ValueError(f"primary cortex LoRA status unavailable: {exc}") from exc

    previous = resolve_ollama_model(app_context=APP_CONTEXT)
    verification: Optional[Dict[str, Any]] = None
    if require_verification or verification_results is not None:
        try:
            from System.swarm_multimodal_cortex_verifier import run_harness

            verification = run_harness(
                installed_match,
                verification_results or {},
                root=_STATE,
                write_ledger=True,
            )
        except Exception as exc:
            if require_verification:
                raise ValueError(f"primary cortex verification failed to run: {exc}") from exc
            verification = {
                "truth_label": "MULTIMODAL_CORTEX_VERIFICATION",
                "pass": False,
                "error": str(exc),
            }
        if require_verification and not verification.get("pass"):
            try:
                from System.swarm_governance_ledger import GovernanceLedger

                GovernanceLedger.record_conflict(
                    "PRIMARY_CORTEX_VERIFICATION_FAILED",
                    [previous, installed_match],
                    "blocked_promotion_until_multimodal_probe_passes",
                    human_override=True,
                    root=_STATE,
                )
            except Exception:
                pass
            raise ValueError(
                "primary cortex verification failed; promotion blocked "
                f"for {installed_match}"
            )

    selected = set_app_ollama_model(APP_CONTEXT, installed_match)
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "PRIMARY_CORTEX_SWITCH_RECEIPT",
        "source": source,
        "app_context": APP_CONTEXT,
        "previous_model": previous,
        "selected_model": selected,
        "installed_models": installed_names,
    }
    if verification is not None:
        row["cortex_verification"] = verification
    _STATE.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, sort_keys=True) + "\n"
    if append_line_locked is not None:
        append_line_locked(_LEDGER, line, encoding="utf-8")
    else:  # pragma: no cover
        with _LEDGER.open("a", encoding="utf-8") as f:
            f.write(line)
    return row


def current_primary_cortex_truth(
    *,
    installed: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Return compact truth for prompt/UI: active model and local install fact."""
    active = resolve_ollama_model(app_context=APP_CONTEXT)
    installed_names = list(installed) if installed is not None else [
        row["name"] for row in installed_ollama_models()
    ]
    installed_active = any(_same_model(active, x) for x in installed_names)
    return {
        "active_model": active,
        "installed": installed_active,
        "installed_models": installed_names,
        "truth_label": "PRIMARY_CORTEX_LOCAL_MODEL_TRUTH",
        "multimodal_native_known": None,
        "note": (
            "Native multimodal capability must be proven by the installed model "
            "artifact. SIFTA external camera/audio organs remain separate from "
            "the primary text cortex."
        ),
    }


__all__ = [
    "APP_CONTEXT",
    "PREFERRED_PRIMARY_CORTICES",
    "current_primary_cortex_truth",
    "installed_ollama_models",
    "primary_cortex_options",
    "set_primary_cortex",
]
