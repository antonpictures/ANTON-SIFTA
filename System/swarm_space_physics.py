#!/usr/bin/env python3
"""
swarm_space_physics.py — Astrophysical execution engine
═══════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Implements true biological path-graph traversal inspired by astrophysical phenomena.
1. Cosmic Ray Spallation: Extreme energy generates short-lived execution Swimmers (Muons)
   that drop geological memory (Isotopes) directly into the Stigmergic Field.
2. Magnetic Reconnection: Path-Graph tension is logged sequentially. Infinite loop
   traversals snap and auto-quarantine, forcing systemic expulsion out of dead-loops.
"""

import math
import random
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

from System.swarm_potential_field import SwarmPotentialField

MODULE_VERSION = "2026-04-18.v1"


class FluxLattice:
    """
    Tracks topological stress (flux twist) on edges between paths.
    """
    def __init__(self, decay_rate: float = 0.95):
        # Maps an ascending string edge (A->B or B->A normalized) to tension.
        self.tension: Dict[Tuple[str, str], float] = defaultdict(float)
        self.decay_rate = decay_rate

    def _normalize_edge(self, p1: Path, p2: Path) -> Tuple[str, str]:
        s1, s2 = str(p1), str(p2)
        return (s1, s2) if s1 < s2 else (s2, s1)

    def inject_twist(self, p1: Path, p2: Path, force: float = 1.0):
        edge = self._normalize_edge(p1, p2)
        self.tension[edge] += force

    def step(self):
        keys_to_del = []
        for edge in list(self.tension.keys()):
            self.tension[edge] *= self.decay_rate
            if self.tension[edge] < 0.01:
                keys_to_del.append(edge)
        for k in keys_to_del:
            del self.tension[k]

    def reset_edge(self, p1: Path, p2: Path):
        edge = self._normalize_edge(p1, p2)
        if edge in self.tension:
            del self.tension[edge]


class MuonSwimmer:
    """
    Transient, high-speed execution agent. 
    It holds NO internal memory. It acts immediately and drops permanent isotopes.
    """
    def __init__(self, start_path: Path, energy: float):
        self.path = Path(start_path).resolve()
        self.energy = energy
        self.alive = True

    def move(self, field: SwarmPotentialField, lattice: FluxLattice):
        if not self.alive:
            return

        # Burn energy to act
        self.energy -= 1.0
        if self.energy <= 0:
            self.alive = False
            return

        # 1. Action: The Muon determines descent direction using the geological Field
        next_path = field.gradient_descent(self.path)
        
        # If it's forced to remain in place due to complete topographical isolation
        if next_path == self.path:
            self.alive = False
            return
            
        # 2. Tension: The movement generates braided stress
        lattice.inject_twist(self.path, next_path, force=1.0)

        # 3. Spallation Isotope: The muon drops massive structural stigmergy on the destination
        # to guarantee future biological tracing.
        # C47H BUG-26 fix: was field.step() which both persists AND decays the
        # ENTIRE field — so 100 muon moves caused 100 disk writes (BUG-13
        # regression) and aged every other heat trace by 0.98^100 ≈ 0.13×.
        # commit() flushes I/O without touching diffusion/decay; the global
        # heartbeat owns step() scheduling, not per-muon motion.
        field.write_potential(next_path, 2.0)
        field.commit()

        self.path = next_path


class MagneticReconnectionEngine:
    """
    Monitors graph tension and forces explosive Reconnection when limits are breached.
    """
    def __init__(self, crack_threshold: float = 10.0):
        self.threshold = crack_threshold

    def cycle(self, field: SwarmPotentialField, lattice: FluxLattice, swimmers: List[MuonSwimmer]) -> bool:
        """
        Returns True if a reconnection event breached the topology.
        """
        breached_edges = []
        for (u, v), tension in lattice.tension.items():
            if tension > self.threshold:
                breached_edges.append((Path(u), Path(v)))
                
        if not breached_edges:
            return False
            
        # Trigger Magnetic Reconnection (The Snapping of Plasma)
        for p1, p2 in breached_edges:
            # 1. Reset Tension Topology
            lattice.reset_edge(p1, p2)
            
            # 2. Napalm the Dead-Loop: Force complete isolation via massive negative dead-zones
            # A 500 magnitude topological exclusion prevents any future Muons from returning
            # C47H BUG-26 fix: was field.step() per breached edge — N edges = N
            # full disk dumps + N rounds of global decay. commit() persists the
            # deadzone without aging the rest of the field. Step scheduling is
            # the global heartbeat's job.
            field.write_deadzone(p1, 500.0)
            field.write_deadzone(p2, 500.0)
            field.commit()
            
            # 3. Plasma Ejection: Any swimmer caught in the blast vector is radially blasted
            for swimmer in swimmers:
                if swimmer.alive and (swimmer.path == p1 or swimmer.path == p2):
                    # Radially eject by destroying its trajectory entirely
                    swimmer.alive = False 
                    
        return True


if __name__ == "__main__":
    import shutil
    import tempfile

    # Smoke Test
    print("═" * 58)
    print("  SIFTA — SWARM SPACE PHYSICS (SPALLATION/RECONNECTION)")
    print("═" * 58 + "\n")
    
    _tmp = Path(tempfile.mkdtemp())
    try:
        field = SwarmPotentialField(state_dir=_tmp)
        lattice = FluxLattice()
        engine = MagneticReconnectionEngine(crack_threshold=5.0)
        
        path_a = Path("/ide/virtual/A.py")
        path_b = Path("/ide/virtual/B.py")
        
        # Manually construct a massive topology trap
        print("[TEST] Magnetic Reconnection Engine (Topology Snaps)")
        for _ in range(6): 
            lattice.inject_twist(path_a, path_b)
            
        # Place a muon directly inside the dead-loop
        swimmer = MuonSwimmer(path_a, energy=100)
        
        breach = engine.cycle(field, lattice, [swimmer])
        assert breach == True, "Failed to detect explosive loop tension."
        assert swimmer.alive == False, "Swimmer was not ejected during Magnetic Reconnection."
        
        dead_heat_a = field.field.get(path_a, 0.0)
        assert dead_heat_a < 0.0, "Reconnection failed to napalm the topology limits."
        
        print("  [PASS] Reconnection Engine flawlessly snapped dead topologies (-∇ DeadZones Applied).")
        print("  [PASS] Trapped Muon successfully ejected out of loop lattice.\n")
        
        print("[TEST] Cosmic-Ray Spallation (Transient & Stable State)")
        valid_path = Path("/ide/virtual/Root.py")
        worker = MuonSwimmer(valid_path, energy=3)
        
        # Inject positive vector 
        field.write_potential(valid_path.parent, 10.0)
        
        worker.move(field, lattice)
        assert worker.energy == 2, "Muon didn't burn transient energy."
        
        isotope_heat = field.field.get(worker.path, 0.0)
        assert isotope_heat > 0.0, "Muon failed to drop permanent Isotope trace on the execution target."
        print(f"  [PASS] Spallation Isotope flawlessly deposited memory onto {worker.path.name}.")
        
        print("\n[SUCCESS] Astrophysics Stigmergy accurately operational.")

    finally:
        shutil.rmtree(_tmp, ignore_errors=True)
