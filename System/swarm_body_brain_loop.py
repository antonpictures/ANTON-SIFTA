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
    from System.swarm_reset_recovery_immunity import recovery_action, write_reset_recovery
    _RESET_RECOVERY_AVAILABLE = True
except Exception:
    _RESET_RECOVERY_AVAILABLE = False
    def write_reset_recovery(**kw): return {}  # type: ignore
    def recovery_action(row): return {}  # type: ignore

try:
    from System.swarm_hippocampal_novelty_map import write_novelty_map
    from System.swarm_novelty_metabolic_gate import compute_novelty_gate, NoveltyGateFrame
    _NOVELTY_MAP_AVAILABLE = True
except Exception:
    _NOVELTY_MAP_AVAILABLE = False
    def write_novelty_map(**kw): return {}  # type: ignore
    def compute_novelty_gate(*a, **kw): return None  # type: ignore

try:
    from System.swarm_orienting_reflex import write_orienting_reflex
    _ORIENTING_REFLEX_AVAILABLE = True
except Exception:
    _ORIENTING_REFLEX_AVAILABLE = False
    def write_orienting_reflex(**kw): return {}  # type: ignore

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


def _apply_novelty_metabolic_gate(
    homeostat: MetabolicHomeostat,
    danger: Dict[str, Any],
    novelty_frame: Any,
) -> Dict[str, Any]:
    """CA1-style match/mismatch → metabolic governor (FAMILIAR clamps, NOVEL relaxes).

    Does not mask true starvation: if the pre-gate state is already critical,
    the gate is skipped so RED/CRITICAL pressure cannot be hidden by novelty.
    """
    out = dict(danger)
    phase = str(getattr(novelty_frame, "phase", "") or "")
    if bool(out.get("is_critical")):
        out["novelty_metabolic_gate"] = "SKIPPED_CRITICAL"
        out["novelty_phase_echo"] = phase
        return out
    raw_p = float(out.get("pressure", 0.0) or 0.0)
    if phase == "FAMILIAR":
        factor = 1.1
    elif phase == "NOVEL":
        factor = 0.82
    else:
        factor = 1.0
    adj = max(0.0, min(1.0, raw_p * factor))
    out["pressure"] = adj
    out["mode"] = homeostat.mode(adj)
    out["is_critical"] = out["mode"] in ("RED_CONSERVE", "CRITICAL_STARVATION")
    out["novelty_phase"] = phase
    out["novelty_pressure_factor"] = factor
    out["novelty_metabolic_gate"] = "APPLIED"
    return out


def _apply_novelty_metabolic_gate(
    homeostat: MetabolicHomeostat,
    danger: Dict[str, Any],
    novelty_frame: Any,
) -> Dict[str, Any]:
    """CA1-style match/mismatch → metabolic governor (FAMILIAR clamps, NOVEL relaxes).
    Does not mask true starvation: if the pre-gate state is already critical,
    the gate is skipped so RED/CRITICAL pressure cannot be ``hidden'' by novelty.
    """
    out = dict(danger)
    if novelty_frame is None:
        return out
    phase = str(getattr(novelty_frame, "phase", "") or "")
    if bool(out.get("is_critical")):
        out["novelty_metabolic_gate"] = "SKIPPED_CRITICAL"
        out["novelty_phase_echo"] = phase
        return out

    if phase == "FAMILIAR":
        out["pressure"] = min(1.0, out.get("pressure", 0.0) + 0.15)
        out["mode"] = homeostat.mode(out["pressure"])
        out["novelty_metabolic_gate"] = "FAMILIAR_CLAMP"
    elif phase == "NOVEL":
        out["pressure"] = max(0.0, out.get("pressure", 0.0) - 0.15)
        out["mode"] = homeostat.mode(out["pressure"])
        out["novelty_metabolic_gate"] = "NOVEL_RELAX"
    else:
        out["novelty_metabolic_gate"] = "MIXED_OR_NONE"

    out["novelty_phase_echo"] = phase
    return out

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
        reset_recovery: Optional[Dict[str, Any]] = None,
        novelty_frame: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Basal Ganglia routing: what should we physically do?

        Event 101: homeostatic_frame can override the attention drive
        and cap action intensity before the motor gate fires.
        Event 102: allostatic_row.drive_modifiers compose with homeostatic
        drive_weight to produce a compound regulator signal.
        Event 103: crystallized skill mass biases explore vs forage (motor_policy.jsonl).
        Event 110: post-reset immunity can block unsafe autonomy until ledgers rehydrate.
        """
        if reset_recovery and str(reset_recovery.get("autonomy_gate") or "") == "BLOCK":
            return recovery_action(reset_recovery)

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

        if reset_recovery and str(reset_recovery.get("autonomy_gate") or "") == "LIMITED":
            action_intensity = min(action_intensity, 0.35)

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
                novelty_ex = 0.0
                novelty_fg = 0.0
                if novelty_frame is not None:
                    ph = str(getattr(novelty_frame, "phase", "") or "")
                    ns = float(getattr(novelty_frame, "novelty_score", 0.0) or 0.0)
                    if ph == "NOVEL":
                        novelty_ex = 0.55 * min(1.0, max(0.0, ns))
                    elif ph == "FAMILIAR":
                        novelty_fg = 0.4
                motor_type, motor_bias = select_action_type_from_skills(
                    ("explore", "forage"),
                    attention,
                    state_dir=state_root,
                    regime=_regime,
                    crystallizer_gate=_cgate,
                    novelty_explore_mass=novelty_ex,
                    novelty_forage_mass=novelty_fg,
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
        extra_fields: Optional[Dict[str, Any]] = None,
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
        if extra_fields:
            row.update(extra_fields)
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
                
                # Event 101 Horizontal Stigmergy: Broadcast and ingest boundary engrams
                try:
                    from System.swarm_horizontal_stigmergy import HorizontalStigmergyEngine
                    hs_engine = HorizontalStigmergyEngine(_STATE_DIR)
                    exp_count = hs_engine.export_stable_skills()
                    imp_count = hs_engine.import_foreign_engrams()
                    if exp_count > 0 or imp_count > 0:
                        logger.info(f"Horizontal Stigmergy: {exp_count} exported, {imp_count} imported")
                except Exception:
                    logger.exception("Horizontal Stigmergy failed")

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
        causal_probe_tick: Optional[int] = None
        causal_probe_reverts_applied = 0
        try:
            from System.swarm_active_causal_prober import (
                advance_runtime_tick as _advance_causal_probe_tick,
                apply_pending_reverts as _apply_causal_probe_reverts,
            )

            causal_probe_tick = _advance_causal_probe_tick(root=_STATE_DIR)
            causal_probe_reverts_applied = _apply_causal_probe_reverts(
                current_tick=causal_probe_tick,
                root=_STATE_DIR,
            )
            if causal_probe_reverts_applied:
                logger.info(
                    "[Event139] Applied %s pending causal probe reverts",
                    causal_probe_reverts_applied,
                )
        except Exception:
            logger.debug("Active causal prober revert sweep skipped (non-fatal)")

        # 0b. Event 110 — Reset Recovery Immunity (post-reset wound scan)
        reset_recovery: Optional[Dict[str, Any]] = None
        if _RESET_RECOVERY_AVAILABLE:
            try:
                reset_recovery = write_reset_recovery(state_dir=_STATE_DIR)
                if reset_recovery.get("autonomy_gate") != "ALLOW":
                    logger.info(
                        "[Event110] phase=%s gate=%s warmth=%.3f",
                        reset_recovery.get("phase"),
                        reset_recovery.get("autonomy_gate"),
                        float(reset_recovery.get("warmth", 0.0) or 0.0),
                    )
            except Exception:
                logger.exception("Reset recovery immunity skipped (non-fatal)")
        
        # 1. Interoception + Event 112/113 — CA1 comparator & orienting (intake valve)
        _intero_snapshot = read_interoception(_STATE_DIR)
        body_state = MetabolicHomeostat.sample_live(self.homeostat.cfg)

        # 2. Assess Danger
        danger = self._assess_danger(body_state)
        
        # 2b. Event 112 — Hippocampal Novelty Map & Metabolic Gate
        novelty_frame: Optional[Any] = None
        orienting_row: Optional[Dict[str, Any]] = None
        if _NOVELTY_MAP_AVAILABLE:
            try:
                novelty_row = write_novelty_map(state_dir=_STATE_DIR)
                novelty_frame = compute_novelty_gate(novelty_row)
                logger.info(
                    "[Event112] Novelty: %s (score=%.2f) td_bias=%.2f",
                    getattr(novelty_frame, "phase", "?"),
                    float(getattr(novelty_frame, "novelty_score", 0.0) or 0.0),
                    float(getattr(novelty_frame, "td_bias", 0.0) or 0.0),
                )
            except Exception:
                logger.exception("Hippocampal novelty map skipped")
        if _ORIENTING_REFLEX_AVAILABLE:
            try:
                orienting_row = write_orienting_reflex(state_dir=_STATE_DIR)
            except Exception:
                logger.exception("Orienting reflex skipped (non-fatal)")

        danger = _apply_novelty_metabolic_gate(self.homeostat, danger, novelty_frame)

        # 3. Drives / Wants
        recent_ev: Optional[Dict[str, Any]] = None
        if novelty_frame is not None:
            recent_ev = {
                "novelty": float(getattr(novelty_frame, "novelty_score", 0.0) or 0.0),
                "novelty_phase": str(getattr(novelty_frame, "phase", "") or ""),
            }
        consc_state = self.consciousness.tick(
            metabolic_state=body_state,
            now_state=now_state,
            commit=True,
            recent_events=recent_ev,
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

        # 4. Action Selection — George Prior + Homeostatic + Allostatic + CA1 motor bias
        action = self._choose_action(
            attention,
            danger,
            intrinsic_receipt=intrinsic_receipt,
            homeostatic_frame=homeostatic_frame,
            allostatic_row=allostatic_row,
            reset_recovery=reset_recovery,
            novelty_frame=novelty_frame,
        )

        # 5. Execution
        result = self._execute_action(action)

        # 6. Value Signal
        value = self._compute_value(result, danger)
        
        # Apply hippocampal novelty and orienting reflex value modulation.
        if novelty_frame:
            value += novelty_frame.td_bias
        if orienting_row:
            try:
                value += float(orienting_row.get("td_bias", 0.0) or 0.0)
            except Exception:
                pass

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
        memory_extra: Dict[str, Any] = {}
        if causal_probe_tick is not None:
            memory_extra.update({
                "causal_probe_tick": causal_probe_tick,
                "causal_probe_reverts_applied": causal_probe_reverts_applied,
            })
        if homeostatic_frame is not None:
            memory_extra.update({
                "homeostasis_regime":     homeostatic_frame.regime,
                "homeostasis_weight":     homeostatic_frame.drive_weight,
                "homeostasis_intensity":  homeostatic_frame.action_intensity,
                "homeostasis_type":       homeostatic_frame.intervention_type,
                "crystallizer_weight":    homeostatic_frame.crystallizer_weight,
            })
        if allostatic_row:
            memory_extra.update({
                "allostatic_load":    allostatic_row.get("allostatic_load", 0.0),
                "allostatic_policy":  allostatic_row.get("policy", "ALLOW_GROWTH"),
            })
        if reset_recovery:
            memory_extra.update({
                "reset_recovery_phase": reset_recovery.get("phase"),
                "reset_recovery_gate": reset_recovery.get("autonomy_gate"),
                "reset_recovery_warmth": reset_recovery.get("warmth"),
                "reset_recovery_score": reset_recovery.get("recovery_score"),
            })
        if novelty_frame:
            memory_extra.update({
                "novelty_phase": novelty_frame.phase,
                "novelty_score": novelty_frame.novelty_score,
                "novelty_td_bias": novelty_frame.td_bias,
            })
        if orienting_row:
            command = orienting_row.get("command") if isinstance(orienting_row.get("command"), dict) else {}
            memory_extra.update({
                "orient_trigger": orienting_row.get("orient_trigger"),
                "orienting_intensity": orienting_row.get("orienting_intensity"),
                "orienting_td_bias": orienting_row.get("td_bias"),
                "orienting_attention_gain": command.get("attention_gain"),
                "orienting_memory_encode_bias": command.get("memory_encode_bias"),
                "orienting_explore_bias": command.get("explore_bias"),
            })

        mem_row = self._write_memory(
            action,
            result,
            value,
            now_state,
            drive_state=str(attention),
            metabolic_mode=str(danger.get("mode") or ""),
            plasticity_danger=d_token,
            extra_fields=memory_extra,
        )
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

        # 8c. Stability Audit + Active Clamps (Event 134 — Khalil 2002; Liberzon 2003)
        # Runs before astrocyte so metabolic LR can honor the same-tick receipt.
        _clamp_receipt: Dict[str, Any] = {"clamp_level": "NONE", "stability_ok": True,
                                           "max_prunes_override": None, "active_clamps": [],
                                           "kind": "STABILITY_CLAMP", "truth_label": "STABILITY_CLAMP"}
        _stability_snapshot: Dict[str, Any] = {}
        _clamp_overrides: Dict[str, Any] = {
            "lr_ceiling": 1.0,
            "max_prunes_override": None,
            "block_new_gates": False,
            "clamp_level": "NONE",
            "stability_ok": True,
            "exploration_bias_cap": None,
        }
        try:
            from System.swarm_stability_audit import (
                compute_stability_snapshot,
                enforce_stability_clamps,
                get_current_clamp_overrides,
            )
            _stability_snapshot = compute_stability_snapshot(write_ledger=True)
            _clamp_receipt = enforce_stability_clamps(_stability_snapshot, write_ledger=True)
            _clamp_overrides = get_current_clamp_overrides(
                root=_STATE_DIR,
                same_tick_receipt=_clamp_receipt,
            )
            if _clamp_receipt["clamp_level"] != "NONE":
                logger.warning(
                    "[Event134] Stability clamp=%s energy=%.3f delta=%.3f clamps=%s",
                    _clamp_receipt["clamp_level"],
                    _clamp_receipt.get("lyapunov_energy", 0.0),
                    _clamp_receipt.get("delta_lyapunov_energy", 0.0),
                    _clamp_receipt.get("active_clamps", []),
                )
        except Exception:
            logger.debug("Stability audit skipped (non-fatal)")

        # 7b. LC/NA Arousal (Event 142) — gain, exploration bias, LR ceiling
        # Runs AFTER stability clamps, BEFORE astrocyte so NA modulates LR ceiling.
        # Bio-math proven: Sara 2009; Yu & Dayan 2005; Aston-Jones & Cohen 2005.
        _lc_na_receipt: Dict[str, Any] = {
            "na_level": 0.5, "gain": 1.0, "exploration_bias": 0.5,
            "lr_ceiling": 0.05, "arousal_regime": "OPTIMAL",
        }
        try:
            from System.swarm_locus_coeruleus_na import compute_lc_na
            _terms = _stability_snapshot.get("terms", {}) if isinstance(_stability_snapshot, dict) else {}
            _uncertainty_for_na = max(
                float(_terms.get("world_error_norm", 0.0) or 0.0),
                abs(1.0 - float(mem_row.get("td_value", 0.0) or 0.0)),
            )
            _heat_for_na = float(_terms.get("astrocyte_heat_norm", 0.0) or 0.3)
            try:
                from System.swarm_proto_self_interoception import read_proto_self_interoception
                _uptime_h = read_proto_self_interoception(write_ledger=False).get("uptime_hours", 4.0)
            except Exception:
                _uptime_h = 4.0
            _lc_na_receipt = compute_lc_na(
                uncertainty=min(1.0, max(0.0, _uncertainty_for_na)),
                astrocyte_heat_norm=min(1.0, max(0.0, _heat_for_na)),
                uptime_hours=float(_uptime_h),
                clamp_level=str(_clamp_receipt.get("clamp_level", "NONE")),  # TWO-PHASE
                root=_STATE_DIR,
                write_ledger=True,
            )
            logger.debug(
                "[Event142] LC/NA regime=%s na=%.3f gain=%.3f explore=%.3f lr_ceil=%.4f",
                _lc_na_receipt.get("arousal_regime"),
                float(_lc_na_receipt.get("na_level", 0.5)),
                float(_lc_na_receipt.get("gain", 1.0)),
                float(_lc_na_receipt.get("exploration_bias", 0.5)),
                float(_lc_na_receipt.get("lr_ceiling", 0.05)),
            )
        except Exception:
            logger.debug("LC/NA arousal skipped (non-fatal)")

        # 8. Astrocyte Glial Modulation (Event 135) — scale LR/ε/budget from surprise
        # NA lr_ceiling is now passed in from Event 142 (overrides clamp default)
        try:
            from System.swarm_astrocyte_glial_modulator import AstrocyteGlialModulator
            _astrocyte = AstrocyteGlialModulator()
            _surprise = float(mem_row.get("td_value", 0.0) or 0.0)
            _compute_spent = float(mem_row.get("result", {}).get("energy_used", 0.05) or 0.05) * 1000
            # LC/NA lr_ceiling overrides stability clamp ceiling (NA is more granular)
            _na_lr_ceiling = float(_lc_na_receipt.get("lr_ceiling", 0.05))
            _clamp_lr_ceiling = float(_clamp_overrides.get("lr_ceiling", 1.0) or 1.0)
            _effective_lr_ceiling = min(_na_lr_ceiling, _clamp_lr_ceiling)
            _astro_kw: Dict[str, Any] = {"lr_ceiling": _effective_lr_ceiling}
            # NA exploration_bias caps astrocyte's own exploration_bias_cap
            _na_explore = float(_lc_na_receipt.get("exploration_bias", 0.5))
            _clamp_explore = _clamp_overrides.get("exploration_bias_cap")
            _effective_explore = _na_explore if _clamp_explore is None else min(_na_explore, float(_clamp_explore))
            _astro_kw["exploration_bias_cap"] = _effective_explore
            _astrocyte.observe_global_state(
                abs(1.0 - _surprise),
                _compute_spent,
                **_astro_kw,
            )
        except Exception:
            logger.debug("Astrocyte modulation skipped (non-fatal)")

        # 8c. Metacognitive State Monitor (Event 145) — second-order uncertainty
        # Runs after LC/NA + astrocyte so PE series reflects current arousal state.
        # Bio-math proven: Fleming & Dolan 2012; Nelson 1990; Friston 2005; Yeung & Summerfield 2012.
        _metacog_receipt: Dict[str, Any] = {
            "metacog_regime": "CALIBRATED", "monitoring_score": 0.5,
            "confidence_bias": 0.0, "meta_uncertainty": 0.0,
        }
        try:
            from System.swarm_metacognitive_monitor import compute_metacognitive_state
            _metacog_receipt = compute_metacognitive_state(root=_STATE_DIR, write_ledger=True)
            logger.debug(
                "[Event145] Metacog regime=%s bias=%.3f monitoring=%.3f efficiency=%.3f",
                _metacog_receipt.get("metacog_regime"),
                float(_metacog_receipt.get("confidence_bias", 0.0)),
                float(_metacog_receipt.get("monitoring_score", 0.5)),
                float(_metacog_receipt.get("metacog_efficiency", 1.0)),
            )
        except Exception:
            logger.debug("Metacognitive monitor skipped (non-fatal)")

        # 8e. Theory of Mind / Owner Mental Model (Event 147) — owner-centric social brain
        # Premack & Woodruff 1978; Frith 1992; Saxe & Kanwisher 2003; Lieberman 2007.
        # Runs after metacog so it can incorporate overconfidence signals into risk gate.
        _tom_receipt: Dict[str, Any] = {
            "risk_adjustment": 1.0,
            "arousal_boost":   0.0,
            "pruning_conservatism": 0.0,
            "communication_policy": {"detail_level": 0.6, "explain_reasoning": False,
                                     "ask_for_clarification": False},
            "owner_state": {},
        }
        try:
            from System.swarm_theory_of_mind import compute_owner_mental_model
            _tom_receipt = compute_owner_mental_model(
                root=_STATE_DIR,
                tick_id=str(mem_row.get("tick_id") or ""),
                write_ledger=True,
            )
            # Wire arousal_boost back into LC/NA: if owner knowledge is low or
            # frustration rising, elevate effective arousal (Lieberman 2007 §4)
            _tom_arousal_boost = float(_tom_receipt.get("arousal_boost", 0.0))
            if _tom_arousal_boost > 0.0:
                _boosted_na = min(1.0, float(_lc_na_receipt.get("na_level", 0.5)) + _tom_arousal_boost)
                _lc_na_receipt["na_level_tom_boosted"] = round(_boosted_na, 4)
            logger.debug(
                "[Event147] ToM frustration=%.3f knowledge=%.3f risk_adj=%.3f arousal_boost=%.3f",
                float((_tom_receipt.get("owner_state") or {}).get("frustration", 0.0)),
                float((_tom_receipt.get("owner_state") or {}).get("knowledge_of_system", 0.6)),
                float(_tom_receipt.get("risk_adjustment", 1.0)),
                float(_tom_receipt.get("arousal_boost", 0.0)),
            )
        except Exception:
            logger.debug("Theory of Mind organ skipped (non-fatal)")

        # 8f. Affective Valence Tag (Event 144) — fast approach/avoid prior
        # Schultz/Dayan/Montague 1997; LeDoux 1996; Damasio 1994.
        _valence_receipt: Dict[str, Any] = {
            "valence": 0.0, "intensity": 0.0, "regime": "NEUTRAL",
        }
        try:
            from System.swarm_affective_valence import compute_affective_valence
            _terms = _stability_snapshot.get("terms", {}) if isinstance(_stability_snapshot, dict) else {}
            _reward = float(mem_row.get("td_value", 0.5) or 0.5)
            _surprise = max(
                float(_terms.get("world_error_norm", 0.0) or 0.0),
                abs(1.0 - _reward),
            )
            _threat = max(
                1.0 if danger.get("is_critical", False) else 0.0,
                0.65 if str(_clamp_receipt.get("clamp_level", "NONE")) == "EMERGENCY" else 0.0,
                0.40 if str(_clamp_receipt.get("clamp_level", "NONE")) == "BLOCK_NEW" else 0.0,
                0.20 if str(_clamp_receipt.get("clamp_level", "NONE")) == "RATE_LIMIT" else 0.0,
                float(_tom_receipt.get("risk_adjustment", 1.0) or 1.0) - 1.0,
            )
            _valence_receipt = compute_affective_valence(
                event=str(action.get("type") or action.get("name") or "body_brain_tick"),
                reward=min(1.0, max(0.0, _reward)),
                surprise=min(1.0, max(0.0, _surprise)),
                threat=min(1.0, max(0.0, _threat)),
                arousal=float(_lc_na_receipt.get("na_level", 0.5) or 0.5),
                root=_STATE_DIR,
                write_ledger=True,
            )
            logger.debug(
                "[Event144] Valence regime=%s valence=%.3f intensity=%.3f",
                _valence_receipt.get("regime"),
                float(_valence_receipt.get("valence", 0.0) or 0.0),
                float(_valence_receipt.get("intensity", 0.0) or 0.0),
            )
        except Exception:
            logger.debug("Affective valence skipped (non-fatal)")

        # 8d. Active Causal Probing (Event 139) — bounded do() experiments.
        # NA global_gain and meta_confidence now gate probing aggressiveness:
        #   - Uncertainty threshold RAISED when metacog says OVERCONFIDENT
        #     (Yeung & Summerfield 2012: don't trust self-assessment during overconfidence)
        #   - Uncertainty threshold LOWERED when metacog says UNDERCONFIDENT
        #     (more willingness to experiment when organism undersells its own accuracy)
        #   - Negative valence raises the threshold (probe less under aversion);
        #     positive valence slightly lowers it (safe approach bias)
        #   - Only run real interventions when NA gain >= 1.0 (OPTIMAL or above)
        _causal_probe_receipt: Optional[Dict[str, Any]] = None
        try:
            from System.swarm_active_causal_prober import propose_and_execute_runtime_intervention

            _terms = _stability_snapshot.get("terms", {}) if isinstance(_stability_snapshot, dict) else {}
            _uncertainty = max(
                float(_terms.get("world_error_norm", 0.0) or 0.0),
                float(_terms.get("astrocyte_heat_norm", 0.0) or 0.0),
                abs(1.0 - float(mem_row.get("td_value", 0.0) or 0.0)),
            )

            # Meta_confidence gate (Grok integration spec)
            # OVERCONFIDENT → raise uncertainty_threshold (harder to trigger probe)
            # UNDERCONFIDENT → lower threshold (easier to probe)
            _metacog_regime = _metacog_receipt.get("metacog_regime", "CALIBRATED")
            _base_probe_threshold = 0.35
            _probe_threshold = {
                "OVERCONFIDENT":  _base_probe_threshold + 0.10,   # +0.10 harder
                "CALIBRATED":     _base_probe_threshold,           # baseline
                "UNDERCONFIDENT": _base_probe_threshold - 0.05,   # -0.05 easier
            }.get(_metacog_regime, _base_probe_threshold)
            _valence = float(_valence_receipt.get("valence", 0.0) or 0.0)
            if _valence <= -0.20:
                _probe_threshold += min(0.08, abs(_valence) * 0.08)
            elif _valence >= 0.20:
                _probe_threshold -= min(0.04, _valence * 0.04)
            _probe_threshold = min(0.85, max(0.15, _probe_threshold))

            _causal_probe_receipt = propose_and_execute_runtime_intervention(
                tick_id=causal_probe_tick if causal_probe_tick is not None else str(mem_row.get("tick_id") or ""),
                current_uncertainty=min(1.0, max(0.0, _uncertainty)),
                current_clamp_level=str(_clamp_receipt.get("clamp_level", "NONE")),
                root=_STATE_DIR,
                uncertainty_threshold=_probe_threshold,
            )
            if _causal_probe_receipt:
                logger.info(
                    "[Event139] Active causal probe target=%s effect=%.3f dry_run=%s metacog_regime=%s valence=%.3f threshold=%.3f",
                    _causal_probe_receipt.get("intervention", {}).get("do", {}).get("target"),
                    float(_causal_probe_receipt.get("causal_effect_size", 0.0) or 0.0),
                    _causal_probe_receipt.get("intervention", {}).get("do", {}).get("dry_run"),
                    _metacog_regime,
                    _valence,
                    _probe_threshold,
                )
        except Exception:
            logger.debug("Active causal prober skipped (non-fatal)")

        # 8b. Microglia Synaptic Pruner (Event 137) — controlled forgetting gate
        # Only prunes if stability_ok (non-critical metabolic mode).
        try:
            from System.swarm_microglia_synaptic_pruner import MicrogliaSynapticPruner
            _stability_ok = (
                not danger.get("is_critical", False)
                and bool(_clamp_receipt.get("stability_ok", True))
            )
            if _stability_ok:
                _microglia = MicrogliaSynapticPruner()
                # Collect stale candidate rows from body_brain_memory
                _bbm_path = _STATE_DIR / "body_brain_memory.jsonl"
                if _bbm_path.exists():
                    import time as _time
                    _now = _time.time()
                    _candidates = []
                    _tail_take = 200
                    try:
                        _lines = _bbm_path.read_text(errors="ignore").strip().splitlines()
                        _nlines = len(_lines)
                        if _nlines > 180:
                            _tail_take = 120
                            logger.info(
                                "[Event137] microglia_tail_read degraded tail=%s (file_lines=%s)",
                                _tail_take,
                                _nlines,
                            )
                        for _l in _lines[-_tail_take:]:
                            try:
                                _r = json.loads(_l)
                                _age_h = (_now - float(_r.get("ts", _now))) / 3600.0
                                _r["age_hours"] = _age_h
                                _r["usage_count"] = 1  # body-brain rows are used once
                                _r["recent_reward_mean"] = float(_r.get("td_value", 0.0) or 0.0)
                                _candidates.append(_r)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    if _candidates:
                        _microglia.prune(
                            _candidates,
                            ledger_type="replay",
                            stability_ok=_stability_ok,
                            max_prunes_override=_clamp_overrides.get("max_prunes_override"),
                            tail_lines_read=_tail_take,
                        )
        except Exception:
            logger.debug("Microglia pruner skipped (non-fatal)")

        # 8d. Autopoiesis Viability Monitor (Event 140 — Q2)
        _viability_receipt: dict = {}
        try:
            from System.swarm_autopoiesis_monitor import compute_viability
            _viability_receipt = compute_viability(write_ledger=True)
            if _viability_receipt.get("viability_regime") == "CRITICAL":
                logger.warning(
                    "[Event140] CRITICAL viability V_t=%.3f — organism below conservation floor",
                    float(_viability_receipt.get("viability", 0.0) or 0.0),
                )
        except Exception:
            logger.debug("Autopoiesis monitor skipped (non-fatal)")

        # 8e. NPPL Hard Gate (Event 141) — verify the current action is permitted
        _nppl_receipt: dict = {"permitted": True, "tier": "SAFE"}
        try:
            from System.swarm_nppl_gate import check_tool as _nppl_check
            _action_type = str(action.get("type", "explore") or "explore")
            _nppl_receipt = _nppl_check(
                _action_type,
                clamp_level=str(_clamp_receipt.get("clamp_level", "NONE")),
                stability_ok=bool(_clamp_receipt.get("stability_ok", True)),
                context={"tick_id": str(mem_row.get("tick_id", "")), "organ": "body_brain_tick"},
                write_ledger=True,
            )
            if not _nppl_receipt["permitted"]:
                logger.warning(
                    "[Event141] NPPL blocked action=%s reason=%s",
                    _action_type,
                    _nppl_receipt.get("reason", "?")[:80],
                )
        except Exception:
            logger.debug("NPPL gate skipped (non-fatal)")

        # 9. Sleep / Recovery (pass crystallizer_weight from homeostatic frame)
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
            "reset_recovery":     reset_recovery,
            "novelty_gate":       novelty_frame.as_dict() if novelty_frame else None,
            "orienting_reflex":    orienting_row,
            "stability_clamp":     _clamp_receipt,
            "causal_probe":        _causal_probe_receipt,
            "viability":           _viability_receipt,
            "nppl_gate":           _nppl_receipt,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Initiating Swarm Physiology Loop...")
    physiology = SwarmPhysiology()
    cycle_result = physiology.body_brain_tick()
    print("Cycle complete:", json.dumps(cycle_result, indent=2))
