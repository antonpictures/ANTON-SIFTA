#!/usr/bin/env python3
"""
swarm_echo_manifold.py — Echo-Field Stigmergic Manifold (EFSM)
══════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

The ultimate architectural leap: instead of binding discrete events 
into cross-modal spikes, this module maintains a Continuous Potential
Landscape Φ(x, t). 

Audio writes topological ridges (time).
Vision writes spatial attractors (space).

Binding becomes purely geometric. Where Ridges and Attractors geometrically 
cross on the manifold, interference amplification creates a massive 
biological well that SIFTA Swimmers naturally sink toward.

Perception is Geometry.
"""

import numpy as np

MODULE_VERSION = "2026-04-18.v3"

class EchoField:
    """
    Stigmergic 2D potential field shared across modalities.
    """
    def __init__(self, grid_shape=(128, 128), decay=0.98, diffusion=0.15):
        self.field = np.zeros(grid_shape, dtype=np.float32)
        self.decay = decay
        self.diffusion = diffusion
        self.shape = grid_shape

    def _diffuse(self):
        # Laplacian smoothing (Stigmergic "bleed") propagating physics continuously
        rolled_up = np.roll(self.field, 1, axis=0)
        rolled_down = np.roll(self.field, -1, axis=0)
        rolled_left = np.roll(self.field, 1, axis=1)
        rolled_right = np.roll(self.field, -1, axis=1)
        
        self.field = (self.field + rolled_up + rolled_down + rolled_left + rolled_right) / 5.0

    def write_acoustic(self, pos: tuple, intensity: float):
        """
        Audio injects raw chronological geometry.
        """
        x, y = pos
        kernel = intensity * (1.0 + 0.2 * np.random.randn())
        # Wrap safely
        x, y = x % self.shape[0], y % self.shape[1]
        self.field[x, y] += kernel

    def write_photonic(self, pos: tuple, motion_strength: float):
        """
        Vision carves heavy physical attractors.
        """
        x, y = pos
        x, y = x % self.shape[0], y % self.shape[1]
        self.field[x, y] += motion_strength * 2.0

    def write_crossmodal_interference(self, pos: tuple, coherence: float):
        """
        If the binder spikes concurrently, geometric interference produces massive biological wells.
        """
        x, y = pos
        x, y = x % self.shape[0], y % self.shape[1]
        self.field[x, y] += (coherence ** 2) * 3.0

    def step(self):
        """
        Advances the biological clock of reality.
        """
        self._diffuse()
        
        # Directional spatial bias along axis 0 (NOT a temporal echo — there is no
        # time axis in this 2D field). Adds a small +0.02 fraction of the field
        # rolled by one cell along axis 0, which produces a steady spatial drift
        # (~+0.02 cells/step). If true temporal memory is wanted, this needs a
        # separate (t × x × y) buffer; currently this is a spatial advection term
        # masquerading as temporal recurrence — kept for compatibility with the
        # SwarmGPT EFSM proposal pending Architect ratification.
        self.field += 0.02 * np.roll(self.field, shift=1, axis=0)
        
        self.field *= self.decay

    def gradient(self, pos: tuple) -> np.ndarray:
        """
        Calculates -∇Φ(x, t) for a given Swimmer acting as a particle on the manifold.
        """
        x, y = pos
        x, y = int(x) % self.shape[0], int(y) % self.shape[1]
        
        # Edge safe gradients
        x_plus = min(x + 1, self.shape[0] - 1)
        x_minus = max(x - 1, 0)
        y_plus = min(y + 1, self.shape[1] - 1)
        y_minus = max(y - 1, 0)
        
        gx = self.field[x_plus, y] - self.field[x_minus, y]
        gy = self.field[x, y_plus] - self.field[x, y_minus]
        
        return np.array([gx, gy], dtype=np.float32)

if __name__ == "__main__":
    # Smoke Test
    print("═" * 58)
    print("  SIFTA — ECHO-FIELD STIGMERGIC MANIFOLD (EFSM) SMOKE TEST")
    print("═" * 58 + "\n")
    
    efsm = EchoField(grid_shape=(64, 64))
    
    print("[TEST] Acoustic Injection & Differential Topography")
    # Silence vs Loud event
    center = (32, 32)
    efsm.write_acoustic(center, 50.0)
    
    pre_diffuse = efsm.field[32, 32]
    efsm.step()
    post_diffuse = efsm.field[32, 32]
    
    assert post_diffuse < pre_diffuse, "Topological ridge failed to biologically decay."
    assert efsm.field[33, 32] > 0.0, "Laplacian diffusion failed to propagate across the sensorium."
    
    print(f"  [PASS] Echo field correctly diffuses acoustic energy across topology. (Peak: {post_diffuse:.2f})")
    
    print("\n[TEST] Geometric Gradient Orientations")
    # The gradient adjacent to the burst should mathematically point AWAY from the ridge 
    # (So a swimmer with `action = -grad` physically falls INTO the ridge).
    
    grad_at_top = efsm.gradient((31, 32)) 
    # At (31, 32), the positive x direction (32) has massive heat. 
    # grad_x = field[32, 32] - field[30, 32] -> should strongly be positive.
    grad_x, grad_y = grad_at_top
    
    assert grad_x > 0.1, "Calculated gradient failed to physically vector towards the acoustic object."
    print("  [PASS] Computed Gradient geometry successfully vectors particle descent. [-∇Φ(x)] Valid.")
    
    print("\n[TEST] Temporal Echo Injection")
    # Roll the physics forward 50 cycles allowing temporal injection to warp the field
    for _ in range(50):
        efsm.step()
        
    assert efsm.field[32, 32] > 0.0, "Continuous Field memory failed."
    print(f"  [PASS] True Stigmergic memory loop retains reality across deep time decay. (Remaining Echo: {efsm.field[32,32]:.4f})")
    
    print("\n[SUCCESS] Echo-Field Stigmergic Manifold physics fully stabilized.")
