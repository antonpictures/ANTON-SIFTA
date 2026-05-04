import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from System.jsonl_file_lock import append_line_locked, read_text_locked, rewrite_text_locked
from System.swarm_persistent_owner_history import state_dir


def _clamp(value: Any, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        f = lo
    return min(hi, max(lo, f))


class AstrocyteGlialModulator:
    """
    Event 135: Astrocyte & Glial Resource Modulator
    Manages the synaptic environment by dynamically modulating learning rates, 
    epistemic exploration weights, and caloric/compute budget based on global surprise (stress).
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = state_dir(root)
        self.state_file = self.root / "astrocyte_glial_state.json"
        self.log_file = self.root / "astrocyte_modulation_log.jsonl"
        
        self.base_lr = 0.1
        self.base_epistemic_weight = 0.25
        self.base_compute_budget = 1000 # Abstract STGM or calorie limit
        
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                content = read_text_locked(self.state_file, encoding="utf-8")
                if content.strip():
                    return json.loads(content)
            except Exception:
                pass
        return {
            "global_surprise_ema": 0.0,
            "metabolic_heat": 0.0,
            "current_lr": self.base_lr,
            "current_epistemic_weight": self.base_epistemic_weight,
            "current_compute_budget": self.base_compute_budget
        }

    def _save_state(self) -> None:
        rewrite_text_locked(
            self.state_file,
            json.dumps(self.state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def observe_global_state(
        self,
        new_surprise: float,
        compute_expended: float,
        *,
        lr_ceiling: Optional[float] = None,
        exploration_bias_cap: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Ingest the latest prediction error (surprise) from the World Model 
        and the compute expended. Astrocyte modulates the parameters globally.
        """
        surprise = max(0.0, float(new_surprise))
        compute = max(0.0, float(compute_expended))
        if os.environ.get("SIFTA_ASTROCYTE_DISABLE", "").strip() == "1":
            return {
                "ts": time.time(),
                "trace_id": str(uuid.uuid4()),
                "truth_label": "ASTROCYTE_MODULATION",
                "kind": "ASTROCYTE_MODULATION",
                "disabled": True,
                "global_surprise": round(self.state["global_surprise_ema"], 4),
                "metabolic_heat": round(self.state["metabolic_heat"], 4),
                "modulated_lr": round(self.state["current_lr"], 4),
                "modulated_epistemic_weight": round(self.state["current_epistemic_weight"], 4),
                "modulated_budget": round(self.state["current_compute_budget"], 4),
            }

        # Update EMA of Global Surprise
        alpha = 0.2
        ema = (self.state["global_surprise_ema"] * (1 - alpha)) + (surprise * alpha)
        self.state["global_surprise_ema"] = ema
        
        # Update metabolic heat (stress)
        self.state["metabolic_heat"] += compute
        # Cooling
        self.state["metabolic_heat"] = max(0.0, self.state["metabolic_heat"] - 50.0)
        
        # Modulation Logic (Astrocytic Ca2+ wave equivalent)
        # 1. High surprise = learning rate spikes to rapidly integrate new reality.
        #    If surprise is low, LR drops to prevent catastrophic forgetting.
        surprise_factor = min(2.0, max(0.5, 1.0 + ema))
        new_lr = self.base_lr * surprise_factor
        
        # 2. High surprise = epistemic exploration weight drops (exploit to survive).
        #    Low surprise = epistemic weight rises (safe to explore).
        epistemic_factor = 1.0 / max(0.5, surprise_factor)
        new_epistemic = self.base_epistemic_weight * epistemic_factor
        
        # 3. High metabolic heat = compute budget squeezed.
        heat_factor = min(1.0, 1000.0 / max(1.0, self.state["metabolic_heat"]))
        new_budget = self.base_compute_budget * heat_factor

        if lr_ceiling is not None:
            try:
                new_lr = min(new_lr, float(lr_ceiling))
            except (TypeError, ValueError):
                pass
        if exploration_bias_cap is not None:
            try:
                new_epistemic = min(new_epistemic, float(exploration_bias_cap))
            except (TypeError, ValueError):
                pass

        self.state["current_lr"] = new_lr
        self.state["current_epistemic_weight"] = new_epistemic
        self.state["current_compute_budget"] = new_budget
        
        self._save_state()
        
        trace = {
            "ts": time.time(),
            "trace_id": str(uuid.uuid4()),
            "truth_label": "ASTROCYTE_MODULATION",
            "kind": "ASTROCYTE_MODULATION",
            "input_surprise": round(surprise, 4),
            "input_compute_expended": round(compute, 4),
            "global_surprise": round(ema, 4),
            "metabolic_heat": round(self.state["metabolic_heat"], 4),
            "modulated_lr": round(new_lr, 4),
            "modulated_epistemic_weight": round(new_epistemic, 4),
            "modulated_budget": round(new_budget, 4),
            "disabled": False,
            "stability_lr_ceiling_applied": lr_ceiling,
            "stability_exploration_bias_cap_applied": exploration_bias_cap,
        }
        append_line_locked(self.log_file, json.dumps(trace) + "\n", encoding="utf-8")
        return trace

    def get_current_parameters(self) -> Dict[str, float]:
        return {
            "lr": self.state["current_lr"],
            "epistemic_weight": self.state["current_epistemic_weight"],
            "budget": self.state["current_compute_budget"]
        }

    def preferences_patch(self) -> Dict[str, float]:
        """Event 133 preference overrides for active inference scoring."""
        return {
            "uncertainty_weight": self.state["current_epistemic_weight"],
            "cost_weight": 0.25 + _clamp(self.state["metabolic_heat"] / 2000.0, 0.0, 0.75),
        }

    def summary_for_prompt(self) -> str:
        params = self.get_current_parameters()
        return (
            "ASTROCYTE GLIAL MODULATOR (Event 135): "
            f"lr={params['lr']:.3f}, epistemic_weight={params['epistemic_weight']:.3f}, "
            f"compute_budget={params['budget']:.1f}"
        )
