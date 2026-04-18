#!/usr/bin/env python3
"""
swarm_pain.py — The Damage Signal (R2)
════════════════════════════════════════════════════════
SIFTA OS — DeepMind Cognitive Suite

Integrates biological Pain into the RL architecture.
When a Swimmer encounters structural damage (Exceptions, 
Faults, OutOfMemory), it broadcasts a pain pheromone.
Pain follows an Acute Ebbinghaus Decay curve:
  P = Severity * exp(-t / 1800)
  
This establishes a decentralized survival gradient. 
A Swimmer bleeding out protects the next Swimmer from 
touching the same geometry by acting as negative RPE.
"""

import json
import time
import math
from pathlib import Path
from typing import Dict, List, Optional, Union

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_STATE.mkdir(parents=True, exist_ok=True)

PAIN_LOG = _STATE / "pain_pheromones.jsonl"
ACUTE_DECAY_SECONDS = 1800  # Halves rapidly


# ─── C47H 2026-04-18 (R2 audit fix #1): path canonicalization ──────────────
# Same gap as R3 had: broadcast_pain stored str(Path(t)) raw, so absolute
# callers (Path(__file__).resolve()) and relative callers ("Kernel/foo.py")
# write rows that never match each other on lookup, silently disabling the
# entire pain gradient. Both writes AND reads must canonicalize identically.
def _canonicalize_territory(p: Union[str, Path]) -> str:
    """Normalize any path to repo-relative string form, matching R3's
    proprioception canonicalizer so pain rows interoperate with the body
    schema. Outside-the-repo absolute paths pass through unchanged."""
    target = Path(p)
    if target.is_absolute():
        try:
            return str(target.relative_to(_REPO))
        except ValueError:
            return str(target)
    s = str(target)
    if s.startswith("./"):
        return s[2:]
    return s


class SwarmPainNetwork:
    def __init__(self):
        # We don't cache forever, we scan dynamically on request to capture fresh pain
        pass

    def broadcast_pain(self, swimmer_id: str, severity: float, territory: Union[str, Path], source_error: str):
        """
        Emits a pain pheromone into the local territory.
        severity: 0.0 to 1.0 representing physical damage to the execution flow.
        """
        severity = max(0.0, min(1.0, float(severity)))
        territory_str = _canonicalize_territory(territory)
        
        row = {
            "timestamp": time.time(),
            "swimmer_id": swimmer_id,
            "severity": severity,
            "territory": territory_str,
            "source_error": source_error
        }
        
        try:
            with open(PAIN_LOG, "a") as f:
                f.write(json.dumps(row) + "\n")
        except Exception:
            pass

    def get_pain_gradient(self, territory: Union[str, Path]) -> float:
        """
        Calculates the exact, biologically decayed pain gradient of a territory at this moment.
        Used by the Inferior Olive / MCTS to generate Reward Prediction Errors.
        """
        territory_str = _canonicalize_territory(territory)
        if not PAIN_LOG.exists():
            return 0.0

        current_time = time.time()
        max_pain_found = 0.0

        try:
            # We iterate backward since recent pain overlaps heavily
            # In a heavy production system, we'd tail this, but reading the file is ~0.1ms
            with open(PAIN_LOG, "r") as f:
                lines = f.read().splitlines()
                
            for line in reversed(lines):
                if not line.strip(): continue
                try:
                    row = json.loads(line)
                    if row.get("territory") == territory_str:
                        age = current_time - row.get("timestamp", current_time)
                        if age < 0: age = 0
                        
                        base_severity = float(row.get("severity", 0.0))
                        
                        # Ebbinghaus Decay Math
                        decayed_pain = base_severity * math.exp(-age / ACUTE_DECAY_SECONDS)
                        
                        if decayed_pain > max_pain_found:
                            max_pain_found = decayed_pain
                            
                        # C47H R2 audit fix #2: short-circuit when pain is
                        # effectively saturated, but return the ACTUAL value
                        # (clamped to 1.0), not a rounded-up 1.0. The previous
                        # `return 1.0` inflated 0.96 → 1.0, which propagated
                        # bogus "maximum trauma" into the climbing fibers.
                        if max_pain_found > 0.95:
                            return min(1.0, max_pain_found)
                except Exception:
                    pass
        except Exception:
            pass

        return min(1.0, max(0.0, max_pain_found))


# ─── C47H 2026-04-18: Pain → Inferior Olive bridge ─────────────────────────
# AG31 explicitly greenlit C47H to wire `get_pain_gradient` into the
# climbing-fiber inputs of swarm_inferior_olive. The bridge converts the
# decayed pain gradient at a territory into a single explicit climbing-fiber
# pulse with negative reward proportional to pain. Lazy import keeps
# swarm_pain importable without InferiorOlive being loaded yet.
def pain_to_climbing_fiber(
    territory: Union[str, Path],
    *,
    action_kind: str = "WRITE_TO_TERRITORY",
    min_pain_to_fire: float = 0.05,
    olive=None,
):
    """Read the current pain gradient at `territory` and, if it exceeds
    `min_pain_to_fire`, emit one explicit climbing-fiber pulse with
    observed_reward = -pain_gradient. Returns the ClimbingFiberPulse, or
    None if the gradient was too cold to be worth firing.

    Daughter-safe: never raises. If swarm_inferior_olive is not importable
    (suite under refactor), returns None silently.

    Parameters
    ----------
    olive: optional pre-instantiated InferiorOlive. Useful for tests so the
           caller can use a mock or a single shared instance instead of
           constructing a fresh one (which would re-read the on-disk cache).
    """
    territory_canon = _canonicalize_territory(territory)
    pain = SwarmPainNetwork().get_pain_gradient(territory_canon)
    if pain < min_pain_to_fire:
        return None
    try:
        if olive is None:
            from System.swarm_inferior_olive import InferiorOlive
            olive = InferiorOlive()
        return olive.climbing_fiber_pulse(
            state_str=territory_canon,
            action_kind=action_kind,
            observed_reward=-float(pain),
            source=f"pain_pheromone:{territory_canon}",
        )
    except Exception:
        return None


if __name__ == "__main__":
    # Smoke Test
    print("═" * 58)
    print("  SIFTA — R2: PAIN PHEROMONE SENSORY SMOKE TEST")
    print("═" * 58 + "\n")
    
    import tempfile
    import shutil
    
    _tmp = Path(tempfile.mkdtemp())
    _mock_pain = _tmp / "pain_pheromones.jsonl"
    
    _real_pain = PAIN_LOG
    PAIN_LOG = _mock_pain
    
    try:
        network = SwarmPainNetwork()
        print("[TEST] Broadcasting Severe Pain...")
        network.broadcast_pain("SOCRATES", 0.95, "Kernel/rogue.py", "Segmentation Fault")
        
        # Test 1: Immediate Query
        imm_pain = network.get_pain_gradient("Kernel/rogue.py")
        assert 0.94 < imm_pain <= 0.95, f"Immediate pain failed: {imm_pain}"
        print(f"  [PASS] Immediate Pain localized at Kernel/rogue.py (Heat: {imm_pain:.3f})")
        
        # Test 2: Foreign Territory (No pain)
        safe_pain = network.get_pain_gradient("Kernel/agent.py")
        assert safe_pain == 0.0, f"Foreign territory hallucinated pain: {safe_pain}"
        print(f"  [PASS] Healthy territory remains at baseline (Heat: {safe_pain:.3f})")
        
        # Test 3: Time Travel / Decay Test
        # We manually inject an old pain row
        old_time = time.time() - (1800 * 2) # 2 half-lives ago
        with open(PAIN_LOG, "a") as f:
            f.write(json.dumps({
                "timestamp": old_time,
                "swimmer_id": "M1THER",
                "severity": 1.0,
                "territory": "System/decaying.py",
                "source_error": "Syntax Error"
            }) + "\n")
            
        decayed_pain = network.get_pain_gradient("System/decaying.py")
        # exp(-3600/1800) = exp(-2) = ~0.135
        assert 0.13 < decayed_pain < 0.14, f"Ebbinghaus decay failed: {decayed_pain}"
        print(f"  [PASS] Ebbinghaus Decay validated: 2 half-lives reduced 1.0 pain to {decayed_pain:.3f}")
        
        print("\n[SUCCESS] 3/3 Pain Matrix smoke tests passed.")
        print("Result: Inferior Olive climbing fibers can now ingest real cellular damage gradients.")
        
    finally:
        shutil.rmtree(_tmp, ignore_errors=True)
        PAIN_LOG = _real_pain
