#!/usr/bin/env python3
"""
System/swarm_body_brain_loop.py
══════════════════════════════════════════════════════════════════════
The Executable Physiology of the Swarm.

This module converts the static body-brain architecture diagram into a living,
executable tick. It connects the organism's interoception to its drives, routes
those drives through action selection, executes them, measures the thermodynamic
value of the result, writes stigmergic memory, and handles sleep/consolidation.

Author: AG31 / Bishop Vanguard
"""

import time
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from System.swarm_metabolic_homeostasis import MetabolicHomeostat, MetabolicState
from System.swarm_consciousness_engine import ConsciousnessEngine, ConsciousnessEngineConfig, read_interoception
from System.swarm_dream_engine import SwarmDreamEngine
from System.jsonl_file_lock import append_line_locked
from System.swarm_now_state import build_now_state
from System.swarm_biology_drive_plasticity import (
    plasticity_danger_token,
    update_drive_plasticity,
)
try:
    from System.swarm_intrinsic_drive import start_george_prior, get_current_drive
    _GEORGE_PRIOR_AVAILABLE = True
except Exception:
    _GEORGE_PRIOR_AVAILABLE = False
    def start_george_prior(*a, **kw): return None  # type: ignore
    def get_current_drive(): return None  # type: ignore

try:
    from System.swarm_homeostatic_stabilizer import compute_homeostasis, HomeostaticFrame
    _HOMEOSTASIS_AVAILABLE = True
except Exception:
    _HOMEOSTASIS_AVAILABLE = False
    def compute_homeostasis(drive, **kw): return None  # type: ignore

try:
    from System.swarm_allostatic_load import write_allostatic_load
    _ALLOSTATIC_AVAILABLE = True
except Exception:
    _ALLOSTATIC_AVAILABLE = False
    def write_allostatic_load(**kw): return {}  # type: ignore

try:
    from System.swarm_stigmergic_observability import stamp_tick_row
    _OBSERVABILITY_AVAILABLE = True
except Exception:
    _OBSERVABILITY_AVAILABLE = False
    def stamp_tick_row(row, **kw): return ""  # type: ignore

try:
    from System.swarm_motor_policy import (
        select_action_type_from_skills,
        write_motor_policy_row,
    )
    _MOTOR_POLICY_AVAILABLE = True
except Exception:
    _MOTOR_POLICY_AVAILABLE = False

logger = logging.getLogger("BodyBrainLoop")
_STATE_DIR = Path(".sifta_state")
DRIVE_BIAS_SCORE_FLOOR = 0.05


def _receipt_value(receipt: Any, key: str, default: Any = None) -> Any:
    """Read a field from a DriveReceipt dataclass or a synthetic test dict."""
    if receipt is None:
        return default
    if isinstance(receipt, dict):
        return receipt.get(key, default)
    return getattr(receipt, key, default)


def _receipt_as_dict(receipt: Optional[Any]) -> Optional[Dict[str, Any]]:
    """Serialize a real or synthetic intrinsic-drive receipt."""
    if receipt is None:
        return None
    if isinstance(receipt, dict):
        return dict(receipt)
    if hasattr(receipt, "as_dict"):
        return receipt.as_dict()
    return {
        "topic": _receipt_value(receipt, "topic", ""),
        "goal": _receipt_value(receipt, "goal", ""),
        "score": _receipt_value(receipt, "score", 0.0),
        "source": _receipt_value(receipt, "source", ""),
    }


def _drive_bias_fields(intrinsic_receipt: Optional[Any]) -> Dict[str, Any]:
    """Return ledger-safe Event 100 drive-bias fields."""
    try:
        score = float(_receipt_value(intrinsic_receipt, "score", 0.0) or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    topic = str(_receipt_value(intrinsic_receipt, "topic", "") or "")
    goal = str(_receipt_value(intrinsic_receipt, "goal", "") or "")
    source = str(_receipt_value(intrinsic_receipt, "source", "") or "")
    applied = bool(intrinsic_receipt is not None and score > DRIVE_BIAS_SCORE_FLOOR and topic and goal)
    return {
        "drive_bias_applied": applied,
        "drive_bias_topic": topic if applied else "",
        "drive_bias_goal": goal if applied else "",
        "drive_bias_score": round(score, 6) if applied else 0.0,
        "drive_bias_source": source if applied else "",
        "truth_label": "SIMULATED_INTRINSIC_DRIVE" if applied else "NO_INTRINSIC_DRIVE_BIAS",
    }


def _no_drive_bias_fields() -> Dict[str, Any]:
    """Explicit Event 100 false-bias ledger fields."""
    return _drive_bias_fields(None)


class SwarmPhysiology:
    def __init__(self, dream_engine: Optional[Any] = None, enable_george_prior: bool = True):
        self.homeostat = MetabolicHomeostat()
        self.consciousness = ConsciousnessEngine(cfg=ConsciousnessEngineConfig(spend_on_drive=True))
        self.dream_engine = dream_engine or SwarmDreamEngine(_STATE_DIR)
        self.value_history = []
        # ── George Prior heartbeat — starts once, runs forever as daemon ──
        self._george_prior_daemon = None
        if enable_george_prior and _GEORGE_PRIOR_AVAILABLE:
            try:
                self._george_prior_daemon = start_george_prior()
                logger.info("George Prior daemon started — Alice has a heartbeat. 🐜⚡")
            except Exception:
                logger.exception("George Prior daemon failed to start (non-fatal)")

    def _assess_danger(self, body_state: MetabolicState) -> Dict[str, Any]:
        """Convert raw metabolic state into a danger/pressure signal."""
        pressure = self.homeostat.pressure(body_state)
        mode = self.homeostat.mode(pressure)
        return {
            "pressure": pressure,
            "mode": mode,
            "is_critical": mode in ("RED_CONSERVE", "CRITICAL_STARVATION")
        }

    def _select_attention(self, consciousness_state) -> str:
        """Filter drives to focus the organism's attention."""
        if consciousness_state.emitted_drive:
            return consciousness_state.emitted_drive.domain
        return consciousness_state.dominant_drive

    def _choose_action(
        self,
        attention: str,
        danger: Dict[str, Any],
        intrinsic_receipt: Optional[Any] = None,
        homeostatic_frame: Optional[Any] = None,
        allostatic_row: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Basal Ganglia routing: what should we physically do?

        Event 101: homeostatic_frame can override the attention drive
        and cap action intensity before the motor gate fires.
        Event 102: allostatic_row.drive_modifiers compose with homeostatic
        drive_weight to produce a compound regulator signal.
        Event 103: crystallized skill mass biases explore vs forage (motor_policy.jsonl).
        """
        # Event 101 — homeostatic regulation gate
        if homeostatic_frame is not None:
            attention = str(getattr(homeostatic_frame, "regulated_drive", attention) or attention)
            action_intensity = float(getattr(homeostatic_frame, "action_intensity", 1.0))
            if getattr(homeostatic_frame, "intervention_type", "NONE") == "REST_FORCED":
                return {
                    "type": "rest",
                    "reason": "homeostatic_stabilizer_event_101",
                    "action_intensity": action_intensity,
                    **_no_drive_bias_fields(),
                }
        else:
            action_intensity = 1.0

        # Event 102 — allostatic load compose with homeostatic weight
        if allostatic_row:
            al_modifiers = allostatic_row.get("drive_modifiers", {})
            al_modifier = float(al_modifiers.get(attention, 1.0))
            al_policy = allostatic_row.get("policy", "ALLOW_GROWTH")
            # Compound: homeostatic already redirected attention; now dampen
            # action_intensity further if chronic stress is high
            if al_policy == "FORCE_REST_REPAIR" and attention not in ("rest", "repair", "safety"):
                # Allostatic override: reroute to rest
                return {
                    "type": "rest",
                    "reason": "allostatic_load_event_102",
                    "action_intensity": min(action_intensity, 0.15),
                    "allostatic_load": allostatic_row.get("allostatic_load", 0.0),
                    **_no_drive_bias_fields(),
                }
            # Otherwise compose intensity: multiply by allostatic modifier (clamped)
            al_intensity_factor = max(0.1, min(2.0, al_modifier))
            action_intensity = min(1.0, action_intensity * al_intensity_factor)
        else:
            al_policy = "ALLOW_GROWTH"

        drive_bias = _drive_bias_fields(intrinsic_receipt)
        if danger["is_critical"]:
            return {"type": "rest", "reason": "starvation_or_heat",
                    "action_intensity": min(action_intensity, 0.1),
                    **_no_drive_bias_fields()}

        if attention == "energy":
            return {"type": "forage", "target": "pouw_work",
                    "action_intensity": action_intensity, **_no_drive_bias_fields()}

        # Red Queen stagnation break (unchanged — drives do not override)
        if len(self.value_history) >= 5 and len(set(self.value_history[-5:])) == 1:
            logger.info("Stagnation detected. Injecting exploration variation.")
            return {
                "type": "explore",
                "target": "random_mutation",
                "is_stagnation_break": True,
                "action_intensity": action_intensity,
                **_no_drive_bias_fields(),
            }

        if drive_bias["drive_bias_applied"]:
            return {
                "type": "explore",
                "target": attention,
                "drive_bias_target": f"{drive_bias['drive_bias_topic']}::{drive_bias['drive_bias_goal']}",
                "action_intensity": action_intensity,
                **drive_bias,
            }

        # Event 103 — skill-weighted motor policy (crystallizer → basal ganglia coupling)
        # Now regime-aware: homeostatic_frame regime + crystallizer_gate modulate
        # which skill types get mass (stabilizer → phase controller → policy mass loop).
        if _MOTOR_POLICY_AVAILABLE:
            try:
                state_root = Path(__file__).resolve().parent.parent / ".sifta_state"
                # Extract regime + gate from homeostatic frame (Event 101 → 103 feedback)
                _regime = (
                    getattr(homeostatic_frame, "regime", None)
                    if homeostatic_frame is not None else None
                )
                _cgate = (
                    float(getattr(homeostatic_frame, "crystallizer_weight", 1.0))
                    if homeostatic_frame is not None else 1.0
                )
                motor_type, motor_bias = select_action_type_from_skills(
                    ("explore", "forage"),
                    attention,
                    state_dir=state_root,
                    regime=_regime,
                    crystallizer_gate=_cgate,
                )
                write_motor_policy_row(
                    selected_action=motor_type,
                    bias=motor_bias,
                    current_drive=attention,
                    state_dir=state_root,
                    regime=_regime,
                    crystallizer_gate=_cgate,
                )
                if motor_type == "forage":
                    return {
                        "type": "forage",
                        "target": str(attention),
                        "action_intensity": action_intensity,
                        "truth_label": "SKILL_WEIGHTED_POLICY",
                        **_no_drive_bias_fields(),
                    }
            except Exception:
                logger.exception("Motor policy skipped (non-fatal)")

        return {"type": "explore", "target": attention,
                "action_intensity": action_intensity, **drive_bias}

    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Motor cortex/effectors. Simulated for the loop skeleton."""
        # In a full run, this bridges to the Agent/Swimmer execution.
        time.sleep(0.1) # Simulate physical time cost
        return {
            "status": "completed",
            "action": action,
            "latency": 0.1,
            "energy_used": 0.05
        }

    def _compute_value(self, result: Dict[str, Any], danger: Dict[str, Any]) -> float:
        """TD-Learning value assignment: was this good for the organism?"""
        val = -1.0
        if result.get("status") == "completed":
            # Survival value is higher when executed under danger
            val = 1.0 if not danger["is_critical"] else 2.5
        
        self.value_history.append(val)
        if len(self.value_history) > 20:
            self.value_history.pop(0)
            
        return val

    def _write_memory(
        self,
        action: Dict[str, Any],
        result: Dict[str, Any],
        value: float,
        now_state: Dict[str, Any],
        *,
        drive_state: str,
        metabolic_mode: str,
        intrinsic_receipt: Optional[Any] = None,
        plasticity_danger: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Append to stigmergic ledger; return row for downstream phenotype bridge."""
        circadian = now_state.get("circadian") if isinstance(now_state.get("circadian"), dict) else {}
        drive_bias = _drive_bias_fields(intrinsic_receipt)
        action_bias = {
            # Event 100 — George Prior bias fields (always present for query consistency)
            "drive_bias_applied": action.get("drive_bias_applied", False),
            "drive_bias_topic":   action.get("drive_bias_topic") or None,
            "drive_bias_goal":    action.get("drive_bias_goal"),
            "drive_bias_score":   action.get("drive_bias_score") or None,
            "drive_bias_source":  action.get("drive_bias_source"),
            "truth_label":        action.get("truth_label"),
        }
        drive_bias.update(action_bias)
        row: Dict[str, Any] = {
            "event": "body_brain_tick",
            "tick_id": str(uuid.uuid4()),
            "action": action,
            "result": result,
            "td_value": value,
            "now_state": now_state,
            "circadian_phase": circadian.get("phase"),
            "drive_state": drive_state,
            "metabolic_mode": metabolic_mode,
            "ts": time.time(),
            **drive_bias,
        }
        if plasticity_danger:
            row["plasticity_danger"] = plasticity_danger
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        append_line_locked(_STATE_DIR / "body_brain_memory.jsonl", json.dumps(row) + "\n")
        return row

    def _maybe_sleep(
        self,
        body_state: MetabolicState,
        danger: Dict[str, Any],
        crystallizer_weight: float = 1.0,
    ) -> Optional[Dict[str, Any]]:
        """Glymphatic consolidation and rest enforcement.

        Event 101: crystallizer_weight gates how aggressively new skills are
        crystallized. During CRITICAL_COLLAPSE the homeostatic stabilizer sets
        this to ~0.1, preventing panic-state patterns from being baked in.
        """
        rest_sec = self.homeostat.rest_seconds(body_state, danger["pressure"])
        if rest_sec > 0:
            dream_cycle: Optional[Dict[str, Any]] = None
            try:
                receipt = self.dream_engine.trigger_rem_sleep(
                    rest_seconds=rest_sec,
                    pressure=danger.get("pressure"),
                    metabolic_mode=str(danger.get("mode") or ""),
                    crystallizer_weight=crystallizer_weight,
                )
                dream_cycle = receipt.as_dict() if hasattr(receipt, "as_dict") else dict(receipt)
                logger.info(
                    "Dream consolidation cycle %s: %s (crystallizer_w=%.2f)",
                    dream_cycle.get("cycle_id"),
                    dream_cycle.get("status"),
                    crystallizer_weight,
                )
            except Exception:
                logger.exception("Dream consolidation failed; preserving raw body-brain ledger.")
            logger.info(f"Sleep enforced by metabolism. Resting {rest_sec}s.")
            time.sleep(min(rest_sec, 2.0))  # Capped for testing
            return dream_cycle
        return None

    def body_brain_tick(self) -> Dict[str, Any]:
        """The master unified cycle."""
        
        # 0. Spacetime / Circadian Context
        now_state = build_now_state()
        
        # 1. Interoception
        raw_body = read_interoception(_STATE_DIR)
        body_state = MetabolicHomeostat.sample_live(self.homeostat.cfg)
        
        # 2. Assess Danger
        danger = self._assess_danger(body_state)
        
        # 3. Drives / Wants
        # Tick the DMN to update arousal/boredom and emit drives if conditions allow
        consc_state = self.consciousness.tick(
            metabolic_state=body_state,
            now_state=now_state,
            commit=True
        )

        # 3b. Attention selection from consciousness state
        attention = self._select_attention(consc_state)

        # 3c_pre. George Prior — read the latest spontaneous drive receipt (non-blocking)
        intrinsic_receipt: Optional[Any] = None
        if _GEORGE_PRIOR_AVAILABLE:
            try:
                intrinsic_receipt = get_current_drive()
                if intrinsic_receipt:
                    logger.debug(
                        "George Prior active: [%s] %s",
                        _receipt_value(intrinsic_receipt, "topic", ""),
                        str(_receipt_value(intrinsic_receipt, "goal", ""))[:60],
                    )
            except Exception:
                pass

        # 3c. Event 101 — Homeostatic Stabilizer (hypothalamus regulation gate)
        homeostatic_frame: Optional[Any] = None
        if _HOMEOSTASIS_AVAILABLE:
            try:
                homeostatic_frame = compute_homeostasis(
                    input_drive=attention,
                    metabolic_mode=str(danger.get("mode") or "UNKNOWN"),
                    intrinsic_receipt=intrinsic_receipt,
                )
                if homeostatic_frame and homeostatic_frame.intervention_type != "NONE":
                    logger.info(
                        "[Event101] %s: %s",
                        homeostatic_frame.intervention_type,
                        homeostatic_frame.reason[:80],
                    )
                    # Reroute attention to the regulated drive
                    attention = homeostatic_frame.regulated_drive
            except Exception:
                logger.exception("Homeostatic stabilizer skipped (non-fatal)")

        # 3d. Event 102 — Allostatic Load (chronic stress accumulator)
        allostatic_row: Optional[Dict[str, Any]] = None
        if _ALLOSTATIC_AVAILABLE:
            try:
                allostatic_row = write_allostatic_load()
                al_load = allostatic_row.get("allostatic_load", 0.0)
                al_policy = allostatic_row.get("policy", "ALLOW_GROWTH")
                if al_policy != "ALLOW_GROWTH":
                    logger.info(
                        "[Event102] load=%.3f policy=%s",
                        al_load,
                        al_policy,
                    )
            except Exception:
                logger.exception("Allostatic load write skipped (non-fatal)")

        # 4. Action Selection — George Prior + Homeostatic + Allostatic
        action = self._choose_action(
            attention,
            danger,
            intrinsic_receipt=intrinsic_receipt,
            homeostatic_frame=homeostatic_frame,
            allostatic_row=allostatic_row,
        )
        
        # 5. Execution
        result = self._execute_action(action)
        
        # 6. Value Signal
        value = self._compute_value(result, danger)
        d_token = plasticity_danger_token(str(danger.get("mode") or ""), now_state)

        # 6b. Drive plasticity (slow Hebbian / homeostatic weights on disk)
        drive_plasticity: Optional[Dict[str, Any]] = None
        try:
            drive_plasticity = update_drive_plasticity(
                active_drive=attention,
                value=value,
                danger_state=d_token,
            )
        except Exception:
            logger.exception("Drive plasticity update skipped")

        # 7. Memory Consolidation
        mem_row = self._write_memory(
            action,
            result,
            value,
            now_state,
            drive_state=str(attention),
            metabolic_mode=str(danger.get("mode") or ""),
            plasticity_danger=d_token,
        )
        # Stamp Event 101 homeostatic frame fields into the ledger row
        if homeostatic_frame is not None:
            mem_row["homeostasis_regime"]     = homeostatic_frame.regime
            mem_row["homeostasis_weight"]     = homeostatic_frame.drive_weight
            mem_row["homeostasis_intensity"]  = homeostatic_frame.action_intensity
            mem_row["homeostasis_type"]       = homeostatic_frame.intervention_type
            mem_row["crystallizer_weight"]    = homeostatic_frame.crystallizer_weight
        # Stamp Event 102 allostatic load fields into the ledger row
        if allostatic_row:
            mem_row["allostatic_load"]    = allostatic_row.get("allostatic_load", 0.0)
            mem_row["allostatic_policy"]  = allostatic_row.get("policy", "ALLOW_GROWTH")
        try:
            from System.swarm_pheromone_field import update_pheromone_field

            pheromone_receipt = update_pheromone_field(mem_row)  # Event 94: spatial path memory deposit
            mem_row["trace_gradient"] = pheromone_receipt.get("chemotaxis_gradient", 0.0)
        except Exception:
            logger.exception("Pheromone field update skipped")
        try:
            from System.swarm_visual_phenotype_bridge import write_visual_phenotype_uniforms

            write_visual_phenotype_uniforms(mem_row)
        except Exception:
            logger.exception("Visual phenotype bridge skipped")

        # 7b. Event 104 — Stigmergic Observability stamp (The Auditor Organ)
        obs_id: str = ""
        if _OBSERVABILITY_AVAILABLE:
            try:
                obs_id = stamp_tick_row(
                    mem_row,
                    source="AG31",
                    causal_parent_ids=[],  # first in chain; downstream rows will cite this
                )
                mem_row["obs_id"] = obs_id
            except Exception:
                logger.exception("Observability stamp skipped (non-fatal)")

        # 8. Sleep / Recovery (pass crystallizer_weight from homeostatic frame)
        crystallizer_weight = (
            homeostatic_frame.crystallizer_weight
            if homeostatic_frame is not None else 1.0
        )
        dream_cycle = self._maybe_sleep(body_state, danger,
                                        crystallizer_weight=crystallizer_weight)
        
        return {
            "action":             action,
            "value":              value,
            "metabolic_mode":     danger["mode"],
            "drive_state":        attention,
            "dream_cycle":        dream_cycle,
            "now_state":          now_state,
            "drive_plasticity":   drive_plasticity,
            "intrinsic_drive":    _receipt_as_dict(intrinsic_receipt),
            "homeostatic_frame":  homeostatic_frame.as_dict() if homeostatic_frame else None,
            "allostatic_load":    allostatic_row.get("allostatic_load", 0.0) if allostatic_row else 0.0,
            "allostatic_policy":  allostatic_row.get("policy", "ALLOW_GROWTH") if allostatic_row else "ALLOW_GROWTH",
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Initiating Swarm Physiology Loop...")
    physiology = SwarmPhysiology()
    cycle_result = physiology.body_brain_tick()
    print("Cycle complete:", json.dumps(cycle_result, indent=2))
