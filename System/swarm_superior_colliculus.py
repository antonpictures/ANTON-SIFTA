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
from typing import Dict, Optional

from System.jsonl_file_lock import append_line_locked

_REPO = Path(__file__).resolve().parent.parent
STATE_DIR = Path(".sifta_state")
COLLICULUS_LOG = STATE_DIR / "superior_colliculus.jsonl"
TRUTH_LABEL = "MULTISENSORY_SALIENCE"


def _state_root() -> Path:
    try:
        import System.swarm_body_brain_loop as _bbl

        root = getattr(_bbl, "_STATE_DIR", None)
        if root is not None:
            return Path(root).resolve()
    except Exception:
        pass
    return (_REPO / ".sifta_state").resolve()


def colliculus_ledger_path(state_root: Optional[Path] = None) -> Path:
    if state_root is not None:
        return Path(state_root) / "superior_colliculus.jsonl"
    if COLLICULUS_LOG != Path(".sifta_state/superior_colliculus.jsonl"):
        return COLLICULUS_LOG
    return _state_root() / "superior_colliculus.jsonl"


def clamp01(x: float) -> float:
    try:
        value = float(x)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _finite_float(x: float, default: float = 0.0) -> float:
    try:
        value = float(x)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value):
        return default
    return value


def angular_difference(a: float, b: float) -> float:
    """Smallest angular distance in radians."""
    return abs((a - b + math.pi) % (2.0 * math.pi) - math.pi)

class SuperiorColliculus:
    def integrate(self, 
                  visual_signal: float, visual_azimuth: float, 
                  audio_signal: float, audio_azimuth: float,
                  time_delta_sec: float) -> Dict:
        """
        Multisensory enhancement based on Meredith/Stein principles.
        """
        visual_signal = clamp01(visual_signal)
        audio_signal = clamp01(audio_signal)
        visual_azimuth = _finite_float(visual_azimuth)
        audio_azimuth = _finite_float(audio_azimuth)
        time_delta_sec = _finite_float(time_delta_sec)

        # Temporal window decay (temporal rule)
        # Decay is exponential based on time difference between visual and audio events
        temporal_alignment = math.exp(-abs(time_delta_sec) * 5.0)
        
        # Spatial alignment decay (spatial rule)
        spatial_diff = angular_difference(visual_azimuth, audio_azimuth)
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
            "ts": time.time(),
            "truth_label": TRUTH_LABEL,
            "visual_input": round(float(visual_signal), 4),
            "audio_input": round(float(audio_signal), 4),
            "visual_azimuth": round(float(visual_azimuth), 4),
            "audio_azimuth": round(float(audio_azimuth), 4),
            "time_delta_sec": round(float(time_delta_sec), 6),
            "temporal_alignment": round(float(temporal_alignment), 4),
            "spatial_alignment": round(float(spatial_alignment), 4),
            "inverse_effectiveness": round(float(inverse_eff), 4),
            "enhancement": round(float(enhancement), 4),
            "integrated_salience": round(float(salience), 4)
        }
        return row
        
    def append_integration(
        self,
        vis_sig: float,
        vis_az: float,
        aud_sig: float,
        aud_az: float,
        dt: float,
        *,
        ledger_path: Optional[Path] = None,
        state_root: Optional[Path] = None,
    ) -> Dict:
        row = self.integrate(vis_sig, vis_az, aud_sig, aud_az, dt)
        target = ledger_path or colliculus_ledger_path(state_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        append_line_locked(target, json.dumps(row, sort_keys=True) + "\n")
        return row
