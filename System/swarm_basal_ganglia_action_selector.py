"""
Event 126a — Basal ganglia action selector (parallel loop competition).

Winner-take-all over **named** competing drives with explicit salience, cost, and
reward_potential. **Dopamine proxy** optionally read from `swarm_dopamine_critic_organ`
aggregate (not literal midbrain).

Truth label: **OBSERVED** — toy dynamics for routing; not a full BG model.
Kill-switch: ``SIFTA_BASAL_GANGLIA_DISABLE=1``.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from System.jsonl_file_lock import append_line_locked
from System.swarm_persistent_owner_history import state_dir

LOG_NAME = "basal_ganglia_selections.jsonl"


def selection_log_path(root: Optional[Path] = None) -> Path:
    return state_dir(root) / LOG_NAME


def dopamine_proxy(*, root: Optional[Path] = None) -> float:
    """Map critic aggregate to [0.35, 0.85] for modulation strength."""
    try:
        from System.swarm_dopamine_critic_organ import learning_summary

        s = learning_summary(root=root)
        avg = float(s.get("avg_outcome_score") or 0.0)
        m = max(-1.0, min(1.0, avg))
        return round(0.5 + 0.35 * m, 4)
    except Exception:
        return 0.55


def select_action(
    available_loops: List[Dict[str, Any]],
    dopamine_level: Optional[float] = None,
    *,
    root: Optional[Path] = None,
    write_ledger: bool = True,
) -> Tuple[str, float]:
    """
    Each loop: ``name``, ``salience``, ``cost``, ``reward_potential`` (floats).
    Net = salience + dopamine * reward_potential - cost; pick argmax.
    """
    if os.environ.get("SIFTA_BASAL_GANGLIA_DISABLE", "").strip() == "1":
        return "idle", 0.0

    if not available_loops:
        return "idle", 0.0

    da = dopamine_level if dopamine_level is not None else dopamine_proxy(root=root)
    da = max(0.0, min(1.0, float(da)))

    # --- High-Dimensional Stigmergic Coupling ---
    # The decision organ reads the internal biological field (skin and electric state)
    # to modulate its evaluation of competing loops.
    alarm_active = False
    electric_autonomic_tone = 0.5
    try:
        from System.swarm_persistent_owner_history import state_dir
        _st = state_dir(root)
        cuttle_lines = (_st / "cuttlefish_display.jsonl").read_text(encoding="utf-8").strip().splitlines()
        if cuttle_lines:
            c_row = json.loads(cuttle_lines[-1])
            if c_row.get("payload", c_row).get("pattern") == "alarm":
                alarm_active = True
                
        elec_lines = (_st / "electric_field.jsonl").read_text(encoding="utf-8").strip().splitlines()
        if elec_lines:
            e_row = json.loads(elec_lines[-1])
            dipoles = e_row.get("payload", e_row).get("dipole_moments")
            if dipoles and len(dipoles) >= 3:
                # Z-axis is autonomic tone
                electric_autonomic_tone = dipoles[2]
    except Exception:
        pass

    stability_signal: Dict[str, Any] = {}
    stability_bias: Dict[str, Any] = {
        "applied": False,
        "reason": "stability_bridge_unavailable",
        "suppressed_candidates": [],
        "boosted_candidates": [],
    }
    somatic_signal: Dict[str, Any] = {
        "ok": False,
        "reason": "owner_somatic_unavailable",
    }
    try:
        from System.swarm_stability_to_homeostasis_bridge import (
            bias_basal_ganglia_loops,
            read_latest_clamp_signal,
        )
        from System.swarm_owner_somatic_state import latest_somatic_signal

        stability_signal = read_latest_clamp_signal(root=root)
        available_loops, stability_bias = bias_basal_ganglia_loops(
            available_loops,
            stability_signal,
        )
        somatic_signal = latest_somatic_signal(state_dir=root, max_age_s=420)
    except Exception:
        stability_signal = {}
        somatic_signal = {}

    best_name = "idle"
    best_score = float("-inf")
    scored: List[Tuple[str, float, Dict[str, Any]]] = []

    for loop in available_loops:
        name = str(loop.get("name") or "unnamed").strip() or "unnamed"
        name_l = name.lower()
        try:
            sal = float(loop.get("salience", 0.5))
            cost = float(loop.get("cost", 0.3))
            rp = float(loop.get("reward_potential", 0.5))
        except (TypeError, ValueError):
            sal, cost, rp = 0.5, 0.3, 0.5
            
        # Modulate action evaluations based on internal biology
        if alarm_active:
            if "protect" in name or "repair" in name or "defense" in name:
                sal += 0.3  # Panic raises salience of defense
            elif "explore" in name or "curiosity" in name:
                cost += 0.4 # Panic increases cost of exploration
                
        # High autonomic tone from electric field lowers action cost globally
        if electric_autonomic_tone > 0.6:
            cost = max(0.0, cost - 0.15)

        if somatic_signal.get("is_fatigued"):
            if any(key in name_l for key in ("repair", "sustain", "guard", "defend", "throttle", "recover")):
                sal += 0.25
            elif any(key in name_l for key in ("explore", "research", "curious", "observe", "scan", "coach")):
                cost += 0.2

        if somatic_signal.get("is_high_energy") and "grok" in name_l:
            cost = max(0.0, cost - 0.25)
            
        net = sal + da * rp - cost
        scored.append((name, net, loop))
        if net > best_score:
            best_score = net
            best_name = name

    row: Dict[str, Any] = {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "BASAL_GANGLIA_SELECTION",
        "selected_action": best_name,
        "winner_score": round(float(best_score), 4),
        "dopamine_proxy": round(da, 4),
        "competing_loops": len(available_loops),
        "biological_modifiers": {
            "cuttlefish_alarm": alarm_active,
            "electric_tone": round(electric_autonomic_tone, 4),
            "stability_homeostasis": {
                "clamp_level": stability_signal.get("clamp_level", "NONE"),
                "energy": stability_signal.get("energy", 0.0),
                "suppress_new_arms": bool(stability_signal.get("suppress_new_arms", False)),
                "conserve_repair": bool(stability_signal.get("conserve_repair", False)),
                "reason": stability_signal.get("reason", "no_stability_signal"),
                "bias": stability_bias,
            },
            "owner_somatic": {
                "source": somatic_signal.get("source"),
                "energy_level": somatic_signal.get("energy_level", "medium"),
                "energy_score": somatic_signal.get("energy_score"),
                "posture": somatic_signal.get("posture"),
                "movement_quality": somatic_signal.get("movement_quality"),
                "is_fatigued": bool(somatic_signal.get("is_fatigued")),
                "is_high_energy": bool(somatic_signal.get("is_high_energy")),
                "age_s": somatic_signal.get("age_s"),
            },
        },
        "candidates": [
            {"name": n, "net_score": round(s, 4)} for n, s, _ in scored
        ],
    }
    if write_ledger:
        append_line_locked(
            selection_log_path(root),
            json.dumps(row, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return best_name, float(best_score)


__all__ = [
    "dopamine_proxy",
    "select_action",
    "selection_log_path",
]
