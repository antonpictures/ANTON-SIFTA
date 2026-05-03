import json
import math
import time
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from System.jsonl_file_lock import append_line_locked, read_text_locked
except ImportError:
    def read_text_locked(path: Path, **kwargs) -> str:
        if not path.exists(): return ""
        return path.read_text(**kwargs)
    
    def append_line_locked(path: Path, line: str, **kwargs) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", **kwargs) as f:
            f.write(line)

class AstrocyteGlialModulator:
    """
    Event 135: Astrocyte & Glial Resource Modulator
    Manages the synaptic environment by dynamically modulating learning rates, 
    epistemic exploration weights, and caloric/compute budget based on global surprise (stress).
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = root or Path(".sifta_state")
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
        try:
            from System.jsonl_file_lock import _lock, _unlock
            with open(self.state_file, "w", encoding="utf-8") as f:
                _lock(f.fileno())
                json.dump(self.state, f, indent=2)
                _unlock(f.fileno())
        except ImportError:
            self.state_file.write_text(json.dumps(self.state, indent=2))

    def observe_global_state(self, new_surprise: float, compute_expended: float) -> Dict[str, Any]:
        """
        Ingest the latest prediction error (surprise) from the World Model 
        and the compute expended. Astrocyte modulates the parameters globally.
        """
        # Update EMA of Global Surprise
        alpha = 0.2
        ema = (self.state["global_surprise_ema"] * (1 - alpha)) + (new_surprise * alpha)
        self.state["global_surprise_ema"] = ema
        
        # Update metabolic heat (stress)
        self.state["metabolic_heat"] += compute_expended
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

        self.state["current_lr"] = new_lr
        self.state["current_epistemic_weight"] = new_epistemic
        self.state["current_compute_budget"] = new_budget
        
        self._save_state()
        
        trace = {
            "ts": time.time(),
            "kind": "ASTROCYTE_MODULATION",
            "global_surprise": round(ema, 4),
            "metabolic_heat": round(self.state["metabolic_heat"], 4),
            "modulated_lr": round(new_lr, 4),
            "modulated_epistemic_weight": round(new_epistemic, 4),
            "modulated_budget": round(new_budget, 4)
        }
        append_line_locked(self.log_file, json.dumps(trace) + "\n", encoding="utf-8")
        return trace

    def get_current_parameters(self) -> Dict[str, float]:
        return {
            "lr": self.state["current_lr"],
            "epistemic_weight": self.state["current_epistemic_weight"],
            "budget": self.state["current_compute_budget"]
        }
