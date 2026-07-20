#!/usr/bin/env python3
"""Receipt-backed adaptive cortex timeout policy.

The foreground Talk cortex should not use a magic constant forever. Timeout
seconds start at a conservative base and then move with the local pheromone
field: recent timeout/error receipts deposit more patience, fast clean success
receipts evaporate it back down. The policy is deterministic and bounded.
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any

try:
    from System.jsonl_file_lock import append_line_locked
except Exception:  # pragma: no cover
    append_line_locked = None  # type: ignore[assignment]

SCHEMA = "SIFTA_STIGMERGIC_TIMEOUT_POLICY_V1"
LEDGER_NAME = "stigmergic_timeout_policy.jsonl"
LOCAL_UNCENSORED_CORTEX_FALLBACK = "krishairnd/Gemma-4-Uncensored:latest"  # r1386: renamed identifier only; real Ollama tag unchanged


def _state_dir(state_dir: str | Path | None = None) -> Path:
    if state_dir is None:
        env = os.environ.get("SIFTA_STATE_DIR")
        if env:
            p = Path(env)
            return p if p.name == ".sifta_state" else (p / ".sifta_state")
        return Path(__file__).resolve().parents[1] / ".sifta_state"
    p = Path(state_dir)
    return p if p.name == ".sifta_state" else (p / ".sifta_state")


def model_key(model: str | None) -> str:
    """Group model ids into the timeout pheromone lane they belong to."""
    low = str(model or "").strip().lower()
    if low.startswith("mimo:"):
        return "mimo"
    if low.startswith("grok:") or low.startswith("xai:"):
        return "grok"
    if low.startswith("codex:"):
        return "codex"
    if low.startswith("claude:"):
        return "claude"
    if low.startswith("qwen:"):
        return "qwen"
    if low.startswith("cline:"):
        return "cline"
    if low.startswith("antigravity:"):
        return "antigravity"
    return low or "unknown"


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return rows
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def recent_outcomes(
    model: str | None,
    *,
    state_dir: str | Path | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Return recent local outcome rows plus timeout-recovery rows for a model lane."""
    sd = _state_dir(state_dir)
    key = model_key(model)
    rows: list[dict[str, Any]] = []
    for row in _iter_jsonl(sd / LEDGER_NAME):
        if row.get("model_key") == key:
            rows.append(dict(row))

    # Existing recovery receipts are also timeout pheromones. They predate this
    # organ, so normalize them into the same shape without mutating history.
    for row in _iter_jsonl(sd / "cortex_timeout_recovery.jsonl"):
        if model_key(str(row.get("model") or "")) != key:
            continue
        cause = str(row.get("cause") or "timeout")
        timeout_s = int(row.get("timeout_s") or 120)
        normalized = {
            "schema": SCHEMA,
            "trace_id": row.get("trace_id") or row.get("receipt_id") or "",
            "ts": float(row.get("ts") or 0.0),
            "model": row.get("model") or "",
            "model_key": key,
            "outcome": cause if "no_token" in cause.lower() else "timeout",
            "cause": cause,
            "timeout_s": timeout_s,
            "elapsed_s": timeout_s,
            "source": "cortex_timeout_recovery",
        }
        if "no_token" in cause.lower():
            normalized["first_token_censored_s"] = timeout_s
        rows.append(normalized)
    rows.sort(key=lambda r: float(r.get("ts") or 0.0))
    return rows[-max(1, int(limit)) :]


def timeout_for_model(
    model: str | None,
    *,
    state_dir: str | Path | None = None,
    base_s: int = 120,
    min_s: int = 60,
    max_s: int = 300,
) -> dict[str, Any]:
    """Compute bounded timeout seconds from recent success/failure pheromones."""
    rows = recent_outcomes(model, state_dir=state_dir)
    failures = [
        r for r in rows
        if str(r.get("outcome") or "").lower() in {"timeout", "error", "no_token_watchdog"}
    ]
    fast_successes = [
        r for r in rows
        if str(r.get("outcome") or "").lower() == "success"
        and float(r.get("elapsed_s") or 0.0) > 0.0
        and float(r.get("elapsed_s") or 0.0) <= max(20.0, 0.45 * float(r.get("timeout_s") or base_s))
    ]
    last = rows[-1] if rows else {}
    seconds = int(base_s)
    seconds += min(150, 30 * len(failures))
    if str(last.get("outcome") or "").lower() in {"timeout", "error", "no_token_watchdog"}:
        seconds += 30
    seconds -= min(60, 15 * len(fast_successes))
    seconds = max(int(min_s), min(int(max_s), int(seconds)))
    return {
        "schema": SCHEMA,
        "model": str(model or ""),
        "model_key": model_key(model),
        "timeout_s": seconds,
        "base_s": int(base_s),
        "min_s": int(min_s),
        "max_s": int(max_s),
        "recent_rows": len(rows),
        "recent_failures": len(failures),
        "recent_fast_successes": len(fast_successes),
        "last_outcome": str(last.get("outcome") or ""),
        "truth_label": "OBSERVED" if rows else "DEFAULT_NO_PRIOR",
    }


_FIRST_TOKEN_OUTCOMES = frozenset({"first_token", "success"})
_NO_TOKEN_OUTCOMES = frozenset({"no_token_watchdog", "body_action_no_token_watchdog"})


def _positive_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out <= 0.0 or out != out:
        return None
    return out


def _percentile(values: list[float], q: float) -> float:
    """Linear percentile for tiny local receipt samples."""
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    q = max(0.0, min(1.0, float(q)))
    pos = (len(ordered) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _first_token_samples(rows: list[dict[str, Any]]) -> tuple[list[float], int]:
    samples: list[float] = []
    censored = 0
    for row in rows:
        for key in ("first_token_latency_s", "first_token_elapsed_s", "first_token_s"):
            val = _positive_float(row.get(key))
            if val is not None:
                samples.append(val)
                break
        else:
            outcome = str(row.get("outcome") or row.get("cause") or "").lower()
            if outcome in _NO_TOKEN_OUTCOMES or "no_token" in outcome:
                lower_bound = (
                    _positive_float(row.get("first_token_censored_s"))
                    or _positive_float(row.get("elapsed_s"))
                    or _positive_float(row.get("timeout_s"))
                )
                if lower_bound is not None:
                    samples.append(lower_bound)
                    censored += 1
    return samples, censored


def first_token_patience_for_model(
    model: str | None,
    *,
    state_dir: str | Path | None = None,
    floor_s: float = 12.0,
    default_s: float | None = None,
    max_s: float = 300.0,
    percentile: float = 0.95,
    limit: int = 32,
) -> dict[str, Any]:
    """Learn a bounded first-token wait window from this model lane's receipts.

    Successful first-token receipts contribute the observed latency. No-token
    watchdog receipts contribute a censored lower bound: the model needed at
    least that long. Slow cortexes earn patience without unbounded hangs.
    """
    rows = recent_outcomes(model, state_dir=state_dir, limit=limit)
    samples, censored = _first_token_samples(rows)
    floor = max(1.0, float(floor_s or 12.0))
    ceiling = max(floor, float(max_s or floor))
    default = floor if default_s is None else max(floor, float(default_s))
    p = _percentile(samples, percentile) if samples else 0.0
    cushion = min(30.0, max(2.0, p * 0.15)) if samples else 0.0
    seconds = default if not samples else max(default, p + cushion)
    seconds = max(floor, min(ceiling, seconds))
    return {
        "schema": SCHEMA,
        "model": str(model or ""),
        "model_key": model_key(model),
        "patience_s": round(float(seconds), 3),
        "floor_s": round(float(floor), 3),
        "default_s": round(float(default), 3),
        "max_s": round(float(ceiling), 3),
        "percentile": float(percentile),
        "sample_count": len(samples),
        "censored_sample_count": censored,
        "p_latency_s": round(float(p), 3) if samples else 0.0,
        "truth_label": "OBSERVED" if samples else "DEFAULT_NO_PRIOR",
    }


def record_timeout_outcome(
    model: str | None,
    *,
    outcome: str,
    timeout_s: int,
    elapsed_s: float | None = None,
    first_token_latency_s: float | None = None,
    context_chars: int | None = None,
    context_messages: int | None = None,
    finish_reason: str = "",
    fallback_model: str = "",
    detail: str = "",
    state_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Append one outcome receipt for future timeout decisions."""
    outcome_s = str(outcome or "unknown")
    row = {
        "schema": SCHEMA,
        "trace_id": str(uuid.uuid4()),
        "ts": time.time(),
        "model": str(model or ""),
        "model_key": model_key(model),
        "outcome": outcome_s,
        "timeout_s": int(timeout_s or 0),
        "elapsed_s": round(float(elapsed_s or 0.0), 3),
        "fallback_model": str(fallback_model or ""),
        "detail": str(detail or "")[:240],
        "truth_label": "FAILED" if outcome_s.lower() == "empty_output_failed" else "OBSERVED",
    }
    first_token_latency = _positive_float(first_token_latency_s)
    if first_token_latency is not None:
        row["first_token_latency_s"] = round(first_token_latency, 3)
    try:
        if context_chars is not None and int(context_chars) >= 0:
            row["context_chars"] = int(context_chars)
    except Exception:
        pass
    try:
        if context_messages is not None and int(context_messages) >= 0:
            row["context_messages"] = int(context_messages)
    except Exception:
        pass
    finish_reason_s = str(finish_reason or "").strip()
    if finish_reason_s:
        row["finish_reason"] = finish_reason_s[:120]
    sd = _state_dir(state_dir)
    path = sd / LEDGER_NAME
    line = json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
    if append_line_locked is not None:
        append_line_locked(path, line)
    else:  # pragma: no cover
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    return row


def local_fallback_for_model(model: str | None) -> str:
    """Return the local fallback cortex for a cloud/teacher model, if any."""
    if model_key(model) == "mimo":
        try:
            from System.sifta_inference_defaults import resolve_live_local_ollama_default

            live = resolve_live_local_ollama_default()
            if live:
                return live
        except Exception:
            pass
        return LOCAL_UNCENSORED_CORTEX_FALLBACK
    return ""


_FAILURE_OUTCOMES = frozenset({"timeout", "error", "no_token_watchdog"})


def should_fast_fallback_cloud(
    model: str | None,
    *,
    state_dir: str | Path | None = None,
    cooldown_s: int = 900,
) -> dict[str, Any]:
    """True when a cloud/teacher cortex recently failed and should not block the owner again.

    After a timeout/error receipt, the foreground Talk ladder should answer on the local
    fallback first instead of waiting through another full cloud timeout."""
    key = model_key(model)
    low = str(model or "").strip().lower()
    is_cloud_lane = bool(low) and (
        low.startswith("mimo:")
        or low.startswith("grok:")
        or low.startswith("xai:")
        or low.startswith("claude:")
        or low.startswith("codex:")
        or low.startswith("qwen:")
        or low.startswith("cline:")
        or low.startswith("antigravity:")
    )
    if not is_cloud_lane:
        return {
            "schema": SCHEMA,
            "model": str(model or ""),
            "model_key": key,
            "fast_fallback": False,
            "local_fallback": "",
            "truth_label": "NOT_CLOUD_LANE",
        }
    rows = recent_outcomes(model, state_dir=state_dir, limit=4)
    if not rows:
        return {
            "schema": SCHEMA,
            "model": str(model or ""),
            "model_key": key,
            "fast_fallback": False,
            "local_fallback": local_fallback_for_model(model),
            "truth_label": "DEFAULT_NO_PRIOR",
        }
    last = rows[-1]
    outcome = str(last.get("outcome") or "").lower()
    age_s = max(0.0, time.time() - float(last.get("ts") or 0.0))
    fast = outcome in _FAILURE_OUTCOMES and age_s <= max(60, int(cooldown_s))
    fallback = local_fallback_for_model(model)
    return {
        "schema": SCHEMA,
        "model": str(model or ""),
        "model_key": key,
        "fast_fallback": bool(fast and fallback),
        "local_fallback": fallback if fast else "",
        "last_outcome": outcome,
        "age_s": round(age_s, 1),
        "cooldown_s": int(cooldown_s),
        "truth_label": "OBSERVED" if rows else "DEFAULT_NO_PRIOR",
    }


__all__ = [
    "SCHEMA",
    "LEDGER_NAME",
    "LOCAL_UNCENSORED_CORTEX_FALLBACK",
    "model_key",
    "recent_outcomes",
    "timeout_for_model",
    "first_token_patience_for_model",
    "record_timeout_outcome",
    "local_fallback_for_model",
    "should_fast_fallback_cloud",
]
