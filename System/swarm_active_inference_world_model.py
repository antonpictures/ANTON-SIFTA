"""
Event 133 - Active inference world model.

Minimal generative model for:

    p(s_next, reward, harm | state, action, context)

The organ is intentionally small and receipt-driven. It stores tabular EMA
models keyed by state/action/context hashes, predicts next-state statistics,
updates from prediction error, and can rank candidate actions by expected free
energy. This is not a learned neural world model; it is the first operational
control-theory substrate that lets SIFTA compare "what I expect" to "what
happened" across action choices.

Truth labels:
  WORLD_MODEL_PREDICTION
  WORLD_MODEL_OBSERVATION
  WORLD_MODEL_ACTION_SCORE

Kill-switch: SIFTA_WORLD_MODEL_DISABLE=1.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked
from System.swarm_persistent_owner_history import state_dir

MODEL_FILE = "active_inference_world_models.json"
TRACE_FILE = "active_inference_world_model.jsonl"

BASE_MODEL: Dict[str, Any] = {
    "n": 0,
    "reward_mu": 0.0,
    "harm_mu": 0.0,
    "cost_mu": 0.0,
    "uncertainty": 1.0,
    "next_state_mu": {},
    "next_state_template": {},
}

DEFAULT_PREFERENCES: Dict[str, float] = {
    "target_reward": 1.0,
    "target_harm": 0.0,
    "reward_weight": 1.0,
    "harm_weight": 1.6,
    "uncertainty_weight": 0.35,
    "cost_weight": 0.25,
}


def model_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / MODEL_FILE


def trace_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / TRACE_FILE


def _disabled() -> bool:
    return os.environ.get("SIFTA_WORLD_MODEL_DISABLE", "").strip() == "1"


def _clamp(value: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = lo
    return round(min(hi, max(lo, f)), 4)


def _nonnegative(value: Any, fallback: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = fallback
    return round(max(0.0, f), 4)


def _alpha(n: int) -> float:
    return 1.0 / min(max(1, n), 20)


def _json_hash(prefix: str, payload: Any) -> str:
    blob = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}_{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:12]}"


def _compact(payload: Any, limit: int = 600) -> Any:
    try:
        blob = json.dumps(payload, sort_keys=True, default=str)
    except TypeError:
        return {"preview": str(payload)[:limit]}
    if len(blob) <= limit:
        return payload
    return {"preview": blob[:limit]}


def _flatten_numeric(prefix: str, value: Any, out: Dict[str, float]) -> None:
    if isinstance(value, bool):
        out[prefix] = 1.0 if value else 0.0
    elif isinstance(value, (int, float)):
        out[prefix] = round(float(value), 6)
    elif isinstance(value, dict):
        for key, child in sorted(value.items()):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten_numeric(child_prefix, child, out)


def numeric_features(payload: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    _flatten_numeric("", payload or {}, out)
    return out


def state_schema(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "state_hash": _json_hash("s", state),
        "numeric_features": numeric_features(state),
        "raw": _compact(state),
    }


def action_schema(action: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "action_hash": _json_hash("a", action),
        "name": str(action.get("name") or action.get("tool") or action.get("type") or "unknown"),
        "raw": _compact(action),
    }


def context_schema(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "context_hash": _json_hash("c", context),
        "raw": _compact(context),
    }


def model_key(
    state: Dict[str, Any],
    action: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> str:
    ss = state_schema(state)
    aa = action_schema(action)
    cc = context_schema(context or {})
    return "::".join([ss["state_hash"], aa["action_hash"], cc["context_hash"]])


def _normal_model(raw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    model = dict(BASE_MODEL)
    if raw:
        model.update(raw)
    try:
        model["n"] = max(0, int(model.get("n", 0)))
    except (TypeError, ValueError):
        model["n"] = 0
    model["reward_mu"] = _clamp(model.get("reward_mu", 0.0), lo=-1.0, hi=1.0)
    model["harm_mu"] = _clamp(model.get("harm_mu", 0.0), lo=0.0, hi=1.0)
    model["cost_mu"] = _nonnegative(model.get("cost_mu", 0.0), 0.0)
    model["uncertainty"] = _clamp(model.get("uncertainty", 1.0))
    if not isinstance(model.get("next_state_mu"), dict):
        model["next_state_mu"] = {}
    else:
        model["next_state_mu"] = {
            str(k): round(float(v), 6)
            for k, v in model["next_state_mu"].items()
            if isinstance(v, (int, float))
        }
    if not isinstance(model.get("next_state_template"), dict):
        model["next_state_template"] = {}
    return model


def load_models(root: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    raw = read_text_locked(model_path(root), encoding="utf-8", errors="replace")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(k): _normal_model(v)
        for k, v in data.items()
        if isinstance(k, str) and isinstance(v, dict)
    }


def save_models(models: Dict[str, Dict[str, Any]], root: Optional[Path] = None) -> None:
    normalized = {str(k): _normal_model(v) for k, v in models.items()}
    rewrite_text_locked(
        model_path(root),
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _state_prediction_error(predicted: Dict[str, float], actual: Dict[str, float]) -> Optional[float]:
    if not predicted or not actual:
        return None
    keys = sorted(set(predicted) & set(actual))
    if not keys:
        return None
    mse = sum((float(actual[k]) - float(predicted[k])) ** 2 for k in keys) / len(keys)
    return round(math.sqrt(mse), 6)


def predict(
    state: Dict[str, Any],
    action: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    *,
    root: Optional[Path] = None,
    write_ledger: bool = False,
) -> Dict[str, Any]:
    key = model_key(state, action, context)
    model = _normal_model(load_models(root).get(key))
    ss = state_schema(state)
    aa = action_schema(action)
    cc = context_schema(context or {})
    row: Dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "WORLD_MODEL_PREDICTION",
        "kind": "WORLD_MODEL_PREDICTION",
        "model_key": key,
        "state_schema": ss,
        "action_schema": aa,
        "context_schema": cc,
        "predicted_next_state": model["next_state_mu"],
        "predicted_reward": model["reward_mu"],
        "predicted_harm": model["harm_mu"],
        "predicted_cost": model["cost_mu"],
        "uncertainty": model["uncertainty"],
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
    state: Dict[str, Any],
    action: Dict[str, Any],
    context: Optional[Dict[str, Any]],
    next_state: Dict[str, Any],
    reward: float,
    *,
    harm: float = 0.0,
    cost: Optional[float] = None,
    root: Optional[Path] = None,
    now: Optional[float] = None,
    write_ledger: bool = True,
) -> Dict[str, Any]:
    t_now = time.time() if now is None else float(now)
    key = model_key(state, action, context)
    models = load_models(root)
    prior = _normal_model(models.get(key))
    actual_next = numeric_features(next_state)
    predicted_next = dict(prior["next_state_mu"])
    state_error = _state_prediction_error(predicted_next, actual_next)

    old_reward = float(prior["reward_mu"])
    old_harm = float(prior["harm_mu"])
    old_cost = float(prior["cost_mu"])
    n = int(prior["n"]) + 1
    alpha = _alpha(n)

    updated_next = dict(predicted_next)
    for feature, value in actual_next.items():
        old_value = updated_next.get(feature, value)
        updated_next[feature] = round(old_value + alpha * (value - old_value), 6)

    reward_f = _clamp(reward, lo=-1.0, hi=1.0)
    harm_f = _clamp(harm)
    cost_f = old_cost if cost is None else _nonnegative(cost, 0.0)
    error_for_uncertainty = 0.0 if state_error is None else min(1.0, state_error)

    updated = _normal_model(
        {
            "n": n,
            "reward_mu": old_reward + alpha * (reward_f - old_reward),
            "harm_mu": old_harm + alpha * (harm_f - old_harm),
            "cost_mu": old_cost + alpha * (cost_f - old_cost),
            "uncertainty": max(
                0.05,
                float(prior["uncertainty"]) * (1.0 - alpha) + error_for_uncertainty * alpha,
            ),
            "next_state_mu": updated_next,
            "next_state_template": _compact(next_state),
        }
    )

    row: Dict[str, Any] = {
        "ts": t_now,
        "trace_id": str(uuid.uuid4()),
        "truth_label": "WORLD_MODEL_OBSERVATION",
        "kind": "WORLD_MODEL_OBSERVATION",
        "model_key": key,
        "state_schema": state_schema(state),
        "action_schema": action_schema(action),
        "context_schema": context_schema(context or {}),
        "predicted_next_state": predicted_next,
        "actual_next_state": _compact(next_state),
        "state_prediction_error": state_error,
        "predicted_reward": round(old_reward, 4),
        "actual_reward": reward_f,
        "reward_error": round(reward_f - old_reward, 4),
        "predicted_harm": round(old_harm, 4),
        "actual_harm": harm_f,
        "harm_error": round(harm_f - old_harm, 4),
        "predicted_cost": round(old_cost, 4),
        "actual_cost": cost,
        "alpha": round(alpha, 4),
        "updated_model": updated,
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


def expected_free_energy(
    prediction: Dict[str, Any],
    preferences: Optional[Dict[str, float]] = None,
) -> float:
    prefs = dict(DEFAULT_PREFERENCES)
    if preferences:
        prefs.update(preferences)
    reward_gap = max(0.0, float(prefs["target_reward"]) - float(prediction["predicted_reward"]))
    harm_gap = max(0.0, float(prediction["predicted_harm"]) - float(prefs["target_harm"]))
    efe = (
        float(prefs["reward_weight"]) * reward_gap
        + float(prefs["harm_weight"]) * harm_gap
        + float(prefs["uncertainty_weight"]) * float(prediction["uncertainty"])
        + float(prefs["cost_weight"]) * float(prediction["predicted_cost"])
    )
    return round(max(0.0, efe), 6)


def score_actions(
    state: Dict[str, Any],
    candidate_actions: Iterable[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
    *,
    preferences: Optional[Dict[str, float]] = None,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    for action in candidate_actions:
        if not isinstance(action, dict):
            continue
        pred = predict(state, action, context, root=root, write_ledger=False)
        efe = expected_free_energy(pred, preferences)
        candidates.append(
            {
                "action": _compact(action),
                "action_hash": pred["action_schema"]["action_hash"],
                "action_name": pred["action_schema"]["name"],
                "expected_free_energy": efe,
                "predicted_reward": pred["predicted_reward"],
                "predicted_harm": pred["predicted_harm"],
                "predicted_cost": pred["predicted_cost"],
                "uncertainty": pred["uncertainty"],
                "n": pred["n"],
            }
        )

    ranked = sorted(candidates, key=lambda row: (row["expected_free_energy"], -row["n"], row["action_hash"]))
    selected = ranked[0] if ranked else None
    row: Dict[str, Any] = {
        "ts": time.time() if now is None else float(now),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "WORLD_MODEL_ACTION_SCORE",
        "kind": "WORLD_MODEL_ACTION_SCORE",
        "state_schema": state_schema(state),
        "context_schema": context_schema(context or {}),
        "preferences": dict(DEFAULT_PREFERENCES, **(preferences or {})),
        "candidates": ranked,
        "selected_action": selected["action"] if selected else None,
        "selected_action_name": selected["action_name"] if selected else None,
        "selected_expected_free_energy": selected["expected_free_energy"] if selected else None,
        "disabled": _disabled(),
    }
    if write_ledger and not _disabled():
        append_line_locked(
            trace_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def tail_world_model_rows(max_rows: int = 32, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = trace_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    out: List[Dict[str, Any]] = []
    for line in raw.splitlines()[-max(1, min(max_rows, 500)) :]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = tail_world_model_rows(1, root=root)
    if not rows:
        return ""
    row = rows[-1]
    label = row.get("truth_label", "WORLD_MODEL")
    if label == "WORLD_MODEL_ACTION_SCORE":
        return (
            "ACTIVE INFERENCE WORLD MODEL (Event 133): "
            f"selected={row.get('selected_action_name')}; "
            f"efe={row.get('selected_expected_free_energy')}"
        )
    if label == "WORLD_MODEL_OBSERVATION":
        return (
            "ACTIVE INFERENCE WORLD MODEL (Event 133): "
            f"reward_error={row.get('reward_error')}; "
            f"harm_error={row.get('harm_error')}; "
            f"state_prediction_error={row.get('state_prediction_error')}"
        )
    return "ACTIVE INFERENCE WORLD MODEL (Event 133): prediction receipt available"


__all__ = [
    "BASE_MODEL",
    "DEFAULT_PREFERENCES",
    "MODEL_FILE",
    "TRACE_FILE",
    "action_schema",
    "context_schema",
    "expected_free_energy",
    "load_models",
    "model_key",
    "model_path",
    "numeric_features",
    "observe",
    "predict",
    "save_models",
    "score_actions",
    "state_schema",
    "summary_for_prompt",
    "tail_world_model_rows",
    "trace_path",
]
