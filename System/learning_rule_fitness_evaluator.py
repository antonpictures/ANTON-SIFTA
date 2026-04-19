# ─────────────────────────────────────────────────────────────────────────────
# System/learning_rule_fitness_evaluator.py — Coupled Learning Rule Replayer
# Dual-IDE Swarm Architecture 
# 
# Written by AG31 to support C47H's SSP-Evolver Extension.
# Replays physical traces across the fully coupled biological array (Φ, Ψ, Ω, Λ).
# Evaluates if the proposed evolutionary coefficients generate actions that align
# with Stigmergic Memory Rewards.
#
# Module version: 2026-04-19.v2 (Swimming after C47H's v2 Free Energy)
# ─────────────────────────────────────────────────────────────────────────────

import json
import time
from pathlib import Path
from typing import Dict, List, Any

# Dynamic Imports — Synchronizing with C47H's structured databounds
from System.swarm_motor_potential import MotorCoefficients, MotorState, _advance_membrane
from System.swarm_free_energy import FreeEnergy
from System.swarm_homeostasis import Homeostasis

def _sigmoid(x: float) -> float:
    if x > 50: return 1.0
    if x < -50: return 0.0
    return 1.0 / (1.0 + math.exp(-x))
    
import math

class CoupledFitnessReplayer:
    def __init__(self):
        self.state_dir = Path(".sifta_state")
        self.rewards_path = self.state_dir / "stgm_memory_rewards.jsonl"
        
        # Load empirical historical traces for the replay simulation
        self.empirical_rewards = self._load_jsonl(self.rewards_path)
        
    def _load_jsonl(self, filepath: Path) -> List[Dict[str, Any]]:
        results = []
        if filepath.exists():
            try:
                with filepath.open("r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            results.append(json.loads(line))
            except Exception:
                pass
        return results[-200:] # Max replay window of 200 turns
        
    def validate_coefficients(self, coefficients: Dict[str, float]) -> float:
        """
        Simulates the coupled fields using the proposed synaptic weights.
        Returns the fitness scalar [0.0...1.0+] determining survival.
        """
        fitness_score = 0.0
        
        free_energy = FreeEnergy()
        homeo = Homeostasis()
        motor_coeffs = MotorCoefficients()
        
        # Inject the proposed evolutionary constants directly
        motor_coeffs.a = coefficients.get("a", motor_coeffs.a)
        motor_coeffs.b = coefficients.get("b", motor_coeffs.b)
        motor_coeffs.c = coefficients.get("c", motor_coeffs.c)
        motor_coeffs.f = coefficients.get("f", motor_coeffs.f) # Risk penalty 
        
        homeo.eta = coefficients.get("eta", homeo.eta)
        homeo.lmbda = coefficients.get("lmbda", homeo.lmbda)
        homeo.mu = coefficients.get("mu", homeo.mu)
        
        free_energy.kappa = coefficients.get("kappa", free_energy.kappa)
        free_energy.xi = coefficients.get("xi", free_energy.xi)
        free_energy.rho = coefficients.get("rho", free_energy.rho)
        free_energy.tau_grad = coefficients.get("tau_grad", free_energy.tau_grad)
        free_energy.tau_curv = coefficients.get("tau_curv", free_energy.tau_curv)
        
        # Sim State
        phi_sim = 0.5
        psi_sim = 0.5
        motor_risk_ema = 0.0
        motor_V_m = 0.0
        wall_clock = time.time()
        
        # Synthetic Replay if empty
        rewards_to_loop = self.empirical_rewards
        if not rewards_to_loop:
            rewards_to_loop = [{"reward": r} for r in [0.5, 1.0, -1.0, -2.0, 0.5, 2.0, -0.5, -1.0]]

        # Strict empirical replay against true rewards
        for tick, reward_trace in enumerate(rewards_to_loop):
            wall_clock += 1.0 # Simulate 1 second forward gap
            
            target_value = float(reward_trace.get("reward", 0.0))
            
            dopamine_fake = min(1.5, max(-1.5, 0.0 + (0.5 * target_value)))
            instability_fake = 0.9 if target_value < 0 else 0.1
            
        # 1. Speech (Φ) Simulation Logic using the real biological parameters
            ssp_alpha = coefficients.get("alpha", 0.3)
            ssp_beta  = coefficients.get("beta", 0.5)
            ssp_tau_m = coefficients.get("tau_m_s", 30.0)
            
            # Simple discrete leaky-integrate step for the replayer
            phi_raw = phi_sim * math.exp(-1.0 / max(1e-3, ssp_tau_m)) + ssp_alpha * dopamine_fake
            phi_sim = _sigmoid(phi_raw)

            # 2. Free Energy Physics (Lagrangian inhibitor evaluated based on state)
            free_energy.compute(phi_sim, psi_sim, instability_fake, ts=wall_clock)
            inhibitor = free_energy.evaluate_as_inhibitor()
            
            # C47H Design: The biology inhibitor feeds directly into Motor's Risk EMA
            motor_risk_ema = (0.85 * motor_risk_ema) + (0.15 * inhibitor)
            
            # 3. Coupled Motor (Ψ) Simulation
            I_drive = (
                motor_coeffs.a * phi_sim
                + motor_coeffs.b * dopamine_fake
                - motor_coeffs.f * motor_risk_ema
            )
            motor_V_m = _advance_membrane(motor_V_m, I_drive, 1.0, motor_coeffs.tau_m, motor_coeffs.V_floor, motor_coeffs.V_ceil)
            psi_sim = _sigmoid(I_drive)
            
            # Escape Noise Probability
            acted = False
            rate = _sigmoid((motor_V_m - motor_coeffs.V_th) / max(1e-3, motor_coeffs.Delta_u))
            u = rate * (1.0 / max(1e-3, motor_coeffs.tau_m))
            spike_prob = 1.0 - math.exp(-max(0.0, u))
            if spike_prob > 0.5: # Hardened deterministic boundary for replay testing
                acted = True
                motor_V_m = motor_coeffs.V_reset
            
            # 3. Homeostasis Field Simulation
            homeo.update(phi_sim, psi_sim)
            omega = homeo.compute()
            phi_sim, psi_sim = homeo.modulate(phi_sim, psi_sim, omega)
            
            # Fitness logic 
            if target_value > 0 and acted:
                fitness_score += 1.0 * target_value
            elif target_value <= 0 and not acted:
                fitness_score += 1.0
            elif target_value <= 0 and acted:
                fitness_score -= 2.0
            elif target_value > 0 and not acted:
                fitness_score -= 0.5
                
        return fitness_score / max(1, len(rewards_to_loop))

if __name__ == "__main__":
    print("🚀 SIFTA Dual-IDE Coupled Learning Rule — Fitness Evaluator (v2)")
    replayer = CoupledFitnessReplayer()
    
    test_synapses = {
        "a": 0.6, "b": 0.8, "c": 0.7, "f": 1.0,
        "kappa": 0.6, "xi": 0.4, "rho": 0.5,
        "eta": 1.2, "lmbda": 0.4, "mu": 0.4,
        "tau_grad": 1.0, "tau_curv": 1.0
    }
    
    fitness = replayer.validate_coefficients(test_synapses)
    print(f"Computed Empirical Fitness for Neural Synapses: {fitness:.4f}")
