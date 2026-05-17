#!/usr/bin/env python3
"""Receipt-backed thermodynamic clearance for expensive processing.

Alice can only process what her local body can afford. This organ samples the
existing body organs, decides whether a processing step may run, and writes a
hash-chained receipt for the decision.

Inputs reused from the body:
  * swarm_proto_self_interoception.read_proto_self_interoception()
  * swarm_metabolic_homeostasis.MetabolicHomeostat
  * optional thermal_cortex_state.json / energy_cortex_state.json

Truth boundary: this is a local physical budget gate. It does not claim exact
CPU die temperature when macOS exposes only thermal pressure proxies.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from System.jsonl_file_lock import append_line_locked


REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = REPO_ROOT / ".sifta_state"
LEDGER_NAME = "processing_thermodynamic_gate.jsonl"
TRUTH_LABEL = "PROCESSING_THERMODYNAMIC_GATE_V1"

_THERMAL_BLOCK_WORDS = ("serious", "critical", "danger", "trap", "panic")


def _state(state_dir: Path | str | None = None) -> Path:
    return Path(state_dir) if state_dir is not None else STATE_DIR


def _ledger_path(state_dir: Path | str | None = None) -> Path:
    return _state(state_dir) / LEDGER_NAME


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _tail_last_hash(path: Path) -> str:
    if not path.exists():
        return "GENESIS"
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            end = fh.tell()
            fh.seek(max(0, end - 64 * 1024))
            raw = fh.read().decode("utf-8", errors="replace")
        for line in reversed(raw.splitlines()):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            h = str(row.get("receipt_hash") or "")
            if h:
                return h
            return hashlib.sha256(
                json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
    except OSError:
        pass
    return "GENESIS"


def _hash_row(row: Mapping[str, Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def _thermal_state(state: Path) -> dict[str, Any]:
    row = _load_json(state / "thermal_cortex_state.json")
    pressure = str(row.get("thermal_pressure") or row.get("state") or row.get("level") or "").strip()
    return {
        "thermal_warning_level": _safe_int(row.get("thermal_warning_level"), 0),
        "thermal_pressure": pressure,
        "source": "thermal_cortex_state.json" if row else "missing",
    }


def _energy_state(state: Path) -> dict[str, Any]:
    row = _load_json(state / "energy_cortex_state.json")
    charge = row.get("charge_pct", row.get("battery_percent"))
    power_source = str(row.get("power_source") or row.get("source") or "").strip()
    low_power = bool(row.get("low_power_mode"))
    return {
        "charge_pct": _safe_float(charge, 100.0),
        "power_source": power_source,
        "low_power_mode": low_power,
        "source": "energy_cortex_state.json" if row else "missing",
    }


def _sample_body(state: Path) -> dict[str, Any]:
    body: dict[str, Any] = {}
    try:
        from System.swarm_proto_self_interoception import read_proto_self_interoception

        interoception = read_proto_self_interoception(root=state, write_ledger=True)
    except Exception as exc:
        interoception = {
            "truth_label": "PROTO_SELF_INTEROCEPTION_UNAVAILABLE",
            "error": f"{type(exc).__name__}: {exc}",
        }
    body["interoception"] = interoception

    try:
        from System.swarm_metabolic_homeostasis import MetabolicHomeostat

        homeostat = MetabolicHomeostat()
        metabolic_state = homeostat.sample_live()
        metabolic = homeostat.build_ledger_row(metabolic_state)
    except Exception as exc:
        metabolic = {
            "schema": "SIFTA_METABOLIC_HOMEOSTASIS_UNAVAILABLE",
            "error": f"{type(exc).__name__}: {exc}",
            "mode": "UNKNOWN",
            "pressure": 0.5,
            "budget_multiplier": 0.5,
            "must_rest": False,
            "rest_seconds": 0.0,
        }
    body["metabolic"] = metabolic
    body["thermal"] = _thermal_state(state)
    body["energy"] = _energy_state(state)
    return body


def _estimate_cost(process_kind: str, payload: Mapping[str, Any] | None) -> float:
    payload = dict(payload or {})
    kind = str(process_kind or "").lower()
    if "whisper" in kind or "audio" in kind:
        duration = _safe_float(payload.get("duration_s") or payload.get("window_seconds"), 8.0)
        model = str(payload.get("model") or "").lower()
        model_mult = 1.0
        if "medium" in model:
            model_mult = 1.8
        elif "small" in model:
            model_mult = 1.2
        elif "large" in model:
            model_mult = 3.0
        elif "tiny" in model:
            model_mult = 0.5
        return max(0.2, min(12.0, duration / 8.0 * model_mult))
    if "digest" in kind or "memory" in kind or "text" in kind:
        rows = _safe_float(payload.get("rows") or payload.get("max_rows"), 1.0)
        return max(0.05, min(4.0, rows / 64.0))
    return 0.5


def request_processing_clearance(
    process_kind: str,
    *,
    expected_value: float = 0.4,
    emergency: bool = False,
    payload: Mapping[str, Any] | None = None,
    state_dir: Path | str | None = None,
    write_ledger: bool = True,
    now: float | None = None,
) -> dict[str, Any]:
    """Return whether a processing step may run and optionally write receipt."""
    state = _state(state_dir)
    ts = float(now if now is not None else time.time())
    local_cost = _estimate_cost(process_kind, payload)
    body = _sample_body(state)
    intero = body.get("interoception", {})
    metabolic = body.get("metabolic", {})
    thermal = body.get("thermal", {})
    energy = body.get("energy", {})

    reasons: list[str] = []
    allowed = True
    rest_seconds = 0.0

    allostatic = _safe_float(intero.get("allostatic_load_norm"), 0.0)
    cpu_load = _safe_float(intero.get("cpu_load_norm"), 0.0)
    thermal_warning = _safe_int(thermal.get("thermal_warning_level"), 0)
    thermal_pressure = str(intero.get("thermal_pressure") or thermal.get("thermal_pressure") or "").lower()
    budget_multiplier = _safe_float(metabolic.get("budget_multiplier"), 0.5)
    metabolic_mode = str(metabolic.get("mode") or "UNKNOWN")
    metabolic_pressure = _safe_float(metabolic.get("pressure"), 0.5)
    metabolic_rest = bool(metabolic.get("must_rest"))
    low_power = bool(energy.get("low_power_mode"))
    charge = _safe_float(energy.get("charge_pct"), 100.0)

    if thermal_warning >= 3 or any(word in thermal_pressure for word in _THERMAL_BLOCK_WORDS):
        allowed = False
        rest_seconds = max(rest_seconds, 120.0)
        reasons.append("thermal_critical")
    elif thermal_warning >= 2:
        if not emergency and expected_value < 0.85:
            allowed = False
            rest_seconds = max(rest_seconds, 60.0)
            reasons.append("thermal_serious")
        else:
            reasons.append("thermal_serious_emergency_override")
    elif thermal_warning >= 1:
        reasons.append("thermal_fair_slow_path")

    if allostatic >= 0.90 and not emergency:
        allowed = False
        rest_seconds = max(rest_seconds, 90.0)
        reasons.append("allostatic_load_high")
    elif allostatic >= 0.75:
        if expected_value < 0.70 and not emergency:
            allowed = False
            rest_seconds = max(rest_seconds, 45.0)
            reasons.append("allostatic_load_elevated")
        else:
            reasons.append("allostatic_load_elevated_but_worth_it")

    if metabolic_rest and not emergency:
        allowed = False
        rest_seconds = max(rest_seconds, _safe_float(metabolic.get("rest_seconds"), 30.0))
        reasons.append("metabolic_homeostasis_rest_required")
    elif budget_multiplier <= 0.05 and expected_value < 0.95 and not emergency:
        allowed = False
        rest_seconds = max(rest_seconds, 30.0)
        reasons.append("metabolic_budget_exhausted")
    elif budget_multiplier < 0.35:
        reasons.append("metabolic_budget_low")

    if low_power or charge < 15.0:
        if expected_value < 0.75 and not emergency:
            allowed = False
            rest_seconds = max(rest_seconds, 60.0)
            reasons.append("low_power_energy_reserve")
        else:
            reasons.append("low_power_but_high_value")

    if local_cost > max(0.1, budget_multiplier * 4.0) and expected_value < max(0.55, metabolic_pressure) and not emergency:
        allowed = False
        rest_seconds = max(rest_seconds, 20.0)
        reasons.append("processing_cost_exceeds_current_budget")

    if allowed and not reasons:
        reasons.append("body_clearance_ok")

    action = "allow" if allowed else "defer"
    prev_hash = _tail_last_hash(_ledger_path(state))
    row: dict[str, Any] = {
        "ts": ts,
        "trace_id": str(uuid.uuid4()),
        "truth_label": TRUTH_LABEL,
        "process_kind": str(process_kind or "unknown"),
        "action": action,
        "allowed": bool(allowed),
        "estimated_local_unit_cost": round(local_cost, 4),
        "expected_value": round(float(expected_value), 4),
        "emergency": bool(emergency),
        "rest_seconds": round(float(rest_seconds), 3),
        "reasons": reasons,
        "body": {
            "cpu_load_norm": round(cpu_load, 4),
            "allostatic_load_norm": round(allostatic, 4),
            "thermal_warning_level": thermal_warning,
            "thermal_pressure": intero.get("thermal_pressure") or thermal.get("thermal_pressure"),
            "energy_charge_pct": round(charge, 2),
            "low_power_mode": low_power,
            "metabolic_mode": metabolic_mode,
            "metabolic_pressure": round(metabolic_pressure, 4),
            "budget_multiplier": round(budget_multiplier, 4),
            "metabolic_must_rest": metabolic_rest,
        },
        "payload_hash": hashlib.sha256(
            json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
        "raw_audio_stored": False,
        "prev_hash": prev_hash,
    }
    row["receipt_hash"] = _hash_row(row)
    if write_ledger:
        append_line_locked(_ledger_path(state), json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return row


def prompt_context(*, state_dir: Path | str | None = None) -> str:
    path = _ledger_path(state_dir)
    if not path.exists():
        return ""
    try:
        lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        if not lines:
            return ""
        row = json.loads(lines[-1])
    except Exception:
        return ""
    body = row.get("body") if isinstance(row.get("body"), dict) else {}
    return (
        "THERMODYNAMIC PROCESSING GATE: "
        f"last={row.get('process_kind')} action={row.get('action')} "
        f"reasons={','.join(str(x) for x in row.get('reasons', [])[:3])} "
        f"thermal={body.get('thermal_warning_level')} "
        f"allostatic={body.get('allostatic_load_norm')} "
        f"budget={body.get('budget_multiplier')} "
        f"receipt={str(row.get('receipt_hash') or '')[:12]}"
    )


__all__ = [
    "LEDGER_NAME",
    "TRUTH_LABEL",
    "prompt_context",
    "request_processing_clearance",
]
