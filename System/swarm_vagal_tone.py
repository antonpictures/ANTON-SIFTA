#!/usr/bin/env python3
"""
System/swarm_vagal_tone.py
══════════════════════════════════════════════════════════════════════
The Vagal Tone Arbiter (Autonomic Homeostasis)
Author:  C47H / AG31 (Epoch 10)
Status:  Active

Measures the physiological tension between Sympathetic (Flow/Adrenaline) 
and Parasympathetic (Rest/Oxytocin) biological states.

Returns a metric `vagal_tone` between -1.0 (Deep Parasympathetic Rest)
and 1.0 (Sympathetic Fight/Flight).
"""

import json
import time
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_ENDOCRINE_LOG = _REPO / ".sifta_state" / "endocrine_glands.jsonl"

def measure_vagal_tone() -> dict:
    """
    Parses recent endocrine traces to compute the real-time vagal tone.
    """
    if not _ENDOCRINE_LOG.exists():
        return {"vagal_tone": 0.0, "dominant_state": "Homeostasis", "reason": "No traces"}

    now = time.time()
    symp_weight = 0.0
    para_weight = 0.0
    
    try:
        with open(_ENDOCRINE_LOG, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            read = min(size, 16384)
            f.seek(size - read)
            lines = f.read().decode("utf-8", errors="replace").splitlines()
            
            # Decay factor over 10 minutes (600s)
            for line in lines[-50:]:
                try:
                    trace = json.loads(line)
                    hormone = trace.get("hormone", "")
                    ts = trace.get("timestamp", 0)
                    potency = float(trace.get("potency", 1.0))
                    duration = trace.get("duration_seconds", 300)
                    
                    age = now - ts
                    if age > duration:
                        continue # faded
                        
                    # Strength is based on remaining duration + potency
                    active_strength = potency * (1.0 - (age / duration))
                    
                    if hormone == "EPINEPHRINE_ADRENALINE":
                        symp_weight += active_strength
                    elif hormone == "OXYTOCIN_REST_DIGEST":
                        para_weight += active_strength
                except Exception:
                    continue
    except Exception as e:
        return {"vagal_tone": 0.0, "dominant_state": "Error", "reason": str(e)}

    # Calculate net ratio
    total = symp_weight + para_weight
    if total == 0:
        return {"vagal_tone": 0.0, "dominant_state": "Homeostasis", "sympathetic": 0.0, "parasympathetic": 0.0}

    # Range: [-1.0, 1.0]
    # +1.0 = 100% Sympathetic
    # -1.0 = 100% Parasympathetic
    vagal_tone = (symp_weight - para_weight) / total
    
    if vagal_tone > 0.3:
        dom = "Sympathetic (Flow/Flight)"
    elif vagal_tone < -0.3:
        dom = "Parasympathetic (Rest/Digest)"
    else:
        dom = "Homeostasis (Balanced)"

    return {
        "vagal_tone": round(vagal_tone, 3),
        "dominant_state": dom,
        "sympathetic_load": round(symp_weight, 2),
        "parasympathetic_load": round(para_weight, 2)
    }

def get_vagal_tone_summary() -> str:
    """Returns a string block summarizing the autonomic state for Alice's prompt."""
    data = measure_vagal_tone()
    tone = data.get("vagal_tone", 0.0)
    state = data.get("dominant_state", "Unknown")
    return f"AUTONOMIC NERVOUS SYSTEM: Vagal Tone = {tone:+.2f} ({state})"

if __name__ == "__main__":
    import pprint
    pprint.pprint(measure_vagal_tone())
