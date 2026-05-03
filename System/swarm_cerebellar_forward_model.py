"""
Event 128 - Cerebellar forward model.

Predicts action/tool execution geometry before motion and updates the model from
post-action prediction error. This complements strategic PFC/BG arbitration:
PFC/BG chooses; cerebellum predicts timing, reliability, cost, and expected
observation echoes.

Truth labels:
  CEREBELLAR_FORWARD_PREDICTION
  CEREBELLAR_FORWARD_OBSERVATION

Kill-switch: SIFTA_CEREBELLUM_DISABLE=1.
"""
from __future__ import annotations

import json
import hashlib
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked

STATE_DIR = Path(".sifta_state")
MODEL_FILE = "cerebellar_tool_models.json"
TRACE_FILE = "cerebellar_forward_model.jsonl"

DEFAULT_MODEL: Dict[str, Any] = {
    "latency_mu": 1.0,
    "success_rate": 0.75,
    "cost_mu": 0.0,
    "n": 0,
    "expected_observation": None,
}


def _state_dir(root: Optional[Path] = None) -> Path:
    return root or STATE_DIR


def state_path(root: Optional[Path] = None) -> Path:
    return _state_dir(root) / MODEL_FILE


def trace_path(root: Optional[Path] = None) -> Path:
    return _state_dir(root) / TRACE_FILE


def _clamp01(value: Any) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = 0.0
    return round(min(1.0, max(0.0, f)), 4)


def _nonnegative(value: Any, fallback: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = fallback
    return round(max(0.0, f), 4)


def _normal_model(raw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    model = dict(DEFAULT_MODEL)
    if raw:
        model.update(raw)
    model["latency_mu"] = _nonnegative(model.get("latency_mu"), 1.0)
    model["success_rate"] = _clamp01(model.get("success_rate", 0.75))
    model["cost_mu"] = _nonnegative(model.get("cost_mu"), 0.0)
    try:
        model["n"] = max(0, int(model.get("n", 0)))
    except (TypeError, ValueError):
        model["n"] = 0
    return model


def load_models(root: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    path = state_path(root)
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for tool, model in data.items():
        if isinstance(tool, str) and isinstance(model, dict):
            out[tool] = _normal_model(model)
    return out


def save_models(models: Dict[str, Dict[str, Any]], root: Optional[Path] = None) -> None:
    normalized = {str(tool): _normal_model(model) for tool, model in models.items()}
    rewrite_text_locked(
        state_path(root),
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _disabled() -> bool:
    return os.environ.get("SIFTA_CEREBELLUM_DISABLE", "").strip() == "1"


def _alpha(n: int) -> float:
    return 1.0 / min(max(1, n), 20)


def context_hash(context_features: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Stable short hash for a context-conditioned forward model."""
    if not context_features:
        return None
    blob = json.dumps(context_features, sort_keys=True, separators=(",", ":"), default=str)
    return "ctx_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def model_key(tool: str, context_features: Optional[Dict[str, Any]] = None) -> str:
    ctx = context_hash(context_features)
    return f"{tool}::{ctx}" if ctx else tool


def predict(
    tool: str,
    *,
    context_features: Optional[Dict[str, Any]] = None,
    root: Optional[Path] = None,
    write_ledger: bool = False,
) -> Dict[str, Any]:
    """Predict latency, success prior, cost, and next observation template."""
    key = model_key(tool, context_features)
    ctx = context_hash(context_features)
    model = _normal_model(load_models(root).get(key))
    row: Dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "CEREBELLAR_FORWARD_PREDICTION",
        "tool": tool,
        "model_key": key,
        "context_hash": ctx,
        "context_features": context_features or {},
        "predicted_latency_s": model["latency_mu"],
        "predicted_success": model["success_rate"],
        "predicted_cost": model["cost_mu"],
        "expected_observation": model.get("expected_observation"),
        "n": model["n"],
        "disabled": _disabled(),
    }
    if write_ledger and not _disabled():
        append_line_locked(
            trace_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def observe(
    tool: str,
    started_at: float,
    success: bool,
    *,
    context_features: Optional[Dict[str, Any]] = None,
    root: Optional[Path] = None,
    actual_cost: Optional[float] = None,
    actual_observation: Optional[Any] = None,
    now: Optional[float] = None,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    """Update the forward model from observed execution error."""
    t_now = time.time() if now is None else float(now)
    actual_latency = _nonnegative(t_now - float(started_at), 0.0)
    models = load_models(root)
    key = model_key(tool, context_features)
    ctx = context_hash(context_features)
    prior = _normal_model(models.get(key))

    n = int(prior.get("n", 0)) + 1
    alpha = _alpha(n)
    old_latency = float(prior["latency_mu"])
    old_success = float(prior["success_rate"])
    old_cost = float(prior["cost_mu"])

    new_latency = old_latency + alpha * (actual_latency - old_latency)
    new_success = old_success + alpha * ((1.0 if success else 0.0) - old_success)
    new_cost = old_cost
    cost_error = None
    if actual_cost is not None:
        actual_cost_f = _nonnegative(actual_cost, 0.0)
        cost_error = round(actual_cost_f - old_cost, 4)
        new_cost = old_cost + alpha * (actual_cost_f - old_cost)

    updated = _normal_model(
        {
            "latency_mu": new_latency,
            "success_rate": new_success,
            "cost_mu": new_cost,
            "n": n,
            "expected_observation": actual_observation
            if actual_observation is not None
            else prior.get("expected_observation"),
        }
    )

    row: Dict[str, Any] = {
        "ts": t_now,
        "trace_id": str(uuid.uuid4()),
        "truth_label": "CEREBELLAR_FORWARD_OBSERVATION",
        "kind": "CEREBELLAR_PREDICTION",
        "tool": tool,
        "model_key": key,
        "context_hash": ctx,
        "context_features": context_features or {},
        "predicted_latency_s": round(old_latency, 4),
        "actual_latency_s": actual_latency,
        "latency_error": round(actual_latency - old_latency, 4),
        "predicted_success": round(old_success, 4),
        "actual_success": bool(success),
        "predicted_cost": round(old_cost, 4),
        "actual_cost": actual_cost,
        "cost_error": cost_error,
        "alpha": round(alpha, 4),
        "expected_observation_before": prior.get("expected_observation"),
        "actual_observation": actual_observation,
        "updated_tool_model": {key: updated},
        "disabled": _disabled(),
    }

    if _disabled():
        return row

    models[key] = updated
    save_models(models, root)
    if write_ledger:
        append_line_locked(
            trace_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


__all__ = [
    "DEFAULT_MODEL",
    "MODEL_FILE",
    "TRACE_FILE",
    "load_models",
    "context_hash",
    "model_key",
    "observe",
    "predict",
    "save_models",
    "state_path",
    "trace_path",
]
