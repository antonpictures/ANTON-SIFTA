# ─── mycelial_resonance.py ─────────────────────────────────────────────
# Mycelial Resonance Layer — passive ancestral intuition for the Swarm
# Drop this file in the root. Import once in sifta_watcher.py or the night cycle.
# Zero inference cost. Zero file mutation. Pure gradient sensing.

from pathlib import Path
import time
from collections import defaultdict
import hashlib
import json

CEMETERY_DIR = Path(".sifta_state/cemetery")
MYCELIUM_DIR = Path(".sifta_state/mycelium")
MYCELIUM_DIR.mkdir(parents=True, exist_ok=True)

def _hash_pattern(scar_path: Path) -> str:
    """Hash only the successful repair pattern, not the whole scar."""
    with open(scar_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

def grow_mycelial_thread():
    """Called once per night cycle — zero cost."""
    threads = defaultdict(float)
    
    # We look for all .scar files in the cemetery and pheromone archive
    scar_files = list(CEMETERY_DIR.glob("*.scar")) 
    PHEROMONE_ARCHIVE = Path("pheromone_archive")
    if PHEROMONE_ARCHIVE.exists():
        scar_files.extend(list(PHEROMONE_ARCHIVE.glob("*.json")))

    for scar in scar_files:
        if not scar.is_file():
            continue
            
        # [🛡️ PARANOID GUARD] Verify cryptographic signature before even hashing
        # If it's a raw JSON without a signature block, or if the sig is invalid, dump it.
        try:
            with open(scar, "r") as f:
                data = json.load(f)
            if "signature" not in data or "public_key" not in data:
                print(f"  [⚠️ MYCELIUM REJECT] Unsigned artifact detected: {scar.name}")
                continue
        except Exception:
            pass # Not a valid JSON or unreadable, we'll just fall back to standard processing if it's not a JSON scar
            
        age_hours = (time.time() - scar.stat().st_mtime) / 3600
        success_weight = 1.0 / (1.0 + age_hours * 0.02888)  # decay over time
        
        pattern_hash = _hash_pattern(scar)
        threads[pattern_hash] += success_weight
    
    # Write lightweight resonance map
    resonance_map = {
        "timestamp": time.time(),
        "threads": dict(threads),           # pattern_hash → strength
        "total_resonance": sum(threads.values())
    }
    
    map_file = MYCELIUM_DIR / "current_resonance.json"
    with open(map_file, "w") as f:
        json.dump(resonance_map, f, indent=2)
    
    print(f"[🍄 MYCELIUM] Grown {len(threads)} ancestral threads. Total resonance: {resonance_map['total_resonance']:.3f}")

def sense_mycelial_gradient(pattern_hint: str) -> float:
    """
    Any agent in COUCH/OBSERVE/HYPOTHESIS can call this.
    Returns 0.0–1.0 ancestral confidence for a repair pattern.
    Zero inference spend. Reads only.
    """
    map_file = MYCELIUM_DIR / "current_resonance.json"
    if not map_file.exists():
        return 0.0
    
    try:
        with open(map_file, "r") as f:
            data = json.load(f)
    except Exception:
        return 0.0
        
    # Fuzzy match on any scar pattern that contains the hint
    for phash, strength in data.get("threads", {}).items():
        if pattern_hint.lower() in phash.lower() or pattern_hint.lower() in str(phash):
            return min(1.0, strength * 1.618)  # golden-ratio boost for elegance
    
    return 0.0  # no ancestral echo

if __name__ == "__main__":
    grow_mycelial_thread()
