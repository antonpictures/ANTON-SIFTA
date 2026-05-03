"""
Event 137 — Microglia Synaptic Pruner.

Controlled forgetting for SIFTA's adaptive ledgers. This organ never silently
deletes data. It writes prune/depress/correct receipts first; consumers may
later honor those receipts. Execute mode is receipt-only unless a downstream
organ explicitly implements a safe mutation path.

Kill switches:
  SIFTA_MICROGLIA_DISABLE=1  -> no scoring, no receipts
  SIFTA_MICROGLIA_EXECUTE=1  -> mark receipt-only correction rows as executed

Thresholds:
  MICROGLIA_STALE_HOURS
  MICROGLIA_LOW_REWARD_MEAN
  MICROGLIA_LOW_USAGE_COUNT
  MICROGLIA_HIGH_REGRET
  MICROGLIA_CONTRADICTION_PE
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


def prune_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / EVENT_LOG_NAME


def _legacy_class_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LEGACY_CLASS_LOG_NAME


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
    root: Optional[Path] = None,
    write_ledger: bool = True,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Evaluate one synapse/policy/memory candidate and append a receipt.

    Actions are recommendations unless SIFTA_MICROGLIA_EXECUTE=1. Even execute
    mode is receipt-only: it writes an executed correction/depression row, not a
    silent deletion of source ledgers.
    """
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

    stale_hours = _env_float("MICROGLIA_STALE_HOURS", 72.0)
    low_reward_mean = _env_float("MICROGLIA_LOW_REWARD_MEAN", -0.1)
    low_usage_count = _env_int("MICROGLIA_LOW_USAGE_COUNT", 1)
    high_regret = _env_float("MICROGLIA_HIGH_REGRET", 0.3)
    contradiction_pe = _env_float("MICROGLIA_CONTRADICTION_PE", 0.4)

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

    if safety_critical or ledger_type == "owner":
        action = "none"
        prune_recommended = False
    elif unsafe:
        action = "recommend_delete"
        prune_recommended = True
    elif reasons:
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
        "unsafe": bool(unsafe),
        "safety_critical": bool(safety_critical),
        "reasons": reasons,
        "action": action,
        "prune_recommended": prune_recommended,
        "dry_run": not execute,
        "executed": execute,
        "execute_mode": "receipt_only" if execute else "dry_run",
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


def summary_for_prompt(*, root: Optional[Path] = None) -> str:
    rows = tail_prune_rows(8, root=root)
    if not rows:
        return ""
    active = [r for r in rows if r.get("prune_recommended")]
    executed = [r for r in rows if r.get("executed")]
    return (
        "MICROGLIA PRUNER (Event 137): "
        f"recent={len(rows)}, recommended={len(active)}, executed_receipts={len(executed)}"
    )


class MicrogliaSynapticPruner:
    """
    Compatibility facade for the older class-level pruning API.

    It still writes the legacy `microglia_prune.jsonl` receipts expected by
    existing tests, while the new module-level API writes Event 137 receipts to
    `microglia_synaptic_prunes.jsonl`.
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = state_dir(root)
        self.log_path = _legacy_class_log_path(root)

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
        Q5 — SHY homeostatic pressure (Tononi & Cirelli 2014).

        P_homeo = (total reward-weighted trace norm / buffer_capacity) - θ_baseline

        Tononi & Cirelli (2014) SHY: the trigger criterion for homeostatic
        downscaling is **net synaptic potentiation** accumulated during wakefulness,
        not raw energy norm. We approximate this as the sum of |reward| × eligibility
        across recent replay traces, normalised by buffer capacity.

        P_homeo > 0.35 AND stability_ok → prune.

        Args:
            recent_traces: list of replay rows; each should have
                'recent_reward_mean' and optionally 'eligibility_trace_norm'.
            buffer_capacity: nominal replay buffer size (default 200).
        Returns:
            float in [0, 1]: homeostatic pressure.

        Ref: Tononi, G. & Cirelli, C. (2014). Sleep and the price of plasticity:
             from synaptic and cellular homeostasis to memory consolidation and
             integration. Neuron, 81(1), 12-34.
        """
        if not recent_traces:
            return 0.0
        theta_baseline = 0.2  # steady-state potentiation level
        total_potentiation = 0.0
        for r in recent_traces:
            reward = abs(float(r.get("recent_reward_mean", 0.0) or 0.0))
            elig   = float(r.get("eligibility_trace_norm", 1.0) or 1.0)
            total_potentiation += reward * elig
        raw = total_potentiation / max(1, buffer_capacity)
        pressure = max(0.0, raw - theta_baseline)
        return min(1.0, round(pressure, 4))

    def should_prune_homeostatic(
        self,
        recent_traces: List[Dict[str, Any]],
        stability_ok: bool,
        pressure_threshold: float = 0.35,
        buffer_capacity: int = 200,
    ) -> bool:
        """
        Q5 — SHY-based pruning gate.

        Prunes when P_homeo > threshold AND stability_ok.
        Suppressed in EMERGENCY regardless of pressure (matches Lyapunov gate).
        Ref: Tononi & Cirelli (2014) SHY.
        """
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

        for entry in ledger:
            is_safety = bool(
                entry.get("safety_critical", False)
                or ledger_type == "owner"
                or entry.get("invariant", False)
            )
            score, dominant = self.score_entry(entry)
            action = self.decide_action(score, is_safety)

            if action == "delete" and not stability_ok:
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
            }
            append_line_locked(self.log_path, json.dumps(receipt) + "\n", encoding="utf-8")
            receipts.append(receipt)

        return receipts


__all__ = [
    "MicrogliaSynapticPruner",
    "batch_evaluate",
    "evaluate_prune_candidate",
    "prune_log_path",
    "summary_for_prompt",
    "tail_prune_rows",
]
