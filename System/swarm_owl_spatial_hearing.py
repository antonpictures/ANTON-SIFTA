# System/swarm_owl_spatial_hearing.py

"""
Event 97 — Owl Spatial Hearing Organ
Truth label: SIMULATED_SPATIAL_HEARING
Biology: Barn owls use Interaural Time Difference (ITD) for azimuth and Interaural Level Difference (ILD) for elevation.
SIFTA: We simulate spatial hearing via stereo separation proxies or synthetic binaural delays.
"""

import json
import time
import math
from pathlib import Path
from typing import Dict, Any

import numpy as np

OWL_LEDGER = Path(".sifta_state/owl_spatial_hearing.jsonl")

class OwlSpatialHearing:
    def __init__(self, ear_distance_meters: float = 0.2, speed_of_sound: float = 343.0):
        self.ear_dist = ear_distance_meters
        self.c = speed_of_sound
        
    def compute_localization(self, left_channel: np.ndarray, right_channel: np.ndarray, sr: int = 16000) -> Dict[str, Any]:
        """
        Compute ITD and ILD from stereo audio buffers.
        """
        if len(left_channel) == 0 or len(right_channel) == 0:
            return self._default_state()
            
        # 1. ILD (Interaural Level Difference)
        rms_left = float(np.sqrt(np.mean(left_channel**2))) + 1e-8
        rms_right = float(np.sqrt(np.mean(right_channel**2))) + 1e-8
        ild_db = 20.0 * math.log10(rms_right / rms_left)
        
        # 2. ITD (Interaural Time Difference) via cross-correlation
        correlation = np.correlate(right_channel, left_channel, mode='full')
        lag = np.argmax(correlation) - (len(left_channel) - 1)
        itd_seconds = float(lag / sr)
        
        # 3. Map to Azimuth (radians)
        # ITD = (d / c) * sin(theta) -> sin(theta) = ITD * c / d
        sin_theta = (itd_seconds * self.c) / self.ear_dist
        sin_theta = max(-1.0, min(1.0, float(sin_theta)))
        azimuth = math.asin(sin_theta)
        
        # 4. Map to Elevation (proxy via ILD, usually frequency-dependent in owls but simplified here)
        elevation = math.tanh(ild_db / 10.0) * (math.pi / 4)
        
        return {
            "timestamp": time.time(),
            "truth_label": "SIMULATED_SPATIAL_HEARING",
            "azimuth_rad": round(float(azimuth), 4),
            "elevation_rad": round(float(elevation), 4),
            "ild_db": round(float(ild_db), 4),
            "itd_sec": round(float(itd_seconds), 6),
            "spatial_confidence": round(float(min(1.0, (rms_left + rms_right) * 10.0)), 4)
        }

    def _default_state(self) -> Dict[str, Any]:
        return {
            "timestamp": time.time(),
            "truth_label": "SIMULATED_SPATIAL_HEARING",
            "azimuth_rad": 0.0,
            "elevation_rad": 0.0,
            "ild_db": 0.0,
            "itd_sec": 0.0,
            "spatial_confidence": 0.0
        }

    def log_localization(self, left: np.ndarray, right: np.ndarray, sr: int = 16000) -> Dict:
        OWL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        row = self.compute_localization(left, right, sr)
        with OWL_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        return row
