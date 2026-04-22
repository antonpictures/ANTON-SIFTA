#!/usr/bin/env python3
"""
System/swarm_identity_integrity_guard.py — Swarm Wallet & Identity Integrity
════════════════════════════════════════════════════════════════════════════

Boot-time guard to ensure Alice's multi-vessel bodies and the entire node 
population strictly adhere to the STGM Quorum Ledger. 

Auto-heals two critical drift classes:
1. File/ID Mismatch (e.g. SIFTA_QUEEN.json containing "id": "OPENCLAW_QUEEN").
   Heals: Enforces that data["id"] == path.stem.
2. File/Ledger Wallet Drift (e.g. ribosome_state.json storing out-of-sync STGM).
   Heals: Overwrites local JSON wallet balance with Kernel.inference_economy.ledger_balance.

SIFTA doctrine: Storage JSONs are caches; the Quorum Ledger is the sole 
source of physical truth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any

def enforce_population_integrity() -> Dict[str, int]:
    """Walks .sifta_state/ and enforces ledger constraints across the whole swarm.
    Returns healing statistics."""
    
    repo_root = Path(__file__).resolve().parent.parent
    state_dir = repo_root / ".sifta_state"
    
    if not state_dir.exists():
        return {"scanned": 0, "healed": 0}
        
    try:
        from Kernel.inference_economy import ledger_balance
    except ImportError:
        # If economy module is missing, we gracefully bypass
        return {"scanned": 0, "healed": 0}

    stats = {"scanned": 0, "healed": 0}

    for p in state_dir.glob("*.json"):
        # Skip special indices and config files
        if p.name in {
            "api_keys.json", "active_index.json", "identity_stats.json", 
            "identity_topology.json", "swimmer_body_integrity_baseline.json", 
            "swimmer_ollama_assignments.json", "apple_silicon_specs.json",
            "free_energy_coefficients.json", "intelligence_settings.json",
            "clock_settings.json", "motor_potential_coefficients.json",
            "optical_ghost_coefficients.json", "optical_immune_baseline.json",
            "optical_immune_coefficients.json", "speech_potential.json",
            "speech_potential_coefficients.json", "state_bus.json",
            "physical_registry.json"
        }:
            continue

        try:
            raw = p.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception:
            continue
            
        if not isinstance(data, dict):
            continue
            
        # Target: Files that possess either an internal ID or an stgm_balance.
        # This identifies standard Swarm Identity vessels / nodes.
        if "id" not in data and "stgm_balance" not in data and "energy" not in data:
            continue

        stats["scanned"] += 1
        healed_this_file = False
        
        # 1. Canonical ID resolution
        target_id = p.stem
        existing_id = data.get("id", "")
        
        if existing_id.upper() != target_id.upper():
            # Apply File/ID heal. The filename corresponds to the logical node location.
            data["id"] = target_id
            healed_this_file = True

        uid = target_id
        
        # 2. Wallet synchronization from Canonical Ledger
        local_balance = float(data.get("stgm_balance", 0.0))
        true_balance = ledger_balance(uid)
        
        if abs(local_balance - true_balance) > 0.001:
            data["stgm_balance"] = round(true_balance, 4)
            healed_this_file = True

        # 3. Write back trace if healed
        if healed_this_file:
            stats["healed"] += 1
            try:
                p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                # Optional: Logging could be printed here if verbosity is desired,
                # but boot sequence values concise output.
            except Exception:
                # Read-only failure
                pass

    return stats


if __name__ == "__main__":
    import sys
    # Direct execution test runner
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    
    print("[INTEGRITY] Walking population...")
    result = enforce_population_integrity()
    print(f"[INTEGRITY] Scan complete. Scanned {result['scanned']} bodies, healed {result['healed']} wallets/IDs.")
