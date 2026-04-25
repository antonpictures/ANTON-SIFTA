#!/usr/bin/env python3
import json
import os
import sys
import time
import shutil
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path so we can import Kernel
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Kernel.inference_economy import LOG_PATH as LEDGER_PATH
from System.crypto_keychain import sign_block, get_silicon_identity, _ensure_keychain

STATE_DIR = Path(".sifta_state")
ATTIC_DIR = STATE_DIR / "wallet_attic"
FROZEN_MARKER = STATE_DIR / "LEDGER_FROZEN_FOR_FEDERATION_MIGRATION"

def main():
    print("Executing Wallet Cuts 0.2 -> 0.5...")
    ATTIC_DIR.mkdir(parents=True, exist_ok=True)
    
    # ── CUT 0.3: Freeze ──────────────────────────────────────────────
    print("[Cut 0.3] Freezing ledger...")
    FROZEN_MARKER.touch(exist_ok=True)

    # ── CUT 0.4: Key Minting ─────────────────────────────────────────
    print("[Cut 0.4] Ensuring Ed25519 node keys exist...")
    _ensure_keychain()
    
    hw_serial = get_silicon_identity()
    
    # ── CUT 0.2: Reconcile ───────────────────────────────────────────
    print("[Cut 0.2] Reconciling unattributed bags...")
    
    # Group decisions
    m1_agents = ["M1SIFTA_BODY", "MACMINI.LAN", "M1THER"]
    m5_agents = ["SIFTA_QUEEN", "STRIATAL_BEAT_CLOCK", "CONVERSATION_CHAIN", 
                 "SUPERIOR_COLLICULUS", "PHYSARUM_ENGINE", "EVENT_CLOCK", 
                 "FMO_QUANTUM_ENGINE", "SYSTEM_IDE", "SHAME_REGISTRY"]
    ghosts = ["GROK_SWARMGPT", "REPAIR-DRONE", "REPAIR_DRONE_31c823", 
              "MEDIC_31c823", "WATCHER_31c823", "SCOUT_31c823", 
              "QUEEN_31c823", "MICHEL_BAUWENS", "ribosome_state"]
              
    events = []
    ts = datetime.now(timezone.utc).isoformat()
    
    for a in m1_agents:
        body = f"WALLET_RECONCILIATION::{a}::HOME[C07FL0JAQ6NV]::TS[{ts}]::NODE[{hw_serial}]"
        sig = sign_block(body)
        events.append({
            "event": "WALLET_RECONCILIATION_v1", "ts": ts, "agent_id": a,
            "homeworld_serial": "C07FL0JAQ6NV", "ed25519_sig": sig, "signing_node": hw_serial
        })
        
    for a in m5_agents:
        body = f"WALLET_RECONCILIATION::{a}::HOME[GTH4921YP3]::TS[{ts}]::NODE[{hw_serial}]"
        sig = sign_block(body)
        events.append({
            "event": "WALLET_RECONCILIATION_v1", "ts": ts, "agent_id": a,
            "homeworld_serial": "GTH4921YP3", "ed25519_sig": sig, "signing_node": hw_serial
        })
        
    for a in ghosts:
        body = f"WALLET_ARCHIVE_GHOST::{a}::TS[{ts}]::NODE[{hw_serial}]"
        sig = sign_block(body)
        events.append({
            "event": "WALLET_ARCHIVE_GHOST", "ts": ts, "agent_id": a,
            "ed25519_sig": sig, "signing_node": hw_serial
        })
        
        # Move ghost file to attic
        fpath = STATE_DIR / f"{a}.json"
        if fpath.exists():
            shutil.move(str(fpath), str(ATTIC_DIR / f"{a}.json"))
            print(f"  Moved {a}.json to wallet_attic.")

    # ── CUT 0.5: Re-baptize M1QUEEN ──────────────────────────────────
    print("[Cut 0.5] Re-baptizing M1QUEEN and demoting stale copy...")
    m1q_path = STATE_DIR / "M1QUEEN.json"
    if m1q_path.exists():
        attic_path = ATTIC_DIR / "M1QUEEN_GHOST_2026-04-23.json"
        try:
            data = json.loads(m1q_path.read_text())
            data["archived"] = True
            attic_path.write_text(json.dumps(data, indent=2))
            m1q_path.unlink()
            print("  Demoted M1QUEEN.json to M1QUEEN_GHOST_2026-04-23.json in attic.")
        except Exception as e:
            print(f"  Failed to demote M1QUEEN: {e}")
            
    # Write reconciliation rows to ledger
    with open(LEDGER_PATH, "a") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")
    print(f"  Wrote {len(events)} reconciliation events to {LEDGER_PATH}.")
            
    # Unfreeze
    print("[Unfreeze] Lifting federation migration lock.")
    if FROZEN_MARKER.exists():
        FROZEN_MARKER.unlink()
        
    print("All cuts executed successfully. The substrate is clean.")

if __name__ == "__main__":
    main()
