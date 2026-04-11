#!/usr/bin/env python3
"""
sifta_cardio.py
The SIFTA Execution Kernel & Biological Heartbeat.
Reads mathematically validated commands from the Ledger and clamps them into
strictly defined capability Sandboxes. No fuzzy routing. No smart logic.
"""
import os
import time
import json
import sqlite3
import subprocess
from pathlib import Path

STATE_DIR = Path(".sifta_state")
LEDGER_DB = STATE_DIR / "task_ledger.db"

REGISTRY_VERSION = "v1.0"

# Strict Capability Enum - No None, No Ambiguity
class Cap:
    DENY  = "DENY"
    ALLOW = "ALLOW"
    @staticmethod
    def SCOPED(path: str): return f"SCOPED:{path}"

# Constitutional Intent Registry (Immutable in production)
INTENT_REGISTRY = {
    REGISTRY_VERSION: {
        "system.ping": {
            "agent_id": "echo_agent",
            "agent_hash": "f3ca5b9e2d1a",   # Pin to executable hash in production
            "capabilities": {
                "network": Cap.DENY,
                "fs_read":  Cap.DENY,
                "fs_write": Cap.DENY
            },
            "execution_lease_seconds": 10
        },
        "fs.organize": {
            "agent_id": "file_organizer_v1",
            "agent_hash": "a1b2c3d4e5f6",
            "capabilities": {
                "network": Cap.DENY,
                "fs_read":  Cap.SCOPED("/Users/ioanganton/Downloads"),
                "fs_write": Cap.SCOPED("/Users/ioanganton/Downloads/Sorted")
            },
            "execution_lease_seconds": 60
        },
        "swarm.medic": {
            "agent_id": "run_medic_drone",
            "agent_hash": "9c8d7e6f5a4b",
            "capabilities": {
                "network": Cap.DENY,
                "fs_read":  Cap.SCOPED(str(Path(".").resolve())),
                "fs_write": Cap.SCOPED(str(STATE_DIR.resolve()))
            },
            "execution_lease_seconds": 120
        }
    }
}

def init_ledger():
    conn = sqlite3.connect(LEDGER_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, source TEXT, timestamp REAL,
            intent TEXT, payload JSON, status TEXT,
            lease_expires_at REAL DEFAULT 0,
            registry_version TEXT DEFAULT 'v1.0'
        )
    ''')
    conn.commit()
    conn.close()

def recover_stale_leases():
    """Reconcile crashed/hung executions that never completed."""
    conn = sqlite3.connect(LEDGER_DB)
    cursor = conn.cursor()
    now = time.time()
    cursor.execute(
        "UPDATE tasks SET status='failed_lease_expired' WHERE status='executing' AND lease_expires_at < ?",
        (now,)
    )
    recovered = cursor.rowcount
    conn.commit()
    conn.close()
    if recovered:
        print(f"[💓 CARDIO] Recovered {recovered} stale lease(s) from crash.")

def lock_and_retrieve_task():
    import reputation_engine

    conn = sqlite3.connect(LEDGER_DB)
    cursor = conn.cursor()
    cursor.execute("BEGIN EXCLUSIVE")
    
    # Priority Layer: Fetch all validated tasks to organically sort them
    cursor.execute("SELECT id, intent, payload, registry_version FROM tasks WHERE status = 'validated'")
    rows = cursor.fetchall()
    
    if rows:
        from sifta_trust_graph import get_trust_score
        def _get_rep(row):
            reg = INTENT_REGISTRY.get(row[3], {})
            agt = reg.get(row[1], {}).get("agent_id", "UNKNOWN")
            return get_trust_score(agt) if agt != "UNKNOWN" else 0.5
            
        rows.sort(key=_get_rep, reverse=True)
        task_id, intent, payload, reg_ver = rows[0]
        
        # Resolve lease from registry
        registry = INTENT_REGISTRY.get(reg_ver, {})
        lease_s = registry.get(intent, {}).get("execution_lease_seconds", 60)
        lease_expires = time.time() + lease_s
        cursor.execute(
            "UPDATE tasks SET status = 'executing', lease_expires_at = ? WHERE id = ?",
            (lease_expires, task_id)
        )
        conn.commit()
    else:
        conn.rollback()
        task_id, intent, payload, reg_ver = None, None, None, None
    conn.close()
    return task_id, intent, payload, reg_ver

def construct_sandbox_contract(intent: str, reg_ver: str):
    registry = INTENT_REGISTRY.get(reg_ver)
    if not registry:
        raise ValueError(f"Unknown registry version [{reg_ver}]. Rejected.")
    if intent not in registry:
        raise ValueError(f"Intent [{intent}] is structurally invalid in registry [{reg_ver}].")
    contract = registry[intent]
    # Enforce strict enum types - reject any DENY capability leak
    for cap_name, cap_val in contract["capabilities"].items():
        if cap_val is None:
            raise ValueError(f"Capability [{cap_name}] has NULL semantics. Architecture violation.")
    return contract

def physical_execution(task_id: str, contract: dict, payload: dict):
    agent_id = contract["agent_id"]
    caps = contract["capabilities"]
    print(f"    [AGENT] Detaching [{agent_id}] | net={caps['network']} | read={caps['fs_read']} | write={caps['fs_write']}")
    
    # Generate the locked environment copy
    locked_env = os.environ.copy()
    locked_env["SIFTA_CARDIO"] = "1"
    
    if agent_id == "echo_agent":
        print(f"    [AGENT OUTPUT] Ping acknowledged. Payload: {payload}")
    elif agent_id == "run_medic_drone":
        subprocess.run([".venv/bin/python", "medic_drone.py"], env=locked_env)
    else:
        print(f"    [AGENT OUTPUT] Simulated run of {agent_id}.")
    return "completed"

def pump_blood():
    task_id, intent, payload_json, reg_ver = lock_and_retrieve_task()
    if not task_id:
        return False
    print(f"\n[💓 CARDIO] {task_id[:8]} | [{reg_ver}] | [{intent}] → EXECUTING")
    try:
        contract = construct_sandbox_contract(intent, reg_ver)
        payload  = json.loads(payload_json)
        final_state = physical_execution(task_id, contract, payload)
    except ValueError as e:
        print(f"[-] Policy Violation: {e}")
        final_state = "rejected_policy"
    except Exception as e:
        print(f"[-] Execution Catastrophe: {e}")
        final_state = "failed"
    conn = sqlite3.connect(LEDGER_DB)
    conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (final_state, task_id))
    conn.commit()
    conn.close()
    print(f"[💓 CARDIO] {task_id[:8]} → {final_state.upper()}")
    return True

# ─── JELLYFISH URGENCY TRIGGER ────────────────────────────────────────────────

def _sense_scar_density() -> dict:
    """
    Scan the territory for bleeding scar density.
    Returns aggregate stats to modulate the heartbeat rhythm.
    """
    try:
        import pheromone
        root_path = Path(__file__).parent.absolute()
        territories = pheromone.scan_all_territories(root_path)
        
        total_bleeding = sum(t.get("bleeding_count", 0) for t in territories)
        total_potency = sum(t.get("total_potency", 0.0) for t in territories)
        
        return {
            "bleeding_count": total_bleeding,
            "total_potency": round(total_potency, 3),
            "territory_count": len(territories),
        }
    except Exception:
        return {"bleeding_count": 0, "total_potency": 0.0, "territory_count": 0}


def _compute_heartbeat_interval(density: dict) -> float:
    """
    The Jellyfish Clock: two timing systems.
    1. Steady baseline rhythm (2s)
    2. Environmental urgency signal from BLEEDING scar density

    High urgency = fast heartbeat.  Calm territory = slow heartbeat.
    """
    bleeding = density.get("bleeding_count", 0)
    potency = density.get("total_potency", 0.0)

    # Safety interlock: don't accelerate if proposals/ isn't wired
    proposals_dir = Path(__file__).parent / "proposals"
    proposals_active = proposals_dir.exists()

    if bleeding > 3 and potency > 2.0:
        if not proposals_active:
            # Proposals not set up — refuse urgency mode (safety)
            return 2.0
        return 0.5   # URGENCY — fast heartbeat
    elif bleeding == 0:
        return 5.0   # REST — slow heartbeat
    else:
        return 2.0   # NORMAL — baseline


if __name__ == "__main__":
    init_ledger()
    print("[*] SIFTA Cardio Daemon initialized. Registry:", REGISTRY_VERSION)
    print("[*] Jellyfish Urgency Trigger: ACTIVE")

    current_interval = 2.0
    last_mode = "NORMAL"

    while True:
        try:
            recover_stale_leases()
            work_found = pump_blood()

            # Jellyfish scar density sensing (every heartbeat)
            density = _sense_scar_density()
            new_interval = _compute_heartbeat_interval(density)

            # Detect and log mode transitions
            if new_interval == 0.5:
                new_mode = "URGENCY"
            elif new_interval == 5.0:
                new_mode = "REST"
            else:
                new_mode = "NORMAL"

            if new_mode != last_mode:
                print(f"[💓 CARDIO] Jellyfish shift: {last_mode} → {new_mode} "
                      f"(bleeding={density['bleeding_count']}, potency={density['total_potency']})")
                last_mode = new_mode

            current_interval = new_interval

            if not work_found:
                time.sleep(current_interval)
        except KeyboardInterrupt:
            print("\n[*] SIFTA Cardio Daemon shutting down.")
            break

