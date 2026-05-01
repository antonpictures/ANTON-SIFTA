# System/swarm_superior_colliculus.py

"""
Event 98 — Superior Colliculus (Multisensory Integration)
Biology: Meredith, Nemitz & Stein (1987); Wallace et al. (1996)
Rules of Integration:
1. Spatial Rule: coincident spatial fields enhance signal.
2. Temporal Rule: coincident timing enhances signal.
3. Inverse Effectiveness: maximum enhancement occurs when individual unimodal stimuli are weak.

SIFTA: Merges visual phenotype uniform state with acoustic spatial cues (owl) into unified salience.
Truth label: MULTISENSORY_SALIENCE
"""

import json
import time
import math
from pathlib import Path
from typing import Dict

STATE_DIR = Path(".sifta_state")
COLLICULUS_LOG = STATE_DIR / "superior_colliculus.jsonl"

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

class SuperiorColliculus:
    def integrate(self, 
                  visual_signal: float, visual_azimuth: float, 
                  audio_signal: float, audio_azimuth: float,
                  time_delta_sec: float) -> Dict:
        """
        Multisensory enhancement based on Meredith/Stein principles.
        """
        # Temporal window decay (temporal rule)
        # Decay is exponential based on time difference between visual and audio events
        temporal_alignment = math.exp(-abs(time_delta_sec) * 5.0)
        
        # Spatial alignment decay (spatial rule)
        spatial_diff = abs(visual_azimuth - audio_azimuth)
        spatial_alignment = math.exp(-spatial_diff * 2.0)
        
        # Base linear sum
        linear_sum = visual_signal + audio_signal
        
        # Inverse Effectiveness: enhancement multiplier is higher when signals are weak
        avg_strength = (visual_signal + audio_signal) / 2.0
        inverse_eff = 1.0
        if avg_strength > 0:
            inverse_eff = 1.0 + math.exp(-avg_strength * 4.0) * 1.5
            
        # Superadditive enhancement (only if aligned in space and time)
        enhancement = (visual_signal * audio_signal) * temporal_alignment * spatial_alignment * inverse_eff
        
        # Final integrated salience
        salience = clamp01(linear_sum + enhancement)
        
        row = {
            "timestamp": time.time(),
            "truth_label": "MULTISENSORY_SALIENCE",
            "visual_input": round(float(visual_signal), 4),
            "audio_input": round(float(audio_signal), 4),
            "temporal_alignment": round(float(temporal_alignment), 4),
            "spatial_alignment": round(float(spatial_alignment), 4),
            "inverse_effectiveness": round(float(inverse_eff), 4),
            "enhancement": round(float(enhancement), 4),
            "integrated_salience": round(float(salience), 4)
        }
        return row
        
    def append_integration(self, vis_sig: float, vis_az: float, aud_sig: float, aud_az: float, dt: float) -> Dict:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        row = self.integrate(vis_sig, vis_az, aud_sig, aud_az, dt)
        with COLLICULUS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        return row
