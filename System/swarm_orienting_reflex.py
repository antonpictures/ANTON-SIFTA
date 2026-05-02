# System/swarm_orienting_reflex.py

"""
Event 113 — Orienting Reflex
Blends hippocampal novelty with collicular salience to trigger an orienting reflex.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_STATE = Path(".sifta_state")
NOVELTY = "hippocampal_novelty_map.jsonl"
COLLICULUS = "superior_colliculus.jsonl"
REFLEX = "orienting_reflex.jsonl"


def clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def read_tail(path: Path, n: int = 1) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(errors="ignore").splitlines()[-n:]:
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def compute_orienting_reflex(state_dir: Optional[Path] = None) -> Dict[str, Any]:
    sd = state_dir if state_dir is not None else _DEFAULT_STATE
    
    novelty_rows = read_tail(sd / NOVELTY, 1)
    colliculus_rows = read_tail(sd / COLLICULUS, 1)
    
    novelty_score = 0.0
    if novelty_rows:
        novelty_score = clamp01(novelty_rows[-1].get("novelty_score", 0.0))
        
    salience = 0.0
    if colliculus_rows:
        salience = clamp01(colliculus_rows[-1].get("integrated_salience", 0.0))
        
    # Blends novelty_score with integrated_salience (plus a small cross-term)
    cross_term = novelty_score * salience
    raw_trigger = (0.5 * novelty_score) + (0.5 * salience) + (0.2 * cross_term)
    orienting_intensity = clamp01(raw_trigger)
    
    orient_trigger = bool(orienting_intensity > 0.6)
    
    attention_gain = 1.0 + (1.5 * orienting_intensity)
    memory_encode_bias = 1.0 + (1.2 * orienting_intensity)
    explore_bias = 1.0 + (0.8 * orienting_intensity)

    return {
        "ts": time.time(),
        "trace_id": str(uuid.uuid4()),
        "truth_label": "SIMULATED_ORIENTING_REFLEX",
        "novelty_score": round(novelty_score, 4),
        "integrated_salience": round(salience, 4),
        "orienting_intensity": round(orienting_intensity, 4),
        "orient_trigger": orient_trigger,
        "command": {
            "attention_gain": round(attention_gain, 4),
            "memory_encode_bias": round(memory_encode_bias, 4),
            "explore_bias": round(explore_bias, 4),
        }
    }


def write_orienting_reflex(state_dir: Optional[Path] = None) -> Dict[str, Any]:
    sd = state_dir if state_dir is not None else _DEFAULT_STATE
    sd.mkdir(parents=True, exist_ok=True)
    
    row = compute_orienting_reflex(sd)
    out_path = sd / REFLEX
    line = json.dumps(row, sort_keys=True) + "\n"
    
    try:
        from System.jsonl_file_lock import append_line_locked
        append_line_locked(out_path, line, encoding="utf-8")
    except ImportError:
        with out_path.open("a", encoding="utf-8") as f:
            f.write(line)
            
    return row

if __name__ == "__main__":
    print(json.dumps(write_orienting_reflex(), indent=2, sort_keys=True))
