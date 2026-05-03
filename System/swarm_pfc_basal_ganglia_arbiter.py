import json
import time
import uuid
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

STATE_DIR = Path(".sifta_state")
ARBITER_LOG = STATE_DIR / "pfc_basal_ganglia_arbiter.jsonl"
OPTIONS_LEDGER = STATE_DIR / "sutton_options_ledger.jsonl"

def append_line_locked(path: Path, text: str, encoding: str = "utf-8"):
    # Fallback/stub if System.jsonl_file_lock unavailable
    try:
        from System.jsonl_file_lock import append_line_locked as append_locked
        append_locked(path, text, encoding=encoding)
    except ImportError:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(text)

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
            with open(self.options_path, "r", encoding="utf-8") as f:
                for line in f:
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

    def select_action(
        self,
        task_id: str,
        available_options: List[str],
        state_features: Dict[str, float],
        lambd: float = 0.4,
        beta: float = 1.0,
        gamma: float = 0.5,
        kappa: float = 1.0
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        2. Select among options under uncertainty.
        3. Inhibit unsafe/low-value actions.
        """
        if os.environ.get("SIFTA_PFC_DISABLE", "").strip() == "1":
            return "idle", 0.0, {}

        scores = []
        option_details = {}
        for opt in available_options:
            if opt not in self.options:
                self.convert_replay_to_option([opt], opt)
            
            data = self.options[opt]
            q = data.get("q_value", 0.5)
            model_val = data.get("model_value", 0.5)
            unc = data.get("uncertainty", 0.5)
            risk = data.get("risk", 0.1)
            cost = data.get("cost", 0.1)

            # Daw/Sutton Equation
            score = q + (lambd * model_val) - (beta * unc) - (gamma * risk) - (kappa * cost)
            scores.append((score, opt))
            option_details[opt] = {
                "q_value": q,
                "model_value": model_val,
                "uncertainty": unc,
                "risk": risk,
                "cost": cost,
                "computed_score": score
            }

        # Winner-take-all (Basal Ganglia lateral inhibition)
        if not scores:
            return "idle", 0.0, {}
            
        scores.sort(reverse=True)
        winner_score, winner_name = scores[0]

        # Inhibit if net score is negative
        if winner_score < 0:
            winner_name = "idle"
            winner_score = 0.0

        selection = {
            "ts": time.time(),
            "task_id": task_id,
            "selected_option": winner_name,
            "score": winner_score,
            "details": option_details.get(winner_name, {})
        }
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
        new_unc = (data.get("uncertainty", 0.5) * 0.9) + (pred_error * 0.1)

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
            "gate_updates": {"q_delta": round(new_q - q_state, 3), "unc_delta": round(new_unc - data.get("uncertainty", 0.5), 3)}
        }

        append_line_locked(self.log_path, json.dumps(trace) + "\n")
        return trace
