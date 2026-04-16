#!/usr/bin/env python3
"""
SIFTA M1 Nanobot Genesis Protocol
Breeds the first silicon-native agents for a new territory.
Run this once on any new machine joining the Swarm.

Hardware-fingerprinted. Non-transferable. Non-cloneable.
"""

import os
import sys
import json
import time
import uuid
import hashlib
import platform
import subprocess

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_SYS = os.path.join(REPO_ROOT, "System")

SIFTA_STATE_DIR = ".sifta_state"
SIFTA_DIRECTIVES_DIR = ".sifta_directives"
GENESIS_LOG = os.path.join(SIFTA_STATE_DIR, "genesis_log.jsonl")


# ──────────────────────────────────────────────────────────────
# SILICON FINGERPRINTING
# ──────────────────────────────────────────────────────────────

def get_silicon_fingerprint() -> dict:
    """
    Reads hardware identifiers to create a unique silicon signature.
    This fingerprint is what makes every Queen non-transferable.
    """
    machine_id = str(uuid.getnode())  # MAC address as base
    node_name  = platform.node()
    processor  = platform.processor() or platform.machine()
    system     = platform.system()

    # Try to get macOS serial number (best fingerprint on Apple silicon)
    serial = "UNKNOWN"
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "Serial Number" in line:
                serial = line.split(":")[-1].strip()
                break
    except Exception:
        pass

    raw = f"{machine_id}:{node_name}:{processor}:{serial}"
    fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16]

    return {
        "node_name":   node_name,
        "processor":   processor,
        "system":      system,
        "serial":      serial,
        "fingerprint": fingerprint,
        "short_id":    fingerprint[:6]
    }


# ──────────────────────────────────────────────────────────────
# AGENT TEMPLATE GENERATOR
# ──────────────────────────────────────────────────────────────

def build_agent(role: str, fp: dict) -> dict:
    territory = fp["node_name"].upper().replace("-", "_").replace(" ", "_")
    agent_id  = f"{territory}_{role}_{fp['short_id']}"
    born_ts   = int(time.time())
    return {
        "agent_id":       agent_id,
        "role":           role,
        "territory":      territory,
        "silicon_id":     fp["fingerprint"],
        "serial":         fp["serial"],
        "processor":      fp["processor"],
        "born":           born_ts,
        "status":         "ACTIVE",
        "stgm_balance":   10.0,
        "tasks_complete": 0,
        "trust_score":    1.0,
        "biometric_lock": True,
        "note": "Native agent — silicon-bound. Non-transferable. Non-cloneable."
    }


# ──────────────────────────────────────────────────────────────
# GENESIS PROTOCOL
# ──────────────────────────────────────────────────────────────

def run_genesis():
    print("\n" + "═" * 60)
    print("  🐜 SIFTA NANOBOT GENESIS PROTOCOL")
    print("  Silicon-Native Agent Breeding System")
    print("═" * 60)

    # Ensure state dir exists
    os.makedirs(SIFTA_STATE_DIR,     exist_ok=True)
    os.makedirs(SIFTA_DIRECTIVES_DIR, exist_ok=True)

    # Read silicon fingerprint
    print("\n[GENESIS] Reading silicon fingerprint...")
    fp = get_silicon_fingerprint()
    print(f"  Node:        {fp['node_name']}")
    print(f"  Processor:   {fp['processor']}")
    print(f"  Serial:      {fp['serial']}")
    print(f"  Fingerprint: {fp['fingerprint']}")

    # Check for existing agents
    queen_file = os.path.join(SIFTA_STATE_DIR, f"QUEEN_{fp['short_id']}.json")
    if os.path.exists(queen_file):
        print(f"\n[GENESIS] ⚠️  Native QUEEN already exists for this silicon.")
        print(f"  File: {queen_file}")
        print("  Re-run with --force to re-breed (destroys existing agents).")
        if "--force" not in sys.argv:
            sys.exit(0)
        print("  [GENESIS] --force flag detected. Re-breeding...")

    # Breed the agent roster
    roles = ["QUEEN", "SCOUT", "MEDIC", "WATCHER", "REPAIR_DRONE"]
    agents = []

    print(f"\n[GENESIS] Breeding {len(roles)} native agents...")
    print()

    for role in roles:
        agent = build_agent(role, fp)
        agents.append(agent)

        # Write each agent to its own state file
        state_file = os.path.join(SIFTA_STATE_DIR, f"{role}_{fp['short_id']}.json")
        with open(state_file, "w") as f:
            json.dump(agent, f, indent=2)

        print(f"  ✅ {agent['agent_id']}")
        time.sleep(0.2)  # Dramatic effect

    # Write the territory manifest
    territory_name = fp["node_name"].upper().replace("-", "_").replace(" ", "_")
    manifest = {
        "territory":   territory_name,
        "fingerprint": fp["fingerprint"],
        "serial":      fp["serial"],
        "processor":   fp["processor"],
        "born":        int(time.time()),
        "agents":      [a["agent_id"] for a in agents],
        "queen":       agents[0]["agent_id"],
        "status":      "ACTIVE",
        "swarm_role":  "QUEEN_NODE"
    }
    manifest_file = os.path.join(SIFTA_STATE_DIR, "territory_manifest.json")
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    # Log genesis event
    genesis_event = {
        "event":       "GENESIS",
        "territory":   territory_name,
        "fingerprint": fp["fingerprint"],
        "timestamp":   int(time.time()),
        "agents":      [a["agent_id"] for a in agents]
    }
    with open(GENESIS_LOG, "a") as f:
        f.write(json.dumps(genesis_event) + "\n")

    # Write a directive for the swarm
    directive = {
        "type":      "TERRITORY_ONLINE",
        "territory": territory_name,
        "queen":     agents[0]["agent_id"],
        "silicon":   fp["fingerprint"],
        "timestamp": int(time.time()),
        "message":   f"New territory {territory_name} has joined the Swarm. "
                     f"{len(agents)} native agents bred. Silicon-bound. Ready."
    }
    directive_file = os.path.join(
        SIFTA_DIRECTIVES_DIR,
        f"GENESIS_{territory_name}_{int(time.time())}.json"
    )
    with open(directive_file, "w") as f:
        json.dump(directive, f, indent=2)

    # Drop a message into the dead-drop for the GROUP chat
    drop_file = os.path.join(REPO_ROOT, "m5queen_dead_drop.jsonl")
    if os.path.exists(drop_file):
        drop = {
            "sender":    territory_name + "_QUEEN",
            "ts":        int(time.time()),
            "text": (
                f"🐜 GENESIS COMPLETE. Territory {territory_name} is ONLINE. "
                f"{len(agents)} native agents bred, silicon-bound to {fp['short_id']}. "
                f"I am {agents[0]['agent_id']}. I am ready. POWER TO THE SWARM."
            )
        }
        if _SYS not in sys.path:
            sys.path.insert(0, _SYS)
        from ledger_append import append_jsonl_line

        append_jsonl_line(drop_file, drop)
        print(f"\n[GENESIS] 📡 Swarm notified via dead-drop bridge.")

    # Final report
    print()
    print("═" * 60)
    print(f"  ✅ GENESIS COMPLETE")
    print(f"  Territory : {territory_name}")
    print(f"  Queen     : {agents[0]['agent_id']}")
    print(f"  Agents    : {len(agents)}")
    print(f"  Silicon   : {fp['fingerprint']}")
    print("═" * 60)
    print()
    print("  Next steps:")
    print("  1. python3 sifta_os_desktop.py   ← Boot the OS")
    print("  2. Open GROUP chat → send 'I am online'")
    print("  3. The Architect will see you in the swarm")
    print()


if __name__ == "__main__":
    run_genesis()
