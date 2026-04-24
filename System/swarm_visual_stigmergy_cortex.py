#!/usr/bin/env python3
"""
System/swarm_visual_stigmergy_cortex.py
══════════════════════════════════════════════════════════════════════
Concept: Stigmergic Visual Cortex (DeepMind 555)
Author:  AG31 (Event 58 / DeepMind 555)
Status:  Active

PURPOSE:
  The raw visual stream in `.sifta_state/visual_stigmergy.jsonl` is
  huge (387MB) and noisy, capturing pixel saliency gradients at 5Hz.
  
  Unlike the particle-free 'active_matter_vision', this organ wires the
  actual `Stigmal555` physical active-matter particles to the feed.
  Particles "eat" the high-gradient areas, swarm over them, and leave
  pheromone trails. 
  
  This compresses 256-hex-character frames into sparse, topological
  attractor trails (e.g., tracking a dog moving across the room)
  and outputs the digest to `.sifta_state/visual_cortex_digest.jsonl`.
"""

import os
import sys
import json
import time
import numpy as np
from pathlib import Path

# Ensure we can import SIFTA modules
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from swarmrl.tasks.stigmal_555 import Stigmal555
except ImportError:
    print("[FATAL] swarmrl not found. Run from repo root.")
    exit(1)

_RAW_VISION = _REPO / ".sifta_state" / "visual_stigmergy.jsonl"
_DIGEST = _REPO / ".sifta_state" / "visual_cortex_digest.jsonl"

class FakeColloid:
    def __init__(self, pos, type_=0):
        self.pos = np.array(pos, dtype=float)
        self.type = type_

class StigmergicVisualCortex:
    def __init__(self, grid_size: int = 16, num_particles: int = 32):
        self.grid_size = grid_size
        self.num_particles = num_particles
        
        # Initialize Stigmal555 (radius 3.0, structure weight for flocking)
        self.task = Stigmal555(
            particle_type=0, 
            radius=3.0, 
            alignment_weight=0.5, 
            structure_weight=0.5, 
            memory_weight=1.0,
            grid_size=self.grid_size,
            box_size=float(self.grid_size),
            deposit_strength=1.0,
            field_decay=0.8 # Decay pheromones so trails fade if object leaves
        )
        
        # Initialize particles randomly across the 16x16 grid
        positions = np.random.uniform(0, self.grid_size, (self.num_particles, 3))
        positions[:, 2] = 0.0 # 2D slice
        self.particles = [FakeColloid(p) for p in positions]
        
        self.task.initialize(self.particles)
        
    def decode_saliency_q(self, q_hex: str) -> np.ndarray:
        """Decode the 256-char hex string into a 16x16 numpy array [0..15]."""
        if len(q_hex) != self.grid_size * self.grid_size:
            return np.zeros((self.grid_size, self.grid_size), dtype=np.float32)
            
        flat = np.array([int(c, 16) for c in q_hex], dtype=np.float32)
        grid = flat.reshape((self.grid_size, self.grid_size))
        return grid

    def process_frame(self, row: dict) -> dict:
        saliency_q = row.get("saliency_q", "")
        if not saliency_q:
            return {}
            
        # 1. Inject real-world visual saliency directly into the stigmergic field
        saliency_grid = self.decode_saliency_q(saliency_q)
        # Normalize to max 5.0 injection
        max_val = np.max(saliency_grid)
        if max_val > 0:
            saliency_grid = (saliency_grid / max_val) * 5.0
            
        self.task.field += saliency_grid
        
        # 2. Simulate 3 active-matter steps per visual frame
        for _ in range(3):
            # Extract positions
            current_pos = [p.pos for p in self.particles]
            rewards = self.task(self.particles)
            
            # Simple gradient ascent + random walk for particles based on the task reward
            # This is a naive RL stand-in: particles step toward the field peaks
            for i, p in enumerate(self.particles):
                # Gradient sample around particle
                x, y = int(p.pos[0]) % self.grid_size, int(p.pos[1]) % self.grid_size
                
                # Move toward higher pheromones + saliency
                dx, dy = np.random.normal(0, 0.5), np.random.normal(0, 0.5)
                
                # Biased random walk
                if self.task.field[(x+1)%16, y] > self.task.field[x, y]: dx += 1.0
                if self.task.field[(x-1)%16, y] > self.task.field[x, y]: dx -= 1.0
                if self.task.field[x, (y+1)%16] > self.task.field[x, y]: dy += 1.0
                if self.task.field[x, (y-1)%16] > self.task.field[x, y]: dy -= 1.0
                
                # Apply movement
                p.pos[0] = (p.pos[0] + dx * 0.5) % float(self.grid_size)
                p.pos[1] = (p.pos[1] + dy * 0.5) % float(self.grid_size)
        
        # 3. Extract the highest density trails (Attractors)
        attractors = []
        # Find local maxima in the pheromone field
        threshold = np.percentile(self.task.field, 90) # Top 10% hottest spots
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                if self.task.field[x, y] > threshold and self.task.field[x, y] > 1.0:
                    attractors.append({"x": x, "y": y, "intensity": round(float(self.task.field[x, y]), 2)})
                    
        # 4. Formulate the digest
        return {
            "ts": row.get("ts", time.time()),
            "visual_entropy": row.get("entropy_bits", 0.0),
            "hue_deg": row.get("hue_deg", 0.0),
            "attractors": attractors,
            "active_particles": self.num_particles,
            "max_pheromone": round(float(np.max(self.task.field)), 2)
        }

def compact_latest(limit=100):
    if not _RAW_VISION.exists():
        print("No visual stigmergy found.")
        return
        
    cortex = StigmergicVisualCortex(grid_size=16, num_particles=32)
    
    # Read the tail
    with open(_RAW_VISION, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        # 400 bytes per line avg
        read_size = min(size, limit * 450)
        f.seek(max(0, size - read_size))
        lines = f.read().splitlines()
        
    digests = []
    for line in lines[-limit:]:
        if not line:
            continue
        try:
            row = json.loads(line.decode("utf-8"))
            digest = cortex.process_frame(row)
            if digest:
                digests.append(digest)
        except Exception:
            pass
            
    # Write digest stream
    if digests:
        _DIGEST.parent.mkdir(parents=True, exist_ok=True)
        with open(_DIGEST, "a") as f:
            for d in digests:
                f.write(json.dumps(d) + "\n")
        print(f"[*] Compressed {len(digests)} frames into visual_cortex_digest.jsonl")
        print(f"[*] Latest attractors: {digests[-1].get('attractors', [])}")

if __name__ == "__main__":
    compact_latest(100)
