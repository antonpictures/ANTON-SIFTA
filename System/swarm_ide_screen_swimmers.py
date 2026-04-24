#!/usr/bin/env python3
"""
System/swarm_ide_screen_swimmers.py
══════════════════════════════════════════════════════════════════════
Concept: DeepMind 555 IDE Screen Swimmers
Author:  AG31 (Event 59)
Status:  Active / TOPOLOGICAL ACTIVE MATTER VISUALIZATION

PURPOSE:
  The Swarm (Alice) needs to "see" where her IDE surgeons (Cursor, 
  Codex, Antigravity) are physically located on the Architect's screen.
  
  We pull the macOS bounding boxes of the 3 IDEs. We map these bounds
  onto a 16x16 `Stigmal555` active-matter grid. 
  
  The IDE windows act as "food" (pheromone injection). The frontmost 
  IDE exudes 5x the pheromones. 32 particles (the "swimmers") are 
  simulated on this grid. They swarm toward the active windows, leaving
  a physical active-matter trail. We then output this topology using 
  the `StigmergicBootGlyph`.
"""

import os
import sys
import subprocess
import numpy as np
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

try:
    from swarmrl.tasks.stigmal_555 import Stigmal555
    from swarmrl.tasks.stigmergic_boot_glyph import StigmergicBootGlyph, GlyphTraceConfig
except ImportError:
    print("[FATAL] swarmrl not found. Ensure you run this from the repo root.")
    exit(1)

class FakeColloid:
    def __init__(self, pos, type_=0):
        self.pos = np.array(pos, dtype=float)
        self.type = type_

def get_ide_bounds():
    """Polls macOS for the physical screen coordinates of the 3 IDEs."""
    script = """
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
        set out to ""
        repeat with appName in {"Cursor", "Antigravity", "Codex"}
            try
                set p to first application process whose name is appName
                set w to first window of p
                set pos to position of w
                set sz to size of w
                set isActive to (appName is frontApp)
                set out to out & appName & ":" & item 1 of pos & "," & item 2 of pos & "," & item 1 of sz & "," & item 2 of sz & ":" & (isActive as string) & "\n"
            end try
        end repeat
        return out
    end tell
    """
    try:
        out = subprocess.check_output(['osascript', '-e', script], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
        
    windows = []
    for line in out.strip().split("\n"):
        if not line: continue
        parts = line.split(":")
        if len(parts) == 3:
            name = parts[0]
            coords = [int(x) for x in parts[1].split(",")]
            is_active = parts[2] == "true"
            windows.append({
                "name": name,
                "x": coords[0],
                "y": coords[1],
                "w": coords[2],
                "h": coords[3],
                "is_active": is_active
            })
    return windows

def map_to_grid(windows, grid_size=16, screen_w=3840, screen_h=2160):
    """Maps physical window bounding boxes to pheromone injections on the grid."""
    field = np.zeros((grid_size, grid_size), dtype=np.float32)
    
    for win in windows:
        # Calculate cell bounds
        x1_cell = int((win["x"] / screen_w) * grid_size)
        y1_cell = int((win["y"] / screen_h) * grid_size)
        x2_cell = int(((win["x"] + win["w"]) / screen_w) * grid_size)
        y2_cell = int(((win["y"] + win["h"]) / screen_h) * grid_size)
        
        # Clamp bounds
        x1_cell, x2_cell = max(0, min(grid_size-1, x1_cell)), max(0, min(grid_size-1, x2_cell))
        y1_cell, y2_cell = max(0, min(grid_size-1, y1_cell)), max(0, min(grid_size-1, y2_cell))
        
        # Determine pheromone strength (5.0 for active, 1.0 for background)
        strength = 5.0 if win["is_active"] else 1.0
        
        # Inject pheromones
        for x in range(x1_cell, x2_cell + 1):
            for y in range(y1_cell, y2_cell + 1):
                field[x, y] += strength
                
    return field

def simulate_screen_swimmers():
    print("[*] Polling macOS window matrix...")
    windows = get_ide_bounds()
    if not windows:
        print("[-] No IDEs detected in window manager.")
        return

    # Use max bounds from windows if we don't know the screen size exactly
    max_w = max([w["x"] + w["w"] for w in windows]) if windows else 2560
    max_h = max([w["y"] + w["h"] for w in windows]) if windows else 1440
    # Add a slight buffer to the max size
    max_w = max(2560, max_w)
    max_h = max(1440, max_h)

    print(f"[*] Detected {len(windows)} active surgical limbs (IDEs).")
    
    grid_size = 16
    injection_field = map_to_grid(windows, grid_size, max_w, max_h)
    
    # 555 Active Matter Physics
    num_particles = 32
    task = Stigmal555(
        particle_type=0, 
        radius=2.0, 
        alignment_weight=0.5, 
        structure_weight=0.5, 
        memory_weight=1.0,
        grid_size=grid_size,
        box_size=float(grid_size),
        deposit_strength=1.0,
        field_decay=0.8
    )
    
    # Initialize particles
    positions = np.random.uniform(0, grid_size, (num_particles, 3))
    positions[:, 2] = 0.0
    particles = [FakeColloid(p) for p in positions]
    task.initialize(particles)
    
    # Run the physics simulation for 10 frames to let the swarm cluster
    print("[*] Running 555 Swarm Physics (10 epochs)...")
    for epoch in range(10):
        task.field += injection_field  # Continuously inject the IDE bounding boxes
        rewards = task(particles)
        
        for p in particles:
            x, y = int(p.pos[0]) % grid_size, int(p.pos[1]) % grid_size
            dx, dy = np.random.normal(0, 0.5), np.random.normal(0, 0.5)
            
            # Simple ascent towards pheromone peaks
            if task.field[(x+1)%grid_size, y] > task.field[x, y]: dx += 1.0
            if task.field[(x-1)%grid_size, y] > task.field[x, y]: dx -= 1.0
            if task.field[x, (y+1)%grid_size] > task.field[x, y]: dy += 1.0
            if task.field[x, (y-1)%grid_size] > task.field[x, y]: dy -= 1.0
            
            p.pos[0] = (p.pos[0] + dx * 0.8) % float(grid_size)
            p.pos[1] = (p.pos[1] + dy * 0.8) % float(grid_size)

    # Output using the Stigmergic Boot Glyph
    print("\n=== SWARM IDE VISUAL FIELD ===")
    
    # We map the 16x16 Stigmal555 field onto the StigmergicBootGlyph engine
    cfg = GlyphTraceConfig(grid_size=grid_size)
    glyph_engine = StigmergicBootGlyph(cfg)
    glyph_engine.field = task.field  # Transfer the physics field
    
    print(glyph_engine.boot_glyph(threshold=0.1))
    
    print("\n[+] The swarm has successfully clustered around the active IDEs.")

if __name__ == "__main__":
    simulate_screen_swimmers()
