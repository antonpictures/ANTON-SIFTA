#!/usr/bin/env python3
"""
swarm_potential_field.py — Path-Graph Potential Field
═════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Opus C47H Correction Module.
The original EFSM hypothesis used an alien Euclidean Numpy grid. 
SIFTA swimmers traverse a Path-Graph (the OS file system tree). 

This module replaces 2D geometry with explicit Graph Topology.
Sensory fields (Audio, Vision, Pain) deposit physical Heat (Φ) onto 
a specific File Path. That heat diffuses across graph edges (up to 
the parent directory, down to active siblings) and decays over time.

Instead of a spatial vector descent, swimmers query `-∇Φ(path)` and 
are mathematically vectored to the adjacent URI containing the 
steepest ascending biological potential.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Optional

MODULE_VERSION = "2026-04-18.v5"

class SwarmPotentialField:
    def __init__(self, decay: float = 0.98, state_dir: Optional[Path] = None):
        if state_dir is None:
            # Default to the SIFTA biological config directory
            base_dir = Path(__file__).resolve().parent.parent
            self.state_file = base_dir / ".sifta_state" / "potential_field.json"
        else:
            self.state_file = state_dir / "potential_field.json"
            
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Topological manifold maps Paths to intensity limits
        self.field: Dict[Path, float] = self._load_state()
        self.decay = decay

    def _load_state(self) -> Dict[Path, float]:
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, "r") as f:
                raw_data = json.load(f)
                return {Path(k): float(v) for k, v in raw_data.items()}
        except (json.JSONDecodeError, ValueError):
            return {}
            
    def _persist(self):
        """
        Physically locks the memory state to the filesystem to survive process death.
        """
        # Convert path keys back to strings for JSON
        raw_data = {str(k): v for k, v in self.field.items()}
        try:
            tmp = self.state_file.with_suffix(".json.tmp")
            with open(tmp, "w") as f:
                json.dump(raw_data, f)
            tmp.replace(self.state_file)
        except Exception:
            pass

    def write_potential(self, path: Path, intensity: float):
        """
        Sensory substrates (Audio, Photonic) inject local intensity to a file node.
        Lazy-persist: caller must invoke commit() or step() to flush to disk.
        High-frequency sensory streams should rely on step() batching.
        """
        p = Path(path).resolve()
        self.field[p] = self.field.get(p, 0.0) + intensity

    def write_deadzone(self, path: Path, severity: float = 100.0):
        """
        File System Auto-Immunity.
        Non-biological accesses (e.g. random bot reading) physically scar the topography, 
        rendering the exact coordinates mathematically repulsive.
        Lazy-persist: caller must invoke commit() or step() to flush to disk.
        """
        p = Path(path).resolve()
        self.field[p] = self.field.get(p, 0.0) - severity

    def commit(self):
        """
        C47H bugfix (BUG-17): explicit single-shot persistence path for callers
        that need their write to survive process death NOW (e.g. swarm_pain
        broadcasting an immune deadzone, swarm_crossmodal_binding stamping a
        coherent object). Decoupled from step() so it doesn't trigger
        diffusion/decay — pure I/O flush. Continuous sensory writers should
        keep using step() for batched cycle-aligned persistence.
        """
        self._persist()

    def _diffuse(self):
        """
        Laplacian smoothing mapped onto the File System Graph.
        Heat bleeds from nodes to their parent directories and structure.
        """
        next_field: Dict[Path, float] = {}
        
        for path, heat in self.field.items():
            if abs(heat) < 0.001:
                continue  # Floor out trace vapor (garbage collection bounds the memory inherently)
                
            # Biological retention: 80% of heat stays at the specific node
            local_heat = heat * 0.80
            next_field[path] = next_field.get(path, 0.0) + local_heat
            
            # Asymmetric Diffusion (BUG-10):
            # Only positive geometric heat pulls upward. Negative (Dead Zones) are localized.
            if heat > 0:
                parent = path.parent
                if parent != path:
                    bleed = heat * 0.20
                    next_field[parent] = next_field.get(parent, 0.0) + bleed
                    
        self.field = next_field
        
    def step(self):
        """
        Advances the biological clock of reality through the graph.
        """
        self._diffuse()
        
        # Temporal mathematical decay and Garbage Collection
        keys_to_delete = []
        for k in list(self.field.keys()):
            self.field[k] *= self.decay
            if abs(self.field[k]) < 0.001:
                keys_to_delete.append(k)
                
        for k in keys_to_delete:
            del self.field[k]
            
        self._persist()

    def gradient_descent(self, current_path: Path) -> Path:
        """
        Calculates -∇Φ for a file system agent. 
        Returns the adjacent anatomical node (parent or known sibling) 
        possessing the highest biological mass relative to the current position.
        """
        current_path = Path(current_path).resolve()
        
        best_path = current_path
        best_heat = self.field.get(current_path, 0.0)
        
        # Search the Parent node
        parent = current_path.parent
        p_heat = self.field.get(parent, 0.0)
        if p_heat > best_heat:
            best_heat = p_heat
            best_path = parent
            
        # Search geometrically adjacent physical edges (Siblings or Direct Children) that hold heat
        for path, heat in self.field.items():
            if path == current_path: 
                continue
                
            if path.parent == current_path.parent or path.parent == current_path:
                if heat > best_heat:
                    best_heat = heat
                    best_path = path

        return best_path


if __name__ == "__main__":
    import shutil
    # Smoke Test
    print("═" * 58)
    print("  SIFTA — PATH-GRAPH POTENTIAL FIELD SMOKE TEST")
    print("═" * 58 + "\n")
    
    test_tmp = Path(tempfile.mkdtemp())
    try:
        field = SwarmPotentialField(state_dir=test_tmp)
        
        deep_file = Path("/sifta/Documents/Research/math_kernel.py")
        parent_dir = Path("/sifta/Documents/Research")
        sibling_file = Path("/sifta/Documents/Research/test_kernel.py")
        
        print("[TEST] Graph Edge Diffusion (Asymmetric BUG-10)")
        field.write_potential(deep_file, 100.0)
        field.step()
        
        deep_heat = field.field.get(deep_file, 0.0)
        parent_heat = field.field.get(parent_dir, 0.0)
        
        assert parent_heat > 0.0, "Graph failed to physically diffuse up to the parent edge."
        print("  [PASS] Stigmergic vapor successfully bled up the file system tree geometry.")
        print(f"         Deep Node Positive Heat: {deep_heat:.2f} | Parent Edge Heat: {parent_heat:.2f}")

        field.write_deadzone(deep_file, 1000.0)
        field.step()
        parent_heat_after = field.field.get(parent_dir, 0.0)
        # Parent heat biologically retains 80% (bleeding 20% up to its own parent), then decays 98% temporally
        decay_expected = parent_heat * 0.80 * 0.98
        assert abs(parent_heat_after - decay_expected) < 0.01, f"Negative Auto-immunity bleached the parent structure. (Expected {decay_expected}, got {parent_heat_after})"
        print("  [PASS] Negative Napalm Asymmetry confirmed: Parent topological structures securely isolated.")

        print("\n[TEST] Topological Gradient Descent (-∇Φ)")
        field.write_potential(sibling_file, 200.0)
        field.step()
        
        vector_path = field.gradient_descent(parent_dir)
        assert vector_path == sibling_file, f"Geometric descent mathematically failed. Went to {vector_path}"
        print(f"  [PASS] Descent accurately routed agent off `{parent_dir.name}` into heaviest adjacent well: `{vector_path.name}`.")

        print("\n[TEST] Auto-Immune Excision (Dead Zones)")
        corrupt_file = Path("/sifta/Documents/Research/bot_dirt.txt")
        field.write_deadzone(corrupt_file, 500.0)
        field.step()
        
        vector_survive = field.gradient_descent(corrupt_file)
        assert vector_survive != corrupt_file, "Swimmer incorrectly chose to remain on biologically corrupt layout."
        print("  [PASS] Negative Topography organically forces complete structural repulsion away from PheroPath traces.")

        print("\n[TEST] Stigmergic Persistence (BUG-7)")
        field2 = SwarmPotentialField(state_dir=test_tmp)
        deep2 = field2.field.get(deep_file, 0.0)
        assert deep2 < 0.0, "Topological structure suffered amnesia after process death."
        print(f"  [PASS] Field memory properly survived python interpreter death. (Retrieved: {deep2:.2f})")

        print("\n[SUCCESS] Path-Graph Auto-Immunity and True Stigmergy natively operational.")
    finally:
        shutil.rmtree(test_tmp, ignore_errors=True)
