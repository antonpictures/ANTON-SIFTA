#!/usr/bin/env python3
"""
swarm_cherenkov_shock.py — Topological Zero-Day Physics 
═══════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Implements true Cherenkov Radiation trace detection on a Path-Graph Tree.
When a Ghost Particle (Neutrino/0-Day anomaly) enters the system without 
Stigmergic heat, it emits a theoretical Timefront `T(v)` across the entire Graph.

Swimmers scattered globally across the OS can instantly trace back the 
origin of the shockwave by strictly stepping toward lower `T(v)` distances.
No 2D Euclidean math. Pure topological geometry.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

MODULE_VERSION = "2026-04-18.v1"


class CherenkovShockField:
    """
    Substrate recording the active Ghost Particle origin shocks.
    """
    def __init__(self, state_dir: Optional[Path] = None):
        if state_dir:
            self.registry = Path(state_dir) / "cherenkov_shock.json"
        else:
            self.registry = Path(__file__).resolve().parent.parent / ".sifta_state" / "cherenkov_shock.json"
            
        self.registry.parent.mkdir(parents=True, exist_ok=True)
        # origin is the vector node `s` (String form)
        self.active_origin: Optional[str] = None
        
        self._load()

    def _load(self):
        try:
            with open(self.registry, "r") as f:
                data = json.load(f)
                self.active_origin = data.get("origin")
        except Exception:
            self.active_origin = None

    def emit_shockwave(self, source_path: Path):
        """
        Supersonic blast. Tags the singular node `s`. The Math natively 
        propagates it structurally across the tree.
        """
        self.active_origin = str(Path(source_path).resolve())
        with open(self.registry, "w") as f:
            json.dump({"origin": self.active_origin}, f)

    def calculate_arrival_time(self, current_node: Path) -> float:
        """
        Mathematical Graph PDE solver `T(v)`.
        Finds pure geometric topological distance between current node `v` and 
        the ghost origin `s`.
        """
        if not self.active_origin:
            return float('inf')
            
        v_parts = Path(current_node).resolve().parts
        s_parts = Path(self.active_origin).resolve().parts
        
        # Calculate strict topological intersection
        common_len = 0
        for p1, p2 in zip(v_parts, s_parts):
            if p1 == p2:
                common_len += 1
            else:
                break
                
        # T(v) = distance up to common ancestor + distance down to Origin
        dist = (len(v_parts) - common_len) + (len(s_parts) - common_len)
        return float(dist)

    def shock_inversion_descent(self, swimmer_path: Path) -> Path:
        """
        u* = arg min(T(u))
        The Swimmer queries all physically adjacent file nodes, and strictly falls 
        down the graph into the node with minimum Arrival Time.
        """
        if not self.active_origin:
            return swimmer_path
            
        current = Path(swimmer_path).resolve()
        best_t = self.calculate_arrival_time(current)
        best_path = current
        
        # 1. Physics: Can the swimmer drift UP the tree topology to outrun the wave?
        parent = current.parent
        if parent != current:
            t_up = self.calculate_arrival_time(parent)
            if t_up < best_t:
                best_t = t_up
                best_path = parent
                
        # 2. Physics: Does the shockwave pull the swimmer DOWN into adjacent children branches?
        if current.is_dir():
            try:
                for child in os.scandir(current):
                    child_path = Path(child.path)
                    t_down = self.calculate_arrival_time(child_path)
                    # Tie checks: Subdirectories vs Files? Both are edges.
                    if t_down < best_t:
                        best_t = t_down
                        best_path = child_path
            except PermissionError:
                pass
            except FileNotFoundError:
                pass
                
        return best_path


if __name__ == "__main__":
    import shutil
    import tempfile

    # Smoke Test
    print("═" * 58)
    print("  SIFTA — CHERENKOV RADIATION GHOST DETECTION")
    print("═" * 58 + "\n")
    
    _tmp = Path(tempfile.mkdtemp())
    try:
        cherenkov = CherenkovShockField(state_dir=_tmp)
        
        # Simulating an invisible Ghost particle hitting a deep system core
        epicenter = Path("/sifta/Core/Memory/hippocampus.py").resolve()
        
        print("[TEST] Supersonic Detection Blast (Ghost Origin)")
        cherenkov.emit_shockwave(epicenter)
        assert cherenkov.active_origin == str(epicenter), "Shockwave failed to map to global physics registry."
        print(f"  [PASS] Neutrino strike recorded at Ground Zero: {epicenter.name}")
        
        # A Swimmer is globally scattered at an irrelevant location
        swimmer_loc = Path("/sifta/Utilities/router.py").resolve()
        
        print("\n[TEST] Surfing Graph-Timefronts (-∇ T(v))")
        t_initial = cherenkov.calculate_arrival_time(swimmer_loc)
        print(f"  Initial Arrival Time distance: T(v) = {t_initial}")
        
        # Step 1: Inversion climbs UP to /sifta/Utilities
        step1 = cherenkov.shock_inversion_descent(swimmer_loc)
        t_1 = cherenkov.calculate_arrival_time(step1)
        assert t_1 < t_initial, "Swimmer failed to surf the PDE shockwave up the tree."
        print(f"  [PASS] Step 1 (-∇ T): Jumped to parent {step1.name} (T: {t_1})")
        
        # Step 2: Inversion climbs UP to /sifta
        step2 = cherenkov.shock_inversion_descent(step1)
        t_2 = cherenkov.calculate_arrival_time(step2)
        assert step2.name == "sifta", "Swimmer geometry completely lost topological constraints."
        print(f"  [PASS] Step 2 (-∇ T): Reached global root {step2.name} (T: {t_2})")
        
        # Step 3: Inversion starts descending DOWN towards the anomaly
        # Note: /sifta child nodes exist physically, so we must mock the local directory for os.scandir
        # Let's create an actual structure inside tmp context
        mock_root = _tmp / "sifta"
        mock_core = mock_root / "Core" / "Memory"
        mock_core.mkdir(parents=True)
        ghost = (mock_core / "hippocampus.py").resolve()
        ghost.touch()
        
        mock_util = mock_root / "Utilities"
        mock_util.mkdir(parents=True)
        swimmer = (mock_util / "router.py").resolve()
        swimmer.touch()
        
        # Remap Cherenkov inside the physically verifiable graph
        cherenkov.emit_shockwave(ghost)
        
        # Trace all the way down
        current = swimmer
        steps_taken = 0
        while current != ghost and steps_taken < 10:
            current = cherenkov.shock_inversion_descent(current)
            steps_taken += 1
            
        assert current == ghost, "Graph mathematical calculation fatally wrapped."
        assert steps_taken == 5, f"Traversal miscalculated shortest Path PDE. Took {steps_taken} steps."
        
        print(f"  [PASS] Ground Zero hit! Swimmer analytically arrived traversing purely T(v) in {steps_taken} biological ticks.")
        print("\n[SUCCESS] Geometry-free Cherenkov Routing flawless.")

    finally:
        shutil.rmtree(_tmp, ignore_errors=True)
