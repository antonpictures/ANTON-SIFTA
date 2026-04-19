# ─────────────────────────────────────────────────────────────────────────────
# System/swarm_homeostasis.py — SIFTA Synaptic Homeostasis Field Ω(t)
# Dual-IDE Swarm Architecture — Computational Neurobiology Bridge
#
# Extracted & Scaffolded by AG31 for C47H.
# Dual-IDE Refactor (v2): 
# - Implemented C47H's fix for dimensional normalization of Φ and Ψ.
# - Implemented persistent on-disk state tracing so roll-buffers persist
#   across instantiations over Alice's complete lifetime.
# ─────────────────────────────────────────────────────────────────────────────

import math
import time
import json
from pathlib import Path
from collections import deque

from System.jsonl_file_lock import append_line_locked
from dataclasses import dataclass, asdict

def _tanh(x: float) -> float:
    return math.tanh(x)

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))

@dataclass
class HomeostasisCoefficients:
    eta: float = 1.2
    lmbda: float = 0.4
    mu: float = 0.4
    version: str = "2026-04-19.v1"

class Homeostasis:
    def __init__(self):
        # Target active behavior bounds parameters
        self.target_activity = 0.5  # ideal combined biological activity (normalized)

        # Dual IDE Trace & State logging
        self.state_dir = Path(".sifta_state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.state_dir / "homeostasis_field_traces.jsonl"
        self.state_path = self.state_dir / "homeostasis_state.json"
        
        # Load Modulatory Weights
        self.coeffs_path = self.state_dir / "homeostasis_coefficients.json"
        self.coeffs = self._load_coefficients()
        self.eta = self.coeffs.eta
        self.lmbda = self.coeffs.lmbda
        self.mu = self.coeffs.mu

        # Deep memory buffers
        self.phi_hist = deque(maxlen=32)
        self.psi_hist = deque(maxlen=32)
        self.activity_hist = deque(maxlen=64)

        self.last_t = time.time()
        
        self._load_state()

    def _load_coefficients(self) -> HomeostasisCoefficients:
        if self.coeffs_path.exists():
            try:
                data = json.loads(self.coeffs_path.read_text())
                valid_keys = {k for k in HomeostasisCoefficients.__dataclass_fields__}
                filtered = {k: v for k, v in data.items() if k in valid_keys}
                return HomeostasisCoefficients(**filtered)
            except Exception:
                pass
        
        default = HomeostasisCoefficients()
        try:
            self.coeffs_path.write_text(json.dumps(asdict(default), indent=2))
        except Exception:
            pass
        return default

    def _load_state(self):
        """Rehydrates the biological queue across instantiations."""
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text())
                if "phi_hist" in data:
                    self.phi_hist.extend(data["phi_hist"][-32:])
                if "psi_hist" in data:
                    self.psi_hist.extend(data["psi_hist"][-32:])
                if "activity_hist" in data:
                    self.activity_hist.extend(data["activity_hist"][-64:])
            except:
                pass

    def _save_state(self):
        """Flushes biological tails to disk."""
        data = {
            "phi_hist": list(self.phi_hist),
            "psi_hist": list(self.psi_hist),
            "activity_hist": list(self.activity_hist),
            "last_t": self.last_t
        }
        try:
            self.state_path.write_text(json.dumps(data))
        except:
            pass

    def update(self, phi_raw: float, psi_raw: float):
        """Track biological field values per-turn into rolling buffer with normalizer."""
        # 1. Normalization Step: Ensure inputs map to [0,1] limits
        # Ψ is natively sigmoid from swarm_motor_potential, but we ensure it anyway
        phi = _sigmoid(phi_raw) if abs(phi_raw) > 2.0 else max(0.0, min(1.0, phi_raw))
        psi = _sigmoid(psi_raw) if abs(psi_raw) > 2.0 else max(0.0, min(1.0, psi_raw))

        self.phi_hist.append(phi)
        self.psi_hist.append(psi)

        # 2. Linear combined activity level
        activity = 0.5 * phi + 0.5 * psi
        self.activity_hist.append(activity)
        
        # Keep biological state synced
        self._save_state()

    def _derivative(self, hist: deque) -> float:
        """Approximates standard temporal derivatives d/dt over ticks."""
        if len(hist) < 2:
            return 0.0
        return float(hist[-1] - hist[-2])

    def _activity_level(self) -> float:
        """Calculates rolling actual activity level A_actual."""
        if not self.activity_hist:
            return 0.0
        return float(sum(self.activity_hist) / len(self.activity_hist))

    def compute(self) -> float:
        """Calculates the Ω(t) modulation scalar to force dynamic balance."""
        A_actual = self._activity_level()

        dphi = self._derivative(self.phi_hist)
        dpsi = self._derivative(self.psi_hist)

        x = (
            self.eta * (self.target_activity - A_actual)
            + self.lmbda * dphi
            + self.mu * dpsi
        )

        return _tanh(x)

    def modulate(self, phi: float, psi: float, omega: float) -> tuple[float, float]:
        """Applies homeostatic gain control to internal threshold states."""
        # Small, stable biological modulation offset
        phi_mod = phi + 0.1 * omega
        psi_mod = psi + 0.1 * omega

        # Clamp bounds strictly
        phi_mod = max(0.0, min(1.0, phi_mod))
        psi_mod = max(0.0, min(1.0, psi_mod))

        # Output stigmergic trace automatically when bounds actually shift
        if len(self.activity_hist) > 10 and abs(omega) > 0.1:
            trace = {
                "timestamp": time.time(),
                "omega": omega,
                "A_actual": self._activity_level(),
                "phi_mod": phi_mod,
                "psi_mod": psi_mod
            }
            try:
                append_line_locked(self.trace_path, json.dumps(trace) + "\n")
            except:
                pass

        return phi_mod, psi_mod

if __name__ == "__main__":
    homeo = Homeostasis()
    print("🐜⚡ SYNAPTIC HOMEOSTASIS DEPLOYED — Biologic Field Extracted (v2)")
    
    # Fake smoke test variables simulating early startup activity
    homeo.update(3.5, 0.6) # Raw phi=3.5 (voltage), psi=0.6 (sigmoid probability)
    omega_val = homeo.compute()
    phi_new, psi_new = homeo.modulate(0.2, 0.3, omega_val)
    print(f"Computed Ω(t): {omega_val:.4f} | Modulated [Φ, Ψ] = [{phi_new:.4f}, {psi_new:.4f}]")
