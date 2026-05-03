"""
Event 137 - Microglia Synaptic Pruner.

Controlled forgetting for SIFTA's adaptive ledgers. This organ never silently
deletes data. It writes prune/depress/correct receipts first; consumers may
later honor those receipts. Execute mode is receipt-only unless a downstream
organ explicitly implements a safe mutation path.

v8 upgrade: TREM2/CD33 two-signal pruning
-----------------------------------------
Microglia do not prune from a single score. They integrate:

  activation_signal: complement/TREM2-like "eat me" pressure
  inhibition_signal: CD33/fractalkine/"do not eat me" brake

The decision layer consumes net_pruning_pressure, not raw damage alone.

Kill switches:
  SIFTA_MICROGLIA_DISABLE=1  -> no scoring, no receipts
  SIFTA_MICROGLIA_EXECUTE=1  -> mark receipt-only correction rows as executed

Thresholds:
  MICROGLIA_STALE_HOURS
  MICROGLIA_LOW_REWARD_MEAN
  MICROGLIA_LOW_USAGE_COUNT
  MICROGLIA_HIGH_REGRET
  MICROGLIA_CONTRADICTION_PE
  MICROGLIA_NET_PRUNE_PRESSURE
  MICROGLIA_NET_DELETE_PRESSURE
  MICROGLIA_CLEARANCE_NET_PRESSURE
  MICROGLIA_SLEEP_WINDOW          JSON: {"enabled": true, "start_hour": 23, "end_hour": 7}
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from System.jsonl_file_lock import append_line_locked, read_text_locked
from System.swarm_persistent_owner_history import state_dir

_DISABLE_ENV = "SIFTA_MICROGLIA_DISABLE"
_EXECUTE_ENV = "SIFTA_MICROGLIA_EXECUTE"
_SLEEP_WINDOW_ENV = "MICROGLIA_SLEEP_WINDOW"
MAX_PRUNES_PER_CYCLE = 10
EVENT_LOG_NAME = "microglia_synaptic_prunes.jsonl"
LEGACY_CLASS_LOG_NAME = "microglia_prune.jsonl"

PruneAction = Literal["keep", "depress", "delete"]

_CRITERIA: Dict[str, float] = {
    "unused": 0.25,
    "low_reward": 0.30,
    "high_regret": 0.20,
    "contradicted": 0.15,
    "stale": 0.10,
}
assert abs(sum(_CRITERIA.values()) - 1.0) < 1e-9, "Criterion weights must sum to 1.0"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _disabled() -> bool:
    return os.environ.get(_DISABLE_ENV, "").strip() == "1"


def _execute_enabled() -> bool:
    return os.environ.get(_EXECUTE_ENV, "").strip() == "1"


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        x = default
    return min(1.0, max(0.0, x))


def _usage_norm(usage_count: int) -> float:
    return min(1.0, max(0.0, float(usage_count) / 8.0))


def _hour_in_window(hour: float, start_hour: float, end_hour: float) -> bool:
    if start_hour == end_hour:
        return True
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def microglia_sleep_window_receipt(
    *,
    now: Optional[float] = None,
    raw_config: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Decode MICROGLIA_SLEEP_WINDOW without side effects.

    Supported JSON shapes:
      {"enabled": true, "start_hour": 23, "end_hour": 7}
      {"windows": [{"name": "night", "start_hour": 23, "end_hour": 7}]}

    The returned dict is embedded in prune receipts so sleep-window clearance is
    auditable instead of hidden in a wall-clock branch.
    """
    raw = raw_config if raw_config is not None else os.environ.get(_SLEEP_WINDOW_ENV, "").strip()
    hour_struct = time.localtime(now or time.time())
    current_hour = hour_struct.tm_hour + hour_struct.tm_min / 60.0
    base: Dict[str, Any] = {
        "sleep_window_configured": False,
        "sleep_window_active": False,
        "sleep_window_name": "none",
        "sleep_current_hour": round(current_hour, 3),
        "sleep_start_hour": None,
        "sleep_end_hour": None,
        "sleep_activation_boost": 0.0,
        "sleep_net_threshold_delta": 0.0,
    }
    if not raw:
        return base
    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError:
        base.update({
            "sleep_window_configured": True,
            "sleep_window_error": "invalid_json",
        })
        return base

    windows = cfg.get("windows") if isinstance(cfg, dict) else cfg
    if isinstance(windows, dict):
        windows = [windows]
    if not isinstance(windows, list):
        windows = [cfg] if isinstance(cfg, dict) else []

    base["sleep_window_configured"] = True
    for idx, win in enumerate(windows):
        if not isinstance(win, dict) or win.get("enabled", True) is False:
            continue
        try:
            start = float(win.get("start_hour"))
            end = float(win.get("end_hour"))
        except (TypeError, ValueError):
            continue
        if _hour_in_window(current_hour, start, end):
            base.update({
                "sleep_window_active": True,
                "sleep_window_name": str(win.get("name") or f"window_{idx}"),
                "sleep_start_hour": start,
                "sleep_end_hour": end,
                "sleep_activation_boost": _clamp01(win.get("activation_boost", 0.08)),
                "sleep_net_threshold_delta": min(0.20, _clamp01(win.get("net_threshold_delta", 0.03))),
            })
            return base

    return base


def prune_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / EVENT_LOG_NAME


def _legacy_class_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LEGACY_CLASS_LOG_NAME


def _compute_damage_score(
    *,
    age_hours: float,
    usage_count: int,
    recent_reward_mean: float,
    recent_regret: float,
    wm_contradiction_pe: float,
    unsafe: bool,
) -> float:
    """
    TREM2/DAM-like damage score [0, 1].

    Damage is debris/corruption/regret/contradiction pressure. Age and weak
    activity matter, but they are not enough by themselves to override brakes.
    """
    stale_hours = _env_float("MICROGLIA_STALE_HOURS", 72.0)
    low_reward = _env_float("MICROGLIA_LOW_REWARD_MEAN", -0.1)
    high_regret = _env_float("MICROGLIA_HIGH_REGRET", 0.3)
    contradiction_pe = _env_float("MICROGLIA_CONTRADICTION_PE", 0.4)
    low_usage = _env_int("MICROGLIA_LOW_USAGE_COUNT", 1)

    dmg = 0.0
    if unsafe:
        dmg += 0.50
    if age_hours >= stale_hours and usage_count <= low_usage:
        dmg += 0.25
    if recent_reward_mean <= low_reward:
        dmg += 0.20
    if recent_regret >= high_regret:
        dmg += 0.15
    if wm_contradiction_pe >= contradiction_pe:
        dmg += 0.10
    return round(min(1.0, max(0.0, dmg)), 4)


def _compute_inhibition_signal(
    *,
    protection_score: float = 0.0,
    na_caution: float = 0.0,
    tom_pruning_conservatism: float = 0.0,
    safety_critical: bool = False,
    ledger_type: str = "adaptive_policy",
) -> float:
    """
    CD33/Siglec-like inhibition signal [0, 1].

    Safety/owner ledgers are a maximum brake. Other brakes are capped so one
    protection source cannot mask obvious corruption forever.
    """
    if safety_critical or ledger_type == "owner":
        return 1.0
    inh = 0.0
    inh += min(0.40, _clamp01(protection_score))
    inh += min(0.30, _clamp01(na_caution) * 0.30)
    inh += min(0.30, _clamp01(tom_pruning_conservatism))
    return round(min(1.0, max(0.0, inh)), 4)


def compute_two_signal_pressure(
    *,
    age_hours: float = 0.0,
    usage_count: int = 0,
    recent_reward_mean: float = 0.0,
    recent_regret: float = 0.0,
    wm_contradiction_pe: float = 0.0,
    unsafe: bool = False,
    safety_critical: bool = False,
    ledger_type: str = "adaptive_policy",
    homeostatic_pressure: float = 0.0,
    pruning_conservatism: float = 0.0,
    tom_pruning_conservatism: Optional[float] = None,
    protection_score: float = 0.0,
    recent_high_value_usage: float = 0.0,
    currently_active_in_arbiter: bool = False,
    stability_ok: bool = True,
    clamp_level: str = "NONE",
    na_level: float = 0.5,
    na_caution: Optional[float] = None,
    valence: float = 0.0,
    # Rich fractalkine upgrade (§10.14.25 — CX3CL1–CX3CR1 continuous signal)
    # Cardona et al. (2006) Nature Neuroscience 9(7):917-924
    # Paolicelli et al. (2011) Science 333(6048):1456-1458
    # Ransohoff, R.M. (2009) Nature 462(7271):183-184
    stability_dwell_score: float = 0.0,   # 0–1: how long organism has been calm
    goal_alignment: float = 0.5,          # 0–1: candidate aligned with current goals
    owner_frustration: float = 0.0,       # 0–1: from ToM; frustrated owner → less fractalkine
) -> Dict[str, float | bool | str]:
    """
    Return the TREM2/CD33 two-signal state for one candidate.

    v8.1 upgrade (§10.14.25): continuous fractalkine CX3CL1 signal replaces binary flag.
    fractalkine = stability_dwell × goal_alignment × (1 − owner_frustration × 0.5)
    This mirrors the CX3CL1–CX3CR1 'calm context' protection:
        - dwell: sustained stability allows fractalkine expression (Cardona 2006)
        - goal alignment: goal-relevant synapses are protected (Paolicelli 2011)
        - owner frustration attenuates protection (Ransohoff 2009 state-dependency)
    """
    conservatism = _clamp01(
        pruning_conservatism if tom_pruning_conservatism is None else tom_pruning_conservatism
    )
    usage = _usage_norm(usage_count)
    stale_hours = _env_float("MICROGLIA_STALE_HOURS", 72.0)
    age_norm = _clamp01(float(age_hours) / max(1.0, stale_hours))
    neg_reward = _clamp01(max(0.0, -float(recent_reward_mean)))
    positive_reward = _clamp01(max(0.0, float(recent_reward_mean)))
    contradiction = _clamp01(wm_contradiction_pe)
    high_value = max(_clamp01(recent_high_value_usage), positive_reward)

    damage_score = _compute_damage_score(
        age_hours=age_hours,
        usage_count=usage_count,
        recent_reward_mean=recent_reward_mean,
        recent_regret=recent_regret,
        wm_contradiction_pe=wm_contradiction_pe,
        unsafe=unsafe,
    )

    prune_tag = _clamp01(
        0.40 * (1.0 - usage)
        + 0.30 * neg_reward
        + 0.20 * contradiction
        + 0.10 * age_norm
    )

    owner_or_safety = 1.0 if safety_critical or ledger_type == "owner" else 0.0
    active_bonus = 1.0 if currently_active_in_arbiter else 0.0
    protection = _clamp01(
        max(_clamp01(protection_score), 0.50 * high_value + 0.30 * owner_or_safety + 0.20 * active_bonus)
    )

    na = _clamp01(na_level, 0.5)
    val = max(-1.0, min(1.0, float(valence or 0.0)))
    stress_brake_applied = False
    derived_na_caution = 0.0
    if na > 0.65 and val < -0.20 and damage_score < 0.75:
        derived_na_caution = min(1.0, (na - 0.65) + abs(val) * 0.25)
        stress_brake_applied = True
    if na_caution is not None:
        derived_na_caution = max(derived_na_caution, _clamp01(na_caution))

    inhibition_signal = _compute_inhibition_signal(
        protection_score=protection,
        na_caution=derived_na_caution,
        tom_pruning_conservatism=conservatism,
        safety_critical=safety_critical,
        ledger_type=ledger_type,
    )

    # Rich CX3CL1-CX3CR1 fractalkine signal (continuous, §10.14.25)
    # Cardona (2006): fractalkine expressed during calm/stable states, gates microglial pruning
    # Paolicelli (2011): goal-relevant synapses retain fractalkine protection longer
    # Ransohoff (2009): owner frustration / social stress attenuates CX3CL1 expression
    # Formula: fractalkine = dwell × goal_align × (1 − frustration × 0.5)
    #   capped at 0.30 so it cannot alone block a genuinely damaged synapse
    _dwell   = _clamp01(stability_dwell_score)
    _goal    = _clamp01(goal_alignment)
    _frustr  = _clamp01(owner_frustration)
    fractalkine = round(
        _clamp01(_dwell * _goal * (1.0 - _frustr * 0.5)) * 0.30,
        4,
    )
    # Fractalkine baseline: even at dwell=0, stable+no-clamp gives a small floor
    if stability_ok and clamp_level == "NONE" and damage_score < 0.50:
        fractalkine = round(max(fractalkine, 0.05), 4)   # floor (old binary was 0.03)
    inhibition_signal = round(min(1.0, inhibition_signal + fractalkine), 4)

    activation_signal = _clamp01(
        0.60 * prune_tag
        + 0.35 * damage_score
        + 0.20 * _clamp01(homeostatic_pressure)
        + (0.20 if unsafe else 0.0)
    )

    # Net-based clearance (§10.14.25.3: threshold on net, not just damage_score >= 0.75)
    # Keren-Shaul (2017) DAM Phase 2 clears when activation clearly dominates inhibition
    net_prune_threshold = _env_float("MICROGLIA_NET_PRUNE_PRESSURE", 0.12)
    net_delete_threshold = _env_float("MICROGLIA_NET_DELETE_PRESSURE", 0.55)
    clearance_mode = bool(
        (activation_signal - inhibition_signal) >= net_delete_threshold
        and stability_ok
        and clamp_level in ("NONE", "RATE_LIMIT")
        and conservatism < 0.35
    )
    if clearance_mode:
        activation_signal = _clamp01(activation_signal + 0.15)

    net = round(activation_signal - inhibition_signal, 4)
    return {
        "prune_tag":            round(prune_tag, 4),
        "damage_score":         round(damage_score, 4),
        "trem2_signal":         round(damage_score, 4),
        "protection_score":     round(protection, 4),
        "inhibition_signal":    round(inhibition_signal, 4),
        "cd33_signal":          round(inhibition_signal, 4),
        "activation_signal":    round(activation_signal, 4),
        "net_pruning_pressure": net,
        "net_signal":           net,
        # Rich fractalkine fields (§10.14.25)
        "fractalkine":          fractalkine,
        "fractalkine_analog":   fractalkine,          # legacy alias
        "stability_dwell_score": round(_dwell, 4),
        "goal_alignment":       round(_goal, 4),
        "owner_frustration":    round(_frustr, 4),
        "clearance_mode":       clearance_mode,
        "stress_brake_applied": stress_brake_applied,
        "provenance": (
            "Stevens2007Cell; Schafer2012Neuron; Jonsson2013NEJM; Griciuc2013Neuron; "
            "Keren-Shaul2017Cell; Cardona2006NatNeurosci; Paolicelli2011Science; "
            "Ransohoff2009Nature; Tononi&Cirelli2014Neuron"
        ),
    }


def evaluate_prune_candidate(
    target: str,
    *,
    age_hours: float = 0.0,
    usage_count: int = 0,
    recent_reward_mean: float = 0.0,
    recent_regret: float = 0.0,
    wm_contradiction_pe: float = 0.0,
    unsafe: bool = False,
    safety_critical: bool = False,
    ledger_type: str = "adaptive_policy",
    protection_score: float = 0.0,
    na_caution: float = 0.0,
    tom_pruning_conservatism: float = 0.0,
    homeostatic_pressure: float = 0.0,
    pruning_conservatism: float = 0.0,
    recent_high_value_usage: float = 0.0,
    currently_active_in_arbiter: bool = False,
    stability_ok: bool = True,
    clamp_level: str = "NONE",
    na_level: float = 0.5,
    valence: float = 0.0,
    # Rich fractalkine inputs (§10.14.25 — Cardona 2006; Paolicelli 2011; Ransohoff 2009)
    stability_dwell_score: float = 0.0,
    goal_alignment: float = 0.5,
    owner_frustration: float = 0.0,
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Evaluate one synapse/policy/memory candidate and append a receipt."""
    if _disabled():
        return {
            "ts": now or time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": "MICROGLIA_PRUNE",
            "kind": "MICROGLIA_PRUNE",
            "target": target,
            "disabled": True,
            "action": "disabled",
            "prune_recommended": False,
            "dry_run": True,
            "executed": False,
            "reasons": [],
        }

    conservatism = max(_clamp01(tom_pruning_conservatism), _clamp01(pruning_conservatism))
    two_signal = compute_two_signal_pressure(
        age_hours=age_hours,
        usage_count=usage_count,
        recent_reward_mean=recent_reward_mean,
        recent_regret=recent_regret,
        wm_contradiction_pe=wm_contradiction_pe,
        unsafe=unsafe,
        safety_critical=safety_critical,
        ledger_type=ledger_type,
        homeostatic_pressure=homeostatic_pressure,
        pruning_conservatism=conservatism,
        protection_score=protection_score,
        recent_high_value_usage=recent_high_value_usage,
        currently_active_in_arbiter=currently_active_in_arbiter,
        stability_ok=stability_ok,
        clamp_level=clamp_level,
        na_level=na_level,
        na_caution=na_caution,
        valence=valence,
        # Rich fractalkine (§10.14.25)
        stability_dwell_score=stability_dwell_score,
        goal_alignment=goal_alignment,
        owner_frustration=owner_frustration,
    )

    stale_hours = _env_float("MICROGLIA_STALE_HOURS", 72.0)
    low_reward_mean = _env_float("MICROGLIA_LOW_REWARD_MEAN", -0.1)
    low_usage_count = _env_int("MICROGLIA_LOW_USAGE_COUNT", 1)
    high_regret = _env_float("MICROGLIA_HIGH_REGRET", 0.3)
    contradiction_pe = _env_float("MICROGLIA_CONTRADICTION_PE", 0.4)
    net_threshold = _env_float("MICROGLIA_NET_PRUNE_PRESSURE", 0.12)
    delete_threshold = _env_float("MICROGLIA_NET_DELETE_PRESSURE", 0.55)

    reasons: List[str] = []
    if unsafe:
        reasons.append("unsafe")
    if age_hours >= stale_hours and usage_count <= low_usage_count:
        reasons.append("stale_low_usage")
    if age_hours >= stale_hours and recent_reward_mean <= low_reward_mean:
        reasons.append("stale_low_reward")
    if recent_regret >= high_regret:
        reasons.append("high_regret")
    if wm_contradiction_pe >= contradiction_pe:
        reasons.append("contradicted")
    if safety_critical or ledger_type == "owner":
        reasons.append("safety_invariant_keep")
    if bool(two_signal["clearance_mode"]):
        reasons.append("trem2_clearance_mode")
    if bool(two_signal["stress_brake_applied"]):
        reasons.append("cd33_stress_brake")
    if float(two_signal["net_pruning_pressure"]) >= net_threshold:
        reasons.append("net_pruning_pressure")

    if safety_critical or ledger_type == "owner":
        action = "none"
        prune_recommended = False
    elif unsafe:
        action = "recommend_delete"
        prune_recommended = True
    elif float(two_signal["net_pruning_pressure"]) >= delete_threshold:
        action = "recommend_delete"
        prune_recommended = True
    elif float(two_signal["net_pruning_pressure"]) >= net_threshold:
        action = "recommend_depress"
        prune_recommended = True
    elif reasons and float(two_signal["net_pruning_pressure"]) > 0.0:
        action = "recommend_depress"
        prune_recommended = True
    else:
        action = "none"
        prune_recommended = False

    execute = bool(prune_recommended and _execute_enabled())
    row: Dict[str, Any] = {
        "ts": now or time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "MICROGLIA_PRUNE",
        "kind": "MICROGLIA_PRUNE",
        "target": target,
        "ledger_type": ledger_type,
        "age_hours": float(age_hours),
        "usage_count": int(usage_count),
        "recent_reward_mean": float(recent_reward_mean),
        "recent_regret": float(recent_regret),
        "wm_contradiction_pe": float(wm_contradiction_pe),
        "homeostatic_pressure": float(homeostatic_pressure),
        "pruning_conservatism": float(conservatism),
        "recent_high_value_usage": float(recent_high_value_usage),
        "currently_active_in_arbiter": bool(currently_active_in_arbiter),
        "stability_ok": bool(stability_ok),
        "clamp_level": str(clamp_level),
        "na_level": float(na_level),
        "valence": float(valence),
        "unsafe": bool(unsafe),
        "safety_critical": bool(safety_critical),
        "reasons": reasons,
        "action": action,
        "prune_recommended": prune_recommended,
        "dry_run": not execute,
        "executed": execute,
        "execute_mode": "receipt_only" if execute else "dry_run",
        "two_signal_model": "TREM2_CD33",
        "provenance": (
            "Stevens2007_Cell; Schafer2012_Neuron; Hong2016_Science; "
            "Jonsson2013_NEJM_TREM2; Griciuc2013_Nature_CD33; Tononi_Cirelli2014_SHY"
        ),
        **two_signal,
    }

    if write_ledger:
        append_line_locked(
            prune_log_path(root),
            json.dumps(row, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return row


def batch_evaluate(
    candidates: List[Dict[str, Any]],
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
) -> List[Dict[str, Any]]:
    if _disabled():
        return []
    rows: List[Dict[str, Any]] = []
    for cand in candidates:
        target = str(cand.get("target") or cand.get("key") or cand.get("kind") or "unknown")
        rows.append(
            evaluate_prune_candidate(
                target,
                age_hours=float(cand.get("age_hours", 0.0) or 0.0),
                usage_count=int(cand.get("usage_count", 0) or 0),
                recent_reward_mean=float(cand.get("recent_reward_mean", 0.0) or 0.0),
                recent_regret=float(cand.get("recent_regret", 0.0) or 0.0),
                wm_contradiction_pe=float(cand.get("wm_contradiction_pe", 0.0) or 0.0),
                unsafe=bool(cand.get("unsafe", False)),
                safety_critical=bool(cand.get("safety_critical", False) or cand.get("invariant", False)),
                ledger_type=str(cand.get("ledger_type", "adaptive_policy")),
                protection_score=float(cand.get("protection_score", 0.0) or 0.0),
                na_caution=float(cand.get("na_caution", 0.0) or 0.0),
                tom_pruning_conservatism=float(cand.get("tom_pruning_conservatism", 0.0) or 0.0),
                homeostatic_pressure=float(cand.get("homeostatic_pressure", 0.0) or 0.0),
                pruning_conservatism=float(cand.get("pruning_conservatism", 0.0) or 0.0),
                recent_high_value_usage=float(cand.get("recent_high_value_usage", 0.0) or 0.0),
                currently_active_in_arbiter=bool(cand.get("currently_active_in_arbiter", False)),
                stability_ok=bool(cand.get("stability_ok", True)),
                clamp_level=str(cand.get("clamp_level", "NONE")),
                na_level=float(cand.get("na_level", 0.5) or 0.5),
                valence=float(cand.get("valence", 0.0) or 0.0),
                root=root,
                write_ledger=write_ledger,
            )
        )
    return rows


def tail_prune_rows(max_rows: int = 12, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = prune_log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    out: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out[-max(1, min(max_rows, 200)) :]


def _tail_legacy_rows(max_rows: int = 12, *, root: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = _legacy_class_log_path(root)
    if not path.exists():
        return []
    raw = read_text_locked(path, encoding="utf-8", errors="replace")
    out: List[Dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out[-max(1, min(max_rows, 200)) :]


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = tail_prune_rows(8, root=root)
    if not rows:
        rows = _tail_legacy_rows(8, root=root)
    if not rows:
        return ""
    active = [
        r for r in rows
        if r.get("prune_recommended") or str(r.get("action")) in {"delete", "depress", "recommend_delete", "recommend_depress"}
    ]
    executed = [r for r in rows if r.get("executed")]
    base = (
        "MICROGLIA PRUNER (Event 137): "
        f"recent={len(rows)}, recommended={len(active)}, executed_receipts={len(executed)}"
    )
    latest = rows[-1]
    if "net_pruning_pressure" in latest:
        base += (
            f" | TREM2={latest.get('damage_score')} CD33={latest.get('inhibition_signal')} "
            f"net={latest.get('net_pruning_pressure')}"
        )
    elif "damage_score" in latest:
        base += (
            f" | TREM2={latest.get('damage_score')} CD33={latest.get('inhibition_signal')} "
            f"net={latest.get('net_signal')}"
        )
    return base


class MicrogliaSynapticPruner:
    """
    Compatibility facade for the older class-level pruning API.

    It writes the legacy `microglia_prune.jsonl` receipts expected by existing
    dashboards while carrying the v8 TREM2/CD33 fields.
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = state_dir(root)
        self.log_path = _legacy_class_log_path(root)
        self._ema_pressure: float = 0.0
        self._ema_alpha: float = 0.3

    def score_entry(self, entry: Dict[str, Any]) -> Tuple[float, str]:
        scores: Dict[str, float] = {}
        scores["unused"] = _CRITERIA["unused"] if entry.get("usage_count", 1) == 0 else 0.0
        scores["low_reward"] = (
            _CRITERIA["low_reward"] if entry.get("recent_reward_mean", 0.0) < -0.1 else 0.0
        )
        scores["high_regret"] = (
            _CRITERIA["high_regret"] if entry.get("recent_regret", 0.0) > 0.3 else 0.0
        )
        scores["contradicted"] = (
            _CRITERIA["contradicted"] if entry.get("wm_contradiction_pe", 0.0) > 0.4 else 0.0
        )
        scores["stale"] = _CRITERIA["stale"] if entry.get("age_hours", 0.0) > 72.0 else 0.0

        total = min(sum(scores.values()), 1.0)
        dominant = max(scores, key=lambda k: scores[k]) if total > 0 else "none"
        return total, dominant

    def two_signal_entry(
        self,
        entry: Dict[str, Any],
        *,
        ledger_type: str = "replay",
        stability_ok: bool = True,
        pruning_conservatism: float = 0.0,
        tom_pruning_conservatism: Optional[float] = None,
        clamp_level: str = "NONE",
        na_level: float = 0.5,
        na_caution: Optional[float] = None,
        valence: float = 0.0,
        homeostatic_pressure: float = 0.0,
    ) -> Dict[str, float | bool | str]:
        return compute_two_signal_pressure(
            age_hours=float(entry.get("age_hours", 0.0) or 0.0),
            usage_count=int(entry.get("usage_count", 0) or 0),
            recent_reward_mean=float(entry.get("recent_reward_mean", 0.0) or 0.0),
            recent_regret=float(entry.get("recent_regret", 0.0) or 0.0),
            wm_contradiction_pe=float(entry.get("wm_contradiction_pe", 0.0) or 0.0),
            unsafe=bool(entry.get("unsafe", False)),
            safety_critical=bool(entry.get("safety_critical", False) or entry.get("invariant", False)),
            ledger_type=ledger_type,
            homeostatic_pressure=homeostatic_pressure,
            pruning_conservatism=pruning_conservatism,
            tom_pruning_conservatism=tom_pruning_conservatism,
            protection_score=float(entry.get("protection_score", 0.0) or 0.0),
            recent_high_value_usage=float(entry.get("recent_high_value_usage", 0.0) or 0.0),
            currently_active_in_arbiter=bool(entry.get("currently_active_in_arbiter", False)),
            stability_ok=stability_ok,
            clamp_level=clamp_level,
            na_level=na_level,
            na_caution=na_caution,
            valence=valence,
        )

    def decide_action(self, score: float, safety_critical: bool) -> PruneAction:
        if safety_critical or score < 0.4:
            return "keep"
        if score < 0.7:
            return "depress"
        return "delete"

    def compute_homeostatic_pressure(
        self,
        recent_traces: List[Dict[str, Any]],
        buffer_capacity: int = 200,
    ) -> float:
        """
        Q5 - SHY homeostatic pressure with EMA smoothing.

        P_homeo = EMA(alpha=0.3)[(sum |reward|*eligibility)/capacity - theta]
        """
        if not recent_traces:
            self._ema_pressure = self._ema_pressure * (1.0 - self._ema_alpha)
            return round(self._ema_pressure, 4)

        theta_baseline = 0.2
        total_potentiation = 0.0
        for r in recent_traces:
            reward = abs(float(r.get("recent_reward_mean", 0.0) or 0.0))
            elig = float(r.get("eligibility_trace_norm", 1.0) or 1.0)
            total_potentiation += reward * elig
        raw = total_potentiation / max(1, buffer_capacity)
        instant = max(0.0, min(1.0, raw - theta_baseline))
        self._ema_pressure = (
            self._ema_alpha * instant
            + (1.0 - self._ema_alpha) * self._ema_pressure
        )
        return round(self._ema_pressure, 4)

    def should_prune_homeostatic(
        self,
        recent_traces: List[Dict[str, Any]],
        stability_ok: bool,
        pressure_threshold: float = 0.35,
        buffer_capacity: int = 200,
    ) -> bool:
        if not stability_ok:
            return False
        pressure = self.compute_homeostatic_pressure(recent_traces, buffer_capacity)
        return pressure > pressure_threshold

    def prune(
        self,
        ledger: List[Dict[str, Any]],
        ledger_type: str = "replay",
        stability_ok: bool = True,
        *,
        max_prunes_override: Optional[int] = None,
        tail_lines_read: Optional[int] = None,
        pruning_conservatism: float = 0.0,
        tom_pruning_conservatism: Optional[float] = None,
        clamp_level: str = "NONE",
        na_level: float = 0.5,
        na_caution: Optional[float] = None,
        valence: float = 0.0,
        homeostatic_pressure: float = 0.0,
    ) -> List[Dict[str, Any]]:
        if _disabled():
            return []

        receipts: List[Dict[str, Any]] = []
        delete_count = 0
        delete_cap = MAX_PRUNES_PER_CYCLE
        if max_prunes_override is not None:
            try:
                mo = int(max_prunes_override)
            except (TypeError, ValueError):
                mo = MAX_PRUNES_PER_CYCLE
            delete_cap = max(0, min(MAX_PRUNES_PER_CYCLE, mo))

        conservatism = max(
            _clamp01(pruning_conservatism),
            _clamp01(tom_pruning_conservatism or 0.0),
        )

        for entry in ledger:
            is_safety = bool(
                entry.get("safety_critical", False)
                or ledger_type == "owner"
                or entry.get("invariant", False)
            )
            score, dominant = self.score_entry(entry)
            two_signal = self.two_signal_entry(
                entry,
                ledger_type=ledger_type,
                stability_ok=stability_ok,
                pruning_conservatism=conservatism,
                clamp_level=clamp_level,
                na_level=na_level,
                na_caution=na_caution,
                valence=valence,
                homeostatic_pressure=homeostatic_pressure,
            )
            action = self.decide_action(score, is_safety)

            if action == "delete" and not stability_ok:
                action = "depress"
            if action == "delete" and float(two_signal["inhibition_signal"]) >= 0.45:
                action = "depress"
            if action == "delete" and bool(two_signal["stress_brake_applied"]):
                action = "depress"
            if action == "delete":
                if delete_count >= delete_cap:
                    action = "depress"
                else:
                    delete_count += 1
            if action == "keep":
                continue

            receipt: Dict[str, Any] = {
                "ts": time.time(),
                "kind": "MICROGLIA_PRUNE",
                "ledger_type": ledger_type,
                "target_key": entry.get("key", entry.get("kind", "unknown")),
                "prune_score": round(score, 4),
                "dominant_criterion": dominant,
                "age_hours": entry.get("age_hours", 0.0),
                "usage_count": entry.get("usage_count", 0),
                "recent_reward_mean": entry.get("recent_reward_mean", 0.0),
                "wm_contradiction_pe": entry.get("wm_contradiction_pe", 0.0),
                "safety_critical": is_safety,
                "action": action,
                "stability_ok": stability_ok,
                "truth_label": "CONTROLLED_FORGETTING",
                "max_prunes_override_applied": max_prunes_override,
                "tail_lines_read": tail_lines_read,
                "two_signal_model": "TREM2_CD33",
                "pruning_conservatism": round(conservatism, 4),
                "tom_pruning_conservatism": round(conservatism, 4),
                "clamp_level": str(clamp_level),
                "na_level": float(na_level),
                "valence": float(valence),
                "homeostatic_pressure": float(homeostatic_pressure),
                **two_signal,
            }
            append_line_locked(self.log_path, json.dumps(receipt) + "\n", encoding="utf-8")
            receipts.append(receipt)

        return receipts


__all__ = [
    "MicrogliaSynapticPruner",
    "batch_evaluate",
    "compute_two_signal_pressure",
    "evaluate_prune_candidate",
    "prune_log_path",
    "summary_for_prompt",
    "tail_prune_rows",
    "_compute_damage_score",
    "_compute_inhibition_signal",
]
