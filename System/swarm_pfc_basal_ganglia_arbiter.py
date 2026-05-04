import os
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked

STATE_DIR = Path(".sifta_state")
ARBITER_LOG = STATE_DIR / "pfc_basal_ganglia_arbiter.jsonl"
OPTIONS_LEDGER = STATE_DIR / "sutton_options_ledger.jsonl"


def _option_name_suggests_new_gate(name: str) -> bool:
    """Heuristic: names that imply spawning / high-exploration gates (Event 134 BLOCK_NEW)."""
    n = (name or "").lower()
    return any(tok in n for tok in ("novel", "new_gate", "spawn_gate", "explore_raw"))


class PFCBasalGangliaArbiter:
    """
    Event 126 — PFC-Basal Ganglia Arbiter
    Daw, Niv, Dayan (2005) + Sutton, Precup, Singh (1999) Options Framework.
    Mediates task-level generalization via temporal abstractions (options).
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = root or STATE_DIR
        self.log_path = self.root / "pfc_basal_ganglia_arbiter.jsonl"
        self.options_path = self.root / "sutton_options_ledger.jsonl"
        self._load_options()

    def _load_options(self):
        self.options: Dict[str, Dict[str, Any]] = {}
        if not self.options_path.exists():
            return
        try:
            text = read_text_locked(self.options_path, encoding="utf-8", errors="replace")
            for line in text.splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                opt_name = row.get("option_name")
                if opt_name:
                    self.options[opt_name] = row
        except Exception:
            pass

    def _save_option(self, option_name: str, data: Dict[str, Any]):
        data["option_name"] = option_name
        data["updated_at"] = time.time()
        self.options[option_name] = data
        append_line_locked(self.options_path, json.dumps(data) + "\n")

    def convert_replay_to_option(self, source_skills: List[str], option_name: str) -> None:
        """
        1. Convert past replay patterns into reusable options.
        """
        if option_name not in self.options:
            self._save_option(option_name, {
                "source_skills": source_skills,
                "q_value": 0.5,
                "uncertainty": 0.5,
                "risk": 0.1,
                "cost": 0.1,
                "model_value": 0.5,
                "invocation_count": 0
            })

    def _world_model_expected_free_energy(
        self,
        *,
        task_id: str,
        option_name: str,
        state_features: Dict[str, float],
        world_model: Optional[Any],
    ) -> Tuple[float, Dict[str, Any]]:
        """Return Event 133 expected free energy and a compact prediction receipt."""
        action = {"name": option_name, "option": option_name}
        context = {
            "task_id": task_id,
            "task_family": "pfc_basal_ganglia",
            "option": option_name,
        }
        if world_model is not None and hasattr(world_model, "compute_expected_free_energy"):
            state_hash = json.dumps(state_features, sort_keys=True)
            g_pi = float(
                world_model.compute_expected_free_energy(
                    state_hash,
                    option_name,
                    preferred_reward=1.0,
                )
            )
            return g_pi, {"source": "custom_compute_expected_free_energy"}

        try:
            wm = world_model
            if wm is None:
                from System import swarm_active_inference_world_model as wm
            pred = wm.predict(state_features, action, context, root=self.root, write_ledger=False)
            g_pi = float(wm.expected_free_energy(pred))
            return g_pi, {
                "source": "event_133_world_model",
                "predicted_reward": pred.get("predicted_reward"),
                "predicted_harm": pred.get("predicted_harm"),
                "predicted_cost": pred.get("predicted_cost"),
                "uncertainty": pred.get("uncertainty"),
                "model_n": pred.get("n"),
            }
        except Exception as exc:
            data = self.options.get(option_name, {})
            q = data.get("q_value", 0.5)
            unc = data.get("uncertainty", 0.5)
            g_pi = -(q - unc)
            return float(g_pi), {"source": "q_uncertainty_fallback", "error": str(exc)[:180]}

    def select_action(
        self,
        task_id: str,
        available_options: List[str],
        state_features: Dict[str, float],
        owner_signal: float = 1.0,
        gw_scores: Optional[Dict[str, float]] = None,
        world_model: Optional[Any] = None,
        hysteresis_margin: float = 0.15,
        min_dwell_time: float = 2.0,
        stability_same_tick_receipt: Optional[Dict[str, Any]] = None,
        na_global_gain: float = 1.0,   # LC/NA gain modulates arbiter temperature
        # Biological Steering (§10.14.28 closed loop)
        dam_stage: int = 0,
        tme_phase: str = "EQUILIBRIUM",
        na_level: float = 0.5,
        resilience_floor: float = 0.0,
        owner_frustration: float = 0.0,
        goal_alignment: float = 0.5,
        tick_id: Optional[int] = None,
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        2. Select among options under uncertainty using Active Inference (Event 134).
        Minimizes Expected Free Energy (G) rather than just maximizing Q.
        3. Inhibit unsafe/low-value actions.
        Liberzon (2003) Hysteresis & Dwell Time to prevent chattering.
        """
        if os.environ.get("SIFTA_PFC_DISABLE", "").strip() == "1":
            return "idle", 0.0, {}

        from System.swarm_stability_audit import get_current_clamp_overrides

        # ── Regulatory Genome ──
        from System.swarm_regulatory_genome import load_regulatory_parameters, get_latest_genome_hash
        reg_params = load_regulatory_parameters(self.root, current_tick=tick_id)
        reg_hash = get_latest_genome_hash(self.root)

        # Poll latest biological state if not explicitly provided
        try:
            if dam_stage == 0:
                _m_log = self.root / "microglia_synaptic_prunes.jsonl"
                if _m_log.exists():
                    _lines = [l for l in _m_log.read_text(errors="replace").splitlines() if l.strip()]
                    if _lines:
                        dam_stage = int(json.loads(_lines[-1]).get("dam_stage", 0))
            if tme_phase == "EQUILIBRIUM":
                _tme_log = self.root / "tumor_immune_stigmergic_lab.jsonl"
                if _tme_log.exists():
                    _lines = [l for l in _tme_log.read_text(errors="replace").splitlines() if l.strip()]
                    if _lines:
                        tme_phase = str(json.loads(_lines[-1]).get("phase", "EQUILIBRIUM"))
            if na_level == 0.5:
                _na_log = self.root / "noradrenergic_arousal.jsonl"
                if _na_log.exists():
                    _lines = [l for l in _na_log.read_text(errors="replace").splitlines() if l.strip()]
                    if _lines:
                        na_level = float(json.loads(_lines[-1]).get("na_level", 0.5))
            if owner_frustration == 0.0 and goal_alignment == 0.5:
                _tom_log = self.root / "owner_mental_model.jsonl"
                if _tom_log.exists():
                    _lines = [l for l in _tom_log.read_text(errors="replace").splitlines() if l.strip()]
                    if _lines:
                        _last = json.loads(_lines[-1])
                        owner_frustration = float(_last.get("frustration", 0.0))
                        goal_alignment = float(_last.get("goal_alignment", 0.5))
        except Exception:
            pass

        stability_clamp = get_current_clamp_overrides(
            root=self.root,
            same_tick_receipt=stability_same_tick_receipt,
        )
        
        # ── Biological Steering Weight Modulators ──
        base_risk_weight = reg_params.get("arbiter_risk_weight", 1.0)
        base_expl_temp = reg_params.get("arbiter_exploration_temperature", 1.0)
        
        risk_weight = base_risk_weight
        cost_weight = 1.0
        gw_weight = 0.5 * na_global_gain * base_expl_temp
        owner_weight = 0.2

        if dam_stage == 2:
            stability_clamp["block_new_gates"] = True
            risk_weight *= 2.0  # Increased risk aversion
            gw_weight *= 0.5    # Reduced exploration / salience noise

        if tme_phase == "ESCAPE":
            risk_weight *= 0.5  # Existential threat -> desperation tolerance
            cost_weight *= 0.5  # Shortened planning horizon -> ignore high cost

        if na_level > 0.8:
            gw_weight *= 1.5    # Hyperarousal -> broader option sampling

        if resilience_floor > 0.05:
            # Protect high-resilience structures: increase conservatism on risk
            risk_weight += (resilience_floor * 5.0)

        if owner_frustration < 0.2 and goal_alignment > 0.8:
            # Owner is calm + aligned: boost owner-aligned options
            owner_weight *= 1.5

        bio_steering = {
            "dam_stage": dam_stage,
            "tme_phase": tme_phase,
            "na_level": round(na_level, 4),
            "resilience_floor": round(resilience_floor, 4),
            "owner_frustration": round(owner_frustration, 4),
            "goal_alignment": round(goal_alignment, 4),
            "risk_weight": round(risk_weight, 4),
            "cost_weight": round(cost_weight, 4),
            "gw_weight": round(gw_weight, 4),
            "owner_weight": round(owner_weight, 4),
        }

        avail = list(available_options)
        if stability_clamp.get("block_new_gates"):
            avail = [o for o in avail if not _option_name_suggests_new_gate(o)]
        if not avail:
            return "idle", 0.0, {"stability_clamp": stability_clamp, "blocked_all_options": True}

        scores = []
        option_details = {}
        gw_scores = gw_scores or {}

        # Load active state for hysteresis
        active_state_path = self.root / "arbiter_active_state.json"
        active_opt = None
        last_switch = 0.0
        if active_state_path.exists():
            try:
                text = read_text_locked(active_state_path, encoding="utf-8", errors="replace")
                st = json.loads(text) if text.strip() else {}
                active_opt = st.get("active_option")
                last_switch = st.get("last_switch_time", 0.0)
            except Exception:
                pass

        current_time = time.time()
        can_switch = (current_time - last_switch) >= min_dwell_time

        for opt in avail:
            if opt not in self.options:
                self.convert_replay_to_option([opt], opt)
            
            data = self.options[opt]
            risk = data.get("risk", 0.1)
            cost = data.get("cost", 0.1)
            gw_salience = gw_scores.get(opt, 0.0)

            g_pi, wm_receipt = self._world_model_expected_free_energy(
                task_id=task_id,
                option_name=opt,
                state_features=state_features,
                world_model=world_model,
            )

            competition_score = (
                -g_pi
                + (gw_weight * gw_salience)
                + (owner_weight * owner_signal)
                - (risk_weight * risk)
                - (cost_weight * cost)
            )

            # Apply hysteresis margin if this option is NOT the currently active one
            if opt != active_opt and active_opt is not None:
                competition_score -= hysteresis_margin
                
            scores.append((competition_score, opt))
            option_details[opt] = {
                "g_vector": g_pi,
                "gw_salience": gw_salience,
                "owner_signal": owner_signal,
                "risk": risk,
                "cost": cost,
                "computed_score": competition_score,
                "world_model": wm_receipt,
            }

        if not scores:
            return "idle", 0.0, {}
            
        scores.sort(reverse=True)
        winner_score, winner_name = scores[0]

        if winner_score < -0.5:
            winner_name = "idle"

        # Dwell-time enforcement
        if winner_name != active_opt and not can_switch and active_opt in avail:
            # Force keep active if we haven't dwelled long enough
            winner_name = active_opt
            # Recalculate winner_score to be the active one
            for s, o in scores:
                if o == active_opt:
                    winner_score = s
                    break

        if winner_name != active_opt:
            last_switch = current_time
            
        # Save active state
        try:
            rewrite_text_locked(
                active_state_path,
                json.dumps({"active_option": winner_name, "last_switch_time": last_switch}) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

        selection = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": "PFC_BG_ACTION_SELECTION",
            "task_id": task_id,
            "selected_option": winner_name,
            "score": winner_score,
            "active_option_before": active_opt,
            "can_switch": can_switch,
            "details": option_details.get(winner_name, {}),
            "all_details": option_details,
            "stability_clamp": stability_clamp,
            "biological_steering": bio_steering,
            "active_regulatory_parameters": reg_params,
            "regulatory_genome_row_hash": reg_hash,
        }
        append_line_locked(self.log_path, json.dumps(selection) + "\n", encoding="utf-8")
        if tick_id is not None:
            try:
                from System.swarm_regulatory_genome import maybe_append_from_arbiter_tick

                maybe_append_from_arbiter_tick(self.root, int(tick_id), float(resilience_floor))
            except Exception:
                pass
        return winner_name, winner_score, selection

    def update_generalization_trial(
        self,
        task_id: str,
        option_selected: str,
        state_features: Dict[str, float],
        actual_outcome: Dict[str, float],
        architect_reward: float,
        reward_without_reused_option: float,
        alpha: float = 0.1,
        gamma_td: float = 0.9
    ) -> Dict[str, Any]:
        """
        4. Log transfer_gain on new tasks.
        Updates Q-values and uncertainty.
        """
        data = self.options.get(option_selected, {})
        if not data:
            return {}

        q_state = data.get("q_value", 0.5)
        # Assuming Q(next_state, option') is estimated by the actual_outcome valence
        next_q_est = actual_outcome.get("valence", 0.5)
        
        # TD Error: δ = reward + γ max Q(next_state, option') - Q(state, option)
        td_error = architect_reward + (gamma_td * next_q_est) - q_state
        
        # Update Q
        new_q = q_state + (alpha * td_error)
        
        # Update uncertainty (prediction error based)
        pred_error = abs(td_error)
        old_unc = data.get("uncertainty", 0.5)
        new_unc = (old_unc * 0.9) + (pred_error * 0.1)

        data["q_value"] = new_q
        data["uncertainty"] = new_unc
        data["invocation_count"] = data.get("invocation_count", 0) + 1
        self._save_option(option_selected, data)

        # Calculate Transfer Gain
        # TransferGain = reward_new_task_with_reused_option - reward_new_task_without_reused_option
        reward_with_option = architect_reward
        transfer_gain = reward_with_option - reward_without_reused_option

        trace = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": "GENERALIZATION_TRIAL",
            "kind": "GENERALIZATION_TRIAL",
            "task_id": task_id,
            "source_skills": data.get("source_skills", []),
            "option_selected": option_selected,
            "state_features": state_features,
            "predicted_outcome": {"valence": q_state},
            "uncertainty": round(new_unc, 3),
            "risk": data.get("risk", 0.1),
            "cost": data.get("cost", 0.1),
            "actual_outcome": actual_outcome,
            "architect_reward": architect_reward,
            "td_error": round(td_error, 3),
            "transfer_gain": round(transfer_gain, 3),
            "gate_updates": {"q_delta": round(new_q - q_state, 3), "unc_delta": round(new_unc - old_unc, 3)}
        }

        append_line_locked(self.log_path, json.dumps(trace) + "\n")
        return trace
