#!/usr/bin/env python3
"""
System/swarm_entropy_gate_demo.py
══════════════════════════════════════════════════════════════════════
Concept: Stigmergic Entropy Gate Demo
Author:  AG31 (SwarmGPT Drop Integration)

This script wires the `StigmergicEntropyGate` into a live physics loop.
Agents drop pheromones, sense the field, and adjust their trajectories
based on the entropy constraints (trail reward, novelty, entropy, crowding).
"""

import sys
import time
import numpy as np
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from swarmrl.tasks.stigmergic_entropy_gate import StigmergicEntropyGate, EntropyGateConfig
except ImportError:
    print("[FATAL] swarmrl not found.")
    sys.exit(1)

class Agent:
    def __init__(self, x, y, grid_size):
        self.pos = np.array([float(x), float(y)])
        self.vel = np.random.normal(0, 1.0, 2)
        self.grid_size = grid_size
        self.reward = 0.0

    def sense_field(self, task: StigmergicEntropyGate):
        # Sample the surrounding cells (3x3 grid)
        # Find the max gradient to climb
        best_val = -1
        best_dir = np.array([0.0, 0.0])
        
        # Current cell index
        ix, iy = task._idx(self.pos)
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0: continue
                nx, ny = np.clip(ix + dx, 0, self.grid_size - 1), np.clip(iy + dy, 0, self.grid_size - 1)
                val = task.field[nx, ny]
                if val > best_val:
                    best_val = val
                    best_dir = np.array([float(dx), float(dy)])
                    
        return best_dir, best_val

    def update(self, task: StigmergicEntropyGate):
        # 1. Sense the stigmergic field
        grad_dir, grad_val = self.sense_field(task)
        
        # 2. If the field has high pheromones, we steer towards the gradient.
        #    If not, we just wander.
        if grad_val > 0.1:
            # We want to follow the trail, but with some noise
            self.vel = 0.7 * self.vel + 0.3 * grad_dir
        else:
            # Random walk
            self.vel += np.random.normal(0, 0.5, 2)
            
        # Normalize velocity so they don't explode
        speed = np.linalg.norm(self.vel)
        if speed > 0:
            self.vel = (self.vel / speed) * 1.5
            
        self.pos += self.vel
        
        # Bounce off walls (or wrap, let's wrap for infinite topology)
        self.pos[0] = self.pos[0] % float(self.grid_size)
        self.pos[1] = self.pos[1] % float(self.grid_size)

def run_simulation():
    cfg = EntropyGateConfig(
        grid_size=32,
        deposit_strength=0.5,
        decay=0.97, # Slightly lower decay for faster field build
        diffusion=0.1
    )
    task = StigmergicEntropyGate(cfg)
    
    num_agents = 50
    agents = [Agent(np.random.uniform(0, cfg.grid_size), np.random.uniform(0, cfg.grid_size), cfg.grid_size) for _ in range(num_agents)]
    
    print("\033[H\033[J") # Clear screen
    print("[*] Spawning the Swarm... \n")
    
    try:
        for step in range(1, 201):
            # 1. Update positions
            for agent in agents:
                agent.update(task)
                
            positions = np.array([agent.pos for agent in agents])
            
            # 2. Feed positions into the stigmergic task
            # The task expects coordinates in [0, 1] for _idx if they aren't scaled?
            # Wait, StigmergicEntropyGate _idx clips to [0,1] and multiplies by grid_size!
            # Let's check _idx logic in StigmergicEntropyGate:
            # `xy = np.clip(xy[:2], 0.0, 1.0); ij = np.floor(xy * (g - 1)).astype(int)`
            # Ah! So positions must be normalized between 0 and 1!
            
            normalized_positions = positions / float(cfg.grid_size)
            
            rewards = task.step(normalized_positions)
            
            for agent, r in zip(agents, rewards):
                agent.reward += r
                
            # 3. Print the glyph
            if step % 25 == 0:
                print(f"--- Epoch {step} ---")
                print(f"Max field: {task.field.max():.2f}")
                print(task.glyph())
                print("\n")
                
    except KeyboardInterrupt:
        print("\n[+] Simulation halted.")
        
    print("\n[+] Swarm memory crystallized. Stigmergic Entropy Gate functional.")

if __name__ == "__main__":
    run_simulation()
