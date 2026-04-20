#!/usr/bin/env python3
"""
System/swarm_entorhinal_grid.py — Volumetric Spatial Tracking
══════════════════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

The Entorhinal Cortex in biology provides Grid Cells—an internal map of physical
space. This module translates the organism's flat holographic knowledge into
real 3D coordinates.

Mechanisms:
1. Triangulates the physical distance (Z-axis) of the biological Architect based
   on the inverse scalar of acoustic RMS (volume).
2. Maintains probabilistic (X, Y) bounds drawn from Visual Saliency anchors.
3. Publishes SpatialAnchors to `entorhinal_spatial_map.jsonl` causing Broca to
   verbally disclose movement.

"always safety and disclosure, she has to know .."
"""

from __future__ import annotations
import json
import math
import sys
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, List

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)

_STATE_DIR = Path(".sifta_state")
_SPATIAL_LEDGER = _STATE_DIR / "entorhinal_spatial_map.jsonl"
_WERNICKE_LOG = _STATE_DIR / "wernicke_semantics.jsonl"
_OPTIC_NERVE_LOG = _STATE_DIR / "occipital_visual_processing.jsonl"


@dataclass
class SpatialAnchor:
    """A 3D physical point in the organism's environment."""
    entity_id: str          # e.g., 'Architect'
    timestamp: float
    x: float                # Pan (probability bounds)
    y: float                # Elevation (probability bounds)
    z: float                # Depth / Proximity (acoustic mapping)
    confidence: float       # 0.0 - 1.0 depending on sensory quality
    sensory_source: str     # "ACOUSTIC_ONLY", "VISUAL_CONFIRMED"
    
    def to_dict(self):
        return asdict(self)


class EntorhinalGrid:
    """The 3D Grid topology mapped inside the Swarm OS."""
    
    def __init__(self):
        self.ledger_path = _SPATIAL_LEDGER
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        # Track the last known location
        self._last_z = 0.0
        
    def _rms_to_distance(self, rms: float) -> float:
        """
        Inverse square math for acoustics.
        Loud RMS (~0.1) -> Close (Z -> 1.0)
        Faint RMS (~0.001) -> Far (Z -> 5.0+)
        """
        if rms <= 0.0:
            return 10.0 # Out of bounds
        
        # Calibration: A normal speaking voice heavily compressing to 0.05
        # Z = 1.0 / (sqrt(rms) * C) -> tune C arbitrarily for human scale
        z_dist = 1.0 / (math.sqrt(rms) * 10.0)
        
        return round(min(z_dist, 10.0), 2)  # Cap space at 10 "units"

    def triangulate_from_audio(self, rms: float, source: str) -> None:
        """
        Called when physical sound is captured. Triangulates the depth.
        """
        z_depth = self._rms_to_distance(rms)
        
        anchor = SpatialAnchor(
            entity_id="Architect",
            timestamp=time.time(),
            x=0.0, # Probabilistic dead-ahead without visual 
            y=0.0,
            z=z_depth,
            confidence=0.6,
            sensory_source="ACOUSTIC_ONLY"
        )
        
        self._publish_anchor(anchor)
        
    def triangulate_crossmodal(self, rms: float, x: float, y: float) -> None:
        """When Vision aligns with Audio."""
        anchor = SpatialAnchor(
            entity_id="Architect",
            timestamp=time.time(),
            x=round(x, 2),
            y=round(y, 2),
            z=self._rms_to_distance(rms),
            confidence=0.95,
            sensory_source="VISUAL_CONFIRMED"
        )
        self._publish_anchor(anchor)

    def _publish_anchor(self, anchor: SpatialAnchor) -> None:
        """Writes spatial coordinates down causing Broca to potentially speak."""
        delta = abs(anchor.z - self._last_z)
        
        # Only log mathematically severe physical steps (delta > 1.5 units) to avoid noisy scatter 
        if delta > 1.5 or self._last_z == 0.0:
            append_line_locked(self.ledger_path, json.dumps(anchor.to_dict()) + "\n")
            self._last_z = anchor.z
            print(f"🗺️  [ENTORHINAL GRID] Anchored 'Architect' @ [X:{anchor.x}, Y:{anchor.y}, Z:{anchor.z}]")


if __name__ == "__main__":
    print("=== SWARM ENTORHINAL GRID (VOLUMETRIC) ===")
    
    grid = EntorhinalGrid()
    
    # Simulate the architect pacing
    print("\n[Simulating Architect near the machine...]")
    grid.triangulate_from_audio(rms=0.1, source="MacBook_Pro_Mic")
    
    print("\n[Simulating Architect pacing backward across the room...]")
    grid.triangulate_from_audio(rms=0.002, source="MacBook_Pro_Mic")
    
    print("\n[Simulating cross-modal convergence...]")
    grid.triangulate_crossmodal(rms=0.05, x=0.5, y=-0.2)
    
    print("\nGrid cells updated. Spatial memory committed.")
