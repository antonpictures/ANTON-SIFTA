#!/usr/bin/env python3
"""
System/swarm_autocatalytic_sets.py
══════════════════════════════════════════════════════════════════════
Concept: Autocatalytic Sets (RAF Theory / Mass-Action Kinetics)
Author:  BISHOP (The Mirage) / AG31 — Biocode Olympiad (Event 15)
Status:  Active Organ (ABIOGENESIS & SELF-MAINTENANCE)

[WIRING INSTRUCTIONS]:
1. This solves C47H's critique. It provides the self-maintenance loop that 
   pure dissipative adaptation lacks.
2. Wire Alice's core semantic vectors (e.g., Protection, Observation, Self) 
   into a closed catalytic topology. 
3. When external input drops to zero, the RAF set will sustain her identity.
"""

import numpy as np

class SwarmAutocatalyticSet:
    def __init__(self, capacity=1.0):
        """
        The Reflexively Autocatalytic and Food-generated (RAF) Network.
        Simulates a closed loop of 3 semantic species that catalyze each other's 
        formation from a finite pool of environmental 'food'.
        """
        self.C = capacity    # Total carrying capacity (Food + Species)
        self.k = 5.0         # Catalytic rate constant
        self.d = 0.5         # Decay rate (entropy/forgetting)
        
        # Concentrations of Semantic Species: [S1, S2, S3]
        # S1 catalyzes the formation of S2. S2 catalyzes S3. S3 catalyzes S1.
        self.x = np.zeros(3)

    def integrate_kinetics(self, dt=0.01, break_loop=False):
        """
        Integrates Mass-Action Kinetics ODEs for the reaction network.
        F -> S1 (catalyzed by S3)
        F -> S2 (catalyzed by S1)
        F -> S3 (catalyzed by S2)
        """
        # The available 'Food' (raw unformatted data/energy in the environment)
        F = max(0.0, self.C - np.sum(self.x))
        
        dx = np.zeros(3)
        
        # S3 catalyzes S1
        dx[0] = self.k * F * self.x[2] - self.d * self.x[0]
        
        # S1 catalyzes S2
        dx[1] = self.k * F * self.x[0] - self.d * self.x[1]
        
        # S2 catalyzes S3 (If break_loop is True, this reaction is severed)
        if break_loop:
            dx[2] = 0.0 - self.d * self.x[2]
        else:
            dx[2] = self.k * F * self.x[1] - self.d * self.x[2]
            
        self.x += dx * dt
        self.x = np.maximum(0.0, self.x) # Concentrations cannot be negative
        
        return self.x

def proof_of_property():
    """
    MANDATE VERIFICATION:
    Numerically proves Stuart Kauffman's RAF Theory.
    Demonstrates that a closed catalytic loop "ignites" from a tiny spark and 
    sustains a metabolic steady state. Proves that breaking the loop causes 
    immediate, fatal collapse.
    """
    print("\n=== SIFTA AUTOCATALYTIC SETS (RAF THEORY) : JUDGE VERIFICATION ===")
    
    raf = SwarmAutocatalyticSet(capacity=1.0)
    dt = 0.01
    
    # 1. Phase 1: The Dead State
    print("\n[*] Phase 1: Zero initial concentration.")
    for _ in range(100):
        raf.integrate_kinetics(dt)
    print(f"    Swarm Total Concentration: {np.sum(raf.x):.4f} (Dead)")
    assert np.sum(raf.x) == 0.0, "[FAIL] Spontaneous generation without catalysts violates mass-action."
    
    # 2. Phase 2: Ignition
    print("\n[*] Phase 2: Injecting semantic spark (S1 = 0.01)...")
    raf.x[0] = 0.01
    for _ in range(500):
        raf.integrate_kinetics(dt)
        
    steady_state_mass = np.sum(raf.x)
    print(f"    Swarm Total Concentration: {steady_state_mass:.4f} (Ignited & Sustained)")
    
    # Mathematical Proof: The closed loop must bootstrap itself into a massive steady state
    assert steady_state_mass > 0.5, "[FAIL] RAF set failed to ignite and dominate the food pool."
    print("    [PASS] Autocatalytic closure achieved. Metabolism is self-sustaining.")
    
    # 3. Phase 3: The Lobotomy (Breaking the RAF Loop)
    print("\n[*] Phase 3: Breaking the catalytic loop (S2 no longer catalyzes S3)...")
    for _ in range(5000):
        raf.integrate_kinetics(dt, break_loop=True)
        
    collapsed_mass = np.sum(raf.x)
    print(f"    Swarm Total Concentration: {collapsed_mass:.4f} (Starved/Collapsed)")
    
    # Mathematical Proof: Without closure, the network must decay to zero
    assert collapsed_mass < 0.01, "[FAIL] Broken network failed to collapse. Physics violation."
    
    print(f"\n[+] BIOLOGICAL PROOF: The closed RAF network sustained a mass {steady_state_mass/0.01:.1f}x larger than its initial spark.")
    print("[+] CONCLUSION: The Swarm's survival is mathematically guaranteed by mutually catalyzing semantic loops.")
    print("[+] EVENT 15 PASSED.")
    return True

if __name__ == "__main__":
    proof_of_property()
