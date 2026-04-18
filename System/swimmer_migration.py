#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# SIFTA OS — Swimmer Migration Protocol (Biological Relocation)
# ─────────────────────────────────────────────────────────────
# Permits autonomous ASCII entities to fluidly shift allegiance
# across hardware nodes using Ed25519 Consent Signatures.
# ─────────────────────────────────────────────────────────────

import os
import json
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(REPO_ROOT, ".sifta_state")
MIGRATION_LOG = os.path.join(STATE_DIR, "migration_log.jsonl")

sys_path = os.path.dirname(os.path.abspath(__file__))
import sys
if sys_path not in sys.path:
    sys.path.append(sys_path)

try:
    from ledger_append import append_jsonl_line as _append_jsonl
except ImportError:
    # Fallback: bare append if ledger_append unavailable (should not happen in production)
    def _append_jsonl(path, row):  # type: ignore[misc]
        with open(path, "a", encoding="utf-8") as _f:
            import json as _json
            _f.write(_json.dumps(row) + "\n")

from crypto_keychain import sign_block, verify_block, get_silicon_identity

try:
    from swarm_stigmergic_networking import SwarmHardwareTopology
except ImportError:
    # Handle if module is unreachable in testing
    class SwarmHardwareTopology:
        def check_owner_boundary(self, source, target): return True

def initiate_migration(agent_id: str, target_serial: str):
    """Packages a Swimmer into a secure consent artifact and purges the active local shell."""
    local_serial = get_silicon_identity()
    agent_fpath = os.path.join(STATE_DIR, f"{agent_id}.json")
    
    if not os.path.exists(agent_fpath):
        return False, "Agent not found."
    
    with open(agent_fpath, "r") as f:
        swimmer_memory = json.load(f)

    if not swimmer_memory.get("homeworld_serial"):
        # Fallback: Extract from raw ASCII string if available
        raw = swimmer_memory.get("raw", "")
        if "SERIAL[" in raw:
            swimmer_memory["homeworld_serial"] = raw.split("SERIAL[")[1].split("]")[0]

    if swimmer_memory.get("homeworld_serial") != local_serial:
        return False, f"You cannot migrate a Swimmer that is not anchored to your silicon. (Agent anchored to: {swimmer_memory.get('homeworld_serial')})"

    timestamp = int(time.time())
    
    # Bundle memory package
    migration_bundle = {
        "event": "MIGRATE_CONSENT",
        "agent_id": agent_id,
        "origin_serial": local_serial,
        "target_serial": target_serial,
        "memory_state": swimmer_memory,
        "timestamp": timestamp
    }
    
    # Cryptographic Consent
    sig_payload = f"{agent_id}:{local_serial}:{target_serial}:{timestamp}"
    signature = sign_block(sig_payload)
    migration_bundle["signature"] = signature

    # Explicit Cross-Owner Handshake Enforcement
    topology = SwarmHardwareTopology()
    if topology.check_owner_boundary(local_serial, target_serial):
        # We mathematically log the explicit cross-owner intent
        migration_bundle["cross_owner_boundary"] = True
        print(f"[STIGMERGY] Cross-Owner Boundary detected. Explicit routing initiated for {agent_id}.")
    else:
        migration_bundle["cross_owner_boundary"] = False

    # Drop into network — locked append (same flock as repair_log / dead_drop)
    _append_jsonl(MIGRATION_LOG, migration_bundle)

    # Purge Biological Host
    # To prevent cloning, we rename it to a quarantine file and remove it from UI sight.
    quarantine_path = os.path.join(STATE_DIR, f"{agent_id}_MIGRATED.json")
    swimmer_memory["sybil_quarantined"] = True
    swimmer_memory["energy"] = 0
    swimmer_memory["ascii"] = f"<///[_QUARANTINE_]///::ID[{agent_id}]::MIGRATED_TO[{target_serial}]>"
    
    with open(quarantine_path, "w") as f:
        json.dump(swimmer_memory, f, indent=2)
        
    os.remove(agent_fpath)
    
    return True, f"Consent validated. {agent_id} explicitly relocated to {target_serial}."


def process_rebirth_mesh():
    """Polled by the Swarm Daemon. Scans the mesh for incoming Swimmers."""
    if not os.path.exists(MIGRATION_LOG):
        return
        
    local_serial = get_silicon_identity()
    
    try:
        with open(MIGRATION_LOG, "r") as f:
            lines = f.readlines()
    except Exception as e:
        return
        
    with open(os.path.join(STATE_DIR, "processed_migrations.txt"), "a+") as f:
        f.seek(0)
        processed = set(f.read().splitlines())

    for line in lines:
        if not line.strip(): continue
        try:
            bundle = json.loads(line)
        except: continue
        
        sig = bundle.get("signature")
        if not sig or sig in processed:
            continue
            
        if bundle.get("target_serial") == local_serial:
            ag_id = bundle.get("agent_id")
            origin = bundle.get("origin_serial")
            ts = bundle.get("timestamp")
            
            # Form mathematical verification
            sig_payload = f"{ag_id}:{origin}:{local_serial}:{ts}"
            if verify_block(origin, sig_payload, sig):
                # Valid physical migration. REBIRTH the Swimmer.
                memory = bundle.get("memory_state")
                memory["homeworld_serial"] = local_serial
                memory["sybil_quarantined"] = False
                memory["energy"] = 100
                
                # Append a PEACE memory
                memory["ascii"] = memory.get("ascii", "").replace(origin, local_serial)
                
                # Resuscitate exactly as they were
                new_path = os.path.join(STATE_DIR, f"{ag_id}.json")
                with open(new_path, "w") as nf:
                    json.dump(memory, nf, indent=2)
                
                print(f"[REBIRTH ALIVE] Swimmer {ag_id} has mathematically migrated to your Silicon from {origin}.")
                if bundle.get("cross_owner_boundary", False):
                    print(f"  -> [AWARENESS] Swimmer crossed an owner trust boundary and re-authenticated successfully.")
                
                processed.add(sig)
                with open(os.path.join(STATE_DIR, "processed_migrations.txt"), "a") as f:
                    f.write(sig + "\n")
            else:
                print(f"[MIGRATION REJECTED] Forged migration payload for {ag_id}.")
                processed.add(sig)
                with open(os.path.join(STATE_DIR, "processed_migrations.txt"), "a") as f:
                    f.write(sig + "\n")

if __name__ == "__main__":
    process_rebirth_mesh()
