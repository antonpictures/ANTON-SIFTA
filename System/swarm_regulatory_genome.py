"""
Regulatory genome — modest second-order closure (§10.14.32.5).

Append-only `.sifta_state/regulatory_genome.jsonl`; five bounded parameters;
MetacognitiveMonitor + Arbiter may propose updates; governance reset.
"""
from __future__ import annotations

import json
import math
import time
import uuid
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    def read_text_locked(path: Path, **kw: Any) -> str:
        return path.read_text(**kw) if path.exists() else ""

    def append_line_locked(path: Path, line: str, **kw: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kw) as f:
            f.write(line)

try:
    from System.swarm_persistent_owner_history import state_dir
except ImportError:
    def state_dir(root: Optional[Path] = None) -> Path:
        return Path(root) if root else Path(".sifta_state")


LOG_NAME = "regulatory_genome.jsonl"
LEASE_NAME = "regulatory_genome_lease.json"
UPDATE_THROTTLE_TICKS = 20
THIRD_ORDER_WINDOW = 3

BOUNDS: Dict[str, Dict[str, float]] = {
    "metacog_evidence_threshold":          {"min": 0.30, "max": 0.85, "default": 0.50},
    "arbiter_risk_weight":                 {"min": 0.50, "max": 2.50, "default": 1.00},
    "arbiter_exploration_temperature":     {"min": 0.40, "max": 1.60, "default": 1.00},
    "causal_prober_uncertainty_threshold": {"min": 0.20, "max": 0.70, "default": 0.50},
    "microglia_priming_half_life_hours":   {"min": 6.0,  "max": 168.0, "default": 48.0},
}

META_RULE_BOUNDS: Dict[str, Dict[str, float]] = {
    "meta_adjustment_rate": {"min": 0.02, "max": 0.20, "default": 0.05},
}

ADJUST = {
    "metacog_evidence_threshold":          0.05,
    "arbiter_risk_weight":                 0.10,
    "arbiter_exploration_temperature":     0.05,
    "causal_prober_uncertainty_threshold": 0.05,
    "microglia_priming_half_life_hours":   6.0,
}


def get_regulatory_genome_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def _hash_row(row_str: str) -> str:
    return "sha256:" + hashlib.sha256(row_str.encode("utf-8")).hexdigest()


def _last_genome_update_row(path: Path) -> Optional[Dict[str, Any]]:
    for line in reversed(_read_all_lines(path)):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") == "REGULATORY_GENOME_UPDATE" and row.get("bounds_check") == "passed":
            return row
    return None

def load_latest_genome_row(root: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    path = get_regulatory_genome_path(root)
    return _last_genome_update_row(path)


def _read_all_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    try:
        return [l for l in read_text_locked(path, encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


def _append_reject(
    root: Optional[Path],
    *,
    reason: str,
    detail: Dict[str, Any],
) -> None:
    path = get_regulatory_genome_path(root)
    row = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "REGULATORY_GENOME_REJECT",
        "kind": "REGULATORY_GENOME_REJECT",
        "reason": reason,
        "detail": detail,
    }
    append_line_locked(path, json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")


def default_regulatory_parameters() -> Dict[str, float]:
    return {k: float(v["default"]) for k, v in BOUNDS.items()}


def default_regulatory_meta_rules() -> Dict[str, float]:
    return {k: float(v["default"]) for k, v in META_RULE_BOUNDS.items()}


def _validate_params_dict(params: Dict[str, Any]) -> Tuple[bool, Dict[str, float], str]:
    out: Dict[str, float] = {}
    for k, spec in BOUNDS.items():
        raw = params.get(k, spec["default"])
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return False, default_regulatory_parameters(), f"non_numeric:{k}"
        if val < spec["min"] or val > spec["max"]:
            return False, default_regulatory_parameters(), f"out_of_bounds:{k}"
        out[k] = val
    return True, out, "ok"


def _validate_meta_rules(meta_rules: Dict[str, Any]) -> Tuple[bool, Dict[str, float], str]:
    out: Dict[str, float] = {}
    for k, spec in META_RULE_BOUNDS.items():
        raw = meta_rules.get(k, spec["default"])
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return False, default_regulatory_meta_rules(), f"non_numeric:{k}"
        if val < spec["min"] or val > spec["max"]:
            return False, default_regulatory_meta_rules(), f"out_of_bounds:{k}"
        out[k] = val
    return True, out, "ok"


def _tail_genome_update_rows(path: Path, limit: int = 12) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in _read_all_lines(path):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") == "REGULATORY_GENOME_UPDATE" and row.get("bounds_check") == "passed":
            rows.append(row)
    return rows[-max(1, limit):]


def load_regulatory_meta_rules(root: Optional[Path] = None) -> Dict[str, float]:
    """Latest bounded third-order rules for future genome updates."""
    path = get_regulatory_genome_path(root)
    for row in reversed(_tail_genome_update_rows(path, 40)):
        meta_rules = row.get("meta_rules") or {}
        ok, validated, _ = _validate_meta_rules(meta_rules)
        if ok:
            return validated
    return default_regulatory_meta_rules()


def load_regulatory_parameters(
    root: Optional[Path] = None,
    *,
    current_tick: Optional[int] = None,
    decay_after_ticks: int = 500,
) -> Dict[str, float]:
    """
    Latest persisted parameters, clamped to bounds.

    Staleness:
    - If the last REGULATORY_GENOME_UPDATE row carries ``tick_id`` and ``current_tick``
      is provided, decay uses tick age (spec).
    - Otherwise falls back to wall-clock seconds since ``ts`` (legacy / tests).
    """
    defaults = default_regulatory_parameters()
    path = get_regulatory_genome_path(root)
    last: Optional[Dict[str, Any]] = None
    for line in reversed(_read_all_lines(path)):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") != "REGULATORY_GENOME_UPDATE":
            continue
        if row.get("bounds_check") != "passed":
            continue
        last = row
        break

    if not last:
        return defaults

    params = last.get("parameters") or {}
    ok, validated, _ = _validate_params_dict(params)
    if not ok:
        return defaults

    row_tick = last.get("tick_id")
    if current_tick is not None and row_tick is not None:
        try:
            age_ticks = int(current_tick) - int(row_tick)
        except (TypeError, ValueError):
            age_ticks = 0
        if age_ticks > 0:
            span = float(decay_after_ticks) if decay_after_ticks else 1.0
            blend = math.exp(-age_ticks / span)
            blended: Dict[str, float] = {}
            for k, v in validated.items():
                blended[k] = float(defaults[k]) + (float(v) - float(defaults[k])) * blend
            ok2, out, _ = _validate_params_dict(blended)
            return out if ok2 else defaults
    else:
        row_ts = float(last.get("ts", time.time()))
        age_sec = time.time() - row_ts
        if age_sec > 0:
            span_sec = float(decay_after_ticks) if decay_after_ticks else 1.0
            blend = math.exp(-age_sec / span_sec)
            blended2: Dict[str, float] = {}
            for k, v in validated.items():
                blended2[k] = float(defaults[k]) + (float(v) - float(defaults[k])) * blend
            ok3, out2, _ = _validate_params_dict(blended2)
            return out2 if ok3 else defaults

    return validated


def _parameter_delta(previous: Dict[str, float], current: Dict[str, float]) -> Dict[str, float]:
    return {
        key: round(float(current.get(key, 0.0)) - float(previous.get(key, 0.0)), 6)
        for key in BOUNDS
    }


def _clip_meta_rule(key: str, value: float) -> float:
    spec = META_RULE_BOUNDS[key]
    return round(max(float(spec["min"]), min(float(spec["max"]), float(value))), 4)


def _third_order_streak(
    rows: List[Dict[str, Any]],
    *,
    key: str,
    direction: int,
) -> int:
    """Consecutive prior genome rows whose parameter delta moved in one direction."""
    streak = 0
    for row in reversed(rows):
        delta = row.get("parameter_delta") or {}
        try:
            val = float(delta.get(key, 0.0) or 0.0)
        except (TypeError, ValueError):
            break
        if direction > 0 and val > 0:
            streak += 1
            continue
        if direction < 0 and val < 0:
            streak += 1
            continue
        break
    return streak


def apply_third_order_closure(
    previous_params: Dict[str, float],
    proposed_params: Dict[str, float],
    trigger_context: Dict[str, Any],
    source: str,
    root: Optional[Path] = None,
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, Any]]:
    """
    Light third-order closure: update rules can adapt to sustained update patterns.

    Minimal ratified rule:
      If metacog keeps raising its evidence threshold during chronic DAM Stage 2,
      slightly raise microglia priming half-life and the meta adjustment rate.

    This remains bounded, append-only, and separate from consumer-facing parameters.
    """
    path = get_regulatory_genome_path(root)
    current_meta = load_regulatory_meta_rules(root)
    next_meta = dict(current_meta)
    next_params = dict(proposed_params)
    deltas = _parameter_delta(previous_params, proposed_params)
    closure: Dict[str, Any] = {
        "applied": False,
        "rule": "none",
        "window": THIRD_ORDER_WINDOW,
        "meta_rules_before": current_meta,
    }

    dam_stage = int(trigger_context.get("dam_stage", 0) or 0)
    sustained_regime = str(trigger_context.get("sustained_regime", ""))
    meta_delta = deltas.get("metacog_evidence_threshold", 0.0)
    if source == "MetacognitiveMonitor" and dam_stage >= 2 and sustained_regime == "UNDERCONFIDENT" and meta_delta > 0:
        prior_streak = _third_order_streak(
            _tail_genome_update_rows(path, 12),
            key="metacog_evidence_threshold",
            direction=1,
        )
        streak_with_current = prior_streak + 1
        closure.update({
            "rule": "metacog_threshold_up_under_chronic_dam",
            "prior_streak": prior_streak,
            "streak_with_current": streak_with_current,
        })
        if streak_with_current >= THIRD_ORDER_WINDOW:
            meta_before = float(current_meta["meta_adjustment_rate"])
            meta_after = _clip_meta_rule("meta_adjustment_rate", meta_before + 0.01)
            next_meta["meta_adjustment_rate"] = meta_after
            half_life_before = float(next_params["microglia_priming_half_life_hours"])
            half_life_delta = max(
                1.0,
                ADJUST["microglia_priming_half_life_hours"] * meta_after,
            )
            half_life_after = min(
                BOUNDS["microglia_priming_half_life_hours"]["max"],
                half_life_before + half_life_delta,
            )
            next_params["microglia_priming_half_life_hours"] = round(half_life_after, 4)
            closure.update({
                "applied": True,
                "parameter_injected": "microglia_priming_half_life_hours",
                "parameter_before": round(half_life_before, 4),
                "parameter_after": round(half_life_after, 4),
                "meta_adjustment_rate_before": meta_before,
                "meta_adjustment_rate_after": meta_after,
            })

    if not closure["applied"]:
        default_meta = default_regulatory_meta_rules()["meta_adjustment_rate"]
        current_rate = float(current_meta["meta_adjustment_rate"])
        if current_rate > default_meta:
            next_meta["meta_adjustment_rate"] = _clip_meta_rule(
                "meta_adjustment_rate",
                max(default_meta, current_rate - 0.005),
            )
            closure.update({
                "rule": "meta_adjustment_rate_decay",
                "meta_adjustment_rate_before": current_rate,
                "meta_adjustment_rate_after": next_meta["meta_adjustment_rate"],
            })

    closure["meta_rules_after"] = next_meta
    return next_params, next_meta, closure


def get_latest_genome_hash(root: Optional[Path] = None) -> str:
    path = get_regulatory_genome_path(root)
    lines = _read_all_lines(path)
    if not lines:
        return "sha256:genesis"
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") == "REGULATORY_GENOME_UPDATE" and row.get("bounds_check") == "passed":
            return _hash_row(line)
    return _hash_row(lines[-1])


def _acquire_lease(root: Optional[Path], writer_id: str, current_tick_id: int) -> bool:
    lease_path = state_dir(root) / LEASE_NAME
    now = time.time()
    try:
        if lease_path.exists():
            lease = json.loads(lease_path.read_text(encoding="utf-8"))
            if lease.get("writer_id") != writer_id:
                # TTL 30 ticks approx 30 seconds
                if now - lease.get("acquired_ts", 0) < 30.0:
                    return False
    except Exception:
        pass
    
    try:
        with open(lease_path, "w", encoding="utf-8") as f:
            json.dump({
                "writer_id": writer_id,
                "acquired_tick": current_tick_id,
                "acquired_ts": now,
                "ttl_ticks": 30
            }, f)
        return True
    except Exception:
        return False

def _throttle_blocks(
    path: Path,
    *,
    current_tick_id: Optional[int],
) -> bool:
    """Return True if we should block (still in throttle window)."""
    last = _last_genome_update_row(path)
    if not last:
        return False
    if last.get("governance_override"):
        return False
    lt = last.get("tick_id")
    if current_tick_id is not None and lt is not None:
        try:
            return int(current_tick_id) - int(lt) < UPDATE_THROTTLE_TICKS
        except (TypeError, ValueError):
            pass
    last_ts = float(last.get("ts", 0))
    return (time.time() - last_ts) < float(UPDATE_THROTTLE_TICKS)


def propose_regulatory_update(
    proposed: Dict[str, float],
    trigger_context: Dict[str, Any],
    source: str,
    root: Optional[Path] = None,
    *,
    current_tick_id: Optional[int] = None,
    governance_token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if source not in ("MetacognitiveMonitor", "Arbiter"):
        _append_reject(root, reason="bad_source", detail={"source": source})
        return None

    path = get_regulatory_genome_path(root)
    
    if current_tick_id is not None:
        if not _acquire_lease(root, source, current_tick_id):
            return None

    if _throttle_blocks(path, current_tick_id=current_tick_id):
        return None

    if source == "MetacognitiveMonitor":
        allowed_keys = {
            "metacog_evidence_threshold",
            "arbiter_risk_weight",
            "causal_prober_uncertainty_threshold",
            "microglia_priming_half_life_hours",
        }
        regime = str(trigger_context.get("sustained_regime", ""))
        duration = int(trigger_context.get("duration_ticks", 0))
        dam_stage = int(trigger_context.get("dam_stage", 0))
        tme_phase = str(trigger_context.get("tme_phase", ""))
        valid = False
        if regime == "UNDERCONFIDENT" and duration >= 30 and dam_stage >= 1:
            valid = True
        elif regime == "OVERCONFIDENT" and duration >= 20 and tme_phase == "ESCAPE":
            valid = True
        if not valid:
            return None
    elif source == "Arbiter":
        allowed_keys = {"arbiter_risk_weight", "arbiter_exploration_temperature"}
        duration = int(trigger_context.get("duration_ticks", 0))
        resilience = float(trigger_context.get("resilience_floor", 0.0))
        regret = float(trigger_context.get("avg_regret", 0.0))
        if not (duration >= 40 and resilience >= 0.08 and regret > 0.2):
            return None
    else:
        allowed_keys = set()

    current_params = load_regulatory_parameters(root, current_tick=current_tick_id)
    new_params = dict(current_params)
    for k, v in proposed.items():
        if k not in allowed_keys or k not in BOUNDS:
            continue
        if k == "microglia_priming_half_life_hours" and not governance_token:
            _append_reject(root, reason="missing_nppl_token", detail={"key": k, "source": source})
            continue
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        if val < BOUNDS[k]["min"] or val > BOUNDS[k]["max"]:
            _append_reject(
                root,
                reason="bounds_violation",
                detail={"key": k, "value": val, "source": source},
            )
            return None
        new_params[k] = val

    if new_params == current_params:
        return None

    new_params, meta_rules, third_order = apply_third_order_closure(
        current_params,
        new_params,
        trigger_context,
        source,
        root,
    )

    prev_hash = get_latest_genome_hash(root)
    row: Dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "REGULATORY_GENOME_UPDATE",
        "kind": "REGULATORY_GENOME_UPDATE",
        "version": 1,
        "parameters": new_params,
        "previous_parameters": current_params,
        "parameter_delta": _parameter_delta(current_params, new_params),
        "meta_rules": meta_rules,
        "third_order_closure": third_order,
        "trigger_context": trigger_context,
        "biological_steering": {
            "source": source,
            "reason": f"Sustained condition detected by {source}",
        },
        "bounds_check": "passed",
        "governance_override": False,
        "prev_row_hash": prev_hash,
    }
    if current_tick_id is not None:
        row["tick_id"] = int(current_tick_id)

    row_str = json.dumps(row, sort_keys=True)
    append_line_locked(path, row_str + "\n", encoding="utf-8")
    return row


def reset_regulatory_genome(
    reason: str = "governance_reset",
    root: Optional[Path] = None,
    *,
    current_tick_id: Optional[int] = None,
) -> Dict[str, Any]:
    path = get_regulatory_genome_path(root)
    
    # Safeguard: if >3 resets within 100 ticks, emit a high-severity governance event
    reset_count = 0
    for line in reversed(_read_all_lines(path)):
        try:
            r = json.loads(line)
            if r.get("governance_override"):
                r_tick = r.get("tick_id")
                if current_tick_id and r_tick and (current_tick_id - int(r_tick)) <= 100:
                    reset_count += 1
        except Exception:
            continue
    
    if reset_count > 3:
        # Emit high severity governance event (write directly to ledger as a warning)
        append_line_locked(
            path,
            json.dumps({
                "ts": time.time(),
                "trace_id": str(uuid.uuid4()),
                "truth_label": "GOVERNANCE_WARNING",
                "message": "High frequency of regulatory resets detected."
            }) + "\n",
            encoding="utf-8"
        )
    
    prev_hash = get_latest_genome_hash(root)
    defaults = default_regulatory_parameters()
    row: Dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "REGULATORY_GENOME_UPDATE",
        "kind": "REGULATORY_GENOME_UPDATE",
        "version": 1,
        "parameters": defaults,
        "previous_parameters": load_regulatory_parameters(root, current_tick=current_tick_id),
        "parameter_delta": _parameter_delta(load_regulatory_parameters(root, current_tick=current_tick_id), defaults),
        "meta_rules": default_regulatory_meta_rules(),
        "third_order_closure": {
            "applied": False,
            "rule": "governance_reset",
            "meta_rules_after": default_regulatory_meta_rules(),
        },
        "trigger_context": {"reason": reason},
        "biological_steering": {"source": "Governance", "reason": reason},
        "bounds_check": "passed",
        "governance_override": True,
        "prev_row_hash": prev_hash,
    }
    if current_tick_id is not None:
        row["tick_id"] = int(current_tick_id)
    append_line_locked(path, json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
    return row


def _tail_metacog_rows(sd: Path, limit: int = 80) -> List[Dict[str, Any]]:
    path = sd / "metacognitive_state.jsonl"
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("kind") == "METACOGNITIVE_STATE":
            rows.append(r)
    return rows[-limit:]


def _underconf_streak(rows_tail: List[Dict[str, Any]]) -> int:
    streak = 0
    for r in reversed(rows_tail):
        if r.get("metacog_regime") != "UNDERCONFIDENT":
            break
        streak += 1
    return streak


def _overconf_streak(rows_tail: List[Dict[str, Any]]) -> int:
    streak = 0
    for r in reversed(rows_tail):
        if r.get("metacog_regime") != "OVERCONFIDENT":
            break
        streak += 1
    return streak


def maybe_append_from_metacognitive_tick(
    sd: Path,
    tick_id: int,
    regime: str,
    dam_stage: int,
    tme_phase: str,
    na_level: float,
) -> Optional[Dict[str, Any]]:
    """
    Called after a METACOGNITIVE_STATE row is appended. Uses ledger tail for streak length.
    """
    tail = _tail_metacog_rows(sd, 120)
    cur = load_regulatory_parameters(sd, current_tick=tick_id)

    if regime == "UNDERCONFIDENT" and dam_stage >= 1:
        streak = _underconf_streak(tail)
        if streak >= 30:
            proposed = {
                "metacog_evidence_threshold": min(
                    BOUNDS["metacog_evidence_threshold"]["max"],
                    cur["metacog_evidence_threshold"] + ADJUST["metacog_evidence_threshold"],
                ),
                "arbiter_risk_weight": min(
                    BOUNDS["arbiter_risk_weight"]["max"],
                    cur["arbiter_risk_weight"] + ADJUST["arbiter_risk_weight"],
                ),
                "microglia_priming_half_life_hours": min(
                    BOUNDS["microglia_priming_half_life_hours"]["max"],
                    cur["microglia_priming_half_life_hours"] + ADJUST["microglia_priming_half_life_hours"],
                ),
            }
            return propose_regulatory_update(
                proposed,
                {
                    "dam_stage": dam_stage,
                    "tme_phase": tme_phase,
                    "na_level": na_level,
                    "sustained_regime": "UNDERCONFIDENT",
                    "duration_ticks": streak,
                },
                "MetacognitiveMonitor",
                sd,
                current_tick_id=tick_id,
            )

    if regime == "OVERCONFIDENT" and tme_phase == "ESCAPE":
        streak = _overconf_streak(tail)
        if streak >= 20:
            proposed = {
                "causal_prober_uncertainty_threshold": max(
                    BOUNDS["causal_prober_uncertainty_threshold"]["min"],
                    cur["causal_prober_uncertainty_threshold"] - ADJUST["causal_prober_uncertainty_threshold"],
                ),
                "arbiter_exploration_temperature": min(
                    BOUNDS["arbiter_exploration_temperature"]["max"],
                    cur["arbiter_exploration_temperature"] + ADJUST["arbiter_exploration_temperature"],
                ),
            }
            return propose_regulatory_update(
                proposed,
                {
                    "dam_stage": dam_stage,
                    "tme_phase": tme_phase,
                    "na_level": na_level,
                    "sustained_regime": "OVERCONFIDENT",
                    "duration_ticks": streak,
                },
                "MetacognitiveMonitor",
                sd,
                current_tick_id=tick_id,
            )
    return None


def _arbiter_selection_tail(root: Path, limit: int = 25) -> List[Dict[str, Any]]:
    path = root / "pfc_basal_ganglia_arbiter.jsonl"
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in read_text_locked(path, encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("truth_label") == "PFC_BG_ACTION_SELECTION":
            rows.append(r)
    return rows[-limit:]


def maybe_append_from_arbiter_tick(
    root: Path,
    tick_id: int,
    resilience_floor: float,
) -> Optional[Dict[str, Any]]:
    rows = _arbiter_selection_tail(root, 45)
    if len(rows) < 15:
        return None
    regrets: List[float] = []
    
    # Calculate safe baseline risk
    all_risks = [float(r.get("details", {}).get("risk", 0.1) or 0.1) for r in rows[-15:]]
    all_risks.sort()
    bottom_25_count = max(1, len(all_risks) // 4)
    safe_baseline_risk = sum(all_risks[:bottom_25_count]) / bottom_25_count

    for r in rows[-15:]:
        det = r.get("details") or {}
        risk = float(det.get("risk", 0.1) or 0.1)
        gw = float(det.get("gw_salience", 0.0) or 0.0)
        exploratory = gw > 0.35
        if exploratory:
            regrets.append(max(0.0, risk - safe_baseline_risk))
        else:
            regrets.append(max(0.0, risk - safe_baseline_risk))
    avg_regret = sum(regrets) / len(regrets) if regrets else 0.0
    if len(rows) < 40 or resilience_floor < 0.08 or avg_regret <= 0.2:
        return None

    cur = load_regulatory_parameters(root, current_tick=tick_id)
    proposed = {
        "arbiter_risk_weight": min(
            BOUNDS["arbiter_risk_weight"]["max"],
            cur["arbiter_risk_weight"] + ADJUST["arbiter_risk_weight"],
        ),
        "arbiter_exploration_temperature": max(
            BOUNDS["arbiter_exploration_temperature"]["min"],
            cur["arbiter_exploration_temperature"] - ADJUST["arbiter_exploration_temperature"],
        ),
    }
    return propose_regulatory_update(
        proposed,
        {
            "duration_ticks": len(rows),
            "resilience_floor": resilience_floor,
            "avg_regret": round(avg_regret, 4),
        },
        "Arbiter",
        root,
        current_tick_id=tick_id,
    )


__all__ = [
    "ADJUST",
    "BOUNDS",
    "META_RULE_BOUNDS",
    "apply_third_order_closure",
    "default_regulatory_meta_rules",
    "default_regulatory_parameters",
    "get_latest_genome_hash",
    "get_regulatory_genome_path",
    "load_regulatory_meta_rules",
    "load_regulatory_parameters",
    "maybe_append_from_arbiter_tick",
    "maybe_append_from_metacognitive_tick",
    "propose_regulatory_update",
    "reset_regulatory_genome",
]
