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


def _clip01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


def _core_self_salience(
    *,
    action_confidence: Any = 0.0,
    causal_effect_size: Any = 0.0,
    uncertainty: Any = 0.0,
    valence: Any = 0.0,
    na_level: Any = 0.5,
    clamp_level: str = "NONE",
) -> float:
    """
    Damasio Phase 2 salience proxy for Core Self interaction receipts.

    High salience means an event plausibly changed the organism's body-state
    map enough to matter for later revival/autobiographical continuity.
    """
    confidence_term = _clip01(action_confidence)
    effect_term = _clip01(abs(float(causal_effect_size or 0.0)) * 3.0)
    uncertainty_term = _clip01(uncertainty)
    valence_term = _clip01(abs(float(valence or 0.0)))
    arousal_term = _clip01(max(0.0, float(na_level or 0.5) - 0.5) * 2.0)
    clamp_term = 0.75 if str(clamp_level) in ("BLOCK_NEW", "EMERGENCY") else 0.0
    return round(max(
        confidence_term,
        effect_term,
        uncertainty_term,
        valence_term,
        arousal_term,
        clamp_term,
    ), 4)


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

        # 0c. Organizational Identity Rehydration (Priority #1)
        # Runs once per body tick so long gaps / genome drift can temporarily
        # tighten probing and pruning until the organism recalibrates.
        _identity_receipt: Dict[str, Any] = {
            "revival_score": 1.0,
            "conservative_mode": False,
            "recommended_genome_blend": 1.0,
        }
        _core_self_before_event: Optional[Dict[str, float]] = None
        _core_self_event_type: Optional[str] = None
        _core_self_event_summary = ""
        _core_self_event_salience = 0.0
        try:
            from System.swarm_organizational_identity import rehydrate_identity
            _identity_receipt = rehydrate_identity(
                root=_STATE_DIR,
                current_tick=causal_probe_tick if causal_probe_tick is not None else int(time.time()),
            )
            if _identity_receipt.get("conservative_mode"):
                logger.warning(
                    "[Identity] conservative_mode revival=%.3f blend=%.3f",
                    float(_identity_receipt.get("revival_score", 0.0) or 0.0),
                    float(_identity_receipt.get("recommended_genome_blend", 1.0) or 1.0),
                )
        except Exception:
            logger.debug("Organizational identity rehydration skipped (non-fatal)")

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

        # 5b. Efference Copy / Agency (Event 143) — predicted vs observed effect
        # Corollary discharge for tool/body actions: self-generated vs external PE.
        efference_receipt: Dict[str, Any] = {
            "agency_confidence": 0.5,
            "sensorimotor_pe": 0.0,
            "self_generated": False,
        }
        try:
            from System.swarm_efference_copy import compare_action_effect
            efference_receipt = compare_action_effect(
                action,
                result,
                root=_STATE_DIR,
                tick_id=None,
                write_ledger=True,
            )
            logger.debug(
                "[Event143] Efference action=%s agency=%.3f pe=%.3f self=%s",
                efference_receipt.get("action"),
                float(efference_receipt.get("agency_confidence", 0.5) or 0.5),
                float(efference_receipt.get("sensorimotor_pe", 0.0) or 0.0),
                efference_receipt.get("self_generated"),
            )
        except Exception:
            logger.debug("Efference copy skipped (non-fatal)")

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
        if efference_receipt:
            memory_extra.update({
                "efference_agency_confidence": efference_receipt.get("agency_confidence"),
                "efference_sensorimotor_pe": efference_receipt.get("sensorimotor_pe"),
                "efference_self_generated": efference_receipt.get("self_generated"),
                "efference_trace_id": efference_receipt.get("trace_id"),
            })
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
            _metacog_receipt = compute_metacognitive_state(
                root=_STATE_DIR,
                write_ledger=True,
                tick_id=causal_probe_tick,
            )
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

        # 8f.1 Efference Copy / Sensorimotor Agency (Event 143)
        # Sperry 1950; von Holst & Mittelstaedt 1950; Wolpert+1995; Blakemore+1998; Frith+2000.
        # Forward model compares predicted tick features to observed → PE + agency_confidence.
        # PE wires into: (a) Causal Prober uncertainty, (b) LC/NA arousal boost.
        _efference_receipt: Dict[str, Any] = {
            "prediction_error": 0.0, "agency_confidence": 1.0,
            "self_generated": True, "pe_ema": 0.0,
        }
        try:
            from System.swarm_efference_copy import compute_efference_copy
            _observed_tick = {
                "td_value":        float(mem_row.get("td_value", 0.5) or 0.5),
                "uncertainty":     float((_stability_snapshot.get("terms") or {}).get("world_error_norm", 0.5) or 0.5),
                "stability_score": float((_stability_snapshot.get("terms") or {}).get("stability_score", 0.5) or 0.5),
                "astrocyte_heat":  float((_stability_snapshot.get("terms") or {}).get("astrocyte_heat_norm", 0.3) or 0.3),
                "na_level":        float(_lc_na_receipt.get("na_level", 0.5) or 0.5),
                "valence":         0.5,  # placeholder: valence not yet computed this tick
            }
            _efference_receipt = compute_efference_copy(
                action_kind=str(action.get("type") or action.get("name") or "body_brain_tick"),
                action_payload={"task_id": str(mem_row.get("tick_id") or "")},
                observed_tick_state=_observed_tick,
                root=_STATE_DIR,
                write_ledger=True,
            )
            # Wire PE boost into LC/NA: unexpected outcomes elevate arousal (Blakemore 1998)
            _efference_pe = float(_efference_receipt.get("prediction_error", 0.0))
            if _efference_pe > 0.3:
                _pe_arousal_bump = round((_efference_pe - 0.3) * 0.3, 4)  # modest bump
                _existing_na = float(_lc_na_receipt.get("na_level_tom_boosted",
                                      _lc_na_receipt.get("na_level", 0.5)))
                _lc_na_receipt["na_level_efference_boosted"] = round(min(1.0, _existing_na + _pe_arousal_bump), 4)
            logger.debug(
                "[Event143] Efference PE=%.3f agency_conf=%.3f self_gen=%s pe_ema=%.3f",
                _efference_pe,
                float(_efference_receipt.get("agency_confidence", 1.0)),
                _efference_receipt.get("self_generated"),
                float(_efference_receipt.get("pe_ema", 0.0)),
            )
        except Exception:
            logger.debug("Efference copy organ skipped (non-fatal)")

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
            from System.swarm_organizational_identity import build_current_internal_state_vector

            _terms = _stability_snapshot.get("terms", {}) if isinstance(_stability_snapshot, dict) else {}
            _uncertainty = max(
                float(_terms.get("world_error_norm", 0.0) or 0.0),
                float(_terms.get("astrocyte_heat_norm", 0.0) or 0.0),
                abs(1.0 - float(mem_row.get("td_value", 0.0) or 0.0)),
                # Efference PE: unexpected outcomes add to uncertainty (Frith 2000)
                float(_efference_receipt.get("prediction_error", 0.0)) * 0.5,
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
            if bool(_identity_receipt.get("conservative_mode", False)):
                _revival = float(_identity_receipt.get("revival_score", 1.0) or 1.0)
                _probe_threshold += min(0.20, max(0.0, 1.0 - _revival) * 0.25)
            _probe_threshold = min(0.85, max(0.15, _probe_threshold))
            _proto_before_probe = build_current_internal_state_vector(root=_STATE_DIR)

            # Poll biological stress state (§10.14.28 integration)
            _dam_stage = 0
            _tme_phase = "EQUILIBRIUM"
            try:
                import json
                _microglia_log = _STATE_DIR / "microglia_synaptic_prunes.jsonl"
                if _microglia_log.exists():
                    _lines = [l for l in _microglia_log.read_text(errors="replace").splitlines() if l.strip()]
                    if _lines:
                        _dam_stage = int(json.loads(_lines[-1]).get("dam_stage", 0))
                
                _tme_log = _STATE_DIR / "tumor_immune_stigmergic_lab.jsonl"
                if _tme_log.exists():
                    _lines = [l for l in _tme_log.read_text(errors="replace").splitlines() if l.strip()]
                    if _lines:
                        _tme_phase = str(json.loads(_lines[-1]).get("phase", "EQUILIBRIUM"))
            except Exception:
                pass

            _causal_probe_receipt = propose_and_execute_runtime_intervention(
                tick_id=causal_probe_tick if causal_probe_tick is not None else str(mem_row.get("tick_id") or ""),
                current_uncertainty=min(1.0, max(0.0, _uncertainty)),
                current_clamp_level=str(_clamp_receipt.get("clamp_level", "NONE")),
                root=_STATE_DIR,
                uncertainty_threshold=_probe_threshold,
                dam_stage=_dam_stage,
                tme_phase=_tme_phase,
                na_level=float(_lc_na_receipt.get("na_level", 0.5) or 0.5),
            )
            if _causal_probe_receipt:
                _effect = float(_causal_probe_receipt.get("causal_effect_size", 0.0) or 0.0)
                _target = _causal_probe_receipt.get("intervention", {}).get("do", {}).get("target")
                _dry_run = _causal_probe_receipt.get("intervention", {}).get("do", {}).get("dry_run")
                _core_self_before_event = _proto_before_probe
                _core_self_event_type = "CAUSAL_PROBE"
                _core_self_event_salience = _core_self_salience(
                    action_confidence=(action or {}).get("confidence", 0.5),
                    causal_effect_size=_effect,
                    uncertainty=_uncertainty,
                    valence=_valence,
                    na_level=float(_lc_na_receipt.get("na_level", 0.5) or 0.5),
                    clamp_level=str(_clamp_receipt.get("clamp_level", "NONE")),
                )
                _core_self_event_summary = (
                    f"causal_probe target={_target} effect={_effect:.3f} "
                    f"dry_run={_dry_run} threshold={_probe_threshold:.3f}"
                )
                logger.info(
                    "[Event139] Active causal probe target=%s effect=%.3f dry_run=%s metacog_regime=%s valence=%.3f threshold=%.3f",
                    _target,
                    _effect,
                    _dry_run,
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
                        # Rich fractalkine (\u00a710.14.25 \u2014 Cardona 2006; Paolicelli 2011)
                        # stability_dwell_score: 1.0 when NONE, falls for active clamps
                        _clamp_lv = str(_clamp_receipt.get("clamp_level", "NONE"))
                        _dwell_score = {
                            "NONE": 1.0, "RATE_LIMIT": 0.5,
                            "BLOCK_NEW": 0.2, "EMERGENCY": 0.0,
                        }.get(_clamp_lv, 0.0)
                        # goal_alignment: arbiter action confidence as proxy
                        _goal_align = float(
                            (action or {}).get("confidence", 0.5) or 0.5
                        )
                        # owner_frustration: directly from ToM receipt (Ransohoff 2009)
                        _owner_frustr = float(
                            (_tom_receipt.get("owner_state") or {}).get("frustration", 0.0) or 0.0
                        )
                        _identity_conservative = bool(_identity_receipt.get("conservative_mode", False))
                        _identity_revival = float(_identity_receipt.get("revival_score", 1.0) or 1.0)
                        _max_prunes = _clamp_overrides.get("max_prunes_override")
                        if _identity_conservative:
                            _max_prunes = 0
                        _pruning_conservatism = float(
                            _tom_receipt.get("pruning_conservatism", 0.0) or 0.0
                        )
                        if _identity_conservative:
                            _pruning_conservatism += min(0.5, max(0.0, 1.0 - _identity_revival) * 0.5)
                        _microglia.prune(
                            _candidates,
                            ledger_type="replay",
                            stability_ok=_stability_ok,
                            max_prunes_override=_max_prunes,
                            tail_lines_read=_tail_take,
                            # Two-signal inhibition (Griciuc 2013 CD33)
                            pruning_conservatism=_pruning_conservatism,
                            clamp_level=_clamp_lv,
                            na_level=float(
                                _lc_na_receipt.get(
                                    "na_level_efference_boosted",
                                    _lc_na_receipt.get(
                                        "na_level_tom_boosted",
                                        _lc_na_receipt.get("na_level", 0.5),
                                    ),
                                ) or 0.5
                            ),
                            valence=float(_valence_receipt.get("valence", 0.0) or 0.0),
                            # Rich fractalkine CX3CL1 inputs (\u00a710.14.25)
                            stability_dwell_score=_dwell_score,
                            goal_alignment=_goal_align,
                            owner_frustration=_owner_frustr,
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
        
        # 10. Snapshot Proto-Self + Core Self Interaction (Damasio Phase 1/2)
        try:
            from System.swarm_organizational_identity import (
                build_current_internal_state_vector,
                record_core_self_interaction,
                snapshot_proto_self,
            )
            _tick_val = causal_probe_tick if causal_probe_tick is not None else int(time.time())
            if _core_self_before_event is not None and _core_self_event_type:
                _proto_after_event = build_current_internal_state_vector(root=_STATE_DIR)
                record_core_self_interaction(
                    interaction_type=_core_self_event_type,
                    salience=_core_self_event_salience,
                    proto_self_before=_core_self_before_event,
                    proto_self_after=_proto_after_event,
                    summary=_core_self_event_summary,
                    root=_STATE_DIR,
                    tick_id=_tick_val,
                )
            if _tick_val % 5 == 0:
                snapshot_proto_self(root=_STATE_DIR, tick_id=_tick_val)
        except Exception:
            logger.debug("Proto/Core-self identity producer skipped")
        
        # 11. Stigmergic organ heartbeats (Event 400) — keep prompt-visible
        # Body Monitor organs fresh through receipt-backed ledgers.
        try:
            self._write_organ_heartbeats(
                action=action,
                value=value,
                danger=danger,
                mem_row=mem_row,
                now_state=now_state,
            )
        except Exception:
            logger.debug("Organ heartbeat write skipped")
        
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

    def _write_organ_heartbeats(
        self,
        *,
        action: Dict[str, Any],
        value: float,
        danger: Dict[str, Any],
        mem_row: Dict[str, Any],
        now_state: Any,
    ) -> None:
        """
        Event 400: Maintain active ledger rows for the final prompt-visible
        biological organs and truth-continuity.

        These rows are not high-resolution perception. They are heartbeat
        receipts proving the organs are connected to the body-brain tick and
        keeping their composite-identity probes fresh.
        """
        import hashlib
        import math
        from System.organ_event_schema import build_organ_event
        from System.swarm_kernel_identity import owner_silicon

        _state = _STATE_DIR
        _state.mkdir(exist_ok=True)
        now = time.time()
        tick_id = str(mem_row.get("tick_id") or "")
        action_type = str(action.get("type") or action.get("name") or "body_brain_tick")
        action_target = str(action.get("target") or action.get("kind") or "")
        mode = str(danger.get("mode") or "UNKNOWN")
        value_f = _clip01(value, default=0.5)
        pressure = _clip01(danger.get("pressure", 0.0), default=0.0)
        
        hw_serial = owner_silicon()

        def _append_jsonl(name: str, row: Dict[str, Any]) -> None:
            append_line_locked(
                _state / name,
                json.dumps(row, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        def _write_json(name: str, row: Dict[str, Any]) -> None:
            path = _state / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")

        def _organ_event(
            *,
            organ: str,
            event_type: str,
            payload: Dict[str, Any],
        ) -> Dict[str, Any]:
            row = build_organ_event(
                source="swarm_body_brain_loop:organ_heartbeat",
                homeworld_serial=hw_serial,
                organ=organ,
                event_type=event_type,
                payload={
                    **payload,
                    "tick_id": tick_id,
                    "action_type": action_type,
                    "target": action_target,
                    "metabolic_mode": mode,
                },
                truth_label="OPERATIONAL",
                ts=now,
                mark_schema=True,
            )
            # Keep legacy top-level fields during migration so existing probes
            # can read the same heartbeat while payload-aware readers roll out.
            row.update(payload)
            row["tick_id"] = tick_id
            return row

        # --- Stigmergic Cross-Organ Coupling ---
        # Read the previous states to implement a unified coupled dynamical system.
        def _read_last_row(filename: str) -> Dict[str, Any]:
            try:
                path = _state / filename
                if filename.endswith(".json"):
                    return json.loads(path.read_text(encoding="utf-8"))
                lines = path.read_text(encoding="utf-8").strip().splitlines()
                if lines:
                    return json.loads(lines[-1])
            except Exception:
                pass
            return {}

        def _read_last(filename: str) -> Dict[str, Any]:
            row = _read_last_row(filename)
            return row.get("payload", row) if isinstance(row, dict) else {}

        def _ledger_freshness(filename: str, max_age_s: float = 600.0) -> float:
            try:
                row = _read_last_row(filename)
                payload = row.get("payload", {}) if isinstance(row.get("payload"), dict) else {}
                ts = row.get("ts", payload.get("ts", 0.0))
                age = now - float(ts or 0.0)
                if age < 0:
                    return 1.0
                return max(0.0, min(1.0, 1.0 - age / max(1.0, max_age_s)))
            except Exception:
                return 0.0

        last_electric = _read_last("electric_field.jsonl")
        last_honeybee = _read_last("waggle_quorum.jsonl")
        last_octopus = _read_last("motor_bus.jsonl")
        last_truth = _read_last("truth_continuity_events.jsonl")

        prev_e_phase = float(last_electric.get("phase", 0.0) or 0.0)
        prev_hb_vigor = float(last_honeybee.get("vigor", 0.5) or 0.5)
        prev_octo_coh = float(last_octopus.get("coherence", 0.5) or 0.5)
        truth_score = _clip01(last_truth.get("continuity_score", 1.0), default=1.0)
        truth_flags = last_truth.get("drift_flags", [])
        if not isinstance(truth_flags, list):
            truth_flags = []
        if last_truth.get("override_applied") or "allowed_dissociation_override" in truth_flags:
            truth_reward = float(last_truth.get("td_reward_override", 0.0) or 0.0)
        else:
            truth_reward = max(-1.0, min(0.0, truth_score - 1.0 - 0.10 * len(truth_flags)))

        # --- High-Dimensional Stigmergic Field Coupling ---
        # "Alice must be aware of her all organs all senses everything in her stigmergic unified field"
        # We read the real spatial 2D pheromone gradient to seed the biology.
        try:
            from System.swarm_pheromone_field import _real_position, sample_gradient
            px, py, _ = _real_position()
            (bx, by), phero_val = sample_gradient(px, py)
            dx, dy = bx - px, by - py
        except Exception:
            dx, dy, phero_val = 0.0, 0.0, 0.0

        # --- Cognitive Feedback (Mind -> Body) ---
        # The biological field physically responds to cognitive decisions and surprise/dopamine.
        td_error = 0.0
        bg_action = "idle"
        try:
            td_row = _read_last("td_receipts.jsonl")
            if td_row:
                td_error = float(td_row.get("td_error", 0.0))

            bg_row = _read_last("basal_ganglia_selections.jsonl")
            if bg_row:
                bg_action = str(
                    bg_row.get("selected_action")
                    or bg_row.get("winner")
                    or bg_row.get("action")
                    or "idle"
                )
        except Exception:
            pass

        # --- Cognitive / Reflex Organ Receipts ---
        # Keep the decision substrate fresh in the same state directory as this
        # body tick. These are heartbeat-level Bellman and episode receipts, not
        # claims of solved general intelligence.
        td_actions = ["listen", "respond", "log_body_event", "probe_vision", "idle"]
        td_action = action_type if action_type in td_actions else "idle"
        prev_cuttlefish = _read_last("cuttlefish_display.jsonl")
        prev_skin = str(prev_cuttlefish.get("pattern", "mottle"))[:16]
        td_state = (
            f"{mode}:value_{int(value_f * 10):02d}:"
            f"pressure_{int(pressure * 10):02d}:skin_{prev_skin}"
        )
        td_next_state = f"{mode}:value_{int(value_f * 10):02d}:pressure_{int(pressure * 10):02d}:skin_pending"
        reward = round(max(-1.0, min(1.0, value_f - pressure + truth_reward)), 4)
        try:
            q_path = _state / "td_q_table.json"
            if q_path.exists():
                q_table = json.loads(q_path.read_text(encoding="utf-8"))
                if not isinstance(q_table, dict):
                    q_table = {}
            else:
                q_table = {}
            for state_key in (td_state, td_next_state):
                if state_key not in q_table or not isinstance(q_table.get(state_key), dict):
                    q_table[state_key] = {name: 0.0 for name in td_actions}
                else:
                    for name in td_actions:
                        q_table[state_key].setdefault(name, 0.0)
            q_sa = float(q_table[td_state].get(td_action, 0.0))
            max_next = max(float(v) for v in q_table[td_next_state].values())
            td_error = reward + 0.95 * max_next - q_sa
            q_table[td_state][td_action] = q_sa + 0.1 * td_error
            _write_json("td_q_table.json", q_table)
        except Exception:
            td_error = reward
            q_table = {td_state: {name: 0.0 for name in td_actions}}

        marker = "BURST" if td_error > 0.1 else ("PAUSE" if td_error < -0.1 else "TONIC")
        td_receipt = {
            "ts": now,
            "state": td_state,
            "action": td_action,
            "reward": reward,
            "td_error": round(td_error, 6),
            "truth_continuity_score": round(truth_score, 4),
            "truth_reward": round(truth_reward, 4),
            "truth_drift_flags": [str(flag)[:80] for flag in truth_flags[:8]],
            "q_states": len(q_table),
            "source": "swarm_body_brain_loop:cognitive_heartbeat",
            "tick_id": tick_id,
            "coupled_from": [
                "body_brain_tick.value",
                "body_brain_tick.pressure",
                "cuttlefish_display.jsonl",
                "truth_continuity_events.jsonl",
            ],
        }
        _append_jsonl("td_receipts.jsonl", td_receipt)
        _append_jsonl(
            "dopamine_reward_ledger.jsonl",
            {
                "ts": now,
                "delta": round(td_error, 6),
                "marker": marker,
                "action": td_action,
                "source": "swarm_body_brain_loop:cognitive_heartbeat",
                "context": "body_brain_tick",
                "truth_reward": round(truth_reward, 4),
                "tick_id": tick_id,
            },
        )
        episode_id = hashlib.sha256(f"{now:.6f}:{tick_id}:body_brain_tick".encode()).hexdigest()[:12]
        _append_jsonl(
            "hippocampus/events.jsonl",
            {
                "ts": now,
                "episode_id": episode_id,
                "event_type": "body_brain_tick",
                "summary": (
                    f"Body tick action={td_action} mode={mode} value={value_f:.3f} "
                    f"pressure={pressure:.3f} td_error={td_error:.3f}"
                ),
                "source": "swarm_body_brain_loop:cognitive_heartbeat",
                "tick_id": tick_id,
            },
        )
        reflex_fired = bool(pressure >= 0.85 or mode in {"RED_CONSERVE", "CRITICAL_STARVATION"})
        _append_jsonl(
            "reflex_arc_trace.jsonl",
            {
                "ts": now,
                "category": "pressure_reflex" if reflex_fired else "monitor_tick",
                "latency_ms": 0.1 if reflex_fired else 0.0,
                "fired": reflex_fired,
                "source": "swarm_body_brain_loop:reflex_monitor",
                "pressure": round(pressure, 4),
                "metabolic_mode": mode,
                "tick_id": tick_id,
            },
        )

        # Honeybee (Waggle Dance Vector)
        # Driven by true spatial insect stigmergy: bees orient the waggle run relative to the pheromone gradient
        base_angle = math.atan2(dy, dx) if (dx != 0 or dy != 0) else 0.0
        # If no local gradient, use internal memory route Hash + phase
        if dx == 0 and dy == 0:
            action_hash = sum(ord(ch) for ch in action_type + action_target)
            base_angle = (action_hash * 0.017 + now * 0.01) % (2 * math.pi)
        base_angle = (base_angle + 0.1 * math.sin(prev_e_phase)) % (2 * math.pi)

        # ── HOMEOSTATIC CONTROLLER CLAMPS ──
        # Monitor somatic volatility. If soma_score drops >0.25 in <5 ticks -> emergency damping
        emergency_damping = False
        try:
            visc_lines = (_state / "visceral_field.jsonl").read_text(encoding="utf-8").strip().splitlines()[-5:]
            if len(visc_lines) >= 2:
                scores = [float(json.loads(line).get("payload", {}).get("soma_score", 1.0)) for line in visc_lines]
                if scores[0] - scores[-1] > 0.25:
                    emergency_damping = True
        except Exception:
            pass

        # Cognitive Feedback: TD Error (Dopamine surprise) directly spikes Honeybee Vigor
        # Clamp TD error contribution to vigor capped at +0.3 per tick
        cognitive_arousal = min(0.3, abs(td_error))
        
        raw_vigor = 0.35 + 0.50 * value_f + 0.15 * phero_val + 0.05 * prev_octo_coh + cognitive_arousal
        if emergency_damping:
            raw_vigor *= 0.5 # Emergency damping mode
            
        # Vigor clamped to [0.1, 0.95]
        vigor = max(0.1, min(0.95, raw_vigor))
        waggle_vector = [round(math.cos(base_angle) * vigor, 4), round(math.sin(base_angle) * vigor, 4)]
        
        _append_jsonl(
            "waggle_quorum.jsonl",
            _organ_event(
                organ="honeybee",
                event_type="waggle_vector",
                payload={
                    "angle": round(base_angle, 6),
                    "vigor": round(vigor, 4),
                    "dance_vector": waggle_vector,
                    "local_pheromone": round(phero_val, 4),
                    "route": action_target or action_type,
                    "prev_electric_phase": round(prev_e_phase, 6),
                    "prev_octopus_coherence": round(prev_octo_coh, 6),
                    "coupled_from": ["swarm_pheromone_field.py", "electric_field.jsonl", "motor_bus.jsonl"],
                },
            ),
        )

        # Octopus (Motor Nerve Tensor)
        # The 8 arms deploy directionally based on the Honeybee spatial vector, metabolic pressure,
        # and are physically biased by the Basal Ganglia's cognitive action selection.
        motor_vigor = max(0.0, min(1.0, 0.75 * vigor + 0.25 * prev_hb_vigor))
        arm_activations = []
        for i in range(8):
            arm_angle = i * (math.pi / 4.0)
            # Alignment between the arm's natural angle and the swarm's spatial drive vector
            alignment = math.cos(arm_angle - base_angle)
            
            # Cognitive Feedback: Defense actions pull arms inward (negative alignment bias)
            # Explore actions push arms outward.
            cognitive_motor_bias = 0.0
            if "protect" in bg_action or "repair" in bg_action:
                cognitive_motor_bias = -0.2
            elif "explore" in bg_action or "forage" in bg_action:
                cognitive_motor_bias = +0.2
                
            activation = max(0.0, min(1.0, 0.5 + 0.3 * alignment * motor_vigor - 0.2 * pressure + cognitive_motor_bias))
            arm_activations.append(round(activation, 4))
            
        overall_coherence = round(sum(arm_activations) / 8.0, 4)
        _append_jsonl(
            "motor_bus.jsonl",
            _organ_event(
                organ="octopus",
                event_type="motor_bus_tensor",
                payload={
                    "coherence": overall_coherence,
                    "arms_active": 8,
                    "arm_activations": arm_activations,
                    "prev_honeybee_vigor": round(prev_hb_vigor, 6),
                    "coupled_from": ["waggle_quorum.jsonl"],
                },
            ),
        )

        # Electric Field (3D Dipole Moments)
        # Muscle twitches from the 8 octopus arms physically generate the electric field.
        # We project the 8 arm activations into a 3D dipole vector [x, y, z]
        dipole_x = sum(a * math.cos(i * math.pi / 4) for i, a in enumerate(arm_activations))
        dipole_y = sum(a * math.sin(i * math.pi / 4) for i, a in enumerate(arm_activations))
        dipole_z = max(-1.0, min(1.0, value_f - pressure + 0.1 * (prev_octo_coh - 0.5)))  # autonomic tone
        dipole_vector = [round(dipole_x, 4), round(dipole_y, 4), round(dipole_z, 4)]
        phase = math.atan2(dipole_y, dipole_x) % (2 * math.pi)
        
        _append_jsonl(
            "electric_field.jsonl",
            _organ_event(
                organ="electric",
                event_type="dipole_tensor",
                payload={
                    "phase": round(phase, 6),
                    "jar_active": True,
                    "dipole_moments": dipole_vector,
                    "prev_octopus_coherence": round(prev_octo_coh, 6),
                    "coupled_from": ["motor_bus.jsonl"],
                },
            ),
        )

        # Cuttlefish (Chromatophore Skin Grid)
        # The skin is a high-dimensional 4x4 matrix, visually expressing the internal electrical state and pressure.
        chromatophore_grid = []
        for row in range(4):
            grid_row = []
            for col in range(4):
                # Ripple effect driven by electric phase and local pressure
                cell_val = (
                    0.5
                    + 0.3 * math.sin(phase + 0.1 * prev_e_phase + (row * col * 0.5))
                    + 0.2 * phero_val
                    + 0.05 * (prev_hb_vigor - 0.5)
                )
                grid_row.append(round(max(0.0, min(1.0, cell_val)), 4))
            chromatophore_grid.append(grid_row)
            
        contrast = round(sum(sum(r) for r in chromatophore_grid) / 16.0, 4)
        pattern = "alarm" if (pressure >= 0.65 or vigor > 0.85 or prev_hb_vigor > 0.85) else "mottle"
        _append_jsonl(
            "cuttlefish_display.jsonl",
            _organ_event(
                organ="cuttlefish",
                event_type="chromatophore_grid",
                payload={
                    "contrast": contrast, 
                    "pattern": pattern,
                    "skin_matrix": chromatophore_grid,
                    "prev_electric_phase": round(prev_e_phase, 6),
                    "prev_honeybee_vigor": round(prev_hb_vigor, 6),
                    "coupled_from": ["electric_field.jsonl", "waggle_quorum.jsonl", "swarm_pheromone_field.py"],
                },
            ),
        )

        # Basal Ganglia (decision selector receipt)
        # The selector reads the current biological field and writes the winner
        # for the next tick's motor bias. This closes the field freshness loop
        # without feeding current-tick decisions backward in time.
        dopamine_proxy = max(0.0, min(1.0, 0.5 + 0.35 * max(-1.0, min(1.0, td_error))))
        candidate_loops = [
            {
                "name": td_action,
                "salience": 0.45 + 0.20 * value_f,
                "cost": 0.20 + 0.15 * pressure,
                "reward_potential": 0.50 + 0.20 * value_f,
            },
            {
                "name": "repair",
                "salience": 0.35 + 0.55 * pressure,
                "cost": 0.18,
                "reward_potential": 0.65,
            },
            {
                "name": "explore",
                "salience": 0.35 + 0.45 * value_f,
                "cost": 0.28 + 0.35 * pressure,
                "reward_potential": 0.70,
            },
            {
                "name": "idle",
                "salience": 0.30,
                "cost": 0.05,
                "reward_potential": 0.20,
            },
        ]
        bg_scored = []
        bg_winner = "idle"
        bg_score = float("-inf")
        alarm_active = pattern == "alarm"
        electric_tone = float(dipole_z)
        for loop in candidate_loops:
            name = str(loop["name"])
            salience = float(loop["salience"])
            cost = float(loop["cost"])
            reward_potential = float(loop["reward_potential"])
            if alarm_active:
                if "protect" in name or "repair" in name:
                    salience += 0.30
                elif "explore" in name:
                    cost += 0.40
            if electric_tone > 0.60:
                cost = max(0.0, cost - 0.15)
            net_score = salience + dopamine_proxy * reward_potential - cost
            bg_scored.append({"name": name, "net_score": round(net_score, 4)})
            if net_score > bg_score:
                bg_score = net_score
                bg_winner = name
        _append_jsonl(
            "basal_ganglia_selections.jsonl",
            {
                "ts": now,
                "truth_label": "BASAL_GANGLIA_SELECTION",
                "selected_action": bg_winner,
                "winner": bg_winner,
                "winner_score": round(bg_score, 4),
                "dopamine_proxy": round(dopamine_proxy, 4),
                "competing_loops": len(candidate_loops),
                "biological_modifiers": {
                    "cuttlefish_alarm": alarm_active,
                    "electric_tone": round(electric_tone, 4),
                },
                "candidates": bg_scored,
                "source": "swarm_body_brain_loop:bg_selector_heartbeat",
                "tick_id": tick_id,
                "coupled_from": [
                    "td_receipts.jsonl",
                    "dopamine_reward_ledger.jsonl",
                    "cuttlefish_display.jsonl",
                    "electric_field.jsonl",
                ],
            },
        )
        _append_jsonl(
            "corvid_apprentice_trace.jsonl",
            {
                "event_kind": "CORVID_APPRENTICE_HEARTBEAT",
                "ts": now,
                "task": "idle",
                "model": "alice-m1-scout-2.3b-2.7gb:latest",
                "latency_s": 0.0,
                "success": True,
                "heartbeat_only": True,
                "source": "swarm_body_brain_loop:corvid_heartbeat",
                "selected_action": bg_winner,
                "tick_id": tick_id,
                "coupled_from": [
                    "body_brain_tick",
                    "basal_ganglia_selections.jsonl",
                ],
            },
        )

        # Real metabolic cost: make inference latency, estimated token burn,
        # estimated joules, and hardware thermal pressure visible to the field.
        result = mem_row.get("result", {}) if isinstance(mem_row.get("result"), dict) else {}
        latency_s = max(0.0, float(result.get("latency", 0.0) or 0.0))
        estimated_tokens = max(1, int(len(json.dumps(mem_row, ensure_ascii=False)) / 4))
        estimated_joules = round(max(0.001, latency_s * 8.0), 6)
        thermal_stress = 0.0
        thermal_source = "unavailable"
        try:
            import subprocess
            therm = subprocess.run(
                ["pmset", "-g", "therm"],
                capture_output=True,
                text=True,
                timeout=0.35,
                check=False,
            )
            if therm.stdout:
                thermal_source = "pmset -g therm"
                for line in therm.stdout.splitlines():
                    if "CPU_Speed_Limit" in line and "=" in line:
                        limit = float(line.rsplit("=", 1)[1].strip())
                        thermal_stress = _clip01(1.0 - limit / 100.0)
                        break
        except Exception:
            pass
        cost_pressure = _clip01(
            latency_s / 2.0
            + estimated_joules / 20.0
            + estimated_tokens / 4000.0
            + thermal_stress
        )
        metabolic_cost = {
            "latency_ms": round(latency_s * 1000.0, 3),
            "estimated_tokens": estimated_tokens,
            "estimated_joules": estimated_joules,
            "thermal_stress": round(thermal_stress, 4),
            "thermal_source": thermal_source,
            "cost_pressure": round(cost_pressure, 6),
            "source": "result.latency+mem_row_size+hardware_thermal_probe",
            "truth_label": "ESTIMATED",
        }

        # Unified high-dimensional field vector.
        # This is the prompt/ledger bridge from "separate organ values" to one
        # receipt-backed field. It records the vector, its dimensions, source
        # ledgers, and the coupling graph used to compute it.
        dimension_names = (
            ["waggle_x", "waggle_y"]
            + [f"octopus_arm_{i}" for i in range(8)]
            + ["electric_dipole_x", "electric_dipole_y", "electric_dipole_z"]
            + [f"skin_{row}_{col}" for row in range(4) for col in range(4)]
            + ["metabolic_value", "metabolic_pressure", "local_pheromone"]
            + ["latency_ms_norm", "joules_norm", "thermal_stress", "token_burn_norm"]
        )
        skin_flat = [cell for grid_row in chromatophore_grid for cell in grid_row]
        field_vector = [
            *waggle_vector,
            *arm_activations,
            *dipole_vector,
            *skin_flat,
            round(value_f, 4),
            round(pressure, 4),
            round(phero_val, 4),
            round(min(1.0, latency_s / 2.0), 4),
            round(min(1.0, estimated_joules / 20.0), 4),
            round(thermal_stress, 4),
            round(min(1.0, estimated_tokens / 4000.0), 4),
        ]
        declared_organs = [
            "field",
            "rl",
            "octopus",
            "cuttlefish",
            "electric",
            "honeybee",
            "starling",
            "fly",
            "metabolic",
            "time",
            "reflex",
            "corvid",
            "td_learner",
            "dopamine",
            "hippocampus",
            "sensor_gate",
            "bg_selector",
        ]
        td_receipt_freshness = _ledger_freshness("td_receipts.jsonl")
        sensor_gate_row = _read_last("sensor_gate_lock.json")
        sensor_gate_known = bool(sensor_gate_row)
        sensor_gate_health = 0.0
        if sensor_gate_known:
            sensor_gate_health = 0.35 if sensor_gate_row.get("locked") is True else 1.0
        bg_selector_freshness = _ledger_freshness("basal_ganglia_selections.jsonl")
        organ_health = {
            "field": 0.0,  # filled after field_energy is computed
            "rl": max(td_receipt_freshness, min(1.0, abs(td_error))),
            "octopus": overall_coherence,
            "cuttlefish": contrast,
            "electric": 1.0 if dipole_vector else 0.0,
            "honeybee": round(vigor, 4),
            "starling": _ledger_freshness("network_topology.jsonl"),
            "fly": _ledger_freshness("active_window.jsonl", 120.0),
            "metabolic": max(0.0, min(1.0, value_f)),
            "time": 1.0,
            "reflex": _ledger_freshness("reflex_arc_trace.jsonl"),
            "corvid": _ledger_freshness("corvid_apprentice_trace.jsonl"),
            "td_learner": td_receipt_freshness,
            "dopamine": min(1.0, abs(td_error)),
            "hippocampus": _ledger_freshness("hippocampus/events.jsonl", 3600.0),
            "sensor_gate": sensor_gate_health,
            "bg_selector": bg_selector_freshness,
        }
        organ_health_vector = [round(float(organ_health.get(name, 0.0)), 4) for name in declared_organs]
        dimension_names = list(dimension_names) + [f"organ_health_{name}" for name in declared_organs]
        field_vector = field_vector + organ_health_vector
        field_energy = math.sqrt(sum(float(x) * float(x) for x in field_vector) / len(field_vector))
        organ_health["field"] = round(field_energy, 4)
        # ── SWIMMER MITOSIS AND APOPTOSIS ──
        # Swimmers are not just static structures; they live, die, and reproduce 
        # based on the metabolic health and cognitive coherence of their organ.
        base_swimmer_counts = {
            "field": len(declared_organs),
            "rl": 2,
            "octopus": 8,
            "cuttlefish": 16,
            "electric": 3,
            "honeybee": 2,
            "starling": 3,
            "fly": 2,
            "metabolic": 4,
            "time": 3,
            "reflex": 2,
            "corvid": 2,
            "td_learner": 5,
            "dopamine": 2,
            "hippocampus": 3,
            "sensor_gate": 2,
            "bg_selector": 5,
        }
        
        # Recover previous generations
        prev_swimmers = {}
        try:
            prev_lines = (_state / "organ_field_vector.jsonl").read_text(encoding="utf-8").strip().splitlines()
            if prev_lines:
                last_state = json.loads(prev_lines[-1])
                for node in last_state.get("payload", {}).get("organ_nodes", []):
                    prev_swimmers[node["organ"]] = node.get("swimmer_count", base_swimmer_counts.get(node["organ"], 1))
        except Exception:
            pass
            
        swimmer_counts = {}
        for organ_name, base_count in base_swimmer_counts.items():
            current_count = prev_swimmers.get(organ_name, base_count)
            health = float(organ_health.get(organ_name, 0.5))
            
            # Evolution Step
            if health > 0.85 and current_count < base_count * 3:
                current_count += 1 # Mitosis
            elif health < 0.35 and current_count > 1:
                current_count -= 1 # Apoptosis
                
            swimmer_counts[organ_name] = current_count
        organ_nodes = [
            {
                "organ": name,
                "health": round(float(organ_health.get(name, 0.0)), 4),
                "swimmer_count": int(swimmer_counts.get(name, 1)),
            }
            for name in declared_organs
        ]
        swimmer_registry = []
        try:
            from System.swimmer_registry import seed_default_swimmers as _sr_seed
            _sr_export = _sr_seed().export_for_field()
            if _sr_export:
                swimmer_registry = _sr_export
        except Exception:
            pass
        if not swimmer_registry:
            for node in organ_nodes:
                for idx in range(int(node["swimmer_count"])):
                    swimmer_registry.append({
                        "swimmer_id": f"{node['organ']}:{idx}",
                        "organ": node["organ"],
                        "index": idx,
                    })
        coupling_edges = [
            {"source": "swarm_pheromone_field.py", "target": "honeybee", "variables": ["angle", "vigor", "dance_vector"]},
            {"source": "electric_field.jsonl", "target": "honeybee", "variables": ["prev_electric_phase"]},
            {"source": "motor_bus.jsonl", "target": "honeybee", "variables": ["prev_octopus_coherence"]},
            {"source": "body_brain_tick.value", "target": "honeybee", "variables": ["vigor"]},
            {"source": "honeybee", "target": "octopus", "variables": ["dance_vector", "vigor"]},
            {"source": "waggle_quorum.jsonl", "target": "octopus", "variables": ["prev_honeybee_vigor"]},
            {"source": "octopus", "target": "electric", "variables": ["arm_activations", "coherence"]},
            {"source": "motor_bus.jsonl", "target": "electric", "variables": ["prev_octopus_coherence"]},
            {"source": "electric", "target": "cuttlefish", "variables": ["phase", "dipole_moments"]},
            {"source": "electric_field.jsonl", "target": "cuttlefish", "variables": ["prev_electric_phase"]},
            {"source": "waggle_quorum.jsonl", "target": "cuttlefish", "variables": ["prev_honeybee_vigor"]},
            {"source": "swarm_pheromone_field.py", "target": "cuttlefish", "variables": ["local_pheromone"]},
            {"source": "body_brain_tick.pressure", "target": "octopus", "variables": ["arm_activations"]},
            {"source": "body_brain_tick.pressure", "target": "cuttlefish", "variables": ["pattern", "contrast"]},
            {"source": "td_learner", "target": "dopamine", "variables": ["td_error"]},
            {"source": "td_learner", "target": "honeybee", "variables": ["cognitive_arousal", "vigor"]},
            {"source": "basal_ganglia", "target": "octopus", "variables": ["cognitive_motor_bias", "arm_activations"]},
            {"source": "cuttlefish", "target": "basal_ganglia", "variables": ["skin_matrix", "pattern"]},
            {"source": "electric", "target": "basal_ganglia", "variables": ["dipole_moments", "autonomic_tone"]},
            {"source": "sensor_gate", "target": "field", "variables": ["locked"]},
            {"source": "hippocampus", "target": "td_learner", "variables": ["episode_context"]},
            {"source": "dopamine", "target": "td_learner", "variables": ["reward_prediction_error"]},
            {"source": "metabolic", "target": "field", "variables": ["value", "pressure"]},
            {"source": "time", "target": "field", "variables": ["tick"]},
        ]
        organ_ring_edges = [
            {
                "source": declared_organs[i],
                "target": declared_organs[(i + 1) % len(declared_organs)],
                "variables": ["organ_health"],
            }
            for i in range(len(declared_organs))
        ]
        coupling_edges.extend(organ_ring_edges)
        source_specs = {
            "field": ("organ_field_vector.jsonl", 1.0, "current_tick_field_vector"),
            "rl": ("td_receipts.jsonl", td_receipt_freshness, "ledger_recent"),
            "octopus": ("motor_bus.jsonl", 1.0, "heartbeat_tensor"),
            "cuttlefish": ("cuttlefish_display.jsonl", 1.0, "heartbeat_tensor"),
            "electric": ("electric_field.jsonl", 1.0, "heartbeat_tensor"),
            "honeybee": ("waggle_quorum.jsonl", 1.0, "heartbeat_tensor"),
            "starling": ("network_topology.jsonl", organ_health["starling"], "ledger_tail"),
            "fly": ("active_window.jsonl", organ_health["fly"], "ledger_tail"),
            "metabolic": ("body_brain_tick.value", 1.0, "current_tick_scalar"),
            "time": ("body_brain_tick.time", 1.0, "current_tick_scalar"),
            "reflex": ("reflex_arc_trace.jsonl", organ_health["reflex"], "ledger_tail"),
            "corvid": ("corvid_apprentice_trace.jsonl", organ_health["corvid"], "ledger_tail"),
            "td_learner": ("td_receipts.jsonl", td_receipt_freshness, "ledger_tail"),
            "dopamine": ("td_receipts.jsonl", td_receipt_freshness, "derived_from_td_error"),
            "hippocampus": ("hippocampus/events.jsonl", organ_health["hippocampus"], "ledger_tail"),
            "sensor_gate": (
                "sensor_gate_lock.json",
                1.0 if sensor_gate_known else 0.0,
                "json_state" if sensor_gate_known else "missing",
            ),
            "bg_selector": (
                "basal_ganglia_selections.jsonl",
                bg_selector_freshness,
                "ledger_tail",
            ),
        }
        for node in organ_nodes:
            source, source_strength, resolution = source_specs.get(
                node["organ"],
                ("unknown", 0.0, "missing"),
            )
            node["source"] = source
            node["source_strength"] = round(float(source_strength), 4)
            node["resolution"] = resolution

        unknown_vectors = []
        low_resolution_vectors = []
        weak_vectors = []
        low_resolution_labels = {
            "heartbeat_tensor",
            "current_tick_scalar",
            "derived_from_td_error",
            "ledger_tail",
        }
        for node in organ_nodes:
            source_strength = float(node.get("source_strength", 0.0))
            health = float(node.get("health", 0.0))
            resolution = str(node.get("resolution") or "missing")
            if source_strength <= 0.0 or resolution == "missing":
                unknown_vectors.append({
                    "organ": node["organ"],
                    "reason": "missing_or_stale_source",
                    "source": node["source"],
                    "health": round(health, 4),
                    "resolution": resolution,
                })
            if resolution in low_resolution_labels:
                low_resolution_vectors.append({
                    "organ": node["organ"],
                    "reason": "low_resolution_receipt",
                    "source": node["source"],
                    "health": round(health, 4),
                    "resolution": resolution,
                })
            if 0.0 < source_strength and health < 0.15:
                weak_vectors.append({
                    "organ": node["organ"],
                    "reason": "low_current_signal",
                    "source": node["source"],
                    "health": round(health, 4),
                    "resolution": resolution,
                })
        field_completeness = (
            (len(declared_organs) - len(unknown_vectors)) / max(1, len(declared_organs))
        )
        homeostatic_error = (
            max(0.0, 0.95 - field_completeness)
            + max(0.0, cost_pressure - 0.65)
            + max(0.0, 0.85 - truth_score)
            + 0.05 * len(truth_flags)
        )
        if homeostatic_error >= 0.35:
            field_homeostasis_state = "CONSERVE_REPAIR"
            field_control_action = "reduce_cost_and_repair_truth"
        elif homeostatic_error >= 0.12:
            field_homeostasis_state = "REGULATE"
            field_control_action = "tighten_outputs_and_watch_cost"
        else:
            field_homeostasis_state = "VIABLE"
            field_control_action = "maintain"
        field_homeostasis = {
            "state": field_homeostasis_state,
            "control_action": field_control_action,
            "error": round(homeostatic_error, 6),
            "targets": {
                "field_completeness_min": 0.95,
                "cost_pressure_max": 0.65,
                "truth_continuity_min": 0.85,
            },
            "observed": {
                "field_completeness": round(field_completeness, 6),
                "cost_pressure": round(cost_pressure, 6),
                "truth_continuity_score": round(truth_score, 4),
                "truth_flag_count": len(truth_flags),
            },
        }
        _append_jsonl(
            "field_homeostasis.jsonl",
            {
                "ts": now,
                "truth_label": "FIELD_HOMEOSTASIS",
                "tick_id": tick_id,
                "source": "swarm_body_brain_loop:field_homeostasis",
                **field_homeostasis,
            },
        )

        prev_field_row = _read_last_row("organ_field_vector.jsonl")
        prev_field_payload = (
            prev_field_row.get("payload", prev_field_row)
            if isinstance(prev_field_row, dict) else {}
        )
        prev_vector = prev_field_payload.get("field_memory_vector") or prev_field_payload.get("field_vector") or []
        prev_ts = float(prev_field_row.get("ts", 0.0) or 0.0) if isinstance(prev_field_row, dict) else 0.0
        memory_age_s = max(0.0, now - prev_ts) if prev_ts else 0.0
        memory_retention = math.exp(-memory_age_s / 3600.0) if prev_vector else 0.0
        field_memory_vector = []
        for idx, current in enumerate(field_vector):
            previous = (
                float(prev_vector[idx])
                if idx < len(prev_vector) and isinstance(prev_vector[idx], (int, float))
                else float(current)
            )
            retained = previous * memory_retention + float(current) * (1.0 - memory_retention)
            field_memory_vector.append(round(retained, 4))
        field_memory_energy = (
            math.sqrt(sum(float(x) * float(x) for x in field_memory_vector) / len(field_memory_vector))
            if field_memory_vector else 0.0
        )
        field_decay = {
            "memory_retention": round(memory_retention, 6),
            "evaporation_rate": round(1.0 - memory_retention, 6),
            "memory_age_s": round(memory_age_s, 3),
            "field_memory_energy": round(field_memory_energy, 6),
            "decay_tau_s": 3600.0,
        }

        motor_effector_policy = {
            "selected_motor_policy": (
                "alarm" if field_homeostasis_state == "CONSERVE_REPAIR" or pattern == "alarm"
                else "thinking" if abs(electric_tone) > 0.55
                else "heartbeat"
            ),
            "effector_gate": "LEDGER_ONLY",
            "octopus_coherence": overall_coherence,
            "electric_tone": round(electric_tone, 4),
            "basal_ganglia_winner": bg_winner,
            "field_homeostasis_state": field_homeostasis_state,
        }
        _append_jsonl(
            "field_motor_effector.jsonl",
            {
                "ts": now,
                "truth_label": "FIELD_MOTOR_EFFECTOR_POLICY",
                "tick_id": tick_id,
                "source": "swarm_body_brain_loop:field_motor_effector",
                **motor_effector_policy,
            },
        )
        _append_jsonl(
            "motor_pulses.jsonl",
            {
                "ts": now,
                "kind": motor_effector_policy["selected_motor_policy"],
                "truth_label": "MOTOR_PULSE",
                "source": "swarm_body_brain_loop:field_motor_effector",
                "effector_gate": "LEDGER_ONLY",
                "tick_id": tick_id,
                "field_homeostasis_state": field_homeostasis_state,
            },
        )

        coupling_edges.extend([
            {"source": "truth_continuity_events.jsonl", "target": "td_learner", "variables": ["truth_reward", "continuity_score", "drift_flags"]},
            {"source": "metabolic_cost", "target": "field", "variables": ["latency_ms", "estimated_joules", "thermal_stress", "estimated_tokens"]},
            {"source": "field_homeostasis", "target": "basal_ganglia", "variables": ["control_action", "error"]},
            {"source": "field_memory", "target": "field", "variables": ["memory_retention", "evaporation_rate"]},
            {"source": "field", "target": "motor_effector", "variables": ["octopus_coherence", "electric_tone", "homeostasis_state"]},
        ])
        field_event = _organ_event(
            organ="unified_field",
            event_type="high_dimensional_field_vector",
            payload={
                "dimension_count": len(field_vector),
                "dimension_names": dimension_names,
                "field_vector": [round(float(x), 4) for x in field_vector],
                "field_energy": round(field_energy, 6),
                "metabolic_cost": metabolic_cost,
                "cost_pressure": round(cost_pressure, 6),
                "field_homeostasis": field_homeostasis,
                "field_homeostasis_state": field_homeostasis_state,
                "field_control_action": field_control_action,
                "field_decay": field_decay,
                "field_memory_vector": field_memory_vector,
                "field_memory_energy": round(field_memory_energy, 6),
                "field_memory_retention": round(memory_retention, 6),
                "motor_effector_policy": motor_effector_policy,
                "truth_reward": round(truth_reward, 4),
                "coupling_edges": coupling_edges,
                "coupling_edge_count": len(coupling_edges),
                "coupling_density": round(len(coupling_edges) / len(field_vector), 6),
                "declared_organs": declared_organs,
                "declared_organ_count": len(declared_organs),
                "connected_organ_count": len({edge["source"] for edge in organ_ring_edges} | {edge["target"] for edge in organ_ring_edges}),
                "organ_health": {k: round(float(v), 4) for k, v in organ_health.items()},
                "organ_nodes": organ_nodes,
                "swimmer_registry": swimmer_registry,
                "swimmer_count": len(swimmer_registry),
                "unknown_vectors": unknown_vectors,
                "unknown_vector_count": len(unknown_vectors),
                "low_resolution_vectors": low_resolution_vectors,
                "low_resolution_vector_count": len(low_resolution_vectors),
                "weak_vectors": weak_vectors,
                "weak_vector_count": len(weak_vectors),
                "field_completeness": round(field_completeness, 6),
                "source_ledgers": [
                    "waggle_quorum.jsonl",
                    "motor_bus.jsonl",
                    "electric_field.jsonl",
                    "cuttlefish_display.jsonl",
                    "swarm_pheromone_field.py",
                    "body_brain_memory.jsonl",
                    "td_receipts.jsonl",
                    "dopamine_reward_ledger.jsonl",
                    "hippocampus/events.jsonl",
                    "reflex_arc_trace.jsonl",
                    "basal_ganglia_selections.jsonl",
                    "field_homeostasis.jsonl",
                    "field_motor_effector.jsonl",
                    "motor_pulses.jsonl",
                    "truth_continuity_events.jsonl",
                ],
                "tensor_shapes": {
                    "waggle_vector": [2],
                    "octopus_arms": [8],
                    "electric_dipole": [3],
                    "cuttlefish_skin": [4, 4],
                    "metabolic_context": [7],
                    "organ_health": [len(declared_organs)],
                    "field_memory": [len(field_memory_vector)],
                },
            },
        )
        _append_jsonl("organ_field_vector.jsonl", field_event)
        try:
            from System.swarm_unified_organ_ecology import append_organ_ecology_from_field

            append_organ_ecology_from_field(field_event, state_dir=_state, now=now)
        except Exception:
            pass

        # Swimmer Registry heartbeat — pulse all swimmers alive on each tick.
        # Swimmers know their organs, organs know their swimmers.
        # Decide → Execute → Receipt.
        try:
            from System.swimmer_registry import seed_default_swimmers
            _sr = seed_default_swimmers()
            _sr_count = _sr.heartbeat_all()
            _sr_health = _sr.health_check()
            logger.info(
                "Swimmer registry pulsed: %d swimmers, %d alive, %d organs",
                _sr_count,
                len(_sr_health.get("alive", [])),
                len(_sr.organ_summary()),
            )
        except Exception:
            pass

        # Truth Continuity (truth_continuity_events)
        from System.swarm_truth_continuity import build_event

        body_memory = _state / "body_brain_memory.jsonl"
        turn_index = 0
        if body_memory.exists():
            try:
                turn_index = len(body_memory.read_text(encoding="utf-8").splitlines())
            except Exception:
                turn_index = 0
        truth_row = build_event(
            turn_index=turn_index,
            continuity_score=1.0,
            drift_flags=[],
            evidence_refs=[
                "body_brain_memory.jsonl",
                "motor_bus.jsonl",
                "cuttlefish_display.jsonl",
                "electric_field.jsonl",
                "waggle_quorum.jsonl",
                "organ_field_vector.jsonl",
            ],
            writer="swarm_body_brain_loop:organ_heartbeat",
            note="Baseline heartbeat: body-brain tick wrote coupled organ ledgers and high-dimensional field vector; no output critic score computed.",
            truth_label="OPERATIONAL",
        )
        truth_row["tick_id"] = tick_id
        _append_jsonl("truth_continuity_events.jsonl", truth_row)
        try:
            from System.swarm_field_slo import append_state_dir_report
            append_state_dir_report(_state)
        except Exception:
            pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Initiating Swarm Physiology Loop...")
    physiology = SwarmPhysiology()
    cycle_result = physiology.body_brain_tick()
    print("Cycle complete:", json.dumps(cycle_result, indent=2))
