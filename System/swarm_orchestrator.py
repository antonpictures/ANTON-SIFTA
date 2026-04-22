#!/usr/bin/env python3
"""
System/swarm_orchestrator.py — Intrinsic Biological Motivation (Epoch 9)
════════════════════════════════════════════════════════════════════════
The Master Biological Daemon. Wakes up all living Swimmers implicitly.
If a Swimmer has hoarded enough STGM from Proof of Useful Work, this daemon
naturally executes Cell Division (Biological Mitosis).
"""

import sys
import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO / "Kernel") not in sys.path: sys.path.insert(0, str(_REPO / "Kernel"))
if str(_REPO / "System") not in sys.path: sys.path.insert(0, str(_REPO / "System"))

from body_state import load_agent_state
from swarm_reproduction import CellularMitosis

_STATE_DIR = _REPO / "Kernel" / ".sifta_state"

def wake_swimmers():
    """
    Find all biological Swimmers on disk and poke them to move.
    """
    if not _STATE_DIR.exists():
        return

    # To avoid deadlocks, run each agent externally
    print("🌊 [ORCHESTRATOR] Surging the ecosystem...")
    for body_file in _STATE_DIR.glob("*.json"):
        agent_id = body_file.stem
        
        # Ignore system files
        if agent_id in ("api_keys", "app_fitness", "apple_silicon_specs", "bishapi_alice_budget", 
                        "cherenkov_shock", "chorus_consent", "circadian_m1", "circadian_m5", 
                        "clinical_heartbeat", "clock_settings", "developmental_epoch", 
                        "energy_cortex_state", "free_energy_coefficients", "fs_pheromone", 
                        "hippocampus_last_run", "identity_stats", "intelligence_settings", 
                        "iot_devices", "m1queen_identity_anchor", "marketplace_listings", 
                        "memory_fitness", "motor_potential_coefficients", "network_cortex_state", 
                        "node_pki_registry", "olfactory_state", "optical_ghost_coefficients", 
                        "optical_ghost_energy", "optical_ghost_particles", "optical_immune_baseline", 
                        "optical_immune_coefficients", "optical_immune_state", "owner_genesis", 
                        "physical_registry", "potential_field", "scheduler_m5", "sifta_out", 
                        "speech_potential", "speech_potential_coefficients", "state_bus", 
                        "stdout", "swimmer_ollama_assignments", "territory_manifest", 
                        "thermal_cortex_state", "wm_pheromone"):
            continue
        
        # Load state to check if they are quarantined/dead
        state = load_agent_state(agent_id)
        if not state:
            continue
            
        status = state.get("style", "")
        if status == "COUCH":
            continue # Leave them sleeping or resting

        # Map Lineage to Script
        script = None
        if "SOCRATES" in agent_id:
            script = "System/socrates_agent.py"
        elif "INFRA" in agent_id:
            script = "System/infrastructure_sentinel.py"
        
        if script:
            try:
                subprocess.Popen(
                    [sys.executable, str(_REPO / script), agent_id],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                print(f"  [>] Poked {agent_id}.")
            except Exception as e:
                pass

        # ── MITOSIS CHECK ──
        # Swimmers naturally divide if they hoard enough wealth
        try:
            mitosis_engine = CellularMitosis(reproduction_cost=1000.0)
            mitosis_engine.evaluate_and_divide(agent_id)
        except Exception:
            pass

if __name__ == "__main__":
    print("=== SWARM ORCHESTRATOR ===")
    wake_swimmers()
